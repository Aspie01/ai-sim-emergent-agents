"""Canonical enabled-language evidence and disabled fail-closed behavior."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from thalren_vale.coalitions import (
    CoalitionRuntimeState,
    InformalCoalition,
    build_coalition_membership_snapshot,
)
from thalren_vale.config import (
    CoalitionConfig,
    CoalitionDialectConfig,
    LanguageEvolutionConfig,
    SimulationConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    AssociationOrigin,
    CommunicationContext,
    CoalitionDialectRuntimeState,
    LanguageInvariantError,
    LexicalAssociation,
    Meaning,
    Signal,
    canonical_language_snapshot,
    communicate,
    initialize_language_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.state import SimulationState


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENABLED = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 5, True)
DIALECT = CoalitionDialectConfig(True, 1.50, 1.25)
COALITIONS = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)


def person(name: str, inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(name, 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    inhabitant.faction = None
    return inhabitant


def world() -> list:
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


def enabled_fixture(seed: int = 202) -> tuple[SimulationState, dict, list]:
    sender = person("Sender", 1)
    receiver = person("Receiver", 2)
    state = SimulationState(people=[sender, receiver], next_inhabitant_id=3)
    initialize_language_runtime(state.language, seed)
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        language_forgetting_interval=5,
    ).manifest_dict()
    communicate(
        sender,
        receiver,
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=ENABLED,
        runtime=state.language,
    )
    return state, configuration, world()


def run_language_subprocess(hash_seed: str) -> dict:
    script = textwrap.dedent(
        """
        import json

        from thalren_vale.config import LanguageEvolutionConfig, SimulationConfig
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.language import (
            CommunicationContext,
            Meaning,
            canonical_language_snapshot,
            communicate,
            initialize_language_runtime,
            language_runtime_record,
        )
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        people = [Inhabitant("Sender", 0, 0), Inhabitant("Receiver", 0, 0)]
        for inhabitant, inhabitant_id in zip(people, (1, 2)):
            inhabitant.inhabitant_id = inhabitant_id
            inhabitant.faction = None
        state = SimulationState(people=people, next_inhabitant_id=3)
        initialize_language_runtime(state.language, 202)
        config = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 5, True)
        active_ids = frozenset({1, 2})
        for tick in range(1, 5):
            communicate(
                people[0], people[1], Meaning.FOOD,
                context=CommunicationContext.AID_TRANSFER,
                tick=tick, active_ids=active_ids, config=config,
                runtime=state.language,
            )
        manifest_config = SimulationConfig(
            language_evolution_enabled=True,
            language_forgetting_interval=5,
        ).manifest_dict()
        world = [[{
            "biome": "plains",
            "habitable": True,
            "resources": {
                "food": 1, "wood": 0, "ore": 0, "stone": 0, "water": 0,
            },
        }]]
        print(json.dumps({
            "snapshot": canonical_language_snapshot(people, config=config),
            "runtime": language_runtime_record(state.language),
            "state_hash": canonical_state_hash(state, world, manifest_config),
        }, sort_keys=True, separators=(",", ":")))
        """
    )
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_enabled_snapshots_and_hashes_ignore_pythonhashseed_across_processes():
    first = run_language_subprocess("1")
    second = run_language_subprocess("987654")

    assert first == second
    assert len(first["state_hash"]) == 64
    assert first["snapshot"][0]["next_invention_index"] == 1
    assert first["runtime"]["seed_domain_fingerprint"]


def test_one_agents_inventions_do_not_perturb_another_agents_signal():
    def second_signal(*, first_agent_acts: bool) -> Signal:
        first = person("First", 1)
        second = person("Second", 2)
        observer = person("Observer", 3)
        state = SimulationState(people=[first, second, observer])
        initialize_language_runtime(state.language, 909)
        active = frozenset({1, 2, 3})
        if first_agent_acts:
            for tick, meaning in enumerate((Meaning.FOOD, Meaning.WOOD), start=1):
                communicate(
                    first,
                    observer,
                    meaning,
                    context=CommunicationContext.AID_TRANSFER,
                    tick=tick,
                    active_ids=active,
                    config=ENABLED,
                    runtime=state.language,
                )
        outcome = communicate(
            second,
            observer,
            Meaning.ORE,
            context=CommunicationContext.PAID_TRADE,
            tick=3,
            active_ids=active,
            config=ENABLED,
            runtime=state.language,
        )
        assert outcome.produced_signal is not None
        return outcome.produced_signal

    assert second_signal(first_agent_acts=False) == second_signal(
        first_agent_acts=True)


def test_enabled_hash_covers_runtime_index_controls_origin_and_source():
    state, configuration, tiles = enabled_fixture()
    baseline = canonical_state_hash(state, tiles, configuration)

    different_runtime = copy.deepcopy(state)
    different_runtime.language.invention_count += 1
    assert canonical_state_hash(
        different_runtime, tiles, configuration) != baseline

    different_ticks = copy.deepcopy(state)
    different_ticks.language.last_forgetting_tick = 5
    assert canonical_state_hash(different_ticks, tiles, configuration) != baseline

    different_domain = copy.deepcopy(state)
    different_domain.language.seed_domain = (
        "thalren-vale:endogenous-language-v1|seed=203"
    )
    different_domain.language.seed_domain_fingerprint = hashlib.sha256(
        different_domain.language.seed_domain.encode("ascii")
    ).hexdigest()
    assert canonical_state_hash(different_domain, tiles, configuration) != baseline

    different_index = copy.deepcopy(state)
    different_index.people[0].language.next_invention_index += 1
    assert canonical_state_hash(different_index, tiles, configuration) != baseline

    different_controls = dict(configuration)
    different_controls["language_learning_rate"] = 0.25
    assert canonical_state_hash(state, tiles, different_controls) != baseline

    different_source = copy.deepcopy(state)
    receiver = different_source.people[1]
    key, association = next(iter(receiver.language.comprehension.items()))
    receiver.language.comprehension[key] = replace(
        association, learned_from_id=99)
    assert canonical_state_hash(different_source, tiles, configuration) != baseline

    learned_production = copy.deepcopy(state)
    sender = learned_production.people[0]
    key, association = next(iter(sender.language.production.items()))
    sender.language.production[key] = replace(
        association,
        origin=AssociationOrigin.LEARNED,
        learned_from_id=2,
    )
    assert canonical_state_hash(learned_production, tiles, configuration) != baseline


@pytest.mark.parametrize("missing", [
    "language_controls_status",
    "language_control_notices",
])
def test_enabled_hash_requires_separate_status_and_notices(missing):
    state, configuration, tiles = enabled_fixture()
    del configuration[missing]

    with pytest.raises(ValueError, match="lacks controls"):
        canonical_state_hash(state, tiles, configuration)


def test_enabled_hash_is_independent_of_association_insertion_order():
    state, configuration, tiles = enabled_fixture()
    receiver = state.people[1]
    first_signal = next(iter(receiver.language.comprehension))[0]
    second_signal = Signal((7, 6))
    receiver.language.comprehension[(second_signal, Meaning.WOOD)] = (
        LexicalAssociation(
            meaning=Meaning.WOOD,
            signal=second_signal,
            confidence=0.30,
            observation_count=1,
            last_used_tick=1,
            origin=AssociationOrigin.LEARNED,
            learned_from_id=1,
        )
    )
    receiver.language.comprehension[(first_signal, Meaning.ORE)] = (
        LexicalAssociation(
            meaning=Meaning.ORE,
            signal=first_signal,
            confidence=0.10,
            observation_count=1,
            last_used_tick=1,
            origin=AssociationOrigin.LEARNED,
            learned_from_id=1,
        )
    )
    baseline_snapshot = canonical_language_snapshot(state.people, config=ENABLED)
    baseline_hash = canonical_state_hash(state, tiles, configuration)

    reordered = copy.deepcopy(state)
    for inhabitant in reordered.people:
        inhabitant.language.production = dict(
            reversed(tuple(inhabitant.language.production.items())))
        inhabitant.language.comprehension = dict(
            reversed(tuple(inhabitant.language.comprehension.items())))

    assert canonical_language_snapshot(
        reordered.people, config=ENABLED) == baseline_snapshot
    assert canonical_state_hash(reordered, tiles, configuration) == baseline_hash


def test_disabled_language_controls_are_omitted_from_behavioral_hash():
    inhabitant = person("Stable", 7)
    state = SimulationState(people=[inhabitant], next_inhabitant_id=9)
    historical_configuration = {"ticks": 1}
    explicit_disabled = {
        **historical_configuration,
        "language_evolution_enabled": False,
        "maximum_language_associations": 32,
        "maximum_signal_length": 3,
        "language_learning_rate": 0.20,
        "language_reinforcement_rate": 0.10,
        "language_forgetting_interval": 25,
        "language_invention_enabled": True,
        "language_controls_status": "disabled",
        "language_control_notices": [],
    }

    assert canonical_state_hash(
        state, world(), historical_configuration
    ) == canonical_state_hash(state, world(), explicit_disabled)


@pytest.mark.parametrize("hidden", ["association", "index", "runtime"])
def test_disabled_hash_fails_closed_on_hidden_language_state(hidden):
    inhabitant = person("Stable", 7)
    state = SimulationState(people=[inhabitant], next_inhabitant_id=9)
    if hidden == "association":
        signal = Signal((0, 1))
        inhabitant.language.production[(Meaning.FOOD, signal)] = (
            LexicalAssociation(
                meaning=Meaning.FOOD,
                signal=signal,
                confidence=0.50,
            )
        )
    elif hidden == "index":
        inhabitant.language.next_invention_index = 1
    else:
        initialize_language_runtime(state.language, 1)

    with pytest.raises(LanguageInvariantError, match="pristine"):
        canonical_state_hash(state, world(), {"ticks": 1})


def test_disabled_hash_does_not_tolerate_a_missing_synthetic_language_state():
    state = SimulationState(
        people=[SimpleNamespace(inhabitant_id=1)],
        next_inhabitant_id=2,
    )

    with pytest.raises(
        LanguageInvariantError,
        match="missing AgentLanguageState",
    ):
        canonical_state_hash(state, world(), {"ticks": 1})


def enabled_dialect_fixture():
    people = [person(f"P{index}", index) for index in range(1, 4)]
    state = SimulationState(people=people, next_inhabitant_id=4)
    state.coalitions = CoalitionRuntimeState(
        active_coalitions={0: InformalCoalition(0, 1, (1, 2, 3))},
        member_to_coalition={1: 0, 2: 0, 3: 0},
        next_coalition_id=1,
        candidate_formation_count=1,
        last_observation_tick=1,
        last_active_inhabitant_ids=(1, 2, 3),
    )
    initialize_language_runtime(
        state.language,
        404,
        coalition_dialect_influence_enabled=True,
    )
    membership = build_coalition_membership_snapshot(
        state.coalitions,
        snapshot_tick=2,
        active_inhabitant_ids=(1, 2, 3),
        config=COALITIONS,
    )
    communicate(
        people[0],
        people[1],
        Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER,
        tick=2,
        active_ids=frozenset({1, 2, 3}),
        config=ENABLED,
        runtime=state.language,
        dialect_config=DIALECT,
        dialect_runtime=state.dialect,
        coalition_membership_snapshot=membership,
    )
    configuration = SimulationConfig(
        social_memory_enabled=True,
        language_evolution_enabled=True,
        language_forgetting_interval=5,
        coalition_emergence_enabled=True,
        coalition_dialect_influence_enabled=True,
    ).manifest_dict()
    return state, configuration, world()


def test_enabled_hash_covers_exact_dialect_controls_and_runtime():
    state, configuration, tiles = enabled_dialect_fixture()
    baseline = canonical_state_hash(state, tiles, configuration)

    different_runtime = copy.deepcopy(state)
    different_runtime.dialect.same_coalition_rate_application_count += 1
    assert canonical_state_hash(
        different_runtime, tiles, configuration) != baseline

    different_controls = dict(configuration)
    different_controls["same_coalition_learning_multiplier"] = 1.75
    assert canonical_state_hash(state, tiles, different_controls) != baseline


def test_disabled_dialect_controls_are_omitted_from_enabled_language_hash():
    state, configuration, tiles = enabled_fixture()
    historical = {
        key: value
        for key, value in configuration.items()
        if key not in {
            "coalition_dialect_influence_enabled",
            "same_coalition_learning_multiplier",
            "same_coalition_reinforcement_multiplier",
            "dialect_controls_status",
            "dialect_control_notices",
        }
    }

    assert canonical_state_hash(
        state, tiles, configuration
    ) == canonical_state_hash(state, tiles, historical)


def test_disabled_hash_rejects_hidden_or_mismatched_dialect_state():
    state = SimulationState(people=[person("Stable", 1)], next_inhabitant_id=2)
    state.dialect.same_coalition_communication_count = 1
    state.dialect.last_classification_tick = 1
    with pytest.raises(LanguageInvariantError, match="pristine"):
        canonical_state_hash(state, world(), {"ticks": 1})

    state = SimulationState(people=[person("Stable", 1)], next_inhabitant_id=2)
    initialize_language_runtime(
        state.language,
        8,
        coalition_dialect_influence_enabled=True,
    )
    configuration = SimulationConfig(
        language_evolution_enabled=True,
        language_forgetting_interval=5,
    ).manifest_dict()
    with pytest.raises(LanguageInvariantError, match="gate"):
        canonical_state_hash(state, world(), configuration)


def run_dialect_subprocess(hash_seed: str) -> dict:
    script = textwrap.dedent(
        """
        import json

        from thalren_vale.coalitions import (
            CoalitionRuntimeState, InformalCoalition,
            build_coalition_membership_snapshot,
        )
        from thalren_vale.config import (
            CoalitionConfig, CoalitionDialectConfig,
            LanguageEvolutionConfig, SimulationConfig,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.language import (
            CommunicationContext, Meaning, canonical_language_snapshot,
            coalition_dialect_summary, communicate, initialize_language_runtime,
        )
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        people = [Inhabitant(f"P{index}", 0, 0) for index in range(1, 4)]
        for index, inhabitant in enumerate(people, start=1):
            inhabitant.inhabitant_id = index
            inhabitant.faction = None
        state = SimulationState(people=people, next_inhabitant_id=4)
        state.coalitions = CoalitionRuntimeState(
            active_coalitions={0: InformalCoalition(0, 1, (1, 2, 3))},
            member_to_coalition={3: 0, 1: 0, 2: 0},
            next_coalition_id=1,
            candidate_formation_count=1,
            last_observation_tick=1,
            last_active_inhabitant_ids=(1, 2, 3),
        )
        language = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 5, True)
        coalitions = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 5, 32)
        dialect = CoalitionDialectConfig(True, 1.50, 1.25)
        initialize_language_runtime(
            state.language, 404, coalition_dialect_influence_enabled=True)
        snapshot = build_coalition_membership_snapshot(
            state.coalitions, snapshot_tick=2,
            active_inhabitant_ids=(3, 1, 2), config=coalitions)
        for _ in range(4):
            communicate(
                people[0], people[1], Meaning.FOOD,
                context=CommunicationContext.AID_TRANSFER,
                tick=2, active_ids=frozenset({3, 1, 2}), config=language,
                runtime=state.language, dialect_config=dialect,
                dialect_runtime=state.dialect,
                coalition_membership_snapshot=snapshot)
        configuration = SimulationConfig(
            social_memory_enabled=True,
            language_evolution_enabled=True,
            language_forgetting_interval=5,
            coalition_emergence_enabled=True,
            coalition_dialect_influence_enabled=True,
        ).manifest_dict()
        world = [[{
            "biome": "plains", "habitable": True,
            "resources": {
                "food": 1, "wood": 0, "ore": 0, "stone": 0, "water": 0,
            },
        }]]
        print(json.dumps({
            "snapshot": canonical_language_snapshot(people, config=language),
            "dialects": coalition_dialect_summary(
                people, snapshot=snapshot, language_config=language,
                dialect_config=dialect, language_runtime=state.language,
                dialect_runtime=state.dialect),
            "hash": canonical_state_hash(state, world, configuration),
        }, sort_keys=True, separators=(",", ":")))
        """
    )
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_enabled_dialect_snapshots_summaries_and_hashes_ignore_pythonhashseed():
    assert run_dialect_subprocess("1") == run_dialect_subprocess("987654")
