"""Deterministic directed relationship semantics and bounded maintenance."""

from __future__ import annotations

import random

import pytest

from thalren_vale.config import SocialMemoryConfig
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.social import (
    InteractionKind,
    Relationship,
    canonical_relationship_snapshot,
    maintain_relationships,
    record_interaction,
    relationship_summary,
    strongest_relationship_targets,
)


ENABLED = SocialMemoryConfig(True, True, 32, 25)


def person(name: str, inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(name, 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    return inhabitant


def test_live_interaction_enum_contains_only_authentic_implemented_kinds():
    assert set(InteractionKind) == {InteractionKind.AID, InteractionKind.TRADE}


def test_aid_creates_directed_trust_and_asymmetric_obligation_once():
    helper = person("Helper", 1)
    recipient = person("Recipient", 2)
    unrelated = person("Unrelated", 3)

    recorded = record_interaction(
        helper,
        recipient,
        InteractionKind.AID,
        tick=7,
        active_ids=frozenset({1, 2, 3}),
        config=ENABLED,
    )

    assert recorded is True
    toward_helper = recipient.relationships[1]
    toward_recipient = helper.relationships[2]
    assert toward_helper.trust == 0.08
    assert toward_helper.obligation == 0.10
    assert toward_helper.interaction_count == 1
    assert toward_helper.last_interaction_tick == 7
    assert toward_recipient.trust == 0.0
    assert toward_recipient.obligation == 0.0
    assert toward_recipient.interaction_count == 1
    assert unrelated.relationships == {}


def test_trade_creates_reciprocal_familiarity_and_modest_trust():
    seller = person("Seller", 10)
    buyer = person("Buyer", 11)

    record_interaction(
        seller,
        buyer,
        InteractionKind.TRADE,
        tick=4,
        active_ids=frozenset({10, 11}),
        config=ENABLED,
    )

    assert seller.relationships[11].familiarity == 0.08
    assert buyer.relationships[10].familiarity == 0.08
    assert seller.relationships[11].trust == 0.03
    assert buyer.relationships[10].trust == 0.03


def test_repeated_interactions_accumulate_and_clamp_every_field():
    helper = person("Helper", 1)
    recipient = person("Recipient", 2)

    for tick in range(20):
        record_interaction(
            helper,
            recipient,
            InteractionKind.AID,
            tick=tick,
            active_ids=frozenset({1, 2}),
            config=ENABLED,
        )

    record = recipient.relationships[1]
    assert record.trust == 1.0
    assert record.obligation == 1.0
    assert record.familiarity == 1.0
    assert record.interaction_count == 20


def test_directionality_does_not_imply_reciprocal_trust():
    actor = person("A", 1)
    target = person("B", 2)

    record_interaction(
        actor,
        target,
        InteractionKind.AID,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
    )

    assert target.relationships[1].trust > 0.0
    assert actor.relationships[2].trust == 0.0


def test_invalid_or_inactive_interaction_participants_fail_safely():
    actor = person("A", 1)
    target = person("B", 2)
    unassigned = Inhabitant("Temporary", 0, 0)

    with pytest.raises(ValueError, match="self-interactions"):
        record_interaction(
            actor,
            actor,
            InteractionKind.AID,
            tick=1,
            active_ids=frozenset({1}),
            config=ENABLED,
        )
    with pytest.raises(ValueError, match="assigned"):
        record_interaction(
            actor,
            unassigned,
            InteractionKind.AID,
            tick=1,
            active_ids=frozenset({1}),
            config=ENABLED,
        )
    with pytest.raises(TypeError, match="InteractionKind"):
        record_interaction(
            actor,
            target,
            "aid",  # type: ignore[arg-type]
            tick=1,
            active_ids=frozenset({1, 2}),
            config=ENABLED,
        )
    with pytest.raises(ValueError, match="magnitude"):
        record_interaction(
            actor,
            target,
            InteractionKind.AID,
            tick=1,
            magnitude=float("nan"),
            active_ids=frozenset({1, 2}),
            config=ENABLED,
        )

    assert record_interaction(
        actor,
        target,
        InteractionKind.AID,
        tick=1,
        active_ids=frozenset({1}),
        config=ENABLED,
    ) is False
    assert actor.relationships == {}
    assert target.relationships == {}


def test_decay_waits_for_inactivity_and_moves_values_toward_neutral():
    owner = person("Owner", 1)
    old_target = person("Old", 2)
    recent_target = person("Recent", 3)
    owner.relationships[2] = Relationship(
        trust=-0.50,
        affinity=0.50,
        grievance=0.40,
        obligation=0.30,
        familiarity=0.20,
        last_interaction_tick=0,
    )
    owner.relationships[3] = Relationship(
        trust=0.50,
        affinity=-0.50,
        grievance=0.40,
        obligation=0.30,
        familiarity=0.20,
        last_interaction_tick=10,
    )

    maintain_relationships(
        [owner, old_target, recent_target], [], tick=24, config=ENABLED)
    assert owner.relationships[2].trust == -0.50

    maintain_relationships(
        [owner, old_target, recent_target], [], tick=25, config=ENABLED)

    old = owner.relationships[2]
    recent = owner.relationships[3]
    assert old.trust == -0.49
    assert old.affinity == 0.49
    assert old.grievance == 0.38
    assert old.obligation == 0.28
    assert old.familiarity == 0.195
    assert recent.trust == 0.50
    assert recent.affinity == -0.50


def test_pruning_is_capped_deterministic_and_insertion_order_independent():
    targets = [person(f"T{target_id}", target_id) for target_id in (10, 20, 30)]
    config = SocialMemoryConfig(True, True, 2, 25)

    def retained(order: tuple[int, ...]) -> tuple[int, ...]:
        owner = person("Owner", 1)
        records = {
            10: Relationship(trust=0.9, last_interaction_tick=1),
            20: Relationship(grievance=0.8, last_interaction_tick=1),
            30: Relationship(familiarity=0.01, last_interaction_tick=0),
        }
        for target_id in order:
            owner.relationships[target_id] = records[target_id]
        maintain_relationships([owner, *targets], [], tick=1, config=config)
        return tuple(sorted(owner.relationships))

    assert retained((10, 20, 30)) == retained((30, 20, 10)) == (10, 20)


def test_dead_identities_are_removed_and_dead_memory_is_cleared():
    owner = person("Owner", 1)
    survivor = person("Survivor", 2)
    dead = person("Dead", 3)
    owner.relationships[2] = Relationship(trust=0.3)
    owner.relationships[3] = Relationship(trust=0.8)
    dead.relationships[1] = Relationship(trust=0.8)

    maintain_relationships([owner, survivor], [dead], tick=2, config=ENABLED)

    assert tuple(owner.relationships) == (2,)
    assert dead.relationships == {}


def test_invalid_relationship_cleanup_is_deterministic_and_rng_free():
    config = SocialMemoryConfig(True, True, 1, 25)

    def retained(order: tuple[object, ...]) -> tuple[int, ...]:
        owner = person("Owner", 1)
        valid = person("Valid", 2)
        records = {
            1: Relationship(trust=1.0),
            2: Relationship(trust=0.8),
            99: Relationship(trust=0.9),
            "malformed": Relationship(trust=1.0),
        }
        for target_id in order:
            owner.relationships[target_id] = records[target_id]

        before = random.getstate()
        maintain_relationships([owner, valid], [], tick=1, config=config)
        after = random.getstate()

        assert before == after
        assert all(len(inhabitant.relationships) <= 1
                   for inhabitant in (owner, valid))
        return tuple(owner.relationships)

    assert retained((1, 2, 99, "malformed")) == (2,)
    assert retained(("malformed", 99, 2, 1)) == (2,)


def test_unassigned_owner_relationships_are_removed():
    owner = Inhabitant("Unassigned", 0, 0)
    valid = person("Valid", 2)
    owner.relationships[2] = Relationship(trust=0.8)

    maintain_relationships([owner, valid], [], tick=1, config=ENABLED)

    assert owner.relationships == {}


def test_synthetic_population_remains_sparse_and_within_configured_cap():
    config = SocialMemoryConfig(True, True, 4, 25)
    people = [person(f"P{index}", index) for index in range(100)]
    active_ids = frozenset(range(100))

    for target in people[1:]:
        record_interaction(
            people[0],
            target,
            InteractionKind.TRADE,
            tick=1,
            active_ids=active_ids,
            config=config,
        )

    assert all(len(inhabitant.relationships) <= 4 for inhabitant in people)
    assert sum(len(inhabitant.relationships) for inhabitant in people) <= 100 * 4


def test_internal_social_observability_is_canonical_and_bounded():
    first = person("First", 1)
    second = person("Second", 2)
    third = person("Third", 3)
    first.relationships[3] = Relationship(trust=-0.2, grievance=0.4)
    first.relationships[2] = Relationship(trust=0.8, familiarity=0.5)

    snapshot = canonical_relationship_snapshot([third, first, second])
    summary = relationship_summary([first, second, third])

    assert [row["inhabitant_id"] for row in snapshot] == [1, 2, 3]
    assert [row["target_id"] for row in snapshot[0]["relationships"]] == [2, 3]
    assert summary.active_directed_ties == 2
    assert summary.positive_trust_ties == 1
    assert summary.negative_trust_ties == 1
    assert strongest_relationship_targets(
        first, current_tick=1, decay_interval=25, limit=1) == (2,)
