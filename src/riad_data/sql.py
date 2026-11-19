"""Connects to the lakehouse SQL endpoint with a user's Entra token. Pooling stays off, so a
connection made with one user's token is never reused for another (CLAUDE.md)."""

import struct

ACCESS_TOKEN = 1256  # SQL_COPT_SS_ACCESS_TOKEN
SCOPE = "https://database.windows.net/.default"


def pack_token(token: str) -> bytes:
    raw = token.encode("utf-16-le")
    return struct.pack(f"<I{len(raw)}s", len(raw), raw)


def connect(host: str, database: str, token: str):
    import mssql_python  # imported here so tests and CI never load the native driver

    mssql_python.pooling(enabled=False)
    return mssql_python.connect(
        f"Server={host};Database={database};Encrypt=yes",
        attrs_before={ACCESS_TOKEN: pack_token(token)},
    )
