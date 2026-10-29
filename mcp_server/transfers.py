"""Transfer proposals under the action contract, from the certified metrics.

The rules and the metric versions they were checked against come from
actions/propose_transfer.yml (why: decisions/DR-012.md). The numbers come
from the semantic layer: available_stock and days_of_cover at the data date,
and units_sold_28d for the pace inside days_of_cover. Purchase units and
drive times come from the contracted marts dim_sku and fct_store_routes.

golden/reference/transfer_candidates.sql computes the same proposals from
the raw extracts, written from DR-012's text; tests/test_transfers.py checks
that the two agree.

Nothing here writes. mcp_server/shadow.py keeps the proposals an agent files.
"""

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "golden")]

import duckdb  # noqa: E402
import yaml  # noqa: E402

from run_golden import store_sync_state  # noqa: E402
from semantic_client import DUCKDB_FILE, READ_ONLY  # noqa: E402

CONTRACT = ROOT / "actions" / "propose_transfer.yml"
AS_OF = date(2026, 9, 15)  # dbt var snapshot_date: stock positions exist only on this day
SHARED_DONOR_ORDER = ["target_cover", "target_store"]


class Refused(Exception):
    """The engine will not propose anything: the contract and the data disagree."""


@dataclass(frozen=True)
class Position:
    available: int  # base units (DR-001, DR-003)
    sold_28d: int  # base units sold in the 28 full days before the as-of day
    cover: float | None  # days_of_cover, as the semantic layer serves it


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def check_versions(sl, contract: dict) -> dict[str, int]:
    """The metric versions the rules were checked against must be the ones served."""
    if contract.get("status") != "certified":
        raise Refused(f"{contract.get('action')} is {contract.get('status')}, not certified")
    pins = contract["reads"]["metrics"]
    for metric, pin in pins.items():
        meta = sl.governance(metric)
        if meta.get("status") != "certified":
            raise Refused(f"the contract reads {metric}, which the semantic layer does not serve as certified")
        if str(meta.get("version")) != str(pin):
            raise Refused(f"the contract pins {metric} v{pin}, the semantic layer serves v{meta.get('version')}; "
                          f"supply chain must re-check {contract['decision']} first")
    for block in contract["reads"].get("building_blocks") or []:
        if block not in sl.metrics:
            raise Refused(f"the contract reads {block}, which the semantic layer does not have")
    return {m: int(v) for m, v in pins.items()}


def _by_store_sku(sl, metric: str, day: date) -> dict[tuple[str, str], float | None]:
    where = ["{{ TimeDimension('metric_time', 'day') }} = '%s'" % day]
    return {(r["store"], r["sku"]): r[metric] for r in sl.query([metric], ["metric_time__day", "store", "sku"], where)}


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


class TransferPlanner:
    """Every proposal DR-012 makes at the data date, and why each other target gets none."""

    def __init__(self, sl, contract: dict | None = None, as_of: date = AS_OF):
        self.contract = contract or load_contract()
        self.rules = self.contract["rules"]
        if self.rules.get("shared_donor_order") != SHARED_DONOR_ORDER:
            raise Refused(f"shared_donor_order {self.rules.get('shared_donor_order')} is not one this engine implements")
        self.as_of = as_of
        self.metric_versions = check_versions(sl, self.contract)
        self.positions = self._positions(sl)
        self.excluded = self._excluded(sl)
        self.units, self.routes = self._marts()
        self.proposals, self.reasons = self._allocate()

    # Inputs

    def _positions(self, sl) -> dict[tuple[str, str], Position]:
        available = _by_store_sku(sl, "available_stock", self.as_of)
        cover = _by_store_sku(sl, "days_of_cover", self.as_of)
        # The pace days_of_cover uses: the 28 full days before the as-of day.
        sold = _by_store_sku(sl, "units_sold_28d", self.as_of - timedelta(days=1))
        days = self.rules["pace_days"]
        positions = {}
        for key in set(available) | set(sold):
            p = Position(int(round(available.get(key) or 0)), int(sold.get(key) or 0), cover.get(key))
            expected = None if p.sold_28d == 0 else p.available * days / p.sold_28d
            if (expected is None) != (p.cover is None) or (expected is not None and not _close(expected, p.cover)):
                raise Refused(f"days_of_cover for {key[0]} / {key[1]} is {p.cover}, but available / pace is {expected}; "
                              "the metric no longer means what the rules assume")
            positions[key] = p
        return positions

    def _excluded(self, sl) -> dict[str, str]:
        excluded = {}
        for s in store_sync_state(sl):
            if s["data_through"] < self.as_of - timedelta(days=1):
                excluded[s["store"]] = "excluded:pos_sync_lag"
            elif s["opened_on"] >= self.as_of - timedelta(days=self.rules["pace_days"]):
                excluded[s["store"]] = "excluded:new_store"
        return excluded

    def _marts(self) -> tuple[dict[str, tuple[str, int]], dict[tuple[str, str], float]]:
        with duckdb.connect(str(DUCKDB_FILE), config=READ_ONLY) as con:
            units = {sku: (unit, int(factor)) for sku, unit, factor in con.execute(
                "select sku_code, purchase_uom, purchase_uom_factor from marts.dim_sku").fetchall()}
            routes = {(o, d): float(m) for o, d, m in con.execute(
                "select origin_store_code, destination_store_code, drive_minutes from marts.fct_store_routes").fetchall()}
        return units, routes

    # The rules, on whole numbers so a boundary like 7.0 days is exact

    def _pos(self, store: str, sku: str) -> Position:
        return self.positions.get((store, sku), Position(0, 0, None))

    def _is_target(self, p: Position) -> bool:
        return p.sold_28d > 0 and p.available * self.rules["pace_days"] < self.rules["target_max_cover_days"] * p.sold_28d

    def _spare(self, p: Position, factor: int) -> int:
        """Whole purchase units a store can give and keep donor_keep_days."""
        days = self.rules["pace_days"]
        return max(0, (days * p.available - self.rules["donor_keep_days"] * p.sold_28d) // (days * factor))

    def _is_donor(self, p: Position, factor: int) -> bool:
        return (p.sold_28d > 0 and p.available * self.rules["pace_days"] > self.rules["donor_min_cover_days"] * p.sold_28d
                and self._spare(p, factor) >= 1)

    def _need(self, p: Position, factor: int) -> int:
        """Whole purchase units to bring the target to target_fill_days, rounded up."""
        days = self.rules["pace_days"]
        return -(-(self.rules["target_fill_days"] * p.sold_28d - days * p.available) // (days * factor))

    def _cap(self, p: Position, factor: int) -> int:
        """Whole purchase units that keep the target at target_max_after_days or less."""
        days = self.rules["pace_days"]
        return (self.rules["target_max_after_days"] * p.sold_28d - days * p.available) // (days * factor)

    def _cover(self, available: int, sold: int) -> float | None:
        return None if sold == 0 else available * self.rules["pace_days"] / sold

    def _urgency(self, store: str, sku: str) -> tuple:
        p = self._pos(store, sku)
        return (Fraction(p.available * self.rules["pace_days"], p.sold_28d) if p.sold_28d else Fraction(10**9), store)

    def _donors(self, target: str, sku: str) -> list[tuple[float, str]]:
        """Donors of this SKU within reach of the target, nearest first."""
        factor = self.units[sku][1]
        return sorted(
            (self.routes[(store, target)], store)
            for (store, s), p in self.positions.items()
            if s == sku and store != target and store not in self.excluded
            and (store, target) in self.routes and self.routes[(store, target)] <= self.rules["max_drive_minutes"]
            and self._is_donor(p, factor)
        )

    def _allocate(self) -> tuple[dict[tuple[str, str], dict], dict[tuple[str, str], dict]]:
        targets = sorted(
            (key for key, p in self.positions.items() if key[0] not in self.excluded and self._is_target(p)),
            key=lambda k: (self._urgency(*k), k[1]),
        )
        left: dict[tuple[str, str], int] = {}
        proposals, reasons = {}, {}
        for target, sku in targets:
            unit, factor = self.units[sku]
            p = self._pos(target, sku)
            donors = self._donors(target, sku)
            if not donors:
                reasons[(target, sku)] = {"reason": "no_donor_in_reach",
                                          "detail": f"no store within {self.rules['max_drive_minutes']} minutes can spare a whole {unit}"}
                continue
            if self._cap(p, factor) < 1:
                reasons[(target, sku)] = {"reason": "one_unit_exceeds_60_days",
                                          "detail": f"one {unit} of {factor} would leave it above {self.rules['target_max_after_days']} days of cover"}
                continue
            for _, donor in donors:
                left.setdefault((donor, sku), self._spare(self._pos(donor, sku), factor))
            chosen = next(((m, d) for m, d in donors if left[(d, sku)] >= 1), None)
            if chosen is None:
                reasons[(target, sku)] = {"reason": "donors_already_promised",
                                          "detail": "every donor in reach has promised its spare units to more urgent targets"}
                continue
            minutes, donor = chosen
            need, cap = self._need(p, factor), self._cap(p, factor)
            quantity = min(need, cap, left[(donor, sku)])
            left[(donor, sku)] -= quantity
            proposals[(target, sku)] = self._proposal(target, donor, sku, quantity, minutes, partial=quantity < need)
        return proposals, reasons

    def _proposal(self, target: str, donor: str, sku: str, quantity: int, minutes: float, partial: bool) -> dict:
        unit, factor = self.units[sku]
        t, d = self._pos(target, sku), self._pos(donor, sku)
        moved = quantity * factor
        return {
            "as_of": self.as_of.isoformat(),
            "target_store": target,
            "donor_store": donor,
            "sku": sku,
            "quantity": quantity,
            "unit": unit,
            "base_units": moved,
            "drive_minutes": minutes,
            "partial": partial,
            "target_cover_before": self._cover(t.available, t.sold_28d),
            "target_cover_after": self._cover(t.available + moved, t.sold_28d),
            "donor_cover_before": self._cover(d.available, d.sold_28d),
            "donor_cover_after": self._cover(d.available - moved, d.sold_28d),
            "metric_versions": dict(self.metric_versions),
        }

    # What an agent asks

    def explain(self, store: str, sku: str) -> dict:
        """The rules' proposal for this store-SKU as a target, or why there is none."""
        if (store, sku) in self.proposals:
            return {"proposal": self.proposals[(store, sku)]}
        base = {"store": store, "sku": sku}
        if store in self.excluded:
            detail = {
                "excluded:pos_sync_lag": "its POS data lags (DR-004), so its stock and pace miss recent sales",
                "excluded:new_store": f"it opened inside the {self.rules['pace_days']}-day pace window, so its pace is not settled",
            }[self.excluded[store]]
            return {**base, "reason": self.excluded[store], "detail": detail}
        if (store, sku) in self.reasons:
            return {**base, **self.reasons[(store, sku)]}
        p = self._pos(store, sku)
        if p.sold_28d == 0:
            return {**base, "reason": "no_sales", "detail": "nothing sold in the 28 days, so it has no cover"}
        if not any(store in pair for pair in self.routes):
            return {**base, "reason": "no_route", "detail": "the logistics provider has no route for this store yet"}
        return {**base, "reason": "not_a_target", "cover": self._cover(p.available, p.sold_28d),
                "detail": f"it has {self.rules['target_max_cover_days']} days of cover or more"}

    def simulate(self, target: str, donor: str, sku: str, quantity: int) -> dict:
        """What sending `quantity` purchase units would do, checked against every rule. Writes nothing."""
        r = self.rules
        unit, factor = self.units[sku]
        t, d = self._pos(target, sku), self._pos(donor, sku)
        moved = quantity * factor
        days = r["pace_days"]
        minutes = self.routes.get((donor, target))
        # What the donor still has after the rules' proposals for more urgent targets.
        promised = sum(
            p["quantity"] for (tgt, s), p in self.proposals.items()
            if s == sku and p["donor_store"] == donor and tgt != target
            and (self._urgency(tgt, s), s) < (self._urgency(target, sku), sku)
        )
        left = self._spare(d, factor) - promised
        checks = [
            (f"quantity is a whole number of {unit}s, at least 1", quantity >= 1),
            ("target store is not excluded", target not in self.excluded),
            ("donor store is not excluded", donor not in self.excluded),
            (f"target has under {r['target_max_cover_days']} days of cover", self._is_target(t)),
            (f"donor has over {r['donor_min_cover_days']} days of cover",
             d.sold_28d > 0 and d.available * days > r["donor_min_cover_days"] * d.sold_28d),
            (f"donor keeps at least {r['donor_keep_days']} days of cover",
             d.sold_28d > 0 and days * (d.available - moved) >= r["donor_keep_days"] * d.sold_28d),
            (f"target ends at {r['target_max_after_days']} days of cover or less",
             t.sold_28d > 0 and days * (t.available + moved) <= r["target_max_after_days"] * t.sold_28d),
            (f"donor is within {r['max_drive_minutes']} minutes' drive",
             minutes is not None and minutes <= r["max_drive_minutes"]),
            ("donor has these units left after the rules' proposals for more urgent targets", quantity <= left),
        ]
        return {
            "target_store": target,
            "donor_store": donor,
            "sku": sku,
            "quantity": quantity,
            "unit": unit,
            "base_units": moved,
            "drive_minutes": minutes,
            "target_cover_before": self._cover(t.available, t.sold_28d),
            "target_cover_after": self._cover(t.available + moved, t.sold_28d),
            "donor_cover_before": self._cover(d.available, d.sold_28d),
            "donor_cover_after": self._cover(d.available - moved, d.sold_28d),
            "checks": [{"rule": rule, "passed": passed} for rule, passed in checks],
            "passes": all(passed for _, passed in checks),
            "rules_propose": self.explain(target, sku),
        }
