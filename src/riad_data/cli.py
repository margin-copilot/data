"""riad-data: loads Riad Market's data into Azure SQL with region security, and verifies it.
One browser sign-in as the database admin (ADMIN_USERS in the infra repo)."""

import argparse
import os
import sys

import msal

from riad_data import settings, sql
from riad_data.generate import generate
from riad_data.load import load as load_dataset
from riad_data.tables import user_region_rows


def sign_in(values: dict[str, str]) -> str:
    tenant, client = settings.require(values, "TENANT_ID", "DATA_TOOLS_CLIENT_ID")
    app = msal.PublicClientApplication(
        client, authority=f"https://login.microsoftonline.com/{tenant}"
    )
    result = app.acquire_token_interactive(
        [sql.SCOPE], login_hint=values.get("ADMIN_UPN") or None, prompt="select_account"
    )
    if "access_token" not in result:
        raise SystemExit(
            f"sign-in failed: {result.get('error')}: {result.get('error_description')}"
        )
    return result["access_token"]


def connect(values: dict[str, str]):
    server, database = settings.require(values, "SQL_SERVER", "SQL_DATABASE")
    return sql.connect(server, database, sign_in(values))


def load(values: dict[str, str]) -> None:
    (domain,) = settings.require(values, "ENTRA_DOMAIN")
    users = user_region_rows(domain, values["USER_REGIONS"])
    connection = connect(values)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT ORIGINAL_LOGIN(), USER_NAME()")
        login, user = cursor.fetchone()
        print(f"connected as {login} (database user {user})")
        for table, count in load_dataset(connection, generate(), users).items():
            print(f"loaded {table}: {count} rows")
        print("region security applied")
    finally:
        connection.close()


def verify(values: dict[str, str]) -> None:
    connection = connect(values)
    try:
        cursor = connection.cursor()
        for table in ("dbo.dim_store", "dbo.fact_sales", "rls.user_region"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]} rows visible to the signed-in admin")
    finally:
        connection.close()


COMMANDS = {"load": load, "verify": verify}


def main() -> None:
    if env := sql.openssl3_env(sys.platform, os.environ):
        os.execve(sys.executable, [sys.executable, *sys.argv], env)
    parser = argparse.ArgumentParser(prog="riad-data", description=__doc__)
    parser.add_argument("command", choices=list(COMMANDS))
    COMMANDS[parser.parse_args().command](settings.load())
