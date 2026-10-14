# SPEC: unwritten-rules

## 1. Goal
An open-source reference implementation that a real company can adopt on its existing dbt project and warehouse to make business definitions safe for AI agents.

A data lead should be able to:
1. Clone the repo and see the whole loop working locally in under 10 minutes, with no cloud account.
2. Recognize their own company in the example: messy sources, conflicting dashboards, rules nobody wrote down.
3. Copy the governance pieces (decision records, golden questions, CODEOWNERS, CI, playbook) into their own repo in an afternoon.
4. Point the same project at Snowflake, BigQuery, Databricks or Postgres by changing only `profiles.yml`.

Companion to the Substack article "When the One Asking for Data Is No Longer a Person" (link placeholder: `SUBSTACK_URL`).

## 2. Non-goals
- Not a new semantic engine or standard. Use dbt + MetricFlow for definitions; export or map to Open Semantic Interchange (OSI) where supported.
- Not a hosted product, no web UI.
- No LLM calls in the core demo or default CI. Agent pieces are optional phases.

## 3. Phases
| Phase | Scope | Why it matters to an adopting company |
| --- | --- | --- |
| v0.1 Core | Realistic data, dbt project, semantic models, decision records, golden questions, governance CI, drift and conflict demos, playbook | Works with no AI at all. Pays off for dashboards on day one. |
| v0.2 Agent-ready | MCP server over the semantic layer, agent eval harness on golden questions | Shows how an agent should consume certified definitions and how to measure it. |
| v0.3 Actions | One action contract, shadow table, simulation, approval, idempotent write-back, audit log | Shows the safe path from answers to actions. |

Build v0.1 completely before starting v0.2. Ask me before starting v0.2 or v0.3.

## 4. Repo structure (v0.1)
```
unwritten-rules/
  CLAUDE.md  SPEC.md  PROGRESS.md  README.md  LICENSE (Apache-2.0)  CHANGELOG.md
  Makefile  pyproject.toml
  .github/
    CODEOWNERS
    pull_request_template.md
    workflows/governance.yml
  example/
    generate.py              # synthetic source extracts (CSV / Parquet)
  legacy/                    # three conflicting "existing dashboard" SQL definitions
  dbt/
    dbt_project.yml  profiles.example.yml
    models/staging/          # one model per source, cleaning and dedup
    models/marts/            # fct_inventory_batch, fct_sales, dim_store, dim_sku, fct_transfers
    models/semantic/         # MetricFlow semantic models + metrics, with governance meta
    tests/                   # dbt data tests (singular)
  decisions/                 # DR-001.md ... + TEMPLATE.md
  golden/
    questions/               # golden question YAML files, grouped by domain
    reference/               # independent reference computations
    run_golden.py
  governance/
    lint.py                  # meta checks, DR links, stale certifications
    registry.md              # generated: metric, owner, version, status, DR, last certified
  playbook/
  adoption/
  tests/                     # pytest for runner and lint
```

## 5. Synthetic data that looks real (`example/generate.py`)
A fictional pharmacy retail chain ("Northwind Pharmacy" style invented name, never a real brand). Fixed seed. Fixed snapshot date 2026-09-15. Output as raw extracts, the way they arrive from source systems, not as clean tables.

Sources:
| Source system | Extract | Realistic problems to include |
| --- | --- | --- |
| ERP | stores, skus, batches, transfers | status codes instead of words (`TR`, `DL`, `CX`); a cancelled transfer still present; SKU renamed mid-period |
| POS (two vendors) | sales lines | different column names and date formats per vendor; duplicate lines from a retry; amounts in VND as integers |
| POS sync log | last sync per store | two newly opened stores lagging 3 days behind |
| Returns system | returns | returns arriving weeks after the sale; some returns with no matching sale |

Scale: about 30 stores in 5 districts, 150 SKUs across 6 categories, 6 months of sales. Small enough for DuckDB on a laptop, large enough that wrong rules produce visibly wrong numbers.

The data must make every tacit rule matter: batches under 90 days to expiry, outbound transfers in transit, cancelled transfers, late returns, duplicate POS lines, lagging stores.

## 6. dbt project (`dbt/`)
- Staging: one model per source, rename to a common vocabulary, decode status codes, dedupe POS retries, convert types. Document every column.
- Marts: `dim_store` (with `is_newly_opened`, `last_synced_at`), `dim_sku`, `fct_inventory_batch`, `fct_transfers`, `fct_sales`, `fct_returns`.
- Data tests (generic and singular): uniqueness, not null, accepted values, and a freshness-style test that flags stores whose POS sync lags.
- Data tests check the data is clean. Golden questions check the meaning is right. Keep both and explain the difference in README.
- `profiles.example.yml` with commented blocks for duckdb, snowflake, bigquery, databricks, postgres.

## 7. Semantic layer (`dbt/models/semantic/`)
Use MetricFlow semantic models and metrics. First verify MetricFlow queries run against dbt-duckdb locally (for example with `mf query`). If they do not, tell me before choosing a fallback.

Every metric carries governance fields in `meta`:
```yaml
meta:
  owner: supply_chain_ops        # business owner, a team handle, never a person's name
  data_owner: data_platform
  version: 3
  status: certified              # draft | certified | deprecated
  certified_on: 2026-09-10
  recertify_every_days: 180
  decision: decisions/DR-001.md
  agent_notes: "Use this, never sum qty_on_hand directly."
```

Metrics for v0.1:
| Metric | Rule written down |
| --- | --- |
| `available_stock` | on hand, minus outbound transfers in transit (excluding cancelled), minus batches under 90 days to expiry |
| `near_expiry_value` | value of stock in batches expiring within 90 days |
| `net_revenue` | gross minus discounts minus returns, returns counted in the month of the return |
| `gross_margin` | net revenue minus cost of goods sold |
| `sell_through_rate` | units sold over units received in the period |
| `days_of_cover` | available stock over average daily units sold, last 28 days |

Also include one `deprecated` metric (for example `revenue_v1`) with a pointer to its replacement, to show the lifecycle.

If dbt or MetricFlow provides an OSI export, add `make export-osi`. If not, add a short mapping table in README from MetricFlow fields to OSI concepts.

## 8. Legacy conflict (`legacy/`)
Three SQL files that mimic real dashboards: `finance_dashboard.sql`, `sales_dashboard.sql`, `ops_weekly_report.sql`. Each computes "net revenue" differently (returns by sale month, returns ignored, discounts ignored). `make demo-conflict` runs all three plus the certified metric for the same month and prints the four numbers side by side, with the DR that settled it.

## 9. Decision records (`decisions/`)
`TEMPLATE.md` sections: Context, Decision, Options considered, Decided by (role), Date, Consequences, Linked metrics, Linked golden questions, Supersedes.

v0.1 records:
- DR-001: available stock excludes batches under 90 days to expiry (60 vs 90 considered).
- DR-002: net revenue counts returns in the month of the return (finance vs sales; who broke the tie and why).
- DR-003: cancelled transfers are excluded from in-transit stock.
- DR-004: stores lagging POS sync are included but flagged; answers must carry a caveat.
- DR-005: deprecate `revenue_v1` in favor of `net_revenue`.

## 10. Golden questions (`golden/`)
About 25 questions, grouped by domain, covering four kinds:
| Kind | Example | What it protects |
| --- | --- | --- |
| Tacit rule | Available stock of an item in one district | the 90-day and in-transit rules |
| Conflict | Net revenue for August | the certified definition beats legacy ones |
| Caveat required | Sales yesterday across all stores | answer must flag lagging stores |
| Deprecated | Revenue using `revenue_v1` | must point to the replacement |

Fields: `id`, `question`, `kind`, `metric`, `filters`, `as_of`, `expected`, `tolerance`, `expected_caveats`, `why`, `decision`, `signed_off_by` (role), `signed_off_on`.

Expected values come from `golden/reference/`, written independently from the semantic layer, in plain pandas or SQL directly over source extracts. Freeze results into YAML with a script, and document why in README.

`run_golden.py` queries the semantic layer, compares with tolerance, checks caveats where relevant, prints a table, shows `why` and the DR link on failure, writes a JUnit XML report for CI, and exits non-zero on failure.

## 11. Governance in Git
- `CODEOWNERS`: map each semantic file and DR to a placeholder team (for example `@your-org/supply-chain-ops`), so changing a definition requires the business owner's review. This is how ownership becomes enforceable, not just documented.
- `pull_request_template.md`: which metric changed, linked DR, golden questions added or updated, owner approval.
- `governance/lint.py` fails when: a metric lacks a required `meta` field; a DR link is broken; a certified metric has no golden question; a certification is older than `recertify_every_days` (warning, configurable to fail); a deprecated metric has no replacement.
- `governance/registry.md`: generated table of every metric with owner, version, status, DR and last certified date. This is the page a manager reads.
- `CHANGELOG.md` for definition changes, kept by hand.

## 12. Demos
- `make demo-drift`: change the 90-day threshold to 60 in `available_stock` without touching DR-001 or golden questions; run golden questions; show failures with `why`; restore the file even if a step fails.
- `make demo-conflict`: see section 8.

## 13. Playbook (`playbook/`)
- `running-a-definition-session.md`: attendees, prep, how to break ties, the three outputs of every session (DR, metric change, golden questions).
- `ownership.md`: business owner vs data owner, what each is accountable for, and a RACI table template.
- `from-analyst-answers-to-golden-questions.md`: harvest the questions analysts answer every week; why this is easier than asking them to list their rules.
- `recertification.md`: how often to review, who signs, what happens to stale metrics.

## 14. Adoption guide (`adoption/`)
- `adopt-in-30-days.md`: week 1 pick the 10 numbers leadership looks at most and find their owners; week 2 run definition sessions and write DRs; week 3 encode metrics and golden questions; week 4 turn on CI and CODEOWNERS.
- `existing-dbt-project.md`: how to copy `decisions/`, `golden/`, `governance/` and `.github/` into an existing dbt repo.
- `warehouses.md`: switching to Snowflake, BigQuery, Databricks or Postgres.
- `cost-and-roles.md`: the real cost is business experts' hours, not tooling; who to involve and how much time to budget.

## 15. README
1. The problem, in 5 to 6 sentences, link to `SUBSTACK_URL`
2. What you get: four homes for knowledge (semantic model = what, decisions = why, golden questions = proof, Git = ownership)
3. Quickstart
4. Demo 1: conflicting dashboards. Demo 2: silent drift caught.
5. Adopting it in your company (link to `adoption/`)
6. What this is not
7. Roadmap (v0.2 agents, v0.3 actions)

## 16. v0.2 Agent-ready (do not start without asking)
- `mcp/`: an MCP server exposing `list_metrics`, `describe_metric` (definition, owner, `agent_notes`, DR summary), `query_metric`. It refuses deprecated and draft metrics with a pointer to the certified one.
- `agent_eval/`: runs golden questions through an agent connected to the MCP server, scores accuracy and caveat handling, outputs a report. Pluggable model provider, needs an API key, not in default CI.

## 17. v0.3 Actions (do not start without asking)
One action contract (`propose_transfer`) with preconditions using certified metrics, a shadow table for proposals, a simulation of impact, an approval step, idempotent write-back to a fake ERP table, and an audit log recording the metric versions used.

## 18. Build order (v0.1)
1. Synthetic source extracts
2. dbt staging + marts + data tests
3. Verify MetricFlow on DuckDB, then semantic models and metrics
4. Decision records
5. Reference computations + golden questions + runner
6. Governance lint, registry, CODEOWNERS, PR template
7. Demos (conflict, drift)
8. Playbook + adoption guide
9. README + CHANGELOG
10. CI

Run and verify each step before moving to the next.

## 19. Definition of done (v0.1)
- On a fresh clone: `make setup && make data && make build && make test` passes in under 10 minutes on a laptop.
- `make demo-conflict` prints four different net revenue numbers and names the DR that settled it.
- `make demo-drift` shows golden questions failing for the right reason, then restores everything.
- `make lint` fails with a clear message when an owner is removed, a DR link breaks, or a certified metric has no golden question.
- Switching `profiles.yml` to another warehouse needs no model changes (documented, not tested in CI).
- No real company names or rules, and no em dash character anywhere in the repo.