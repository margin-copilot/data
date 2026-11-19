"""T-SQL for region security in Azure SQL (D-008, D-031): every dbo table with region_id except the
reference dimensions is filtered by the caller's UPN through rls.user_region. Test users read dbo
through a role and can't read rls."""

import re

from riad_data import tables

# Readers get SELECT on all of dbo: every dbo table with region_id is filtered unless listed here.
UNFILTERED = {"dim_region", "dim_store"}  # reference data: region and store lists aren't sensitive
READERS = "pricing_readers"
UPN = re.compile(r"^[a-z0-9][a-z0-9._-]*@[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def quote_upn(upn: str) -> str:
    if not UPN.match(upn):
        raise ValueError(f"refusing to put {upn!r} into T-SQL")
    return f"[{upn}]"


def regional_tables() -> list[str]:
    return [
        table
        for table, columns in tables.COLUMNS.items()
        if tables.SCHEMA_OF[table] == "dbo"
        and table not in UNFILTERED
        and any(column == "region_id" for column, _ in columns)
    ]


def drop_statements() -> list[str]:
    return [
        "DROP SECURITY POLICY IF EXISTS rls.region_policy",
        "DROP FUNCTION IF EXISTS rls.fn_region_filter",
    ]


def principal_statements(upns: list[str]) -> list[str]:
    """Database users and the reader role. Run outside the load transaction; idempotent."""
    quoted = [quote_upn(upn) for upn in upns]
    return [
        # The DENY below needs the schema on a first load.
        "IF SCHEMA_ID('rls') IS NULL EXEC('CREATE SCHEMA rls')",
        *(
            f"IF DATABASE_PRINCIPAL_ID(N'{upn}') IS NULL "
            f"EXEC(N'CREATE USER {name} FROM EXTERNAL PROVIDER')"
            for upn, name in zip(upns, quoted, strict=True)
        ),
        f"IF DATABASE_PRINCIPAL_ID(N'{READERS}') IS NULL CREATE ROLE {READERS}",
        *(f"ALTER ROLE {READERS} ADD MEMBER {name}" for name in quoted),
        f"GRANT SELECT ON SCHEMA::dbo TO {READERS}",
        f"DENY SELECT ON SCHEMA::rls TO {READERS}",
    ]


def policy_statements() -> list[str]:
    """The filter: drop and recreate, inside the load transaction."""
    predicates = ",\n".join(
        f"ADD FILTER PREDICATE rls.fn_region_filter(region_id) ON dbo.{table}"
        for table in regional_tables()
    )
    return [
        *drop_statements(),
        "CREATE FUNCTION rls.fn_region_filter(@region_id AS char(1))\n"
        "RETURNS TABLE\n"
        "WITH SCHEMABINDING\n"
        "AS\n"
        "RETURN SELECT 1 AS allowed\n"
        "FROM rls.user_region AS m\n"
        "WHERE m.upn = LOWER(ORIGINAL_LOGIN()) AND (m.region_id = @region_id OR m.region_id = '*')",
        f"CREATE SECURITY POLICY rls.region_policy\n{predicates}\nWITH (STATE = ON)",
    ]
