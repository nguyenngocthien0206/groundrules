"""Golden questions: complete and frozen from an independent reference.

The runner itself (golden/run_golden.py) asks the semantic layer; these tests
check everything around it, without the warehouse where possible. Links
between questions, decision records and metrics are the governance lint's
job (governance/lint.py, tested in tests/test_lint.py).
"""

import re
from datetime import date

import pytest
import yaml

import freeze
from catalog import EXPECTED_DIR, KINDS, QUESTION_FIELDS, ROOT, data_fingerprint, load_expected, load_questions
from reference import DEFAULT_DATA_DIR, Reference
from run_golden import Answer, build_query, caveats, check, lag_caveats, new_store_caveats

QUESTIONS = load_questions()
AS_OF = date(2026, 9, 15)


@pytest.fixture(scope="module")
def ref() -> Reference:
    return Reference()


@pytest.fixture(scope="module")
def fresh() -> dict:
    return freeze.compute()


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


# Expected values


def test_expected_files_mirror_question_files_with_one_answer_per_question():
    assert sorted(p.name for p in EXPECTED_DIR.glob("*.yml")) == sorted({q["file"] for q in QUESTIONS})
    assert set(load_expected()["answers"]) == {q["id"] for q in QUESTIONS}


def test_expected_values_were_frozen_from_the_current_data():
    assert load_expected()["data_fingerprint"] == data_fingerprint(DEFAULT_DATA_DIR)


def test_expected_values_equal_a_fresh_reference_run(fresh):
    """Nobody edits golden/expected/ by hand: it is exactly what the reference says."""
    merged = {qid: answer for frozen in fresh.values() for qid, answer in frozen["answers"].items()}
    assert merged == load_expected()["answers"]


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
        ("sell_through_rate", {"store": "NW014", "month": "2026-08"}, 1.117, 0.0005),    # DR-011
        ("sell_through_rate", {"store": "NW029", "month": "2026-08"}, 0.340, 0.0005),    # DR-011
        ("days_of_cover", {"store": "NW001"}, 26.32, 0.005),                             # DR-010
    ],
)
def test_reference_reproduces_the_worked_examples(ref, metric, filters, expected, tolerance):
    assert ref.value(metric, filters, AS_OF) == pytest.approx(expected, abs=tolerance)


def test_reference_names_lagging_stores_only_when_they_matter(ref):
    assert ref.caveats("net_revenue", {"day": "2026-09-14"}, AS_OF) == ["pos_sync_lag:NW029", "pos_sync_lag:NW030"]
    assert ref.caveats("net_revenue", {"month": "2026-08", "district": "D02"}, AS_OF) == []
    assert ref.caveats("available_stock", {"district": "D02"}, AS_OF) == ["pos_sync_lag:NW029"]


def test_reference_sell_through_has_no_value_when_net_received_is_not_positive(ref):
    # DR-011: NW030 received 590 and sent away 1,012 in September.
    assert ref.value("sell_through_rate", {"store": "NW030", "month": "2026-09"}, AS_OF) is None
    assert ref.value("sell_through_rate", {"store": "NW030", "month": "2026-08"}, AS_OF) == 0.0


def test_reference_names_new_stores_for_sell_through_only(ref):
    assert ref.caveats("sell_through_rate", {"store": "NW030", "month": "2026-08"}, AS_OF) == ["new_store:NW030"]
    assert ref.caveats("sell_through_rate", {"month": "2026-08", "district": "D02"}, AS_OF) == ["new_store:NW029"]
    assert ref.caveats("sell_through_rate", {"store": "NW029", "month": "2026-09"}, AS_OF) == ["pos_sync_lag:NW029"]
    assert ref.caveats("net_revenue", {"store": "NW030", "month": "2026-08"}, AS_OF) == []


# Runner logic, without the warehouse

STORES = [
    {"store": "NW001", "district": "D02", "opened_on": date(2019, 3, 4), "data_through": date(2026, 9, 14)},
    {"store": "NW029", "district": "D02", "opened_on": date(2026, 8, 18), "data_through": date(2026, 9, 11)},
    {"store": "NW030", "district": "D05", "opened_on": date(2026, 9, 1), "data_through": date(2026, 9, 11)},
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


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"month": "2026-08", "store": "NW030"}, ["new_store:NW030"]),     # opened the day after
        ({"month": "2026-09", "store": "NW030"}, []),                      # opened on the first day
        ({"month": "2026-08", "store": "NW029"}, ["new_store:NW029"]),     # opened mid-month
        ({"month": "2026-07"}, []),                                        # both opened over 7 days later
        ({"month": "2026-08", "district": "D05"}, ["new_store:NW030"]),
        ({"start": "2026-07-01", "end": "2026-08-31"}, ["new_store:NW029", "new_store:NW030"]),
    ],
)
def test_runner_flags_new_stores_by_opening_day(filters, expected):
    assert new_store_caveats("sell_through_rate", filters, AS_OF, STORES) == expected


def test_new_store_caveats_are_for_sell_through_only_and_merge_with_lag():
    assert new_store_caveats("net_revenue", {"month": "2026-08"}, AS_OF, STORES) == []
    assert caveats("sell_through_rate", {"month": "2026-09"}, AS_OF, STORES) == ["pos_sync_lag:NW029", "pos_sync_lag:NW030"]
    assert caveats("sell_through_rate", {"month": "2026-08"}, AS_OF, STORES) == ["new_store:NW029", "new_store:NW030"]


def test_no_value_is_frozen_as_null_and_read_back_as_none():
    rendered = freeze.render({"data_fingerprint": "x", "answers": {"GQ-X-01": {"expected": None, "expected_caveats": []}}})
    assert "expected: null" in rendered
    assert yaml.safe_load(rendered)["answers"]["GQ-X-01"]["expected"] is None


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


def test_expected_files_are_plain_yaml_written_by_freeze(fresh):
    for name, frozen in fresh.items():
        rendered = freeze.render(frozen)
        assert yaml.safe_load(rendered)["answers"] == frozen["answers"]
        assert (EXPECTED_DIR / name).read_text(encoding="utf-8") == rendered
