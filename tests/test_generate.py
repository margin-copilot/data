from decimal import Decimal

import pytest

from riad_data.generate import generate

COLUMNS = {
    "dim_region": ["region_id", "name"],
    "dim_store": ["store_id", "store_name", "city", "region_id", "format", "sales_area_m2"],
    "dim_product": ["sku", "product_name", "category", "tier", "start_price_mad"],
    "fact_sales": [
        "sale_date",
        "store_id",
        "region_id",
        "sku",
        "units",
        "shelf_price_mad",
        "promo_id",
        "net_sales_mad",
        "unit_cost_mad",
        "cogs_mad",
    ],
    "supplier_costs": ["sku", "region_id", "supplier_id", "effective_from", "unit_cost_mad"],
    "promotions": [
        "promo_id",
        "sku",
        "region_id",
        "start_date",
        "end_date",
        "discount_pct",
        "supplier_funded_pct",
    ],
    "price_history": [
        "change_id",
        "sku",
        "region_id",
        "effective_date",
        "old_price_mad",
        "new_price_mad",
        "change_pct",
        "reason_code",
        "proposed_by",
        "approved_by",
    ],
    "competitor_prices": ["week_start", "region_id", "sku", "competitor_price_mad"],
}


@pytest.fixture(scope="module")
def data():
    return generate()


def test_same_seed_same_data(data):
    again = generate()
    assert again.tables["fact_sales"][:500] == data.tables["fact_sales"][:500]
    assert again.tables["fact_sales"][-500:] == data.tables["fact_sales"][-500:]


def test_another_seed_changes_the_noise_but_not_the_stories():
    other = generate(seed=7).tables["fact_sales"]
    base = generate().tables["fact_sales"]
    assert [r["units"] for r in other[:200]] != [r["units"] for r in base[:200]]


def test_every_table_has_its_columns_in_order(data):
    assert set(data.tables) == set(COLUMNS)
    for name, columns in COLUMNS.items():
        assert all(list(row) == columns for row in data.tables[name]), name


def test_values_are_plausible(data):
    for row in data.tables["fact_sales"]:
        assert row["units"] >= 0
        assert row["unit_cost_mad"] > 0
        assert row["net_sales_mad"] >= 0
        assert row["region_id"] == row["store_id"][0]


def test_every_regional_table_carries_region_id(data):
    for name in (
        "fact_sales",
        "supplier_costs",
        "promotions",
        "price_history",
        "competitor_prices",
    ):
        assert {row["region_id"] for row in data.tables[name]} <= {"N", "C", "S"}, name


def test_money_has_two_decimals(data):
    for row in data.tables["fact_sales"][:5000]:
        for column in ("shelf_price_mad", "net_sales_mad", "unit_cost_mad", "cogs_mad"):
            assert row[column] == row[column].quantize(Decimal("0.01")), column
