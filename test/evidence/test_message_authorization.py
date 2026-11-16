import asyncio
import gc
import re
import unittest
from binascii import a2b_base64
from io import BytesIO
from unittest.mock import patch

import platform
from app import AppError
from apps.signmessage import signmessage
from embit import bip32, script
from embit.liquid.networks import NETWORKS
from embit.misc import secp256k1 as embit_secp256k1
from tests.util import clear_testdir, get_keystore


# Bootloader's reference release-format message in test/test_bl_signature.cpp.
FIRMWARE_MESSAGE = (
    b"b77.777.777rc77-77.777.777rc77-1tudm93ag6fu6y7x4q6s87ar6zskyc"
    b"pmceltrmt7s577aa94yzan9zeyvfd"
)
MAIN_ONLY_FIRMWARE_MESSAGE = (
    b"77.777.777rc77-1tudm93ag6fu6y7x4q6s87ar6zskyc"
    b"pmceltrmt7s577aa94yzan9zeyvfd"
)


# A line drawn purely from rule characters, i.e. something that reads as a
# frame / separator on screen regardless of its exact length or glyph.
_SEPARATOR_LINE = re.compile(r"^\s*[_\-=~*#.─━]{5,}\s*$")


def _separator_lines(text):
    return sum(1 for line in (text or "").split("\n") if _SEPARATOR_LINE.match(line))


class _RecordingPrompt:
    last_title = None
    last_msg = None
    last_kwargs = None

    # Mirrors gui.screens.prompt.Prompt's signature loosely so a fix that
    # passes note=/warning= or extra widgets does not break the recorder.
    def __init__(self, title="", message="", *args, **kwargs):
        self.title = title
        self.msg = message
        _RecordingPrompt.last_title = title
        _RecordingPrompt.last_msg = message
        _RecordingPrompt.last_kwargs = kwargs


async def _approve(_screen):
    return True


def write_firmware_signature_fixture(path):
    clear_testdir()
    try:
        keystore = get_keystore()
        app = signmessage.MessageApp("testdir/message")
        app.init(keystore, "regtest", lambda *args, **kwargs: None, None)
        derivation = bip32.parse_path("m/44h/0h/0h/0/0")
        signed_hashes = []

        def sign_recoverable(requested_derivation, digest):
            signed_hashes.append(digest)
            private_key = keystore.root.derive(requested_derivation).key
            return private_key.sign(digest), 0

        with (
            patch.object(keystore, "sign_recoverable", sign_recoverable),
            patch.object(
                signmessage.secp256k1,
                "ecdsa_signature_serialize_compact",
                embit_secp256k1.ecdsa_signature_serialize_compact,
                create=True,
            ),
        ):
            encoded_signature = app.sign_message(derivation, FIRMWARE_MESSAGE)

        signature = a2b_base64(encoded_signature)
        public_key = keystore.root.derive(derivation).key.get_public_key()
        public_key.compressed = False
        pubkey_bytes = public_key.sec()
        if len(signed_hashes) != 1 or len(signature) != 65 or len(pubkey_bytes) != 65:
            raise ValueError("Message-signing fixture has an invalid shape")
        path.write_bytes(
            bytes([len(FIRMWARE_MESSAGE)])
            + FIRMWARE_MESSAGE
            + signed_hashes[0]
            + signature[1:]
            + pubkey_bytes
        )
    finally:
        clear_testdir()


class MessageAuthorizationEvidence(unittest.TestCase):
    def setUp(self):
        clear_testdir()
        platform.maybe_mkdir("testdir")
        self.keystore = get_keystore()
        self.prompt_patch = patch.object(signmessage, "Prompt", _RecordingPrompt)
        self.prompt_patch.start()
        self.addCleanup(self.prompt_patch.stop)
        self.addCleanup(clear_testdir)
        self.addCleanup(gc.collect)
        _RecordingPrompt.last_title = None
        _RecordingPrompt.last_msg = None
        self.signed = []
        self.app = signmessage.MessageApp("testdir/message")
        self.app.init(self.keystore, "regtest", lambda *args, **kwargs: None, None)
        self.app.sign_message = self._record_signature

    def _record_signature(self, derivation, message):
        self.signed.append(message)
        return b"test-signature"

    def _send(self, path, message):
        command = b"signmessage " + path + b" ascii:" + message
        return asyncio.run(self.app.process_host_command(BytesIO(command), _approve))

    def _send_or_reject(self, path, message):
        """Returns the host-command result, or None if the app rejected it.

        Rejecting the request outright is an acceptable fix, so the property
        tests below treat AppError as a pass rather than an error.
        """
        try:
            return self._send(path, message)
        except AppError:
            return None

    def test_firmware_authorization_message_is_not_generically_signed(self):
        for candidate in (FIRMWARE_MESSAGE, MAIN_ONLY_FIRMWARE_MESSAGE):
            with self.subTest(message=candidate.decode()):
                self.signed.clear()
                _RecordingPrompt.last_title = None
                _RecordingPrompt.last_msg = None
                try:
                    self._send(b"m/44h/0h/0h/0/0", candidate)
                except AppError:
                    continue
                prompt_text = "%s\n%s" % (
                    _RecordingPrompt.last_title or "",
                    _RecordingPrompt.last_msg or "",
                )
                if "firmware" in prompt_text.lower():
                    continue
                self.assertEqual(
                    self.signed,
                    [],
                    "F-17 (audit.md): the ordinary message app signed a bootloader-format "
                    "firmware authorization message under a generic prompt",
                )

    def test_printable_message_cannot_impersonate_trusted_frame(self):
        path = b"m/44h/0h/0h/0/0"
        # Baseline: a benign message must still be accepted. Any separator
        # lines in its message string are the app's own (trusted) frame.
        self._send(path, b"Pay Alice")
        trusted = _separator_lines(_RecordingPrompt.last_msg)
        if trusted == 0:
            # Frame lives outside the message string (F-21 action-plan
            # item 2), so nothing in this string can impersonate it. Require
            # that the app really hands the frame to Prompt, so removing the
            # frame cannot pass this test. The message-only content is also
            # checked in tests_native/test_message_signing_display.py.
            self.assertTrue(
                (_RecordingPrompt.last_kwargs or {}).get("frame_title"),
                "F-21 (audit.md): no separator in the message string and no frame_title "
                "passed to Prompt; the message is shown without a frame",
            )
            self.assertEqual(_RecordingPrompt.last_msg, "Pay Alice")
            return
        # The display font is proportional, so near-length copies and other
        # rule glyphs look the same as the exact frame on screen.
        forgeries = (b"_" * 34, b"_" * 20, b"_" * 48, b"-" * 34, b"=" * 34)
        for forged in forgeries:
            with self.subTest(forged=forged.decode()):
                _RecordingPrompt.last_msg = None
                if self._send_or_reject(
                    path, b"Pay Alice\n" + forged + b"\nPay Mallory"
                ) is None:
                    continue
                shown = _RecordingPrompt.last_msg
                # Escaping, quoting or hex-dumping the attacker's text keeps
                # the separator count at or below the trusted frame's own.
                self.assertLessEqual(
                    _separator_lines(shown),
                    trusted,
                    "F-21 (audit.md): printable message text impersonated the prompt's "
                    "own frame: %r" % shown,
                )

    def _assert_no_legacy_address(self, path):
        result = self._send_or_reject(path.encode(), b"Confirm account")
        if result is None:
            return
        _, metadata = result
        public_key = self.keystore.get_xpub(
            bip32.parse_path(path)
        ).get_public_key()
        legacy_address = script.p2pkh(public_key).address(NETWORKS["regtest"])
        # Match the address alone, not a label, so renaming the label is not
        # mistaken for a fix. Note: a P2TR address also passes here; whether
        # that is acceptable next to a legacy ECDSA signature is open (F-21).
        self.assertNotIn(
            legacy_address,
            metadata.get("note", ""),
            "F-21 (audit.md): the app displayed a legacy address for %s" % path,
        )

    def test_taproot_path_does_not_display_legacy_address(self):
        self._assert_no_legacy_address("m/86h/1h/0h/0/0")

    def test_unrecognized_purpose_does_not_display_legacy_address(self):
        for path in ("m/48h/1h/0h/2h/0/0", "m/1234h/1h/0h/0/0"):
            with self.subTest(path=path):
                self._assert_no_legacy_address(path)
