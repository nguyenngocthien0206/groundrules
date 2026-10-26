# PROGRESS

Living status of the build. Claude reads this at the start of every session and updates it at the end of every build step. Keep entries short. Newest first in every log.

## Current status
- Phase: v0.1 Core
- Current step: 10. README + CHANGELOG
- State: not started (step 9 built on `step-09-playbook-adoption`)
- Last verified green: 2026-10-26 (`make build`: 97 dbt nodes, 1 expected warning; `make test`: lint 0 errors 0 warnings, 30 golden questions, 7 Parquet exports, 149 pytest)

## Build checklist (v0.1)
Tick a step only when it runs end to end and its checks pass.

- [x] 1. Synthetic source extracts (`example/generate.py`) + checksum test
- [x] 2. dbt staging + marts + unit tests + data tests + freshness
- [x] 3. Verify MetricFlow on DuckDB (versions, spec, Python API, saved queries), then semantic models and metrics
- [x] 4. Decision records (DR-001 to DR-010 + TEMPLATE)
- [x] 5. Reference computations + golden questions + runner
- [x] 6. Governance lint, registry, groups, exposures, CODEOWNERS, PR template
- [x] 7. Demos (`make demo-conflict`, `make demo-drift`)
- [x] 8. Dashboard: saved queries, Parquet export, Power BI project, TMDL lint (optional)
- [x] 9. Playbook + adoption guide
- [ ] 10. README + CHANGELOG
- [ ] 11. CI

## Definition of done (v0.1)
Copied from SPEC section 20. Tick when verified on a fresh clone.

- [ ] `make setup && make data && make build && make test` passes in under 10 minutes
- [ ] Generator checksum test passes on a second machine
- [x] `make demo-conflict` prints four different net revenue numbers and names the DR
- [x] `make demo-drift` fails golden questions for the right reason, then restores everything
- [x] `make lint` fails clearly on: removed owner group, broken DR link, certified metric with no golden question, deprecated metric with no replacement, em dash
- [x] `make lint` gives the same result on any calendar day with the default `--today`
- [ ] CI fails when `registry.md` is out of date
- [x] (Optional dashboard) `make dashboard-data` matches golden expected values; Power BI report opens and refreshes on Windows (manual)
- [x] Warehouse switch documented: profiles, sources, the staging models that depend on how data lands, and the reference's raw views change; marts and the semantic layer do not
- [ ] No real company names or rules, no em dash character anywhere

## Later phases (locked until the owner says go)
- [ ] v0.2 Agent-ready: MCP server + agent eval harness
- [ ] v0.3 Actions: action contract, shadow table, approval, write-back, audit log

## Implementation decisions
Technical choices made during the build that are not already in SPEC.md. One line each: date, decision, why. If a decision changes the spec, say so and ask the owner first.

| Date | Decision | Why |
| --- | --- | --- |
| 2026-10-26 | Playbook gains `changing-a-rule.md` (PR #9 as the worked example) and `when-a-golden-question-fails.md`, beyond SPEC's four pages | The two situations a team meets first; told with what really happened in this repo instead of an invented case. |
| 2026-10-26 | The warehouse doc and definition of done say exactly what changes: profiles, sources, the two returns staging models (nested JSON), the POS file name column, `qualify` on Postgres, the reference's raw views, freshness offsets | Checking the claim "no model changes" against the code found the returns struct and array, the `filename` column and `qualify`. The owner chose the truthful wording over adding untested per-warehouse macros. |
| 2026-10-26 | `tests/test_docs.py` checks links, `make` targets and folder indexes in `playbook/` and `adoption/` | Docs that name commands and files rot silently; this keeps them true as the repo changes. |
| 2026-10-26 | DR-011 supersedes DR-009: sell-through has no value when net received is zero or negative, and stores opened after the period began and within 7 days after it carry `new_store:<store>`; `sell_through_rate` v2 | Step 8's export showed NW030 at -20.43 (September) and 0 (August, opening stock only). The owner chose a caveat over hiding new stores on the dashboard, so agents warn too. |
| 2026-10-26 | `dim_store.opened_on` became a time dimension; the runner reads opening days from the semantic layer, the reference from `raw_stores` | Same pattern as the lag caveat: the runner asks what an agent would ask, the reference stays independent. |
| 2026-10-26 | The dashboard's `caveats` column uses the golden caveat strings (`new_store:NW030, pos_sync_lag:NW030`) | One caveat vocabulary for agents, tests and managers once there is more than one kind. |
| 2026-10-26 | Lint: a governed metric must link an accepted record, and `supersedes` / `superseded_by` must point at each other | A rule changes by a new record replacing the old one; the old record stays as history and nothing may keep pointing at it. |
| 2026-10-26 | Freeze writes `null` for no value | Python's `None` written as text reads back from YAML as the string "None". |
| 2026-10-26 | Dashboard slices are six saved queries in `saved_queries_finance.yml` and `saved_queries_supply_chain.yml`, each at the grain its visual shows; the lint requires each file to be owned by its metrics' teams | A saved query decides which slice managers see, so it is a rule like any other. Re-aggregating a ratio or a stock position in DAX gives a wrong number. |
| 2026-10-26 | `pyarrow==26.0.0` in the dev group; `dashboards/export.py` writes one Parquet per saved query plus `metric_versions.parquet`, with `as_of` and `caveats` on every row, and refuses non-certified metrics | Power BI reads Parquet with its built-in connector; versions sit in their own table instead of a column on every row. Approved by the owner. |
| 2026-10-26 | Power BI project in PBIP (TMDL + PBIR, Desktop 2.159); measures are `SELECTEDVALUE` over one column, named `<metric> by <slice>` (visuals show the short label through `displayName`), with a `/// metric: <name> v<version>` description, metric columns hidden with `summarizeBy: none`, `discourageImplicitMeasures` on, totals blank | The model only displays certified numbers; the lint reads the TMDL and fails on anything that computes. Power BI refuses a model where two measures share a name, even in different tables (found on the first open), so the lint checks that too. PBIR files were checked against Microsoft's JSON schemas; TMDL has no public schema, so Desktop is the check. |
| 2026-10-26 | Monthly saved queries start in April 2026, the first full month of POS data; monthly exports carry `data_through` and `is_month_to_date`; the export refuses a month that starts before the POS history | The first export showed 168 rows of sell-through 0 for September 2025 to February 2026 (ERP receipts, no tills yet) and a half-month March. "No data" must not read as 0, and the running month must say it is month to date. Confirmed by the owner. |
| 2026-10-26 | The Power BI files are committed as Desktop saves them (lineage tags, `.platform`, `.pbi/editorSettings.json`, `cultures/`), with Auto date/time off, relationship autodetect off, metric columns marked `SummarizationSetBy = User`, and `ExportFolder` back on the placeholder; the lint checks the last three | The first save in Desktop reset all 12 metric columns to `sum`, added 16 hidden date tables and wrote the owner's local path. The lint caught the `sum` columns at once; the new checks cover the rest. |
| 2026-10-26 | `make test` runs `make dashboard-data` before pytest | The dashboard tests compare exports with golden expected values and need fresh files; it adds a few seconds. |
| 2026-10-26 | The Power BI report is exposure `groundrules_powerbi_report`, depending on the six certified metrics | `make affected` lists it when any of them changes. |
| 2026-10-26 | Each legacy dashboard differs from `net_revenue` by exactly one recorded rule: finance puts refunds on the sale month (DR-002), sales leaves returns out (DR-002), the ops report uses till amounts with VAT (DR-006, replacing SPEC's "discounts ignored") | The demo names the record behind every gap; no record covers discounts. Confirmed by the owner. |
| 2026-10-26 | Legacy SQL reads the marts directly; the conflict demo exits 1 if two answers agree | That is how an old dashboard reads the warehouse; the demo cannot silently stop making its point. |
| 2026-10-26 | The drift demo shows the lint (0 errors), `affected` and CODEOWNERS before the golden questions, and restores the rule file byte for byte in `finally` | The point: every formal check passes, a reviewer would have to spot 60 vs 90, and only the golden questions catch the meaning change. |
| 2026-10-26 | DuckDB connections opened with default settings next to MetricFlow | In one process DuckDB refuses a `read_only` connection to a file the dbt adapter already holds; the queries only read. |
| 2026-10-26 | Cross-model metrics split by owner (`metrics_finance.yml`, `metrics_supply_chain.yml`); expected values split by domain (`golden/expected/<domain>.yml`) | On GitHub any listed code owner can approve a file, so a shared file would let one team approve another team's rules or numbers. Confirmed by the owner. |
| 2026-10-26 | Team handles live in `models/groups.yml` as `config.meta.github_team`; new group `retail_operations` | One source for ownership; the lint checks CODEOWNERS against it. `config.meta` instead of extra `owner` keys keeps the dbt JSON schema (and IDEs) happy; both parsers accept it. |
| 2026-10-26 | A rule file's CODEOWNERS must be exactly the teams of the metrics its rules shape; hidden building blocks count for the certified metrics that use them. Decision records and golden files must at least reach every team they cover | Exact for rule files so no extra team can approve alone; `fct_sales.yml` is the one shared rule file (finance revenue blocks and supply chain units sold). |
| 2026-10-26 | The lint is functions over loaded data (`governance/repo.py`), not over files; it absorbed `tests/test_decisions.py` and the question link checks | Tests break a deep copy instead of files and do not rerun dbt. |
| 2026-10-26 | The registry shows "recertify by" dates, not "stale" | The file stays the same whatever the calendar says; staleness is the lint's job, with `--today`. |
| 2026-10-26 | Three legacy dashboards declared as exposures now (their SQL comes in step 7); `make affected` follows dbt lineage from changed files to metrics and exposures | Exposures are what `make affected` and the registry report on. |
| 2026-10-26 | Reference computations are SQL over the raw extracts (DuckDB reading the files, one SQL file per metric citing its DRs), not Python or pandas | What teams use for reconciliation in practice: analysts and owners can read and sign SQL, and adopters swap `read_csv` for raw tables. A test forbids marts, dbt and MetricFlow in `golden/reference/`. Asked by the owner. |
| 2026-10-26 | Expected values live in generated `golden/expected.yml` (with the data fingerprint); question files are human-written | Owner's choice; a script never rewrites what people wrote. A test fails if `expected.yml` differs from a fresh reference run. |
| 2026-10-26 | `pos_sync_lag` follows stores and days: a lagging store in scope counts when the period reaches past its last day of data, or for a stock position at `as_of`. One clarifying sentence added to DR-004 | Owner's choice; avoids a caveat on every chain-level question. GQ-POS-04 guards against over-caveating. |
| 2026-10-26 | Reference money is summed as `decimal(38, 6)` per line; raw files are loaded once into in-memory tables | Floating-point sums changed in the last digits between runs (parallel aggregation), which would make every re-freeze a noisy diff; freezing dropped from 33s to 3s. |
| 2026-10-26 | Gross margin questions use a 100 VND tolerance, other money questions 1 VND | The mart stores unit cost to 4 decimals, so the chain total drifts by about 2 VND from the reference; a changed cost rule moves it by millions. |
| 2026-10-26 | Deprecated questions carry `expected_replacement` in the question file; freeze copies it | The replacement is a decision (DR-005), not something the data can compute. |
| 2026-10-26 | `dim_store.pos_data_through` became a time dimension; the runner gets lag information through a dimension-only MetricFlow query | Caveats come from the semantic layer, as an agent's will. |
| 2026-10-26 | `golden/semantic_client.py` is the one MetricFlow wrapper; `tests/test_semantic_layer.py` uses it | One place for the step 3 rules (absolute DuckDB path, one where constraint per filter). |
| 2026-10-26 | Decision records use MADR-style YAML front matter (id, status, date, decided_by, consulted, linked_metrics, linked_golden_questions, supersedes, superseded_by) plus body sections Context, Decision, Options considered, Consequences, Worked example | Front matter is machine readable for the lint; teams already know the format. |
| 2026-10-26 | New DR-010 for the days-of-cover pace window; `days_of_cover` now links to it instead of DR-001. DR-001 also records that near-expiry value includes expired stock | The 28-day window was a rule with no record. |
| 2026-10-26 | Golden question ids reserved in the records (GQ-STOCK-01 to 05, GQ-REV-01 to 03, GQ-POS-01 to 02, GQ-LIFE-01, GQ-MARGIN-01, GQ-SELL-01, GQ-COVER-01 to 02); step 5 must create each one | Records and questions stay linked from the start. |
| 2026-10-26 | Worked examples use real rows from the marts and were cross-checked against MetricFlow (all match) | A reader can check one number by hand; step 5 reuses the same cases in `why`. |
| 2026-10-26 | `tests/test_decisions.py` checks front matter, sections, metric links both ways and the index; `pyyaml==6.0.3` pinned as a dev dependency | Step 6's lint will take these checks over. |
| 2026-10-24 | Business rules for step 3: COGS at weighted average cost per store and SKU over all receipts, not reversed for returns (DR-008); sell-through = gross units sold / units received net of transfers out (DR-009); near-expiry value includes expired stock not yet written off | Confirmed by the owner. |
| 2026-10-24 | Semantic layer in dbt's latest YAML spec on dbt-core 1.12.6 + dbt-metricflow 0.15.0 (MetricFlow 0.213.0); each mart's properties moved to `models/semantic/<mart>.yml`, cross-model metrics in `models/semantic/metrics.yml` | dbt's recommended spec; a semantic model must share a properties file with its model, and this keeps every rule in one folder for CODEOWNERS. |
| 2026-10-24 | Building-block metrics use `hidden: true` (stored as `is_private`), not `status: draft` | They drop out of `mf list`, the OSI document and later the agent; `draft` keeps its meaning of "not yet approved". |
| 2026-10-24 | `semantic_model: {enabled: true}` instead of `semantic_model: true` | The v2 parser rejects the boolean form; the struct form works on both. |
| 2026-10-24 | Time dimensions written `dimension: {type: time}` with `granularity` on the column | dbt-core 1.12.6 drops the granularity of the `dimension: time` shorthand, leaving time dimensions without a grain. |
| 2026-10-24 | Optional inputs of derived metrics are wrapped in `coalesce(..., 0)`; no `fill_nulls_with` | dbt-core 1.12.6 does not pass `fill_nulls_with` for latest-spec metrics; without coalesce, `available_stock` was null for every store with nothing in transit. |
| 2026-10-24 | Python access: `CLIConfiguration().setup(dbt_profiles_path=dbt, dbt_project_path=dbt)` then `cfg.mf.query(MetricFlowQueryRequest.create(...))`, with `GROUNDRULES_DUCKDB` set to an absolute path | Same engine as `mf query`; the profile path is relative to the working directory, so a relative path silently opens an empty database. |
| 2026-10-24 | Each query filter is its own where constraint (time separate from store or district); `time_constraint_start/end` are not used | Joined into one string, or as time constraints, MetricFlow applies the time filter below `days_of_cover`'s 1-day offset and returns nothing. The step 5 runner must follow this. |
| 2026-10-24 | Makefile exports `PYTHONUTF8=1` | MetricFlow's CLI spinner fails on emoji on a Windows console without it. |
| 2026-10-24 | `make export-osi` uses the OSI document dbt 1.12 writes on parse (`target/osi_document.json`, OSI 0.1.1, 7 visible metrics) | Answers SPEC section 7: no custom mapping needed. |
| 2026-10-24 | `fct_transfers` gains `snapshot_date`; `fct_sales` gains `unit_cost_excl_vat` and `cogs_excl_vat` from new `int_store_sku_costs`; daily `metricflow_time_spine` 2025 to 2027 | In-transit stock aggregates on the same date as on-hand; COGS needs a cost per line; cumulative windows need a spine. |
| 2026-10-24 | Groups `supply_chain_ops`, `finance`, `data_platform` added in step 3 instead of step 6 | Metrics name their owner group, which must exist when they are parsed. |
| 2026-10-24 | dbt line: dbt-core 1.12.6 + dbt-duckdb 1.11.0 (duckdb 2.0.0). The project also passes `dbt parse --use-v2-parser` (dbt-oss 2.0.8) | dbt v2's bundled DuckDB adapter may not infer schemas for CSV or JSON sources and cannot load extensions; dbt itself says to reach 1.12 before moving to v2. dbt-metricflow 0.15.0 resolves on this line. Confirmed by the owner. |
| 2026-10-24 | Raw files are read through dbt-duckdb `external_location` with `all_varchar`, so staging does all typing; the returns source uses `formatter: template` so its `columns = {...}` type map keeps its braces | Mirrors a loader that lands strings; explicit JSON types stop DuckDB guessing the time zone. |
| 2026-10-24 | Date parsing and UTC to local use only standard SQL and dbt cross-database macros (`dbt.concat`, `dbt.dateadd`); only the returns unnest is DuckDB syntax | Switching warehouse should not need model edits; on a warehouse, loaders deliver nested returns lines as their own table. |
| 2026-10-24 | New `models/intermediate/` layer (`int_sales_lines`, `int_return_lines`); SPEC's `fct_receipts` is named `fct_goods_received` | Unions, unit conversion and VAT split in one place; "receipt" already means a sales receipt. |
| 2026-10-24 | Amounts excluding VAT are kept unrounded as `decimal(18,4)`; nothing is rounded in the marts | Rounding is a reporting rule, not a fact. |
| 2026-10-24 | Source freshness adds `(now - extract_at)` inside `loaded_at_field`, so the demo measures freshness as of the extract time | The data stops on 2026-09-15; against today's clock it would always fail. Real projects use the plain column. |
| 2026-10-24 | Per-store POS lag is a singular test with `severity: warn` that lists the 2 lagging stores on every build | Table-level freshness passes while single stores are days behind; DR-004 keeps them in the numbers but flagged. |
| 2026-10-24 | Unit tests whose input is a file source use `format: sql` fixtures | dbt cannot look up column types of an `external_location` source for dict fixtures. |
| 2026-10-24 | No dbt packages; a 10-line `unique_combination` generic test replaces dbt_utils | Quickstart needs no package download. |
| 2026-10-24 | Environment with uv and a committed `uv.lock`; Python 3.11 to 3.13; verified with Python 3.11.9, uv 0.11.14, pytest 9.1.1 | Lockfile pins indirect dependencies too; no venv path differences between Windows and Unix in the Makefile. Confirmed by the owner. |
| 2026-10-24 | Generator uses the standard library only, one `random.Random(f"{seed}:{name}")` stream per part, and writes LF, UTF-8, integer amounts | No library can shift the numbers; output is byte-identical (checked on Python 3.11 and 3.14). |
| 2026-10-24 | Extracts are not committed; `tests/fixtures/expected_manifest.json` (SHA-256 and rows per file) is. `make data-manifest` re-freezes it after an intended change | Keeps the repo small while still catching any drift in the data golden values depend on. |
| 2026-10-24 | District names are invented (Riverside, Old Quarter, Airport, Industrial Park, New Town); store codes `NW001` to `NW030` | No real place names; Vietnam dropped the district level in 2025 anyway. Confirmed by the owner. |
| 2026-10-24 | Source formats: ERP CSV (UPPER_SNAKE, `YYYYMMDD`); POS vendor A CSV per UTC day with UTC ISO timestamps and upload retries; POS vendor B semicolon CSV per local day with BOM, Vietnamese headers and `dd/mm/yyyy`; returns as nested JSON Lines with `+07:00` | Each source looks like its own system, so staging has real work to do. |
| 2026-10-24 | Stock behaviour: FEFO sales, supplier minimum order quantities, discounted short-dated lots, write-off of expired stock on the 1st of the month, transfers reserved at the sender until delivered | Gives about 5% of on-hand value within 90 days of expiry (typical for a pharmacy) and makes the in-transit and cancelled-transfer rules matter. |
| 2026-10-24 | Dashboard is Power BI Desktop on Parquet exports of dbt saved queries; optional, outside the core DoD | Official Semantic Layer connectors (Power BI included) need the paid dbt platform. Lightdash reads MetricFlow locally but is beta and skips `non_additive_dimension`, cross-model ratio and derived inputs, and cumulative metrics, which puts `available_stock`, `sell_through_rate` and `days_of_cover` at risk. dbt Charts (beta) cannot query the semantic layer yet. Confirmed by the owner. |
| 2026-10-24 | Business thresholds live in semantic YAML; marts expose neutral facts | Keeps every rule change inside files CODEOWNERS protects, and makes `demo-drift` edit the right place. |
| 2026-10-24 | dbt-native governance first: groups for owners, contracts on certified marts, exposures for dashboards; `meta` only for status, version, certification, DR, `replaced_by`, `agent_notes` | Matches how companies already run dbt, so adopters copy less custom structure. |
| 2026-10-24 | Lint reads `target/manifest.json` and takes `--today` (default 2026-09-15) | Robust to YAML layout; the demo does not go stale with the calendar. |
| 2026-10-24 | Data gains VAT in POS prices, box/strip/tablet units, UTC vs local POS timestamps; new DR-006 (revenue before VAT) and DR-007 (base unit); DR-004 also covers the local business day | Closer to how a Vietnamese pharmacy chain's data actually arrives. |
| 2026-10-24 | v0.2 builds MCP access on `dbt-mcp` first | Build on what companies already run. |
| 2026-10-24 | CLAUDE.md, SPEC.md and PROGRESS.md stay in `docs/` | Owner's choice. |
| 2026-10-14 | Product name Groundrules, repo `groundrules` | Short product-style name; "ground rules" plus "grounding" an agent. Confirmed by the owner. |

## Open questions and blockers
Things that need the owner's input. Remove an item once it is answered, and record the answer under Implementation decisions.

- Do `dbt-mcp` semantic layer tools work against local MetricFlow, or only the dbt platform? Verify before v0.2.

## Session log
One entry per working session. Format:

```
### YYYY-MM-DD
- Done: what was built or changed
- Verified: which commands ran green
- Next: the very next action
- Notes: anything surprising, worked around, or worth knowing next time
```

### 2026-10-26 (step 9)
- Done: `playbook/` (index plus six pages) and `adoption/` (index plus five pages), warehouse wording corrected in `profiles.example.yml`, CLAUDE.md, SPEC and the definition of done, `tests/test_docs.py`
- Verified: every number quoted checked against the repo (four August revenue answers, GQ-STOCK-01's 48 vs 49, NW030's -20.43, the 2.16 VND margin drift, the 12 reset columns, recertification periods of 90 and 180 days); the docs test fails on a broken link and on an unknown make target, then passes; `make test` green; no em dash
- Next: step 10, starting in plan mode: README and CHANGELOG
- Notes: the warehouse claim was wrong in the spec and in `profiles.example.yml` ("models run unchanged"); five staging-level changes are needed, all where staging is meant to absorb them.

### 2026-10-26 (fix: sell-through for new stores)
- Done: DR-011 superseding DR-009, `sell_through_rate` v2 (no value when net received is not positive), `new_store` caveat in the reference, runner and export, GQ-SELL-04 and 05, lint checks for superseded records, Power BI description at v2, registry, 17 new tests
- Verified: `mf query`: NW030 September empty, August 0, NW014 August 1.117; freeze diff only in `golden/expected/sell_through.yml` (SELL-02 and 03 gain `new_store:NW029, new_store:NW030` with unchanged values, SELL-04 null, SELL-05 0.0), stable on a second run; the lint failed on the v1 Power BI description and the stale registry until both were updated; `make test`: lint clean, golden 30/30, 149 pytest; no negative sell-through in the export; both demos pass; v2 parser parses; no em dash
- Next: step 9, starting in plan mode, with this change as the playbook's worked example of a rule change
- Notes: opening stock arrives the day before a store opens in the data (NW029 on 17 August, NW030 on 31 August); DR-011 states a 7-day window as the business assumption.

### 2026-10-26 (step 8)
- Done: six saved queries split by owner, `dashboards/export.py` and `make dashboard-data`, `saved_query()` in the shared MetricFlow client, the Power BI project (`groundrules.pbip`: TMDL model with 7 tables, PBIR report with 3 pages and 7 visuals), `check_powerbi` and saved query owners in the lint, the report as an exposure, CODEOWNERS and `.gitignore` entries, 28 new tests
- Verified: `make build` 97 nodes green; `mf validate-configs` 0 errors; exports 36/30/6/172/6/30/6 rows (April to September; September marked month to date, data through 9/14); exports match GQ-REV-01, GQ-POS-03 (caveat NW030), GQ-POS-04, GQ-REV-03, GQ-MARGIN-03, GQ-SELL-01, GQ-COVER-01, GQ-COVER-02 (caveat NW029), GQ-STOCK-08; every visual field exists in the TMDL; 16 PBIR files pass Microsoft's schemas; `make test`: lint clean, golden 28/28, 132 pytest; removing the April filter makes the export refuse with a clear message; v2 parser parses (own `--target-path`); no em dash
- Verified by the owner: `groundrules.pbip` opens in Power BI Desktop 2.159, refreshes from the Parquet exports after setting `ExportFolder`, and the numbers match the golden questions on all three pages
- Next: step 9, starting in plan mode
- Notes: the first open failed because measure names must be unique across the whole model, not per table; the first save reset every metric column to `sum` (caught by the lint), added Auto date/time tables and wrote a local path. The first export had 368 sell-through rows, 168 of them a false 0 before the tills' history began; reading every row, not only the golden slices, caught it. Saved queries also work through MetricFlow's Python engine (`saved_query_name=`). The stock saved queries group by the snapshot day and filter on it; the export drops that column, since `as_of` already says the day. Totals in the report stay blank by design.

### 2026-10-26 (step 7)
- Done: `legacy/` with the three dashboards, `demos/conflict.py` and `demos/drift.py`, `make demo-conflict` and `make demo-drift`, legacy files in CODEOWNERS, ops exposure description updated, `store_sync_state` factored out of the runner, 11 demo tests
- Verified: August: finance 7,387,021,279 (+13,578,516), sales 7,442,338,602 (+68,895,839), ops 7,855,865,056 (+482,422,293), certified 7,373,442,763 with DR-002 and GQ-REV-01; July works too. Drift: lint 0 errors, affected lists the three stock metrics and the ops report, CODEOWNERS asks supply chain, 4 golden questions fail (GQ-STOCK-01 48 vs 49 with DR-001), file restored; run twice in a row; a failure injected mid-demo still restores the file (test on a copy). `make test`: lint clean, golden 28/28, 104 pytest
- Next: owner to choose between step 8 (optional Power BI dashboard, needs `pyarrow` approval) and step 9 (playbook and adoption guide)
- Notes: four of ten definition-of-done items are now ticked; the rest come with steps 9 to 11.

### 2026-10-26 (step 6)
- Done: governance lint (8 checks plus staleness), registry generator and `registry.md`, `affected.py`, team handles on groups, `retail_operations` group, three legacy exposures, CODEOWNERS, PR template, metrics and expected values split by owner, `make lint`, `make registry`, `make affected`; `make test` now runs lint, golden, pytest; 20 lint tests, `tests/test_decisions.py` removed
- Verified: lint 0 errors 0 warnings; on the real repo each definition-of-done break fails `make lint` with one clear line (owner group removed, decision link broken, a certified metric's golden questions deleted, `replaced_by` removed, an em dash added) and passes again once restored; `--today 2027-01-04` warns on the two finance metrics due 2026-12-09, `--fail-on-stale` fails; golden 28/28; pytest 93; v2 parser parses (run with its own `--target-path`)
- Next: step 7, starting in plan mode: the three legacy SQL files, `make demo-conflict` and `make demo-drift`
- Notes: the lint caught its own em dash on its first run (an escaped code point had been written out as the literal character); it now uses `chr(0x2014)`. A changed `int_store_sku_costs.sql` reaches every `fct_sales` metric and all three dashboards through lineage, which is conservative but honest at model level.

### 2026-10-26 (step 5)
- Done: reference SQL over the raw extracts (raw views + 6 metric files + lagging stores), 28 golden questions in 7 files covering all four kinds and every certified metric, `expected.yml` frozen from the reference, the runner (table, why and DR on failure, JUnit XML), shared MetricFlow client, `make golden` and `make golden-freeze`, `make test` now runs golden first, 29 new tests
- Verified: `make build` green, `make metrics` 0 errors, golden 28/28 in about 10s, pytest 106 pass, v2 parser parses. Freezing three times gives identical files. Drift dry run (90 to 60 days in `available_stock`): 4 questions fail, GQ-STOCK-01 shows 48 vs 49 with its why and DR-001; restored. A wrong expected caveat on GQ-POS-04 fails on caveats, not value. Pointing a reference SQL file at `marts.` fails the independence test
- Next: step 6, starting in plan mode: governance lint on manifest.json (absorbing tests/test_decisions.py and the question link checks), registry, exposures, CODEOWNERS, PR template
- Notes: first runner pass found the only mismatch at 2.16 VND on chain gross margin (rounding of unit cost in the mart), not a rule error. The reference independently reproduces every decision record worked example within its rounding. The whole quickstart now takes about 3 minutes on this laptop. `dbt parse --use-v2-parser` overwrites `dbt/target/` and writes `config: null` for metrics without config; readers now accept that, and step 11's CI must run the v2 check with its own `--target-path`.

### 2026-10-26 (step 4)
- Done: `decisions/` with TEMPLATE, README index and DR-001 to DR-010, each with a real worked example; `days_of_cover` linked to DR-010; decision record tests
- Verified: `make build` green, `make metrics` 0 errors, `make test` 77 pass; tests fail when a section, a front matter key or a metric link is broken (tried and restored); worked examples match MetricFlow: available_stock NW001/100031 229, NW014/100002 2,326, NW004/100010 477; near_expiry_value NW001/100031 83,120 and NW013/100149 4,896,318; net_revenue NW001 August 236,303,956.71 and chain August 7,373,442,762.59; sell_through_rate NW014 August 1.1169; days_of_cover NW001 26.32
- Next: step 5, starting in plan mode: reference computations over source extracts, about 30 golden questions including every reserved id, and the runner
- Notes: `near_expiry_value` returns None (not 0) for a store and SKU with no short-dated batch; the runner must treat a missing value as 0 where the question expects 0. The 24-hour store sale used in DR-004 sits in vendor A's file for 2026-07-31 although its business day is 2026-08-01.

### 2026-10-24 (step 3)
- Done: dbt-metricflow added and verified on DuckDB (validate-configs, query, saved query, Python engine, group and meta, filter, non-additive, cumulative window, offset). Semantic models on all 7 marts; 6 certified metrics plus deprecated `revenue_v1`; 10 hidden building blocks; groups; time spine; weighted average cost; `make metrics`, `make export-osi`; 10 semantic layer smoke tests
- Verified: `make build` green (86 pass, 1 expected warning); `make metrics` 0 errors on every level; `make test` 44 pass; v2 parser parses; `available_stock` matches a hand-written SQL total exactly (1,228,249 base units) and `days_of_cover` for NW001 matches a hand calculation (26.32 days)
- Next: step 4, starting in plan mode: DR-001 to DR-009 and the template, each with a worked example
- Notes: August 2026: net revenue 7.37 bn VND vs revenue_v1 7.93 bn, gross margin 2.41 bn (about 33%), sell-through 0.97. Near-expiry value at the snapshot 272.7 m. NW029 shows 38.8 days of cover because it opened on 2026-08-18 and lags 3 days: exactly the case DR-004's caveat is for. Three dbt 1.12.6 quirks are worked around (time dimension shorthand, fill_nulls_with, boolean semantic_model for v2).

### 2026-10-24 (step 2)
- Done: dbt project on DuckDB: 10 staging models (ERP, POS A/B, sync log, returns), 2 intermediate, 7 marts with enforced contracts and documented columns; 6 unit tests; data tests; source freshness; per-store POS lag warning
- Verified: `make build` green in about 35s (79 pass, 1 expected warning listing NW029 and NW030), freshness pass on 3 sources; `make test` 34 pass; a deliberately wrong contract type fails the build; v2 parser parses the project
- Next: step 3, starting in plan mode: add dbt-metricflow, check spec, Python API and saved queries on DuckDB
- Notes: POS A retries removed exactly (472,947 lines, the simulated count). 16 transfers in transit and 50 cancelled at the snapshot. Returns: 4,793 lines match a sale, 228 have no receipt, 115 point to sales before the window; 1,446 land in a later month than the sale. Some 24-hour store sales on the evening of 31 March UTC belong to 1 April local, a good month-boundary case for golden questions.

### 2026-10-24 (step 1)
- Done: synthetic extracts for 30 stores, 150 SKUs, six months: ERP stores, SKUs, units, batches, transfers; POS vendors A and B; POS sync log; returns. Manifest plus reproducibility test.
- Verified: `make setup && make data && make build && make test` green, 34 tests in about 65s; `make data` about 30s for 376 files and 505k rows; same bytes on Python 3.14
- Next: step 2, starting in plan mode
- Notes: a receipt can hold the same SKU and unit on two lines (scanned twice), so staging and the reference computations must not key sales on receipt plus SKU. Lagging stores have no sales after 2026-09-11 in any source. Returns are never restocked.

### 2026-10-24
- Done: reviewed the spec and updated CLAUDE.md, SPEC.md and PROGRESS.md (golden scoring for caveat and deprecated kinds, rule placement, missing source columns, lint `--today`, version pinning, reference independence, registry check, em dash check, dbt-native governance, VN pharmacy data realism, optional Power BI dashboard, `dbt-mcp` for v0.2)
- Verified: docs only, no code yet
- Next: step 1, synthetic source extracts
- Notes: SPEC sections were renumbered; the dashboard is section 13 and the definition of done is section 20