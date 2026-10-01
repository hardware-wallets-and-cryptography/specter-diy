import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rng


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STM32 = ROOT / "f469-disco/micropython/ports/stm32"


class NativeRngEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="specter-rng-evidence-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.executable = Path(cls.build.name) / "rng_driver"
        subprocess.run(
            [
                os.environ.get("CC", "cc"),
                "-I" + str(HERE),
                "-I" + str(STM32),
                "-include",
                str(HERE / "rng_stubs.h"),
                str(STM32 / "rng.c"),
                str(HERE / "rng_driver.c"),
                "-o",
                str(cls.executable),
            ],
            check=True,
            capture_output=True,
        )

    def test_healthy_peripheral_returns_its_word(self):
        result = subprocess.run([self.executable, "healthy"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_timeout_reports_failure(self):
        self._assert_fault("timeout")

    def test_seed_error_during_wait_reports_failure(self):
        self._assert_fault("seed")

    def test_clock_error_with_ready_data_reports_failure(self):
        self._assert_fault("clock")

    def _assert_fault(self, fault):
        result = subprocess.run([self.executable, fault], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class RNGFailurePropagationEvidence(unittest.TestCase):
    def test_hardware_read_failure_is_an_rng_error_without_feeding_pool(self):
        original_pool = rng.entropy_pool
        rng.entropy_pool = b"A" * 64
        self.addCleanup(setattr, rng, "entropy_pool", original_pool)
        with patch.object(rng, "get_trng_bytes", side_effect=OSError(5, "RNG fault")):
            try:
                rng.get_random_bytes(32)
            except rng.RNGError:
                pass
            except OSError:
                self.fail("F-18: a hardware failure escaped without an RNGError")
            else:
                self.fail("F-18: a hardware failure was not reported")
        self.assertEqual(rng.entropy_pool, b"A" * 64)
