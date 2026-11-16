"""
Demo of a simple app that extends Specter with custom functionality.
"""
from app import BaseApp, AppError
from gui.screens import Prompt

from embit import ec, bip32, script, compact
from embit.liquid.networks import NETWORKS
from hashlib import sha256
from binascii import b2a_base64, unhexlify, a2b_base64, hexlify
import secp256k1
from io import BytesIO

HARDENED = 0x80000000
MAX_MSG_LEN = 512
MAX_PATH_DEPTH = 10

# Purposes whose single-key address is derived from the same pubkey the
# recoverable ECDSA signature commits to. The header byte is always the
# compressed-P2PKH one (31-34), not the BIP-137 segwit ones (35-42), so
# Electrum-style verifiers accept 49h/84h addresses but strict BIP-137
# verifiers and Bitcoin Core (P2PKH only) do not.
ADDRESS_TYPES = {
    HARDENED + 44: "p2pkh",
    HARDENED + 49: "p2sh-p2wpkh",
    HARDENED + 84: "p2wpkh",
}


def is_standard_path(derivation, network):
    """purpose'/coin'/account'/change/index with a known purpose and the
    coin type of the current network."""
    if len(derivation) != 5:
        return False
    purpose, coin, account, change, index = derivation
    return (
        purpose in ADDRESS_TYPES
        and coin == HARDENED + network["bip32"]
        and account >= HARDENED
        and change in (0, 1)
        and index < HARDENED
    )


def path_address(derivation, pub, network):
    """Single-key address for the path, or None for purposes (e.g. 86h,
    48h) where no single-key address matches the signing key's use."""
    kind = ADDRESS_TYPES.get(derivation[0]) if derivation else None
    if kind == "p2pkh":
        return script.p2pkh(pub).address(network)
    if kind == "p2sh-p2wpkh":
        return script.p2sh(script.p2wpkh(pub)).address(network)
    if kind == "p2wpkh":
        return script.p2wpkh(pub).address(network)
    return None


class MessageApp(BaseApp):
    """
    This app can sign a text message with a private key.
    """

    prefixes = [b"signmessage"]
    name = "message"

    async def process_host_command(self, stream, show_screen):
        """
        If command with one of the prefixes is received
        it will be passed to this method.
        Should return a tuple:
        - stream (file, BytesIO etc)
        - meta object with title and note
        """
        # reads prefix from the stream (until first space)
        prefix = self.get_prefix(stream)
        if prefix != b"signmessage":
            # WTF? It's not our data...
            raise AppError("Prefix is not valid: %s" % prefix.decode())
        # data format: message to sign<space>derivation_path
        # read all and delete all crap at the end (if any)
        # also message should be utf-8 decodable
        data = stream.read().strip()
        if b" " not in data:
            raise AppError("Invalid data encoding")
        arr = data.split(b" ")
        derivation_path = arr[0].decode()
        message = b" ".join(arr[1:])
        # if we have fingerprint
        if not derivation_path.startswith("m"):
            fingerprint = unhexlify(derivation_path[:8])
            if fingerprint != self.keystore.fingerprint:
                raise AppError("Not my fingerprint")
            derivation_path = "m" + derivation_path[8:]
        # Returns a list of indexes
        derivation_path = bip32.parse_path(derivation_path)
        if len(derivation_path) > MAX_PATH_DEPTH:
            raise AppError(
                "Derivation path too deep (%d > %d)"
                % (len(derivation_path), MAX_PATH_DEPTH)
            )

        if message.startswith(b"ascii:"):
            message = message[len(b"ascii:") :]
        elif message.startswith(b"base64:"):
            message = a2b_base64(message[len(b"base64:") :])
        else:
            raise AppError("Invalid message encoding!")
        # explicit byte validation - .decode("ascii") does not actually
        # enforce ASCII (embedded NUL and other control bytes decode fine),
        # so a hex dump is the only safe fallback for anything not printable
        if len(message) > MAX_MSG_LEN:
            raise AppError("Message too long (%d > %d bytes)" % (len(message), MAX_MSG_LEN))
        printable = all(0x20 <= b <= 0x7E or b == 0x0A for b in message)
        # The frame is drawn by Prompt in separate trusted labels, so the
        # message label holds only the message bytes.
        if printable:
            frame_title = "Message:"
            msg = message.decode()
        else:
            frame_title = "Hex message:"
            msg = hexlify(message).decode()
        warning = None
        if not is_standard_path(derivation_path, NETWORKS[self.network]):
            warning = "Non-standard derivation path!\nCheck it before signing."
        # Path in the note, not the title: a long path in the large title
        # font would wrap over several lines and push the message page down.
        scr = Prompt(
            "Sign message?",
            msg,
            note="Derivation path: %s" % bip32.path_to_str(derivation_path),
            frame_title=frame_title,
            warning=warning,
        )
        res = await show_screen(scr)
        if res is False:
            return False
        sig = self.sign_message(derivation_path, message)
        # for GUI we can also return an object with helpful data
        pub = self.keystore.get_xpub(derivation_path).get_public_key()
        # Show an address only where its type matches this signature format;
        # for other purposes (e.g. 86h Taproot, 48h multisig) any single-key
        # address would mislead whoever verifies the signature.
        addr = path_address(derivation_path, pub, NETWORKS[self.network])
        if addr is None:
            note = "Address: not shown for this path"
        else:
            note = "Address: %s" % addr
        note += "\nDerivation path: %s" % bip32.path_to_str(derivation_path)
        obj = {
            "title": "Message signature:",
            "note": note,   
        }
        return BytesIO(sig), obj

    def sign_message(self, derivation, msg: bytes, compressed: bool = True) -> bytes:
        """Sign message with private key"""
        msghash = sha256(
            sha256(
                b"\x18Bitcoin Signed Message:\n" + compact.to_bytes(len(msg)) + msg
            ).digest()
        ).digest()
        sig, flag = self.keystore.sign_recoverable(derivation, msghash)
        c = 4 if compressed else 0
        flag = bytes([27 + flag + c])
        ser = flag + secp256k1.ecdsa_signature_serialize_compact(sig._sig)
        return b2a_base64(ser).strip().decode()
