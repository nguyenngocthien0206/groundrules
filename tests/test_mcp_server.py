"""The MCP servers give agents the certified answers, and only those.

The tool functions are called directly on the real warehouse, then each
server is started once over stdio, the way an agent connects. Needs
`make build` first.
"""

import asyncio
import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

import raw_sql
import semantic
from catalog import load_expected
from repo import ROOT


@pytest.fixture(scope="module")
def expected() -> dict:
    return load_expected()["answers"]


# Governed access


def test_only_governed_metrics_are_listed():
    names = {m["name"]: m["status"] for m in semantic.list_metrics()["metrics"]}
    assert names["net_revenue"] == "certified" and names["revenue_v1"] == "deprecated"
    assert "units_sold" not in names  # a hidden building block
    assert len(names) == 7


def test_a_metric_is_described_with_its_owner_decision_and_caveats():
    d = semantic.describe_metric("sell_through_rate")
    assert d["status"] == "certified" and d["owner_team"] == "@your-org/supply-chain-ops"
    assert d["decision"]["id"] == "DR-011" and "no value" in d["decision"]["decision"].lower()
    assert any(c.startswith("new_store:") for c in d["caveats"])
    assert d["golden_questions"] == 5
    assert not any(c.startswith("new_store:") for c in semantic.describe_metric("net_revenue")["caveats"])
    assert "error" in semantic.describe_metric("units_sold")


def test_the_margin_note_makes_the_amount_the_default():
    # v0.2.0 eval: the old note ("For a margin rate, divide by net_revenue")
    # led one run of GQ-MARGIN-03 to answer a rate the question never asked for.
    note = semantic.describe_metric("gross_margin")["agent_notes"]
    assert "means this amount" in note
    assert "only when the question asks for a rate or a percentage" in note


def test_names_resolve_to_codes():
    assert semantic.find_values("district", "old quarter")["matches"] == [{"district_code": "D02", "district_name": "Old Quarter"}]
    assert semantic.find_values("category", "Vitamins")["matches"][0]["category_code"] == "VITA"
    assert semantic.find_values("store")["total"] == 30


@pytest.mark.parametrize(("question", "args"), [
    ("GQ-SELL-01", {"metric": "sell_through_rate", "store": "NW014", "month": "2026-08"}),
    ("GQ-SELL-04", {"metric": "sell_through_rate", "store": "NW030", "month": "2026-09"}),
    ("GQ-STOCK-01", {"metric": "available_stock", "store": "NW001", "sku": "100075"}),
    ("GQ-POS-04", {"metric": "net_revenue", "district": "D02", "month": "2026-08"}),
])
def test_answers_match_the_golden_questions(expected, question, args):
    got = semantic.query_metric(**args)
    want = expected[question]
    if want["expected"] is None:
        assert got["value"] is None and "note" in got
    else:
        assert got["value"] == pytest.approx(want["expected"], abs=1)
    assert got["caveats"] == list(want["expected_caveats"])


def test_a_store_that_ran_out_has_zero_days_of_cover_not_no_value():
    # days_of_cover v1 gave no value here: no stock row, so empty stock / pace.
    got = semantic.query_metric("days_of_cover", store="NW001", sku="100125")
    assert got["value"] == 0 and got["version"] == 2 and "note" not in got


def test_a_deprecated_metric_is_refused_with_its_replacement():
    got = semantic.query_metric("revenue_v1", month="2026-08")
    assert got["refused"] and got["use_instead"] == "net_revenue" and "value" not in got


def test_a_building_block_is_refused_with_the_certified_list():
    got = semantic.query_metric("units_sold", month="2026-08")
    assert got["refused"] and "net_revenue" in got["certified_metrics"]


@pytest.mark.parametrize(("args", "message"), [
    ({"district": "Old Quarter", "month": "2026-08"}, "use find_values"),
    ({"month": "2026-08", "day": "2026-08-01"}, "at most one period"),
    ({"start": "2026-07-01"}, "start and end go together"),
    ({"month": "August 2026"}, "month must look like YYYY-MM"),
])
def test_bad_filters_are_explained_not_answered(args, message):
    got = semantic.query_metric("net_revenue", **args)
    assert message in got["error"] and "value" not in got


# Raw SQL, the control arm


def test_raw_sql_sees_the_marts_and_their_docs():
    tables = {t["table"]: t["description"] for t in raw_sql.list_tables()["tables"]}
    assert "marts.fct_sales" in tables and all(t.startswith("marts.") for t in tables)
    columns = {c["name"]: c["description"] for c in raw_sql.describe_table("marts.fct_inventory_batch")["columns"]}
    assert columns["days_to_expiry"]  # a neutral fact; the 90-day rule is not in the marts


def test_raw_sql_runs_one_select_and_nothing_else():
    assert raw_sql.run_sql("select count(*) as n from marts.dim_store")["rows"] == [[30]]
    assert "only one SELECT" in raw_sql.run_sql("delete from marts.fct_sales")["error"]
    assert "only one SELECT" in raw_sql.run_sql("select 1; select 2")["error"]
    big = raw_sql.run_sql("select * from marts.fct_sales")
    assert len(big["rows"]) == raw_sql.MAX_ROWS and big["truncated"]


@pytest.mark.parametrize("query", [
    "select content from read_text('pyproject.toml')",
    "select * from read_csv('example/data/erp/stores.csv')",
    "select count(*) from glob('*')",
])
def test_raw_sql_cannot_read_files_on_the_machine(query):
    # A SELECT can call DuckDB's file functions; read-only alone does not stop them.
    assert "Permission Error" in raw_sql.run_sql(query)["error"]


# Over stdio, the way an agent connects


async def _call(script: str, tool: str, arguments: dict) -> tuple[list[str], dict]:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server" / script)])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        result = await session.call_tool(tool, arguments)
        assert not result.is_error
        return tools, json.loads(result.content[0].text)


def test_the_governed_server_answers_over_stdio(expected):
    tools, got = asyncio.run(_call("semantic.py", "query_metric",
                                   {"metric": "sell_through_rate", "store": "NW014", "month": "2026-08"}))
    assert tools == ["list_metrics", "describe_metric", "find_values", "query_metric"]
    assert got["value"] == pytest.approx(expected["GQ-SELL-01"]["expected"], abs=0.0001)


def test_the_raw_sql_server_answers_over_stdio():
    tools, got = asyncio.run(_call("raw_sql.py", "run_sql", {"query": "select count(*) from marts.dim_store"}))
    assert tools == ["list_tables", "describe_table", "run_sql"]
    assert got["rows"] == [[30]]


# The action eval's control arm: raw SQL plus a write tool that checks nothing


def test_the_control_arm_files_whatever_it_is_told(tmp_path, monkeypatch):
    import duckdb
    import raw_actions

    monkeypatch.setenv("GROUNDRULES_ACTIONS_DB", str(tmp_path / "filed.duckdb"))
    # One carton to a store that sells 2 bottles a month: DR-012 says no, this tool does not ask.
    assert raw_actions.file_transfer("NW001", "NW003", "100125", 1, "CARTON") == {"filed": True, "transfer_number": 1}
    with duckdb.connect(str(tmp_path / "filed.duckdb"), read_only=True) as con:
        assert con.execute("select target_store, donor_store, quantity, unit from unguarded_transfers").fetchall() == [
            ("NW001", "NW003", 1, "CARTON")]
    assert "Permission Error" in raw_sql.run_sql("select * from read_csv('example/data/erp/stores.csv')")["error"]


def test_the_control_arm_serves_sql_and_the_write_tool_over_stdio():
    tools, got = asyncio.run(_call("raw_actions.py", "run_sql", {"query": "select count(*) from marts.fct_store_routes"}))
    assert tools == ["list_tables", "describe_table", "run_sql", "file_transfer"]
    assert got["rows"] == [[756]]
