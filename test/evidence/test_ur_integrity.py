import unittest
from binascii import crc32
from io import BytesIO

from microur.decoder import URDecoder
from microur.encoder import UREncoder
from microur.util import bytewords, ur


def _encode(data):
    out = BytesIO()
    bytewords.stream_encode(BytesIO(data), len(data), out)
    return out.getvalue().decode()


def _frames():
    payload = b"multipart proof"
    encoder = UREncoder("crypto-psbt", BytesIO(payload), part_len=8)
    assert encoder.seq_len == 2
    return payload, encoder, [encoder.get_part(i) for i in range(2)]


class URIntegrityEvidence(unittest.TestCase):
    def test_unmodified_multipart_message_round_trips(self):
        payload, _, frames = _frames()
        decoder = URDecoder()
        for frame in frames:
            decoder.process_part(frame)
        with decoder.result() as stream:
            self.assertEqual(stream.read(), bytes([len(payload) | 0x40]) + payload)

    def test_bad_per_part_bytewords_crc_is_rejected(self):
        _, encoder, frames = _frames()
        prefix, encoded = frames[1].rsplit("/", 1)
        decoded = bytearray(bytewords.decode(encoded))
        header = BytesIO()
        ur.write_header(2, encoder.seq_len, encoder.msg_len, encoder.checksum,
                        encoder.payload_len, header)
        decoded[len(header.getvalue())] ^= 1
        frames[1] = prefix + "/" + _encode(decoded)

        decoder = URDecoder()
        decoder.process_part(frames[0])
        with self.assertRaises(ValueError, msg="F-28: corrupted part CRC was accepted"):
            decoder.process_part(frames[1])

    def test_recomputed_part_crc_cannot_bypass_message_crc(self):
        payload, encoder, frames = _frames()
        prefix, encoded = frames[1].rsplit("/", 1)
        decoded = bytearray(bytewords.decode(encoded))
        header = BytesIO()
        ur.write_header(2, encoder.seq_len, encoder.msg_len, encoder.checksum,
                        encoder.payload_len, header)
        decoded[len(header.getvalue())] ^= 1
        decoded[-4:] = crc32(decoded[:-4]).to_bytes(4, "big")
        frames[1] = prefix + "/" + _encode(decoded)
        self.assertNotEqual(decoded[-4:], bytewords.decode(encoded)[-4:])

        decoder = URDecoder()
        for frame in frames:
            decoder.process_part(frame)
        self.assertTrue(decoder.is_complete)
        for _ in range(2):
            with self.assertRaises(ValueError, msg="F-28: invalid message CRC was accepted"):
                with decoder.result() as stream:
                    self.assertNotEqual(
                        stream.read(), bytes([len(payload) | 0x40]) + payload
                    )
            self.assertFalse(
                decoder.is_combined,
                "F-28: a rejected message must not leave a cached combined part",
            )
