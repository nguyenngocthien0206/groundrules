# CLAUDE.md

## Project
Groundrules (repo: `groundrules`): an open-source reference implementation showing how a real data team turns tacit knowledge into something an AI agent can rely on. Companies should be able to read it, recognize their own mess in it, and adopt it on their existing dbt project and warehouse. The full spec is in `SPEC.md`. Read it before starting any task. Build status lives in `PROGRESS.md`.

Core idea: agents remove the arrangement (an analyst in the loop) that made it safe to leave business rules unwritten. So:
- the "what" lives in the semantic model (`dbt/models/semantic/`)
- the "why" lives in decision records linked to it (`decisions/`)
- the analyst's judgment lives in golden questions run as tests (`golden/`)
- ownership is enforced by Git itself (`CODEOWNERS`, PR template, CI)

## Stack
- Python 3.11+, dbt-core, dbt-duckdb (local demo), MetricFlow (dbt Semantic Layer, open source), PyYAML, pytest
- Pin exact versions in `pyproject.toml`. Record the versions you verified in `PROGRESS.md`. The dbt line is dbt-core 1.12 with dbt-duckdb 1.11 (decided in step 2, see `PROGRESS.md`); the project also parses with `dbt parse --use-v2-parser`.
- The warehouse is swappable: the same project must run on Snowflake, BigQuery, Databricks or Postgres by changing only `profiles.yml`.
- Optional dashboard: Power BI Desktop (Windows only, opened by hand) reading Parquet exports of saved queries. `pyarrow` for writing Parquet is pending approval.
- Optional extras (phase 2 and later, never required for the core demo): MCP access built on `dbt-mcp`, and an agent eval harness.
- Ask before adding any dependency not listed here.
- `make` needs WSL or Git Bash on Windows.

## Commands
- `make setup`: install dependencies
- `make data`: generate synthetic source data
- `make build`: dbt build (staging, marts, unit tests, data tests) + source freshness
- `make test`: governance lint + golden questions + pytest
- `make lint`: `dbt parse`, then governance checks on `target/manifest.json` (default `--today` is the snapshot date 2026-09-15)
- `make dashboard-data`: run saved queries through MetricFlow and write Parquet for the Power BI report (optional)
- `make demo-drift`: change a rule silently, show golden questions failing, restore
- `make demo-conflict`: show three legacy definitions of net revenue disagreeing, then the certified one

## Rules that must never be broken
- Realistic but synthetic. Data must look like real ERP and POS extracts (messy, late, duplicated), but every name, number and rule is invented with a fixed seed. Never use real company names, store names, people's names or real internal business rules.
- Build on what companies already run (dbt, MetricFlow, Open Semantic Interchange). Do not write a custom semantic engine or a competing YAML standard.
- Golden question expected values come from an independent reference computation over source tables (`golden/reference/`), never from the semantic layer code path. Otherwise the tests are circular.
- Every metric has an owner (its dbt group), a version, a certification state and a linked decision record. CI enforces this.
- Business thresholds and exclusions live in the semantic YAML (`dbt/models/semantic/`), never in mart SQL. Marts expose neutral facts such as `days_to_expiry`.
- Use what dbt already provides (groups, contracts, exposures, unit tests, source freshness, saved queries) before adding custom `meta` fields. `meta` holds only what dbt has no field for.
- Dashboards never redefine a certified metric. They show saved query exports at the grain they were exported, and lint checks the Power BI TMDL for this.
- When unsure whether a tool supports something (for example MetricFlow on DuckDB, or OSI export), verify it by running it or reading its docs before building on it, and tell me what you found.

## Writing style for README and all docs
- Plain, direct English. Short paragraphs. Written for a data lead deciding whether to adopt this.
- Weave a technical takeaway and a team/management takeaway into each section, rather than splitting them into separate sections.
- Never use the em dash character anywhere.

## Workflow
- At the start of every session, read `PROGRESS.md` and continue from its "Current step". Do not redo ticked steps.
- At the end of every build step, update `PROGRESS.md`: tick the step, update "Current status", add a session log entry, and record any implementation decisions or open questions.
- If you are blocked or need a decision from me, add it under "Open questions and blockers" and stop to ask, rather than guessing.
- Start every phase in plan mode and show the plan and file list before writing code.
- Build in the order given in `SPEC.md`. After each step, run it and confirm it works before moving on.
- Keep `make build && make test` green at the end of every step.
- Small commits with clear messages, one logical change each.