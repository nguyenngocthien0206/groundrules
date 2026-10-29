"""Check the action golden questions against the transfer engine.

Usage: python golden/run_actions.py   (`make golden` runs it after the metric questions)

For each question in golden/actions/questions/, the engine that serves agents
(mcp_server/transfers.py, on the certified metrics) must make the proposal
the independent reference froze into golden/actions/expected/, or make none,
and then for the reason the owner wrote down. Exits 1 on any failure.
"""

import sys
import time
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent
sys.path[:0] = [str(GOLDEN), str(GOLDEN.parent / "mcp_server")]

from catalog import load_action_expected, load_action_questions  # noqa: E402


def reason_category(engine_reason: str) -> str:
    """The engine's reason in the questions' terms: every exclusion is one category."""
    return "excluded_store" if engine_reason.startswith("excluded:") or engine_reason == "no_route" else engine_reason


def check(question: dict, expected: dict | None, found: dict) -> str | None:
    """None when the engine's answer matches, otherwise what went wrong."""
    proposal = found.get("proposal")
    if expected is None:
        if proposal is not None:
            return f"expected no proposal, got {proposal['quantity']} {proposal['unit']} from {proposal['donor_store']}"
        got = reason_category(found["reason"])
        return None if got == question["expected_reason"] else f"expected reason {question['expected_reason']}, got {got}"
    if proposal is None:
        return f"expected {expected['quantity']} {expected['unit']} from {expected['donor_store']}, got none ({found['reason']})"
    got = {k: proposal[k] for k in expected}
    return None if got == expected else f"expected {expected}, got {got}"


def main() -> int:
    import transfers
    from semantic_client import SemanticLayer

    started = time.perf_counter()
    planner = transfers.TransferPlanner(SemanticLayer())
    expected = load_action_expected()["answers"]
    failed = 0
    print(f"{'id':<16}{'kind':<13}{'target':<8}{'sku':<8}{'expected':<26}result")
    for q in load_action_questions():
        want = expected[q["id"]]["expected"]
        problem = check(q, want, planner.explain(q["target_store"], str(q["sku"])))
        shown = q["expected_reason"] if want is None else f"{want['quantity']} {want['unit']} from {want['donor_store']}"
        print(f"{q['id']:<16}{q['kind']:<13}{q['target_store']:<8}{q['sku']:<8}{shown:<26}{'FAIL: ' + problem if problem else 'PASS'}")
        failed += problem is not None
    total = len(expected)
    print(f"\n{total - failed} passed, {failed} failed in {time.perf_counter() - started:.1f}s (action questions).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
