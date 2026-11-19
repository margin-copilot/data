"""Generates Riad Market's synthetic year of sales, deterministically from a seed.

Dairy margins hit the monthly targets in the catalog: the other dairy products' costs are
calibrated per region and month around the planted UHT cost rise and yogurt promotion."""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from riad_data import catalog as c

CENT = Decimal("0.01")
CALIBRATED_DAIRY = ["DAI-001", "DAI-004", "DAI-005", "DAI-006", "DAI-007", "DAI-008"]
FINE_TUNE_SKU = "DAI-006"
SUPPLIER = {"N": "SUP-014", "C": "SUP-027", "S": "SUP-033"}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Dataset:
    tables: dict[str, list[dict]] = field(default_factory=dict)


def days() -> list[date]:
    return [c.START + timedelta(n) for n in range((c.END - c.START).days + 1)]


def month_index(day: date) -> int:
    return (day.year - c.START.year) * 12 + day.month - c.START.month


def store_scale(store_id: str) -> float:
    return c.STORES[store_id][4] / 6500


def weekday_factor(day: date) -> float:
    return {4: 1.15, 5: 1.15, 6: 1.05}.get(day.weekday(), 0.95)


def shelf_price(region: str, sku: str, day: date) -> Decimal:
    price = c.PRODUCTS[sku][3]
    for change_sku, change_region, effective, new_price, *_ in sorted(
        c.PRICE_CHANGES.values(), key=lambda change: change[2]
    ):
        if (change_sku, change_region) == (sku, region) and effective <= day:
            price = new_price
    return price


def promotion(region: str, sku: str, day: date) -> tuple[str, int, int] | None:
    for promo_id, (p_sku, p_region, start, end, discount, funded) in c.PROMOTIONS.items():
        if (p_sku, p_region) == (sku, region) and start <= day <= end:
            return promo_id, discount, funded
    return None


def base_cost(region: str, sku: str) -> Decimal:
    if (sku, region) in c.FIXED_BASE_COSTS:
        return c.FIXED_BASE_COSTS[(sku, region)]
    if sku == "DAI-003":
        return c.DAIRY_YOGURT_COST
    category = c.PRODUCTS[sku][1]
    return money(c.PRODUCTS[sku][3] * (1 - c.BASE_MARGIN[category]))


def planted_cost(region: str, sku: str, day: date) -> Decimal | None:
    cost = None
    for c_sku, c_region, _supplier, effective, unit_cost in c.COST_CHANGES:
        if (c_sku, c_region) == (sku, region) and effective <= day:
            cost = unit_cost
    return cost


def generate(seed: int = c.SEED) -> Dataset:
    rng = random.Random(seed)
    rows: list[dict] = []
    for day in days():
        for store_id, (_name, _city, region, _format, _area) in c.STORES.items():
            closed = c.CLOSURES.get(store_id)
            if closed and closed[0] <= day <= closed[1]:
                continue
            for sku, (_pname, _cat, _tier, _price, base_units) in c.PRODUCTS.items():
                promo = promotion(region, sku, day)
                units = base_units * store_scale(store_id) * weekday_factor(day)
                if c.RAMADAN[0] <= day <= c.RAMADAN[1]:
                    units *= c.RAMADAN_UPLIFT.get(sku, 1.0)
                if promo:
                    units *= 1 + 2.5 * promo[1] / 100
                units = max(0, round(units * rng.gauss(1.0, 0.08)))
                price = shelf_price(region, sku, day)
                discount = Decimal(promo[1]) / 100 if promo else Decimal(0)
                rows.append(
                    {
                        "sale_date": day,
                        "store_id": store_id,
                        "region_id": region,
                        "sku": sku,
                        "units": units,
                        "shelf_price_mad": price,
                        "promo_id": promo[0] if promo else None,
                        "net_sales_mad": money(units * price * (1 - discount)),
                        "_funding": (price * discount * Decimal(promo[2]) / 100)
                        if promo
                        else Decimal(0),
                    }
                )
    costs = _costs(rows)
    for row in rows:
        unit_cost = costs[(row["region_id"], row["sku"], month_index(row["sale_date"]))]
        planted = planted_cost(row["region_id"], row["sku"], row["sale_date"])
        unit_cost = planted if planted is not None else unit_cost
        row["unit_cost_mad"] = unit_cost
        row["cogs_mad"] = money(row["units"] * (unit_cost - row.pop("_funding")))
    data = Dataset()
    data.tables["dim_region"] = [{"region_id": r, "name": n} for r, n in c.REGIONS.items()]
    data.tables["dim_store"] = [
        {
            "store_id": s,
            "store_name": n,
            "city": city,
            "region_id": r,
            "format": f,
            "sales_area_m2": a,
        }
        for s, (n, city, r, f, a) in c.STORES.items()
    ]
    data.tables["dim_product"] = [
        {"sku": sku, "product_name": n, "category": cat, "tier": t, "start_price_mad": p}
        for sku, (n, cat, t, p, _units) in c.PRODUCTS.items()
    ]
    data.tables["fact_sales"] = rows
    data.tables["supplier_costs"] = _supplier_costs(costs)
    data.tables["promotions"] = [
        {
            "promo_id": promo_id,
            "sku": sku,
            "region_id": region,
            "start_date": start,
            "end_date": end,
            "discount_pct": discount,
            "supplier_funded_pct": funded,
        }
        for promo_id, (sku, region, start, end, discount, funded) in c.PROMOTIONS.items()
    ]
    data.tables["price_history"] = _price_history()
    data.tables["competitor_prices"] = _competitor_prices()
    return data


def _supplier_costs(costs: dict[tuple[str, str, int], Decimal]) -> list[dict]:
    rows = []
    for region in c.REGIONS:
        for sku in c.PRODUCTS:
            months = range(12) if sku in CALIBRATED_DAIRY else range(1)
            for month in months:
                effective = date(
                    c.START.year + (c.START.month - 1 + month) // 12,
                    (c.START.month - 1 + month) % 12 + 1,
                    1,
                )
                rows.append(_cost_row(sku, region, effective, costs[(region, sku, month)]))
    for sku, region, supplier, effective, unit_cost in c.COST_CHANGES:
        rows.append(_cost_row(sku, region, effective, unit_cost, supplier))
    return sorted(rows, key=lambda r: (r["region_id"], r["sku"], r["effective_from"]))


def _cost_row(sku, region, effective, unit_cost, supplier=None) -> dict:
    return {
        "sku": sku,
        "region_id": region,
        "supplier_id": supplier or SUPPLIER[region],
        "effective_from": effective,
        "unit_cost_mad": unit_cost,
    }


def _price_history() -> list[dict]:
    rows = []
    for change_id, (sku, region, effective, new_price, reason, proposed, approved) in sorted(
        c.PRICE_CHANGES.items()
    ):
        old_price = shelf_price(region, sku, effective - timedelta(1))
        rows.append(
            {
                "change_id": change_id,
                "sku": sku,
                "region_id": region,
                "effective_date": effective,
                "old_price_mad": old_price,
                "new_price_mad": new_price,
                "change_pct": ((new_price - old_price) / old_price * 100).quantize(Decimal("0.1")),
                "reason_code": reason,
                "proposed_by": proposed,
                "approved_by": approved,
            }
        )
    return rows


def _competitor_prices() -> list[dict]:
    first_monday = c.START + timedelta((7 - c.START.weekday()) % 7)
    rows = []
    week = first_monday
    while week <= c.END:
        for region in c.REGIONS:
            for sku in c.COMPETITOR_SKUS:
                price = c.PRODUCTS[sku][3]
                planted = c.COMPETITOR_PLANTED.get((region, sku))
                if planted and planted[0] <= week:
                    price = planted[1]
                rows.append(
                    {
                        "week_start": week,
                        "region_id": region,
                        "sku": sku,
                        "competitor_price_mad": price,
                    }
                )
        week += timedelta(7)
    return rows


def _costs(rows: list[dict]) -> dict[tuple[str, str, int], Decimal]:
    """Unit cost per (region, sku, month), calibrating the other dairy products to the targets."""
    costs = {
        (region, sku, month): base_cost(region, sku)
        for region in c.REGIONS
        for sku in c.PRODUCTS
        for month in range(12)
    }
    sales: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        if c.PRODUCTS[row["sku"]][1] == "Dairy":
            sales[(row["region_id"], month_index(row["sale_date"]))].append(row)
    for (region, month), dairy in sales.items():
        target = Decimal(str(c.DAIRY_MARGIN_TARGET[region][month])) / 100
        net = sum(r["net_sales_mad"] for r in dairy)
        fixed = sum(
            r["units"]
            * (
                (planted_cost(region, r["sku"], r["sale_date"]) or base_cost(region, r["sku"]))
                - r["_funding"]
            )
            for r in dairy
            if r["sku"] not in CALIBRATED_DAIRY
        )
        base = sum(
            r["units"] * base_cost(region, r["sku"]) for r in dairy if r["sku"] in CALIBRATED_DAIRY
        )
        factor = (net * (1 - target) - fixed) / base
        for sku in CALIBRATED_DAIRY:
            costs[(region, sku, month)] = money(base_cost(region, sku) * factor)
        _fine_tune(costs, region, month, dairy, net, fixed, target)
    return costs


def _fine_tune(costs, region, month, dairy, net, fixed, target) -> None:
    """Absorbs the cent rounding of calibrated costs in one product, so targets hold."""

    def margin() -> Decimal:
        calibrated = sum(
            r["units"] * costs[(region, r["sku"], month)]
            for r in dairy
            if r["sku"] in CALIBRATED_DAIRY
        )
        return (net - fixed - calibrated) / net

    units = sum(r["units"] for r in dairy if r["sku"] == FINE_TUNE_SKU)
    gap = margin() - target  # positive: margin too high, raise the cost
    costs[(region, FINE_TUNE_SKU, month)] += money(gap * net / units)
