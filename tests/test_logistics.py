"""The logistics routes make district lines and travel time disagree, on purpose.

Checks the generator's geography and the routes mart built from it. Needs
`make data` and `make build`.
"""

import csv
import math
from datetime import datetime, timedelta

import duckdb
import pytest

from semantic_client import DUCKDB_FILE, READ_ONLY
from synth import config, logistics
from synth.master import build_stores

STORES = build_stores(config.SEED)
DISTRICT = {s.code: s.district_code for s in STORES}
NEW = {s.code for s in STORES if s.opened_on in config.NEW_STORE_OPENINGS}
EXTRACT_UTC = config.EXTRACT_AT - config.UTC_OFFSET


@pytest.fixture(scope="module")
def raw() -> list[dict]:
    from repo import ROOT

    with (ROOT / "example" / "data" / "logistics" / "store_routes.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def routes() -> dict[tuple[str, str], dict]:
    with duckdb.connect(str(DUCKDB_FILE), config=READ_ONLY) as con:
        rows = con.execute("select origin_store_code, destination_store_code, distance_km, drive_minutes "
                           "from marts.fct_store_routes").fetchall()
    return {(o, d): {"km": float(km), "minutes": float(m)} for o, d, km, m in rows}


def test_district_lines_do_not_say_what_is_near(routes):
    same = [r["minutes"] for (o, d), r in routes.items() if DISTRICT[o] == DISTRICT[d]]
    cross = [r["minutes"] for (o, d), r in routes.items() if DISTRICT[o] != DISTRICT[d]]
    # Some store in another district is closer than some store in the same one.
    assert min(cross) < max(same)
    # And for at least one store, the nearest other store is in another district.
    nearest = {o: min((r["minutes"], d) for (oo, d), r in routes.items() if oo == o)[1] for o, _ in routes}
    assert any(DISTRICT[o] != DISTRICT[d] for o, d in nearest.items())


def test_crossing_the_river_means_a_detour_over_a_bridge(routes):
    pos = logistics.place_stores(config.SEED, STORES)
    riverside = [c for c in pos if DISTRICT[c] == "D01" and c not in NEW]
    detours = [routes[(a, b)]["km"] / math.dist(pos[a], pos[b])
               for a in riverside for b in riverside
               if a != b and logistics.bank(*pos[a]) != logistics.bank(*pos[b])]
    assert detours and max(detours) > 2  # same district, opposite banks: far apart by road


def test_each_direction_is_computed_separately_but_close(routes):
    gaps = [abs(r["minutes"] - routes[(d, o)]["minutes"]) / max(r["minutes"], routes[(d, o)]["minutes"])
            for (o, d), r in routes.items()]
    assert max(gaps) < 0.15 and sum(g > 0 for g in gaps) > len(gaps) / 2


def test_new_stores_have_no_routes_yet_and_every_other_pair_has_one(routes):
    routed = [s.code for s in STORES if s.code not in NEW]
    assert NEW == {"NW029", "NW030"}
    assert not any(o in NEW or d in NEW for o, d in routes)
    assert set(routes) == {(a, b) for a in routed for b in routed if a != b}


def test_resent_routes_exist_and_the_latest_wins(raw, routes):
    by_pair: dict[tuple[str, str], list[dict]] = {}
    for row in raw:
        by_pair.setdefault((row["origin_code"], row["destination_code"]), []).append(row)
    resent = {k: v for k, v in by_pair.items() if len(v) > 1}
    assert len(resent) >= 10
    for pair, rows in resent.items():
        latest = max(rows, key=lambda r: r["computed_at"])
        assert routes[pair]["minutes"] == pytest.approx(int(latest["duration_s"]) / 60, abs=0.01)


def test_every_route_was_computed_before_the_extract(raw):
    stamps = [datetime.strptime(r["computed_at"], "%Y-%m-%dT%H:%M:%SZ") for r in raw]
    assert max(stamps) < EXTRACT_UTC and min(stamps) > EXTRACT_UTC - timedelta(days=7)


def test_the_same_seed_gives_the_same_routes():
    assert logistics.routes(config.SEED, STORES) == logistics.routes(config.SEED, STORES)
