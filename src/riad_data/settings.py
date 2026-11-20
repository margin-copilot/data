"""Settings from the environment and the repo's gitignored .env (names in .env.example).
Values already in the environment win over .env."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
NAMES = (
    "TENANT_ID",
    "DATA_TOOLS_CLIENT_ID",
    "ADMIN_UPN",
    "SQL_SERVER",
    "SQL_DATABASE",
    "ENTRA_DOMAIN",
    "USER_REGIONS",
    "SEARCH_ENDPOINT",
    "POLICY_GROUPS",
)
DEFAULTS = {
    "SQL_DATABASE": "riad",
    "USER_REGIONS": "north.mgr:N,center.mgr:C,south.mgr:S,pricing.director:*",
}


def load(path: Path = ENV_FILE, environ: dict[str, str] | None = None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    values = dict(DEFAULTS)
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            key = key.strip()
            if sep and key and not key.startswith("#"):
                values[key] = value.strip().strip('"')
    values.update({name: environ[name] for name in NAMES if name in environ})
    return values


def require(values: dict[str, str], *names: str) -> list[str]:
    missing = [name for name in names if not values.get(name)]
    if missing:
        raise SystemExit(f"missing settings: {', '.join(missing)} (see .env.example)")
    return [values[name] for name in names]
