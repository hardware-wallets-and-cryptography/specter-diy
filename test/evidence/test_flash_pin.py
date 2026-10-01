import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import keystore.flash as flash
from helpers import tagged_hash


class _DeviceHmac:
    @staticmethod
    def new(key, msg=None, digestmod=None):
        if isinstance(msg, str):
            msg = msg.encode()
        return hmac.new(key, msg, digestmod)


class FlashPinEvidence(unittest.TestCase):
    def test_flash_dump_cannot_check_short_pin_with_one_hmac_per_guess(self):
        with tempfile.TemporaryDirectory() as path, patch.object(flash, "hmac", _DeviceHmac):
            keystore = flash.FlashKeyStore()
            keystore.path = path
            keystore.load_secret(path)
            keystore.load_state()
            keystore._set_pin("0042")
            del keystore

            secret = (Path(path) / "secret").read_bytes()
            attacker = flash.FlashKeyStore()
            _, record = attacker.load_aead(str(Path(path) / "pin"), secret)
            verifier = bytes.fromhex(json.loads(record.decode())["pin"])

            key = tagged_hash("pin", secret)
            recovered = None
            for guess in range(10000):
                candidate = "%04d" % guess
                if hmac.compare_digest(
                    hmac.new(key, candidate.encode(), "sha256").digest(),
                    verifier,
                ):
                    recovered = candidate
                    break

            if recovered is not None:
                pin_secret = tagged_hash("pin", secret + recovered.encode())
                _, unwrapped = attacker.load_aead(
                    str(Path(path) / "enc_secret"), pin_secret
                )
                self.assertEqual(len(unwrapped), 32)

            self.assertIsNone(
                recovered,
                "F-06: flash records revealed PIN %s after %d offline HMACs; "
                "the attempt counter was never consulted"
                % (recovered, guess + 1),
            )
