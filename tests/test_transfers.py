"""Transfer proposals: the certified metrics give what the raw reference gives, and only proposals are written.

The engine reads the semantic layer and the marts; the reference reads the
raw extracts. They are written apart and must agree. Needs `make build`.
The shadow table goes to a temp folder.
"""

import asyncio
import copy
import json
import os
import sys

import duckdb
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

import shadow
import transfers
from reference import Reference
from repo import ROOT
from semantic_client import SemanticLayer


@pytest.fixture(scope="module")
def sl() -> SemanticLayer:
    return SemanticLayer()


@pytest.fixture(scope="module")
def plan(sl) -> transfers.TransferPlanner:
    return transfers.TransferPlanner(sl)


@pytest.fixture
def shadow_db(tmp_path, monkeypatch):
    path = tmp_path / "actions.duckdb"
    monkeypatch.setenv("GROUNDRULES_ACTIONS_DB", str(path))
    return path


# The engine agrees with the reference


def test_the_engine_proposes_exactly_what_the_reference_does(plan):
    expected = {(p["target"], p["sku"]): p for p in Reference().transfer_candidates(transfers.AS_OF)}
    assert set(plan.proposals) == set(expected) and len(expected) == 108
    for key, want in expected.items():
        got = plan.proposals[key]
        assert (got["donor_store"], got["quantity"], got["unit"], got["base_units"], got["partial"]) == (
            want["donor"], want["quantity"], want["unit"], want["base_units"], want["partial"])
        assert got["drive_minutes"] == pytest.approx(want["drive_minutes"], abs=0.01)
        for field in ("target_cover_before", "target_cover_after", "donor_cover_before", "donor_cover_after"):
            assert got[field] == pytest.approx(want[field], rel=1e-9)
        assert got["metric_versions"] == {"available_stock": 3, "days_of_cover": 2}


@pytest.mark.parametrize(("store", "sku", "reason"), [
    ("NW001", "100125", "one_unit_exceeds_60_days"),  # one carton would last 336 days
    ("NW016", "100035", "donors_already_promised"),   # NW020 was more urgent
    ("NW029", "100001", "excluded:pos_sync_lag"),
    ("NW009", "100056", "not_a_target"),              # a donor, 140 days of cover
])
def test_every_store_sku_without_a_proposal_says_why(plan, store, sku, reason):
    assert plan.explain(store, sku)["reason"] == reason


def test_targets_without_a_proposal_are_counted_by_reason(plan):
    reasons = [r["reason"] for r in plan.reasons.values()]
    assert (reasons.count("no_donor_in_reach"), reasons.count("one_unit_exceeds_60_days"),
            reasons.count("donors_already_promised")) == (66, 35, 2)


# Simulation


def failed(result: dict) -> list[str]:
    return [c["rule"] for c in result["checks"] if not c["passed"]]


def test_a_what_if_on_units_another_target_was_promised_fails_on_that_alone(plan):
    result = plan.simulate("NW022", "NW011", "100146", 1)
    assert failed(result) == ["donor has these units left after the rules' proposals for more urgent targets"]
    assert result["rules_propose"]["proposal"]["donor_store"] == "NW023"


def test_a_what_if_past_60_days_fails_the_cap(plan):
    result = plan.simulate("NW001", "NW003", "100125", 1)
    assert failed(result) == ["target ends at 60 days of cover or less"]
    assert result["target_cover_after"] == pytest.approx(336)


def test_the_rules_own_proposal_passes_every_check(plan):
    result = plan.simulate("NW013", "NW009", "100056", 6)
    assert result["passes"] and result["target_cover_after"] == pytest.approx(16.016, abs=0.001)


# Guards


def test_a_pin_the_semantic_layer_does_not_serve_is_refused(sl):
    contract = copy.deepcopy(transfers.load_contract())
    contract["reads"]["metrics"]["days_of_cover"] = 1
    with pytest.raises(transfers.Refused, match="pins days_of_cover v1, the semantic layer serves v2"):
        transfers.check_versions(sl, contract)


class FakeLayer:
    def __init__(self, cover: float | None):
        self.rows = {"available_stock": 14.0, "days_of_cover": cover, "units_sold_28d": 56}

    def query(self, metrics, group_by, where):
        return [{"store": "NW001", "sku": "100001", metrics[0]: self.rows[metrics[0]]}]


@pytest.mark.parametrize("cover", [9.0, None])
def test_a_cover_that_disagrees_with_stock_and_pace_is_refused(cover):
    planner = object.__new__(transfers.TransferPlanner)
    planner.rules, planner.as_of = transfers.load_contract()["rules"], transfers.AS_OF
    assert planner._positions(FakeLayer(7.0))[("NW001", "100001")].cover == 7.0  # 14 / (56 / 28)
    with pytest.raises(transfers.Refused, match="no longer means what the rules assume"):
        planner._positions(FakeLayer(cover))


# The shadow table


def test_filing_a_proposal_twice_keeps_one_row(plan, shadow_db):
    proposal = plan.explain("NW014", "100025")["proposal"]
    first = shadow.record(proposal, "propose_transfer", 1, "test")
    second = shadow.record(proposal, "propose_transfer", 1, "someone else")
    assert first["proposal_id"] == second["proposal_id"] and first["proposal_id"].startswith("TP-")
    assert (first["already_proposed"], second["already_proposed"]) == (False, True)
    assert second["proposed_by"] == "test"  # the first filing stands
    assert (first["donor_store"], first["quantity"], first["partial"], first["status"]) == ("NW003", 2, True, "proposed")
    assert first["metric_versions"] == {"available_stock": 3, "days_of_cover": 2}
    assert len(shadow.list_proposals()) == 1


def test_the_warehouse_is_never_the_shadow_table(shadow_db):
    from semantic_client import DUCKDB_FILE

    assert shadow.db_path() == shadow_db
    assert shadow.DEFAULT_DB == ROOT / "var" / "actions.duckdb" != DUCKDB_FILE


# Over stdio, the way an agent connects


async def _session(env: dict, calls: list[tuple[str, dict]]) -> tuple[list[str], list[dict]]:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server" / "actions.py")], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        results = []
        for tool, arguments in calls:
            result = await session.call_tool(tool, arguments)
            assert not result.is_error
            results.append(json.loads(result.content[0].text))
        return tools, results


def test_an_agent_files_a_proposal_and_only_the_shadow_table_changes(tmp_path):
    db = tmp_path / "actions.duckdb"
    tools, (none, filed, listed) = asyncio.run(_session({**os.environ, "GROUNDRULES_ACTIONS_DB": str(db)}, [
        ("propose_transfer", {"target_store": "NW001", "sku": "100125"}),
        ("propose_transfer", {"target_store": "NW014", "sku": "100025"}),
        ("list_proposals", {}),
    ]))
    assert tools == ["describe_action", "find_transfer_candidates", "simulate_transfer", "propose_transfer", "list_proposals"]
    assert none["filed"] is False and none["reason"] == "one_unit_exceeds_60_days"
    assert filed["filed"] and filed["waits_for_approval_by"] == "supply_chain_ops"
    assert filed["proposal"]["proposed_by"].startswith("mcp:")
    assert [p["proposal_id"] for p in listed["proposals"]] == [filed["proposal"]["proposal_id"]]
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("select count(*) from transfer_proposals").fetchone() == (1,)
