.PHONY: setup data data-manifest build test

DATA_DIR := example/data

setup:
	uv sync

data:
	uv run python example/generate.py --out $(DATA_DIR)

# Re-freeze the data fingerprint after an intended generator change.
data-manifest: data
	cp $(DATA_DIR)/_manifest.json tests/fixtures/expected_manifest.json

build:
	@echo "Nothing to build yet: the dbt project arrives in build step 2."

test:
	uv run pytest
