"""Governed access to the certified metrics, for AI agents, over MCP.

Usage: python mcp_server/semantic.py   (or `make mcp-server`); speaks MCP over stdio.

An agent asks here instead of writing SQL. Every answer takes the code path
the golden questions prove (golden/run_golden.py): a deprecated metric is
refused with a pointer to its replacement, caveats name the lagging and new
stores an answer depends on (DR-004, DR-011), and "no value" stays null.
Nothing here defines a metric; the definitions live in dbt/models/semantic/.

The warehouse and MetricFlow load on the first call, after the server has
claimed stdout, so nothing they print can corrupt the protocol.
"""

import re
import sys
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden"), str(ROOT / "governance")]

from mcp.server.mcpserver import MCPServer  # noqa: E402

from run_golden import NEW_STORE_METRICS, answer, store_sync_state  # noqa: E402

SNAPSHOT = date(2026, 9, 15)  # dbt var snapshot_date: the day the extracts were taken
MONTH = re.compile(r"^\d{4}-\d{2}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_VALUES = 25

INSTRUCTIONS = """\
Certified business metrics for Northwind Pharmacy, a 30-store chain, with data up to 2026-09-15.
Use list_metrics and describe_metric to pick the metric that answers the question, find_values to
turn store, district, category or product names into codes, then query_metric. Report the value
and every caveat exactly as query_metric returns them. A null value means the metric has no value
for that slice; say so rather than reporting 0. A refused metric names the one to use instead."""

server = MCPServer("groundrules", instructions=INSTRUCTIONS)


@cache
def _sl():
    from semantic_client import SemanticLayer

    return SemanticLayer()


@cache
def _repo():
    from repo import load

    return load(with_text_files=False)


@cache
def _stores() -> list[dict]:
    return store_sync_state(_sl())


DIMENSIONS = {
    "store": ["store", "store__store_name", "store__district_code", "store__district_name"],
    "district": ["store__district_code", "store__district_name"],
    "category": ["sku__category_code", "sku__category_name"],
    "sku": ["sku", "sku__sku_name", "sku__category_code"],
}
CODE_FIELD = {"store": "store", "district": "store__district_code", "category": "sku__category_code", "sku": "sku"}


@cache
def _values(kind: str) -> list[dict]:
    rows = _sl().query([], DIMENSIONS[kind])
    unique = {tuple(r[f] for f in DIMENSIONS[kind]): r for r in rows}
    return sorted(unique.values(), key=lambda r: str(r[CODE_FIELD[kind]]))


def _governed() -> dict:
    return {name: m for name, m in _repo().metrics.items() if not m.hidden}


def _decision(link: str | None) -> dict | None:
    if not link:
        return None
    dr = _repo().decisions.get(Path(link).stem)
    if dr is None or dr.front is None:
        return None
    return {"id": dr.id, "title": dr.front.get("title"), "decision": dr.sections.get("Decision", "").strip()}


@server.tool()
def list_metrics() -> dict:
    """List the metrics you may use, with their status. Only certified metrics are answered."""
    metrics = []
    for name, m in sorted(_governed().items()):
        metrics.append({
            "name": name,
            "label": m.label,
            "status": m.meta.get("status"),
            "version": m.meta.get("version"),
            "owner": m.group,
            "description": " ".join(_sl().metrics.get(name, {}).get("description", "").split()),
            "replaced_by": m.meta.get("replaced_by"),
        })
    return {"data_as_of": SNAPSHOT.isoformat(), "metrics": metrics}


@server.tool()
def describe_metric(name: str) -> dict:
    """The full definition of one metric: what it counts, who owns it, the decision behind it,
    notes for agents, and the caveats an answer can carry."""
    m = _governed().get(name)
    if m is None:
        return {"error": f"unknown metric '{name}'", "available": sorted(_governed())}
    meta = m.meta
    caveats = ["pos_sync_lag:<store>: the store's POS data does not cover the whole period yet (DR-004)"]
    if name in NEW_STORE_METRICS:
        caveats.append("new_store:<store>: the store opened during or just after the period (DR-011)")
    certified_on = meta.get("certified_on")
    recertify_by = None
    if certified_on and meta.get("recertify_every_days"):
        recertify_by = (date.fromisoformat(str(certified_on)) + timedelta(days=int(meta["recertify_every_days"]))).isoformat()
    return {
        "name": name,
        "label": m.label,
        "description": " ".join(_sl().metrics.get(name, {}).get("description", "").split()),
        "status": meta.get("status"),
        "version": meta.get("version"),
        "owner": m.group,
        "owner_team": _repo().group_teams.get(m.group or ""),
        "certified_on": str(certified_on) if certified_on else None,
        "recertify_by": recertify_by,
        "agent_notes": " ".join(str(meta.get("agent_notes") or "").split()),
        "decision": _decision(meta.get("decision")),
        "golden_questions": sum(1 for q in _repo().questions if q["metric"] == name),
        "caveats": caveats,
        "replaced_by": meta.get("replaced_by"),
    }


@server.tool()
def find_values(kind: Literal["store", "district", "category", "sku"], search: str = "") -> dict:
    """Find the codes query_metric needs, by name. kind is store, district, category or sku
    (a product); search matches any part of a code or name, case-insensitive. Empty lists all."""
    words = search.lower().split()
    found = [
        {k.split("__")[-1]: v for k, v in r.items()}
        for r in _values(kind)
        if all(w in " ".join(str(v) for v in r.values()).lower() for w in words)
    ]
    return {"kind": kind, "matches": found[:MAX_VALUES], "total": len(found)}


def _check_code(kind: str, code: str | None) -> str | None:
    if code is None:
        return None
    codes = {str(r[CODE_FIELD[kind]]) for r in _values(kind)}
    return None if code in codes else f"unknown {kind} '{code}'; use find_values to look up the code"


@server.tool()
def query_metric(
    metric: str,
    store: str | None = None,
    district: str | None = None,
    category: str | None = None,
    sku: str | None = None,
    month: str | None = None,
    day: str | None = None,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Answer with a certified metric. Filters are codes (see find_values). Give at most one
    period: month (YYYY-MM), day (YYYY-MM-DD), or start and end (YYYY-MM-DD, inclusive).
    Stock metrics are positions read on as_of, which defaults to the data date 2026-09-15."""
    problems = [p for p in (
        _check_code("store", store), _check_code("district", district),
        _check_code("category", category), _check_code("sku", sku),
    ) if p]
    periods = sum(x is not None for x in (month, day, start or end))
    if periods > 1:
        problems.append("give at most one period: month, day, or start and end")
    if (start is None) != (end is None):
        problems.append("start and end go together")
    for value, pattern, label in ((month, MONTH, "month"), (day, DAY, "day"), (start, DAY, "start"),
                                  (end, DAY, "end"), (as_of, DAY, "as_of")):
        if value is not None and not pattern.match(value):
            problems.append(f"{label} must look like {'YYYY-MM' if label == 'month' else 'YYYY-MM-DD'}")
    if problems:
        return {"error": "; ".join(problems)}

    filters = {k: v for k, v in {"store": store, "district": district, "category": category, "sku": sku,
                                 "month": month, "day": day, "start": start, "end": end}.items() if v is not None}
    question = {"metric": metric, "filters": filters, "as_of": date.fromisoformat(as_of) if as_of else SNAPSHOT}
    meta = _sl().governance(metric)
    got = answer(_sl(), question, _stores())

    if meta.get("status") == "deprecated":
        return {"metric": metric, "refused": True, "reason": got.note, "use_instead": got.value}
    if meta.get("status") != "certified":
        certified = sorted(n for n, m in _governed().items() if m.meta.get("status") == "certified")
        return {"metric": metric, "refused": True, "reason": f"{metric} is not a certified metric",
                "certified_metrics": certified}
    result = {
        "metric": metric,
        "version": meta.get("version"),
        "filters": filters,
        "as_of": question["as_of"].isoformat(),
        "value": got.value,
        "caveats": got.caveats,
    }
    if got.value is None:
        result["note"] = "no value for this slice; see describe_metric's agent_notes before answering"
    return result


if __name__ == "__main__":
    server.run("stdio")
