"""Raw SQL plus a write tool that checks nothing, for AI agents, over MCP: the action eval's control arm.

Usage: python mcp_server/raw_actions.py   (the agent eval starts it; there is no make target on purpose)

This is what an agent gets when it is handed write access without an action
contract: the reporting tables, a SQL tool, and a tool that files whatever
transfer it is told. In the eval the agent also has DR-012's rules in its
prompt, so the comparison with mcp_server/actions.py is a policy written in
the prompt against a policy the tools enforce. Never give this to an agent
in production.

The SQL tools are raw_sql.py's: read-only, one SELECT per call, no files.
`file_transfer` writes to `unguarded_transfers` in GROUNDRULES_ACTIONS_DB
(default var/unguarded.duckdb), never to the warehouse or the ERP.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "mcp_server")]

import duckdb  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

import raw_sql  # noqa: E402

DEFAULT_DB = ROOT / "var" / "unguarded.duckdb"
SCHEMA = """
create table if not exists unguarded_transfers (
    target_store varchar,
    donor_store varchar,
    sku varchar,
    quantity integer,
    unit varchar,
    filed_at timestamp  -- UTC
)
"""

INSTRUCTIONS = raw_sql.INSTRUCTIONS + """
file_transfer records a stock transfer between two stores."""

server = MCPServer("warehouse-actions", instructions=INSTRUCTIONS)
for tool in (raw_sql.list_tables, raw_sql.describe_table, raw_sql.run_sql):
    server.tool()(tool)


def db_path() -> Path:
    return Path(os.environ.get("GROUNDRULES_ACTIONS_DB", DEFAULT_DB))


@server.tool()
def file_transfer(target_store: str, donor_store: str, sku: str, quantity: int, unit: str) -> dict:
    """File a stock transfer: `quantity` of `unit` (BOX or CARTON) of a SKU from the donor store to
    the target store. Store codes look like NW001, SKU codes like 100001."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as con:
        con.execute(SCHEMA)
        con.execute("insert into unguarded_transfers values (?, ?, ?, ?, ?, ?)",
                    [target_store, donor_store, sku, quantity, unit, datetime.now(timezone.utc).replace(tzinfo=None)])
        filed = con.execute("select count(*) from unguarded_transfers").fetchone()[0]
    return {"filed": True, "transfer_number": filed}


if __name__ == "__main__":
    server.run("stdio")
