from unittest import TestCase
from keystore import FlashKeyStore
import os
import platform
import rng

TEST_DIR = "testdir"
PIN = "1234"
FILES = ("secret", "pin", "enc_secret")

def init_keystore(ks):
    platform.maybe_mkdir(ks.path)
    ks.load_secret(ks.path)
    ks.load_state()
    ks.initialized = True

class FlashKeyStoreTest(TestCase):

    def get_keystore(self):
        """Clean up the test folder and create fresh keystore"""
        try:
            platform.delete_recursively(TEST_DIR)
            os.rmdir(TEST_DIR)
        except:
            pass
        FlashKeyStore.path = TEST_DIR
        return FlashKeyStore()

    def test_create_config(self):
        """Test initial config creation"""
        ks = self.get_keystore()
        init_keystore(ks)
        files = [f[0] for f in os.ilistdir(TEST_DIR)]
        self.assertTrue("secret" in files)
        self.assertTrue("pin" in files)
        self.assertEqual(ks.is_pin_set, False)
        self.assertEqual(ks.pin_attempts_left, ks.pin_attempts_max)
        self.assertTrue(ks.pin_attempts_left is not None)

    def test_change_secret(self):
        """Test wipe exception if secret is changed"""
        # create keystore
        ks = self.get_keystore()
        init_keystore(ks)
        files = [f[0] for f in os.ilistdir(TEST_DIR)]
        self.assertTrue("secret" in files)
        self.assertTrue("pin" in files)
        # now change secret value
        with open(TEST_DIR+"/secret", "wb") as f:
            # a different value
            f.write(b"5"*32)
        ks = FlashKeyStore()
        # check it raises
        with self.assertRaises(platform.CriticalErrorWipeImmediately):
            init_keystore(ks)
        # files are deleted
        files = [f[0] for f in os.ilistdir(TEST_DIR)]
        self.assertFalse("secret" in files)
        self.assertFalse("pin" in files)

    def test_change_pin_file(self):
        """Test wipe exception if pin state changed"""
        # create keystore
        ks = self.get_keystore()
        init_keystore(ks)
        # load signed pin state
        with open(TEST_DIR+"/pin", "rb") as f:
            # a different value
            content = f.read()
        # set invalid value
        content = content[1:] + b"1"
        # write new state
        with open(TEST_DIR+"/pin", "wb") as f:
            # a different value
            f.write(content)
        ks = FlashKeyStore()
        # check it raises
        with self.assertRaises(platform.CriticalErrorWipeImmediately):
            init_keystore(ks)
        # files are deleted
        files = [f[0] for f in os.ilistdir(TEST_DIR)]
        self.assertFalse("secret" in files)
        self.assertFalse("pin" in files)


def _dead_trng(nbytes):
    # a stalled STM32 TRNG: rng_get() returns 0 on timeout and os.urandom()
    # calls it once per byte
    return b"\x00" * nbytes


def _read(name):
    with open(TEST_DIR + "/" + name, "rb") as f:
        return f.read()


def _files():
    return [f[0] for f in os.ilistdir(TEST_DIR)]


class FlashKeyStoreRNGFailureTest(TestCase):
    """A dead TRNG during PIN entry must raise RNGError, not wipe the device"""

    def setUp(self):
        self.trng = rng.get_trng_bytes

    def tearDown(self):
        rng.get_trng_bytes = self.trng

    def get_locked_keystore(self, attempts_left=None):
        try:
            platform.delete_recursively(TEST_DIR)
            os.rmdir(TEST_DIR)
        except:
            pass
        FlashKeyStore.path = TEST_DIR
        ks = FlashKeyStore()
        init_keystore(ks)
        ks._set_pin(PIN)
        if attempts_left is not None:
            ks._pin_attempts_left = attempts_left
            ks.save_state()
        ks.lock()
        return ks

    def test_dead_trng_on_unlock_raises_rng_error_without_wiping(self):
        ks = self.get_locked_keystore()
        attempts = ks.pin_attempts_left
        before = [_read(name) for name in FILES]
        rng.get_trng_bytes = _dead_trng
        # correct and wrong PIN alike: the TRNG fails before the PIN is checked
        for pin in (PIN, "0000"):
            with self.assertRaises(rng.RNGError):
                ks._unlock(pin)
            self.assertEqual(ks.pin_attempts_left, attempts)
            self.assertTrue(ks.is_locked)
        # nothing deleted, nothing rewritten
        self.assertEqual([_read(name) for name in FILES], before)
        # the counter on flash agrees with the one in memory
        rng.get_trng_bytes = self.trng
        reloaded = FlashKeyStore()
        init_keystore(reloaded)
        self.assertEqual(reloaded.pin_attempts_left, attempts)
        # the device works again once the TRNG recovers
        ks._unlock(PIN)
        self.assertFalse(ks.is_locked)
        self.assertEqual(ks.pin_attempts_left, ks.pin_attempts_max)

    def test_dead_trng_on_last_attempt_keeps_the_counter_enforced(self):
        ks = self.get_locked_keystore(attempts_left=1)
        rng.get_trng_bytes = _dead_trng
        with self.assertRaises(rng.RNGError):
            ks._unlock("0000")
        self.assertEqual(ks.pin_attempts_left, 1)
        for name in FILES:
            self.assertIn(name, _files())
        # with the TRNG back, the last attempt still wipes
        rng.get_trng_bytes = self.trng
        with self.assertRaises(platform.CriticalErrorWipeImmediately):
            ks._unlock("0000")
        self.assertFalse("secret" in _files())
        self.assertFalse("pin" in _files())

    def test_dead_trng_after_correct_pin_keeps_the_keystore_locked(self):
        ks = self.get_locked_keystore()
        attempts = ks.pin_attempts_left
        save_state = ks.save_state
        calls = []

        # the decrement is saved, then the TRNG dies before the reset is saved
        def save_state_trng_dies_on_reset():
            calls.append(1)
            if len(calls) == 2:
                rng.get_trng_bytes = _dead_trng
            save_state()

        ks.save_state = save_state_trng_dies_on_reset
        with self.assertRaises(rng.RNGError):
            ks._unlock(PIN)
        self.assertTrue(ks.is_locked)
        # memory agrees with flash: one attempt used, not reset
        self.assertEqual(ks.pin_attempts_left, attempts - 1)
        rng.get_trng_bytes = self.trng
        reloaded = FlashKeyStore()
        init_keystore(reloaded)
        self.assertEqual(reloaded.pin_attempts_left, attempts - 1)
        # the device unlocks once the TRNG recovers
        ks.save_state = save_state
        ks._unlock(PIN)
        self.assertFalse(ks.is_locked)
        self.assertEqual(ks.pin_attempts_left, ks.pin_attempts_max)

    def test_other_errors_while_saving_the_counter_still_wipe(self):
        ks = self.get_locked_keystore()

        def broken_save_state():
            raise OSError(28)

        ks.save_state = broken_save_state
        with self.assertRaises(platform.CriticalErrorWipeImmediately):
            ks._unlock(PIN)
