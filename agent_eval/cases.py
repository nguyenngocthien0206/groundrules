"""The eval's cases: the golden questions, as their owners wrote and signed them.

The agent sees only the question text. Filters, expected values, decision
records and the `why` stay here, for grading.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden")]

from catalog import load_expected, load_questions  # noqa: E402


def load_cases(ids: list[str] | None = None) -> list[dict]:
    expected = load_expected()["answers"]
    cases = []
    for q in load_questions():
        if ids and q["id"] not in ids:
            continue
        want = expected[q["id"]]
        cases.append({
            "id": q["id"],
            "question": q["question"],
            "kind": q["kind"],
            "metric": q["metric"],
            "tolerance": q["tolerance"],
            "decision": q["decision"],
            "expected": want["expected"],
            "expected_caveats": list(want["expected_caveats"]),
        })
    unknown = set(ids or []) - {c["id"] for c in cases}
    if unknown:
        raise ValueError(f"unknown golden question ids: {', '.join(sorted(unknown))}")
    return cases
