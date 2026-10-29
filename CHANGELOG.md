# Changelog

This file has two parts.

**Definitions** is for the people who read the numbers: managers, analysts,
and the agents that answer for them. It says when the meaning of a certified
number changed, what moves on their dashboards, and where the reasoning is
written down. A code change that moves no number does not belong here.

**Repository** is for the people who adopt or contribute to this repo, in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style.

Both are kept by hand. The governance lint checks that every governed
metric's and every action's current version has an entry under
Definitions, so a version bump without a note here fails CI.

## Definitions

Newest first. Each entry: what changed, what moves for readers, the decision
record, the golden questions that pin it, and the pull request.

### 2026-10-29: `days_of_cover` v2

- **What changed:** a store that has run out of a SKU it still sells now
  has 0 days of cover. v1 gave no value there: with no stock row left, the
  formula divided an empty stock by the pace. The rule in DR-010 did not
  change; the definition now follows it, so there is no new decision record.
- **What moves:** only store-SKU answers for stock that has run out, from no
  value to 0 (for example NW001, SKU 100125). Store, district, category and
  chain answers, and the dashboard, do not move. A store-SKU that sold
  nothing in the 28 days still has no value.
- **Decision:** [DR-010](decisions/DR-010.md).
- **Golden questions:** GQ-COVER-04 added (NW001, SKU 100125: 0 days).
- **Also:** the action `propose_transfer` now reads `days_of_cover` v2; the
  lint stopped it until the pin was bumped. Its proposals do not change.

### 2026-10-29: action `propose_transfer` v1

- **What changed:** the first action an agent may take. It proposes a stock
  transfer to a store with under 7 days of cover, from the nearest store
  within 30 minutes' drive that has over 60 days and can spare whole boxes
  while keeping 30. It rounds up to bring the target to 14 days, never
  past 60, and a person in supply chain approves each proposal.
- **What moves:** no number changes. At the 2026-09-15 snapshot the rule
  gives 108 proposals, 28 of them partial; the reference that computes them
  is `golden/reference/transfer_candidates.sql`.
- **Decision:** [DR-012](decisions/DR-012.md). Decided by the Head of
  Supply Chain.
- **Reads:** `available_stock` v3 and `days_of_cover` v1. When either moves
  to a new version, the lint fails until supply chain re-checks the rule.
- **Pull request:** #20.

### 2026-10-26: `sell_through_rate` v2

- **What changed:** sell-through has no value when a store's net received
  (received minus transferred out) is zero or negative. A store that opened
  after the period began, and within 7 days after it ended, adds the caveat
  `new_store:<store>`, because its opening stock counts as received while
  its sales cover only part of the period.
- **What moves:** NW030 in September 2026 shows no value instead of -20.43.
  NW030 and NW029 in August 2026 keep their numbers (0 and 0.340) but are now
  flagged as new stores. Chain and category answers that include them carry
  the same flags. No established store's number moved.
- **Decision:** [DR-011](decisions/DR-011.md), superseding
  [DR-009](decisions/DR-009.md). Decided by the Head of Supply Chain.
- **Golden questions:** GQ-SELL-04 and GQ-SELL-05 added; GQ-SELL-02 and
  GQ-SELL-03 now expect `new_store:NW029, new_store:NW030`.
- **Pull request:** #9.

### 2026-09-10: certified definitions published

The first set of certified definitions, as the owners signed them. Versions
before this date are the owners' history and are not recorded here.

| Metric | Version | Owner | Decision records | Golden questions |
| --- | --- | --- | --- | --- |
| `available_stock` | v3 | supply chain | [DR-001](decisions/DR-001.md), [DR-003](decisions/DR-003.md), [DR-004](decisions/DR-004.md), [DR-007](decisions/DR-007.md) | 5 |
| `near_expiry_value` | v1 | supply chain | [DR-001](decisions/DR-001.md) | 3 |
| `days_of_cover` | v1 | supply chain | [DR-010](decisions/DR-010.md), [DR-004](decisions/DR-004.md), [DR-007](decisions/DR-007.md) | 3 |
| `sell_through_rate` | v1 | supply chain | [DR-009](decisions/DR-009.md), [DR-007](decisions/DR-007.md) | 3 |
| `net_revenue` | v2 | finance | [DR-002](decisions/DR-002.md), [DR-004](decisions/DR-004.md), [DR-005](decisions/DR-005.md), [DR-006](decisions/DR-006.md) | 9 |
| `gross_margin` | v1 | finance | [DR-008](decisions/DR-008.md), [DR-006](decisions/DR-006.md) | 3 |

- **Deprecated:** `revenue_v1` v1 (VAT included, returns ignored), certified
  in March 2026, is deprecated in favor of `net_revenue`
  ([DR-005](decisions/DR-005.md)). Asking for it returns a pointer to
  `net_revenue` instead of a number.
- **What moves:** for anyone still reading the legacy dashboards, August
  2026 revenue is 7,373,442,763 VND certified, against 7,387,021,279
  (finance dashboard), 7,442,338,602 (store sales dashboard) and
  7,855,865,056 (operations weekly report). `make demo-conflict` shows each
  gap and the record that settled it.

## Repository

### [Unreleased]

#### Added
- A logistics provider's route table (`logistics/store_routes.csv`): road
  distance and drive time between stores over an invented city with a
  river, staged and modelled as `fct_store_routes`. Existing extracts and
  every golden value are unchanged.
- Action contracts (`actions/`): `propose_transfer` v1 with its rules,
  owner, approver and the metric versions it reads, and DR-012 explaining
  them. The governance lint checks each contract (owner and approver
  groups, an accepted decision, certified metrics at their current
  version, consistent rules, CODEOWNERS, a changelog entry) and the
  registry lists it. An independent reference computes the expected
  proposals from the raw extracts.
- Transfer proposals for agents (`mcp_server/actions.py`, `make
  mcp-server-actions`): find what the rules propose, simulate any what-if,
  and file the rules' proposal for a target store and SKU into a shadow
  table in its own file (`var/actions.duckdb`). The engine
  (`mcp_server/transfers.py`) reads the certified metrics at the versions
  the contract pins, refuses when they differ, and proposes exactly what
  the raw reference does (108 proposals at the snapshot). Nothing reaches
  the ERP yet.
- Approval and write-back (`mcp_server/approvals.py`, `make proposals`,
  `make approve`, `make reject`): someone listed in `actions/approvers.yml`
  (owned by supply chain, checked by the lint) approves a proposal as it is
  or rejects it with a reason, never on what they filed. Approval is
  refused and the proposal marked stale when a metric or the contract has
  moved to a new version, or the rules no longer give the same donor and
  quantity. An approved proposal becomes one transfer request in a
  stand-in ERP (`var/erp.duckdb`), however often approval runs, even after
  a crash halfway. An append-only audit log records every event with who,
  when and the versions.

#### Changed
- `days_of_cover` v2: a store that has run out has 0 days of cover instead
  of no value. GQ-COVER-04 pins it; the transfer action reads v2.
- `gross_margin`'s agent note now makes the VND amount the default and a
  margin rate the exception, after it caused the governed arm's one miss
  in the v0.2.0 eval. The number does not change, so the version stays.
  The three margin questions, rerun three times each, came back right 9
  of 9 (`agent_eval/results/followup-margin/`).

### [0.2.0] - 2026-10-27

Agent-ready: the certified definitions can be used by AI agents, and the
gain is measured.

#### Added
- MCP server for agents (`mcp_server/semantic.py`): list, describe and query
  certified metrics, resolve names to codes, refuse deprecated metrics with
  their replacement, and carry the same caveats as the golden questions.
  A raw SQL server is the control arm for the agent eval; it is read-only
  and cannot reach files or the network (#14, #15).
- Agent eval (`agent_eval/`): the golden questions through an agent on
  either server, graded with the golden runner's own check, with resume,
  traces, failure classes and bootstrap intervals. Runs on Claude Code
  headless; a Claude API provider is included (#15).
- Agent eval results (`agent_eval/results/v0.2.0/`): on the 30 golden
  questions, three times each with Sonnet 5.5, the governed MCP server
  gave 99% correct answers (95% interval 97% to 100%) and raw SQL over
  the same tables 8% (0% to 18%). Every answer and its trace is included (#16).

#### Changed
- MetricFlow readers open the DuckDB warehouse read-only, so several
  processes can read at once; `dbt build` still writes (#14).

### [0.1.0] - 2026-10-26

The first release: the whole loop runs on a laptop with no cloud account,
and every check runs in CI on every pull request.

#### Added
- Synthetic source extracts for a fictional pharmacy chain: 30 stores, 150
  SKUs, six months of ERP, two POS vendors and returns, messy on purpose
  (#1).
- dbt project on DuckDB: staging, intermediate and marts with enforced
  contracts, unit tests, data tests and source freshness (#2).
- Semantic layer in dbt's YAML spec with MetricFlow: six certified metrics,
  one deprecated, hidden building blocks, owners as dbt groups (#3).
- Decision records DR-001 to DR-010 with a template and an index (#4).
- Golden questions with an independent SQL reference over the raw extracts,
  frozen expected values per domain, and a runner with JUnit output (#5).
- Governance lint, metric registry, `make affected`, CODEOWNERS and a pull
  request template (#6).
- Demos: conflicting dashboards and a silent drift caught by golden
  questions (#7).
- Optional Power BI report on certified saved query exports, with a lint
  check on the Power BI files (#8).
- Playbook and adoption guide, with a test that keeps their links and
  commands true (#10).
- README, this changelog, the Apache-2.0 license, and a lint check that
  every metric version has a definitions entry (#11).
- CI on GitHub Actions: build, lint as of today, registry check, golden
  questions, tests, both demos and the dbt v2 parser on every pull request,
  affected metrics in the job summary, and a weekly run that fails on
  overdue recertification (#12).

#### Changed
- `sell_through_rate` v2 under DR-011, the `new_store` caveat, and lint
  checks for superseded decision records (#9). See Definitions above.
