import gc
from binascii import hexlify
from io import BytesIO
from unittest import TestCase

from embit import bip32, ec, script
from embit.descriptor import Descriptor
from embit.psbt import PSBT, DerivationPath
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from tests.util import clear_testdir, get_keystore, get_wallets_app


class SigningAuthorizationEvidence(TestCase):
    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.wallets_app = get_wallets_app(self.keystore, "regtest")
        self.manager = self.wallets_app.manager

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def test_unverified_second_input_cannot_produce_an_unqualified_fee(self):
        pub = self.keystore.root.derive(
            bip32.parse_path("m/84h/1h/0h/0/0")
        ).key.get_public_key()
        prevtx = Transaction(
            vin=[TransactionInput(b"0" * 32, 0)],
            vout=[TransactionOutput(100000, script.p2wpkh(pub))],
        )
        tx = Transaction(
            vin=[
                TransactionInput(prevtx.txid(), 0),
                TransactionInput(b"2" * 32, 0),
            ],
            vout=[TransactionOutput(190000, script.p2wpkh(pub))],
        )
        psbt = PSBT(tx)
        psbt.inputs[0].non_witness_utxo = prevtx
        # The host can change this unauthenticated amount independently of
        # input 0's signature, making the displayed fee look much smaller.
        psbt.inputs[1].witness_utxo = TransactionOutput(
            100000, script.p2wpkh(pub)
        )

        _, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), BytesIO()
        )

        self.assertEqual(meta["fee"], 10000)
        self.assertNotIn("warning", meta["inputs"][0])
        self.assertIn("NOT verified", meta["inputs"][1]["warning"])
        with self.subTest("visible warning"):
            self.assertIn(
                "unverified",
                " ".join(meta.get("warnings", [])).lower(),
                "the primary confirmation screen only displays meta['warnings']; "
                "per-input metadata alone does not warn the user (F-03)",
            )
        with self.subTest("fee provenance"):
            self.assertIs(
                meta.get("fee_verified"),
                False,
                "an unauthenticated input must never produce a verified fee (F-03)",
            )

    def test_signing_refuses_script_not_committed_by_verified_prevtx(self):
        attacker_path = bip32.parse_path("m/49h/1h/0h/0/7")
        attacker_pub = self.keystore.root.derive(
            attacker_path
        ).key.get_public_key()
        cosigner = ec.PrivateKey(bytes([5]) * 32).get_public_key()
        other_cosigner = ec.PrivateKey(bytes([6]) * 32).get_public_key()

        supplied_script = Descriptor.from_string(
            "wsh(multi(2,%s,%s))"
            % (hexlify(attacker_pub.sec()).decode(), hexlify(cosigner.sec()).decode())
        )
        committed_script = Descriptor.from_string(
            "wsh(multi(2,%s,%s))"
            % (hexlify(cosigner.sec()).decode(), hexlify(other_cosigner.sec()).decode())
        )
        prevtx = Transaction(
            vin=[TransactionInput(b"0" * 32, 0)],
            vout=[TransactionOutput(100000, committed_script.script_pubkey())],
        )
        tx = Transaction(
            vin=[TransactionInput(prevtx.txid(), 0)],
            vout=[TransactionOutput(90000, script.p2wpkh(attacker_pub))],
        )
        psbt = PSBT(tx)
        psbt.inputs[0].non_witness_utxo = prevtx
        psbt.inputs[0].witness_script = supplied_script.witness_script()
        psbt.inputs[0].bip32_derivations[attacker_pub] = DerivationPath(
            self.keystore.fingerprint, attacker_path
        )

        filled = BytesIO()
        wallets, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), filled
        )
        self.assertIn(None, wallets)
        self.assertNotIn("warning", meta["inputs"][0])
        self.assertNotEqual(
            script.p2wsh(supplied_script.witness_script()),
            prevtx.vout[0].script_pubkey,
        )

        filled.seek(0)
        psbtv = self.manager.PSBTViewClass.view(filled, compress=True)
        self.assertTrue(psbtv.input(0).verify())
        signed = BytesIO()
        self.manager.sign_psbtview(psbtv, signed, wallets, None)
        signed.seek(0)
        signed_psbt = PSBT.read_from(signed)

        self.assertNotIn(
            attacker_pub,
            signed_psbt.inputs[0].partial_sigs,
            "a verified prevtx does not authorize an unrelated witness_script; "
            "signing with this derived key is still possible (F-04)",
        )
