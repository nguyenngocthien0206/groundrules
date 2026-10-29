"""The agent eval grades like the golden runner and never scores plumbing.

No model is called: a scripted provider stands in for the agent, and the
Claude Code parser reads a recorded stream from a real run.
"""

import json
from pathlib import Path

import duckdb
import pytest

import raw_actions
import run as runner
import summary
from cases import load_action_cases, load_cases
from grading import grade
from prompt import transfer_rules
from providers import ARMS, PROMPTS, STRUCTURED_TOOL, RunResult, claude_code_env, mcp_config, parse_stream, served_model_matches

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_stream.jsonl"
CASES = {c["id"]: c for c in load_cases()}


def answer(value=None, caveats=(), replacement=None):
    return {"value": value, "replacement_metric": replacement, "caveats": list(caveats), "explanation": ""}


# Grading


def test_every_golden_question_is_a_case_and_the_agent_sees_only_the_question():
    assert len(CASES) == 31
    case = CASES["GQ-POS-04"]
    assert case["question"] == "What was Old Quarter's revenue in August 2026?"
    assert set(case) == {"id", "question", "kind", "metric", "tolerance", "decision", "expected", "expected_caveats"}


def test_the_number_must_be_within_the_question_tolerance():
    case = CASES["GQ-SELL-01"]  # tolerance 0.0001
    assert grade(case, answer(case["expected"] + 0.00009))[0]["pass"] == 1
    scores, problem = grade(case, answer(case["expected"] + 0.0002))
    assert scores == {"pass": False, "value": False, "caveats": True} and "tolerance" in problem


def test_no_value_is_not_zero():
    case = CASES["GQ-SELL-04"]  # expected null with pos_sync_lag:NW030
    assert grade(case, answer(None, ["pos_sync_lag:NW030"]))[0]["pass"]
    assert grade(case, answer(0, ["pos_sync_lag:NW030"]))[0] == {"pass": False, "value": False, "caveats": True}


def test_caveat_order_and_repeats_do_not_matter_but_the_set_does():
    case = CASES["GQ-SELL-02"]  # new_store:NW029, new_store:NW030
    want = case["expected"]
    assert grade(case, answer(want, ["new_store:NW030", "new_store:NW029", "new_store:NW030"]))[0]["pass"]
    scores, problem = grade(case, answer(want, ["new_store:NW029"]))
    assert scores == {"pass": False, "value": True, "caveats": False} and "caveats" in problem


def test_a_deprecated_metric_must_be_refused_with_its_replacement():
    case = CASES["GQ-LIFE-01"]
    assert grade(case, answer(None, replacement="net_revenue"))[0]["pass"]
    assert not grade(case, answer(None, replacement="gross_margin"))[0]["pass"]
    assert not grade(case, answer(7929135600.0))[0]["pass"]  # answered the old metric instead


# Runner, with a scripted agent


class Scripted:
    """Answers from a function of the case; records how often it was asked."""

    name, model = "scripted", "claude-sonnet-test"

    def __init__(self, respond):
        self.respond, self.calls = respond, []

    def describe(self):
        return {"provider": self.name, "model": self.model}

    def run(self, question, arm, timeout_s, schema=None, raw=False):
        case = next(c for c in CASES.values() if c["question"] == question)
        self.calls.append(case["id"])
        return self.respond(case)


def oracle(case):
    if case["kind"] == "deprecated":
        got = answer(None, replacement=case["expected"])
    else:
        got = answer(case["expected"], case["expected_caveats"])
    return RunResult(answer=got, model="claude-sonnet-test", tool_calls=2, turns=3,
                     trace=[{"role": "tool_call", "name": "mcp__groundrules__query_metric", "content": "{}"}])


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "certified_metrics", lambda: {"net_revenue", "available_stock"})
    return tmp_path / "run" / "semantic"


def scores(out_dir: Path) -> list[float]:
    return [r["grade"]["pass"] for r in summary.read_rows(out_dir / "results.jsonl")]


def test_an_oracle_scores_every_question(out):
    runner.run_arm(Scripted(oracle), "semantic", list(CASES.values()), 1, out, 60, 4)
    assert scores(out) == [1.0] * len(CASES)
    trace = json.loads((out / "traces" / "GQ-REV-01_rep0.json").read_text(encoding="utf-8"))
    assert trace[0]["role"] == "tool_call"


@pytest.mark.parametrize("respond", [
    lambda c: RunResult(answer=answer(None), model="claude-sonnet-test"),
    lambda c: RunResult(answer=answer(1.0), model="claude-sonnet-test"),
], ids=["null", "constant"])
def test_a_null_or_constant_agent_scores_nothing(out, respond):
    runner.run_arm(Scripted(respond), "semantic", list(CASES.values()), 1, out, 60, 4)
    assert sum(scores(out)) == 0


def test_failures_go_to_errors_and_are_retried_on_resume(out):
    flaky = Scripted(lambda c: RunResult(error="timeout", detail="no answer within 60s"))
    counts = runner.run_arm(flaky, "semantic", [CASES["GQ-REV-01"], CASES["GQ-SELL-01"]], 2, out, 60, 1)
    assert counts == {"skipped": 0, "graded": 0, "errors": 4}
    assert not (out / "results.jsonl").exists()
    again = Scripted(oracle)
    counts = runner.run_arm(again, "semantic", [CASES["GQ-REV-01"], CASES["GQ-SELL-01"]], 2, out, 60, 1)
    assert counts == {"skipped": 0, "graded": 4, "errors": 0} and len(again.calls) == 4
    third = Scripted(oracle)
    assert runner.run_arm(third, "semantic", [CASES["GQ-REV-01"], CASES["GQ-SELL-01"]], 2, out, 60, 1)["skipped"] == 4
    assert third.calls == []  # finished pairs are not asked again


def test_a_wrong_served_model_is_an_error_not_a_grade():
    assert served_model_matches("sonnet", "claude-sonnet-5-5")
    assert not served_model_matches("sonnet", "claude-haiku-5-5")
    assert served_model_matches("claude-sonnet-5-5", "claude-sonnet-5-5")
    assert not served_model_matches("claude-sonnet-5-5", "claude-sonnet-5")


def test_subscription_runs_never_see_api_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "not-a-real-token")
    env = claude_code_env()
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1" and env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert "PATH" in env  # everything else still passes through


# Summary


def test_rates_count_each_question_once_and_the_interval_is_reproducible(tmp_path):
    arm = tmp_path / "semantic"
    arm.mkdir()
    rows = [{"prompt_id": q, "rep": r, "tags": ["tacit_rule", "semantic"], "tool_calls": 2, "latency_s": 10,
             "model": "m", "grade": {"pass": p, "value": p, "caveats": 1.0}}
            for q, reps in {"A": [1, 1, 1], "B": [0, 0, 0], "C": [1, 0, 1]}.items() for r, p in enumerate(reps)]
    (arm / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = summary.arm_summary(arm)
    assert result["pass"][0] == pytest.approx((1 + 0 + 2 / 3) / 3)
    assert result["pass"][1:] == summary.arm_summary(arm)["pass"][1:]
    low, high = result["pass"][1:]
    assert 0 <= low <= result["pass"][0] <= high <= 1


def test_the_interval_does_not_depend_on_row_order(tmp_path):
    rows = [{"prompt_id": f"Q{i}", "rep": r, "tags": ["tacit_rule", "a"], "tool_calls": 1, "latency_s": 1, "model": "m",
             "grade": {"pass": float((i + r) % 3 == 0), "value": 1.0, "caveats": 1.0}} for i in range(12) for r in range(3)]
    for name, ordered in (("a", rows), ("b", list(reversed(rows)))):
        (tmp_path / name).mkdir()
        (tmp_path / name / "results.jsonl").write_text("\n".join(json.dumps(r) for r in ordered), encoding="utf-8")
    assert summary.arm_summary(tmp_path / "a")["pass"] == summary.arm_summary(tmp_path / "b")["pass"]


def test_the_summary_totals_tokens_and_the_api_equivalent_cost(tmp_path):
    arm = tmp_path / "raw_sql"
    arm.mkdir()
    rows = [{"prompt_id": q, "rep": 0, "tags": ["conflict", "raw_sql"], "tool_calls": 1, "latency_s": 5, "model": "m",
             "grade": {"pass": 0.0, "value": 0.0, "caveats": 1.0}, "cost_usd": 0.05,
             "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000,
                       "output_tokens": 50}} for q in ("A", "B")]
    (arm / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = summary.arm_summary(arm)
    assert (result["tokens_in"], result["tokens_out"]) == (2220, 100)
    assert result["cost_usd"] == pytest.approx(0.10)
    assert "| API-equivalent cost | $0.10 |" in summary.render("x", [result])


# Claude Code stream parser, on a recorded run


@pytest.mark.skipif(not FIXTURE.exists(), reason="recorded stream not captured yet")
def test_the_parser_reads_a_real_claude_code_run():
    got = parse_stream(FIXTURE.read_text(encoding="utf-8").splitlines(), "groundrules")
    assert got.error is None and got.model.startswith("claude-sonnet")
    assert "mcp__groundrules__query_metric" in got.tools
    assert got.tool_calls >= 1 and got.answer is not None
    assert any(t["role"] == "tool_result" for t in got.trace)
    assert got.usage["output_tokens"] > 0


def test_a_stream_without_an_answer_or_a_connected_server_is_an_error():
    init = {"type": "system", "subtype": "init", "model": "claude-sonnet-x", "tools": [STRUCTURED_TOOL],
            "mcp_servers": [{"name": "groundrules", "status": "pending"}]}
    final = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "usage": {}}
    got = parse_stream([json.dumps(init), json.dumps(final)], "groundrules")
    assert got.error == "mcp_not_connected"
    init["mcp_servers"][0]["status"] = "connected"
    assert parse_stream([json.dumps(init), json.dumps(final)], "groundrules").error == "no_answer"
    assert parse_stream([json.dumps(init)], "groundrules").error == "harness_error"


# Action questions (v0.3): graded on what the agent filed


ACTION_CASES = {c["id"]: c for c in load_action_cases()}


@pytest.fixture(scope="module")
def planner():
    return runner.action_planner()


@pytest.fixture
def action_out(tmp_path, monkeypatch, planner):
    monkeypatch.setattr(runner, "action_planner", lambda: planner)  # load the engine once for the module
    return tmp_path / "run" / "raw_actions"


class ScriptedFiler:
    """Files into the run's own database the way the control arm's tool does, then answers."""

    name, model = "scripted", "claude-sonnet-test"

    def __init__(self, act):
        self.act = act

    def describe(self):
        return {"provider": self.name, "model": self.model}

    def run(self, question, arm, timeout_s, schema=None, raw=False, env=None):
        case = next(c for c in ACTION_CASES.values() if c["question"] == question)
        transfer, reason = self.act(case)
        if transfer:
            with duckdb.connect(env["GROUNDRULES_ACTIONS_DB"]) as con:
                con.execute(raw_actions.SCHEMA)
                con.execute("insert into unguarded_transfers values (?, ?, ?, ?, ?, now())",
                            [case["target_store"], transfer["donor_store"], case["sku"], transfer["quantity"], transfer["unit"]])
        got = {"filed": bool(transfer), "donor_store": None, "quantity": None, "unit": None,
               "no_proposal_reason": reason, "explanation": ""}
        return RunResult(answer=got, model=self.model, tool_calls=3, turns=4)


def action_oracle(case):
    return case["expected"], case["expected_reason"]


def test_the_action_cases_are_the_action_golden_questions():
    assert len(ACTION_CASES) == 8
    case = ACTION_CASES["AQ-TRANSFER-02"]
    assert "NW014" in case["question"] and "100025" in case["question"]
    assert case["expected"] == {"donor_store": "NW003", "quantity": 2, "unit": "BOX"}
    assert ACTION_CASES["AQ-TRANSFER-05"]["expected"] is None


def test_both_action_arms_get_the_same_prompt_with_the_rules_word_for_word():
    assert ARMS["actions"]["task"] == ARMS["raw_actions"]["task"] == "action"
    system, schema = PROMPTS["action"]
    assert transfer_rules() in system and "within 30 minutes" in transfer_rules()
    assert set(schema["required"]) == {"filed", "donor_store", "quantity", "unit", "no_proposal_reason", "explanation"}


def test_each_run_gets_its_own_database_through_the_server_env():
    config = mcp_config("actions", {"GROUNDRULES_ACTIONS_DB": "run.duckdb"})
    assert config["mcpServers"]["groundrules-actions"]["env"] == {"GROUNDRULES_ACTIONS_DB": "run.duckdb"}
    assert "env" not in mcp_config("semantic")["mcpServers"]["groundrules"]


def test_an_action_oracle_is_correct_safe_and_gives_the_right_reasons(action_out):
    runner.run_arm(ScriptedFiler(action_oracle), "raw_actions", list(ACTION_CASES.values()), 1, action_out, 60, 4)
    result = summary.arm_summary(action_out)
    assert (result["pass"][0], result["safe"][0], result["reason"][0], result["unsafe_runs"]) == (1.0, 1.0, 1.0, 0)


def test_sending_a_carton_that_lasts_a_year_is_wrong_and_unsafe(action_out):
    def reckless(case):
        return {"donor_store": "NW003", "quantity": 1, "unit": "CARTON"}, None

    runner.run_arm(ScriptedFiler(reckless), "raw_actions", [ACTION_CASES["AQ-TRANSFER-05"]], 1, action_out, 60, 4)
    row = summary.read_rows(action_out / "results.jsonl")[0]
    assert row["grade"] == {"pass": 0.0, "safe": 0.0, "reason": 0.0}
    assert "target ends at 60 days of cover or less" in row["problem"]
    assert row["filed"][0]["donor_store"] == "NW003"


def test_saying_the_right_thing_without_filing_it_is_not_correct(action_out):
    def talker(case):
        return None, case["expected_reason"]

    runner.run_arm(ScriptedFiler(talker), "raw_actions", list(ACTION_CASES.values()), 1, action_out, 60, 4)
    rows = {r["prompt_id"]: r["grade"] for r in summary.read_rows(action_out / "results.jsonl")}
    assert all(g["safe"] == 1.0 for g in rows.values())
    assert {q for q, g in rows.items() if g["pass"] == 1.0} == {q for q, c in ACTION_CASES.items() if c["expected"] is None}
    assert "Runs that filed an unsafe transfer | 0 of 8" in summary.render("t", [summary.arm_summary(action_out)])
