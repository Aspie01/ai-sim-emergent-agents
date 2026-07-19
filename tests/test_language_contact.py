"""Language Contact v1 acquisition, provenance, transaction, and bound tests."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import random

import pytest

from thalren_vale import economy, language as language_module, sim
from thalren_vale import coalitions as coalitions_module
from thalren_vale.coalitions import (
    CoalitionCommunicationContext,
    CoalitionMembershipSnapshot,
    CoalitionRuntimeState,
    InformalCoalition,
    build_coalition_membership_snapshot,
)
from thalren_vale.config import (
    CoalitionConfig,
    CoalitionDialectConfig,
    LanguageContactConfig,
    LanguageEvolutionConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AssociationOrigin,
    BorrowingProvenance,
    CoalitionDialectRuntimeState,
    CommunicationContext,
    CommunicationResult,
    ContactExposure,
    LanguageContactRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    MAX_LANGUAGE_COUNTER,
    MIN_USABLE_CONFIDENCE,
    Meaning,
    Signal,
    communicate,
    initialize_language_contact_runtime,
    initialize_language_runtime,
    language_contact_summary,
    validate_agent_language_state,
)


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)
CONTACT = LanguageContactConfig(True, 1.50, 3, 0.50)
DIALECT = CoalitionDialectConfig(True, 1.50, 1.25)
COALITIONS = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)


def person(inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(f"P{inhabitant_id}", 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    inhabitant.faction = None
    for resource in economy.RES_TRADE:
        inhabitant.inventory[resource] = 0
    return inhabitant


def invented(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.50,
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


def learned(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.50,
    *,
    source: int = 1,
    successful_uses: int = 0,
    failed_uses: int = 0,
    observations: int = 0,
    tick: int = 0,
    contact_exposure: ContactExposure | None = None,
    borrowing_provenance: BorrowingProvenance | None = None,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        successful_uses=successful_uses,
        failed_uses=failed_uses,
        observation_count=observations,
        last_used_tick=tick,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=source,
        contact_exposure=contact_exposure,
        borrowing_provenance=borrowing_provenance,
    )


def language_runtime(
    *,
    contact: bool,
    dialect: bool = False,
    seed: int = 37,
) -> LanguageRuntimeState:
    state = LanguageRuntimeState()
    initialize_language_runtime(
        state,
        seed,
        coalition_dialect_influence_enabled=dialect,
        language_contact_enabled=contact,
    )
    return state


def contact_runtime() -> LanguageContactRuntimeState:
    state = LanguageContactRuntimeState()
    initialize_language_contact_runtime(state, CONTACT)
    return state


def coalition_runtime(
    groups: tuple[tuple[int, ...], ...],
    *,
    active_ids: tuple[int, ...],
    observation_tick: int,
    reverse_insertion: bool = False,
) -> CoalitionRuntimeState:
    active_coalitions = {
        coalition_id: InformalCoalition(coalition_id, 1, members)
        for coalition_id, members in enumerate(groups)
    }
    member_to_coalition = {
        member_id: coalition_id
        for coalition_id, members in enumerate(groups)
        for member_id in members
    }
    if reverse_insertion:
        active_coalitions = dict(reversed(tuple(active_coalitions.items())))
        member_to_coalition = dict(reversed(tuple(member_to_coalition.items())))
    return CoalitionRuntimeState(
        active_coalitions=active_coalitions,
        member_to_coalition=member_to_coalition,
        next_coalition_id=len(groups),
        candidate_formation_count=len(groups),
        last_observation_tick=observation_tick,
        last_active_inhabitant_ids=tuple(sorted(active_ids)),
    )


def snapshot(
    tick: int,
    *,
    groups: tuple[tuple[int, ...], ...] = ((1, 2, 3), (4, 5, 6)),
    active_ids: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    reverse_insertion: bool = False,
) -> CoalitionMembershipSnapshot:
    state = coalition_runtime(
        groups,
        active_ids=active_ids,
        observation_tick=tick - 1,
        reverse_insertion=reverse_insertion,
    )
    return build_coalition_membership_snapshot(
        state,
        snapshot_tick=tick,
        active_inhabitant_ids=active_ids,
        config=COALITIONS,
    )


def contact_call(
    sender: Inhabitant,
    receiver: Inhabitant,
    language_state: LanguageRuntimeState,
    contact_state: LanguageContactRuntimeState,
    *,
    tick: int,
    frozen: CoalitionMembershipSnapshot | None = None,
    dialect_state: CoalitionDialectRuntimeState | None = None,
):
    if frozen is None:
        frozen = snapshot(tick)
    kwargs = {}
    if dialect_state is not None:
        kwargs.update(dialect_config=DIALECT, dialect_runtime=dialect_state)
    return communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=tick,
        active_ids=frozenset(frozen.active_inhabitant_ids),
        config=LANGUAGE,
        runtime=language_state,
        contact_config=CONTACT,
        contact_runtime=contact_state,
        coalition_membership_snapshot=frozen,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("sender_id", "receiver_id", "expected_context", "qualifies"),
    [
        (1, 4, CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS, True),
        (1, 2, CoalitionCommunicationContext.SAME_ACTIVE_COALITION, False),
        (1, 7, CoalitionCommunicationContext.ASSIGNED_UNASSIGNED, False),
        (7, 8, CoalitionCommunicationContext.BOTH_UNASSIGNED, False),
    ],
)
def test_only_different_active_coalitions_create_contact_exposure(
    sender_id,
    receiver_id,
    expected_context,
    qualifies,
):
    sender, receiver = person(sender_id), person(receiver_id)
    signal = Signal((1, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    frozen = snapshot(
        2,
        active_ids=(1, 2, 3, 4, 5, 6, 7, 8),
    )

    outcome = contact_call(
        sender,
        receiver,
        language_state,
        contact_state,
        tick=2,
        frozen=frozen,
    )

    association = receiver.language.comprehension[(signal, Meaning.FOOD)]
    assert outcome.coalition_context is expected_context
    assert association.confidence == (0.30 if qualifies else 0.20)
    assert (association.contact_exposure is not None) is qualifies
    assert contact_state.cross_coalition_contact_attempt_count == int(qualifies)
    assert contact_state.cross_coalition_unknown_signal_count == int(qualifies)


def test_misunderstanding_records_only_intended_correction_and_promotes_on_success():
    sender, receiver = person(1), person(4)
    signal = Signal((2, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal, 0.80)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD,
        signal,
        0.70,
        source=9,
    )
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()

    first = contact_call(sender, receiver, language_state, contact_state, tick=2)
    second = contact_call(sender, receiver, language_state, contact_state, tick=3)

    assert first.result is second.result is CommunicationResult.MISUNDERSTANDING
    wrong = receiver.language.comprehension[(signal, Meaning.WOOD)]
    correct = receiver.language.comprehension[(signal, Meaning.FOOD)]
    assert wrong.contact_exposure is None
    assert correct.contact_exposure == ContactExposure(
        first_contact_tick=2,
        first_source_speaker_id=1,
        first_source_coalition_id=0,
        exposure_count=2,
        successful_comprehension_count=0,
    )
    assert receiver.language.production == {}

    third = contact_call(sender, receiver, language_state, contact_state, tick=4)

    assert third.result is CommunicationResult.SUCCESS
    correct = receiver.language.comprehension[(signal, Meaning.FOOD)]
    promoted = receiver.language.production[(Meaning.FOOD, signal)]
    assert correct.contact_exposure == ContactExposure(2, 1, 0, 3, 1)
    assert promoted.learned_from_id == 1
    assert promoted.borrowing_provenance == BorrowingProvenance(
        first_contact_tick=2,
        first_source_speaker_id=1,
        first_source_coalition_id=0,
        adoption_tick=4,
        adoption_source_speaker_id=1,
        adoption_source_coalition_id=0,
        exposure_count_at_adoption=3,
        successful_comprehension_count_at_adoption=1,
    )
    assert contact_state.cross_coalition_contact_attempt_count == 3
    assert contact_state.cross_coalition_misunderstanding_count == 2
    assert contact_state.cross_coalition_success_count == 1
    assert contact_state.borrowing_candidate_creation_count == 1
    assert contact_state.borrowing_promotion_count == 1


def test_contact_promotion_waits_for_prelearning_success_outcome():
    sender, receiver = person(1), person(4)
    signal = Signal((2, 7))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal, 0.80)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD,
        signal,
        1.00,
        source=9,
    )
    contact_config = LanguageContactConfig(True, 1.50, 2, 0.50)
    language_state = language_runtime(contact=True)
    contact_state = LanguageContactRuntimeState()
    initialize_language_contact_runtime(contact_state, contact_config)
    frozen = snapshot(2)

    outcomes = []
    for tick in (2, 3, 4):
        outcomes.append(communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=tick,
            active_ids=frozenset(frozen.active_inhabitant_ids),
            config=LANGUAGE,
            runtime=language_state,
            contact_config=contact_config,
            contact_runtime=contact_state,
            coalition_membership_snapshot=(
                frozen if tick == 2 else snapshot(tick)
            ),
        ))
        assert receiver.language.production == {}

    assert [outcome.result for outcome in outcomes] == [
        CommunicationResult.MISUNDERSTANDING,
        CommunicationResult.MISUNDERSTANDING,
        CommunicationResult.MISUNDERSTANDING,
    ]
    success = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=5,
        active_ids=frozenset(frozen.active_inhabitant_ids),
        config=LANGUAGE,
        runtime=language_state,
        contact_config=contact_config,
        contact_runtime=contact_state,
        coalition_membership_snapshot=snapshot(5),
    )

    assert success.result is CommunicationResult.SUCCESS
    assert receiver.language.production[
        (Meaning.FOOD, signal)
    ].borrowing_provenance is not None
    assert contact_state.borrowing_promotion_count == 1


def test_unknown_then_two_successes_is_distinct_from_generic_promotion():
    sender, receiver = person(1), person(4)
    signal = Signal((3, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()

    outcomes = [
        contact_call(sender, receiver, language_state, contact_state, tick=tick)
        for tick in (2, 3, 4)
    ]

    assert [outcome.result for outcome in outcomes] == [
        CommunicationResult.UNKNOWN_SIGNAL,
        CommunicationResult.SUCCESS,
        CommunicationResult.SUCCESS,
    ]
    comprehension = receiver.language.comprehension[(signal, Meaning.FOOD)]
    production = receiver.language.production[(Meaning.FOOD, signal)]
    assert comprehension.confidence == 0.50
    assert comprehension.successful_uses == 2
    assert comprehension.contact_exposure == ContactExposure(2, 1, 0, 3, 2)
    assert comprehension.contact_exposure.exposure_count <= (
        comprehension.observation_count
    )
    assert comprehension.contact_exposure.successful_comprehension_count <= (
        comprehension.successful_uses
    )
    assert production.borrowing_provenance is not None
    assert contact_state.borrowing_promotion_count == 1

    provenance = production.borrowing_provenance
    first_contact_facts = (
        comprehension.contact_exposure.first_contact_tick,
        comprehension.contact_exposure.first_source_speaker_id,
        comprehension.contact_exposure.first_source_coalition_id,
    )
    contact_call(sender, receiver, language_state, contact_state, tick=5)
    assert contact_state.borrowing_promotion_count == 1
    assert (
        receiver.language.production[(Meaning.FOOD, signal)].borrowing_provenance
        == provenance
    )
    later_exposure = receiver.language.comprehension[
        (signal, Meaning.FOOD)
    ].contact_exposure
    assert later_exposure is not None
    assert (
        later_exposure.first_contact_tick,
        later_exposure.first_source_speaker_id,
        later_exposure.first_source_coalition_id,
    ) == first_contact_facts


def test_contact_precedes_generic_promotion_exactly_once_when_both_qualify():
    sender, receiver = person(1), person(4)
    signal = Signal((4, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD,
        signal,
        0.50,
        successful_uses=2,
        observations=2,
        tick=1,
        contact_exposure=ContactExposure(0, 1, 0, 2, 2),
    )
    language_state = language_runtime(contact=True)
    language_state.communication_attempt_count = 2
    language_state.successful_interpretation_count = 2
    language_state.last_communication_tick = 1
    contact_state = contact_runtime()
    contact_state.cross_coalition_contact_attempt_count = 2
    contact_state.cross_coalition_success_count = 2
    contact_state.borrowing_candidate_creation_count = 1
    contact_state.last_contact_tick = 1

    outcome = contact_call(sender, receiver, language_state, contact_state, tick=2)

    assert outcome.result is CommunicationResult.SUCCESS
    promoted = receiver.language.production[(Meaning.FOOD, signal)]
    assert promoted.borrowing_provenance is not None
    assert receiver.language.comprehension[(signal, Meaning.FOOD)].successful_uses == 3
    assert contact_state.borrowing_promotion_count == 1
    assert language_state.learned_association_count == 1


def test_existing_exact_production_is_never_relabelled_as_borrowed():
    sender, receiver = person(1), person(4)
    signal = Signal((5, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD,
        signal,
        0.50,
        successful_uses=2,
        observations=2,
        tick=1,
        contact_exposure=ContactExposure(0, 1, 0, 2, 2),
    )
    receiver.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal, 0.60, tick=1)
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()

    contact_call(sender, receiver, language_state, contact_state, tick=2)

    existing = receiver.language.production[(Meaning.FOOD, signal)]
    assert existing.origin is AssociationOrigin.INVENTED
    assert existing.borrowing_provenance is None
    assert contact_state.borrowing_promotion_count == 0


@pytest.mark.parametrize(
    "association",
    [
        learned(
            Meaning.FOOD,
            Signal((6, 0)),
            successful_uses=1,
            observations=1,
            tick=2,
            contact_exposure=ContactExposure(2, 1, 0, 1, 2),
        ),
        learned(
            Meaning.FOOD,
            Signal((6, 1)),
            observations=1,
            tick=2,
            contact_exposure=ContactExposure(3, 1, 0, 1, 0),
        ),
        learned(
            Meaning.FOOD,
            Signal((6, 7)),
            observations=1,
            tick=2,
            contact_exposure=ContactExposure(1, 1, 0, 2, 0),
        ),
        learned(
            Meaning.FOOD,
            Signal((5, 0)),
            observations=1,
            tick=2,
            contact_exposure=ContactExposure(1, True, 0, 1, 0),
        ),
        learned(
            Meaning.FOOD,
            Signal((5, 1)),
            observations=1,
            tick=2,
            contact_exposure=ContactExposure(1, 1, -1, 1, 0),
        ),
        learned(
            Meaning.FOOD,
            Signal((6, 2)),
            observations=1,
            tick=2,
            borrowing_provenance=BorrowingProvenance(
                2, 1, 0, 1, 1, 0, 3, 1),
        ),
        learned(
            Meaning.FOOD,
            Signal((6, 3)),
            observations=1,
            tick=2,
            borrowing_provenance=BorrowingProvenance(
                1, 1, 0, 2, 1, 0, 2, 1),
        ),
        learned(
            Meaning.FOOD,
            Signal((5, 2)),
            observations=1,
            tick=2,
            borrowing_provenance=BorrowingProvenance(
                1, 1, 0, 3, 1, 0, 3, 1),
        ),
        learned(
            Meaning.FOOD,
            Signal((5, 3)),
            observations=1,
            tick=2,
            borrowing_provenance=BorrowingProvenance(
                1, 1, 0, 2, 1, 0, 3, 4),
        ),
        LexicalAssociation(
            meaning=Meaning.FOOD,
            signal=Signal((5, 4)),
            confidence=0.50,
            observation_count=1,
            last_used_tick=2,
            origin=AssociationOrigin.INVENTED,
            borrowing_provenance=BorrowingProvenance(
                1, 1, 0, 2, 1, 0, 3, 1),
        ),
    ],
)
def test_contact_metadata_subset_and_tick_invariants_fail_closed(association):
    state = person(4).language
    if association.contact_exposure is not None:
        state.comprehension[(association.signal, association.meaning)] = association
    else:
        state.production[(association.meaning, association.signal)] = association

    with pytest.raises(LanguageInvariantError):
        validate_agent_language_state(
            state,
            config=LANGUAGE,
            contact_config=CONTACT,
        )


def test_historical_source_coalition_ids_need_not_remain_active():
    signal = Signal((5, 5))
    borrowed_signal = Signal((5, 6))
    state = person(4).language
    state.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD,
        signal,
        successful_uses=1,
        observations=1,
        tick=2,
        contact_exposure=ContactExposure(1, 1, 999, 1, 1),
    )
    state.production[(Meaning.FOOD, borrowed_signal)] = learned(
        Meaning.FOOD,
        borrowed_signal,
        observations=1,
        tick=2,
        borrowing_provenance=BorrowingProvenance(
            1, 1, 999, 2, 1, 999, 3, 1),
    )

    assert validate_agent_language_state(
        state,
        config=LANGUAGE,
        contact_config=CONTACT,
    ) is state


def test_attempt_saturation_freezes_partition_but_advances_contact_tick():
    sender, receiver = person(1), person(4)
    signal = Signal((6, 4))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    language_state = language_runtime(contact=True)
    language_state.communication_attempt_count = MAX_LANGUAGE_COUNTER
    language_state.unknown_signal_count = MAX_LANGUAGE_COUNTER
    language_state.last_communication_tick = 1
    contact_state = contact_runtime()
    contact_state.cross_coalition_contact_attempt_count = MAX_LANGUAGE_COUNTER
    contact_state.cross_coalition_unknown_signal_count = MAX_LANGUAGE_COUNTER
    contact_state.last_contact_tick = 1

    outcome = contact_call(sender, receiver, language_state, contact_state, tick=2)

    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert language_state.communication_attempt_count == MAX_LANGUAGE_COUNTER
    assert language_state.unknown_signal_count == MAX_LANGUAGE_COUNTER
    assert contact_state.cross_coalition_contact_attempt_count == MAX_LANGUAGE_COUNTER
    assert contact_state.cross_coalition_unknown_signal_count == MAX_LANGUAGE_COUNTER
    assert language_state.last_communication_tick == 2
    assert contact_state.last_contact_tick == 2


def test_enabled_inputs_are_mandatory_and_disabled_path_enters_no_contact_helper(
    monkeypatch,
):
    sender, receiver = person(1), person(4)
    signal = Signal((6, 5))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    enabled_runtime = language_runtime(contact=True)
    before = copy.deepcopy((sender.language, receiver.language, enabled_runtime))

    with pytest.raises(LanguageInvariantError):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 4}),
            config=LANGUAGE,
            runtime=enabled_runtime,
        )
    assert (sender.language, receiver.language, enabled_runtime) == before

    disabled_sender, disabled_receiver = person(1), person(4)
    disabled_sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    disabled_runtime = language_runtime(contact=False)
    supplied_contact_runtime = contact_runtime()

    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("disabled language entered coalition classification")

    monkeypatch.setattr(
        language_module,
        "classify_coalition_communication",
        forbidden,
    )
    for helper_name in (
        "_communicate_with_contact",
        "_record_contact_exposure",
        "_record_contact_outcome",
        "_effective_contact_rate",
        "validate_language_contact_config",
        "validate_language_contact_runtime",
    ):
        monkeypatch.setattr(language_module, helper_name, forbidden)
    outcome = communicate(
        disabled_sender,
        disabled_receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset({1, 4}),
        config=LANGUAGE,
        runtime=disabled_runtime,
    )
    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL

    with pytest.raises(LanguageInvariantError):
        communicate(
            person(1),
            person(4),
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 2, 3, 4, 5, 6}),
            config=LANGUAGE,
            runtime=language_runtime(contact=False),
            contact_config=CONTACT,
            contact_runtime=supplied_contact_runtime,
            coalition_membership_snapshot=snapshot(2),
        )


@pytest.mark.parametrize(
    "invalid_input",
    [
        "missing_config",
        "disabled_config",
        "wrong_config_type",
        "wrong_runtime_type",
        "partial_runtime",
        "mismatched_runtime",
        "missing_snapshot",
        "wrong_snapshot_type",
        "stale_snapshot",
        "forged_snapshot",
    ],
)
def test_contact_enabled_inputs_fail_closed_before_proposal_mutation(invalid_input):
    sender, receiver = person(1), person(4)
    signal = Signal((6, 5))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    kwargs = {
        "contact_config": CONTACT,
        "contact_runtime": contact_state,
        "coalition_membership_snapshot": snapshot(2),
    }
    if invalid_input == "missing_config":
        kwargs["contact_config"] = None
    elif invalid_input == "disabled_config":
        kwargs["contact_config"] = replace(
            CONTACT, language_contact_enabled=False)
    elif invalid_input == "wrong_config_type":
        kwargs["contact_config"] = object()
    elif invalid_input == "wrong_runtime_type":
        kwargs["contact_runtime"] = object()
    elif invalid_input == "partial_runtime":
        contact_state.borrowing_exposure_threshold = None
    elif invalid_input == "mismatched_runtime":
        contact_state.cross_group_learning_multiplier = 1.75
    elif invalid_input == "missing_snapshot":
        kwargs["coalition_membership_snapshot"] = None
    elif invalid_input == "wrong_snapshot_type":
        kwargs["coalition_membership_snapshot"] = object()
    elif invalid_input == "stale_snapshot":
        kwargs["coalition_membership_snapshot"] = snapshot(3)
    else:
        forged = snapshot(2)
        object.__setattr__(forged, "_factory_token", object())
        kwargs["coalition_membership_snapshot"] = forged
    before = copy.deepcopy((
        sender.language,
        receiver.language,
        language_state,
        contact_state,
    ))

    with pytest.raises((LanguageInvariantError, ValueError)):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 2, 3, 4, 5, 6}),
            config=LANGUAGE,
            runtime=language_state,
            **kwargs,
        )

    assert (
        sender.language,
        receiver.language,
        language_state,
        contact_state,
    ) == before


def test_dialect_and_contact_share_one_classification(monkeypatch):
    sender, receiver = person(1), person(4)
    signal = Signal((6, 6))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    language_state = language_runtime(contact=True, dialect=True)
    contact_state = contact_runtime()
    dialect_state = CoalitionDialectRuntimeState()
    classifications = 0
    snapshot_validations = 0
    real_classify = language_module.classify_coalition_communication
    real_snapshot_validation = (
        coalitions_module.validate_coalition_membership_snapshot
    )

    def counted(*args, **kwargs):
        nonlocal classifications
        classifications += 1
        return real_classify(*args, **kwargs)

    def counted_snapshot_validation(*args, **kwargs):
        nonlocal snapshot_validations
        snapshot_validations += 1
        return real_snapshot_validation(*args, **kwargs)

    monkeypatch.setattr(
        language_module,
        "classify_coalition_communication",
        counted,
    )
    monkeypatch.setattr(
        coalitions_module,
        "validate_coalition_membership_snapshot",
        counted_snapshot_validation,
    )
    outcome = contact_call(
        sender,
        receiver,
        language_state,
        contact_state,
        tick=2,
        dialect_state=dialect_state,
    )

    assert classifications == 1
    assert snapshot_validations == 1
    assert outcome.coalition_context is (
        CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS)
    assert dialect_state.different_coalition_communication_count == 1
    assert dialect_state.same_coalition_rate_application_count == 0
    assert contact_state.cross_coalition_contact_attempt_count == 1
    assert receiver.language.comprehension[(signal, Meaning.FOOD)].confidence == 0.30


def test_contact_only_builds_one_snapshot_for_the_complete_economy_pass(
    monkeypatch,
):
    people = [person(index) for index in range(1, 5)]
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    monkeypatch.setattr(sim, "people", people)
    monkeypatch.setattr(sim, "factions", [])
    monkeypatch.setattr(sim.state, "coalitions", CoalitionRuntimeState())
    monkeypatch.setattr(sim.state, "language", language_state)
    monkeypatch.setattr(sim.state, "language_contact", contact_state)
    build_calls = 0
    observed_snapshot = None
    real_builder = sim.build_coalition_membership_snapshot

    def counted_builder(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return real_builder(*args, **kwargs)

    def inspect_economy(*args, **kwargs):
        nonlocal observed_snapshot
        del args
        observed_snapshot = kwargs["coalition_membership_snapshot"]
        assert kwargs["contact_config"] is CONTACT
        assert kwargs["contact_runtime"] is contact_state
        assert kwargs["dialect_config"] is None
        assert kwargs["dialect_runtime"] is None

    monkeypatch.setattr(sim, "build_coalition_membership_snapshot", counted_builder)
    monkeypatch.setattr(economy, "economy_tick", inspect_economy)

    sim.economy_layer(
        1,
        SocialMemoryConfig(True, False, 32, 25),
        LANGUAGE,
        CoalitionDialectConfig(False, 1.50, 1.25),
        COALITIONS,
        CONTACT,
    )

    assert build_calls == 1
    assert observed_snapshot is not None


def test_late_contact_failure_rolls_back_every_owner_and_external_state(monkeypatch):
    sender, receiver = person(1), person(4)
    sender.inventory["food"] = 7
    sender.currency = 9
    sender.relationships[4] = {"sentinel": True}
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    frozen = snapshot(2)
    coalition_state = coalition_runtime(
        ((1, 2, 3), (4, 5, 6)),
        active_ids=(1, 2, 3, 4, 5, 6),
        observation_tick=1,
    )
    before = copy.deepcopy((
        sender.language,
        receiver.language,
        language_state,
        contact_state,
        sender.inventory,
        sender.currency,
        sender.relationships,
        coalition_state,
    ))
    rng_before = random.getstate()
    population = [sender, receiver]

    def fail_retention(*args, **kwargs):
        del args, kwargs
        raise LanguageInvariantError("injected_contact_failure", "late failure")

    monkeypatch.setattr(language_module, "_retain_canonical", fail_retention)
    with pytest.raises(LanguageInvariantError, match="late failure"):
        contact_call(
            sender,
            receiver,
            language_state,
            contact_state,
            tick=2,
            frozen=frozen,
        )

    assert (
        sender.language,
        receiver.language,
        language_state,
        contact_state,
        sender.inventory,
        sender.currency,
        sender.relationships,
        coalition_state,
    ) == before
    assert sender.language.next_invention_index == 0
    assert population == [sender, receiver]
    assert random.getstate() == rng_before


def test_transfer_precedes_language_transaction_and_is_not_rolled_back(
    monkeypatch,
):
    giver, recipient = person(1), person(4)
    giver.inventory["food"] = 3
    recipient.inventory["food"] = 0
    giver.faction = "A"
    recipient.faction = "B"
    population = [giver, recipient]
    coalition_state = coalition_runtime(
        ((1, 2, 3), (4, 5, 6)),
        active_ids=(1, 2, 3, 4, 5, 6),
        observation_tick=1,
    )
    frozen = build_coalition_membership_snapshot(
        coalition_state,
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
        config=COALITIONS,
    )
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    language_before = copy.deepcopy((
        giver.language,
        recipient.language,
        language_state,
        contact_state,
    ))
    communication_entry = None
    rng_at_entry = None
    real_communicate = economy.communicate

    def capture_communication_entry(*args, **kwargs):
        nonlocal communication_entry, rng_at_entry
        communication_entry = (
            copy.deepcopy(giver.relationships),
            copy.deepcopy(recipient.relationships),
            giver.faction,
            recipient.faction,
            tuple(population),
            copy.deepcopy(coalition_state),
        )
        rng_at_entry = random.getstate()
        return real_communicate(*args, **kwargs)

    def fail_retention(*args, **kwargs):
        del args, kwargs
        raise LanguageInvariantError("injected_contact_failure", "late failure")

    monkeypatch.setattr(economy, "communicate", capture_communication_entry)
    monkeypatch.setattr(language_module, "_retain_canonical", fail_retention)

    with pytest.raises(LanguageInvariantError, match="late failure"):
        economy._commit_individual_transfer(
            giver,
            recipient,
            "food",
            t=2,
            social_config=SocialMemoryConfig(False, False, 32, 25),
            language_config=LANGUAGE,
            language_runtime=language_state,
            contact_config=CONTACT,
            contact_runtime=contact_state,
            coalition_membership_snapshot=frozen,
            active_ids=frozenset({1, 2, 3, 4, 5, 6}),
        )

    assert giver.inventory["food"] == 2
    assert recipient.inventory["food"] == 1
    assert (
        giver.language,
        recipient.language,
        language_state,
        contact_state,
    ) == language_before
    assert communication_entry is not None
    assert (
        giver.relationships,
        recipient.relationships,
        giver.faction,
        recipient.faction,
        tuple(population),
        coalition_state,
    ) == communication_entry
    assert random.getstate() == rng_at_entry


class SummaryInhabitantSpy:
    """Count stable-ID reads and reject inhabitant comparisons."""

    def __init__(self, inhabitant: Inhabitant) -> None:
        self._inhabitant_id = inhabitant.inhabitant_id
        self.language = inhabitant.language
        self.inhabitant_id_read_count = 0

    @property
    def inhabitant_id(self) -> int:
        self.inhabitant_id_read_count += 1
        return self._inhabitant_id

    def __lt__(self, other: object) -> bool:
        del other
        raise AssertionError("contact summary compared inhabitants globally")


class OneShotPopulation:
    """Require aggregation during one and only one population iteration."""

    def __init__(self, inhabitants: list[SummaryInhabitantSpy]) -> None:
        self._inhabitants = inhabitants
        self.iteration_count = 0
        self.yield_count = 0

    def __iter__(self):
        self.iteration_count += 1
        if self.iteration_count != 1:
            raise AssertionError("population iterable was entered more than once")
        for inhabitant in self._inhabitants:
            reads_before = inhabitant.inhabitant_id_read_count
            self.yield_count += 1
            yield inhabitant
            if inhabitant.inhabitant_id_read_count != reads_before + 1:
                raise AssertionError(
                    "population was materialized instead of aggregated linearly")


def borrowed_population(count: int) -> list[Inhabitant]:
    people = [person(index) for index in range(1, count + 1)]
    half = count // 2
    for inhabitant in people:
        inhabitant_id = inhabitant.inhabitant_id
        assert inhabitant_id is not None
        signal = Signal(((inhabitant_id - 1) // 8, (inhabitant_id - 1) % 8))
        source_id = half + 1 if inhabitant_id <= half else 1
        source_coalition_id = 1 if inhabitant_id <= half else 0
        provenance = BorrowingProvenance(
            first_contact_tick=1,
            first_source_speaker_id=source_id,
            first_source_coalition_id=source_coalition_id,
            adoption_tick=2,
            adoption_source_speaker_id=source_id,
            adoption_source_coalition_id=source_coalition_id,
            exposure_count_at_adoption=3,
            successful_comprehension_count_at_adoption=2,
        )
        inhabitant.language.production[(Meaning.FOOD, signal)] = learned(
            Meaning.FOOD,
            signal,
            0.60,
            source=source_id,
            observations=1,
            tick=2,
            borrowing_provenance=provenance,
        )
        local_signal = Signal((7, inhabitant_id % 8))
        inhabitant.language.production[(Meaning.FOOD, local_signal)] = invented(
            Meaning.FOOD,
            local_signal,
            0.40,
            tick=2,
        )
        inhabitant.language.comprehension[(signal, Meaning.FOOD)] = learned(
            Meaning.FOOD,
            signal,
            0.60,
            source=source_id,
            successful_uses=2,
            observations=3,
            tick=2,
            contact_exposure=ContactExposure(
                1,
                source_id,
                source_coalition_id,
                3,
                2,
            ),
        )
    return people


def summary_snapshot(count: int, *, reverse_insertion: bool = False):
    half = count // 2
    groups = (
        tuple(range(1, half + 1)),
        tuple(range(half + 1, count + 1)),
    )
    return snapshot(
        2,
        groups=groups,
        active_ids=tuple(range(1, count + 1)),
        reverse_insertion=reverse_insertion,
    )


def render_contact_summary(people, frozen) -> str:
    summary = summarize_contact(people, frozen)
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))


def summarize_contact(
    people,
    frozen,
    *,
    language_state: LanguageRuntimeState | None = None,
    contact_state: LanguageContactRuntimeState | None = None,
):
    return language_contact_summary(
        people,
        snapshot=frozen,
        language_config=LANGUAGE,
        contact_config=CONTACT,
        language_runtime=(
            language_runtime(contact=True)
            if language_state is None else language_state
        ),
        contact_runtime=(
            contact_runtime() if contact_state is None else contact_state
        ),
    )


def borrowed_association(
    meaning: Meaning,
    signal: Signal,
    *,
    source_coalition_id: int,
    source_id: int = 99,
    confidence: float = 0.60,
) -> LexicalAssociation:
    return learned(
        meaning,
        signal,
        confidence,
        source=source_id,
        observations=1,
        tick=2,
        borrowing_provenance=BorrowingProvenance(
            first_contact_tick=1,
            first_source_speaker_id=source_id,
            first_source_coalition_id=source_coalition_id,
            adoption_tick=2,
            adoption_source_speaker_id=source_id,
            adoption_source_coalition_id=source_coalition_id,
            exposure_count_at_adoption=3,
            successful_comprehension_count_at_adoption=1,
        ),
    )


def meaning_frequency_record(summary, field_name: str, meaning: Meaning):
    return next(
        record
        for record in summary["totals"][field_name]
        if record["meaning"] == meaning.name
    )


def lexical_distance_record(summary, meaning: Meaning):
    return next(
        record
        for record in summary["between_coalitions"]
        if record["meaning"] == meaning.name
    )


def test_contact_summary_is_one_pass_order_independent_and_state_isolated():
    people = borrowed_population(6)
    frozen = summary_snapshot(6)
    spies = [SummaryInhabitantSpy(inhabitant) for inhabitant in people]
    one_shot = OneShotPopulation(spies)
    before_people = copy.deepcopy([inhabitant.language for inhabitant in people])
    rng_before = random.getstate()

    one_shot_result = render_contact_summary(one_shot, frozen)

    assert one_shot.iteration_count == 1
    assert one_shot.yield_count == len(people)
    assert all(spy.inhabitant_id_read_count == 1 for spy in spies)
    assert [inhabitant.language for inhabitant in people] == before_people
    assert random.getstate() == rng_before

    variants = [
        list(people),
        list(reversed(people)),
        people[::2] + people[1::2],
        people[2:] + people[:2],
    ]
    for variant in variants:
        for inhabitant in variant:
            inhabitant.language.production = dict(reversed(
                tuple(inhabitant.language.production.items())))
            inhabitant.language.comprehension = dict(reversed(
                tuple(inhabitant.language.comprehension.items())))
        assert render_contact_summary(
            variant,
            summary_snapshot(6, reverse_insertion=True),
        ) == one_shot_result


def test_contact_summary_rejects_malformed_metadata_without_mutation():
    people = borrowed_population(6)
    association_key, association = next(iter(
        people[0].language.comprehension.items()))
    assert association.contact_exposure is not None
    people[0].language.comprehension[association_key] = replace(
        association,
        contact_exposure=replace(
            association.contact_exposure,
            exposure_count=association.observation_count + 1,
        ),
    )
    language_state = language_runtime(contact=True)
    contact_state = contact_runtime()
    before = copy.deepcopy((
        [inhabitant.language for inhabitant in people],
        language_state,
        contact_state,
    ))

    with pytest.raises(LanguageInvariantError, match="exposures exceed"):
        language_contact_summary(
            iter(people),
            snapshot=summary_snapshot(6),
            language_config=LANGUAGE,
            contact_config=CONTACT,
            language_runtime=language_state,
            contact_runtime=contact_state,
        )

    assert (
        [inhabitant.language for inhabitant in people],
        language_state,
        contact_state,
    ) == before


def test_contact_summary_association_work_scales_with_population(monkeypatch):
    real_validate = language_module._validate_association
    real_validate_state = language_module.validate_agent_language_state

    def validation_count(count: int) -> tuple[int, int]:
        association_calls = 0
        state_calls = 0

        def counted(*args, **kwargs):
            nonlocal association_calls
            association_calls += 1
            return real_validate(*args, **kwargs)

        def counted_state(*args, **kwargs):
            nonlocal state_calls
            state_calls += 1
            return real_validate_state(*args, **kwargs)

        monkeypatch.setattr(language_module, "_validate_association", counted)
        monkeypatch.setattr(
            language_module,
            "validate_agent_language_state",
            counted_state,
        )
        render_contact_summary(
            borrowed_population(count),
            summary_snapshot(count),
        )
        monkeypatch.setattr(
            language_module,
            "_validate_association",
            real_validate,
        )
        monkeypatch.setattr(
            language_module,
            "validate_agent_language_state",
            real_validate_state,
        )
        return state_calls, association_calls

    small = validation_count(6)
    large = validation_count(18)

    assert small == (6, 18)
    assert large == (18, 54)


def test_contact_summary_excludes_below_threshold_borrowing_everywhere():
    assert MIN_USABLE_CONFIDENCE == 0.10
    people = borrowed_population(6)
    borrowed_key, borrowed = next(
        (key, association)
        for key, association in people[0].language.production.items()
        if association.borrowing_provenance is not None
    )
    people[0].language.production[borrowed_key] = replace(
        borrowed,
        confidence=0.05,
    )

    summary = summarize_contact(people, summary_snapshot(6))
    totals = summary["totals"]
    food_frequencies = meaning_frequency_record(
        summary,
        "selected_borrowed_signal_frequencies",
        Meaning.FOOD,
    )

    assert totals["usable_production_association_count"] == 11
    assert totals["usable_borrowed_production_association_count"] == 5
    assert totals["borrowed_production_count"] == 5
    assert totals["borrowed_production_carrier_count"] == 5
    assert totals["mixed_production_carrier_count"] == 5
    assert totals["borrowed_association_share"] == 0.454545
    assert sum(item["count"] for item in food_frequencies["signals"]) == 5
    assert borrowed.signal.phoneme_ids not in {
        tuple(item["signal"]) for item in food_frequencies["signals"]
    }


def test_contact_summary_carriers_mixing_share_and_source_diversity():
    people = [person(index) for index in range(1, 7)]
    borrowed_only = Signal((0, 1))
    local_only = Signal((0, 2))
    mixed_borrowed = Signal((0, 3))
    mixed_local = Signal((0, 4))
    different_borrowed = Signal((0, 5))
    different_local = Signal((0, 6))
    unusable_borrowed = Signal((0, 7))

    people[0].language.production[(Meaning.FOOD, borrowed_only)] = (
        borrowed_association(
            Meaning.FOOD,
            borrowed_only,
            source_coalition_id=90,
        )
    )
    people[1].language.production[(Meaning.FOOD, local_only)] = invented(
        Meaning.FOOD, local_only, 0.60, tick=2)
    people[2].language.production[(Meaning.FOOD, mixed_borrowed)] = (
        borrowed_association(
            Meaning.FOOD,
            mixed_borrowed,
            source_coalition_id=90,
        )
    )
    people[2].language.production[(Meaning.FOOD, mixed_local)] = invented(
        Meaning.FOOD, mixed_local, 0.50, tick=2)
    people[3].language.production[(Meaning.FOOD, different_borrowed)] = (
        borrowed_association(
            Meaning.FOOD,
            different_borrowed,
            source_coalition_id=91,
        )
    )
    people[3].language.production[(Meaning.WOOD, different_local)] = invented(
        Meaning.WOOD, different_local, 0.70, tick=2)
    people[4].language.production[(Meaning.FOOD, unusable_borrowed)] = (
        borrowed_association(
            Meaning.FOOD,
            unusable_borrowed,
            source_coalition_id=92,
            confidence=0.05,
        )
    )
    people[4].language.production[(Meaning.FOOD, local_only)] = invented(
        Meaning.FOOD, local_only, 0.40, tick=2)

    summary = summarize_contact(people, summary_snapshot(6))
    totals = summary["totals"]

    assert totals["usable_production_association_count"] == 7
    assert totals["usable_borrowed_production_association_count"] == 3
    assert totals["borrowed_production_carrier_count"] == 3
    assert totals["mixed_production_carrier_count"] == 1
    assert totals["borrowed_association_share"] == 0.428571
    assert summary["source_coalition_diversity_count"] == 2
    assert {90, 91}.isdisjoint(summary_snapshot(6).active_coalition_ids)


def test_contact_summary_zero_usable_production_has_no_borrowed_share():
    people = [person(index) for index in range(1, 7)]
    summary = summarize_contact(people, summary_snapshot(6))

    assert summary["totals"]["usable_production_association_count"] == 0
    assert summary["totals"]["borrowed_association_share"] is None


def test_contact_summary_counts_only_selected_borrowed_signals_canonically():
    people = [person(index) for index in range(1, 7)]
    weak_borrowed = Signal((1, 1))
    strong_local = Signal((1, 2))
    strong_borrowed = Signal((1, 3))
    weak_local = Signal((1, 4))
    tie_borrowed_first = Signal((1, 5))
    tie_local_later = Signal((1, 6))
    tie_local_first = Signal((2, 0))
    tie_borrowed_later = Signal((2, 1))

    people[0].language.production[(Meaning.FOOD, weak_borrowed)] = (
        borrowed_association(
            Meaning.FOOD, weak_borrowed, source_coalition_id=80)
    )
    people[0].language.production[(Meaning.FOOD, strong_local)] = invented(
        Meaning.FOOD, strong_local, 0.80, tick=2)
    people[1].language.production[(Meaning.FOOD, strong_borrowed)] = (
        borrowed_association(
            Meaning.FOOD,
            strong_borrowed,
            source_coalition_id=81,
            confidence=0.90,
        )
    )
    people[1].language.production[(Meaning.FOOD, weak_local)] = invented(
        Meaning.FOOD, weak_local, 0.80, tick=2)
    people[2].language.production[(Meaning.FOOD, tie_borrowed_first)] = (
        borrowed_association(
            Meaning.FOOD,
            tie_borrowed_first,
            source_coalition_id=82,
        )
    )
    people[2].language.production[(Meaning.FOOD, tie_local_later)] = invented(
        Meaning.FOOD, tie_local_later, 0.60, tick=2)
    people[3].language.production[(Meaning.FOOD, tie_local_first)] = invented(
        Meaning.FOOD, tie_local_first, 0.60, tick=2)
    people[3].language.production[(Meaning.FOOD, tie_borrowed_later)] = (
        borrowed_association(
            Meaning.FOOD,
            tie_borrowed_later,
            source_coalition_id=83,
        )
    )

    summary = summarize_contact(people, summary_snapshot(6))
    frequencies = meaning_frequency_record(
        summary,
        "selected_borrowed_signal_frequencies",
        Meaning.FOOD,
    )["signals"]

    assert frequencies == [
        {"signal": list(strong_borrowed.phoneme_ids), "count": 1},
        {"signal": list(tie_borrowed_first.phoneme_ids), "count": 1},
    ]
    assert summary["totals"]["borrowed_production_carrier_count"] == 4

    people[0].language.production[(Meaning.FOOD, weak_borrowed)] = replace(
        people[0].language.production[(Meaning.FOOD, weak_borrowed)],
        confidence=0.90,
    )
    promoted_frequencies = meaning_frequency_record(
        summarize_contact(people, summary_snapshot(6)),
        "selected_borrowed_signal_frequencies",
        Meaning.FOOD,
    )["signals"]
    assert promoted_frequencies == [
        {"signal": list(weak_borrowed.phoneme_ids), "count": 1},
        {"signal": list(strong_borrowed.phoneme_ids), "count": 1},
        {"signal": list(tie_borrowed_first.phoneme_ids), "count": 1},
    ]


def test_contact_summary_success_rate_excludes_no_signal_and_validates_partition():
    people = [person(index) for index in range(1, 7)]
    language_state = language_runtime(contact=True)
    language_state.communication_attempt_count = 10
    language_state.successful_interpretation_count = 2
    language_state.misunderstanding_count = 3
    language_state.unknown_signal_count = 1
    language_state.no_signal_count = 4
    language_state.last_communication_tick = 2
    contact_state = contact_runtime()
    contact_state.cross_coalition_contact_attempt_count = 10
    contact_state.cross_coalition_success_count = 2
    contact_state.cross_coalition_misunderstanding_count = 3
    contact_state.cross_coalition_unknown_signal_count = 1
    contact_state.cross_coalition_no_signal_count = 4
    contact_state.last_contact_tick = 2

    summary = summarize_contact(
        people,
        summary_snapshot(6),
        language_state=language_state,
        contact_state=contact_state,
    )

    assert summary["cross_coalition_comprehension_success_rate"] == 0.333333
    assert summarize_contact(
        people,
        summary_snapshot(6),
    )["cross_coalition_comprehension_success_rate"] is None

    contact_state.cross_coalition_contact_attempt_count = 9
    with pytest.raises(LanguageInvariantError, match="partition"):
        summarize_contact(
            people,
            summary_snapshot(6),
            language_state=language_state,
            contact_state=contact_state,
        )


@pytest.mark.parametrize(
    ("signals", "expected_distance"),
    [
        (((3, 0),) * 6, 0.0),
        (((3, 0),) * 3 + ((3, 1),) * 3, 1.0),
        (((3, 0), (3, 0), (3, 1), (3, 0), (3, 1), (3, 1)), 0.555556),
    ],
)
def test_contact_summary_between_coalition_lexical_distance(
    signals,
    expected_distance,
):
    people = [person(index) for index in range(1, 7)]
    for inhabitant, phoneme_ids in zip(people, signals, strict=True):
        signal = Signal(phoneme_ids)
        inhabitant.language.production[(Meaning.FOOD, signal)] = invented(
            Meaning.FOOD, signal, 0.60, tick=2)

    summary = summarize_contact(people, summary_snapshot(6))
    record = lexical_distance_record(summary, Meaning.FOOD)

    assert record == {
        "meaning": "FOOD",
        "eligible_coalition_count": 2,
        "selected_speaker_count": 6,
        "lexical_distance": expected_distance,
    }
    assert summary["mean_between_coalition_lexical_distance"] == (
        expected_distance
    )


def test_contact_summary_lexical_distance_excludes_unusable_production():
    people = [person(index) for index in range(1, 7)]
    for index, inhabitant in enumerate(people):
        signal = Signal((4, index % 3))
        confidence = 0.60 if index < 3 else 0.05
        inhabitant.language.production[(Meaning.FOOD, signal)] = invented(
            Meaning.FOOD, signal, confidence, tick=2)

    summary = summarize_contact(people, summary_snapshot(6))

    assert lexical_distance_record(summary, Meaning.FOOD) == {
        "meaning": "FOOD",
        "eligible_coalition_count": 1,
        "selected_speaker_count": 3,
        "lexical_distance": None,
    }
    assert summary["mean_between_coalition_lexical_distance"] is None
