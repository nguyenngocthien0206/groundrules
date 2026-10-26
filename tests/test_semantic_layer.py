"""Smoke tests for the semantic layer, through MetricFlow's Python engine.

These check that every metric runs and that each written-down rule moves the
number in the expected direction. They are not golden questions: expected
values come from the independent reference computations in step 5.

Run after `make build`, which creates the DuckDB file and the manifests.
"""

import json

import pytest

from semantic_client import DBT_DIR, SEMANTIC_MANIFEST, SemanticLayer

GOVERNANCE_FIELDS = {"version", "status", "certified_on", "recertify_every_days", "decision", "replaced_by", "agent_notes"}
CERTIFIED = {"available_stock", "near_expiry_value", "net_revenue", "gross_margin", "sell_through_rate", "days_of_cover"}

SNAPSHOT_DAY = "{{ TimeDimension('metric_time', 'day') }} = '2026-09-15'"
AUGUST = "{{ TimeDimension('metric_time', 'month') }} = '2026-08-01'"


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not SEMANTIC_MANIFEST.exists():
        pytest.fail("No semantic manifest: run `make data && make build` first.")
    return json.loads(SEMANTIC_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def query():
    """The shared semantic layer client's query function (golden/semantic_client.py)."""
    try:
        return SemanticLayer().query
    except FileNotFoundError as e:
        pytest.fail(str(e))


def _metric(manifest: dict, name: str) -> dict:
    return next(m for m in manifest["metrics"] if m["name"] == name)


def test_visible_metrics_are_the_certified_ones_and_the_deprecated_one(manifest):
    visible = {m["name"] for m in manifest["metrics"] if not m["type_params"].get("is_private")}
    assert visible == CERTIFIED | {"revenue_v1"}


def test_certified_and_deprecated_metrics_carry_an_owner_and_governance_fields(manifest):
    dbt_manifest = json.loads((DBT_DIR / "target" / "manifest.json").read_text(encoding="utf-8"))
    groups = {m["name"]: m["config"].get("group") for m in dbt_manifest["metrics"].values()}
    for name in CERTIFIED | {"revenue_v1"}:
        meta = _metric(manifest, name)["config"]["meta"]
        assert groups[name] in {"supply_chain_ops", "finance"}, name
        assert GOVERNANCE_FIELDS <= set(meta), name
        assert meta["status"] == ("deprecated" if name == "revenue_v1" else "certified"), name


def test_deprecated_metric_points_to_a_certified_replacement(manifest):
    replacement = _metric(manifest, "revenue_v1")["config"]["meta"]["replaced_by"]
    assert _metric(manifest, replacement)["config"]["meta"]["status"] == "certified"


def test_every_certified_metric_returns_a_number(query):
    stock = query(["available_stock", "near_expiry_value", "days_of_cover"], ["metric_time__day"], [SNAPSHOT_DAY])
    flows = query(["net_revenue", "gross_margin", "sell_through_rate"], ["metric_time__month"], [AUGUST])
    for row in stock + flows:
        assert all(v is not None for v in row.values()), row


def test_available_stock_excludes_short_dated_and_in_transit_stock(query):
    row = query(["available_stock", "on_hand_units"], ["metric_time__day"], [SNAPSHOT_DAY])[0]
    assert 0 < row["available_stock"] < row["on_hand_units"]


def test_every_store_has_available_stock_even_without_transfers_in_transit(query):
    rows = query(["available_stock"], ["store", "metric_time__day"], [SNAPSHOT_DAY])
    assert len(rows) == 30
    assert all(r["available_stock"] is not None and r["available_stock"] > 0 for r in rows)


def test_net_revenue_is_below_the_deprecated_revenue_v1(query):
    row = query(["net_revenue", "revenue_v1"], ["metric_time__month"], [AUGUST])[0]
    # revenue_v1 keeps VAT and ignores returns.
    assert row["net_revenue"] < row["revenue_v1"] / 1.04


def test_gross_margin_is_a_plausible_share_of_net_revenue(query):
    row = query(["gross_margin", "net_revenue"], ["metric_time__month"], [AUGUST])[0]
    assert 0.15 < row["gross_margin"] / row["net_revenue"] < 0.5


def test_chain_sell_through_is_plausible(query):
    row = query(["sell_through_rate"], ["metric_time__month"], [AUGUST])[0]
    assert 0.5 < row["sell_through_rate"] < 1.5


def test_days_of_cover_works_with_a_store_filter(query):
    rows = query(
        ["days_of_cover"],
        ["store", "metric_time__day"],
        [SNAPSHOT_DAY, "{{ Entity('store') }} in ('NW001', 'NW029')"],
    )
    cover = {r["store"]: r["days_of_cover"] for r in rows}
    assert set(cover) == {"NW001", "NW029"}
    assert all(5 < c < 120 for c in cover.values())
