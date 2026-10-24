# PROGRESS

Living status of the build. Claude reads this at the start of every session and updates it at the end of every build step. Keep entries short. Newest first in every log.

## Current status
- Phase: v0.1 Core
- Current step: 1. Synthetic source extracts
- State: not started
- Last verified green: never (`make build && make test` not yet runnable)

## Build checklist (v0.1)
Tick a step only when it runs end to end and its checks pass.

- [ ] 1. Synthetic source extracts (`example/generate.py`) + checksum test
- [ ] 2. dbt staging + marts + unit tests + data tests + freshness
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

- dbt v2 (GA at dbt Summit 2026) or dbt-core 1.x? Decide in step 3 after checking that dbt-duckdb and MetricFlow run on it.
- Which semantic YAML spec does the chosen dbt version expect (top-level `semantic_models:` or the newer spec on the model)? Verify in step 3.
- Does MetricFlow's Python API, and `saved_queries`, work locally on DuckDB? Verify in step 3; the runner and the dashboard export depend on it.
- Do `groups` and `meta` under `config` work on metrics and semantic models in the chosen version? Verify in step 3.
- Approve `pyarrow` as a dependency for Parquet exports (step 8).
- Does Power BI Desktop's built-in Parquet connector read the local export files with no extra setup? Verify in step 8.
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

### 2026-10-24
- Done: reviewed the spec and updated CLAUDE.md, SPEC.md and PROGRESS.md (golden scoring for caveat and deprecated kinds, rule placement, missing source columns, lint `--today`, version pinning, reference independence, registry check, em dash check, dbt-native governance, VN pharmacy data realism, optional Power BI dashboard, `dbt-mcp` for v0.2)
- Verified: docs only, no code yet
- Next: step 1, synthetic source extracts
- Notes: SPEC sections were renumbered; the dashboard is section 13 and the definition of done is section 20