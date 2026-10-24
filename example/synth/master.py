"""Master data: stores, SKUs and their units of measure."""

from dataclasses import dataclass, replace
from datetime import date, timedelta

from synth import config, rng


@dataclass(frozen=True)
class Store:
    code: str
    name: str
    district_code: str
    district_name: str
    opened_on: date
    open_24h: bool
    pos_vendor: str  # "A" or "B"
    traffic: float  # receipts per day relative to an average store

    @property
    def number(self) -> int:
        return int(self.code[2:])

    @property
    def is_lagging(self) -> bool:
        return self.opened_on in config.NEW_STORE_OPENINGS

    @property
    def last_synced_day(self) -> date:
        """Last business day whose sales reached the extract."""
        if self.is_lagging:
            return config.SALES_END - timedelta(days=config.POS_SYNC_LAG_DAYS)
        return config.SALES_END


@dataclass(frozen=True)
class Uom:
    code: str
    factor: int  # base units per one of this unit
    price: int | None  # VND including VAT, None when not sold in this unit


@dataclass(frozen=True)
class Sku:
    item_no: str
    name: str  # current name, the only one the ERP keeps
    old_name: str | None  # name before the mid-period rename, if any
    category_code: str
    category_name: str
    vat_rate: int  # percent
    form: str
    base_uom: str
    receive_uom: str  # the unit purchase orders and transfers use
    uoms: tuple[Uom, ...]
    shelf_life_days: int
    popularity: float
    created_on: date

    def uom(self, code: str) -> Uom:
        for u in self.uoms:
            if u.code == code:
                return u
        raise KeyError(f"{self.item_no} has no unit {code}")

    @property
    def receive_factor(self) -> int:
        return self.uom(self.receive_uom).factor

    def name_on(self, day: date) -> str:
        if self.old_name and day < config.RENAME_ON:
            return self.old_name
        return self.name


def _round_to(value: float, step: int) -> int:
    return max(step, int(round(value / step)) * step)


def build_stores(seed: str) -> list[Store]:
    r = rng(seed, "stores")
    n_existing = len(config.DISTRICTS) * config.STORES_PER_DISTRICT - len(config.NEW_STORE_OPENINGS)

    # Store codes follow opening order, so older stores have lower numbers.
    first, last = date(2016, 1, 1), date(2025, 12, 31)
    span = (last - first).days
    openings = sorted(first + timedelta(days=r.randrange(span)) for _ in range(n_existing))
    openings += list(config.NEW_STORE_OPENINGS)

    districts = [d for d in config.DISTRICTS for _ in range(config.STORES_PER_DISTRICT)]
    r.shuffle(districts)

    n_total = len(openings)
    first_b = n_total - config.VENDOR_B_STORES
    open_24h = set(r.sample(range(first_b), config.STORES_24H))

    stores: list[Store] = []
    seen_in_district: dict[str, int] = {}
    for i, (opened_on, (d_code, d_name)) in enumerate(zip(openings, districts)):
        seen_in_district[d_code] = seen_in_district.get(d_code, 0) + 1
        is_new = opened_on in config.NEW_STORE_OPENINGS
        stores.append(
            Store(
                code=f"NW{i + 1:03d}",
                name=f"{config.CHAIN_NAME} {d_name} {seen_in_district[d_code]}",
                district_code=d_code,
                district_name=d_name,
                opened_on=opened_on,
                open_24h=i in open_24h,
                pos_vendor="B" if i >= first_b else "A",
                traffic=round(r.uniform(0.5, 0.7) if is_new else r.uniform(0.6, 1.5), 3),
            )
        )
    return stores


def _tablet_uoms(r, category: str, strips_per_box: int) -> tuple[Uom, ...]:
    low, high = config.TABLET_PRICE_RANGE[category]
    strip = _round_to(r.uniform(low, high) * config.TABLETS_PER_STRIP, 500)
    tablet = _round_to(strip / config.TABLETS_PER_STRIP * 1.1, 100)  # loose tablets cost more
    box = _round_to(strip * strips_per_box * 0.97, 1000)  # small discount for a full box
    return (
        Uom("TAB", 1, tablet),
        Uom("STRIP", config.TABLETS_PER_STRIP, strip),
        Uom("BOX", config.TABLETS_PER_STRIP * strips_per_box, box),
    )


def _bottle_uoms(r) -> tuple[Uom, ...]:
    low, high = config.BOTTLE_PRICE_RANGE
    return (
        Uom("BOTTLE", 1, _round_to(r.uniform(low, high), 1000)),
        Uom("CARTON", config.BOTTLES_PER_CARTON, None),
    )


def _piece_uoms(per_box: int, piece_price: int) -> tuple[Uom, ...]:
    return (
        Uom("PIECE", 1, piece_price),
        Uom("BOX", per_box, _round_to(piece_price * per_box * 0.95, 1000)),
    )


def _products(category: str):
    """Yield (name, form, uom builder args) for one category, in a fixed order."""
    for product in config.TABLET_PRODUCTS.get(category, ()):
        for label, strips in config.TABLET_PACKS:
            yield f"{product} ({label})", config.FORM_TABLET, strips
    for product in config.BOTTLE_PRODUCTS.get(category, ()):
        yield product, config.FORM_BOTTLE, None
    for product, per_box, price in config.PIECE_PRODUCTS.get(category, ()):
        yield product, config.FORM_PIECE, (per_box, price)


def build_skus(seed: str) -> list[Sku]:
    r = rng(seed, "skus")
    renamed_from = {new: old for old, new in config.RENAMES.items()}

    skus: list[Sku] = []
    for cat_code, cat_name, vat in config.CATEGORIES:
        products = list(_products(cat_code))[: config.SKUS_PER_CATEGORY[cat_code]]
        assert len(products) == config.SKUS_PER_CATEGORY[cat_code], cat_code
        for name, form, arg in products:
            if form == config.FORM_TABLET:
                uoms = _tablet_uoms(r, cat_code, arg)
                base, receive, shelf_life = "TAB", "BOX", r.choice((730, 1095))
            elif form == config.FORM_BOTTLE:
                uoms = _bottle_uoms(r)
                base, receive, shelf_life = "BOTTLE", "CARTON", r.choice((540, 730))
            else:
                uoms = _piece_uoms(*arg)
                base, receive, shelf_life = "PIECE", "BOX", r.choice((1095, 1825))
            current = config.RENAMES.get(name, name)
            skus.append(
                Sku(
                    item_no=f"{100001 + len(skus)}",
                    name=current,
                    old_name=renamed_from.get(current),
                    category_code=cat_code,
                    category_name=cat_name,
                    vat_rate=vat,
                    form=form,
                    base_uom=base,
                    receive_uom=receive,
                    uoms=uoms,
                    shelf_life_days=shelf_life,
                    popularity=0.0,
                    created_on=date(2015, 1, 1) + timedelta(days=r.randrange(3650)),
                )
            )

    # Demand follows a long tail: no single SKU dominates, the best sellers
    # sell every hour, and the slow tail sells a few times a month. The slow
    # tail is where near-expiry stock piles up.
    ranks = list(range(1, len(skus) + 1))
    r.shuffle(ranks)
    return [replace(s, popularity=round(1.0 / (rank + 10) ** 1.3, 6)) for s, rank in zip(skus, ranks)]
