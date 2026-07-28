"""Versioning, validation, and resume behavior for experiment batches."""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping
from types import MappingProxyType, SimpleNamespace

import pytest

import run_experiments as runner
from thalren_vale.artifact_validation import inspect_run_outputs

from run_experiments import (
    RESULT_CANCELLED,
    RESULT_COMPLETED,
    RESULT_EXCEPTION,
    RESULT_INVALID_OUTPUT,
    RESULT_WALL_CLOCK_LIMIT,
    UnsafeResumeError,
    classify_result,
    load_plan,
    main,
    parse_seed_range,
    run_from_plan,
    run_single,
    validate_run_outputs,
    verify_outputs,
)


def write_plan(path, **overrides):
    plan = {
        "schema_version": 1,
        "experiment_id": "test-batch-v1",
        "default_ticks": 1,
        "conditions": [{"name": "baseline", "seeds": "1"}],
    }
    plan.update(overrides)
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def snapshot_tree(root):
    """Capture every in-root entry without following symlinks."""
    root_stat = os.lstat(root)
    snapshot = {
        root.relative_to(root): (
            "directory",
            root_stat.st_mode,
            root_stat.st_mtime_ns,
        ),
    }

    def capture(path):
        relative = path.relative_to(root)
        path_stat = os.lstat(path)
        if path.is_symlink():
            snapshot[relative] = (
                "symlink",
                os.readlink(path),
                path_stat.st_mode,
                path_stat.st_mtime_ns,
            )
        elif path.is_dir():
            snapshot[relative] = (
                "directory",
                path_stat.st_mode,
                path_stat.st_mtime_ns,
            )
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                capture(child)
        elif path.is_file():
            snapshot[relative] = (
                "file",
                path.read_bytes(),
                path_stat.st_mode,
                path_stat.st_mtime_ns,
            )
        else:
            snapshot[relative] = (
                "other",
                path_stat.st_mode,
                path_stat.st_mtime_ns,
            )

    for child in sorted(root.iterdir(), key=lambda item: item.name):
        capture(child)
    return snapshot


def matching_batch_manifest(plan_path, *, plan_sha256=None):
    plan, loaded_hash = load_plan(plan_path)
    return {
        "schema_version": 1,
        "experiment_id": plan["experiment_id"],
        "plan_sha256": plan_sha256 or loaded_hash,
        "results": [],
    }


def write_batch_manifest(output, plan_path, *, plan_sha256=None):
    (output / "experiment_manifest.json").write_text(
        json.dumps(
            matching_batch_manifest(plan_path, plan_sha256=plan_sha256),
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def assert_resume_rejected_read_only(plan_path, output):
    before = snapshot_tree(output)
    with pytest.raises(UnsafeResumeError, match="cannot resume nonempty output root"):
        run_from_plan(plan_path, output, resume=True)
    assert snapshot_tree(output) == before


def assert_pid_reaped(pid):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail(f"timed-out child process {pid} was not reaped")


def fresh_cell_spec() -> list[dict]:
    return [{
        "seed": 1,
        "condition": "baseline",
        "ticks": 1,
        "extra_args": [],
        "timeout_seconds": 5,
    }]


ABBREVIATED_SOCIAL_ARGUMENTS = [
    ["--enable-social-m"],
    ["--disable-social-m"],
    ["--enable-social-partner-b"],
    ["--disable-social-partner-b"],
    ["--maximum-social-t", "16"],
    ["--relationship-decay-i", "10"],
]

FULL_SOCIAL_ARGUMENTS = [
    ["--enable-social-memory"],
    ["--disable-social-memory"],
    ["--enable-social-partner-bias"],
    ["--disable-social-partner-bias"],
    ["--maximum-social-ties", "16"],
    ["--relationship-decay-interval", "10"],
]

EQUALS_SOCIAL_ARGUMENTS = [
    ["--enable-social-memory=true"],
    ["--disable-social-memory=true"],
    ["--enable-social-partner-bias=true"],
    ["--disable-social-partner-bias=true"],
    ["--maximum-social-ties=16"],
    ["--relationship-decay-interval=10"],
]

ABBREVIATED_COALITION_ARGUMENTS = [
    ["--enable-coalition-e"],
    ["--disable-coalition-e"],
    ["--coalition-minimum-s", "3"],
    ["--coalition-trust-t", "0.24"],
    ["--coalition-familiarity-t", "0.40"],
    ["--coalition-maximum-g", "0.20"],
    ["--coalition-persistence-t", "5"],
    ["--maximum-active-c", "32"],
]

FULL_COALITION_ARGUMENTS = [
    ["--enable-coalition-emergence"],
    ["--disable-coalition-emergence"],
    ["--coalition-minimum-size", "3"],
    ["--coalition-trust-threshold", "0.24"],
    ["--coalition-familiarity-threshold", "0.40"],
    ["--coalition-maximum-grievance", "0.20"],
    ["--coalition-persistence-ticks", "5"],
    ["--maximum-active-coalitions", "32"],
]

EQUALS_COALITION_ARGUMENTS = [
    ["--enable-coalition-emergence=true"],
    ["--disable-coalition-emergence=true"],
    ["--coalition-minimum-size=3"],
    ["--coalition-trust-threshold=0.24"],
    ["--coalition-familiarity-threshold=0.40"],
    ["--coalition-maximum-grievance=0.20"],
    ["--coalition-persistence-ticks=5"],
    ["--maximum-active-coalitions=32"],
]

ABBREVIATED_LANGUAGE_ARGUMENTS = [
    ["--enable-language-e"],
    ["--disable-language-e"],
    ["--maximum-language-a", "16"],
    ["--maximum-signal-l", "3"],
    ["--language-learning-r", "0.2"],
    ["--language-reinforcement-r", "0.1"],
    ["--language-forgetting-i", "25"],
    ["--enable-language-i"],
    ["--disable-language-i"],
]

FULL_LANGUAGE_ARGUMENTS = [
    ["--enable-language-evolution"],
    ["--disable-language-evolution"],
    ["--maximum-language-associations", "16"],
    ["--maximum-signal-length", "3"],
    ["--language-learning-rate", "0.2"],
    ["--language-reinforcement-rate", "0.1"],
    ["--language-forgetting-interval", "25"],
    ["--enable-language-invention"],
    ["--disable-language-invention"],
]

EQUALS_LANGUAGE_ARGUMENTS = [
    ["--enable-language-evolution=true"],
    ["--disable-language-evolution=true"],
    ["--maximum-language-associations=16"],
    ["--maximum-signal-length=3"],
    ["--language-learning-rate=0.2"],
    ["--language-reinforcement-rate=0.1"],
    ["--language-forgetting-interval=25"],
    ["--enable-language-invention=true"],
    ["--disable-language-invention=true"],
]

ABBREVIATED_DIALECT_ARGUMENTS = [
    ["--same-coalition"],
    ["--same-coalition-learning", "1.5"],
    ["--same-coalition-reinforcement", "1.25"],
    ["--enable-coalition-dialect"],
    ["--disable-coalition-dialect"],
]

FULL_DIALECT_ARGUMENTS = [
    ["--enable-coalition-dialect-influence"],
    ["--disable-coalition-dialect-influence"],
    ["--same-coalition-learning-multiplier", "1.5"],
    ["--same-coalition-reinforcement-multiplier", "1.25"],
]

EQUALS_DIALECT_ARGUMENTS = [
    ["--enable-coalition-dialect-influence=true"],
    ["--disable-coalition-dialect-influence=true"],
    ["--same-coalition-learning-multiplier=1.5"],
    ["--same-coalition-reinforcement-multiplier=1.25"],
    ["--same-coalition=1.5"],
]

CONTACT_OPTION_NAMES = (
    "--enable-language-contact",
    "--disable-language-contact",
    "--cross-group-learning-multiplier",
    "--borrowing-exposure-threshold",
    "--borrowing-confidence-threshold",
)

FULL_CONTACT_ARGUMENTS = [
    ["--enable-language-contact"],
    ["--disable-language-contact"],
    ["--cross-group-learning-multiplier", "1.5"],
    ["--borrowing-exposure-threshold", "3"],
    ["--borrowing-confidence-threshold", "0.5"],
]

EQUALS_CONTACT_ARGUMENTS = [
    ["--enable-language-contact=true"],
    ["--disable-language-contact=true"],
    ["--cross-group-learning-multiplier=1.5"],
    ["--borrowing-exposure-threshold=3"],
    ["--borrowing-confidence-threshold=0.5"],
]

PROPER_PREFIX_CONTACT_ARGUMENTS = [
    [prefix]
    for prefix in sorted({
        option[:length]
        for option in CONTACT_OPTION_NAMES
        for length in range(3, len(option))
    })
]

INTERGENERATIONAL_OPTION_NAMES = (
    "--enable-intergenerational-language",
    "--disable-intergenerational-language",
    "--maximum-parental-meanings-per-parent",
    "--intergenerational-learning-strength",
)

FULL_INTERGENERATIONAL_ARGUMENTS = [
    ["--enable-intergenerational-language"],
    ["--disable-intergenerational-language"],
    ["--maximum-parental-meanings-per-parent", "2"],
    ["--intergenerational-learning-strength", "0.2"],
]

EQUALS_INTERGENERATIONAL_ARGUMENTS = [
    ["--enable-intergenerational-language=true"],
    ["--disable-intergenerational-language=true"],
    ["--maximum-parental-meanings-per-parent=2"],
    ["--intergenerational-learning-strength=0.2"],
]

PROPER_PREFIX_INTERGENERATIONAL_ARGUMENTS = [
    [prefix]
    for prefix in sorted({
        option[:length]
        for option in INTERGENERATIONAL_OPTION_NAMES
        for length in range(3, len(option))
    })
]


@pytest.mark.parametrize(
    "extra_args",
    ABBREVIATED_SOCIAL_ARGUMENTS
    + FULL_SOCIAL_ARGUMENTS
    + EQUALS_SOCIAL_ARGUMENTS,
)
def test_runner_rejects_uncontracted_social_controls_before_creating_root(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted social control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


@pytest.mark.parametrize(
    "extra_args",
    ABBREVIATED_COALITION_ARGUMENTS
    + FULL_COALITION_ARGUMENTS
    + EQUALS_COALITION_ARGUMENTS,
)
def test_runner_rejects_uncontracted_coalition_controls_before_creating_root(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted coalition control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


@pytest.mark.parametrize(
    "extra_args",
    ABBREVIATED_LANGUAGE_ARGUMENTS
    + FULL_LANGUAGE_ARGUMENTS
    + EQUALS_LANGUAGE_ARGUMENTS,
)
def test_runner_rejects_uncontracted_language_controls_before_creating_root(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted language control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


@pytest.mark.parametrize(
    "extra_args",
    ABBREVIATED_DIALECT_ARGUMENTS
    + FULL_DIALECT_ARGUMENTS
    + EQUALS_DIALECT_ARGUMENTS,
)
def test_runner_rejects_every_dialect_prefix_before_filesystem_or_child_activity(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted dialect control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


@pytest.mark.parametrize(
    "extra_args",
    PROPER_PREFIX_CONTACT_ARGUMENTS
    + FULL_CONTACT_ARGUMENTS
    + EQUALS_CONTACT_ARGUMENTS,
)
def test_runner_rejects_every_contact_prefix_before_filesystem_or_child_activity(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


def test_rejected_contact_control_preserves_existing_output_tree(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    output.mkdir()
    sentinel = output / "sentinel.bin"
    sentinel.write_bytes(b"preserve contact rejection\x00")
    before = snapshot_tree(output)
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = ["--borrowing"]
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted language contact control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert snapshot_tree(output) == before


@pytest.mark.parametrize(
    "extra_args",
    PROPER_PREFIX_INTERGENERATIONAL_ARGUMENTS
    + FULL_INTERGENERATIONAL_ARGUMENTS
    + EQUALS_INTERGENERATIONAL_ARGUMENTS,
)
def test_runner_rejects_every_intergenerational_option_before_any_activity(
    tmp_path,
    monkeypatch,
    extra_args,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = extra_args
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


def test_rejected_intergenerational_control_preserves_existing_output_tree(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "sentinel.bin").write_bytes(b"preserve transmission rejection\x00")
    before = snapshot_tree(output)
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = ["--maximum-parental"]
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(
        ValueError, match="uncontracted intergenerational language control"
    ):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert snapshot_tree(output) == before


def test_rejected_coalition_control_preserves_existing_output_tree(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    output.mkdir()
    sentinel = output / "sentinel.bin"
    sentinel.write_bytes(b"preserve coalition rejection\x00")
    before = snapshot_tree(output)
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = ["--coalition-minimum-size=3"]
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="uncontracted coalition control"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert snapshot_tree(output) == before


def test_runner_accepts_unrelated_valid_extra_arguments():
    cell = fresh_cell_spec()[0]
    cell["extra_args"] = ["--disable-raids"]

    frozen = runner._freeze_cell(cell)

    assert frozen.extra_args == ("--disable-raids",)


@pytest.mark.parametrize("extra_args", ABBREVIATED_SOCIAL_ARGUMENTS)
def test_simulator_rejects_abbreviated_social_options_before_execution(
    tmp_path,
    extra_args,
):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(runner.SOURCE_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            *extra_args,
            "--ticks",
            "0",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert extra_args[0] in result.stderr
    assert "ticks must be at least 1" not in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("extra_args", ABBREVIATED_COALITION_ARGUMENTS)
def test_simulator_rejects_abbreviated_coalition_options_before_execution(
    tmp_path,
    extra_args,
):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(runner.SOURCE_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            *extra_args,
            "--ticks",
            "0",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert extra_args[0] in result.stderr
    assert "ticks must be at least 1" not in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("extra_args", ABBREVIATED_LANGUAGE_ARGUMENTS)
def test_simulator_rejects_abbreviated_language_options_before_execution(
    tmp_path,
    extra_args,
):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(runner.SOURCE_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            *extra_args,
            "--ticks",
            "0",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert extra_args[0] in result.stderr
    assert "ticks must be at least 1" not in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("extra_args", ABBREVIATED_DIALECT_ARGUMENTS)
def test_simulator_rejects_abbreviated_dialect_options_before_execution(
    tmp_path,
    extra_args,
):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(runner.SOURCE_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            *extra_args,
            "--ticks",
            "0",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert extra_args[0] in result.stderr
    assert "ticks must be at least 1" not in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "extra_args",
    (
        ["--enable-language-cont"],
        ["--disable-language-cont"],
        ["--cross-group-learning"],
        ["--borrowing-exposure"],
        ["--borrowing-confidence"],
        ["--borrowing"],
    ),
)
def test_simulator_rejects_abbreviated_contact_options_before_execution(
    tmp_path,
    extra_args,
):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(runner.SOURCE_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            *extra_args,
            "--ticks",
            "0",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert extra_args[0] in result.stderr
    assert "ticks must be at least 1" not in result.stderr
    assert not (tmp_path / "data").exists()


def test_plan_loading_rejects_engineering_social_controls(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "social-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": "--enable-social-memory",
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uncontracted social control"):
        runner.load_plan(plan_path)


def test_plan_loading_rejects_engineering_coalition_controls(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "coalitions-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": "--enable-coalition-emergence",
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uncontracted coalition control"):
        runner.load_plan(plan_path)


def test_plan_loading_rejects_engineering_language_controls(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "language-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": "--enable-language-evolution",
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uncontracted language control"):
        runner.load_plan(plan_path)


@pytest.mark.parametrize(
    "extra_args",
    ("--same-coalition", "--enable-coalition-dialect",
     "--same-coalition-reinforcement-multiplier=1.25"),
)
def test_plan_loading_rejects_exact_ambiguous_and_equals_dialect_flags(
    tmp_path,
    extra_args,
):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "dialects-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": extra_args,
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uncontracted dialect control"):
        runner.load_plan(plan_path)


@pytest.mark.parametrize(
    "extra_args",
    (
        "--enable-language-contact",
        "--cross-group-learning-multiplier=1.5",
        "--borrowing",
    ),
)
def test_plan_loading_rejects_exact_equals_and_ambiguous_contact_flags(
    tmp_path,
    extra_args,
):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "contact-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": extra_args,
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uncontracted language contact control"):
        runner.load_plan(plan_path)


@pytest.mark.parametrize(
    "extra_args",
    (
        "--enable-intergenerational-language",
        "--intergenerational-learning-strength=0.2",
        "--maximum-parental",
    ),
)
def test_plan_loading_rejects_intergenerational_option_family(
    tmp_path,
    extra_args,
):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "transmission-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": extra_args,
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="uncontracted intergenerational language control"
    ):
        runner.load_plan(plan_path)


def test_verify_rejects_contact_plan_without_changing_existing_output(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "contact-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": "--borrowing-confidence-threshold=0.5",
            }],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "sentinel").write_bytes(b"unchanged")
    before = snapshot_tree(output)

    with pytest.raises(ValueError, match="uncontracted language contact control"):
        verify_outputs(plan_path, output, validation_mode="strict")

    assert snapshot_tree(output) == before


def test_verify_rejects_intergenerational_plan_without_output_mutation(
    tmp_path,
):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "schema_version": runner.PLAN_SCHEMA_VERSION,
            "experiment_id": "transmission-not-contracted",
            "conditions": [{
                "name": "baseline",
                "seeds": "1",
                "ticks": 1,
                "extra_args": (
                    "--maximum-parental-meanings-per-parent=2"
                ),
            }],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "sentinel").write_bytes(b"unchanged")
    before = snapshot_tree(output)

    with pytest.raises(
        ValueError, match="uncontracted intergenerational language control"
    ):
        verify_outputs(plan_path, output, validation_mode="strict")

    assert snapshot_tree(output) == before


class EscapingDict(dict):
    """Expose the exact dual-view behavior from Review 4 if ever read."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = 0

    def get(self, key, default=None):
        self.reads += 1
        if key == "condition":
            return "baseline"
        return super().get(key, default)

    def __getitem__(self, key):
        self.reads += 1
        if key == "condition":
            return "../unrelated"
        return super().__getitem__(key)


class MutatingAfterReadDict(dict):
    """Mutate its condition after the first access if it is ever trusted."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = 0

    def get(self, key, default=None):
        self.reads += 1
        value = super().get(key, default)
        if self.reads == 1:
            dict.__setitem__(self, "condition", "../unrelated")
        return value

    def __getitem__(self, key):
        self.reads += 1
        return super().__getitem__(key)


class OrdinaryLookingDictSubclass(dict):
    pass


class OrdinaryLookingListSubclass(list):
    pass


class OrdinaryLookingStringSubclass(str):
    pass


class ProxyCell(Mapping):
    def __init__(self, value):
        self.value = value
        self.reads = 0

    def __getitem__(self, key):
        self.reads += 1
        return self.value[key]

    def __iter__(self):
        self.reads += 1
        return iter(self.value)

    def __len__(self):
        self.reads += 1
        return len(self.value)


def test_seed_ranges_are_unique_and_ordered():
    assert parse_seed_range("1-3,2,5") == [1, 2, 3, 5]
    with pytest.raises(ValueError, match="descending"):
        parse_seed_range("5-1")


def test_plan_requires_supported_schema(tmp_path):
    path = write_plan(tmp_path / "plan.json", schema_version=99)
    with pytest.raises(ValueError, match="schema_version"):
        load_plan(path)


def test_valid_schema_two_nonready_root_rejects_resume_and_overwrite_read_only(
    tmp_path,
):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"

    first, _ = run_from_plan(plan_path, output)
    valid, errors = validate_run_outputs(
        output / "baseline" / "seed_1", "baseline", 1)
    assert first[0]["status"] == "completed"
    assert first[0]["result"] == RESULT_COMPLETED
    assert valid, errors

    report = inspect_run_outputs(
        output / "baseline" / "seed_1",
        "baseline",
        1,
        expected_ticks=1,
        mode="strict",
    )
    assert report.valid, report.errors
    assert not report.v2_ready

    with pytest.raises(FileExistsError):
        run_from_plan(plan_path, output)

    assert_resume_rejected_read_only(plan_path, output)

    before = snapshot_tree(output)
    with pytest.raises(UnsafeResumeError, match="cannot overwrite nonempty output root"):
        run_from_plan(plan_path, output, overwrite=True)
    assert snapshot_tree(output) == before

    manifest = json.loads(
        (output / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert manifest["plan_sha256"]


def test_run_result_classification_uses_explicit_terms():
    assert classify_result(0, True) == RESULT_COMPLETED
    assert classify_result(-1, False, timed_out=True) == RESULT_WALL_CLOCK_LIMIT
    assert classify_result(-2, False) == RESULT_CANCELLED
    assert classify_result(130, False) == RESULT_CANCELLED
    assert classify_result(-signal.SIGTERM, False) == RESULT_EXCEPTION
    assert classify_result(1, False) == RESULT_EXCEPTION
    assert classify_result(0, False) == RESULT_INVALID_OUTPUT


@pytest.mark.parametrize(
    "root_kind",
    (
        "manifest_only",
        "manifest_and_index",
        "unknown",
        "stale",
        "extra_condition",
        "partial_cell",
        "plan_hash_mismatch",
    ),
)
def test_every_other_nonempty_resume_root_is_rejected_read_only(
    tmp_path,
    root_kind,
):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"
    output.mkdir()

    if root_kind == "manifest_only":
        write_batch_manifest(output, plan_path)
    elif root_kind == "manifest_and_index":
        write_batch_manifest(output, plan_path)
        (output / "run_index.csv").write_text(
            "condition,seed,status\nbaseline,1,completed\n",
            encoding="utf-8",
        )
    elif root_kind == "unknown":
        (output / "unrelated.bin").write_bytes(b"untrusted evidence\x00")
    elif root_kind == "stale":
        (output / "run_index.csv.tmp").write_text(
            "interrupted atomic index write\n",
            encoding="utf-8",
        )
    elif root_kind == "extra_condition":
        write_batch_manifest(output, plan_path)
        extra_data = output / "unplanned" / "seed_99" / "data"
        extra_data.mkdir(parents=True)
        (extra_data / "old.csv").write_text("old evidence\n", encoding="utf-8")
    elif root_kind == "partial_cell":
        data = output / "baseline" / "seed_1" / "data"
        data.mkdir(parents=True)
        (data / "metrics_baseline_seed_1.csv").write_text(
            "partial metrics\n", encoding="utf-8")
    elif root_kind == "plan_hash_mismatch":
        write_batch_manifest(output, plan_path, plan_sha256="0" * 64)
    else:  # pragma: no cover - protects future parameter edits.
        raise AssertionError(f"unknown root kind: {root_kind}")

    assert any(output.iterdir())
    assert_resume_rejected_read_only(plan_path, output)


@pytest.mark.parametrize("create_root", (False, True), ids=("absent", "empty"))
def test_resume_allows_absent_and_empty_output_roots(tmp_path, create_root):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"
    if create_root:
        output.mkdir()

    results, root = run_from_plan(plan_path, output, resume=True)

    assert root == output
    assert results[0]["runner_action"] == "executed"
    assert results[0]["result"] == RESULT_COMPLETED
    assert (output / "experiment_manifest.json").is_file()


def test_timeout_kills_and_reaps_real_child_and_blocks_resume(tmp_path, monkeypatch):
    plan_path = write_plan(tmp_path / "plan.json", timeout_seconds=1)
    output = tmp_path / "outputs"
    child_script = "\n".join(
        (
            "from pathlib import Path",
            "import os",
            "import time",
            "Path('child.pid').write_text(str(os.getpid()), encoding='utf-8')",
            "Path('data').mkdir()",
            "Path('data/metrics_baseline_seed_1.csv').write_text("
            "'partial metrics\\n', encoding='utf-8')",
            "time.sleep(60)",
            "Path('child-survived.txt').write_text('unexpected', encoding='utf-8')",
        )
    )
    monkeypatch.setattr(
        "run_experiments._simulation_command",
        lambda *args: [sys.executable, "-c", child_script],
    )

    results, _ = run_from_plan(plan_path, output)

    result = results[0]
    run_dir = output / "baseline" / "seed_1"
    assert result["result"] == RESULT_WALL_CLOCK_LIMIT
    assert result["ok"] is False
    assert result["returncode"] == -1
    assert_pid_reaped(int((run_dir / "child.pid").read_text(encoding="utf-8")))
    assert not (run_dir / "child-survived.txt").exists()
    valid, errors = validate_run_outputs(
        run_dir,
        "baseline",
        1,
        expected_ticks=1,
        mode="strict",
    )
    assert not valid
    assert errors
    assert_resume_rejected_read_only(plan_path, output)


def test_sigint_cancellation_is_classified_and_blocks_resume(tmp_path, monkeypatch):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"
    monkeypatch.setattr(
        "run_experiments._simulation_command",
        lambda *args: [
            sys.executable,
            "-c",
            "import os, signal; os.kill(os.getpid(), signal.SIGINT)",
        ],
    )

    results, _ = run_from_plan(plan_path, output)

    result = results[0]
    assert result["result"] == RESULT_CANCELLED
    assert result["status"] == RESULT_CANCELLED
    assert result["returncode"] in {-signal.SIGINT, 128 + signal.SIGINT}
    valid, errors = validate_run_outputs(
        output / "baseline" / "seed_1",
        "baseline",
        1,
        expected_ticks=1,
        mode="strict",
    )
    assert not valid
    assert errors
    assert_resume_rejected_read_only(plan_path, output)


def test_symlinked_output_ancestor_is_rejected_before_creating_root(tmp_path):
    plan_path = write_plan(tmp_path / "plan.json")
    external = tmp_path / "external"
    external.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(external, target_is_directory=True)
    output = linked_parent / "outputs"

    before = snapshot_tree(external)
    with pytest.raises(UnsafeResumeError, match="symlinked path component"):
        run_from_plan(plan_path, output, resume=True)
    assert snapshot_tree(external) == before
    assert not (external / "outputs").exists()


def test_cli_does_not_resolve_a_symlinked_output_root(tmp_path, monkeypatch):
    plan_path = write_plan(tmp_path / "plan.json")
    external = tmp_path / "external"
    external.mkdir()
    output = tmp_path / "output-link"
    output.symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiments.py",
            "--plan",
            str(plan_path),
            "--output-dir",
            str(output),
            "--resume",
        ],
    )

    before = snapshot_tree(external)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert snapshot_tree(external) == before


def test_direct_run_rejects_symlinked_condition_parent(tmp_path):
    output = tmp_path / "outputs"
    output.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (output / "baseline").symlink_to(external, target_is_directory=True)

    output_before = snapshot_tree(output)
    external_before = snapshot_tree(external)
    with pytest.raises(UnsafeResumeError, match="symlinked path component"):
        run_single(1, "baseline", 1, [], output)
    assert snapshot_tree(output) == output_before
    assert snapshot_tree(external) == external_before


def test_old_fresh_batch_capability_surface_is_removed():
    assert not hasattr(runner, "_FRESH_BATCH_SECRET")
    assert not hasattr(runner, "_FreshBatchContext")
    assert not hasattr(runner, "_run_single_in_fresh_batch")


@pytest.mark.parametrize(
    "cell_factory",
    (
        pytest.param(lambda cell: EscapingDict(cell), id="dual-view-dict"),
        pytest.param(
            lambda cell: MutatingAfterReadDict(cell),
            id="mutating-after-read",
        ),
        pytest.param(
            lambda cell: OrdinaryLookingDictSubclass(cell),
            id="ordinary-dict-subclass",
        ),
        pytest.param(lambda cell: ProxyCell(cell), id="custom-mapping"),
        pytest.param(
            lambda cell: MappingProxyType(cell),
            id="mapping-proxy",
        ),
    ),
)
def test_private_orchestrator_rejects_nonexact_cell_mappings_without_mutation(
    tmp_path,
    monkeypatch,
    cell_factory,
):
    output = tmp_path / "outputs"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    sentinel = unrelated / "sentinel.bin"
    sentinel.write_bytes(b"preserve every byte\x00\xff")
    (unrelated / "sentinel-link").symlink_to(sentinel.name)
    cell = cell_factory(fresh_cell_spec()[0])
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    before = snapshot_tree(tmp_path)

    with pytest.raises(ValueError, match="exact built-in dict"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()
    assert not (unrelated / "seed_1").exists()
    assert snapshot_tree(tmp_path) == before
    if hasattr(cell, "reads"):
        assert cell.reads == 0


def test_private_orchestrator_uses_frozen_copy_after_external_dict_mutation(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "sentinel.bin").write_bytes(b"unchanged\x00")
    unrelated_before = snapshot_tree(unrelated)
    cell = fresh_cell_spec()[0]
    input_cells = [cell]
    command_calls = []
    original_preflight = runner._preflight_fresh_output_root

    def preflight_then_mutate(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        cell["condition"] = "../unrelated"
        cell["seed"] = 999
        cell["ticks"] = 999
        cell["extra_args"].append("--mutated-after-freeze")
        input_cells.clear()
        return result

    def tiny_command(seed, condition, ticks, extra_args):
        command_calls.append((seed, condition, ticks, extra_args))
        return [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('frozen.txt').write_text('ok')",
        ]

    monkeypatch.setattr(
        runner, "_preflight_fresh_output_root", preflight_then_mutate)
    monkeypatch.setattr(runner, "_simulation_command", tiny_command)
    monkeypatch.setattr(
        runner,
        "inspect_run_outputs",
        lambda *args, **kwargs: SimpleNamespace(
            valid=True,
            errors=[],
            v2_ready=False,
        ),
    )

    results, root = runner._run_cells_in_fresh_root(input_cells, output)

    assert root == output
    assert command_calls == [(1, "baseline", 1, ())]
    assert results[0]["condition"] == "baseline"
    assert results[0]["seed"] == 1
    assert results[0]["run_dir"] == "baseline/seed_1"
    assert (output / "baseline" / "seed_1" / "frozen.txt").read_text() == "ok"
    assert not (unrelated / "seed_999").exists()
    assert snapshot_tree(unrelated) == unrelated_before


@pytest.mark.parametrize(
    ("field", "value"),
    (
        pytest.param("condition", "../unrelated", id="condition-traversal"),
        pytest.param("condition", "/absolute", id="condition-absolute"),
        pytest.param("condition", "bad/name", id="condition-separator"),
        pytest.param("condition", "bad\\name", id="condition-alt-separator"),
        pytest.param("condition", 1, id="condition-non-string"),
        pytest.param(
            "condition",
            OrdinaryLookingStringSubclass("baseline"),
            id="condition-string-subclass",
        ),
        pytest.param("seed", True, id="seed-bool"),
        pytest.param("seed", "1", id="seed-non-integer"),
        pytest.param("ticks", True, id="ticks-bool"),
        pytest.param("ticks", 0, id="ticks-nonpositive"),
        pytest.param("ticks", "1", id="ticks-non-integer"),
        pytest.param("extra_args", (), id="args-non-list"),
        pytest.param(
            "extra_args",
            OrdinaryLookingListSubclass(),
            id="args-list-subclass",
        ),
        pytest.param("extra_args", [1], id="args-non-string-item"),
        pytest.param(
            "extra_args",
            [OrdinaryLookingStringSubclass("--value")],
            id="args-string-subclass-item",
        ),
        pytest.param("timeout_seconds", True, id="timeout-bool"),
        pytest.param("timeout_seconds", 0, id="timeout-nonpositive"),
        pytest.param("timeout_seconds", "5", id="timeout-non-integer"),
        pytest.param("announcement", False, id="announcement-non-string"),
    ),
)
def test_private_orchestrator_rejects_malformed_cell_primitives_before_root(
    tmp_path,
    monkeypatch,
    field,
    value,
):
    output = tmp_path / "outputs"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "sentinel.bin").write_bytes(b"untouched")
    cell = fresh_cell_spec()[0]
    cell[field] = value
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    before = snapshot_tree(tmp_path)

    with pytest.raises(ValueError):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()
    assert snapshot_tree(tmp_path) == before


@pytest.mark.parametrize("key_case", ("missing", "unexpected"))
def test_private_orchestrator_rejects_wrong_cell_keys_before_root(
    tmp_path,
    monkeypatch,
    key_case,
):
    output = tmp_path / "outputs"
    cell = fresh_cell_spec()[0]
    if key_case == "missing":
        cell.pop("ticks")
    else:
        cell["not_in_contract"] = "value"
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )

    with pytest.raises(ValueError, match="cell keys"):
        runner._run_cells_in_fresh_root([cell], output)

    assert child_calls == []
    assert not output.exists()


@pytest.mark.parametrize("flag_name", ("resume", "overwrite", "direct"))
def test_private_orchestrator_rejects_nonboolean_flags_before_root(
    tmp_path,
    flag_name,
):
    output = tmp_path / "outputs"

    with pytest.raises(ValueError, match="must be a boolean"):
        runner._run_cells_in_fresh_root(
            fresh_cell_spec(),
            output,
            **{flag_name: 1},
        )

    assert not output.exists()


@pytest.mark.parametrize(
    "tree_kind",
    (
        "unknown_root",
        "schema_two_cell",
        "manifest_only",
        "unrelated_sentinel",
    ),
)
def test_private_fresh_root_orchestrator_rejects_nonempty_roots_read_only(
    tmp_path,
    monkeypatch,
    tree_kind,
):
    output = tmp_path / "outputs"
    output.mkdir()
    if tree_kind == "unknown_root":
        (output / "different-condition" / "seed_99").mkdir(parents=True)
    elif tree_kind == "schema_two_cell":
        data = output / "baseline" / "seed_99" / "data"
        data.mkdir(parents=True)
        (data / "run_manifest_baseline_seed_99.json").write_text(
            json.dumps({"schema_version": 2}) + "\n",
            encoding="utf-8",
        )
    elif tree_kind == "manifest_only":
        (output / "experiment_manifest.json").write_text(
            '{"schema_version": 1}\n', encoding="utf-8")
    elif tree_kind == "unrelated_sentinel":
        (output / "do-not-touch.bin").write_bytes(b"preserve me\xff")
    else:  # pragma: no cover - protects future parameter edits.
        raise AssertionError(tree_kind)

    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    before = snapshot_tree(output)

    with pytest.raises((UnsafeResumeError, FileExistsError)):
        runner._run_cells_in_fresh_root(
            fresh_cell_spec(), output, direct=False)

    assert child_calls == []
    assert snapshot_tree(output) == before


def test_private_fresh_root_orchestrator_has_no_rebind_or_reuse_argument(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    output.mkdir()
    sentinel = output / "sentinel.bin"
    sentinel.write_bytes(b"unchanged\x00")
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    before = snapshot_tree(output)

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        runner._run_cells_in_fresh_root(
            fresh_cell_spec(), output, context=object())

    assert child_calls == []
    assert snapshot_tree(output) == before


def test_fresh_batch_revalidates_the_owned_layout_before_each_cell(
    tmp_path,
    monkeypatch,
):
    plan_path = write_plan(
        tmp_path / "plan.json",
        conditions=[{"name": "baseline", "seeds": "1,2"}],
    )
    output = tmp_path / "outputs"
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_code_revision",
        lambda: {"commit": "c" * 40, "dirty": True},
    )

    def inject_unknown_root_entry(*args, **kwargs):
        child_calls.append((args, kwargs))
        (output / "not-created-by-runner.bin").write_bytes(b"external")
        return runner.subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", inject_unknown_root_entry)

    with pytest.raises(UnsafeResumeError, match="root layout changed"):
        run_from_plan(plan_path, output)

    assert len(child_calls) == 1
    assert not (output / "baseline" / "seed_2").exists()


@pytest.mark.parametrize(
    "replacement_kind",
    ("ordinary-directory", "symlink"),
)
def test_fresh_batch_rejects_replaced_condition_before_next_child(
    tmp_path,
    monkeypatch,
    replacement_kind,
):
    output = tmp_path / "outputs"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "sentinel.bin").write_bytes(b"unrelated evidence\x00")
    unrelated_before = snapshot_tree(unrelated)
    relocated = tmp_path / "relocated-condition"
    child_calls = []
    cells = [
        {**fresh_cell_spec()[0], "seed": seed}
        for seed in (1, 2)
    ]

    def replace_condition(*args, **kwargs):
        child_calls.append(kwargs["cwd"])
        condition_path = output / "baseline"
        condition_path.rename(relocated)
        if replacement_kind == "symlink":
            condition_path.symlink_to(unrelated, target_is_directory=True)
        else:
            condition_path.mkdir()
            (condition_path / "seed_1").mkdir()
        return runner.subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", replace_condition)

    with pytest.raises(UnsafeResumeError, match="condition path"):
        runner._run_cells_in_fresh_root(cells, output)

    assert len(child_calls) == 1
    assert not (output / "baseline" / "seed_2").exists()
    assert snapshot_tree(unrelated) == unrelated_before


def test_fresh_batch_rejects_symlinked_root_ancestor_before_next_child(
    tmp_path,
    monkeypatch,
):
    parent = tmp_path / "owned-parent"
    parent.mkdir()
    output = parent / "outputs"
    relocated_parent = tmp_path / "relocated-parent"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "sentinel.bin").write_bytes(b"unrelated evidence\xff")
    unrelated_before = snapshot_tree(unrelated)
    child_calls = []
    cells = [
        {**fresh_cell_spec()[0], "seed": seed}
        for seed in (1, 2)
    ]

    def replace_ancestor(*args, **kwargs):
        child_calls.append(kwargs["cwd"])
        parent.rename(relocated_parent)
        parent.symlink_to(unrelated, target_is_directory=True)
        return runner.subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", replace_ancestor)

    with pytest.raises(UnsafeResumeError, match="symlinked path component"):
        runner._run_cells_in_fresh_root(cells, output)

    assert len(child_calls) == 1
    assert not (unrelated / "outputs").exists()
    assert not (
        relocated_parent / "outputs" / "baseline" / "seed_2"
    ).exists()
    assert snapshot_tree(unrelated) == unrelated_before


def test_fresh_batch_executes_multiple_frozen_cells_with_tiny_children(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "outputs"
    command_calls = []
    cells = [
        {
            **fresh_cell_spec()[0],
            "seed": seed,
            "extra_args": [f"--cell={seed}"],
            "announcement": f"cell {seed}",
        }
        for seed in (1, 2)
    ]
    batch_manifest = {
        "schema_version": 1,
        "experiment_id": "tiny-orchestrator-test",
        "results": [],
    }

    def tiny_command(seed, condition, ticks, extra_args):
        command_calls.append((seed, condition, ticks, extra_args))
        script = (
            "from pathlib import Path; "
            f"Path('tiny-child.txt').write_text({str(seed)!r}, encoding='utf-8')"
        )
        return [sys.executable, "-c", script]

    monkeypatch.setattr(runner, "_simulation_command", tiny_command)
    monkeypatch.setattr(
        runner,
        "inspect_run_outputs",
        lambda *args, **kwargs: SimpleNamespace(
            valid=True,
            errors=[],
            v2_ready=False,
        ),
    )

    results, root = runner._run_cells_in_fresh_root(
        cells,
        output,
        batch_manifest=batch_manifest,
    )

    assert root == output
    assert command_calls == [
        (1, "baseline", 1, ("--cell=1",)),
        (2, "baseline", 1, ("--cell=2",)),
    ]
    assert [result["status"] for result in results] == [
        RESULT_COMPLETED,
        RESULT_COMPLETED,
    ]
    assert [result["run_dir"] for result in results] == [
        "baseline/seed_1",
        "baseline/seed_2",
    ]
    assert {path.name for path in output.iterdir()} == {
        "baseline",
        "experiment_manifest.json",
        "run_index.csv",
    }
    condition_path = output / "baseline"
    assert {path.name for path in condition_path.iterdir()} == {
        "seed_1",
        "seed_2",
    }
    for seed in (1, 2):
        run_dir = condition_path / f"seed_{seed}"
        assert run_dir.resolve().is_relative_to(output.resolve())
        assert {path.name for path in run_dir.iterdir()} == {"tiny-child.txt"}
        assert (run_dir / "tiny-child.txt").read_text(encoding="utf-8") == str(seed)


@pytest.mark.parametrize("link_kind", ("root", "cell"))
def test_private_fresh_root_orchestrator_rejects_symlinked_paths_read_only(
    tmp_path,
    monkeypatch,
    link_kind,
):
    external = tmp_path / "external"
    external.mkdir()
    output = tmp_path / "outputs"
    if link_kind == "root":
        output.symlink_to(external, target_is_directory=True)
    else:
        output.mkdir()
        condition = output / "baseline"
        condition.mkdir()
        (condition / "seed_1").symlink_to(
            external, target_is_directory=True)
    child_calls = []
    monkeypatch.setattr(
        runner,
        "_simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    external_before = snapshot_tree(external)
    output_before = None if output.is_symlink() else snapshot_tree(output)

    with pytest.raises(UnsafeResumeError, match="symlinked"):
        runner._run_cells_in_fresh_root(fresh_cell_spec(), output)

    assert child_calls == []
    assert snapshot_tree(external) == external_before
    if output_before is not None:
        assert snapshot_tree(output) == output_before


@pytest.mark.parametrize(
    "tree_kind",
    (
        "unknown_root",
        "ordinary_cell",
        "schema_two_cell",
        "partial_cell",
        "manifest_only",
        "unrelated_sentinel",
    ),
)
@pytest.mark.parametrize(
    "runner_flags",
    ({}, {"resume": False}, {"resume": True}, {"overwrite": True}),
    ids=("ordinary", "resume-false", "resume-true", "overwrite-true"),
)
def test_direct_run_rejects_every_nonempty_root_without_starting_child(
    tmp_path,
    monkeypatch,
    tree_kind,
    runner_flags,
):
    output = tmp_path / "outputs"
    output.mkdir()
    if tree_kind == "unknown_root":
        (output / "different-condition" / "seed_99").mkdir(parents=True)
    elif tree_kind == "ordinary_cell":
        cell = output / "baseline" / "seed_1"
        cell.mkdir(parents=True)
        (cell / "sentinel.txt").write_bytes(b"ordinary cell\x00")
    elif tree_kind == "schema_two_cell":
        data = output / "baseline" / "seed_1" / "data"
        data.mkdir(parents=True)
        (data / "run_manifest_baseline_seed_1.json").write_text(
            json.dumps({"schema_version": 2}) + "\n",
            encoding="utf-8",
        )
    elif tree_kind == "partial_cell":
        data = output / "baseline" / "seed_1" / "data"
        data.mkdir(parents=True)
        (data / "metrics_baseline_seed_1.csv").write_text(
            "partial\n", encoding="utf-8")
    elif tree_kind == "manifest_only":
        (output / "experiment_manifest.json").write_text(
            '{"schema_version": 1}\n', encoding="utf-8")
    elif tree_kind == "unrelated_sentinel":
        (output / "do-not-touch.bin").write_bytes(b"preserve me\xff")
    else:  # pragma: no cover - protects parameter edits.
        raise AssertionError(tree_kind)

    child_calls = []
    monkeypatch.setattr(
        "run_experiments._simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    before = snapshot_tree(output)
    with pytest.raises(UnsafeResumeError, match="nonempty output root"):
        run_single(1, "baseline", 1, [], output, **runner_flags)

    assert child_calls == []
    assert snapshot_tree(output) == before


@pytest.mark.parametrize("link_kind", ("root", "cell"))
def test_direct_run_rejects_symlinked_root_or_cell_read_only(
    tmp_path,
    monkeypatch,
    link_kind,
):
    external = tmp_path / "external"
    external.mkdir()
    output = tmp_path / "outputs"
    if link_kind == "root":
        output.symlink_to(external, target_is_directory=True)
    else:
        output.mkdir()
        condition = output / "baseline"
        condition.mkdir()
        (condition / "seed_1").symlink_to(
            external, target_is_directory=True)

    child_calls = []
    monkeypatch.setattr(
        "run_experiments._simulation_command",
        lambda *args: child_calls.append(args) or [sys.executable, "-c", "pass"],
    )
    external_before = snapshot_tree(external)
    output_before = None if output.is_symlink() else snapshot_tree(output)

    with pytest.raises(UnsafeResumeError, match="symlinked"):
        run_single(1, "baseline", 1, [], output)

    assert child_calls == []
    assert snapshot_tree(external) == external_before
    if output_before is not None:
        assert snapshot_tree(output) == output_before


def test_verify_defaults_to_auto_and_labels_schema_one_legacy(
    tmp_path, capsys,
):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"
    run_from_plan(plan_path, output)
    manifest_path = (
        output / "baseline" / "seed_1" / "data"
        / "run_manifest_baseline_seed_1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    for field_name in (
        "requested_ticks", "final_tick", "completed_ticks",
        "termination_reason", "result_status", "completed_normally",
        "writer_health", "artifact_inventory", "artifact_inventory_errors",
        "artifact_schema_versions", "metrics_timing_contract",
    ):
        manifest.pop(field_name, None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert verify_outputs(plan_path, output) is True
    output_text = capsys.readouterr().out
    assert "LEGACY — not V2-ready" in output_text
    assert "v2_ready=false" in output_text
    assert verify_outputs(
        plan_path, output, validation_mode="strict") is False


def test_resume_rejects_legacy_artifacts_without_mutating_them(tmp_path):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"
    run_from_plan(plan_path, output)
    manifest_path = (
        output / "baseline" / "seed_1" / "data"
        / "run_manifest_baseline_seed_1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*") if path.is_file()
    }

    with pytest.raises(UnsafeResumeError, match="preserved every existing byte unchanged"):
        run_from_plan(plan_path, output, resume=True)

    after = {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*") if path.is_file()
    }
    assert after == before
