"""Deterministic bounded protolanguage semantics and maintenance."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
import random

import pytest

from thalren_vale.config import LanguageEvolutionConfig
from thalren_vale.inhabitants import Inhabitant
from thalren_vale import language as language_module
from thalren_vale.language import (
    AgentLanguageState,
    AssociationOrigin,
    CommunicationContext,
    CommunicationResult,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Signal,
    _retain_canonical,
    canonical_language_snapshot,
    communicate,
    derive_invention_signal,
    initialize_language_runtime,
    language_runtime_is_pristine,
    lexical_convergence_snapshot,
    maintain_language_state,
    meaning_for_resource,
    validate_agent_language_state,
)


ENABLED = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 5, True)
DISABLED = LanguageEvolutionConfig(False, 32, 3, 0.20, 0.10, 5, True)


def person(name: str, inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(name, 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    inhabitant.faction = None
    return inhabitant


def runtime(seed: int = 123) -> LanguageRuntimeState:
    result = LanguageRuntimeState()
    initialize_language_runtime(result, seed)
    return result


def learned(
    meaning: Meaning,
    signal: Signal,
    confidence: float,
    *,
    source: int = 1,
    successful: int = 0,
    failed: int = 0,
    observations: int = 0,
    tick: int = 0,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        successful_uses=successful,
        failed_uses=failed,
        observation_count=observations,
        last_used_tick=tick,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=source,
    )


def invented(
    meaning: Meaning,
    signal: Signal,
    confidence: float,
    *,
    tick: int = 0,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        last_used_tick=tick,
        origin=AssociationOrigin.INVENTED,
    )


def language_population(
    count: int,
    *,
    first_id: int = 0,
) -> list[Inhabitant]:
    result = []
    for offset in range(count):
        inhabitant_id = first_id + offset
        inhabitant = person(f"Person {inhabitant_id}", inhabitant_id)
        signal = Signal((inhabitant_id % 8, (inhabitant_id // 8) % 8))
        inhabitant.language.production[(Meaning.FOOD, signal)] = invented(
            Meaning.FOOD,
            signal,
            0.60,
        )
        result.append(inhabitant)
    return result


def instrument_maintenance(monkeypatch) -> dict[str, int]:
    counts = {
        "identity": 0,
        "state_validation": 0,
        "association_validation": 0,
        "retention": 0,
    }
    real_identity = language_module._language_state_identity
    real_state_validation = language_module.validate_agent_language_state
    real_association_validation = language_module._validate_association
    real_retention = language_module._retain_canonical

    def counted_identity(*args, **kwargs):
        counts["identity"] += 1
        return real_identity(*args, **kwargs)

    def counted_state_validation(*args, **kwargs):
        counts["state_validation"] += 1
        return real_state_validation(*args, **kwargs)

    def counted_association_validation(*args, **kwargs):
        counts["association_validation"] += 1
        return real_association_validation(*args, **kwargs)

    def counted_retention(*args, **kwargs):
        counts["retention"] += 1
        return real_retention(*args, **kwargs)

    monkeypatch.setattr(
        language_module, "_language_state_identity", counted_identity)
    monkeypatch.setattr(
        language_module, "validate_agent_language_state", counted_state_validation)
    monkeypatch.setattr(
        language_module, "_validate_association", counted_association_validation)
    monkeypatch.setattr(language_module, "_retain_canonical", counted_retention)
    return counts


def test_meanings_are_exactly_the_committed_trade_resources():
    assert tuple(Meaning) == (
        Meaning.FOOD,
        Meaning.WOOD,
        Meaning.ORE,
        Meaning.STONE,
    )
    assert {resource: meaning_for_resource(resource) for resource in (
        "food", "wood", "ore", "stone"
    )} == {
        "food": Meaning.FOOD,
        "wood": Meaning.WOOD,
        "ore": Meaning.ORE,
        "stone": Meaning.STONE,
    }
    with pytest.raises(LanguageInvariantError, match="unsupported resource"):
        meaning_for_resource("water")


def test_counter_invention_has_pinned_canonical_vectors():
    state = runtime(123)

    assert state.seed_domain_fingerprint == (
        "f528213b24c7578a1cd82d384e2d205bc7244993373c16dfa03c506846118787"
    )
    assert derive_invention_signal(
        state,
        inventor_id=7,
        meaning=Meaning.FOOD,
        invention_index=0,
        maximum_signal_length=3,
    ).phoneme_ids == (5, 7)
    assert derive_invention_signal(
        state,
        inventor_id=7,
        meaning=Meaning.FOOD,
        invention_index=1,
        maximum_signal_length=3,
    ).phoneme_ids == (0, 7)


@pytest.mark.parametrize(
    "phonemes",
    [
        (1,),
        (0, 1, 2, 3, 4),
        (0, 8),
        (True, 1),
    ],
)
def test_signal_domain_rejects_noncanonical_or_out_of_bound_forms(phonemes):
    with pytest.raises(LanguageInvariantError, match="invalid_signal"):
        Signal(phonemes)


def test_effective_signal_and_all_vocabulary_caps_are_enforced_together():
    short_config = LanguageEvolutionConfig(True, 40, 2, 0.20, 0.10, 5, True)
    state = AgentLanguageState()
    long_signal = Signal((0, 1, 2))
    state.production[(Meaning.FOOD, long_signal)] = invented(
        Meaning.FOOD, long_signal, 0.50)

    with pytest.raises(LanguageInvariantError, match="maximum length"):
        validate_agent_language_state(state, config=short_config)

    candidates = AgentLanguageState()
    for index in range(9):
        signal = Signal((index // 8, index % 8))
        candidates.comprehension[(signal, Meaning.FOOD)] = learned(
            Meaning.FOOD, signal, 0.90 - index * 0.05)
    retained, lost = _retain_canonical(candidates, config=ENABLED)

    assert len(retained.comprehension) == 8
    assert lost == 1
    validate_agent_language_state(retained, config=ENABLED)


def test_unknown_learning_success_and_promotion_have_exact_counters():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime()
    active = frozenset({1, 2})

    first = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=1,
        active_ids=active,
        config=ENABLED,
        runtime=state,
    )

    assert first.result is CommunicationResult.UNKNOWN_SIGNAL
    signal = first.produced_signal
    assert signal is not None
    production = sender.language.production[(Meaning.FOOD, signal)]
    comprehension = receiver.language.comprehension[(signal, Meaning.FOOD)]
    assert (production.confidence, production.observation_count) == (0.45, 1)
    assert (production.successful_uses, production.failed_uses) == (0, 1)
    assert (comprehension.confidence, comprehension.observation_count) == (0.20, 1)
    assert (comprehension.successful_uses, comprehension.failed_uses) == (0, 0)
    assert receiver.language.production == {}
    assert sender.language.next_invention_index == 1
    assert state.communication_attempt_count == 1
    assert state.unknown_signal_count == 1
    assert state.invention_count == 1
    assert state.learned_association_count == 1

    for tick in (2, 3, 4):
        outcome = communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=active,
            config=ENABLED,
            runtime=state,
        )
        assert outcome.result is CommunicationResult.SUCCESS

    production = sender.language.production[(Meaning.FOOD, signal)]
    comprehension = receiver.language.comprehension[(signal, Meaning.FOOD)]
    promoted = receiver.language.production[(Meaning.FOOD, signal)]
    assert (production.confidence, production.observation_count) == (0.75, 4)
    assert (production.successful_uses, production.failed_uses) == (3, 1)
    assert (comprehension.confidence, comprehension.observation_count) == (0.50, 4)
    assert (comprehension.successful_uses, comprehension.failed_uses) == (3, 0)
    assert (promoted.confidence, promoted.observation_count) == (0.50, 1)
    assert (promoted.successful_uses, promoted.failed_uses) == (0, 0)
    assert promoted.origin is AssociationOrigin.LEARNED
    assert promoted.learned_from_id == 1
    assert state.successful_interpretation_count == 3
    assert state.learned_association_count == 2

    communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=5,
        active_ids=active,
        config=ENABLED,
        runtime=state,
    )
    promoted = receiver.language.production[(Meaning.FOOD, signal)]
    assert (promoted.confidence, promoted.observation_count) == (0.60, 2)
    assert (promoted.successful_uses, promoted.failed_uses) == (0, 0)


def test_misunderstanding_weakens_selected_mapping_once_and_teaches_correct_one():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime()
    signal = Signal((1, 2))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal, 0.50)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD, signal, 0.60, source=9)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD, signal, 0.20, source=1)

    outcome = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.PAID_TRADE,
        tick=3,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=state,
    )

    assert outcome.result is CommunicationResult.MISUNDERSTANDING
    wrong = receiver.language.comprehension[(signal, Meaning.WOOD)]
    correct = receiver.language.comprehension[(signal, Meaning.FOOD)]
    produced = sender.language.production[(Meaning.FOOD, signal)]
    assert (wrong.confidence, wrong.observation_count, wrong.failed_uses) == (
        0.50, 1, 1)
    assert (correct.confidence, correct.observation_count) == (0.40, 1)
    assert (correct.successful_uses, correct.failed_uses) == (0, 0)
    assert (produced.confidence, produced.observation_count, produced.failed_uses) == (
        0.45, 1, 1)
    assert state.misunderstanding_count == 1


def test_same_key_invention_collision_revives_at_fixed_confidence_then_uses_once():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime(99)
    signal = derive_invention_signal(
        state,
        inventor_id=1,
        meaning=Meaning.FOOD,
        invention_index=0,
        maximum_signal_length=3,
    )
    dormant = learned(
        Meaning.FOOD,
        signal,
        0.05,
        source=8,
        successful=2,
        observations=4,
    )
    sender.language.production[(Meaning.FOOD, signal)] = dormant

    outcome = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=state,
    )

    revived = sender.language.production[(Meaning.FOOD, signal)]
    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert revived.confidence == 0.45
    assert revived.origin is AssociationOrigin.LEARNED
    assert revived.learned_from_id == 8
    assert (revived.successful_uses, revived.failed_uses) == (2, 1)
    assert revived.observation_count == 5
    assert sender.language.next_invention_index == 1
    assert state.invention_count == 1


def test_cross_meaning_production_collision_is_retained_without_retry():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime(45)
    signal = derive_invention_signal(
        state,
        inventor_id=1,
        meaning=Meaning.FOOD,
        invention_index=0,
        maximum_signal_length=3,
    )
    sender.language.production[(Meaning.WOOD, signal)] = invented(
        Meaning.WOOD, signal, 0.70)

    outcome = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=state,
    )

    assert outcome.produced_signal == signal
    assert set(sender.language.production) == {
        (Meaning.FOOD, signal),
        (Meaning.WOOD, signal),
    }
    assert sender.language.next_invention_index == 1


def test_equal_comprehension_collision_uses_canonical_meaning_order():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime()
    signal = Signal((4, 4))
    sender.language.production[(Meaning.STONE, signal)] = invented(
        Meaning.STONE, signal, 0.50)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD, signal, 0.50)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD, signal, 0.50)

    outcome = communicate(
        sender,
        receiver,
        Meaning.STONE,
        context=CommunicationContext.FACTION_TRADE,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=state,
    )

    assert outcome.interpreted_meaning is Meaning.FOOD
    assert outcome.result is CommunicationResult.MISUNDERSTANDING


def test_equal_production_confidence_uses_canonical_signal_order():
    signals = (Signal((0, 7)), Signal((7, 0)))

    def produce(order):
        sender = person("Sender", 1)
        receiver = person("Receiver", 2)
        for signal in order:
            sender.language.production[(Meaning.FOOD, signal)] = invented(
                Meaning.FOOD, signal, 0.50)
            receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
                Meaning.FOOD, signal, 0.50)
        outcome = communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=1,
            active_ids=frozenset({1, 2}),
            config=ENABLED,
            runtime=runtime(),
        )
        return outcome.produced_signal

    assert produce(signals) == produce(reversed(signals)) == signals[0]


def test_synonym_weakening_changes_confidence_without_use_counters():
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    selected_signal = Signal((0, 1))
    competing_signal = Signal((1, 0))
    sender.language.production[(Meaning.FOOD, selected_signal)] = invented(
        Meaning.FOOD, selected_signal, 0.60, tick=1)
    sender.language.production[(Meaning.FOOD, competing_signal)] = invented(
        Meaning.FOOD, competing_signal, 0.50, tick=1)
    receiver.language.comprehension[(selected_signal, Meaning.FOOD)] = learned(
        Meaning.FOOD,
        selected_signal,
        0.60,
        observations=2,
        successful=1,
        tick=1,
    )

    communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=runtime(),
    )

    selected = sender.language.production[(Meaning.FOOD, selected_signal)]
    competitor = sender.language.production[(Meaning.FOOD, competing_signal)]
    assert (
        selected.confidence,
        selected.observation_count,
        selected.successful_uses,
        selected.failed_uses,
        selected.last_used_tick,
    ) == (0.70, 1, 1, 0, 2)
    assert (
        competitor.confidence,
        competitor.observation_count,
        competitor.successful_uses,
        competitor.failed_uses,
        competitor.last_used_tick,
    ) == (0.475, 0, 0, 0, 1)


def test_combined_retention_is_insertion_order_independent():
    config = LanguageEvolutionConfig(True, 4, 4, 0.20, 0.10, 5, True)
    entries = [
        ("production", Meaning.FOOD, Signal((0, 0)), 0.90),
        ("production", Meaning.FOOD, Signal((0, 1)), 0.80),
        ("production", Meaning.FOOD, Signal((0, 2)), 0.70),
        ("production", Meaning.WOOD, Signal((0, 3)), 0.60),
        ("comprehension", Meaning.FOOD, Signal((1, 0)), 0.95),
        ("comprehension", Meaning.WOOD, Signal((1, 0)), 0.85),
        ("comprehension", Meaning.ORE, Signal((1, 0)), 0.75),
    ]

    def retained(order):
        state = AgentLanguageState()
        for store, meaning, signal, confidence in order:
            association = (
                invented(meaning, signal, confidence)
                if store == "production"
                else learned(meaning, signal, confidence)
            )
            if store == "production":
                state.production[(meaning, signal)] = association
            else:
                state.comprehension[(signal, meaning)] = association
        result, lost = _retain_canonical(state, config=config)
        return result, lost

    forward, forward_lost = retained(entries)
    reverse, reverse_lost = retained(reversed(entries))

    assert forward.production == reverse.production
    assert forward.comprehension == reverse.comprehension
    assert forward_lost == reverse_lost == 3
    assert len(forward.production) + len(forward.comprehension) == 4
    assert sum(signal == Signal((1, 0)) for signal, _meaning in forward.comprehension) == 2


def test_communication_pruning_counts_each_removed_association_once():
    config = LanguageEvolutionConfig(True, 1, 3, 0.20, 0.10, 5, True)
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime()
    active = frozenset({1, 2})

    for tick in range(1, 5):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=active,
            config=config,
            runtime=state,
        )

    assert receiver.language.production == {}
    assert len(receiver.language.comprehension) == 1
    assert state.lost_association_count == 1


def test_failed_proposal_changes_no_state_or_rng(monkeypatch):
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = runtime()
    sender.inventory["food"] = 7
    sender.relationships[2] = object()
    before_sender = copy.deepcopy(sender.language)
    before_receiver = copy.deepcopy(receiver.language)
    before_runtime = copy.deepcopy(state)
    before_inventory = dict(sender.inventory)
    before_relationships = dict(sender.relationships)
    before_rng = random.getstate()

    def fail_retention(*args, **kwargs):
        raise LanguageInvariantError("injected_failure", "proposal failed")

    monkeypatch.setattr(language_module, "_retain_canonical", fail_retention)
    with pytest.raises(LanguageInvariantError, match="proposal failed"):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=1,
            active_ids=frozenset({1, 2}),
            config=ENABLED,
            runtime=state,
        )

    assert sender.language == before_sender
    assert receiver.language == before_receiver
    assert state == before_runtime
    assert sender.language.next_invention_index == 0
    assert sender.inventory == before_inventory
    assert sender.relationships == before_relationships
    assert random.getstate() == before_rng


def test_nonforgetting_no_death_fast_path_never_scans_population(monkeypatch):
    class PopulationIterationForbidden(list):
        def __iter__(self):
            raise AssertionError("non-forgetting maintenance scanned inhabitants")

    inhabitants = language_population(256)
    guarded_population = PopulationIterationForbidden(inhabitants)
    state = runtime()
    before_languages = copy.deepcopy(
        [inhabitant.language for inhabitant in inhabitants])
    before_runtime = copy.deepcopy(state)
    before_rng = random.getstate()

    def unexpected_validation(*args, **kwargs):
        raise AssertionError("non-forgetting maintenance validated language state")

    monkeypatch.setattr(
        language_module, "validate_agent_language_state", unexpected_validation)
    monkeypatch.setattr(
        language_module, "_language_state_identity", unexpected_validation)

    maintain_language_state(
        guarded_population,
        [],
        tick=1,
        config=ENABLED,
        runtime=state,
    )

    assert [inhabitant.language for inhabitant in inhabitants] == before_languages
    assert state == before_runtime
    assert all(
        inhabitant.language.next_invention_index == 0
        for inhabitant in inhabitants
    )
    assert random.getstate() == before_rng


def test_due_maintenance_visits_population_and_associations_linearly(monkeypatch):
    inhabitants = language_population(256)
    state = runtime()
    counts = instrument_maintenance(monkeypatch)

    maintain_language_state(
        inhabitants,
        [],
        tick=5,
        config=ENABLED,
        runtime=state,
    )

    assert counts == {
        "identity": len(inhabitants),
        "state_validation": 2 * len(inhabitants),
        "association_validation": 2 * len(inhabitants),
        "retention": len(inhabitants),
    }
    assert all(
        next(iter(inhabitant.language.production.values())).confidence == 0.55
        for inhabitant in inhabitants
    )
    assert state.last_forgetting_tick == 5


def test_death_cleanup_visits_each_active_and_dead_owner_linearly(monkeypatch):
    active = language_population(192)
    dead = language_population(64, first_id=len(active))
    for inhabitant in dead:
        inhabitant.language.next_invention_index = 3
    state = runtime()
    counts = instrument_maintenance(monkeypatch)

    maintain_language_state(
        active,
        dead,
        tick=1,
        config=ENABLED,
        runtime=state,
    )

    assert counts == {
        "identity": len(active) + len(dead),
        "state_validation": 2 * len(active) + len(dead),
        "association_validation": 2 * len(active) + len(dead),
        "retention": len(active),
    }
    assert all(len(inhabitant.language.production) == 1 for inhabitant in active)
    assert all(
        inhabitant.language == AgentLanguageState(next_invention_index=3)
        for inhabitant in dead
    )
    assert state.lost_association_count == len(dead)
    assert state.last_forgetting_tick is None


def test_maintenance_uses_exact_interval_and_stale_boundary():
    speaker = person("Speaker", 1)
    signal = Signal((2, 3))
    speaker.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal, 0.12, tick=0)
    state = runtime()

    maintain_language_state(
        [speaker], [], tick=4, config=ENABLED, runtime=state)
    assert speaker.language.production[(Meaning.FOOD, signal)].confidence == 0.12
    assert state.last_forgetting_tick is None

    maintain_language_state(
        [speaker], [], tick=5, config=ENABLED, runtime=state)
    assert speaker.language.production[(Meaning.FOOD, signal)].confidence == 0.07
    first_decay = speaker.language.production[(Meaning.FOOD, signal)]
    assert (
        first_decay.observation_count,
        first_decay.successful_uses,
        first_decay.failed_uses,
        first_decay.last_used_tick,
    ) == (0, 0, 0, 0)
    assert state.last_forgetting_tick == 5
    assert speaker.language.next_invention_index == 0

    maintain_language_state(
        [speaker], [], tick=10, config=ENABLED, runtime=state)
    assert speaker.language.production[(Meaning.FOOD, signal)].confidence == 0.02
    maintain_language_state(
        [speaker], [], tick=15, config=ENABLED, runtime=state)
    assert speaker.language.production == {}
    assert state.lost_association_count == 1

    with pytest.raises(LanguageInvariantError, match="already ran"):
        maintain_language_state(
            [speaker], [], tick=15, config=ENABLED, runtime=state)


def test_empty_interval_boundary_is_a_true_no_op():
    speaker = person("Speaker", 1)
    state = runtime()
    before_language = speaker.language
    before_runtime = copy.deepcopy(state)

    maintain_language_state(
        [speaker], [], tick=5, config=ENABLED, runtime=state)

    assert speaker.language is before_language
    assert state == before_runtime
    assert speaker.language.next_invention_index == 0


def test_disabled_runtime_is_pristine_and_processing_fails_closed():
    speaker = person("Speaker", 1)
    state = LanguageRuntimeState()
    assert language_runtime_is_pristine(state)

    with pytest.raises(LanguageInvariantError, match="disabled"):
        maintain_language_state(
            [speaker], [], tick=5, config=DISABLED, runtime=state)

    assert language_runtime_is_pristine(state)
    assert speaker.language == AgentLanguageState()


def test_repeated_partners_converge_while_disconnected_groups_remain_distinct():
    first_sender = person("A", 1)
    first_receiver = person("B", 2)
    second_sender = person("C", 3)
    second_receiver = person("D", 4)
    state = runtime(808)
    active = frozenset({1, 2, 3, 4})

    first_signal = None
    second_signal = None
    for tick in range(1, 7):
        first = communicate(
            first_sender,
            first_receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=active,
            config=ENABLED,
            runtime=state,
        )
        second = communicate(
            second_sender,
            second_receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=active,
            config=ENABLED,
            runtime=state,
        )
        first_signal = first.produced_signal
        second_signal = second.produced_signal

    assert first_signal is not None and second_signal is not None
    assert first_signal != second_signal
    assert (Meaning.FOOD, first_signal) in first_receiver.language.production
    assert (Meaning.FOOD, second_signal) in second_receiver.language.production

    first_group = lexical_convergence_snapshot(
        [first_sender, first_receiver, second_sender, second_receiver],
        config=ENABLED,
        inhabitant_ids=(1, 2),
    )
    second_group = lexical_convergence_snapshot(
        [first_sender, first_receiver, second_sender, second_receiver],
        config=ENABLED,
        inhabitant_ids=(3, 4),
    )
    assert first_group["meanings"][0]["dominant_signal"] == list(
        first_signal.phoneme_ids)
    assert second_group["meanings"][0]["dominant_signal"] == list(
        second_signal.phoneme_ids)
    assert first_group["meanings"][0]["pairwise_agreement"] == 1.0
    assert second_group["meanings"][0]["pairwise_agreement"] == 1.0


def test_language_source_contains_no_rng_hash_or_recursion_workaround():
    path = Path(language_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_calls = {"hash", "setrecursionlimit"}

    assert all(
        not isinstance(node, (ast.Import, ast.ImportFrom))
        or all(alias.name != "random" for alias in node.names)
        for node in ast.walk(tree)
    )
    identity_users = {
        function.name
        for function in ast.walk(tree)
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "id"
            for node in ast.walk(function)
        )
    }
    assert identity_users == {"_language_state_identity"}
    assert all(
        not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
        )
        for node in ast.walk(tree)
    )
    assert all(
        not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setrecursionlimit"
        )
        for node in ast.walk(tree)
    )


def test_canonical_snapshot_is_independent_of_population_and_mapping_order():
    first = person("First", 1)
    second = person("Second", 2)
    signals = (Signal((1, 2)), Signal((2, 1)))
    first.language.production[(Meaning.FOOD, signals[1])] = invented(
        Meaning.FOOD, signals[1], 0.6)
    first.language.production[(Meaning.FOOD, signals[0])] = invented(
        Meaning.FOOD, signals[0], 0.7)

    forward = canonical_language_snapshot([second, first], config=ENABLED)
    reordered = copy.deepcopy(first)
    reordered.language.production = dict(reversed(
        tuple(reordered.language.production.items())))
    reverse = canonical_language_snapshot([reordered, second], config=ENABLED)

    assert forward == reverse
