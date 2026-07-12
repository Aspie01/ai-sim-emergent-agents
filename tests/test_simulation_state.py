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
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Signal,
    initialize_language_runtime,
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
