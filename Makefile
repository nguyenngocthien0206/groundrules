.PHONY: setup data data-manifest build metrics export-osi test

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

test:
	uv run pytest
