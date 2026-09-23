import sys

if sys.implementation.name != 'micropython':
    from native_support import setup_native_stubs

    setup_native_stubs()

from unittest import TestCase
from io import BytesIO
from binascii import b2a_base64
import asyncio
import gc

import apps.signmessage.signmessage as signmessage_mod
from apps.signmessage.signmessage import MessageApp
from tests.util import get_keystore, clear_testdir
import platform

TEST_DIR = "testdir"


class _RecordingPrompt:
    """
    Stand-in for gui.screens.Prompt. Records the exact (title, msg)
    strings the real GUI would receive, instead of touching lvgl.
    """

    last_msg = None

    def __init__(self, title, msg):
        _RecordingPrompt.last_msg = msg
        self.title = title
        self.msg = msg


async def _approve(scr):
    return True


class MessageSigningDisplayTest(TestCase):
    """
    F-21 (audit.md): signmessage.py's only content check is
    `message.decode("ascii")` inside a bare `except:` - an embedded NUL
    byte decodes without error (NUL is legal ASCII/UTF-8), so the hex
    fallback never runs and the raw text - hidden tail included - is
    handed straight to the label. `sign_message()` then hashes the
    complete byte string. The recommended fix (audit action-plan item 1)
    is an explicit printable-byte check that routes anything containing
    a control byte to the hex-dump branch instead.

    This test encodes that fix and fails today: it asserts a message
    containing a NUL must be shown as a hex dump, and that no hidden
    attacker text ever appears in the displayed string. Right now the
    ascii-decode branch is taken instead, so both assertions fail.

    Coverage note - MicroPython-specific gap (partial coverage):
    this suite runs under CPython, not the pinned MicroPython fork, so
    two things the finding cites are NOT reproduced or asserted here:
      - `objstr.c`'s `bytes.decode()` throwing away the `encoding`
        argument and substituting utf-8 (`py/objstr.c:157`), which is
        what additionally lets non-ASCII homoglyph / U+202E
        right-to-left-override bytes through a call that is supposed
        to enforce ASCII;
      - `lv_label.c`'s actual on-device `strlen()`-based truncation,
        which is a second, independent way the same NUL-containing
        message would fail to display in full even if the Python-level
        check below were fixed to route it through `decode()` anyway.
    Both rest on direct source citation in the audit, not on a native
    test. What this test does reproduce, against the real
    `MessageApp.process_host_command` code path, is the NUL-only case:
    a NUL is valid under both strict ASCII and UTF-8, so it survives a
    spec-correct ascii codec too. That makes the display/sign
    divergence a distinct logic bug (no control-byte rejection before
    display), not merely a symptom of the MicroPython decode quirk.
    """

    def setUp(self):
        clear_testdir()
        platform.maybe_mkdir(TEST_DIR)
        self.keystore = get_keystore()
        self._orig_prompt = signmessage_mod.Prompt
        signmessage_mod.Prompt = _RecordingPrompt
        _RecordingPrompt.last_msg = None

        self.app = MessageApp(TEST_DIR + "/message")
        self.app.init(self.keystore, "regtest", lambda *a, **k: None, None)
        # Stub out the actual ECDSA math (native secp256k1 usermod, out of
        # scope here) so the flow completes. This test is about the
        # display/authorization boundary before signing, not the
        # signature bytes themselves.
        self.app.sign_message = lambda derivation, message: b"fake-signature"

    def tearDown(self):
        signmessage_mod.Prompt = self._orig_prompt
        clear_testdir()
        gc.collect()

    def test_message_with_embedded_nul_must_not_display_as_readable_text(self):
        visible = b"I authorise nothing."
        hidden = b"<arbitrary attacker text the user is never shown>"
        payload = visible + b"\x00" + hidden

        command = b"signmessage m/44h/0h/0h/0/0 base64:" + b2a_base64(
            payload, newline=False
        )
        stream = BytesIO(command)

        result = asyncio.run(self.app.process_host_command(stream, _approve))
        self.assertNotEqual(result, False, "signing must not have been rejected")

        displayed = _RecordingPrompt.last_msg
        self.assertIsNotNone(displayed, "Prompt was never shown")

        # sign_message() commits to the full payload regardless, so the
        # display is the only authorization boundary here - it must
        # never show the hidden tail as literal readable text.
        self.assertNotIn(
            hidden.decode("ascii"),
            displayed,
            "hidden attacker text must never appear as readable text in "
            "the signing prompt (F-21); displayed was: %r" % displayed,
        )
        # Recommended fix (action-plan item 1): a message containing a
        # control byte like NUL is not printable and must be routed to
        # the hex-dump branch instead of the pretty-printed one.
        self.assertTrue(
            displayed.startswith("Hex message:"),
            "a message containing a NUL byte must be shown as a hex "
            "dump, not decoded and displayed as text (F-21); displayed "
            "was: %r" % displayed,
        )
