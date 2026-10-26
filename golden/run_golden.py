"""Ask the semantic layer every golden question and check the answers.

Usage: python golden/run_golden.py   (or `make golden`)

For each question the runner plays the part an agent will play later: it
refuses deprecated metrics with a pointer to the replacement, asks MetricFlow
for the number, and names any store whose missing POS data affects the
answer (DR-004). It compares value and caveats with golden/expected.yml,
prints a table, explains each failure with its `why` and decision record,
writes a JUnit report for CI and exits 1 on any failure.
"""

import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog import GOLDEN, load_expected, load_questions  # noqa: E402

REPORT = GOLDEN / "report" / "junit.xml"
STOCK_METRICS = frozenset({"available_stock", "near_expiry_value", "days_of_cover"})
# Sums over nothing are zero; a ratio over nothing has no value.
ADDITIVE_METRICS = frozenset({"available_stock", "near_expiry_value", "net_revenue", "gross_margin"})
CAVEAT_POS_SYNC_LAG = "pos_sync_lag"

SCOPE_FILTERS = {
    "store": "{{ Entity('store') }} = '%s'",
    "sku": "{{ Entity('sku') }} = '%s'",
    "district": "{{ Dimension('store__district_code') }} = '%s'",
    "category": "{{ Dimension('sku__category_code') }} = '%s'",
}


@dataclass
class Answer:
    value: float | str | None
    caveats: list[str] = field(default_factory=list)
    note: str = ""


def period(filters: dict, as_of: date) -> tuple[date, date]:
    if "day" in filters:
        day = date.fromisoformat(str(filters["day"]))
        return day, day
    if "month" in filters:
        start = date.fromisoformat(f"{filters['month']}-01")
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return start, end
    if "start" in filters:
        return date.fromisoformat(str(filters["start"])), date.fromisoformat(str(filters["end"]))
    return as_of, as_of


def build_query(metric: str, filters: dict, as_of: date) -> tuple[list[str], list[str]]:
    """Group-by items and where constraints for one question. One row comes back."""
    where = [SCOPE_FILTERS[key] % filters[key] for key in SCOPE_FILTERS if key in filters]
    if metric in STOCK_METRICS or not ({"day", "month", "start"} & set(filters)):
        day = filters.get("day", as_of)
        return ["metric_time__day"], ["{{ TimeDimension('metric_time', 'day') }} = '%s'" % day] + where
    if "day" in filters:
        return ["metric_time__day"], ["{{ TimeDimension('metric_time', 'day') }} = '%s'" % filters["day"]] + where
    if "month" in filters:
        return ["metric_time__month"], ["{{ TimeDimension('metric_time', 'month') }} = '%s-01'" % filters["month"]] + where
    span = "{{ TimeDimension('metric_time', 'day') }} >= '%s' and {{ TimeDimension('metric_time', 'day') }} <= '%s'"
    return [], [span % (filters["start"], filters["end"])] + where


def lag_caveats(metric: str, filters: dict, as_of: date, stores: list[dict]) -> list[str]:
    """DR-004: name each lagging store the answer depends on (stores and days)."""
    start, end = period(filters, as_of)
    yesterday = as_of - timedelta(days=1)
    caveats = []
    for s in stores:
        if "store" in filters and s["store"] != filters["store"]:
            continue
        if "district" in filters and s["district"] != filters["district"]:
            continue
        if s["data_through"] >= yesterday:
            continue
        if metric in STOCK_METRICS or (s["data_through"] < end and start <= yesterday):
            caveats.append(f"{CAVEAT_POS_SYNC_LAG}:{s['store']}")
    return sorted(caveats)


def answer(sl, question: dict, stores: list[dict]) -> Answer:
    metric, filters, as_of = question["metric"], question["filters"], question["as_of"]
    meta = sl.governance(metric)
    if meta.get("status") == "deprecated":
        return Answer(meta.get("replaced_by"), note=f"{metric} is deprecated; use {meta.get('replaced_by')}")
    if meta.get("status") != "certified":
        return Answer(None, note=f"{metric} is not a certified metric")
    group_by, where = build_query(metric, filters, as_of)
    rows = sl.query([metric], group_by, where)
    value = rows[0][metric] if rows else None
    if value is None and metric in ADDITIVE_METRICS:
        value = 0.0
    return Answer(value, lag_caveats(metric, filters, as_of, stores))


def check(question: dict, expected: dict, got: Answer, replacement_certified: bool) -> str | None:
    """None when the answer is right, else what is wrong."""
    want = expected["expected"]
    if question["kind"] == "deprecated":
        if got.value != want:
            return f"expected a pointer to {want}, got {got.value!r}"
        if not replacement_certified:
            return f"replacement {want} is not certified"
        return None
    if got.value is None or want is None:
        if got.value != want:
            return f"expected {want}, got {got.value}"
    elif abs(float(got.value) - float(want)) > question["tolerance"] + 1e-9:
        return f"expected {want:,.4f}, got {float(got.value):,.4f} (tolerance {question['tolerance']})"
    if got.caveats != list(expected["expected_caveats"]):
        return f"expected caveats {expected['expected_caveats']}, got {got.caveats}"
    return None


def fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.4f}" if abs(value) < 1000 else f"{value:,.2f}"
    return str(value)


def write_junit(results: list[tuple[dict, Answer, str | None]], seconds: float) -> None:
    failures = sum(1 for _, _, problem in results if problem)
    suite = ET.Element("testsuite", name="golden", tests=str(len(results)), failures=str(failures), time=f"{seconds:.1f}")
    for q, got, problem in results:
        case = ET.SubElement(suite, "testcase", classname=f"golden.{Path(q['file']).stem}", name=q["id"])
        if problem:
            failure = ET.SubElement(case, "failure", message=problem)
            failure.text = f"{q['question']}\nWhy: {q['why'].strip()}\nDecision: decisions/{q['decision']}.md"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(REPORT, encoding="utf-8", xml_declaration=True)


def main() -> int:
    from semantic_client import SemanticLayer

    started = time.perf_counter()
    questions, expected = load_questions(), load_expected()["answers"]
    sl = SemanticLayer()
    stores = [
        {"store": r["store"], "district": r["store__district_code"], "data_through": r["store__pos_data_through__day"].date()}
        for r in sl.query([], ["store", "store__district_code", "store__pos_data_through__day"])
    ]

    results = []
    for q in questions:
        got = answer(sl, q, stores)
        replacement = sl.governance(str(got.value)).get("status") == "certified"
        results.append((q, got, check(q, expected[q["id"]], got, replacement)))
    seconds = time.perf_counter() - started

    print(f"{'id':<14}{'kind':<17}{'metric':<19}{'expected':>22}{'actual':>22}  caveats  result")
    for q, got, problem in results:
        want = expected[q["id"]]["expected"]
        caveats = ",".join(c.split(":")[1] for c in got.caveats) or "-"
        print(f"{q['id']:<14}{q['kind']:<17}{q['metric']:<19}{fmt(want):>22}{fmt(got.value):>22}  "
              f"{caveats:<7}  {'FAIL' if problem else 'PASS'}")
    failed = [(q, problem) for q, _, problem in results if problem]
    for q, problem in failed:
        print(f"\nFAIL {q['id']}: {q['question']}\n  {problem}\n  Why: {' '.join(q['why'].split())}\n"
              f"  Decision: decisions/{q['decision']}.md")
    write_junit(results, seconds)
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed in {seconds:.1f}s. Report: {REPORT.relative_to(GOLDEN.parent)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
