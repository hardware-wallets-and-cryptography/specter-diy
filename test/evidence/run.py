"""Run deliberately failing security-property tests outside normal CI."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
TEST_ROOT = HERE.parent
ROOT = TEST_ROOT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(TEST_ROOT))
sys.path.insert(1, str(ROOT / "src"))
sys.path.insert(2, str(ROOT / "f469-disco/libs/common/embit/src"))
sys.path.append(str(ROOT / "f469-disco/libs/common"))
sys.path.append(str(ROOT / "f469-disco/libs/unix"))
sys.path.append(str(ROOT / "f469-disco/usermods/udisplay_f469/display_unixport"))
sys.path.append(str(ROOT / "f469-disco/tests"))

from native_support import setup_native_stubs


def main():
    setup_native_stubs()
    with tempfile.TemporaryDirectory(prefix="specter-evidence-") as build_dir:
        original_dir = Path.cwd()
        try:
            os.chdir(build_dir)
            suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=2).run(suite)

            from test_message_authorization import write_firmware_signature_fixture

            fixture = Path(build_dir) / "firmware_signature.bin"
            write_firmware_signature_fixture(fixture)
            bootloader = subprocess.run(
                [
                    "make",
                    "-s",
                    "-f",
                    "test/Makefile",
                    "TARGET=security_evidence",
                    "CMN_ROOT=" + str(ROOT / "bootloader"),
                    "BUILD_DIR_ROOT=" + build_dir,
                    "CPP_SOURCES=test/test_main.cpp ../test/evidence/test_firmware_domain.cpp ../test/evidence/test_firmware_integrity.cpp",
                    "test",
                ],
                cwd=ROOT / "bootloader",
                env={**os.environ, "SPECTER_EVIDENCE_SIGNATURE": str(fixture)},
                check=False,
            )
        finally:
            os.chdir(original_dir)
    return 0 if result.wasSuccessful() and bootloader.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
