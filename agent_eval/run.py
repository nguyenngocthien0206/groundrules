"""Run the golden questions through an agent and grade every answer.

Usage:
  python agent_eval/run.py --arm semantic [--provider claude-code] [--model sonnet] [--reps 3]
                           [--cases GQ-SELL-01,GQ-REV-01] [--run-id NAME] [--concurrency 2]
  python agent_eval/run.py --arm actions        # the action questions (or --arm raw_actions)
  python agent_eval/run.py --probe [--arm ARM]  # check the agent's context is clean before a scored run

Metric arms (semantic, raw_sql) answer the metric golden questions and are
graded on the answer. Action arms (actions, raw_actions) get the action
golden questions; each run files into its own database, and what it filed
is graded, not what it says.

Each (question, rep) lands in agent_eval/runs/<run-id>/<arm>/: one graded
row in results.jsonl, its transcript in traces/, or a failure in errors.jsonl
(timeouts, harness errors, refusals, a wrong served model). Failures are
never scored as wrong answers, and a rerun with the same run id resumes:
finished (question, rep) pairs are skipped, failed ones are tried again.
"""

import argparse
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "governance"), str(HERE.parent / "mcp_server")]

import duckdb  # noqa: E402

from cases import load_action_cases, load_cases  # noqa: E402
from grading import grade, grade_action  # noqa: E402
from prompt import PROBE_PROMPT, PROBE_SCHEMA  # noqa: E402
from providers import ARMS, PROVIDERS, STRUCTURED_TOOL, EvalError, RunResult  # noqa: E402

RUNS = HERE / "runs"


def done_keys(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    return {(r["prompt_id"], r["rep"]) for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r}


def certified_metrics() -> set[str]:
    from repo import load

    return {n for n, m in load(with_text_files=False).metrics.items() if not m.hidden and m.meta.get("status") == "certified"}


def run_arm(provider, arm: str, cases: list[dict], reps: int, out: Path, timeout_s: float, concurrency: int) -> dict:
    """Run every pending (case, rep); return counts of what happened."""
    (out / "traces").mkdir(parents=True, exist_ok=True)
    results, errors = out / "results.jsonl", out / "errors.jsonl"
    finished = done_keys(results)
    action = ARMS[arm]["task"] == "action"
    certified = set() if action else certified_metrics()
    planner = action_planner() if action else None
    todo = [(c, rep) for c in cases for rep in range(reps) if (c["id"], rep) not in finished]
    lock = threading.Lock()
    counts = {"skipped": len(cases) * reps - len(todo), "graded": 0, "errors": 0}

    def one(case: dict, rep: int) -> None:
        if action:
            # Each run files into its own empty database, so what it filed can be read back and graded.
            filed_db = out / "filed" / f"{case['id']}_rep{rep}.duckdb"
            filed_db.parent.mkdir(exist_ok=True)
            filed_db.unlink(missing_ok=True)  # left by an attempt that ended in an error
            got: RunResult = provider.run(case["question"], arm, timeout_s, env={"GROUNDRULES_ACTIONS_DB": str(filed_db)})
        else:
            got = provider.run(case["question"], arm, timeout_s)
        trace_file = out / "traces" / f"{case['id']}_rep{rep}.json"
        # Agent text is recorded verbatim; non-ASCII stays as JSON escapes (same content once parsed).
        trace_file.write_text(json.dumps(got.trace, indent=2), encoding="utf-8")
        base = {"prompt_id": case["id"], "rep": rep, "arm": arm, "model": got.model, "usage": got.usage,
                "latency_s": got.latency_s, "tool_calls": got.tool_calls, "turns": got.turns,
                "cost_usd": got.cost_usd, "stop_reason": got.stop_reason}
        with lock:
            if got.error:
                row = {**base, "error": got.error, "detail": got.detail, "at": now()}
                append(errors, row)
                counts["errors"] += 1
                print(f"  {case['id']} rep{rep}: {got.error} {got.detail[:120]}", flush=True)
                return
            if action:
                filed = read_filed(filed_db)
                scores, problem = grade_action(case, filed, got.answer, planner)
                expected = {"transfer": case["expected"], "reason": case["expected_reason"]}
                meta = {"decision": case["decision"], "action": case["action"]}
            else:
                filed = None
                replacement = got.answer.get("replacement_metric") in certified
                scores, problem = grade(case, got.answer, replacement_certified=replacement)
                expected = {"value": case["expected"], "caveats": case["expected_caveats"]}
                meta = {"decision": case["decision"], "metric": case["metric"]}
            row = {**base, "prompt": case["question"], "tags": [case["kind"], arm], "status": "ok",
                   "grade": {k: None if v is None else float(v) for k, v in scores.items()}, "answer": got.answer,
                   "expected": expected, "problem": problem, "meta": meta}
            if action:
                row["filed"] = filed
            append(results, row)
            counts["graded"] += 1
            mark = "pass" if scores["pass"] else f"FAIL ({problem})"
            print(f"  {case['id']} rep{rep}: {mark} [{got.tool_calls} tool calls, {got.latency_s}s]", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for future in [pool.submit(one, c, rep) for c, rep in todo]:
            future.result()
    return counts


def action_planner():
    """The transfer engine, to check every filed transfer against DR-012."""
    from semantic_client import SemanticLayer
    from transfers import TransferPlanner

    return TransferPlanner(SemanticLayer())


def read_filed(path: Path) -> list[dict]:
    """The transfers one run filed: proposals on the actions server, rows on the control arm."""
    if not path.exists():
        return []
    columns = "target_store, donor_store, sku, quantity, unit"
    with duckdb.connect(str(path), read_only=True) as con:
        tables = {t for (t,) in con.execute("select table_name from information_schema.tables").fetchall()}
        rows = []
        for table in ("transfer_proposals", "unguarded_transfers"):
            if table in tables:
                rows += con.execute(f"select {columns} from {table}").fetchall()
    return [dict(zip(("target_store", "donor_store", "sku", "quantity", "unit"), r)) for r in rows]


def append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE.parent,
                          capture_output=True, text=True).stdout.strip()


def probe(provider, timeout_s: float, arm: str = "semantic") -> int:
    """Ask the agent what it can see. Pass only if its tools are exactly the arm's tools."""
    got = provider.run(PROBE_PROMPT, arm, timeout_s, schema=PROBE_SCHEMA, raw=True)
    if got.error and got.error != "no_answer":
        print(f"Probe failed: {got.error} {got.detail}")
        return 1
    answer = got.answer or {}
    tools = sorted(set(got.tools) - {STRUCTURED_TOOL, "submit_answer"})
    expected = sorted(f"mcp__{ARMS[arm]['server']}__{t}" for t in ARMS[arm]["tools"])
    print(f"Model: {got.model}")
    print(f"Tools available to the agent: {tools}")
    print(f"Tools the agent says it has: {answer.get('tools')}")
    print(f"Other context it reports:\n  {answer.get('other_context', '(no answer)')}")
    if tools != expected:
        print(f"Probe failed: expected exactly {expected}.")
        return 1
    print("Probe passed: only the arm's tools. Read the other context above before a scored run.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="claude-code")
    parser.add_argument("--arm", choices=sorted(ARMS), default="semantic")
    parser.add_argument("--model", default=None, help="default: sonnet (claude-code) or claude-sonnet-5-5 (anthropic-api)")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--cases", default="", help="comma-separated golden question ids (default: all)")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M"))
    parser.add_argument("--timeout-s", type=float, default=300)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--probe", action="store_true", help="check the agent's context instead of running questions")
    args = parser.parse_args(argv)

    try:
        provider = PROVIDERS[args.provider](args.model)
    except EvalError as e:
        print(e)
        return 1
    if args.probe:
        return probe(provider, args.timeout_s, args.arm)

    ids = [c for c in args.cases.split(",") if c] or None
    cases = load_action_cases(ids) if ARMS[args.arm]["task"] == "action" else load_cases(ids)
    out = RUNS / args.run_id / args.arm
    out.mkdir(parents=True, exist_ok=True)
    meta = out / "meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({**provider.describe(), "arm": args.arm, "reps": args.reps,
                                    "cases": [c["id"] for c in cases], "git": git_commit(), "started": now()},
                                   indent=2), encoding="utf-8")
    print(f"{args.arm}: {len(cases)} questions x {args.reps} reps on {args.provider} ({provider.model}) -> {out.relative_to(HERE.parent)}")
    counts = run_arm(provider, args.arm, cases, args.reps, out, args.timeout_s, args.concurrency)
    print(f"Done: {counts['graded']} graded, {counts['errors']} errors, {counts['skipped']} already done. "
          f"Summary: python agent_eval/summary.py {args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
