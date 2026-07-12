"""Coalition Dialects v1 semantics, transactionality, and bounds."""

from __future__ import annotations

import ast
import builtins
import copy
from dataclasses import FrozenInstanceError
import inspect
import json
import random
from types import MappingProxyType

import pytest

from thalren_vale import economy, language as language_module, sim
from thalren_vale.coalitions import (
    CoalitionCommunicationContext,
    CoalitionInvariantError,
    CoalitionMembershipSnapshot,
    CoalitionRuntimeState,
    InformalCoalition,
    build_coalition_membership_snapshot,
    classify_coalition_communication,
    transition_informal_coalitions,
)
from thalren_vale.config import (
    CoalitionConfig,
    CoalitionDialectConfig,
    LanguageEvolutionConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AssociationOrigin,
    CoalitionDialectRuntimeState,
    CommunicationContext,
    CommunicationResult,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    MAX_LANGUAGE_COUNTER,
    Meaning,
    Signal,
    canonical_language_snapshot,
    coalition_dialect_summary,
    communicate,
    initialize_language_runtime,
    lexical_convergence_snapshot,
)


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)
NO_INVENTION = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, False)
LOW_RATE_LANGUAGE = LanguageEvolutionConfig(
    True, 32, 3, 0.10, 0.05, 25, True)
SOCIAL_DISABLED = SocialMemoryConfig(False, False, 32, 25)
COALITIONS = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)
DIALECT = CoalitionDialectConfig(True, 1.50, 1.25)
STRONG_DIALECT = CoalitionDialectConfig(True, 2.0, 2.0)


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
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        origin=AssociationOrigin.INVENTED,
    )


def learned(
    meaning: Meaning,
    signal: Signal,
    confidence: float = 0.50,
    *,
    successful_uses: int = 0,
) -> LexicalAssociation:
    return LexicalAssociation(
        meaning=meaning,
        signal=signal,
        confidence=confidence,
        successful_uses=successful_uses,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
    )


def language_runtime(
    *,
    dialect: bool,
    seed: int = 17,
) -> LanguageRuntimeState:
    runtime = LanguageRuntimeState()
    initialize_language_runtime(
        runtime,
        seed,
        coalition_dialect_influence_enabled=dialect,
    )
    return runtime


def coalition_runtime(
    groups: tuple[tuple[int, ...], ...],
    *,
    active_ids: tuple[int, ...] | None = None,
    last_tick: int = 1,
) -> CoalitionRuntimeState:
    coalitions = {
        coalition_id: InformalCoalition(coalition_id, 1, members)
        for coalition_id, members in enumerate(groups)
    }
    membership = {
        member_id: coalition_id
        for coalition_id, members in enumerate(groups)
        for member_id in members
    }
    if active_ids is None:
        active_ids = tuple(sorted(membership))
    return CoalitionRuntimeState(
        active_coalitions=coalitions,
        member_to_coalition=membership,
        next_coalition_id=len(groups),
        candidate_formation_count=len(groups),
        last_observation_tick=last_tick,
        last_active_inhabitant_ids=tuple(sorted(active_ids)),
    )


def snapshot(
    groups: tuple[tuple[int, ...], ...] = ((1, 2, 3),),
    *,
    current_ids: tuple[int, ...] | None = None,
) -> CoalitionMembershipSnapshot:
    runtime = coalition_runtime(groups)
    if current_ids is None:
        current_ids = runtime.last_active_inhabitant_ids
    return build_coalition_membership_snapshot(
        runtime,
        snapshot_tick=2,
        active_inhabitant_ids=current_ids,
        config=COALITIONS,
    )


def dialect_call(
    sender: Inhabitant,
    receiver: Inhabitant,
    runtime: LanguageRuntimeState,
    dialect_runtime: CoalitionDialectRuntimeState,
    membership_snapshot: CoalitionMembershipSnapshot,
    *,
    config: LanguageEvolutionConfig = LANGUAGE,
    dialect_config: CoalitionDialectConfig = DIALECT,
):
    return communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset(membership_snapshot.active_inhabitant_ids),
        config=config,
        runtime=runtime,
        dialect_config=dialect_config,
        dialect_runtime=dialect_runtime,
        coalition_membership_snapshot=membership_snapshot,
    )


class SummaryInhabitantSpy:
    """Expose only summary inputs while counting stable-ID observations."""

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
        raise AssertionError("dialect summary compared inhabitants globally")


class OneShotPopulation:
    """Require each yielded inhabitant to be aggregated before the next."""

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
                    "population was materialized instead of aggregated in one pass"
                )


def semantic_summary_fixture(
    *,
    reverse_coalition_insertion: bool = False,
    reverse_lexical_insertion: bool = False,
):
    """Build deterministic active, dissolved, and unassigned summary groups."""
    people = [person(index) for index in range(1, 9)]
    food_a = Signal((1, 0))
    food_b = Signal((2, 0))
    wood_c = Signal((3, 0))
    wood_d = Signal((4, 0))
    ore_e = Signal((5, 0))
    food_alternative = Signal((7, 7))
    wood_alternative = Signal((7, 6))

    assignments = {
        1: ((Meaning.FOOD, food_a), (Meaning.WOOD, wood_c), (Meaning.ORE, ore_e)),
        2: ((Meaning.FOOD, food_a), (Meaning.WOOD, wood_c)),
        3: ((Meaning.FOOD, food_b), (Meaning.WOOD, wood_c)),
        4: ((Meaning.FOOD, food_b), (Meaning.WOOD, wood_d)),
        5: ((Meaning.FOOD, food_b), (Meaning.WOOD, wood_d)),
        6: ((Meaning.WOOD, wood_d),),
        7: ((Meaning.FOOD, food_a),),
        8: (),
    }
    for inhabitant in people:
        for meaning, signal in assignments[inhabitant.inhabitant_id]:
            inhabitant.language.production[(meaning, signal)] = invented(
                meaning, signal, 0.70)
            inhabitant.language.comprehension[(signal, meaning)] = learned(
                meaning, signal, 0.45)

    people[0].language.production[(
        Meaning.FOOD, food_alternative
    )] = invented(Meaning.FOOD, food_alternative, 0.20)
    people[3].language.production[(
        Meaning.WOOD, wood_alternative
    )] = invented(Meaning.WOOD, wood_alternative, 0.20)

    if reverse_lexical_insertion:
        for inhabitant in people:
            inhabitant.language.production = dict(reversed(
                tuple(inhabitant.language.production.items())))
            inhabitant.language.comprehension = dict(reversed(
                tuple(inhabitant.language.comprehension.items())))

    active_coalitions = {
        0: InformalCoalition(0, 1, (1, 2, 3)),
        2: InformalCoalition(2, 1, (4, 5, 6)),
    }
    membership = {
        1: 0,
        2: 0,
        3: 0,
        4: 2,
        5: 2,
        6: 2,
    }
    if reverse_coalition_insertion:
        active_coalitions = dict(reversed(tuple(active_coalitions.items())))
        membership = dict(reversed(tuple(membership.items())))
    coalition_state = CoalitionRuntimeState(
        active_coalitions=active_coalitions,
        member_to_coalition=membership,
        next_coalition_id=3,
        candidate_formation_count=3,
        dissolution_count=1,
        last_observation_tick=1,
        last_active_inhabitant_ids=tuple(range(1, 9)),
    )
    frozen = build_coalition_membership_snapshot(
        coalition_state,
        snapshot_tick=2,
        active_inhabitant_ids=tuple(range(1, 9)),
        config=COALITIONS,
    )
    return (
        people,
        coalition_state,
        frozen,
        language_runtime(dialect=True),
        CoalitionDialectRuntimeState(),
    )


def render_dialect_summary(
    people,
    frozen,
    runtime,
    dialect_runtime,
) -> str:
    """Render the canonical insertion order without JSON key re-sorting."""
    summary = coalition_dialect_summary(
        people,
        snapshot=frozen,
        language_config=LANGUAGE,
        dialect_config=DIALECT,
        language_runtime=runtime,
        dialect_runtime=dialect_runtime,
    )
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))


def test_snapshot_is_private_immutable_and_freezes_all_four_contexts():
    runtime = coalition_runtime(
        ((1, 2, 3), (4, 5, 6)),
        active_ids=(1, 2, 3, 4, 5, 6, 7, 8),
    )
    frozen = build_coalition_membership_snapshot(
        runtime,
        snapshot_tick=2,
        active_inhabitant_ids=(8, 7, 6, 5, 4, 3, 2, 1),
        config=COALITIONS,
    )

    assert frozen.active_inhabitant_ids == tuple(range(1, 9))
    assert classify_coalition_communication(
        frozen, tick=2, sender_id=1, receiver_id=2
    ).context is CoalitionCommunicationContext.SAME_ACTIVE_COALITION
    assert classify_coalition_communication(
        frozen, tick=2, sender_id=1, receiver_id=4
    ).context is CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS
    assert classify_coalition_communication(
        frozen, tick=2, sender_id=1, receiver_id=7
    ).context is CoalitionCommunicationContext.ASSIGNED_UNASSIGNED
    assert classify_coalition_communication(
        frozen, tick=2, sender_id=7, receiver_id=8
    ).context is CoalitionCommunicationContext.BOTH_UNASSIGNED

    runtime.member_to_coalition.clear()
    runtime.active_coalitions.clear()
    assert classify_coalition_communication(
        frozen, tick=2, sender_id=1, receiver_id=2
    ).context is CoalitionCommunicationContext.SAME_ACTIVE_COALITION
    with pytest.raises(TypeError):
        frozen._member_to_coalition[1] = 99
    with pytest.raises(FrozenInstanceError):
        frozen.snapshot_tick = 3


def test_stale_and_forged_snapshots_fail_before_any_language_mutation():
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot()
    before = (
        canonical_language_snapshot([sender, receiver], config=LANGUAGE),
        copy.deepcopy(state),
        copy.deepcopy(dialect_state),
    )

    with pytest.raises(CoalitionInvariantError, match="stale"):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=3,
            active_ids=frozenset({1, 2}),
            config=LANGUAGE,
            runtime=state,
            dialect_config=DIALECT,
            dialect_runtime=dialect_state,
            coalition_membership_snapshot=frozen,
        )
    assert before == (
        canonical_language_snapshot([sender, receiver], config=LANGUAGE),
        state,
        dialect_state,
    )

    with pytest.raises(CoalitionInvariantError, match="forged"):
        CoalitionMembershipSnapshot(
            snapshot_tick=2,
            source_observation_tick=1,
            active_coalition_ids=(0,),
            active_inhabitant_ids=(1, 2),
            lineage=(1, 1, 0),
            member_to_coalition={1: 0, 2: 0},
            factory_token=object(),
        )


def test_communicator_absent_from_frozen_active_ids_is_rejected():
    sender, receiver = person(1), person(7)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot(current_ids=(1, 2))

    with pytest.raises(CoalitionInvariantError, match="frozen active-ID"):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 7}),
            config=LANGUAGE,
            runtime=state,
            dialect_config=DIALECT,
            dialect_runtime=dialect_state,
            coalition_membership_snapshot=frozen,
        )

    assert state.communication_attempt_count == 0
    assert dialect_state == CoalitionDialectRuntimeState()


@pytest.mark.parametrize(
    "missing",
    ["dialect_config", "dialect_runtime", "coalition_membership_snapshot"],
)
def test_enabled_communicate_requires_every_dialect_owner(missing):
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot()
    kwargs = {
        "dialect_config": DIALECT,
        "dialect_runtime": dialect_state,
        "coalition_membership_snapshot": frozen,
    }
    del kwargs[missing]

    with pytest.raises(LanguageInvariantError, match="missing_dialect"):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 2}),
            config=LANGUAGE,
            runtime=state,
            **kwargs,
        )
    assert sender.language.production == {}
    assert receiver.language.comprehension == {}
    assert state.communication_attempt_count == 0
    assert dialect_state == CoalitionDialectRuntimeState()


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("dialect_config", object()),
        ("dialect_runtime", LanguageRuntimeState()),
        ("coalition_membership_snapshot", object()),
    ],
)
def test_wrong_type_dialect_inputs_fail_before_language_mutation(
    field,
    wrong_value,
):
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    kwargs = {
        "dialect_config": DIALECT,
        "dialect_runtime": dialect_state,
        "coalition_membership_snapshot": snapshot(),
    }
    kwargs[field] = wrong_value

    with pytest.raises((LanguageInvariantError, CoalitionInvariantError)):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 2}),
            config=LANGUAGE,
            runtime=state,
            **kwargs,
        )

    assert sender.language == language_module.AgentLanguageState()
    assert receiver.language == language_module.AgentLanguageState()
    assert state.communication_attempt_count == 0
    assert dialect_state == CoalitionDialectRuntimeState()


def test_disabled_communication_enters_no_dialect_helper_or_rng_path(monkeypatch):
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=False)
    for name in (
        "validate_coalition_dialect_config",
        "validate_coalition_dialect_runtime",
        "classify_coalition_communication",
        "_effective_dialect_rate",
        "_saturating_add",
    ):
        monkeypatch.setattr(
            language_module,
            name,
            lambda *args, _name=name, **kwargs: pytest.fail(
                f"disabled path entered {_name}"
            ),
        )
    rng_state = random.getstate()

    outcome = communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset({1, 2}),
        config=LANGUAGE,
        runtime=state,
    )

    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert random.getstate() == rng_state


def test_disabled_counter_overflow_keeps_the_original_language_v1_failure():
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=False)
    state.communication_attempt_count = MAX_LANGUAGE_COUNTER
    state.unknown_signal_count = MAX_LANGUAGE_COUNTER
    state.last_communication_tick = 1
    before = copy.deepcopy((sender.language, receiver.language, state))

    with pytest.raises(LanguageInvariantError, match="counter_overflow"):
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=frozenset({1, 2}),
            config=LANGUAGE,
            runtime=state,
        )

    assert sender.language == before[0]
    assert receiver.language == before[1]
    assert state == before[2]


def test_same_coalition_unknown_learning_is_adjusted_after_classification():
    sender, receiver = person(1), person(2)
    signal = Signal((6, 1))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    outcome = dialect_call(sender, receiver, state, dialect_state, snapshot())

    association = receiver.language.comprehension[(signal, Meaning.FOOD)]
    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert outcome.interpreted_meaning is None
    assert association.confidence == 0.30
    assert sender.language.production[(Meaning.FOOD, signal)].confidence == 0.45
    assert dialect_state.same_coalition_communication_count == 1
    assert dialect_state.same_coalition_rate_application_count == 1


def test_same_coalition_misunderstanding_uses_only_corrective_adjustment():
    sender, receiver = person(1), person(2)
    signal = Signal((6, 2))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD, signal, 0.60)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    outcome = dialect_call(sender, receiver, state, dialect_state, snapshot())

    assert outcome.result is CommunicationResult.MISUNDERSTANDING
    assert receiver.language.comprehension[(signal, Meaning.WOOD)].confidence == 0.50
    assert receiver.language.comprehension[(signal, Meaning.FOOD)].confidence == 0.30
    assert sender.language.production[(Meaning.FOOD, signal)].confidence == 0.45
    assert dialect_state.same_coalition_rate_application_count == 1


def test_same_coalition_success_counts_each_adjusted_confidence_delta():
    sender, receiver = person(1), person(2)
    signal = Signal((6, 3))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD, signal)
    receiver.language.production[(Meaning.FOOD, signal)] = learned(
        Meaning.FOOD, signal, 0.40)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    outcome = dialect_call(sender, receiver, state, dialect_state, snapshot())

    assert outcome.result is CommunicationResult.SUCCESS
    assert sender.language.production[(Meaning.FOOD, signal)].confidence == 0.625
    assert receiver.language.comprehension[(signal, Meaning.FOOD)].confidence == 0.625
    assert receiver.language.production[(Meaning.FOOD, signal)].confidence == 0.55
    assert dialect_state.same_coalition_rate_application_count == 3


def test_promotion_and_no_signal_do_not_count_as_adjusted_deltas():
    sender, receiver = person(1), person(2)
    signal = Signal((6, 4))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.FOOD)] = learned(
        Meaning.FOOD, signal, successful_uses=2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    outcome = dialect_call(sender, receiver, state, dialect_state, snapshot())
    assert outcome.result is CommunicationResult.SUCCESS
    assert (Meaning.FOOD, signal) in receiver.language.production
    assert dialect_state.same_coalition_rate_application_count == 2

    empty_sender, empty_receiver = person(1), person(2)
    empty_state = language_runtime(dialect=True)
    empty_dialect = CoalitionDialectRuntimeState()
    outcome = dialect_call(
        empty_sender,
        empty_receiver,
        empty_state,
        empty_dialect,
        snapshot(),
        config=NO_INVENTION,
    )
    assert outcome.result is CommunicationResult.NO_SIGNAL
    assert empty_dialect.same_coalition_rate_application_count == 0


def test_adjusted_delta_is_counted_even_when_canonical_retention_prunes_it():
    one_association = LanguageEvolutionConfig(
        True, 1, 3, 0.20, 0.10, 25, True)
    sender, receiver = person(1), person(2)
    signal = Signal((6, 5))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    receiver.language.comprehension[(signal, Meaning.WOOD)] = learned(
        Meaning.WOOD, signal, 0.60)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    outcome = dialect_call(
        sender,
        receiver,
        state,
        dialect_state,
        snapshot(),
        config=one_association,
    )

    assert outcome.result is CommunicationResult.MISUNDERSTANDING
    assert (signal, Meaning.FOOD) not in receiver.language.comprehension
    assert dialect_state.same_coalition_rate_application_count == 1


@pytest.mark.parametrize(
    ("groups", "current_ids", "sender_id", "receiver_id", "expected_context"),
    [
        (
            ((1, 2, 3), (4, 5, 6)),
            (1, 2, 3, 4, 5, 6),
            1,
            4,
            CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS,
        ),
        (
            ((1, 2, 3),),
            (1, 2, 3, 7),
            1,
            7,
            CoalitionCommunicationContext.ASSIGNED_UNASSIGNED,
        ),
        (
            ((1, 2, 3),),
            (1, 2, 3, 7, 8),
            7,
            8,
            CoalitionCommunicationContext.BOTH_UNASSIGNED,
        ),
    ],
)
def test_cross_group_contexts_retain_base_language_rates(
    groups,
    current_ids,
    sender_id,
    receiver_id,
    expected_context,
):
    sender, receiver = person(sender_id), person(receiver_id)
    signal = Signal((5, 1))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot(groups, current_ids=current_ids)

    outcome = dialect_call(sender, receiver, state, dialect_state, frozen)

    assert outcome.coalition_context is expected_context
    assert receiver.language.comprehension[(signal, Meaning.FOOD)].confidence == 0.20
    assert dialect_state.same_coalition_rate_application_count == 0
    expected_counter = {
        CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS: (
            "different_coalition_communication_count"
        ),
        CoalitionCommunicationContext.ASSIGNED_UNASSIGNED: (
            "assigned_unassigned_communication_count"
        ),
        CoalitionCommunicationContext.BOTH_UNASSIGNED: (
            "both_unassigned_communication_count"
        ),
    }[expected_context]
    assert getattr(dialect_state, expected_counter) == 1


def test_attempt_saturation_preserves_the_context_partition():
    sender, receiver = person(1), person(2)
    signal = Signal((4, 1))
    sender.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    state = language_runtime(dialect=True)
    state.communication_attempt_count = MAX_LANGUAGE_COUNTER
    state.unknown_signal_count = MAX_LANGUAGE_COUNTER
    state.last_communication_tick = 1
    dialect_state = CoalitionDialectRuntimeState(
        same_coalition_communication_count=MAX_LANGUAGE_COUNTER,
        same_coalition_rate_application_count=MAX_LANGUAGE_COUNTER,
        last_classification_tick=1,
    )

    outcome = dialect_call(sender, receiver, state, dialect_state, snapshot())

    assert outcome.result is CommunicationResult.UNKNOWN_SIGNAL
    assert state.communication_attempt_count == MAX_LANGUAGE_COUNTER
    assert state.unknown_signal_count == MAX_LANGUAGE_COUNTER
    assert dialect_state.same_coalition_communication_count == MAX_LANGUAGE_COUNTER
    assert (
        dialect_state.same_coalition_communication_count
        + dialect_state.different_coalition_communication_count
        + dialect_state.assigned_unassigned_communication_count
        + dialect_state.both_unassigned_communication_count
    ) == state.communication_attempt_count
    assert (
        dialect_state.same_coalition_rate_application_count
        == MAX_LANGUAGE_COUNTER
    )


def test_partition_mismatch_rolls_back_all_four_proposed_owners():
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState(
        same_coalition_communication_count=1,
        last_classification_tick=1,
    )
    before = copy.deepcopy((sender, receiver, state, dialect_state))

    with pytest.raises(LanguageInvariantError, match="partition"):
        dialect_call(sender, receiver, state, dialect_state, snapshot())

    assert canonical_language_snapshot(
        [sender, receiver], config=LANGUAGE
    ) == canonical_language_snapshot([before[0], before[1]], config=LANGUAGE)
    assert state == before[2]
    assert dialect_state == before[3]


def test_late_dialect_proposal_failure_rolls_back_four_owners_and_external_state(
    monkeypatch,
):
    sender, receiver = person(1), person(2)
    sender.inventory["food"] = 7
    sender.relationships[2] = object()
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    before = copy.deepcopy((sender.language, receiver.language, state, dialect_state))
    inventory_before = dict(sender.inventory)
    relationships_before = dict(sender.relationships)
    rng_before = random.getstate()

    def fail_retention(*args, **kwargs):
        raise LanguageInvariantError("injected_failure", "dialect proposal failed")

    monkeypatch.setattr(language_module, "_retain_canonical", fail_retention)
    with pytest.raises(LanguageInvariantError, match="dialect proposal failed"):
        dialect_call(sender, receiver, state, dialect_state, snapshot())

    assert sender.language == before[0]
    assert receiver.language == before[1]
    assert state == before[2]
    assert dialect_state == before[3]
    assert sender.inventory == inventory_before
    assert sender.relationships == relationships_before
    assert random.getstate() == rng_before


def test_snapshot_builder_runs_once_and_one_object_serves_the_economy_pass(
    monkeypatch,
):
    people = [person(index) for index in range(1, 5)]
    monkeypatch.setattr(sim, "people", people)
    monkeypatch.setattr(sim, "factions", [])
    monkeypatch.setattr(sim.state, "coalitions", CoalitionRuntimeState())
    monkeypatch.setattr(sim.state, "language", language_runtime(dialect=True))
    monkeypatch.setattr(
        sim.state, "dialect", CoalitionDialectRuntimeState())
    build_calls = []
    observed_snapshots = []
    real_builder = sim.build_coalition_membership_snapshot

    def counted_builder(*args, **kwargs):
        build_calls.append((args, kwargs))
        return real_builder(*args, **kwargs)

    def two_authentic_occurrences(
        active_people,
        factions,
        tick,
        event_log,
        **kwargs,
    ):
        del factions, event_log
        frozen = kwargs["coalition_membership_snapshot"]
        for sender, receiver in ((active_people[0], active_people[1]),
                                 (active_people[2], active_people[3])):
            observed_snapshots.append(frozen)
            communicate(
                sender,
                receiver,
                Meaning.FOOD,
                context=CommunicationContext.AID_TRANSFER,
                tick=tick,
                active_ids=frozenset(range(1, 5)),
                config=kwargs["language_config"],
                runtime=kwargs["language_runtime"],
                dialect_config=kwargs["dialect_config"],
                dialect_runtime=kwargs["dialect_runtime"],
                coalition_membership_snapshot=frozen,
            )

    monkeypatch.setattr(sim, "build_coalition_membership_snapshot", counted_builder)
    monkeypatch.setattr(economy, "economy_tick", two_authentic_occurrences)

    sim.economy_layer(
        1,
        SocialMemoryConfig(True, False, 32, 25),
        LANGUAGE,
        DIALECT,
        COALITIONS,
    )

    assert len(build_calls) == 1
    assert len(observed_snapshots) == 2
    assert observed_snapshots[0] is observed_snapshots[1]


def test_per_occurrence_classification_contains_no_membership_scan():
    source = inspect.getsource(classify_coalition_communication)
    tree = ast.parse(source)

    assert not any(isinstance(node, (ast.For, ast.ListComp, ast.SetComp,
                                     ast.DictComp, ast.GeneratorExp))
                   for node in ast.walk(tree))
    assert ".items(" not in source
    assert ".keys(" not in source
    assert ".values(" not in source
    assert source.count("._member_to_coalition.get(") == 2


def test_enabled_communicate_does_constant_active_id_validation(monkeypatch):
    frozen = snapshot()
    real_exact = language_module._exact_nonnegative_int

    def validation_count(active_ids):
        sender, receiver = person(1), person(2)
        state = language_runtime(dialect=True)
        dialect_state = CoalitionDialectRuntimeState()
        calls = 0

        def counted(value):
            nonlocal calls
            calls += 1
            return real_exact(value)

        monkeypatch.setattr(language_module, "_exact_nonnegative_int", counted)
        communicate(
            sender,
            receiver,
            Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER,
            tick=2,
            active_ids=active_ids,
            config=LANGUAGE,
            runtime=state,
            dialect_config=DIALECT,
            dialect_runtime=dialect_state,
            coalition_membership_snapshot=frozen,
        )
        monkeypatch.setattr(
            language_module, "_exact_nonnegative_int", real_exact)
        return calls

    small = validation_count(frozenset({1, 2, 3}))
    large = validation_count(frozenset(range(20_000)))

    assert small == large


def test_many_same_tick_occurrences_do_one_constant_classification_each(
    monkeypatch,
):
    sender, receiver = person(1), person(2)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot()
    classification_calls = 0
    real_classify = language_module.classify_coalition_communication

    def counted(*args, **kwargs):
        nonlocal classification_calls
        classification_calls += 1
        return real_classify(*args, **kwargs)

    monkeypatch.setattr(language_module, "classify_coalition_communication", counted)
    for _occurrence in range(128):
        dialect_call(sender, receiver, state, dialect_state, frozen)

    assert classification_calls == 128
    assert state.communication_attempt_count == 128
    assert dialect_state.same_coalition_communication_count == 128
    assert (
        len(sender.language.production)
        + len(sender.language.comprehension)
        <= LANGUAGE.maximum_language_associations
    )
    assert (
        len(receiver.language.production)
        + len(receiver.language.comprehension)
        <= LANGUAGE.maximum_language_associations
    )


def test_committed_transfer_classifies_once_and_failed_transfer_not_at_all(
    monkeypatch,
):
    giver, receiver = person(1), person(2)
    giver.inventory["food"] = 3
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    authoritative_coalitions = coalition_runtime(((1, 2, 3),))
    frozen = build_coalition_membership_snapshot(
        authoritative_coalitions,
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2),
        config=COALITIONS,
    )
    coalition_before = copy.deepcopy(authoritative_coalitions)
    classifications = 0
    real_classify = language_module.classify_coalition_communication

    def counted(*args, **kwargs):
        nonlocal classifications
        classifications += 1
        return real_classify(*args, **kwargs)

    monkeypatch.setattr(language_module, "classify_coalition_communication", counted)
    economy._commit_individual_transfer(
        giver,
        receiver,
        "food",
        t=2,
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE,
        language_runtime=state,
        dialect_config=DIALECT,
        dialect_runtime=dialect_state,
        coalition_membership_snapshot=frozen,
        active_ids=frozenset({1, 2}),
    )
    assert classifications == 1
    assert giver.inventory["food"] == 2
    assert receiver.inventory["food"] == 1
    assert authoritative_coalitions == coalition_before

    failed_giver, failed_receiver = person(1), person(2)
    failed_giver.inventory["food"] = 2
    assert not economy._attempt_individual_transfer(
        failed_giver,
        failed_receiver,
        t=2,
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE,
        language_runtime=state,
        dialect_config=DIALECT,
        dialect_runtime=dialect_state,
        coalition_membership_snapshot=frozen,
        active_ids=frozenset({1, 2}),
    )
    assert classifications == 1


def test_dialect_influence_changes_only_language_for_the_same_transfer():
    initial = (person(1), person(2))
    initial[0].inventory["food"] = 3
    initial[1].currency = economy.BASE_PRICES["food"]
    baseline = copy.deepcopy(initial)
    influenced = copy.deepcopy(initial)
    baseline_runtime = language_runtime(dialect=False)
    influenced_runtime = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    authoritative = coalition_runtime(((1, 2, 3),))
    authoritative_before = copy.deepcopy(authoritative)
    frozen = build_coalition_membership_snapshot(
        authoritative,
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2),
        config=COALITIONS,
    )
    rng_before = random.getstate()

    economy._commit_individual_transfer(
        baseline[0],
        baseline[1],
        "food",
        t=2,
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE,
        language_runtime=baseline_runtime,
        active_ids=frozenset({1, 2}),
    )
    economy._commit_individual_transfer(
        influenced[0],
        influenced[1],
        "food",
        t=2,
        social_config=SOCIAL_DISABLED,
        language_config=LANGUAGE,
        language_runtime=influenced_runtime,
        dialect_config=DIALECT,
        dialect_runtime=dialect_state,
        coalition_membership_snapshot=frozen,
        active_ids=frozenset({1, 2}),
    )

    for baseline_person, influenced_person in zip(baseline, influenced):
        assert baseline_person.inventory == influenced_person.inventory
        assert baseline_person.currency == influenced_person.currency
        assert baseline_person.trust == influenced_person.trust
        assert baseline_person.trade_count == influenced_person.trade_count
        assert baseline_person.relationships == influenced_person.relationships
        assert baseline_person.faction == influenced_person.faction
        assert baseline_person.health == influenced_person.health
    assert authoritative == authoritative_before
    assert random.getstate() == rng_before
    base_confidence = next(iter(
        baseline[1].language.comprehension.values())).confidence
    influenced_confidence = next(iter(
        influenced[1].language.comprehension.values())).confidence
    assert base_confidence == 0.20
    assert influenced_confidence == 0.30


def test_language_results_do_not_change_the_next_coalition_transition():
    baseline_people = [person(index) for index in range(1, 4)]
    influenced_people = copy.deepcopy(baseline_people)
    baseline_coalitions = coalition_runtime(((1, 2, 3),))
    influenced_coalitions = copy.deepcopy(baseline_coalitions)
    frozen = build_coalition_membership_snapshot(
        influenced_coalitions,
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2, 3),
        config=COALITIONS,
    )
    baseline_runtime = language_runtime(dialect=False)
    influenced_runtime = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()

    communicate(
        baseline_people[0],
        baseline_people[1],
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset({1, 2, 3}),
        config=LANGUAGE,
        runtime=baseline_runtime,
    )
    dialect_call(
        influenced_people[0],
        influenced_people[1],
        influenced_runtime,
        dialect_state,
        frozen,
    )

    baseline_result = transition_informal_coalitions(
        baseline_people,
        baseline_coalitions,
        tick=2,
        config=COALITIONS,
    )
    influenced_result = transition_informal_coalitions(
        influenced_people,
        influenced_coalitions,
        tick=2,
        config=COALITIONS,
    )

    assert baseline_result == influenced_result


def test_repeated_in_group_events_can_outpace_base_rate_convergence():
    signal = Signal((3, 7))

    def interact(*, dialect: bool):
        sender, receiver = person(1), person(2)
        sender.language.production[(Meaning.FOOD, signal)] = invented(
            Meaning.FOOD, signal)
        state = language_runtime(dialect=dialect)
        dialect_state = CoalitionDialectRuntimeState()
        for _occurrence in range(4):
            if dialect:
                dialect_call(
                    sender,
                    receiver,
                    state,
                    dialect_state,
                    snapshot(),
                    config=LOW_RATE_LANGUAGE,
                    dialect_config=STRONG_DIALECT,
                )
            else:
                communicate(
                    sender,
                    receiver,
                    Meaning.FOOD,
                    context=CommunicationContext.AID_TRANSFER,
                    tick=2,
                    active_ids=frozenset({1, 2}),
                    config=LOW_RATE_LANGUAGE,
                    runtime=state,
                )
        return lexical_convergence_snapshot(
            [sender, receiver], config=LOW_RATE_LANGUAGE)

    base = interact(dialect=False)
    influenced = interact(dialect=True)

    assert base["meanings"][0]["speaker_count"] == 1
    assert influenced["meanings"][0]["speaker_count"] == 2
    assert influenced["meanings"][0]["pairwise_agreement"] == 1.0


def test_isolated_coalitions_can_retain_distinct_member_carried_signals():
    people = [person(index) for index in range(1, 7)]
    first_signal = Signal((1, 7))
    second_signal = Signal((7, 1))
    people[0].language.production[(Meaning.FOOD, first_signal)] = invented(
        Meaning.FOOD, first_signal)
    people[3].language.production[(Meaning.FOOD, second_signal)] = invented(
        Meaning.FOOD, second_signal)
    state = language_runtime(dialect=True)
    dialect_state = CoalitionDialectRuntimeState()
    frozen = snapshot(((1, 2, 3), (4, 5, 6)))
    for sender, receiver in ((people[0], people[1]), (people[3], people[4])):
        for _occurrence in range(4):
            dialect_call(
                sender,
                receiver,
                state,
                dialect_state,
                frozen,
                config=LOW_RATE_LANGUAGE,
                dialect_config=STRONG_DIALECT,
            )

    summary = coalition_dialect_summary(
        people,
        snapshot=frozen,
        language_config=LOW_RATE_LANGUAGE,
        dialect_config=STRONG_DIALECT,
        language_runtime=state,
        dialect_runtime=dialect_state,
    )

    food = [record["meanings"][0] for record in summary["coalitions"]]
    assert food[0]["dominant_signal"] == [1, 7]
    assert food[1]["dominant_signal"] == [7, 1]
    assert summary["between_coalitions"][0] == {
        "meaning": "FOOD",
        "sufficient_coalition_count": 2,
        "lexical_distance": 1.0,
    }


def test_membership_changes_and_dissolution_never_rewrite_vocabulary():
    inhabitant = person(1)
    signal = Signal((2, 5))
    inhabitant.language.production[(Meaning.FOOD, signal)] = invented(
        Meaning.FOOD, signal)
    before = canonical_language_snapshot([inhabitant], config=LANGUAGE)

    build_coalition_membership_snapshot(
        coalition_runtime(((1, 2, 3),)),
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2, 3),
        config=COALITIONS,
    )
    build_coalition_membership_snapshot(
        coalition_runtime(((4, 5, 6),), active_ids=(1, 4, 5, 6)),
        snapshot_tick=2,
        active_inhabitant_ids=(1, 4, 5, 6),
        config=COALITIONS,
    )

    assert canonical_language_snapshot([inhabitant], config=LANGUAGE) == before


def test_dialect_summary_consumes_and_aggregates_population_exactly_once():
    people, _coalitions, frozen, runtime, dialect_state = (
        semantic_summary_fixture()
    )
    spies = [SummaryInhabitantSpy(inhabitant) for inhabitant in people]
    one_shot = OneShotPopulation(spies)

    summary = coalition_dialect_summary(
        one_shot,
        snapshot=frozen,
        language_config=LANGUAGE,
        dialect_config=DIALECT,
        language_runtime=runtime,
        dialect_runtime=dialect_state,
    )

    assert summary["active_coalition_count"] == 2
    assert one_shot.iteration_count == 1
    assert one_shot.yield_count == len(people)
    assert all(spy.inhabitant_id_read_count == 1 for spy in spies)


def test_dialect_summary_population_and_association_work_is_linear(
    monkeypatch,
):
    real_validate_state = language_module.validate_agent_language_state
    real_validate_association = language_module._validate_association
    real_select_production = language_module._select_production
    real_sorted = builtins.sorted

    def operation_counts(population_size: int) -> dict[str, object]:
        people = [person(index) for index in range(1, population_size + 1)]
        for inhabitant in people:
            for meaning_index, meaning in enumerate(Meaning):
                signal = Signal((meaning_index, inhabitant.inhabitant_id % 4))
                inhabitant.language.production[(meaning, signal)] = invented(
                    meaning, signal)
        frozen = snapshot(
            ((1, 2, 3),),
            current_ids=tuple(range(1, population_size + 1)),
        )
        spies = [SummaryInhabitantSpy(inhabitant) for inhabitant in people]
        counts: dict[str, object] = {
            "state_validations": 0,
            "association_validations": 0,
            "production_selections": 0,
            "selection_association_visits": 0,
            "sorted_sizes": [],
        }

        def counted_state_validation(state, *, config):
            counts["state_validations"] += 1
            return real_validate_state(state, config=config)

        def counted_association_validation(association, *, maximum_signal_length):
            counts["association_validations"] += 1
            return real_validate_association(
                association,
                maximum_signal_length=maximum_signal_length,
            )

        def counted_selection(state, meaning):
            counts["production_selections"] += 1
            counts["selection_association_visits"] += len(state.production)
            return real_select_production(state, meaning)

        def bounded_sorted(values, *args, **kwargs):
            materialized = tuple(values)
            assert not any(
                isinstance(value, SummaryInhabitantSpy)
                for value in materialized
            )
            counts["sorted_sizes"].append(len(materialized))
            return real_sorted(materialized, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(
                language_module,
                "validate_agent_language_state",
                counted_state_validation,
            )
            patch.setattr(
                language_module,
                "_validate_association",
                counted_association_validation,
            )
            patch.setattr(
                language_module,
                "_select_production",
                counted_selection,
            )
            patch.setattr(
                language_module,
                "sorted",
                bounded_sorted,
                raising=False,
            )
            coalition_dialect_summary(
                spies,
                snapshot=frozen,
                language_config=LANGUAGE,
                dialect_config=DIALECT,
                language_runtime=language_runtime(dialect=True),
                dialect_runtime=CoalitionDialectRuntimeState(),
            )

        counts["inhabitant_id_reads"] = sum(
            spy.inhabitant_id_read_count for spy in spies)
        return counts

    small = operation_counts(64)
    large = operation_counts(128)

    assert small["state_validations"] == 64
    assert large["state_validations"] == 128
    assert small["association_validations"] == 64 * len(Meaning)
    assert large["association_validations"] == 128 * len(Meaning)
    assert small["production_selections"] == 64 * len(Meaning)
    assert large["production_selections"] == 128 * len(Meaning)
    assert small["selection_association_visits"] == 64 * len(Meaning) ** 2
    assert large["selection_association_visits"] == 128 * len(Meaning) ** 2
    assert small["inhabitant_id_reads"] == 64
    assert large["inhabitant_id_reads"] == 128
    assert small["sorted_sizes"] == large["sorted_sizes"]
    assert max(small["sorted_sizes"], default=0) <= 4


def test_dialect_summary_is_byte_stable_across_all_insertion_orders():
    people, _coalitions, frozen, runtime, dialect_state = (
        semantic_summary_fixture()
    )
    population_orders = [
        people,
        list(reversed(people)),
        [people[index] for index in (2, 0, 7, 4, 1, 6, 3, 5)],
        [people[index] for index in (5, 3, 1, 7, 0, 6, 4, 2)],
    ]
    rendered = [
        render_dialect_summary(
            population,
            frozen,
            runtime,
            dialect_state,
        )
        for population in population_orders
    ]

    (
        reversed_people,
        _reversed_coalitions,
        reversed_frozen,
        reversed_runtime,
        reversed_dialect_state,
    ) = semantic_summary_fixture(
        reverse_coalition_insertion=True,
        reverse_lexical_insertion=True,
    )
    rendered.append(render_dialect_summary(
        [reversed_people[index] for index in (4, 7, 2, 0, 6, 1, 5, 3)],
        reversed_frozen,
        reversed_runtime,
        reversed_dialect_state,
    ))

    assert len(set(rendered)) == 1


def test_dialect_summary_preserves_frequency_semantics_and_former_vocabulary():
    people, _coalitions, frozen, runtime, dialect_state = (
        semantic_summary_fixture()
    )

    summary = coalition_dialect_summary(
        people,
        snapshot=frozen,
        language_config=LANGUAGE,
        dialect_config=DIALECT,
        language_runtime=runtime,
        dialect_runtime=dialect_state,
    )

    assert [record["coalition_id"] for record in summary["coalitions"]] == [0, 2]
    first_food, first_wood, first_ore, first_stone = (
        summary["coalitions"][0]["meanings"]
    )
    assert first_food == {
        "meaning": "FOOD",
        "speaker_count": 3,
        "non_speaker_count": 0,
        "dominant_signal": [1, 0],
        "signal_frequencies": [
            {"signal": [1, 0], "count": 2},
            {"signal": [2, 0], "count": 1},
        ],
        "pairwise_agreement": 0.333333,
    }
    assert first_wood["pairwise_agreement"] == 1.0
    assert first_ore["speaker_count"] == 1
    assert first_ore["non_speaker_count"] == 2
    assert first_ore["pairwise_agreement"] is None
    assert first_stone["speaker_count"] == 0
    assert first_stone["non_speaker_count"] == 3
    assert first_stone["pairwise_agreement"] is None
    assert summary["coalitions"][0]["mean_agreement"] == 0.666667
    assert summary["coalitions"][1]["mean_agreement"] == 1.0
    assert summary["between_coalitions"][:2] == [
        {
            "meaning": "FOOD",
            "sufficient_coalition_count": 2,
            "lexical_distance": 0.666667,
        },
        {
            "meaning": "WOOD",
            "sufficient_coalition_count": 2,
            "lexical_distance": 1.0,
        },
    ]
    assert summary["between_coalitions"][2]["lexical_distance"] is None
    assert summary["unassigned"] == {
        "member_count": 2,
        "meanings": [
            {
                "meaning": "FOOD",
                "speaker_count": 1,
                "non_speaker_count": 1,
                "dominant_signal": [1, 0],
                "signal_frequencies": [{"signal": [1, 0], "count": 1}],
                "pairwise_agreement": None,
            },
            *[
                {
                    "meaning": meaning.name,
                    "speaker_count": 0,
                    "non_speaker_count": 2,
                    "dominant_signal": None,
                    "signal_frequencies": [],
                    "pairwise_agreement": None,
                }
                for meaning in tuple(Meaning)[1:]
            ],
        ],
    }


def test_dialect_summary_is_observational_and_consumes_no_rng():
    people, coalition_state, frozen, runtime, dialect_state = (
        semantic_summary_fixture()
    )

    def inhabitant_record(inhabitant: Inhabitant) -> dict[str, object]:
        return {
            slot: copy.deepcopy(getattr(inhabitant, slot))
            for slot in Inhabitant.__slots__
            if hasattr(inhabitant, slot)
        }

    people_before = [inhabitant_record(inhabitant) for inhabitant in people]
    coalition_before = copy.deepcopy(coalition_state)
    runtime_before = copy.deepcopy(runtime)
    dialect_before = copy.deepcopy(dialect_state)
    invention_indices_before = [
        inhabitant.language.next_invention_index for inhabitant in people
    ]
    snapshot_before = (
        frozen.snapshot_tick,
        frozen.source_observation_tick,
        frozen.active_coalition_ids,
        frozen.active_inhabitant_ids,
        frozen.lineage,
        frozenset(frozen._active_inhabitant_id_set),
        dict(frozen._member_to_coalition),
    )
    rng_before = random.getstate()

    coalition_dialect_summary(
        people,
        snapshot=frozen,
        language_config=LANGUAGE,
        dialect_config=DIALECT,
        language_runtime=runtime,
        dialect_runtime=dialect_state,
    )

    assert [inhabitant_record(inhabitant) for inhabitant in people] == people_before
    assert coalition_state == coalition_before
    assert runtime == runtime_before
    assert dialect_state == dialect_before
    assert [
        inhabitant.language.next_invention_index for inhabitant in people
    ] == invention_indices_before
    assert (
        frozen.snapshot_tick,
        frozen.source_observation_tick,
        frozen.active_coalition_ids,
        frozen.active_inhabitant_ids,
        frozen.lineage,
        frozenset(frozen._active_inhabitant_id_set),
        dict(frozen._member_to_coalition),
    ) == snapshot_before
    assert random.getstate() == rng_before
