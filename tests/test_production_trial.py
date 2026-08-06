"""Occasional runner-up production, breaking the adoption deadlock."""

from __future__ import annotations

import os
import random
import subprocess
import sys
import textwrap

import pytest

import run_experiments
import thalren_vale.language as language_module
from thalren_vale import world
from thalren_vale.config import (
    PRODUCTION_TRIAL_NOTICE_WITHOUT_LANGUAGE,
    LanguageEvolutionConfig,
    ProductionTrialConfig,
    SimulationConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    CommunicationContext,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Signal,
    _select_trial_production,
    communicate,
    initialize_language_runtime,
)

LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 250, True)
TRIAL = ProductionTrialConfig(True, 8)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def person(inhabitant_id: int) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.language = AgentLanguageState()
    return result


def runtime(seed: int = 42) -> LanguageRuntimeState:
    result = LanguageRuntimeState()
    initialize_language_runtime(result, seed)
    return result


def give(state: AgentLanguageState, tokens, confidence, meaning=Meaning.FOOD):
    signal = Signal(tuple(tokens))
    state.production[(meaning, signal)] = LexicalAssociation(
        meaning=meaning, signal=signal, confidence=confidence,
        last_used_tick=1)
    return signal


# ── Candidate requirements ──────────────────────────────────────────────────

def test_a_single_form_is_never_trialed():
    """With no runner-up there is nothing to try."""
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    assert all(
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=2) is None
        for tick in range(1, 60)
    )


def test_unusable_runner_up_is_not_a_candidate():
    """A form below the usable floor cannot be trialed."""
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    give(state, (4, 5, 6), language_module.MIN_USABLE_CONFIDENCE / 2)
    assert all(
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=2) is None
        for tick in range(1, 60)
    )


def test_trial_returns_the_runner_up_not_the_leader():
    state = AgentLanguageState()
    leader = give(state, (1, 2, 3), 0.9)
    runner_up = give(state, (4, 5, 6), 0.4)
    picked = {
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=2)
        for tick in range(1, 200)
    }
    picked.discard(None)
    signals = {association.signal for association in picked}
    assert signals == {runner_up}
    assert leader not in signals


def test_only_the_requested_meaning_is_considered():
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9, meaning=Meaning.FOOD)
    give(state, (4, 5, 6), 0.4, meaning=Meaning.ORE)
    assert all(
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=2) is None
        for tick in range(1, 60)
    )


# ── Determinism ─────────────────────────────────────────────────────────────

def test_trial_occasions_are_deterministic():
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    give(state, (4, 5, 6), 0.4)

    def occasions():
        return [
            _select_trial_production(
                state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
                tick=tick, trial_interval=8) is not None
            for tick in range(1, 300)
        ]

    first = occasions()
    random.seed(1234)
    [random.random() for _ in range(50)]
    assert first == occasions()


def test_trial_consumes_no_random_stream():
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    give(state, (4, 5, 6), 0.4)
    random.seed(99)
    before = random.getstate()
    for tick in range(1, 100):
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=8)
    assert random.getstate() == before


def test_speakers_do_not_trial_in_lockstep():
    """Occasions must differ per speaker, or trials would synchronise."""
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    give(state, (4, 5, 6), 0.4)
    patterns = {
        speaker: tuple(
            _select_trial_production(
                state, Meaning.FOOD, runtime=runtime(), speaker_id=speaker,
                tick=tick, trial_interval=8) is not None
            for tick in range(1, 200)
        )
        for speaker in range(6)
    }
    assert len(set(patterns.values())) > 1


@pytest.mark.parametrize("interval", [2, 8, 32])
def test_larger_intervals_trial_less_often(interval):
    state = AgentLanguageState()
    give(state, (1, 2, 3), 0.9)
    give(state, (4, 5, 6), 0.4)
    fired = sum(
        _select_trial_production(
            state, Meaning.FOOD, runtime=runtime(), speaker_id=7,
            tick=tick, trial_interval=interval) is not None
        for tick in range(1, 2000)
    )
    # Roughly 1-in-interval, with generous slack for digest granularity.
    assert 0 < fired < 2000 * (3.0 / interval)


# ── Communication integration ───────────────────────────────────────────────

def _emit(trial_config, ticks=60):
    rt = runtime()
    sender, receiver = person(7), person(9)
    give(sender.language, (1, 2, 3), 0.9)
    give(sender.language, (4, 5, 6), 0.4)
    emitted = []
    for tick in range(1, ticks):
        outcome = communicate(
            sender, receiver, Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER, tick=tick,
            active_ids=frozenset({7, 9}), config=LANGUAGE, runtime=rt,
            trial_config=trial_config)
        if outcome.produced_signal is not None:
            emitted.append(outcome.produced_signal.phoneme_ids)
    return emitted


def test_disabled_trials_never_emit_the_runner_up():
    assert (4, 5, 6) not in _emit(None)
    assert (4, 5, 6) not in _emit(ProductionTrialConfig(False, 8))


def test_enabled_trials_do_emit_the_runner_up():
    emitted = _emit(TRIAL)
    assert (4, 5, 6) in emitted
    # The leader must still dominate; this is variation, not replacement.
    assert emitted.count((1, 2, 3)) > emitted.count((4, 5, 6))


def test_trials_reach_the_contact_delegation():
    """`communicate` delegates to the contact variant and must forward this.

    The owner was dropped on exactly this edge, which silently disabled the
    feature for every contact-enabled run while all unit tests passed.
    """
    import inspect

    source = inspect.getsource(language_module.communicate)
    delegation = source[source.index("_communicate_with_contact("):]
    body = delegation[:delegation.index("\n        )")]
    assert "trial_config=trial_config" in body


# ── Dependency cascade ──────────────────────────────────────────────────────

def test_trials_without_language_normalize_with_a_notice():
    config = SimulationConfig(production_trial_enabled=True)
    config.validate()
    assert config.production_trial_enabled is False
    assert PRODUCTION_TRIAL_NOTICE_WITHOUT_LANGUAGE in (
        config.production_trial_control_notices)


def test_satisfied_dependency_keeps_trials_enabled():
    config = SimulationConfig(
        language_evolution_enabled=True, production_trial_enabled=True)
    config.validate()
    assert config.production_trial_enabled is True
    assert config.production_trial_control_notices == ()


@pytest.mark.parametrize("interval", [0, 1, -4, 128, True, 8.0, None])
def test_config_rejects_invalid_intervals(interval):
    with pytest.raises(ValueError):
        config = SimulationConfig(production_trial_interval=interval)
        config.validate()


# ── Hashing ─────────────────────────────────────────────────────────────────

def test_canonical_hash_is_independent_of_python_hash_seed():
    script = textwrap.dedent(
        """
        import random
        from thalren_vale import world
        from thalren_vale.config import SimulationConfig
        from thalren_vale.language import (
            AgentLanguageState, CommunicationContext, LexicalAssociation,
            Meaning, Signal, communicate, initialize_language_runtime)
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        random.seed(42)
        world.reseed_world()
        config = SimulationConfig(
            language_evolution_enabled=True, production_trial_enabled=True)
        config.validate()
        state = SimulationState()
        initialize_language_runtime(state.language, 42)
        people = []
        for identifier in (7, 9):
            person = Inhabitant("P" + str(identifier), 0, 0)
            person.inhabitant_id = identifier
            person.faction = None
            person.language = AgentLanguageState()
            state.people.append(person)
            people.append(person)
        for tokens, confidence in (((1, 2, 3), 0.9), ((4, 5, 6), 0.4)):
            signal = Signal(tokens)
            people[0].language.production[(Meaning.FOOD, signal)] = (
                LexicalAssociation(
                    meaning=Meaning.FOOD, signal=signal,
                    confidence=confidence, last_used_tick=1))
        state.next_inhabitant_id = 10
        for tick in range(1, 40):
            communicate(
                people[0], people[1], Meaning.FOOD,
                context=CommunicationContext.AID_TRANSFER, tick=tick,
                active_ids=frozenset({7, 9}),
                config=config.language_evolution_config,
                runtime=state.language,
                trial_config=config.production_trial_config)
        print(canonical_state_hash(
            state, world.world, config.manifest_dict()))
        """
    )

    def run(hash_seed: str) -> str:
        environment = dict(
            os.environ, PYTHONHASHSEED=hash_seed,
            PYTHONPATH=os.path.join(PROJECT_ROOT, "src"))
        completed = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
            timeout=120, env=environment, cwd=PROJECT_ROOT)
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    first = run("0")
    assert first
    assert first == run("7") == run("12345")


# ── Runner containment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argument", [
    "--enable-production-trial",
    "--disable-production-trial",
    "--production-trial-interval",
    "--production-trial-interval=8",
    "--enable-production",
    "--production-trial",
])
def test_runner_rejects_the_complete_trial_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_production_trial_args((argument,))


@pytest.mark.parametrize("argument", ["--ticks=10", "--seed=1", "--log-mode"])
def test_runner_still_accepts_unrelated_options(argument):
    run_experiments._reject_uncontracted_production_trial_args((argument,))


# ── Artifact validation ─────────────────────────────────────────────────────

def collect(config: dict):
    from thalren_vale.artifact_validation import (
        _IssueCollector, _validate_production_trial_configuration)

    issues = _IssueCollector()
    _validate_production_trial_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = SimulationConfig(
        language_evolution_enabled=True, production_trial_enabled=True)
    enabled.validate()
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"production_trial_enabled": True, "language_evolution_enabled": False},
    {"production_trial_interval": 1},
    {"production_trial_interval": 999},
    {"production_trial_interval": True},
    {"production_trial_controls_status": "bogus"},
    {"production_trial_interval": 4,
     "production_trial_controls_status": "disabled"},
    {"production_trial_controls_status": "normalized_uncontracted",
     "production_trial_control_notices": []},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)


def test_nondefault_trial_controls_are_not_v2_ready():
    from thalren_vale.artifact_validation import _readiness_issues

    config = SimulationConfig(production_trial_interval=4)
    config.validate()
    issues = _readiness_issues({"configuration": config.manifest_dict()}, None)
    assert "production_trial_controls_not_v2_ready" in {
        issue.code for issue in issues}
