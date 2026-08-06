"""Causally isolated relationship feedback in existing resource sharing."""

from __future__ import annotations

import random

from thalren_vale import economy
from thalren_vale.config import SocialMemoryConfig
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.social import Relationship, canonical_relationship_snapshot


DISABLED = SocialMemoryConfig(False, False, 32, 25)
MEMORY_ONLY = SocialMemoryConfig(True, False, 32, 25)
ENABLED = SocialMemoryConfig(True, True, 32, 25)


def person(name: str, inhabitant_id: int, *, tile=(0, 0)) -> Inhabitant:
    inhabitant = Inhabitant(name, *tile)
    inhabitant.inhabitant_id = inhabitant_id
    for resource in economy.RES_TRADE:
        inhabitant.inventory[resource] = 0
    return inhabitant


def prepared_group(seed: int = 17) -> tuple[list[Inhabitant], list[int]]:
    people = [person(f"P{index}", index) for index in range(4)]
    order = list(range(4))
    random.Random(seed).shuffle(order)
    for rank, index in enumerate(order):
        people[index].inventory["food"] = 3 if rank % 2 == 0 else 0
    return people, order


def clone_group(people: list[Inhabitant]) -> list[Inhabitant]:
    clones = []
    for original in people:
        clone = person(
            original.name,
            original.inhabitant_id,
            tile=(original.r, original.c),
        )
        clone.inventory.update(original.inventory)
        clone.currency = original.currency
        clone.relationships.update(original.relationships)
        clones.append(clone)
    return clones


def legacy_state(people: list[Inhabitant]) -> list[tuple]:
    return [
        (
            inhabitant.inhabitant_id,
            dict(inhabitant.inventory),
            dict(inhabitant.trust),
            inhabitant.trade_count,
            inhabitant.currency,
        )
        for inhabitant in people
    ]


def test_enabled_empty_relationships_preserve_baseline_pairs_and_rng_state():
    initial, _order = prepared_group()
    baseline = clone_group(initial)
    enabled = clone_group(initial)
    repeated = clone_group(initial)
    baseline_rng = random.Random(17)
    enabled_rng = random.Random(17)
    repeated_rng = random.Random(17)

    economy._historical_barter(
        baseline,
        1,
        social_config=DISABLED,
        active_ids=frozenset(),
        rng=baseline_rng,
    )
    economy._individual_barter(
        enabled, 1, [], social_config=ENABLED, rng=enabled_rng)
    economy._individual_barter(
        repeated, 1, [], social_config=ENABLED, rng=repeated_rng)

    assert legacy_state(enabled) == legacy_state(baseline)
    assert enabled_rng.getstate() == baseline_rng.getstate()
    assert any(inhabitant.relationships for inhabitant in enabled)
    assert canonical_relationship_snapshot(enabled) == (
        canonical_relationship_snapshot(repeated)
    )
    assert repeated_rng.getstate() == enabled_rng.getstate()


def test_explicit_disabled_feature_uses_exact_historical_rng_path():
    initial, _order = prepared_group(seed=23)
    historical = clone_group(initial)
    disabled = clone_group(initial)
    historical_rng = random.Random(23)
    disabled_rng = random.Random(23)

    economy._historical_barter(
        historical,
        3,
        social_config=DISABLED,
        active_ids=frozenset(),
        rng=historical_rng,
    )
    economy._individual_barter(
        disabled, 3, [], social_config=DISABLED, rng=disabled_rng)

    assert legacy_state(disabled) == legacy_state(historical)
    assert disabled_rng.getstate() == historical_rng.getstate()
    assert all(not inhabitant.relationships for inhabitant in disabled)


def test_memory_enabled_bias_disabled_records_ties_without_changing_choice():
    initial, _order = prepared_group(seed=31)
    baseline = clone_group(initial)
    memory_only = clone_group(initial)
    baseline_rng = random.Random(31)
    memory_rng = random.Random(31)

    economy._historical_barter(
        baseline,
        2,
        social_config=DISABLED,
        active_ids=frozenset(),
        rng=baseline_rng,
    )
    economy._individual_barter(
        memory_only, 2, [], social_config=MEMORY_ONLY, rng=memory_rng)

    assert legacy_state(memory_only) == legacy_state(baseline)
    assert memory_rng.getstate() == baseline_rng.getstate()
    assert any(inhabitant.relationships for inhabitant in memory_only)


def test_positive_eligible_relationship_redirects_one_baseline_opportunity():
    people, order = prepared_group()
    giver = people[order[0]]
    baseline_target = people[order[1]]
    preferred = people[order[2]]
    preferred.inventory["food"] = 0
    giver.relationships[preferred.inhabitant_id] = Relationship(
        trust=0.9, familiarity=0.5)
    tick = next(tick for tick in range(1, 5)
                if (tick + giver.inhabitant_id) % 4 != 0)

    economy._individual_barter(
        people, tick, [], social_config=ENABLED, rng=random.Random(17))

    assert giver.trust.get(preferred.name) == 1
    assert giver.trust.get(baseline_target.name, 0) == 0
    assert preferred.inventory["food"] == 1
    assert baseline_target.inventory["food"] == 0


def test_authentic_interaction_memory_redirects_a_later_baseline_pair():
    class OrderedRandom:
        def __init__(self, order):
            self.rank = {name: index for index, name in enumerate(order)}

        def shuffle(self, values):
            values.sort(key=lambda inhabitant: self.rank[inhabitant.name])

    giver = person("Giver", 1)
    familiar = person("Familiar", 2)
    neutral = person("Neutral", 3)
    fourth = person("Fourth", 4)
    people = [giver, familiar, neutral, fourth]
    giver.inventory["food"] = 3

    economy._individual_barter(
        people,
        1,
        [],
        social_config=ENABLED,
        rng=OrderedRandom(["Giver", "Familiar", "Fourth", "Neutral"]),
    )
    assert giver.relationships[2].interaction_count == 1

    giver.inventory["food"] = 3
    familiar.inventory["food"] = 0
    neutral.inventory["food"] = 0
    exploitation_tick = next(
        tick for tick in range(2, 6)
        if (tick + giver.inhabitant_id) % 4 != 0
    )
    economy._individual_barter(
        people,
        exploitation_tick,
        [],
        social_config=ENABLED,
        rng=OrderedRandom(["Giver", "Neutral", "Familiar", "Fourth"]),
    )

    assert familiar.inventory["food"] == 1
    assert neutral.inventory["food"] == 0
    assert giver.relationships[2].interaction_count == 2
    assert 3 not in giver.relationships


def test_positive_but_ineligible_relationship_does_not_redirect():
    people, order = prepared_group()
    giver = people[order[0]]
    baseline_target = people[order[1]]
    ineligible = people[order[2]]
    ineligible.inventory["food"] = 1
    giver.relationships[ineligible.inhabitant_id] = Relationship(trust=1.0)
    tick = next(tick for tick in range(1, 5)
                if (tick + giver.inhabitant_id) % 4 != 0)

    economy._individual_barter(
        people, tick, [], social_config=ENABLED, rng=random.Random(17))

    assert giver.trust.get(baseline_target.name) == 1
    assert giver.trust.get(ineligible.name, 0) == 0


def test_staggered_exploration_retains_adjacent_unfamiliar_partner():
    people, order = prepared_group()
    giver = people[order[0]]
    baseline_target = people[order[1]]
    preferred = people[order[2]]
    preferred.inventory["food"] = 0
    giver.relationships[preferred.inhabitant_id] = Relationship(trust=1.0)
    tick = (-giver.inhabitant_id) % 4 or 4

    economy._individual_barter(
        people, tick, [], social_config=ENABLED, rng=random.Random(17))

    assert giver.trust.get(baseline_target.name) == 1
    assert giver.trust.get(preferred.name, 0) == 0


def test_no_baseline_transfer_opportunity_cannot_create_a_global_search():
    people, order = prepared_group()
    giver = people[order[0]]
    baseline_target = people[order[1]]
    preferred = people[order[2]]
    baseline_target.inventory["food"] = 1
    preferred.inventory["food"] = 0
    giver.relationships[preferred.inhabitant_id] = Relationship(trust=1.0)
    tick = next(tick for tick in range(1, 5)
                if (tick + giver.inhabitant_id) % 4 != 0)

    economy._individual_barter(
        people, tick, [], social_config=ENABLED, rng=random.Random(17))

    assert preferred.inventory["food"] == 0
    assert baseline_target.inventory["food"] == 1
    assert giver.trade_count == 0


def test_equal_scores_use_shuffled_rank_before_stable_id():
    people, order = prepared_group()
    giver = people[order[0]]
    baseline_target = people[order[1]]
    earlier_rank = people[order[2]]
    later_rank = people[order[3]]
    giver.inhabitant_id = 10
    baseline_target.inhabitant_id = 20
    earlier_rank.inhabitant_id = 99
    later_rank.inhabitant_id = 1
    earlier_rank.inventory["food"] = 0
    later_rank.inventory["food"] = 0
    giver.relationships = {
        earlier_rank.inhabitant_id: Relationship(trust=0.8),
        later_rank.inhabitant_id: Relationship(trust=0.8),
    }
    tick = next(tick for tick in range(1, 5)
                if (tick + giver.inhabitant_id) % 4 != 0)

    economy._individual_barter(
        people, tick, [], social_config=ENABLED, rng=random.Random(17))

    assert giver.trust.get(earlier_rank.name) == 1
    assert giver.trust.get(later_rank.name, 0) == 0


def test_enabled_path_performs_exactly_one_existing_shuffle_per_nontrivial_tile():
    class CountingRandom:
        def __init__(self):
            self.inner = random.Random(5)
            self.shuffle_count = 0

        def shuffle(self, values):
            self.shuffle_count += 1
            self.inner.shuffle(values)

    people = [
        person("A", 1, tile=(0, 0)),
        person("B", 2, tile=(0, 0)),
        person("C", 3, tile=(1, 1)),
        person("D", 4, tile=(1, 1)),
        person("E", 5, tile=(2, 2)),
    ]
    rng = CountingRandom()

    economy._individual_barter(
        people, 1, [], social_config=ENABLED, rng=rng)

    assert rng.shuffle_count == 2
