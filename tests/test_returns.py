import json
from datetime import datetime, timedelta

import pytest

from synth import config


def _at(ts: str) -> datetime:
    assert ts.endswith("+07:00")
    return datetime.fromisoformat(ts[:-6])


@pytest.fixture(scope="module")
def returns(data_dir) -> list[dict]:
    with (data_dir / "returns" / "returns.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def sales(pos_a, pos_b) -> dict[tuple[str, str, str], tuple[datetime, int]]:
    """(receipt, sku, ERP unit) -> (local sale time, amount paid).

    A receipt can hold the same SKU and unit on two lines, so amounts add up.
    Vendor A retries are dropped first.
    """
    a_units = {"BTL": "BOTTLE", "PCS": "PIECE"}
    b_units = {"Viên": "TAB", "Vỉ": "STRIP", "Hộp": "BOX", "Chai": "BOTTLE", "Cái": "PIECE"}
    lines = {}
    for rows in pos_a.values():
        for r in rows:
            at = datetime.strptime(r["txn_ts"], "%Y-%m-%dT%H:%M:%SZ") + config.UTC_OFFSET
            key = (r["txn_id"], r["item_code"], a_units.get(r["uom"], r["uom"]))
            lines[(r["txn_id"], r["line_no"])] = (key, at, int(r["line_amount"]))
    for rows in pos_b.values():
        for r in rows:
            at = datetime.strptime(f"{r['NgayBan']} {r['GioBan']}", "%d/%m/%Y %H:%M:%S")
            key = (r["SoHoaDon"], r["MaHang"], b_units[r["DVT"]])
            lines[(r["SoHoaDon"], r["Dong"])] = (key, at, int(r["ThanhTien"]))
    out: dict = {}
    for key, at, amount in lines.values():
        out[key] = (at, out.get(key, (at, 0))[1] + amount)
    return out


def test_returns_are_api_style_records_in_time_order(returns):
    assert returns
    times = [_at(r["returned_at"]) for r in returns]
    assert times == sorted(times)
    assert max(times) <= config.EXTRACT_AT
    assert len({r["return_id"] for r in returns}) == len(returns)
    for r in returns:
        assert set(r) == {"return_id", "store", "returned_at", "original_receipt", "reason", "lines"}
        assert r["lines"]
        assert all(line["qty"] >= 1 and line["refund_vnd"] > 0 for line in r["lines"])


def test_matched_returns_never_refund_more_than_was_paid(returns, sales):
    for r in returns:
        for line in r["lines"]:
            key = (r["original_receipt"], line["sku"], line["uom"])
            if key in sales:
                assert line["refund_vnd"] <= sales[key][1]


def test_some_returns_arrive_weeks_later_and_in_a_later_month(returns, sales):
    lags, month_changes = [], 0
    for r in returns:
        key = (r["original_receipt"], r["lines"][0]["sku"], r["lines"][0]["uom"])
        if key not in sales:
            continue
        sold, returned = sales[key][0], _at(r["returned_at"])
        assert returned >= sold
        lags.append((returned - sold).days)
        month_changes += (sold.year, sold.month) != (returned.year, returned.month)
    assert max(lags) > 30
    assert month_changes > 0


def test_some_returns_match_no_sale(returns, sales):
    receipts = {k[0] for k in sales}
    no_receipt = [r for r in returns if r["original_receipt"] is None]
    unknown = [r for r in returns if r["original_receipt"] and r["original_receipt"] not in receipts]
    assert no_receipt
    assert unknown
    # Unknown receipts are sales from before the extract window.
    assert all(_at(r["returned_at"]).date() <= config.SALES_START + timedelta(days=60) for r in unknown)
