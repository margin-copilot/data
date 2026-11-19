"""Arrow schemas for every table, and writing the dataset as Delta tables, locally or to OneLake.
Dates are date32 and money is decimal: no naive timestamps, which the SQL endpoint can't read."""

import re

import pyarrow as pa
from deltalake import write_deltalake

from riad_data.generate import Dataset

MONEY = pa.decimal128(8, 2)
AMOUNT = pa.decimal128(12, 2)
S = pa.string()
DATE = pa.date32()

SCHEMAS = {
    "dim_region": pa.schema([("region_id", S), ("name", S)]),
    "dim_store": pa.schema(
        [
            ("store_id", S),
            ("store_name", S),
            ("city", S),
            ("region_id", S),
            ("format", S),
            ("sales_area_m2", pa.int32()),
        ]
    ),
    "dim_product": pa.schema(
        [("sku", S), ("product_name", S), ("category", S), ("tier", S), ("start_price_mad", MONEY)]
    ),
    "fact_sales": pa.schema(
        [
            ("sale_date", DATE),
            ("store_id", S),
            ("region_id", S),
            ("sku", S),
            ("units", pa.int32()),
            ("shelf_price_mad", MONEY),
            ("promo_id", S),
            ("net_sales_mad", AMOUNT),
            ("unit_cost_mad", MONEY),
            ("cogs_mad", AMOUNT),
        ]
    ),
    "supplier_costs": pa.schema(
        [
            ("sku", S),
            ("region_id", S),
            ("supplier_id", S),
            ("effective_from", DATE),
            ("unit_cost_mad", MONEY),
        ]
    ),
    "promotions": pa.schema(
        [
            ("promo_id", S),
            ("sku", S),
            ("region_id", S),
            ("start_date", DATE),
            ("end_date", DATE),
            ("discount_pct", pa.int32()),
            ("supplier_funded_pct", pa.int32()),
        ]
    ),
    "price_history": pa.schema(
        [
            ("change_id", S),
            ("sku", S),
            ("region_id", S),
            ("effective_date", DATE),
            ("old_price_mad", MONEY),
            ("new_price_mad", MONEY),
            ("change_pct", pa.decimal128(5, 1)),
            ("reason_code", S),
            ("proposed_by", S),
            ("approved_by", S),
        ]
    ),
    "competitor_prices": pa.schema(
        [("week_start", DATE), ("region_id", S), ("sku", S), ("competitor_price_mad", MONEY)]
    ),
    "user_region": pa.schema([("upn", S), ("region_id", S)]),
}
SCHEMA_OF = {name: "dbo" for name in SCHEMAS} | {"user_region": "rls"}
REGION_CODES = {"N", "C", "S", "*"}
ALIAS = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DOMAIN = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def user_region_rows(domain: str, user_regions: str) -> list[dict]:
    """USER_REGIONS from .env, e.g. "north.mgr:N,pricing.director:*", into rls.user_region rows."""
    domain = domain.strip().lower()
    if not DOMAIN.match(domain):
        raise ValueError(f"invalid domain {domain!r}")
    rows = []
    for entry in user_regions.split(","):
        alias, _, region = entry.strip().partition(":")
        alias = alias.strip().lower()
        if not ALIAS.match(alias) or region not in REGION_CODES:
            raise ValueError(f"invalid USER_REGIONS entry {entry!r}")
        rows.append({"upn": f"{alias}@{domain}", "region_id": region})
    return rows


def to_arrow(data: Dataset, user_region: list[dict]) -> dict[str, pa.Table]:
    tables = {
        name: pa.Table.from_pylist(rows, schema=SCHEMAS[name]) for name, rows in data.tables.items()
    }
    tables["user_region"] = pa.Table.from_pylist(user_region, schema=SCHEMAS["user_region"])
    return tables


def onelake_uri(workspace_id: str, lakehouse_id: str) -> str:
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}"


def write_tables(
    base_uri: str, tables: dict[str, pa.Table], storage_options: dict[str, str] | None = None
) -> list[str]:
    written = []
    for name, table in tables.items():
        uri = f"{base_uri}/Tables/{SCHEMA_OF[name]}/{name}"
        write_deltalake(
            uri, table, mode="overwrite", schema_mode="overwrite", storage_options=storage_options
        )
        written.append(f"{SCHEMA_OF[name]}.{name}")
    return written
