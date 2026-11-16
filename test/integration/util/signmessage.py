"""Helpers for F-21 message-signing checks against the simulator.

The simulator is unlocked by util.controller with the mnemonic below and runs
on regtest (see simulator.py), so expected keys and addresses can be derived
here on the host side.
"""
from binascii import a2b_base64, b2a_base64
from hashlib import sha256

from embit import bip32, bip39, compact, script
from embit.networks import NETWORKS
from embit.util import secp256k1

MNEMONIC = "abandon " * 11 + "about"

# 40 short lines: taller than the 600 px prompt page, within the 512-byte cap.
LONG_MESSAGE = b"\n".join(b"line %02d" % i for i in range(40))
assert len(LONG_MESSAGE) <= 512
# Longest path the app accepts: MAX_PATH_DEPTH (10) levels of the largest
# index. Non-standard, so the prompt also shows the warning.
DEEP_PATH = "m" + "/2147483647h" * 10
NETWORK = NETWORKS["regtest"]

_root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(MNEMONIC), version=NETWORK["xprv"])


def command(path: str, message: bytes) -> bytes:
    """signmessage host command; base64 so any byte (\\n, NUL) survives."""
    return b"signmessage %s base64:%s" % (
        path.encode(),
        b2a_base64(message).strip(),
    )


def pubkey(path: str):
    return _root.derive(path).key.get_public_key()


def expected_address(path: str):
    """Address the device should show in the result note, or None."""
    pub = pubkey(path)
    purpose = bip32.parse_path(path)[0]
    if purpose == 0x80000000 + 44:
        return script.p2pkh(pub).address(NETWORK)
    if purpose == 0x80000000 + 49:
        return script.p2sh(script.p2wpkh(pub)).address(NETWORK)
    if purpose == 0x80000000 + 84:
        return script.p2wpkh(pub).address(NETWORK)
    return None


def digest(message: bytes) -> bytes:
    return sha256(sha256(
        b"\x18Bitcoin Signed Message:\n" + compact.to_bytes(len(message)) + message
    ).digest()).digest()


def check_signature(response: bytes, path: str, message: bytes):
    """Returns None if `response` is a valid BIP-137 signature over the full
    `message` by the key at `path`, otherwise a reason string."""
    try:
        sig = a2b_base64(response)
    except Exception as e:
        return "not base64: %r (%s)" % (response, e)
    if len(sig) != 65:
        return "signature is %d bytes, expected 65: %r" % (len(sig), response)
    recid = sig[0] - 27 - 4
    if recid not in range(4):
        return "bad header byte %d" % sig[0]
    rsig = secp256k1.ecdsa_recoverable_signature_parse_compact(sig[1:], recid)
    recovered = secp256k1.ec_pubkey_serialize(secp256k1.ecdsa_recover(rsig, digest(message)))
    if recovered != pubkey(path).sec():
        return "signature does not recover to the key at %s" % path
    return None
