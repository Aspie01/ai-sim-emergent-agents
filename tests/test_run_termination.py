"""Short subprocess tests for termination-aware simulator manifests."""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from thalren_vale import reproducibility
from thalren_vale.artifact_validation import inspect_run_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The 5-tick baseline never reaches technology research, so its fingerprint is
# unchanged by the active-research payload repair.
BASELINE_HASH = "3dcb25d98e634034da0814618bd8c28f3f6289491a536238950e866c5e75bc6f"
# Repinned by Language Research Readiness v1. The canonical payload previously
# read `researching` and `research_progress`, which nothing in the simulation
# ever assigns, so in-progress research was invisible: two factions researching
# different technologies produced identical fingerprints. The payload now reads
# the authoritative `active_research` mapping. This 40-tick run reaches
# research, so its fingerprint moved. Previous value:
# ef15589175c3c1e48ddab9ba837429626c46423d2637b35e8120189e110a7163
ANTISTAG_BASELINE_HASH = "b8c26ad01ca38b3c3c5cc706e994ca2f25db870602633d1ba09373072e4dce5e"


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


def _manifest_path(run_dir: Path, condition: str, seed: int) -> Path:
    return run_dir / "data" / f"run_manifest_{condition}_seed_{seed}.json"


def _run_module(
    run_dir: Path,
    *,
    seed: int = 456,
    ticks: int = 3,
    condition: str = "termination",
    disable_antistag: bool = True,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir()
    command = [
        sys.executable, "-m", "thalren_vale",
        "--seed", str(seed),
        "--ticks", str(ticks),
        "--condition", condition,
        "--log-mode", "metrics_only",
    ]
    if disable_antistag:
        command.append("--disable-antistag")
    return subprocess.run(
        command,
        cwd=run_dir,
        env=_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def _run_injected(
    run_dir: Path,
    injection: str,
    *,
    ticks: int = 3,
    condition: str = "termination",
    seed: int = 456,
    log_mode: str = "metrics_only",
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir()
    script = f"""
import sys
from thalren_vale import sim
{injection}
sys.argv = [
    'thalren_vale', '--seed', '{seed}', '--ticks', '{ticks}',
    '--condition', '{condition}', '--disable-antistag',
    '--log-mode', '{log_mode}',
]
sim.run()
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=run_dir,
        env=_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def _read_manifest(run_dir: Path, condition: str = "termination", seed: int = 456) -> dict:
    return json.loads(
        _manifest_path(run_dir, condition, seed).read_text(encoding="utf-8"))


def test_requested_horizon_records_completed_termination(tmp_path):
    run_dir = tmp_path / "completed"
    result = _run_module(run_dir)

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir)
    assert manifest["requested_ticks"] == 3
    assert manifest["final_tick"] == manifest["completed_ticks"] == 3
    assert manifest["termination_reason"] == "requested_ticks_reached"
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True
    assert not _manifest_path(run_dir, "termination", 456).with_suffix(".json.tmp").exists()

    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=3, mode="strict")
    assert report.valid, report.errors


def test_final_metrics_summary_and_manifest_agree(tmp_path):
    run_dir = tmp_path / "agreement"
    result = _run_module(run_dir)
    assert result.returncode == 0, result.stderr

    manifest = _read_manifest(run_dir)
    with (run_dir / "data" / "metrics_termination_seed_456.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        metrics = list(csv.DictReader(handle))
    with (run_dir / "data" / "run_summaries.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        summary = list(csv.DictReader(handle))

    assert int(metrics[-1]["tick"]) == manifest["final_tick"]
    assert metrics[-1]["population"] == summary[0]["final_population"]
    assert metrics[-1]["faction_count"] == summary[0]["final_faction_count"]


def test_keyboard_interrupt_records_cancelled_and_exits_nonzero(tmp_path):
    run_dir = tmp_path / "cancelled"
    result = _run_injected(
        run_dir,
        """
_original_world_layer = sim.world_layer
def _interrupt(tick, winter_just_ended):
    if tick == 2:
        raise KeyboardInterrupt()
    return _original_world_layer(tick, winter_just_ended)
sim.world_layer = _interrupt
""",
    )

    assert result.returncode != 0
    manifest = _read_manifest(run_dir)
    assert manifest["final_tick"] == 1
    assert manifest["termination_reason"] == "user_cancelled"
    assert manifest["result_status"] == "cancelled"
    assert manifest["completed_normally"] is False
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=3, mode="strict")
    assert not report.valid
    assert "noncompleted_result_status" in {issue.code for issue in report.issues}


def test_unhandled_exception_records_failed_and_exits_nonzero(tmp_path):
    run_dir = tmp_path / "failed"
    result = _run_injected(
        run_dir,
        """
_original_world_layer = sim.world_layer
def _fail(tick, winter_just_ended):
    if tick == 2:
        raise RuntimeError('injected lifecycle failure')
    return _original_world_layer(tick, winter_just_ended)
sim.world_layer = _fail
""",
    )

    assert result.returncode != 0
    manifest = _read_manifest(run_dir)
    assert manifest["final_tick"] == 1
    assert manifest["termination_reason"] == "exception"
    assert manifest["result_status"] == "failed"
    assert manifest["completed_normally"] is False
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=3, mode="strict")
    assert not report.valid


def test_initialization_exception_records_failed_before_tick_one(tmp_path):
    run_dir = tmp_path / "initialization_failed"
    result = _run_injected(
        run_dir,
        """
def _fail_initialization():
    raise RuntimeError('injected initialization failure')
sim.init_world = _fail_initialization
""",
    )

    assert result.returncode != 0
    manifest = _read_manifest(run_dir)
    assert manifest["final_tick"] == 0
    assert manifest["termination_reason"] == "exception"
    assert manifest["result_status"] == "failed"
    assert manifest["completed_normally"] is False


def test_required_finalization_exception_marks_attempt_failed(tmp_path):
    run_dir = tmp_path / "finalization_failed"
    result = _run_injected(
        run_dir,
        """
from thalren_vale import metrics
def _fail_finalize(self, world, inhabitants, factions):
    raise OSError('injected finalization failure')
metrics.MetricsLogger.finalize = _fail_finalize
""",
        ticks=1,
    )

    assert result.returncode != 0
    manifest = _read_manifest(run_dir)
    assert manifest["final_tick"] == 1
    assert manifest["termination_reason"] == "exception"
    assert manifest["result_status"] == "failed"
    assert manifest["completed_normally"] is False
    assert manifest["writer_health"]["unresolved_failures"]


def test_extinction_before_horizon_is_registered_natural_terminal(tmp_path):
    run_dir = tmp_path / "extinction"
    result = _run_injected(
        run_dir,
        "sim.init_inhabitants = lambda habitable: None",
        ticks=3,
    )

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir)
    assert manifest["final_tick"] == 1
    assert manifest["termination_reason"] == "extinction"
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=3, mode="strict")
    assert report.valid, report.errors


def test_extinction_on_final_tick_is_a_completed_requested_horizon(tmp_path):
    run_dir = tmp_path / "final_tick_extinction"
    result = _run_injected(
        run_dir,
        "sim.init_inhabitants = lambda habitable: None",
        ticks=1,
    )

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir)
    assert manifest["requested_ticks"] == 1
    assert manifest["final_tick"] == manifest["completed_ticks"] == 1
    assert manifest["termination_reason"] == "requested_ticks_reached"
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True


def test_preseal_manifest_write_failure_is_fatal_and_auditable(tmp_path):
    run_dir = tmp_path / "manifest_failure"
    result = _run_injected(
        run_dir,
        """
def _fail_manifest(*args, **kwargs):
    raise OSError('injected pre-seal manifest write failure')
sim.write_run_manifest = _fail_manifest
""",
        ticks=1,
    )

    assert result.returncode != 0
    manifest_path = _manifest_path(run_dir, "termination", 456)
    assert not manifest_path.exists()
    error_path = manifest_path.with_suffix(".error.txt")
    assert error_path.exists()
    assert "injected pre-seal manifest write failure" in error_path.read_text(
        encoding="utf-8")


def test_optional_final_report_failure_is_diagnostic_only(tmp_path):
    run_dir = tmp_path / "final_report_failure"
    result = _run_injected(
        run_dir,
        """
def _fail_final_report(*args, **kwargs):
    raise OSError('injected optional final report failure')
sim.display.final_report = _fail_final_report
""",
        ticks=1,
        log_mode="summary",
    )

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir)
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True
    assert any(
        diagnostic.startswith("final_report_failed: OSError:")
        for diagnostic in manifest["finalization_diagnostics"]
    )


@pytest.mark.parametrize(
    ("exception_expression", "expected_status", "expected_reason", "exit_code"),
    (
        ("KeyboardInterrupt()", "cancelled", "user_cancelled", None),
        ("SystemExit(23)", "failed", "exception", 23),
    ),
)
def test_optional_final_report_baseexceptions_are_sealed_and_reraised(
    tmp_path,
    exception_expression,
    expected_status,
    expected_reason,
    exit_code,
):
    run_dir = tmp_path / f"optional_{expected_status}"
    result = _run_injected(
        run_dir,
        f"""
def _interrupt_final_report(*args, **kwargs):
    raise {exception_expression}
sim.display.final_report = _interrupt_final_report
""",
        ticks=1,
        log_mode="summary",
    )

    assert result.returncode != 0
    if exit_code is not None:
        assert result.returncode == exit_code
    manifest = _read_manifest(run_dir)
    assert manifest["result_status"] == expected_status
    assert manifest["termination_reason"] == expected_reason
    assert manifest["completed_normally"] is False
    assert any(
        diagnostic.startswith("final_report_failed:")
        for diagnostic in manifest["finalization_diagnostics"]
    )
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=1, mode="strict")
    assert not report.valid


@pytest.mark.parametrize(
    ("exception_expression", "expected_status", "expected_reason", "exit_code"),
    (
        ("KeyboardInterrupt()", "cancelled", "user_cancelled", None),
        ("SystemExit(29)", "failed", "exception", 29),
    ),
)
def test_required_finalization_baseexceptions_are_sealed_and_reraised(
    tmp_path,
    exception_expression,
    expected_status,
    expected_reason,
    exit_code,
):
    run_dir = tmp_path / f"required_{expected_status}"
    result = _run_injected(
        run_dir,
        f"""
from thalren_vale import metrics
def _interrupt_finalize(self, world, inhabitants, factions):
    raise {exception_expression}
metrics.MetricsLogger.finalize = _interrupt_finalize
""",
        ticks=1,
    )

    assert result.returncode != 0
    if exit_code is not None:
        assert result.returncode == exit_code
    manifest = _read_manifest(run_dir)
    assert manifest["result_status"] == expected_status
    assert manifest["termination_reason"] == expected_reason
    assert manifest["completed_normally"] is False
    assert manifest["writer_health"]["finalization_failures"] == 1
    assert manifest["writer_health"]["unresolved_failures"]
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=1, mode="strict")
    assert not report.valid


def test_stdout_restoration_failure_cannot_publish_completion(tmp_path):
    run_dir = tmp_path / "stdout_restore_failure"
    result = _run_injected(
        run_dir,
        """
def _fail_restore(real_stdout):
    raise OSError('injected stdout restoration failure')
sim._restore_stdout = _fail_restore
""",
        ticks=1,
    )

    assert result.returncode != 0
    manifest = _read_manifest(run_dir)
    assert manifest["result_status"] == "failed"
    assert manifest["termination_reason"] == "exception"
    assert manifest["completed_normally"] is False
    assert any(
        diagnostic.startswith("stdout_restore_failed: OSError:")
        for diagnostic in manifest["finalization_diagnostics"]
    )
    report = inspect_run_outputs(
        run_dir, "termination", 456, expected_ticks=1, mode="strict")
    assert not report.valid


def test_manifest_publication_is_the_last_explicit_operation(tmp_path):
    run_dir = tmp_path / "publication_last"
    result = _run_injected(
        run_dir,
        """
from pathlib import Path
_original_write_manifest = sim.write_run_manifest
def _seal_then_arm_failure(*args, **kwargs):
    path = _original_write_manifest(*args, **kwargs)
    def _post_seal_operation():
        Path('post-seal-operation.txt').write_text('called', encoding='utf-8')
        raise BaseException('operation ran after authoritative publication')
    sim._write_summary_text = _post_seal_operation
    return path
sim.write_run_manifest = _seal_then_arm_failure
""",
        ticks=1,
        log_mode="summary",
    )

    assert result.returncode == 0, result.stderr
    assert not (run_dir / "post-seal-operation.txt").exists()
    manifest = _read_manifest(run_dir)
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True


def test_atomic_manifest_replace_failure_preserves_existing_manifest(
    tmp_path, monkeypatch,
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    manifest_path = data_dir / "run_manifest_atomic_seed_7.json"
    original = b'{"sealed": "previous"}\n'
    manifest_path.write_bytes(original)

    def _fail_replace(source, destination):
        assert Path(destination) == manifest_path
        raise OSError("injected atomic replacement failure")

    monkeypatch.setattr(reproducibility.os, "replace", _fail_replace)

    with pytest.raises(OSError, match="injected atomic replacement failure"):
        reproducibility.write_run_manifest(
            str(data_dir),
            seed=7,
            condition="atomic",
            configuration={},
            state_hash="0" * 64,
            execution_mode="serial",
            requested_ticks=1,
            final_tick=1,
            termination_reason="requested_ticks_reached",
            result_status="completed",
            completed_normally=True,
            writer_health={},
        )

    assert manifest_path.read_bytes() == original
    assert manifest_path.with_suffix(".json.tmp").exists()


def test_pruning_boundary_records_typed_and_legacy_observations_once(tmp_path):
    baseline_dir = tmp_path / "pruning_baseline"
    injected_dir = tmp_path / "pruning_injected"
    typed_detail = "typed pruning-boundary sentinel"
    repeated_message = "Tick 0050: WORLD EVENT — repeated promoted text"
    first_promoted_detail = "promoted actor A sentinel"
    second_promoted_detail = "promoted actor B sentinel"
    legacy_detail = "Tick 0050: WORLD EVENT — legacy pruning-boundary sentinel"

    baseline = _run_module(
        baseline_dir,
        ticks=50,
        condition="pruning_baseline",
    )
    result = _run_injected(
        injected_dir,
        f"""
import json
from pathlib import Path
_original_world_layer = sim.world_layer
def _inject_pruning_boundary(tick, winter_just_ended):
    result = _original_world_layer(tick, winter_just_ended)
    if tick == 50:
        for index in range(201):
            sim.event_log.append(
                f'Tick {{tick:04d}}: narrative pruning filler {{index:03d}}')
        sim.emit_event(
            sim.event_log,
            tick=tick,
            event_type='world_event',
            detail='{typed_detail}',
            message='Tick 0050: WORLD EVENT — typed pruning-boundary sentinel',
        )
        actor_a_token = sim.event_log.append('{repeated_message}')
        actor_b_token = sim.event_log.append('{repeated_message}')
        sim.emit_event(
            sim.event_log,
            tick=tick,
            event_type='world_event',
            actor='actor-B',
            detail='{second_promoted_detail}',
            message='{repeated_message}',
            append_text=False,
            journal_token=actor_b_token,
        )
        sim.emit_event(
            sim.event_log,
            tick=tick,
            event_type='world_event',
            actor='actor-A',
            detail='{first_promoted_detail}',
            message='{repeated_message}',
            append_text=False,
            journal_token=actor_a_token,
        )
        sim.event_log.append('{legacy_detail}')
    return result
sim.world_layer = _inject_pruning_boundary
_original_manifest_writer = sim.write_run_manifest
def _write_manifest_with_journal_probe(*args, **kwargs):
    Path('journal_probe.json').write_text(json.dumps({{
        'narrative_count': len(sim.event_log),
        'journal_count': len(sim.event_log._observation_journal),
    }}), encoding='utf-8')
    return _original_manifest_writer(*args, **kwargs)
sim.write_run_manifest = _write_manifest_with_journal_probe
""",
        ticks=50,
        condition="pruning_injected",
    )

    assert baseline.returncode == 0, baseline.stderr
    assert result.returncode == 0, result.stderr
    baseline_manifest = _read_manifest(baseline_dir, "pruning_baseline")
    manifest = _read_manifest(injected_dir, "pruning_injected")
    assert manifest["state_hash"] == baseline_manifest["state_hash"]

    with (injected_dir / "data" / "faction_events_pruning_injected_seed_456.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        events = list(csv.DictReader(handle))

    sentinels = {
        typed_detail,
        first_promoted_detail,
        second_promoted_detail,
        legacy_detail,
    }
    assert [row for row in events if row["detail"] in sentinels] == [
        {
            "event_schema_version": "1",
            "seed": "456",
            "tick": "50",
            "event_type": "world_event",
            "actor": "",
            "target": "",
            "detail": typed_detail,
        },
        {
            "event_schema_version": "1",
            "seed": "456",
            "tick": "50",
            "event_type": "world_event",
            "actor": "actor-A",
            "target": "",
            "detail": first_promoted_detail,
        },
        {
            "event_schema_version": "1",
            "seed": "456",
            "tick": "50",
            "event_type": "world_event",
            "actor": "actor-B",
            "target": "",
            "detail": second_promoted_detail,
        },
        {
            "event_schema_version": "1",
            "seed": "456",
            "tick": "50",
            "event_type": "world_event",
            "actor": "",
            "target": "",
            "detail": legacy_detail,
        },
    ]
    probe = json.loads(
        (injected_dir / "journal_probe.json").read_text(encoding="utf-8"))
    assert probe == {"narrative_count": 200, "journal_count": 0}


def test_end_of_tick_observation_preserves_frozen_state_hash(tmp_path):
    run_dir = tmp_path / "hash"
    result = _run_module(
        run_dir,
        ticks=5,
        condition="termination_baseline",
    )

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir, "termination_baseline")
    assert manifest["state_hash"] == BASELINE_HASH


def test_end_of_tick_observation_preserves_antistag_state_hash(tmp_path):
    run_dir = tmp_path / "antistag_hash"
    result = _run_module(
        run_dir,
        ticks=40,
        condition="timing_baseline",
        disable_antistag=False,
    )

    assert result.returncode == 0, result.stderr
    manifest = _read_manifest(run_dir, "timing_baseline")
    assert manifest["state_hash"] == ANTISTAG_BASELINE_HASH
