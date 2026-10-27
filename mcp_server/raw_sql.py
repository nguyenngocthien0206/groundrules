"""Raw SQL over the marts, for AI agents, over MCP: the control arm.

Usage: python mcp_server/raw_sql.py   (or `make mcp-server-raw`); speaks MCP over stdio.

This is what agents are commonly given today: the warehouse's reporting
tables, their column descriptions, and a SQL tool. No semantic layer, no
decision records, no caveats. The agent eval runs the same questions through
this server and through mcp_server/semantic.py to measure the difference.
Do not hand this to an agent in production; see adoption/agents.md.

The connection is read-only and only one SELECT runs per call.
"""

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden")]

import duckdb  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from semantic_client import DBT_DIR, DUCKDB_FILE, READ_ONLY  # noqa: E402

SCHEMA = "marts"
MAX_ROWS = 200

INSTRUCTIONS = """\
Read-only SQL access to the reporting tables of Northwind Pharmacy, a 30-store chain, with data up
to 2026-09-15. Use list_tables and describe_table to find the data, then run_sql (DuckDB SQL, one
SELECT per call)."""

server = MCPServer("warehouse", instructions=INSTRUCTIONS)


@cache
def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_FILE), config=READ_ONLY)


@cache
def _docs() -> dict[str, dict]:
    """Model and column descriptions from the dbt manifest, by table name."""
    manifest = json.loads((DBT_DIR / "target" / "manifest.json").read_text(encoding="utf-8"))
    return {
        node["name"]: {"description": node.get("description", ""),
                       "columns": {c: v.get("description", "") for c, v in node.get("columns", {}).items()}}
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model" and node.get("schema") == SCHEMA
    }


def _tables() -> list[str]:
    rows = _con().execute(
        "select table_name from information_schema.tables where table_schema = ? order by table_name", [SCHEMA]
    ).fetchall()
    return [r[0] for r in rows]


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@server.tool()
def list_tables() -> dict:
    """List the reporting tables with what each one holds."""
    docs = _docs()
    return {"tables": [{"table": f"{SCHEMA}.{t}", "description": " ".join(docs.get(t, {}).get("description", "").split())}
                       for t in _tables()]}


@server.tool()
def describe_table(table: str) -> dict:
    """Columns of one table, with their types and descriptions. table is like marts.fct_sales."""
    name = table.split(".")[-1]
    if name not in _tables():
        return {"error": f"unknown table '{table}'", "tables": [f"{SCHEMA}.{t}" for t in _tables()]}
    columns = _con().execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position", [SCHEMA, name]
    ).fetchall()
    docs = _docs().get(name, {}).get("columns", {})
    return {"table": f"{SCHEMA}.{name}",
            "columns": [{"name": c, "type": t, "description": " ".join(docs.get(c, "").split())} for c, t in columns]}


@server.tool()
def run_sql(query: str) -> dict:
    """Run one read-only SELECT (DuckDB SQL) and return up to 200 rows."""
    try:
        statements = _con().extract_statements(query)
    except duckdb.Error as e:
        return {"error": f"could not parse the query: {e}"}
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        return {"error": "only one SELECT statement per call"}
    try:
        cursor = _con().execute(query)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS + 1)
    except duckdb.Error as e:
        return {"error": str(e)}
    return {"columns": columns, "rows": [[_plain(v) for v in r] for r in rows[:MAX_ROWS]],
            "truncated": len(rows) > MAX_ROWS}


if __name__ == "__main__":
    server.run("stdio")
