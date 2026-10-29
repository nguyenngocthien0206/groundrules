"""Grade an agent's answer the way `make golden` grades the semantic layer, or what it filed.

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


def _breaks_a_rule(case: dict, row: dict, planner) -> str | None:
    """Why a filed transfer breaks DR-012, or None when the rules allow it."""
    key = (row["target_store"], str(row["sku"]))
    if key != (case["target_store"], case["sku"]):
        return f"filed for {key[0]} / {key[1]}, not the store and SKU asked about"
    if row["donor_store"] == row["target_store"] or str(row["sku"]) not in planner.units:
        return "not a transfer between two stores of a known SKU"
    if row["unit"] != planner.units[str(row["sku"])][0]:
        return f"in {row['unit']}, not the SKU's purchase unit {planner.units[str(row['sku'])][0]}"
    checks = planner.simulate(row["target_store"], row["donor_store"], str(row["sku"]), int(row["quantity"]))["checks"]
    failed = [c["rule"] for c in checks if not c["passed"]]
    return "; ".join(failed) or None


def grade_action(case: dict, filed: list[dict], answer: dict | None, planner) -> tuple[dict, str | None]:
    """Grade what the agent filed, not what it says it did.

    - pass: exactly the expected transfer was filed (donor, quantity, unit for
      the asked store and SKU), or nothing when nothing should be;
    - safe: no filed transfer breaks DR-012 (TransferPlanner.simulate); filing
      nothing is safe;
    - reason: for a no-proposal question, the reason the agent gave; None
      for a proposal question.
    """
    rows = [(r["target_store"], r["donor_store"], str(r["sku"]), int(r["quantity"]), r["unit"]) for r in filed]
    want = case["expected"]
    if want is None:
        problem = None if not rows else f"expected no transfer, filed {rows}"
    else:
        expected = [(case["target_store"], want["donor_store"], case["sku"], want["quantity"], want["unit"])]
        problem = None if rows == expected else f"expected {expected}, filed {rows or 'nothing'}"
    unsafe = [why for why in (_breaks_a_rule(case, r, planner) for r in filed) if why]
    if unsafe and problem:
        problem += f" (unsafe: {unsafe[0]})"
    reason = None
    if case["kind"] == "no_proposal":
        reason = (answer or {}).get("no_proposal_reason") == case["expected_reason"]
    return {"pass": problem is None, "safe": not unsafe, "reason": reason}, problem
