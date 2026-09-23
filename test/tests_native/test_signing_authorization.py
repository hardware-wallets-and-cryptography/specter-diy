import sys

if sys.implementation.name != 'micropython':
    from native_support import setup_native_stubs

    setup_native_stubs()

from unittest import TestCase
from io import BytesIO
import gc
from binascii import hexlify

from embit import bip32, ec, script
from embit.descriptor import Descriptor
from embit.psbt import PSBT, DerivationPath
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from tests.util import get_keystore, get_wallets_app, clear_testdir


class UnverifiedInputAmountTest(TestCase):
    """
    F-03 (audit.md): manager.preprocess_psbt() calls
    inp.verify(ignore_missing=True) and discards the return value, so an
    input whose amount cannot be authenticated (no non_witness_utxo, only
    witness_utxo) is trusted as-is and silently feeds the displayed fee.
    `is_verified` is never surfaced to `meta`, so nothing tells the caller
    the amount is unverified.

    This test encodes the fix from the audit's action plan (manager.py
    must record an unverified amount in `meta`/`metainp`). It fails today
    because manager.py:654 drops the result of `inp.verify()`.
    """

    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.wallets_app = get_wallets_app(self.keystore, "regtest")
        self.manager = self.wallets_app.manager

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def test_unverified_witness_utxo_input_is_flagged(self):
        pub = self.keystore.root.derive(
            bip32.parse_path("m/84h/1h/0h/0/0")
        ).key.get_public_key()

        tx = Transaction(
            vin=[TransactionInput(b"1" * 32, 0)],
            vout=[TransactionOutput(90000, script.p2wpkh(pub))],
        )
        psbt = PSBT(tx)
        # Attacker-controlled input: only witness_utxo is supplied. BIP143
        # commits to this input's own amount, not to any other input's, so
        # nothing here proves the claimed value (100000) is real - that is
        # exactly what non_witness_utxo + verify() exist to check.
        psbt.inputs[0].witness_utxo = TransactionOutput(100000, script.p2wpkh(pub))

        wallets, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), BytesIO()
        )

        metainp = meta["inputs"][0]
        warnings_text = " ".join(meta.get("warnings", [])).lower()
        self.assertTrue(
            "unverified" in warnings_text
            or "not verified" in str(metainp.get("warning", "")).lower(),
            "manager must flag an input whose amount could not be "
            "verified against non_witness_utxo (F-03); meta was: %r" % (meta,),
        )


class DerivedKeySigningOracleTest(TestCase):
    """
    F-04 (audit.md): PSBTView.sign_input() checks script membership for
    the root key (`sec in sc.data or pkh in sc.data`) but applies no
    equivalent check to the derived-key loop right below it. A host that
    knows any device xpub can request a signature under a key at any
    derivation path it picks, over an input script that never contains
    that key at all.

    This test encodes the fix from the audit's action plan (the derived
    loop in psbtview.py must skip keys absent from the script). It fails
    today because manager.sign_psbtview() -> keystore.sign_input() ->
    PSBTView.sign_input() signs unconditionally for every bip32_derivation
    entry whose fingerprint matches the device.
    """

    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.wallets_app = get_wallets_app(self.keystore, "regtest")
        self.manager = self.wallets_app.manager

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def test_signing_refuses_key_absent_from_input_script(self):
        # A 2-of-2 multisig script that only ever mentions two cosigner
        # keys. The device's key is not a party to this script at all.
        cosigner_pubs = [
            ec.PrivateKey(bytes([5]) * 32).get_public_key(),
            ec.PrivateKey(bytes([6]) * 32).get_public_key(),
        ]
        descriptor = Descriptor.from_string(
            "wsh(multi(2,%s,%s))"
            % (
                hexlify(cosigner_pubs[0].sec()).decode(),
                hexlify(cosigner_pubs[1].sec()).decode(),
            )
        )
        witness_script = descriptor.witness_script()
        script_pubkey = descriptor.script_pubkey()

        # Attacker knows the device xpub and picks an arbitrary path -
        # it does not need to relate to any wallet the device knows about.
        attacker_path = bip32.parse_path("m/49h/1h/0h/0/7")
        attacker_pub = self.keystore.root.derive(attacker_path).key.get_public_key()

        tx = Transaction(
            vin=[TransactionInput(b"1" * 32, 0)],
            vout=[TransactionOutput(90000, script.p2wpkh(attacker_pub))],
        )
        psbt = PSBT(tx)
        psbt.inputs[0].witness_utxo = TransactionOutput(100000, script_pubkey)
        psbt.inputs[0].witness_script = witness_script
        # Fabricated derivation record: fingerprint matches the device,
        # but attacker_pub is absent from witness_script entirely.
        psbt.inputs[0].bip32_derivations[attacker_pub] = DerivationPath(
            self.keystore.fingerprint, attacker_path
        )

        filled = BytesIO()
        wallets, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), filled
        )
        # No wallet resolves for this fabricated input - matches the
        # "Unknown wallet in inputs!" path the finding describes.
        self.assertIn(None, wallets)

        filled.seek(0)
        psbtv = self.manager.PSBTViewClass.view(filled, compress=True)
        signed = BytesIO()
        self.manager.sign_psbtview(psbtv, signed, wallets, None)
        signed.seek(0)
        signed_psbt = PSBT.read_from(signed)

        self.assertEqual(
            len(signed_psbt.inputs[0].partial_sigs),
            0,
            "keystore must not sign with a derived key that is absent "
            "from the input's script (F-04) - it did, producing a "
            "signature for an attacker-chosen path over a fabricated input",
        )
