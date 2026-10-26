"""Export the dashboard's saved queries to Parquet for Power BI.

Usage: python dashboards/export.py   (or `make dashboard-data`)

Each dbt saved query runs through MetricFlow and lands as one Parquet file in
dashboards/exports/, at exactly the grain the report shows. Every row says
which day it is as of and which lagging stores it depends on (DR-004), and
metric_versions.parquet says which certified version each number is. Monthly
rows also say how far their month's data goes, so the current month reads as
month to date, not as a bad month. Only certified metrics, and only months
inside the POS history, are exported. Power BI reads these files and adds
nothing up.
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "golden"))
sys.path.insert(0, str(ROOT / "governance"))

from run_golden import STOCK_METRICS, lag_caveats, store_sync_state  # noqa: E402
from semantic_client import DBT_DIR, SemanticLayer  # noqa: E402

EXPORTS = ROOT / "dashboards" / "exports"
SAVED_QUERY_FILES = ("saved_queries_finance.yml", "saved_queries_supply_chain.yml")

# MetricFlow's column names, renamed for the people reading the report.
RENAME = {
    "metric_time__month": "month",
    "store": "store_code",
    "store__store_name": "store_name",
    "store__district_code": "district_code",
    "store__district_name": "district",
    "sku__category_code": "category_code",
    "sku__category_name": "category",
}
DROP = {"metric_time__day"}  # stock slices are all read at the snapshot; `as_of` says so


def snapshot_date() -> date:
    project = yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text(encoding="utf-8"))
    return date.fromisoformat(project["vars"]["snapshot_date"])


def pos_window(sl: SemanticLayer, stores: list[dict]) -> tuple[date, date]:
    """First and last day of POS data in the chain. Lagging stores end earlier; caveats name them."""
    days = [r["metric_time__day"].date() for r in sl.query(["net_revenue"], ["metric_time__day"])]
    return min(days), max(s["data_through"] for s in stores)


def month_end(month: date) -> date:
    return (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def saved_queries() -> dict[str, list[str]]:
    """Saved query name -> metrics it exports, from the dbt manifest."""
    manifest = json.loads((DBT_DIR / "target" / "manifest.json").read_text(encoding="utf-8"))
    found = {}
    for sq in manifest["saved_queries"].values():
        if Path(sq["original_file_path"]).name in SAVED_QUERY_FILES:
            found[sq["name"]] = list(sq["query_params"]["metrics"])
    return dict(sorted(found.items()))


def row_caveats(row: dict, metrics: list[str], as_of: date, stores: list[dict]) -> str:
    """Lagging stores this row depends on, by the stores-and-days rule (DR-004)."""
    filters = {}
    if row.get("store_code"):
        filters["store"] = row["store_code"]
    if row.get("district_code"):
        filters["district"] = row["district_code"]
    if row.get("month"):
        filters["month"] = row["month"].strftime("%Y-%m")
    lagging = set()
    for metric in metrics:
        metric_filters = {k: v for k, v in filters.items() if not (metric in STOCK_METRICS and k == "month")}
        lagging |= {c.split(":", 1)[1] for c in lag_caveats(metric, metric_filters, as_of, stores)}
    return ", ".join(sorted(lagging))


def shape(name: str, rows: list[dict], metrics: list[str], as_of: date, stores: list[dict],
          window: tuple[date, date]) -> list[dict]:
    first, last = window
    shaped = []
    for raw in rows:
        row = {}
        for key, value in raw.items():
            if key in DROP:
                continue
            if isinstance(value, datetime):
                value = value.date()
            row[RENAME.get(key, key)] = value
        if "month" in row:
            if row["month"] < first:
                raise ValueError(
                    f"{name}: {row['month']:%Y-%m} starts before POS data begins on {first}; "
                    "start the saved query at the first full month"
                )
            row["data_through"] = min(month_end(row["month"]), last)
            row["is_month_to_date"] = month_end(row["month"]) > last
        row["as_of"] = as_of
        row["caveats"] = row_caveats(row, metrics, as_of, stores)
        shaped.append(row)
    keys = [k for k in ("month", "district_code", "category_code", "store_code") if shaped and k in shaped[0]]
    return sorted(shaped, key=lambda r: tuple(r[k] for k in keys))


def schema_for(rows: list[dict], metrics: list[str]) -> pa.Schema:
    fields = []
    for name in rows[0]:
        if name in metrics:
            fields.append(pa.field(name, pa.float64()))
        elif name in ("month", "data_through", "as_of"):
            fields.append(pa.field(name, pa.date32()))
        elif name == "is_month_to_date":
            fields.append(pa.field(name, pa.bool_()))
        else:
            fields.append(pa.field(name, pa.string()))
    return pa.schema(fields)


def export(sl: SemanticLayer | None = None) -> dict[str, int]:
    """Write every export; return rows per file."""
    sl = sl or SemanticLayer()
    as_of = snapshot_date()
    stores = store_sync_state(sl)
    window = pos_window(sl, stores)
    queries = saved_queries()
    exported_metrics = sorted({m for metrics in queries.values() for m in metrics})
    for metric in exported_metrics:
        status = sl.governance(metric).get("status")
        if status != "certified":
            raise ValueError(f"{metric} is {status or 'not governed'}: only certified metrics reach a dashboard")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, metrics in queries.items():
        rows = shape(name, sl.saved_query(name), metrics, as_of, stores, window)
        table = pa.Table.from_pylist(rows, schema=schema_for(rows, metrics))
        pq.write_table(table, EXPORTS / f"{name}.parquet")
        written[name] = len(rows)

    from repo import load  # the metric owner (dbt group) lives in manifest.json

    repo = load(with_text_files=False)
    versions = [
        {
            "metric": m,
            "label": repo.metrics[m].label,
            "version": int(repo.metrics[m].meta["version"]),
            "status": repo.metrics[m].meta["status"],
            "owner": repo.metrics[m].group,
            "decision": repo.metrics[m].meta["decision"],
            "as_of": as_of,
        }
        for m in exported_metrics
    ]
    pq.write_table(pa.Table.from_pylist(versions), EXPORTS / "metric_versions.parquet")
    written["metric_versions"] = len(versions)
    return written


def main() -> int:
    if not (DBT_DIR / "groundrules.duckdb").exists():
        print("No warehouse yet: run `make data && make build` first.")
        return 1
    for name, rows in export().items():
        print(f"  {name + '.parquet':<38}{rows:>5} rows")
    print(f"Exports in {EXPORTS.relative_to(ROOT)}. In Power BI, set the ExportFolder parameter to this folder's full path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
