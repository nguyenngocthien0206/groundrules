# Warehouses

The demo runs on DuckDB so anyone can clone it and run it on a laptop in a
few minutes. Your company runs Snowflake, BigQuery, Databricks or Postgres.
This page says exactly what changes when you move, including the parts that
are more than a profile switch.

## What changes, all of it
| # | What | Why | Effort |
| --- | --- | --- | --- |
| 1 | `profiles.yml` | the connection | copy a block from `dbt/profiles.example.yml` and install the adapter |
| 2 | Source definitions (`dbt/models/staging/*/_*__sources.yml`) | locally the raw extracts are files read through `external_location`; on a warehouse they are tables your loader fills | replace `external_location` with `database` and `schema` |
| 3 | The two returns staging models | the returns API sends nested JSON (the store as an object, the lines as an array); DuckDB reads it as a struct and a list | depends on how your loader lands JSON (below) |
| 4 | The POS file name column | POS vendor A's staging keeps the first upload of each line by file name; DuckDB adds `filename` when it reads the files | make your loader's file name column arrive as `filename`, or rename it in the two POS staging models |
| 5 | `qualify`, on Postgres only | POS vendor A's deduplication uses `qualify`; Snowflake, BigQuery and Databricks support it, Postgres does not | rewrite as a subquery on `row_number()` |
| 6 | `golden/reference/raw.sql` | the reference reads the extract files with `read_csv` and `read_json` | read your raw tables instead (see [Existing dbt project](existing-dbt-project.md)) |
| 7 | Source freshness `loaded_at_field` | the demo adds an offset so freshness is measured as of the extract time | use the plain timestamp column |

Nothing else changes. The intermediate models, the marts, the time spine and
every business rule in the semantic YAML stay as they are: staging parses
dates with standard SQL and dbt's cross-database macros (`dbt.concat`,
`dbt.dateadd`), the marts are plain SQL, and MetricFlow compiles the
semantic layer for whichever adapter you use. The governance lint, the
registry and the golden runner read dbt's manifest and talk to MetricFlow,
so they do not care which warehouse is underneath.

All of the changes sit in sources and staging, which is where they belong:
staging exists to absorb how data arrives. If a warehouse move ever needs a
change in a mart or a metric, treat that as a smell and look for the
staging model that should have absorbed it.

## Source definitions
Locally, a source looks like this:

```yaml
sources:
  - name: erp
    config:
      meta:
        external_location: "read_csv('.../erp/{name}.csv', header = true, all_varchar = true)"
```

On a warehouse, drop the `meta` block and say where the loader writes:

```yaml
sources:
  - name: erp
    database: raw          # Snowflake database, BigQuery project, Databricks catalog
    schema: erp_nightly    # where your loader lands the ERP extract
```

The column names stay as the source system sends them (UPPER_SNAKE for the
ERP, Vietnamese headers for POS vendor B), because staging is written
against those. If your loader renames columns, adjust staging, not the
marts.

The demo reads every column as text (`all_varchar`) so that staging does
all the typing. Most loaders also land text or loosely typed columns, so
the casts in staging still apply.

## The returns models
`stg_returns__returns.sql` reads `store.code`, and
`stg_returns__return_lines.sql` unnests the `lines` array with DuckDB's
`unnest` and `generate_subscripts`.

Most loaders (Fivetran, Airbyte, dlt and similar) flatten a nested object
into columns (for example `store_code`) and split a nested array into its
own child table, with the parent key and a position column. If yours does,
both models become plain selects from those tables. That is the cleanest
option.

If the JSON lands in a single JSON or variant column instead, use your
warehouse's syntax. These sketches show the shape of the lines model; check
the column names and types against what your loader writes:

```sql
-- Snowflake
select r.return_id, l.index + 1 as line_no, l.value:sku::string as sku_code, ...
from {{ source('returns', 'returns') }} r, lateral flatten(input => r.lines) l

-- BigQuery
select r.return_id, pos + 1 as line_no, line.sku as sku_code, ...
from {{ source('returns', 'returns') }} r, unnest(r.lines) as line with offset pos

-- Databricks
select r.return_id, p.pos + 1 as line_no, p.line.sku as sku_code, ...
from {{ source('returns', 'returns') }} r
lateral view posexplode(r.lines) p as pos, line

-- Postgres (lines as jsonb)
select r.return_id, l.ordinality as line_no, l.value->>'sku' as sku_code, ...
from {{ source('returns', 'returns') }} r, jsonb_array_elements(r.lines) with ordinality l
```

The store object follows the same idea: `store:code::string` on Snowflake,
`store.code` on BigQuery and Databricks, `store->>'code'` on Postgres.

After the change, `make build` runs the data tests on these models, and the
golden questions on net revenue and gross margin (which subtract refunds)
tell you whether the returns still land on the right day and store.

## What we have and have not tested
DuckDB is tested on every run. The other warehouses are not run in this
repo's CI: the profile blocks, the source changes and the sketches above
are written from each warehouse's documentation and dbt adapter
conventions. If you switch, expect a short round of fixes in staging, run
`make build` and `make golden`, and treat a passing golden suite as the
sign that your numbers still follow the demo's rules.

That last point is the real reason to keep the golden questions through a
migration: a warehouse move that changes a number by a rounding difference
or a time zone is exactly the kind of change nobody notices until a
quarter-end report is wrong.
