"""Story checks: every planted fact the eval cases rely on, computed from the generated tables.
Each check returns (name, passed, detail). Used by the tests and by the live Fabric check."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from riad_data import catalog as c
from riad_data.generate import Dataset, days, month_index

Check = tuple[str, bool, str]


def margin(rows: list[dict]) -> float:
    net = sum(r["net_sales_mad"] for r in rows)
    return float((net - sum(r["cogs_mad"] for r in rows)) / net * 100)


def run(data: Dataset) -> list[Check]:
    return [check(data) for check in CHECKS]


def row_count(data: Dataset) -> Check:
    rows = data.tables["fact_sales"]
    expected = len(days()) * len(c.STORES) * len(c.PRODUCTS) - 3 * len(c.PRODUCTS)
    return ("row count", len(rows) == expected == 98_460, f"{len(rows)} rows")


def guelmim_gap(data: Dataset) -> Check:
    closed = [
        r
        for r in data.tables["fact_sales"]
        if r["store_id"] == "S02" and date(2026, 7, 14) <= r["sale_date"] <= date(2026, 7, 16)
    ]
    open_days = {r["sale_date"] for r in data.tables["fact_sales"] if r["store_id"] == "S02"}
    ok = not closed and date(2026, 7, 13) in open_days and date(2026, 7, 17) in open_days
    return ("Guelmim closed 14-16 Jul 2026, open around it", ok, f"{len(closed)} rows while closed")


def dairy_margins(data: Dataset) -> Check:
    by_month = defaultdict(list)
    for r in data.tables["fact_sales"]:
        if c.PRODUCTS[r["sku"]][1] == "Dairy":
            by_month[(r["region_id"], month_index(r["sale_date"]))].append(r)
    misses = [
        f"{region}{month}: {margin(by_month[(region, month)]):.2f} vs {target}"
        for region, targets in c.DAIRY_MARGIN_TARGET.items()
        for month, target in enumerate(targets)
        if abs(margin(by_month[(region, month)]) - target) >= 0.05
    ]
    return ("dairy margin by region and month", not misses, "; ".join(misses) or "all 36 on target")


def north_october_bridge(data: Dataset) -> Check:
    october = [
        r
        for r in data.tables["fact_sales"]
        if r["region_id"] == "N"
        and c.PRODUCTS[r["sku"]][1] == "Dairy"
        and month_index(r["sale_date"]) == 11
    ]
    net = sum(r["net_sales_mad"] for r in october)
    uht_units = sum(r["units"] for r in october if r["sku"] == "DAI-002")
    uht = float(-uht_units * (Decimal("5.62") - Decimal("5.30")) / net * 100)
    yogurt = [r for r in october if r["sku"] == "DAI-003"]
    september_terms = sum(r["units"] for r in yogurt) * (Decimal("8.00") - Decimal("5.80"))
    promo = float(
        (sum(r["net_sales_mad"] - r["cogs_mad"] for r in yogurt) - september_terms) / net * 100
    )
    ok = abs(uht + 1.6) <= 0.2 and abs(promo + 1.0) <= 0.2
    return (
        "North dairy Sep->Oct bridge",
        ok,
        f"UHT {uht:.2f} pts, yogurt promotion {promo:.2f} pts",
    )


def uht_cost(data: Dataset) -> Check:
    costs = {
        r["sale_date"]: r["unit_cost_mad"]
        for r in data.tables["fact_sales"]
        if r["region_id"] == "N" and r["sku"] == "DAI-002"
    }
    ok = costs[date(2026, 9, 30)] == Decimal("5.30") and costs[date(2026, 10, 1)] == Decimal("5.62")
    return (
        "North UHT cost 5.30 -> 5.62 on 1 Oct",
        ok,
        f"{costs[date(2026, 9, 30)]} -> {costs[date(2026, 10, 1)]}",
    )


def competitor_uht(data: Dataset) -> Check:
    latest = max(
        (
            r
            for r in data.tables["competitor_prices"]
            if r["region_id"] == "N" and r["sku"] == "DAI-002"
        ),
        key=lambda r: r["week_start"],
    )
    index = float(Decimal("7.00") / latest["competitor_price_mad"] * 100)
    ok = latest["competitor_price_mad"] == Decimal("7.20") and round(index, 1) == 97.2
    return (
        "competitor UHT North 7.20, index 97.2",
        ok,
        f"{latest['competitor_price_mad']}, index {index:.1f}",
    )


def promotions(data: Dataset) -> Check:
    found = {
        r["promo_id"]: (r["discount_pct"], r["supplier_funded_pct"])
        for r in data.tables["promotions"]
    }
    expected = {promo_id: (p[4], p[5]) for promo_id, p in c.PROMOTIONS.items()}
    return ("planted promotions", found == expected, f"{len(found)} promotions")


def price_changes(data: Dataset) -> Check:
    found = {
        r["change_id"]: (
            str(r["old_price_mad"]),
            str(r["new_price_mad"]),
            str(r["change_pct"]),
            r["approved_by"],
        )
        for r in data.tables["price_history"]
    }
    expected = {
        "PH-0187": ("7.00", "9.50", "35.7", None),
        "PH-0219": ("35.00", "36.00", "2.9", "pricing.director"),
        "PH-0341": ("75.00", "80.25", "7.0", None),
        "PH-0402": ("6.00", "5.50", "-8.3", None),
    }
    return ("planted price changes", found == expected, str(found))


def south_water_match(data: Dataset) -> Check:
    south_bev = [
        r
        for r in data.tables["fact_sales"]
        if r["region_id"] == "S" and c.PRODUCTS[r["sku"]][1] == "Beverages"
    ]
    july = margin(
        [r for r in south_bev if r["sale_date"].month == 7 and r["sale_date"].year == 2026]
    )
    after = margin(
        [r for r in south_bev if date(2026, 8, 12) <= r["sale_date"] <= date(2026, 8, 31)]
    )
    drop = july - after
    return (
        "South beverage margin ~3 pts lower after 11 Aug",
        2.0 <= drop <= 4.0,
        f"{july:.1f} -> {after:.1f}",
    )


def center_tomato_spike(data: Dataset) -> Check:
    produce = [
        r
        for r in data.tables["fact_sales"]
        if r["region_id"] == "C" and c.PRODUCTS[r["sku"]][1] == "Produce"
    ]

    def window(start: date, end: date) -> float:
        return margin([r for r in produce if start <= r["sale_date"] <= end])

    before = window(date(2026, 1, 8), date(2026, 1, 14))
    spike = window(date(2026, 1, 15), date(2026, 1, 18))
    after = window(date(2026, 1, 19), date(2026, 1, 25))
    ok = before - spike >= 3 and abs(after - before) <= 1.5
    return (
        "Center produce dips 15-18 Jan, recovers from 19 Jan",
        ok,
        f"{before:.1f} / {spike:.1f} / {after:.1f}",
    )


def ramadan_demand(data: Dataset) -> Check:
    start, end = c.RAMADAN
    totals = defaultdict(lambda: [0, 0, 0, 0])  # in-units, in-days, out-units, out-days per sku
    for r in data.tables["fact_sales"]:
        if r["sku"] in c.RAMADAN_UPLIFT and r["store_id"] != "S02" and r["promo_id"] is None:
            inside = start <= r["sale_date"] <= end
            totals[r["sku"]][0 if inside else 2] += r["units"]
            totals[r["sku"]][1 if inside else 3] += 1
    ratios = {sku: (t[0] / t[1]) / (t[2] / t[3]) for sku, t in totals.items()}
    ok = all(abs(ratios[sku] - uplift) <= 0.15 for sku, uplift in c.RAMADAN_UPLIFT.items())
    return (
        "Ramadan demand uplift",
        ok,
        ", ".join(f"{sku} {ratio:.2f}" for sku, ratio in ratios.items()),
    )


CHECKS = [
    row_count,
    guelmim_gap,
    dairy_margins,
    north_october_bridge,
    uht_cost,
    competitor_uht,
    promotions,
    price_changes,
    south_water_match,
    center_tomato_spike,
    ramadan_demand,
]
