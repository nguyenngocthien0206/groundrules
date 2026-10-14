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
- The warehouse is swappable: the same project must run on Snowflake, BigQuery, Databricks or Postgres by changing only `profiles.yml`.
- Optional extras (phase 2 and later, never required for the core demo): an MCP server and an agent eval harness.
- Ask before adding any dependency not listed here.

## Commands
- `make setup`: install dependencies
- `make data`: generate synthetic source data
- `make build`: dbt build (staging, marts, data tests)
- `make test`: governance lint + golden questions + pytest
- `make lint`: governance checks only
- `make demo-drift`: change a rule silently, show golden questions failing, restore
- `make demo-conflict`: show three legacy definitions of net revenue disagreeing, then the certified one

## Rules that must never be broken
- Realistic but synthetic. Data must look like real ERP and POS extracts (messy, late, duplicated), but every name, number and rule is invented with a fixed seed. Never use real company names, store names, people's names or real internal business rules.
- Build on what companies already run (dbt, MetricFlow, Open Semantic Interchange). Do not write a custom semantic engine or a competing YAML standard.
- Golden question expected values come from an independent reference computation over source tables (`golden/reference/`), never from the semantic layer code path. Otherwise the tests are circular.
- Every metric has an owner, a version, a certification state and a linked decision record. CI enforces this.
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