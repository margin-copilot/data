import struct

import pytest

from riad_data.sql import pack_token, with_wake_retry


def test_token_is_packed_as_length_prefixed_utf16le():
    assert pack_token("abc") == struct.pack("<I", 6) + "abc".encode("utf-16-le")


def test_waking_database_is_retried_with_backoff():
    attempts, sleeps = [], []

    def open_connection():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("[40613] Database 'riad' on server is not currently available")
        return "connection"

    assert with_wake_retry(open_connection, sleep=sleeps.append) == "connection"
    assert sleeps == [5, 10]


def test_other_errors_are_not_retried():
    def denied():
        raise RuntimeError("[18456] Login failed")

    with pytest.raises(RuntimeError, match="18456"):
        with_wake_retry(denied, sleep=lambda s: None)


def test_retries_stop_after_the_last_attempt():
    def never_awake():
        raise RuntimeError("40613")

    with pytest.raises(RuntimeError):
        with_wake_retry(never_awake, attempts=3, sleep=lambda s: None)
