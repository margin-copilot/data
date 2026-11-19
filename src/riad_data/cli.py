"""riad-fabric: sets up the Fabric lakehouse, loads the data and applies region security.
One browser sign-in as the Fabric admin; tokens for Fabric, OneLake and SQL come from it."""

import argparse

import httpx
import msal

from riad_data import rls, settings, sql
from riad_data.fabric import API, Fabric
from riad_data.generate import generate
from riad_data.tables import onelake_uri, to_arrow, user_region_rows, write_tables

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"


class Session:
    def __init__(self, values: dict[str, str]) -> None:
        tenant, client = settings.require(values, "TENANT_ID", "DATA_TOOLS_CLIENT_ID")
        self.app = msal.PublicClientApplication(
            client, authority=f"https://login.microsoftonline.com/{tenant}"
        )
        result = self.app.acquire_token_interactive(
            [FABRIC_SCOPE],
            login_hint=values.get("FABRIC_ADMIN_UPN") or None,
            prompt="select_account",
        )
        if "access_token" not in result:
            raise SystemExit(
                f"sign-in failed: {result.get('error')}: {result.get('error_description')}"
            )
        self.account = self.app.get_accounts()[0]

    def token(self, scope: str) -> str:
        result = self.app.acquire_token_silent([scope], account=self.account)
        if not result or "access_token" not in result:
            raise SystemExit(
                f"no token for {scope}: {(result or {}).get('error', 'consent missing?')}"
            )
        return result["access_token"]

    def fabric(self) -> Fabric:
        headers = {"Authorization": f"Bearer {self.token(FABRIC_SCOPE)}"}
        return Fabric(httpx.Client(base_url=API, headers=headers, timeout=60))


def setup(session: Session, values: dict[str, str]) -> None:
    (group,) = settings.require(values, "VIEWER_GROUP_ID")
    fabric = session.fabric()
    capacity = fabric.trial_capacity(values.get("FABRIC_CAPACITY") or None)
    workspace = fabric.ensure_workspace(values["FABRIC_WORKSPACE"], capacity["id"])
    lakehouse = fabric.ensure_lakehouse(workspace, values["FABRIC_LAKEHOUSE"])
    host, endpoint = fabric.sql_endpoint(workspace, lakehouse)
    fabric.ensure_viewer(workspace, group)
    values.update(
        WORKSPACE_ID=workspace,
        LAKEHOUSE_ID=lakehouse,
        SQL_ENDPOINT_ID=endpoint,
        SQL_ENDPOINT_HOST=host,
    )
    print(f"capacity: {capacity['displayName']} ({capacity['sku']}, {capacity.get('region')})")
    print("add to .env:")
    for key in ("WORKSPACE_ID", "LAKEHOUSE_ID", "SQL_ENDPOINT_ID", "SQL_ENDPOINT_HOST"):
        print(f"{key}={values[key]}")


def load(session: Session, values: dict[str, str]) -> None:
    workspace, lakehouse, endpoint, domain = settings.require(
        values, "WORKSPACE_ID", "LAKEHOUSE_ID", "SQL_ENDPOINT_ID", "ENTRA_DOMAIN"
    )
    tables = to_arrow(generate(), user_region_rows(domain, values["USER_REGIONS"]))
    options = {"bearer_token": session.token(STORAGE_SCOPE), "use_fabric_endpoint": "true"}
    for name in write_tables(onelake_uri(workspace, lakehouse), tables, options):
        print(f"wrote {name}")
    session.fabric().refresh_metadata(workspace, endpoint)
    print("SQL endpoint metadata refreshed")


def apply_rls(session: Session, values: dict[str, str]) -> None:
    host, lakehouse, domain = settings.require(
        values, "SQL_ENDPOINT_HOST", "FABRIC_LAKEHOUSE", "ENTRA_DOMAIN"
    )
    upns = [row["upn"] for row in user_region_rows(domain, values["USER_REGIONS"])]
    with sql.connect(host, lakehouse, session.token(sql.SCOPE)) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT USER_NAME()")
        print(f"connected as {cursor.fetchone()[0]}")
        for statement in rls.statements(upns):
            cursor.execute(statement)
            print(f"ok: {statement.splitlines()[0]}")
        connection.commit()


def verify(session: Session, values: dict[str, str]) -> None:
    host, lakehouse = settings.require(values, "SQL_ENDPOINT_HOST", "FABRIC_LAKEHOUSE")
    with sql.connect(host, lakehouse, session.token(sql.SCOPE)) as connection:
        cursor = connection.cursor()
        for table in ("dbo.dim_store", "dbo.fact_sales", "rls.user_region"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]} rows visible to the signed-in admin")


COMMANDS = {"setup": setup, "load": load, "rls": apply_rls, "verify": verify}


def main() -> None:
    parser = argparse.ArgumentParser(prog="riad-fabric", description=__doc__)
    parser.add_argument("command", choices=[*COMMANDS, "all"])
    command = parser.parse_args().command
    values = settings.load()
    session = Session(values)
    for name in ("setup", "load", "rls") if command == "all" else (command,):
        COMMANDS[name](session, values)
