"""Settings from the environment and the repo's gitignored .env (names in .env.example).
Values already in the environment win over .env."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
NAMES = (
    "TENANT_ID",
    "DATA_TOOLS_CLIENT_ID",
    "FABRIC_ADMIN_UPN",
    "FABRIC_WORKSPACE",
    "FABRIC_LAKEHOUSE",
    "FABRIC_CAPACITY",
    "VIEWER_GROUP_ID",
    "ENTRA_DOMAIN",
    "USER_REGIONS",
    "WORKSPACE_ID",
    "LAKEHOUSE_ID",
    "SQL_ENDPOINT_ID",
    "SQL_ENDPOINT_HOST",
)
DEFAULTS = {
    "FABRIC_WORKSPACE": "margin-copilot",
    "FABRIC_LAKEHOUSE": "riad",
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
