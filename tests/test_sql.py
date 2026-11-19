import struct

from riad_data.sql import pack_token


def test_token_is_packed_as_length_prefixed_utf16le():
    packed = pack_token("abc")
    assert packed == struct.pack("<I", 6) + "abc".encode("utf-16-le")
