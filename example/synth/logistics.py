"""The logistics provider's route table between stores, over an invented city.

Stores get a position on a local map (`config.DISTRICT_LAYOUT`), and every
pair gets a road distance and a drive time: the straight line times a detour
factor, over the nearer bridge when the river is in between, slower in the
Old Quarter. The provider computes each direction separately (one-way
streets), re-sends a few pairs with an update, and has no routes yet for
stores opened in the last month.

Two random streams of their own ("geography", "routes"), so nothing else in
the extracts moves.
"""

import math
from datetime import timedelta
from pathlib import Path

from synth import config, rng
from synth.extracts import write_csv
from synth.master import Store


def river_x(y: float) -> float:
    return config.RIVER_X_KM + config.RIVER_MEANDER_KM * math.sin(y / 3.0)


def bank(x: float, y: float) -> str:
    return "west" if x < river_x(y) else "east"


def bridges() -> list[tuple[float, float]]:
    return [(river_x(y), y) for y in config.BRIDGES_Y_KM]


def place_stores(seed: str, stores: list[Store]) -> dict[str, tuple[float, float]]:
    """Each store's (x, y) in km, near its district's center and on the right bank."""
    r = rng(seed, "geography")
    positions = {}
    for s in stores:
        cx, cy, spread, side = config.DISTRICT_LAYOUT[s.district_code]
        while True:
            y = min(max(r.gauss(cy, spread), 0.5), config.CITY_HEIGHT_KM - 0.5)
            if side == "both":  # along the river, on a random bank
                x = river_x(y) + r.choice((-1, 1)) * r.uniform(0.4, 2.2)
            else:
                x = min(max(r.gauss(cx, spread), 0.5), config.CITY_WIDTH_KM - 0.5)
            if side == "both" or (bank(x, y) == side and abs(x - river_x(y)) > 0.3):
                break
        positions[s.code] = (round(x, 3), round(y, 3))
    return positions


def path_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line km between two points, through the nearer bridge across the river."""
    if bank(*a) == bank(*b):
        return math.dist(a, b)
    return min(math.dist(a, p) + math.dist(p, b) for p in bridges())


def routes(seed: str, stores: list[Store]) -> list[list]:
    """Rows of the provider's export: origin, destination, metres, seconds, computed_at (UTC)."""
    r = rng(seed, "routes")
    pos = place_stores(seed, stores)
    routed = [s for s in stores if s.opened_on not in config.NEW_STORE_OPENINGS]
    district = {s.code: s.district_code for s in stores}
    detour = {}
    rows = []
    for a in routed:
        for b in routed:
            if a.code == b.code:
                continue
            key = tuple(sorted((a.code, b.code)))
            detour.setdefault(key, r.uniform(1.25, 1.45))
            km = path_km(pos[a.code], pos[b.code]) * detour[key] * r.uniform(0.97, 1.03)
            slow = "D02" in (district[a.code], district[b.code])
            speed = config.OLD_QUARTER_SPEED_KMH if slow else config.ROAD_SPEED_KMH
            minutes = (km / speed * 60 + config.LOADING_MINUTES) * r.uniform(0.94, 1.06)
            computed = config.ROUTES_COMPUTED_AT + timedelta(minutes=r.randrange(0, 90))
            rows.append([a.code, b.code, round(km * 1000), round(minutes * 60), computed])
    # The provider re-sends some pairs the next day with an updated time,
    # always before the nightly extract ran (06:00 local is 23:00 UTC).
    resent = []
    for row in rows:
        if r.random() < config.ROUTE_RESEND_SHARE:
            later = row[4] + timedelta(minutes=r.randrange(120, 24 * 60))
            resent.append([row[0], row[1], row[2], round(row[3] * r.uniform(0.95, 1.05)), later])
    return rows + resent


def write_store_routes(out: Path, seed: str, stores: list[Store]) -> None:
    write_csv(
        out / "logistics" / "store_routes.csv",
        ["origin_code", "destination_code", "distance_m", "duration_s", "computed_at"],
        ([o, d, m, s, t.strftime("%Y-%m-%dT%H:%M:%SZ")] for o, d, m, s, t in routes(seed, stores)),
    )
