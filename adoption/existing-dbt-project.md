# Bringing this into an existing dbt project

You do not need to start a new repository. Everything here is a few
folders next to your dbt project and a handful of dbt features you may
already use. This page says what to copy, what to adopt, and what to throw
away.

## What to copy
| Folder | What it gives you | What to change |
| --- | --- | --- |
| `decisions/` | the template, the index and the format the lint reads | delete DR-001 to DR-011, keep `TEMPLATE.md` and the README's "when to write one" |
| `golden/` | the question format, the runner, the freeze script, the shared MetricFlow client | replace the questions, expected files and reference SQL with your own |
| `governance/` | the lint, the registry generator, `affected.py` | `DBT_DIR` in `governance/repo.py` if your dbt project is not in `dbt/` |
| `.github/` | CODEOWNERS and the pull request template | your team handles; the CI workflow comes with this repo's CI step |
| `Makefile` targets | `golden`, `golden-freeze`, `lint`, `registry`, `affected` | paths, if your dbt project is not in `dbt/` |

The lint and the registry read the manifest dbt writes on `dbt parse`, so
they work whether your semantic models live in one folder or many: the
files that need an owner in CODEOWNERS are found from each metric's file
path in the manifest. The layout assumptions are few: the dbt project in
`dbt/` (one constant), decision records in `decisions/`, CODEOWNERS in
`.github/`, and the Power BI check, which only runs if
`dashboards/groundrules.SemanticModel/` exists.

## What to adopt in dbt, if you do not use it yet
This repo leans on dbt features instead of custom fields, so a company that
already uses them copies less:

- **Groups** for owners. One group per owning team, with the team's GitHub
  handle in `config.meta.github_team`. Every governed metric needs a group.
- **The semantic layer** (MetricFlow) in dbt's current YAML spec: semantic
  models on the model, simple metrics with their filters, derived metrics
  for ratios. Business thresholds go in these filters, not in mart SQL,
  so every rule sits in files CODEOWNERS protects.
- **Model contracts** on the marts behind certified metrics, enforced. A
  column type change then fails the build instead of silently changing a
  number.
- **Exposures** for the dashboards that matter, with `depends_on` naming
  the metrics or models they read. `make affected` follows them, and the
  registry lists them.
- **Saved queries**, if a BI tool reads exports (see [BI tools](bi-tools.md)).
- **Unit tests and source freshness**, which the golden questions do not
  replace: unit tests check SQL logic on fixed rows, golden questions check
  meaning on real data.

Each of these is worth having on its own, which makes the case to your team
easier than "adopt this framework".

## Point the reference at your raw data
`golden/reference/raw.sql` builds the reference's views from the extract
files with `read_csv` and `read_json`. In your project, those become your
raw tables, as the loader lands them, before any dbt model touches them.
The reference must not read your staging or mart models, or it is no longer
independent (`tests/test_golden.py` checks that here, and is worth keeping).

The reference runs on DuckDB in this repo. On a warehouse, you can either
run the same SQL through your warehouse's Python connector, or keep DuckDB
and read a sample of raw tables exported to Parquet. The second is cheaper
and fine for golden questions, which only need the rows they ask about.

## What to delete
- `example/`: the synthetic data generator.
- `legacy/` and `demos/`: the conflicting dashboards and the two demos. Keep
  them in a branch if you want to show the idea to your team first.
- `dashboards/`, if you do not use Power BI. If you use another BI tool,
  keep `dashboards/export.py` as a starting point.
- This repo's semantic models, marts and staging, obviously.

## The order that works
1. Groups and CODEOWNERS first: ownership costs nothing and settles who
   approves what.
2. Decision records for the numbers you start with.
3. Metrics and golden questions together, one metric at a time.
4. The lint in CI, as a warning for a week, then required.

Turning everything on in one pull request on a large project produces a
lint report nobody reads. One metric at a time produces a team that knows
what each check is for.
