"""Independent-process reproducibility guarantees."""

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace


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


def run_and_read_manifest(run_dir: Path, seed: int) -> dict:
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


def test_different_seeds_have_different_hashes(tmp_path):
    first = run_and_read_manifest(tmp_path / "first", 456)
    second = run_and_read_manifest(tmp_path / "second", 457)

    assert first["state_hash"] != second["state_hash"]


def test_manifest_records_code_provenance(tmp_path):
    manifest = run_and_read_manifest(tmp_path / "run", 456)

    assert manifest["schema_version"] == 1
    assert manifest["event_schema_version"] == 1
    assert manifest["state_hash_algorithm"] == "sha256"
    assert len(manifest["state_hash"]) == 64
    assert set(manifest["code"]) == {"commit", "dirty"}
