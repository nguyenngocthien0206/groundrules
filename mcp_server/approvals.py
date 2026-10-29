"""Approve or reject transfer proposals, and write approved ones to the ERP.

Usage: python mcp_server/approvals.py list [--status proposed|approved|rejected|stale|all]
       python mcp_server/approvals.py show TP-...
       python mcp_server/approvals.py approve TP-... --as planner.riverside@example.com
       python mcp_server/approvals.py reject TP-... --as planner.riverside@example.com --reason "..."
       (or `make proposals`, `make approve ID=... AS=...`, `make reject ID=... AS=... REASON="..."`)

For people, not agents: the actions server has no tool that approves.
Only someone listed in actions/approvers.yml may decide, never on what they
filed, and only on a proposal as it is (DR-012). Before approving, the
proposal is checked again: the contract and the metrics must still be at
the versions it was computed with, and the rules, run again on today's
data, must give the same donor and quantity. Otherwise it is marked stale
and the agent proposes again.

The ERP and the shadow table are separate systems, so the request is
written first (once per proposal, however often this runs) and the decision
second. An approval that stopped between the two finishes when run again.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden"), str(ROOT / "mcp_server")]

import yaml  # noqa: E402

import erp  # noqa: E402
import shadow  # noqa: E402
import transfers  # noqa: E402

APPROVERS = ROOT / "actions" / "approvers.yml"


class Refusal(Exception):
    """The decision was not taken; the message says why."""


def approvers(action: str) -> set[str]:
    entry = (yaml.safe_load(APPROVERS.read_text(encoding="utf-8")) or {}).get(action) or {}
    return {str(p).lower() for p in entry.get("people") or []}


def _refuse(proposal: dict, approver: str, reason: str) -> None:
    shadow.log(proposal["proposal_id"], "refused", approver, reason)
    raise Refusal(reason)


def _get(pid: str) -> dict:
    proposal = shadow.get(pid)
    if proposal is None:
        raise Refusal(f"there is no proposal {pid}")
    return proposal


def _check_approver(proposal: dict, approver: str) -> None:
    if approver.lower() not in approvers(proposal["action"]):
        _refuse(proposal, approver, f"{approver} is not listed in actions/approvers.yml for {proposal['action']}")
    if approver.lower() == proposal["proposed_by"].removeprefix("mcp:").lower():
        _refuse(proposal, approver, f"{approver} filed this proposal and cannot approve it")


def _planner() -> transfers.TransferPlanner:
    from semantic_client import SemanticLayer

    return transfers.TransferPlanner(SemanticLayer())


def why_stale(proposal: dict, contract: dict, planner_factory) -> str | None:
    """Why the proposal no longer stands, or None if it does."""
    if contract["version"] != proposal["contract_version"] or contract["status"] != "certified":
        return (f"the contract is now v{contract['version']} ({contract['status']}); "
                f"the proposal was made under v{proposal['contract_version']}")
    try:
        planner = planner_factory()
    except transfers.Refused as e:
        return str(e)
    if planner.metric_versions != proposal["metric_versions"]:
        return f"the metrics are now {planner.metric_versions}; the proposal used {proposal['metric_versions']}"
    now = planner.explain(proposal["target_store"], proposal["sku"]).get("proposal")
    if now is None:
        return "the rules, run again on today's data, propose nothing for this target"
    then = {k: proposal[k] for k in ("as_of", "donor_store", "quantity", "unit")}
    current = {k: now[k] for k in then}
    if current != then:
        return f"the rules, run again on today's data, now propose {current}, not {then}"
    return None


def approve(pid: str, approver: str, planner: transfers.TransferPlanner | None = None) -> dict:
    proposal = _get(pid)
    if proposal["status"] == "approved":
        return {"approved": True, "already_approved": True, "proposal": proposal, "erp_request": erp.find(pid)}
    if proposal["status"] != "proposed":
        _refuse(proposal, approver, f"{pid} is {proposal['status']}, so it can no longer be approved")
    _check_approver(proposal, approver)
    contract = transfers.load_contract()
    stale = why_stale(proposal, contract, (lambda: planner) if planner else _planner)
    if stale:
        shadow.decide(pid, "stale", approver, [("stale", stale)], reason=stale)
        raise Refusal(f"{pid} is stale: {stale}. The agent has to propose again.")
    request, _ = erp.write_request(proposal, contract["writes"]["min_days_to_expiry"], approver)
    row = shadow.decide(pid, "approved", approver, [("approved", None), ("erp_written", request["request_no"])],
                        erp_request_no=request["request_no"])
    return {"approved": True, "already_approved": False, "proposal": row, "erp_request": request}


def reject(pid: str, approver: str, reason: str) -> dict:
    proposal = _get(pid)
    if proposal["status"] != "proposed":
        _refuse(proposal, approver, f"{pid} is {proposal['status']}, so it can no longer be rejected")
    _check_approver(proposal, approver)
    if not reason.strip():
        _refuse(proposal, approver, "a rejection needs a reason, so the owners can see whether the rule should change")
    return {"rejected": True, "proposal": shadow.decide(pid, "rejected", approver, [("rejected", reason.strip())],
                                                        reason=reason.strip())}


# Command line


def _line(p: dict) -> str:
    covers = f"cover {p['target_cover_before']:.1f} -> {p['target_cover_after']:.1f} days"
    return (f"{p['proposal_id']}  {p['status']:<8}  {p['target_store']} {p['sku']}: {p['quantity']} {p['unit']} "
            f"from {p['donor_store']} ({p['drive_minutes']:.1f} min), {covers}{' (partial)' if p['partial'] else ''}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approve or reject transfer proposals.")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="proposals by status")
    listing.add_argument("--status", default="proposed", help="proposed, approved, rejected, stale or all")
    sub.add_parser("show", help="one proposal and its history").add_argument("id")
    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("--as", dest="approver", required=True, help="your address, as listed in actions/approvers.yml")
        if name == "reject":
            p.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            rows = shadow.list_proposals(None if args.status == "all" else args.status)
            for p in rows:
                print(_line(p))
            print(f"{len(rows)} proposals ({args.status})")
        elif args.command == "show":
            p = _get(args.id)
            print(_line(p))
            print(f"  versions: contract v{p['contract_version']}, metrics {p['metric_versions']}")
            if p["decided_by"]:
                print(f"  {p['status']} by {p['decided_by']} at {p['decided_at']}"
                      f"{': ' + p['decision_reason'] if p['decision_reason'] else ''}")
            if p["erp_request_no"]:
                print(f"  ERP request: {p['erp_request_no']}")
            for e in shadow.history(args.id):
                print(f"  {e['logged_at']}  {e['event']:<12} {e['actor']}{'  ' + e['detail'] if e['detail'] else ''}")
        elif args.command == "approve":
            result = approve(args.id, args.approver)
            request = result["erp_request"]
            note = " (already approved)" if result["already_approved"] else ""
            print(f"Approved {args.id}{note}. ERP request {request['request_no']}: {request['qty']} {request['uom']} "
                  f"of {request['item_no']} from {request['from_store']} to {request['to_store']}, "
                  f"lots with at least {request['min_days_to_expiry']} days left.")
        else:
            reject(args.id, args.approver, args.reason)
            print(f"Rejected {args.id}: {args.reason.strip()}")
    except Refusal as e:
        print(f"Refused: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
