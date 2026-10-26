.PHONY: setup data data-manifest build metrics export-osi golden golden-freeze test

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
# Review the diff of golden/expected.yml before committing it.
golden-freeze:
	uv run python golden/reference/freeze.py

test: golden
	uv run pytest
