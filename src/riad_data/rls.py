"""T-SQL for region security on the lakehouse SQL endpoint (D-008): one filter predicate on every
table with region_id, keyed on the caller's UPN via rls.user_region, which test users can't read."""

import re

REGIONAL_TABLES = [
    "fact_sales",
    "supplier_costs",
    "promotions",
    "price_history",
    "competitor_prices",
]
UPN = re.compile(r"^[a-z0-9][a-z0-9._-]*@[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def quote_upn(upn: str) -> str:
    if not UPN.match(upn):
        raise ValueError(f"refusing to put {upn!r} into T-SQL")
    return f"[{upn}]"


def statements(denied_upns: list[str]) -> list[str]:
    predicates = ",\n".join(
        f"ADD FILTER PREDICATE rls.fn_region_filter(region_id) ON dbo.{table}"
        for table in REGIONAL_TABLES
    )
    return [
        "DROP SECURITY POLICY IF EXISTS rls.region_policy",
        "DROP FUNCTION IF EXISTS rls.fn_region_filter",
        "CREATE FUNCTION rls.fn_region_filter(@region_id AS varchar(8000))\n"
        "RETURNS TABLE\n"
        "WITH SCHEMABINDING\n"
        "AS\n"
        "RETURN SELECT 1 AS allowed\n"
        "FROM rls.user_region AS m\n"
        "WHERE m.upn = LOWER(USER_NAME()) AND (m.region_id = @region_id OR m.region_id = '*')",
        f"CREATE SECURITY POLICY rls.region_policy\n{predicates}\nWITH (STATE = ON)",
        *(f"DENY SELECT ON rls.user_region TO {quote_upn(upn)}" for upn in denied_upns),
    ]
