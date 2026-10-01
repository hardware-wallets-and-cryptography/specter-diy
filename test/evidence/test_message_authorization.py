import asyncio
import gc
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


class _RecordingPrompt:
    last_msg = None

    def __init__(self, title, msg):
        self.title = title
        self.msg = msg
        _RecordingPrompt.last_msg = msg


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

    def test_firmware_authorization_message_is_not_generically_signed(self):
        try:
            self._send(b"m/44h/0h/0h/0/0", FIRMWARE_MESSAGE)
        except AppError:
            pass
        self.assertEqual(
            self.signed,
            [],
            "F-17: the ordinary message app signed a bootloader-format "
            "firmware authorization message",
        )

    def test_printable_message_cannot_impersonate_trusted_frame(self):
        frame = b"_" * 34
        self._send(b"m/44h/0h/0h/0/0", b"Pay Alice\n" + frame + b"\nPay Mallory")
        self.assertTrue(
            _RecordingPrompt.last_msg.startswith("Hex message:"),
            "F-21: printable message text impersonated the prompt's own frame: %r"
            % _RecordingPrompt.last_msg,
        )

    def test_taproot_path_does_not_display_legacy_address(self):
        path = "m/86h/1h/0h/0/0"
        _, metadata = self._send(path.encode(), b"Confirm account")
        public_key = self.keystore.get_xpub(
            bip32.parse_path(path)
        ).get_public_key()
        legacy_address = script.p2pkh(public_key).address(NETWORKS["regtest"])
        self.assertNotIn(
            "Address: " + legacy_address,
            metadata["note"],
            "F-21: the app displayed a legacy address for a Taproot path",
        )
