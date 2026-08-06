"""Exact-once language hooks on authentic committed economy transfers."""

from __future__ import annotations

import copy
import inspect
import random
from types import SimpleNamespace

import pytest

from thalren_vale import combat, diplomacy, economy, sim
from thalren_vale.coalitions import CoalitionRuntimeState
from thalren_vale.config import (
    LanguageEvolutionConfig,
    SimulationConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    CommunicationContext,
    LanguageInvariantError,
    LanguageRuntimeState,
    Meaning,
    communicate,
    initialize_language_runtime,
)
from thalren_vale.social import Relationship


SOCIAL_DISABLED = SocialMemoryConfig(False, False, 32, 25)
LANGUAGE_DISABLED = LanguageEvolutionConfig(False, 32, 3, 0.20, 0.10, 25, True)
LANGUAGE_ENABLED = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)


class PreserveOrderRandom:
    def shuffle(self, values):
        del values


def pair() -> tuple[Inhabitant, Inhabitant]:
    giver = Inhabitant("Giver", 0, 0)
    recipient = Inhabitant("Recipient", 0, 0)
    giver.inhabitant_id = 1
    recipient.inhabitant_id = 2
    giver.faction = None
    recipient.faction = None
    for resource in economy.RES_TRADE:
        giver.inventory[resource] = 0
        recipient.inventory[resource] = 0
    return giver, recipient


def runtime(seed: int = 11) -> LanguageRuntimeState:
    result = LanguageRuntimeState()
    initialize_language_runtime(result, seed)
    return result


def test_nested_individual_helpers_emit_exactly_one_post_commit_attempt(monkeypatch):
    giver, recipient = pair()
    giver.inventory["food"] = 3
    state = runtime()
    calls = []
    real_communicate = economy.communicate

    def observe(*args, **kwargs):
        calls.append((args, kwargs))
        return real_communicate(*args, **kwargs)

    monkeypatch.setattr(economy, "communicate", observe)
    active_ids = economy._individual_barter(
        [giver, recipient],
        5,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        rng=PreserveOrderRandom(),
    )

    assert active_ids == frozenset({1, 2})
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is giver and args[1] is recipient
    assert args[2] is Meaning.FOOD
    assert kwargs["context"] is CommunicationContext.AID_TRANSFER
    assert state.communication_attempt_count == 1
    assert giver.inventory["food"] == 2
    assert recipient.inventory["food"] == 1


def test_paid_individual_transfer_uses_seller_and_buyer_roles(monkeypatch):
    seller, buyer = pair()
    seller.inventory["food"] = 3
    buyer.currency = economy.BASE_PRICES["food"]
    state = runtime()
    roles = []
    real_communicate = economy.communicate

    def observe(*args, **kwargs):
        roles.append((args[0], args[1], kwargs["context"]))
        return real_communicate(*args, **kwargs)

    monkeypatch.setattr(economy, "communicate", observe)
    economy._individual_barter(
        [seller, buyer],
        6,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        rng=PreserveOrderRandom(),
    )

    assert roles == [(seller, buyer, CommunicationContext.PAID_TRADE)]
    assert state.communication_attempt_count == 1


def test_faction_commit_emits_exactly_once_for_donor_and_taker(
    monkeypatch,
):
    donor, taker = pair()
    donor.inventory["food"] = 5
    giver = SimpleNamespace(name="Givers", members=[donor])
    receiver = SimpleNamespace(name="Receivers", members=[taker])
    key = ("Givers", "Receivers")
    economy.trade_routes.clear()
    economy.faction_prices.clear()
    economy.RIVALRIES[key] = 0
    monkeypatch.setattr(economy, "add_belief", lambda *args: None)
    monkeypatch.setattr(economy.combat, "are_allied", lambda *args: False)
    monkeypatch.setattr(diplomacy, "trade_bonus", lambda *args: 1.0)
    state = runtime()
    calls = []
    real_communicate = economy.communicate

    def observe(*args, **kwargs):
        calls.append((args, kwargs))
        return real_communicate(*args, **kwargs)

    monkeypatch.setattr(economy, "communicate", observe)
    committed = economy._do_trade(
        giver,
        receiver,
        "food",
        3,
        9,
        [],
        key,
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        active_ids=frozenset({1, 2}),
    )

    assert committed is True
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is donor and args[1] is taker
    assert args[2] is Meaning.FOOD
    assert kwargs["context"] is CommunicationContext.FACTION_TRADE
    assert state.communication_attempt_count == 1


def test_failed_individual_and_faction_transfers_emit_zero_attempts(monkeypatch):
    giver, recipient = pair()
    giver.inventory["food"] = 2
    state = runtime()
    calls = []
    monkeypatch.setattr(
        economy,
        "communicate",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    economy._individual_barter(
        [giver, recipient],
        5,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        rng=PreserveOrderRandom(),
    )
    committed = economy._do_trade(
        SimpleNamespace(name="G", members=[giver]),
        SimpleNamespace(name="R", members=[recipient]),
        "food",
        3,
        6,
        [],
        ("G", "R"),
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        active_ids=frozenset({1, 2}),
    )

    assert committed is False
    assert calls == []
    assert state.communication_attempt_count == 0
    assert giver.language.next_invention_index == 0


def test_language_enabled_preserves_transfer_results_and_simulation_rng():
    initial = pair()
    initial[0].inventory["food"] = 3
    baseline = copy.deepcopy(initial)
    enabled = copy.deepcopy(initial)
    baseline_rng = random.Random(44)
    enabled_rng = random.Random(44)
    state = runtime(91)

    economy._individual_barter(
        list(baseline),
        1,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_DISABLED,
        rng=baseline_rng,
    )
    economy._individual_barter(
        list(enabled),
        1,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        rng=enabled_rng,
    )

    def nonlanguage(inhabitants):
        return [
            (
                dict(inhabitant.inventory),
                dict(inhabitant.trust),
                inhabitant.trade_count,
                inhabitant.currency,
                dict(inhabitant.relationships),
                inhabitant.health,
                inhabitant.faction,
            )
            for inhabitant in inhabitants
        ]

    assert nonlanguage(enabled) == nonlanguage(baseline)
    assert enabled_rng.getstate() == baseline_rng.getstate()
    assert state.communication_attempt_count == 1


def test_communication_cannot_mutate_relationship_coalition_or_faction_state():
    sender, receiver = pair()
    sender.relationships[2] = Relationship(trust=0.8, familiarity=0.8)
    receiver.relationships[1] = Relationship(trust=0.8, familiarity=0.8)
    sender.faction = "A"
    receiver.faction = "B"
    coalitions = CoalitionRuntimeState()
    population = [sender, receiver]
    before_relationships = copy.deepcopy(
        (sender.relationships, receiver.relationships))
    before_coalitions = copy.deepcopy(coalitions)
    before_factions = (sender.faction, receiver.faction)
    before_inventories = copy.deepcopy((sender.inventory, receiver.inventory))
    before_health = (sender.health, receiver.health)
    before_population = tuple(population)
    before_wars = tuple(combat.active_wars)

    communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=LANGUAGE_ENABLED,
        runtime=runtime(),
    )

    assert (sender.relationships, receiver.relationships) == before_relationships
    assert coalitions == before_coalitions
    assert (sender.faction, receiver.faction) == before_factions
    assert (sender.inventory, receiver.inventory) == before_inventories
    assert (sender.health, receiver.health) == before_health
    assert tuple(population) == before_population
    assert tuple(combat.active_wars) == before_wars


@pytest.mark.parametrize(
    ("sender_id", "receiver_id", "active_ids"),
    [
        (True, 2, frozenset({1, 2})),
        (1, False, frozenset({1, 2})),
        (1, 1, frozenset({1})),
        (1, 2, frozenset({1})),
    ],
)
def test_communication_requires_distinct_active_exact_integer_ids(
    sender_id,
    receiver_id,
    active_ids,
):
    sender, receiver = pair()
    sender.inhabitant_id = sender_id
    receiver.inhabitant_id = receiver_id
    state = runtime()

    with pytest.raises(LanguageInvariantError):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=1,
            active_ids=active_ids,
            config=LANGUAGE_ENABLED,
            runtime=state,
        )

    assert state.communication_attempt_count == 0


def test_end_of_tick_maintenance_orders_social_coalition_then_language(
    monkeypatch,
):
    calls = []
    run_config = SimulationConfig(
        social_memory_enabled=True,
        coalition_emergence_enabled=True,
        language_evolution_enabled=True,
    )
    monkeypatch.setattr(sim, "people", [])
    monkeypatch.setattr(
        sim,
        "maintain_relationships",
        lambda *args, **kwargs: calls.append("social"),
    )

    def coalition(*args, **kwargs):
        calls.append("coalition")
        return args[1]

    monkeypatch.setattr(sim, "transition_informal_coalitions", coalition)
    monkeypatch.setattr(
        sim,
        "maintain_language_state",
        lambda *args, **kwargs: calls.append("language"),
    )

    sim.maintain_emergent_state(5, [], run_config)

    assert calls == ["social", "coalition", "language"]


def test_run_places_language_maintenance_after_economy_before_observation():
    source = inspect.getsource(sim.run)

    economy_position = source.index("economy_layer(")
    maintenance_position = source.index("maintain_emergent_state(")
    journal_position = source.index("_record_observation_journal(")
    metrics_position = source.index("_logger.record_tick(")
    hash_position = source.index("canonical_state_hash(")

    assert economy_position < maintenance_position < journal_position
    assert maintenance_position < metrics_position
    assert maintenance_position < hash_position
    assert source.count("maintain_emergent_state(") == 1


def test_no_transfer_opportunity_and_empty_maintenance_change_no_language():
    giver, recipient = pair()
    state = runtime()
    before_runtime = copy.deepcopy(state)
    before_languages = copy.deepcopy((giver.language, recipient.language))

    economy._individual_barter(
        [giver, recipient],
        25,
        [],
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE_ENABLED,
        language_runtime=state,
        rng=PreserveOrderRandom(),
    )
    from thalren_vale.language import maintain_language_state
    maintain_language_state(
        [giver, recipient],
        [],
        tick=25,
        config=LANGUAGE_ENABLED,
        runtime=state,
    )

    assert (giver.language, recipient.language) == before_languages
    assert state == before_runtime
