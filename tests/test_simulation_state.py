"""Tests for explicit simulation state ownership and lifecycle."""

import copy
import sys

import pytest

from thalren_vale import combat, diplomacy, economy, factions, religion, sim
from thalren_vale.events import JournalClaimError
from thalren_vale.coalitions import CoalitionCandidate, InformalCoalition
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    AssociationOrigin,
    CoalitionDialectRuntimeState,
    ContactExposure,
    LanguageContactRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Signal,
    contact_runtime_is_pristine,
    initialize_language_contact_runtime,
    initialize_language_runtime,
    dialect_runtime_is_pristine,
    language_runtime_is_pristine,
)


def reset_inhabitant(name: str, inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(name, 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    return inhabitant


def seed_failed_reset_state(
    living: list[Inhabitant],
    dead: list[Inhabitant] | None = None,
) -> dict[str, object]:
    sim.reset_runtime_state()
    sim.people.extend(living)
    sim.all_dead.extend(dead or [])
    list.append(sim.event_log, "reset sentinel")
    sim.state.next_inhabitant_id = 41
    sim.state.coalitions.candidate_formation_count = 3
    initialize_language_runtime(sim.state.language, 777)
    sim.state.language.invention_count = 2
    return {
        "people": tuple(sim.people),
        "all_dead": tuple(sim.all_dead),
        "event_log": tuple(sim.event_log),
        "next_inhabitant_id": sim.state.next_inhabitant_id,
        "coalition_formation_count": (
            sim.state.coalitions.candidate_formation_count
        ),
        "language_runtime": copy.deepcopy(sim.state.language),
        "dialect_runtime": copy.deepcopy(sim.state.dialect),
        "contact_runtime": copy.deepcopy(sim.state.language_contact),
    }


def assert_failed_reset_state_unchanged(before: dict[str, object]) -> None:
    assert tuple(sim.people) == before["people"]
    assert tuple(sim.all_dead) == before["all_dead"]
    assert tuple(sim.event_log) == before["event_log"]
    assert sim.state.next_inhabitant_id == before["next_inhabitant_id"]
    assert sim.state.coalitions.candidate_formation_count == (
        before["coalition_formation_count"]
    )
    assert sim.state.language == before["language_runtime"]
    assert sim.state.dialect == before["dialect_runtime"]
    assert sim.state.language_contact == before["contact_runtime"]


def test_domain_modules_share_state_owned_collections():
    assert combat.active_wars is sim.state.active_wars
    assert combat.war_history is sim.state.war_history
    assert factions.RIVALRIES is sim.state.rivalries
    assert diplomacy._treaties is sim.state.treaties
    assert diplomacy.treaty_log is sim.state.treaty_log
    assert diplomacy._reputation is sim.state.reputation
    assert economy.faction_currencies is sim.state.faction_currencies
    assert economy.trade_routes is sim.state.trade_routes
    assert religion._religions is sim.state.religions
    assert religion._HOLY_WARS is sim.state.holy_wars


def test_reset_runtime_state_clears_core_and_domain_stores():
    sim.reset_runtime_state()
    resident = reset_inhabitant("Resident", 0)
    speaker = reset_inhabitant("Speaker", 1)
    deceased = reset_inhabitant("Deceased", 2)
    signal = Signal((1, 2))
    speaker.language.production[(Meaning.FOOD, signal)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=signal,
        confidence=0.5,
        last_used_tick=1,
        origin=AssociationOrigin.INVENTED,
    )
    speaker.language.next_invention_index = 1
    deceased.language.comprehension[(signal, Meaning.FOOD)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=signal,
        confidence=0.4,
        last_used_tick=1,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=1,
    )
    deceased.language.next_invention_index = 2
    sim.state.people.extend((resident, speaker))
    sim.state.all_dead.append(deceased)
    initialize_language_runtime(sim.state.language, 7)
    sim.state.language.communication_attempt_count = 1
    sim.state.language.unknown_signal_count = 1
    sim.state.language.last_communication_tick = 1
    sim.state.event_log.begin_observation_tick(1)
    sim.state.event_log.append("event")
    combat.active_wars.append(object())
    economy.trade_routes[frozenset(("a", "b"))] = {}
    diplomacy._reputation["a"] = 5
    religion._HOLY_WARS.add(frozenset(("a", "b")))
    sim.state.coalitions.candidates[(1, 2, 3)] = CoalitionCandidate(
        (1, 2, 3), 1, 1, 1)
    sim.state.coalitions.active_coalitions[0] = InformalCoalition(
        0, 1, (4, 5, 6))
    sim.state.coalitions.member_to_coalition.update({4: 0, 5: 0, 6: 0})
    sim.state.coalitions.next_coalition_id = 1
    sim.state.coalitions.candidate_formation_count = 1
    sim.state.coalitions.last_observation_tick = 1
    sim.state.coalitions.last_active_inhabitant_ids = (1, 2, 3, 4, 5, 6)

    sim.reset_runtime_state()

    assert sim.people == []
    assert sim.event_log == []
    assert combat.active_wars == []
    assert economy.trade_routes == {}
    assert diplomacy._reputation == {}
    assert religion._HOLY_WARS == set()
    assert sim.state.coalitions.candidates == {}
    assert sim.state.coalitions.active_coalitions == {}
    assert sim.state.coalitions.member_to_coalition == {}
    assert sim.state.coalitions.next_coalition_id == 0
    assert sim.state.coalitions.last_observation_tick is None
    assert speaker.language.production == {}
    assert speaker.language.comprehension == {}
    assert speaker.language.next_invention_index == 0
    assert deceased.language.production == {}
    assert deceased.language.comprehension == {}
    assert deceased.language.next_invention_index == 0
    assert language_runtime_is_pristine(sim.state.language)
    assert dialect_runtime_is_pristine(sim.state.dialect)
    assert contact_runtime_is_pristine(sim.state.language_contact)


def test_reset_accepts_valid_enabled_dialect_runtime_and_restores_pristine():
    sim.reset_runtime_state()
    initialize_language_runtime(
        sim.state.language,
        33,
        coalition_dialect_influence_enabled=True,
    )
    sim.state.language.communication_attempt_count = 1
    sim.state.language.unknown_signal_count = 1
    sim.state.language.last_communication_tick = 1
    sim.state.dialect.same_coalition_communication_count = 1
    sim.state.dialect.same_coalition_rate_application_count = 1
    sim.state.dialect.last_classification_tick = 1

    sim.reset_runtime_state()

    assert language_runtime_is_pristine(sim.state.language)
    assert dialect_runtime_is_pristine(sim.state.dialect)


def test_malformed_contact_metadata_blocks_reset_before_mutation():
    sim.reset_runtime_state()
    inhabitant = reset_inhabitant("Malformed Contact", 1)
    signal = Signal((1, 3))
    inhabitant.language.comprehension[(signal, Meaning.FOOD)] = (
        LexicalAssociation(
            meaning=Meaning.FOOD,
            signal=signal,
            confidence=0.50,
            observation_count=1,
            last_used_tick=1,
            origin=AssociationOrigin.LEARNED,
            learned_from_id=2,
            contact_exposure=ContactExposure(1, 2, 99, 2, 0),
        )
    )
    sim.people.append(inhabitant)
    list.append(sim.event_log, "reset sentinel")
    initialize_language_runtime(
        sim.state.language,
        88,
        language_contact_enabled=True,
    )
    contact_config = sim.config.LanguageContactConfig(True, 1.50, 3, 0.50)
    initialize_language_contact_runtime(
        sim.state.language_contact,
        contact_config,
    )
    before = copy.deepcopy((
        inhabitant.language,
        sim.state.language,
        sim.state.language_contact,
        tuple(sim.event_log),
    ))

    try:
        with pytest.raises(LanguageInvariantError, match="exposures exceed"):
            sim.reset_runtime_state()

        assert (
            inhabitant.language,
            sim.state.language,
            sim.state.language_contact,
            tuple(sim.event_log),
        ) == before
    finally:
        inhabitant.language = AgentLanguageState()
        sim.reset_runtime_state()


def test_reset_rejects_hidden_disabled_dialect_state_before_mutation():
    resident = reset_inhabitant("Resident", 0)
    before = seed_failed_reset_state([resident])
    sim.state.dialect.same_coalition_communication_count = 1
    sim.state.dialect.last_classification_tick = 1
    before["dialect_runtime"] = copy.deepcopy(sim.state.dialect)

    try:
        with pytest.raises(LanguageInvariantError) as exc_info:
            sim.reset_runtime_state()

        assert exc_info.value.code == "nonpristine_dialect_runtime"
        assert_failed_reset_state_unchanged(before)
    finally:
        sim.state.dialect = CoalitionDialectRuntimeState()
        sim.reset_runtime_state()


def test_reset_missing_language_attribute_fails_before_any_mutation():
    invalid = reset_inhabitant("Missing", 0)
    invalid.relationships[1] = object()
    relationship_before = dict(invalid.relationships)
    del invalid.language
    before = seed_failed_reset_state([invalid])

    try:
        with pytest.raises(LanguageInvariantError) as exc_info:
            sim.reset_runtime_state()

        assert exc_info.value.code == "missing_reset_agent_language_state"
        assert_failed_reset_state_unchanged(before)
        assert invalid.relationships == relationship_before
        assert not hasattr(invalid, "language")
    finally:
        invalid.language = AgentLanguageState()
        sim.reset_runtime_state()


@pytest.mark.parametrize(
    ("invalid_language", "expected_code"),
    [
        (None, "invalid_agent_language_state"),
        (LanguageRuntimeState(), "invalid_agent_language_state"),
        (AgentLanguageState(next_invention_index=True), "invalid_invention_index"),
    ],
)
def test_reset_none_wrong_type_and_malformed_language_fail_closed(
    invalid_language,
    expected_code,
):
    invalid = reset_inhabitant("Invalid", 0)
    invalid.language = invalid_language
    invalid.relationships[1] = object()
    relationship_before = dict(invalid.relationships)
    before = seed_failed_reset_state([invalid])

    try:
        with pytest.raises(LanguageInvariantError) as exc_info:
            sim.reset_runtime_state()

        assert exc_info.value.code == expected_code
        assert_failed_reset_state_unchanged(before)
        assert invalid.language is invalid_language
        assert invalid.relationships == relationship_before
    finally:
        invalid.language = AgentLanguageState()
        sim.reset_runtime_state()


def test_invalid_dead_language_blocks_reset_before_living_state_changes():
    living = reset_inhabitant("Living", 0)
    signal = Signal((2, 3))
    living.language.production[(Meaning.FOOD, signal)] = LexicalAssociation(
        meaning=Meaning.FOOD,
        signal=signal,
        confidence=0.5,
    )
    living_before = copy.deepcopy(living.language)
    invalid_dead = reset_inhabitant("Invalid Dead", 1)
    invalid_dead.language = None
    before = seed_failed_reset_state([living], [invalid_dead])

    try:
        with pytest.raises(LanguageInvariantError):
            sim.reset_runtime_state()

        assert_failed_reset_state_unchanged(before)
        assert living.language == living_before
        assert invalid_dead.language is None
    finally:
        invalid_dead.language = AgentLanguageState()
        sim.reset_runtime_state()


def test_late_invalid_language_cannot_partially_clear_earlier_owners():
    first = reset_inhabitant("First", 0)
    second = reset_inhabitant("Second", 1)
    invalid = reset_inhabitant("Late Invalid", 2)
    signal = Signal((3, 4))
    first.language.production[(Meaning.WOOD, signal)] = LexicalAssociation(
        meaning=Meaning.WOOD,
        signal=signal,
        confidence=0.5,
    )
    second.language.next_invention_index = 4
    first.relationships[1] = object()
    first_language_before = copy.deepcopy(first.language)
    second_language_before = copy.deepcopy(second.language)
    first_relationships_before = dict(first.relationships)
    invalid.language = object()
    before = seed_failed_reset_state([first, second, invalid])

    try:
        with pytest.raises(LanguageInvariantError):
            sim.reset_runtime_state()

        assert_failed_reset_state_unchanged(before)
        assert first.language == first_language_before
        assert second.language == second_language_before
        assert first.relationships == first_relationships_before
    finally:
        invalid.language = AgentLanguageState()
        sim.reset_runtime_state()


def test_duplicate_reset_owner_is_validated_and_cleared_once(monkeypatch):
    sim.reset_runtime_state()
    inhabitant = reset_inhabitant("Duplicate", 0)
    signal = Signal((4, 5))
    inhabitant.language.production[(Meaning.ORE, signal)] = LexicalAssociation(
        meaning=Meaning.ORE,
        signal=signal,
        confidence=0.5,
    )
    inhabitant.language.next_invention_index = 1
    sim.people.append(inhabitant)
    sim.all_dead.append(inhabitant)
    real_validation = sim.validate_agent_language_state
    validation_calls = 0

    def counted_validation(*args, **kwargs):
        nonlocal validation_calls
        validation_calls += 1
        return real_validation(*args, **kwargs)

    monkeypatch.setattr(sim, "validate_agent_language_state", counted_validation)

    sim.reset_runtime_state()

    assert validation_calls == 1
    assert inhabitant.language == AgentLanguageState()
    assert sim.people == []
    assert sim.all_dead == []


def test_reset_runtime_state_invalidates_prior_journal_tokens():
    message = "Tick 0001: reset-generation observation"
    sim.reset_runtime_state()
    sim.event_log.begin_observation_tick(1)
    stale = sim.event_log.append(message)

    sim.reset_runtime_state()
    sim.event_log.begin_observation_tick(1)
    current = sim.event_log.append(message)

    with pytest.raises(JournalClaimError, match="reset generation"):
        sim.emit_event(
            sim.event_log,
            tick=1,
            event_type="world_event",
            detail="stale",
            message=message,
            append_text=False,
            journal_token=stale,
        )
    sim.emit_event(
        sim.event_log,
        tick=1,
        event_type="world_event",
        detail="current",
        message=message,
        append_text=False,
        journal_token=current,
    )
    assert sim.event_log.drain_observation_journal()[0]["event"].detail == "current"
    sim.reset_runtime_state()


def test_same_seed_is_repeatable_in_one_process(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "thalren-vale",
            "--seed",
            "321",
            "--ticks",
            "5",
            "--condition",
            "repeatable",
            "--disable-antistag",
        ],
    )

    metrics_path = tmp_path / "data" / "metrics_repeatable_seed_321.csv"

    sim.run()
    first_metrics = metrics_path.read_text(encoding="utf-8")

    sim.run()
    second_metrics = metrics_path.read_text(encoding="utf-8")

    assert second_metrics == first_metrics


# ── Inhabitant naming capacity ──────────────────────────────────────────────

def test_traveler_names_do_not_run_out():
    """Naming must not cap how many inhabitants a run can ever produce.

    Generation suffixes used to stop at 9, so `len(NAMES) * 9` names existed in
    total. The two birth paths build their `used` set from the living *and* the
    dead, so that was a ceiling on lifetime inhabitants rather than on
    concurrent ones. On reaching it `_make_traveler_name` returned None and the
    callers broke out of procreation, which stopped births permanently and
    killed the population off. Anti-stagnation hid it by spawning from a pool
    that only excluded the living.
    """
    used = set()
    for _ in range(len(sim.NAMES) * 9 + 500):
        name = sim._make_traveler_name(used)
        assert name is not None, (
            f"naming exhausted after {len(used)} names")
        assert name not in used, f"duplicate name issued: {name}"
        used.add(name)


def test_names_below_the_old_ceiling_are_unchanged():
    """The fix must not renumber inhabitants in runs that never hit the cap."""
    used = set()
    produced = []
    for _ in range(len(sim.NAMES) * 9):
        name = sim._make_traveler_name(used)
        used.add(name)
        produced.append(name)

    assert produced[0] == sim.NAMES[0]
    assert produced[len(sim.NAMES)] == f"{sim.NAMES[0]}2"
    assert produced[-1] == f"{sim.NAMES[-1]}9"
    assert len(set(produced)) == len(sim.NAMES) * 9


def test_naming_continues_past_the_old_ceiling():
    used = {n for n in sim.NAMES}
    used |= {f"{n}{gen}" for gen in range(2, 10) for n in sim.NAMES}
    assert sim._make_traveler_name(used) == f"{sim.NAMES[0]}10"


def test_dead_names_are_never_reissued():
    """Trust, memory, and grievance are name-keyed.

    Recycling a dead inhabitant's name would hand its social history to a
    newborn, so the birth paths pass the living and the dead and naming must
    respect that.
    """
    dead = {sim.NAMES[0]}
    issued = set()
    for _ in range(20):
        name = sim._make_traveler_name(dead | issued)
        issued.add(name)
    assert sim.NAMES[0] not in issued


def test_empty_name_pool_reports_failure_instead_of_hanging(monkeypatch):
    """The unbounded suffix loop must not spin when there is nothing to suffix."""
    monkeypatch.setattr(sim, "NAMES", [])
    assert sim._make_traveler_name(set()) is None
