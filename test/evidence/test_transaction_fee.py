import gc
import unittest
from io import BytesIO

from embit import bip32, script
from embit.psbt import PSBT
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from tests.util import clear_testdir, get_keystore, get_wallets_app


class TransactionFeeEvidence(unittest.TestCase):
    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.manager = get_wallets_app(self.keystore, "regtest").manager
        self.pub = self.keystore.root.derive(
            bip32.parse_path("m/84h/1h/0h/0/0")
        ).key.get_public_key()

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def _metadata_for_fee(self, input_value, output_value):
        destination = script.p2wpkh(self.pub)
        prevtx = Transaction(
            vin=[TransactionInput(b"0" * 32, 0)],
            vout=[TransactionOutput(input_value, destination)],
        )
        tx = Transaction(
            vin=[TransactionInput(prevtx.txid(), 0)],
            vout=[TransactionOutput(output_value, destination)],
        )
        psbt = PSBT(tx)
        psbt.inputs[0].non_witness_utxo = prevtx
        _, meta = self.manager.preprocess_psbt(
            BytesIO(psbt.serialize()), BytesIO()
        )
        self.assertEqual(meta["fee"], input_value - output_value)
        return meta

    def test_extreme_fee_requires_a_visible_warning(self):
        meta = self._metadata_for_fee(100_000, 50_000)
        self.assertTrue(
            any("fee" in warning.lower() for warning in meta.get("warnings", [])),
            "F-24: a 50% fee reached confirmation without a fee warning",
        )

    def test_negative_fee_requires_a_visible_warning(self):
        meta = self._metadata_for_fee(100_000, 101_000)
        self.assertTrue(
            any("fee" in warning.lower() for warning in meta.get("warnings", [])),
            "F-24: a negative fee was displayed without a warning",
        )
