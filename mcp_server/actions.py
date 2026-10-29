"""Actions for AI agents, over MCP: propose stock transfers between stores.

Usage: python mcp_server/actions.py   (or `make mcp-server-actions`); speaks MCP over stdio.

The one server here that writes, and it writes only proposals, into the
shadow table (mcp_server/shadow.py), never into the ERP. A person in supply
chain approves each one (step 18). The rules come from the action contract
actions/propose_transfer.yml and its decision record DR-012: the agent picks
a target, the rules pick the donor and the quantity. Ask numbers on the
semantic server (mcp_server/semantic.py); connect both.

The warehouse and MetricFlow load on the first call, after the server has
claimed stdout, so nothing they print can corrupt the protocol.
"""

import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden"), str(ROOT / "governance"), str(ROOT / "mcp_server")]

from mcp.server.mcpserver import Context, MCPServer  # noqa: E402

import shadow  # noqa: E402
import transfers  # noqa: E402

MAX_ITEMS = 25
CONTRACT = transfers.load_contract()

INSTRUCTIONS = f"""\
Stock transfer proposals for Northwind Pharmacy, a 30-store chain, with stock as of {transfers.AS_OF}.
describe_action gives the rules. find_transfer_candidates lists what the rules would propose;
simulate_transfer checks any what-if without saving; propose_transfer files the rules' proposal
for one target store and SKU, to wait for approval by {CONTRACT['approver']}. Store and SKU codes
come from find_values on the metrics server. {" ".join(CONTRACT['agent_notes'].split())}"""

server = MCPServer("groundrules-actions", instructions=INSTRUCTIONS)


@cache
def _sl():
    from semantic_client import SemanticLayer

    return SemanticLayer()


@cache
def _planner() -> transfers.TransferPlanner:
    return transfers.TransferPlanner(_sl(), CONTRACT)


@cache
def _districts() -> dict[str, str]:
    from run_golden import store_sync_state

    return {s["store"]: s["district"] for s in store_sync_state(_sl())}


def _check(**codes: str | None) -> str | None:
    known = {"store": set(_districts()), "sku": set(_planner().units)}
    for name, code in codes.items():
        kind = "sku" if name == "sku" else "store"
        if code is not None and code not in known[kind]:
            return f"unknown {kind} '{code}'; use find_values on the metrics server to look up the code"
    return None


def _guarded(call):
    """Run against the planner, or say why the engine refuses to propose anything."""
    try:
        return call(_planner())
    except transfers.Refused as e:
        return {"error": f"no proposals: {e}"}


@server.tool()
def describe_action() -> dict:
    """The transfer rules: who approves, the decision behind them, the numbers, and what to tell people."""
    from repo import parse_decision

    dr = parse_decision(ROOT / CONTRACT["decision"])
    return {
        "action": CONTRACT["action"],
        "label": CONTRACT["label"],
        "version": CONTRACT["version"],
        "status": CONTRACT["status"],
        "owner": CONTRACT["owner"],
        "approver": CONTRACT["approver"],
        "decision": {"id": dr.id, "title": (dr.front or {}).get("title"), "decision": dr.sections.get("Decision", "").strip()},
        "reads": CONTRACT["reads"]["metrics"],
        "rules": CONTRACT["rules"],
        "agent_notes": " ".join(CONTRACT["agent_notes"].split()),
        "data_as_of": transfers.AS_OF.isoformat(),
    }


@server.tool()
def find_transfer_candidates(store: str | None = None, district: str | None = None, sku: str | None = None) -> dict:
    """What the rules would propose, without saving anything. Filter by target store, the target's
    district code or SKU code. Also lists targets in scope that get no proposal, and why."""
    problem = _check(store=store, sku=sku)
    if problem:
        return {"error": problem}

    def run(plan: transfers.TransferPlanner) -> dict:
        def in_scope(target: str, s: str) -> bool:
            return ((store is None or target == store) and (sku is None or s == sku)
                    and (district is None or _districts().get(target) == district))

        proposals = [p for (t, s), p in sorted(plan.proposals.items()) if in_scope(t, s)]
        missing = [{"store": t, "sku": s, **r} for (t, s), r in sorted(plan.reasons.items()) if in_scope(t, s)]
        result = {"data_as_of": plan.as_of.isoformat(), "saved": False,
                  "proposals": proposals[:MAX_ITEMS], "total_proposals": len(proposals),
                  "targets_without_proposal": missing[:MAX_ITEMS], "total_targets_without_proposal": len(missing)}
        if store and sku and not proposals and not missing:
            result["explanation"] = plan.explain(store, sku)
        return result

    return _guarded(run)


@server.tool()
def simulate_transfer(target_store: str, donor_store: str, sku: str, quantity: int) -> dict:
    """Check a what-if: sending `quantity` purchase units (boxes or cartons) of a SKU from one store
    to another. Returns the covers before and after and every rule passed or failed. Saves nothing."""
    problem = _check(target_store=target_store, donor_store=donor_store, sku=sku)
    if problem:
        return {"error": problem}
    if target_store == donor_store:
        return {"error": "target and donor must be different stores"}
    return _guarded(lambda plan: {"saved": False, **plan.simulate(target_store, donor_store, sku, quantity)})


def _client_name(ctx: Context | None) -> str:
    try:
        return f"mcp:{ctx.session.client_params.client_info.name}"
    except AttributeError:
        return "agent"


@server.tool()
def propose_transfer(target_store: str, sku: str, ctx: Context) -> dict:
    """File the rules' transfer proposal for one target store and SKU. The rules choose the donor and
    the quantity. The proposal waits for approval; nothing moves until a person approves it."""
    problem = _check(target_store=target_store, sku=sku)
    if problem:
        return {"error": problem}

    def run(plan: transfers.TransferPlanner) -> dict:
        found = plan.explain(target_store, sku)
        if "proposal" not in found:
            return {"filed": False, **found}
        row = shadow.record(found["proposal"], CONTRACT["action"], CONTRACT["version"], _client_name(ctx))
        return {"filed": True, "waits_for_approval_by": CONTRACT["approver"], "proposal": row}

    return _guarded(run)


@server.tool()
def list_proposals(status: str = "proposed") -> dict:
    """Proposals filed so far, with their status. status is proposed (the default) or all."""
    rows = shadow.list_proposals(None if status == "all" else status)
    return {"status": status, "proposals": rows[:MAX_ITEMS], "total": len(rows)}


if __name__ == "__main__":
    server.run("stdio")
