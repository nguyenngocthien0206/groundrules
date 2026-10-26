"""The two demos make their point, and the drift demo always cleans up.

Needs `make build` first (the legacy dashboards read the marts).
"""

from datetime import date

import duckdb
import pytest

import conflict
import drift
from catalog import load_expected
from semantic_client import DUCKDB_FILE

AUGUST = "2026-08"


@pytest.fixture(scope="module")
def old() -> dict[str, float]:
    if not DUCKDB_FILE.exists():
        pytest.fail("No warehouse: run `make data && make build` first.")
    return conflict.legacy_numbers(AUGUST)


@pytest.fixture(scope="module")
def certified() -> float:
    return float(load_expected()["answers"]["GQ-REV-01"]["expected"])


@pytest.fixture(scope="module")
def marts():
    def one(sql: str) -> float:
        with duckdb.connect(str(DUCKDB_FILE)) as con:
            return float(con.execute(sql, {"s": date(2026, 8, 1), "e": date(2026, 8, 31)}).fetchone()[0])
    return one


def test_four_answers_to_one_question_all_differ(old, certified):
    numbers = [*old.values(), certified]
    assert len({round(n) for n in numbers}) == 4


def test_the_semantic_layer_gives_the_frozen_certified_answer(certified):
    from semantic_client import SemanticLayer

    assert conflict.certified_number(SemanticLayer(), AUGUST) == pytest.approx(certified, abs=1)


def test_the_sales_dashboard_is_off_by_exactly_the_month_refunds(old, certified, marts):
    refunds = marts("select sum(refund_excl_vat) from marts.fct_returns where return_date between $s and $e")
    assert old["sales_dashboard"] - certified == pytest.approx(refunds, abs=1)


def test_the_finance_dashboard_is_off_only_by_which_month_refunds_count_in(old, certified, marts):
    by_return = marts("select sum(refund_excl_vat) from marts.fct_returns where return_date between $s and $e")
    by_sale = marts("select sum(refund_excl_vat) from marts.fct_returns where sale_business_date between $s and $e")
    assert old["finance_dashboard"] - certified == pytest.approx(by_return - by_sale, abs=1)


def test_the_ops_report_is_the_till_with_vat(old, marts):
    paid = marts("select sum(amount_incl_vat) from marts.fct_sales where business_date between $s and $e")
    refunded = marts("select sum(refund_incl_vat) from marts.fct_returns where return_date between $s and $e")
    assert old["ops_weekly_report"] == pytest.approx(paid - refunded, abs=1)


def test_every_gap_names_a_decision_record():
    for _, _, _, record in conflict.LEGACY:
        assert conflict.decision(record)["status"] == "accepted"


# Drift demo


def test_the_drift_changes_exactly_one_threshold():
    text = f"a\nfilter: \"{drift.BEFORE}\"\nb\n"
    assert drift.apply_drift(text) == f"a\nfilter: \"{drift.AFTER}\"\nb\n"


@pytest.mark.parametrize("text", ["no filter here", f"{drift.BEFORE}\n{drift.BEFORE}"])
def test_the_drift_refuses_when_the_rule_is_missing_or_ambiguous(text):
    with pytest.raises(ValueError):
        drift.apply_drift(text)


@pytest.fixture
def rule_copy(tmp_path, monkeypatch):
    """Point the demo at a copy of the rule file and skip dbt, so no real file is touched."""
    copy = tmp_path / "fct_inventory_batch.yml"
    copy.write_bytes(drift.RULE_FILE.read_bytes())
    monkeypatch.setattr(drift, "RULE_FILE", copy)
    monkeypatch.setattr(drift, "dbt_parse", lambda: None)
    return copy


def test_the_rule_file_is_restored_even_when_a_step_fails(rule_copy, monkeypatch):
    original = rule_copy.read_bytes()

    def boom() -> int:
        assert drift.AFTER in rule_copy.read_text(encoding="utf-8")  # the drift was really applied
        raise RuntimeError("the warehouse went away mid-demo")

    monkeypatch.setattr(drift, "show_safeguards", boom)
    with pytest.raises(RuntimeError):
        drift.main()
    assert rule_copy.read_bytes() == original


def test_the_demo_only_succeeds_when_golden_questions_catch_the_drift(rule_copy, monkeypatch):
    monkeypatch.setattr(drift, "show_safeguards", lambda: 4)
    assert drift.main() == 0
    monkeypatch.setattr(drift, "show_safeguards", lambda: 0)
    assert drift.main() == 1
