import pytest

from riad_data.rls import REGIONAL_TABLES, quote_upn, statements


def test_policy_filters_every_regional_table():
    policy = next(s for s in statements([]) if s.startswith("CREATE SECURITY POLICY"))
    for table in REGIONAL_TABLES:
        assert f"rls.fn_region_filter(region_id) ON dbo.{table}" in policy
    assert policy.endswith("WITH (STATE = ON)")


def test_predicate_keys_on_the_callers_upn_and_allows_a_wildcard_region():
    function = next(s for s in statements([]) if s.startswith("CREATE FUNCTION"))
    assert "WITH SCHEMABINDING" in function
    assert "m.upn = LOWER(USER_NAME())" in function
    assert "m.region_id = '*'" in function


def test_statements_are_rerunnable():
    first, second = statements([])[:2]
    assert first == "DROP SECURITY POLICY IF EXISTS rls.region_policy"
    assert second == "DROP FUNCTION IF EXISTS rls.fn_region_filter"


def test_mapping_table_is_denied_to_each_user():
    denies = [s for s in statements(["north.mgr@example.onmicrosoft.com"]) if s.startswith("DENY")]
    assert denies == ["DENY SELECT ON rls.user_region TO [north.mgr@example.onmicrosoft.com]"]


@pytest.mark.parametrize(
    "upn", ["x]; DROP TABLE t; --@a.com", "North.Mgr@example.com", "no-at-sign"]
)
def test_only_plain_lowercase_upns_reach_tsql(upn):
    with pytest.raises(ValueError):
        quote_upn(upn)
