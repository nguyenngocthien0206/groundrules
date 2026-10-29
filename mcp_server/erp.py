"""A stand-in for the ERP's transfer request table.

An approved proposal becomes one row here, in the ERP's own terms (item
number, from and to store, quantity in the purchase unit). In a company this
is the ERP's API or an import table; here it is its own DuckDB file
(var/erp.duckdb, or the path in GROUNDRULES_ERP_DB), apart from the shadow
table, because it is another system.

Writing is idempotent: one request per proposal, whatever the number of
attempts, so an approval that stopped halfway can simply run again.
"""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "var" / "erp.duckdb"

SCHEMA = """
create table if not exists erp_transfer_requests (
    request_no varchar primary key,
    source_ref varchar not null unique,   -- the proposal id; one request per proposal
    item_no varchar not null,
    from_store varchar not null,
    to_store varchar not null,
    qty integer not null,                  -- in uom
    uom varchar not null,
    min_days_to_expiry integer not null,   -- the warehouse picks lots with at least this much left
    status varchar not null,               -- OPEN until the warehouse picks it
    created_at timestamp not null,         -- UTC
    created_by varchar not null
)
"""
COLUMNS = ("request_no", "source_ref", "item_no", "from_store", "to_store", "qty", "uom",
           "min_days_to_expiry", "status", "created_at", "created_by")


def db_path() -> Path:
    return Path(os.environ.get("GROUNDRULES_ERP_DB", DEFAULT_DB))


def _connect() -> duckdb.DuckDBPyConnection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def _row(values: tuple) -> dict:
    row = dict(zip(COLUMNS, values))
    row["created_at"] = row["created_at"].isoformat() + "Z"
    return row


def find(source_ref: str) -> dict | None:
    with _connect() as con:
        found = con.execute(f"select {', '.join(COLUMNS)} from erp_transfer_requests where source_ref = ?", [source_ref]).fetchone()
    return _row(found) if found else None


def requests() -> list[dict]:
    with _connect() as con:
        return [_row(r) for r in con.execute(f"select {', '.join(COLUMNS)} from erp_transfer_requests order by created_at").fetchall()]


def write_request(proposal: dict, min_days_to_expiry: int, created_by: str) -> tuple[dict, bool]:
    """The ERP request for an approved proposal, and whether this call created it."""
    existing = find(proposal["proposal_id"])
    if existing:
        return existing, False
    digest = hashlib.sha256(proposal["proposal_id"].encode()).hexdigest()
    row = {
        "request_no": f"TRQ-{digest[:10].upper()}",
        "source_ref": proposal["proposal_id"],
        "item_no": proposal["sku"],
        "from_store": proposal["donor_store"],
        "to_store": proposal["target_store"],
        "qty": proposal["quantity"],
        "uom": proposal["unit"],
        "min_days_to_expiry": min_days_to_expiry,
        "status": "OPEN",
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "created_by": created_by,
    }
    with _connect() as con:
        try:
            con.execute(f"insert into erp_transfer_requests ({', '.join(COLUMNS)}) values ({', '.join('?' * len(COLUMNS))})",
                        [row[c] for c in COLUMNS])
        except duckdb.ConstraintException:
            return find(proposal["proposal_id"]), False  # another attempt got there first
    return find(proposal["proposal_id"]), True
