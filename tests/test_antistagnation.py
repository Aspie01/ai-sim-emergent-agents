"""Regression tests for command-line anti-stagnation controls."""

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAVELER_EVENT = "Travelers from beyond the known lands arrive"


def run_sim(tmp_path: Path, ticks: int, *extra_args: str) -> str:
    """Run an isolated, deterministic simulation and return its output."""
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
            str(ticks),
            "--condition",
            "test",
            *extra_args,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return result.stdout


def test_traveler_wave_does_not_run_before_tick_40(tmp_path):
    output = run_sim(tmp_path, 39, "--disable-layer", "factions")
    assert TRAVELER_EVENT not in output


def test_traveler_wave_runs_at_tick_40_when_needed(tmp_path):
    output = run_sim(tmp_path, 40, "--disable-layer", "factions")
    assert "Tick 0040: 🧳 " + TRAVELER_EVENT in output


def test_disable_antistag_suppresses_traveler_wave(tmp_path):
    output = run_sim(
        tmp_path,
        40,
        "--disable-layer",
        "factions",
        "--disable-antistag",
    )
    assert TRAVELER_EVENT not in output
