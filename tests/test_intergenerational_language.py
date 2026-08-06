"""Bounded exact-once language acquisition from committed birth parents."""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from thalren_vale import language as language_module
from thalren_vale import sim
from thalren_vale.coalitions import (
    CoalitionRuntimeState,
    InformalCoalition,
    build_coalition_membership_snapshot,
)
from thalren_vale.config import (
    CoalitionConfig,
    IntergenerationalLanguageConfig,
    LanguageContactConfig,
    LanguageEvolutionConfig,
    SimulationConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    AssociationOrigin,
    BorrowingProvenance,
    CommunicationContext,
    ContactExposure,
    IntergenerationalLanguageRuntimeState,
    IntergenerationalProvenance,
    LanguageContactRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    MAX_INTERGENERATIONAL_ATTEMPTS,
    Meaning,
    Signal,
    agent_language_record,
    communicate,
    initialize_intergenerational_language_runtime,
    initialize_language_contact_runtime,
    initialize_language_runtime,
    intergenerational_language_summary,
    intergenerational_language_runtime_record,
    intergenerational_runtime_is_pristine,
    transmit_intergenerational_language,
    validate_agent_language_state,
    validate_intergenerational_language_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.state import SimulationState


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)
INTERGENERATIONAL = IntergenerationalLanguageConfig(True, 2, 0.20)
CONTACT = LanguageContactConfig(True, 1.50, 3, 0.50)
COALITIONS = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)


@pytest.fixture(autouse=True)
def isolated_simulation_state():
    """Keep birth-hook tests isolated from module-owned runtime collections."""
    original_people = sim.people
    original_all_dead = sim.all_dead
    original_pop_cap = sim.POP_CAP
    original_birth_cap = sim.MAX_BIRTHS_PER_TICK
    sim.people = sim.state.people
    sim.all_dead = sim.state.all_dead
    sim.grid_occupants.clear()
    sim.reset_runtime_state()
    yield
    sim.people = sim.state.people
    sim.all_dead = sim.state.all_dead
    sim.grid_occupants.clear()
    sim.reset_runtime_state()
    sim.POP_CAP = original_pop_cap
    sim.MAX_BIRTHS_PER_TICK = original_birth_cap
    sim.people = original_people
    sim.all_dead = original_all_dead


def person(inhabitant_id: int, *, generation: int = 0) -> Inhabitant:
    inhabitant = Inhabitant(f"P{inhabitant_id}", 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    inhabitant.faction = None
    inhabitant.generation = generation
    return inhabitant


def invented(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.60,
    *,
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
        origin=AssociationOrigin.INVENTED,
    )


def borrowed(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.70,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        successful_uses=2,
        observation_count=3,
        last_used_tick=2,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=0,
        borrowing_provenance=BorrowingProvenance(
            first_contact_tick=1,
            first_source_speaker_id=0,
            first_source_coalition_id=0,
            adoption_tick=2,
            adoption_source_speaker_id=0,
            adoption_source_coalition_id=0,
            exposure_count_at_adoption=3,
            successful_comprehension_count_at_adoption=2,
        ),
    )


def initialized_runtimes(
    *,
    contact: bool = False,
    intergenerational_config: IntergenerationalLanguageConfig = (
        INTERGENERATIONAL
    ),
) -> tuple[
    LanguageRuntimeState,
    IntergenerationalLanguageRuntimeState,
    LanguageContactRuntimeState | None,
]:
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime,
        123,
        language_contact_enabled=contact,
        intergenerational_language_enabled=True,
    )
    intergenerational_runtime = IntergenerationalLanguageRuntimeState()
    initialize_intergenerational_language_runtime(
        intergenerational_runtime,
        intergenerational_config,
    )
    contact_runtime = None
    if contact:
        contact_runtime = LanguageContactRuntimeState()
        initialize_language_contact_runtime(contact_runtime, CONTACT)
    return language_runtime, intergenerational_runtime, contact_runtime


def transmit(
    child: Inhabitant,
    parents: tuple[Inhabitant, Inhabitant],
    *,
    tick: int = 5,
    language_config: LanguageEvolutionConfig = LANGUAGE,
    intergenerational_config: IntergenerationalLanguageConfig = (
        INTERGENERATIONAL
    ),
    language_runtime: LanguageRuntimeState | None = None,
    intergenerational_runtime: (
        IntergenerationalLanguageRuntimeState | None
    ) = None,
    contact_config: LanguageContactConfig | None = None,
) -> tuple[LanguageRuntimeState, IntergenerationalLanguageRuntimeState]:
    if language_runtime is None or intergenerational_runtime is None:
        language_runtime, intergenerational_runtime, _ = initialized_runtimes(
            contact=contact_config is not None,
            intergenerational_config=intergenerational_config,
        )
    transmit_intergenerational_language(
        child,
        parents,
        tick=tick,
        language_config=language_config,
        intergenerational_config=intergenerational_config,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        contact_config=contact_config,
    )
    return language_runtime, intergenerational_runtime


def add_production(
    inhabitant: Inhabitant,
    association: LexicalAssociation,
) -> None:
    inhabitant.language.production[
        (association.meaning, association.signal)
    ] = association


def prepare_birth_parents() -> tuple[Inhabitant, Inhabitant]:
    first = Inhabitant("Parent A", 0, 0)
    second = Inhabitant("Parent B", 0, 0)
    for parent, other in ((first, second), (second, first)):
        parent.trust[other.name] = 100
        parent.inventory["food"] = 20
        parent.hunger = 0
        parent.faction = None
    sim._spawn(first)
    sim._spawn(second)
    sim.MAX_BIRTHS_PER_TICK = 1
    sim.POP_CAP = 20
    return first, second


def configure_enabled_birth_runtime() -> None:
    initialize_language_runtime(
        sim.state.language,
        123,
        intergenerational_language_enabled=True,
    )
    initialize_intergenerational_language_runtime(
        sim.state.intergenerational_language,
        INTERGENERATIONAL,
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


def test_partial_comprehension_uses_salience_then_exact_parent_cap():
    first, second, child = person(1), person(2), person(3, generation=1)
    low_fixed_order = Signal((0, 1))
    salient = Signal((2, 1))
    second_salient = Signal((3, 1))
    unusable = Signal((4, 1))
    add_production(
        first,
        invented(
            Meaning.FOOD,
            low_fixed_order,
            0.60,
            successful=50,
            observations=50,
        ),
    )
    add_production(
        first,
        invented(Meaning.WOOD, salient, 0.90, successful=1),
    )
    add_production(
        first,
        invented(Meaning.ORE, second_salient, 0.80, successful=1),
    )
    add_production(
        first,
        invented(
            Meaning.STONE,
            unusable,
            0.19,
            successful=100,
        ),
    )
    parent_languages = copy.deepcopy((first.language, second.language))
    rng_state = random.getstate()

    language_runtime, intergenerational_runtime = transmit(
        child, (first, second))

    assert child.language.production == {}
    assert set(child.language.comprehension) == {
        (salient, Meaning.WOOD),
        (second_salient, Meaning.ORE),
    }
    for association in child.language.comprehension.values():
        assert association.confidence == 0.20
        assert association.observation_count == 1
        assert association.successful_uses == 0
        assert association.failed_uses == 0
        assert association.origin is AssociationOrigin.LEARNED
        assert association.learned_from_id == 1
        assert association.last_used_tick == 5
    assert language_runtime.learned_association_count == 0
    assert intergenerational_runtime.transmitted_signal_exposure_count == 2
    assert (
        intergenerational_runtime
        .parental_source_without_usable_signal_count
    ) == 1
    assert (first.language, second.language) == parent_languages
    assert random.getstate() == rng_state


def test_parental_same_meaning_tie_uses_authoritative_lexical_signal():
    first, second, child = person(1), person(2), person(3, generation=1)
    later = Signal((7, 1))
    canonical = Signal((0, 1))
    add_production(first, invented(Meaning.FOOD, later, 0.80))
    add_production(first, invented(Meaning.FOOD, canonical, 0.80))

    transmit(child, (first, second))

    assert set(child.language.comprehension) == {
        (canonical, Meaning.FOOD),
    }


def test_parent_order_is_canonical_and_duplicate_competing_forms_partition():
    first, second = person(1), person(2)
    shared = Signal((1, 1))
    first_wood = Signal((2, 1))
    second_wood = Signal((3, 1))
    add_production(first, invented(Meaning.FOOD, shared, 0.90))
    add_production(second, invented(Meaning.FOOD, shared, 0.80))
    add_production(first, invented(Meaning.WOOD, first_wood, 0.70))
    add_production(second, invented(Meaning.WOOD, second_wood, 0.70))

    records = []
    runtime_records = []
    for parents in ((first, second), (second, first)):
        child = person(3, generation=1)
        language_runtime, intergenerational_runtime, _ = initialized_runtimes()
        transmit(
            child,
            parents,
            language_runtime=language_runtime,
            intergenerational_runtime=intergenerational_runtime,
        )
        records.append(agent_language_record(
            child,
            config=LANGUAGE,
            include_intergenerational=True,
        ))
        runtime_records.append(intergenerational_language_runtime_record(
            intergenerational_runtime,
            config=INTERGENERATIONAL,
            language_runtime=language_runtime,
        ))

    assert records[0] == records[1]
    assert runtime_records[0] == runtime_records[1]
    shared_association = next(
        association
        for association in records[0]["comprehension"]
        if association["meaning"] == "FOOD"
    )
    assert shared_association["observation_count"] == 2
    assert shared_association["intergenerational_provenance"] == {
        "first_transmission_tick": 5,
        "first_parent_id": 1,
        "first_parent_signal_origin": "invented",
        "first_parent_form_was_borrowed": False,
        "parent_count": 2,
        "borrowed_parent_count": 0,
    }
    assert runtime_records[0]["transmitted_signal_exposure_count"] == 4
    assert runtime_records[0]["comprehension_association_creation_count"] == 3
    assert (
        runtime_records[0]["comprehension_association_reinforcement_count"]
        == 1
    )
    assert runtime_records[0]["duplicate_parent_form_count"] == 1
    assert runtime_records[0]["competing_parent_form_count"] == 1


def test_existing_comprehension_is_observed_without_overwriting_first_channel():
    first, second, child = person(1), person(2), person(3, generation=1)
    signal = Signal((1, 4))
    add_production(first, invented(Meaning.FOOD, signal, 0.80))
    child.language.comprehension[(signal, Meaning.FOOD)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=signal,
        confidence=0.40,
        successful_uses=3,
        failed_uses=2,
        observation_count=5,
        last_used_tick=3,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=0,
    )

    transmit(child, (second, first))

    learned = child.language.comprehension[(signal, Meaning.FOOD)]
    assert learned.confidence == 0.60
    assert learned.observation_count == 6
    assert learned.successful_uses == 3
    assert learned.failed_uses == 2
    assert learned.origin is AssociationOrigin.LEARNED
    assert learned.learned_from_id == 0
    assert learned.intergenerational_provenance.first_parent_id == 1


def test_borrowed_parent_form_records_only_direct_parent_channel():
    first, second, child = person(1), person(2), person(4, generation=1)
    signal = Signal((5, 1))
    add_production(first, borrowed(Meaning.FOOD, signal))
    language_runtime, intergenerational_runtime, contact_runtime = (
        initialized_runtimes(contact=True)
    )
    assert contact_runtime is not None
    before_contact = copy.deepcopy(contact_runtime)

    transmit(
        child,
        (second, first),
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        contact_config=CONTACT,
    )

    association = child.language.comprehension[(signal, Meaning.FOOD)]
    provenance = association.intergenerational_provenance
    assert association.borrowing_provenance is None
    assert association.contact_exposure is None
    assert provenance == IntergenerationalProvenance(
        first_transmission_tick=5,
        first_parent_id=1,
        first_parent_signal_origin=AssociationOrigin.LEARNED,
        first_parent_form_was_borrowed=True,
        parent_count=1,
        borrowed_parent_count=1,
    )
    assert contact_runtime == before_contact
    assert (
        intergenerational_runtime.borrowed_parent_form_transmission_count
        == 1
    )


@pytest.mark.parametrize(
    ("first_borrowed", "second_borrowed", "expected_borrowed_count"),
    [
        (False, False, 0),
        (False, True, 1),
        (True, False, 1),
        (True, True, 2),
    ],
)
def test_duplicate_parent_borrowing_counts_each_direct_source_exactly(
    first_borrowed,
    second_borrowed,
    expected_borrowed_count,
):
    first, second, child = person(1), person(2), person(3, generation=1)
    signal = Signal((5, 2))
    first_association = (
        borrowed(Meaning.FOOD, signal)
        if first_borrowed
        else invented(Meaning.FOOD, signal, 0.70)
    )
    second_association = (
        borrowed(Meaning.FOOD, signal)
        if second_borrowed
        else invented(Meaning.FOOD, signal, 0.70)
    )
    add_production(first, first_association)
    add_production(second, second_association)
    language_runtime, intergenerational_runtime, contact_runtime = (
        initialized_runtimes(contact=True)
    )
    assert contact_runtime is not None
    before_contact = copy.deepcopy(contact_runtime)

    transmit(
        child,
        (second, first),
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        contact_config=CONTACT,
    )

    provenance = child.language.comprehension[
        (signal, Meaning.FOOD)
    ].intergenerational_provenance
    assert provenance.parent_count == 2
    assert provenance.borrowed_parent_count == expected_borrowed_count
    assert provenance.first_parent_form_was_borrowed is first_borrowed
    assert (
        intergenerational_runtime.borrowed_parent_form_transmission_count
        == expected_borrowed_count
    )
    assert intergenerational_runtime.duplicate_parent_form_count == 1
    assert contact_runtime == before_contact


def test_later_authentic_contact_coexists_without_provenance_copy_or_overwrite():
    first, second, child = person(1), person(2), person(4, generation=1)
    signal = Signal((2, 6))
    add_production(first, invented(Meaning.FOOD, signal, 0.80))
    language_runtime, intergenerational_runtime, contact_runtime = (
        initialized_runtimes(contact=True)
    )
    assert contact_runtime is not None
    transmit(
        child,
        (first, second),
        tick=2,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
        contact_config=CONTACT,
    )
    first_provenance = child.language.comprehension[
        (signal, Meaning.FOOD)
    ].intergenerational_provenance
    coalition_runtime = CoalitionRuntimeState(
        active_coalitions={
            0: InformalCoalition(0, 1, (1, 2, 3)),
            1: InformalCoalition(1, 1, (4, 5, 6)),
        },
        member_to_coalition={
            1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1,
        },
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=2,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
    )
    frozen = build_coalition_membership_snapshot(
        coalition_runtime,
        snapshot_tick=3,
        active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
        config=COALITIONS,
    )

    communicate(
        first,
        child,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=3,
        active_ids=frozenset(frozen.active_inhabitant_ids),
        config=LANGUAGE,
        runtime=language_runtime,
        contact_config=CONTACT,
        contact_runtime=contact_runtime,
        coalition_membership_snapshot=frozen,
    )

    association = child.language.comprehension[(signal, Meaning.FOOD)]
    assert association.intergenerational_provenance == first_provenance
    assert association.contact_exposure == ContactExposure(3, 1, 0, 1, 1)
    assert child.language.production == {}

    for tick in (4, 5):
        coalition_runtime.last_observation_tick = tick - 1
        later = build_coalition_membership_snapshot(
            coalition_runtime,
            snapshot_tick=tick,
            active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
            config=COALITIONS,
        )
        communicate(
            first,
            child,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=frozenset(later.active_inhabitant_ids),
            config=LANGUAGE,
            runtime=language_runtime,
            contact_config=CONTACT,
            contact_runtime=contact_runtime,
            coalition_membership_snapshot=later,
        )

    promoted = child.language.production[(Meaning.FOOD, signal)]
    assert promoted.intergenerational_provenance is None
    assert child.language.comprehension[
        (signal, Meaning.FOOD)
    ].intergenerational_provenance == first_provenance


def test_retention_runs_once_and_lost_association_has_no_hidden_archive(
    monkeypatch,
):
    bounded_language = LanguageEvolutionConfig(
        True, 4, 3, 0.20, 0.10, 25, True)
    intergenerational = IntergenerationalLanguageConfig(True, 1, 0.20)
    first, second, child = person(1), person(2), person(3, generation=1)
    parental_signal = Signal((7, 7))
    add_production(first, invented(Meaning.FOOD, parental_signal, 0.80))
    for index, meaning in enumerate(Meaning):
        signal = Signal((index, 0))
        child.language.production[(meaning, signal)] = invented(
            meaning, signal, 0.90)
    language_runtime, intergenerational_runtime, _ = initialized_runtimes(
        intergenerational_config=intergenerational)
    real_retention = language_module._retain_canonical
    calls = 0

    def counted_retention(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_retention(*args, **kwargs)

    monkeypatch.setattr(
        language_module, "_retain_canonical", counted_retention)
    transmit(
        child,
        (first, second),
        language_config=bounded_language,
        intergenerational_config=intergenerational,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )

    assert calls == 1
    assert language_runtime.lost_association_count == 1
    assert intergenerational_runtime.comprehension_association_creation_count == 1
    assert child.language.comprehension == {}
    assert all(
        association.intergenerational_provenance is None
        for association in child.language.production.values()
    )


def test_exact_once_child_sentinel_advances_without_parental_forms():
    first, second = person(1), person(2)
    first_child = person(3, generation=1)
    second_child = person(4, generation=1)
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()

    transmit(
        first_child,
        (first, second),
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )
    after_first = copy.deepcopy(intergenerational_runtime)
    with pytest.raises(
        LanguageInvariantError, match="strictly advance|already carries"
    ):
        transmit(
            first_child,
            (first, second),
            language_runtime=language_runtime,
            intergenerational_runtime=intergenerational_runtime,
        )
    assert intergenerational_runtime == after_first
    assert intergenerational_runtime.last_transmission_child_id == 3
    assert intergenerational_runtime.last_transmission_tick == 5
    assert (
        intergenerational_runtime
        .parental_source_without_usable_signal_count
    ) == 2

    transmit(
        second_child,
        (second, first),
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )
    assert intergenerational_runtime.last_transmission_child_id == 4
    assert (
        intergenerational_runtime
        .successful_birth_transmission_attempt_count
    ) == 2


def test_synchronized_counter_saturation_still_updates_tick_and_child_sentinel():
    first, second, child = person(0), person(1), person(3, generation=1)
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()
    cap = MAX_INTERGENERATIONAL_ATTEMPTS
    intergenerational_runtime.successful_birth_transmission_attempt_count = cap
    intergenerational_runtime.parental_source_count = 2 * cap
    intergenerational_runtime.transmitted_signal_exposure_count = 2 * cap
    intergenerational_runtime.comprehension_association_creation_count = 2 * cap
    intergenerational_runtime.last_transmission_tick = 4
    intergenerational_runtime.last_transmission_child_id = 2
    before_counters = {
        name: getattr(intergenerational_runtime, name)
        for name in language_module._INTERGENERATIONAL_COUNTER_FIELDS
    }
    validate_intergenerational_language_runtime(
        intergenerational_runtime,
        config=INTERGENERATIONAL,
        language_runtime=language_runtime,
    )

    transmit(
        child,
        (second, first),
        tick=5,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )

    assert {
        name: getattr(intergenerational_runtime, name)
        for name in language_module._INTERGENERATIONAL_COUNTER_FIELDS
    } == before_counters
    assert intergenerational_runtime.last_transmission_tick == 5
    assert intergenerational_runtime.last_transmission_child_id == 3


def test_repeated_births_remain_agent_local_and_bounded():
    first, second = person(1), person(2)
    for index, meaning in enumerate(Meaning):
        add_production(
            first,
            invented(
                meaning,
                Signal((index, 1)),
                round(0.80 - index * 0.05, 6),
            ),
        )
        add_production(
            second,
            invented(
                meaning,
                Signal((index, 2)),
                round(0.80 - index * 0.05, 6),
            ),
        )
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()

    for child_id in range(3, 53):
        child = person(child_id, generation=1)
        transmit(
            child,
            (first, second),
            tick=5,
            language_runtime=language_runtime,
            intergenerational_runtime=intergenerational_runtime,
        )
        assert child.language.production == {}
        assert len(child.language.comprehension) == 4
        assert len(child.language.comprehension) <= (
            LANGUAGE.maximum_language_associations)

    assert (
        intergenerational_runtime
        .successful_birth_transmission_attempt_count
    ) == 50
    assert intergenerational_runtime.parental_source_count == 100
    assert intergenerational_runtime.transmitted_signal_exposure_count == 200
    assert intergenerational_runtime.last_transmission_child_id == 52


@pytest.mark.parametrize(
    "corruption",
    ("config", "runtime", "parent", "child", "provenance"),
)
def test_malformed_transaction_inputs_fail_before_any_owner_mutation(
    corruption,
):
    first, second, child = person(1), person(2), person(3, generation=1)
    signal = Signal((1, 3))
    add_production(first, invented(Meaning.FOOD, signal, 0.80))
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()
    intergenerational_config: object = INTERGENERATIONAL
    if corruption == "config":
        intergenerational_config = SimpleNamespace(
            intergenerational_language_enabled=True,
            maximum_parental_meanings_per_parent=2,
            intergenerational_learning_strength=0.20,
        )
    elif corruption == "runtime":
        intergenerational_runtime.parental_source_count = 1
    elif corruption == "parent":
        first.language.production[
            (Meaning.WOOD, Signal((2, 3)))
        ] = replace(
            invented(Meaning.WOOD, Signal((2, 3)), 0.80),
            confidence=0.1234567,
        )
    elif corruption == "child":
        child.language.comprehension[
            (Signal((3, 3)), Meaning.FOOD)
        ] = invented(Meaning.FOOD, Signal((3, 3)), 0.50)
    else:
        child.language.comprehension[
            (Signal((3, 3)), Meaning.FOOD)
        ] = LexicalAssociation(
            meaning=Meaning.FOOD,
            signal=Signal((3, 3)),
            confidence=0.50,
            observation_count=1,
            last_used_tick=1,
            origin=AssociationOrigin.LEARNED,
            learned_from_id=1,
            intergenerational_provenance=IntergenerationalProvenance(
                first_transmission_tick=1,
                first_parent_id=1,
                first_parent_signal_origin=AssociationOrigin.INVENTED,
                first_parent_form_was_borrowed=False,
                parent_count=3,
                borrowed_parent_count=0,
            ),
        )
    before_child = copy.deepcopy(child.language)
    before_parents = copy.deepcopy((first.language, second.language))
    before_language_runtime = copy.deepcopy(language_runtime)
    before_intergenerational_runtime = copy.deepcopy(
        intergenerational_runtime)
    rng_state = random.getstate()

    with pytest.raises((LanguageInvariantError, AttributeError)):
        transmit_intergenerational_language(
            child,
            (first, second),
            tick=5,
            language_config=LANGUAGE,
            intergenerational_config=intergenerational_config,
            language_runtime=language_runtime,
            intergenerational_runtime=intergenerational_runtime,
        )

    assert child.language == before_child
    assert (first.language, second.language) == before_parents
    assert language_runtime == before_language_runtime
    assert intergenerational_runtime == before_intergenerational_runtime
    assert random.getstate() == rng_state


def test_post_spawn_failure_keeps_birth_but_rolls_back_language_owners(
    monkeypatch,
):
    first, second = prepare_birth_parents()
    first.faction = "F"
    second.faction = "F"
    faction = SimpleNamespace(name="F", members=[])
    sim.factions.append(faction)
    signal = Signal((1, 7))
    add_production(first, invented(Meaning.FOOD, signal, 0.80))
    configure_enabled_birth_runtime()
    monkeypatch.setattr(sim, "_make_traveler_name", lambda _used: "Child")
    monkeypatch.setattr(sim.random, "choice", lambda values: values[0])

    religion_calls: list[object] = []
    event_calls: list[object] = []
    monkeypatch.setattr(
        sim.religion,
        "get_faction_religion",
        lambda value: religion_calls.append(value),
    )
    monkeypatch.setattr(
        sim,
        "emit_event",
        lambda *args, **kwargs: event_calls.append((args, kwargs)),
    )

    entry: dict[str, object] = {}
    real_transmit = sim.transmit_intergenerational_language

    def recording_transmit(child, parents, **kwargs):
        entry["child"] = child
        entry["child_language"] = copy.deepcopy(child.language)
        entry["language_runtime"] = copy.deepcopy(sim.state.language)
        entry["intergenerational_runtime"] = copy.deepcopy(
            sim.state.intergenerational_language)
        entry["contact_runtime"] = copy.deepcopy(sim.state.language_contact)
        entry["dialect_runtime"] = copy.deepcopy(sim.state.dialect)
        entry["coalition_runtime"] = copy.deepcopy(sim.state.coalitions)
        entry["rng"] = random.getstate()
        entry["population"] = tuple(sim.people)
        assert child in sim.people
        assert child in sim.grid_occupants[(child.r, child.c)]
        assert child.inhabitant_id == 2
        assert tuple(parents) == (first, second)
        return real_transmit(child, parents, **kwargs)

    monkeypatch.setattr(
        sim, "transmit_intergenerational_language", recording_transmit)
    real_commit = language_module._commit_intergenerational_runtime
    commit_calls = 0

    def fail_first_commit(target, proposed):
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            target.last_transmission_tick = 999
            raise RuntimeError("injected late transmission failure")
        return real_commit(target, proposed)

    monkeypatch.setattr(
        language_module,
        "_commit_intergenerational_runtime",
        fail_first_commit,
    )

    with pytest.raises(RuntimeError, match="injected late"):
        sim.procreation_layer(
            1,
            LANGUAGE,
            INTERGENERATIONAL,
            None,
        )

    child = entry["child"]
    assert child in sim.people
    assert child in faction.members
    assert child.inhabitant_id == 2
    assert sim.state.next_inhabitant_id == 3
    assert child.language == entry["child_language"]
    assert sim.state.language == entry["language_runtime"]
    assert (
        sim.state.intergenerational_language
        == entry["intergenerational_runtime"]
    )
    assert sim.state.language_contact == entry["contact_runtime"]
    assert sim.state.dialect == entry["dialect_runtime"]
    assert sim.state.coalitions == entry["coalition_runtime"]
    assert tuple(sim.people) == entry["population"]
    assert random.getstate() == entry["rng"]
    assert first.inventory["food"] == 15
    assert second.inventory["food"] == 15
    assert religion_calls == []
    assert event_calls == []
    assert commit_calls == 2


def test_only_successful_birth_admission_enters_hook(monkeypatch):
    first, second = prepare_birth_parents()
    configure_enabled_birth_runtime()
    monkeypatch.setattr(sim, "_make_traveler_name", lambda _used: "Child")
    monkeypatch.setattr(sim.random, "choice", lambda values: values[0])
    calls: list[tuple[object, tuple[object, object]]] = []
    real_transmit = sim.transmit_intergenerational_language

    def record(child, parents, **kwargs):
        assert child in sim.people
        assert child.inhabitant_id == 2
        calls.append((child, parents))
        return real_transmit(child, parents, **kwargs)

    monkeypatch.setattr(sim, "transmit_intergenerational_language", record)
    sim.procreation_layer(1, LANGUAGE, INTERGENERATIONAL, None)

    assert len(calls) == 1
    assert calls[0][1] == (first, second)
    traveler = Inhabitant("Traveler", 0, 0)
    sim._spawn(traveler)
    assert len(calls) == 1
    assert inspect.getsource(sim).count(
        "transmit_intergenerational_language("
    ) == 1
    transmission_source = inspect.getsource(
        language_module.transmit_intergenerational_language)
    assert "population" not in transmission_source
    assert "people" not in transmission_source


def test_failed_spawn_and_disabled_birth_never_enter_helper(monkeypatch):
    first, second = prepare_birth_parents()
    real_spawn = sim._spawn
    configure_enabled_birth_runtime()
    monkeypatch.setattr(sim, "_make_traveler_name", lambda _used: "Child")
    monkeypatch.setattr(sim.random, "choice", lambda values: values[0])
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        sim, "transmit_intergenerational_language", forbidden)
    monkeypatch.setattr(
        sim, "_spawn", lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("admission failed")))
    with pytest.raises(RuntimeError, match="admission failed"):
        sim.procreation_layer(1, LANGUAGE, INTERGENERATIONAL, None)
    assert calls == 0

    monkeypatch.setattr(sim, "_spawn", real_spawn)
    sim.reset_runtime_state()
    ineligible_first = Inhabitant("Ineligible A", 0, 0)
    ineligible_second = Inhabitant("Ineligible B", 0, 0)
    for inhabitant in (ineligible_first, ineligible_second):
        inhabitant.faction = None
        inhabitant.inventory["food"] = 20
        sim._spawn(inhabitant)
    configure_enabled_birth_runtime()
    sim.procreation_layer(1, LANGUAGE, INTERGENERATIONAL, None)
    assert calls == 0

    sim.reset_runtime_state()
    prepare_birth_parents()
    disabled = IntergenerationalLanguageConfig(False, 2, 0.20)
    sim.procreation_layer(1, LANGUAGE, disabled, None)
    assert calls == 0
    assert len(sim.people) == 3
    assert sim.people[-1].inhabitant_id == 2


def test_parent_death_remains_valid_hash_provenance_but_absence_fails():
    first, second, child = person(1), person(2), person(3, generation=1)
    signal = Signal((1, 5))
    add_production(first, invented(Meaning.FOOD, signal, 0.80))
    state = SimulationState(
        people=[child],
        all_dead=[first, second],
        next_inhabitant_id=4,
    )
    initialize_language_runtime(
        state.language,
        123,
        intergenerational_language_enabled=True,
    )
    initialize_intergenerational_language_runtime(
        state.intergenerational_language,
        INTERGENERATIONAL,
    )
    transmit(
        child,
        (first, second),
        language_runtime=state.language,
        intergenerational_runtime=state.intergenerational_language,
    )
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        intergenerational_language_enabled=True,
    ).manifest_dict()

    assert len(canonical_state_hash(
        state, one_cell_world(), configuration)) == 64
    state.all_dead.remove(first)
    with pytest.raises(
        LanguageInvariantError, match="complete stable-ID cohort"
    ):
        canonical_state_hash(state, one_cell_world(), configuration)


def test_hash_rejects_transmission_sentinel_absent_from_complete_cohort():
    first, second = person(1), person(2)
    state = SimulationState(
        people=[first, second],
        next_inhabitant_id=3,
    )
    initialize_language_runtime(
        state.language,
        123,
        intergenerational_language_enabled=True,
    )
    initialize_intergenerational_language_runtime(
        state.intergenerational_language,
        INTERGENERATIONAL,
    )
    runtime = state.intergenerational_language
    runtime.successful_birth_transmission_attempt_count = 1
    runtime.parental_source_count = 2
    runtime.parental_source_without_usable_signal_count = 2
    runtime.last_transmission_tick = 5
    runtime.last_transmission_child_id = 99
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        intergenerational_language_enabled=True,
    ).manifest_dict()

    with pytest.raises(
        LanguageInvariantError, match="last transmitted child ID"
    ):
        canonical_state_hash(state, one_cell_world(), configuration)


def test_reversed_parents_produce_identical_enabled_hashes():
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        intergenerational_language_enabled=True,
    ).manifest_dict()
    hashes = []
    for reverse in (False, True):
        first, second, child = person(1), person(2), person(3, generation=1)
        shared = Signal((1, 2))
        add_production(first, invented(Meaning.FOOD, shared, 0.80))
        add_production(second, invented(Meaning.FOOD, shared, 0.70))
        state = SimulationState(
            people=[first, second, child],
            next_inhabitant_id=4,
        )
        initialize_language_runtime(
            state.language,
            123,
            intergenerational_language_enabled=True,
        )
        initialize_intergenerational_language_runtime(
            state.intergenerational_language,
            INTERGENERATIONAL,
        )
        parents = (second, first) if reverse else (first, second)
        transmit(
            child,
            parents,
            language_runtime=state.language,
            intergenerational_runtime=state.intergenerational_language,
        )
        hashes.append(canonical_state_hash(
            state, one_cell_world(), configuration))

    assert hashes[0] == hashes[1]


def test_python_hash_seed_does_not_change_enabled_hash_or_summary():
    project_root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import json

        from thalren_vale.config import (
            IntergenerationalLanguageConfig,
            LanguageEvolutionConfig,
            SimulationConfig,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.language import (
            AssociationOrigin,
            IntergenerationalLanguageRuntimeState,
            LanguageRuntimeState,
            LexicalAssociation,
            Meaning,
            Signal,
            initialize_intergenerational_language_runtime,
            initialize_language_runtime,
            intergenerational_language_summary,
            transmit_intergenerational_language,
        )
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        language = LanguageEvolutionConfig(
            True, 32, 3, 0.20, 0.10, 25, True)
        transmission = IntergenerationalLanguageConfig(True, 2, 0.20)
        people = [Inhabitant(f"P{value}", 0, 0) for value in (1, 2, 3)]
        for inhabitant, inhabitant_id in zip(people, (1, 2, 3)):
            inhabitant.inhabitant_id = inhabitant_id
            inhabitant.faction = None
        people[2].generation = 1
        candidates = {
            ("FOOD", (1, 1), 0.80),
            ("WOOD", (2, 2), 0.70),
            ("ORE", (3, 3), 0.60),
        }
        for meaning_name, phonemes, confidence in candidates:
            meaning = Meaning[meaning_name]
            signal = Signal(phonemes)
            association = LexicalAssociation(
                meaning=meaning,
                signal=signal,
                confidence=confidence,
                origin=AssociationOrigin.INVENTED,
            )
            people[0].language.production[(meaning, signal)] = association
            people[1].language.production[(meaning, signal)] = association
        state = SimulationState(people=people, next_inhabitant_id=4)
        initialize_language_runtime(
            state.language,
            123,
            intergenerational_language_enabled=True,
        )
        initialize_intergenerational_language_runtime(
            state.intergenerational_language,
            transmission,
        )
        transmit_intergenerational_language(
            people[2],
            (people[1], people[0]),
            tick=5,
            language_config=language,
            intergenerational_config=transmission,
            language_runtime=state.language,
            intergenerational_runtime=state.intergenerational_language,
        )
        world = [[{
            "biome": "plains",
            "habitable": True,
            "resources": {
                "food": 1, "wood": 0, "ore": 0, "stone": 0, "water": 0,
            },
        }]]
        configuration = SimulationConfig(
            language_evolution_enabled=True,
            intergenerational_language_enabled=True,
        ).manifest_dict()
        print(json.dumps({
            "hash": canonical_state_hash(state, world, configuration),
            "summary": intergenerational_language_summary(
                iter(people),
                language_config=language,
                intergenerational_config=transmission,
                language_runtime=state.language,
                intergenerational_runtime=state.intergenerational_language,
            ),
        }, sort_keys=True))
        """
    )
    outputs = []
    for seed in ("1", "987654"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        outputs.append(json.loads(completed.stdout))

    assert outputs[0] == outputs[1]


class OneShotPopulation:
    def __init__(self, inhabitants):
        self.inhabitants = tuple(inhabitants)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations != 1:
            raise AssertionError("population iterable was consumed twice")
        return iter(self.inhabitants)


def test_summary_rates_are_none_before_any_committed_transmission():
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()

    summary = intergenerational_language_summary(
        OneShotPopulation((person(1), person(2))),
        language_config=LANGUAGE,
        intergenerational_config=INTERGENERATIONAL,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )

    assert summary["retained_exposure_retention_rate"] is None
    assert summary["usable_exposure_retention_rate"] is None
    assert summary["runtime"]["last_transmission_tick"] is None
    assert summary["runtime"]["last_transmission_child_id"] is None


def test_summary_is_one_pass_bounded_and_insertion_order_independent():
    first, second, child = person(1), person(2), person(3, generation=1)
    shared = Signal((1, 1))
    competing = Signal((2, 1))
    add_production(first, invented(Meaning.FOOD, shared, 0.90))
    add_production(second, invented(Meaning.FOOD, shared, 0.80))
    add_production(first, invented(Meaning.WOOD, shared, 0.70))
    add_production(second, invented(Meaning.WOOD, competing, 0.70))
    language_runtime, intergenerational_runtime, _ = initialized_runtimes()
    transmit(
        child,
        (first, second),
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )
    population = OneShotPopulation((first, second, child))

    first_summary = intergenerational_language_summary(
        population,
        language_config=LANGUAGE,
        intergenerational_config=INTERGENERATIONAL,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )
    child.language.comprehension = dict(reversed(tuple(
        child.language.comprehension.items())))
    second_summary = intergenerational_language_summary(
        OneShotPopulation((child, second, first)),
        language_config=LANGUAGE,
        intergenerational_config=INTERGENERATIONAL,
        language_runtime=language_runtime,
        intergenerational_runtime=intergenerational_runtime,
    )

    assert population.iterations == 1
    assert first_summary == second_summary
    assert first_summary["population_count"] == 3
    assert (
        first_summary[
            "retained_intergenerational_comprehension_carrier_count"
        ]
        == 1
    )
    assert first_summary["retained_parental_source_exposure_count"] == 4
    assert first_summary["retained_exposure_retention_rate"] == 1.0
    assert first_summary["usable_exposure_retention_rate"] == 1.0
    assert first_summary["single_parent_association_count"] == 2
    assert first_summary["dual_parent_association_count"] == 1
    assert (
        first_summary[
            "agent_meaning_slots_with_competing_intergenerational_signals"
        ]
        == 1
    )

    source = inspect.getsource(
        language_module.intergenerational_language_summary)
    tree = ast.parse(source)
    assert all(
        not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sorted"
        )
        for node in ast.walk(tree)
    )
    assert "first_parent_id" not in source
    assert source.count("for inhabitant in people") == 1


def test_malformed_hidden_metadata_fails_hashing_and_reset_without_mutation():
    parent, child = person(1), person(2, generation=1)
    signal = Signal((3, 3))
    child.language.comprehension[(signal, Meaning.FOOD)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=signal,
        confidence=0.30,
        observation_count=1,
        last_used_tick=1,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
        intergenerational_provenance=IntergenerationalProvenance(
            first_transmission_tick=1,
            first_parent_id=1,
            first_parent_signal_origin=AssociationOrigin.INVENTED,
            first_parent_form_was_borrowed=False,
            parent_count=1,
            borrowed_parent_count=0,
        ),
    )
    state = SimulationState(
        people=[child],
        all_dead=[parent],
        next_inhabitant_id=3,
    )
    before_people = tuple(state.people)
    before_dead = tuple(state.all_dead)
    before_child_language = copy.deepcopy(child.language)
    before_runtime = copy.deepcopy(state.intergenerational_language)
    with pytest.raises(
        LanguageInvariantError, match="disabled intergenerational"
    ):
        canonical_state_hash(
            state,
            one_cell_world(),
            SimulationConfig(
                language_evolution_enabled=True,
            ).manifest_dict(),
        )
    assert tuple(state.people) == before_people
    assert tuple(state.all_dead) == before_dead
    assert child.language == before_child_language
    assert state.intergenerational_language == before_runtime

    sim.people.extend((child,))
    sim.all_dead.extend((parent,))
    before_people = tuple(sim.people)
    before_language = copy.deepcopy(child.language)
    with pytest.raises(
        LanguageInvariantError, match="disabled intergenerational"
    ):
        sim.reset_runtime_state()
    assert tuple(sim.people) == before_people
    assert child.language == before_language
    child.language = AgentLanguageState()


def test_disabled_runtime_is_pristine_and_default_hash_payload_is_unchanged():
    state = SimulationState()
    historical = SimulationConfig().manifest_dict()
    explicit = dict(historical)
    for name in (
        "intergenerational_language_enabled",
        "maximum_parental_meanings_per_parent",
        "intergenerational_learning_strength",
        "intergenerational_language_controls_status",
        "intergenerational_language_control_notices",
    ):
        explicit.pop(name)

    assert intergenerational_runtime_is_pristine(
        state.intergenerational_language)
    assert canonical_state_hash(
        state, one_cell_world(), historical
    ) == canonical_state_hash(state, one_cell_world(), explicit)


def test_reset_restores_exact_pristine_intergenerational_runtime():
    first, second, child = person(1), person(2), person(3, generation=1)
    add_production(first, invented(Meaning.FOOD, Signal((6, 6)), 0.80))
    sim.people.extend((child,))
    sim.all_dead.extend((first, second))
    initialize_language_runtime(
        sim.state.language,
        123,
        intergenerational_language_enabled=True,
    )
    initialize_intergenerational_language_runtime(
        sim.state.intergenerational_language,
        INTERGENERATIONAL,
    )
    transmit(
        child,
        (first, second),
        language_runtime=sim.state.language,
        intergenerational_runtime=sim.state.intergenerational_language,
    )

    sim.reset_runtime_state()

    assert sim.people == []
    assert sim.all_dead == []
    assert intergenerational_runtime_is_pristine(
        sim.state.intergenerational_language)


def test_reset_requires_historical_parent_in_complete_cohort_before_mutation():
    first, second, child = person(1), person(2), person(3, generation=1)
    add_production(first, invented(Meaning.FOOD, Signal((6, 5)), 0.80))
    sim.people.append(child)
    sim.all_dead.extend((first, second))
    initialize_language_runtime(
        sim.state.language,
        123,
        intergenerational_language_enabled=True,
    )
    initialize_intergenerational_language_runtime(
        sim.state.intergenerational_language,
        INTERGENERATIONAL,
    )
    transmit(
        child,
        (first, second),
        language_runtime=sim.state.language,
        intergenerational_runtime=sim.state.intergenerational_language,
    )
    sim.all_dead.remove(first)
    before_people = tuple(sim.people)
    before_dead = tuple(sim.all_dead)
    before_language = copy.deepcopy(child.language)
    before_runtime = copy.deepcopy(sim.state.intergenerational_language)

    with pytest.raises(
        LanguageInvariantError, match="complete stable-ID cohort"
    ):
        sim.reset_runtime_state()

    assert tuple(sim.people) == before_people
    assert tuple(sim.all_dead) == before_dead
    assert child.language == before_language
    assert sim.state.intergenerational_language == before_runtime
    sim.all_dead.append(first)
