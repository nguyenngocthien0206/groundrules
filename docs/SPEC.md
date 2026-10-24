# SPEC: Groundrules

Repo name: `groundrules`. Tagline for the GitHub description and README header:
"Write down the rules your senior analyst never did, so your AI agent can follow them. Semantic models, decision records, and golden questions in CI, built on dbt."

The name is a deliberate double meaning: "ground rules" are the business rules everyone must follow, and "grounding" is how an AI agent is anchored to trusted definitions.

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
- Not a hosted product, no web UI. The optional Power BI report (section 13) is a file opened in a tool the company already owns.
- No LLM calls in the core demo or default CI. Agent pieces are optional phases.

## 3. Phases
| Phase | Scope | Why it matters to an adopting company |
| --- | --- | --- |
| v0.1 Core | Realistic data, dbt project, semantic models, decision records, golden questions, governance CI, drift and conflict demos, optional Power BI dashboard on certified exports, playbook | Works with no AI at all. Pays off for dashboards on day one. |
| v0.2 Agent-ready | MCP access to the semantic layer (built on `dbt-mcp` where possible), agent eval harness on golden questions | Shows how an agent should consume certified definitions and how to measure it. |
| v0.3 Actions | One action contract, shadow table, simulation, approval, idempotent write-back, audit log | Shows the safe path from answers to actions. |

Build v0.1 completely before starting v0.2. Ask me before starting v0.2 or v0.3.

## 4. Repo structure (v0.1)
```
groundrules/
  README.md  LICENSE (Apache-2.0)  CHANGELOG.md
  Makefile  pyproject.toml           # exact pinned versions
  docs/
    CLAUDE.md  SPEC.md  PROGRESS.md
  .github/
    CODEOWNERS
    pull_request_template.md
    workflows/governance.yml
  example/
    generate.py              # synthetic source extracts (CSV / JSON Lines)
    synth/                   # generator modules: config, master data, simulation, extract writers
  legacy/                    # three conflicting "existing dashboard" SQL definitions
  dbt/
    dbt_project.yml  profiles.yml (local DuckDB)  profiles.example.yml
    macros/                  # portable date parsing, schema naming, small generic tests
    models/staging/          # one model per source, cleaning, dedup, unit tests
    models/intermediate/     # both POS vendors as one, base units, VAT split, returns matched to sales
    models/marts/            # SQL of dims and facts, plus the MetricFlow time spine
    models/semantic/         # one properties file per mart (contract, entities, dimensions, simple
                             # metrics with their rule filters) + metrics.yml + saved queries
    models/groups.yml        # dbt groups = owning teams
    models/exposures.yml     # legacy dashboards and the Power BI report
    tests/                   # dbt data tests (singular)
  decisions/                 # DR-001.md ... + TEMPLATE.md
  golden/
    questions/               # golden question YAML files, grouped by domain
    reference/               # independent reference computations
    run_golden.py
  governance/
    lint.py                  # reads target/manifest.json; meta, DR links, staleness, TMDL, em dash
    registry.md              # generated: metric, owner, version, status, DR, last certified
  dashboards/
    export.py                # runs saved queries through MetricFlow, writes Parquet
    exports/                 # generated Parquet, not committed
    groundrules.pbip         # Power BI project (TMDL model + PBIR report), text files
  playbook/
  adoption/
  tests/                     # pytest for runner, lint, generator checksum, exports
```

## 5. Synthetic data that looks real (`example/generate.py`)
A fictional pharmacy retail chain in Vietnam ("Northwind Pharmacy" style invented name, never a real brand). Fixed seed. Fixed snapshot date 2026-09-15. Output as raw extracts, the way they arrive from source systems, not as clean tables.

Sources:
| Source system | Extract | Realistic problems to include |
| --- | --- | --- |
| ERP | stores | `opened_on` date; two stores opened in the last month |
| ERP | skus | SKU renamed mid-period; VAT rate per SKU; base unit and pack sizes (box, strip, tablet) |
| ERP | batches | `unit_cost` per batch; `received_qty` and `received_at` in boxes; expiry date |
| ERP | transfers | status codes instead of words (`TR`, `DL`, `CX`); a cancelled transfer still present; quantities in boxes |
| POS (two vendors) | sales lines | different column names and date formats per vendor; vendor A stamps UTC, vendor B stamps local time; duplicate lines from a retry; amounts in VND as integers, VAT included; `discount_amount` per line; sold in strips or tablets |
| POS sync log | last sync per store | two newly opened stores lagging 3 days behind |
| Returns system | returns | returns arriving weeks after the sale; some returns with no matching sale |

Scale: about 30 stores in 5 districts, 150 SKUs across 6 categories, 6 months of sales. Small enough for DuckDB on a laptop, large enough that wrong rules produce visibly wrong numbers.

The data must make every tacit rule matter: batches under 90 days to expiry, outbound transfers in transit, cancelled transfers, late returns, duplicate POS lines, lagging stores, VAT in POS prices, mixed units of measure, and sales near midnight that land on a different business day in UTC.

VAT rates and pack sizes are set in the generator and are illustrative only. They are not tax advice and not any real chain's master data.

Reproducibility: golden expected values are frozen from this output, so the generator must produce byte-identical files on every machine. Pin every library version, and keep a checksum test in `tests/` that fails if the output changes.

## 6. dbt project (`dbt/`)
- Staging: one model per source, rename to a common vocabulary, decode status codes, dedupe POS retries, convert types, convert POS timestamps to local business time (Asia/Ho_Chi_Minh), convert quantities to the SKU base unit, split VAT out of POS amounts. Document every column.
- Intermediate: `int_sales_lines` (both vendors in one shape, base units, amounts with and without VAT), `int_return_lines` (base units, before VAT, original sale date when the receipt is found) and `int_store_sku_costs` (weighted average cost per store and SKU, DR-008).
- Marts: `dim_store` (with `opened_on`, `is_newly_opened`, `last_synced_at`, `pos_lag_days`, `is_pos_sync_lagging`), `dim_sku`, `fct_inventory_batch`, `fct_transfers` (with `snapshot_date`), `fct_sales` (with `unit_cost_excl_vat` and `cogs_excl_vat`), `fct_returns`, `fct_goods_received` (stock received from suppliers or by transfer; not "receipts", which already means sales receipts here), and `metricflow_time_spine`.
- The properties of each mart (contract, docs, tests, semantic model) live in `models/semantic/<mart>.yml`, next to its metrics (section 7).
- Marts expose neutral facts, never business thresholds. For example `fct_inventory_batch.days_to_expiry` (computed against the snapshot date), `fct_transfers.transfer_status`, `fct_returns.return_date`. The 90-day rule, the cancelled-transfer exclusion and the return-month rule live in the semantic layer (section 7), so changing them always touches a file that CODEOWNERS protects.
- Marts that feed a certified metric use `contract: enforced` and `access: public`. A column rename then fails the build instead of silently breaking a metric.
- Unit tests (dbt `unit_tests`) for the logic most likely to break quietly: POS retry dedupe, status code decoding, UTC to local business day, unit of measure conversion, VAT split.
- Data tests (generic and singular): uniqueness, not null, accepted values.
- Freshness: `dbt source freshness` with `loaded_at_field` on the POS sources, plus a singular test that flags each store whose POS sync lags.
- Data tests check the data is clean. Golden questions check the meaning is right. Keep both and explain the difference in README.
- `profiles.example.yml` with commented blocks for duckdb, snowflake, bigquery, databricks, postgres.

## 7. Semantic layer (`dbt/models/semantic/`)
Use MetricFlow semantic models and metrics in dbt's latest YAML spec: the semantic model sits on the model (`semantic_model: {enabled: true}`, `agg_time_dimension`), entities and dimensions sit on columns, and simple metrics with direct keys (`agg`, `expr`, `filter`, `non_additive_dimension`) replace measures. Verified on dbt-core 1.12.6 with dbt-metricflow 0.15.0 (MetricFlow 0.213.0) on DuckDB: `mf validate-configs`, `mf query`, saved queries and the Python engine all work. Quirks found and handled are listed in PROGRESS.

Layout: in this spec a semantic model must sit in the same properties file as its model, so each mart's properties live in `models/semantic/<mart>.yml`, together with the simple metrics built on it. Metrics that combine several semantic models live in `models/semantic/metrics.yml`. Every business rule therefore sits in this folder.

Building-block metrics (for example on-hand units, sales before VAT) are `hidden: true`. They feed the certified metrics but do not show in `mf list metrics`, in the OSI document, or to agents.

Use what dbt already provides before adding custom fields:
- Business owner: the metric's dbt `group` (defined in `models/groups.yml`, a team handle, never a person's name).
- Data owner: the `group` of the mart behind the semantic model, usually `data_platform`.
- Description and label: the native `description` and `label`.

Only what dbt has no field for goes into `meta`:
```yaml
config:
  group: supply_chain_ops
  meta:
    version: 3
    status: certified            # draft | certified | deprecated
    certified_on: 2026-09-10
    recertify_every_days: 180
    decision: decisions/DR-001.md
    replaced_by: null            # required when status is deprecated
    agent_notes: "Use this, never sum qty_on_hand directly."
```

Business thresholds and exclusions are written as metric or measure filters here, not in mart SQL. For example the 90-day rule is a filter on `days_to_expiry` inside `available_stock`.

Metrics for v0.1:
| Metric | Rule written down |
| --- | --- |
| `available_stock` | on hand in base units in batches with at least 90 days to expiry, minus outbound transfers in transit (cancelled ones not subtracted). Semi-additive over time: `non_additive_dimension` on the snapshot date |
| `near_expiry_value` | cost value of stock in batches with fewer than 90 days to expiry, expired stock not yet written off included |
| `net_revenue` | sales after discounts and before VAT by sale date, minus refunds before VAT by return date |
| `gross_margin` | net revenue minus cost of goods sold at the store's weighted average cost for the SKU; not reversed for returns (destroyed) |
| `sell_through_rate` | base units sold (gross of returns) over base units received net: from suppliers and other stores, minus transfers out |
| `days_of_cover` | available stock at the snapshot over average daily base units sold in the 28 full days before it (a 28-day cumulative window offset by one day) |

Also include one `deprecated` metric, `revenue_v1` (VAT included, by sale date, returns ignored), with `replaced_by: net_revenue`, to show the lifecycle.

Saved queries: the slices the dashboard shows (section 13) are defined as dbt `saved_queries` in this folder. They are the only way a dashboard gets a number.

OSI: dbt 1.12 writes an Open Semantic Interchange document (`target/osi_document.json`, OSI 0.1.1) on every parse, with hidden metrics left out. `make export-osi` runs the parse and points to it.

## 8. Legacy conflict (`legacy/`)
Three SQL files that mimic real dashboards: `finance_dashboard.sql`, `sales_dashboard.sql`, `ops_weekly_report.sql`. Each computes "net revenue" differently (returns by sale month, returns ignored, discounts ignored). `make demo-conflict` runs all three plus the certified metric for the same month and prints the four numbers side by side, with the DR that settled it. Each legacy dashboard is declared as a dbt `exposure` with an owner and `maturity: low`, the way a company would catalog what it already has.

## 9. Decision records (`decisions/`)
`TEMPLATE.md` sections: Context, Decision, Options considered, Decided by (role), Date, Consequences, Linked metrics, Linked golden questions, Supersedes, Worked example (one case computed by hand).

v0.1 records:
- DR-001: available stock excludes batches under 90 days to expiry (60 vs 90 considered).
- DR-002: net revenue counts returns in the month of the return (finance vs sales; who broke the tie and why).
- DR-003: cancelled transfers are excluded from in-transit stock.
- DR-004: POS data rules. The business day is local time (Asia/Ho_Chi_Minh), whatever timestamp the vendor sends. Stores lagging POS sync are included but flagged; answers must carry a caveat.
- DR-005: deprecate `revenue_v1` in favor of `net_revenue`.
- DR-006: revenue metrics are reported before VAT (finance and tax view vs the shelf price store managers see).
- DR-007: stock and sell-through are counted in the SKU base unit; boxes and strips are converted, never added as they are.
- DR-008: cost of goods sold uses the weighted average cost per store and SKU over all its receipts, because POS lines carry no batch (store-level vs chain-level average considered). Returns are destroyed, so their cost is not reversed.
- DR-009: sell-through divides gross units sold by units received net (suppliers plus transfers in, minus transfers out), so it is right per store and for the chain (supplier-only and supplier-plus-transfers-in considered).

## 10. Golden questions (`golden/`)
About 30 questions, grouped by domain, covering four kinds:
| Kind | Example | What it protects |
| --- | --- | --- |
| Tacit rule | Available stock of an item in one district | the 90-day, in-transit, base unit and VAT rules |
| Conflict | Net revenue for August | the certified definition beats legacy ones |
| Caveat required | Sales yesterday across all stores | answer must flag lagging stores and use the local business day |
| Deprecated | Revenue using `revenue_v1` | must point to the replacement |

Fields: `id`, `question`, `kind`, `metric`, `filters`, `as_of`, `expected`, `tolerance`, `expected_caveats`, `why`, `decision`, `signed_off_by` (role), `signed_off_on`.

Expected values come from `golden/reference/`, written independently from the semantic layer, in plain pandas or SQL directly over source extracts. Freeze results into YAML with a script, and document why in README.

How to keep the reference really independent: write each reference computation from the text of its DR, before the matching metric exists. Each DR's worked example must also appear in `why` of at least one golden question, so a person can check one number without running anything.

How each kind passes in v0.1 (there is no agent yet, so the runner plays that role):
- Tacit rule and conflict: the semantic layer value is within `tolerance` of `expected`.
- Caveat required: the runner derives caveats from data. If the filtered scope includes a store where `dim_store` marks POS sync as lagging at `as_of`, the result carries `pos_sync_lag`. The question passes only when the value matches and the derived caveats equal `expected_caveats`.
- Deprecated: the runner refuses to return the old metric's number. It passes when the metric has `status: deprecated`, `replaced_by` points to a certified metric, and the runner's answer names that replacement.

`run_golden.py` queries the semantic layer through MetricFlow's Python API (not one `mf query` subprocess per question, which reloads the project each time), compares with tolerance, checks caveats, prints a table, shows `why` and the DR link on failure, writes a JUnit XML report for CI, and exits non-zero on failure. Measure its run time and keep the whole quickstart under 10 minutes.

## 11. Governance in Git
- `CODEOWNERS`: map `models/semantic/`, each DR, `golden/`, and every mart that feeds a certified metric to a placeholder team (for example `@your-org/supply-chain-ops`). Changing a definition, its proof, or the data under it then requires the business owner's review. This is how ownership becomes enforceable, not just documented.
- `pull_request_template.md`: which metric changed, linked DR, golden questions added or updated, affected exposures (dashboards and reports that depend on it), owner approval.
- `governance/lint.py` runs on `target/manifest.json` (after `dbt parse`), not on hand-parsed YAML. It fails when:
  - a metric has no `group`, or lacks a required `meta` field;
  - a DR link is broken;
  - a certified metric has no golden question;
  - a deprecated metric has no `replaced_by`, or it points to a metric that is not certified;
  - a mart feeding a certified metric has no enforced contract;
  - any text file in the repo contains the em dash character (U+2014);
  - a Power BI measure recomputes a metric (section 13).
- Staleness: a certification older than `recertify_every_days` is a warning, configurable to fail. Lint takes `--today`. The default is the snapshot date (2026-09-15), so the demo gives the same result on any calendar day. A company's real CI passes the actual date.
- Recertification follows the business review rhythm: 90 days for finance metrics (quarterly review), 180 days for operations metrics.
- Lint also prints, for each changed metric, the exposures that depend on it, so the PR author can fill in "affected exposures".
- `governance/registry.md`: generated table of every metric with owner, version, status, DR and last certified date. This is the page a manager reads. CI regenerates it and fails on `git diff --exit-code`, so the registry can never drift from the YAML.
- `CHANGELOG.md` for definition changes, kept by hand.

## 12. Demos
- `make demo-drift`: change the 90-day threshold to 60 in `available_stock` without touching DR-001 or golden questions; run golden questions; show failures with `why`; restore the file even if a step fails.
- `make demo-conflict`: see section 8.

## 13. Dashboards (Power BI, optional)
Most companies already own a BI tool, and the biggest risk is that the tool quietly becomes a second place where metrics are defined. This section shows the safe pattern with Power BI Desktop. It is optional: not part of `make test`, and its definition-of-done item is checked separately from the core ones.

Why not connect Power BI straight to the semantic layer: dbt's official Power BI connector needs the dbt platform (Starter plan or above) and is in preview. Open-source MetricFlow on DuckDB has no server for it to talk to, and Power BI has no native DuckDB connector. So the repo copies what companies on the dbt platform do with saved queries and exports.

How it works:
1. Every slice the report shows is a dbt saved query (section 7).
2. `make dashboard-data` runs `dashboards/export.py`, which executes each saved query through MetricFlow and writes one Parquet file per saved query to `dashboards/exports/`, with `metric_version`, `as_of` and `caveats` columns.
3. `dashboards/groundrules.pbip` is a Power BI project: the semantic model in TMDL and the report in PBIR, both text, so changes are reviewed in a PR like any other definition. It imports the Parquet files with Power BI's built-in Parquet connector, so nothing needs to be installed.
4. The report never recomputes a certified metric. Ratio and semi-additive metrics (`sell_through_rate`, `days_of_cover`, `available_stock`) are exported at exactly the grain the visual shows, because summing them again in DAX gives a wrong number. Lint reads the TMDL files and fails when a measure has no description naming its metric and version, or uses anything beyond display functions (`SELECTEDVALUE`, `MAX`, `MIN`).
5. A pytest compares the exported Parquet with golden expected values wherever a saved query and a golden question cover the same slice. The numbers on the dashboard are then backed by the same proof as the metric.
6. The report is declared as a dbt `exposure` that depends on the semantic models it uses, so lint can list it as affected when a metric changes.

Limits, stated plainly in README: Power BI Desktop runs only on Windows, so CI runs the export, the TMDL lint and the pytest, and opening the report is a manual step. Mac and Linux users can point any BI tool at the Parquet files. A company on the dbt platform replaces step 2 with dbt exports or the official connector, and keeps everything else.

## 14. Playbook (`playbook/`)
- `running-a-definition-session.md`: attendees, prep, how to break ties, the three outputs of every session (DR, metric change, golden questions).
- `ownership.md`: business owner vs data owner, what each is accountable for, how they map to dbt groups, and a RACI table template.
- `from-analyst-answers-to-golden-questions.md`: harvest the questions analysts answer every week; why this is easier than asking them to list their rules.
- `recertification.md`: how often to review (tied to the quarterly business review), who signs, what happens to stale metrics.

## 15. Adoption guide (`adoption/`)
- `adopt-in-30-days.md`: week 1 pick the 10 numbers leadership looks at most and find their owners; week 2 run definition sessions and write DRs; week 3 encode metrics and golden questions; week 4 turn on CI and CODEOWNERS.
- `existing-dbt-project.md`: how to copy `decisions/`, `golden/`, `governance/` and `.github/` into an existing dbt repo, and how to adopt groups, contracts and exposures if the project does not use them yet.
- `warehouses.md`: switching to Snowflake, BigQuery, Databricks or Postgres.
- `bi-tools.md`: keeping BI tools from redefining metrics. The export pattern from section 13, when to switch to dbt platform exports or official connectors, and what to check before trusting a BI tool that "reads the semantic layer" (some skip semi-additive, cross-model or cumulative metrics with only a warning; golden questions catch this).
- `cost-and-roles.md`: the real cost is business experts' hours, not tooling; who to involve and how much time to budget.

## 16. README
1. The problem, in 5 to 6 sentences, link to `SUBSTACK_URL`
2. What you get: four homes for knowledge (semantic model = what, decisions = why, golden questions = proof, Git = ownership)
3. Quickstart. Note that `make` needs WSL or Git Bash on Windows.
4. Demo 1: conflicting dashboards. Demo 2: silent drift caught. Demo 3 (optional, Windows): the Power BI report on certified exports.
5. Adopting it in your company (link to `adoption/`)
6. What this is not. Not a semantic engine; not a replacement for the dbt platform Semantic Layer or for vendor context layers such as Fivetran Context Layer. It is the process and governance around definitions, and it plugs into those products.
7. Roadmap (v0.2 agents, v0.3 actions)

## 17. v0.2 Agent-ready (do not start without asking)
- MCP access: build on the official `dbt-mcp` server first, in line with "build on what companies already run". Verify whether its semantic layer tools work against local MetricFlow or only against the dbt platform. Write a thin `mcp/` server (`list_metrics`, `describe_metric` with definition, owner, `agent_notes`, DR summary; `query_metric`) only for what `dbt-mcp` cannot do locally. Either way, deprecated and draft metrics are refused with a pointer to the certified one.
- `agent_eval/`: runs golden questions through an agent connected over MCP, scores accuracy and caveat handling, outputs a report. Pluggable model provider, needs an API key, not in default CI.

## 18. v0.3 Actions (do not start without asking)
One action contract (`propose_transfer`) with preconditions using certified metrics, a shadow table for proposals, a simulation of impact, an approval step, idempotent write-back to a fake ERP table, and an audit log recording the metric versions used.

## 19. Build order (v0.1)
1. Synthetic source extracts
2. dbt staging + marts + unit tests + data tests + freshness
3. Verify MetricFlow on DuckDB (versions, spec, Python API, saved queries), then semantic models and metrics
4. Decision records
5. Reference computations + golden questions + runner
6. Governance lint, registry, groups, exposures, CODEOWNERS, PR template
7. Demos (conflict, drift)
8. Dashboard: saved queries, Parquet export, Power BI project, TMDL lint (optional)
9. Playbook + adoption guide
10. README + CHANGELOG
11. CI

Run and verify each step before moving to the next.

## 20. Definition of done (v0.1)
- On a fresh clone: `make setup && make data && make build && make test` passes in under 10 minutes on a laptop.
- The generator checksum test passes on a second machine.
- `make demo-conflict` prints four different net revenue numbers and names the DR that settled it.
- `make demo-drift` shows golden questions failing for the right reason, then restores everything.
- `make lint` fails with a clear message when an owner group is removed, a DR link breaks, a certified metric has no golden question, a deprecated metric has no replacement, or an em dash appears.
- `make lint` gives the same result on any calendar day with the default `--today`.
- CI fails when `registry.md` is out of date.
- Optional dashboard, checked separately from the core items: `make dashboard-data` writes Parquet that matches golden expected values, and the Power BI report opens and refreshes on Windows (manual check).
- Switching `profiles.yml` to another warehouse needs no model changes (documented, not tested in CI).
- No real company names or rules, and no em dash character anywhere in the repo.
