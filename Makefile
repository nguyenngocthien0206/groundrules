.PHONY: setup data data-manifest build test

DATA_DIR := example/data
export DBT_SEND_ANONYMOUS_USAGE_STATS := false

setup:
	uv sync

data:
	uv run python example/generate.py --out $(DATA_DIR)

# Re-freeze the data fingerprint after an intended generator change.
data-manifest: data
	cp $(DATA_DIR)/_manifest.json tests/fixtures/expected_manifest.json

DBT := cd dbt && uv run dbt

build:
	$(DBT) build --profiles-dir .
	$(DBT) source freshness --profiles-dir .

test:
	uv run pytest
