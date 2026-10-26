"""The dashboard shows the certified numbers, and the report only asks for what exists.

Needs `make build` and `make dashboard-data` (`make test` runs the export first).
"""

import json
from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import export
from catalog import load_expected
from repo import ROOT, load, parse_tmdl_table

EXPORTS = ROOT / "dashboards" / "exports"
TABLES = ROOT / "dashboards" / "groundrules.SemanticModel" / "definition" / "tables"
PAGES = ROOT / "dashboards" / "groundrules.Report" / "definition" / "pages"
MONTHLY = ["revenue_by_month", "revenue_by_district_month", "revenue_by_category_month", "sell_through_by_store_month"]
# The tills' history; the extracts are fixed by tests/fixtures/expected_manifest.json.
POS_FIRST_DAY, POS_LAST_DAY = date(2026, 3, 15), date(2026, 9, 14)


@pytest.fixture(scope="module")
def exports() -> dict[str, list[dict]]:
    if not (EXPORTS / "metric_versions.parquet").exists():
        pytest.fail("No exports: run `make dashboard-data` first.")
    return {p.stem: pq.read_table(p).to_pylist() for p in EXPORTS.glob("*.parquet")}


@pytest.fixture(scope="module")
def expected() -> dict:
    return load_expected()["answers"]


def _row(rows: list[dict], **keys) -> dict:
    found = [r for r in rows if all(r[k] == v for k, v in keys.items())]
    assert len(found) == 1, keys
    return found[0]


def _caveats(expected_caveats: list[str]) -> str:
    return ", ".join(expected_caveats)  # the dashboard uses the golden questions' words


# (export, row keys, metric column, golden question, tolerance)
SAME_SLICE = [
    ("revenue_by_month", {"month": date(2026, 8, 1)}, "net_revenue", "GQ-REV-01", 1),
    ("revenue_by_district_month", {"month": date(2026, 8, 1), "district_code": "D02"}, "net_revenue", "GQ-POS-04", 1),
    ("revenue_by_district_month", {"month": date(2026, 9, 1), "district_code": "D05"}, "net_revenue", "GQ-POS-03", 1),
    ("revenue_by_category_month", {"month": date(2026, 7, 1), "category_code": "VITA"}, "net_revenue", "GQ-REV-03", 1),
    ("revenue_by_category_month", {"month": date(2026, 7, 1), "category_code": "VITA"}, "gross_margin", "GQ-MARGIN-03", 100),
    ("sell_through_by_store_month", {"month": date(2026, 8, 1), "store_code": "NW014"}, "sell_through_rate", "GQ-SELL-01", 0.0001),
    ("sell_through_by_store_month", {"month": date(2026, 9, 1), "store_code": "NW030"}, "sell_through_rate", "GQ-SELL-04", 0.0001),
    ("sell_through_by_store_month", {"month": date(2026, 8, 1), "store_code": "NW030"}, "sell_through_rate", "GQ-SELL-05", 0.0001),
    ("stock_by_store", {"store_code": "NW001"}, "days_of_cover", "GQ-COVER-01", 0.0001),
    ("stock_by_store", {"store_code": "NW029"}, "days_of_cover", "GQ-COVER-02", 0.0001),
    ("stock_by_category", {"category_code": "VITA"}, "near_expiry_value", "GQ-STOCK-08", 1),
]


@pytest.mark.parametrize(("export", "keys", "column", "question", "tolerance"), SAME_SLICE,
                         ids=[f"{s[0]}-{s[3]}" for s in SAME_SLICE])
def test_exports_match_the_golden_questions_on_the_same_slice(exports, expected, export, keys, column, question, tolerance):
    row = _row(exports[export], **keys)
    if expected[question]["expected"] is None:
        assert row[column] is None  # no value stays empty, never 0
    else:
        assert row[column] == pytest.approx(expected[question]["expected"], abs=tolerance)
    assert row["caveats"] == _caveats(expected[question]["expected_caveats"])


def test_monthly_exports_start_at_the_first_full_month_of_pos_data(exports):
    # Before April the ERP has receipts but the tills have no sales: a sell-through
    # of 0 there would mean "no data", and March would be half a month.
    for name in MONTHLY:
        assert sorted({r["month"] for r in exports[name]}) == [date(2026, m, 1) for m in range(4, 10)], name
    assert len(exports["sell_through_by_store_month"]) == 28 * 4 + 30 * 2  # two stores opened in August


def test_a_month_the_data_does_not_fully_cover_is_marked_month_to_date(exports):
    for name in MONTHLY:
        for r in exports[name]:
            end = export.month_end(r["month"])
            assert r["month"] >= POS_FIRST_DAY, (name, r["month"])
            assert r["data_through"] == min(end, POS_LAST_DAY), (name, r["month"])
            assert r["is_month_to_date"] == (end > POS_LAST_DAY), (name, r["month"])
    assert {r["month"] for r in exports["revenue_by_month"] if r["is_month_to_date"]} == {date(2026, 9, 1)}


def test_the_export_refuses_a_month_that_starts_before_the_pos_history():
    raw = [{"metric_time__month": datetime(2026, 3, 1), "net_revenue": 1.0}]
    with pytest.raises(ValueError, match="2026-03 starts before POS data begins on 2026-03-15"):
        export.shape("revenue_by_month", raw, ["net_revenue"], date(2026, 9, 15), [], (POS_FIRST_DAY, POS_LAST_DAY))


def test_no_sell_through_is_negative(exports):
    rates = [r["sell_through_rate"] for r in exports["sell_through_by_store_month"]]
    assert all(r is None or r >= 0 for r in rates)


def test_every_row_says_what_day_it_is_as_of(exports):
    for name, rows in exports.items():
        assert rows and all(r["as_of"] == date(2026, 9, 15) for r in rows), name


def test_metric_versions_match_the_certified_definitions(exports):
    repo = load(with_text_files=False)
    for row in exports["metric_versions"]:
        assert row["status"] == "certified"
        assert row["version"] == int(repo.metrics[row["metric"]].meta["version"])


def test_every_export_has_a_power_bi_table_reading_it(exports):
    tmdl = " ".join(p.read_text(encoding="utf-8") for p in TABLES.glob("*.tmdl"))
    for name in exports:
        assert f'"\\{name}.parquet"' in tmdl, name


def test_the_report_only_asks_for_columns_and_measures_that_exist():
    fields = {}
    for path in TABLES.glob("*.tmdl"):
        t = parse_tmdl_table(path)
        fields[t["name"]] = {("Column", c["name"]) for c in t["columns"]} | {("Measure", m["name"]) for m in t["measures"]}
    visuals = list(PAGES.glob("*/visuals/*/visual.json"))
    assert len(visuals) >= 7
    for path in visuals:
        query = json.loads(path.read_text(encoding="utf-8"))["visual"]["query"]["queryState"]
        for role in query.values():
            for p in role["projections"]:
                (kind, ref), = p["field"].items()
                table, prop = ref["Expression"]["SourceRef"]["Entity"], ref["Property"]
                assert (kind, prop) in fields.get(table, set()), f"{Path(path).parent.name}: {table}.{prop}"
                assert p["queryRef"] == f"{table}.{prop}"


def test_pages_listed_in_order_exist():
    order = json.loads((PAGES / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    assert order == ["revenue", "stock", "sell_through"]
    for name in order:
        assert json.loads((PAGES / name / "page.json").read_text(encoding="utf-8"))["name"] == name
