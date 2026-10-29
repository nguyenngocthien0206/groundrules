"""Run the reference SQL: the independent answer to each golden question.

Usage: python golden/reference/reference.py net_revenue month=2026-08 store=NW001
       python golden/reference/reference.py transfer_candidates [as_of=2026-09-15]

Reads only the raw extracts (see raw.sql), never the dbt marts or the
semantic layer, so its numbers can check them.
"""

import calendar
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction
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

    def transfer_candidates(self, as_of: date) -> list[dict]:
        """The transfers DR-012 proposes at `as_of`, most urgent target first.

        transfer_candidates.sql pairs each target with its donors within 30
        minutes. Here each target takes the nearest donor that still has a
        unit to spare, so a donor never promises the same box twice: the
        target with the lowest cover goes first, then by store code.
        """
        rows = self._run("transfer_candidates", {"as_of": as_of})
        columns = [d[0] for d in self.con.description]
        pairs: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            pair = dict(zip(columns, row))
            pairs.setdefault((pair["target"], pair["sku"]), []).append(pair)  # nearest first
        spare = {(p["donor"], p["sku"]): int(p["spare_units"]) for ps in pairs.values() for p in ps}

        def cover(available: int, sold_28d: int) -> Fraction:
            return Fraction(28 * int(available), int(sold_28d))

        proposals = []
        for (target, sku), options in sorted(
            pairs.items(), key=lambda kv: (cover(kv[1][0]["target_available"], kv[1][0]["target_sold_28d"]), kv[0])
        ):
            first = options[0]
            if first["cap_units"] < 1:
                continue  # one unit would take the target above 60 days
            chosen = next((p for p in options if spare[(p["donor"], sku)] >= 1), None)
            if chosen is None:
                continue
            quantity = min(int(first["need_units"]), int(first["cap_units"]), spare[(chosen["donor"], sku)])
            spare[(chosen["donor"], sku)] -= quantity
            moved = quantity * int(first["factor"])
            proposals.append({
                "target": target,
                "donor": chosen["donor"],
                "sku": sku,
                "quantity": quantity,
                "unit": first["purchase_unit"],
                "base_units": moved,
                "drive_minutes": chosen["drive_seconds"] / 60,
                "partial": quantity < first["need_units"],
                "target_cover_before": float(cover(first["target_available"], first["target_sold_28d"])),
                "target_cover_after": float(cover(first["target_available"] + moved, first["target_sold_28d"])),
                "donor_cover_before": float(cover(chosen["donor_available"], chosen["donor_sold_28d"])),
                "donor_cover_after": float(cover(chosen["donor_available"] - moved, chosen["donor_sold_28d"])),
            })
        return proposals


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in (*METRICS, "transfer_candidates"):
        print(__doc__)
        print("Metrics:", ", ".join(METRICS))
        return 2
    filters = dict(arg.split("=", 1) for arg in argv[1:])
    as_of = date.fromisoformat(filters.pop("as_of", "2026-09-15"))
    ref = Reference()
    if argv[0] == "transfer_candidates":
        proposals = ref.transfer_candidates(as_of)
        for p in proposals:
            print(f"{p['target']} {p['sku']}: {p['quantity']} {p['unit']} from {p['donor']} ({p['drive_minutes']:.1f} min), "
                  f"cover {p['target_cover_before']:.1f} -> {p['target_cover_after']:.1f} days"
                  f"{' (partial)' if p['partial'] else ''}")
        print(f"{len(proposals)} proposals, {sum(p['partial'] for p in proposals)} partial")
        return 0
    print(argv[0], filters, "=", ref.value(argv[0], filters, as_of))
    print("caveats:", ref.caveats(argv[0], filters, as_of) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
