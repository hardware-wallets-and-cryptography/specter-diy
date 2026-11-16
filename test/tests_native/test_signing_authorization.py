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
from tests.util import get_keystore, get_wallets_app, clear_testdir, add_previous_txs
from apps.wallets.manager import MISSING_PREVIOUS_TX_ERROR
from apps.wallets.wallet import WalletError


class UnverifiedInputAmountTest(TestCase):
    """F-03 (audit.md): unverified input amounts must be rejected before the
    confirmation screen."""

    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.wallets_app = get_wallets_app(self.keystore, "regtest")
        self.manager = self.wallets_app.manager

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def test_unverified_witness_utxo_input_is_rejected(self):
        pub = self.keystore.root.derive(
            bip32.parse_path("m/84h/1h/0h/0/0")
        ).key.get_public_key()

        tx = Transaction(
            vin=[TransactionInput(b"1" * 32, 0)],
            vout=[TransactionOutput(90000, script.p2wpkh(pub))],
        )
        psbt = PSBT(tx)
        # Without non_witness_utxo, the claimed value cannot be authenticated.
        psbt.inputs[0].witness_utxo = TransactionOutput(100000, script.p2wpkh(pub))

        with self.assertRaises(
            WalletError,
            msg="manager must reject an input whose amount could not be "
            "verified against non_witness_utxo (F-03 (audit.md))",
        ) as ctx:
            self.manager.preprocess_psbt(BytesIO(psbt.serialize()), BytesIO())
        self.assertEqual(str(ctx.exception), MISSING_PREVIOUS_TX_ERROR)

class DerivedKeySigningOracleTest(TestCase):
    """F-04 (audit.md): keys absent from input scripts must not be signed."""

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
        add_previous_txs(psbt)

        filled = BytesIO()
        wallets, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), filled
        )
        # No wallet resolves for this fabricated input - matches the
        # "Unknown wallet in inputs!" path the finding describes.
        self.assertIn(None, wallets)

        filled.seek(0)
        psbtv = self.manager.PSBTViewClass.view(filled, compress=True)

        # Security boundary: the keystore itself must refuse to sign.
        sig_stream = BytesIO()
        sig_count = self.keystore.sign_input(
            psbtv, 0, sig_stream, self.manager.DEFAULT_SIGHASH, psbtv.input(0)
        )
        self.assertEqual(
            sig_count,
            0,
            "keystore must not sign with a derived key that is absent "
            "from the input's script (F-04 (audit.md)) - it did, producing a "
            "signature for an attacker-chosen path over a fabricated input",
        )

        # End-to-end: the manager surfaces the refusal as an error.
        with self.assertRaises(
            WalletError,
            msg="sign_psbtview must reject a PSBT the keystore refused to "
            "sign (F-04 (audit.md)) instead of returning it",
        ) as ctx:
            self.manager.sign_psbtview(psbtv, BytesIO(), wallets, None)
        self.assertIn("didn't add any signatures", str(ctx.exception))
