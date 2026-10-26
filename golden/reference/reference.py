"""Run the reference SQL: the independent answer to each golden question.

Usage: python golden/reference/reference.py net_revenue month=2026-08 store=NW001

Reads only the raw extracts (see raw.sql), never the dbt marts or the
semantic layer, so its numbers can check them.
"""

import calendar
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = HERE.parent.parent / "example" / "data"

METRICS = ("available_stock", "near_expiry_value", "net_revenue", "gross_margin", "sell_through_rate", "days_of_cover")
# A stock position is read at one day; the others add up over a period.
STOCK_METRICS = frozenset({"available_stock", "near_expiry_value", "days_of_cover"})
SCOPE_KEYS = ("store", "sku", "district", "category")
CAVEAT_POS_SYNC_LAG = "pos_sync_lag"
CAVEAT_NEW_STORE = "new_store"
# Metrics whose answer counts a new store's opening stock (DR-011).
NEW_STORE_METRICS = frozenset({"sell_through_rate"})


def period(filters: dict, as_of: date) -> tuple[date, date]:
    """First and last business day a question covers."""
    if "day" in filters:
        day = date.fromisoformat(str(filters["day"]))
        return day, day
    if "month" in filters:
        year, month = (int(p) for p in str(filters["month"]).split("-"))
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if "start" in filters and "end" in filters:
        return date.fromisoformat(str(filters["start"])), date.fromisoformat(str(filters["end"]))
    return as_of, as_of


class Reference:
    def __init__(self, data_dir: Path | None = None):
        data_dir = Path(data_dir or os.environ.get("GROUNDRULES_DATA_DIR", DEFAULT_DATA_DIR)).resolve()
        if not (data_dir / "_manifest.json").exists():
            raise FileNotFoundError(f"No extracts in {data_dir}: run `make data` first.")
        self.con = duckdb.connect()
        setup = (HERE / "raw.sql").read_text(encoding="utf-8").replace("{data_dir}", data_dir.as_posix())
        self.con.execute(setup)

    def _run(self, name: str, params: dict) -> list[tuple]:
        sql = (HERE / f"{name}.sql").read_text(encoding="utf-8")
        used = set(re.findall(r"\$(\w+)", sql))
        return self.con.execute(sql, {k: v for k, v in params.items() if k in used}).fetchall()

    def _params(self, filters: dict, as_of: date) -> dict:
        start, end = period(filters, as_of)
        params = {key: filters.get(key) for key in SCOPE_KEYS}
        params.update(start=start, end=end, as_of=as_of)
        return params

    def value(self, metric: str, filters: dict, as_of: date) -> float | None:
        if metric not in METRICS:
            raise ValueError(f"No reference computation for {metric}")
        value = self._run(metric, self._params(filters, as_of))[0][0]
        return None if value is None else float(value)

    def caveats(self, metric: str, filters: dict, as_of: date) -> list[str]:
        """Name every store whose data makes the answer need a warning.

        DR-004: a lagging store in scope counts when the metric is a stock
        position at the as-of day (its ERP stock has not seen the unsynced
        sales) or the period asked about reaches past the last day its data
        covers. DR-011: for sell-through, a store in scope that opened in the
        period or within 7 days after it (new_stores.sql).
        """
        start, end = period(filters, as_of)
        params = self._params(filters, as_of)
        caveats = [
            f"{CAVEAT_POS_SYNC_LAG}:{store}"
            for store, data_through in self._run("lagging_stores", params)
            if metric in STOCK_METRICS or (data_through < end and start <= as_of - timedelta(days=1))
        ]
        if metric in NEW_STORE_METRICS:
            caveats += [f"{CAVEAT_NEW_STORE}:{store}" for store, _ in self._run("new_stores", params)]
        return sorted(caveats)


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in METRICS:
        print(__doc__)
        print("Metrics:", ", ".join(METRICS))
        return 2
    filters = dict(arg.split("=", 1) for arg in argv[1:])
    as_of = date.fromisoformat(filters.pop("as_of", "2026-09-15"))
    ref = Reference()
    print(argv[0], filters, "=", ref.value(argv[0], filters, as_of))
    print("caveats:", ref.caveats(argv[0], filters, as_of) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
