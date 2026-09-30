import sys

if sys.implementation.name != 'micropython':
    from native_support import setup_native_stubs

    setup_native_stubs()

from unittest import TestCase, expectedFailure
import hmac as _hmac
import json
import shutil
import tempfile
import time

import keystore.flash as flash
from keystore.flash import FlashKeyStore
from keystore.core import PinError


class _StrHmac:
    """
    The device's native `hmac` (usermods/uhashlib/uhmac.c:82-87) reads `msg`
    through the buffer protocol, so a str is hashed as its UTF-8 bytes.
    CPython's hmac rejects str. `_set_pin` passes the PIN as str
    (flash.py:178), so encode it here to match the device.
    """

    @staticmethod
    def new(key, msg=None, digestmod=None):
        if isinstance(msg, str):
            msg = msg.encode()
        return _hmac.new(key, msg, digestmod)


class _FlashPinTestBase(TestCase):
    PIN = "1234"

    def setUp(self):
        self._orig_hmac = flash.hmac
        flash.hmac = _StrHmac
        self.path = tempfile.mkdtemp()
        self.ks = self._new_keystore()
        self.ks._set_pin(self.PIN)

    def tearDown(self):
        flash.hmac = self._orig_hmac
        shutil.rmtree(self.path, ignore_errors=True)

    def _new_keystore(self):
        ks = FlashKeyStore()
        ks.path = self.path
        ks.load_secret(self.path)
        ks.load_state()
        return ks


class PinKeySeparationTest(_FlashPinTestBase):
    """
    F-06 (audit.md): the PIN verifier stored in flash must never be the key
    that unwraps `enc_secret`. If it were, reading flash would give the
    unwrapping key directly, with no PIN guessing at all.

    Attacker model: full read of internal flash, i.e. the device `secret`,
    the `/pin` record (decryptable with `secret`), and `enc_secret`.

    These tests pass on the current HMAC scheme. They must keep passing after
    the F-06 KDF change: a version that stores the KDF output as the verifier
    and also uses it as `pin_secret` fails them.
    """

    def _stored_verifier(self):
        # what an attacker recovers from a flash dump
        _, data = self.ks.load_aead(self.path + "/pin", self.ks.secret)
        return bytes.fromhex(json.loads(data.decode())["pin"])

    def test_verifier_is_not_the_unwrapping_key(self):
        self.assertIsNotNone(self.ks.pin_secret)
        self.assertNotEqual(self.ks.pin, self.ks.pin_secret)
        self.assertNotEqual(self._stored_verifier(), self.ks.pin_secret)

    def test_flash_contents_do_not_unwrap_enc_secret(self):
        enc_path = self.path + "/enc_secret"
        # sanity: the real key does unwrap it, so the negative checks are meaningful
        _, secret = self.ks.load_aead(enc_path, self.ks.pin_secret)
        self.assertEqual(secret, self.ks.enc_secret)
        # nothing readable from flash without the PIN may unwrap it
        for key in (self._stored_verifier(), self.ks.secret):
            with self.assertRaises(Exception):
                self.ks.load_aead(enc_path, key)

    def test_unlock_rederives_the_same_unwrapping_key(self):
        ks = self._new_keystore()
        ks._unlock(self.PIN)
        self.assertEqual(ks.pin_secret, self.ks.pin_secret)
        self.assertEqual(ks.enc_secret, self.ks.enc_secret)

    def test_wrong_pin_derives_no_unwrapping_key(self):
        ks = self._new_keystore()
        with self.assertRaises(PinError):
            ks._unlock("9999")
        self.assertIsNone(ks.pin_secret)
        self.assertIsNone(ks.enc_secret)

    def test_change_pin_rewraps_enc_secret_under_new_key(self):
        old_key = self.ks.pin_secret
        enc_secret = self.ks.enc_secret
        self.ks._change_pin(self.PIN, "5678")
        self.assertNotEqual(self.ks.pin_secret, old_key)
        self.assertNotEqual(self.ks.pin, self.ks.pin_secret)
        ks = self._new_keystore()
        ks._unlock("5678")
        self.assertEqual(ks.enc_secret, enc_secret)


class PinGuessCostTest(_FlashPinTestBase):
    """
    F-06 (audit.md): checking one PIN guess costs one fast HMAC, so a flash
    dump lets an attacker try every short PIN offline almost instantly.

    This measures the cost of the keystore's own PIN check on wrong guesses,
    with file writes stubbed out. It checks the property, not a formula, so
    it also catches a later cut of the KDF iteration count.

    Expected to fail until the F-06 KDF change lands. Today a guess costs
    microseconds on the host. PBKDF2-SHA256 at 200k iterations costs tens of
    milliseconds. The 5 ms threshold sits between the two with a wide margin.
    When the fix lands this reports an unexpected success, which fails the
    run: remove `@expectedFailure` then.
    """

    GUESSES = 20
    MIN_SECONDS_PER_GUESS = 0.005

    @expectedFailure
    def test_offline_pin_guess_is_expensive(self):
        ks = self._new_keystore()
        # measure the PIN check only, not flash writes
        ks.save_state = lambda: None
        ks.load_enc_secret = lambda: None
        start = time.perf_counter()
        for i in range(self.GUESSES):
            ks._pin_attempts_left = ks._pin_attempts_max
            with self.assertRaises(PinError):
                ks._unlock("%04d" % (9000 + i))
        per_guess = (time.perf_counter() - start) / self.GUESSES
        self.assertGreaterEqual(per_guess, self.MIN_SECONDS_PER_GUESS)
