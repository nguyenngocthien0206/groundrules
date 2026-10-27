"""Summarize an agent eval run: how often each arm got the right answer.

Usage: python agent_eval/summary.py <run-id>   (or `make agent-eval-summary RUN=<run-id>`)

Rates are means over questions (each question's reps averaged first), so a
question asked three times counts once. The 95% interval is a bootstrap over
questions with a fixed seed, so the same results always print the same
numbers. Writes summary.md next to the arms.
"""

import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
METRICS = (("pass", "Correct"), ("value", "Right number"), ("caveats", "Right caveats"))
KINDS = ("tacit_rule", "conflict", "caveat_required", "deprecated")


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def per_question(rows: list[dict], metric: str) -> dict[str, float]:
    scores: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        scores[r["prompt_id"]].append(r["grade"][metric])
    return {q: sum(v) / len(v) for q, v in scores.items()}


def bootstrap(values: list[float], resamples: int = 2000, seed: int = 7) -> tuple[float, float]:
    """95% interval of the mean, resampling questions."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def arm_summary(arm_dir: Path) -> dict:
    rows = read_rows(arm_dir / "results.jsonl")
    errors = read_rows(arm_dir / "errors.jsonl")
    finished = {(r["prompt_id"], r["rep"]) for r in rows}
    open_errors = [e for e in errors if (e["prompt_id"], e["rep"]) not in finished]
    out = {"arm": arm_dir.name, "rows": len(rows), "questions": len({r["prompt_id"] for r in rows}),
           "errors": len(open_errors), "error_classes": sorted({e["error"] for e in open_errors})}
    for metric, _ in METRICS:
        values = list(per_question(rows, metric).values())
        out[metric] = (statistics.fmean(values) if values else 0.0, *bootstrap(values))
    kinds = {r["prompt_id"]: r["tags"][0] for r in rows}
    out["by_kind"] = {}
    for kind in KINDS:
        values = [v for q, v in per_question(rows, "pass").items() if kinds[q] == kind]
        if values:
            out["by_kind"][kind] = (statistics.fmean(values), len(values))
    out["tool_calls"] = statistics.median([r["tool_calls"] for r in rows]) if rows else 0
    out["latency_s"] = statistics.median([r["latency_s"] for r in rows]) if rows else 0
    out["models"] = sorted({r["model"] for r in rows if r.get("model")})
    return out


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def render(run_id: str, arms: list[dict]) -> str:
    lines = [f"# Agent eval: {run_id}", ""]
    header = "| | " + " | ".join(a["arm"] for a in arms) + " |"
    lines += [header, "|" + " --- |" * (len(arms) + 1)]
    for metric, label in METRICS:
        cells = [f"{pct(a[metric][0])} ({pct(a[metric][1])} to {pct(a[metric][2])})" for a in arms]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    for kind in KINDS:
        cells = [f"{pct(a['by_kind'][kind][0])} of {a['by_kind'][kind][1]}" if kind in a["by_kind"] else "-" for a in arms]
        lines.append(f"| Correct, {kind} | " + " | ".join(cells) + " |")
    lines.append("| Graded answers | " + " | ".join(f"{a['rows']} on {a['questions']} questions" for a in arms) + " |")
    lines.append("| Open errors | " + " | ".join(f"{a['errors']} {', '.join(a['error_classes'])}".strip() for a in arms) + " |")
    lines.append("| Median tool calls | " + " | ".join(str(a["tool_calls"]) for a in arms) + " |")
    lines.append("| Median seconds | " + " | ".join(str(a["latency_s"]) for a in arms) + " |")
    lines.append("| Model | " + " | ".join(", ".join(a["models"]) for a in arms) + " |")
    lines += ["", "Rates are means over questions; brackets are 95% bootstrap intervals over questions."]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    run_dir = RUNS / argv[0]
    arms = [arm_summary(d) for d in sorted(p for p in run_dir.iterdir() if p.is_dir())] if run_dir.exists() else []
    if not arms:
        print(f"No results in {run_dir}")
        return 1
    text = render(argv[0], arms)
    (run_dir / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
