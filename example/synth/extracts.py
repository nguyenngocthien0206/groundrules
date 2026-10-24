"""Write each source the way its system exports it, quirks included.

The ERP speaks UPPER_SNAKE columns, `YYYYMMDD` dates and status codes.
Each POS vendor and the returns system has its own format on top of that.
"""

import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from synth import config, rng
from synth.master import Sku, Store
from synth.simulate import SaleLine, World

# Each POS vendor has its own unit codes, and neither matches the ERP.
POS_A_UNITS = {"TAB": "TAB", "STRIP": "STRIP", "BOX": "BOX", "BOTTLE": "BTL", "PIECE": "PCS"}
POS_B_UNITS = {"TAB": "Viên", "STRIP": "Vỉ", "BOX": "Hộp", "BOTTLE": "Chai", "PIECE": "Cái"}

# Vendor A's uploader sometimes retries a receipt: the same lines appear again
# later in the same file, or in the next day's file.
RETRY_SAME_FILE_SHARE = 0.004
RETRY_NEXT_FILE_SHARE = 0.001

RETURN_RECEIPT_SHARE = 0.015
RETURN_LAG_SHARES = (0.60, 0.25)  # within 3 days, within 30 days; the rest 31 to 60 days
RETURN_NO_RECEIPT_SHARE = 0.05
RETURN_ORPHAN_SHARE = 0.03


def _ymd(d: date | None) -> str:
    return d.strftime("%Y%m%d") if d else ""


def write_csv(path: Path, header: list[str], rows, *, delimiter: str = ",", bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    with path.open("w", encoding=encoding, newline="") as f:
        w = csv.writer(f, delimiter=delimiter, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_erp_stores(out: Path, stores: list[Store]) -> None:
    write_csv(
        out / "erp" / "stores.csv",
        ["STORE_CD", "STORE_NAME", "DISTRICT_CD", "DISTRICT_NAME", "OPENED_ON", "OPEN_24H", "POS_SYSTEM", "STATUS"],
        (
            [s.code, s.name, s.district_code, s.district_name, _ymd(s.opened_on),
             "Y" if s.open_24h else "N", s.pos_vendor, "A"]
            for s in stores
        ),
    )


def write_erp_skus(out: Path, skus: list[Sku]) -> None:
    # The ERP keeps only the current name. UPDATED_AT is the one hint that
    # something changed.
    write_csv(
        out / "erp" / "skus.csv",
        ["ITEM_NO", "ITEM_NAME", "CATEGORY_CD", "CATEGORY_NAME", "BASE_UOM", "PURCH_UOM",
         "VAT_RATE", "LIST_PRICE", "SHELF_LIFE_DAYS", "CREATED_AT", "UPDATED_AT"],
        (
            [s.item_no, s.name, s.category_code, s.category_name, s.base_uom, s.receive_uom,
             s.vat_rate, s.uom(s.base_uom).price, s.shelf_life_days, _ymd(s.created_on),
             _ymd(config.RENAME_ON if s.old_name else s.created_on)]
            for s in skus
        ),
    )


def write_erp_batches(out: Path, world: World) -> None:
    # Received quantities are in the purchase unit, on-hand is in the base
    # unit, as many pharmacy ERPs keep them. On-hand includes stock reserved
    # for transfers that have shipped but not arrived.
    skus = {s.item_no: s for s in world.skus}
    write_csv(
        out / "erp" / "batches.csv",
        ["BATCH_ID", "STORE_CD", "ITEM_NO", "LOT_NO", "EXP_DATE", "RCV_DATE", "RCV_QTY",
         "RCV_UOM", "UNIT_COST", "SOURCE_DOC", "ONHAND_QTY", "ONHAND_UOM"],
        (
            [b.batch_id, b.store, b.item_no, b.lot_no, _ymd(b.expiry), _ymd(b.received_on),
             b.received_qty, skus[b.item_no].receive_uom, b.unit_cost, b.source_doc,
             b.on_hand, skus[b.item_no].base_uom]
            for b in world.batches
        ),
    )


def write_erp_transfers(out: Path, world: World) -> None:
    skus = {s.item_no: s for s in world.skus}
    write_csv(
        out / "erp" / "transfers.csv",
        ["TRF_NO", "ITEM_NO", "LOT_NO", "FROM_STORE", "TO_STORE", "QTY", "UOM", "STATUS",
         "CREATED_AT", "SHIPPED_AT", "RECEIVED_AT", "UPDATED_AT"],
        (
            [t.transfer_no, t.item_no, t.lot_no, t.from_store, t.to_store, t.qty,
             skus[t.item_no].receive_uom, t.status, _ymd(t.created_on), _ymd(t.shipped_on),
             _ymd(t.received_on), _ymd(t.updated_on or t.shipped_on)]
            for t in world.transfers
        ),
    )


def _receipts(lines: list[SaleLine]) -> dict[tuple[str, date, int], list[SaleLine]]:
    out: dict[tuple[str, date, int], list[SaleLine]] = defaultdict(list)
    for s in lines:
        out[(s.store, s.day, s.receipt_seq)].append(s)
    return out


def _utc(local: datetime) -> datetime:
    return local - config.UTC_OFFSET


def receipt_no(store: Store, day: date, seq: int) -> str:
    """Receipt number as the store's POS vendor prints it."""
    if store.pos_vendor == "A":
        return f"A{store.number:03d}{day:%y%m%d}{seq:04d}"
    return f"HD{store.number:03d}{day:%y%m%d}{seq:04d}"


def write_pos_a(out: Path, world: World, seed: str) -> None:
    """Vendor A: one file per UTC day, ISO timestamps in UTC, upload retries.

    Files are cut on the UTC date, so a 24-hour store's sale at 02:00 local
    time lands in the previous day's file.
    """
    r = rng(seed, "pos_a")
    stores = {s.code: s for s in world.stores if s.pos_vendor == "A"}
    files: dict[date, list[list]] = defaultdict(list)
    retries: dict[date, list[list]] = defaultdict(list)

    for (store, day, seq), lines in _receipts([s for s in world.sales if s.store in stores]).items():
        utc = _utc(lines[0].at)
        txn_id = receipt_no(stores[store], day, seq)
        rows = [
            [txn_id, s.line_no, store, s.item_no, POS_A_UNITS[s.uom], s.qty, s.unit_price,
             s.discount, s.amount, f"{utc:%Y-%m-%dT%H:%M:%SZ}"]
            for s in lines
        ]
        exported = utc + timedelta(minutes=r.randint(1, 20))
        files[utc.date()].extend(row + [f"{exported:%Y-%m-%dT%H:%M:%SZ}"] for row in rows)
        x = r.random()
        if x < RETRY_SAME_FILE_SHARE:
            again = exported + timedelta(minutes=r.randint(30, 300))
            retry_day = utc.date()
        elif x < RETRY_SAME_FILE_SHARE + RETRY_NEXT_FILE_SHARE:
            retry_day = utc.date() + timedelta(days=1)
            again = datetime.combine(retry_day, datetime.min.time()) + timedelta(minutes=r.randint(5, 120))
        else:
            continue
        if _utc(config.EXTRACT_AT) > again:  # a retry after the extract ran is not in it
            retries[retry_day].extend(row + [f"{again:%Y-%m-%dT%H:%M:%SZ}"] for row in rows)

    header = ["txn_id", "line_no", "store_code", "item_code", "uom", "qty", "unit_price",
              "discount_amount", "line_amount", "txn_ts", "exported_at"]
    for day in sorted(set(files) | set(retries)):
        rows = sorted(files[day], key=lambda row: (row[9], row[0], row[1])) + retries[day]
        write_csv(out / "pos_a" / f"sales_{day:%Y%m%d}.csv", header, rows)


def write_pos_b(out: Path, world: World) -> None:
    """Vendor B: one file per local day, semicolons, Excel BOM, Vietnamese headers.

    Dates are dd/mm/yyyy in local time, and the item name printed is the one
    valid on the day of the sale.
    """
    stores = {s.code: s for s in world.stores if s.pos_vendor == "B"}
    skus = {s.item_no: s for s in world.skus}
    files: dict[date, list[list]] = defaultdict(list)
    for s in world.sales:
        if s.store not in stores:
            continue
        files[s.day].append(
            [receipt_no(stores[s.store], s.day, s.receipt_seq), s.line_no, s.store, s.item_no, skus[s.item_no].name_on(s.day),
             POS_B_UNITS[s.uom], s.qty, s.unit_price, s.discount, s.amount,
             f"{s.at:%d/%m/%Y}", f"{s.at:%H:%M:%S}"]
        )

    header = ["SoHoaDon", "Dong", "MaCuaHang", "MaHang", "TenHang", "DVT", "SoLuong",
              "DonGia", "ChietKhau", "ThanhTien", "NgayBan", "GioBan"]
    day = config.SALES_START
    while day <= config.SALES_END:
        write_csv(out / "pos_b" / f"BanHang_{day:%d%m%Y}.csv", header, files.get(day, []),
                  delimiter=";", bom=True)
        day += timedelta(days=1)


def write_pos_sync_log(out: Path, world: World, seed: str) -> None:
    """The integration job's view of each store: last good sync and last attempt."""
    r = rng(seed, "sync_log")
    rows = []
    for s in world.stores:
        attempt = config.EXTRACT_AT - timedelta(minutes=r.randint(10, 40), seconds=r.randrange(60))
        if s.is_lagging:
            synced = datetime.combine(s.last_synced_day + timedelta(days=1), attempt.time())
            error = "connection timeout"
        else:
            synced, error = attempt, ""
        rows.append([s.code, s.pos_vendor, f"{synced:%Y-%m-%d %H:%M:%S}",
                     f"{attempt:%Y-%m-%d %H:%M:%S}", error])
    write_csv(out / "pos_sync_log.csv",
              ["store_code", "pos_vendor", "last_success_at", "last_attempt_at", "last_error"], rows)


def write_returns(out: Path, world: World, seed: str) -> None:
    """Returns system: JSON Lines from its API, one return with nested lines.

    Returns arrive days or weeks after the sale, so some land in a later month.
    Some carry no receipt, and some point to receipts from before the extract
    window, so they match no sale at all. Refunds include VAT, net of the
    discount given at the sale. Returned medicine is destroyed, not restocked.
    """
    r = rng(seed, "returns")
    stores = {s.code: s for s in world.stores}
    extract_at = config.EXTRACT_AT
    returns = []

    def returned_at(after: datetime) -> datetime:
        x = r.random()
        if x < RETURN_LAG_SHARES[0]:
            lag = r.randint(0, 3)
        elif x < RETURN_LAG_SHARES[0] + RETURN_LAG_SHARES[1]:
            lag = r.randint(4, 30)
        else:
            lag = r.randint(31, 60)
        day = after.date() + timedelta(days=lag)
        at = datetime.combine(day, datetime.min.time()) + timedelta(
            hours=r.randint(8, 20), minutes=r.randrange(60), seconds=r.randrange(60))
        return max(at, after + timedelta(minutes=10))

    def line(item_no: str, uom: str, qty: int, refund: int) -> dict:
        return {"sku": item_no, "uom": uom, "qty": qty, "refund_vnd": refund}

    for (store, day, seq), lines in _receipts(world.sales).items():
        if r.random() >= RETURN_RECEIPT_SHARE:
            continue
        picked = [s for s in lines if r.random() < 0.6] or [r.choice(lines)]
        at = returned_at(lines[0].at)
        if at > extract_at:
            continue  # not returned yet when the extract ran
        receipt = None if r.random() < RETURN_NO_RECEIPT_SHARE else receipt_no(stores[store], day, seq)
        items = []
        for s in picked:
            qty = r.randint(1, s.qty)
            items.append(line(s.item_no, s.uom, qty, round(s.amount * qty / s.qty)))
        returns.append((at, store, receipt, items))

    # Returns of sales made before the extract window: no sale to match.
    open_stores = [s for s in world.stores if s.opened_on < config.SALES_START]
    for _ in range(round(len(returns) * RETURN_ORPHAN_SHARE)):
        st = r.choice(open_stores)
        sold = config.SALES_START - timedelta(days=r.randint(1, 30))
        at = returned_at(datetime.combine(sold, datetime.min.time()) + timedelta(hours=12))
        if at.date() < config.SALES_START:
            at = datetime.combine(config.SALES_START, at.time())
        sku = r.choices(world.skus, weights=[s.popularity for s in world.skus])[0]
        unit = sku.base_uom if sku.form != config.FORM_TABLET else "STRIP"
        qty = r.randint(1, 2)
        items = [line(sku.item_no, unit, qty, qty * sku.uom(unit).price)]
        returns.append((at, st.code, receipt_no(st, sold, r.randint(1, 60)), items))

    returns.sort(key=lambda x: (x[0], x[1]))
    reasons = ("CHANGED_MIND", "WRONG_ITEM", "ADVERSE_REACTION", "DAMAGED_PACK", "DOCTOR_CHANGED_PRESCRIPTION")
    path = out / "returns" / "returns.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for i, (at, store, receipt, items) in enumerate(returns, start=1):
            record = {
                "return_id": f"RT{i:07d}",
                "store": {"code": store, "name": stores[store].name},
                "returned_at": f"{at:%Y-%m-%dT%H:%M:%S}+07:00",
                "original_receipt": receipt,
                "reason": r.choice(reasons),
                "lines": items,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_erp_sku_uom(out: Path, skus: list[Sku]) -> None:
    write_csv(
        out / "erp" / "sku_uom.csv",
        ["ITEM_NO", "UOM_CD", "FACTOR_TO_BASE", "IS_BASE", "SELL_PRICE"],
        (
            [s.item_no, u.code, u.factor, "Y" if u.code == s.base_uom else "N",
             "" if u.price is None else u.price]
            for s in skus
            for u in s.uoms
        ),
    )
