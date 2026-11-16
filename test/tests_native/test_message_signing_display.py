import sys

if sys.implementation.name != 'micropython':
    from native_support import setup_native_stubs

    setup_native_stubs()

from unittest import TestCase
from io import BytesIO
from binascii import b2a_base64, a2b_base64, hexlify
from hashlib import sha256
import asyncio
import gc

import apps.signmessage.signmessage as signmessage_mod
from apps.signmessage.signmessage import MessageApp
from app import AppError
import keystore.ram as ram_mod
from embit import bip32, script
from embit.liquid.networks import NETWORKS
from tests.util import get_keystore, clear_testdir
import platform

TEST_DIR = "testdir"


class _RecordingPrompt:
    """
    Stand-in for gui.screens.Prompt. Records the exact (title, msg)
    strings the real GUI would receive, instead of touching lvgl.
    """

    last_title = None
    last_msg = None
    last_kwargs = None

    def __init__(self, title, msg, **kwargs):
        _RecordingPrompt.last_title = title
        _RecordingPrompt.last_msg = msg
        _RecordingPrompt.last_kwargs = kwargs
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
    Both rest on direct source citation in the audit.md, not on a native
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
        self.assertEqual(
            _RecordingPrompt.last_kwargs.get("frame_title"),
            "Hex message:",
            "a message containing a NUL byte must be shown as a hex "
            "dump, not decoded and displayed as text (F-21)",
        )
        self.assertEqual(displayed, hexlify(payload).decode())

    def _send(self, path, message):
        command = b"signmessage " + path + b" ascii:" + message
        return asyncio.run(self.app.process_host_command(BytesIO(command), _approve))

    def test_printable_message_is_shown_inside_trusted_frame(self):
        self._send(b"m/44h/0h/0h/0/0", b"Pay Alice")
        # The message label holds only the message; the frame is drawn
        # by Prompt from frame_title in separate labels.
        self.assertEqual(_RecordingPrompt.last_msg, "Pay Alice")
        self.assertEqual(_RecordingPrompt.last_kwargs.get("frame_title"), "Message:")

    def test_path_deeper_than_limit_is_rejected(self):
        path = b"m" + b"/0" * (signmessage_mod.MAX_PATH_DEPTH + 1)
        with self.assertRaises(AppError):
            self._send(path, b"hello")
        self.assertIsNone(_RecordingPrompt.last_msg, "prompt shown for a too-deep path")

    def test_non_standard_path_shows_warning(self):
        for path in (b"m/86h/1h/0h/0/0", b"m/44h/0h/0h/0/0",  # wrong coin for regtest
                     b"m/84h/1h/0/0/0", b"m/84h/1h/0h/0/0/0", b"m/1234h/1h/0h/0/0"):
            with self.subTest(path=path):
                self._send(path, b"hello")
                self.assertTrue(_RecordingPrompt.last_kwargs.get("warning"))

    def test_standard_path_shows_no_warning(self):
        for path in (b"m/44h/1h/0h/0/0", b"m/49h/1h/2h/1/7", b"m/84h/1h/0h/0/0"):
            with self.subTest(path=path):
                self._send(path, b"hello")
                self.assertIsNone(_RecordingPrompt.last_kwargs.get("warning"))

    def test_address_shown_only_for_matching_purposes(self):
        net = NETWORKS["regtest"]
        cases = {
            "m/44h/1h/0h/0/0": lambda pub: script.p2pkh(pub).address(net),
            "m/49h/1h/0h/0/0": lambda pub: script.p2sh(script.p2wpkh(pub)).address(net),
            "m/84h/1h/0h/0/0": lambda pub: script.p2wpkh(pub).address(net),
            "m/86h/1h/0h/0/0": None,
            "m/48h/1h/0h/2h/0/0": None,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                _, meta = self._send(path.encode(), b"hello")
                pub = self.keystore.get_xpub(bip32.parse_path(path)).get_public_key()
                if expected is None:
                    self.assertIn("Address: not shown", meta["note"])
                    self.assertNotIn(script.p2pkh(pub).address(net), meta["note"])
                else:
                    self.assertIn("Address: %s\n" % expected(pub), meta["note"])

    def test_path_is_shown_in_note_not_title(self):
        # In the large title font a long path wrapped over several lines and
        # pushed the message page down; it is shown in the note label instead.
        path = "m" + "/2147483647h" * signmessage_mod.MAX_PATH_DEPTH
        self._send(path.encode(), b"hello")
        self.assertEqual(_RecordingPrompt.last_title, "Sign message?")
        self.assertEqual(_RecordingPrompt.last_kwargs.get("note"),
                         "Derivation path: %s" % path)
