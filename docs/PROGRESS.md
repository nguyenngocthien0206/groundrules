# PROGRESS

Living status of the build. Claude reads this at the start of every session and updates it at the end of every build step. Keep entries short. Newest first in every log.

## Current status
- Phase: v0.1 Core
- Current step: none; v0.3 is complete
- State: v0.3.0 released on 2026-10-29 (#19 to #26); a use-case guide built on `docs-use-case-guide`
- Last verified green: 2026-10-26 on GitHub Actions, run 40357875267 on main (`make build`: 97 dbt nodes, 1 expected warning; lint 0 errors 0 warnings as of 2026-10-26; golden 30/30; 185 pytest; both demos; v2 parser)

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
- [x] 10. README + CHANGELOG
- [x] 11. CI

## Definition of done (v0.1)
Copied from SPEC section 20. Tick when verified on a fresh clone.

- [x] `make setup && make data && make build && make test` passes in under 10 minutes (289 seconds on a fresh clone, uv cache warm)
- [x] Generator checksum test passes on a second machine (Ubuntu runner in CI, run 40357875267)
- [x] `make demo-conflict` prints four different net revenue numbers and names the DR
- [x] `make demo-drift` fails golden questions for the right reason, then restores everything
- [x] `make lint` fails clearly on: removed owner group, broken DR link, certified metric with no golden question, deprecated metric with no replacement, em dash
- [x] `make lint` gives the same result on any calendar day with the default `--today`
- [x] CI fails when `registry.md` is out of date (the lint step and the registry step both fail; verified with the CI commands on a version bump without `make registry`)
- [x] (Optional dashboard) `make dashboard-data` matches golden expected values; Power BI report opens and refreshes on Windows (manual)
- [x] Warehouse switch documented: profiles, sources, the staging models that depend on how data lands, and the reference's raw views change; marts and the semantic layer do not
- [ ] No real company names or rules, no em dash character anywhere

## Later phases (locked until the owner says go)
- [x] v0.2 Agent-ready: MCP server + agent eval harness
  - [x] 12. MCP server (`mcp_server/semantic.py`, raw SQL control arm)
  - [x] 13. Agent eval harness (`agent_eval/`, providers `claude-code` and `anthropic-api`)
  - [x] 14. Real run (Sonnet, 30 questions x 3 reps x 2 arms), results, release 0.2.0
- [x] v0.3 Actions: action contract, shadow table, approval, write-back, audit log
  - [x] 15. Logistics routes (invented city, `fct_store_routes`)
  - [x] 16. Action contract `propose_transfer` and DR-012
  - [x] 17. Proposals: MCP tool, simulation, shadow table
  - [x] 18. Approval, idempotent write-back, audit log
  - [x] 19. Action golden questions and agent eval
  - [x] 20. Docs and release 0.3.0

## Implementation decisions
Technical choices made during the build that are not already in SPEC.md. One line each: date, decision, why. If a decision changes the spec, say so and ask the owner first.

| Date | Decision | Why |
| --- | --- | --- |
| 2026-10-29 | Both action arms get DR-012's Decision section in the system prompt; only the tools differ | Owner's choice for the control arm; giving the governed arm the same text keeps "only the tools differ", so the eval measures enforcement against a policy in the prompt. |
| 2026-10-29 | Action questions name store and SKU codes | Owner's choice: the eval tests the rules, not code lookup, and needs fewer tool calls on the subscription. |
| 2026-10-29 | The action eval grades what was filed, from each run's own DuckDB file, and adds a safety score from `TransferPlanner.simulate` | What an agent writes is what matters; "safe" is the share of runs that filed nothing breaking DR-012. |
| 2026-10-29 | A no-proposal question's reason is the owner's, written in the question; the reference only says whether there is a proposal and what it is | The reference was written to compute proposals; the reason is a business classification the owner signs. |
| 2026-10-29 | Approvers are listed in `actions/approvers.yml`, owned by the approver group through CODEOWNERS and checked by the lint | Owner's choice: adding an approver is a pull request supply chain approves, not a config anyone can change. |
| 2026-10-29 | Approval rechecks versions and recomputes the proposal; anything different marks it stale | Owner's choice: a proposal computed on an old definition or old stock is not approved, the agent proposes again. |
| 2026-10-29 | Approve as is or reject with a reason; no editing; nobody approves what they filed | Owner's choice: an edit would step outside DR-012; a reason tells the owners whether the rule should change. |
| 2026-10-29 | The stand-in ERP is its own DuckDB file; the request is written first, keyed by the proposal id, then the decision | Two systems cannot share a transaction, so the write is idempotent and a retry after a crash finishes the approval with one request. |
| 2026-10-29 | The audit log lives next to the proposals and is only ever appended to | One place to answer "who approved this, when, on which versions", including refusals. |
| 2026-10-29 | The agent names a target store and SKU; the rules choose donor and quantity. `simulate_transfer` answers any what-if and writes nothing | Owner's choice: an agent cannot pick a farther donor or a bigger quantity than DR-012 allows, but can still explore alternatives. |
| 2026-10-29 | Actions get their own MCP server (`mcp_server/actions.py`) and their own DuckDB file (`var/actions.duckdb`) | Owner's choice: the v0.2 semantic server and its measured eval stay as they were, and the warehouse stays read-only for every reader. |
| 2026-10-29 | The engine compares thresholds on whole numbers (available x 28 against sold x days) and refuses if `days_of_cover` disagrees | Keeps 7.0 and 60.0 exact like the reference, and turns a silent change in what cover means into a refusal. |
| 2026-10-29 | A proposal's id is a hash of action, contract version, data date, target and SKU; the shadow file is opened per call | Filing the same proposal twice keeps one row; the approval tool in step 18 can open the file between an agent's calls. |
| 2026-10-29 | `days_of_cover` v2 coalesces an empty available stock to 0; no new decision record | A store-SKU that has run out has no stock row, so v1 divided an empty stock and gave no value where DR-010 gives 0. The rule did not change, only the code now follows it. Owner chose to fix it in its own PR before step 17. |
| 2026-10-29 | Transfers move whole purchase units (box or carton): round up to 14 days, never more than the donor can spare | Owner's choice: the ERP and the warehouse move boxes; nobody opens a box to send part of it. Recorded in DR-012. |
| 2026-10-29 | A partial proposal comes from the nearest donor; one donor per proposal | Owner's choice: one van, one stop. Another donor could cover the whole need in only 7 of the 28 partial cases. |
| 2026-10-29 | No proposal leaves the target above 60 days of cover | Owner's choice after the data showed 35 proposals (all stores that had run out, mostly slow sellers getting a full carton) that would have made the target a donor at once. |
| 2026-10-29 | When targets share a donor, the lowest cover goes first, then store code; a later target takes its next nearest donor | Without an order a donor could promise the same box twice (NW011, SKU 100146, to NW025 and NW022). Proposed in the step 16 plan and approved by the owner. |
| 2026-10-29 | "Newly opened" for transfers means opened on or after the first day of the 28-day pace window | The pace of a store that opened inside the window is not settled. Today it catches the same two stores as the lag rule and the missing routes. |
| 2026-10-29 | The action contract pins certified metric versions and may read a hidden metric only when it sits inside a pinned one | A version bump forces the owner to re-check the rule; `units_sold_28d` is needed because a store that has run out has no cover to work the pace back from. |
| 2026-10-29 | The transfer reference shares out donor stock in a short Python loop after the SQL | Sequential allocation is awkward in SQL; the SQL still holds every threshold, written from DR-012's text. |
| 2026-10-29 | v0.3 transfer rules decided by the owner: target cover under 7 days, donor over 60; bring the target to 14 days, donor keeps at least 30; only `available_stock` moves; donor within 30 minutes' drive by the route table (not by district), nearest first; no lagging or newly opened store; supply chain approves each proposal | These become DR-012 in step 16. The distance rule came from the owner: a store on a district's edge can be nearer the next district than its own. |
| 2026-10-29 | Store routes come from a new logistics extract over an invented city (river, two bridges), generated from two new random streams | Existing extracts stay byte-identical, so no golden value moves (only the data fingerprint lines). No real place names or coordinates. |
| 2026-10-29 | Route staging deduplicates with `row_number()` in a subquery, not `qualify` | Keeps the new model portable to Postgres; `qualify` is already listed as a portability cost in the warehouses guide. |
| 2026-10-29 | `gross_margin`'s `agent_notes` now say a question about margin means the VND amount, and a rate only when asked; no version bump | The old note ("For a margin rate, divide by net_revenue") led one v0.2.0 run to answer a rate. The number is unchanged, so the version and the definitions changelog stay; finance still reviews it through CODEOWNERS. The other notes were reviewed and none invites a derived number. |
| 2026-10-27 | Caveats are graded strictly against the caveat codes; the right number is scored separately | Owner's choice after the pilot: a program reading the answer needs `pos_sync_lag:NW029`, not a sentence; scoring the number on its own keeps the control arm from losing twice for one gap. |
| 2026-10-27 | The full run was split into batches by measured usage (12-run probe batch, one rep for every question, then reps 2 and 3); the runner resumed each time | The owner's subscription was at 53% when the run started; a 12-run batch measured the cost per run before committing to the rest. |
| 2026-10-27 | Recorded agent output keeps non-ASCII characters as JSON escapes | One raw SQL trace contained an em dash in the agent's own words; escaping keeps the evidence verbatim when parsed and keeps the repo free of the character. |
| 2026-10-27 | The governed arm's one miss (GQ-MARGIN-03, a rate instead of the amount, caused by `gross_margin`'s `agent_notes`) stays in the results; changing the note is follow-up work | Changing it mid-run would have made the result look better than what was measured. |
| 2026-10-27 | The raw SQL server sets `enable_external_access = false`; the claude-code provider strips `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the agent's environment | Found in a security check before merge: DuckDB's `read_text`, `read_csv` and `glob` let a read-only SELECT read any file on the machine (credentials could have reached committed traces), and an API key in the environment could turn subscription runs into per-token billing. Both are tested. |
| 2026-10-27 | The agent eval grades with `run_golden.check()`; scores are pass, value and caveats; failures (timeout, harness error, MCP not connected, no answer, refusal, wrong model) go to `errors.jsonl`, never into the score | One definition of correct for agents and the semantic layer; a broken run must not read as a wrong answer. |
| 2026-10-27 | Claude Code runs from an empty temp folder with `CLAUDE_CODE_DISABLE_CLAUDE_MDS`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`, `--setting-sources project`, `--tools ""`, `--strict-mcp-config`; requires Claude Code 2.1.221+; the probe checks the agent's tools from the init event | `--bare` only accepts an API key. Before 2.1.221 `-p` does not wait for MCP servers, so the agent ran with no tools (found by the probe on 2.1.156; the owner updated to 2.1.311). Claude Code still injects its own current date, so every question carries "as of 2026-09-15". |
| 2026-10-27 | On Windows the harness calls the native `claude.exe` behind npm's `claude.cmd` | A batch shim cuts arguments at newlines and mangles quotes; the first probe ran with none of its flags. |
| 2026-10-27 | v0.2 builds its own thin MCP server on the official `mcp` SDK (2.3.0) instead of `dbt-mcp` | `dbt-mcp`'s semantic layer tools need the dbt platform (`DBT_HOST`, `DBT_TOKEN`, `DBT_PROD_ENV_ID`; "works without dbt platform: no") and it needs Python 3.12+; locally it only offers dbt CLI tools, which would let an agent compute metrics in SQL. |
| 2026-10-27 | `mcp_server/`, not SPEC's `mcp/` | A top-level `mcp` folder can shadow the `mcp` SDK package on `sys.path`. |
| 2026-10-27 | MetricFlow readers open DuckDB with `access_mode: READ_ONLY` (profile `config_options` from `GROUNDRULES_DUCKDB_ACCESS`, set by `SemanticLayer`); direct connections pass the same config | DuckDB allows one read-write process, so several MCP servers (one per agent session) and the tests' stdio servers could not share the file. In one process every connection must carry the same config. `dbt build` keeps the default and writes. |
| 2026-10-27 | `query_metric` reuses `run_golden.answer()`; codes are checked against the dimensions before querying | One code path for agents and golden questions. An unknown code would otherwise return 0 for an additive metric. |
| 2026-10-27 | Eval runs on Claude Code headless (the owner's subscription, Sonnet); an `anthropic-api` provider is written but not run until there is an API key | The Claude API is billed separately from a subscription; the owner has no key. `--bare` only accepts an API key, so the headless run keeps the agent's context clean another way and checks it with a probe. |
| 2026-10-26 | CI is one GitHub Actions job with one step per promise, each calling the same `make` target people run locally; actions pinned by commit SHA to releases at least two weeks old; uv pinned to 0.11.14 | A red step names the broken promise; local and CI cannot drift apart. The newest setup-uv was four days old, so the release before it is used. |
| 2026-10-26 | Overdue recertification warns on pull requests; a weekly scheduled run adds `--fail-on-stale` | Owner's choice: one late metric should not block every team's pull request, but its owner must hear about it. |
| 2026-10-26 | `make check-v2` parses with dbt's v2 parser into `target_v2/` | The v2 parser overwrites `target/`; one target keeps that knowledge in one place. |
| 2026-10-26 | Release in its own pull request after CI is green on main: CHANGELOG `[0.1.0]`, pyproject and `uv.lock` to 0.1.0, then the tag | Owner's choice: the release is only declared once a clean Linux machine has run everything. |
| 2026-10-26 | `CHANGELOG.md` has two parts: Definitions (for readers of the numbers) and Repository (Keep a Changelog, `[Unreleased]` until v0.1.0 is tagged after CI); the lint fails when a governed metric's current version has no Definitions entry | Owner's choice. SPEC asked for a definitions changelog kept by hand; the check makes "by hand" safe. The baseline records versions as certified on 2026-09-10 and invents no earlier history. |
| 2026-10-26 | Apache-2.0 `LICENSE`, copied verbatim from an installed package's copy with the appendix placeholders left as in the original | Owner's choice; SPEC listed it but the file did not exist. Copying avoids retyping legal text. |
| 2026-10-26 | The README does not link the Substack article | Owner's choice; the README stands on its own. |
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


## Session log
One entry per working session. Format:

```
### YYYY-MM-DD
- Done: what was built or changed
- Verified: which commands ran green
- Next: the very next action
- Notes: anything surprising, worked around, or worth knowing next time
```

### 2026-10-30 (use-case guide)
- Done: `GUIDE.md` (nine use cases with who, steps and done-when, and a table mapping every playbook and adoption page to its use cases), `playbook/a-new-metric.md`, "Where else the rules hide" in the golden questions page, pointers from README, `adoption/README.md` and `playbook/README.md`, a docs test that every playbook and adoption page is linked from the guide
- Verified: every behavior the new pages describe read against the code (the MCP server refuses draft metrics, the registry lists them, the lint asks a draft for its CODEOWNERS entry and CHANGELOG entry and fails a link to a record still proposed, golden questions are required for certified metrics only); summaries of other pages checked against those pages; docs tests, lint, `make test`
- Next: nothing planned
- Notes: the owner asked for the guide after asking how to run two situations (extracting the rules on joining a company, and a new metric for a new dashboard); the second had no page until now.

### 2026-10-29 (release 0.3.0)
- Done: CHANGELOG `[0.3.0]` with the PR behind each entry, version 0.3.0 in `pyproject.toml` and `uv.lock`, v0.3 checked
- Verified: lint 0/0, golden 31/31 and 8/8, `make test` on the release branch
- Next: the owner tags v0.3.0 and publishes the GitHub release; nothing further is planned
- Notes: the docs PR was #25.

### 2026-10-29 (step 20, docs)
- Done: README section on actions with the v0.3.0 results, an Actions row in "What you get", the route table in the example company, repo map, "not an automation engine", roadmap; `adoption/actions.md` (when to start, picking the first action, the six pieces and who signs each, staged rollout, what to replace, prompt against contract, where the hours go); `playbook/approving-proposals.md` (daily decisions, stale proposals, the monthly look at rejections, refusals); index rows; SPEC status
- Verified: every number in the new pages read back from `agent_eval/results/v0.3.0/summary.md` and the step 16 to 19 records; docs tests (links, make targets, indexes), lint 0/0, `make test`
- Next: the release PR (`release-0.3.0`): CHANGELOG `[0.3.0]`, version 0.3.0 in `pyproject.toml` and `uv.lock`, PROGRESS; then the tag and the release notes
- Notes: no hour estimates were added for actions; the cost section names who spends the time, not how much, until a company measures its own.

### 2026-10-29 (step 19, run)
- Done: probes of both action arms, a pilot (AQ-TRANSFER-03 and 05 x 1 rep x 2 arms) resumed to the full run (8 questions x 3 reps x 2 arms), evidence copied to `agent_eval/results/v0.3.0/` (results, traces, meta with a note on the pilot and the uncommitted code; the per-run DuckDB files stay in `runs/`), agents guide and SPEC with the numbers
- Verified: 48 graded runs, no errors, no duplicate (question, rep); actions 24/24 correct and right reason 12/12; raw_actions 21/24 correct, 9/12 right reason, 0 unsafe filings on either arm; every miss read in the results: all count short-dated stock (DR-001); traces scanned for personal data and the em dash
- Next: step 20, docs and release 0.3.0, starting in plan mode
- Notes: usage went from 0% after the reset to 3% (probes, pilot), 5% (actions arm, about 0.1% a run) and then the raw_actions arm, about four times the tokens per run. The unguarded agent filed nothing when unsure rather than something wrong, so "safe" did not separate the arms; "correct" and "right reason" did.

### 2026-10-29 (step 19, built)
- Done: 8 action golden questions with expected proposals frozen from the reference, `golden/run_actions.py` in `make golden`, lint checks and a registry column for them, the control arm `mcp_server/raw_actions.py`, action arms and graded filings in the agent eval (prompt with DR-012's rules, per-run database, correct, safe, reason), an arm-aware probe, 17 new tests
- Verified: action questions 8/8 against the engine; scripted agents: an oracle scores 100% on all three, a carton to NW001 is wrong and unsafe, answering right without filing fails the proposal questions; lint 0/0, golden 31/31 plus 8/8
- Next: on the owner's "Run eval": probe both action arms, pilot 2 questions x 1 rep x 2 arms, report usage per run, then the full run on the owner's go
- Notes: usage was 74% to 76% when this was built; the real run waits for the reset.

### 2026-10-29 (step 18)
- Done: `actions/approvers.yml` with its lint checks and CODEOWNERS entry, decisions and an append-only audit log in `mcp_server/shadow.py`, a stand-in ERP in `mcp_server/erp.py`, `mcp_server/approvals.py` with `make proposals`, `make approve`, `make reject`, 9 approval tests, 4 lint tests, the actions README walk-through
- Verified: by hand on scratch files, a stranger was refused (and logged), a planner's approval wrote one ERP request (TRQ-..., 2 boxes of 100025 from NW003 to NW014, lots with 90 days or more), a second approval changed nothing, a rejection kept its reason, `show` printed the history; tests cover the crash between the two writes and the three ways a proposal goes stale; lint 0/0, golden 31/31
- Next: step 19, action golden questions and the agent eval, starting in plan mode, with usage measured first
- Notes: `at` is a keyword in DuckDB, so the audit timestamp column is `logged_at`.

### 2026-10-29 (step 17)
- Done: `mcp_server/transfers.py` (engine under the contract, version and cover guards, reasons, simulation), `mcp_server/shadow.py` (shadow table, idempotent filing), `mcp_server/actions.py` (five tools), `make mcp-server-actions`, `var/` ignored, 15 tests, an agents guide section
- Verified: the engine's 108 proposals equal the raw reference field by field; reasons 66 no donor in reach, 35 over the 60-day cap, 2 donors already promised; the what-ifs fail on exactly the expected rule; an agent session over stdio files NW014 / 100025 (2 boxes from NW003, partial) into a temp shadow file and nothing else; lint 0/0, golden 31/31
- Next: step 18, approval, write-back to the fake ERP table and the audit log, starting in plan mode
- Notes: the semantic layer and the reference agree on every store-SKU with sales (4,388) for stock, pace and cover, so the engine needs no correction for either side.

### 2026-10-29 (fix: `days_of_cover` v2)
- Done: `coalesce(available_stock, 0)` in `days_of_cover`, version 2, GQ-COVER-04 (NW001, SKU 100125: 0 days) linked from DR-010, the transfer action pinned to v2, the Power BI tag, CHANGELOG, registry, a semantic server test
- Verified: before the pin was bumped the lint failed on exactly four things (the action's pin, the changelog, the Power BI tag, the registry); after, 0 errors 0 warnings with 31 golden questions; golden 31/31 with no other expected value changed; no 0 or empty cover at chain, store, district, category or store-category level, so only store-SKU answers move
- Next: step 17 on a fresh branch once this is merged
- Notes: the golden runner had hidden the same gap for `available_stock` alone (it falls back to 0 when no row comes back), so only the derived metric showed it.

### 2026-10-29 (step 16)
- Done: DR-012 with worked examples from real rows, `actions/propose_transfer.yml` and `actions/README.md`, `linked_actions` in the DR template, action contracts loaded by `governance/repo.py`, `check_actions` in the lint (owner and approver groups, accepted decision listing the action, certified metrics at their pinned version, building blocks inside a pinned metric, models with enforced contracts, consistent rules), action files in the CODEOWNERS and changelog checks, an Actions table in the registry, `raw_routes` and the purchase unit in the reference views, `transfer_candidates.sql` and `Reference.transfer_candidates()`, 10 lint tests and 9 reference tests
- Verified: lint 0 errors 0 warnings (7 metrics, 1 action, 12 records); golden 30/30, expected files untouched; `make test` 250 passed; 108 proposals at 2026-09-15, 28 partial, 94 in boxes and 14 in cartons; every number in DR-012's examples matches the semantic layer (`available_stock`, `days_of_cover`) and `fct_store_routes`
- Next: step 17, proposals through an MCP tool, the simulation and the shadow table, starting in plan mode
- Notes: `days_of_cover` v1 returns no value for a store-SKU that has run out and still sells (NW001 SKU 100125, NW004 SKU 100051), where DR-010 gives 0 days. Step 16 does not change the metric; step 17 must not read "no value" as "no sales", and the owner should decide whether to fix the metric (a version bump) first.

### 2026-10-29 (step 15)
- Done: invented city geography and `logistics/store_routes.csv` in the generator, logistics source with freshness, `stg_logistics__store_routes` with a unit test, `fct_store_routes` with an enforced contract, data tests and a plausibility test, CODEOWNERS entry, 7 tests
- Verified: 376 existing extract files byte-identical, one file added (789 rows, 33 re-sent); golden expected files changed only their fingerprint line; `make build` 111 nodes, freshness pass; the mart has 756 routes (28 x 27), 246 under 30 minutes, none for NW029 or NW030; the longest same-district drive (33 min, Riverside across the river) is longer than the shortest cross-district one (5.6 min)
- Next: step 16, the action contract and DR-012, starting in plan mode
- Notes: the first version re-sent some routes after the extract time; the resend window now ends before 23:00 UTC on the extract night.

### 2026-10-29 (follow-up: gross margin agent note)
- Done: rewrote `gross_margin`'s `agent_notes`, a test that the amount is the default, rerun of the three margin questions, evidence in `agent_eval/results/followup-margin/`
- Verified: 9 of 9 correct (GQ-MARGIN-03 was 2 of 3 in v0.2.0), 0 errors, 89 seconds; lint 0/0; registry unchanged
- Next: v0.3, step 15 (logistics data), starting in plan mode
- Notes: one rerun explained "The question asks for margin, not a rate, so I report the VND amount", the note doing its job.

### 2026-10-27 (step 14)
- Done: probe, pilot (4 questions, one per kind, both arms) reviewed by the owner, full run of 30 questions x 3 reps x 2 arms on Sonnet 5.5 through Claude Code 2.1.311, results and traces in `agent_eval/results/v0.2.0/`, summary with token totals and API-equivalent cost and order-independent intervals, README and agents guide updated
- Verified: 180 graded answers, no errors, no duplicate (question, rep), every row with model, usage, latency and grade; governed 89/90 correct (99%, 97% to 100%), raw SQL 7/90 (8%, 0% to 18%); right number 99% versus 13%; raw SQL 0% on conflict, caveat and deprecated questions; API-equivalent cost $1.37 (governed) and $2.84 (raw SQL), not billed on the subscription; results scanned for personal data and the em dash
- Next: release 0.2.0 (separate PR), then follow-up: tighten `gross_margin`'s `agent_notes` so "margin" without "rate" means the amount, and rerun GQ-MARGIN-03
- Notes: usage went from 53% to 72% over the probe, pilot and full run (the conversation itself counted too). Latency rose from about 24 s per answer in the pilot to about 40 s during the full run, from load, not from the harness. The raw SQL agent quoted decision record numbers it found in column descriptions, yet still missed the rules.

### 2026-10-27 (step 13)
- Done: `agent_eval/` (cases from the golden questions, one prompt and answer schema for both arms, grading through `run_golden.check()`, Claude Code and Claude API providers, resumable runner with traces and failure classes, probe, summary with bootstrap intervals), optional `eval-api` dependency group, `make agent-eval`, `agent-eval-probe`, `agent-eval-summary`, 13 tests with a recorded Claude Code stream
- Verified: oracle 100%, null and constant 0%, timeouts go to errors and are retried on resume; probe passes on Claude Code 2.1.311 (only the four MCP tools, no CLAUDE.md, memory or skills); one real semantic run of GQ-SELL-01 passed (1.117, five tool calls, 35 s); one real raw SQL run failed (0.556: the agent invented "units sold / (opening stock + units received)" and left out transfers); the API provider imports without `anthropic` and refuses to run without its group
- Security check before merge: no secrets in the tree or the history; the raw SQL server could read local files and the provider passed API credentials through, both fixed and tested.
- Next: step 14: pilot for the owner's review, then the full run (30 questions x 3 reps x 2 arms on Sonnet)
- Notes: five headless calls were used, two more than planned: the first ran through npm's `claude.cmd` and lost every flag, the second showed Claude Code 2.1.156 does not wait for MCP servers. The anthropic-api provider is untested by the owner's decision. Claude Code also uses a small model for background work; the served-model check reads the main model from the init event.

### 2026-10-27 (step 12)
- Done: `mcp_server/semantic.py` (list, describe, find values, query; refusals; caveats; null stays null), `mcp_server/raw_sql.py` (read-only, one SELECT, 200-row cap), read-only warehouse access for MetricFlow readers, `make mcp-server` and `make mcp-server-raw`, `adoption/agents.md`, 17 tests including a stdio round trip per server
- Verified: answers match GQ-SELL-01, GQ-SELL-04 (null with `pos_sync_lag:NW030`), GQ-STOCK-01 (48) and GQ-POS-04; `revenue_v1` refused with `net_revenue`; `units_sold` refused with the certified list; a name instead of a code is explained, not answered; raw SQL rejects writes and multiple statements; a stdio round trip takes about 12 seconds including the MetricFlow load
- Next: step 13, the agent eval harness
- Notes: `dbt-mcp` was checked against its docs before writing anything. mcp 2.x renamed FastMCP to MCPServer and already diverts stray stdout to stderr while serving; MetricFlow loads on the first call so nothing it prints reaches the protocol. The 70ml saline spray is named "Sodium chloride 0.9% nasal spray 70ml", a realistic case for `find_values` (the question also gives the code).

### 2026-10-26 (step 11 and release 0.1.0)
- Done: `.github/workflows/governance.yml` (locked install, data, build, lint as of today with the result in the job summary, registry diff, affected metrics on PRs, golden with the JUnit report as an artifact, export, pytest, both demos with a clean-tree check, v2 parser; weekly run with `--fail-on-stale`), `make check-v2`, CI badge, branch protection guidance in the adoption guide; release branch with CHANGELOG `[0.1.0]` and version 0.1.0
- Verified: actionlint passes; every step run locally in order; a version bump without `make registry` makes the registry step exit 1 and the lint fail; GitHub Actions green on PR #12 (run 40357479803) and on main (run 40357875267, 1 minute 54 seconds: 185 pytest including the generator checksum on Ubuntu)
- Next: owner checks the last definition-of-done item (real company names), turns on branch protection, merges the release PR and tags v0.1.0. v0.2 waits for the owner
- Notes: the suite runs faster on the Linux runner (pytest 31 seconds) than on this Windows laptop (99 seconds). Editing `registry.md` by hand is not the failure case to test, because `make registry` rewrites it; the real case is a definition changed without regenerating it.

### 2026-10-26 (step 10)
- Done: `README.md` (problem, four homes, quickstart, three demos with real output, example company, repo map, adoption, what this is not, roadmap), `CHANGELOG.md` (Definitions and Repository), `LICENSE` (Apache-2.0), `check_changelog` in the lint, README and CHANGELOG covered by the docs test, SPEC goal 4 and README item corrected
- Verified: fresh clone of `main`: `make setup && make data && make build && make test` exit 0 in 289 seconds (uv cache warm, so a new machine adds the dependency download); every number in the README taken from `make demo-conflict` and `make demo-drift` output; bumping `gross_margin` to v2 without an entry fails the changelog check; `make test` green; no em dash
- Next: step 11, starting in plan mode: CI (lint with the real date, golden, pytest, registry diff, v2 parser with its own target path), then tag v0.1.0
- Notes: the fresh clone's golden run took 24 seconds against 10 on the warm working copy; first runs warm up MetricFlow and DuckDB.

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