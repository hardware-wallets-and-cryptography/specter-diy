import asyncio
import unittest
from types import SimpleNamespace

import pyb

if not hasattr(pyb, "Pin"):
    pyb.Pin = SimpleNamespace(
        cpu=SimpleNamespace(A2=None, A4=None, G10=None, C2=None, C5=None)
    )

from keystore.javacard.applets.secureapplet import SecureApplet
from keystore.memorycard import MemoryCard


class _UnlockedCard:
    def __init__(self):
        self.requests = []

    def request(self, command):
        self.requests.append(command)
        if command == SecureApplet.PIN_STATUS:
            return bytes((3, 3, SecureApplet.PIN_UNLOCKED))
        if command.startswith(SecureApplet.UNLOCK):
            return b""
        raise AssertionError("Unexpected card request: %r" % command)


def _untrusted_applet():
    applet = object.__new__(SecureApplet)
    applet.sc = _UnlockedCard()
    applet._pin_attempts_left = None
    applet._pin_attempts_max = None
    applet._pin_status = None
    return applet


class CardStatusEvidence(unittest.TestCase):
    def test_claimed_unlocked_status_does_not_skip_pin_prompt(self):
        applet = _untrusted_applet()
        keystore = object.__new__(MemoryCard)
        keystore.applet = applet
        keystore.show_loader = lambda _message: None
        prompted = []

        async def get_pin():
            prompted.append(True)
            return "1234"

        keystore.get_pin = get_pin
        keystore._unlock = applet.unlock
        asyncio.run(keystore.unlock())

        self.assertEqual(
            prompted,
            [True],
            "F-22: the card's PIN_UNLOCKED response skipped the boot PIN prompt",
        )

    def test_claimed_unlocked_status_does_not_skip_applet_unlock(self):
        applet = _untrusted_applet()
        applet.unlock("1234")
        self.assertTrue(
            any(
                command.startswith(SecureApplet.UNLOCK)
                for command in applet.sc.requests
            ),
            "F-22: SecureApplet trusted PIN_UNLOCKED and never sent a PIN",
        )
