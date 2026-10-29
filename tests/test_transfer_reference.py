"""The transfer reference proposes what DR-012 says, and nothing the contract forbids.

The reference reads only the raw extracts. Its rules are written from
DR-012's text; this file reads the numbers from the action contract, so
the two must agree. Needs `make data`.
"""

from collections import Counter
from datetime import date

import pytest
import yaml

from reference import Reference
from repo import ROOT

AS_OF = date(2026, 9, 15)
RULES = yaml.safe_load((ROOT / "actions" / "propose_transfer.yml").read_text(encoding="utf-8"))["rules"]


@pytest.fixture(scope="module")
def ref() -> Reference:
    return Reference()


@pytest.fixture(scope="module")
def proposals(ref) -> dict[tuple[str, str], dict]:
    return {(p["target"], p["sku"]): p for p in ref.transfer_candidates(AS_OF)}


@pytest.fixture(scope="module")
def pairs(ref) -> list[dict]:
    rows = ref._run("transfer_candidates", {"as_of": AS_OF})
    columns = [d[0] for d in ref.con.description]
    return [dict(zip(columns, row)) for row in rows]


# DR-012's worked examples


def test_a_full_proposal(proposals):
    p = proposals[("NW013", "100056")]
    assert (p["donor"], p["quantity"], p["unit"], p["base_units"], p["partial"]) == ("NW009", 6, "BOX", 600, False)
    assert p["target_cover_after"] == pytest.approx(16.0, abs=0.05)
    assert p["donor_cover_after"] == pytest.approx(61.4, abs=0.05)


def test_a_partial_proposal_from_the_only_donor_in_reach(proposals, pairs):
    p = proposals[("NW014", "100025")]
    assert (p["donor"], p["quantity"], p["partial"]) == ("NW003", 2, True)
    assert p["target_cover_after"] == pytest.approx(5.67, abs=0.005)
    assert [q["donor"] for q in pairs if (q["target"], q["sku"]) == ("NW014", "100025")] == ["NW003"]


def test_the_nearest_donor_in_another_district_goes_to_the_most_urgent_target(proposals):
    first, second = proposals[("NW025", "100146")], proposals[("NW022", "100146")]
    assert first["target_cover_before"] < second["target_cover_before"]
    assert (first["donor"], first["quantity"], round(first["drive_minutes"], 1)) == ("NW011", 3, 6.9)
    # NW011 has nothing left, so NW022 goes to its next nearest donor.
    assert (second["donor"], second["quantity"], round(second["drive_minutes"], 1)) == ("NW023", 1, 26.7)


def test_no_proposal_when_one_carton_would_last_a_year(proposals, pairs):
    options = [q for q in pairs if (q["target"], q["sku"]) == ("NW001", "100125")]
    assert len(options) == 6 and options[0]["cap_units"] == 0
    assert ("NW001", "100125") not in proposals


def test_the_snapshot_totals(proposals):
    assert len(proposals) == 108
    assert sum(p["partial"] for p in proposals.values()) == 28
    assert Counter(p["unit"] for p in proposals.values()) == {"BOX": 94, "CARTON": 14}


# Every proposal obeys the contract


def test_every_proposal_obeys_the_rules(proposals):
    for p in proposals.values():
        assert p["target_cover_before"] < RULES["target_max_cover_days"]
        assert p["target_cover_after"] <= RULES["target_max_after_days"]
        assert (p["target_cover_after"] < RULES["target_fill_days"]) == p["partial"]
        assert p["donor_cover_before"] > RULES["donor_min_cover_days"]
        assert p["donor_cover_after"] >= RULES["donor_keep_days"]
        assert p["drive_minutes"] <= RULES["max_drive_minutes"]
        assert p["quantity"] >= 1


def test_quantities_are_whole_purchase_units(ref, proposals):
    units = dict(ref.con.execute("select sku, purchase_unit from raw_skus").fetchall())
    sizes = {(s, u): f for s, u, f in ref.con.execute("select sku, unit, factor from raw_units").fetchall()}
    for p in proposals.values():
        assert p["unit"] == units[p["sku"]]
        assert p["base_units"] == p["quantity"] * sizes[(p["sku"], p["unit"])]


def test_excluded_stores_are_on_neither_side(ref, proposals):
    lagging = {s for s, _ in ref._run("lagging_stores", {"store": None, "district": None, "as_of": AS_OF})}
    assert lagging == {"NW029", "NW030"}
    stores = {p["target"] for p in proposals.values()} | {p["donor"] for p in proposals.values()}
    assert not stores & lagging


def test_a_donor_never_gives_more_than_it_can_spare(proposals, pairs):
    spare = {(q["donor"], q["sku"]): q["spare_units"] for q in pairs}
    given = Counter()
    for p in proposals.values():
        given[(p["donor"], p["sku"])] += p["quantity"]
    assert all(given[k] <= spare[k] for k in given)
    # The limit is reached, not just respected: some donors give all they can spare.
    assert any(given[k] == spare[k] for k in given)
