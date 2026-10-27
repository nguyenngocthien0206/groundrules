"""Run the golden questions through an agent and grade every answer.

Usage:
  python agent_eval/run.py --arm semantic [--provider claude-code] [--model sonnet] [--reps 3]
                           [--cases GQ-SELL-01,GQ-REV-01] [--run-id NAME] [--concurrency 2]
  python agent_eval/run.py --probe     # check the agent's context is clean before a scored run

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
sys.path[:0] = [str(HERE), str(HERE.parent / "governance")]

from cases import load_cases  # noqa: E402
from grading import grade  # noqa: E402
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
    certified = certified_metrics()
    todo = [(c, rep) for c in cases for rep in range(reps) if (c["id"], rep) not in finished]
    lock = threading.Lock()
    counts = {"skipped": len(cases) * reps - len(todo), "graded": 0, "errors": 0}

    def one(case: dict, rep: int) -> None:
        got: RunResult = provider.run(case["question"], arm, timeout_s)
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
            replacement = got.answer.get("replacement_metric") in certified
            scores, problem = grade(case, got.answer, replacement_certified=replacement)
            row = {**base, "prompt": case["question"], "tags": [case["kind"], arm], "status": "ok",
                   "grade": {k: float(v) for k, v in scores.items()}, "answer": got.answer,
                   "expected": {"value": case["expected"], "caveats": case["expected_caveats"]},
                   "problem": problem, "meta": {"decision": case["decision"], "metric": case["metric"]}}
            append(results, row)
            counts["graded"] += 1
            mark = "pass" if scores["pass"] else f"FAIL ({problem})"
            print(f"  {case['id']} rep{rep}: {mark} [{got.tool_calls} tool calls, {got.latency_s}s]", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for future in [pool.submit(one, c, rep) for c, rep in todo]:
            future.result()
    return counts


def append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE.parent,
                          capture_output=True, text=True).stdout.strip()


def probe(provider, timeout_s: float) -> int:
    """Ask the agent what it can see. Pass only if its tools are exactly the arm's tools."""
    got = provider.run(PROBE_PROMPT, "semantic", timeout_s, schema=PROBE_SCHEMA, raw=True)
    if got.error and got.error != "no_answer":
        print(f"Probe failed: {got.error} {got.detail}")
        return 1
    answer = got.answer or {}
    tools = sorted(set(got.tools) - {STRUCTURED_TOOL, "submit_answer"})
    expected = sorted(f"mcp__groundrules__{t}" for t in ("list_metrics", "describe_metric", "find_values", "query_metric"))
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
        return probe(provider, args.timeout_s)

    cases = load_cases([c for c in args.cases.split(",") if c] or None)
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
