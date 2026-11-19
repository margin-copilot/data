import copy
from datetime import date

import pytest

from riad_data import checks
from riad_data.generate import generate


@pytest.fixture(scope="module")
def data():
    return generate()


def test_every_story_check_passes_on_the_generated_data(data):
    failures = [f"{name}: {detail}" for name, ok, detail in checks.run(data) if not ok]
    assert failures == []


def broken(data, table, mutate):
    copied = copy.deepcopy(data)
    mutate(copied.tables[table])
    return copied


def test_checks_catch_a_missing_closure(data):
    def reopen(rows):
        template = next(r for r in rows if r["store_id"] == "S02")
        rows.append({**template, "sale_date": date(2026, 7, 15)})

    name, ok, _ = checks.guelmim_gap(broken(data, "fact_sales", reopen))
    assert not ok, name


def test_checks_catch_a_changed_promotion(data):
    def unfund(rows):
        next(r for r in rows if r["promo_id"] == "P-2609-N-04")["supplier_funded_pct"] = 0

    assert not checks.promotions(broken(data, "promotions", unfund))[1]


def test_checks_catch_a_missing_approval(data):
    def drop_approval(rows):
        next(r for r in rows if r["change_id"] == "PH-0219")["approved_by"] = None

    assert not checks.price_changes(broken(data, "price_history", drop_approval))[1]


def test_checks_catch_an_off_target_margin(data):
    def raise_october_cost(rows):
        for r in rows:
            if r["region_id"] == "N" and r["sku"] == "DAI-006" and r["sale_date"].month == 10:
                r["cogs_mad"] *= 2

    assert not checks.dairy_margins(broken(data, "fact_sales", raise_october_cost))[1]
