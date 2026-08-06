"""Learnable constituent order inferred from minimal pairs, never parsed."""

from __future__ import annotations

from dataclasses import asdict
import os
import random
import subprocess
import sys
import textwrap

import pytest

import run_experiments
from thalren_vale import economy, world
from thalren_vale.config import (
    GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION,
    GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    CompositionalProtolanguageConfig,
    GrammarEvolutionConfig,
    LanguageEvolutionConfig,
    SimulationConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    CommunicationContext,
    CompositeMeaning,
    CompositionalProtolanguageRuntimeState,
    ConstituentOrder,
    GrammarEvolutionRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Signal,
    apply_order_adoption,
    communicate,
    derive_initial_constituent_order,
    grammar_evolution_runtime_is_pristine,
    grammar_evolution_runtime_record,
    grammar_evolution_summary,
    infer_constituent_order,
    initialize_compositional_protolanguage_runtime,
    initialize_grammar_evolution_runtime,
    initialize_language_runtime,
    validate_grammar_evolution_config,
    validate_grammar_evolution_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.state import SimulationState


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 250, True)
COMPOSITIONAL = CompositionalProtolanguageConfig(True, 2, 1)
GRAMMAR = GrammarEvolutionConfig(True, 3)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def person(inhabitant_id: int) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.language = AgentLanguageState()
    return result


def runtimes(seed: int = 42):
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime, seed,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True)
    compositional_runtime = CompositionalProtolanguageRuntimeState()
    initialize_compositional_protolanguage_runtime(
        compositional_runtime, COMPOSITIONAL, seed)
    grammar_runtime = GrammarEvolutionRuntimeState()
    initialize_grammar_evolution_runtime(grammar_runtime, GRAMMAR)
    return language_runtime, compositional_runtime, grammar_runtime


def learn(state: AgentLanguageState, tokens, meaning) -> None:
    """Place one comprehension association without driving communication."""
    signal = Signal(tuple(tokens))
    state.comprehension[(signal, meaning)] = LexicalAssociation(
        signal=signal, meaning=meaning, confidence=0.9, last_used_tick=1)


# ── Closed order space ──────────────────────────────────────────────────────

def test_constituent_order_space_is_closed_and_exactly_two():
    assert len(ConstituentOrder) == 2
    assert {order.value for order in ConstituentOrder} == {
        "RESOURCE_FIRST", "MODALITY_FIRST"}


def test_agent_state_starts_without_an_order_or_evidence():
    state = AgentLanguageState()
    assert state.constituent_order is None
    assert state.opposing_order_evidence == 0


# ── Deterministic initial order ─────────────────────────────────────────────

def test_initial_order_is_derived_without_rng_and_is_stable():
    _language, compositional, _grammar = runtimes()
    first = [
        derive_initial_constituent_order(compositional, speaker_id=index)
        for index in range(16)
    ]
    random.seed(1234)
    [random.random() for _ in range(50)]
    second = [
        derive_initial_constituent_order(compositional, speaker_id=index)
        for index in range(16)
    ]
    assert first == second
    assert set(first) == set(ConstituentOrder), (
        "a usable derivation must produce both orders across speakers")


def test_initial_order_differs_across_seeds():
    _l1, first, _g1 = runtimes(seed=42)
    _l2, second, _g2 = runtimes(seed=99)
    left = [
        derive_initial_constituent_order(first, speaker_id=i).value
        for i in range(24)
    ]
    right = [
        derive_initial_constituent_order(second, speaker_id=i).value
        for i in range(24)
    ]
    assert left != right


def test_initial_order_rejects_invalid_speaker_identity():
    _language, compositional, _grammar = runtimes()
    for identity in (-1, True, 1.0, "3", None):
        with pytest.raises(LanguageInvariantError):
            derive_initial_constituent_order(
                compositional, speaker_id=identity)


def test_initial_order_requires_an_initialized_runtime():
    with pytest.raises(LanguageInvariantError):
        derive_initial_constituent_order(
            CompositionalProtolanguageRuntimeState(), speaker_id=0)


# ── Minimal-pair inference ──────────────────────────────────────────────────

def test_no_minimal_pair_yields_no_inference():
    state = AgentLanguageState()
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((1, 2, 5)), CompositeMeaning.FOOD_GIFT) is None


def test_shared_trailing_modality_morpheme_implies_resource_first():
    state = AgentLanguageState()
    # Same speaker, same modality, different resource: [res][res][mod].
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((3, 4, 5)), CompositeMeaning.ORE_GIFT
    ) is ConstituentOrder.RESOURCE_FIRST


def test_shared_leading_modality_morpheme_implies_modality_first():
    state = AgentLanguageState()
    learn(state, (5, 1, 2), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((5, 3, 4)), CompositeMeaning.ORE_GIFT
    ) is ConstituentOrder.MODALITY_FIRST


def test_shared_leading_resource_morpheme_implies_resource_first():
    state = AgentLanguageState()
    # Same resource, different modality: the shared run is the resource.
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((1, 2, 6)), CompositeMeaning.FOOD_EXCHANGE
    ) is ConstituentOrder.RESOURCE_FIRST


def test_shared_trailing_resource_morpheme_implies_modality_first():
    state = AgentLanguageState()
    learn(state, (5, 1, 2), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((6, 1, 2)), CompositeMeaning.FOOD_EXCHANGE
    ) is ConstituentOrder.MODALITY_FIRST


def test_pairs_differing_in_both_dimensions_prove_nothing():
    state = AgentLanguageState()
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((3, 4, 6)), CompositeMeaning.ORE_EXCHANGE) is None


def test_identical_meaning_synonyms_are_not_a_minimal_pair():
    state = AgentLanguageState()
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((7, 6, 4)), CompositeMeaning.FOOD_GIFT) is None


def test_overlap_on_both_ends_is_ambiguous_and_proves_nothing():
    state = AgentLanguageState()
    learn(state, (1, 2, 1), CompositeMeaning.FOOD_GIFT)
    # Shares a leading and a trailing token; position is undetermined.
    assert infer_constituent_order(
        state, Signal((1, 3, 1)), CompositeMeaning.ORE_GIFT) is None


def test_absent_overlap_proves_nothing():
    state = AgentLanguageState()
    learn(state, (1, 2, 3), CompositeMeaning.FOOD_GIFT)
    assert infer_constituent_order(
        state, Signal((4, 5, 6)), CompositeMeaning.ORE_GIFT) is None


def test_contradictory_evidence_yields_no_inference():
    state = AgentLanguageState()
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)      # -> RESOURCE
    learn(state, (3, 1, 2), CompositeMeaning.STONE_GIFT)     # -> MODALITY
    assert infer_constituent_order(
        state, Signal((3, 4, 5)), CompositeMeaning.ORE_GIFT) is None


def test_base_meanings_are_ignored_by_inference():
    state = AgentLanguageState()
    signal = Signal((1, 2, 5))
    state.comprehension[(signal, Meaning.FOOD)] = LexicalAssociation(
        signal=signal, meaning=Meaning.FOOD,
        confidence=0.9, last_used_tick=1)
    assert infer_constituent_order(
        state, Signal((3, 4, 5)), CompositeMeaning.ORE_GIFT) is None


def test_inference_rejects_non_composite_meanings():
    state = AgentLanguageState()
    with pytest.raises(LanguageInvariantError):
        infer_constituent_order(state, Signal((1,)), Meaning.FOOD)


def test_inference_rejects_a_non_signal():
    state = AgentLanguageState()
    with pytest.raises(LanguageInvariantError):
        infer_constituent_order(
            state, (1, 2, 3), CompositeMeaning.FOOD_GIFT)


def test_inference_never_mutates_agent_state():
    state = AgentLanguageState()
    learn(state, (1, 2, 5), CompositeMeaning.FOOD_GIFT)
    before = repr(state)
    infer_constituent_order(
        state, Signal((3, 4, 5)), CompositeMeaning.ORE_GIFT)
    assert repr(state) == before


# ── Consecutive-evidence adoption ───────────────────────────────────────────

def test_agreeing_evidence_resets_the_opposing_counter():
    state = AgentLanguageState()
    state.constituent_order = ConstituentOrder.RESOURCE_FIRST
    state.opposing_order_evidence = 2
    adopted = apply_order_adoption(
        state, ConstituentOrder.RESOURCE_FIRST, adoption_threshold=3)
    assert adopted is False
    assert state.opposing_order_evidence == 0
    assert state.constituent_order is ConstituentOrder.RESOURCE_FIRST


def test_adoption_requires_consecutive_opposing_evidence():
    state = AgentLanguageState()
    state.constituent_order = ConstituentOrder.RESOURCE_FIRST
    for _ in range(2):
        assert apply_order_adoption(
            state, ConstituentOrder.MODALITY_FIRST,
            adoption_threshold=3) is False
    # One agreeing observation must undo the accumulated pressure.
    apply_order_adoption(
        state, ConstituentOrder.RESOURCE_FIRST, adoption_threshold=3)
    for _ in range(2):
        assert apply_order_adoption(
            state, ConstituentOrder.MODALITY_FIRST,
            adoption_threshold=3) is False
    assert state.constituent_order is ConstituentOrder.RESOURCE_FIRST
    assert apply_order_adoption(
        state, ConstituentOrder.MODALITY_FIRST, adoption_threshold=3) is True
    assert state.constituent_order is ConstituentOrder.MODALITY_FIRST
    assert state.opposing_order_evidence == 0


def test_adoption_rejects_an_invalid_threshold():
    state = AgentLanguageState()
    state.constituent_order = ConstituentOrder.RESOURCE_FIRST
    for threshold in (0, -1, True, 1.0, None):
        with pytest.raises(LanguageInvariantError):
            apply_order_adoption(
                state, ConstituentOrder.MODALITY_FIRST,
                adoption_threshold=threshold)


# ── Runtime validation and partition invariants ─────────────────────────────

def test_fresh_runtime_is_pristine_and_initialization_freezes_controls():
    runtime = GrammarEvolutionRuntimeState()
    assert grammar_evolution_runtime_is_pristine(runtime)
    initialize_grammar_evolution_runtime(runtime, GRAMMAR)
    assert not grammar_evolution_runtime_is_pristine(runtime)
    assert runtime.order_adoption_threshold == GRAMMAR.order_adoption_threshold


def test_initialization_requires_an_enabled_config():
    runtime = GrammarEvolutionRuntimeState()
    with pytest.raises(LanguageInvariantError):
        initialize_grammar_evolution_runtime(
            runtime, GrammarEvolutionConfig(False, 3))


def test_runtime_rejects_a_control_mismatch():
    _language, _compositional, runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_runtime(
            runtime, config=GrammarEvolutionConfig(True, 9))


@pytest.mark.parametrize("mutation", [
    {"order_inference_attempt_count": 5},          # != inferred + not_inferred
    {"order_agreement_count": 5},                  # != inferred
    {"order_adoption_count": 5},                   # > conflicts
])
def test_runtime_counter_partitions_are_enforced(mutation):
    _language, _compositional, runtime = runtimes()
    for name, value in mutation.items():
        setattr(runtime, name, value)
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_runtime(runtime, config=GRAMMAR)


def test_runtime_rejects_a_foreign_type():
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_runtime(object(), config=GRAMMAR)


# ── Config validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("threshold", [0, -1, True, 1.0, None, "3"])
def test_config_rejects_invalid_thresholds(threshold):
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_config(
            GrammarEvolutionConfig(True, threshold))


def test_config_rejects_a_nonboolean_gate():
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_config(GrammarEvolutionConfig(1, 3))


def test_require_enabled_rejects_a_disabled_config():
    with pytest.raises(LanguageInvariantError):
        validate_grammar_evolution_config(
            GrammarEvolutionConfig(False, 3), require_enabled=True)


# ── Dependency cascade ──────────────────────────────────────────────────────

def test_grammar_without_language_normalizes_with_both_notices():
    config = SimulationConfig(grammar_evolution_enabled=True)
    config.validate()
    assert config.grammar_evolution_enabled is False
    notices = config.grammar_evolution_control_notices
    assert GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE in notices
    assert GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION in notices
    assert list(notices) == sorted(notices)


def test_grammar_without_composition_normalizes_with_one_notice():
    config = SimulationConfig(
        language_evolution_enabled=True, grammar_evolution_enabled=True)
    config.validate()
    assert config.grammar_evolution_enabled is False
    notices = config.grammar_evolution_control_notices
    assert GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION in notices
    assert GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE not in notices


def test_fully_satisfied_dependencies_keep_grammar_enabled():
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True)
    config.validate()
    assert config.grammar_evolution_enabled is True
    assert config.grammar_evolution_control_notices == ()


def test_runtime_gate_requires_composition():
    runtime = LanguageRuntimeState()
    with pytest.raises(LanguageInvariantError):
        initialize_language_runtime(
            runtime, 42, grammar_evolution_enabled=True)


# ── Communication integration ───────────────────────────────────────────────

def speak(sender, receiver, meaning, context, tick, language_runtime,
          compositional_runtime, grammar_runtime,
          active_ids=frozenset({7, 9})):
    return communicate(
        sender, receiver, meaning, context=context, tick=tick,
        active_ids=active_ids,
        config=LANGUAGE, runtime=language_runtime,
        compositional_config=COMPOSITIONAL,
        compositional_runtime=compositional_runtime,
        grammar_config=GRAMMAR, grammar_runtime=grammar_runtime,
    )


def test_enabled_grammar_requires_both_owners():
    language_runtime, compositional_runtime, _grammar = runtimes()
    sender, receiver = person(7), person(9)
    with pytest.raises(LanguageInvariantError):
        communicate(
            sender, receiver, Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER, tick=1,
            active_ids=frozenset({7, 9}),
            config=LANGUAGE, runtime=language_runtime,
            compositional_config=COMPOSITIONAL,
            compositional_runtime=compositional_runtime,
            grammar_config=GRAMMAR, grammar_runtime=None,
        )


def test_speakers_receive_an_order_lazily_on_first_use():
    language_runtime, compositional_runtime, grammar_runtime = runtimes()
    sender, receiver = person(7), person(9)
    assert sender.language.constituent_order is None
    speak(sender, receiver, Meaning.FOOD,
          CommunicationContext.AID_TRANSFER, 1,
          language_runtime, compositional_runtime, grammar_runtime)
    assert sender.language.constituent_order is not None
    assert sender.language.constituent_order is (
        derive_initial_constituent_order(compositional_runtime, speaker_id=7))


def test_inference_runs_only_on_successful_comprehension():
    language_runtime, compositional_runtime, grammar_runtime = runtimes()
    sender, receiver = person(7), person(9)
    # First contact cannot be understood, so nothing may be inferred.
    speak(sender, receiver, Meaning.FOOD,
          CommunicationContext.AID_TRANSFER, 1,
          language_runtime, compositional_runtime, grammar_runtime)
    assert grammar_runtime.order_inference_attempt_count == 0


def test_agent_order_survives_repeated_communication():
    """Every AgentLanguageState rebuild must carry the order forward."""
    language_runtime, compositional_runtime, grammar_runtime = runtimes()
    sender, receiver = person(7), person(9)
    speak(sender, receiver, Meaning.FOOD,
          CommunicationContext.AID_TRANSFER, 1,
          language_runtime, compositional_runtime, grammar_runtime)
    expected = sender.language.constituent_order
    assert expected is not None
    for tick in range(2, 12):
        speak(sender, receiver, Meaning.FOOD,
              CommunicationContext.AID_TRANSFER, tick,
              language_runtime, compositional_runtime, grammar_runtime)
        assert sender.language.constituent_order is expected


def test_disabled_grammar_leaves_agent_order_untouched():
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime, 42, compositional_protolanguage_enabled=True)
    compositional_runtime = CompositionalProtolanguageRuntimeState()
    initialize_compositional_protolanguage_runtime(
        compositional_runtime, COMPOSITIONAL, 42)
    sender, receiver = person(7), person(9)
    for tick in range(1, 6):
        communicate(
            sender, receiver, Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER, tick=tick,
            active_ids=frozenset({7, 9}),
            config=LANGUAGE, runtime=language_runtime,
            compositional_config=COMPOSITIONAL,
            compositional_runtime=compositional_runtime,
        )
    assert sender.language.constituent_order is None
    assert receiver.language.constituent_order is None


# ── Economy reachability ────────────────────────────────────────────────────

def _grammar_economy_pass(ticks: int = 400):
    """Drive a bounded economy pass that produces a real minimal pair.

    One giver alternates two resources to one hearer, so the hearer learns
    two composite meanings from the same speaker differing in exactly one
    dimension. Without that structure no minimal pair exists and inference
    correctly reports nothing.
    """
    random.seed(42)
    world.reseed_world()
    state = SimulationState()
    social = SocialMemoryConfig(True, True, 8, 25)
    initialize_language_runtime(
        state.language, 42,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True)
    initialize_compositional_protolanguage_runtime(
        state.compositional_protolanguage, COMPOSITIONAL, 42)
    initialize_grammar_evolution_runtime(state.grammar_evolution, GRAMMAR)

    people = [person(0), person(1)]
    for inhabitant in people:
        inhabitant.inventory = {
            'food': 0, 'wood': 0, 'ore': 0, 'stone': 0, 'water': 0}
    state.next_inhabitant_id = len(people)
    state.people.extend(people)
    giver, hearer = people

    event_log: list = []
    for tick in range(1, ticks):
        giver.inventory.update({'food': 4, 'ore': 4})
        hearer.inventory['ore' if tick % 2 == 0 else 'food'] = 0
        economy.economy_tick(
            people, [], tick, event_log,
            social_config=social,
            language_config=LANGUAGE,
            language_runtime=state.language,
            compositional_config=COMPOSITIONAL,
            compositional_runtime=state.compositional_protolanguage,
            grammar_config=GRAMMAR,
            grammar_runtime=state.grammar_evolution,
            raids_enabled=False,
        )
    return state, people


def test_grammar_engages_through_the_economy_layer():
    state, _people = _grammar_economy_pass()
    runtime = state.grammar_evolution
    assert runtime.order_inference_attempt_count > 0
    assert runtime.order_inferred_count > 0


def test_economy_pass_preserves_every_counter_partition():
    state, _people = _grammar_economy_pass()
    runtime = state.grammar_evolution
    assert runtime.order_inference_attempt_count == (
        runtime.order_inferred_count + runtime.order_not_inferred_count)
    assert runtime.order_agreement_count + runtime.order_conflict_count == (
        runtime.order_inferred_count)
    assert runtime.order_adoption_count <= runtime.order_conflict_count


def test_adoption_records_the_tick_it_happened():
    state, _people = _grammar_economy_pass()
    runtime = state.grammar_evolution
    if runtime.order_adoption_count:
        assert type(runtime.last_adoption_tick) is int
        assert runtime.last_adoption_tick > 0
    else:
        assert runtime.last_adoption_tick is None


# ── Runtime record and summary ──────────────────────────────────────────────

def test_runtime_record_exposes_controls_and_counters():
    language_runtime, _compositional, grammar_runtime = runtimes()
    record = grammar_evolution_runtime_record(
        grammar_runtime, config=GRAMMAR, language_runtime=language_runtime)
    assert record["order_adoption_threshold"] == 3
    assert record["last_adoption_tick"] is None
    assert set(record) == {
        "order_adoption_threshold",
        "order_inference_attempt_count",
        "order_inferred_count",
        "order_not_inferred_count",
        "order_agreement_count",
        "order_conflict_count",
        "order_adoption_count",
        "last_adoption_tick",
    }


def test_summary_counts_carriers_by_order_without_mutating():
    language_runtime, _compositional, grammar_runtime = runtimes()
    people = [person(index) for index in range(4)]
    people[0].language.constituent_order = ConstituentOrder.RESOURCE_FIRST
    people[1].language.constituent_order = ConstituentOrder.RESOURCE_FIRST
    people[2].language.constituent_order = ConstituentOrder.MODALITY_FIRST
    people[2].language.opposing_order_evidence = 2
    before = [asdict(p.language) for p in people]
    summary = grammar_evolution_summary(
        people, runtime=grammar_runtime, config=GRAMMAR,
        language_runtime=language_runtime)
    assert summary["population"] == 4
    assert summary["ordered_carriers"] == 3
    assert summary["pending_evidence_carriers"] == 1
    assert summary["carriers_by_constituent_order"] == {
        "RESOURCE_FIRST": 2, "MODALITY_FIRST": 1}
    assert [asdict(p.language) for p in people] == before


def test_summary_consumes_a_one_shot_iterable_exactly_once():
    language_runtime, _compositional, grammar_runtime = runtimes()
    people = [person(index) for index in range(3)]
    summary = grammar_evolution_summary(
        iter(people), runtime=grammar_runtime, config=GRAMMAR,
        language_runtime=language_runtime)
    assert summary["population"] == 3


def test_summary_requires_explicit_agent_language_state():
    language_runtime, _compositional, grammar_runtime = runtimes()
    stranger = Inhabitant("X", 0, 0)
    stranger.inhabitant_id = 0
    stranger.language = None
    with pytest.raises(LanguageInvariantError):
        grammar_evolution_summary(
            [stranger], runtime=grammar_runtime, config=GRAMMAR,
            language_runtime=language_runtime)


# ── Canonical hashing ───────────────────────────────────────────────────────

def _hash_state(order, evidence=0, attempts=0):
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True)
    initialize_compositional_protolanguage_runtime(
        state.compositional_protolanguage,
        config.compositional_protolanguage_config, 42)
    initialize_grammar_evolution_runtime(
        state.grammar_evolution, config.grammar_evolution_config)
    inhabitant = person(0)
    inhabitant.language.constituent_order = order
    inhabitant.language.opposing_order_evidence = evidence
    state.people.append(inhabitant)
    state.grammar_evolution.order_inference_attempt_count = attempts
    state.grammar_evolution.order_not_inferred_count = attempts
    return canonical_state_hash(state, world.world, config.manifest_dict())


def test_agent_order_changes_the_canonical_hash():
    assert _hash_state(ConstituentOrder.RESOURCE_FIRST) != _hash_state(
        ConstituentOrder.MODALITY_FIRST)


def test_pending_evidence_changes_the_canonical_hash():
    base = _hash_state(ConstituentOrder.RESOURCE_FIRST)
    assert base != _hash_state(ConstituentOrder.RESOURCE_FIRST, evidence=2)


def test_runtime_counters_change_the_canonical_hash():
    base = _hash_state(ConstituentOrder.RESOURCE_FIRST)
    assert base != _hash_state(ConstituentOrder.RESOURCE_FIRST, attempts=5)


def test_disabled_grammar_cannot_conceal_agent_order():
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, compositional_protolanguage_enabled=True)
    initialize_compositional_protolanguage_runtime(
        state.compositional_protolanguage,
        config.compositional_protolanguage_config, 42)
    inhabitant = person(0)
    inhabitant.language.constituent_order = ConstituentOrder.RESOURCE_FIRST
    state.people.append(inhabitant)
    with pytest.raises(LanguageInvariantError):
        canonical_state_hash(state, world.world, config.manifest_dict())


def test_disabled_grammar_cannot_retain_runtime_state():
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, compositional_protolanguage_enabled=True)
    initialize_compositional_protolanguage_runtime(
        state.compositional_protolanguage,
        config.compositional_protolanguage_config, 42)
    state.grammar_evolution.order_adoption_count = 1
    with pytest.raises((LanguageInvariantError, ValueError)):
        canonical_state_hash(state, world.world, config.manifest_dict())


def test_canonical_hash_is_independent_of_python_hash_seed():
    script = textwrap.dedent(
        """
        import random
        from thalren_vale import world
        from thalren_vale.config import SimulationConfig
        from thalren_vale.language import (
            AgentLanguageState, ConstituentOrder,
            initialize_compositional_protolanguage_runtime,
            initialize_grammar_evolution_runtime,
            initialize_language_runtime,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        random.seed(42)
        world.reseed_world()
        config = SimulationConfig(
            language_evolution_enabled=True,
            compositional_protolanguage_enabled=True,
            grammar_evolution_enabled=True,
        )
        config.validate()
        state = SimulationState()
        initialize_language_runtime(
            state.language, 42,
            compositional_protolanguage_enabled=True,
            grammar_evolution_enabled=True)
        initialize_compositional_protolanguage_runtime(
            state.compositional_protolanguage,
            config.compositional_protolanguage_config, 42)
        initialize_grammar_evolution_runtime(
            state.grammar_evolution, config.grammar_evolution_config)
        for identifier, order in (
            (7, ConstituentOrder.RESOURCE_FIRST),
            (9, ConstituentOrder.MODALITY_FIRST),
        ):
            person = Inhabitant("P" + str(identifier), 0, 0)
            person.inhabitant_id = identifier
            person.faction = None
            person.language = AgentLanguageState()
            person.language.constituent_order = order
            person.language.opposing_order_evidence = 1
            state.people.append(person)
        print(canonical_state_hash(
            state, world.world, config.manifest_dict()))
        """
    )

    def run(hash_seed: str) -> str:
        environment = dict(
            os.environ,
            PYTHONHASHSEED=hash_seed,
            PYTHONPATH=os.path.join(PROJECT_ROOT, "src"),
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120, env=environment,
            cwd=PROJECT_ROOT,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    first = run("0")
    assert first
    assert first == run("7") == run("12345")


# ── Runner containment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argument", [
    "--enable-grammar-evolution",
    "--disable-grammar-evolution",
    "--order-adoption-threshold",
    "--order-adoption-threshold=3",
    "--enable-grammar-evolution=true",
    "--enable-grammar",
    "--order-adoption",
    "--enable-gram",
    "--o",
])
def test_runner_rejects_the_complete_grammar_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_grammar_evolution_args(
            (argument,))


@pytest.mark.parametrize("argument", [
    "--ticks=10", "--seed=1", "--log-mode", "--enable-social-memory",
])
def test_runner_still_accepts_unrelated_options(argument):
    run_experiments._reject_uncontracted_grammar_evolution_args((argument,))


def test_runner_rejects_a_plan_before_creating_any_output_root(tmp_path):
    import json

    plan_path = tmp_path / "plan.json"
    root = tmp_path / "never-created-root"
    plan_path.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "containment",
        "default_ticks": 2,
        "conditions": [{
            "name": "a",
            "seeds": "1",
            "extra_args": [
                "--log-mode", "metrics_only",
                "--enable-grammar-evolution",
            ],
        }],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        run_experiments.load_plan(plan_path)
    assert not root.exists()


# ── Artifact validation ─────────────────────────────────────────────────────

def collect(config: dict):
    from thalren_vale.artifact_validation import (
        _IssueCollector,
        _validate_grammar_evolution_configuration,
    )

    issues = _IssueCollector()
    _validate_grammar_evolution_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
        grammar_evolution_enabled=True,
    )
    enabled.validate()
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"grammar_evolution_enabled": True, "language_evolution_enabled": False,
     "compositional_protolanguage_enabled": True},
    {"grammar_evolution_enabled": True, "language_evolution_enabled": True,
     "compositional_protolanguage_enabled": False},
    {"order_adoption_threshold": 0},
    {"order_adoption_threshold": 999},
    {"order_adoption_threshold": True},
    {"grammar_evolution_controls_status": "bogus"},
    {"order_adoption_threshold": 7,
     "grammar_evolution_controls_status": "disabled"},
    {"grammar_evolution_enabled": True,
     "grammar_evolution_control_notices": [
         GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE]},
    {"grammar_evolution_controls_status": "normalized_uncontracted",
     "grammar_evolution_control_notices": []},
    {"grammar_evolution_control_notices": [
        GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
        GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE]},
    {"grammar_evolution_control_notices": sorted([
        GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
        GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION])[::-1]},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)
