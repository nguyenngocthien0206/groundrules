# PROGRESS

Living status of the build. Claude reads this at the start of every session and updates it at the end of every build step. Keep entries short. Newest first in every log.

## Current status
- Phase: v0.1 Core
- Current step: 3. Verify MetricFlow on DuckDB, then semantic models and metrics
- State: not started
- Last verified green: 2026-10-24 (`make build`: 80 dbt nodes, 1 expected warning, freshness pass; `make test`: 34 tests)

## Build checklist (v0.1)
Tick a step only when it runs end to end and its checks pass.

- [x] 1. Synthetic source extracts (`example/generate.py`) + checksum test
- [x] 2. dbt staging + marts + unit tests + data tests + freshness
- [ ] 3. Verify MetricFlow on DuckDB (versions, spec, Python API, saved queries), then semantic models and metrics
- [ ] 4. Decision records (DR-001 to DR-007 + TEMPLATE)
- [ ] 5. Reference computations + golden questions + runner
- [ ] 6. Governance lint, registry, groups, exposures, CODEOWNERS, PR template
- [ ] 7. Demos (`make demo-conflict`, `make demo-drift`)
- [ ] 8. Dashboard: saved queries, Parquet export, Power BI project, TMDL lint (optional)
- [ ] 9. Playbook + adoption guide
- [ ] 10. README + CHANGELOG
- [ ] 11. CI

## Definition of done (v0.1)
Copied from SPEC section 20. Tick when verified on a fresh clone.

- [ ] `make setup && make data && make build && make test` passes in under 10 minutes
- [ ] Generator checksum test passes on a second machine
- [ ] `make demo-conflict` prints four different net revenue numbers and names the DR
- [ ] `make demo-drift` fails golden questions for the right reason, then restores everything
- [ ] `make lint` fails clearly on: removed owner group, broken DR link, certified metric with no golden question, deprecated metric with no replacement, em dash
- [ ] `make lint` gives the same result on any calendar day with the default `--today`
- [ ] CI fails when `registry.md` is out of date
- [ ] (Optional dashboard) `make dashboard-data` matches golden expected values; Power BI report opens and refreshes on Windows (manual)
- [ ] Warehouse switch documented, needs no model changes
- [ ] No real company names or rules, no em dash character anywhere

## Later phases (locked until the owner says go)
- [ ] v0.2 Agent-ready: MCP server + agent eval harness
- [ ] v0.3 Actions: action contract, shadow table, approval, write-back, audit log

## Implementation decisions
Technical choices made during the build that are not already in SPEC.md. One line each: date, decision, why. If a decision changes the spec, say so and ask the owner first.

| Date | Decision | Why |
| --- | --- | --- |
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

- Which semantic YAML spec does the chosen dbt version expect (top-level `semantic_models:` or the newer spec on the model)? Verify in step 3.
- Does MetricFlow's Python API, and `saved_queries`, work locally on DuckDB? Verify in step 3; the runner and the dashboard export depend on it.
- Do `groups` and `meta` under `config` work on metrics and semantic models in the chosen version? Verify in step 3.
- Approve `pyarrow` as a dependency for Parquet exports (step 8).
- Does Power BI Desktop's built-in Parquet connector read the local export files with no extra setup? Verify in step 8.
- Do `dbt-mcp` semantic layer tools work against local MetricFlow, or only the dbt platform? Verify before v0.2.
- Cost method for `gross_margin`: POS lines carry no batch, so COGS needs a rule (weighted average cost per store and SKU, or FEFO). Needs a DR in step 4.
- Does `sell_through_rate` count stock received by transfer (`SOURCE_DOC` starting with `TRF`) as "received", or only supplier deliveries (`PO`)? Needs a DR in step 4.

## Session log
One entry per working session. Format:

```
### YYYY-MM-DD
- Done: what was built or changed
- Verified: which commands ran green
- Next: the very next action
- Notes: anything surprising, worked around, or worth knowing next time
```

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