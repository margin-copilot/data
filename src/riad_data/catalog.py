"""Riad Market's fixed facts: regions, stores, products and the planted stories' numbers.
Every value here comes from the dataset and policy previews (docs: dataset preview, PP-01…PP-07)."""

from datetime import date
from decimal import Decimal as D

START = date(2025, 11, 1)
END = date(2026, 10, 31)  # inclusive: one year of sales
SEED = 42

REGIONS = {"N": "North", "C": "Center", "S": "South"}

# store_id: (store_name, city, region_id, format, sales_area_m2)
STORES = {
    "N01": ("Tanger Malabata", "Tanger", "N", "Hyper", 6500),
    "N02": ("Tétouan Centre", "Tétouan", "N", "Super", 2200),
    "N03": ("Larache", "Larache", "N", "Super", 1800),
    "C01": ("Casablanca Maarif", "Casablanca", "C", "Hyper", 7200),
    "C02": ("Rabat Agdal", "Rabat", "C", "Super", 2600),
    "C03": ("Kénitra", "Kénitra", "C", "Super", 2000),
    "S01": ("Agadir Founty", "Agadir", "S", "Hyper", 5800),
    "S02": ("Guelmim", "Guelmim", "S", "Super", 1500),
    "S03": ("Tiznit", "Tiznit", "S", "Super", 1600),
}

# sku: (product_name, category, tier, start_price_mad, base_daily_units_in_a_hyper)
PRODUCTS = {
    "DAI-001": ("Fresh milk 1 L", "Dairy", "A", D("6.50"), 380),
    "DAI-002": ("UHT milk 1 L", "Dairy", "B", D("7.00"), 500),
    "DAI-003": ("Plain yogurt 4 × 110 g", "Dairy", "B", D("10.00"), 28),
    "DAI-004": ("Lben 1 L", "Dairy", "B", D("8.00"), 120),
    "DAI-005": ("Drinking yogurt 6 × 170 ml", "Dairy", "B", D("13.50"), 60),
    "DAI-006": ("Butter 250 g", "Dairy", "B", D("22.00"), 45),
    "DAI-007": ("Cheese spread, 8 portions", "Dairy", "C", D("14.00"), 40),
    "DAI-008": ("Fresh cream 200 ml", "Dairy", "C", D("9.50"), 35),
    "BAK-001": ("Baguette 250 g", "Bakery", "A", D("1.20"), 900),
    "BAK-002": ("Msemen, 5 pieces", "Bakery", "B", D("6.00"), 150),
    "BAK-003": ("Sliced bread 500 g", "Bakery", "B", D("9.00"), 110),
    "GRO-001": ("Sugar 1 kg", "Grocery", "A", D("6.60"), 260),
    "GRO-002": ("Soft wheat flour 5 kg", "Grocery", "A", D("35.00"), 90),
    "GRO-003": ("Sunflower oil 1 L", "Grocery", "A", D("18.50"), 140),
    "GRO-004": ("Green tea 200 g", "Grocery", "A", D("16.00"), 120),
    "GRO-005": ("Couscous 1 kg", "Grocery", "B", D("14.00"), 80),
    "GRO-006": ("Lentils 1 kg", "Grocery", "B", D("18.00"), 50),
    "GRO-007": ("Tomato paste 400 g", "Grocery", "B", D("8.50"), 90),
    "GRO-008": ("Olive oil 1 L", "Grocery", "B", D("75.00"), 30),
    "BEV-001": ("Mineral water 1.5 L", "Beverages", "A", D("6.00"), 280),
    "BEV-002": ("Orange juice 1 L", "Beverages", "C", D("15.00"), 50),
    "BEV-003": ("Cola 1 L", "Beverages", "C", D("9.00"), 110),
    "PRO-001": ("Tomatoes 1 kg", "Produce", "A", D("7.00"), 230),
    "PRO-002": ("Potatoes 1 kg", "Produce", "A", D("5.00"), 260),
    "PRO-003": ("Onions 1 kg", "Produce", "A", D("6.00"), 200),
    "PRO-004": ("Oranges 1 kg", "Produce", "B", D("6.00"), 150),
    "PRO-005": ("Medjool dates 500 g", "Produce", "C", D("45.00"), 25),
    "HOU-001": ("Dish soap 1 L", "Household", "C", D("12.00"), 45),
    "HOU-002": ("Laundry powder 3 kg", "Household", "B", D("55.00"), 25),
    "HOU-003": ("Bleach 1 L", "Household", "C", D("8.00"), 55),
}

# Base gross margin by category, before stories and calibration.
BASE_MARGIN = {
    "Dairy": D("0.24"),
    "Bakery": D("0.18"),
    "Grocery": D("0.17"),
    "Beverages": D("0.22"),
    "Produce": D("0.20"),
    "Household": D("0.27"),
}

# Dairy margin targets by region, Nov 2025 … Oct 2026 (dataset preview chart).
DAIRY_MARGIN_TARGET = {
    "N": [23.9, 24.0, 23.8, 24.4, 24.6, 24.0, 23.9, 24.1, 24.0, 24.2, 24.1, 21.3],
    "C": [23.4, 23.6, 23.3, 23.9, 24.1, 23.5, 23.4, 23.6, 23.5, 23.6, 23.5, 23.6],
    "S": [24.2, 24.3, 24.1, 24.7, 24.9, 24.3, 24.2, 24.4, 24.3, 24.4, 24.3, 24.2],
}

RAMADAN = (date(2026, 2, 18), date(2026, 3, 19))
RAMADAN_UPLIFT = {"PRO-005": 2.2, "BAK-002": 1.8, "GRO-002": 1.5, "DAI-001": 1.3, "DAI-002": 1.3}

CLOSURES = {"S02": (date(2026, 7, 14), date(2026, 7, 16))}  # Guelmim renovation: no rows

# promo_id: (sku, region, start, end, discount_pct, supplier_funded_pct)
PROMOTIONS = {
    "P-2602-C-11": ("PRO-005", "C", date(2026, 2, 1), date(2026, 2, 14), 15, 30),
    "P-2608-S-05": ("BEV-001", "S", date(2026, 8, 1), date(2026, 8, 10), 10, 0),
    "P-2609-N-04": ("DAI-003", "N", date(2026, 9, 1), date(2026, 9, 30), 20, 50),
    "P-2610-N-07": ("DAI-003", "N", date(2026, 10, 1), date(2026, 10, 31), 30, 0),
    "P-2610-S-02": ("DAI-003", "S", date(2026, 10, 1), date(2026, 10, 31), 20, 50),
}

# change_id: (sku, region, effective_date, new_price, reason, proposed_by, approved_by)
PRICE_CHANGES = {
    "PH-0187": ("PRO-001", "C", date(2026, 1, 19), D("9.50"), "COST", "center.mgr", None),
    "PH-0219": (
        "GRO-002",
        "N",
        date(2026, 2, 25),
        D("36.00"),
        "COST",
        "north.mgr",
        "pricing.director",
    ),
    "PH-0341": ("GRO-008", "C", date(2026, 6, 8), D("80.25"), "COST", "center.mgr", None),
    "PH-0402": ("BEV-001", "S", date(2026, 8, 11), D("5.50"), "COMP", "south.mgr", None),
}

# Planted supplier cost changes: (sku, region, supplier_id, effective_from, unit_cost)
COST_CHANGES = [
    ("DAI-002", "N", "SUP-014", date(2026, 10, 1), D("5.62")),
    ("PRO-001", "C", "SUP-040", date(2026, 1, 15), D("6.90")),
]
FIXED_BASE_COSTS = {
    ("DAI-002", "N"): D("5.30"),
    ("DAI-002", "S"): D("5.30"),
    ("PRO-001", "C"): D("5.10"),
}
DAIRY_YOGURT_COST = D("6.80")

# Reference competitor, weekly (week_start Mondays). Planted values override the default.
COMPETITOR_SKUS = ["DAI-001", "DAI-002", "BEV-001", "GRO-002", "PRO-001"]
COMPETITOR_PLANTED = {
    ("S", "BEV-001"): (date(2026, 8, 10), D("5.50")),  # cut from the week of 10 Aug
    ("N", "DAI-002"): (date(2026, 10, 5), D("7.20")),
}
