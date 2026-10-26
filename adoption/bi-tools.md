# BI tools

Your company already has a BI tool, and that is where most people meet a
number. The risk is not the tool; it is that the tool quietly becomes a
second place where metrics are defined. Someone drags a column, picks
"sum", and a ratio or a stock position is now computed in a way no decision
record describes. This page covers how to keep that from happening.

## The pattern used here: export, then display
`dashboards/` in this repo connects Power BI Desktop to the semantic layer
without any connector:

1. Every slice the report shows is a dbt **saved query**, in a file owned by
   the metric's team.
2. `make dashboard-data` runs each saved query through MetricFlow and writes
   Parquet, with `as_of`, caveats and the certified version of each metric.
3. The Power BI model only **displays** those numbers: each measure is
   `SELECTEDVALUE` of one exported column, metric columns cannot be summed,
   and totals stay blank because a total nobody exported is a total nobody
   certified.
4. The governance lint reads the Power BI files (TMDL, plain text in Git)
   and fails on anything that computes.
5. A test compares the exports with the golden questions' expected values.

Ratios and stock positions are exported at exactly the grain the visual
shows. Summing `sell_through_rate` across stores or `available_stock`
across days in the BI tool gives a wrong number with no error, which is why
the BI layer is not allowed to add anything up.

## When to move past exports
The export pattern exists because open-source MetricFlow has no server for
a BI tool to talk to. If your company is on the dbt platform, its Semantic
Layer offers official integrations (Power BI, Tableau, Google Sheets and
others) and scheduled exports. Use them: they query the same definitions
live, with no export step to keep running. Keep everything else in this
repo, because none of it depends on how the BI tool connects: owners,
decision records, golden questions and the lint.

## Before trusting a tool that "reads the semantic layer"
Several BI tools now read MetricFlow or dbt metrics directly. Some support
only part of the spec and skip the rest with a warning, not an error. The
hard parts are exactly the metrics that matter most:

- **Semi-additive metrics**, such as stock on hand, which must not be summed
  over days (`non_additive_dimension`).
- **Ratios across semantic models**, such as sell-through (units sold from
  sales, units received from goods received).
- **Cumulative and offset windows**, such as days of cover's 28-day pace
  ending the day before the snapshot.
- **Filters inside metrics**, such as the 90-day rule in available stock.

The test is cheap: run your golden questions through the tool and compare.
If a tool answers GQ-STOCK-01 with 49 instead of 48, it dropped the 90-day
filter, and you found out before a store manager did.

## Lessons from opening this project in Power BI Desktop
The first real open and save in Power BI Desktop found four things no
schema check could. Each is now a lint check, so a careless save cannot
reach the main branch:

1. **Measure names must be unique across the whole model**, not per table.
   With three tables each holding a "Net revenue" measure, the project would
   not open. Measures are now named `<metric> by <slice>`, and visuals show
   the short label.
2. **Power BI resets `summarizeBy` on refresh.** After one save, all 12
   metric columns had gone from `none` to `sum`. A column keeps `none` only
   with the annotation `SummarizationSetBy = User`.
3. **Auto date/time** added 16 hidden date tables and relationships, one per
   date column. Turn it off in the file's options.
4. **Saving writes the saver's local path** into the export folder
   parameter. The committed file keeps a placeholder; each person sets the
   path once after cloning and does not commit it.

The lesson is general: a BI tool rewrites its own files, and a save is the
easiest way for a metric to be redefined without anyone deciding to. Keep
the BI definition as text in Git, and let checks, not memory, guard it.

## Other BI tools
The same pattern works for any tool that reads Parquet or a table:
- Point it at the exported files, or load them into a reporting schema.
- Build visuals at the exported grain, with no aggregation on metric
  columns. Most tools have a "don't summarize" or "dimension" setting for
  this.
- If the tool stores its definitions as text (LookML, Tableau's `.twb`,
  Metabase serialization), add a lint check like the Power BI one for
  aggregations on metric columns. If it does not, review dashboards against
  the golden questions on a schedule instead.
