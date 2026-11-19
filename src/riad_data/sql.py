"""Connects to Azure SQL with a user's Entra token. Pooling stays off, so a connection made with one
user's token is never reused for another (CLAUDE.md). Retries while a paused database wakes up."""

import struct
import time
from pathlib import Path

ACCESS_TOKEN = 1256  # SQL_COPT_SS_ACCESS_TOKEN
SCOPE = "https://database.windows.net/.default"
WAKING = "40613"  # database not currently available: the serverless database is resuming
# The bundled macOS ODBC driver loads OpenSSL only from Homebrew's unversioned openssl link, which
# can point at OpenSSL 4 (unsupported); macOS reads DYLD_LIBRARY_PATH only at process start.
HOMEBREW_OPENSSL3 = Path("/opt/homebrew/opt/openssl@3/lib")


def openssl3_env(platform: str, environ, lib_dir: Path = HOMEBREW_OPENSSL3) -> dict | None:
    """Environment to restart with on macOS so the driver finds OpenSSL 3, or None if not needed."""
    if platform != "darwin" or environ.get("DYLD_LIBRARY_PATH") == str(lib_dir):
        return None
    if not (lib_dir / "libssl.3.dylib").exists():
        return None
    return {**environ, "DYLD_LIBRARY_PATH": str(lib_dir)}


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
