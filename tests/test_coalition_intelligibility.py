"""Coalition formation gated on mutual intelligibility."""

from __future__ import annotations

import contextlib
import io
import random

import pytest

import run_experiments
from thalren_vale import economy, world
from thalren_vale.coalitions import (
    build_qualifying_reciprocal_graph,
    transition_informal_coalitions,
)
from thalren_vale.config import (
    COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS,
    COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COEVOLUTION,
    SimulationConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    initialize_language_coevolution_runtime,
    initialize_language_runtime,
)
from thalren_vale.social import Relationship
from thalren_vale.state import SimulationState


def qualified(**overrides) -> Relationship:
    """A tie clearing every non-intelligibility coalition threshold."""
    record = Relationship(
        trust=0.5, familiarity=0.6, grievance=0.0, interaction_count=4,
        last_interaction_tick=1)
    for name, value in overrides.items():
        setattr(record, name, value)
    return record


def person(inhabitant_id: int, relationships) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.language = AgentLanguageState()
    result.relationships.update(relationships)
    return result


def coalition_config(**overrides):
    config = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        coalition_emergence_enabled=True, **overrides)
    config.validate()
    return config


# ── Edge qualification ──────────────────────────────────────────────────────

def _edge_count(threshold, first_value, second_value):
    config = coalition_config()
    people = [
        person(0, {1: qualified(intelligibility=first_value)}),
        person(1, {0: qualified(intelligibility=second_value)}),
    ]
    graph = build_qualifying_reciprocal_graph(
        people, tick=1, config=config.coalition_config,
        intelligibility_threshold=threshold)
    return graph.edge_count


def test_ungated_qualification_ignores_intelligibility():
    """With no threshold the graph must be exactly as it was before v2."""
    assert _edge_count(None, 0.0, 0.0) == 1
    assert _edge_count(None, -1.0, -1.0) == 1


def test_both_directions_must_clear_the_threshold():
    assert _edge_count(0.10, 0.5, 0.5) == 1
    assert _edge_count(0.10, 0.5, 0.0) == 0
    assert _edge_count(0.10, 0.0, 0.5) == 0


def test_silence_never_counts_as_understanding():
    """A pair that never communicated sits at exactly 0.0.

    The threshold is strictly positive by configuration, so an untested pair
    cannot coalesce on the strength of never having failed.
    """
    assert _edge_count(0.0001, 0.0, 0.0) == 0


def test_mutual_unintelligibility_removes_the_edge():
    assert _edge_count(0.10, -0.5, -0.5) == 0


def test_threshold_boundary_is_inclusive():
    assert _edge_count(0.10, 0.10, 0.10) == 1
    assert _edge_count(0.10, 0.0999, 0.10) == 0


def test_gating_cannot_admit_a_tie_the_base_thresholds_reject():
    """Intelligibility narrows qualification; it never widens it."""
    config = coalition_config()
    people = [
        person(0, {1: qualified(trust=0.0, intelligibility=1.0)}),
        person(1, {0: qualified(trust=0.0, intelligibility=1.0)}),
    ]
    graph = build_qualifying_reciprocal_graph(
        people, tick=1, config=config.coalition_config,
        intelligibility_threshold=0.10)
    assert graph.edge_count == 0


# ── Dependency cascade ──────────────────────────────────────────────────────

def test_gating_without_either_dependency_emits_both_notices():
    config = SimulationConfig(coalition_intelligibility_enabled=True)
    config.validate()
    assert config.coalition_intelligibility_enabled is False
    notices = config.coalition_intelligibility_control_notices
    assert COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS in notices
    assert COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COEVOLUTION in notices
    assert list(notices) == sorted(notices)


def test_gating_without_coevolution_emits_one_notice():
    config = SimulationConfig(
        social_memory_enabled=True, coalition_emergence_enabled=True,
        coalition_intelligibility_enabled=True)
    config.validate()
    assert config.coalition_intelligibility_enabled is False
    notices = config.coalition_intelligibility_control_notices
    assert COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COEVOLUTION in notices
    assert COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS not in notices


def test_fully_satisfied_dependencies_keep_gating_enabled():
    config = coalition_config(
        language_evolution_enabled=True, language_coevolution_enabled=True,
        coalition_intelligibility_enabled=True)
    assert config.coalition_intelligibility_enabled is True
    assert config.coalition_intelligibility_control_notices == ()


@pytest.mark.parametrize("threshold", [0.0, -0.1, 1.5, 1, True, None])
def test_config_rejects_invalid_thresholds(threshold):
    with pytest.raises(ValueError):
        config = SimulationConfig(
            coalition_intelligibility_threshold=threshold)
        config.validate()


# ── End-to-end emergent behaviour ───────────────────────────────────────────

def _run(threshold, ticks=260):
    """Drive economy and coalition maintenance in the real tick order."""
    random.seed(42)
    world.reseed_world()
    config = coalition_config(
        language_evolution_enabled=True, language_coevolution_enabled=True,
        coalition_intelligibility_enabled=threshold is not None,
        coalition_intelligibility_threshold=(
            threshold if threshold is not None else 0.50))
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, language_coevolution_enabled=True)
    initialize_language_coevolution_runtime(
        state.language_coevolution, config.language_coevolution_config)

    people = []
    for index in range(12):
        inhabitant = person(index, {})
        inhabitant.inventory = {
            'food': 0, 'wood': 0, 'ore': 0, 'stone': 0, 'water': 0}
        people.append(inhabitant)
    state.next_inhabitant_id = len(people)
    state.people.extend(people)

    event_log: list = []
    first_tick = None
    with contextlib.redirect_stdout(io.StringIO()):
        for tick in range(1, ticks):
            for index, inhabitant in enumerate(people):
                inhabitant.inventory['food' if index % 2 == 0 else 'wood'] = 4
                inhabitant.inventory['wood' if index % 2 == 0 else 'food'] = 0
            economy.economy_tick(
                people, [], tick, event_log,
                social_config=config.social_memory_config,
                language_config=config.language_evolution_config,
                language_runtime=state.language,
                coevolution_config=config.language_coevolution_config,
                coevolution_runtime=state.language_coevolution,
                raids_enabled=False)
            state.coalitions = transition_informal_coalitions(
                people, state.coalitions, tick=tick,
                config=config.coalition_config,
                intelligibility_threshold=threshold)
            if first_tick is None and state.coalitions.active_coalitions:
                first_tick = tick
    return state, first_tick


def test_raising_the_threshold_monotonically_narrows_the_graph():
    """More demanding intelligibility must never admit more edges."""
    counts = [
        _run(threshold)[0].coalitions.last_qualifying_reciprocal_edge_count
        for threshold in (None, 0.10, 0.50, 0.95)
    ]
    assert counts == sorted(counts, reverse=True), counts
    assert counts[0] > counts[-1]


def test_a_demanding_threshold_delays_coalescence():
    """Coalitions cannot form until a shared language has emerged."""
    _ungated, ungated_tick = _run(None)
    _gated, gated_tick = _run(0.50)
    assert ungated_tick is not None
    assert gated_tick is not None
    assert gated_tick > ungated_tick


def test_an_unreachable_threshold_prevents_coalescence_entirely():
    state, first_tick = _run(0.95)
    assert first_tick is None
    assert not state.coalitions.active_coalitions
    assert state.coalitions.candidate_formation_count == 0


def test_disabled_gating_reproduces_ungated_coalition_state():
    """The feature must be inert until it is switched on."""
    disabled, disabled_tick = _run(None)
    assert disabled_tick is not None
    assert disabled.coalitions.candidate_formation_count > 0


# ── Runner containment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argument", [
    "--enable-coalition-intelligibility",
    "--disable-coalition-intelligibility",
    "--coalition-intelligibility-threshold",
    "--coalition-intelligibility-threshold=0.5",
    "--enable-coalition-intel",
    "--coalition-intelligibility",
])
def test_runner_rejects_the_complete_gating_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_coalition_intelligibility_args(
            (argument,))


@pytest.mark.parametrize("argument", [
    "--ticks=10", "--seed=1", "--enable-social-memory",
])
def test_runner_still_accepts_unrelated_options(argument):
    run_experiments._reject_uncontracted_coalition_intelligibility_args(
        (argument,))


# ── Artifact validation ─────────────────────────────────────────────────────

def collect(config: dict):
    from thalren_vale.artifact_validation import (
        _IssueCollector,
        _validate_coalition_intelligibility_configuration,
    )

    issues = _IssueCollector()
    _validate_coalition_intelligibility_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = coalition_config(
        language_evolution_enabled=True, language_coevolution_enabled=True,
        coalition_intelligibility_enabled=True)
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"coalition_intelligibility_enabled": True,
     "coalition_emergence_enabled": False},
    {"coalition_intelligibility_enabled": True,
     "language_coevolution_enabled": False},
    {"coalition_intelligibility_threshold": 0.0},
    {"coalition_intelligibility_threshold": 1.5},
    {"coalition_intelligibility_threshold": 1},
    {"coalition_intelligibility_controls_status": "bogus"},
    {"coalition_intelligibility_threshold": 0.4,
     "coalition_intelligibility_controls_status": "disabled"},
    {"coalition_intelligibility_controls_status": "normalized_uncontracted",
     "coalition_intelligibility_control_notices": []},
    {"coalition_intelligibility_control_notices": [
        COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS] * 2},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)


def test_nondefault_gating_controls_are_not_v2_ready():
    from thalren_vale.artifact_validation import _readiness_issues

    config = SimulationConfig(coalition_intelligibility_threshold=0.4)
    config.validate()
    issues = _readiness_issues(
        {"configuration": config.manifest_dict()}, None)
    codes = {issue.code for issue in issues}
    assert "coalition_intelligibility_controls_not_v2_ready" in codes


# ── sim.py wiring ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("enabled, expected", [
    (True, 0.35),
    (False, None),
])
def test_maintenance_supplies_the_threshold_only_when_gating_is_effective(
    monkeypatch, enabled, expected,
):
    """The tick loop must pass the configured threshold through.

    Testing `transition_informal_coalitions` directly does not cover this:
    the maintenance call site has to derive the value from run config and
    supply `None` when gating is off, or the feature never engages in a real
    run despite every unit test passing.
    """
    from thalren_vale import sim

    captured = {}

    def fake_transition(people, current_state, **kwargs):
        captured.update(kwargs)
        return current_state

    monkeypatch.setattr(sim, "transition_informal_coalitions", fake_transition)
    monkeypatch.setattr(sim, "maintain_relationships", lambda *a, **k: None)

    # Maintenance continues into language upkeep after the coalition step, so
    # the module-level state needs an initialized language runtime.
    fresh = SimulationState()
    initialize_language_runtime(
        fresh.language, 42, language_coevolution_enabled=True)
    initialize_language_coevolution_runtime(
        fresh.language_coevolution,
        coalition_config(
            language_evolution_enabled=True,
            language_coevolution_enabled=True,
        ).language_coevolution_config)
    monkeypatch.setattr(sim, "state", fresh)

    run_config = coalition_config(
        language_evolution_enabled=True, language_coevolution_enabled=True,
        coalition_intelligibility_enabled=enabled,
        coalition_intelligibility_threshold=0.35 if enabled else 0.50)

    sim.maintain_emergent_state(1, [], run_config)

    assert "intelligibility_threshold" in captured
    assert captured["intelligibility_threshold"] == expected
