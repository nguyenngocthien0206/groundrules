"""The governance lint passes on the repo and fails, clearly, on each kind of break.

Breaks are made on a deep copy of the loaded repo, so no file is touched and
dbt does not run again. Needs `make build` (or `dbt parse`) first.
"""

import copy
from datetime import date

import pytest

import lint
from affected import affected
from repo import load


@pytest.fixture(scope="module")
def repo():
    try:
        return load()
    except FileNotFoundError as e:
        pytest.fail(str(e))


@pytest.fixture
def broken(repo):
    return copy.deepcopy(repo)


def errors(issues, check=None):
    return [i.message for i in issues if i.level == "error" and (check is None or i.check == check)]


def test_the_repo_passes_with_no_errors_and_no_warnings(repo):
    assert lint.run(repo) == []


# The definition-of-done cases (SPEC section 20)


def test_a_metric_without_an_owner_group_fails(broken):
    broken.metrics["net_revenue"].group = None
    assert any("net_revenue has no group" in m for m in errors(lint.check_ownership(broken)))


def test_a_missing_governance_field_fails(broken):
    del broken.metrics["available_stock"].meta["agent_notes"]
    assert any("available_stock is missing governance fields: agent_notes" in m for m in errors(lint.check_ownership(broken)))


def test_a_broken_decision_link_fails(broken):
    broken.metrics["gross_margin"].meta["decision"] = "decisions/DR-099.md"
    assert any("decisions/DR-099.md does not exist" in m for m in errors(lint.check_decisions(broken)))


def test_a_decision_record_that_does_not_list_its_metric_fails(broken):
    broken.decisions["DR-002"].front["linked_metrics"] = []
    assert any("DR-002.md does not list it" in m for m in errors(lint.check_decisions(broken)))


def test_a_decision_record_missing_a_section_fails(broken):
    del broken.decisions["DR-003"].sections["Options considered"]
    assert any("DR-003.md needs the sections" in m for m in errors(lint.check_decisions(broken)))


def test_a_certified_metric_without_golden_questions_fails(broken):
    broken.questions = [q for q in broken.questions if q["metric"] != "days_of_cover"]
    assert any("certified metric days_of_cover has no golden question" in m for m in errors(lint.check_golden_questions(broken)))


def test_a_reserved_question_that_does_not_exist_fails(broken):
    broken.decisions["DR-009"].front["linked_golden_questions"].append("GQ-SELL-99")
    assert any("reserves GQ-SELL-99" in m for m in errors(lint.check_golden_questions(broken)))


def test_a_deprecated_metric_needs_a_certified_replacement(broken):
    broken.metrics["revenue_v1"].meta["replaced_by"] = None
    assert any("revenue_v1 has no replaced_by" in m for m in errors(lint.check_lifecycle(broken)))
    broken.metrics["revenue_v1"].meta["replaced_by"] = "units_sold"
    assert any("points to units_sold, which is not a certified metric" in m for m in errors(lint.check_lifecycle(broken)))


def test_a_mart_without_an_enforced_contract_fails(broken):
    broken.models["fct_sales"]["contract_enforced"] = False
    assert any("model fct_sales backs semantic model fct_sales" in m for m in errors(lint.check_contracts(broken)))


def test_an_em_dash_anywhere_fails(broken):
    broken.text_files["README.md"] = "first line\nnet revenue " + chr(0x2014) + " before VAT\n"
    assert errors(lint.check_em_dash(broken)) == [
        "README.md:2 contains an em dash; use a comma, a colon or a new sentence"
    ]


# Ownership enforced through CODEOWNERS


def test_a_rule_file_reviewed_by_the_wrong_team_fails(broken):
    broken.codeowners.append(("/dbt/models/semantic/metrics_finance.yml", ["@your-org/supply-chain-ops"]))
    assert any("metrics_finance.yml must be owned by @your-org/finance" in m for m in errors(lint.check_codeowners(broken)))


def test_an_extra_team_on_a_rule_file_fails(broken):
    # Any listed owner can approve on GitHub, so an extra team could approve a rule alone.
    broken.codeowners.append(("/dbt/models/semantic/fct_inventory_batch.yml", ["@your-org/supply-chain-ops", "@your-org/finance"]))
    assert any("fct_inventory_batch.yml must be owned by @your-org/supply-chain-ops" in m for m in errors(lint.check_codeowners(broken)))


def test_a_hidden_building_block_is_owned_by_the_teams_that_use_it(repo):
    required = lint.required_rule_owners(repo)
    # The 90-day filter lives in a hidden metric in this file; supply chain uses it.
    assert required["dbt/models/semantic/fct_inventory_batch.yml"] == {"@your-org/supply-chain-ops"}
    # Units sold (supply chain) and the revenue building blocks (finance) share fct_sales.yml.
    assert required["dbt/models/semantic/fct_sales.yml"] == {"@your-org/finance", "@your-org/supply-chain-ops"}


def test_a_decision_record_must_reach_every_metric_owner(broken):
    broken.codeowners.append(("/decisions/DR-004.md", ["@your-org/retail-operations"]))
    assert any("DR-004.md must be owned by" in m for m in errors(lint.check_codeowners(broken)))


def test_a_group_without_a_github_team_fails(broken):
    broken.group_teams["finance"] = None
    assert any("group finance has no config.meta.github_team" in m for m in errors(lint.check_ownership(broken)))


# Power BI: the report displays certified exports and computes nothing


def _measure(repo, table: str, measure: str) -> dict:
    found = next(t for t in repo.powerbi["tables"] if t["name"] == table)
    return next(m for m in found["measures"] if m["name"] == measure)


def test_a_power_bi_measure_that_recomputes_a_metric_fails(broken):
    _measure(broken, "Revenue by district", "Net revenue by district")["expression"] = "SUM('Revenue by district'[net_revenue])"
    assert any("computes `SUM(" in m for m in errors(lint.check_powerbi(broken)))


def test_a_power_bi_measure_with_a_stale_version_fails(broken):
    m = _measure(broken, "Revenue by month", "Net revenue by month")
    m["description"] = m["description"].replace("net_revenue v2", "net_revenue v1")
    assert any("says net_revenue v1, but the certified version is v2" in msg for msg in errors(lint.check_powerbi(broken)))


def test_a_power_bi_measure_without_a_metric_tag_fails(broken):
    _measure(broken, "Stock by store", "Days of cover by store")["description"] = "Days of cover"
    assert any("needs a /// description naming its metric" in m for m in errors(lint.check_powerbi(broken)))


def test_two_measures_with_one_name_fail(broken):
    # Power BI will not even open the project; it says the measure already exists in the model.
    _measure(broken, "Stock by category", "Available stock by category")["name"] = "available stock by store"
    assert any("measure 'available stock by store' is defined in Stock by category, Stock by store" in m
               for m in errors(lint.check_powerbi(broken)))


def test_a_measure_named_like_a_column_fails(broken):
    _measure(broken, "Revenue by month", "Net revenue by month")["name"] = "Caveats"
    assert any("measure 'caveats' has the same name as a column" in m for m in errors(lint.check_powerbi(broken)))


def test_a_summing_metric_column_fails(broken):
    table = next(t for t in broken.powerbi["tables"] if t["name"] == "Stock by store")
    next(c for c in table["columns"] if c["sourceColumn"] == "available_stock")["summarizeBy"] = "sum"
    assert any("must have summarizeBy: none" in m for m in errors(lint.check_powerbi(broken)))


def test_implicit_measures_must_be_discouraged(broken):
    broken.powerbi["model"] = broken.powerbi["model"].replace("\tdiscourageImplicitMeasures\n", "")
    assert any("discourageImplicitMeasures" in m for m in errors(lint.check_powerbi(broken)))


def test_a_saved_query_file_is_owned_by_its_metrics_owners(broken):
    broken.codeowners.append(("/dbt/models/semantic/saved_queries_finance.yml", ["@your-org/data-platform"]))
    assert any("saved_queries_finance.yml must be owned by @your-org/finance" in m for m in errors(lint.check_codeowners(broken)))


# Registry and staleness


def test_an_outdated_registry_fails(broken):
    broken.metrics["net_revenue"].meta["version"] = 3
    assert errors(lint.check_registry(broken)) == ["governance/registry.md is out of date: run `make registry`"]


def test_staleness_is_a_warning_by_default_and_an_error_on_request(repo):
    later = date(2027, 1, 1)  # finance metrics were due on 2026-12-09
    issues = lint.check_staleness(repo, later)
    assert {i.level for i in issues} == {"warning"}
    assert sorted(i.message.split()[1] for i in issues) == ["gross_margin", "net_revenue"]
    assert {i.level for i in lint.check_staleness(repo, later, fail_on_stale=True)} == {"error"}


def test_the_default_date_makes_the_result_independent_of_the_calendar(repo):
    assert lint.SNAPSHOT_DATE == date(2026, 9, 15)
    assert lint.check_staleness(repo, lint.SNAPSHOT_DATE) == []


# Affected metrics and exposures


def test_a_change_to_the_stock_rules_reaches_stock_metrics_and_their_reports(repo):
    metrics, exposures = affected(repo, ["dbt/models/semantic/fct_inventory_batch.yml"])
    assert metrics == ["available_stock", "days_of_cover", "near_expiry_value"]
    assert exposures == ["groundrules_powerbi_report", "ops_weekly_report"]


def test_a_change_upstream_follows_the_lineage(repo):
    metrics, exposures = affected(repo, ["dbt/models/intermediate/int_store_sku_costs.sql"])
    assert {"gross_margin", "net_revenue", "revenue_v1"} <= set(metrics)
    assert exposures == ["finance_dashboard", "groundrules_powerbi_report", "ops_weekly_report", "sales_dashboard"]


def test_a_docs_change_affects_nothing(repo):
    assert affected(repo, ["docs/SPEC.md"]) == ([], [])
