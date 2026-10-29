"""A person approves or rejects each proposal; only approved ones reach the ERP, once, on record.

Uses the real planner (needs `make build`) and throwaway shadow and ERP files.
"""

import copy

import pytest

import approvals
import erp
import shadow
import transfers
from semantic_client import SemanticLayer

PLANNER = "planner.riverside@example.com"


@pytest.fixture(scope="module")
def plan() -> transfers.TransferPlanner:
    return transfers.TransferPlanner(SemanticLayer())


@pytest.fixture(autouse=True)
def files(tmp_path, monkeypatch):
    monkeypatch.setenv("GROUNDRULES_ACTIONS_DB", str(tmp_path / "actions.duckdb"))
    monkeypatch.setenv("GROUNDRULES_ERP_DB", str(tmp_path / "erp.duckdb"))


def file(plan, target="NW014", sku="100025", by="mcp:test-agent", version=1, **changes) -> str:
    proposal = {**copy.deepcopy(plan.explain(target, sku)["proposal"]), **changes}
    return shadow.record(proposal, "propose_transfer", version, by)["proposal_id"]


def events(pid: str) -> list[str]:
    return [e["event"] for e in shadow.history(pid)]


# Approval writes one request, once


def test_an_approval_writes_one_erp_request_and_the_record(plan):
    pid = file(plan)
    result = approvals.approve(pid, PLANNER, plan)
    request = result["erp_request"]
    assert (request["item_no"], request["from_store"], request["to_store"], request["qty"], request["uom"]) == (
        "100025", "NW003", "NW014", 2, "BOX")
    assert request["min_days_to_expiry"] == 90 and request["status"] == "OPEN" and request["created_by"] == PLANNER
    assert result["proposal"]["status"] == "approved" and result["proposal"]["erp_request_no"] == request["request_no"]
    assert events(pid) == ["proposed", "approved", "erp_written"]


def test_approving_twice_gives_one_request(plan):
    pid = file(plan)
    first = approvals.approve(pid, PLANNER, plan)
    second = approvals.approve(pid, "planner.newtown@example.com", plan)
    assert second["already_approved"] and second["erp_request"] == first["erp_request"]
    assert len(erp.requests()) == 1
    assert events(pid) == ["proposed", "approved", "erp_written"]  # nothing rewritten, nothing added


def test_an_approval_that_stopped_between_the_two_writes_finishes_when_run_again(plan, monkeypatch):
    pid = file(plan)
    decide = shadow.decide

    def crash(*args, **kwargs):
        raise RuntimeError("the process died after the ERP write")

    monkeypatch.setattr(shadow, "decide", crash)
    with pytest.raises(RuntimeError):
        approvals.approve(pid, PLANNER, plan)
    assert len(erp.requests()) == 1 and shadow.get(pid)["status"] == "proposed"
    monkeypatch.setattr(shadow, "decide", decide)
    result = approvals.approve(pid, PLANNER, plan)
    assert len(erp.requests()) == 1 and result["proposal"]["status"] == "approved"
    assert events(pid).count("erp_written") == 1


# Who may decide


def test_only_a_listed_approver_may_decide(plan):
    pid = file(plan)
    with pytest.raises(approvals.Refusal, match="not listed in actions/approvers.yml"):
        approvals.approve(pid, "store.manager@example.com", plan)
    assert events(pid) == ["proposed", "refused"] and erp.requests() == []


def test_nobody_approves_what_they_filed(plan):
    pid = file(plan, by=f"mcp:{PLANNER}")
    with pytest.raises(approvals.Refusal, match="filed this proposal"):
        approvals.approve(pid, PLANNER, plan)
    assert erp.requests() == []


def test_a_rejection_needs_a_reason_and_keeps_it(plan):
    pid = file(plan)
    with pytest.raises(approvals.Refusal, match="needs a reason"):
        approvals.reject(pid, PLANNER, "  ")
    rejected = approvals.reject(pid, PLANNER, "NW003 holds this stock for a clinic order")["proposal"]
    assert (rejected["status"], rejected["decided_by"], rejected["decision_reason"]) == (
        "rejected", PLANNER, "NW003 holds this stock for a clinic order")
    assert events(pid) == ["proposed", "refused", "rejected"]
    with pytest.raises(approvals.Refusal, match="is rejected"):
        approvals.approve(pid, "planner.newtown@example.com", plan)
    assert erp.requests() == []


# Stale proposals are not approved


class MovedPlanner:
    """The rules, run again on changed data, give another quantity."""

    def __init__(self, plan):
        self.plan, self.metric_versions = plan, plan.metric_versions

    def explain(self, store, sku):
        found = copy.deepcopy(self.plan.explain(store, sku))
        found["proposal"]["quantity"] += 1
        return found


@pytest.mark.parametrize(("make", "planner", "why"), [
    (lambda plan: file(plan, metric_versions={"available_stock": 3, "days_of_cover": 1}), None, "the metrics are now"),
    (lambda plan: file(plan, version=0), None, "the contract is now v1"),
    (lambda plan: file(plan), MovedPlanner, "now propose"),
], ids=["metric version", "contract version", "recomputed"])
def test_a_proposal_that_no_longer_stands_is_marked_stale(plan, make, planner, why):
    pid = make(plan)
    with pytest.raises(approvals.Refusal, match="propose again"):
        approvals.approve(pid, PLANNER, planner(plan) if planner else plan)
    stored = shadow.get(pid)
    assert stored["status"] == "stale" and why in stored["decision_reason"]
    assert events(pid) == ["proposed", "stale"] and erp.requests() == []
