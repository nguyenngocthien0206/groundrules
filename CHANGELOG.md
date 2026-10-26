# Changelog

This file has two parts.

**Definitions** is for the people who read the numbers: managers, analysts,
and the agents that answer for them. It says when the meaning of a certified
number changed, what moves on their dashboards, and where the reasoning is
written down. A code change that moves no number does not belong here.

**Repository** is for the people who adopt or contribute to this repo, in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style.

Both are kept by hand. The governance lint checks that every governed
metric's current version has an entry under Definitions, so a version bump
without a note here fails CI.

## Definitions

Newest first. Each entry: what changed, what moves for readers, the decision
record, the golden questions that pin it, and the pull request.

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

Everything below becomes v0.1.0 when the CI step lands and the release is
tagged.

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
  every metric version has a definitions entry.

#### Changed
- `sell_through_rate` v2 under DR-011, the `new_store` caveat, and lint
  checks for superseded decision records (#9). See Definitions above.
