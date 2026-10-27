"""Grade an agent's answer the way `make golden` grades the semantic layer.

`run_golden.check()` decides what "correct" means, so the agent eval and the
golden runner can never disagree. Three scores per answer:
- pass: the number and the caveats are right (for a deprecated metric: it
  named the replacement instead of answering);
- value: the number alone, whatever the caveats;
- caveats: the exact set of caveats, in any order.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden")]

from run_golden import Answer, check  # noqa: E402


def as_answer(case: dict, answer: dict) -> Answer:
    """The agent's structured answer in the runner's terms."""
    caveats = sorted({str(c).strip() for c in answer.get("caveats") or []})
    value = answer.get("replacement_metric") if case["kind"] == "deprecated" else answer.get("value")
    return Answer(value, caveats)


def grade(case: dict, answer: dict, replacement_certified: bool = True) -> tuple[dict, str | None]:
    """Scores and, when it failed, the reason in the golden runner's words."""
    got = as_answer(case, answer)
    question = {"kind": case["kind"], "tolerance": case["tolerance"]}
    want = {"expected": case["expected"], "expected_caveats": sorted(case["expected_caveats"])}
    problem = check(question, want, got, replacement_certified)
    value_problem = check(question, {**want, "expected_caveats": got.caveats}, got, replacement_certified)
    scores = {
        "pass": problem is None,
        "value": value_problem is None,
        "caveats": got.caveats == want["expected_caveats"],
    }
    return scores, problem
