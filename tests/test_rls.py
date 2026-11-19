import pytest

from riad_data.rls import (
    READERS,
    policy_statements,
    principal_statements,
    quote_upn,
    regional_tables,
)

UPNS = ["north.mgr@example.onmicrosoft.com", "pricing.director@example.onmicrosoft.com"]


def test_policy_filters_every_regional_table():
    policy = next(s for s in policy_statements() if s.startswith("CREATE SECURITY POLICY"))
    assert regional_tables() == [
        "fact_sales",
        "supplier_costs",
        "promotions",
        "price_history",
        "competitor_prices",
    ]
    for table in regional_tables():
        assert f"rls.fn_region_filter(region_id) ON dbo.{table}" in policy
    assert policy.endswith("WITH (STATE = ON)")


def test_predicate_keys_on_the_callers_upn_and_allows_a_wildcard_region():
    function = next(s for s in policy_statements() if s.startswith("CREATE FUNCTION"))
    assert "WITH SCHEMABINDING" in function
    assert "m.upn = LOWER(ORIGINAL_LOGIN())" in function
    assert "m.region_id = '*'" in function


def test_each_user_gets_a_database_user_and_the_reader_role():
    sql = principal_statements(UPNS)
    assert (
        "IF DATABASE_PRINCIPAL_ID(N'north.mgr@example.onmicrosoft.com') IS NULL "
        "EXEC(N'CREATE USER [north.mgr@example.onmicrosoft.com] FROM EXTERNAL PROVIDER')"
    ) in sql
    assert f"ALTER ROLE {READERS} ADD MEMBER [pricing.director@example.onmicrosoft.com]" in sql


def test_readers_see_dbo_but_not_the_mapping():
    sql = principal_statements(UPNS)
    assert f"GRANT SELECT ON SCHEMA::dbo TO {READERS}" in sql
    assert f"DENY SELECT ON SCHEMA::rls TO {READERS}" in sql


def test_policy_is_rerunnable():
    first, second = policy_statements()[:2]
    assert first == "DROP SECURITY POLICY IF EXISTS rls.region_policy"
    assert second == "DROP FUNCTION IF EXISTS rls.fn_region_filter"


@pytest.mark.parametrize(
    "upn", ["x]; DROP TABLE t; --@a.com", "North.Mgr@example.com", "o'brien@a.com"]
)
def test_only_plain_lowercase_upns_reach_tsql(upn):
    with pytest.raises(ValueError):
        quote_upn(upn)


def test_principals_create_the_rls_schema_before_denying_it():
    sql = principal_statements(UPNS)
    create = sql.index("IF SCHEMA_ID('rls') IS NULL EXEC('CREATE SCHEMA rls')")
    deny = sql.index(f"DENY SELECT ON SCHEMA::rls TO {READERS}")
    assert create < deny


def test_every_table_with_region_id_is_filtered_except_the_dimensions(monkeypatch):
    from riad_data import rls, tables

    extended = {**tables.COLUMNS, "new_regional": [("region_id", "char(1)"), ("x", "int")]}
    monkeypatch.setattr(tables, "COLUMNS", extended)
    monkeypatch.setattr(tables, "SCHEMA_OF", {**tables.SCHEMA_OF, "new_regional": "dbo"})
    policy = next(s for s in rls.policy_statements() if s.startswith("CREATE SECURITY POLICY"))
    assert "ON dbo.new_regional" in policy
    for table in ("dim_region", "dim_store", "user_region"):
        assert f"ON dbo.{table}" not in policy and f"ON rls.{table}" not in policy
