import pytest

from riad_data.generate import generate
from riad_data.tables import (
    COLUMNS,
    create_statements,
    insert_statement,
    rows_for,
    user_region_rows,
)


def test_user_region_rows_come_from_config():
    assert user_region_rows("Example.onmicrosoft.com", "North.Mgr:N, pricing.director:*") == [
        {"upn": "north.mgr@example.onmicrosoft.com", "region_id": "N"},
        {"upn": "pricing.director@example.onmicrosoft.com", "region_id": "*"},
    ]


@pytest.mark.parametrize(
    ("domain", "users"),
    [
        ("example.onmicrosoft.com", "north.mgr:X"),
        ("example.onmicrosoft.com", "north mgr:N"),
        ("example.onmicrosoft.com", "north.mgr]:N"),
        ("not a domain", "north.mgr:N"),
    ],
)
def test_bad_user_regions_are_rejected(domain, users):
    with pytest.raises(ValueError):
        user_region_rows(domain, users)


def test_columns_match_the_generator_exactly():
    data = generate()
    for table, rows in data.tables.items():
        assert [column for column, _ in COLUMNS[table]] == list(rows[0]), table


def test_create_statements_recreate_every_table_with_nullability():
    statements = create_statements()
    assert statements[0] == "IF SCHEMA_ID('rls') IS NULL EXEC('CREATE SCHEMA rls')"
    fact = next(s for s in statements if s.startswith("CREATE TABLE dbo.fact_sales"))
    assert "promo_id varchar(20) NULL" in fact and "units int NOT NULL" in fact
    assert "net_sales_mad decimal(12,2) NOT NULL" in fact
    assert "DROP TABLE IF EXISTS rls.user_region" in statements
    assert sum(s.startswith("CREATE TABLE") for s in statements) == len(COLUMNS)


def test_inserts_use_parameters_in_column_order():
    assert (
        insert_statement("dim_region")
        == "INSERT INTO dbo.dim_region (region_id, name) VALUES (?, ?)"
    )
    assert rows_for("dim_region", [{"region_id": "N", "name": "North"}]) == [("N", "North")]
