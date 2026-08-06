"""Deterministic lexical substitution, direct-edge provenance, and bounds."""

from __future__ import annotations

import copy
from dataclasses import replace
import inspect
import json
import os
import random
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

import run_experiments
from thalren_vale import economy, language as language_module, sim
from thalren_vale.coalitions import (
    CoalitionRuntimeState,
    InformalCoalition,
    build_coalition_membership_snapshot,
)
from thalren_vale.config import (
    CoalitionConfig,
    CoalitionDialectConfig,
    IntergenerationalLanguageConfig,
    LanguageContactConfig,
    LanguageEvolutionConfig,
    LexicalEvolutionConfig,
    SimulationConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AssociationOrigin,
    BorrowingProvenance,
    CoalitionDialectRuntimeState,
    CommunicationContext,
    CommunicationResult,
    IntergenerationalLanguageRuntimeState,
    LanguageContactRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    LexicalEvolutionProvenance,
    LexicalEvolutionRuntimeState,
    LexicalMutationOperation,
    MAX_LEXICAL_OBSERVATION_OPPORTUNITIES,
    Meaning,
    Signal,
    communicate,
    derive_lexical_mutation_trigger,
    derive_lexical_substitution,
    initialize_intergenerational_language_runtime,
    initialize_language_contact_runtime,
    initialize_language_runtime,
    initialize_lexical_evolution_runtime,
    intergenerational_language_summary,
    lexical_evolution_runtime_record,
    lexical_evolution_runtime_is_pristine,
    lexical_evolution_summary,
    transmit_intergenerational_language,
    validate_agent_language_state,
    validate_lexical_evolution_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.state import SimulationState


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)
CONTACT = LanguageContactConfig(True, 1.50, 3, 0.50)
DIALECT = CoalitionDialectConfig(True, 1.50, 1.25)
COALITIONS = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)
INTERGENERATIONAL = IntergenerationalLanguageConfig(True, 2, 0.20)
SOCIAL_DISABLED = SocialMemoryConfig(False, False, 32, 25)


def person(inhabitant_id: int, *, generation: int = 0) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.generation = generation
    return result


def invented(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.60,
    *,
    tick: int = 0,
    lexical: LexicalEvolutionProvenance | None = None,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        last_used_tick=tick,
        origin=AssociationOrigin.INVENTED,
        lexical_evolution_provenance=lexical,
    )


def runtimes(
    *,
    rate: float = 1.0,
    depth: int = 8,
    seed: int = 123,
    dialect: bool = False,
    contact: bool = False,
    intergenerational: bool = False,
) -> tuple[
    LanguageRuntimeState,
    LexicalEvolutionRuntimeState,
    LexicalEvolutionConfig,
]:
    lexical_config = LexicalEvolutionConfig(True, rate, depth)
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime,
        seed,
        coalition_dialect_influence_enabled=dialect,
        language_contact_enabled=contact,
        intergenerational_language_enabled=intergenerational,
        lexical_evolution_enabled=True,
    )
    lexical_runtime = LexicalEvolutionRuntimeState()
    initialize_lexical_evolution_runtime(
        lexical_runtime, lexical_config, seed)
    return language_runtime, lexical_runtime, lexical_config


def communicate_lexically(
    sender: Inhabitant,
    receiver: Inhabitant,
    language_runtime: LanguageRuntimeState,
    lexical_runtime: LexicalEvolutionRuntimeState,
    lexical_config: LexicalEvolutionConfig,
    *,
    tick: int = 1,
    language_config: LanguageEvolutionConfig = LANGUAGE,
    **kwargs,
):
    return communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=tick,
        active_ids=frozenset(kwargs.pop("active_ids", {1, 2})),
        config=language_config,
        runtime=language_runtime,
        lexical_config=lexical_config,
        lexical_runtime=lexical_runtime,
        **kwargs,
    )


def coalition_snapshot(tick: int):
    runtime = CoalitionRuntimeState(
        active_coalitions={
            0: InformalCoalition(0, 0, (1, 2, 3)),
        },
        member_to_coalition={1: 0, 2: 0, 3: 0},
        next_coalition_id=1,
        candidate_formation_count=1,
        last_observation_tick=tick - 1,
        last_active_inhabitant_ids=(1, 2, 3),
    )
    return build_coalition_membership_snapshot(
        runtime,
        snapshot_tick=tick,
        active_inhabitant_ids=(1, 2, 3),
        config=COALITIONS,
    )


def one_cell_world() -> list:
    return [[{
        "biome": "plains",
        "habitable": True,
        "resources": {
            "food": 1,
            "wood": 0,
            "ore": 0,
            "stone": 0,
            "water": 0,
        },
    }]]


def committed_prior_mutation_runtime(
    *,
    rate: float = 1.0,
    depth: int = 8,
) -> tuple[
    LanguageRuntimeState,
    LexicalEvolutionRuntimeState,
    LexicalEvolutionConfig,
]:
    language_runtime, lexical_runtime, lexical_config = runtimes(
        rate=rate, depth=depth)
    language_runtime.communication_attempt_count = 1
    language_runtime.unknown_signal_count = 1
    language_runtime.last_communication_tick = 0
    lexical_runtime.mutation_derivation_index = 1
    lexical_runtime.eligible_mutation_opportunity_count = 1
    lexical_runtime.mutation_trigger_count = 1
    lexical_runtime.successful_mutation_count = 1
    lexical_runtime.substitution_count = 1
    lexical_runtime.descendant_production_creation_count = 1
    lexical_runtime.maximum_observed_lineage_depth = 1
    lexical_runtime.last_mutation_tick = 0
    validate_lexical_evolution_runtime(
        lexical_runtime,
        config=lexical_config,
        language_runtime=language_runtime,
    )
    return language_runtime, lexical_runtime, lexical_config


def test_configuration_defaults_validation_and_language_only_normalization():
    defaults = SimulationConfig()
    assert defaults.lexical_evolution_enabled is False
    assert defaults.lexical_mutation_rate == 0.05
    assert defaults.maximum_lexical_lineage_depth == 8
    assert defaults.lexical_evolution_controls_status == "disabled"
    assert defaults.lexical_evolution_control_notices == ()

    normalized = SimulationConfig(
        language_evolution_enabled=False,
        lexical_evolution_enabled=True,
        lexical_mutation_rate=0.25,
        maximum_lexical_lineage_depth=9,
    )
    assert normalized.lexical_evolution_enabled is False
    assert normalized.lexical_mutation_rate == 0.25
    assert normalized.maximum_lexical_lineage_depth == 9
    assert normalized.lexical_evolution_control_notices == (
        "lexical_evolution_requested_without_language",
    )
    assert (
        normalized.lexical_evolution_controls_status
        == "normalized_uncontracted"
    )
    independent = SimulationConfig(
        language_evolution_enabled=True,
        lexical_evolution_enabled=True,
        coalition_emergence_enabled=False,
        coalition_dialect_influence_enabled=False,
        language_contact_enabled=False,
        intergenerational_language_enabled=False,
    )
    assert independent.lexical_evolution_enabled is True
    assert (
        independent.lexical_evolution_controls_status
        == "engineering_only_uncontracted"
    )

    for bad_rate in (True, 1, float("nan"), -0.01, 1.01):
        with pytest.raises(ValueError, match="lexical mutation rate"):
            SimulationConfig(lexical_mutation_rate=bad_rate).validate()
    for bad_depth in (True, 1.0, 0, 33):
        with pytest.raises(ValueError, match="maximum lexical lineage depth"):
            SimulationConfig(
                maximum_lexical_lineage_depth=bad_depth).validate()


def test_pinned_trigger_and_substitution_vectors_and_exact_rate_boundaries():
    source = Signal((1, 2, 3))
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    del language_runtime
    assert lexical_runtime.seed_domain_fingerprint == (
        "28351cee8792111ac7d6d52eb241669e64cb1b60bb22a3cd17e59f44ea47ea13"
    )
    assert derive_lexical_mutation_trigger(
        lexical_runtime,
        lexical_config,
        opportunity_index=1,
        tick=7,
        sender_id=11,
        receiver_id=12,
        meaning=Meaning.FOOD,
        source_signal=source,
    ) is True
    descendant, position = derive_lexical_substitution(
        lexical_runtime,
        opportunity_index=1,
        tick=7,
        sender_id=11,
        receiver_id=12,
        meaning=Meaning.FOOD,
        source_signal=source,
    )
    assert descendant == Signal((3, 2, 3))
    assert position == 0
    assert len(descendant.phoneme_ids) == len(source.phoneme_ids)
    assert sum(
        left != right
        for left, right in zip(
            source.phoneme_ids, descendant.phoneme_ids)
    ) == 1

    for rate, expected in ((0.0, False), (1.0, True)):
        _base, runtime, config = runtimes(rate=rate)
        assert derive_lexical_mutation_trigger(
            runtime,
            config,
            opportunity_index=1,
            tick=7,
            sender_id=11,
            receiver_id=12,
            meaning=Meaning.FOOD,
            source_signal=source,
        ) is expected


def test_ordinary_invention_and_unusable_source_create_no_opportunity():
    for source in (None, invented(Meaning.FOOD, Signal((1, 2)), 0.09)):
        sender = person(1)
        receiver = person(2)
        if source is not None:
            sender.language.production[
                (source.meaning, source.signal)] = source
        language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
        outcome = communicate_lexically(
            sender,
            receiver,
            language_runtime,
            lexical_runtime,
            lexical_config,
        )
        assert outcome.produced_signal is not None
        assert language_runtime.invention_count == 1
        assert lexical_runtime.mutation_derivation_index == 0
        assert lexical_runtime.eligible_mutation_opportunity_count == 0
        assert lexical_runtime.successful_mutation_count == 0


def test_descendant_is_actual_emitted_signal_and_receiver_learns_only_it():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    sender.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source)
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    random_state = random.getstate()

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
    )

    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert outcome.produced_signal is not None
    assert outcome.produced_signal != source
    descendant = outcome.produced_signal
    assert (descendant, Meaning.FOOD) in receiver.language.comprehension
    assert (source, Meaning.FOOD) not in receiver.language.comprehension
    assert (Meaning.FOOD, descendant) in sender.language.production
    created = sender.language.production[(Meaning.FOOD, descendant)]
    assert created.origin is AssociationOrigin.INVENTED
    assert created.learned_from_id is None
    assert created.lexical_evolution_provenance is not None
    assert receiver.language.production == {}
    assert language_runtime.invention_count == 0
    assert lexical_runtime.mutation_derivation_index == 1
    assert lexical_runtime.eligible_mutation_opportunity_count == 1
    assert lexical_runtime.mutation_trigger_count == 1
    assert lexical_runtime.successful_mutation_count == 1
    assert lexical_runtime.substitution_count == 1
    assert lexical_runtime.descendant_production_creation_count == 1
    assert lexical_runtime.last_mutation_tick == 1
    assert random.getstate() == random_state


def test_not_triggered_opportunity_emits_exact_source_and_advances_index():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2))
    sender.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source)
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=0.0)

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
    )

    assert outcome.produced_signal == source
    assert lexical_runtime.mutation_derivation_index == 1
    assert lexical_runtime.eligible_mutation_opportunity_count == 1
    assert lexical_runtime.mutation_not_triggered_count == 1
    assert lexical_runtime.successful_mutation_count == 0
    assert lexical_runtime.last_mutation_tick is None
    assert lexical_runtime.maximum_observed_lineage_depth == 0


def test_derivation_is_independent_of_dialect_and_contact_feature_gates():
    def run(*, social_language: bool):
        sender = person(1)
        receiver = person(2)
        source = Signal((1, 2, 3))
        sender.language.production[(Meaning.FOOD, source)] = invented(
            Meaning.FOOD, source)
        language_runtime, lexical_runtime, lexical_config = runtimes(
            rate=1.0,
            dialect=social_language,
            contact=social_language,
        )
        kwargs = {}
        if social_language:
            contact_runtime = LanguageContactRuntimeState()
            initialize_language_contact_runtime(contact_runtime, CONTACT)
            kwargs = {
                "dialect_config": DIALECT,
                "dialect_runtime": CoalitionDialectRuntimeState(),
                "contact_config": CONTACT,
                "contact_runtime": contact_runtime,
                "coalition_membership_snapshot": coalition_snapshot(2),
                "active_ids": {1, 2, 3},
            }
        outcome = communicate_lexically(
            sender,
            receiver,
            language_runtime,
            lexical_runtime,
            lexical_config,
            tick=2,
            **kwargs,
        )
        provenance = sender.language.production[
            (Meaning.FOOD, outcome.produced_signal)
        ].lexical_evolution_provenance
        return outcome.produced_signal, provenance, lexical_runtime

    disabled = run(social_language=False)
    enabled = run(social_language=True)
    assert disabled[0] == enabled[0]
    assert disabled[1] == enabled[1]
    assert disabled[2] == enabled[2]
    digest_source = inspect.getsource(language_module._lexical_derivation_digest)
    assert "coalition" not in digest_source
    assert "dialect" not in digest_source
    assert "contact" not in digest_source


def test_existing_descendant_collision_reinforces_and_attaches_one_edge():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    descendant, _position = derive_lexical_substitution(
        lexical_runtime,
        opportunity_index=1,
        tick=1,
        sender_id=1,
        receiver_id=2,
        meaning=Meaning.FOOD,
        source_signal=source,
    )
    sender.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source, 0.90)
    sender.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, 0.20)

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
    )

    assert outcome.produced_signal == descendant
    assert len(sender.language.production) == 2
    collision = sender.language.production[(Meaning.FOOD, descendant)]
    assert collision.lexical_evolution_provenance is not None
    assert collision.lexical_evolution_provenance.mutation_index == 1
    assert lexical_runtime.descendant_production_creation_count == 0
    assert lexical_runtime.descendant_production_reinforcement_count == 1


def test_borrowed_source_mutates_without_copying_borrowing_provenance():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    borrowing = BorrowingProvenance(
        first_contact_tick=0,
        first_source_speaker_id=2,
        first_source_coalition_id=0,
        adoption_tick=0,
        adoption_source_speaker_id=2,
        adoption_source_coalition_id=0,
        exposure_count_at_adoption=3,
        successful_comprehension_count_at_adoption=2,
    )
    sender.language.production[(Meaning.FOOD, source)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=source,
        confidence=0.80,
        last_used_tick=0,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=2,
        borrowing_provenance=borrowing,
    )
    language_runtime, lexical_runtime, lexical_config = runtimes(
        rate=1.0, contact=True)
    contact_runtime = LanguageContactRuntimeState()
    initialize_language_contact_runtime(contact_runtime, CONTACT)

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
        contact_config=CONTACT,
        contact_runtime=contact_runtime,
        coalition_membership_snapshot=coalition_snapshot(2),
        active_ids={1, 2, 3},
        tick=2,
    )

    descendant = sender.language.production[
        (Meaning.FOOD, outcome.produced_signal)]
    assert descendant.borrowing_provenance is None
    assert descendant.origin is AssociationOrigin.INVENTED
    assert descendant.lexical_evolution_provenance is not None
    assert descendant.lexical_evolution_provenance.source_form_was_borrowed
    assert descendant.lexical_evolution_provenance.direct_source_origin is (
        AssociationOrigin.LEARNED)
    assert lexical_runtime.borrowed_source_mutation_count == 1
    assert contact_runtime.borrowed_production_use_count == 0


def test_depth_cap_emits_source_and_records_depth_limit_without_last_tick():
    sender = person(1)
    receiver = person(2)
    source_signal = Signal((3, 2, 3))
    direct_source = Signal((1, 2, 3))
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=direct_source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    sender.language.production[(Meaning.FOOD, source_signal)] = invented(
        Meaning.FOOD, source_signal, 0.80, lexical=provenance)
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime(depth=1))

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
        tick=1,
    )

    assert outcome.produced_signal == source_signal
    assert lexical_runtime.mutation_derivation_index == 2
    assert lexical_runtime.eligible_mutation_opportunity_count == 2
    assert lexical_runtime.mutation_trigger_count == 2
    assert lexical_runtime.lineage_depth_limit_count == 1
    assert lexical_runtime.successful_mutation_count == 1
    assert lexical_runtime.last_mutation_tick == 0
    assert lexical_runtime.maximum_observed_lineage_depth == 1


def test_receiver_and_parental_exact_copy_preserve_separate_provenance():
    parent = person(1)
    second_parent = person(2)
    child = person(3, generation=1)
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    lexical = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    parent.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, 0.80, lexical=lexical)
    second_parent.language.production[
        (Meaning.WOOD, Signal((4, 4)))
    ] = invented(Meaning.WOOD, Signal((4, 4)), 0.80)
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime())
    language_runtime.intergenerational_language_enabled = True
    intergenerational_runtime = IntergenerationalLanguageRuntimeState()
    initialize_intergenerational_language_runtime(
        intergenerational_runtime, INTERGENERATIONAL)
    lexical_before = copy.deepcopy(lexical_runtime)

    transmit_intergenerational_language(
        child,
        (second_parent, parent),
        tick=1,
        language_config=LANGUAGE,
        intergenerational_config=INTERGENERATIONAL,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        lexical_config=lexical_config,
        lexical_runtime=lexical_runtime,
    )

    association = child.language.comprehension[(descendant, Meaning.FOOD)]
    assert association.lexical_evolution_provenance == lexical
    assert association.intergenerational_provenance is not None
    assert association.intergenerational_provenance.first_parent_id == 1
    assert association.learned_from_id == 1
    assert lexical_runtime == lexical_before
    assert child.language.production == {}
    parental_summary = intergenerational_language_summary(
        (parent, second_parent, child),
        language_config=LANGUAGE,
        intergenerational_config=INTERGENERATIONAL,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        lexical_config=lexical_config,
        lexical_runtime=lexical_runtime,
    )
    assert (
        parental_summary["retained_intergenerational_association_count"]
        == 2
    )
    lexical_summary = lexical_evolution_summary(
        (parent, second_parent, child),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
        intergenerational_enabled=True,
    )
    assert (
        lexical_summary["channels"][
            "retained_intergenerational_provenance_count"]
        == 1
    )


def test_canonical_pruning_removes_lineage_and_counts_one_actual_loss():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    sender.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source, 0.90)
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    cap_one = LanguageEvolutionConfig(True, 1, 3, 0.20, 0.10, 25, True)

    outcome = communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
        language_config=cap_one,
    )

    assert outcome.produced_signal != source
    assert list(sender.language.production) == [(Meaning.FOOD, source)]
    assert all(
        association.lexical_evolution_provenance is None
        for association in sender.language.production.values()
    )
    assert language_runtime.lost_association_count == 1
    assert lexical_runtime.successful_mutation_count == 1


def test_saturated_observability_freezes_counters_but_index_and_mutation_advance():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    sender.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source)
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    language_runtime.communication_attempt_count = 1
    language_runtime.unknown_signal_count = 1
    language_runtime.last_communication_tick = 0
    cap = MAX_LEXICAL_OBSERVATION_OPPORTUNITIES
    lexical_runtime.mutation_derivation_index = cap
    lexical_runtime.eligible_mutation_opportunity_count = cap
    lexical_runtime.mutation_trigger_count = cap
    lexical_runtime.successful_mutation_count = cap
    lexical_runtime.substitution_count = cap
    lexical_runtime.descendant_production_creation_count = cap
    lexical_runtime.maximum_observed_lineage_depth = 1
    lexical_runtime.last_mutation_tick = 0
    frozen = {
        name: getattr(lexical_runtime, name)
        for name in language_module._LEXICAL_COUNTER_FIELDS
    }

    communicate_lexically(
        sender,
        receiver,
        language_runtime,
        lexical_runtime,
        lexical_config,
        tick=1,
    )

    assert {
        name: getattr(lexical_runtime, name)
        for name in language_module._LEXICAL_COUNTER_FIELDS
    } == frozen
    assert lexical_runtime.mutation_derivation_index == cap + 1
    assert lexical_runtime.last_mutation_tick == 1
    assert lexical_runtime.maximum_observed_lineage_depth == 1
    validate_lexical_evolution_runtime(
        lexical_runtime,
        config=lexical_config,
        language_runtime=language_runtime,
    )


def test_late_commit_failure_restores_every_language_owner_and_index(
    monkeypatch,
):
    sender = person(1)
    receiver = person(2)
    sender.language.production[
        (Meaning.FOOD, Signal((1, 2, 3)))
    ] = invented(Meaning.FOOD, Signal((1, 2, 3)))
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    original_sender = sender.language
    original_receiver = receiver.language
    original_language = copy.deepcopy(language_runtime)
    original_lexical = copy.deepcopy(lexical_runtime)
    real_commit = language_module._commit_lexical_runtime
    calls = 0

    def fail_once(target, proposed):
        nonlocal calls
        calls += 1
        real_commit(target, proposed)
        if calls == 1:
            raise RuntimeError("injected lexical commit failure")

    monkeypatch.setattr(
        language_module, "_commit_lexical_runtime", fail_once)
    with pytest.raises(RuntimeError, match="injected lexical commit failure"):
        communicate_lexically(
            sender,
            receiver,
            language_runtime,
            lexical_runtime,
            lexical_config,
        )

    assert sender.language is original_sender
    assert receiver.language is original_receiver
    assert language_runtime == original_language
    assert lexical_runtime == original_lexical
    assert calls == 2


def test_contact_dialect_late_failure_restores_all_language_runtimes(
    monkeypatch,
):
    sender = person(1)
    receiver = person(2)
    sender.language.production[
        (Meaning.FOOD, Signal((1, 2, 3)))
    ] = invented(Meaning.FOOD, Signal((1, 2, 3)))
    language_runtime, lexical_runtime, lexical_config = runtimes(
        rate=1.0, dialect=True, contact=True)
    dialect_runtime = CoalitionDialectRuntimeState()
    contact_runtime = LanguageContactRuntimeState()
    initialize_language_contact_runtime(contact_runtime, CONTACT)
    originals = (
        sender.language,
        receiver.language,
        copy.deepcopy(language_runtime),
        copy.deepcopy(lexical_runtime),
        copy.deepcopy(dialect_runtime),
        copy.deepcopy(contact_runtime),
    )
    real_commit = language_module._commit_lexical_runtime
    calls = 0

    def fail_once(target, proposed):
        nonlocal calls
        calls += 1
        real_commit(target, proposed)
        if calls == 1:
            raise RuntimeError("late contact lexical failure")

    monkeypatch.setattr(
        language_module, "_commit_lexical_runtime", fail_once)
    with pytest.raises(RuntimeError, match="late contact lexical failure"):
        communicate_lexically(
            sender,
            receiver,
            language_runtime,
            lexical_runtime,
            lexical_config,
            tick=2,
            active_ids={1, 2, 3},
            dialect_config=DIALECT,
            dialect_runtime=dialect_runtime,
            contact_config=CONTACT,
            contact_runtime=contact_runtime,
            coalition_membership_snapshot=coalition_snapshot(2),
        )

    assert sender.language is originals[0]
    assert receiver.language is originals[1]
    assert language_runtime == originals[2]
    assert lexical_runtime == originals[3]
    assert dialect_runtime == originals[4]
    assert contact_runtime == originals[5]
    assert calls == 2


def test_transfer_remains_committed_when_lexical_transaction_fails(
    monkeypatch,
):
    giver = person(1)
    recipient = person(2)
    giver.inventory["food"] = 2
    recipient.inventory["food"] = 0
    giver.currency = 0
    recipient.currency = 3
    giver.language.production[
        (Meaning.FOOD, Signal((1, 2, 3)))
    ] = invented(Meaning.FOOD, Signal((1, 2, 3)))
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    original_giver_language = giver.language
    original_recipient_language = recipient.language
    original_language_runtime = copy.deepcopy(language_runtime)
    original_lexical_runtime = copy.deepcopy(lexical_runtime)
    real_commit = language_module._commit_lexical_runtime
    calls = 0

    def fail_once(target, proposed):
        nonlocal calls
        calls += 1
        real_commit(target, proposed)
        if calls == 1:
            raise RuntimeError("post-transfer lexical failure")

    monkeypatch.setattr(
        language_module, "_commit_lexical_runtime", fail_once)
    with pytest.raises(RuntimeError, match="post-transfer lexical failure"):
        economy._commit_individual_transfer(
            giver,
            recipient,
            "food",
            t=1,
            social_config=SOCIAL_DISABLED,
            language_config=LANGUAGE,
            language_runtime=language_runtime,
            lexical_config=lexical_config,
            lexical_runtime=lexical_runtime,
            active_ids=frozenset({1, 2}),
        )

    assert giver.inventory["food"] == 1
    assert recipient.inventory["food"] == 1
    assert giver.currency == 2
    assert recipient.currency == 1
    assert giver.language is original_giver_language
    assert recipient.language is original_recipient_language
    assert language_runtime == original_language_runtime
    assert lexical_runtime == original_lexical_runtime


def test_future_mutation_provenance_fails_before_any_communication_mutation():
    sender = person(1)
    receiver = person(2)
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    sender.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD,
        descendant,
        lexical=LexicalEvolutionProvenance(
            first_mutation_tick=0,
            direct_source_signal=source,
            direct_source_owner_id=1,
            direct_source_origin=AssociationOrigin.INVENTED,
            mutation_operation=LexicalMutationOperation.SUBSTITUTION,
            mutation_position=0,
            mutation_index=2,
            lineage_depth=1,
            source_form_was_borrowed=False,
        ),
    )
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime())
    before = (
        sender.language,
        receiver.language,
        copy.deepcopy(language_runtime),
        copy.deepcopy(lexical_runtime),
    )

    with pytest.raises(
        LanguageInvariantError, match="exceeds committed runtime"
    ):
        communicate_lexically(
            sender,
            receiver,
            language_runtime,
            lexical_runtime,
            lexical_config,
            tick=1,
        )

    assert sender.language is before[0]
    assert receiver.language is before[1]
    assert language_runtime == before[2]
    assert lexical_runtime == before[3]


def test_dead_direct_source_is_valid_for_hash_but_absent_source_fails():
    source_owner = person(1)
    carrier = person(2)
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    carrier.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, lexical=provenance)
    language_runtime, lexical_runtime, _lexical_config = (
        committed_prior_mutation_runtime())
    state = SimulationState(
        people=[carrier],
        all_dead=[source_owner],
        next_inhabitant_id=3,
    )
    state.language = language_runtime
    state.lexical_evolution = lexical_runtime
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        lexical_evolution_enabled=True,
        lexical_mutation_rate=1.0,
    ).manifest_dict()

    assert len(canonical_state_hash(
        state, one_cell_world(), configuration)) == 64
    state.all_dead.clear()
    with pytest.raises(
        LanguageInvariantError, match="complete stable-ID cohort"
    ):
        canonical_state_hash(state, one_cell_world(), configuration)


def test_reset_validates_dead_sources_then_clears_lineage_and_runtime(
    monkeypatch,
):
    sim.reset_runtime_state()
    source_owner = person(1)
    carrier = person(2)
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=Signal((1, 2, 3)),
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    carrier.language.production[
        (Meaning.FOOD, Signal((3, 2, 3)))
    ] = invented(
        Meaning.FOOD, Signal((3, 2, 3)), lexical=provenance)
    language_runtime, lexical_runtime, _config = (
        committed_prior_mutation_runtime())
    sim.state.language = language_runtime
    sim.state.lexical_evolution = lexical_runtime
    monkeypatch.setattr(sim, "people", [carrier])
    monkeypatch.setattr(sim, "all_dead", [source_owner])

    sim.reset_runtime_state()

    assert carrier.language.production == {}
    assert carrier.language.comprehension == {}
    assert lexical_evolution_runtime_is_pristine(
        sim.state.lexical_evolution)


def test_reset_missing_historical_source_fails_without_partial_mutation(
    monkeypatch,
):
    sim.reset_runtime_state()
    carrier = person(2)
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=Signal((1, 2, 3)),
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    carrier.language.production[
        (Meaning.FOOD, Signal((3, 2, 3)))
    ] = invented(
        Meaning.FOOD, Signal((3, 2, 3)), lexical=provenance)
    language_runtime, lexical_runtime, _config = (
        committed_prior_mutation_runtime())
    sim.state.language = language_runtime
    sim.state.lexical_evolution = lexical_runtime
    monkeypatch.setattr(sim, "people", [carrier])
    monkeypatch.setattr(sim, "all_dead", [])
    original_language = carrier.language
    original_runtime = copy.deepcopy(sim.state.language)
    original_lexical = copy.deepcopy(sim.state.lexical_evolution)

    try:
        with pytest.raises(
            LanguageInvariantError, match="complete stable-ID cohort"
        ):
            sim.reset_runtime_state()
        assert carrier.language is original_language
        assert sim.state.language == original_runtime
        assert sim.state.lexical_evolution == original_lexical
    finally:
        sim.state.reset()


class OneShotPopulation:
    def __init__(self, values):
        self.values = tuple(values)
        self.iterations = 0

    def __iter__(self):
        if self.iterations:
            raise AssertionError("population iterable consumed twice")
        self.iterations += 1
        yield from self.values


def test_summary_is_one_pass_bounded_canonical_and_uses_distinct_indices():
    first = person(1)
    second = person(2)
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    first.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source, 0.70)
    first.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, 0.80, lexical=provenance)
    second.language.comprehension[(descendant, Meaning.FOOD)] = (
        LexicalAssociation(
            meaning=Meaning.FOOD,
            signal=descendant,
            confidence=0.40,
            observation_count=1,
            last_used_tick=0,
            origin=AssociationOrigin.LEARNED,
            learned_from_id=1,
            lexical_evolution_provenance=provenance,
        )
    )
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime())
    one_shot = OneShotPopulation((first, second))

    summary = lexical_evolution_summary(
        one_shot,
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )
    reverse_summary = lexical_evolution_summary(
        (second, first),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )
    first.language.production = dict(reversed(
        tuple(first.language.production.items())))
    reversed_insertion_summary = lexical_evolution_summary(
        (first, second),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )

    assert one_shot.iterations == 1
    assert summary == reverse_summary
    assert summary == reversed_insertion_summary
    assert summary["population_count"] == 2
    assert summary["retained_lexical_descendant_carrier_count"] == 2
    assert summary["retained_lexical_descendant_association_count"] == 2
    assert summary["distinct_retained_mutation_index_count"] == 1
    assert summary["retained_mutation_survival_rate"] == 1.0
    assert summary["usable_mutation_survival_rate"] == 1.0
    assert summary["source_descendant_coexistence_count"] == 1
    assert summary["selected_descendant_share"] == 1.0
    assert summary["maximum_retained_lineage_depth"] == 1
    source_text = inspect.getsource(
        language_module.lexical_evolution_summary)
    assert "sorted(" not in source_text
    assert "direct_source_owner_id" in source_text


def test_summary_reports_exact_production_and_comprehension_carriers():
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    production_only = person(1)
    comprehension_only = person(2)
    both_channels = person(3)
    below_usable = person(4)
    no_lineage = person(5)
    production_only.language.production[(Meaning.FOOD, descendant)] = (
        invented(Meaning.FOOD, descendant, 0.80, lexical=provenance)
    )
    comprehension_only.language.comprehension[
        (descendant, Meaning.FOOD)
    ] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=descendant,
        confidence=0.80,
        observation_count=1,
        last_used_tick=0,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
        lexical_evolution_provenance=provenance,
    )
    both_channels.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source, 0.70)
    both_channels.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, 0.80, lexical=provenance)
    both_channels.language.comprehension[
        (descendant, Meaning.FOOD)
    ] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=descendant,
        confidence=0.80,
        observation_count=1,
        last_used_tick=0,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
        lexical_evolution_provenance=provenance,
    )
    below_usable.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, 0.09, lexical=provenance)
    no_lineage.language.production[(Meaning.FOOD, source)] = invented(
        Meaning.FOOD, source, 0.80)
    population = (
        production_only,
        comprehension_only,
        both_channels,
        below_usable,
        no_lineage,
    )
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime())
    original_languages = tuple(
        copy.deepcopy(inhabitant.language) for inhabitant in population)
    original_language_runtime = copy.deepcopy(language_runtime)
    original_lexical_runtime = copy.deepcopy(lexical_runtime)
    original_random_state = random.getstate()
    one_shot = OneShotPopulation(population)

    summary = lexical_evolution_summary(
        one_shot,
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )
    reverse_summary = lexical_evolution_summary(
        reversed(population),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )
    for inhabitant in population:
        inhabitant.language.production = dict(reversed(
            tuple(inhabitant.language.production.items())))
        inhabitant.language.comprehension = dict(reversed(
            tuple(inhabitant.language.comprehension.items())))
    reversed_insertion_summary = lexical_evolution_summary(
        population,
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )

    assert one_shot.iterations == 1
    assert summary == reverse_summary == reversed_insertion_summary
    assert summary["retained_production_descendant_carrier_count"] == 3
    assert summary["usable_production_descendant_carrier_count"] == 2
    assert summary["retained_comprehension_descendant_carrier_count"] == 2
    assert summary["usable_comprehension_descendant_carrier_count"] == 2
    assert summary["retained_lexical_descendant_carrier_count"] == 4
    assert summary["usable_lexical_descendant_carrier_count"] == 3
    assert tuple(
        inhabitant.language for inhabitant in population
    ) == original_languages
    assert language_runtime == original_language_runtime
    assert lexical_runtime == original_lexical_runtime
    assert random.getstate() == original_random_state
    source_text = inspect.getsource(
        language_module.lexical_evolution_summary)
    assert source_text.count("for inhabitant in people:") == 1
    assert "sorted(" not in source_text


def test_summary_distinguishes_borrowed_sources_from_later_borrowing():
    source = Signal((1, 2, 3))
    descendant = Signal((3, 2, 3))
    borrowed_source_provenance = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=source,
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.LEARNED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=True,
    )
    ordinary_source_provenance = replace(
        borrowed_source_provenance,
        direct_source_origin=AssociationOrigin.INVENTED,
        source_form_was_borrowed=False,
    )
    retained_usable = person(1)
    retained_below_usable = person(2)
    later_borrowed = person(3)
    retained_usable.language.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD,
        descendant,
        0.80,
        lexical=borrowed_source_provenance,
    )
    retained_below_usable.language.comprehension[
        (descendant, Meaning.FOOD)
    ] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=descendant,
        confidence=0.09,
        observation_count=1,
        last_used_tick=0,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
        lexical_evolution_provenance=borrowed_source_provenance,
    )
    later_borrowed.language.production[
        (Meaning.FOOD, descendant)
    ] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=descendant,
        confidence=0.80,
        observation_count=1,
        last_used_tick=0,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
        borrowing_provenance=BorrowingProvenance(
            first_contact_tick=0,
            first_source_speaker_id=1,
            first_source_coalition_id=0,
            adoption_tick=0,
            adoption_source_speaker_id=1,
            adoption_source_coalition_id=0,
            exposure_count_at_adoption=3,
            successful_comprehension_count_at_adoption=2,
        ),
        lexical_evolution_provenance=ordinary_source_provenance,
    )
    language_runtime, lexical_runtime, lexical_config = (
        committed_prior_mutation_runtime())
    language_runtime.language_contact_enabled = True

    summary = lexical_evolution_summary(
        (retained_usable, retained_below_usable, later_borrowed),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
        contact_config=CONTACT,
    )

    assert (
        summary[
            "retained_borrowed_source_descendant_association_count"]
        == 2
    )
    assert (
        summary["usable_borrowed_source_descendant_association_count"]
        == 1
    )
    assert summary["retained_borrowed_source_descendant_carrier_count"] == 2
    assert summary["usable_borrowed_source_descendant_carrier_count"] == 1
    assert summary["channels"]["retained_borrowing_provenance_count"] == 1
    assert summary["channels"]["usable_borrowing_provenance_count"] == 1


def test_python_hash_seed_does_not_change_variant_summary_or_hash():
    script = textwrap.dedent(
        """
        import json
        from thalren_vale.config import (
            LanguageEvolutionConfig,
            LexicalEvolutionConfig,
            SimulationConfig,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.language import (
            AssociationOrigin,
            CommunicationContext,
            LanguageRuntimeState,
            LexicalAssociation,
            LexicalEvolutionRuntimeState,
            Meaning,
            Signal,
            communicate,
            initialize_language_runtime,
            initialize_lexical_evolution_runtime,
            lexical_evolution_summary,
        )
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        language_config = LanguageEvolutionConfig(
            True, 32, 3, 0.20, 0.10, 25, True)
        lexical_config = LexicalEvolutionConfig(True, 1.0, 8)
        sender = Inhabitant("Sender", 0, 0)
        receiver = Inhabitant("Receiver", 0, 0)
        sender.inhabitant_id = 1
        receiver.inhabitant_id = 2
        sender.faction = None
        receiver.faction = None
        source = Signal((1, 2, 3))
        sender.language.production[(Meaning.FOOD, source)] = LexicalAssociation(
            meaning=Meaning.FOOD,
            signal=source,
            confidence=0.60,
            origin=AssociationOrigin.INVENTED,
        )
        language_runtime = LanguageRuntimeState()
        initialize_language_runtime(
            language_runtime, 123, lexical_evolution_enabled=True)
        lexical_runtime = LexicalEvolutionRuntimeState()
        initialize_lexical_evolution_runtime(
            lexical_runtime, lexical_config, 123)
        outcome = communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=1,
            active_ids=frozenset({1, 2}),
            config=language_config,
            runtime=language_runtime,
            lexical_config=lexical_config,
            lexical_runtime=lexical_runtime,
        )
        state = SimulationState(
            people=[sender, receiver],
            next_inhabitant_id=3,
        )
        state.language = language_runtime
        state.lexical_evolution = lexical_runtime
        configuration = SimulationConfig(
            language_evolution_enabled=True,
            lexical_evolution_enabled=True,
            lexical_mutation_rate=1.0,
        ).manifest_dict()
        world = [[{
            "biome": "plains",
            "habitable": True,
            "resources": {
                "food": 1,
                "wood": 0,
                "ore": 0,
                "stone": 0,
                "water": 0,
            },
        }]]
        print(json.dumps({
            "signal": list(outcome.produced_signal.phoneme_ids),
            "summary": lexical_evolution_summary(
                state.people,
                language_config=language_config,
                lexical_config=lexical_config,
                language_runtime=language_runtime,
                lexical_runtime=lexical_runtime,
            ),
            "hash": canonical_state_hash(state, world, configuration),
        }, sort_keys=True))
        """
    )
    outputs = []
    for hash_seed in ("1", "987654"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.getcwd(),
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]


def test_saturated_summary_survival_rates_are_undefined():
    language_runtime, lexical_runtime, lexical_config = runtimes(rate=1.0)
    language_runtime.communication_attempt_count = 1
    language_runtime.unknown_signal_count = 1
    language_runtime.last_communication_tick = 0
    cap = MAX_LEXICAL_OBSERVATION_OPPORTUNITIES
    lexical_runtime.mutation_derivation_index = cap
    lexical_runtime.eligible_mutation_opportunity_count = cap
    lexical_runtime.mutation_trigger_count = cap
    lexical_runtime.successful_mutation_count = cap
    lexical_runtime.substitution_count = cap
    lexical_runtime.descendant_production_creation_count = cap
    lexical_runtime.maximum_observed_lineage_depth = 1
    lexical_runtime.last_mutation_tick = 0

    summary = lexical_evolution_summary(
        (),
        language_config=LANGUAGE,
        lexical_config=lexical_config,
        language_runtime=language_runtime,
        lexical_runtime=lexical_runtime,
    )
    assert summary["retained_mutation_survival_rate"] is None
    assert summary["usable_mutation_survival_rate"] is None
    assert summary["runtime"] == lexical_evolution_runtime_record(
        lexical_runtime,
        config=lexical_config,
        language_runtime=language_runtime,
    )


@pytest.mark.parametrize(
    "argument",
    [
        "--enable-lexical-evolution",
        "--disable-lexical-evolution=true",
        "--lexical-mutation-rate=1.0",
        "--maximum-lexical-lineage-depth",
        "--lexical-mut",
        "--enable-lex",
    ],
)
def test_runner_rejects_complete_lexical_option_family(argument):
    with pytest.raises(
        ValueError, match="uncontracted lexical evolution control"
    ):
        run_experiments._reject_uncontracted_lexical_evolution_args(
            (argument,))


def test_cli_namespace_uses_exact_controls_without_coalition_dependencies():
    args = SimpleNamespace(
        condition="baseline",
        ticks=None,
        pop_cap=None,
        starting_pop=None,
        faction_trust_threshold=None,
        war_tension_threshold=None,
        belief_sharing_prob=None,
        disable_layer="",
        disable_raids=False,
        disable_antistag=False,
        enable_belief_tracking=False,
        enable_language_evolution=True,
        disable_language_evolution=False,
        maximum_language_associations=None,
        maximum_signal_length=None,
        language_learning_rate=None,
        language_reinforcement_rate=None,
        language_forgetting_interval=None,
        enable_language_invention=False,
        disable_language_invention=False,
        maximum_social_ties=None,
        relationship_decay_interval=None,
        coalition_minimum_size=None,
        coalition_trust_threshold=None,
        coalition_familiarity_threshold=None,
        coalition_maximum_grievance=None,
        coalition_persistence_ticks=None,
        maximum_active_coalitions=None,
        same_coalition_learning_multiplier=None,
        same_coalition_reinforcement_multiplier=None,
        cross_group_learning_multiplier=None,
        borrowing_exposure_threshold=None,
        borrowing_confidence_threshold=None,
        maximum_parental_meanings_per_parent=None,
        intergenerational_learning_strength=None,
        enable_lexical_evolution=True,
        disable_lexical_evolution=False,
        lexical_mutation_rate=1.0,
        maximum_lexical_lineage_depth=32,
    )
    result = SimulationConfig.from_cli(args)
    assert result.lexical_evolution_config == LexicalEvolutionConfig(
        True, 1.0, 32)


def test_lexical_provenance_type_and_substitution_shape_fail_closed():
    config = LexicalEvolutionConfig(True, 1.0, 8)
    state = person(1).language
    descendant = Signal((3, 2, 3))
    bad = LexicalEvolutionProvenance(
        first_mutation_tick=0,
        direct_source_signal=Signal((1, 2, 4)),
        direct_source_owner_id=1,
        direct_source_origin=AssociationOrigin.INVENTED,
        mutation_operation=LexicalMutationOperation.SUBSTITUTION,
        mutation_position=0,
        mutation_index=1,
        lineage_depth=1,
        source_form_was_borrowed=False,
    )
    state.production[(Meaning.FOOD, descendant)] = invented(
        Meaning.FOOD, descendant, lexical=bad)
    with pytest.raises(
        LanguageInvariantError, match="exactly one substitution"
    ):
        validate_agent_language_state(
            state,
            config=LANGUAGE,
            lexical_config=config,
            owner_id=1,
        )
