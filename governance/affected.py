"""List the metrics and exposures a branch touches, for the pull request.

Usage: python governance/affected.py [--base origin/main] [changed paths ...]
       (`make affected BASE=origin/main`)

Without paths, it reads the files changed since BASE (committed or not, new
files included). It follows dbt's lineage: a changed model moves every model
built on it, the semantic models on those, the metrics they feed, and the
exposures that read any of them. Paste the output into the PR template.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo import ROOT, Repo, consumers, load  # noqa: E402


def changed_files(base: str) -> list[str]:
    def git(*args: str) -> list[str]:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()

    return sorted(set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard")))


def affected(repo: Repo, paths: list[str]) -> tuple[list[str], list[str]]:
    """Governed metrics and exposures touched by changes to `paths`."""
    paths = {p.replace("\\", "/") for p in paths}
    models = {name for name, m in repo.models.items() if m["sql"] in paths or m["yml"] in paths}
    frontier = set(models)
    while frontier:  # everything built on a changed model changes too
        frontier = {c for parent in frontier for c in repo.model_children.get(parent, [])} - models
        models |= frontier

    semantic = {sm for sm, model in repo.semantic_models.items() if model in models}
    touched = {m.name for m in repo.metrics.values() if m.file in paths or semantic & set(m.depends_on)}
    metrics = set()
    for name in touched:
        if not repo.metrics[name].hidden:
            metrics.add(name)
        metrics |= consumers(repo, name)

    exposures = {name for name, e in repo.exposures.items() if set(e["depends_on"]) & (models | metrics)}
    return sorted(metrics), sorted(exposures)


def render(repo: Repo, metrics: list[str], exposures: list[str], base: str) -> str:
    lines = [f"Affected by changes since `{base}`:", ""]
    lines.append("Metrics:" if metrics else "Metrics: none")
    for name in metrics:
        m = repo.metrics[name]
        lines.append(f"- `{name}` ({m.meta.get('status')}, owner {m.group})")
    lines.append("Exposures:" if exposures else "Exposures: none")
    for name in exposures:
        e = repo.exposures[name]
        lines.append(f"- `{name}` ({e['label']}, owner {e['owner']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("paths", nargs="*", help="changed paths (default: git diff against --base)")
    args = parser.parse_args(argv)

    repo = load(with_text_files=False)
    metrics, exposures = affected(repo, args.paths or changed_files(args.base))
    print(render(repo, metrics, exposures, args.base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
