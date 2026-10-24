"""Write each source the way its system exports it, quirks included.

The ERP speaks UPPER_SNAKE columns, `YYYYMMDD` dates and status codes.
Each POS vendor and the returns system has its own format on top of that.
"""

import csv
from datetime import date
from pathlib import Path

from synth import config
from synth.master import Sku, Store
from synth.simulate import World


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
