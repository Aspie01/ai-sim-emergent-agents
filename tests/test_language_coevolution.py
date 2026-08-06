"""Mutual intelligibility fed back into partner choice, bounded and gated."""

from __future__ import annotations

from dataclasses import asdict
import contextlib
import io
import os
import random
import subprocess
import sys
import textwrap

import pytest

import run_experiments
from thalren_vale import economy, world
from thalren_vale.config import (
    LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS,
    LanguageCoevolutionConfig,
    LanguageEvolutionConfig,
    SimulationConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AgentLanguageState,
    LanguageCoevolutionRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    initialize_language_coevolution_runtime,
    initialize_language_runtime,
    language_coevolution_runtime_is_pristine,
    language_coevolution_runtime_record,
    language_coevolution_summary,
    record_intelligibility_outcome,
    validate_language_coevolution_config,
    validate_language_coevolution_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.social import (
    INTELLIGIBILITY_PREFERENCE_WEIGHT,
    Relationship,
    apply_intelligibility_feedback,
    relationship_preference_score,
    relationship_records,
)
from thalren_vale.state import SimulationState


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 250, True)
COEVOLUTION = LanguageCoevolutionConfig(True, 0.06, 0.04)
SOCIAL = SocialMemoryConfig(True, True, 8, 25)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIVE = frozenset({7, 9})


def person(inhabitant_id: int) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.language = AgentLanguageState()
    return result


def runtimes(seed: int = 42):
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime, seed, language_coevolution_enabled=True)
    coevolution_runtime = LanguageCoevolutionRuntimeState()
    initialize_language_coevolution_runtime(coevolution_runtime, COEVOLUTION)
    return language_runtime, coevolution_runtime


# ── Directed feedback ───────────────────────────────────────────────────────

def test_understanding_raises_both_directed_ties():
    sender, receiver = person(7), person(9)
    applied = apply_intelligibility_feedback(
        sender, receiver, understood=True, tick=1,
        reward=0.06, penalty=0.04, active_ids=ACTIVE)
    assert applied is True
    assert sender.relationships[9].intelligibility == pytest.approx(0.06)
    assert receiver.relationships[7].intelligibility == pytest.approx(0.06)


def test_misunderstanding_lowers_both_directed_ties():
    sender, receiver = person(7), person(9)
    apply_intelligibility_feedback(
        sender, receiver, understood=False, tick=1,
        reward=0.06, penalty=0.04, active_ids=ACTIVE)
    assert sender.relationships[9].intelligibility == pytest.approx(-0.04)
    assert receiver.relationships[7].intelligibility == pytest.approx(-0.04)


def test_feedback_is_symmetric_between_the_two_parties():
    sender, receiver = person(7), person(9)
    for tick, understood in enumerate([True, True, False, True], start=1):
        apply_intelligibility_feedback(
            sender, receiver, understood=understood, tick=tick,
            reward=0.06, penalty=0.04, active_ids=ACTIVE)
    assert (sender.relationships[9].intelligibility
            == receiver.relationships[7].intelligibility)


def test_intelligibility_is_clamped_to_the_unit_interval():
    sender, receiver = person(7), person(9)
    for tick in range(1, 200):
        apply_intelligibility_feedback(
            sender, receiver, understood=True, tick=tick,
            reward=0.25, penalty=0.25, active_ids=ACTIVE)
    assert sender.relationships[9].intelligibility == 1.0
    for tick in range(200, 400):
        apply_intelligibility_feedback(
            sender, receiver, understood=False, tick=tick,
            reward=0.25, penalty=0.25, active_ids=ACTIVE)
    assert sender.relationships[9].intelligibility == -1.0


def test_inactive_participants_are_skipped_without_mutation():
    sender, receiver = person(7), person(9)
    applied = apply_intelligibility_feedback(
        sender, receiver, understood=True, tick=1,
        reward=0.06, penalty=0.04, active_ids=frozenset({7}))
    assert applied is False
    assert not sender.relationships
    assert not receiver.relationships


def test_feedback_rejects_self_communication():
    only = person(7)
    with pytest.raises(ValueError):
        apply_intelligibility_feedback(
            only, only, understood=True, tick=1,
            reward=0.06, penalty=0.04, active_ids=ACTIVE)


@pytest.mark.parametrize("rate", [0.0, -0.1, 1.5, 1, True, None])
def test_feedback_rejects_invalid_rates(rate):
    sender, receiver = person(7), person(9)
    with pytest.raises((ValueError, TypeError)):
        apply_intelligibility_feedback(
            sender, receiver, understood=True, tick=1,
            reward=rate, penalty=0.04, active_ids=ACTIVE)


def test_feedback_rejects_a_nonboolean_outcome():
    sender, receiver = person(7), person(9)
    with pytest.raises(TypeError):
        apply_intelligibility_feedback(
            sender, receiver, understood=1, tick=1,
            reward=0.06, penalty=0.04, active_ids=ACTIVE)


# ── Partner preference coupling ─────────────────────────────────────────────

def test_zero_intelligibility_leaves_the_preference_score_unchanged():
    """The ungated preference term must not perturb pre-coevolution runs."""
    record = Relationship(
        trust=0.4, affinity=0.2, grievance=0.1, familiarity=0.3)
    baseline = round(
        0.65 * 0.4 + 0.25 * 0.3 + 0.10 * 0.2 - 0.50 * 0.1, 6)
    assert record.intelligibility == 0.0
    assert relationship_preference_score(record) == baseline


def test_positive_intelligibility_raises_the_preference_score():
    low = Relationship(trust=0.4, intelligibility=0.0)
    high = Relationship(trust=0.4, intelligibility=0.5)
    assert (relationship_preference_score(high)
            > relationship_preference_score(low))
    assert relationship_preference_score(high) == pytest.approx(
        relationship_preference_score(low)
        + INTELLIGIBILITY_PREFERENCE_WEIGHT * 0.5)


def test_negative_intelligibility_lowers_the_preference_score():
    neutral = Relationship(trust=0.4)
    poor = Relationship(trust=0.4, intelligibility=-0.5)
    assert (relationship_preference_score(poor)
            < relationship_preference_score(neutral))


# ── Runtime counters ────────────────────────────────────────────────────────

def test_fresh_runtime_is_pristine_and_initialization_freezes_rates():
    runtime = LanguageCoevolutionRuntimeState()
    assert language_coevolution_runtime_is_pristine(runtime)
    initialize_language_coevolution_runtime(runtime, COEVOLUTION)
    assert not language_coevolution_runtime_is_pristine(runtime)
    assert runtime.intelligibility_reward == COEVOLUTION.intelligibility_reward


def test_initialization_requires_an_enabled_config():
    with pytest.raises(LanguageInvariantError):
        initialize_language_coevolution_runtime(
            LanguageCoevolutionRuntimeState(),
            LanguageCoevolutionConfig(False, 0.06, 0.04))


def test_runtime_rejects_a_rate_mismatch():
    _language, runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        validate_language_coevolution_runtime(
            runtime, config=LanguageCoevolutionConfig(True, 0.2, 0.04))


def test_counters_partition_by_outcome():
    language_runtime, runtime = runtimes()
    for tick, (understood, applied) in enumerate(
        [(True, True), (False, True), (True, True), (False, False)], start=1
    ):
        record_intelligibility_outcome(
            runtime, config=COEVOLUTION,
            understood=understood, applied=applied, tick=tick)
    assert runtime.intelligibility_update_count == 3
    assert runtime.reinforcing_update_count == 2
    assert runtime.eroding_update_count == 1
    assert runtime.skipped_outcome_count == 1
    assert runtime.last_update_tick == 3


def test_skipped_outcomes_do_not_advance_the_update_tick():
    _language, runtime = runtimes()
    record_intelligibility_outcome(
        runtime, config=COEVOLUTION, understood=False, applied=False, tick=5)
    assert runtime.last_update_tick is None
    assert runtime.skipped_outcome_count == 1


@pytest.mark.parametrize("mutation", [
    {"intelligibility_update_count": 5},
    {"reinforcing_update_count": 5},
    {"eroding_update_count": 5},
])
def test_runtime_counter_partition_is_enforced(mutation):
    _language, runtime = runtimes()
    for name, value in mutation.items():
        setattr(runtime, name, value)
    with pytest.raises(LanguageInvariantError):
        validate_language_coevolution_runtime(runtime, config=COEVOLUTION)


def test_counter_update_rejects_a_disabled_config():
    _language, runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        record_intelligibility_outcome(
            runtime, config=LanguageCoevolutionConfig(False, 0.06, 0.04),
            understood=True, applied=True, tick=1)


# ── Config validation and dependency cascade ────────────────────────────────

@pytest.mark.parametrize("rate", [0.0, -0.01, 0.99, 1, True, None, "0.1"])
def test_config_rejects_invalid_rates(rate):
    with pytest.raises(LanguageInvariantError):
        validate_language_coevolution_config(
            LanguageCoevolutionConfig(True, rate, 0.04))


def test_config_rejects_a_nonboolean_gate():
    with pytest.raises(LanguageInvariantError):
        validate_language_coevolution_config(
            LanguageCoevolutionConfig(1, 0.06, 0.04))


def test_coevolution_without_language_normalizes_with_both_notices():
    config = SimulationConfig(language_coevolution_enabled=True)
    config.validate()
    assert config.language_coevolution_enabled is False
    notices = config.language_coevolution_control_notices
    assert LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE in notices
    assert LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS in notices
    assert list(notices) == sorted(notices)


def test_coevolution_without_partner_bias_normalizes_with_one_notice():
    config = SimulationConfig(
        language_evolution_enabled=True, language_coevolution_enabled=True)
    config.validate()
    assert config.language_coevolution_enabled is False
    notices = config.language_coevolution_control_notices
    assert LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS in notices
    assert LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE not in notices


def test_social_memory_alone_does_not_satisfy_the_dependency():
    config = SimulationConfig(
        social_memory_enabled=True,
        language_evolution_enabled=True,
        language_coevolution_enabled=True)
    config.validate()
    assert config.language_coevolution_enabled is False


def test_fully_satisfied_dependencies_keep_coevolution_enabled():
    config = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        language_evolution_enabled=True, language_coevolution_enabled=True)
    config.validate()
    assert config.language_coevolution_enabled is True
    assert config.language_coevolution_control_notices == ()


# ── Economy integration ─────────────────────────────────────────────────────

def _coevolution_economy_pass(*, enabled: bool, ticks: int = 200):
    """Drive a bounded economy pass with a stable two-way trade gradient."""
    random.seed(42)
    world.reseed_world()
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, language_coevolution_enabled=enabled)
    if enabled:
        initialize_language_coevolution_runtime(
            state.language_coevolution, COEVOLUTION)

    people = [person(index) for index in range(12)]
    for inhabitant in people:
        inhabitant.inventory = {
            'food': 0, 'wood': 0, 'ore': 0, 'stone': 0, 'water': 0}
    state.next_inhabitant_id = len(people)
    state.people.extend(people)

    event_log: list = []
    with contextlib.redirect_stdout(io.StringIO()):
        for tick in range(1, ticks):
            for index, inhabitant in enumerate(people):
                inhabitant.inventory['food' if index % 2 == 0 else 'wood'] = 4
                inhabitant.inventory['wood' if index % 2 == 0 else 'food'] = 0
            economy.economy_tick(
                people, [], tick, event_log,
                social_config=SOCIAL,
                language_config=LANGUAGE,
                language_runtime=state.language,
                coevolution_config=COEVOLUTION if enabled else None,
                coevolution_runtime=(
                    state.language_coevolution if enabled else None),
                raids_enabled=False,
            )
    return state, people


def test_coevolution_engages_through_the_economy_layer():
    state, _people = _coevolution_economy_pass(enabled=True)
    runtime = state.language_coevolution
    assert runtime.intelligibility_update_count > 0
    assert runtime.reinforcing_update_count > 0


def test_economy_pass_preserves_the_counter_partition():
    state, _people = _coevolution_economy_pass(enabled=True)
    runtime = state.language_coevolution
    assert runtime.intelligibility_update_count == (
        runtime.reinforcing_update_count + runtime.eroding_update_count)


def test_disabled_coevolution_leaves_every_tie_untouched():
    _state, people = _coevolution_economy_pass(enabled=False)
    values = [
        record.intelligibility
        for inhabitant in people
        for record in inhabitant.relationships.values()
    ]
    assert values, "the scenario must actually form ties"
    assert all(value == 0.0 for value in values)


def test_enabled_coevolution_produces_both_signs():
    """Reward and penalty must both be reachable, so ties can fragment."""
    _state, people = _coevolution_economy_pass(enabled=True)
    values = [
        record.intelligibility
        for inhabitant in people
        for record in inhabitant.relationships.values()
    ]
    assert any(value > 0.0 for value in values)
    assert any(value < 0.0 for value in values)


def test_feedback_changes_which_partners_are_chosen():
    """The loop must close: intelligibility alters later communication."""
    disabled_state, _ = _coevolution_economy_pass(enabled=False)
    enabled_state, _ = _coevolution_economy_pass(enabled=True)
    assert (
        disabled_state.language.communication_attempt_count
        != enabled_state.language.communication_attempt_count
        or disabled_state.language.successful_interpretation_count
        != enabled_state.language.successful_interpretation_count
    )


def _outcome(result):
    from thalren_vale.language import (
        CommunicationContext, CommunicationOutcome, Meaning)

    return CommunicationOutcome(
        tick=1, sender_id=7, receiver_id=9,
        context=CommunicationContext.AID_TRANSFER,
        intended_meaning=Meaning.FOOD,
        produced_signal=None, interpreted_meaning=None,
        result=result,
    )


def test_silence_carries_no_evidence_and_is_skipped():
    """NO_SIGNAL means nothing was said, not that understanding failed."""
    from thalren_vale.language import CommunicationResult

    _language, runtime = runtimes()
    sender, receiver = person(7), person(9)
    economy._apply_language_coevolution(
        sender, receiver,
        outcome=_outcome(CommunicationResult.NO_SIGNAL),
        t=1, active_ids=ACTIVE,
        coevolution_config=COEVOLUTION,
        coevolution_runtime=runtime,
    )
    assert not sender.relationships
    assert not receiver.relationships
    assert runtime.skipped_outcome_count == 1
    assert runtime.intelligibility_update_count == 0
    assert runtime.eroding_update_count == 0


@pytest.mark.parametrize("result_name, understood", [
    ("SUCCESS", True),
    ("MISUNDERSTANDING", False),
    ("UNKNOWN_SIGNAL", False),
])
def test_every_signalled_outcome_updates_the_tie(result_name, understood):
    from thalren_vale.language import CommunicationResult

    _language, runtime = runtimes()
    sender, receiver = person(7), person(9)
    economy._apply_language_coevolution(
        sender, receiver,
        outcome=_outcome(getattr(CommunicationResult, result_name)),
        t=1, active_ids=ACTIVE,
        coevolution_config=COEVOLUTION,
        coevolution_runtime=runtime,
    )
    assert runtime.intelligibility_update_count == 1
    assert runtime.skipped_outcome_count == 0
    expected = 0.06 if understood else -0.04
    assert sender.relationships[9].intelligibility == pytest.approx(expected)


def test_enabled_coevolution_requires_a_runtime():
    with pytest.raises(ValueError):
        economy._apply_language_coevolution(
            person(7), person(9),
            outcome=None, t=1, active_ids=ACTIVE,
            coevolution_config=COEVOLUTION,
            coevolution_runtime=None,
        )


def test_disabled_coevolution_rejects_a_stray_runtime():
    _language, runtime = runtimes()
    with pytest.raises(ValueError):
        economy._apply_language_coevolution(
            person(7), person(9),
            outcome=None, t=1, active_ids=ACTIVE,
            coevolution_config=LanguageCoevolutionConfig(False, 0.06, 0.04),
            coevolution_runtime=runtime,
        )


# ── Record and summary ──────────────────────────────────────────────────────

def test_runtime_record_exposes_rates_and_counters():
    language_runtime, runtime = runtimes()
    record = language_coevolution_runtime_record(
        runtime, config=COEVOLUTION, language_runtime=language_runtime)
    assert record["intelligibility_reward"] == 0.06
    assert record["last_update_tick"] is None
    assert set(record) == {
        "intelligibility_reward",
        "intelligibility_penalty",
        "intelligibility_update_count",
        "reinforcing_update_count",
        "eroding_update_count",
        "skipped_outcome_count",
        "last_update_tick",
    }


def test_summary_classifies_ties_without_mutating():
    language_runtime, runtime = runtimes()
    people = [person(index) for index in range(3)]
    people[0].relationships[1] = Relationship(intelligibility=0.5)
    people[0].relationships[2] = Relationship(intelligibility=-0.2)
    people[1].relationships[0] = Relationship(intelligibility=0.0)
    before = [
        {k: asdict(v) for k, v in p.relationships.items()} for p in people]
    summary = language_coevolution_summary(
        people, runtime=runtime, config=COEVOLUTION,
        language_runtime=language_runtime)
    assert summary["population"] == 3
    assert summary["directed_ties"] == 3
    assert summary["intelligible_ties"] == 1
    assert summary["unintelligible_ties"] == 1
    assert summary["neutral_ties"] == 1
    assert summary["carriers"] == 1
    assert [
        {k: asdict(v) for k, v in p.relationships.items()} for p in people
    ] == before


def test_summary_consumes_a_one_shot_iterable_exactly_once():
    language_runtime, runtime = runtimes()
    people = [person(index) for index in range(4)]
    summary = language_coevolution_summary(
        iter(people), runtime=runtime, config=COEVOLUTION,
        language_runtime=language_runtime)
    assert summary["population"] == 4


# ── Canonical hashing ───────────────────────────────────────────────────────

def _hash_state(intelligibility, updates=0):
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        language_evolution_enabled=True, language_coevolution_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, language_coevolution_enabled=True)
    initialize_language_coevolution_runtime(
        state.language_coevolution, config.language_coevolution_config)
    first, second = person(0), person(1)
    first.relationships[1] = Relationship(intelligibility=intelligibility)
    state.people.extend([first, second])
    state.next_inhabitant_id = 2
    state.language_coevolution.intelligibility_update_count = updates
    state.language_coevolution.reinforcing_update_count = updates
    return canonical_state_hash(state, world.world, config.manifest_dict())


def test_intelligibility_changes_the_canonical_hash():
    assert _hash_state(0.0) != _hash_state(0.5)


def test_runtime_counters_change_the_canonical_hash():
    assert _hash_state(0.0) != _hash_state(0.0, updates=4)


def test_relationship_records_omit_intelligibility_by_default():
    inhabitant = person(0)
    inhabitant.relationships[1] = Relationship(intelligibility=0.5)
    assert "intelligibility" not in relationship_records(inhabitant)[0]
    included = relationship_records(
        inhabitant, include_intelligibility=True)[0]
    assert included["intelligibility"] == 0.5


def test_disabled_coevolution_cannot_conceal_intelligibility():
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        language_evolution_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(state.language, 42)
    first, second = person(0), person(1)
    first.relationships[1] = Relationship(intelligibility=0.5)
    state.people.extend([first, second])
    state.next_inhabitant_id = 2
    with pytest.raises(LanguageInvariantError):
        canonical_state_hash(state, world.world, config.manifest_dict())


def test_disabled_coevolution_cannot_retain_runtime_state():
    random.seed(42)
    world.reseed_world()
    config = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        language_evolution_enabled=True)
    config.validate()
    state = SimulationState()
    initialize_language_runtime(state.language, 42)
    state.language_coevolution.intelligibility_update_count = 1
    state.language_coevolution.reinforcing_update_count = 1
    with pytest.raises((LanguageInvariantError, ValueError)):
        canonical_state_hash(state, world.world, config.manifest_dict())


def test_canonical_hash_is_independent_of_python_hash_seed():
    script = textwrap.dedent(
        """
        import random
        from thalren_vale import world
        from thalren_vale.config import SimulationConfig
        from thalren_vale.language import (
            AgentLanguageState,
            initialize_language_coevolution_runtime,
            initialize_language_runtime,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.social import Relationship
        from thalren_vale.state import SimulationState

        random.seed(42)
        world.reseed_world()
        config = SimulationConfig(
            social_memory_enabled=True,
            social_partner_bias_enabled=True,
            language_evolution_enabled=True,
            language_coevolution_enabled=True,
        )
        config.validate()
        state = SimulationState()
        initialize_language_runtime(
            state.language, 42, language_coevolution_enabled=True)
        initialize_language_coevolution_runtime(
            state.language_coevolution, config.language_coevolution_config)
        for identifier, value in ((7, 0.4), (9, -0.2)):
            person = Inhabitant("P" + str(identifier), 0, 0)
            person.inhabitant_id = identifier
            person.faction = None
            person.language = AgentLanguageState()
            person.relationships[(identifier + 2) % 4] = Relationship(
                intelligibility=value)
            state.people.append(person)
        state.next_inhabitant_id = 10
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
    "--enable-language-coevolution",
    "--disable-language-coevolution",
    "--intelligibility-reward",
    "--intelligibility-reward=0.1",
    "--intelligibility-penalty",
    "--enable-language-coev",
    "--intelligibility",
    "--i",
])
def test_runner_rejects_the_complete_coevolution_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_language_coevolution_args(
            (argument,))


@pytest.mark.parametrize("argument", [
    "--ticks=10", "--seed=1", "--log-mode", "--enable-social-memory",
])
def test_runner_still_accepts_unrelated_options(argument):
    run_experiments._reject_uncontracted_language_coevolution_args((argument,))


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
                "--enable-language-coevolution",
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
        _validate_language_coevolution_configuration,
    )

    issues = _IssueCollector()
    _validate_language_coevolution_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = SimulationConfig(
        social_memory_enabled=True, social_partner_bias_enabled=True,
        language_evolution_enabled=True, language_coevolution_enabled=True)
    enabled.validate()
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"language_coevolution_enabled": True,
     "language_evolution_enabled": False,
     "social_partner_bias_enabled": True},
    {"language_coevolution_enabled": True,
     "language_evolution_enabled": True,
     "social_partner_bias_enabled": False},
    {"intelligibility_reward": 0.0},
    {"intelligibility_reward": 0.99},
    {"intelligibility_penalty": 1},
    {"intelligibility_penalty": True},
    {"language_coevolution_controls_status": "bogus"},
    {"intelligibility_reward": 0.11,
     "language_coevolution_controls_status": "disabled"},
    {"language_coevolution_enabled": True,
     "language_coevolution_control_notices": [
         LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE]},
    {"language_coevolution_controls_status": "normalized_uncontracted",
     "language_coevolution_control_notices": []},
    {"language_coevolution_control_notices": [
        LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE] * 2},
    {"language_coevolution_control_notices": sorted([
        LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE,
        LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS])[::-1]},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)
