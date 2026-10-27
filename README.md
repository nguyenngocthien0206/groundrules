# Groundrules

[![governance](https://github.com/nguyenngocthien0206/groundrules/actions/workflows/governance.yml/badge.svg)](https://github.com/nguyenngocthien0206/groundrules/actions/workflows/governance.yml)

**Write down the rules your senior analyst never did, so your AI agent can
follow them.** Semantic models, decision records, and golden questions in
CI, built on dbt.

## The problem
Every company runs on rules nobody wrote down. "Available stock" leaves out
batches that expire within 90 days; "revenue" is before VAT and counts a
refund in the month it comes back. People get these right because they ask
a senior analyst, who knows. An AI agent answering the same question has no
analyst in the loop, so it picks whichever definition it finds first, and
it sounds just as confident either way. In this repo, four reasonable ways
of answering "what was our revenue in August?" give 7,387,021,279,
7,442,338,602, 7,855,865,056 and 7,373,442,763 VND. Only the last one is
the number the business agreed on, and before you can hand that question
to an agent, the agreement has to live somewhere a machine can read and a
person can review.

## What you get
Four homes for the knowledge that used to live in one person's head:

| | Where | What it holds |
| --- | --- | --- |
| **What** | [`dbt/models/semantic/`](dbt/models/semantic/) | each metric's rule, written once as a dbt semantic model (MetricFlow), with its owner, version and status |
| **Why** | [`decisions/`](decisions/) | a decision record for every rule: who decided, what else was considered, one case worked out by hand |
| **Proof** | [`golden/`](golden/) | real business questions with signed-off answers, checked against an independent computation on every pull request |
| **Ownership** | [`.github/CODEOWNERS`](.github/CODEOWNERS), [`governance/`](governance/) | the owning team must approve any change to its rules; a lint fails when a metric has no owner, no record or no test |

Nothing here is a new engine or a new standard. It is dbt, MetricFlow and
Git, used so that a definition cannot change without its owner knowing and
its tests noticing.

## Quickstart
You need Python 3.11 or later, [uv](https://docs.astral.sh/uv/) and `make`
(on Windows, use WSL or Git Bash). No cloud account: everything runs on
DuckDB on your laptop.

```bash
make setup    # install pinned dependencies
make data     # generate the synthetic source extracts
make build    # dbt build: staging, marts, unit tests, data tests, freshness
make test     # governance lint, golden questions, dashboard export, pytest
```

On a fresh clone the four commands take about 5 minutes on a Windows
laptop, plus the one-time download of dependencies.

## Demo 1: three dashboards, three revenue numbers
```
$ make demo-conflict
What was our revenue in August 2026? Four answers:

  Finance monthly dashboard          7,387,021,279 VND        +13,578,516   refunds put back on the month of the sale (DR-002)
  Store sales dashboard              7,442,338,602 VND        +68,895,839   returns left out (DR-002)
  Operations weekly report           7,855,865,056 VND       +482,422,293   till amounts, VAT included (DR-006)
  net_revenue (certified, v2)        7,373,442,763 VND                      the one answer

Settled by DR-002: Returns count in the month they come back, not the month of the sale.
```

Each legacy dashboard (in [`legacy/`](legacy/)) was a reasonable choice by
a reasonable team. The demo names the one rule behind each gap and the
record that settled it.

## Demo 2: a silent rule change, caught
```
$ make demo-drift
Silent change in dbt/models/semantic/fct_inventory_batch.yml (no decision record, no golden question touched):
   - filter: "{{ Dimension('batch__days_to_expiry') }} >= 90"
   + filter: "{{ Dimension('batch__days_to_expiry') }} >= 60"
1. Governance lint: 0 errors. Owner, version, decision link and golden questions are all still in place, so nothing looks wrong.
2. Affected: available_stock, days_of_cover, near_expiry_value; dashboards: groundrules_powerbi_report, ops_weekly_report.
3. Golden questions: 4 fail.
   GQ-STOCK-01: How many bottles of the 70ml saline nasal spray (100075) can NW001 sell today?
      expected 48.0000, got 49.0000 (tolerance 0)
      Why: ... Only batches with at least 90 days left count, so 48 are available; the rejected 60-day rule would say 49.
      Decision: decisions/DR-001.md
```

Every formal check passes, because the change is well formed. Only a test
that knows what the answer should be catches that the meaning changed. The
demo restores the file afterwards, even if a step fails.

## Demo 3 (optional, Windows): a BI tool that cannot redefine a metric
`make dashboard-data` exports dbt saved queries to Parquet; the Power BI
project in [`dashboards/`](dashboards/) only displays them. Open
`dashboards/groundrules.pbip` in Power BI Desktop, set the `ExportFolder`
parameter to the full path of `dashboards/exports`, and refresh. The lint
reads the Power BI files and fails on any measure that computes instead of
displaying. See [BI tools](adoption/bi-tools.md) for the pattern and what
it took to make it hold.

## An agent, with and without the rules
The same AI agent (Claude Sonnet 5.5) answered all 30 golden questions,
three times each, two ways: through the governed MCP server in
[`mcp_server/`](mcp_server/), and with read-only SQL over the same tables.
The golden runner's own check graded every answer.

| | Raw SQL over the tables | Governed MCP server |
| --- | --- | --- |
| Correct (number and caveats) | **8%** (95% interval 0% to 18%) | **99%** (97% to 100%) |
| Right number | 13% (3% to 27%) | 99% (97% to 100%) |
| Right caveats | 52% (36% to 70%) | 100% |
| Median tool calls | 5 | 2.5 |

With only the tables, the agent counted a bottle that expires in 71 days,
left returns out of revenue, answered a margin as a percentage, invented its
own sell-through formula, and answered a deprecated metric
instead of refusing it. Each mistake is a rule a decision record settles.
The governed agent's one miss in 90 answers came from its own instructions,
not the data, and is written up with the results.

Every answer, its tool calls and its grade are in
[`agent_eval/results/v0.2.0/`](agent_eval/results/v0.2.0/summary.md).
`make agent-eval` reruns it; see [Agents](adoption/agents.md).

## The example company
Northwind Pharmacy is fictional: a chain of 30 pharmacies in five invented
districts, with 150 products and six months of data. Its extracts look like
real ones: an ERP with codes and `YYYYMMDD` dates, two POS vendors with
different formats and time zones, upload retries, returns that arrive weeks
late, two new stores whose sync runs behind. Every name and number is
generated from a fixed seed.

[`governance/registry.md`](governance/registry.md) lists the certified
metrics, their owners, versions, decision records and when each is due for
review. [`CHANGELOG.md`](CHANGELOG.md) says when a number's meaning
changed.

## Repo map
```
dbt/                the dbt project: staging, marts, semantic layer, owners (groups), exposures
decisions/          decision records: the why behind every rule
golden/             golden questions, the independent reference, the runner
governance/         lint, registry, affected metrics
dashboards/         optional Power BI report on certified exports
mcp_server/         MCP servers for agents: governed access, and raw SQL as the eval's control arm
agent_eval/         the golden questions through an agent, graded; results/ holds the evidence
legacy/, demos/     the conflicting dashboards and the two demos
example/            the synthetic data generator
playbook/           how a team runs this week to week
adoption/           how to bring it into your company
docs/               the spec and build log
```

## Adopting it
- [Adoption guide](adoption/): a 30-day plan for your first ten numbers,
  what to copy into an existing dbt project, what changes on Snowflake,
  BigQuery, Databricks or Postgres, and what it costs (mostly business
  experts' hours, not tooling).
- [Playbook](playbook/): running a definition session, ownership, turning
  analysts' answers into golden questions, changing a rule, handling a
  failed golden question, recertification.

## What this is not
- Not a semantic engine. Definitions are dbt semantic models run by
  MetricFlow, and dbt writes the Open Semantic Interchange document.
- Not a replacement for the dbt platform Semantic Layer or for vendor
  context layers such as Fivetran Context Layer. It is the process and
  governance around definitions, and it plugs into those products.
- Not a hosted product. There is no service to run and no UI beyond the
  BI tool you already own.

## Roadmap
- **v0.1:** the core loop above, plus CI.
- **v0.2, agent-ready:** an MCP server that answers only with certified
  metrics and refuses deprecated ones, and an agent eval on the golden
  questions (results above).
- **v0.3, actions (not started):** one action an agent may propose, with
  preconditions on certified metrics, a simulation, an approval step and an
  audit log of the metric versions used.

## License
[Apache-2.0](LICENSE).
