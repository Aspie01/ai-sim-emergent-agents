"""Independent-process reproducibility guarantees."""

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_seeded_layer_one_does_not_spawn_worker_threads(monkeypatch):
    from thalren_vale import sim

    person = SimpleNamespace(name="A", r=2, c=3)
    calls = []

    monkeypatch.setattr(sim, "people", [person])
    monkeypatch.setattr(sim, "all_dead", [])
    monkeypatch.setattr(sim, "_serial_mode", True)
    monkeypatch.setattr(sim, "do_tick_preamble", lambda people, tick: None)
    monkeypatch.setattr(
        sim,
        "process_inhabitants_chunk",
        lambda inhabitants, all_people, tick, bucket: calls.append(
            (list(inhabitants), all_people, tick, bucket)
        ),
    )

    class ForbiddenThread:
        def __init__(self, *args, **kwargs):
            raise AssertionError("serial mode must not construct worker threads")

    monkeypatch.setattr(sim.threading, "Thread", ForbiddenThread)

    deaths, previous_positions = sim.inhabitants_layer(7)

    assert deaths == []
    assert previous_positions == {"A": (2, 3)}
    assert len(calls) == 1
    assert calls[0][0] == [person]
    assert calls[0][1] is sim.people
    assert calls[0][2] == 7


def test_canonical_serializer_handles_runtime_container_types():
    from thalren_vale.reproducibility import _json_safe

    value = {
        "resources": defaultdict(int, {"food": 3}),
        "beliefs": {"trade_builds_bonds", "self_reliance"},
        "route": ("A", "B"),
    }

    converted = _json_safe(value)

    assert converted["resources"] == {"food": 3}
    assert converted["beliefs"] == ["self_reliance", "trade_builds_bonds"]
    assert converted["route"] == ["A", "B"]


def run_and_read_manifest(
    run_dir: Path, seed: int, extra_args: tuple[str, ...] = ()
) -> dict:
    run_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            str(seed),
            "--ticks",
            "5",
            "--condition",
            "repro",
            "--disable-antistag",
            "--log-mode",
            "metrics_only",
            *extra_args,
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    path = run_dir / "data" / f"run_manifest_repro_seed_{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_same_seed_has_same_hash_across_processes(tmp_path):
    first = run_and_read_manifest(tmp_path / "first", 456)
    second = run_and_read_manifest(tmp_path / "second", 456)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["execution_mode"] == second["execution_mode"] == "serial"


def test_explicit_disabled_social_controls_preserve_baseline_hash(tmp_path):
    baseline = run_and_read_manifest(tmp_path / "baseline", 456)
    disabled = run_and_read_manifest(
        tmp_path / "disabled",
        456,
        ("--disable-social-memory", "--disable-social-partner-bias"),
    )

    assert disabled["state_hash"] == baseline["state_hash"]
    assert disabled["configuration"] == baseline["configuration"]
    assert disabled["configuration"]["social_controls_status"] == "disabled"


def test_enabled_social_state_hash_is_stable_across_processes(tmp_path):
    extra_args = (
        "--enable-social-memory",
        "--enable-social-partner-bias",
    )
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["configuration"]["social_memory_enabled"] is True
    assert first["configuration"]["social_partner_bias_enabled"] is True
    assert first["configuration"]["social_controls_status"] == (
        "engineering_only_uncontracted"
    )


def test_raid_disabled_runs_are_deterministic_and_record_policy(tmp_path):
    extra_args = ("--disable-raids",)
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"]["disabled_layers"] == ["raids"]
    assert first["configuration"]["raids_enabled"] is False
    assert first["log_mode"] == "metrics_only"


def test_different_seeds_have_different_hashes(tmp_path):
    first = run_and_read_manifest(tmp_path / "first", 456)
    second = run_and_read_manifest(tmp_path / "second", 457)

    assert first["state_hash"] != second["state_hash"]


def test_manifest_records_code_provenance(tmp_path):
    manifest = run_and_read_manifest(tmp_path / "run", 456)

    assert manifest["schema_version"] == 2
    assert manifest["event_schema_version"] == 1
    assert manifest["metrics_timing_contract"] == "end_of_tick_v2"
    assert manifest["requested_ticks"] == manifest["final_tick"] == 5
    assert manifest["termination_reason"] == "requested_ticks_reached"
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True
    assert manifest["state_hash_algorithm"] == "sha256"
    assert len(manifest["state_hash"]) == 64
    assert set(manifest["code"]) == {"commit", "dirty"}
    assert set(manifest["artifact_inventory"]) == {
        "metrics", "events", "beliefs", "summary",
    }
    assert manifest["configuration"]["social_memory_enabled"] is False
    assert manifest["configuration"]["social_partner_bias_enabled"] is False
    assert manifest["configuration"]["maximum_social_ties"] == 32
    assert manifest["configuration"]["relationship_decay_interval"] == 25
    assert manifest["configuration"]["social_controls_status"] == "disabled"
    assert manifest["configuration"]["social_control_notices"] == []


def test_cli_normalization_warns_and_preserves_requested_bias_provenance(tmp_path):
    run_dir = tmp_path / "normalized"
    run_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            "123",
            "--ticks",
            "1",
            "--condition",
            "normalized",
            "--disable-antistag",
            "--log-mode",
            "metrics_only",
            "--enable-social-partner-bias",
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "normalized to false" in result.stderr
    manifest_path = (
        run_dir / "data" / "run_manifest_normalized_seed_123.json")
    configuration = json.loads(
        manifest_path.read_text(encoding="utf-8"))["configuration"]
    assert configuration["social_memory_enabled"] is False
    assert configuration["social_partner_bias_enabled"] is False
    assert configuration["social_controls_status"] == "normalized_uncontracted"
    assert configuration["social_control_notices"] == [
        "partner_bias_requested_without_social_memory"
    ]


def _social_hash_fixture(*, owner_is_dead: bool = False):
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.state import SimulationState

    inhabitant = Inhabitant("Stable", 0, 0)
    inhabitant.faction = None
    inhabitant.inhabitant_id = 7
    state = SimulationState(
        people=[] if owner_is_dead else [inhabitant],
        all_dead=[inhabitant] if owner_is_dead else [],
        next_inhabitant_id=9,
    )
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 1,
        "social_memory_enabled": False,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "disabled",
        "social_control_notices": [],
    }
    return inhabitant, state, world, configuration


def test_disabled_hash_ignores_allocator_ids_with_empty_social_mappings():
    from thalren_vale.reproducibility import canonical_state_hash

    inhabitant, state, world, configuration = _social_hash_fixture()

    before = canonical_state_hash(state, world, configuration)
    inhabitant.inhabitant_id = 70
    state.next_inhabitant_id = 90
    after = canonical_state_hash(state, world, configuration)

    assert inhabitant.relationships == {}
    assert before == after


@pytest.mark.parametrize(
    ("owner_is_dead", "cohort"),
    [(False, "living"), (True, "dead")],
)
def test_disabled_hash_rejects_hidden_relationship_state(
    owner_is_dead,
    cohort,
):
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import Relationship

    inhabitant, state, world, configuration = _social_hash_fixture(
        owner_is_dead=owner_is_dead)
    inhabitant.relationships[8] = Relationship(trust=0.9)

    with pytest.raises(
        ValueError,
        match=rf"{cohort}\[0\] name='Stable' inhabitant_id=7",
    ):
        canonical_state_hash(state, world, configuration)


def test_different_social_histories_change_enabled_state_hash():
    from thalren_vale.config import SocialMemoryConfig
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import InteractionKind, record_interaction
    from thalren_vale.state import SimulationState

    first = Inhabitant("A", 0, 0)
    second = Inhabitant("B", 0, 0)
    first.faction = None
    second.faction = None
    first.inhabitant_id = 1
    second.inhabitant_id = 2
    state = SimulationState(
        people=[first, second], next_inhabitant_id=3)
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 1,
        "social_memory_enabled": True,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "engineering_only_uncontracted",
        "social_control_notices": [],
    }

    before = canonical_state_hash(state, world, configuration)
    record_interaction(
        first,
        second,
        InteractionKind.TRADE,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=SocialMemoryConfig(True, False, 32, 25),
    )
    after = canonical_state_hash(state, world, configuration)

    assert before != after
