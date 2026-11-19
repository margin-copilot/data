"""Connects to Azure SQL with a user's Entra token. Pooling stays off, so a connection made with one
user's token is never reused for another (CLAUDE.md). Retries while a paused database wakes up."""

import struct
import time

ACCESS_TOKEN = 1256  # SQL_COPT_SS_ACCESS_TOKEN
SCOPE = "https://database.windows.net/.default"
WAKING = "40613"  # database not currently available: the serverless database is resuming


def pack_token(token: str) -> bytes:
    raw = token.encode("utf-16-le")
    return struct.pack(f"<I{len(raw)}s", len(raw), raw)


def connect(server: str, database: str, token: str, attempts: int = 6, sleep=time.sleep):
    import mssql_python  # imported here so tests and CI never load the native driver

    mssql_python.pooling(enabled=False)
    connection_string = f"Server=tcp:{server},1433;Database={database};Encrypt=yes"
    return with_wake_retry(
        lambda: mssql_python.connect(
            connection_string, attrs_before={ACCESS_TOKEN: pack_token(token)}
        ),
        attempts,
        sleep,
    )


def with_wake_retry(open_connection, attempts: int = 6, sleep=time.sleep):
    delay = 5
    for attempt in range(1, attempts + 1):
        try:
            return open_connection()
        except Exception as error:
            if WAKING not in str(error) or attempt == attempts:
                raise
            sleep(delay)
            delay = min(delay * 2, 60)
    raise AssertionError("unreachable")
