"""Governance lint: ownership, decisions, proof and hygiene, enforced in CI.

Usage: python governance/lint.py [--today YYYY-MM-DD] [--fail-on-stale]
       (`make lint` runs `dbt parse` first)

Each check takes the loaded repo (governance/repo.py) and returns issues.
Errors fail the run, one line each, saying what to fix. Warnings are printed.

--today defaults to the snapshot date, so the demo gives the same result on
any calendar day. A company's CI passes the real date.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo import GOVERNANCE_FIELDS, ROOT, STATUSES, Repo, consumers, governed, load  # noqa: E402

SNAPSHOT_DATE = date(2026, 9, 15)
DECISION_KEYS = {
    "id", "title", "status", "date", "decided_by", "consulted",
    "linked_metrics", "linked_golden_questions", "supersedes", "superseded_by",
}
DECISION_STATUSES = {"proposed", "accepted", "superseded"}
DECISION_SECTIONS = ["Context", "Decision", "Options considered", "Consequences", "Worked example"]
EM_DASH = chr(0x2014)  # written as a code point so this file passes its own check


@dataclass(frozen=True)
class Issue:
    level: str  # "error" or "warning"
    check: str
    message: str


def _error(check: str, message: str) -> Issue:
    return Issue("error", check, message)


def check_ownership(repo: Repo) -> list[Issue]:
    issues = []
    for m in governed(repo).values():
        if not m.group:
            issues.append(_error("ownership", f"metric {m.name} has no group (business owner) in {m.file}"))
        elif m.group not in repo.group_teams:
            issues.append(_error("ownership", f"metric {m.name}: group {m.group} is not defined in dbt/models/groups.yml"))
        missing = [f for f in GOVERNANCE_FIELDS if f not in m.meta]
        if missing:
            issues.append(_error("ownership", f"metric {m.name} is missing governance fields: {', '.join(missing)}"))
        if m.meta.get("status") not in STATUSES:
            issues.append(_error("ownership", f"metric {m.name}: status must be one of {', '.join(STATUSES)}"))
    for group, team in repo.group_teams.items():
        if not team:
            issues.append(_error("ownership", f"group {group} has no config.meta.github_team in dbt/models/groups.yml"))
    return issues


def check_decisions(repo: Repo) -> list[Issue]:
    issues = []
    for dr in repo.decisions.values():
        if dr.front is None:
            issues.append(_error("decisions", f"{dr.path} has no readable YAML front matter"))
            continue
        missing = DECISION_KEYS - set(dr.front)
        if missing:
            issues.append(_error("decisions", f"{dr.path} front matter is missing: {', '.join(sorted(missing))}"))
        if dr.front.get("id") != dr.id:
            issues.append(_error("decisions", f"{dr.path}: id must be {dr.id}"))
        if dr.front.get("status") not in DECISION_STATUSES:
            issues.append(_error("decisions", f"{dr.path}: status must be one of {', '.join(sorted(DECISION_STATUSES))}"))
        if list(dr.sections) != DECISION_SECTIONS or not all(dr.sections.values()):
            issues.append(_error("decisions", f"{dr.path} needs the sections {', '.join(DECISION_SECTIONS)}, in order, none empty"))
        elif not re.search(r"\d", dr.sections["Worked example"]):
            issues.append(_error("decisions", f"{dr.path}: the worked example shows no numbers"))
        for name in dr.front.get("linked_metrics") or []:
            if name not in repo.metrics:
                issues.append(_error("decisions", f"{dr.path} links metric {name}, which does not exist"))
        if f"[{dr.id}]({dr.id}.md)" not in repo.decisions_index:
            issues.append(_error("decisions", f"decisions/README.md does not list {dr.id}"))
        # A rule changes by a new record replacing the old one; both must say so.
        newer, older = dr.front.get("superseded_by"), dr.front.get("supersedes")
        if newer and ((repo.decisions.get(newer) and repo.decisions[newer].front or {}).get("supersedes") != dr.id):
            issues.append(_error("decisions", f"{dr.path} is superseded_by {newer}, but {newer} does not say it supersedes {dr.id}"))
        if newer and dr.front.get("status") != "superseded":
            issues.append(_error("decisions", f"{dr.path} is superseded_by {newer}, so its status must be superseded"))
        if older and ((repo.decisions.get(older) and repo.decisions[older].front or {}).get("superseded_by") != dr.id):
            issues.append(_error("decisions", f"{dr.path} supersedes {older}, but {older} does not say superseded_by: {dr.id}"))
    for m in governed(repo).values():
        link = m.meta.get("decision")
        if not link:
            continue
        dr = repo.decisions.get(Path(str(link)).stem)
        if dr is None or link != dr.path:
            issues.append(_error("decisions", f"metric {m.name}: decision {link} does not exist"))
        elif m.name not in (dr.front or {}).get("linked_metrics", []):
            issues.append(_error("decisions", f"metric {m.name}: {link} does not list it under linked_metrics"))
        elif (dr.front or {}).get("status") != "accepted":
            replaced = (dr.front or {}).get("superseded_by")
            hint = f"; link decisions/{replaced}.md, which replaced it" if replaced else ""
            issues.append(_error("decisions", f"metric {m.name}: {link} is {dr.front.get('status')}, not accepted{hint}"))
    return issues


def check_golden_questions(repo: Repo) -> list[Issue]:
    issues = []
    asked = {q["metric"] for q in repo.questions}
    ids = {q["id"] for q in repo.questions}
    for m in governed(repo).values():
        if m.meta.get("status") == "certified" and m.name not in asked:
            issues.append(_error("golden", f"certified metric {m.name} has no golden question in golden/questions/"))
    for q in repo.questions:
        dr = repo.decisions.get(q["decision"])
        if dr is None:
            issues.append(_error("golden", f"{q['id']} ({q['file']}): decision {q['decision']} does not exist"))
        elif q["id"] not in (dr.front or {}).get("linked_golden_questions", []):
            issues.append(_error("golden", f"{q['id']} ({q['file']}): {dr.path} does not list it under linked_golden_questions"))
        if q["metric"] not in governed(repo):
            issues.append(_error("golden", f"{q['id']} asks about {q['metric']}, which is not a governed metric"))
    for dr in repo.decisions.values():
        for qid in sorted(set((dr.front or {}).get("linked_golden_questions") or []) - ids):
            issues.append(_error("golden", f"{dr.path} reserves {qid}, which is not in golden/questions/"))
    question_files = sorted({q["file"] for q in repo.questions})
    if question_files != repo.expected_files:
        issues.append(_error("golden", "golden/expected/ does not mirror golden/questions/: run `make golden-freeze`"))
    return issues


def check_lifecycle(repo: Repo) -> list[Issue]:
    issues = []
    for m in governed(repo).values():
        if m.meta.get("status") != "deprecated":
            continue
        target = m.meta.get("replaced_by")
        if not target:
            issues.append(_error("lifecycle", f"deprecated metric {m.name} has no replaced_by"))
        elif repo.metrics.get(target) is None or repo.metrics[target].meta.get("status") != "certified":
            issues.append(_error("lifecycle", f"deprecated metric {m.name} points to {target}, which is not a certified metric"))
    return issues


def check_contracts(repo: Repo) -> list[Issue]:
    return [
        _error("contracts", f"model {model} backs semantic model {sm} but has no enforced contract")
        for sm, model in sorted(repo.semantic_models.items())
        if not repo.models.get(model, {}).get("contract_enforced")
    ]


def required_rule_owners(repo: Repo) -> dict[str, set[str]]:
    """For each YAML file that holds a rule, the teams that own the metrics it shapes."""
    required: dict[str, set[str]] = {}
    for m in repo.metrics.values():
        owners = [m.name] if not m.hidden else sorted(consumers(repo, m.name))
        for name in owners:
            team = repo.group_teams.get(repo.metrics[name].group or "")
            if team:
                required.setdefault(m.file, set()).add(team)
    # A saved query decides which slice of a metric a dashboard shows.
    for sq in repo.saved_queries.values():
        for name in sq["metrics"]:
            metric = repo.metrics.get(name)
            team = repo.group_teams.get(metric.group or "") if metric else None
            if team:
                required.setdefault(sq["file"], set()).add(team)
    return required


def check_codeowners(repo: Repo) -> list[Issue]:
    if not repo.codeowners:
        return [_error("codeowners", ".github/CODEOWNERS is missing or empty")]
    issues = []
    # A file holding rules is reviewed by exactly the owners of those rules:
    # any listed owner can approve on GitHub, so an extra team could approve alone.
    for path, teams in sorted(required_rule_owners(repo).items()):
        actual = set(repo.teams_for(path))
        if actual != teams:
            issues.append(_error("codeowners", f"{path} must be owned by {', '.join(sorted(teams))}; CODEOWNERS says {', '.join(sorted(actual)) or 'nobody'}"))

    def team(metric: str) -> str | None:
        found = repo.metrics.get(metric)
        return repo.group_teams.get(found.group) if found and found.group else None

    # Decision records and golden files must at least reach every owner they cover.
    for dr in repo.decisions.values():
        needed = {team(n) for n in (dr.front or {}).get("linked_metrics") or []} - {None}
        missing = needed - set(repo.teams_for(dr.path))
        if missing:
            issues.append(_error("codeowners", f"{dr.path} must be owned by {', '.join(sorted(missing))} too"))
    for name in sorted({q["file"] for q in repo.questions}):
        needed = {team(q["metric"]) for q in repo.questions if q["file"] == name} - {None}
        for path in (f"golden/questions/{name}", f"golden/expected/{name}"):
            missing = needed - set(repo.teams_for(path))
            if missing:
                issues.append(_error("codeowners", f"{path} must be owned by {', '.join(sorted(missing))} too"))
    return issues


def check_em_dash(repo: Repo) -> list[Issue]:
    issues = []
    for path, text in sorted(repo.text_files.items()):
        for number, line in enumerate(text.splitlines(), start=1):
            if EM_DASH in line:
                issues.append(_error("em-dash", f"{path}:{number} contains an em dash; use a comma, a colon or a new sentence"))
    return issues


def check_registry(repo: Repo) -> list[Issue]:
    from registry import REGISTRY, render

    current = REGISTRY.read_text(encoding="utf-8") if REGISTRY.exists() else ""
    if current != render(repo):
        return [_error("registry", "governance/registry.md is out of date: run `make registry`")]
    return []


DISPLAY_ONLY = re.compile(r"^(SELECTEDVALUE|MAX|MIN)\(\s*('[^']+'|\w+)\[[^\]]+\]\s*\)$")
METRIC_TAG = re.compile(r"metric:\s*(\w+)\s+v(\d+)")
EXPORT_FOLDER_PLACEHOLDER = r"C:\path\to\groundrules\dashboards\exports"
AUTO_DATE_TABLE = re.compile(r"^(LocalDateTable|DateTableTemplate)_")


def check_powerbi(repo: Repo) -> list[Issue]:
    """The Power BI model shows certified exports and never computes a metric itself."""
    if not repo.powerbi:
        return []
    issues = []
    if not re.search(r"^\tdiscourageImplicitMeasures\s*$", repo.powerbi["model"], re.MULTILINE):
        issues.append(_error("powerbi", "the Power BI model must set discourageImplicitMeasures, so nobody can sum a metric by dragging a column"))
    # Saving in Power BI Desktop writes the saver's own folder into the parameter.
    if f'expression ExportFolder = "{EXPORT_FOLDER_PLACEHOLDER}"' not in repo.powerbi["expressions"]:
        issues.append(_error("powerbi", f"ExportFolder in expressions.tmdl holds someone's local path; put back {EXPORT_FOLDER_PLACEHOLDER} before committing"))
    # Auto date/time adds a hidden date table and relationship for every date column.
    auto_dates = [t["name"] for t in repo.powerbi["tables"] if AUTO_DATE_TABLE.match(t["name"])]
    if auto_dates or "annotation __PBI_TimeIntelligenceEnabled = 0" not in repo.powerbi["model"]:
        issues.append(_error("powerbi", f"Auto date/time is on ({len(auto_dates)} hidden date tables): turn it off in "
                                        "File > Options > Current file > Data load, and remove the LocalDateTable files"))
    # Power BI refuses to open a model where two measures share a name, even in
    # different tables (names are case-insensitive), or a measure is named like a column.
    measure_tables = {}
    for table in repo.powerbi["tables"]:
        for m in table["measures"]:
            measure_tables.setdefault(m["name"].lower(), []).append(table["name"])
    columns = {c["name"].lower() for t in repo.powerbi["tables"] for c in t["columns"]}
    for name, owners in sorted(measure_tables.items()):
        if len(owners) > 1:
            issues.append(_error("powerbi", f"measure '{name}' is defined in {', '.join(owners)}; measure names must be unique in the model, like 'Net revenue by month'"))
        if name in columns:
            issues.append(_error("powerbi", f"measure '{name}' has the same name as a column; Power BI will not open the model"))
    for table in repo.powerbi["tables"]:
        shown = set()
        for m in table["measures"]:
            where = f"{table['file']}: measure '{m['name']}'"
            if not DISPLAY_ONLY.match(m["expression"]):
                issues.append(_error("powerbi", f"{where} computes `{m['expression']}`; only SELECTEDVALUE, MAX or MIN of one exported column is allowed"))
            else:
                shown.add(re.search(r"\[([^\]]+)\]", m["expression"]).group(1))
            tag = METRIC_TAG.search(m["description"])
            if not tag:
                issues.append(_error("powerbi", f"{where} needs a /// description naming its metric and version, like `metric: net_revenue v2`"))
                continue
            metric = repo.metrics.get(tag.group(1))
            if metric is None or metric.meta.get("status") != "certified":
                issues.append(_error("powerbi", f"{where} shows {tag.group(1)}, which is not a certified metric"))
            elif str(metric.meta.get("version")) != tag.group(2):
                issues.append(_error("powerbi", f"{where} says {tag.group(1)} v{tag.group(2)}, but the certified version is v{metric.meta.get('version')}"))
        for c in table["columns"]:
            if (c["sourceColumn"] in shown or c["sourceColumn"] in repo.metrics) and (
                c["summarizeBy"] != "none" or c["summarizationSetBy"] != "User"
            ):
                # Without the User annotation, a refresh in Power BI resets the column to sum.
                issues.append(_error("powerbi", f"{table['file']}: column '{c['name']}' holds a metric and must have "
                                                "summarizeBy: none with `annotation SummarizationSetBy = User`"))
    return issues


def check_staleness(repo: Repo, today: date, fail_on_stale: bool = False) -> list[Issue]:
    issues = []
    for m in governed(repo).values():
        if m.meta.get("status") != "certified":
            continue
        try:
            due = date.fromisoformat(str(m.meta["certified_on"])) + timedelta(days=int(m.meta["recertify_every_days"]))
        except (KeyError, ValueError):
            continue  # reported by check_ownership
        if due < today:
            level = "error" if fail_on_stale else "warning"
            issues.append(Issue(level, "staleness", f"metric {m.name} was due for recertification on {due} (owner: {m.group})"))
    return issues


CHECKS = (
    check_ownership, check_decisions, check_golden_questions, check_lifecycle,
    check_contracts, check_codeowners, check_em_dash, check_registry, check_powerbi,
)


def run(repo: Repo, today: date = SNAPSHOT_DATE, fail_on_stale: bool = False) -> list[Issue]:
    issues = [issue for check in CHECKS for issue in check(repo)]
    return issues + check_staleness(repo, today, fail_on_stale)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governance lint for the semantic layer.")
    parser.add_argument("--today", type=date.fromisoformat, default=SNAPSHOT_DATE,
                        help="date to check recertification against (default: the snapshot date)")
    parser.add_argument("--fail-on-stale", action="store_true", help="treat overdue recertification as an error")
    args = parser.parse_args(argv)

    repo = load()
    issues = run(repo, args.today, args.fail_on_stale)
    errors = [i for i in issues if i.level == "error"]
    for issue in sorted(issues, key=lambda i: (i.level != "error", i.check, i.message)):
        print(f"{issue.level.upper():<8}{issue.check:<12}{issue.message}")
    print(f"\n{len(governed(repo))} governed metrics, {len(repo.decisions)} decision records, "
          f"{len(repo.questions)} golden questions checked as of {args.today}: "
          f"{len(errors)} errors, {len(issues) - len(errors)} warnings.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
