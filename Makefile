.PHONY: setup data data-manifest build metrics export-osi golden golden-freeze lint registry affected dashboard-data mcp-server mcp-server-raw agent-eval agent-eval-probe agent-eval-summary demo-conflict demo-drift check-v2 test

DATA_DIR := example/data
export DBT_SEND_ANONYMOUS_USAGE_STATS := false
# MetricFlow's CLI prints emoji; without UTF-8 mode it fails on a Windows console.
export PYTHONUTF8 := 1

setup:
	uv sync

data:
	uv run python example/generate.py --out $(DATA_DIR)

# Re-freeze the data fingerprint after an intended generator change.
data-manifest: data
	cp $(DATA_DIR)/_manifest.json tests/fixtures/expected_manifest.json

DBT := cd dbt && uv run dbt
MF := cd dbt && uv run mf

build:
	$(DBT) build --profiles-dir .
	$(DBT) source freshness --profiles-dir .

# Check every metric against the warehouse and list the visible ones.
metrics:
	$(MF) validate-configs
	$(MF) list metrics

# dbt writes an Open Semantic Interchange document on every parse. Hidden
# building-block metrics are left out of it on purpose.
export-osi:
	$(DBT) parse --profiles-dir .
	@echo "OSI document: dbt/target/osi_document.json"

# Ask the semantic layer every golden question; fails on a wrong value or caveat.
golden:
	uv run python golden/run_golden.py

# Recompute expected answers from the reference SQL over the raw extracts.
# Review the diff of golden/expected/ before committing it.
golden-freeze:
	uv run python golden/reference/freeze.py

# Ownership, decision links, proof and hygiene. Pass a real date in CI:
#   make lint LINT_ARGS="--today 2027-01-04 --fail-on-stale"
LINT_ARGS ?=
lint:
	$(DBT) parse --profiles-dir . --quiet
	uv run python governance/lint.py $(LINT_ARGS)

# Regenerate the page a manager reads; the lint fails when it is stale.
registry:
	$(DBT) parse --profiles-dir . --quiet
	uv run python governance/registry.py

# Metrics and exposures touched since BASE, for the pull request template.
BASE ?= origin/main
affected:
	$(DBT) parse --profiles-dir . --quiet
	uv run python governance/affected.py --base $(BASE)

# Run the dashboard's saved queries through MetricFlow and write Parquet for
# Power BI (dashboards/exports/). Needs `make build`.
dashboard-data:
	uv run python dashboards/export.py

# MCP servers for agents, over stdio (see adoption/agents.md). Needs `make build`.
# The raw SQL one is the agent eval's control arm, not for production.
mcp-server:
	uv run python mcp_server/semantic.py

mcp-server-raw:
	uv run python mcp_server/raw_sql.py

# Agent eval: the golden questions through an agent connected to one arm
# (semantic or raw_sql). The claude-code provider runs on your Claude
# subscription and uses its usage limits; run the probe first.
#   make agent-eval ARM=raw_sql RUN=pilot CASES=GQ-SELL-01,GQ-REV-01 REPS=1
PROVIDER ?= claude-code
ARM ?= semantic
MODEL ?= sonnet
REPS ?= 3
CASES ?=
RUN ?= $(shell date +%Y%m%d)
agent-eval:
	uv run python agent_eval/run.py --provider $(PROVIDER) --arm $(ARM) --model $(MODEL) --reps $(REPS) --run-id $(RUN) $(if $(CASES),--cases $(CASES))

agent-eval-probe:
	uv run python agent_eval/run.py --provider $(PROVIDER) --model $(MODEL) --probe

agent-eval-summary:
	uv run python agent_eval/summary.py $(RUN)

# Demo 1: three legacy dashboards, three revenue numbers, one certified answer.
MONTH ?= 2026-08
demo-conflict:
	uv run python demos/conflict.py --month $(MONTH)

# Demo 2: change the 90-day rule to 60 silently; the golden questions catch it.
# The rule file is restored afterwards, even if a step fails.
demo-drift:
	uv run python demos/drift.py

# dbt v2's parser must keep parsing the project. It rewrites target/ (and
# writes `config: null`), so it gets a folder of its own.
check-v2:
	$(DBT) parse --use-v2-parser --profiles-dir . --target-path target_v2 --quiet

# The dashboard tests read the exports, so they are rebuilt first.
test: lint golden dashboard-data
	uv run pytest
