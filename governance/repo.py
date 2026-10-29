"""Load what the governance tools read, once, into plain Python data.

Sources: dbt's `target/manifest.json` (after `dbt parse`), the decision
records, the action contracts, the golden questions, `.github/CODEOWNERS`
and the files Git sees.
The checks in lint.py take this data, not files, so tests can hand them a
broken copy without running dbt.
"""

import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = ROOT / "dbt"
MANIFEST = DBT_DIR / "target" / "manifest.json"
sys.path.insert(0, str(ROOT / "golden"))

from catalog import ACTION_EXPECTED_DIR, EXPECTED_DIR, load_action_questions, load_questions  # noqa: E402

GOVERNANCE_FIELDS = ("version", "status", "certified_on", "recertify_every_days", "decision", "replaced_by", "agent_notes")
STATUSES = ("draft", "certified", "deprecated")


@dataclass
class Metric:
    name: str
    label: str
    group: str | None
    meta: dict
    hidden: bool
    file: str  # repo-relative path of the YAML that defines it
    depends_on: list[str]  # names of metrics and semantic models it reads


@dataclass
class Decision:
    id: str
    path: str
    front: dict | None  # None when the front matter is missing or broken
    sections: dict[str, str]


@dataclass
class Repo:
    metrics: dict[str, Metric]
    group_teams: dict[str, str | None]  # group name -> github team
    semantic_models: dict[str, str]  # semantic model name -> model name
    models: dict[str, dict]  # model name -> {contract_enforced, sql, yml}
    exposures: dict[str, dict]  # exposure name -> {label, type, maturity, owner, depends_on, replaced_by_metric}
    decisions: dict[str, Decision]
    decisions_index: str
    questions: list[dict]
    expected_files: list[str]
    codeowners: list[tuple[str, list[str]]]
    text_files: dict[str, str] = field(default_factory=dict)
    model_children: dict[str, list[str]] = field(default_factory=dict)  # model -> models built on it
    saved_queries: dict[str, dict] = field(default_factory=dict)  # name -> {file, metrics}
    powerbi: dict = field(default_factory=dict)  # {"model": text, "tables": [parsed TMDL tables]}
    actions: dict[str, dict] = field(default_factory=dict)  # action file stem -> {"path": ..., "spec": parsed YAML or None}
    approvers: dict = field(default_factory=dict)  # actions/approvers.yml: action -> {"group", "people"}
    action_questions: list[dict] = field(default_factory=list)  # golden/actions/questions/
    action_expected_files: list[str] = field(default_factory=list)

    def teams_for(self, path: str) -> list[str]:
        return owners_of(self.codeowners, path)


def _repo_path(dbt_relative: str) -> str:
    """dbt writes paths relative to its project, with the OS separator."""
    return "dbt/" + dbt_relative.replace("\\", "/").split("://", 1)[-1]


def parse_decision(path: Path) -> Decision:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    front, body = (None, text)
    if match:
        try:
            front = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            front = None
        body = match.group(2)
    parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
    sections = {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}
    return Decision(path.stem, path.relative_to(ROOT).as_posix(), front if isinstance(front, dict) else None, sections)


def parse_codeowners(text: str) -> list[tuple[str, list[str]]]:
    rules = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pattern, *owners = line.split()
            rules.append((pattern, owners))
    return rules


def _matches(pattern: str, path: str) -> bool:
    """The subset of GitHub's CODEOWNERS syntax this repo uses."""
    anchored = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    if pattern.endswith("/"):
        return path.startswith(pattern) if anchored else f"/{pattern}" in f"/{path}"
    if "/" not in pattern and not anchored:
        return fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern)
    return fnmatch.fnmatch(path, pattern)


def owners_of(rules: list[tuple[str, list[str]]], path: str) -> list[str]:
    """Owners of a path: the last matching rule wins, as on GitHub."""
    owners: list[str] = []
    for pattern, rule_owners in rules:
        if _matches(pattern, path):
            owners = rule_owners
    return owners


def parse_tmdl_table(path: Path) -> dict:
    """The parts of a TMDL table file the lint reads: measures and columns.

    Handles the TMDL this repo writes and Power BI Desktop saves: tab
    indentation, `///` descriptions right above an object, one-line measures,
    and the `SummarizationSetBy` annotation on columns.
    """
    table = {"file": path.relative_to(ROOT).as_posix(), "name": None, "measures": [], "columns": []}
    description: list[str] = []
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        depth = len(line) - len(line.lstrip("\t"))
        text = line.strip()
        if depth == 0 and text.startswith("table "):
            table["name"] = text[len("table "):].strip("'")
        elif depth == 1 and text.startswith("///"):
            description.append(text[3:].strip())
        elif depth == 1 and text.startswith("measure "):
            name, _, expression = text[len("measure "):].partition("=")
            current = {"name": name.strip().strip("'"), "expression": expression.strip(), "description": " ".join(description)}
            table["measures"].append(current)
            description = []
        elif depth == 1 and text.startswith("column "):
            current = {"name": text[len("column "):].strip("'"), "summarizeBy": None, "sourceColumn": None,
                       "summarizationSetBy": None, "description": " ".join(description)}
            table["columns"].append(current)
            description = []
        elif depth == 1 and text:
            current, description = None, []
        elif depth == 2 and current is not None and text.startswith("annotation SummarizationSetBy") and current in table["columns"]:
            current["summarizationSetBy"] = text.partition("=")[2].strip()
        elif depth == 2 and current is not None and ":" in text and current in table["columns"]:
            key, _, value = text.partition(":")
            if key in ("summarizeBy", "sourceColumn"):
                current[key] = value.strip()
    return table


APPROVERS = ROOT / "actions" / "approvers.yml"


def load_actions() -> dict[str, dict]:
    actions = {}
    for path in sorted((ROOT / "actions").glob("*.yml")):
        if path == APPROVERS:
            continue
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            spec = None
        actions[path.stem] = {"path": path.relative_to(ROOT).as_posix(), "spec": spec if isinstance(spec, dict) else None}
    return actions


def load_approvers() -> dict:
    if not APPROVERS.exists():
        return {}
    try:
        found = yaml.safe_load(APPROVERS.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {"_unreadable": True}
    return found if isinstance(found, dict) else {"_unreadable": True}


def load_powerbi() -> dict:
    definition = ROOT / "dashboards" / "groundrules.SemanticModel" / "definition"
    if not definition.exists():
        return {}
    return {
        "model": (definition / "model.tmdl").read_text(encoding="utf-8"),
        "expressions": (definition / "expressions.tmdl").read_text(encoding="utf-8"),
        "tables": [parse_tmdl_table(p) for p in sorted((definition / "tables").glob("*.tmdl"))],
    }


def tracked_text_files() -> dict[str, str]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    files = {}
    for rel in listed:
        path = ROOT / rel
        if not path.is_file():
            continue  # deleted in the working tree
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary
    return files


def load(with_text_files: bool = True) -> Repo:
    if not MANIFEST.exists():
        raise FileNotFoundError("No dbt manifest: run `make lint` (it runs `dbt parse` first) or `dbt parse`.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def short(unique_id: str) -> str:
        return unique_id.rsplit(".", 1)[-1]

    metrics = {}
    for m in manifest["metrics"].values():
        config = m.get("config") or {}
        metrics[m["name"]] = Metric(
            name=m["name"],
            label=m.get("label") or m["name"],
            group=m.get("group") or config.get("group"),
            meta=dict(config.get("meta") or {}),
            hidden=bool((m.get("type_params") or {}).get("is_private")),
            file=_repo_path(m["original_file_path"]),
            depends_on=[short(n) for n in m["depends_on"]["nodes"]],
        )
    group_teams = {g["name"]: ((g.get("config") or {}).get("meta") or {}).get("github_team") for g in manifest["groups"].values()}
    models = {
        n["name"]: {
            "contract_enforced": bool(((n.get("config") or {}).get("contract") or {}).get("enforced")),
            "sql": _repo_path(n["original_file_path"]),
            "yml": _repo_path(n["patch_path"]) if n.get("patch_path") else None,
        }
        for n in manifest["nodes"].values()
        if n["resource_type"] == "model"
    }
    semantic_models = {s["name"]: short(s["depends_on"]["nodes"][0]) for s in manifest["semantic_models"].values()}
    exposures = {
        e["name"]: {
            "label": e.get("label") or e["name"],
            "type": e["type"],
            "maturity": e.get("maturity"),
            "owner": (e.get("owner") or {}).get("name"),
            "depends_on": sorted(short(n) for n in e["depends_on"]["nodes"]),
            "replaced_by_metric": ((e.get("config") or {}).get("meta") or {}).get("replaced_by_metric"),
        }
        for e in manifest["exposures"].values()
    }
    model_children = {
        short(parent): sorted(short(c) for c in children if c.startswith("model."))
        for parent, children in manifest["child_map"].items()
        if parent.startswith("model.")
    }
    decisions_dir = ROOT / "decisions"
    decisions = {p.stem: parse_decision(p) for p in sorted(decisions_dir.glob("DR-*.md"))}
    codeowners_file = ROOT / ".github" / "CODEOWNERS"
    return Repo(
        metrics=metrics,
        group_teams=group_teams,
        semantic_models=semantic_models,
        models=models,
        exposures=exposures,
        decisions=decisions,
        decisions_index=(decisions_dir / "README.md").read_text(encoding="utf-8"),
        questions=load_questions(),
        expected_files=sorted(p.name for p in EXPECTED_DIR.glob("*.yml")),
        codeowners=parse_codeowners(codeowners_file.read_text(encoding="utf-8")) if codeowners_file.exists() else [],
        text_files=tracked_text_files() if with_text_files else {},
        model_children=model_children,
        saved_queries={
            sq["name"]: {"file": _repo_path(sq["original_file_path"]), "metrics": list(sq["query_params"]["metrics"])}
            for sq in manifest.get("saved_queries", {}).values()
        },
        powerbi=load_powerbi(),
        actions=load_actions(),
        approvers=load_approvers(),
        action_questions=load_action_questions(),
        action_expected_files=sorted(p.name for p in ACTION_EXPECTED_DIR.glob("*.yml")),
    )


def governed(repo: Repo) -> dict[str, Metric]:
    """Metrics people and agents may use: everything that is not a hidden building block."""
    return {name: m for name, m in repo.metrics.items() if not m.hidden}


def consumers(repo: Repo, name: str) -> set[str]:
    """Governed metrics that read `name`, directly or through other metrics."""
    found, frontier = set(), {name}
    while frontier:
        nxt = {m.name for m in repo.metrics.values() if frontier & set(m.depends_on)} - found
        found |= nxt
        frontier = nxt
    return {n for n in found if not repo.metrics[n].hidden}
