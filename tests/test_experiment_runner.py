"""Versioning, validation, and resume behavior for experiment batches."""

import json

import pytest

from run_experiments import (
    RESULT_CANCELLED,
    RESULT_COMPLETED,
    RESULT_EXCEPTION,
    RESULT_INVALID_OUTPUT,
    RESULT_WALL_CLOCK_LIMIT,
    classify_result,
    load_plan,
    parse_seed_range,
    run_from_plan,
    validate_run_outputs,
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


def test_seed_ranges_are_unique_and_ordered():
    assert parse_seed_range("1-3,2,5") == [1, 2, 3, 5]
    with pytest.raises(ValueError, match="descending"):
        parse_seed_range("5-1")


def test_plan_requires_supported_schema(tmp_path):
    path = write_plan(tmp_path / "plan.json", schema_version=99)
    with pytest.raises(ValueError, match="schema_version"):
        load_plan(path)


def test_batch_refuses_overwrite_and_resumes_valid_run(tmp_path):
    plan_path = write_plan(tmp_path / "plan.json")
    output = tmp_path / "outputs"

    first, _ = run_from_plan(plan_path, output)
    valid, errors = validate_run_outputs(
        output / "baseline" / "seed_1", "baseline", 1)
    assert first[0]["status"] == "completed"
    assert first[0]["result"] == RESULT_COMPLETED
    assert valid, errors

    with pytest.raises(FileExistsError):
        run_from_plan(plan_path, output)

    resumed, _ = run_from_plan(plan_path, output, resume=True)
    assert resumed[0]["status"] == "skipped"
    assert resumed[0]["result"] == RESULT_COMPLETED
    assert resumed[0]["runner_action"] == "skipped_existing"
    assert resumed[0]["state_hash"] == first[0]["state_hash"]

    manifest = json.loads(
        (output / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert manifest["plan_sha256"]


def test_run_result_classification_uses_explicit_terms():
    assert classify_result(0, True) == RESULT_COMPLETED
    assert classify_result(-1, False, timed_out=True) == RESULT_WALL_CLOCK_LIMIT
    assert classify_result(-2, False) == RESULT_CANCELLED
    assert classify_result(1, False) == RESULT_EXCEPTION
    assert classify_result(0, False) == RESULT_INVALID_OUTPUT
