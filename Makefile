.PHONY: setup data data-manifest build metrics export-osi golden golden-freeze lint registry affected demo-conflict demo-drift test

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

# Demo 1: three legacy dashboards, three revenue numbers, one certified answer.
MONTH ?= 2026-08
demo-conflict:
	uv run python demos/conflict.py --month $(MONTH)

# Demo 2: change the 90-day rule to 60 silently; the golden questions catch it.
# The rule file is restored afterwards, even if a step fails.
demo-drift:
	uv run python demos/drift.py

test: lint golden
	uv run pytest
