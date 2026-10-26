"""Decision records are complete and tied to the metrics they explain.

The front matter is for machines, the body for people. Golden question links
are checked in step 5, once the questions exist; the governance lint (step 6)
takes these checks over.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "decisions"
SEMANTIC_MANIFEST = ROOT / "dbt" / "target" / "semantic_manifest.json"

FRONT_MATTER_KEYS = {
    "id", "title", "status", "date", "decided_by", "consulted",
    "linked_metrics", "linked_golden_questions", "supersedes", "superseded_by",
}
STATUSES = {"proposed", "accepted", "superseded"}
HEADINGS = ["Context", "Decision", "Options considered", "Consequences", "Worked example"]


def parse(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, f"{path.name}: no YAML front matter"
    return yaml.safe_load(match.group(1)), match.group(2)


def sections(body: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


RECORDS = sorted(DECISIONS.glob("DR-*.md"))


@pytest.fixture(scope="module")
def metrics() -> dict[str, dict]:
    if not SEMANTIC_MANIFEST.exists():
        pytest.fail("No semantic manifest: run `make build` first.")
    manifest = json.loads(SEMANTIC_MANIFEST.read_text(encoding="utf-8"))
    return {m["name"]: m for m in manifest["metrics"]}


def test_there_are_decision_records():
    assert len(RECORDS) >= 10


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_front_matter_is_complete(path):
    meta, _ = parse(path)
    assert set(meta) == FRONT_MATTER_KEYS
    assert meta["id"] == path.stem
    assert meta["status"] in STATUSES
    assert meta["decided_by"] and meta["linked_metrics"] and meta["linked_golden_questions"]
    assert all(re.fullmatch(r"GQ-[A-Z]+-\d{2}", q) for q in meta["linked_golden_questions"])


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_body_has_every_section_and_a_worked_example(path):
    _, body = parse(path)
    found = sections(body)
    assert list(found) == HEADINGS
    assert all(found[h] for h in HEADINGS)
    # A worked example shows numbers, not prose only.
    assert re.search(r"\d", found["Worked example"])


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_linked_metrics_exist(path, metrics):
    meta, _ = parse(path)
    assert set(meta["linked_metrics"]) <= set(metrics)


def test_every_governed_metric_points_to_a_record_that_lists_it(metrics):
    for name, metric in metrics.items():
        decision = metric["config"]["meta"].get("decision")
        if decision is None:
            continue
        path = ROOT / decision
        assert path.exists(), f"{name}: {decision} does not exist"
        meta, _ = parse(path)
        assert name in meta["linked_metrics"], f"{name} is not listed in {decision}"


def test_index_lists_every_record():
    index = (DECISIONS / "README.md").read_text(encoding="utf-8")
    for path in RECORDS:
        assert f"[{path.stem}]({path.name})" in index
