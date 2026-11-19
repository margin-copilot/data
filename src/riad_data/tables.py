"""T-SQL tables for the dataset, the statements that create them, and rls.user_region rows
built from settings at load time (so no tenant UPN lives in the repo)."""

import re

NAME = "varchar(60)"
ID = "varchar(20)"
MONEY = "decimal(8,2)"
AMOUNT = "decimal(12,2)"

# table: [(column, T-SQL type)], in the generator's column order. "?" marks a nullable column.
COLUMNS = {
    "dim_region": [("region_id", "char(1)"), ("name", NAME)],
    "dim_store": [
        ("store_id", ID),
        ("store_name", NAME),
        ("city", NAME),
        ("region_id", "char(1)"),
        ("format", ID),
        ("sales_area_m2", "int"),
    ],
    "dim_product": [
        ("sku", ID),
        ("product_name", NAME),
        ("category", ID),
        ("tier", "char(1)"),
        ("start_price_mad", MONEY),
    ],
    "fact_sales": [
        ("sale_date", "date"),
        ("store_id", ID),
        ("region_id", "char(1)"),
        ("sku", ID),
        ("units", "int"),
        ("shelf_price_mad", MONEY),
        ("promo_id", f"{ID}?"),
        ("net_sales_mad", AMOUNT),
        ("unit_cost_mad", MONEY),
        ("cogs_mad", AMOUNT),
    ],
    "supplier_costs": [
        ("sku", ID),
        ("region_id", "char(1)"),
        ("supplier_id", ID),
        ("effective_from", "date"),
        ("unit_cost_mad", MONEY),
    ],
    "promotions": [
        ("promo_id", ID),
        ("sku", ID),
        ("region_id", "char(1)"),
        ("start_date", "date"),
        ("end_date", "date"),
        ("discount_pct", "int"),
        ("supplier_funded_pct", "int"),
    ],
    "price_history": [
        ("change_id", ID),
        ("sku", ID),
        ("region_id", "char(1)"),
        ("effective_date", "date"),
        ("old_price_mad", MONEY),
        ("new_price_mad", MONEY),
        ("change_pct", "decimal(5,1)"),
        ("reason_code", ID),
        ("proposed_by", f"{NAME}?"),
        ("approved_by", f"{NAME}?"),
    ],
    "competitor_prices": [
        ("week_start", "date"),
        ("region_id", "char(1)"),
        ("sku", ID),
        ("competitor_price_mad", MONEY),
    ],
    "user_region": [("upn", "varchar(256)"), ("region_id", "char(1)")],
}
SCHEMA_OF = {name: "dbo" for name in COLUMNS} | {"user_region": "rls"}
REGION_CODES = {"N", "C", "S", "*"}
ALIAS = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DOMAIN = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def full_name(table: str) -> str:
    return f"{SCHEMA_OF[table]}.{table}"


def create_statements() -> list[str]:
    statements = ["IF SCHEMA_ID('rls') IS NULL EXEC('CREATE SCHEMA rls')"]
    for table, columns in COLUMNS.items():
        definitions = ", ".join(
            f"{column} {kind.rstrip('?')} {'NULL' if kind.endswith('?') else 'NOT NULL'}"
            for column, kind in columns
        )
        statements += [
            f"DROP TABLE IF EXISTS {full_name(table)}",
            f"CREATE TABLE {full_name(table)} ({definitions})",
        ]
    return statements


def insert_statement(table: str) -> str:
    names = [column for column, _ in COLUMNS[table]]
    placeholders = ", ".join("?" * len(names))
    return f"INSERT INTO {full_name(table)} ({', '.join(names)}) VALUES ({placeholders})"


def rows_for(table: str, rows: list[dict]) -> list[tuple]:
    names = [column for column, _ in COLUMNS[table]]
    return [tuple(row[name] for name in names) for row in rows]


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
