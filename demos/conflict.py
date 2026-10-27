"""Demo 1: three dashboards, three revenue numbers, one certified answer.

Usage: python demos/conflict.py [--month 2026-08]   (or `make demo-conflict`)

Runs the three legacy dashboard queries in legacy/ against the warehouse,
asks the semantic layer for net_revenue, and prints the four numbers side by
side with the reason each old one is off and the decision record that
settled it.
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "golden"))

from semantic_client import DUCKDB_FILE, READ_ONLY, SemanticLayer  # noqa: E402

# (exposure, label, what it gets wrong, decision record that settled it)
LEGACY = (
    ("finance_dashboard", "Finance monthly dashboard", "refunds put back on the month of the sale", "DR-002"),
    ("sales_dashboard", "Store sales dashboard", "returns left out", "DR-002"),
    ("ops_weekly_report", "Operations weekly report", "till amounts, VAT included", "DR-006"),
)
SETTLED_BY = "DR-002"  # the record that defines net revenue and broke the tie


def month_bounds(month: str) -> tuple[date, date]:
    start = date.fromisoformat(f"{month}-01")
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return start, end


def legacy_numbers(month: str) -> dict[str, float]:
    start, end = month_bounds(month)
    # The same read-only config as MetricFlow's connection: in one process
    # DuckDB refuses a second connection to the file with a different one.
    with duckdb.connect(str(DUCKDB_FILE), config=READ_ONLY) as con:
        return {
            name: float(con.execute((ROOT / "legacy" / f"{name}.sql").read_text(encoding="utf-8"),
                                    {"month_start": start, "month_end": end}).fetchone()[0])
            for name, *_ in LEGACY
        }


def certified_number(sl: SemanticLayer, month: str) -> float:
    rows = sl.query(["net_revenue"], ["metric_time__month"],
                    ["{{ TimeDimension('metric_time', 'month') }} = '%s-01'" % month])
    return float(rows[0]["net_revenue"])


def decision(record_id: str) -> dict:
    text = (ROOT / "decisions" / f"{record_id}.md").read_text(encoding="utf-8")
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL).group(1))


def guarding_question(month: str) -> str | None:
    for path in sorted((ROOT / "golden" / "questions").glob("*.yml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]:
            if q["metric"] == "net_revenue" and q["filters"] == {"month": month}:
                return q["id"]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--month", default="2026-08", help="YYYY-MM (default 2026-08)")
    args = parser.parse_args(argv)
    if not DUCKDB_FILE.exists():
        print("No warehouse yet: run `make data && make build` first.")
        return 1

    old = legacy_numbers(args.month)
    sl = SemanticLayer()
    certified = certified_number(sl, args.month)
    version = sl.governance("net_revenue").get("version")
    title = date.fromisoformat(f"{args.month}-01").strftime("%B %Y")

    print(f"\nWhat was our revenue in {title}? Four answers:\n")
    for name, label, reason, record in LEGACY:
        gap = old[name] - certified
        print(f"  {label:<28}{old[name]:>20,.0f} VND   {gap:+16,.0f}   {reason} ({record})")
    print(f"  {'net_revenue (certified, v' + str(version) + ')':<28}{certified:>20,.0f} VND   {'':>16}   the one answer")

    dr = decision(SETTLED_BY)
    print(f"\nSettled by {dr['id']}: {dr['title']}.")
    print(f"Decided by the {dr['decided_by']} on {dr['date']}, after hearing {', '.join(dr['consulted'])}.")
    print(f"VAT is settled by DR-006: {decision('DR-006')['title']}.")
    guard = guarding_question(args.month)
    if guard:
        print(f"Golden question {guard} fails CI if anyone moves this number without a new record.")

    numbers = list(old.values()) + [certified]
    if len({round(n) for n in numbers}) != len(numbers):
        print("\nTwo answers agree: this month does not show the conflict.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
