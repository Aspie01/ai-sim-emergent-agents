"""Adversarial tests for streamed simulation-artifact validation."""

import csv
import gc
import json
import os
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import pytest

from thalren_vale.artifact_contract import (
    BELIEFS_HEADER,
    BELIEFS_SCHEMA_VERSION,
    BELIEF_SNAPSHOT_CARDINALITY,
    BELIEF_SNAPSHOT_INTERVAL,
    EVENTS_HEADER,
    METRICS_CUMULATIVE_FIELDS,
    METRICS_HEADER,
    METRICS_NONNEGATIVE_FLOAT_FIELDS,
    METRICS_NONNEGATIVE_INTEGER_FIELDS,
    METRICS_SCHEMA_VERSION,
    METRICS_TIMING_CONTRACT,
    RUN_MANIFEST_SCHEMA_VERSION,
    RUN_SUMMARY_HEADER,
    RUN_SUMMARY_SCHEMA_VERSION,
    SUMMARY_NONNEGATIVE_FLOAT_FIELDS,
    SUMMARY_NONNEGATIVE_INTEGER_FIELDS,
    TECHNOLOGY_IDENTIFIERS,
)
from thalren_vale.artifact_validation import (
    ExpectedRunContract,
    ValidationPolicy,
    inspect_run_outputs,
)
from thalren_vale.events import EVENT_SCHEMA_VERSION
from thalren_vale.config import (
    COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY,
    DIALECT_NOTICE_WITHOUT_COALITIONS,
    DIALECT_NOTICE_WITHOUT_LANGUAGE,
    INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
    SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY,
)
from thalren_vale.metrics import MetricsLogger
from thalren_vale.reproducibility import (
    build_artifact_inventory,
    write_run_manifest,
)


SEED = 11
CONDITION = "synthetic"


def _write_csv(path: Path, header: tuple[str, ...], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _metric_row(
    seed: int,
    tick: int,
    population: int,
    factions: int,
    counters: dict[str, int],
) -> list[object]:
    return [
        seed, tick, population, factions, 0,
        counters["war_declared"], counters["death"], counters["birth"],
        round(0.1 + min(tick, 1000) * 0.0001, 4), 1.0, 3.0, 0,
        0, 0, 0.0,
        factions, factions,
        counters["schism"], counters["merger"], tick,
        0.0, 0.0, 8, 0,
    ]


def _summary_row(
    seed: int,
    condition: str,
    populations: list[int],
    factions: list[int],
    event_rows: list[list[object]],
) -> list[object]:
    final_tick = len(populations)
    gini_values = [
        round(0.1 + min(tick, 1000) * 0.0001, 4)
        for tick in range(1, final_tick + 1)
    ]
    event_counts: dict[str, int] = {}
    event_ticks: dict[str, list[int]] = {}
    for row in event_rows:
        event_type = str(row[3])
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        event_ticks.setdefault(event_type, []).append(int(row[2]))
    return [
        seed, condition, populations[-1], max(populations),
        min(value for value in populations if value > 0) if any(populations) else 0,
        event_counts.get("faction_formed", 0), factions[-1], max(factions),
        min(event_ticks.get("faction_formed", [0])),
        event_counts.get("war_declared", 0),
        event_counts.get("death", 0), event_counts.get("birth", 0),
        event_counts.get("schism", 0), event_counts.get("merger", 0),
        round(sum(gini_values) / len(gini_values), 4),
        gini_values[-1], max(gini_values), 0, 0.0,
        event_counts.get("treaty_signed", 0),
        event_counts.get("treaty_broken", 0), 0, 0.0,
        event_counts.get("stagnation_trigger", 0),
        event_counts.get("era_shift", 0), 0.1, 1.0,
    ]


def _writer_health(**overrides) -> dict:
    health = {
        "metrics_write_failures": 0,
        "metrics_flush_failures": 0,
        "event_write_failures": 0,
        "event_flush_failures": 0,
        "event_flush_failures_recovered": 0,
        "event_flush_failures_unrecovered": 0,
        "belief_write_failures": 0,
        "belief_flush_failures": 0,
        "summary_write_failures": 0,
        "close_failures": 0,
        "finalization_failures": 0,
        "pending_event_rows": 0,
        "finalized": True,
        "closed": True,
        "unresolved_failures": [],
    }
    health.update(overrides)
    return health


def make_artifacts(
    root: Path,
    *,
    requested_ticks: int = 3,
    populations: list[int] | None = None,
    termination_reason: str = "requested_ticks_reached",
    result_status: str = "completed",
    completed_normally: bool = True,
    event_rows: list[list[object]] | None = None,
    belief_rows: list[list[object]] | None = None,
    summary_rows: list[list[object]] | None = None,
) -> tuple[Path, Path]:
    populations = populations or [3, 4, 3]
    final_tick = len(populations)
    default_events = [
        [EVENT_SCHEMA_VERSION, SEED, 1, "faction_formed", "F", "", "formed"],
        [EVENT_SCHEMA_VERSION, SEED, 2, "birth", "A", "B", "child"],
        [EVENT_SCHEMA_VERSION, SEED, 3, "death", "C", "", "died"],
    ] if final_tick >= 3 else []
    actual_event_rows = event_rows if event_rows is not None else default_events
    factions = [1 if actual_event_rows else 0] * final_tick
    cumulative = {
        "war_declared": 0, "death": 0, "birth": 0,
        "schism": 0, "merger": 0,
    }
    event_rows_by_tick: dict[int, list[list[object]]] = {}
    for row in actual_event_rows:
        event_rows_by_tick.setdefault(int(row[2]), []).append(row)
    metric_rows = []
    for tick, population in enumerate(populations, start=1):
        for row in event_rows_by_tick.get(tick, []):
            event_type = str(row[3])
            if event_type in cumulative:
                cumulative[event_type] += 1
        metric_rows.append(
            _metric_row(SEED, tick, population, factions[tick - 1], cumulative))
    run_dir = root / "run"
    data = run_dir / "data"
    metrics_path = data / f"metrics_{CONDITION}_seed_{SEED}.csv"
    events_path = data / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    beliefs_path = data / f"beliefs_{CONDITION}_seed_{SEED}.csv"
    summary_path = data / "run_summaries.csv"
    manifest_path = data / f"run_manifest_{CONDITION}_seed_{SEED}.json"

    _write_csv(
        metrics_path,
        METRICS_HEADER,
        metric_rows,
    )
    _write_csv(
        events_path,
        EVENTS_HEADER,
        actual_event_rows,
    )
    _write_csv(
        beliefs_path,
        BELIEFS_HEADER,
        belief_rows if belief_rows is not None else [],
    )
    _write_csv(
        summary_path,
        RUN_SUMMARY_HEADER,
        summary_rows if summary_rows is not None else [
            _summary_row(
                SEED, CONDITION, populations, factions, actual_event_rows)
        ],
    )
    inventory, inventory_errors = build_artifact_inventory(
        str(data), seed=SEED, condition=CONDITION)
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "artifact_schema_versions": {
            "metrics": METRICS_SCHEMA_VERSION,
            "events": EVENT_SCHEMA_VERSION,
            "beliefs": BELIEFS_SCHEMA_VERSION,
            "summary": RUN_SUMMARY_SCHEMA_VERSION,
        },
        "metrics_timing_contract": METRICS_TIMING_CONTRACT,
        "seed": SEED,
        "condition": CONDITION,
        "requested_ticks": requested_ticks,
        "final_tick": final_tick,
        "completed_ticks": final_tick,
        "termination_reason": termination_reason,
        "result_status": result_status,
        "completed_normally": completed_normally,
        "configuration": {"ticks": requested_ticks, "condition": CONDITION},
        "log_mode": "metrics_only",
        "execution_mode": "serial",
        "language_endpoint": {
            "name": "comprehension_success_rate",
            "definition": (
                "successful_interpretation_count / "
                "communication_attempt_count"
            ),
            "communication_attempt_count": 0,
            "successful_interpretation_count": 0,
            "comprehension_success_rate": None,
            "measured_at_tick": 3,
            "analysis_contract": "unspecified",
        },
        "state_hash_algorithm": "sha256",
        "state_hash": "a" * 64,
        "required_outputs": [
            "metrics", "events", "beliefs", "run_summary", "run_manifest",
        ],
        "writer_health": _writer_health(),
        "artifact_policy": {
            "allow_zero_events": True,
            "belief_snapshot_interval": BELIEF_SNAPSHOT_INTERVAL,
            "belief_snapshot_cardinality": BELIEF_SNAPSHOT_CARDINALITY,
        },
        "finalization_diagnostics": [],
        "artifact_inventory": inventory,
        "artifact_inventory_errors": inventory_errors,
    }
    manifest["configuration"].update({
        "log_mode": "metrics_only",
        "anti_stagnation_enabled": False,
        "disabled_layers": [],
        "raids_enabled": True,
        "social_memory_enabled": False,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "disabled",
        "social_control_notices": [],
        "language_evolution_enabled": False,
        "maximum_language_associations": 32,
        "maximum_signal_length": 3,
        "language_learning_rate": 0.20,
        "language_reinforcement_rate": 0.10,
        "language_forgetting_interval": 25,
        "language_invention_enabled": True,
        "language_controls_status": "disabled",
        "language_control_notices": [],
        "coalition_emergence_enabled": False,
        "coalition_minimum_size": 3,
        "coalition_trust_threshold": 0.24,
        "coalition_familiarity_threshold": 0.40,
        "coalition_maximum_grievance": 0.20,
        "coalition_persistence_ticks": 5,
        "maximum_active_coalitions": 32,
        "coalition_controls_status": "disabled",
        "coalition_control_notices": [],
        "coalition_dialect_influence_enabled": False,
        "same_coalition_learning_multiplier": 1.50,
        "same_coalition_reinforcement_multiplier": 1.25,
        "dialect_controls_status": "disabled",
        "dialect_control_notices": [],
        "language_contact_enabled": False,
        "cross_group_learning_multiplier": 1.50,
        "borrowing_exposure_threshold": 3,
        "borrowing_confidence_threshold": 0.50,
        "language_contact_controls_status": "disabled",
        "language_contact_control_notices": [],
        "intergenerational_language_enabled": False,
        "maximum_parental_meanings_per_parent": 2,
        "intergenerational_learning_strength": 0.20,
        "intergenerational_language_controls_status": "disabled",
        "intergenerational_language_control_notices": [],
        "lexical_evolution_enabled": False,
        "lexical_mutation_rate": 0.05,
        "maximum_lexical_lineage_depth": 8,
        "lexical_evolution_controls_status": "disabled",
        "lexical_evolution_control_notices": [],
        "compositional_protolanguage_enabled": False,
        "maximum_resource_morpheme_length": 2,
        "modality_morpheme_length": 1,
        "compositional_protolanguage_controls_status": "disabled",
        "compositional_protolanguage_control_notices": [],
        "grammar_evolution_enabled": False,
        "order_adoption_threshold": 3,
        "grammar_evolution_controls_status": "disabled",
        "grammar_evolution_control_notices": [],
        "language_coevolution_enabled": False,
        "intelligibility_reward": 0.06,
        "intelligibility_penalty": 0.04,
        "language_coevolution_controls_status": "disabled",
        "language_coevolution_control_notices": [],
        "coalition_intelligibility_enabled": False,
        "coalition_intelligibility_threshold": 0.50,
        "coalition_intelligibility_controls_status": "disabled",
        "coalition_intelligibility_control_notices": [],
        "production_trial_enabled": False,
        "production_trial_interval": 8,
        "production_trial_controls_status": "disabled",
        "production_trial_control_notices": [],
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir, manifest_path


def make_authentic_schema_one_artifacts(root: Path) -> Path:
    """Construct the historical schema-1 shape without downgrading schema 2."""
    run_dir = root / "legacy_run"
    data = run_dir / "data"
    counters = {
        "war_declared": 0,
        "death": 0,
        "birth": 0,
        "schism": 0,
        "merger": 0,
    }
    metrics = [_metric_row(SEED, 1, 2, 0, counters)]
    _write_csv(
        data / f"metrics_{CONDITION}_seed_{SEED}.csv",
        METRICS_HEADER,
        metrics,
    )
    _write_csv(
        data / f"faction_events_{CONDITION}_seed_{SEED}.csv",
        EVENTS_HEADER,
        [],
    )
    _write_csv(
        data / f"beliefs_{CONDITION}_seed_{SEED}.csv",
        BELIEFS_HEADER,
        [],
    )
    _write_csv(
        data / "run_summaries.csv",
        RUN_SUMMARY_HEADER,
        [_summary_row(SEED, CONDITION, [2], [0], [])],
    )
    manifest = {
        "schema_version": 1,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "seed": SEED,
        "condition": CONDITION,
        "configuration": {"ticks": 1, "condition": CONDITION},
        "execution_mode": "serial",
        "language_endpoint": {
            "name": "comprehension_success_rate",
            "definition": (
                "successful_interpretation_count / "
                "communication_attempt_count"
            ),
            "communication_attempt_count": 0,
            "successful_interpretation_count": 0,
            "comprehension_success_rate": None,
            "measured_at_tick": 3,
            "analysis_contract": "unspecified",
        },
        "state_hash_algorithm": "sha256",
        "state_hash": "a" * 64,
        "code": {"commit": None, "dirty": True},
    }
    (data / f"run_manifest_{CONDITION}_seed_{SEED}.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    return run_dir


def refresh_inventory(run_dir: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory, errors = build_artifact_inventory(
        str(run_dir / "data"), seed=SEED, condition=CONDITION)
    manifest["artifact_inventory"] = inventory
    manifest["artifact_inventory_errors"] = errors
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def read_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def seal_matching_external_identity(manifest_path: Path) -> ExpectedRunContract:
    """Add synthetic later-slice identities solely to exercise readiness matching."""
    manifest = read_manifest(manifest_path)
    manifest.update({
        "plan_identity": "synthetic-plan-v2",
        "plan_sha256": "b" * 64,
        "environment_fingerprint": "d" * 64,
        "code": {
            "commit": "c" * 40,
            "tag": "core-v2-run-ready",
            "dirty": False,
        },
    })
    write_manifest(manifest_path, manifest)
    return ExpectedRunContract(
        seed=SEED,
        condition=CONDITION,
        requested_ticks=manifest["requested_ticks"],
        log_mode="metrics_only",
        anti_stagnation_enabled=False,
        disabled_layers=(),
        combat_enabled=True,
        raids_enabled=True,
        execution_mode="serial",
        plan_identity="synthetic-plan-v2",
        plan_sha256="b" * 64,
        code_commit="c" * 40,
        code_tag="core-v2-run-ready",
        code_dirty=False,
        environment_fingerprint="d" * 64,
        allow_zero_events=True,
        belief_snapshot_interval=BELIEF_SNAPSHOT_INTERVAL,
        belief_snapshot_cardinality=BELIEF_SNAPSHOT_CARDINALITY,
    )


def replace_contract(
    contract: ExpectedRunContract,
    **changes,
) -> ExpectedRunContract:
    values = dict(contract.__dict__)
    values.update(changes)
    return ExpectedRunContract(**values)


def snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | str]]:
    snapshot: dict[str, tuple[str, bytes | str]] = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            snapshot[relative] = ("directory", "")
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def readiness_codes(report) -> set[str]:
    return {issue.code for issue in report.readiness_issues}


def issue_for(report, code: str, artifact: str | None = None):
    return next(
        issue
        for issue in report.issues
        if issue.code == code and (artifact is None or issue.artifact == artifact)
    )


def test_strict_accepts_requested_horizon_and_zero_row_contracts(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path, event_rows=[])

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert report.valid and not report.v2_ready
    assert report.classification == "schema2_valid"
    assert {notice.code for notice in report.notices} == {
        "accepted_zero_event_stream",
        "accepted_zero_beliefs_no_required_cadence",
    }


def test_complete_external_contract_is_required_for_v2_readiness(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)

    without_contract = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")
    incomplete = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=ExpectedRunContract(seed=SEED),
    )
    matched = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert without_contract.valid and not without_contract.v2_ready
    assert "missing_expected_run_contract" in readiness_codes(without_contract)
    assert incomplete.valid and not incomplete.v2_ready
    assert "incomplete_expected_run_contract" in readiness_codes(incomplete)
    assert matched.valid and matched.v2_ready
    assert matched.classification == "v2_ready"


def test_exact_safe_social_defaults_pass_temporary_readiness_veto(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and report.v2_ready
    assert "social_controls_not_v2_ready" not in readiness_codes(report)


SOCIAL_CONFIGURATION_FIELDS = {
    "social_memory_enabled",
    "social_partner_bias_enabled",
    "maximum_social_ties",
    "relationship_decay_interval",
    "social_controls_status",
    "social_control_notices",
}


def inspect_social_configuration(
    tmp_path,
    updates,
    *,
    replace_social_fields=False,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    if replace_social_fields:
        for field in SOCIAL_CONFIGURATION_FIELDS:
            manifest["configuration"].pop(field, None)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


def assert_invalid_social_configuration(report):
    assert report.valid is False
    assert report.v2_ready is False
    assert report.classification == "invalid"
    assert "invalid_social_configuration" in issue_codes(report)


def test_partial_false_memory_true_bias_is_artifact_invalid(tmp_path):
    report = inspect_social_configuration(
        tmp_path,
        {
            "social_memory_enabled": False,
            "social_partner_bias_enabled": True,
        },
        replace_social_fields=True,
    )

    assert_invalid_social_configuration(report)


def test_complete_false_memory_true_bias_is_artifact_invalid(tmp_path):
    report = inspect_social_configuration(
        tmp_path,
        {"social_partner_bias_enabled": True},
    )

    assert_invalid_social_configuration(report)


def test_partial_disabled_defaults_without_numeric_controls_are_nonready(
    tmp_path,
):
    report = inspect_social_configuration(
        tmp_path,
        {
            "social_memory_enabled": False,
            "social_partner_bias_enabled": False,
            "social_controls_status": "disabled",
            "social_control_notices": [],
        },
        replace_social_fields=True,
    )

    assert report.valid is True
    assert report.v2_ready is False
    assert report.classification == "schema2_valid"
    assert "invalid_social_configuration" not in issue_codes(report)
    assert "social_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("social_memory_enabled", 0),
        ("social_partner_bias_enabled", 1),
    ],
)
def test_partial_malformed_social_boolean_is_artifact_invalid(
    tmp_path,
    field,
    value,
):
    report = inspect_social_configuration(
        tmp_path,
        {field: value},
        replace_social_fields=True,
    )

    assert_invalid_social_configuration(report)


@pytest.mark.parametrize(
    "controls",
    [
        {
            "social_controls_status": "disabled",
            "social_control_notices": [SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY],
        },
        {
            "social_controls_status": "normalized_uncontracted",
            "social_control_notices": [],
        },
        {
            "social_memory_enabled": True,
            "social_controls_status": "disabled",
        },
        {
            "social_memory_enabled": True,
            "social_control_notices": [SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY],
        },
        {
            "social_memory_enabled": False,
            "social_partner_bias_enabled": False,
            "maximum_social_ties": 32,
            "relationship_decay_interval": 25,
            "social_controls_status": "engineering_only_uncontracted",
        },
    ],
)
def test_determinable_partial_status_or_notice_conflict_is_invalid(
    tmp_path,
    controls,
):
    report = inspect_social_configuration(
        tmp_path,
        controls,
        replace_social_fields=True,
    )

    assert_invalid_social_configuration(report)


@pytest.mark.parametrize(
    "updates",
    [
        {
            "social_memory_enabled": True,
            "social_controls_status": "engineering_only_uncontracted",
        },
        {
            "social_memory_enabled": True,
            "social_partner_bias_enabled": True,
            "social_controls_status": "engineering_only_uncontracted",
        },
        {
            "maximum_social_ties": 16,
            "social_controls_status": "engineering_only_uncontracted",
        },
        {
            "relationship_decay_interval": 10,
            "social_controls_status": "engineering_only_uncontracted",
        },
    ],
    ids=("memory", "partner-bias", "tie-cap", "decay-interval"),
)
def test_uncontracted_enabled_or_nondefault_social_controls_block_readiness(
    tmp_path,
    updates,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "social_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    "missing",
    [
        "social_memory_enabled",
        "social_partner_bias_enabled",
        "maximum_social_ties",
        "relationship_decay_interval",
        "social_controls_status",
        "social_control_notices",
    ],
)
def test_missing_social_control_is_valid_engineering_artifact_but_not_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "social_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("social_memory_enabled", 0),
        ("social_partner_bias_enabled", 1),
        ("maximum_social_ties", True),
        ("relationship_decay_interval", 0),
        ("social_controls_status", "unknown"),
        ("social_control_notices", "normalized"),
    ],
)
def test_malformed_social_control_makes_artifact_invalid(
    tmp_path,
    field,
    value,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"][field] = value
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert not report.valid and not report.v2_ready
    assert "invalid_social_configuration" in issue_codes(report)


def test_normalized_unsupported_social_request_is_preserved_and_blocks_ready(
    tmp_path,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update({
        "social_memory_enabled": False,
        "social_partner_bias_enabled": False,
        "social_controls_status": "normalized_uncontracted",
        "social_control_notices": [SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY],
    })
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "social_controls_not_v2_ready" in readiness_codes(report)
    assert report.manifest["configuration"]["social_control_notices"] == [
        SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY
    ]


LANGUAGE_CONFIGURATION_FIELDS = {
    "language_evolution_enabled",
    "maximum_language_associations",
    "maximum_signal_length",
    "language_learning_rate",
    "language_reinforcement_rate",
    "language_forgetting_interval",
    "language_invention_enabled",
    "language_controls_status",
    "language_control_notices",
}


def inspect_language_configuration(tmp_path, updates, *, replace_fields=False):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    if replace_fields:
        for field in LANGUAGE_CONFIGURATION_FIELDS:
            manifest["configuration"].pop(field, None)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "maximum_language_associations": 16,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "maximum_signal_length": 4,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "language_learning_rate": 0.30,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "language_reinforcement_rate": 0.20,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "language_forgetting_interval": 10,
            "language_controls_status": "engineering_only_uncontracted",
        },
        {
            "language_invention_enabled": False,
            "language_controls_status": "engineering_only_uncontracted",
        },
    ],
)
def test_uncontracted_language_controls_block_v2_readiness(tmp_path, updates):
    report = inspect_language_configuration(tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert "language_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize("missing", sorted(LANGUAGE_CONFIGURATION_FIELDS))
def test_missing_language_control_is_valid_but_not_v2_ready(tmp_path, missing):
    run_dir, manifest_path = make_artifacts(tmp_path / "missing", event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict",
        expected_contract=contract)

    assert report.valid and not report.v2_ready
    assert "language_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language_evolution_enabled", 0),
        ("maximum_language_associations", 0),
        ("maximum_signal_length", 5),
        ("language_learning_rate", 0.0),
        ("language_reinforcement_rate", float("nan")),
        ("language_forgetting_interval", 0),
        ("language_invention_enabled", 1),
        ("language_controls_status", "normalized_uncontracted"),
        ("language_control_notices", ["invented_notice"]),
    ],
)
def test_malformed_language_control_invalidates_artifact(tmp_path, field, value):
    report = inspect_language_configuration(tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert "invalid_language_configuration" in issue_codes(report)


def test_inconsistent_disabled_language_status_invalidates_artifact(tmp_path):
    report = inspect_language_configuration(tmp_path, {
        "language_evolution_enabled": True,
        "language_controls_status": "disabled",
    })

    assert not report.valid
    assert "invalid_language_configuration" in issue_codes(report)


COALITION_CONFIGURATION_FIELDS = {
    "coalition_emergence_enabled",
    "coalition_minimum_size",
    "coalition_trust_threshold",
    "coalition_familiarity_threshold",
    "coalition_maximum_grievance",
    "coalition_persistence_ticks",
    "maximum_active_coalitions",
    "coalition_controls_status",
    "coalition_control_notices",
}


def inspect_coalition_configuration(
    tmp_path,
    updates,
    *,
    replace_coalition_fields=False,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    if replace_coalition_fields:
        for field in COALITION_CONFIGURATION_FIELDS:
            manifest["configuration"].pop(field, None)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "coalition_emergence_enabled": True,
            "coalition_controls_status": "engineering_only_uncontracted",
            "social_memory_enabled": True,
            "social_controls_status": "engineering_only_uncontracted",
        },
        {
            "coalition_minimum_size": 4,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
        {
            "coalition_trust_threshold": 0.30,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
        {
            "coalition_familiarity_threshold": 0.50,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
        {
            "coalition_maximum_grievance": 0.10,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
        {
            "coalition_persistence_ticks": 6,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
        {
            "maximum_active_coalitions": 16,
            "coalition_controls_status": "engineering_only_uncontracted",
        },
    ],
    ids=(
        "enabled", "minimum-size", "trust", "familiarity", "grievance",
        "persistence", "active-cap",
    ),
)
def test_uncontracted_coalition_controls_block_v2_readiness(
    tmp_path,
    updates,
):
    report = inspect_coalition_configuration(tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert "coalition_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize("missing", sorted(COALITION_CONFIGURATION_FIELDS))
def test_missing_coalition_control_is_valid_but_not_v2_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "coalition_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("coalition_emergence_enabled", 0),
        ("coalition_minimum_size", True),
        ("coalition_minimum_size", 2),
        ("coalition_trust_threshold", 0),
        ("coalition_familiarity_threshold", float("nan")),
        ("coalition_maximum_grievance", 1.1),
        ("coalition_persistence_ticks", 1),
        ("maximum_active_coalitions", 0),
        ("coalition_controls_status", "unknown"),
        ("coalition_control_notices", "normalized"),
    ],
)
def test_malformed_coalition_control_invalidates_artifact(
    tmp_path,
    field,
    value,
):
    report = inspect_coalition_configuration(tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert "invalid_coalition_configuration" in issue_codes(report)


@pytest.mark.parametrize(
    "updates",
    [
        {
            "coalition_emergence_enabled": True,
            "coalition_controls_status": "disabled",
        },
        {
            "coalition_controls_status": "normalized_uncontracted",
            "coalition_control_notices": [],
        },
        {
            "coalition_controls_status": "disabled",
            "coalition_control_notices": [
                COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY
            ],
        },
        {
            "coalition_controls_status": "engineering_only_uncontracted",
            "coalition_control_notices": [
                COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY
            ],
        },
    ],
)
def test_inconsistent_coalition_status_invalidates_artifact(tmp_path, updates):
    report = inspect_coalition_configuration(tmp_path, updates)

    assert not report.valid and not report.v2_ready
    assert "invalid_coalition_configuration" in issue_codes(report)


def test_normalized_coalition_request_is_preserved_and_blocks_ready(tmp_path):
    report = inspect_coalition_configuration(tmp_path, {
        "coalition_emergence_enabled": False,
        "coalition_controls_status": "normalized_uncontracted",
        "coalition_control_notices": [
            COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY
        ],
    })

    assert report.valid and not report.v2_ready
    assert "coalition_controls_not_v2_ready" in readiness_codes(report)
    assert report.manifest["configuration"]["coalition_control_notices"] == [
        COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY
    ]


DIALECT_CONFIGURATION_FIELDS = {
    "coalition_dialect_influence_enabled",
    "same_coalition_learning_multiplier",
    "same_coalition_reinforcement_multiplier",
    "dialect_controls_status",
    "dialect_control_notices",
}


def inspect_dialect_configuration(tmp_path, updates):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "same_coalition_learning_multiplier": 1.75,
            "dialect_controls_status": "engineering_only_uncontracted",
        },
        {
            "same_coalition_reinforcement_multiplier": 1.50,
            "dialect_controls_status": "engineering_only_uncontracted",
        },
        {
            "social_memory_enabled": True,
            "social_controls_status": "engineering_only_uncontracted",
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "coalition_emergence_enabled": True,
            "coalition_controls_status": "engineering_only_uncontracted",
            "coalition_dialect_influence_enabled": True,
            "dialect_controls_status": "engineering_only_uncontracted",
        },
    ],
)
def test_enabled_or_nondefault_dialect_controls_block_v2_ready(tmp_path, updates):
    report = inspect_dialect_configuration(tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert "dialect_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize("missing", sorted(DIALECT_CONFIGURATION_FIELDS))
def test_missing_historical_dialect_field_is_valid_but_never_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "dialect_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("coalition_dialect_influence_enabled", 1),
        ("same_coalition_learning_multiplier", 1),
        ("same_coalition_learning_multiplier", 2.1),
        ("same_coalition_reinforcement_multiplier", float("nan")),
        ("dialect_controls_status", "unknown"),
        ("dialect_control_notices", "normalized"),
        ("dialect_control_notices", ["invented_notice"]),
    ],
)
def test_malformed_dialect_field_invalidates_artifact(tmp_path, field, value):
    report = inspect_dialect_configuration(tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert "invalid_dialect_configuration" in issue_codes(report)


@pytest.mark.parametrize(
    "updates",
    [
        {
            "coalition_dialect_influence_enabled": True,
        },
        {
            "dialect_controls_status": "disabled",
            "same_coalition_learning_multiplier": 1.75,
        },
        {
            "dialect_controls_status": "normalized_uncontracted",
            "coalition_dialect_influence_enabled": False,
            "dialect_control_notices": [],
        },
        {
            "dialect_controls_status": "normalized_uncontracted",
            "coalition_dialect_influence_enabled": False,
            "dialect_control_notices": [DIALECT_NOTICE_WITHOUT_LANGUAGE],
        },
        {
            "dialect_controls_status": "engineering_only_uncontracted",
            "coalition_dialect_influence_enabled": False,
        },
        {
            "dialect_controls_status": "engineering_only_uncontracted",
            "same_coalition_learning_multiplier": 1.75,
            "dialect_control_notices": [DIALECT_NOTICE_WITHOUT_COALITIONS],
        },
    ],
)
def test_dialect_requested_effective_contradictions_invalidate_artifact(
    tmp_path,
    updates,
):
    report = inspect_dialect_configuration(tmp_path, updates)

    assert not report.valid and not report.v2_ready
    assert "invalid_dialect_configuration" in issue_codes(report)


def test_exact_normalized_dialect_notices_remain_valid_but_not_ready(tmp_path):
    report = inspect_dialect_configuration(tmp_path, {
        "coalition_dialect_influence_enabled": False,
        "dialect_controls_status": "normalized_uncontracted",
        "dialect_control_notices": sorted([
            DIALECT_NOTICE_WITHOUT_LANGUAGE,
            DIALECT_NOTICE_WITHOUT_COALITIONS,
        ]),
    })

    assert report.valid and not report.v2_ready
    assert "dialect_controls_not_v2_ready" in readiness_codes(report)


LANGUAGE_CONTACT_CONFIGURATION_FIELDS = {
    "language_contact_enabled",
    "cross_group_learning_multiplier",
    "borrowing_exposure_threshold",
    "borrowing_confidence_threshold",
    "language_contact_controls_status",
    "language_contact_control_notices",
}


def inspect_language_contact_configuration(tmp_path, updates):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "cross_group_learning_multiplier": 1.75,
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
        {
            "borrowing_exposure_threshold": 4,
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
        {
            "borrowing_confidence_threshold": 0.60,
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
        {
            "social_memory_enabled": True,
            "social_controls_status": "engineering_only_uncontracted",
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "coalition_emergence_enabled": True,
            "coalition_controls_status": "engineering_only_uncontracted",
            "language_contact_enabled": True,
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
    ],
)
def test_enabled_or_nondefault_contact_controls_block_v2_ready(
    tmp_path,
    updates,
):
    report = inspect_language_contact_configuration(tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert "language_contact_controls_not_v2_ready" in readiness_codes(report)


def test_enabled_contact_without_dialect_is_valid_but_not_ready(tmp_path):
    report = inspect_language_contact_configuration(tmp_path, {
        "social_memory_enabled": True,
        "social_controls_status": "engineering_only_uncontracted",
        "language_evolution_enabled": True,
        "language_controls_status": "engineering_only_uncontracted",
        "coalition_emergence_enabled": True,
        "coalition_controls_status": "engineering_only_uncontracted",
        "language_contact_enabled": True,
        "language_contact_controls_status": "engineering_only_uncontracted",
    })

    assert report.valid and not report.v2_ready
    assert report.manifest["configuration"][
        "coalition_dialect_influence_enabled"
    ] is False
    assert "language_contact_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    "missing",
    sorted(LANGUAGE_CONTACT_CONFIGURATION_FIELDS),
)
def test_missing_historical_contact_field_is_valid_but_never_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "language_contact_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language_contact_enabled", 1),
        ("cross_group_learning_multiplier", 1),
        ("cross_group_learning_multiplier", 2.1),
        ("borrowing_exposure_threshold", True),
        ("borrowing_exposure_threshold", 33),
        ("borrowing_confidence_threshold", 1),
        ("borrowing_confidence_threshold", float("nan")),
        ("language_contact_controls_status", "unknown"),
        ("language_contact_control_notices", "normalized"),
        ("language_contact_control_notices", ["invented_notice"]),
        (
            "language_contact_control_notices",
            [
                LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
                LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
            ],
        ),
        (
            "language_contact_control_notices",
            [
                LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
                LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
            ],
        ),
    ],
)
def test_malformed_contact_field_invalidates_artifact(tmp_path, field, value):
    report = inspect_language_contact_configuration(tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert "invalid_language_contact_configuration" in issue_codes(report)


@pytest.mark.parametrize(
    "updates",
    [
        {"language_contact_enabled": True},
        {
            "language_contact_controls_status": "disabled",
            "cross_group_learning_multiplier": 1.75,
        },
        {
            "language_contact_controls_status": "normalized_uncontracted",
            "language_contact_enabled": False,
            "language_contact_control_notices": [],
        },
        {
            "language_contact_controls_status": "normalized_uncontracted",
            "language_contact_enabled": False,
            "language_contact_control_notices": [
                LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE
            ],
        },
        {
            "language_evolution_enabled": False,
            "coalition_emergence_enabled": False,
            "language_contact_enabled": False,
            "language_contact_controls_status": "normalized_uncontracted",
            "language_contact_control_notices": [
                LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE
            ],
        },
        {
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
            "language_contact_enabled": False,
        },
        {
            "language_contact_controls_status": (
                "engineering_only_uncontracted"
            ),
            "borrowing_exposure_threshold": 4,
            "language_contact_control_notices": [
                LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS
            ],
        },
    ],
)
def test_contact_requested_effective_contradictions_invalidate_artifact(
    tmp_path,
    updates,
):
    report = inspect_language_contact_configuration(tmp_path, updates)

    assert not report.valid and not report.v2_ready
    assert "invalid_language_contact_configuration" in issue_codes(report)


def test_exact_normalized_contact_notices_are_valid_but_not_ready(tmp_path):
    report = inspect_language_contact_configuration(tmp_path, {
        "language_contact_enabled": False,
        "language_contact_controls_status": "normalized_uncontracted",
        "language_contact_control_notices": sorted([
            LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
            LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
        ]),
    })

    assert report.valid and not report.v2_ready
    assert "language_contact_controls_not_v2_ready" in readiness_codes(report)


INTERGENERATIONAL_LANGUAGE_CONFIGURATION_FIELDS = {
    "intergenerational_language_enabled",
    "maximum_parental_meanings_per_parent",
    "intergenerational_learning_strength",
    "intergenerational_language_controls_status",
    "intergenerational_language_control_notices",
}


def inspect_intergenerational_language_configuration(tmp_path, updates):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "intergenerational_language_enabled": True,
            "intergenerational_language_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
        {
            "maximum_parental_meanings_per_parent": 3,
            "intergenerational_language_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
        {
            "intergenerational_learning_strength": 0.30,
            "intergenerational_language_controls_status": (
                "engineering_only_uncontracted"
            ),
        },
    ],
)
def test_enabled_or_nondefault_intergenerational_controls_block_v2_ready(
    tmp_path,
    updates,
):
    report = inspect_intergenerational_language_configuration(
        tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert (
        "intergenerational_language_controls_not_v2_ready"
        in readiness_codes(report)
    )


@pytest.mark.parametrize(
    "missing",
    sorted(INTERGENERATIONAL_LANGUAGE_CONFIGURATION_FIELDS),
)
def test_missing_historical_intergenerational_field_is_valid_but_never_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert (
        "intergenerational_language_controls_not_v2_ready"
        in readiness_codes(report)
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("intergenerational_language_enabled", 1),
        ("maximum_parental_meanings_per_parent", True),
        ("maximum_parental_meanings_per_parent", 0),
        ("maximum_parental_meanings_per_parent", 5),
        ("intergenerational_learning_strength", 1),
        ("intergenerational_learning_strength", 0.0),
        ("intergenerational_learning_strength", float("nan")),
        ("intergenerational_language_controls_status", "unknown"),
        ("intergenerational_language_control_notices", "normalized"),
        ("intergenerational_language_control_notices", ["invented_notice"]),
        (
            "intergenerational_language_control_notices",
            [
                INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
                INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
            ],
        ),
    ],
)
def test_malformed_intergenerational_field_invalidates_artifact(
    tmp_path,
    field,
    value,
):
    report = inspect_intergenerational_language_configuration(
        tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert (
        "invalid_intergenerational_language_configuration"
        in issue_codes(report)
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"intergenerational_language_enabled": True},
        {
            "intergenerational_language_controls_status": "disabled",
            "maximum_parental_meanings_per_parent": 3,
        },
        {
            "intergenerational_language_controls_status": (
                "normalized_uncontracted"
            ),
            "intergenerational_language_enabled": False,
            "intergenerational_language_control_notices": [],
        },
        {
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "intergenerational_language_enabled": False,
            "intergenerational_language_controls_status": (
                "normalized_uncontracted"
            ),
            "intergenerational_language_control_notices": [
                INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE
            ],
        },
        {
            "intergenerational_language_controls_status": (
                "engineering_only_uncontracted"
            ),
            "intergenerational_language_control_notices": [
                INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE
            ],
        },
    ],
)
def test_intergenerational_contradictions_invalidate_artifact(
    tmp_path,
    updates,
):
    report = inspect_intergenerational_language_configuration(
        tmp_path, updates)

    assert not report.valid and not report.v2_ready
    assert (
        "invalid_intergenerational_language_configuration"
        in issue_codes(report)
    )


def test_exact_normalized_intergenerational_notice_is_valid_but_not_ready(
    tmp_path,
):
    report = inspect_intergenerational_language_configuration(tmp_path, {
        "language_evolution_enabled": False,
        "intergenerational_language_enabled": False,
        "intergenerational_language_controls_status": (
            "normalized_uncontracted"
        ),
        "intergenerational_language_control_notices": [
            INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE
        ],
    })

    assert report.valid and not report.v2_ready
    assert (
        "intergenerational_language_controls_not_v2_ready"
        in readiness_codes(report)
    )


LEXICAL_EVOLUTION_CONFIGURATION_FIELDS = {
    "lexical_evolution_enabled",
    "lexical_mutation_rate",
    "maximum_lexical_lineage_depth",
    "lexical_evolution_controls_status",
    "lexical_evolution_control_notices",
}


def inspect_lexical_evolution_configuration(tmp_path, updates):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    manifest["configuration"].update(updates)
    write_manifest(manifest_path, manifest)
    return inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "lexical_evolution_enabled": True,
            "lexical_evolution_controls_status": (
                "engineering_only_uncontracted"),
        },
        {
            "lexical_mutation_rate": 0.25,
            "lexical_evolution_controls_status": (
                "engineering_only_uncontracted"),
        },
        {
            "maximum_lexical_lineage_depth": 9,
            "lexical_evolution_controls_status": (
                "engineering_only_uncontracted"),
        },
    ],
)
def test_enabled_or_nondefault_lexical_controls_block_v2_ready(
    tmp_path,
    updates,
):
    report = inspect_lexical_evolution_configuration(tmp_path, updates)

    assert report.valid and not report.v2_ready
    assert "lexical_evolution_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    "missing",
    sorted(LEXICAL_EVOLUTION_CONFIGURATION_FIELDS),
)
def test_missing_historical_lexical_field_is_valid_but_never_ready(
    tmp_path,
    missing,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    del manifest["configuration"][missing]
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid and not report.v2_ready
    assert "lexical_evolution_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lexical_evolution_enabled", 1),
        ("lexical_mutation_rate", True),
        ("lexical_mutation_rate", 1),
        ("lexical_mutation_rate", -0.01),
        ("lexical_mutation_rate", 1.01),
        ("lexical_mutation_rate", float("nan")),
        ("maximum_lexical_lineage_depth", True),
        ("maximum_lexical_lineage_depth", 0),
        ("maximum_lexical_lineage_depth", 33),
        ("lexical_evolution_controls_status", "unknown"),
        ("lexical_evolution_control_notices", "normalized"),
        ("lexical_evolution_control_notices", ["invented_notice"]),
    ],
)
def test_malformed_lexical_field_invalidates_artifact(
    tmp_path,
    field,
    value,
):
    report = inspect_lexical_evolution_configuration(
        tmp_path, {field: value})

    assert not report.valid and not report.v2_ready
    assert "invalid_lexical_evolution_configuration" in issue_codes(report)


@pytest.mark.parametrize(
    "updates",
    [
        {"lexical_evolution_enabled": True},
        {
            "lexical_evolution_controls_status": "disabled",
            "lexical_mutation_rate": 0.25,
        },
        {
            "lexical_evolution_controls_status": "normalized_uncontracted",
            "lexical_evolution_enabled": False,
            "lexical_evolution_control_notices": [],
        },
        {
            "language_evolution_enabled": True,
            "language_controls_status": "engineering_only_uncontracted",
            "lexical_evolution_enabled": False,
            "lexical_evolution_controls_status": "normalized_uncontracted",
            "lexical_evolution_control_notices": [
                LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE],
        },
        {
            "lexical_evolution_controls_status": (
                "engineering_only_uncontracted"),
            "lexical_evolution_control_notices": [
                LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE],
        },
    ],
)
def test_lexical_contradictions_invalidate_artifact(tmp_path, updates):
    report = inspect_lexical_evolution_configuration(tmp_path, updates)

    assert not report.valid and not report.v2_ready
    assert "invalid_lexical_evolution_configuration" in issue_codes(report)


def test_exact_normalized_lexical_notice_is_valid_but_not_ready(tmp_path):
    report = inspect_lexical_evolution_configuration(tmp_path, {
        "language_evolution_enabled": False,
        "lexical_evolution_enabled": False,
        "lexical_evolution_controls_status": "normalized_uncontracted",
        "lexical_evolution_control_notices": [
            LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE],
    })

    assert report.valid and not report.v2_ready
    assert "lexical_evolution_controls_not_v2_ready" in readiness_codes(report)


@pytest.mark.parametrize(
    "changes",
    [
        {"seed": SEED + 1},
        {"condition": "other-condition"},
        {"requested_ticks": 4},
        {"log_mode": "summary"},
        {"anti_stagnation_enabled": True},
        {
            "disabled_layers": ("combat",),
            "combat_enabled": False,
        },
        {
            "disabled_layers": ("raids",),
            "raids_enabled": False,
        },
        {"execution_mode": "threaded"},
        {"plan_identity": "other-plan"},
        {"plan_sha256": "e" * 64},
        {"code_commit": "e" * 40},
        {"code_tag": "other-run-ready-tag"},
        {"environment_fingerprint": "e" * 64},
        {"allow_zero_events": False},
        {"belief_snapshot_interval": BELIEF_SNAPSHOT_INTERVAL + 1},
    ],
)
def test_external_contract_mismatches_never_become_v2_ready(tmp_path, changes):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    matching = seal_matching_external_identity(manifest_path)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=replace_contract(matching, **changes),
    )

    assert report.valid
    assert not report.v2_ready
    assert report.classification == "schema2_valid"
    assert "expected_run_contract_mismatch" in readiness_codes(report)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("seed", True),
        ("condition", 7),
        ("requested_ticks", 3.0),
        ("log_mode", 1),
        ("anti_stagnation_enabled", 0),
        ("disabled_layers", []),
        ("combat_enabled", 1),
        ("raids_enabled", 1),
        ("execution_mode", 1),
        ("plan_identity", 1),
        ("plan_sha256", 1),
        ("code_commit", 1),
        ("code_tag", 1),
        ("code_dirty", 0),
        ("environment_fingerprint", 1),
        ("allow_zero_events", 1),
        ("belief_snapshot_interval", True),
        ("belief_snapshot_cardinality", 1),
    ),
)
def test_every_expected_contract_field_requires_its_exact_runtime_type(
    tmp_path,
    field_name,
    invalid_value,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    matching = seal_matching_external_identity(manifest_path)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=replace_contract(
            matching, **{field_name: invalid_value}),
    )

    assert report.valid
    assert not report.v2_ready
    assert report.classification == "schema2_valid"
    assert "incomplete_expected_run_contract" in readiness_codes(report)


@pytest.mark.parametrize(
    ("path", "malformed_value"),
    (
        (("schema_version",), 2.0),
        (("schema_version",), True),
        (("seed",), True),
        (("requested_ticks",), True),
        (("final_tick",), 3.0),
        (("completed_ticks",), "3"),
        (("completed_normally",), 1),
        (("event_schema_version",), 1.0),
        (("artifact_schema_versions", "metrics"), 2.0),
        (("configuration", "ticks"), True),
        (("configuration", "anti_stagnation_enabled"), 0),
        (("configuration", "raids_enabled"), 1),
        (("configuration", "disabled_layers"), None),
        (("configuration", "disabled_layers"), ["combat", 7]),
        (("configuration", "disabled_layers"), ["combat", "combat"]),
        (("artifact_policy", "allow_zero_events"), 1),
        (("artifact_policy", "belief_snapshot_interval"), True),
        (("artifact_policy", "belief_snapshot_cardinality"), None),
        (("writer_health", "pending_event_rows"), False),
        (("writer_health", "finalized"), 1),
        (("artifact_inventory", "metrics", "size_bytes"), True),
        (("artifact_inventory", "events", "data_rows"), 0.0),
        (("artifact_inventory", "summary", "schema_version"), True),
    ),
)
def test_malformed_artifact_json_types_are_structured_invalid_reports(
    tmp_path,
    path,
    malformed_value,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    target = manifest
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = malformed_value
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert not report.v2_ready
    assert report.classification == "invalid"
    assert report.issues


def test_unsupported_future_manifest_schema_is_invalid_not_schema_two(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest["schema_version"] = RUN_MANIFEST_SCHEMA_VERSION + 1
    write_manifest(manifest_path, manifest)

    for mode in ("strict", "auto"):
        report = inspect_run_outputs(
            run_dir, CONDITION, SEED, expected_ticks=3, mode=mode)
        assert not report.valid
        assert not report.v2_ready
        assert report.classification == "invalid"
        assert "unsupported_manifest_schema" in issue_codes(report)


@pytest.mark.parametrize("path", [
    ("plan_identity",),
    ("plan_sha256",),
    ("code", "tag"),
])
def test_absent_provenance_is_valid_but_never_v2_ready(tmp_path, path):
    """Absent runner provenance is ordinary, not malformed.

    A run launched directly rather than by the experiment runner has no plan,
    and a development revision carries no annotated tag. Both are valid
    engineering evidence. Treating them as malformed would make every direct
    run an invalid artifact. Only V2 readiness requires the values, and the
    expected-run contract enforces that separately.

    The environment fingerprint is deliberately not in this list: it is always
    computable, so its absence really is malformed.
    """
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    target = manifest
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = None
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid is True
    assert report.v2_ready is False


@pytest.mark.parametrize(
    ("path", "malformed_value", "expected_code"),
    (
        (("plan_identity",), 7, "invalid_plan_identity"),
        (("plan_identity",), "", "invalid_plan_identity"),
        (("plan_sha256",), 7, "invalid_plan_sha256"),
        (("plan_sha256",), "A" * 64, "invalid_plan_sha256"),
        (("code",), None, "invalid_code_identity_shape"),
        (("code",), [], "invalid_code_identity_shape"),
        (("code",), "revision", "invalid_code_identity_shape"),
        (("code",), {
            "commit": "c" * 40,
            "dirty": False,
            "unexpected": "value",
        }, "invalid_code_identity_shape"),
        (("code", "commit"), 7, "invalid_code_commit"),
        (("code", "dirty"), 0, "invalid_code_dirty"),
        (("environment_fingerprint",), 7,
         "invalid_environment_fingerprint"),
        (("environment_fingerprint",), "short",
         "invalid_environment_fingerprint"),
        (("environment_fingerprint",), None,
         "invalid_environment_fingerprint"),
        (("plan",), {"identity": "duplicate"},
         "conflicting_provenance_representation"),
        (("revision",), {"commit": "d" * 40},
         "conflicting_provenance_representation"),
        (("environment",), {"fingerprint": "e" * 64},
         "conflicting_provenance_representation"),
        (("provenance_schema_version",), 999,
         "invalid_provenance_representation"),
    ),
)
def test_malformed_readiness_identity_never_becomes_v2_ready(
    tmp_path,
    path,
    malformed_value,
    expected_code,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    contract = seal_matching_external_identity(manifest_path)
    manifest = read_manifest(manifest_path)
    target = manifest
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = malformed_value
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        expected_contract=contract,
    )

    assert report.valid is False
    assert report.v2_ready is False
    assert report.classification == "invalid"
    assert expected_code in issue_codes(report)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("plan_identity", "partial-plan"),
        ("plan_sha256", "b" * 64),
        ("code", {"commit": "c" * 40, "dirty": True}),
        ("environment_fingerprint", "d" * 64),
    ),
)
def test_well_formed_incomplete_present_provenance_is_valid_nonready(
    tmp_path,
    field_name,
    value,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest[field_name] = value
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert report.valid is True
    assert report.v2_ready is False
    assert report.classification == "schema2_valid"
    assert "missing_expected_run_contract" in readiness_codes(report)


@pytest.mark.parametrize(
    ("alias", "value"),
    (
        ("plan", None),
        ("plan", []),
        ("plan", {"identity": "unsupported", "extra": True}),
        ("revision", 7),
        ("environment", "fingerprint"),
        ("code_commit", "c" * 40),
    ),
)
def test_unsupported_provenance_representations_are_validity_errors(
    tmp_path,
    alias,
    value,
):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest[alias] = value
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert report.valid is False
    assert report.v2_ready is False
    assert report.classification == "invalid"
    assert "invalid_provenance_representation" in issue_codes(report)


def test_strict_rejects_wrong_final_tick(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["final_tick"] = 2
    manifest["completed_ticks"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "wrong_final_tick" in issue_codes(report)


def test_strict_requires_termination_fields(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field_name in (
        "requested_ticks", "final_tick", "termination_reason",
        "result_status", "completed_normally",
    ):
        manifest.pop(field_name)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "missing_or_invalid_termination_field" in issue_codes(report)


def test_schema_one_is_explicit_legacy_but_never_v2_ready(tmp_path):
    run_dir = make_authentic_schema_one_artifacts(tmp_path)

    auto = inspect_run_outputs(run_dir, CONDITION, SEED, mode="auto")
    legacy = inspect_run_outputs(run_dir, CONDITION, SEED, mode="legacy")
    strict = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert auto.valid and legacy.valid
    assert auto.classification == legacy.classification == "legacy"
    assert not auto.v2_ready and not legacy.v2_ready
    assert not strict.valid and not strict.v2_ready
    assert "legacy_manifest_not_v2_ready" in issue_codes(strict)


@pytest.mark.parametrize(
    ("result_status", "completed_normally", "termination_reason"),
    [
        ("cancelled", False, "user_cancelled"),
        ("failed", False, "exception"),
        ("timed_out", False, "wall_clock_limit"),
        ("invalid", False, "invalid_output"),
    ],
)
def test_strict_rejects_noncompleted_statuses(
    tmp_path, result_status, completed_normally, termination_reason,
):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        result_status=result_status,
        completed_normally=completed_normally,
        termination_reason=termination_reason,
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "noncompleted_result_status" in issue_codes(report)


def test_registered_extinction_is_valid_natural_terminal(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=5,
        populations=[10, 2, 0],
        termination_reason="extinction",
        event_rows=[],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=5, mode="strict")

    assert report.valid
    assert report.manifest["final_tick"] == 3


def test_unregistered_early_termination_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=5,
        populations=[10, 2, 0],
        termination_reason="extinction",
    )

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=5,
        mode="strict",
        policy=ValidationPolicy(registered_natural_terminals=frozenset()),
    )

    assert not report.valid
    assert "unregistered_natural_terminal" in issue_codes(report)


def test_extinction_on_requested_final_tick_uses_requested_horizon(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=3,
        populations=[10, 2, 0],
        termination_reason="requested_ticks_reached",
        event_rows=[],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert report.valid


@pytest.mark.parametrize("artifact", ["metrics", "summary"])
def test_header_only_required_csv_is_rejected(tmp_path, artifact):
    run_dir, manifest_path = make_artifacts(tmp_path)
    path = (
        run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
        if artifact == "metrics" else run_dir / "data" / "run_summaries.csv"
    )
    header = METRICS_HEADER if artifact == "metrics" else RUN_SUMMARY_HEADER
    _write_csv(path, header, [])
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "header_only_required_artifact" in issue_codes(report)


def test_malformed_csv_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    events_path = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    events_path.write_text(
        ",".join(EVENTS_HEADER) + '\n1,11,1,"raid,A,B,unterminated\n',
        encoding="utf-8",
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "malformed_csv" in issue_codes(report)


def test_truncated_width_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    events_path = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    _write_csv(events_path, EVENTS_HEADER, [[1, SEED, 1, "raid"]])
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "invalid_csv_width" in issue_codes(report)


def test_decreasing_event_ticks_are_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        event_rows=[
            [1, SEED, 2, "raid", "A", "B", "first"],
            [1, SEED, 1, "raid", "A", "B", "second"],
        ],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "decreasing_tick" in issue_codes(report)


def test_row_beyond_final_tick_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        event_rows=[[1, SEED, 4, "raid", "A", "B", "late"]],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "row_beyond_final_tick" in issue_codes(report)


def test_missing_final_summary_row_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path, summary_rows=[])

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "header_only_required_artifact" in issue_codes(report)


def test_invalid_state_hash_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state_hash"] = "not-a-hash"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "invalid_state_hash" in issue_codes(report)


def test_inventory_checksum_mismatch_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    events_path = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write("1,11,2,raid,A,B,added later\n")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "artifact_inventory_mismatch" in issue_codes(report)


def test_unresolved_writer_failure_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["writer_health"] = _writer_health(
        pending_event_rows=1,
        unresolved_failures=["events_flush_failed"],
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unresolved_writer_failure" in issue_codes(report)


def test_recovered_flush_failure_remains_valid(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["writer_health"] = _writer_health(
        event_flush_failures=1,
        event_flush_failures_recovered=1,
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert report.valid


@pytest.mark.parametrize(
    "counter",
    [
        "metrics_write_failures",
        "metrics_flush_failures",
        "event_write_failures",
        "belief_write_failures",
        "belief_flush_failures",
        "summary_write_failures",
        "close_failures",
        "finalization_failures",
    ],
)
def test_nonrecoverable_writer_counter_cannot_be_forged_away(tmp_path, counter):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = read_manifest(manifest_path)
    manifest["writer_health"] = _writer_health(**{counter: 1})
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "nonrecoverable_writer_failure" in issue_codes(report)


@pytest.mark.parametrize(
    "health",
    [
        _writer_health(
            event_flush_failures=1,
            event_flush_failures_recovered=0,
            event_flush_failures_unrecovered=0,
        ),
        _writer_health(
            event_flush_failures=0,
            event_flush_failures_recovered=1,
            event_flush_failures_unrecovered=0,
        ),
        _writer_health(
            event_flush_failures=1,
            event_flush_failures_recovered=0,
            event_flush_failures_unrecovered=1,
        ),
        _writer_health(
            event_flush_failures=1,
            event_flush_failures_recovered=1,
            pending_event_rows=1,
        ),
        _writer_health(finalized=False),
        _writer_health(closed=False),
    ],
)
def test_inconsistent_or_unsealed_writer_health_is_rejected(tmp_path, health):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = read_manifest(manifest_path)
    manifest["writer_health"] = health
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert issue_codes(report) & {
        "inconsistent_writer_health",
        "unresolved_writer_failure",
        "pending_event_rows",
        "unsealed_writer",
    }


def test_missing_zero_event_policy_fails_closed(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest["artifact_policy"].pop("allow_zero_events")
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "missing_zero_event_policy" in issue_codes(report)


def test_caller_supplied_zero_event_policy_can_explicitly_accept(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest.pop("artifact_policy")
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        policy=ValidationPolicy(
            allow_zero_events=True,
            belief_snapshot_interval=BELIEF_SNAPSHOT_INTERVAL,
            belief_snapshot_cardinality=BELIEF_SNAPSHOT_CARDINALITY,
        ),
    )

    assert report.valid
    assert "accepted_zero_event_stream" in {
        notice.code for notice in report.notices}


def test_explicit_zero_event_rejection_is_enforced(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path, event_rows=[])
    manifest = read_manifest(manifest_path)
    manifest["artifact_policy"]["allow_zero_events"] = False
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "header_only_required_artifact" in issue_codes(report)


@pytest.mark.parametrize(
    "policy",
    (
        ValidationPolicy(
            allow_zero_events=False,
            belief_snapshot_interval=BELIEF_SNAPSHOT_INTERVAL,
            belief_snapshot_cardinality=BELIEF_SNAPSHOT_CARDINALITY,
        ),
        ValidationPolicy(
            allow_zero_events=True,
            belief_snapshot_interval=BELIEF_SNAPSHOT_INTERVAL + 1,
            belief_snapshot_cardinality=BELIEF_SNAPSHOT_CARDINALITY,
        ),
        ValidationPolicy(
            allow_zero_events=True,
            belief_snapshot_interval=BELIEF_SNAPSHOT_INTERVAL,
            belief_snapshot_cardinality="unsupported_cardinality",
        ),
    ),
)
def test_every_caller_and_sealed_artifact_policy_conflict_is_explicit(
    tmp_path,
    policy,
):
    run_dir, _manifest_path = make_artifacts(tmp_path)

    report = inspect_run_outputs(
        run_dir,
        CONDITION,
        SEED,
        expected_ticks=3,
        mode="strict",
        policy=policy,
    )

    assert not report.valid
    assert "artifact_policy_mismatch" in issue_codes(report)


def _belief_rows(tick: int, population: int) -> list[list[object]]:
    return [
        [SEED, tick, f"inhabitant-{tick}-{index}", "none", "belief"]
        for index in range(population)
    ]


def test_extinction_does_not_excuse_earlier_living_belief_cadence(tmp_path):
    populations = [2] * 199 + [0]
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=250,
        populations=populations,
        termination_reason="extinction",
        belief_rows=[],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=250, mode="strict")

    assert not report.valid
    assert "belief_snapshot_count_mismatch" in issue_codes(report)


def test_omitted_intermediate_belief_cadence_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=300,
        populations=[2] * 300,
        belief_rows=_belief_rows(100, 2) + _belief_rows(300, 2),
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=300, mode="strict")

    assert not report.valid
    assert "belief_snapshot_count_mismatch" in issue_codes(report)


def test_omitted_final_required_belief_cadence_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=200,
        populations=[2] * 200,
        belief_rows=_belief_rows(100, 2),
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=200, mode="strict")

    assert not report.valid
    assert "belief_snapshot_count_mismatch" in issue_codes(report)


def test_duplicate_belief_identity_is_rejected(tmp_path):
    duplicate_rows = [
        [SEED, 100, "same-inhabitant", "none", "belief-a"],
        [SEED, 100, "same-inhabitant", "none", "belief-b"],
    ]
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=100,
        populations=[2] * 100,
        belief_rows=duplicate_rows,
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=100, mode="strict")

    assert not report.valid
    assert "duplicate_belief_identity" in issue_codes(report)
    assert "belief_snapshot_count_mismatch" in issue_codes(report)


def test_zero_population_cadence_rejects_belief_rows(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=100,
        populations=[2] * 99 + [0],
        belief_rows=[[SEED, 100, "ghost", "none", "belief"]],
        event_rows=[],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=100, mode="strict")

    assert not report.valid
    assert "unexpected_belief_snapshot" in issue_codes(report)


def test_header_only_beliefs_are_valid_before_first_cadence(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=99,
        populations=[2] * 99,
        belief_rows=[],
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=99, mode="strict")

    assert report.valid
    assert "accepted_zero_beliefs_no_required_cadence" in {
        notice.code for notice in report.notices}


@pytest.mark.parametrize("artifact", ["metrics", "events", "beliefs", "summary"])
def test_symlinked_required_artifact_is_rejected(tmp_path, artifact):
    run_dir, manifest_path = make_artifacts(tmp_path)
    paths = {
        "metrics": run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv",
        "events": run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv",
        "beliefs": run_dir / "data" / f"beliefs_{CONDITION}_seed_{SEED}.csv",
        "summary": run_dir / "data" / "run_summaries.csv",
    }
    target = paths[artifact]
    outside = tmp_path / f"outside_{artifact}.csv"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_artifact_path" in issue_codes(report)
    assert manifest_path.exists()


def test_symlinked_manifest_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    outside = tmp_path / "outside_manifest.json"
    outside.write_bytes(manifest_path.read_bytes())
    manifest_path.unlink()
    manifest_path.symlink_to(outside)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_artifact_path" in issue_codes(report)


def test_broken_symlinked_required_artifact_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    metrics = run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
    metrics.unlink()
    metrics.symlink_to(tmp_path / "does-not-exist.csv")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_artifact_path" in issue_codes(report)


def test_symlinked_data_root_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    data = run_dir / "data"
    real_data = run_dir / "data_real"
    data.rename(real_data)
    data.symlink_to(real_data, target_is_directory=True)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_evidence_root" in issue_codes(report)


def test_nonregular_required_artifact_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    metrics = run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
    metrics.unlink()
    metrics.mkdir()

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_artifact_path" in issue_codes(report)


@pytest.mark.parametrize("unsafe_path", ["../outside.csv", "/tmp/outside.csv", "C:\\outside.csv"])
def test_inventory_traversal_or_absolute_paths_are_rejected(tmp_path, unsafe_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    manifest = read_manifest(manifest_path)
    manifest["artifact_inventory"]["metrics"]["path"] = unsafe_path
    write_manifest(manifest_path, manifest)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unsafe_inventory_path" in issue_codes(report)


def test_inventory_builder_rejects_symlinked_evidence(tmp_path):
    run_dir, _manifest_path = make_artifacts(tmp_path)
    events = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    outside = tmp_path / "outside_events.csv"
    outside.write_bytes(events.read_bytes())
    events.unlink()
    events.symlink_to(outside)

    inventory, errors = build_artifact_inventory(
        str(run_dir / "data"), seed=SEED, condition=CONDITION)

    assert "events" not in inventory
    assert errors and "EvidencePathError" in errors[0]


def _set_csv_field(path: Path, field: str, value: object, row: int = 0) -> None:
    header, rows = read_csv(path)
    rows[row][header.index(field)] = str(value)
    _write_csv(path, tuple(header), rows)


@pytest.mark.parametrize(
    ("artifact", "field", "value", "expected_code"),
    [
        ("metrics", "population", -1, "negative_metric_value"),
        ("metrics", "gini", "nan", "nonfinite_number"),
        ("metrics", "gini", "-inf", "nonfinite_number"),
        ("metrics", "gini", 1.1, "metric_out_of_domain"),
        ("metrics", "season", 2, "metric_out_of_domain"),
        ("summary", "mean_gini", "inf", "nonfinite_number"),
        ("summary", "final_population", -1, "negative_summary_value"),
    ],
)
def test_nonfinite_negative_and_domain_violations_are_rejected(
    tmp_path, artifact, field, value, expected_code,
):
    run_dir, manifest_path = make_artifacts(tmp_path)
    path = (
        run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
        if artifact == "metrics"
        else run_dir / "data" / "run_summaries.csv"
    )
    _set_csv_field(path, field, value)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert expected_code in issue_codes(report)


@pytest.mark.parametrize(
    "field",
    sorted(METRICS_NONNEGATIVE_INTEGER_FIELDS | METRICS_NONNEGATIVE_FLOAT_FIELDS),
)
def test_every_nonnegative_metric_field_rejects_negative_values(
    tmp_path,
    field,
):
    run_dir, manifest_path = make_artifacts(tmp_path)
    metrics = run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
    _set_csv_field(metrics, field, -1)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "negative_metric_value" in issue_codes(report)


@pytest.mark.parametrize(
    "field",
    sorted(SUMMARY_NONNEGATIVE_INTEGER_FIELDS | SUMMARY_NONNEGATIVE_FLOAT_FIELDS),
)
def test_every_nonnegative_summary_field_rejects_negative_values(
    tmp_path,
    field,
):
    run_dir, manifest_path = make_artifacts(tmp_path)
    summary = run_dir / "data" / "run_summaries.csv"
    _set_csv_field(summary, field, -1)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "negative_summary_value" in issue_codes(report)


@pytest.mark.parametrize("field", METRICS_CUMULATIVE_FIELDS)
def test_every_cumulative_metric_rejects_decrease(tmp_path, field):
    run_dir, manifest_path = make_artifacts(tmp_path)
    metrics = run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
    _set_csv_field(metrics, field, 2, row=0)
    _set_csv_field(metrics, field, 1, row=1)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "decreasing_cumulative_metric" in issue_codes(report)


def test_unknown_event_type_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    events = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    _set_csv_field(events, "event_type", "not_a_real_event")
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unknown_event_type" in issue_codes(report)


def test_empty_event_type_is_rejected(tmp_path):
    run_dir, manifest_path = make_artifacts(tmp_path)
    events = run_dir / "data" / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    _set_csv_field(events, "event_type", "")
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unknown_event_type" in issue_codes(report)


def test_unknown_technology_identifier_is_rejected_by_writer_and_validator(
    tmp_path,
):
    logger = MetricsLogger(SEED, CONDITION, str(tmp_path / "writer"))
    assert not logger.record_event(
        1, "tech_researched", actor="F", detail="not-in-tech-tree")
    assert logger.finalize([], [], [])
    assert logger.close()
    assert logger.writer_health()["event_write_failures"] == 1

    run_dir, manifest_path = make_artifacts(
        tmp_path / "validator",
        event_rows=[[
            EVENT_SCHEMA_VERSION,
            SEED,
            1,
            "tech_researched",
            "F",
            "",
            "not-in-tech-tree",
        ]],
    )
    refresh_inventory(run_dir, manifest_path)
    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert "unknown_technology_identifier" in issue_codes(report)
    assert "not-in-tech-tree" not in TECHNOLOGY_IDENTIFIERS


def test_empty_belief_identity_is_rejected(tmp_path):
    run_dir, _manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=100,
        populations=[2] * 100,
        belief_rows=_belief_rows(100, 2),
    )
    beliefs = run_dir / "data" / f"beliefs_{CONDITION}_seed_{SEED}.csv"
    _set_csv_field(beliefs, "inhabitant_id", "")

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=100, mode="strict")

    assert not report.valid
    assert "invalid_belief_identity" in issue_codes(report)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("final_population", 99, "summary_metrics_mismatch"),
        ("total_factions_formed", 2, "summary_events_mismatch"),
        ("total_treaties_formed", 1, "summary_events_mismatch"),
        ("mean_gini", 0.9, "summary_metrics_mismatch"),
        ("mean_tech_count_per_faction", 1.0, "summary_metrics_mismatch"),
        ("total_unique_techs", 1, "summary_events_mismatch"),
        ("mean_war_duration", 1.0, "summary_events_mismatch"),
    ],
)
def test_summary_deterministic_cross_checks_reject_mismatch(
    tmp_path, field, value, expected_code,
):
    run_dir, manifest_path = make_artifacts(tmp_path)
    summary = run_dir / "data" / "run_summaries.csv"
    _set_csv_field(summary, field, value)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")

    assert not report.valid
    assert expected_code in issue_codes(report)


def test_actual_metrics_logger_output_satisfies_strict_contract(tmp_path):
    run_dir = tmp_path / "writer_run"
    data = run_dir / "data"
    inhabitant = SimpleNamespace(
        name="A",
        inventory={"food": 3, "wood": 0, "ore": 0, "stone": 0},
        currency=0,
        trust={},
        beliefs=[],
        faction="F",
        generation=0,
    )
    faction = SimpleNamespace(name="F", members=[inhabitant], techs=set())
    logger = MetricsLogger(SEED, CONDITION, str(data))
    assert logger.record_event(1, "faction_formed", "F", detail="formed")
    assert logger.record_tick(1, [[{}]], [inhabitant], [faction], [], {}, 0)
    assert logger.finalize([[{}]], [inhabitant], [faction])
    assert logger.close()
    write_run_manifest(
        str(data),
        seed=SEED,
        condition=CONDITION,
        configuration={
            "ticks": 1,
            "condition": CONDITION,
            "log_mode": "metrics_only",
            "anti_stagnation_enabled": False,
            "disabled_layers": [],
            "raids_enabled": True,
        },
        state_hash="a" * 64,
        execution_mode="serial",
        requested_ticks=1,
        final_tick=1,
        termination_reason="requested_ticks_reached",
        result_status="completed",
        completed_normally=True,
        writer_health=logger.writer_health(),
        log_mode="metrics_only",
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=1, mode="strict")

    assert report.valid, report.errors


def test_actual_metrics_writer_extinction_uses_positive_minimum(tmp_path):
    run_dir = tmp_path / "writer_extinction"
    data = run_dir / "data"
    inhabitant = SimpleNamespace(
        name="A",
        inventory={"food": 1, "wood": 0, "ore": 0, "stone": 0},
        currency=0,
        trust={},
        beliefs=[],
        faction=None,
        generation=0,
    )
    logger = MetricsLogger(SEED, CONDITION, str(data))
    assert logger.record_tick(1, [[{}]], [inhabitant], [], [], {}, 0)
    assert logger.record_tick(2, [[{}]], [], [], [], {}, 1)
    assert logger.finalize([[{}]], [], [])
    assert logger.close()
    write_run_manifest(
        str(data),
        seed=SEED,
        condition=CONDITION,
        configuration={
            "ticks": 3,
            "condition": CONDITION,
            "log_mode": "metrics_only",
            "anti_stagnation_enabled": False,
            "disabled_layers": [],
            "raids_enabled": True,
        },
        state_hash="a" * 64,
        execution_mode="serial",
        requested_ticks=3,
        final_tick=2,
        termination_reason="extinction",
        result_status="completed",
        completed_normally=True,
        writer_health=logger.writer_health(),
        log_mode="metrics_only",
    )

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")
    _header, summary_rows = read_csv(data / "run_summaries.csv")

    assert summary_rows[0][RUN_SUMMARY_HEADER.index("min_population")] == "1"
    assert report.valid, report.errors


def _validation_peak_bytes(root: Path, rows: int) -> int:
    run_dir, manifest_path = make_artifacts(
        root,
        requested_ticks=rows,
        populations=[3] * rows,
        event_rows=[],
    )
    manifest = read_manifest(manifest_path)
    manifest["artifact_policy"]["belief_snapshot_interval"] = rows + 1
    write_manifest(manifest_path, manifest)
    gc.collect()
    tracemalloc.start()
    try:
        report = inspect_run_outputs(
            run_dir, CONDITION, SEED, expected_ticks=rows, mode="strict")
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert report.valid, report.errors
    return peak


def test_validation_memory_scales_boundedly_with_large_csv(tmp_path):
    small_peak = _validation_peak_bytes(tmp_path / "small", 512)
    large_peak = _validation_peak_bytes(tmp_path / "large", 32768)

    assert large_peak < 64 * 1024 * 1024
    assert large_peak <= small_peak * 4 + 4 * 1024 * 1024


def _make_event_heavy_artifacts(root: Path, rows: int) -> Path:
    run_dir, manifest_path = make_artifacts(root, event_rows=[])
    events_path = (
        run_dir / "data"
        / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    )
    with events_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(EVENTS_HEADER)
        for index in range(rows):
            writer.writerow([
                EVENT_SCHEMA_VERSION,
                SEED,
                1,
                "world_event",
                "",
                "",
                f"unique-world-detail-{index:08d}-" + "x" * 64,
            ])
    refresh_inventory(run_dir, manifest_path)
    return run_dir


def _event_validation_peak_bytes(run_dir: Path, rows: int) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        report = inspect_run_outputs(
            run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert report.valid, report.errors
    assert report.manifest["artifact_inventory"]["events"]["data_rows"] == rows
    return peak


def test_unique_event_details_do_not_accumulate_in_validation_memory(tmp_path):
    small_rows = 1_000
    large_rows = 65_000
    small_run = _make_event_heavy_artifacts(tmp_path / "events_small", small_rows)
    large_run = _make_event_heavy_artifacts(tmp_path / "events_large", large_rows)

    small_peak = _event_validation_peak_bytes(small_run, small_rows)
    gc.collect()
    large_peak = _event_validation_peak_bytes(large_run, large_rows)

    assert large_peak < 32 * 1024 * 1024
    assert large_peak <= small_peak * 3 + 2 * 1024 * 1024


def _make_malformed_event_heavy_artifacts(root: Path, rows: int) -> Path:
    run_dir, manifest_path = make_artifacts(root, event_rows=[])
    events_path = (
        run_dir / "data"
        / f"faction_events_{CONDITION}_seed_{SEED}.csv"
    )
    with events_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(EVENTS_HEADER)
        for index in range(rows):
            writer.writerow([
                EVENT_SCHEMA_VERSION,
                SEED,
                1,
                "tech_researched",
                "F",
                "",
                f"unknown-technology-{index:08d}-" + "x" * 256,
            ])
    refresh_inventory(run_dir, manifest_path)
    return run_dir


def _malformed_event_validation_peak_bytes(
    run_dir: Path,
    rows: int,
) -> tuple[int, object]:
    gc.collect()
    tracemalloc.start()
    try:
        report = inspect_run_outputs(
            run_dir, CONDITION, SEED, expected_ticks=3, mode="strict")
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    issue = issue_for(report, "unknown_technology_identifier", "events")
    assert report.valid is False
    assert report.manifest["artifact_inventory"]["events"]["data_rows"] == rows
    assert issue.occurrence_count == rows
    assert issue.suppressed_count == rows - 3
    assert issue.representative_rows == (2, 3, 4)
    assert len(issue.representative_messages) == 3
    assert all(len(message) <= 160 for message in issue.representative_messages)
    assert f"occurrences={rows}" in issue.render()
    assert f"suppressed={rows - 3}" in issue.render()
    assert len(report.issues) < 20
    return peak, report


def test_malformed_event_diagnostics_and_memory_are_bounded(tmp_path):
    small_rows = 1_000
    large_rows = 65_000
    small_run = _make_malformed_event_heavy_artifacts(
        tmp_path / "malformed_events_small", small_rows)
    large_run = _make_malformed_event_heavy_artifacts(
        tmp_path / "malformed_events_large", large_rows)

    small_peak, _small_report = _malformed_event_validation_peak_bytes(
        small_run, small_rows)
    gc.collect()
    large_peak, _large_report = _malformed_event_validation_peak_bytes(
        large_run, large_rows)

    print(
        "malformed event validation peaks: "
        f"{small_rows} rows={small_peak} bytes, "
        f"{large_rows} rows={large_peak} bytes"
    )
    assert large_peak < 32 * 1024 * 1024
    assert large_peak <= small_peak * 3 + 2 * 1024 * 1024


def test_metrics_row_diagnostics_use_the_shared_cap(tmp_path):
    rows = 1_000
    run_dir, manifest_path = make_artifacts(
        tmp_path,
        requested_ticks=rows,
        populations=[3] * rows,
        event_rows=[],
    )
    metrics_path = (
        run_dir / "data" / f"metrics_{CONDITION}_seed_{SEED}.csv"
    )
    header, metric_rows = read_csv(metrics_path)
    population_index = header.index("population")
    for row in metric_rows:
        row[population_index] = "-1"
    _write_csv(metrics_path, METRICS_HEADER, metric_rows)
    manifest = read_manifest(manifest_path)
    manifest["artifact_policy"]["belief_snapshot_interval"] = rows + 1
    write_manifest(manifest_path, manifest)
    refresh_inventory(run_dir, manifest_path)

    report = inspect_run_outputs(
        run_dir, CONDITION, SEED, expected_ticks=rows, mode="strict")

    issue = issue_for(report, "negative_metric_value", "metrics")
    assert report.valid is False
    assert issue.occurrence_count == rows
    assert issue.suppressed_count == rows - 3
    assert issue.representative_rows == (2, 3, 4)
    assert issue.representative_messages == ("population",) * 3


# ── Readiness veto coverage ─────────────────────────────────────────────────

def _readiness_codes_for(config_overrides):
    """Return readiness codes for one effective configuration."""
    from thalren_vale.artifact_validation import _readiness_issues
    from thalren_vale.config import SimulationConfig

    config = SimulationConfig(**config_overrides)
    config.validate()
    manifest = {
        "configuration": config.manifest_dict(),
        "language_endpoint": {
            "name": "comprehension_success_rate",
            "definition": (
                "successful_interpretation_count / "
                "communication_attempt_count"
            ),
            "communication_attempt_count": 0,
            "successful_interpretation_count": 0,
            "comprehension_success_rate": None,
            "measured_at_tick": 1,
            "analysis_contract": "unspecified",
        },
    }
    issues = _readiness_issues(manifest, None)
    return {issue.code for issue in issues} - {"missing_expected_run_contract"}


def test_pristine_defaults_trip_no_control_readiness_veto():
    assert _readiness_codes_for({}) == set()


@pytest.mark.parametrize("overrides, expected_code", [
    ({"modality_morpheme_length": 2},
     "compositional_protolanguage_controls_not_v2_ready"),
    ({"maximum_resource_morpheme_length": 3},
     "compositional_protolanguage_controls_not_v2_ready"),
    ({"order_adoption_threshold": 7},
     "grammar_evolution_controls_not_v2_ready"),
    ({"intelligibility_reward": 0.2},
     "language_coevolution_controls_not_v2_ready"),
    ({"intelligibility_penalty": 0.2},
     "language_coevolution_controls_not_v2_ready"),
])
def test_nondefault_uncontracted_controls_are_not_v2_ready(
    overrides, expected_code,
):
    """A nondefault engineering-only control must never pass the gate.

    These three families were added after the veto was written and were
    silently exempt: a run could set a nondefault morpheme length, adoption
    threshold, or feedback rate and still classify as v2_ready.
    """
    assert expected_code in _readiness_codes_for(overrides)


def test_every_control_family_is_covered_by_the_readiness_veto():
    """No control family may be exempt from the V2-readiness gate.

    Each language milestone adds a `*_controls_status` manifest key. A family
    whose key never reaches `_readiness_issues` is invisible to the gate, so
    this asserts coverage structurally rather than case by case.
    """
    import inspect

    from thalren_vale.artifact_validation import _readiness_issues
    from thalren_vale.config import SimulationConfig

    config = SimulationConfig()
    config.validate()
    source = inspect.getsource(_readiness_issues)
    uncovered = [
        key for key in config.manifest_dict()
        if key.endswith("_controls_status") and f'"{key}"' not in source
    ]
    assert not uncovered, f"control families outside the veto: {uncovered}"


# ── Contracted endpoint readiness ───────────────────────────────────────────

def _readiness_codes_with_endpoint(endpoint):
    """Return readiness codes for a pristine config plus a given endpoint."""
    from thalren_vale.artifact_validation import _readiness_issues
    from thalren_vale.config import SimulationConfig

    config = SimulationConfig()
    config.validate()
    manifest = {"configuration": config.manifest_dict()}
    if endpoint is not _ABSENT:
        manifest["language_endpoint"] = endpoint
    issues = _readiness_issues(manifest, None)
    return {issue.code for issue in issues} - {"missing_expected_run_contract"}


_ABSENT = object()

_VALID_ENDPOINT = {
    "name": "comprehension_success_rate",
    "definition": (
        "successful_interpretation_count / communication_attempt_count"),
    "communication_attempt_count": 200,
    "successful_interpretation_count": 50,
    "comprehension_success_rate": 0.25,
    "measured_at_tick": 40,
    "analysis_contract": "unspecified",
}


def test_valid_endpoint_passes_readiness():
    assert _readiness_codes_with_endpoint(_VALID_ENDPOINT) == set()


def test_absent_endpoint_is_not_v2_ready():
    """Evidence predating the contract cannot claim to satisfy it."""
    assert "missing_language_endpoint" in _readiness_codes_with_endpoint(
        _ABSENT)


@pytest.mark.parametrize("override", [
    {"name": "something_else"},
    {"communication_attempt_count": -1},
    {"successful_interpretation_count": 500},        # exceeds attempts
    {"comprehension_success_rate": 1.5},
    {"comprehension_success_rate": "0.25"},
    {"communication_attempt_count": 0,
     "successful_interpretation_count": 0,
     "comprehension_success_rate": 0.0},             # fabricated zero rate
])
def test_inconsistent_endpoint_is_not_v2_ready(override):
    endpoint = dict(_VALID_ENDPOINT)
    endpoint.update(override)
    assert "invalid_language_endpoint" in _readiness_codes_with_endpoint(
        endpoint)
