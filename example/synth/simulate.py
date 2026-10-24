"""Day-by-day simulation of stock, sales and transfers for the whole chain.

The simulation produces clean facts in memory. `extracts.py` then writes them
out the way each source system would, with its own quirks.

How stock behaves, on purpose, like a typical pharmacy ERP:
- Stock lives in batches (one lot, one expiry date, one cost). Sales take the
  batch that expires first (FEFO) and never an expired one.
- Purchase orders and transfers move whole boxes or cartons. Shelves sell by
  box, strip, tablet, bottle or piece, so on-hand is kept in base units.
- A shipped transfer stays in the sender's on-hand until the receiver
  confirms it. It is only reserved, so it cannot be sold. A cancelled transfer
  never leaves the shelf. This is why "available stock" must subtract
  outbound transfers in transit, but not cancelled ones.
- Expired batches are written off on the first day of each month, so stock
  that expired since then is still on hand at the snapshot.
- Lagging stores have no sales after their last sync, because nothing after
  that point has reached any system yet.
"""

import bisect
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from synth import config, rng
from synth.master import Sku, Store

RECEIPTS_PER_DAY = 45  # an average store on a weekday
LINES_PER_RECEIPT = ((1, 50), (2, 30), (3, 15), (4, 5))  # (lines, weight)
WEEKEND_FACTOR = 1.15
RAINY_SEASON = (6, 7, 8, 9)  # months when cough and cold demand rises
RAINY_SEASON_FACTOR = 1.3
EXPENSIVE_PIECE = 500_000  # devices sold one at a time, rarely
LOYALTY_SHARE = 0.08
LOYALTY_DISCOUNT = 0.05
PROMOTIONS = (  # (category, first day, last day, discount)
    ("VITA", date(2026, 7, 1), date(2026, 7, 31), 0.10),
    ("PAIN", date(2026, 4, 10), date(2026, 4, 20), 0.07),
)

REORDER_DAYS = 10  # reorder when stock covers fewer days than this
ORDER_DAYS = 30  # each order covers this many days of demand
# Suppliers set a minimum order per SKU. For slow sellers this means a store
# holds months of stock, which is how near-expiry value builds up.
MIN_ORDER_QTY = ((1, 45), (2, 25), (3, 15), (5, 15))  # (receive units, weight)
SHORT_DATED_SHARE = 0.12  # supplier deliveries that arrive close to expiry
SHORT_DATED_COST_FACTOR = 0.8
TRANSFERS_PER_DAY = (4, 10)
TRANSFER_CANCEL_SHARE = 0.05
TRANSFER_MIN_EXPIRY_DAYS = 120  # stores do not ship stock that is about to expire

# Opening hours, local time. (hour, weight)
HOURS_NORMAL = tuple(zip(range(7, 22), (3, 4, 5, 5, 6, 7, 6, 5, 5, 6, 7, 8, 8, 6, 4)))
HOURS_24H = tuple(zip(range(0, 7), (1, 1, 1, 1, 1, 1, 2))) + HOURS_NORMAL + ((22, 3), (23, 2))


def line_shapes(sku: Sku) -> tuple[tuple[str, int, int, int], ...]:
    """How one sales line of this SKU looks: (unit, weight, min qty, max qty)."""
    if sku.form == config.FORM_TABLET:
        return (("TAB", 25, 2, 10), ("STRIP", 60, 1, 3), ("BOX", 15, 1, 1))
    if sku.form == config.FORM_BOTTLE:
        return (("BOTTLE", 100, 1, 2),)
    if sku.uom("PIECE").price >= EXPENSIVE_PIECE:
        return (("PIECE", 100, 1, 1),)
    return (("PIECE", 70, 1, 3), ("BOX", 30, 1, 1))


def mean_base_units_per_line(sku: Sku) -> float:
    shapes = line_shapes(sku)
    total = sum(w for _, w, _, _ in shapes)
    return sum(w / total * (lo + hi) / 2 * sku.uom(u).factor for u, w, lo, hi in shapes)


@dataclass(slots=True)
class Batch:
    batch_id: str
    store: str
    item_no: str
    lot_no: str
    expiry: date
    received_on: date
    received_qty: int  # in the SKU's receive unit
    unit_cost: int  # VND per receive unit, excluding VAT
    source_doc: str  # PO-... or TRF-...
    on_hand: int  # base units, including stock reserved for transfers
    reserved: int = 0


@dataclass(slots=True)
class Transfer:
    transfer_no: str
    item_no: str
    lot_no: str
    from_store: str
    to_store: str
    qty: int  # in the SKU's receive unit
    created_on: date
    shipped_on: date
    arrives_on: date
    status: str = "TR"  # TR in transit, DL delivered, CX cancelled
    received_on: date | None = None
    updated_on: date | None = None
    batch: Batch | None = None  # where the reserved stock sits


@dataclass(slots=True)
class SaleLine:
    store: str
    day: date  # local business day
    receipt_seq: int  # per store and day
    line_no: int
    at: datetime  # local time
    item_no: str
    uom: str
    qty: int
    unit_price: int  # VND including VAT
    discount: int
    base_qty: int

    @property
    def amount(self) -> int:
        return self.qty * self.unit_price - self.discount


@dataclass
class Shelf:
    """One SKU in one store."""

    batches: list[Batch] = field(default_factory=list)  # sorted by expiry
    sellable: int = 0  # base units, on hand minus reserved
    on_order: int = 0  # base units
    daily_demand: float = 0.0  # expected base units per day

    def add(self, batch: Batch) -> None:
        keys = [b.expiry for b in self.batches]
        self.batches.insert(bisect.bisect_right(keys, batch.expiry), batch)
        self.sellable += batch.on_hand - batch.reserved


@dataclass
class World:
    stores: list[Store]
    skus: list[Sku]
    batches: list[Batch] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    sales: list[SaleLine] = field(default_factory=list)


def _days(first: date, last: date):
    d = first
    while d <= last:
        yield d
        d += timedelta(days=1)


class Simulation:
    def __init__(self, seed: str, stores: list[Store], skus: list[Sku]):
        self.world = World(stores, skus)
        self.skus = {s.item_no: s for s in skus}
        self.r_sales = rng(seed, "sales")
        self.r_stock = rng(seed, "stock")
        self.r_transfers = rng(seed, "transfers")

        r_moq = rng(seed, "moq")
        self.min_order = {
            s.item_no: r_moq.choices([q for q, _ in MIN_ORDER_QTY], [w for _, w in MIN_ORDER_QTY])[0]
            for s in skus
        }

        r_cost = rng(seed, "costs")
        self.cost_per_receive_unit = {}
        for s in skus:
            u = s.uom(s.receive_uom)
            gross = u.price if u.price is not None else u.factor * s.uom(s.base_uom).price
            self.cost_per_receive_unit[s.item_no] = gross / (1 + s.vat_rate / 100) * r_cost.uniform(0.62, 0.75)

        # Demand weights per SKU, with and without the rainy season bump.
        def weight(s: Sku, rainy: bool) -> float:
            w = s.popularity
            if s.form == config.FORM_PIECE and s.uom("PIECE").price >= EXPENSIVE_PIECE:
                w *= 0.1
            if rainy and s.category_code == "RESP":
                w *= RAINY_SEASON_FACTOR
            return w

        self.sku_list = skus
        self.cum_weights = {}
        for rainy in (False, True):
            acc, cum = 0.0, []
            for s in skus:
                acc += weight(s, rainy)
                cum.append(acc)
            self.cum_weights[rainy] = cum

        lines_mean = sum(n * w for n, w in LINES_PER_RECEIPT) / sum(w for _, w in LINES_PER_RECEIPT)
        total_weight = self.cum_weights[False][-1]
        self.shelves: dict[tuple[str, str], Shelf] = {}
        for st in stores:
            for s in skus:
                share = weight(s, False) / total_weight
                demand = RECEIPTS_PER_DAY * st.traffic * lines_mean * share * mean_base_units_per_line(s)
                self.shelves[(st.code, s.item_no)] = Shelf(daily_demand=demand)

        self.pending_orders: dict[date, list[tuple[str, str, int]]] = {}
        self.batch_seq = 0
        self.po_seq = 0
        self.transfer_seq = 0

    # Batches and purchase orders

    def _lot(self, r, day: date) -> str:
        return f"L{day:%y}{r.choice('ABCDEFGHJK')}{r.randrange(10000):04d}"

    def _new_batch(self, store: str, sku: Sku, qty: int, received_on: date, expiry: date,
                   lot: str, unit_cost: int, source_doc: str) -> Batch:
        self.batch_seq += 1
        b = Batch(
            batch_id=f"B{self.batch_seq:07d}", store=store, item_no=sku.item_no, lot_no=lot,
            expiry=expiry, received_on=received_on, received_qty=qty, unit_cost=unit_cost,
            source_doc=source_doc, on_hand=qty * sku.receive_factor,
        )
        self.world.batches.append(b)
        self.shelves[(store, sku.item_no)].add(b)
        return b

    def _supplier_batch(self, store: str, sku: Sku, qty: int, received_on: date, po: str) -> Batch:
        r = self.r_stock
        cost = self.cost_per_receive_unit[sku.item_no] * r.uniform(0.96, 1.05)
        if r.random() < SHORT_DATED_SHARE:
            # Distributors clear short-dated lots at a discount, and stores take them.
            remaining = r.randint(90, 300)
            cost *= SHORT_DATED_COST_FACTOR
        else:
            remaining = int(sku.shelf_life_days * r.uniform(0.45, 0.95))
        cost = round(cost)
        return self._new_batch(store, sku, qty, received_on, received_on + timedelta(days=remaining),
                               self._lot(r, received_on), cost, po)

    def _opening_stock(self, store: Store, sku: Sku, received_by: date) -> None:
        """Stock already on the shelf when the simulation starts, of mixed age."""
        r = self.r_stock
        shelf = self.shelves[(store.code, sku.item_no)]
        target = shelf.daily_demand * r.uniform(15, 45)
        n_batches = 1 if r.random() < 0.6 else 2
        for _ in range(n_batches):
            qty = max(self.min_order[sku.item_no], math.ceil(target / n_batches / sku.receive_factor))
            received = received_by - timedelta(days=r.randint(1, 180))
            # Stock already on the shelf is older than fresh deliveries.
            expiry = received_by + timedelta(days=r.randint(60, min(sku.shelf_life_days, 540)))
            cost = round(self.cost_per_receive_unit[sku.item_no] * r.uniform(0.96, 1.05))
            self.po_seq += 1
            self._new_batch(store.code, sku, qty, received, expiry, self._lot(r, received), cost,
                            f"PO{self.po_seq:06d}")

    def _order_qty(self, shelf: Shelf, sku: Sku) -> int:
        wanted = math.ceil(shelf.daily_demand * ORDER_DAYS / sku.receive_factor)
        return max(self.min_order[sku.item_no], wanted)

    def _replenish(self, day: date, store: Store) -> None:
        r = self.r_stock
        for sku in self.sku_list:
            shelf = self.shelves[(store.code, sku.item_no)]
            if shelf.sellable + shelf.on_order >= shelf.daily_demand * REORDER_DAYS:
                continue
            qty = self._order_qty(shelf, sku)
            arrives = day + timedelta(days=r.randint(1, 3))
            self.pending_orders.setdefault(arrives, []).append((store.code, sku.item_no, qty))
            shelf.on_order += qty * sku.receive_factor

    def _receive_orders(self, day: date) -> None:
        for store, item_no, qty in self.pending_orders.pop(day, []):
            sku = self.skus[item_no]
            self.shelves[(store, item_no)].on_order -= qty * sku.receive_factor
            self.po_seq += 1
            self._supplier_batch(store, sku, qty, day, f"PO{self.po_seq:06d}")

    def _write_off_expired(self, day: date) -> None:
        for shelf in self.shelves.values():
            for b in shelf.batches:
                if b.expiry < day and b.on_hand > b.reserved:
                    shelf.sellable -= b.on_hand - b.reserved
                    b.on_hand = b.reserved

    # Transfers

    def _create_transfers(self, day: date, open_stores: list[Store]) -> None:
        r = self.r_transfers
        # The first transfer created on the day before the snapshot is
        # cancelled, so the extract always holds one that a naive "shipped
        # but not received" filter would count as in transit.
        force_cancel = day == config.SALES_END - timedelta(days=1)
        if len(open_stores) < 2:
            return
        for _ in range(r.randint(*TRANSFERS_PER_DAY)):
            sku = r.choices(self.sku_list, cum_weights=self.cum_weights[False])[0]
            cover = {
                st.code: self.shelves[(st.code, sku.item_no)].sellable
                / max(self.shelves[(st.code, sku.item_no)].daily_demand, 1e-9)
                for st in open_stores
            }
            src = max(cover, key=cover.get)
            dst = min(cover, key=cover.get)
            if src == dst:
                continue
            factor = sku.receive_factor
            batch = next(
                (b for b in self.shelves[(src, sku.item_no)].batches
                 if b.expiry >= day + timedelta(days=TRANSFER_MIN_EXPIRY_DAYS)
                 and b.on_hand - b.reserved >= 2 * factor),
                None,
            )
            if batch is None:
                continue
            qty = min(r.randint(1, 3), (batch.on_hand - batch.reserved) // factor // 2)
            self.transfer_seq += 1
            t = Transfer(
                transfer_no=f"TRF{self.transfer_seq:05d}", item_no=sku.item_no, lot_no=batch.lot_no,
                from_store=src, to_store=dst, qty=qty, created_on=day - timedelta(days=r.randint(0, 1)),
                shipped_on=day, arrives_on=day + timedelta(days=r.randint(1, 3)), batch=batch,
            )
            batch.reserved += qty * factor
            self.shelves[(src, sku.item_no)].sellable -= qty * factor
            if r.random() < TRANSFER_CANCEL_SHARE or force_cancel:
                t.status = "CX"
                t.updated_on = day + timedelta(days=1)
                force_cancel = False
            self.world.transfers.append(t)

    def _settle_transfers(self, day: date) -> None:
        for t in self.world.transfers:
            if t.status != "TR" or t.batch is None:
                continue
            sku = self.skus[t.item_no]
            base = t.qty * sku.receive_factor
            if t.arrives_on == day:
                t.batch.on_hand -= base
                t.batch.reserved -= base
                t.status, t.received_on, t.updated_on = "DL", day, day
                self._new_batch(t.to_store, sku, t.qty, day, t.batch.expiry, t.lot_no,
                                t.batch.unit_cost, t.transfer_no)
                t.batch = None

    def _release_cancelled(self, day: date) -> None:
        for t in self.world.transfers:
            if t.status == "CX" and t.batch is not None and t.updated_on == day:
                base = t.qty * self.skus[t.item_no].receive_factor
                t.batch.reserved -= base
                self.shelves[(t.from_store, t.item_no)].sellable += base
                t.batch = None

    # Sales

    def _sell_line(self, shelf: Shelf, day: date, base_qty: int) -> bool:
        if shelf.sellable < base_qty:
            return False
        usable = [b for b in shelf.batches if b.expiry >= day and b.on_hand > b.reserved]
        if sum(b.on_hand - b.reserved for b in usable) < base_qty:
            return False  # what is left has expired and waits for write-off
        left = base_qty
        for b in usable:
            take = min(left, b.on_hand - b.reserved)
            b.on_hand -= take
            left -= take
            if left == 0:
                break
        shelf.sellable -= base_qty
        return True

    def _sell_day(self, day: date, store: Store) -> None:
        r = self.r_sales
        rainy = day.month in RAINY_SEASON
        cum = self.cum_weights[rainy]
        lam = RECEIPTS_PER_DAY * store.traffic * (WEEKEND_FACTOR if day.weekday() >= 5 else 1.0)
        n_receipts = max(0, round(r.gauss(lam, math.sqrt(lam))))
        hours = HOURS_24H if store.open_24h else HOURS_NORMAL
        hour_values = [h for h, _ in hours]
        hour_weights = [w for _, w in hours]
        line_counts = [n for n, _ in LINES_PER_RECEIPT]
        line_weights = [w for _, w in LINES_PER_RECEIPT]

        times = sorted(
            datetime(day.year, day.month, day.day, r.choices(hour_values, hour_weights)[0],
                     r.randrange(60), r.randrange(60))
            for _ in range(n_receipts)
        )
        for seq, at in enumerate(times, start=1):
            loyalty = r.random() < LOYALTY_SHARE
            line_no = 0
            for _ in range(r.choices(line_counts, line_weights)[0]):
                sku = r.choices(self.sku_list, cum_weights=cum)[0]
                shapes = line_shapes(sku)
                unit, _, lo, hi = r.choices(shapes, [w for _, w, _, _ in shapes])[0]
                qty = r.randint(lo, hi)
                u = sku.uom(unit)
                if not self._sell_line(self.shelves[(store.code, sku.item_no)], day, qty * u.factor):
                    continue  # out of stock, the customer leaves without it
                pct = LOYALTY_DISCOUNT if loyalty else 0.0
                for cat, first, last, promo in PROMOTIONS:
                    if sku.category_code == cat and first <= day <= last:
                        pct = max(pct, promo)
                gross = qty * u.price
                line_no += 1
                self.world.sales.append(
                    SaleLine(store.code, day, seq, line_no, at, sku.item_no, unit, qty, u.price,
                             int(round(gross * pct / 100)) * 100, qty * u.factor)
                )

    # Main loop

    def run(self) -> World:
        stores = self.world.stores
        for st in stores:
            if st.opened_on < config.SALES_START:
                for sku in self.sku_list:
                    self._opening_stock(st, sku, config.SALES_START)

        for day in _days(config.SALES_START, config.SALES_END):
            for st in stores:
                if st.opened_on - timedelta(days=1) == day:
                    # A new store is stocked from suppliers the day before it opens.
                    for sku in self.sku_list:
                        qty = self._order_qty(self.shelves[(st.code, sku.item_no)], sku)
                        self.po_seq += 1
                        self._supplier_batch(st.code, sku, qty, day, f"PO{self.po_seq:06d}")
            if day.day == 1:
                self._write_off_expired(day)
            self._receive_orders(day)
            self._settle_transfers(day)
            self._release_cancelled(day)

            open_stores = [st for st in stores if st.opened_on <= day]
            for st in open_stores:
                if day <= st.last_synced_day:
                    self._sell_day(day, st)
            for st in open_stores:
                self._replenish(day, st)
            self._create_transfers(day, open_stores)
        return self.world


def simulate(seed: str, stores: list[Store], skus: list[Sku]) -> World:
    return Simulation(seed, stores, skus).run()
