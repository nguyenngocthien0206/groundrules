.PHONY: setup data build test

DATA_DIR := example/data

setup:
	uv sync

data:
	uv run python example/generate.py --out $(DATA_DIR)

build:
	@echo "Nothing to build yet: the dbt project arrives in build step 2."

test:
	uv run pytest
