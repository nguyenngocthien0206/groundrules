"""The shadow table: proposals an agent has filed, waiting for a person.

A proposal lands here, never in the ERP. Step 18 adds the approval that
turns one into a transfer request, and the audit log.

The table lives in its own DuckDB file (var/actions.duckdb, or the path in
GROUNDRULES_ACTIONS_DB), so the warehouse stays read-only for every reader.
Each call opens the file and closes it again, so the approval tool can use
it between an agent's calls.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "var" / "actions.duckdb"

SCHEMA = """
create table if not exists transfer_proposals (
    proposal_id varchar primary key,
    action varchar not null,
    contract_version integer not null,
    as_of date not null,
    target_store varchar not null,
    donor_store varchar not null,
    sku varchar not null,
    quantity integer not null,
    unit varchar not null,
    base_units integer not null,
    drive_minutes decimal(8, 2) not null,
    partial boolean not null,
    target_cover_before double,
    target_cover_after double,
    donor_cover_before double,
    donor_cover_after double,
    metric_versions varchar not null,  -- JSON: the certified versions the proposal was computed with
    status varchar not null,           -- proposed; step 18 adds approved, rejected
    proposed_at timestamp not null,    -- UTC
    proposed_by varchar not null
)
"""
COLUMNS = (
    "proposal_id", "action", "contract_version", "as_of", "target_store", "donor_store", "sku", "quantity",
    "unit", "base_units", "drive_minutes", "partial", "target_cover_before", "target_cover_after",
    "donor_cover_before", "donor_cover_after", "metric_versions", "status", "proposed_at", "proposed_by",
)


def db_path() -> Path:
    return Path(os.environ.get("GROUNDRULES_ACTIONS_DB", DEFAULT_DB))


def _connect() -> duckdb.DuckDBPyConnection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def proposal_id(action: str, contract_version: int, as_of: str, target: str, sku: str) -> str:
    """One id per target-SKU, data date and contract version: filing it again finds the same row."""
    digest = hashlib.sha256(f"{action}|v{contract_version}|{as_of}|{target}|{sku}".encode()).hexdigest()
    return f"TP-{digest[:12]}"


def _row(values: tuple) -> dict:
    row = dict(zip(COLUMNS, values))
    row["as_of"] = row["as_of"].isoformat()
    row["drive_minutes"] = float(row["drive_minutes"])
    row["metric_versions"] = json.loads(row["metric_versions"])
    row["proposed_at"] = row["proposed_at"].isoformat() + "Z"
    return row


def get(pid: str) -> dict | None:
    with _connect() as con:
        found = con.execute(f"select {', '.join(COLUMNS)} from transfer_proposals where proposal_id = ?", [pid]).fetchone()
    return _row(found) if found else None


def list_proposals(status: str | None = "proposed") -> list[dict]:
    query = f"select {', '.join(COLUMNS)} from transfer_proposals"
    params = []
    if status is not None:
        query += " where status = ?"
        params.append(status)
    with _connect() as con:
        return [_row(r) for r in con.execute(query + " order by proposed_at, proposal_id", params).fetchall()]


def record(proposal: dict, action: str, contract_version: int, proposed_by: str) -> dict:
    """File a proposal as `proposed`. Filing the same one again returns the stored row."""
    pid = proposal_id(action, contract_version, proposal["as_of"], proposal["target_store"], proposal["sku"])
    row = {
        **{k: proposal[k] for k in COLUMNS if k in proposal},
        "proposal_id": pid,
        "action": action,
        "contract_version": contract_version,
        "metric_versions": json.dumps(proposal["metric_versions"], sort_keys=True),
        "status": "proposed",
        "proposed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "proposed_by": proposed_by,
    }
    with _connect() as con:
        try:
            con.execute(f"insert into transfer_proposals ({', '.join(COLUMNS)}) values ({', '.join('?' * len(COLUMNS))})",
                        [row[c] for c in COLUMNS])
            already = False
        except duckdb.ConstraintException:
            already = True  # filed before, maybe by another session
    return {**get(pid), "already_proposed": already}
