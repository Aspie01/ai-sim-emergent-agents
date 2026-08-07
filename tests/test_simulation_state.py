"""Tests for explicit simulation state ownership and lifecycle."""

import ast
import copy
import importlib
import pathlib
import sys

import pytest

from thalren_vale import (
    combat,
    diplomacy,
    display,
    economy,
    factions,
    mythology,
    religion,
    sim,
)
from thalren_vale.events import JournalClaimError
from thalren_vale.coalitions import (
    CoalitionCandidate,
    CoalitionRuntimeState,
    InformalCoalition,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.state import SimulationState
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


# ── State ownership tables ──────────────────────────────────────────────────

# Every mutable collection `SimulationState` owns, mapped to the module global
# that aliases it. `state.reset()` clears each one *in place* rather than
# rebinding it, precisely so these aliases survive repeated in-process runs; a
# store that is rebound instead silently detaches its layer from the run.
#
# The table is enumerated rather than derived because the owning attribute
# names do not follow one convention (`factions.RIVALRIES`,
# `diplomacy._treaties`, `sim._key_events_archive`).
# `test_every_state_owned_collection_is_declared` keeps it from falling behind.
STATE_COLLECTION_ALIASES = {
    "people": (sim, "people"),
    "factions": (sim, "factions"),
    "all_dead": (sim, "all_dead"),
    "event_log": (sim, "event_log"),
    "loaded_plugins": (sim, "_loaded_plugins"),
    "era_summaries": (sim, "era_summaries"),
    "key_events_archive": (sim, "_key_events_archive"),
    "dead_factions": (sim, "_dead_factions"),
    "active_wars": (combat, "active_wars"),
    "war_history": (combat, "war_history"),
    "rivalries": (factions, "RIVALRIES"),
    "treaties": (diplomacy, "_treaties"),
    "treaty_log": (diplomacy, "treaty_log"),
    "reputation": (diplomacy, "_reputation"),
    "faction_currencies": (economy, "faction_currencies"),
    "faction_prices": (economy, "faction_prices"),
    "price_history": (economy, "price_history"),
    "trade_routes": (economy, "trade_routes"),
    "raid_log": (economy, "raid_log"),
    "scarcity_events": (economy, "scarcity_events"),
    "religions": (religion, "_religions"),
    "holy_wars": (religion, "_HOLY_WARS"),
}

# Collections whose contents are validated during reset, or that are not a
# plain list, so the generic seeder below cannot fill them with a sentinel.
MANUALLY_SEEDED_COLLECTIONS = frozenset({"people", "all_dead", "event_log"})

# Run-scoped globals that `SimulationState` does *not* own, so `state.reset()`
# cannot clear them and `reset_runtime_state` has to clear each one by hand.
# That hand-written list is exactly the kind that falls behind a new store, so
# enumerate it here: (module, attribute, dirty value, value after reset).
RESET_MODULE_GLOBALS = (
    (sim, "_last_dynamic_t", 5, 0),
    (combat, "_alliances", {"reset probe": ["probe"]}, {}),
    (factions, "_ra_tracker", "reset probe", None),
    (economy, "_last_shock_res", "reset probe", ""),
    (diplomacy, "_faction_propose_cd", {"reset probe": 1}, {}),
    (diplomacy, "_faction_break_cd", {"reset probe": 1}, {}),
    (diplomacy, "_last_neg_tick", {"reset probe": 1}, {}),
    (diplomacy, "_ra_tracker", "reset probe", None),
    (mythology, "chronicles", ["reset probe"], []),
    (mythology, "faction_myths", {"reset probe": ["probe"]}, {}),
    (mythology, "epitaphs", {"reset probe": "probe"}, {}),
    (mythology, "_epitaphed", {"reset probe"}, set()),
    (mythology, "_myth_last_t", {"reset probe": 1}, {}),
    (mythology, "_last_chr_t", 5, 0),
    (mythology, "_llm_fired", True, False),
    (display, "_FACT_ABBREV", {"reset probe": "probe"}, {}),
)


def _seed_state_collection(field_name: str) -> None:
    """Put one recognisable entry into a state-owned collection."""
    store = getattr(sim.state, field_name)
    if isinstance(store, dict):
        store["reset probe"] = "reset probe"
    elif isinstance(store, set):
        store.add("reset probe")
    else:
        list.append(store, "reset probe")


def _seed_module_global(module, attribute: str, dirty) -> None:
    """Dirty one module global, mutating containers rather than rebinding.

    Rebinding would hand `reset_runtime_state` a different object from the one
    the owning layer holds, so a reset that cleared nothing would still look
    clean here.
    """
    current = getattr(module, attribute)
    if isinstance(current, dict):
        current.update(dirty)
    elif isinstance(current, set):
        current.update(dirty)
    elif isinstance(current, list):
        current.extend(dirty)
    else:
        setattr(module, attribute, dirty)


def _sim_tree() -> ast.Module:
    source = (
        pathlib.Path(sim.__file__).read_text(encoding="utf-8-sig"))
    return ast.parse(source)


def _sim_module_aliases() -> dict[str, object]:
    """Map every ``from . import x [as y]`` alias in sim.py to its module."""
    aliases: dict[str, object] = {}
    for node in ast.walk(_sim_tree()):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 1 or node.module:
            continue
        for entry in node.names:
            aliases[entry.asname or entry.name] = importlib.import_module(
                f"thalren_vale.{entry.name}")
    return aliases


def _reset_touched_module_globals() -> set[tuple[str, str]]:
    """Return every ``(module, attribute)`` `reset_runtime_state` clears.

    Derived from the source rather than declared, so `RESET_MODULE_GLOBALS`
    cannot quietly fall behind a newly added store.
    """
    aliases = _sim_module_aliases()
    for node in ast.walk(_sim_tree()):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "reset_runtime_state"
        ):
            reset = node
            break
    else:
        raise AssertionError("sim.py defines no reset_runtime_state")

    rebound_globals = {
        name
        for statement in ast.walk(reset)
        if isinstance(statement, ast.Global)
        for name in statement.names
    }
    touched: set[tuple[str, str]] = set()
    for statement in ast.walk(reset):
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in aliases
                ):
                    touched.add(
                        (aliases[target.value.id].__name__, target.attr))
                elif (
                    isinstance(target, ast.Name)
                    and target.id in rebound_globals
                ):
                    touched.add((sim.__name__, target.id))
        elif isinstance(statement, ast.Call):
            call = statement.func
            if (
                isinstance(call, ast.Attribute)
                and call.attr == "clear"
                and isinstance(call.value, ast.Attribute)
                and isinstance(call.value.value, ast.Name)
                and call.value.value.id in aliases
            ):
                touched.add(
                    (aliases[call.value.value.id].__name__, call.value.attr))
    return touched


def test_every_hand_cleared_module_global_is_declared():
    """`RESET_MODULE_GLOBALS` must not fall behind `reset_runtime_state`.

    A store `SimulationState` does not own is only cleared because someone
    remembered to add a line to `reset_runtime_state`. Nothing else notices a
    line that was never added, or one whose store the reset guard below never
    seeds, so compare the declared list against the source itself.
    """
    declared = {
        (module.__name__, attribute)
        for module, attribute, _, _ in RESET_MODULE_GLOBALS
    }
    touched = _reset_touched_module_globals()
    undeclared = sorted(touched - declared)
    stale = sorted(declared - touched)
    assert not undeclared, (
        f"globals reset_runtime_state clears but nothing checks: {undeclared}")
    assert not stale, (
        f"declared globals reset_runtime_state no longer clears: {stale}")


def test_every_state_owned_collection_is_declared():
    """`STATE_COLLECTION_ALIASES` must not fall behind `SimulationState`.

    A collection missing from the table is a store nothing proves is shared
    with its layer and nothing proves `reset_runtime_state` clears, which is
    how a store leaks across in-process runs unnoticed.
    """
    owned = {
        name
        for name, spec in SimulationState.__dataclass_fields__.items()
        if spec.default_factory in (list, dict, set)
    }
    undeclared = sorted(owned - set(STATE_COLLECTION_ALIASES))
    stale = sorted(set(STATE_COLLECTION_ALIASES) - owned)
    assert not undeclared, f"state collections with no alias entry: {undeclared}"
    assert not stale, f"alias entries with no state collection: {stale}"


@pytest.mark.parametrize("field_name", sorted(STATE_COLLECTION_ALIASES))
def test_domain_modules_share_state_owned_collections(field_name):
    module, attribute = STATE_COLLECTION_ALIASES[field_name]
    assert getattr(module, attribute) is getattr(sim.state, field_name), (
        f"{module.__name__}.{attribute} is no longer "
        f"state.{field_name}; reset will not reach it")


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
    sim.state.coalitions.split_event_count = 2
    sim.state.coalitions.split_child_count = 4
    sim.state.coalitions.dissolution_count = 1
    sim.state.coalitions.last_qualifying_reciprocal_edge_count = 9
    sim.state.next_inhabitant_id = 41
    # Every remaining owned collection and hand-cleared global, so the guard
    # covers the whole reset surface rather than the handful seeded above.
    for name in sorted(
        set(STATE_COLLECTION_ALIASES) - MANUALLY_SEEDED_COLLECTIONS
    ):
        _seed_state_collection(name)
    for module, attribute, dirty, _ in RESET_MODULE_GLOBALS:
        _seed_module_global(module, attribute, dirty)

    sim.reset_runtime_state()

    for name, (module, attribute) in sorted(STATE_COLLECTION_ALIASES.items()):
        store = getattr(sim.state, name)
        assert len(store) == 0, f"state.{name} survived reset_runtime_state()"
        assert getattr(module, attribute) is store, (
            f"reset rebound {module.__name__}.{attribute} instead of "
            f"clearing state.{name} in place")
    for module, attribute, _, cleared in RESET_MODULE_GLOBALS:
        assert getattr(module, attribute) == cleared, (
            f"{module.__name__}.{attribute} survived reset_runtime_state()")
    assert sim.state.next_inhabitant_id == 0
    # Compared whole rather than field by field so a new coalition counter is
    # covered on the day it is added.
    assert sim.state.coalitions == CoalitionRuntimeState()
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
