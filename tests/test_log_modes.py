"""Smoke tests for simulation output log modes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from run_experiments import validate_run_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_MODES = ("full", "summary", "metrics_only", "off")


def run_mode(tmp_path: Path, mode: str, ticks: int = 5) -> tuple[Path, dict]:
    run_dir = tmp_path / mode
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
            "777",
            "--ticks",
            str(ticks),
            "--condition",
            "logmode",
            "--log-mode",
            mode,
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    manifest_path = run_dir / "data" / "run_manifest_logmode_seed_777.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return run_dir, manifest


@pytest.mark.parametrize("mode", LOG_MODES)
def test_log_mode_short_run_writes_required_structured_artifacts(tmp_path, mode):
    run_dir, manifest = run_mode(tmp_path, mode)

    valid, errors = validate_run_outputs(run_dir, "logmode", 777)

    assert valid, errors
    assert manifest["log_mode"] == mode
    assert manifest["required_outputs"] == [
        "metrics",
        "events",
        "beliefs",
        "run_summary",
        "run_manifest",
    ]


@pytest.mark.parametrize("mode", ("summary", "metrics_only", "off"))
def test_non_full_log_modes_do_not_write_raw_text_artifacts(tmp_path, mode):
    run_dir, manifest = run_mode(tmp_path, mode)

    raw_paths = [
        *(run_dir.glob("logs/*.txt")),
        *run_dir.glob("manual_chronicle_*.txt"),
        *run_dir.glob("era_export_*.txt"),
    ]

    assert raw_paths == []
    assert not (run_dir / "dashboard_data.json").exists()
    assert "full_text_log" in manifest["optional_outputs"]["suppressed"]
    assert "manual_chronicle" in manifest["optional_outputs"]["suppressed"]


def test_full_log_mode_keeps_legacy_raw_text_artifacts(tmp_path):
    run_dir, manifest = run_mode(tmp_path, "full")

    assert list(run_dir.glob("logs/*.txt"))
    assert list(run_dir.glob("manual_chronicle_*.txt"))
    assert "full_text_log" in manifest["optional_outputs"]["written"]
    assert "manual_chronicle" in manifest["optional_outputs"]["written"]


def test_log_modes_preserve_final_state_hash(tmp_path):
    hashes = {}
    for mode in LOG_MODES:
        _run_dir, manifest = run_mode(tmp_path, mode)
        hashes[mode] = manifest["state_hash"]

    assert len(set(hashes.values())) == 1, hashes


def test_cli_rejects_invalid_log_mode_clearly(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            "777",
            "--ticks",
            "1",
            "--log-mode",
            "verbose",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "--log-mode" in result.stderr
    assert "invalid choice" in result.stderr
