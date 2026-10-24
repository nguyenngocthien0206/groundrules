from collections import defaultdict
from datetime import date, datetime, timedelta

import pytest

from conftest import read_csv
from synth import config


def _ymd(s: str) -> date | None:
    return datetime.strptime(s, "%Y%m%d").date() if s else None


@pytest.fixture(scope="module")
def batches(data_dir):
    return read_csv(data_dir / "erp" / "batches.csv")


@pytest.fixture(scope="module")
def transfers(data_dir):
    return read_csv(data_dir / "erp" / "transfers.csv")


@pytest.fixture(scope="module")
def factors(data_dir):
    out = {}
    for u in read_csv(data_dir / "erp" / "sku_uom.csv"):
        out[(u["ITEM_NO"], u["UOM_CD"])] = int(u["FACTOR_TO_BASE"])
    return out


def _value(b, factors) -> float:
    return int(b["ONHAND_QTY"]) * int(b["UNIT_COST"]) / factors[(b["ITEM_NO"], b["RCV_UOM"])]


def test_received_in_purchase_units_but_on_hand_in_base_units(batches, data_dir):
    skus = {s["ITEM_NO"]: s for s in read_csv(data_dir / "erp" / "skus.csv")}
    for b in batches:
        assert b["RCV_UOM"] == skus[b["ITEM_NO"]]["PURCH_UOM"]
        assert b["ONHAND_UOM"] == skus[b["ITEM_NO"]]["BASE_UOM"]
        assert int(b["ONHAND_QTY"]) >= 0
    assert {b["RCV_UOM"] for b in batches} == {"BOX", "CARTON"}


def test_cost_differs_between_batches_of_one_sku(batches):
    costs = defaultdict(set)
    for b in batches:
        costs[b["ITEM_NO"]].add(b["UNIT_COST"])
    assert all(len(c) > 1 for c in costs.values())


def test_near_expiry_stock_is_a_visible_share_of_value(batches, factors):
    cutoff = config.SNAPSHOT_DATE + timedelta(days=90)
    total = sum(_value(b, factors) for b in batches)
    near = sum(_value(b, factors) for b in batches if _ymd(b["EXP_DATE"]) < cutoff)
    assert 0.03 <= near / total <= 0.15


def test_some_expired_stock_is_still_on_hand_waiting_for_write_off(batches):
    expired = [b for b in batches if _ymd(b["EXP_DATE"]) < config.SNAPSHOT_DATE and int(b["ONHAND_QTY"]) > 0]
    assert expired
    # Write-offs run on the first of the month, so anything older is gone.
    first_of_month = config.SNAPSHOT_DATE.replace(day=1)
    assert all(_ymd(b["EXP_DATE"]) >= first_of_month for b in expired)


def test_transfer_statuses_are_codes(transfers):
    assert {t["STATUS"] for t in transfers} == {"TR", "DL", "CX"}
    assert {t["UOM"] for t in transfers} <= {"BOX", "CARTON"}


def test_only_delivered_transfers_have_a_received_date(transfers):
    for t in transfers:
        assert bool(t["RECEIVED_AT"]) == (t["STATUS"] == "DL")


def test_in_transit_transfers_shipped_just_before_the_snapshot(transfers):
    in_transit = [t for t in transfers if t["STATUS"] == "TR"]
    assert len(in_transit) >= 5
    assert all(_ymd(t["SHIPPED_AT"]) >= config.SNAPSHOT_DATE - timedelta(days=4) for t in in_transit)


def test_a_cancelled_transfer_looks_in_transit_to_a_naive_filter(transfers):
    recent_cx = [
        t for t in transfers
        if t["STATUS"] == "CX" and t["SHIPPED_AT"] and not t["RECEIVED_AT"]
        and _ymd(t["SHIPPED_AT"]) >= config.SNAPSHOT_DATE - timedelta(days=3)
    ]
    assert recent_cx


def test_in_transit_stock_still_counts_in_the_senders_on_hand(transfers, batches, factors):
    on_hand = defaultdict(int)
    for b in batches:
        on_hand[(b["STORE_CD"], b["ITEM_NO"], b["LOT_NO"])] += int(b["ONHAND_QTY"])
    for t in transfers:
        if t["STATUS"] == "TR":
            base = int(t["QTY"]) * factors[(t["ITEM_NO"], t["UOM"])]
            assert on_hand[(t["FROM_STORE"], t["ITEM_NO"], t["LOT_NO"])] >= base


def test_delivered_transfers_create_a_batch_at_the_receiver(transfers, batches):
    by_doc = {b["SOURCE_DOC"]: b for b in batches if b["SOURCE_DOC"].startswith("TRF")}
    for t in transfers:
        if t["STATUS"] == "DL":
            b = by_doc[t["TRF_NO"]]
            assert (b["STORE_CD"], b["LOT_NO"], b["RCV_DATE"]) == (t["TO_STORE"], t["LOT_NO"], t["RECEIVED_AT"])
        else:
            assert t["TRF_NO"] not in by_doc


def test_new_stores_get_stock_only_just_before_they_open(batches, data_dir):
    opened = {s["STORE_CD"]: _ymd(s["OPENED_ON"]) for s in read_csv(data_dir / "erp" / "stores.csv")}
    for b in batches:
        if opened[b["STORE_CD"]] in config.NEW_STORE_OPENINGS:
            assert _ymd(b["RCV_DATE"]) >= opened[b["STORE_CD"]] - timedelta(days=1)
