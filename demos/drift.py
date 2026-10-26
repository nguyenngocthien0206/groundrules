"""Demo 2: a silent rule change that only the golden questions catch.

Usage: python demos/drift.py   (or `make demo-drift`)

Changes the 90-day line in available stock to 60 days, the kind of edit
that looks harmless in a pull request, without touching its decision record
or any golden question. Then shows what each safeguard says: the lint (all
fields and links still in place), the affected metrics and the team
CODEOWNERS will ask, and the golden questions (they fail, with their why).
The file is always restored, even if a step fails or the demo is interrupted.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = ROOT / "dbt"
sys.path.insert(0, str(ROOT / "golden"))
sys.path.insert(0, str(ROOT / "governance"))

RULE_FILE = DBT_DIR / "models" / "semantic" / "fct_inventory_batch.yml"
RULE_FILE_REL = RULE_FILE.relative_to(ROOT).as_posix()
BEFORE = "{{ Dimension('batch__days_to_expiry') }} >= 90"
AFTER = "{{ Dimension('batch__days_to_expiry') }} >= 60"


def apply_drift(text: str) -> str:
    """The silent change: one threshold, nothing else."""
    found = text.count(BEFORE)
    if found != 1:
        raise ValueError(f"expected the 90-day filter exactly once in {RULE_FILE_REL}, found it {found} times")
    return text.replace(BEFORE, AFTER)


def dbt_parse() -> None:
    subprocess.run(["dbt", "parse", "--profiles-dir", ".", "--quiet"], cwd=DBT_DIR, check=True)


def show_safeguards() -> int:
    """Run lint, affected and golden questions against the drifted rule; return the golden failures."""
    from affected import affected
    from catalog import load_expected, load_questions
    from lint import run as run_lint
    from repo import load
    from run_golden import answer, check, store_sync_state
    from semantic_client import SemanticLayer

    repo = load()
    errors = [i for i in run_lint(repo) if i.level == "error"]
    print(f"\n1. Governance lint: {len(errors)} errors. Owner, version, decision link and golden",
          "questions are all still in place, so nothing looks wrong.")
    for issue in errors:
        print(f"   {issue.message}")

    metrics, exposures = affected(repo, [RULE_FILE_REL])
    print(f"\n2. Affected: {', '.join(metrics)}; dashboards: {', '.join(exposures)}.")
    print(f"   CODEOWNERS sends the pull request to {', '.join(repo.teams_for(RULE_FILE_REL))}.")
    print("   A reviewer still has to notice that 60 is not 90.")

    sl = SemanticLayer()
    stores = store_sync_state(sl)
    expected = load_expected()["answers"]
    failures = []
    for q in load_questions():
        got = answer(sl, q, stores)
        replacement = sl.governance(str(got.value)).get("status") == "certified"
        problem = check(q, expected[q["id"]], got, replacement)
        if problem:
            failures.append((q, problem))
    print(f"\n3. Golden questions: {len(failures)} fail.")
    for q, problem in failures:
        print(f"   {q['id']}: {q['question']}\n      {problem}\n      Why: {' '.join(q['why'].split())}\n"
              f"      Decision: decisions/{q['decision']}.md")
    return len(failures)


def main() -> int:
    if not (DBT_DIR / "groundrules.duckdb").exists():
        print("No warehouse yet: run `make data && make build` first.")
        return 1
    original = RULE_FILE.read_bytes()
    drifted = apply_drift(original.decode("utf-8"))
    failures = 0
    try:
        RULE_FILE.write_bytes(drifted.encode("utf-8"))
        print(f"Silent change in {RULE_FILE_REL} (no decision record, no golden question touched):")
        print(f"   - filter: \"{BEFORE}\"\n   + filter: \"{AFTER}\"")
        dbt_parse()
        failures = show_safeguards()
    finally:
        RULE_FILE.write_bytes(original)
        dbt_parse()
    restored = RULE_FILE.read_bytes() == original
    print(f"\n{RULE_FILE_REL} {'restored' if restored else 'NOT restored'}; the manifest is reparsed.")
    if failures == 0:
        print("No golden question failed: the drift went unnoticed, which is the bug this demo exists to show.")
    return 0 if failures and restored else 1


if __name__ == "__main__":
    raise SystemExit(main())
