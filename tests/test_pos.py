from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import pytest

from conftest import read_csv
from synth import config


def _utc(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(scope="module")
def stores(data_dir) -> dict[str, dict]:
    return {s["STORE_CD"]: s for s in read_csv(data_dir / "erp" / "stores.csv")}


@pytest.fixture(scope="module")
def prices(data_dir) -> dict[tuple[str, str], int]:
    return {
        (u["ITEM_NO"], u["UOM_CD"]): int(u["SELL_PRICE"])
        for u in read_csv(data_dir / "erp" / "sku_uom.csv")
        if u["SELL_PRICE"]
    }


def _local_day_a(row) -> date:
    return (_utc(row["txn_ts"]) + config.UTC_OFFSET).date()


def _local_day_b(row) -> date:
    return datetime.strptime(row["NgayBan"], "%d/%m/%Y").date()


def test_each_store_reports_through_its_own_vendor(pos_a, pos_b, stores):
    in_a = {r["store_code"] for rows in pos_a.values() for r in rows}
    in_b = {r["MaCuaHang"] for rows in pos_b.values() for r in rows}
    assert not in_a & in_b
    assert in_a | in_b == set(stores)
    assert all(stores[s]["POS_SYSTEM"] == "A" for s in in_a)
    assert all(stores[s]["POS_SYSTEM"] == "B" for s in in_b)


def test_vendor_a_files_are_cut_on_the_utc_date(pos_a):
    crosses_midnight = 0
    previous: set[tuple[str, str]] = set()
    for name, rows in pos_a.items():
        file_day = datetime.strptime(name, "sales_%Y%m%d.csv").date()
        for r in rows:
            assert r["txn_ts"].endswith("Z")
            if _utc(r["txn_ts"]).date() != file_day:
                # Only a retry of yesterday's receipt may carry yesterday's timestamp.
                assert (r["txn_id"], r["line_no"]) in previous
                continue
            crosses_midnight += _local_day_a(r) != file_day
        previous = {(r["txn_id"], r["line_no"]) for r in rows}
    # Early morning sales in 24-hour stores belong to the next local day.
    assert crosses_midnight > 0


def test_vendor_a_retries_duplicate_lines_within_and_across_files(pos_a):
    within = across = total = 0
    seen: dict[tuple[str, str], str] = {}
    for name, rows in pos_a.items():
        counts = Counter((r["txn_id"], r["line_no"]) for r in rows)
        within += sum(c - 1 for c in counts.values())
        total += len(rows)
        for key in counts:
            if key in seen and seen[key] != name:
                across += 1
            seen.setdefault(key, name)
    assert within > 0
    assert across > 0
    assert (within + across) / total < 0.01


def test_vendor_b_writes_excel_style_semicolon_files(data_dir, pos_b):
    first = sorted((data_dir / "pos_b").glob("*.csv"))[0]
    raw = first.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.split(b"\n")[0].count(b";") == 11
    for name, rows in pos_b.items():
        file_day = datetime.strptime(name, "BanHang_%d%m%Y.csv").date()
        assert all(_local_day_b(r) == file_day for r in rows)


def test_units_use_three_different_vocabularies(pos_a, pos_b, data_dir):
    erp = {u["UOM_CD"] for u in read_csv(data_dir / "erp" / "sku_uom.csv")}
    a = {r["uom"] for rows in pos_a.values() for r in rows}
    b = {r["DVT"] for rows in pos_b.values() for r in rows}
    assert {"TAB", "STRIP", "BOX", "BTL", "PCS"} == a
    assert {"Viên", "Vỉ", "Hộp", "Chai", "Cái"} == b
    assert a - erp and b - erp


def test_amounts_include_vat_and_subtract_discounts(pos_a, pos_b, prices):
    erp_unit = {"BTL": "BOTTLE", "PCS": "PIECE", "Viên": "TAB", "Vỉ": "STRIP", "Hộp": "BOX",
                "Chai": "BOTTLE", "Cái": "PIECE"}
    discounted = 0
    for rows in pos_a.values():
        for r in rows:
            unit = erp_unit.get(r["uom"], r["uom"])
            assert int(r["unit_price"]) == prices[(r["item_code"], unit)]
            assert int(r["line_amount"]) == int(r["qty"]) * int(r["unit_price"]) - int(r["discount_amount"])
            discounted += int(r["discount_amount"]) > 0
    for rows in pos_b.values():
        for r in rows:
            assert int(r["DonGia"]) == prices[(r["MaHang"], erp_unit[r["DVT"]])]
            assert int(r["ThanhTien"]) == int(r["SoLuong"]) * int(r["DonGia"]) - int(r["ChietKhau"])
    assert discounted > 0


def test_vendor_b_prints_the_name_valid_on_the_day(pos_b, data_dir):
    current = {s["ITEM_NO"]: s["ITEM_NAME"] for s in read_csv(data_dir / "erp" / "skus.csv")}
    renamed = {item for item, name in current.items() if name in config.RENAMES.values()}
    names = defaultdict(set)
    for rows in pos_b.values():
        for r in rows:
            if r["MaHang"] in renamed:
                before = _local_day_b(r) < config.RENAME_ON
                names[r["MaHang"]].add(r["TenHang"])
                assert (r["TenHang"] == current[r["MaHang"]]) != before
    assert any(len(n) == 2 for n in names.values())


def test_sales_start_at_opening_and_stop_at_last_sync(pos_a, pos_b, stores):
    days = defaultdict(set)
    for rows in pos_a.values():
        for r in rows:
            days[r["store_code"]].add(_local_day_a(r))
    for rows in pos_b.values():
        for r in rows:
            days[r["MaCuaHang"]].add(_local_day_b(r))
    for code, s in stores.items():
        opened = datetime.strptime(s["OPENED_ON"], "%Y%m%d").date()
        assert min(days[code]) == max(opened, config.SALES_START)
        if opened in config.NEW_STORE_OPENINGS:
            assert max(days[code]) == config.SALES_END - timedelta(days=config.POS_SYNC_LAG_DAYS)
        else:
            assert max(days[code]) == config.SALES_END


def test_sync_log_shows_the_two_lagging_stores(data_dir, stores):
    log = read_csv(data_dir / "pos_sync_log.csv")
    assert {r["store_code"] for r in log} == set(stores)
    late = [r for r in log if r["last_success_at"] < config.SNAPSHOT_DATE.isoformat()]
    assert len(late) == 2
    assert all(r["last_error"] for r in late)
    assert all(
        datetime.strptime(stores[r["store_code"]]["OPENED_ON"], "%Y%m%d").date() in config.NEW_STORE_OPENINGS
        for r in late
    )
