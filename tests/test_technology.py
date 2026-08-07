"""Technology layer: research selection, resource accounting, and bonuses.

Layer 6 of the tick loop had no test module. These cover the parts other
layers depend on — `combat.py` reads `combat_bonus`, and the economy reads
`raid_multiplier` — plus the ordering properties that keep research
reproducible across processes and Python versions.
"""

from __future__ import annotations

import random

import pytest

from thalren_vale.technology import (
    TECH_TREE,
    _can_afford,
    _choose_next_tech,
    _deduct_cost,
    _ensure_tech,
    _pooled_resources,
    _research_duration,
    _researchable,
    combat_bonus,
    defense_bonus,
    has_tech,
    raid_multiplier,
)


class Member:
    def __init__(self, **inventory):
        self.inventory = dict(inventory)


class Faction:
    def __init__(self, members=(), food_reserve=0, beliefs=(), techs=None):
        self.members = list(members)
        self.food_reserve = food_reserve
        self.shared_beliefs = list(beliefs)
        if techs is not None:
            self.techs = set(techs)
            self.active_research = None


def rich(**extra):
    """A faction that can afford anything in the tree."""
    inventory = {"food": 99, "wood": 99, "stone": 99, "ore": 99}
    inventory.update(extra)
    return Faction(members=[Member(**inventory)], techs=set())


# ── Lazy state attachment ───────────────────────────────────────────────────

def test_ensure_tech_attaches_state_once():
    faction = Faction()
    _ensure_tech(faction)
    assert faction.techs == set()
    assert faction.active_research is None


def test_ensure_tech_does_not_clobber_existing_research():
    faction = Faction(techs={"tools"})
    faction.active_research = {"tech": "farming"}
    _ensure_tech(faction)
    assert faction.techs == {"tools"}
    assert faction.active_research == {"tech": "farming"}


# ── Resource pooling ────────────────────────────────────────────────────────

def test_pool_sums_members_and_food_reserve():
    faction = Faction(
        members=[Member(food=3, wood=2), Member(food=4, ore=1)],
        food_reserve=10,
    )
    pool = _pooled_resources(faction)
    assert pool == {"food": 17, "wood": 2, "ore": 1}


def test_pool_reports_food_reserve_even_with_no_members():
    assert _pooled_resources(Faction(food_reserve=7))["food"] == 7


def test_affordability_requires_every_cost_component():
    # tools costs wood 4 + stone 4; wood alone is not enough.
    faction = Faction(members=[Member(wood=99)])
    assert _can_afford(faction, "tools") is False
    faction.members[0].inventory["stone"] = 4
    assert _can_afford(faction, "tools") is True


def test_affordability_is_inclusive_at_the_exact_cost():
    faction = Faction(members=[Member(wood=4, stone=4)])
    assert _can_afford(faction, "tools") is True


# ── Cost deduction ──────────────────────────────────────────────────────────

def test_food_is_taken_from_the_reserve_before_member_inventories():
    # scavenging costs food 5.
    faction = Faction(members=[Member(food=100)], food_reserve=5)
    _deduct_cost(faction, "scavenging")
    assert faction.food_reserve == 0
    assert faction.members[0].inventory["food"] == 100


def test_deduction_falls_through_to_members_when_the_reserve_is_short():
    faction = Faction(members=[Member(food=10)], food_reserve=2)
    _deduct_cost(faction, "scavenging")
    assert faction.food_reserve == 0
    assert faction.members[0].inventory["food"] == 7  # 5 - 2 taken from reserve


def test_deduction_spreads_across_members_and_removes_exactly_the_cost():
    faction = Faction(members=[Member(wood=3), Member(wood=3, stone=9)])
    before = sum(m.inventory.get("wood", 0) for m in faction.members)
    _deduct_cost(faction, "tools")  # wood 4, stone 4
    after = sum(m.inventory.get("wood", 0) for m in faction.members)
    assert before - after == 4
    assert sum(m.inventory.get("stone", 0) for m in faction.members) == 5


def test_deduction_never_drives_an_inventory_negative():
    faction = Faction(members=[Member(wood=1), Member(wood=1)])
    _deduct_cost(faction, "tools")
    assert all(v >= 0 for m in faction.members for v in m.inventory.values())


# ── Prerequisites ───────────────────────────────────────────────────────────

def test_researchable_excludes_owned_techs():
    faction = Faction(techs={"tools"})
    assert "tools" not in _researchable(faction)


def test_researchable_requires_every_prerequisite():
    faction = Faction(techs={"weaponry", "metalwork", "scavenging"})
    # steel needs weaponry AND masonry; masonry is missing.
    assert "steel" not in _researchable(faction)
    faction.techs.add("masonry")
    assert "steel" in _researchable(faction)


def test_tier_one_techs_are_researchable_from_nothing():
    available = set(_researchable(Faction(techs=set())))
    assert {"tools", "scavenging", "oral_tradition"} <= available


# ── Research duration ───────────────────────────────────────────────────────

def test_engineering_shortens_research_by_twenty_percent():
    plain = Faction(techs=set())
    engineer = Faction(techs={"engineering"})
    assert _research_duration(plain, "steel") == TECH_TREE["steel"]["ticks"]
    assert _research_duration(engineer, "steel") == int(
        TECH_TREE["steel"]["ticks"] * 0.80)


def test_research_duration_never_drops_below_five_ticks():
    faction = Faction(techs={"engineering"})
    assert all(_research_duration(faction, tech) >= 5 for tech in TECH_TREE)


def test_research_duration_tolerates_a_faction_without_tech_state():
    assert _research_duration(Faction(), "tools") == TECH_TREE["tools"]["ticks"]


# ── Selection, and its ordering properties ──────────────────────────────────

def test_no_affordable_tech_returns_none():
    assert _choose_next_tech(Faction(members=[Member()], techs=set())) is None


def test_belief_affinity_steers_the_branch():
    martial = rich()
    martial.shared_beliefs = ["the_strong_take", "victory_proves_strength"]
    random.seed(7)
    assert TECH_TREE[_choose_next_tech(martial)]["branch"] == "martial"

    civic = rich()
    civic.shared_beliefs = ["the_wise_must_lead", "loyalty_above_all"]
    random.seed(7)
    assert TECH_TREE[_choose_next_tech(civic)]["branch"] == "civic"


def test_selection_is_reproducible_for_the_same_seed_and_state():
    picks = []
    for _ in range(3):
        faction = rich()
        faction.shared_beliefs = ["trade_builds_bonds"]
        random.seed(12345)
        picks.append(_choose_next_tech(faction))
    assert len(set(picks)) == 1


def test_selection_does_not_depend_on_belief_order():
    """Beliefs are tallied into a dict; the tally must not be order-sensitive.

    `shared_beliefs` is append-mutated at runtime, so the same faction can hold
    the same beliefs in different orders. Two orders that vote for the same
    branch must not research different things.
    """
    beliefs = ["trade_builds_bonds", "community_sustains", "the_sea_provides"]
    picks = []
    for order in (beliefs, list(reversed(beliefs))):
        faction = rich()
        faction.shared_beliefs = list(order)
        random.seed(99)
        picks.append(_choose_next_tech(faction))
    assert picks[0] == picks[1], picks


def test_researchable_order_follows_the_tech_tree_not_the_owned_set():
    """Ordering must come from TECH_TREE, which is insertion-ordered.

    `faction.techs` is a set. If selection ever ordered candidates by iterating
    it, results would differ across Python versions, because the string hash
    changed in 3.11. Building the candidate list from the dict keeps the order
    stable; this pins that.
    """
    owned = {"tools", "scavenging", "oral_tradition"}
    expected = [t for t in TECH_TREE if t not in owned
                and all(r in owned for r in TECH_TREE[t]["requires"])]
    for _ in range(5):
        faction = Faction(techs=set(owned))
        assert _researchable(faction) == expected


# ── Bonuses read by other layers ────────────────────────────────────────────

@pytest.mark.parametrize("techs,expected", [
    (set(), 1.0),
    ({"metalwork"}, 1.30),
    ({"weaponry"}, 1.50),
    ({"steel"}, 1.80),
    ({"metalwork", "weaponry", "steel"}, 1.80),
    ({"metalwork", "weaponry"}, 1.50),
])
def test_combat_bonus_takes_the_strongest_tech(techs, expected):
    assert combat_bonus(Faction(techs=techs)) == expected


@pytest.mark.parametrize("techs,expected", [
    (set(), 1.0), ({"masonry"}, 1.20), ({"steel"}, 1.20),
    ({"masonry", "steel"}, 1.20), ({"weaponry"}, 1.0),
])
def test_defense_bonus_responds_to_masonry_or_steel(techs, expected):
    assert defense_bonus(Faction(techs=techs)) == expected


@pytest.mark.parametrize("techs,expected", [
    (set(), 1), ({"scavenging"}, 2), ({"weaponry"}, 3), ({"steel"}, 4),
    ({"scavenging", "weaponry", "steel"}, 4),
])
def test_raid_multiplier_takes_the_strongest_tech(techs, expected):
    assert raid_multiplier(Faction(techs=techs)) == expected


def test_accessors_tolerate_a_faction_with_no_tech_state():
    """combat.py calls these on any faction, including one never researched."""
    bare = Faction()
    assert has_tech(bare, "steel") is False
    assert combat_bonus(bare) == 1.0
    assert defense_bonus(bare) == 1.0
    assert raid_multiplier(bare) == 1
