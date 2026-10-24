from collections import Counter
from datetime import date, datetime

import generate
from conftest import read_csv
from synth import config


def _ymd(s: str) -> date:
    return datetime.strptime(s, "%Y%m%d").date()


def test_thirty_stores_six_per_district(data_dir):
    stores = read_csv(data_dir / "erp" / "stores.csv")
    assert len(stores) == 30
    assert len({s["STORE_CD"] for s in stores}) == 30
    assert set(Counter(s["DISTRICT_CD"] for s in stores).values()) == {6}


def test_exactly_two_newly_opened_stores_on_vendor_b(data_dir):
    stores = read_csv(data_dir / "erp" / "stores.csv")
    new = [s for s in stores if (config.SNAPSHOT_DATE - _ymd(s["OPENED_ON"])).days <= 31]
    assert len(new) == 2
    assert {s["POS_SYSTEM"] for s in new} == {"B"}
    older = [s for s in stores if s not in new]
    assert all(_ymd(s["OPENED_ON"]) < config.SALES_START for s in older)


def test_24h_stores_are_on_the_utc_vendor(data_dir):
    stores = read_csv(data_dir / "erp" / "stores.csv")
    open_24h = [s for s in stores if s["OPEN_24H"] == "Y"]
    assert len(open_24h) == 3
    assert {s["POS_SYSTEM"] for s in open_24h} == {"A"}


def test_150_skus_in_6_categories_with_two_vat_rates(data_dir):
    skus = read_csv(data_dir / "erp" / "skus.csv")
    assert len(skus) == 150
    assert Counter(s["CATEGORY_CD"] for s in skus) == Counter(config.SKUS_PER_CATEGORY)
    assert {s["VAT_RATE"] for s in skus} == {"5", "10"}


def test_every_sku_has_a_base_unit_and_a_purchase_unit(data_dir):
    skus = {s["ITEM_NO"]: s for s in read_csv(data_dir / "erp" / "skus.csv")}
    uoms: dict[str, dict[str, int]] = {}
    for u in read_csv(data_dir / "erp" / "sku_uom.csv"):
        uoms.setdefault(u["ITEM_NO"], {})[u["UOM_CD"]] = int(u["FACTOR_TO_BASE"])
    for item_no, sku in skus.items():
        assert uoms[item_no][sku["BASE_UOM"]] == 1
        assert uoms[item_no][sku["PURCH_UOM"]] > 1


def test_tablets_come_in_strips_of_ten_and_boxes(data_dir):
    by_item: dict[str, dict[str, int]] = {}
    for u in read_csv(data_dir / "erp" / "sku_uom.csv"):
        by_item.setdefault(u["ITEM_NO"], {})[u["UOM_CD"]] = int(u["FACTOR_TO_BASE"])
    tablets = [u for u in by_item.values() if "TAB" in u]
    assert tablets
    assert all(u["STRIP"] == 10 and u["BOX"] in (30, 100) for u in tablets)


def test_renamed_skus_show_only_their_current_name(data_dir):
    skus = read_csv(data_dir / "erp" / "skus.csv")
    names = {s["ITEM_NAME"] for s in skus}
    assert set(config.RENAMES.values()) <= names
    assert not set(config.RENAMES) & names
    renamed = [s for s in skus if s["ITEM_NAME"] in config.RENAMES.values()]
    assert {s["UPDATED_AT"] for s in renamed} == {config.RENAME_ON.strftime("%Y%m%d")}


def test_same_seed_gives_same_master_data(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate.generate(a)
    generate.generate(b)
    for name in ("stores.csv", "skus.csv", "sku_uom.csv"):
        assert (a / "erp" / name).read_bytes() == (b / "erp" / name).read_bytes()
