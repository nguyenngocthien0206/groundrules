"""The shadow table: proposals an agent has filed, the decisions on them, and the audit log.

A proposal lands here, never in the ERP. A person approves or rejects it
(mcp_server/approvals.py); only an approved one becomes a request in the
ERP. Every event is appended to `action_audit_log` with who, when and the
versions it rests on. The code here never updates or deletes a log row.

The tables live in their own DuckDB file (var/actions.duckdb, or the path in
GROUNDRULES_ACTIONS_DB), so the warehouse stays read-only for every reader.
Each call opens the file and closes it again, so the agent's server and the
approval command can take turns on it.
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
    status varchar not null,           -- proposed, then approved, rejected or stale
    proposed_at timestamp not null,    -- UTC
    proposed_by varchar not null
);
-- Added with approval; a file from before gets them here.
alter table transfer_proposals add column if not exists decided_at timestamp;  -- UTC
alter table transfer_proposals add column if not exists decided_by varchar;
alter table transfer_proposals add column if not exists decision_reason varchar;
alter table transfer_proposals add column if not exists erp_request_no varchar;

create sequence if not exists audit_event_id;
create table if not exists action_audit_log (
    event_id bigint primary key default nextval('audit_event_id'),
    logged_at timestamp not null,      -- UTC
    action varchar not null,
    proposal_id varchar not null,
    event varchar not null,            -- proposed, approved, rejected, stale, refused, erp_written
    actor varchar not null,
    contract_version integer,
    metric_versions varchar,           -- JSON
    detail varchar
);
"""
COLUMNS = (
    "proposal_id", "action", "contract_version", "as_of", "target_store", "donor_store", "sku", "quantity",
    "unit", "base_units", "drive_minutes", "partial", "target_cover_before", "target_cover_after",
    "donor_cover_before", "donor_cover_after", "metric_versions", "status", "proposed_at", "proposed_by",
    "decided_at", "decided_by", "decision_reason", "erp_request_no",
)
NEW_COLUMNS = COLUMNS[:COLUMNS.index("decided_at")]  # what filing a proposal writes
AUDIT_COLUMNS = ("event_id", "logged_at", "action", "proposal_id", "event", "actor", "contract_version", "metric_versions", "detail")


def db_path() -> Path:
    return Path(os.environ.get("GROUNDRULES_ACTIONS_DB", DEFAULT_DB))


def _connect() -> duckdb.DuckDBPyConnection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat() + "Z"


def proposal_id(action: str, contract_version: int, as_of: str, target: str, sku: str) -> str:
    """One id per target-SKU, data date and contract version: filing it again finds the same row."""
    digest = hashlib.sha256(f"{action}|v{contract_version}|{as_of}|{target}|{sku}".encode()).hexdigest()
    return f"TP-{digest[:12]}"


def _row(values: tuple) -> dict:
    row = dict(zip(COLUMNS, values))
    row["as_of"] = row["as_of"].isoformat()
    row["drive_minutes"] = float(row["drive_minutes"])
    row["metric_versions"] = json.loads(row["metric_versions"])
    row["proposed_at"], row["decided_at"] = _iso(row["proposed_at"]), _iso(row["decided_at"])
    return row


def _log(con, row: dict, event: str, actor: str, detail: str | None = None) -> None:
    con.execute(
        "insert into action_audit_log (logged_at, action, proposal_id, event, actor, contract_version, metric_versions, detail) "
        "values (?, ?, ?, ?, ?, ?, ?, ?)",
        [_now(), row["action"], row["proposal_id"], event, actor, row["contract_version"],
         json.dumps(row["metric_versions"], sort_keys=True), detail],
    )


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


def history(pid: str) -> list[dict]:
    """Every audit event for one proposal, oldest first."""
    with _connect() as con:
        rows = con.execute(f"select {', '.join(AUDIT_COLUMNS)} from action_audit_log where proposal_id = ? order by event_id",
                           [pid]).fetchall()
    events = []
    for values in rows:
        e = dict(zip(AUDIT_COLUMNS, values))
        e["logged_at"] = _iso(e["logged_at"])
        e["metric_versions"] = json.loads(e["metric_versions"]) if e["metric_versions"] else None
        events.append(e)
    return events


def record(proposal: dict, action: str, contract_version: int, proposed_by: str) -> dict:
    """File a proposal as `proposed`. Filing the same one again returns the stored row."""
    pid = proposal_id(action, contract_version, proposal["as_of"], proposal["target_store"], proposal["sku"])
    row = {
        **{k: proposal[k] for k in NEW_COLUMNS if k in proposal},
        "proposal_id": pid,
        "action": action,
        "contract_version": contract_version,
        "metric_versions": json.dumps(proposal["metric_versions"], sort_keys=True),
        "status": "proposed",
        "proposed_at": _now(),
        "proposed_by": proposed_by,
    }
    with _connect() as con:
        try:
            con.begin()
            con.execute(f"insert into transfer_proposals ({', '.join(NEW_COLUMNS)}) values ({', '.join('?' * len(NEW_COLUMNS))})",
                        [row[c] for c in NEW_COLUMNS])
            _log(con, {**row, "metric_versions": proposal["metric_versions"]}, "proposed", proposed_by)
            con.commit()
            already = False
        except duckdb.ConstraintException:
            con.rollback()
            already = True  # filed before, maybe by another session
    return {**get(pid), "already_proposed": already}


def log(pid: str, event: str, actor: str, detail: str | None = None) -> None:
    """Append one event, for something that changed no row (a refused approval)."""
    row = get(pid)
    with _connect() as con:
        _log(con, row, event, actor, detail)


def decide(pid: str, status: str, actor: str, events: list[tuple[str, str | None]],
           reason: str | None = None, erp_request_no: str | None = None) -> dict:
    """Move a proposed proposal to `status` and log `events`, in one transaction.

    Only a proposal still `proposed` moves; for any other the stored row comes
    back unchanged and nothing is logged.
    """
    with _connect() as con:
        con.begin()
        found = con.execute(f"select {', '.join(COLUMNS)} from transfer_proposals where proposal_id = ? and status = 'proposed'",
                            [pid]).fetchone()
        if found:
            con.execute(
                "update transfer_proposals set status = ?, decided_at = ?, decided_by = ?, decision_reason = ?, "
                "erp_request_no = ? where proposal_id = ?",
                [status, _now(), actor, reason, erp_request_no, pid],
            )
            row = _row(found)
            for event, detail in events:
                _log(con, row, event, actor, detail)
        con.commit()
    return get(pid)
