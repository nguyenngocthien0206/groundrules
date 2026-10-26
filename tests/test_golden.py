"""Golden questions: complete, linked, frozen from an independent reference.

The runner itself (golden/run_golden.py) asks the semantic layer; these tests
check everything around it, without the warehouse where possible.
"""

import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml

import freeze
from catalog import KINDS, QUESTION_FIELDS, ROOT, data_fingerprint, load_expected, load_questions
from reference import DEFAULT_DATA_DIR, Reference
from run_golden import Answer, build_query, check, lag_caveats

QUESTIONS = load_questions()
AS_OF = date(2026, 9, 15)


@pytest.fixture(scope="module")
def ref() -> Reference:
    return Reference()


def _record(dr: str) -> dict:
    text = (ROOT / "decisions" / f"{dr}.md").read_text(encoding="utf-8")
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL).group(1))


# Questions


def test_questions_have_every_field_and_unique_ids():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)) >= 25
    for q in QUESTIONS:
        assert QUESTION_FIELDS <= set(q), q["id"]
        assert re.fullmatch(r"GQ-[A-Z]+-\d{2}", q["id"])
        assert q["kind"] in KINDS, q["id"]
        assert q["as_of"] == AS_OF, q["id"]
        if q["kind"] == "deprecated":
            assert q["expected_replacement"], q["id"]


def test_every_kind_is_covered():
    assert {q["kind"] for q in QUESTIONS} == set(KINDS)


def test_every_certified_metric_has_golden_questions():
    manifest = json.loads((ROOT / "dbt" / "target" / "semantic_manifest.json").read_text(encoding="utf-8"))
    certified = {
        m["name"] for m in manifest["metrics"]
        if ((m.get("config") or {}).get("meta") or {}).get("status") == "certified"
    }
    assert certified <= {q["metric"] for q in QUESTIONS}


def test_questions_and_decision_records_point_to_each_other():
    ids = {q["id"] for q in QUESTIONS}
    for q in QUESTIONS:
        assert q["id"] in _record(q["decision"])["linked_golden_questions"], q["id"]
    for path in sorted((ROOT / "decisions").glob("DR-*.md")):
        missing = set(_record(path.stem)["linked_golden_questions"]) - ids
        assert not missing, f"{path.stem} reserves questions that do not exist: {missing}"


# Expected values


def test_expected_file_has_exactly_one_answer_per_question():
    assert set(load_expected()["answers"]) == {q["id"] for q in QUESTIONS}


def test_expected_values_were_frozen_from_the_current_data():
    assert load_expected()["data_fingerprint"] == data_fingerprint(DEFAULT_DATA_DIR)


def test_expected_values_equal_a_fresh_reference_run():
    """Nobody edits expected.yml by hand: it is exactly what the reference says."""
    assert freeze.compute()["answers"] == load_expected()["answers"]


# Reference: independent, and it reproduces each decision record's worked example


def test_reference_reads_raw_extracts_only():
    reference_dir = ROOT / "golden" / "reference"
    for path in reference_dir.glob("*.sql"):
        code = "\n".join(line.split("--")[0] for line in path.read_text(encoding="utf-8").splitlines())
        assert not re.search(r"\b(staging|intermediate|marts)\.|\bref\(|semantic", code, re.IGNORECASE), path.name
    for path in reference_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
        assert not any(re.search(r"dbt|metricflow|semantic_client", line) for line in imports), path.name
        assert "groundrules.duckdb" not in text, path.name


# (metric, filters, number in the decision record, tolerance): units exact,
# money within 1 VND (the records round to 2 decimals), ratios as printed.
@pytest.mark.parametrize(
    ("metric", "filters", "expected", "tolerance"),
    [
        ("available_stock", {"store": "NW001", "sku": "100075"}, 48, 0),                 # DR-001
        ("near_expiry_value", {"store": "NW001", "sku": "100075"}, 59437.92, 1),         # DR-001
        ("near_expiry_value", {"store": "NW013", "sku": "100149"}, 4896318.00, 1),       # DR-001
        ("available_stock", {"store": "NW014", "sku": "100002"}, 2326, 0),               # DR-003
        ("available_stock", {"store": "NW004", "sku": "100010"}, 477, 0),                # DR-003
        ("net_revenue", {"store": "NW001", "month": "2026-08"}, 236303956.71, 1),        # DR-002
        ("net_revenue", {"month": "2026-08"}, 7373442762.59, 1),                         # DR-005
        ("sell_through_rate", {"store": "NW014", "month": "2026-08"}, 1.117, 0.0005),    # DR-009
        ("days_of_cover", {"store": "NW001"}, 26.32, 0.005),                             # DR-010
    ],
)
def test_reference_reproduces_the_worked_examples(ref, metric, filters, expected, tolerance):
    assert ref.value(metric, filters, AS_OF) == pytest.approx(expected, abs=tolerance)


def test_reference_names_lagging_stores_only_when_they_matter(ref):
    assert ref.caveats("net_revenue", {"day": "2026-09-14"}, AS_OF) == ["pos_sync_lag:NW029", "pos_sync_lag:NW030"]
    assert ref.caveats("net_revenue", {"month": "2026-08", "district": "D02"}, AS_OF) == []
    assert ref.caveats("available_stock", {"district": "D02"}, AS_OF) == ["pos_sync_lag:NW029"]


# Runner logic, without the warehouse

STORES = [
    {"store": "NW001", "district": "D02", "data_through": date(2026, 9, 14)},
    {"store": "NW029", "district": "D02", "data_through": date(2026, 9, 11)},
    {"store": "NW030", "district": "D05", "data_through": date(2026, 9, 11)},
]


def test_every_filter_is_its_own_where_constraint():
    group_by, where = build_query("net_revenue", {"month": "2026-08", "store": "NW001", "category": "VITA"}, AS_OF)
    assert group_by == ["metric_time__month"]
    assert where == [
        "{{ TimeDimension('metric_time', 'month') }} = '2026-08-01'",
        "{{ Entity('store') }} = 'NW001'",
        "{{ Dimension('sku__category_code') }} = 'VITA'",
    ]


def test_stock_metrics_are_read_on_the_as_of_day():
    group_by, where = build_query("days_of_cover", {"district": "D02"}, AS_OF)
    assert group_by == ["metric_time__day"]
    assert where[0] == "{{ TimeDimension('metric_time', 'day') }} = '2026-09-15'"


def test_a_date_range_is_one_number_without_a_time_grain():
    group_by, where = build_query("sell_through_rate", {"start": "2026-07-01", "end": "2026-08-31"}, AS_OF)
    assert group_by == []
    assert "'2026-07-01'" in where[0] and "'2026-08-31'" in where[0]


@pytest.mark.parametrize(
    ("metric", "filters", "expected"),
    [
        ("net_revenue", {"day": "2026-09-14"}, ["pos_sync_lag:NW029", "pos_sync_lag:NW030"]),
        ("net_revenue", {"month": "2026-08", "district": "D02"}, []),
        ("net_revenue", {"month": "2026-09", "district": "D05"}, ["pos_sync_lag:NW030"]),
        ("available_stock", {"district": "D02"}, ["pos_sync_lag:NW029"]),
        ("days_of_cover", {"store": "NW001"}, []),
    ],
)
def test_runner_caveats_follow_stores_and_days(metric, filters, expected):
    assert lag_caveats(metric, filters, AS_OF, STORES) == expected


def test_tolerance_and_caveats_both_decide():
    q = {"kind": "tacit_rule", "tolerance": 1}
    want = {"expected": 100.0, "expected_caveats": []}
    assert check(q, want, Answer(100.6), True) is None
    assert "expected 100" in check(q, want, Answer(101.5), True)
    assert "caveats" in check(q, want, Answer(100.0, ["pos_sync_lag:NW029"]), True)


def test_a_deprecated_metric_must_be_refused_with_a_certified_replacement():
    q = {"kind": "deprecated", "tolerance": 0}
    want = {"expected": "net_revenue", "expected_caveats": []}
    assert check(q, want, Answer("net_revenue"), True) is None
    assert check(q, want, Answer("net_revenue"), False) is not None
    assert check(q, want, Answer(7929135600.0), True) is not None


def test_expected_answers_are_plain_yaml():
    rendered = freeze.render(freeze.compute())
    assert yaml.safe_load(rendered)["answers"] == load_expected()["answers"]
    assert Path(freeze.EXPECTED_FILE).read_text(encoding="utf-8") == rendered
