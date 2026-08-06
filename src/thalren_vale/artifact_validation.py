"""Streaming validation for simulation research artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from .artifact_contract import (
    BELIEFS_HEADER,
    BELIEFS_SCHEMA_VERSION,
    BELIEF_SNAPSHOT_CARDINALITY,
    EVENTS_HEADER,
    EvidencePathError,
    METRICS_CUMULATIVE_FIELDS,
    METRICS_EVENT_COUNT_FIELDS,
    METRICS_FLOAT_FIELDS,
    METRICS_HEADER,
    METRICS_INTEGER_FIELDS,
    METRICS_NONNEGATIVE_FLOAT_FIELDS,
    METRICS_NONNEGATIVE_INTEGER_FIELDS,
    METRICS_SCHEMA_VERSION,
    METRICS_SEASON_VALUES,
    METRICS_TIMING_CONTRACT,
    METRICS_UNIT_INTERVAL_FIELDS,
    RUN_MANIFEST_SCHEMA_VERSION,
    RUN_SUMMARY_HEADER,
    RUN_SUMMARY_SCHEMA_VERSION,
    SUMMARY_EVENT_COUNT_FIELDS,
    SUMMARY_FLOAT_FIELDS,
    SUMMARY_INTEGER_FIELDS,
    SUMMARY_NONNEGATIVE_FLOAT_FIELDS,
    SUMMARY_NONNEGATIVE_INTEGER_FIELDS,
    SUMMARY_UNIT_INTERVAL_FIELDS,
    TECHNOLOGY_IDENTIFIERS,
    lexical_absolute,
    require_contained_regular_file,
    require_real_directory,
    validate_inventory_relative_path,
)
from .config import (
    DEFAULT_COALITION_EMERGENCE_ENABLED,
    DEFAULT_COALITION_DIALECT_INFLUENCE_ENABLED,
    DEFAULT_BORROWING_CONFIDENCE_THRESHOLD,
    DEFAULT_BORROWING_EXPOSURE_THRESHOLD,
    DEFAULT_COALITION_FAMILIARITY_THRESHOLD,
    DEFAULT_COALITION_MAXIMUM_GRIEVANCE,
    DEFAULT_COALITION_MINIMUM_SIZE,
    DEFAULT_COALITION_PERSISTENCE_TICKS,
    DEFAULT_COALITION_TRUST_THRESHOLD,
    DEFAULT_INTERGENERATIONAL_LANGUAGE_ENABLED,
    DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH,
    COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    DEFAULT_COMPOSITIONAL_PROTOLANGUAGE_ENABLED,
    DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH,
    DEFAULT_MODALITY_MORPHEME_LENGTH,
    MAXIMUM_MODALITY_MORPHEME_LENGTH,
    MAXIMUM_RESOURCE_MORPHEME_LENGTH,
    VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_NOTICES,
    VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_STATUSES,
    GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION,
    GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    DEFAULT_GRAMMAR_EVOLUTION_ENABLED,
    DEFAULT_ORDER_ADOPTION_THRESHOLD,
    MAXIMUM_ORDER_ADOPTION_THRESHOLD,
    VALID_GRAMMAR_EVOLUTION_CONTROL_NOTICES,
    VALID_GRAMMAR_EVOLUTION_CONTROL_STATUSES,
    LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS,
    DEFAULT_LANGUAGE_COEVOLUTION_ENABLED,
    DEFAULT_INTELLIGIBILITY_REWARD,
    DEFAULT_INTELLIGIBILITY_PENALTY,
    MAXIMUM_INTELLIGIBILITY_RATE,
    VALID_LANGUAGE_COEVOLUTION_CONTROL_NOTICES,
    VALID_LANGUAGE_COEVOLUTION_CONTROL_STATUSES,
    COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS,
    COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COEVOLUTION,
    DEFAULT_COALITION_INTELLIGIBILITY_ENABLED,
    DEFAULT_COALITION_INTELLIGIBILITY_THRESHOLD,
    VALID_COALITION_INTELLIGIBILITY_CONTROL_NOTICES,
    VALID_COALITION_INTELLIGIBILITY_CONTROL_STATUSES,
    PRODUCTION_TRIAL_NOTICE_WITHOUT_LANGUAGE,
    DEFAULT_PRODUCTION_TRIAL_ENABLED,
    DEFAULT_PRODUCTION_TRIAL_INTERVAL,
    MAXIMUM_PRODUCTION_TRIAL_INTERVAL,
    VALID_PRODUCTION_TRIAL_CONTROL_NOTICES,
    VALID_PRODUCTION_TRIAL_CONTROL_STATUSES,
    DEFAULT_LEXICAL_EVOLUTION_ENABLED,
    DEFAULT_LEXICAL_MUTATION_RATE,
    DEFAULT_MAXIMUM_ACTIVE_COALITIONS,
    DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH,
    DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT,
    APPROVED_LANGUAGE_CONTROLS,
    DEFAULT_LANGUAGE_EVOLUTION_ENABLED,
    DEFAULT_LANGUAGE_CONTACT_ENABLED,
    DEFAULT_LANGUAGE_FORGETTING_INTERVAL,
    DEFAULT_LANGUAGE_INVENTION_ENABLED,
    DEFAULT_LANGUAGE_LEARNING_RATE,
    DEFAULT_LANGUAGE_REINFORCEMENT_RATE,
    DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS,
    DEFAULT_MAXIMUM_SIGNAL_LENGTH,
    DEFAULT_MAXIMUM_SOCIAL_TIES,
    DEFAULT_RELATIONSHIP_DECAY_INTERVAL,
    DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER,
    DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER,
    DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER,
    DIALECT_NOTICE_WITHOUT_COALITIONS,
    DIALECT_NOTICE_WITHOUT_LANGUAGE,
    INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
    MAXIMUM_INTERGENERATIONAL_MEANINGS,
    VALID_COALITION_CONTROL_NOTICES,
    VALID_COALITION_CONTROL_STATUSES,
    VALID_DISABLE_LAYERS,
    VALID_DIALECT_CONTROL_NOTICES,
    VALID_DIALECT_CONTROL_STATUSES,
    VALID_LANGUAGE_CONTROL_NOTICES,
    VALID_LANGUAGE_CONTROL_STATUSES,
    VALID_LANGUAGE_CONTACT_CONTROL_NOTICES,
    VALID_LANGUAGE_CONTACT_CONTROL_STATUSES,
    VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_NOTICES,
    VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_STATUSES,
    VALID_LEXICAL_EVOLUTION_CONTROL_NOTICES,
    VALID_LEXICAL_EVOLUTION_CONTROL_STATUSES,
    VALID_LOG_MODES,
    VALID_SOCIAL_CONTROL_NOTICES,
    VALID_SOCIAL_CONTROL_STATUSES,
)
from .events import EVENT_SCHEMA_VERSION, EVENT_TYPES_BY_SCHEMA


ValidationMode = Literal["strict", "auto", "legacy"]
ValidationClassification = Literal[
    "v2_ready", "schema2_valid", "legacy", "invalid",
]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_STRICT_ARTIFACTS = ("metrics", "events", "beliefs", "summary")
MAX_ISSUE_REPRESENTATIVES = 3
MAX_ISSUE_MESSAGE_CHARS = 160


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    artifact: str | None = None
    row: int | None = None
    occurrence_count: int = 1
    suppressed_count: int = 0
    representative_rows: tuple[int, ...] = ()
    representative_messages: tuple[str, ...] = ()

    def render(self) -> str:
        location = ""
        if self.artifact:
            location = f" [{self.artifact}"
            if self.representative_rows:
                rows = ",".join(str(row) for row in self.representative_rows)
                location += f" rows {rows}"
            elif self.row is not None:
                location += f" row {self.row}"
            location += "]"
        counts = ""
        if self.occurrence_count > 1:
            counts = (
                f" (occurrences={self.occurrence_count}, "
                f"suppressed={self.suppressed_count})"
            )
        return f"{self.code}{location}: {self.message}{counts}"


@dataclass
class _IssueBucket:
    code: str
    artifact: str | None
    occurrence_count: int = 0
    representatives: list[tuple[int | None, str]] = field(default_factory=list)


class _IssueCollector:
    """Bounded issue aggregation keyed by stable artifact and issue code."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str | None, str], _IssueBucket] = {}

    def __bool__(self) -> bool:
        return bool(self._buckets)

    def add(
        self,
        code: str,
        message: str,
        artifact: str | None,
        row: int | None,
    ) -> None:
        key = (artifact, code)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _IssueBucket(code=code, artifact=artifact)
            self._buckets[key] = bucket
        bucket.occurrence_count += 1
        if len(bucket.representatives) < MAX_ISSUE_REPRESENTATIVES:
            bounded_message = str(message)[:MAX_ISSUE_MESSAGE_CHARS]
            bucket.representatives.append((row, bounded_message))

    def materialize(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for bucket in self._buckets.values():
            rows = tuple(
                row for row, _message in bucket.representatives
                if row is not None
            )
            messages = tuple(
                message for _row, message in bucket.representatives
            )
            first_row = bucket.representatives[0][0]
            first_message = bucket.representatives[0][1]
            retained = len(bucket.representatives)
            issues.append(ValidationIssue(
                code=bucket.code,
                message=first_message,
                artifact=bucket.artifact,
                row=first_row,
                occurrence_count=bucket.occurrence_count,
                suppressed_count=max(0, bucket.occurrence_count - retained),
                representative_rows=rows,
                representative_messages=messages,
            ))
        return issues


@dataclass(frozen=True)
class ValidationNotice:
    code: str
    message: str
    artifact: str | None = None

    def render(self) -> str:
        location = f" [{self.artifact}]" if self.artifact else ""
        return f"{self.code}{location}: {self.message}"


@dataclass(frozen=True)
class ValidationPolicy:
    registered_natural_terminals: frozenset[str] = frozenset({"extinction"})
    allow_zero_events: bool | None = None
    belief_snapshot_interval: int | None = None
    belief_snapshot_cardinality: str | None = None


@dataclass(frozen=True)
class ExpectedRunContract:
    """External identity required before schema-2 evidence is V2-ready."""

    seed: int | None = None
    condition: str | None = None
    requested_ticks: int | None = None
    log_mode: str | None = None
    anti_stagnation_enabled: bool | None = None
    disabled_layers: tuple[str, ...] | None = None
    combat_enabled: bool | None = None
    raids_enabled: bool | None = None
    execution_mode: str | None = None
    plan_identity: str | None = None
    plan_sha256: str | None = None
    code_commit: str | None = None
    code_tag: str | None = None
    code_dirty: bool | None = None
    environment_fingerprint: str | None = None
    allow_zero_events: bool | None = None
    belief_snapshot_interval: int | None = None
    belief_snapshot_cardinality: str | None = None

    def completeness_errors(self) -> list[str]:
        """Return every missing, mistyped, or noncanonical contract field."""
        required = (
            "seed", "condition", "requested_ticks", "log_mode",
            "anti_stagnation_enabled", "disabled_layers", "combat_enabled",
            "raids_enabled", "execution_mode", "plan_sha256", "code_commit",
            "plan_identity", "code_tag", "code_dirty",
            "environment_fingerprint", "allow_zero_events",
            "belief_snapshot_interval", "belief_snapshot_cardinality",
        )
        errors = [name for name in required if getattr(self, name) is None]
        if self.seed is not None and type(self.seed) is not int:
            errors.append("seed_invalid")
        if self.requested_ticks is not None and (
            type(self.requested_ticks) is not int or self.requested_ticks < 1
        ):
            errors.append("requested_ticks_invalid")
        if self.condition is not None and (
            type(self.condition) is not str
            or not _SAFE_NAME.fullmatch(self.condition)
        ):
            errors.append("condition_invalid")
        if self.log_mode is not None and (
            type(self.log_mode) is not str or self.log_mode not in VALID_LOG_MODES
        ):
            errors.append("log_mode_invalid")
        if self.execution_mode is not None and (
            type(self.execution_mode) is not str
            or self.execution_mode not in {"serial", "threaded"}
        ):
            errors.append("execution_mode_invalid")
        if self.plan_identity is not None and (
            type(self.plan_identity) is not str
            or not _SAFE_NAME.fullmatch(self.plan_identity)
        ):
            errors.append("plan_identity_invalid")
        if self.plan_sha256 is not None and (
            type(self.plan_sha256) is not str
            or not _SHA256.fullmatch(self.plan_sha256)
        ):
            errors.append("plan_sha256_invalid")
        if self.environment_fingerprint is not None and (
            type(self.environment_fingerprint) is not str
            or not _SHA256.fullmatch(self.environment_fingerprint)
        ):
            errors.append("environment_fingerprint_invalid")
        if self.code_commit is not None and (
            type(self.code_commit) is not str
            or not _COMMIT.fullmatch(self.code_commit)
        ):
            errors.append("code_commit_invalid")
        if self.code_tag is not None and (
            type(self.code_tag) is not str or not self.code_tag.strip()
        ):
            errors.append("code_tag_invalid")
        if self.code_dirty is not None and (
            type(self.code_dirty) is not bool or self.code_dirty is not False
        ):
            errors.append("code_dirty_must_be_false")
        for field_name in (
            "anti_stagnation_enabled", "combat_enabled", "raids_enabled",
            "allow_zero_events",
        ):
            value = getattr(self, field_name)
            if value is not None and type(value) is not bool:
                errors.append(f"{field_name}_invalid")
        if self.belief_snapshot_interval is not None and (
            type(self.belief_snapshot_interval) is not int
            or self.belief_snapshot_interval < 1
        ):
            errors.append("belief_snapshot_interval_invalid")
        if self.belief_snapshot_cardinality is not None and (
            type(self.belief_snapshot_cardinality) is not str
            or self.belief_snapshot_cardinality != BELIEF_SNAPSHOT_CARDINALITY
        ):
            errors.append("belief_snapshot_cardinality_invalid")
        disabled = self.disabled_layers
        if disabled is not None:
            if type(disabled) is not tuple:
                errors.append("disabled_layers_type_invalid")
            elif any(type(item) is not str or not item for item in disabled):
                errors.append("disabled_layers_element_invalid")
            else:
                if len(disabled) != len(set(disabled)):
                    errors.append("disabled_layers_duplicate")
                if disabled != tuple(sorted(disabled)):
                    errors.append("disabled_layers_not_canonical")
                if set(disabled) - VALID_DISABLE_LAYERS:
                    errors.append("disabled_layers_unknown")
                if (
                    type(self.combat_enabled) is bool
                    and self.combat_enabled is not ("combat" not in disabled)
                ):
                    errors.append("combat_policy_inconsistent")
                if (
                    type(self.raids_enabled) is bool
                    and self.raids_enabled is not ("raids" not in disabled)
                ):
                    errors.append("raid_policy_inconsistent")
        return errors


@dataclass
class CsvStats:
    size_bytes: int = 0
    sha256: str = ""
    data_rows: int = 0
    last_tick: int | None = None
    last_row: dict[str, str] | None = None
    max_population: int | None = None
    min_positive_population: int | None = None
    max_factions: int | None = None
    max_gini: float | None = None
    gini_sum: float = 0.0
    belief_populations: dict[int, int] = field(default_factory=dict)
    event_counts: Counter[str] = field(default_factory=Counter)
    event_first_ticks: dict[str, int] = field(default_factory=dict)
    technology_ids: set[str] = field(default_factory=set)


@dataclass
class ValidationReport:
    valid: bool
    v2_ready: bool
    classification: ValidationClassification
    issues: list[ValidationIssue] = field(default_factory=list)
    notices: list[ValidationNotice] = field(default_factory=list)
    readiness_issues: list[ValidationIssue] = field(default_factory=list)
    manifest: dict | None = None

    @property
    def errors(self) -> list[str]:
        return [issue.render() for issue in self.issues]

    @property
    def readiness_errors(self) -> list[str]:
        return [issue.render() for issue in self.readiness_issues]


def artifact_paths(run_dir: Path, condition: str, seed: int) -> dict[str, Path]:
    if type(condition) is not str or not _SAFE_NAME.fullmatch(condition):
        raise ValueError(f"unsafe condition name: {condition!r}")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    data = lexical_absolute(run_dir) / "data"
    suffix = f"{condition}_seed_{seed}"
    return {
        "metrics": data / f"metrics_{suffix}.csv",
        "events": data / f"faction_events_{suffix}.csv",
        "beliefs": data / f"beliefs_{suffix}.csv",
        "summary": data / "run_summaries.csv",
        "manifest": data / f"run_manifest_{suffix}.json",
    }


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_bool(value: object) -> bool:
    return type(value) is bool


def _is_str(value: object) -> bool:
    return type(value) is str


def _is_dict(value: object) -> bool:
    return type(value) is dict


def _is_list(value: object) -> bool:
    return type(value) is list


def _exact_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        actual_dict = actual
        expected_dict = expected
        if set(actual_dict) != set(expected_dict):
            return False
        return all(
            _exact_equal(actual_dict[key], expected_dict[key])
            for key in expected_dict
        )
    if type(expected) in {list, tuple}:
        actual_items = actual
        expected_items = expected
        return len(actual_items) == len(expected_items) and all(
            _exact_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual_items, expected_items)
        )
    return actual == expected


def _normalize_disabled_layers(value: object) -> tuple[str, ...] | None:
    """Return canonical JSON disabled layers, or ``None`` when malformed."""
    if type(value) is not list:
        return None
    if any(type(item) is not str or not item for item in value):
        return None
    if len(value) != len(set(value)) or value != sorted(value):
        return None
    if set(value) - VALID_DISABLE_LAYERS:
        return None
    return tuple(value)


def _add(
    issues: _IssueCollector,
    code: str,
    message: str,
    artifact: str | None = None,
    row: int | None = None,
) -> None:
    issues.add(code, message, artifact, row)


def _validate_social_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate present engineering social controls without requiring them.

    Missing controls remain valid for historical schema-2 artifacts, but the
    separate readiness veto rejects their use as V2 evidence.
    """
    validators = {
        "social_memory_enabled": _is_bool,
        "social_partner_bias_enabled": _is_bool,
        "maximum_social_ties": (
            lambda value: _is_int(value) and 1 <= value <= 128
        ),
        "relationship_decay_interval": (
            lambda value: _is_int(value) and value >= 1
        ),
        "social_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_SOCIAL_CONTROL_STATUSES
        ),
        "social_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item) and item in VALID_SOCIAL_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_social_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    combination_errors: list[str] = []

    def add_combination_error(message: str) -> None:
        if message not in combination_errors:
            combination_errors.append(message)

    memory_present = "social_memory_enabled" in valid_present
    bias_present = "social_partner_bias_enabled" in valid_present
    maximum_present = "maximum_social_ties" in valid_present
    decay_present = "relationship_decay_interval" in valid_present
    status_present = "social_controls_status" in valid_present
    notices_present = "social_control_notices" in valid_present

    memory_enabled = config.get("social_memory_enabled") if memory_present else None
    bias_enabled = config.get("social_partner_bias_enabled") if bias_present else None
    status = config.get("social_controls_status") if status_present else None
    notices = config.get("social_control_notices") if notices_present else None

    if memory_present and bias_present and bias_enabled and not memory_enabled:
        add_combination_error(
            "effective partner bias cannot be enabled without social memory")

    if notices_present:
        assert type(notices) is list
        if notices:
            if (memory_present and memory_enabled) or (
                bias_present and bias_enabled
            ):
                add_combination_error(
                    "normalization notice conflicts with effective social controls")
            if status_present and status != "normalized_uncontracted":
                add_combination_error(
                    "social_controls_status conflicts with normalization notice")
        elif status_present and status == "normalized_uncontracted":
            add_combination_error(
                "normalized social_controls_status requires a normalization notice")

    if status_present:
        if status == "disabled":
            disabled_conflict = (
                (memory_present and memory_enabled)
                or (bias_present and bias_enabled)
                or (
                    maximum_present
                    and config["maximum_social_ties"]
                    != DEFAULT_MAXIMUM_SOCIAL_TIES
                )
                or (
                    decay_present
                    and config["relationship_decay_interval"]
                    != DEFAULT_RELATIONSHIP_DECAY_INTERVAL
                )
            )
            if disabled_conflict:
                add_combination_error(
                    "disabled social_controls_status conflicts with present controls")
        elif status == "normalized_uncontracted":
            if (memory_present and memory_enabled) or (
                bias_present and bias_enabled
            ):
                add_combination_error(
                    "normalized social_controls_status conflicts with present controls")
        elif status == "engineering_only_uncontracted":
            controls_complete = {
                "social_memory_enabled",
                "social_partner_bias_enabled",
                "maximum_social_ties",
                "relationship_decay_interval",
            } <= valid_present
            if controls_complete and (
                not memory_enabled
                and not bias_enabled
                and config["maximum_social_ties"]
                == DEFAULT_MAXIMUM_SOCIAL_TIES
                and config["relationship_decay_interval"]
                == DEFAULT_RELATIONSHIP_DECAY_INTERVAL
            ):
                add_combination_error(
                    "engineering social_controls_status requires a nondefault control")

    for message in combination_errors:
        _add(
            issues,
            "invalid_social_configuration",
            message,
            "manifest",
        )


def _validate_language_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate present language controls without requiring historical fields."""

    def finite_positive_unit_float(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 < value <= 1.0
        )

    validators = {
        "language_evolution_enabled": _is_bool,
        "maximum_language_associations": (
            lambda value: _is_int(value) and 1 <= value <= 40
        ),
        "maximum_signal_length": (
            lambda value: _is_int(value) and 2 <= value <= 4
        ),
        "language_learning_rate": finite_positive_unit_float,
        "language_reinforcement_rate": finite_positive_unit_float,
        "language_forgetting_interval": (
            lambda value: _is_int(value) and value >= 1
        ),
        "language_invention_enabled": _is_bool,
        "language_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_LANGUAGE_CONTROL_STATUSES
        ),
        "language_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item) and item in VALID_LANGUAGE_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_language_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    defaults = {
        "language_evolution_enabled": DEFAULT_LANGUAGE_EVOLUTION_ENABLED,
        "maximum_language_associations": (
            DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS
        ),
        "maximum_signal_length": DEFAULT_MAXIMUM_SIGNAL_LENGTH,
        "language_learning_rate": DEFAULT_LANGUAGE_LEARNING_RATE,
        "language_reinforcement_rate": DEFAULT_LANGUAGE_REINFORCEMENT_RATE,
        "language_forgetting_interval": DEFAULT_LANGUAGE_FORGETTING_INTERVAL,
        "language_invention_enabled": DEFAULT_LANGUAGE_INVENTION_ENABLED,
    }
    present_controls = set(defaults).intersection(valid_present)
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    controls_complete = set(defaults) <= valid_present
    status = (
        config.get("language_controls_status")
        if "language_controls_status" in valid_present else None
    )
    notices = (
        config.get("language_control_notices")
        if "language_control_notices" in valid_present else None
    )
    errors: list[str] = []

    if notices:
        errors.append("language v1 does not define normalization notices")
    if status == "disabled" and (any_nondefault or bool(notices)):
        errors.append("disabled language status conflicts with present controls")
    if status == "engineering_only_uncontracted":
        if controls_complete and not any_nondefault:
            errors.append("engineering language status requires a nondefault control")
        if notices:
            errors.append("engineering language status conflicts with notices")

    for message in dict.fromkeys(errors):
        _add(
            issues,
            "invalid_language_configuration",
            message,
            "manifest",
        )


def _validate_coalition_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate present uncontracted coalition controls independently."""

    def finite_unit_float(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 <= value <= 1.0
        )

    validators = {
        "coalition_emergence_enabled": _is_bool,
        "coalition_minimum_size": (
            lambda value: _is_int(value) and 3 <= value <= 1024
        ),
        "coalition_trust_threshold": finite_unit_float,
        "coalition_familiarity_threshold": finite_unit_float,
        "coalition_maximum_grievance": finite_unit_float,
        "coalition_persistence_ticks": (
            lambda value: _is_int(value) and value >= 2
        ),
        "maximum_active_coalitions": (
            lambda value: _is_int(value) and 1 <= value <= 1024
        ),
        "coalition_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_COALITION_CONTROL_STATUSES
        ),
        "coalition_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item) and item in VALID_COALITION_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_coalition_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    emergence_present = "coalition_emergence_enabled" in valid_present
    status_present = "coalition_controls_status" in valid_present
    notices_present = "coalition_control_notices" in valid_present
    social_present = "social_memory_enabled" in config and _is_bool(
        config.get("social_memory_enabled"))
    emergence_enabled = (
        config.get("coalition_emergence_enabled")
        if emergence_present else None
    )
    social_enabled = config.get("social_memory_enabled") if social_present else None
    status = config.get("coalition_controls_status") if status_present else None
    notices = config.get("coalition_control_notices") if notices_present else None

    if (
        emergence_present
        and social_present
        and emergence_enabled
        and not social_enabled
    ):
        add_error("effective coalition emergence requires social memory")

    if notices_present:
        assert type(notices) is list
        if notices:
            if emergence_present and emergence_enabled:
                add_error(
                    "coalition normalization notice conflicts with enabled emergence")
            if social_present and social_enabled:
                add_error(
                    "coalition normalization notice conflicts with social memory")
            if status_present and status != "normalized_uncontracted":
                add_error(
                    "coalition status conflicts with normalization notice")
        elif status_present and status == "normalized_uncontracted":
            add_error("normalized coalition status requires a notice")

    defaults = {
        "coalition_emergence_enabled": DEFAULT_COALITION_EMERGENCE_ENABLED,
        "coalition_minimum_size": DEFAULT_COALITION_MINIMUM_SIZE,
        "coalition_trust_threshold": DEFAULT_COALITION_TRUST_THRESHOLD,
        "coalition_familiarity_threshold": (
            DEFAULT_COALITION_FAMILIARITY_THRESHOLD
        ),
        "coalition_maximum_grievance": DEFAULT_COALITION_MAXIMUM_GRIEVANCE,
        "coalition_persistence_ticks": DEFAULT_COALITION_PERSISTENCE_TICKS,
        "maximum_active_coalitions": DEFAULT_MAXIMUM_ACTIVE_COALITIONS,
    }
    present_controls = set(defaults).intersection(valid_present)
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    controls_complete = set(defaults) <= valid_present
    if status_present:
        if status == "disabled":
            if any_nondefault or (notices_present and bool(notices)):
                add_error("disabled coalition status conflicts with controls")
        elif status == "normalized_uncontracted":
            if notices_present and not notices:
                add_error("normalized coalition status requires a notice")
        elif status == "engineering_only_uncontracted":
            if controls_complete and not any_nondefault:
                add_error(
                    "engineering coalition status requires a nondefault control")
            if notices_present and notices:
                add_error(
                    "engineering coalition status conflicts with normalization notice")

    for message in errors:
        _add(
            issues,
            "invalid_coalition_configuration",
            message,
            "manifest",
        )


def _validate_dialect_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate present requested/effective coalition-dialect provenance."""

    def finite_multiplier(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 1.0 <= value <= 2.0
        )

    validators = {
        "coalition_dialect_influence_enabled": _is_bool,
        "same_coalition_learning_multiplier": finite_multiplier,
        "same_coalition_reinforcement_multiplier": finite_multiplier,
        "dialect_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_DIALECT_CONTROL_STATUSES
        ),
        "dialect_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item) and item in VALID_DIALECT_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_dialect_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    influence_present = (
        "coalition_dialect_influence_enabled" in valid_present
    )
    learning_present = "same_coalition_learning_multiplier" in valid_present
    reinforcement_present = (
        "same_coalition_reinforcement_multiplier" in valid_present
    )
    status_present = "dialect_controls_status" in valid_present
    notices_present = "dialect_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    coalitions_present = (
        "coalition_emergence_enabled" in config
        and _is_bool(config.get("coalition_emergence_enabled"))
    )

    influence = (
        config["coalition_dialect_influence_enabled"]
        if influence_present else None
    )
    status = config["dialect_controls_status"] if status_present else None
    notices = config["dialect_control_notices"] if notices_present else None
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if influence is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error("enabled dialect influence requires language evolution")
        if coalitions_present and not config["coalition_emergence_enabled"]:
            add_error("enabled dialect influence requires coalition emergence")
        if notices_present and notices:
            add_error("enabled dialect influence conflicts with normalization notices")

    if notices_present:
        assert type(notices) is list
        language_notice = DIALECT_NOTICE_WITHOUT_LANGUAGE in notices
        coalition_notice = DIALECT_NOTICE_WITHOUT_COALITIONS in notices
        if influence is True and notices:
            add_error("normalization notices require disabled dialect influence")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error("language dependency notice conflicts with effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error("normalized dialect state lacks the language dependency notice")
        if coalitions_present:
            if config["coalition_emergence_enabled"] and coalition_notice:
                add_error("coalition dependency notice conflicts with effective coalitions")
            if (
                notices
                and not config["coalition_emergence_enabled"]
                and not coalition_notice
            ):
                add_error("normalized dialect state lacks the coalition dependency notice")

    controls_complete = (
        influence_present and learning_present and reinforcement_present
    )
    any_nondefault = (
        (influence is True)
        or (
            learning_present
            and not _exact_equal(
                config["same_coalition_learning_multiplier"],
                DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER,
            )
        )
        or (
            reinforcement_present
            and not _exact_equal(
                config["same_coalition_reinforcement_multiplier"],
                DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER,
            )
        )
    )
    if status == "disabled":
        if influence is True or any_nondefault:
            add_error("disabled dialect status conflicts with present controls")
        if notices_present and notices:
            add_error("disabled dialect status requires exact empty notices")
    elif status == "normalized_uncontracted":
        if influence is True:
            add_error("normalized dialect status requires disabled influence")
        if not notices_present or not notices:
            add_error("normalized dialect status requires a dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error("engineering dialect status conflicts with normalization notices")
        if controls_complete and not any_nondefault:
            add_error("engineering dialect status requires a nondefault control")

    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error("dialect status conflicts with normalization notices")

    for message in errors:
        _add(
            issues,
            "invalid_dialect_configuration",
            message,
            "manifest",
        )


def _validate_language_contact_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate present language-contact controls and dependency provenance."""

    def finite_multiplier(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 1.0 <= value <= 2.0
        )

    def finite_confidence(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.10 <= value <= 1.0
        )

    validators = {
        "language_contact_enabled": _is_bool,
        "cross_group_learning_multiplier": finite_multiplier,
        "borrowing_exposure_threshold": (
            lambda value: _is_int(value) and 2 <= value <= 32
        ),
        "borrowing_confidence_threshold": finite_confidence,
        "language_contact_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_LANGUAGE_CONTACT_CONTROL_STATUSES
        ),
        "language_contact_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_LANGUAGE_CONTACT_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_language_contact_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    contact_present = "language_contact_enabled" in valid_present
    status_present = "language_contact_controls_status" in valid_present
    notices_present = "language_contact_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    coalitions_present = (
        "coalition_emergence_enabled" in config
        and _is_bool(config.get("coalition_emergence_enabled"))
    )
    contact_enabled = (
        config["language_contact_enabled"] if contact_present else None
    )
    status = (
        config["language_contact_controls_status"]
        if status_present else None
    )
    notices = (
        config["language_contact_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if contact_enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error("enabled language contact requires language evolution")
        if coalitions_present and not config["coalition_emergence_enabled"]:
            add_error("enabled language contact requires coalition emergence")
        if notices_present and notices:
            add_error("enabled language contact conflicts with normalization notices")

    if notices_present:
        assert type(notices) is list
        language_notice = LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE in notices
        coalition_notice = LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS in notices
        if contact_enabled is True and notices:
            add_error("normalization notices require disabled language contact")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "language contact dependency notice conflicts with effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized language contact lacks the language dependency notice")
        if coalitions_present:
            if config["coalition_emergence_enabled"] and coalition_notice:
                add_error(
                    "language contact dependency notice conflicts with effective coalitions")
            if (
                notices
                and not config["coalition_emergence_enabled"]
                and not coalition_notice
            ):
                add_error(
                    "normalized language contact lacks the coalition dependency notice")

    defaults = {
        "language_contact_enabled": DEFAULT_LANGUAGE_CONTACT_ENABLED,
        "cross_group_learning_multiplier": (
            DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER
        ),
        "borrowing_exposure_threshold": DEFAULT_BORROWING_EXPOSURE_THRESHOLD,
        "borrowing_confidence_threshold": (
            DEFAULT_BORROWING_CONFIDENCE_THRESHOLD
        ),
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )

    if status == "disabled":
        if any_nondefault:
            add_error("disabled language contact status conflicts with present controls")
        if notices_present and notices:
            add_error("disabled language contact status requires exact empty notices")
    elif status == "normalized_uncontracted":
        if contact_enabled is True:
            add_error("normalized language contact status requires disabled contact")
        if not notices_present or not notices:
            add_error("normalized language contact status requires a dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering language contact status conflicts with normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering language contact status requires a nondefault control")

    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error("language contact status conflicts with normalization notices")

    for message in errors:
        _add(
            issues,
            "invalid_language_contact_configuration",
            message,
            "manifest",
        )


def _validate_intergenerational_language_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present transmission control and dependency fact."""

    def finite_strength(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 < value <= 1.0
        )

    validators = {
        "intergenerational_language_enabled": _is_bool,
        "maximum_parental_meanings_per_parent": (
            lambda value: _is_int(value)
            and 1 <= value <= MAXIMUM_INTERGENERATIONAL_MEANINGS
        ),
        "intergenerational_learning_strength": finite_strength,
        "intergenerational_language_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_STATUSES
        ),
        "intergenerational_language_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_intergenerational_language_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "intergenerational_language_enabled" in valid_present
    status_present = (
        "intergenerational_language_controls_status" in valid_present)
    notices_present = (
        "intergenerational_language_control_notices" in valid_present)
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    enabled = (
        config["intergenerational_language_enabled"]
        if enabled_present else None
    )
    status = (
        config["intergenerational_language_controls_status"]
        if status_present else None
    )
    notices = (
        config["intergenerational_language_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error(
                "enabled intergenerational language requires language evolution")
        if notices_present and notices:
            add_error(
                "enabled intergenerational language conflicts with "
                "normalization notices")

    if notices_present:
        assert type(notices) is list
        language_notice = (
            INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE in notices)
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled intergenerational "
                "language")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "intergenerational language dependency notice conflicts "
                    "with effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized intergenerational language lacks the language "
                    "dependency notice")

    defaults = {
        "intergenerational_language_enabled": (
            DEFAULT_INTERGENERATIONAL_LANGUAGE_ENABLED),
        "maximum_parental_meanings_per_parent": (
            DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT),
        "intergenerational_learning_strength": (
            DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH),
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )

    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled intergenerational language status conflicts with "
                "present controls")
        if notices_present and notices:
            add_error(
                "disabled intergenerational language status requires exact "
                "empty notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized intergenerational language status requires "
                "disabled transmission")
        if not notices_present or not notices:
            add_error(
                "normalized intergenerational language status requires a "
                "dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering intergenerational language status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering intergenerational language status requires a "
                "nondefault control")

    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "intergenerational language status conflicts with normalization "
            "notices")

    for message in errors:
        _add(
            issues,
            "invalid_intergenerational_language_configuration",
            message,
            "manifest",
        )


def _validate_compositional_protolanguage_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present composition control and dependency fact."""
    validators = {
        "compositional_protolanguage_enabled": _is_bool,
        "maximum_resource_morpheme_length": (
            lambda value: _is_int(value)
            and 1 <= value <= MAXIMUM_RESOURCE_MORPHEME_LENGTH
        ),
        "modality_morpheme_length": (
            lambda value: _is_int(value)
            and 1 <= value <= MAXIMUM_MODALITY_MORPHEME_LENGTH
        ),
        "compositional_protolanguage_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_STATUSES
        ),
        "compositional_protolanguage_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item
                in VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_compositional_protolanguage_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = (
        "compositional_protolanguage_enabled" in valid_present)
    status_present = (
        "compositional_protolanguage_controls_status" in valid_present)
    notices_present = (
        "compositional_protolanguage_control_notices" in valid_present)
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    enabled = (
        config["compositional_protolanguage_enabled"]
        if enabled_present else None
    )
    status = (
        config["compositional_protolanguage_controls_status"]
        if status_present else None
    )
    notices = (
        config["compositional_protolanguage_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error(
                "enabled compositional protolanguage requires language "
                "evolution")
        if notices_present and notices:
            add_error(
                "enabled compositional protolanguage conflicts with "
                "normalization notices")
        # Composed signals must fit the effective signal-length ceiling.
        if {
            "maximum_resource_morpheme_length",
            "modality_morpheme_length",
        } <= valid_present and _is_int(
            config.get("maximum_signal_length")
        ):
            if (
                config["maximum_resource_morpheme_length"]
                + config["modality_morpheme_length"]
                > config["maximum_signal_length"]
            ):
                add_error(
                    "composed morpheme lengths exceed the effective maximum "
                    "signal length")

    if notices_present:
        assert type(notices) is list
        language_notice = (
            COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE in notices)
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled compositional "
                "protolanguage")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "compositional protolanguage dependency notice conflicts "
                    "with effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized compositional protolanguage lacks the "
                    "language dependency notice")

    defaults = {
        "compositional_protolanguage_enabled": (
            DEFAULT_COMPOSITIONAL_PROTOLANGUAGE_ENABLED),
        "maximum_resource_morpheme_length": (
            DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH),
        "modality_morpheme_length": DEFAULT_MODALITY_MORPHEME_LENGTH,
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled compositional protolanguage status conflicts with "
                "present controls")
        if notices_present and notices:
            add_error(
                "disabled compositional protolanguage status requires exact "
                "empty notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized compositional protolanguage status requires "
                "disabled composition")
        if not notices_present or not notices:
            add_error(
                "normalized compositional protolanguage status requires a "
                "dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering compositional protolanguage status conflicts "
                "with normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering compositional protolanguage status requires a "
                "nondefault control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "compositional protolanguage status conflicts with normalization "
            "notices")
    for message in errors:
        _add(
            issues,
            "invalid_compositional_protolanguage_configuration",
            message,
            "manifest",
        )


def _validate_grammar_evolution_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present order control and both dependency facts.

    Grammar depends on language *and* composition, so each dependency carries
    its own notice and each is checked independently. A manifest that names
    only one of two missing dependencies is itself invalid.
    """
    validators = {
        "grammar_evolution_enabled": _is_bool,
        "order_adoption_threshold": (
            lambda value: _is_int(value)
            and 1 <= value <= MAXIMUM_ORDER_ADOPTION_THRESHOLD
        ),
        "grammar_evolution_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_GRAMMAR_EVOLUTION_CONTROL_STATUSES
        ),
        "grammar_evolution_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_GRAMMAR_EVOLUTION_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_grammar_evolution_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "grammar_evolution_enabled" in valid_present
    status_present = "grammar_evolution_controls_status" in valid_present
    notices_present = "grammar_evolution_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    composition_present = (
        "compositional_protolanguage_enabled" in config
        and _is_bool(config.get("compositional_protolanguage_enabled"))
    )
    enabled = (
        config["grammar_evolution_enabled"] if enabled_present else None
    )
    status = (
        config["grammar_evolution_controls_status"]
        if status_present else None
    )
    notices = (
        config["grammar_evolution_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error("enabled grammar evolution requires language evolution")
        if composition_present and not config[
            "compositional_protolanguage_enabled"
        ]:
            add_error(
                "enabled grammar evolution requires compositional "
                "protolanguage")
        if notices_present and notices:
            add_error(
                "enabled grammar evolution conflicts with normalization "
                "notices")

    if notices_present:
        assert type(notices) is list
        language_notice = GRAMMAR_EVOLUTION_NOTICE_WITHOUT_LANGUAGE in notices
        composition_notice = (
            GRAMMAR_EVOLUTION_NOTICE_WITHOUT_COMPOSITION in notices)
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled grammar evolution")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "grammar evolution language notice conflicts with "
                    "effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized grammar evolution lacks the language "
                    "dependency notice")
        if composition_present:
            if (
                config["compositional_protolanguage_enabled"]
                and composition_notice
            ):
                add_error(
                    "grammar evolution composition notice conflicts with "
                    "effective composition")
            if (
                notices
                and not config["compositional_protolanguage_enabled"]
                and not composition_notice
            ):
                add_error(
                    "normalized grammar evolution lacks the composition "
                    "dependency notice")

    defaults = {
        "grammar_evolution_enabled": DEFAULT_GRAMMAR_EVOLUTION_ENABLED,
        "order_adoption_threshold": DEFAULT_ORDER_ADOPTION_THRESHOLD,
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled grammar evolution status conflicts with present "
                "controls")
        if notices_present and notices:
            add_error(
                "disabled grammar evolution status requires exact empty "
                "notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized grammar evolution status requires disabled "
                "grammar")
        if not notices_present or not notices:
            add_error(
                "normalized grammar evolution status requires a dependency "
                "notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering grammar evolution status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering grammar evolution status requires a nondefault "
                "control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "grammar evolution status conflicts with normalization notices")
    for message in errors:
        _add(
            issues,
            "invalid_grammar_evolution_configuration",
            message,
            "manifest",
        )


def _validate_production_trial_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present runner-up trial control and its dependency."""
    validators = {
        "production_trial_enabled": _is_bool,
        "production_trial_interval": (
            lambda value: _is_int(value)
            and 2 <= value <= MAXIMUM_PRODUCTION_TRIAL_INTERVAL
        ),
        "production_trial_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_PRODUCTION_TRIAL_CONTROL_STATUSES
        ),
        "production_trial_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_PRODUCTION_TRIAL_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_production_trial_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "production_trial_enabled" in valid_present
    status_present = "production_trial_controls_status" in valid_present
    notices_present = "production_trial_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    enabled = config["production_trial_enabled"] if enabled_present else None
    status = (
        config["production_trial_controls_status"] if status_present else None)
    notices = (
        config["production_trial_control_notices"] if notices_present else None)
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error("enabled production trial requires language evolution")
        if notices_present and notices:
            add_error(
                "enabled production trial conflicts with normalization "
                "notices")

    if notices_present:
        assert type(notices) is list
        language_notice = PRODUCTION_TRIAL_NOTICE_WITHOUT_LANGUAGE in notices
        if enabled is True and notices:
            add_error("normalization notices require disabled trials")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "production trial language notice conflicts with "
                    "effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized production trial lacks the language "
                    "dependency notice")

    defaults = {
        "production_trial_enabled": DEFAULT_PRODUCTION_TRIAL_ENABLED,
        "production_trial_interval": DEFAULT_PRODUCTION_TRIAL_INTERVAL,
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled production trial status conflicts with present "
                "controls")
        if notices_present and notices:
            add_error(
                "disabled production trial status requires exact empty "
                "notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized production trial status requires disabled trials")
        if not notices_present or not notices:
            add_error(
                "normalized production trial status requires a dependency "
                "notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering production trial status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering production trial status requires a nondefault "
                "control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "production trial status conflicts with normalization notices")
    for message in errors:
        _add(
            issues,
            "invalid_production_trial_configuration",
            message,
            "manifest",
        )


def _validate_coalition_intelligibility_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate gating controls and both dependency facts.

    Gating reads the intelligibility that coevolution writes and acts on the
    coalition graph, so it depends on both and each is reported separately.
    """

    def threshold(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 < value <= 1.0
        )

    validators = {
        "coalition_intelligibility_enabled": _is_bool,
        "coalition_intelligibility_threshold": threshold,
        "coalition_intelligibility_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_COALITION_INTELLIGIBILITY_CONTROL_STATUSES
        ),
        "coalition_intelligibility_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_COALITION_INTELLIGIBILITY_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_coalition_intelligibility_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "coalition_intelligibility_enabled" in valid_present
    status_present = (
        "coalition_intelligibility_controls_status" in valid_present)
    notices_present = (
        "coalition_intelligibility_control_notices" in valid_present)
    coalitions_present = (
        "coalition_emergence_enabled" in config
        and _is_bool(config.get("coalition_emergence_enabled"))
    )
    coevolution_present = (
        "language_coevolution_enabled" in config
        and _is_bool(config.get("language_coevolution_enabled"))
    )
    enabled = (
        config["coalition_intelligibility_enabled"]
        if enabled_present else None
    )
    status = (
        config["coalition_intelligibility_controls_status"]
        if status_present else None
    )
    notices = (
        config["coalition_intelligibility_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if coalitions_present and not config["coalition_emergence_enabled"]:
            add_error(
                "enabled coalition intelligibility requires coalition "
                "emergence")
        if coevolution_present and not config["language_coevolution_enabled"]:
            add_error(
                "enabled coalition intelligibility requires language "
                "coevolution")
        if notices_present and notices:
            add_error(
                "enabled coalition intelligibility conflicts with "
                "normalization notices")

    if notices_present:
        assert type(notices) is list
        coalitions_notice = (
            COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COALITIONS in notices)
        coevolution_notice = (
            COALITION_INTELLIGIBILITY_NOTICE_WITHOUT_COEVOLUTION in notices)
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled coalition "
                "intelligibility")
        if coalitions_present:
            if config["coalition_emergence_enabled"] and coalitions_notice:
                add_error(
                    "coalition dependency notice conflicts with effective "
                    "coalition emergence")
            if (
                notices
                and not config["coalition_emergence_enabled"]
                and not coalitions_notice
            ):
                add_error(
                    "normalized coalition intelligibility lacks the "
                    "coalition dependency notice")
        if coevolution_present:
            if config["language_coevolution_enabled"] and coevolution_notice:
                add_error(
                    "coevolution dependency notice conflicts with effective "
                    "coevolution")
            if (
                notices
                and not config["language_coevolution_enabled"]
                and not coevolution_notice
            ):
                add_error(
                    "normalized coalition intelligibility lacks the "
                    "coevolution dependency notice")

    defaults = {
        "coalition_intelligibility_enabled": (
            DEFAULT_COALITION_INTELLIGIBILITY_ENABLED),
        "coalition_intelligibility_threshold": (
            DEFAULT_COALITION_INTELLIGIBILITY_THRESHOLD),
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled coalition intelligibility status conflicts with "
                "present controls")
        if notices_present and notices:
            add_error(
                "disabled coalition intelligibility status requires exact "
                "empty notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized coalition intelligibility status requires "
                "disabled gating")
        if not notices_present or not notices:
            add_error(
                "normalized coalition intelligibility status requires a "
                "dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering coalition intelligibility status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering coalition intelligibility status requires a "
                "nondefault control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "coalition intelligibility status conflicts with normalization "
            "notices")
    for message in errors:
        _add(
            issues,
            "invalid_coalition_intelligibility_configuration",
            message,
            "manifest",
        )


def _validate_language_coevolution_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present feedback control and both dependency facts.

    Coevolution depends on language evolution *and* social partner bias:
    without effective partner bias the intelligibility term never reaches a
    partner decision, so there is no loop and each dependency is checked and
    reported independently.
    """

    def finite_rate(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 < value <= MAXIMUM_INTELLIGIBILITY_RATE
        )

    validators = {
        "language_coevolution_enabled": _is_bool,
        "intelligibility_reward": finite_rate,
        "intelligibility_penalty": finite_rate,
        "language_coevolution_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_LANGUAGE_COEVOLUTION_CONTROL_STATUSES
        ),
        "language_coevolution_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_LANGUAGE_COEVOLUTION_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_language_coevolution_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "language_coevolution_enabled" in valid_present
    status_present = "language_coevolution_controls_status" in valid_present
    notices_present = "language_coevolution_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    bias_present = (
        "social_partner_bias_enabled" in config
        and _is_bool(config.get("social_partner_bias_enabled"))
    )
    enabled = (
        config["language_coevolution_enabled"] if enabled_present else None
    )
    status = (
        config["language_coevolution_controls_status"]
        if status_present else None
    )
    notices = (
        config["language_coevolution_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error(
                "enabled language coevolution requires language evolution")
        if bias_present and not config["social_partner_bias_enabled"]:
            add_error(
                "enabled language coevolution requires social partner bias")
        if notices_present and notices:
            add_error(
                "enabled language coevolution conflicts with normalization "
                "notices")

    if notices_present:
        assert type(notices) is list
        language_notice = (
            LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_LANGUAGE in notices)
        bias_notice = (
            LANGUAGE_COEVOLUTION_NOTICE_WITHOUT_PARTNER_BIAS in notices)
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled language coevolution")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "language coevolution language notice conflicts with "
                    "effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized language coevolution lacks the language "
                    "dependency notice")
        if bias_present:
            if config["social_partner_bias_enabled"] and bias_notice:
                add_error(
                    "language coevolution partner-bias notice conflicts with "
                    "effective partner bias")
            if (
                notices
                and not config["social_partner_bias_enabled"]
                and not bias_notice
            ):
                add_error(
                    "normalized language coevolution lacks the partner-bias "
                    "dependency notice")

    defaults = {
        "language_coevolution_enabled": DEFAULT_LANGUAGE_COEVOLUTION_ENABLED,
        "intelligibility_reward": DEFAULT_INTELLIGIBILITY_REWARD,
        "intelligibility_penalty": DEFAULT_INTELLIGIBILITY_PENALTY,
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled language coevolution status conflicts with present "
                "controls")
        if notices_present and notices:
            add_error(
                "disabled language coevolution status requires exact empty "
                "notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized language coevolution status requires disabled "
                "coevolution")
        if not notices_present or not notices:
            add_error(
                "normalized language coevolution status requires a "
                "dependency notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering language coevolution status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering language coevolution status requires a "
                "nondefault control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "language coevolution status conflicts with normalization notices")
    for message in errors:
        _add(
            issues,
            "invalid_language_coevolution_configuration",
            message,
            "manifest",
        )


def _validate_lexical_evolution_configuration(
    config: dict,
    issues: _IssueCollector,
) -> None:
    """Validate every present lexical control and dependency fact."""

    def finite_rate(value: object) -> bool:
        return (
            type(value) is float
            and math.isfinite(value)
            and 0.0 <= value <= 1.0
        )

    validators = {
        "lexical_evolution_enabled": _is_bool,
        "lexical_mutation_rate": finite_rate,
        "maximum_lexical_lineage_depth": (
            lambda value: _is_int(value) and 1 <= value <= 32
        ),
        "lexical_evolution_controls_status": (
            lambda value: _is_str(value)
            and value in VALID_LEXICAL_EVOLUTION_CONTROL_STATUSES
        ),
        "lexical_evolution_control_notices": (
            lambda value: _is_list(value)
            and all(
                _is_str(item)
                and item in VALID_LEXICAL_EVOLUTION_CONTROL_NOTICES
                for item in value
            )
            and len(value) == len(set(value))
            and value == sorted(value)
        ),
    }
    valid_present: set[str] = set()
    for name, validator in validators.items():
        if name not in config:
            continue
        if not validator(config[name]):
            _add(
                issues,
                "invalid_lexical_evolution_configuration",
                f"{name} is malformed",
                "manifest",
            )
        else:
            valid_present.add(name)

    enabled_present = "lexical_evolution_enabled" in valid_present
    status_present = "lexical_evolution_controls_status" in valid_present
    notices_present = "lexical_evolution_control_notices" in valid_present
    language_present = (
        "language_evolution_enabled" in config
        and _is_bool(config.get("language_evolution_enabled"))
    )
    enabled = config["lexical_evolution_enabled"] if enabled_present else None
    status = (
        config["lexical_evolution_controls_status"]
        if status_present else None
    )
    notices = (
        config["lexical_evolution_control_notices"]
        if notices_present else None
    )
    errors: list[str] = []

    def add_error(message: str) -> None:
        if message not in errors:
            errors.append(message)

    if enabled is True:
        if language_present and not config["language_evolution_enabled"]:
            add_error("enabled lexical evolution requires language evolution")
        if notices_present and notices:
            add_error(
                "enabled lexical evolution conflicts with normalization notices")

    if notices_present:
        assert type(notices) is list
        language_notice = LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE in notices
        if enabled is True and notices:
            add_error(
                "normalization notices require disabled lexical evolution")
        if language_present:
            if config["language_evolution_enabled"] and language_notice:
                add_error(
                    "lexical evolution dependency notice conflicts with "
                    "effective language")
            if (
                notices
                and not config["language_evolution_enabled"]
                and not language_notice
            ):
                add_error(
                    "normalized lexical evolution lacks the language "
                    "dependency notice")

    defaults = {
        "lexical_evolution_enabled": DEFAULT_LEXICAL_EVOLUTION_ENABLED,
        "lexical_mutation_rate": DEFAULT_LEXICAL_MUTATION_RATE,
        "maximum_lexical_lineage_depth": (
            DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH),
    }
    present_controls = set(defaults).intersection(valid_present)
    controls_complete = set(defaults) <= valid_present
    any_nondefault = any(
        not _exact_equal(config[name], defaults[name])
        for name in present_controls
    )
    if status == "disabled":
        if any_nondefault:
            add_error(
                "disabled lexical evolution status conflicts with present "
                "controls")
        if notices_present and notices:
            add_error(
                "disabled lexical evolution status requires exact empty notices")
    elif status == "normalized_uncontracted":
        if enabled is True:
            add_error(
                "normalized lexical evolution status requires disabled mutation")
        if not notices_present or not notices:
            add_error(
                "normalized lexical evolution status requires a dependency "
                "notice")
    elif status == "engineering_only_uncontracted":
        if notices_present and notices:
            add_error(
                "engineering lexical evolution status conflicts with "
                "normalization notices")
        if controls_complete and not any_nondefault:
            add_error(
                "engineering lexical evolution status requires a nondefault "
                "control")
    if notices_present and notices and status_present and (
        status != "normalized_uncontracted"
    ):
        add_error(
            "lexical evolution status conflicts with normalization notices")
    for message in errors:
        _add(
            issues,
            "invalid_lexical_evolution_configuration",
            message,
            "manifest",
        )


def _parse_int(
    value: str,
    *,
    field_name: str,
    artifact: str,
    row: int,
    issues: _IssueCollector,
) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        _add(issues, "invalid_integer", f"{field_name} is not an integer", artifact, row)
        return None


def _parse_float(
    value: str,
    *,
    field_name: str,
    artifact: str,
    row: int,
    issues: _IssueCollector,
) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        _add(issues, "invalid_number", f"{field_name} is not numeric", artifact, row)
        return None
    if not math.isfinite(result):
        _add(issues, "nonfinite_number", f"{field_name} must be finite", artifact, row)
        return None
    return result


def _text_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _text_float(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_layout(
    run_dir: Path,
    condition: str,
    seed: int,
    issues: _IssueCollector,
) -> tuple[dict[str, Path] | None, Path | None]:
    try:
        paths = artifact_paths(run_dir, condition, seed)
    except ValueError as exc:
        _add(issues, "unsafe_run_identity", str(exc), "manifest")
        return None, None
    try:
        run_root = require_real_directory(lexical_absolute(run_dir))
        data_root = require_real_directory(run_root / "data")
    except EvidencePathError as exc:
        _add(issues, "unsafe_evidence_root", str(exc), "manifest")
        return paths, None
    if data_root.parent != run_root:
        _add(issues, "unsafe_evidence_root", "data root escaped run root", "manifest")
        return paths, None
    return paths, data_root


def _safe_required_file(
    path: Path,
    *,
    data_root: Path,
    artifact: str,
    issues: _IssueCollector,
) -> Path | None:
    if not path.exists() and not path.is_symlink():
        _add(issues, "missing_or_empty_artifact", str(path), artifact)
        return None
    try:
        safe = require_contained_regular_file(path, data_root)
    except EvidencePathError as exc:
        _add(issues, "unsafe_artifact_path", str(exc), artifact)
        return None
    try:
        if safe.stat().st_size == 0:
            _add(issues, "missing_or_empty_artifact", str(safe), artifact)
            return None
    except OSError as exc:
        _add(issues, "artifact_read_error", str(exc), artifact)
        return None
    return safe


def _stream_csv(
    path: Path,
    *,
    data_root: Path,
    artifact: str,
    header: tuple[str, ...],
    issues: _IssueCollector,
    row_validator: Callable[[dict[str, str], int, CsvStats], None],
    retain_last_row: bool = False,
) -> CsvStats:
    stats = CsvStats()
    safe = _safe_required_file(
        path, data_root=data_root, artifact=artifact, issues=issues)
    if safe is None:
        return stats
    stats.size_bytes = safe.stat().st_size
    try:
        stats.sha256 = _checksum(safe)
        with safe.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                actual_header = tuple(next(reader))
            except StopIteration:
                _add(issues, "missing_csv_header", "CSV has no header", artifact)
                return stats
            if actual_header != header:
                _add(
                    issues,
                    "invalid_csv_header",
                    f"expected {list(header)!r}, found {list(actual_header)!r}",
                    artifact,
                    1,
                )
            for values in reader:
                row_number = reader.line_num
                stats.data_rows += 1
                if len(values) != len(header):
                    _add(
                        issues,
                        "invalid_csv_width",
                        f"expected {len(header)} columns, found {len(values)}",
                        artifact,
                        row_number,
                    )
                    continue
                row = dict(zip(header, values, strict=True))
                if retain_last_row:
                    stats.last_row = row
                row_validator(row, row_number, stats)
    except UnicodeError as exc:
        _add(issues, "invalid_utf8", str(exc), artifact)
    except csv.Error as exc:
        _add(issues, "malformed_csv", str(exc), artifact)
    except OSError as exc:
        _add(issues, "artifact_read_error", str(exc), artifact)
    return stats


def _read_manifest(
    path: Path,
    *,
    data_root: Path,
    issues: _IssueCollector,
) -> dict | None:
    safe = _safe_required_file(
        path, data_root=data_root, artifact="manifest", issues=issues)
    if safe is None:
        return None
    try:
        value = json.loads(safe.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _add(issues, "invalid_manifest", str(exc), "manifest")
        return None
    if not _is_dict(value):
        _add(issues, "invalid_manifest", "manifest root must be an object", "manifest")
        return None
    return value


def _validate_manifest_identity(
    manifest: dict,
    *,
    condition: str,
    seed: int,
    issues: _IssueCollector,
) -> None:
    manifest_seed = manifest.get("seed")
    if not _is_int(manifest_seed):
        _add(issues, "invalid_manifest_identity", "seed must be an integer", "manifest")
    elif manifest_seed != seed:
        _add(issues, "manifest_seed_mismatch", f"expected {seed}", "manifest")
    manifest_condition = manifest.get("condition")
    if not _is_str(manifest_condition):
        _add(issues, "invalid_manifest_identity", "condition must be text", "manifest")
    elif manifest_condition != condition:
        _add(issues, "manifest_condition_mismatch", f"expected {condition!r}", "manifest")
    state_hash = manifest.get("state_hash")
    if not _is_str(state_hash) or not _SHA256.fullmatch(state_hash):
        _add(issues, "invalid_state_hash", "expected lowercase SHA-256", "manifest")


def _validate_present_provenance(
    manifest: dict,
    issues: _IssueCollector,
) -> None:
    """Reject malformed provenance while allowing later-slice fields to be absent."""
    # None means the run was launched directly rather than by the experiment
    # runner, which is ordinary and remains valid engineering evidence. Only
    # V2 readiness requires plan provenance, and the expected-run contract
    # enforces that separately.
    if manifest.get("plan_identity") is not None:
        identity = manifest["plan_identity"]
        if not _is_str(identity) or not _SAFE_NAME.fullmatch(identity):
            _add(
                issues,
                "invalid_plan_identity",
                "plan_identity must be a filename-safe nonempty string",
                "manifest",
            )

    if manifest.get("plan_sha256") is not None:
        plan_sha256 = manifest["plan_sha256"]
        if not _is_str(plan_sha256) or not _SHA256.fullmatch(plan_sha256):
            _add(
                issues,
                "invalid_plan_sha256",
                "plan_sha256 must be a lowercase SHA-256 string",
                "manifest",
            )

    if "code" in manifest:
        code = manifest["code"]
        allowed_shapes = (
            {"commit", "dirty"},
            {"commit", "tag", "dirty"},
        )
        if not _is_dict(code):
            _add(
                issues,
                "invalid_code_identity_shape",
                "code must be an object",
                "manifest",
            )
        else:
            if set(code) not in allowed_shapes:
                _add(
                    issues,
                    "invalid_code_identity_shape",
                    "code must contain exactly commit/dirty and optional tag",
                    "manifest",
                )
            commit = code.get("commit")
            if not _is_str(commit) or not _COMMIT.fullmatch(commit):
                _add(
                    issues,
                    "invalid_code_commit",
                    "code.commit must be a lowercase 40-64 character commit hash",
                    "manifest",
                )
            if "tag" in code:
                tag = code["tag"]
                # None means the revision carries no annotated tag, which is
                # ordinary for development work and is valid engineering
                # evidence. Only V2 readiness requires an actual tag, and the
                # expected-run contract enforces that separately. An empty or
                # non-string tag remains malformed.
                if tag is not None and (not _is_str(tag) or not tag.strip()):
                    _add(
                        issues,
                        "invalid_code_tag",
                        "code.tag must be a nonempty string or null",
                        "manifest",
                    )
            if not _is_bool(code.get("dirty")):
                _add(
                    issues,
                    "invalid_code_dirty",
                    "code.dirty must be a boolean",
                    "manifest",
                )

    if "environment_fingerprint" in manifest:
        fingerprint = manifest["environment_fingerprint"]
        if not _is_str(fingerprint) or not _SHA256.fullmatch(fingerprint):
            _add(
                issues,
                "invalid_environment_fingerprint",
                "environment_fingerprint must be a lowercase SHA-256 string",
                "manifest",
            )

    unsupported_representations = {
        "plan": ("plan_identity", "plan_sha256"),
        "revision": ("code",),
        "environment": ("environment_fingerprint",),
        "code_commit": ("code",),
        "code_tag": ("code",),
        "code_dirty": ("code",),
        "provenance_schema_version": (),
    }
    for alias, canonical_fields in unsupported_representations.items():
        if alias not in manifest:
            continue
        if any(field_name in manifest for field_name in canonical_fields):
            _add(
                issues,
                "conflicting_provenance_representation",
                f"{alias} conflicts with the canonical provenance representation",
                "manifest",
            )
        else:
            _add(
                issues,
                "invalid_provenance_representation",
                f"{alias} is not a supported provenance representation",
                "manifest",
            )


def _resolve_artifact_policy(
    manifest: dict,
    policy: ValidationPolicy,
    issues: _IssueCollector,
) -> tuple[bool | None, int | None, str | None]:
    sealed = manifest.get("artifact_policy")
    if sealed is not None and not _is_dict(sealed):
        _add(issues, "invalid_artifact_policy", "artifact_policy must be an object", "manifest")
        sealed = {}
    sealed = sealed or {}
    if sealed and set(sealed) != {
        "allow_zero_events",
        "belief_snapshot_interval",
        "belief_snapshot_cardinality",
    }:
        _add(
            issues,
            "invalid_artifact_policy",
            "artifact_policy has an unexpected shape",
            "manifest",
        )

    sealed_zero = sealed.get("allow_zero_events")
    if sealed_zero is not None and not _is_bool(sealed_zero):
        _add(issues, "invalid_artifact_policy", "allow_zero_events must be boolean", "manifest")
        sealed_zero = None
    caller_zero = policy.allow_zero_events
    if caller_zero is not None and not _is_bool(caller_zero):
        _add(issues, "invalid_validation_policy", "allow_zero_events must be boolean", "manifest")
        caller_zero = None
    if caller_zero is not None and sealed_zero is not None and (
        caller_zero is not sealed_zero
    ):
        _add(issues, "artifact_policy_mismatch", "zero-event policy differs", "manifest")
    allow_zero = caller_zero if caller_zero is not None else sealed_zero
    if allow_zero is None:
        _add(issues, "missing_zero_event_policy", "zero-event policy must be explicit", "manifest")

    sealed_interval = sealed.get("belief_snapshot_interval")
    if not _is_int(sealed_interval) or sealed_interval < 1:
        if sealed_interval is not None:
            _add(issues, "invalid_artifact_policy", "belief cadence must be positive", "manifest")
        sealed_interval = None
    caller_interval = policy.belief_snapshot_interval
    if caller_interval is not None and (
        not _is_int(caller_interval) or caller_interval < 1
    ):
        _add(issues, "invalid_validation_policy", "belief cadence must be positive", "manifest")
        caller_interval = None
    if caller_interval is not None and sealed_interval is not None and (
        caller_interval != sealed_interval
    ):
        _add(issues, "artifact_policy_mismatch", "belief cadence differs", "manifest")
    interval = (
        caller_interval
        if caller_interval is not None
        else sealed_interval
    )
    if not _is_int(interval) or interval < 1:
        _add(issues, "missing_belief_policy", "belief cadence must be explicit", "manifest")
        interval = None

    sealed_cardinality = sealed.get("belief_snapshot_cardinality")
    if sealed_cardinality is not None and not _is_str(sealed_cardinality):
        _add(issues, "invalid_artifact_policy", "belief cardinality must be text", "manifest")
        sealed_cardinality = None
    caller_cardinality = policy.belief_snapshot_cardinality
    if caller_cardinality is not None and not _is_str(caller_cardinality):
        _add(issues, "invalid_validation_policy", "belief cardinality must be text", "manifest")
        caller_cardinality = None
    if (
        caller_cardinality is not None
        and sealed_cardinality is not None
        and caller_cardinality != sealed_cardinality
    ):
        _add(issues, "artifact_policy_mismatch", "belief cardinality differs", "manifest")
    cardinality = (
        caller_cardinality
        if caller_cardinality is not None
        else sealed_cardinality
    )
    if cardinality is None:
        _add(issues, "missing_belief_policy", "belief cardinality must be explicit", "manifest")
    elif cardinality != BELIEF_SNAPSHOT_CARDINALITY:
        _add(
            issues,
            "unsupported_belief_cardinality",
            f"found {cardinality!r}",
            "manifest",
        )
    return allow_zero, interval, cardinality


def _validate_legacy(
    run_dir: Path,
    condition: str,
    seed: int,
    manifest: dict,
    paths: dict[str, Path],
    data_root: Path,
    issues: _IssueCollector,
    notices: list[ValidationNotice],
) -> ValidationReport:
    _validate_manifest_identity(manifest, condition=condition, seed=seed, issues=issues)
    previous_ticks = {"events": None, "beliefs": None}

    def basic_tick_validator(artifact: str):
        def validate(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
            row_seed = _parse_int(
                row["seed"], field_name="seed", artifact=artifact,
                row=row_number, issues=issues)
            tick = _parse_int(
                row["tick"], field_name="tick", artifact=artifact,
                row=row_number, issues=issues)
            if row_seed is not None and row_seed != seed:
                _add(issues, "csv_seed_mismatch", f"expected {seed}", artifact, row_number)
            previous = previous_ticks.get(artifact)
            if tick is not None and previous is not None and tick < previous:
                _add(issues, "decreasing_tick", f"{tick} follows {previous}", artifact, row_number)
            if tick is not None:
                previous_ticks[artifact] = tick
                stats.last_tick = tick
        return validate

    metrics_previous = 0

    def legacy_metrics(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal metrics_previous
        row_seed = _parse_int(
            row["seed"], field_name="seed", artifact="metrics",
            row=row_number, issues=issues)
        tick = _parse_int(
            row["tick"], field_name="tick", artifact="metrics",
            row=row_number, issues=issues)
        if row_seed is not None and row_seed != seed:
            _add(issues, "csv_seed_mismatch", f"expected {seed}", "metrics", row_number)
        if tick is not None:
            if tick < metrics_previous:
                _add(issues, "decreasing_tick", f"{tick} follows {metrics_previous}", "metrics", row_number)
            metrics_previous = tick
            stats.last_tick = tick

    metrics = _stream_csv(
        paths["metrics"], data_root=data_root, artifact="metrics",
        header=METRICS_HEADER, issues=issues, row_validator=legacy_metrics)
    _stream_csv(
        paths["events"], data_root=data_root, artifact="events",
        header=EVENTS_HEADER, issues=issues,
        row_validator=basic_tick_validator("events"))
    _stream_csv(
        paths["beliefs"], data_root=data_root, artifact="beliefs",
        header=BELIEFS_HEADER, issues=issues,
        row_validator=basic_tick_validator("beliefs"))

    matching_summary_rows = 0

    def legacy_summary(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal matching_summary_rows
        row_seed = _parse_int(
            row["seed"], field_name="seed", artifact="summary",
            row=row_number, issues=issues)
        if row_seed == seed and row["condition"] == condition:
            matching_summary_rows += 1

    summary = _stream_csv(
        paths["summary"], data_root=data_root, artifact="summary",
        header=RUN_SUMMARY_HEADER, issues=issues, row_validator=legacy_summary)
    if metrics.data_rows == 0:
        _add(issues, "header_only_required_artifact", "metrics requires rows", "metrics")
    if summary.data_rows == 0 or matching_summary_rows == 0:
        _add(issues, "missing_summary_row", "no matching legacy summary row", "summary")
    notices.append(ValidationNotice(
        "legacy_evidence",
        "schema-1 evidence is readable but cannot satisfy the V2 completion contract",
        "manifest",
    ))
    valid = not issues
    return ValidationReport(
        valid=valid,
        v2_ready=False,
        classification="legacy" if valid else "invalid",
        issues=issues.materialize(),
        notices=notices,
        manifest=manifest,
    )


def _validate_writer_health(manifest: dict, issues: _IssueCollector) -> None:
    health = manifest.get("writer_health")
    if not _is_dict(health):
        _add(issues, "missing_or_invalid_termination_field", "writer_health must be dict", "manifest")
        return
    expected_health_fields = {
        "metrics_write_failures", "metrics_flush_failures",
        "event_write_failures", "event_flush_failures",
        "event_flush_failures_recovered", "event_flush_failures_unrecovered",
        "belief_write_failures", "belief_flush_failures",
        "summary_write_failures", "close_failures", "finalization_failures",
        "pending_event_rows", "finalized", "closed", "unresolved_failures",
    }
    if set(health) != expected_health_fields:
        _add(issues, "invalid_writer_health", "writer_health has an unexpected shape", "manifest")
    nonrecoverable = (
        "metrics_write_failures", "metrics_flush_failures",
        "event_write_failures", "belief_write_failures",
        "belief_flush_failures", "summary_write_failures", "close_failures",
        "finalization_failures",
    )
    for name in nonrecoverable:
        value = health.get(name)
        if not _is_int(value) or value < 0:
            _add(issues, "invalid_writer_health", f"invalid {name}", "manifest")
        elif value:
            _add(issues, "nonrecoverable_writer_failure", f"{name}={value}", "manifest")
    event_fields = (
        "event_flush_failures", "event_flush_failures_recovered",
        "event_flush_failures_unrecovered", "pending_event_rows",
    )
    parsed: dict[str, int] = {}
    for name in event_fields:
        value = health.get(name)
        if not _is_int(value) or value < 0:
            _add(issues, "invalid_writer_health", f"invalid {name}", "manifest")
        else:
            parsed[name] = value
    total = parsed.get("event_flush_failures")
    recovered = parsed.get("event_flush_failures_recovered")
    unrecovered = parsed.get("event_flush_failures_unrecovered")
    if total is not None and recovered is not None and unrecovered is not None and (
        total != recovered + unrecovered
    ):
        _add(issues, "inconsistent_writer_health", "event flush accounting differs", "manifest")
    if unrecovered:
        _add(issues, "unresolved_writer_failure", "event flush remains unrecovered", "manifest")
    if parsed.get("pending_event_rows"):
        _add(issues, "pending_event_rows", "pending event rows must be zero", "manifest")
    if not _is_bool(health.get("finalized")) or not _is_bool(health.get("closed")):
        _add(issues, "invalid_writer_health", "finalized and closed must be booleans", "manifest")
    if health.get("finalized") is not True or health.get("closed") is not True:
        _add(issues, "unsealed_writer", "writer must be finalized and closed", "manifest")
    unresolved = health.get("unresolved_failures")
    if not _is_list(unresolved) or not all(_is_str(item) for item in unresolved):
        _add(issues, "invalid_writer_health", "unresolved failures must be a text list", "manifest")
    if not _is_list(unresolved) or unresolved:
        _add(issues, "unresolved_writer_failure", f"found {unresolved!r}", "manifest")


def _strict_artifacts(
    *,
    paths: dict[str, Path],
    data_root: Path,
    condition: str,
    seed: int,
    final_tick: object,
    termination_reason: object,
    allow_zero_events: bool | None,
    belief_interval: int | None,
    issues: _IssueCollector,
    notices: list[ValidationNotice],
) -> tuple[dict[str, CsvStats], dict[str, str] | None]:
    expected_tick = 1
    cumulative_previous = {name: 0 for name in METRICS_CUMULATIVE_FIELDS}

    def metrics_validator(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal expected_tick
        integers: dict[str, int | None] = {}
        floats: dict[str, float | None] = {}
        for name in METRICS_INTEGER_FIELDS:
            integers[name] = _parse_int(
                row[name], field_name=name, artifact="metrics",
                row=row_number, issues=issues)
        for name in METRICS_FLOAT_FIELDS:
            floats[name] = _parse_float(
                row[name], field_name=name, artifact="metrics",
                row=row_number, issues=issues)
        if integers["seed"] is not None and integers["seed"] != seed:
            _add(issues, "csv_seed_mismatch", f"expected {seed}", "metrics", row_number)
        for name in METRICS_NONNEGATIVE_INTEGER_FIELDS:
            value = integers[name]
            if value is not None and value < 0:
                _add(issues, "negative_metric_value", name, "metrics", row_number)
        for name in METRICS_NONNEGATIVE_FLOAT_FIELDS:
            value = floats[name]
            if value is not None and value < 0:
                _add(issues, "negative_metric_value", name, "metrics", row_number)
        for name in METRICS_UNIT_INTERVAL_FIELDS:
            value = floats[name]
            if value is not None and not 0 <= value <= 1:
                _add(issues, "metric_out_of_domain", name, "metrics", row_number)
        season = integers["season"]
        if season is not None and season not in METRICS_SEASON_VALUES:
            _add(issues, "metric_out_of_domain", "season", "metrics", row_number)
        for name in METRICS_CUMULATIVE_FIELDS:
            value = integers[name]
            if value is not None:
                if value < cumulative_previous[name]:
                    _add(issues, "decreasing_cumulative_metric", name, "metrics", row_number)
                cumulative_previous[name] = value
        tick = integers["tick"]
        if tick is not None:
            if tick != expected_tick:
                code = "decreasing_tick" if tick < expected_tick else "metrics_tick_gap"
                _add(issues, code, f"expected {expected_tick}, found {tick}", "metrics", row_number)
                expected_tick = tick + 1
            else:
                expected_tick += 1
            if _is_int(final_tick) and tick > final_tick:
                _add(issues, "row_beyond_final_tick", f"tick {tick} exceeds {final_tick}", "metrics", row_number)
            stats.last_tick = tick
            if belief_interval and tick % belief_interval == 0 and integers["population"] is not None:
                stats.belief_populations[tick] = integers["population"]
        population = integers["population"]
        factions = integers["faction_count"]
        gini = floats["gini"]
        if population is not None:
            stats.max_population = population if stats.max_population is None else max(
                stats.max_population, population)
            if population > 0:
                stats.min_positive_population = (
                    population if stats.min_positive_population is None
                    else min(stats.min_positive_population, population)
                )
        if factions is not None:
            stats.max_factions = factions if stats.max_factions is None else max(
                stats.max_factions, factions)
        if gini is not None:
            stats.max_gini = gini if stats.max_gini is None else max(stats.max_gini, gini)
            stats.gini_sum += gini

    metrics = _stream_csv(
        paths["metrics"], data_root=data_root, artifact="metrics",
        header=METRICS_HEADER, issues=issues, row_validator=metrics_validator,
        retain_last_row=True)
    if metrics.data_rows == 0:
        _add(issues, "header_only_required_artifact", "metrics requires rows", "metrics")
    if _is_int(final_tick) and metrics.last_tick != final_tick:
        _add(issues, "wrong_final_tick", f"metrics end at {metrics.last_tick}, manifest says {final_tick}", "metrics")

    event_previous: int | None = None

    def event_validator(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal event_previous
        row_seed = _parse_int(
            row["seed"], field_name="seed", artifact="events",
            row=row_number, issues=issues)
        tick = _parse_int(
            row["tick"], field_name="tick", artifact="events",
            row=row_number, issues=issues)
        schema = _parse_int(
            row["event_schema_version"], field_name="event_schema_version",
            artifact="events", row=row_number, issues=issues)
        if row_seed is not None and row_seed != seed:
            _add(issues, "csv_seed_mismatch", f"expected {seed}", "events", row_number)
        if tick is not None:
            if tick < 1:
                _add(issues, "event_tick_out_of_domain", str(tick), "events", row_number)
            if event_previous is not None and tick < event_previous:
                _add(issues, "decreasing_tick", f"{tick} follows {event_previous}", "events", row_number)
            if _is_int(final_tick) and tick > final_tick:
                _add(issues, "row_beyond_final_tick", f"tick {tick} exceeds {final_tick}", "events", row_number)
            event_previous = tick
            stats.last_tick = tick
        if schema is not None and schema != EVENT_SCHEMA_VERSION:
            _add(issues, "event_schema_version_mismatch", f"found {schema}", "events", row_number)
        event_type = row["event_type"]
        allowed = EVENT_TYPES_BY_SCHEMA.get(schema) if schema is not None else None
        if not event_type or allowed is None or event_type not in allowed:
            _add(issues, "unknown_event_type", repr(event_type), "events", row_number)
        else:
            stats.event_counts[event_type] += 1
            if tick is not None:
                stats.event_first_ticks.setdefault(event_type, tick)
            if event_type == "tech_researched":
                technology = row["detail"]
                if technology not in TECHNOLOGY_IDENTIFIERS:
                    _add(
                        issues,
                        "unknown_technology_identifier",
                        repr(technology),
                        "events",
                        row_number,
                    )
                else:
                    stats.technology_ids.add(technology)

    events = _stream_csv(
        paths["events"], data_root=data_root, artifact="events",
        header=EVENTS_HEADER, issues=issues, row_validator=event_validator)
    if events.data_rows == 0:
        if allow_zero_events is True:
            notices.append(ValidationNotice(
                "accepted_zero_event_stream",
                "the explicit artifact contract permits zero events",
                "events",
            ))
        else:
            _add(issues, "header_only_required_artifact", "events require rows", "events")

    belief_previous: int | None = None
    current_belief_tick: int | None = None
    current_belief_ids: set[str] = set()
    belief_counts: dict[int, int] = {}

    def finish_belief_group() -> None:
        if current_belief_tick is not None:
            belief_counts[current_belief_tick] = len(current_belief_ids)

    def belief_validator(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal belief_previous, current_belief_tick, current_belief_ids
        row_seed = _parse_int(
            row["seed"], field_name="seed", artifact="beliefs",
            row=row_number, issues=issues)
        tick = _parse_int(
            row["tick"], field_name="tick", artifact="beliefs",
            row=row_number, issues=issues)
        if row_seed is not None and row_seed != seed:
            _add(issues, "csv_seed_mismatch", f"expected {seed}", "beliefs", row_number)
        if tick is None:
            return
        if tick < 1:
            _add(issues, "belief_tick_out_of_domain", str(tick), "beliefs", row_number)
        if belief_previous is not None and tick < belief_previous:
            _add(issues, "decreasing_tick", f"{tick} follows {belief_previous}", "beliefs", row_number)
        if _is_int(final_tick) and tick > final_tick:
            _add(issues, "row_beyond_final_tick", f"tick {tick} exceeds {final_tick}", "beliefs", row_number)
        if belief_interval and tick % belief_interval != 0:
            _add(issues, "belief_tick_off_cadence", f"tick {tick}", "beliefs", row_number)
        if current_belief_tick != tick:
            finish_belief_group()
            current_belief_tick = tick
            current_belief_ids = set()
        identity = row["inhabitant_id"].strip()
        if not identity:
            _add(issues, "invalid_belief_identity", "inhabitant_id is empty", "beliefs", row_number)
        elif identity in current_belief_ids:
            _add(issues, "duplicate_belief_identity", identity, "beliefs", row_number)
        else:
            current_belief_ids.add(identity)
        belief_previous = tick
        stats.last_tick = tick

    beliefs = _stream_csv(
        paths["beliefs"], data_root=data_root, artifact="beliefs",
        header=BELIEFS_HEADER, issues=issues, row_validator=belief_validator)
    finish_belief_group()
    expected_beliefs = {
        tick: population
        for tick, population in metrics.belief_populations.items()
        if population > 0
    }
    for tick, population in metrics.belief_populations.items():
        if population == 0 and tick in belief_counts:
            _add(issues, "unexpected_belief_snapshot", f"tick {tick} has no living population", "beliefs")
    for tick, expected_count in expected_beliefs.items():
        actual = belief_counts.get(tick)
        if actual != expected_count:
            _add(
                issues,
                "belief_snapshot_count_mismatch",
                f"tick {tick}: expected {expected_count}, found {actual}",
                "beliefs",
            )
    for tick in set(belief_counts) - set(expected_beliefs):
        if metrics.belief_populations.get(tick, 0) <= 0:
            _add(issues, "unexpected_belief_snapshot", f"tick {tick}", "beliefs")
    if beliefs.data_rows == 0:
        if expected_beliefs:
            _add(issues, "header_only_required_artifact", "belief snapshots require rows", "beliefs")
        else:
            notices.append(ValidationNotice(
                "accepted_zero_beliefs_no_required_cadence",
                "no cadence had living inhabitants requiring belief rows",
                "beliefs",
            ))

    summary_row: dict[str, str] | None = None

    def summary_validator(row: dict[str, str], row_number: int, stats: CsvStats) -> None:
        nonlocal summary_row
        if summary_row is None:
            summary_row = row
        integers: dict[str, int | None] = {}
        floats: dict[str, float | None] = {}
        for name in SUMMARY_INTEGER_FIELDS:
            integers[name] = _parse_int(
                row[name], field_name=name, artifact="summary",
                row=row_number, issues=issues)
        for name in SUMMARY_FLOAT_FIELDS:
            floats[name] = _parse_float(
                row[name], field_name=name, artifact="summary",
                row=row_number, issues=issues)
        for name in SUMMARY_NONNEGATIVE_INTEGER_FIELDS:
            value = integers[name]
            if value is not None and value < 0:
                _add(issues, "negative_summary_value", name, "summary", row_number)
        for name in SUMMARY_NONNEGATIVE_FLOAT_FIELDS:
            value = floats[name]
            if value is not None and value < 0:
                _add(issues, "negative_summary_value", name, "summary", row_number)
        for name in SUMMARY_UNIT_INTERVAL_FIELDS:
            value = floats[name]
            if value is not None and not 0 <= value <= 1:
                _add(issues, "summary_value_out_of_domain", name, "summary", row_number)

    summary = _stream_csv(
        paths["summary"], data_root=data_root, artifact="summary",
        header=RUN_SUMMARY_HEADER, issues=issues, row_validator=summary_validator)
    if summary.data_rows == 0:
        _add(issues, "header_only_required_artifact", "summary requires one row", "summary")
    elif summary.data_rows != 1:
        _add(issues, "summary_row_count_mismatch", f"expected 1, found {summary.data_rows}", "summary")
        summary_row = None

    if summary_row is not None and metrics.last_row is not None:
        if summary_row["seed"] != str(seed):
            _add(issues, "summary_seed_mismatch", f"expected {seed}", "summary", 2)
        if summary_row["condition"] != condition:
            _add(issues, "summary_condition_mismatch", f"expected {condition!r}", "summary", 2)
        expected_min = metrics.min_positive_population
        if expected_min is None:
            expected_min = _text_int(metrics.last_row["population"])
        exact = {
            "final_population": metrics.last_row["population"],
            "peak_population": (
                str(metrics.max_population) if metrics.max_population is not None else None
            ),
            "min_population": str(expected_min) if expected_min is not None else None,
            "final_faction_count": metrics.last_row["faction_count"],
            "peak_faction_count": (
                str(metrics.max_factions) if metrics.max_factions is not None else None
            ),
            "total_wars": metrics.last_row["total_wars_declared"],
            "total_deaths": metrics.last_row["total_deaths"],
            "total_births": metrics.last_row["total_births"],
            "total_schisms": metrics.last_row["total_schisms"],
            "total_mergers": metrics.last_row["total_mergers"],
            "max_generation": metrics.last_row["max_generation"],
        }
        for name, expected in exact.items():
            if expected is not None and summary_row[name] != expected:
                _add(issues, "summary_metrics_mismatch", f"{name}: expected {expected}, found {summary_row[name]}", "summary", 2)
        numeric_expected = {
            "final_gini": _text_float(metrics.last_row["gini"]),
            "peak_gini": metrics.max_gini,
            "mean_gini": round(metrics.gini_sum / metrics.data_rows, 4),
        }
        for name, expected in numeric_expected.items():
            actual = _text_float(summary_row[name])
            if (
                actual is not None
                and expected is not None
                and abs(actual - expected) > 0.0001
            ):
                _add(issues, "summary_metrics_mismatch", f"{name} differs", "summary", 2)
        final_techs = _text_int(metrics.last_row["total_techs"])
        final_factions = _text_int(metrics.last_row["faction_count"])
        if final_techs is not None and final_factions is not None:
            expected_mean_techs = round(
                final_techs / final_factions if final_factions else 0.0,
                4,
            )
            actual_mean_techs = _text_float(
                summary_row["mean_tech_count_per_faction"])
            if (
                actual_mean_techs is not None
                and abs(actual_mean_techs - expected_mean_techs) > 0.0001
            ):
                _add(
                    issues,
                    "summary_metrics_mismatch",
                    "mean_tech_count_per_faction differs",
                    "summary",
                    2,
                )
        unique_techs = len(events.technology_ids)
        total_unique_techs = _text_int(summary_row["total_unique_techs"])
        if total_unique_techs is not None and total_unique_techs != unique_techs:
            _add(
                issues,
                "summary_events_mismatch",
                "total_unique_techs differs from tech_researched rows",
                "summary",
                2,
            )
        mean_war_duration = _text_float(summary_row["mean_war_duration"])
        if (
            mean_war_duration is not None
            and not events.event_counts["war_ended"]
            and mean_war_duration != 0.0
        ):
            _add(
                issues,
                "summary_events_mismatch",
                "mean_war_duration must be zero without war_ended rows",
                "summary",
                2,
            )
        for metrics_field, event_type in METRICS_EVENT_COUNT_FIELDS.items():
            value = _text_int(metrics.last_row[metrics_field])
            if value is not None and value != events.event_counts[event_type]:
                _add(issues, "metrics_events_mismatch", f"{metrics_field} differs from {event_type} rows", "metrics")
        for summary_field, event_type in SUMMARY_EVENT_COUNT_FIELDS.items():
            value = _text_int(summary_row[summary_field])
            if value is not None and value != events.event_counts[event_type]:
                _add(issues, "summary_events_mismatch", f"{summary_field} differs from {event_type} rows", "summary", 2)
        expected_first = events.event_first_ticks.get("faction_formed", 0)
        first_tick = _text_int(summary_row["first_faction_tick"])
        if first_tick is not None and first_tick != expected_first:
            _add(issues, "summary_events_mismatch", "first_faction_tick differs", "summary", 2)
        if termination_reason == "extinction" and metrics.last_row["population"] != "0":
            _add(issues, "invalid_extinction_terminal", "final metrics population is not zero", "metrics")

    return {
        "metrics": metrics,
        "events": events,
        "beliefs": beliefs,
        "summary": summary,
    }, summary_row


def _validate_inventory(
    manifest: dict,
    *,
    paths: dict[str, Path],
    stats: dict[str, CsvStats],
    issues: _IssueCollector,
) -> None:
    inventory_errors = manifest.get("artifact_inventory_errors")
    if (
        not _is_list(inventory_errors)
        or not all(_is_str(item) for item in inventory_errors)
        or inventory_errors
    ):
        _add(issues, "artifact_inventory_error", f"found {inventory_errors!r}", "manifest")
    inventory = manifest.get("artifact_inventory")
    if not _is_dict(inventory):
        _add(issues, "missing_or_invalid_termination_field", "artifact_inventory must be dict", "manifest")
        return
    if set(inventory) != set(_STRICT_ARTIFACTS):
        _add(issues, "artifact_inventory_scope_mismatch", "inventory must contain exactly four artifacts", "manifest")
    versions = {
        "metrics": METRICS_SCHEMA_VERSION,
        "events": EVENT_SCHEMA_VERSION,
        "beliefs": BELIEFS_SCHEMA_VERSION,
        "summary": RUN_SUMMARY_SCHEMA_VERSION,
    }
    for label in _STRICT_ARTIFACTS:
        entry = inventory.get(label)
        if not _is_dict(entry):
            _add(issues, "missing_inventory_entry", label, "manifest")
            continue
        expected_keys = {
            "path", "size_bytes", "sha256", "data_rows", "schema_version",
        }
        if set(entry) != expected_keys:
            _add(
                issues,
                "inventory_entry_shape_mismatch",
                f"{label} must contain exactly {sorted(expected_keys)!r}",
                "manifest",
            )
        expected_name = paths[label].name
        if not validate_inventory_relative_path(entry.get("path"), expected_name):
            _add(issues, "unsafe_inventory_path", f"{label}.path={entry.get('path')!r}", "manifest")
        sha256 = entry.get("sha256")
        if not _is_str(sha256) or not _SHA256.fullmatch(sha256):
            _add(issues, "invalid_inventory_value", f"{label}.sha256", "manifest")
        for name in ("size_bytes", "data_rows", "schema_version"):
            value = entry.get(name)
            if not _is_int(value) or value < 0:
                _add(issues, "invalid_inventory_value", f"{label}.{name}", "manifest")
        expected = {
            "size_bytes": stats[label].size_bytes,
            "sha256": stats[label].sha256,
            "data_rows": stats[label].data_rows,
            "schema_version": versions[label],
        }
        for name, value in expected.items():
            if not _exact_equal(entry.get(name), value):
                _add(issues, "artifact_inventory_mismatch", f"{label}.{name}: expected {value!r}, found {entry.get(name)!r}", "manifest")


def _readiness_issues(
    manifest: dict,
    contract: ExpectedRunContract | None,
) -> list[ValidationIssue]:
    issues = _IssueCollector()
    config_value = manifest.get("configuration")
    config = config_value if _is_dict(config_value) else {}
    safe_social_controls = {
        "social_memory_enabled": False,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": DEFAULT_MAXIMUM_SOCIAL_TIES,
        "relationship_decay_interval": DEFAULT_RELATIONSHIP_DECAY_INTERVAL,
        "social_controls_status": "disabled",
        "social_control_notices": [],
    }
    for name, expected in safe_social_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "social_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    # Endogenous Language v1 is the one contracted language mechanism. The gate
    # may take either value so a run can serve as treatment or control; every
    # other base-language control is pinned to its approved value.
    for name, expected in APPROVED_LANGUAGE_CONTROLS.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "language_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    language_gate = config.get("language_evolution_enabled")
    if not _is_bool(language_gate):
        _add(
            issues,
            "language_controls_not_v2_ready",
            "configuration.language_evolution_enabled: expected a boolean, "
            f"found {language_gate!r}",
            "manifest",
        )
    language_status = config.get("language_controls_status")
    expected_status = "contracted" if language_gate is True else "disabled"
    if not _exact_equal(language_status, expected_status):
        _add(
            issues,
            "language_controls_not_v2_ready",
            f"configuration.language_controls_status: expected "
            f"{expected_status!r}, found {language_status!r}",
            "manifest",
        )
    language_notices = config.get("language_control_notices")
    if not _exact_equal(language_notices, []):
        _add(
            issues,
            "language_controls_not_v2_ready",
            "configuration.language_control_notices: expected [], "
            f"found {language_notices!r}",
            "manifest",
        )
    safe_coalition_controls = {
        "coalition_emergence_enabled": False,
        "coalition_minimum_size": DEFAULT_COALITION_MINIMUM_SIZE,
        "coalition_trust_threshold": DEFAULT_COALITION_TRUST_THRESHOLD,
        "coalition_familiarity_threshold": (
            DEFAULT_COALITION_FAMILIARITY_THRESHOLD
        ),
        "coalition_maximum_grievance": DEFAULT_COALITION_MAXIMUM_GRIEVANCE,
        "coalition_persistence_ticks": DEFAULT_COALITION_PERSISTENCE_TICKS,
        "maximum_active_coalitions": DEFAULT_MAXIMUM_ACTIVE_COALITIONS,
        "coalition_controls_status": "disabled",
        "coalition_control_notices": [],
    }
    for name, expected in safe_coalition_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "coalition_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_dialect_controls = {
        "coalition_dialect_influence_enabled": (
            DEFAULT_COALITION_DIALECT_INFLUENCE_ENABLED
        ),
        "same_coalition_learning_multiplier": (
            DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER
        ),
        "same_coalition_reinforcement_multiplier": (
            DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER
        ),
        "dialect_controls_status": "disabled",
        "dialect_control_notices": [],
    }
    for name, expected in safe_dialect_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "dialect_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_language_contact_controls = {
        "language_contact_enabled": DEFAULT_LANGUAGE_CONTACT_ENABLED,
        "cross_group_learning_multiplier": (
            DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER
        ),
        "borrowing_exposure_threshold": DEFAULT_BORROWING_EXPOSURE_THRESHOLD,
        "borrowing_confidence_threshold": (
            DEFAULT_BORROWING_CONFIDENCE_THRESHOLD
        ),
        "language_contact_controls_status": "disabled",
        "language_contact_control_notices": [],
    }
    for name, expected in safe_language_contact_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "language_contact_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_intergenerational_language_controls = {
        "intergenerational_language_enabled": (
            DEFAULT_INTERGENERATIONAL_LANGUAGE_ENABLED),
        "maximum_parental_meanings_per_parent": (
            DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT),
        "intergenerational_learning_strength": (
            DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH),
        "intergenerational_language_controls_status": "disabled",
        "intergenerational_language_control_notices": [],
    }
    for name, expected in safe_intergenerational_language_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "intergenerational_language_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_lexical_evolution_controls = {
        "lexical_evolution_enabled": DEFAULT_LEXICAL_EVOLUTION_ENABLED,
        "lexical_mutation_rate": DEFAULT_LEXICAL_MUTATION_RATE,
        "maximum_lexical_lineage_depth": (
            DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH),
        "lexical_evolution_controls_status": "disabled",
        "lexical_evolution_control_notices": [],
    }
    for name, expected in safe_lexical_evolution_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "lexical_evolution_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_compositional_protolanguage_controls = {
        "compositional_protolanguage_enabled": (
            DEFAULT_COMPOSITIONAL_PROTOLANGUAGE_ENABLED),
        "maximum_resource_morpheme_length": (
            DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH),
        "modality_morpheme_length": DEFAULT_MODALITY_MORPHEME_LENGTH,
        "compositional_protolanguage_controls_status": "disabled",
        "compositional_protolanguage_control_notices": [],
    }
    for name, expected in safe_compositional_protolanguage_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "compositional_protolanguage_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_grammar_evolution_controls = {
        "grammar_evolution_enabled": DEFAULT_GRAMMAR_EVOLUTION_ENABLED,
        "order_adoption_threshold": DEFAULT_ORDER_ADOPTION_THRESHOLD,
        "grammar_evolution_controls_status": "disabled",
        "grammar_evolution_control_notices": [],
    }
    for name, expected in safe_grammar_evolution_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "grammar_evolution_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_language_coevolution_controls = {
        "language_coevolution_enabled": DEFAULT_LANGUAGE_COEVOLUTION_ENABLED,
        "intelligibility_reward": DEFAULT_INTELLIGIBILITY_REWARD,
        "intelligibility_penalty": DEFAULT_INTELLIGIBILITY_PENALTY,
        "language_coevolution_controls_status": "disabled",
        "language_coevolution_control_notices": [],
    }
    for name, expected in safe_language_coevolution_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "language_coevolution_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    # The contracted primary endpoint must be present and internally
    # consistent. Evidence that does not carry it cannot be V2-ready, which
    # correctly excludes every artifact recorded before this contract.
    endpoint = manifest.get("language_endpoint")
    if not _is_dict(endpoint):
        _add(
            issues,
            "missing_language_endpoint",
            f"language_endpoint must be an object, found {endpoint!r}",
            "manifest",
        )
    else:
        if not _exact_equal(
            endpoint.get("name"), "comprehension_success_rate"
        ):
            _add(
                issues,
                "invalid_language_endpoint",
                f"unexpected endpoint name {endpoint.get('name')!r}",
                "manifest",
            )
        attempts = endpoint.get("communication_attempt_count")
        successes = endpoint.get("successful_interpretation_count")
        rate = endpoint.get("comprehension_success_rate")
        if not _is_int(attempts) or attempts < 0:
            _add(issues, "invalid_language_endpoint",
                 f"communication_attempt_count invalid: {attempts!r}",
                 "manifest")
        elif not _is_int(successes) or not 0 <= successes <= attempts:
            _add(issues, "invalid_language_endpoint",
                 f"successful_interpretation_count invalid: {successes!r}",
                 "manifest")
        elif attempts == 0:
            if rate is not None:
                _add(issues, "invalid_language_endpoint",
                     "an unattempted run has no comprehension rate, "
                     f"found {rate!r}", "manifest")
        elif type(rate) is not float or not 0.0 <= rate <= 1.0:
            _add(issues, "invalid_language_endpoint",
                 f"comprehension_success_rate invalid: {rate!r}", "manifest")
    safe_production_trial_controls = {
        "production_trial_enabled": DEFAULT_PRODUCTION_TRIAL_ENABLED,
        "production_trial_interval": DEFAULT_PRODUCTION_TRIAL_INTERVAL,
        "production_trial_controls_status": "disabled",
        "production_trial_control_notices": [],
    }
    for name, expected in safe_production_trial_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "production_trial_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    safe_coalition_intelligibility_controls = {
        "coalition_intelligibility_enabled": (
            DEFAULT_COALITION_INTELLIGIBILITY_ENABLED),
        "coalition_intelligibility_threshold": (
            DEFAULT_COALITION_INTELLIGIBILITY_THRESHOLD),
        "coalition_intelligibility_controls_status": "disabled",
        "coalition_intelligibility_control_notices": [],
    }
    for name, expected in safe_coalition_intelligibility_controls.items():
        actual = config.get(name)
        if not _exact_equal(actual, expected):
            _add(
                issues,
                "coalition_intelligibility_controls_not_v2_ready",
                f"configuration.{name}: expected {expected!r}, "
                f"found {actual!r}",
                "manifest",
            )
    if contract is None:
        _add(issues, "missing_expected_run_contract", "no complete external expected-run contract was supplied", "manifest")
        return issues.materialize()
    incomplete = contract.completeness_errors()
    if incomplete:
        _add(issues, "incomplete_expected_run_contract", ", ".join(incomplete), "manifest")
        return issues.materialize()
    assert contract.disabled_layers is not None
    policy_value = manifest.get("artifact_policy")
    code_value = manifest.get("code")
    policy = policy_value if _is_dict(policy_value) else {}
    code = code_value if _is_dict(code_value) else {}
    if not _is_dict(config_value):
        _add(issues, "expected_run_contract_mismatch", "configuration must be an object", "manifest")
    if not _is_dict(policy_value) or set(policy) != {
        "allow_zero_events",
        "belief_snapshot_interval",
        "belief_snapshot_cardinality",
    }:
        _add(issues, "expected_run_contract_mismatch", "artifact_policy shape differs", "manifest")
    if not _is_dict(code_value) or set(code) != {"commit", "tag", "dirty"}:
        _add(issues, "expected_run_contract_mismatch", "code identity shape differs", "manifest")
    actual_disabled = _normalize_disabled_layers(config.get("disabled_layers"))
    actual_combat = (
        "combat" not in actual_disabled
        if actual_disabled is not None
        else None
    )
    comparisons = {
        "seed": (manifest.get("seed"), contract.seed),
        "condition": (manifest.get("condition"), contract.condition),
        "requested_ticks": (manifest.get("requested_ticks"), contract.requested_ticks),
        "log_mode": (manifest.get("log_mode"), contract.log_mode),
        "configuration.log_mode": (config.get("log_mode"), contract.log_mode),
        "anti_stagnation_enabled": (config.get("anti_stagnation_enabled"), contract.anti_stagnation_enabled),
        "disabled_layers": (actual_disabled, contract.disabled_layers),
        "combat_enabled": (actual_combat, contract.combat_enabled),
        "raids_enabled": (config.get("raids_enabled"), contract.raids_enabled),
        "execution_mode": (manifest.get("execution_mode"), contract.execution_mode),
        "plan_identity": (manifest.get("plan_identity"), contract.plan_identity),
        "plan_sha256": (manifest.get("plan_sha256"), contract.plan_sha256),
        "code.commit": (code.get("commit"), contract.code_commit),
        "code.tag": (code.get("tag"), contract.code_tag),
        "code.dirty": (code.get("dirty"), contract.code_dirty),
        "environment_fingerprint": (manifest.get("environment_fingerprint"), contract.environment_fingerprint),
        "artifact_policy.allow_zero_events": (policy.get("allow_zero_events"), contract.allow_zero_events),
        "artifact_policy.belief_snapshot_interval": (policy.get("belief_snapshot_interval"), contract.belief_snapshot_interval),
        "artifact_policy.belief_snapshot_cardinality": (
            policy.get("belief_snapshot_cardinality"),
            contract.belief_snapshot_cardinality,
        ),
    }
    for name, (actual, expected) in comparisons.items():
        if not _exact_equal(actual, expected):
            _add(issues, "expected_run_contract_mismatch", f"{name}: expected {expected!r}, found {actual!r}", "manifest")
    return issues.materialize()


def _validate_strict(
    run_dir: Path,
    condition: str,
    seed: int,
    expected_ticks: int | None,
    manifest: dict,
    paths: dict[str, Path],
    data_root: Path,
    policy: ValidationPolicy,
    expected_contract: ExpectedRunContract | None,
    issues: _IssueCollector,
    notices: list[ValidationNotice],
) -> ValidationReport:
    _validate_manifest_identity(manifest, condition=condition, seed=seed, issues=issues)
    _validate_present_provenance(manifest, issues)
    required_fields = {
        "requested_ticks": int,
        "final_tick": int,
        "completed_ticks": int,
        "termination_reason": str,
        "result_status": str,
        "completed_normally": bool,
        "artifact_inventory_errors": list,
        "artifact_schema_versions": dict,
        "metrics_timing_contract": str,
        "finalization_diagnostics": list,
    }
    for name, expected_type in required_fields.items():
        value = manifest.get(name)
        valid_type = type(value) is expected_type
        if name not in manifest or not valid_type:
            _add(issues, "missing_or_invalid_termination_field", f"{name} must be {expected_type.__name__}", "manifest")

    requested_ticks = manifest.get("requested_ticks")
    final_tick = manifest.get("final_tick")
    completed_ticks = manifest.get("completed_ticks")
    if expected_ticks is not None and _is_int(requested_ticks) and requested_ticks != expected_ticks:
        _add(issues, "requested_ticks_mismatch", f"expected {expected_ticks}, found {requested_ticks}", "manifest")
    if _is_int(requested_ticks) and requested_ticks < 1:
        _add(issues, "invalid_requested_ticks", "must be positive", "manifest")
    if _is_int(final_tick) and _is_int(requested_ticks) and not 0 <= final_tick <= requested_ticks:
        _add(issues, "invalid_final_tick", "must be within requested horizon", "manifest")
    if _is_int(completed_ticks) and _is_int(final_tick) and completed_ticks != final_tick:
        _add(issues, "completed_ticks_mismatch", "must equal final_tick", "manifest")

    result_status = manifest.get("result_status")
    completed_normally = manifest.get("completed_normally")
    termination_reason = manifest.get("termination_reason")
    if result_status != "completed":
        _add(issues, "noncompleted_result_status", f"found {result_status!r}", "manifest")
    if completed_normally is not True:
        _add(issues, "not_completed_normally", "must be true", "manifest")
    if termination_reason == "requested_ticks_reached":
        if _is_int(final_tick) and _is_int(requested_ticks) and final_tick != requested_ticks:
            _add(issues, "wrong_final_tick", "requested horizon was not reached", "manifest")
    elif termination_reason == "extinction":
        if "extinction" not in policy.registered_natural_terminals:
            _add(issues, "unregistered_natural_terminal", "extinction is not registered", "manifest")
        if _is_int(final_tick) and _is_int(requested_ticks) and final_tick >= requested_ticks:
            _add(issues, "invalid_extinction_terminal", "extinction must end before requested ticks", "manifest")
    else:
        _add(issues, "invalid_termination_reason", f"{termination_reason!r} is not accepted", "manifest")

    config = manifest.get("configuration")
    canonical_disabled: tuple[str, ...] | None = None
    if not _is_dict(config):
        _add(issues, "invalid_configuration", "configuration must be an object", "manifest")
    else:
        config_ticks = config.get("ticks")
        if not _is_int(config_ticks):
            _add(issues, "invalid_configuration", "configuration ticks must be an integer", "manifest")
        elif not _exact_equal(config_ticks, requested_ticks):
            _add(issues, "configuration_ticks_mismatch", "configuration ticks differ", "manifest")
        config_condition = config.get("condition")
        if not _is_str(config_condition):
            _add(issues, "invalid_configuration", "configuration condition must be text", "manifest")
        elif config_condition != condition:
            _add(issues, "configuration_condition_mismatch", "configuration condition differs", "manifest")
        config_log_mode = config.get("log_mode")
        manifest_log_mode = manifest.get("log_mode")
        if not _is_str(manifest_log_mode) or manifest_log_mode not in VALID_LOG_MODES:
            _add(issues, "invalid_configuration", "manifest log mode is invalid", "manifest")
        if not _is_str(config_log_mode):
            _add(issues, "invalid_configuration", "configuration log mode must be text", "manifest")
        elif not _exact_equal(config_log_mode, manifest_log_mode):
            _add(issues, "configuration_log_mode_mismatch", "configuration log mode differs", "manifest")
        if _is_str(config_log_mode) and config_log_mode not in VALID_LOG_MODES:
            _add(issues, "invalid_configuration", "unknown log mode", "manifest")
        if not _is_bool(config.get("anti_stagnation_enabled")):
            _add(issues, "invalid_configuration", "anti-stagnation setting must be boolean", "manifest")
        disabled = config.get("disabled_layers")
        if not _is_list(disabled):
            _add(issues, "invalid_configuration", "disabled layers must be a list", "manifest")
        elif any(not _is_str(item) or not item for item in disabled):
            _add(issues, "invalid_configuration", "disabled-layer entries must be nonempty text", "manifest")
        elif len(disabled) != len(set(disabled)):
            _add(issues, "invalid_configuration", "disabled layers must not contain duplicates", "manifest")
        elif disabled != sorted(disabled):
            _add(issues, "invalid_configuration", "disabled layers must use canonical order", "manifest")
        elif set(disabled) - VALID_DISABLE_LAYERS:
            _add(issues, "invalid_configuration", "disabled layers contain unknown values", "manifest")
        else:
            canonical_disabled = tuple(disabled)
        raids_enabled = config.get("raids_enabled")
        if not _is_bool(raids_enabled):
            _add(issues, "invalid_configuration", "raid policy must be boolean", "manifest")
        elif canonical_disabled is not None and raids_enabled is not (
            "raids" not in canonical_disabled
        ):
            _add(issues, "invalid_configuration", "raid policy conflicts with disabled layers", "manifest")
        _validate_social_configuration(config, issues)
        _validate_language_configuration(config, issues)
        _validate_coalition_configuration(config, issues)
        _validate_dialect_configuration(config, issues)
        _validate_language_contact_configuration(config, issues)
        _validate_intergenerational_language_configuration(config, issues)
        _validate_lexical_evolution_configuration(config, issues)
        _validate_compositional_protolanguage_configuration(config, issues)
        _validate_grammar_evolution_configuration(config, issues)
        _validate_language_coevolution_configuration(config, issues)
        _validate_coalition_intelligibility_configuration(config, issues)
        _validate_production_trial_configuration(config, issues)
    execution_mode = manifest.get("execution_mode")
    if not _is_str(execution_mode) or execution_mode not in {"serial", "threaded"}:
        _add(issues, "invalid_execution_mode", repr(manifest.get("execution_mode")), "manifest")

    expected_versions = {
        "metrics": METRICS_SCHEMA_VERSION,
        "events": EVENT_SCHEMA_VERSION,
        "beliefs": BELIEFS_SCHEMA_VERSION,
        "summary": RUN_SUMMARY_SCHEMA_VERSION,
    }
    if not _exact_equal(manifest.get("artifact_schema_versions"), expected_versions):
        _add(issues, "artifact_schema_versions_mismatch", "unexpected schema versions", "manifest")
    if not _exact_equal(manifest.get("event_schema_version"), EVENT_SCHEMA_VERSION):
        _add(issues, "event_schema_version_mismatch", "unexpected event schema", "manifest")
    if not _exact_equal(manifest.get("metrics_timing_contract"), METRICS_TIMING_CONTRACT):
        _add(issues, "metrics_timing_contract_mismatch", "expected end_of_tick_v2", "manifest")
    if not _exact_equal(manifest.get("state_hash_algorithm"), "sha256"):
        _add(issues, "state_hash_algorithm_mismatch", "expected sha256", "manifest")
    if not _exact_equal(manifest.get("required_outputs"), [
        "metrics", "events", "beliefs", "run_summary", "run_manifest",
    ]):
        _add(issues, "required_outputs_mismatch", "unexpected required artifact policy", "manifest")
    diagnostics = manifest.get("finalization_diagnostics")
    if _is_list(diagnostics) and not all(_is_str(item) for item in diagnostics):
        _add(issues, "invalid_finalization_diagnostics", "diagnostics must be text", "manifest")

    _validate_writer_health(manifest, issues)
    allow_zero, belief_interval, _cardinality = _resolve_artifact_policy(
        manifest, policy, issues)
    stats, _summary = _strict_artifacts(
        paths=paths,
        data_root=data_root,
        condition=condition,
        seed=seed,
        final_tick=final_tick,
        termination_reason=termination_reason,
        allow_zero_events=allow_zero,
        belief_interval=belief_interval,
        issues=issues,
        notices=notices,
    )
    _validate_inventory(manifest, paths=paths, stats=stats, issues=issues)
    readiness = _readiness_issues(manifest, expected_contract)
    valid = not issues
    v2_ready = valid and not readiness
    return ValidationReport(
        valid=valid,
        v2_ready=v2_ready,
        classification=("v2_ready" if v2_ready else "schema2_valid") if valid else "invalid",
        issues=issues.materialize(),
        notices=notices,
        readiness_issues=readiness,
        manifest=manifest,
    )


def inspect_run_outputs(
    run_dir: Path,
    condition: str,
    seed: int,
    *,
    expected_ticks: int | None = None,
    mode: ValidationMode = "auto",
    policy: ValidationPolicy | None = None,
    expected_contract: ExpectedRunContract | None = None,
) -> ValidationReport:
    """Validate one run and separately evaluate external V2 readiness."""
    if mode not in {"strict", "auto", "legacy"}:
        raise ValueError(f"unknown validation mode: {mode}")
    policy = policy or ValidationPolicy()
    issues = _IssueCollector()
    notices: list[ValidationNotice] = []
    paths, data_root = _safe_layout(run_dir, condition, seed, issues)
    if paths is None or data_root is None:
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices)
    manifest = _read_manifest(paths["manifest"], data_root=data_root, issues=issues)
    if manifest is None:
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices)

    schema_version = manifest.get("schema_version")
    if not _is_int(schema_version):
        _add(
            issues,
            "invalid_manifest_schema_type",
            f"schema_version must be an integer, found {schema_version!r}",
            "manifest",
        )
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices,
            manifest=manifest)
    if mode == "strict" and schema_version != RUN_MANIFEST_SCHEMA_VERSION:
        code = (
            "legacy_manifest_not_v2_ready"
            if schema_version == 1
            else "unsupported_manifest_schema"
        )
        _add(
            issues,
            code,
            f"strict mode requires schema {RUN_MANIFEST_SCHEMA_VERSION}, "
            f"found {schema_version!r}",
            "manifest",
        )
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices,
            manifest=manifest)
    if mode == "legacy" and schema_version != 1:
        _add(issues, "not_legacy_manifest", f"legacy mode requires schema 1, found {schema_version!r}", "manifest")
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices,
            manifest=manifest)
    if mode == "auto" and schema_version not in {1, RUN_MANIFEST_SCHEMA_VERSION}:
        _add(issues, "unsupported_manifest_schema", f"found {schema_version!r}", "manifest")
        return ValidationReport(
            False, False, "invalid", issues.materialize(), notices,
            manifest=manifest)
    if schema_version == 1:
        return _validate_legacy(
            run_dir, condition, seed, manifest, paths, data_root, issues, notices)
    return _validate_strict(
        run_dir,
        condition,
        seed,
        expected_ticks,
        manifest,
        paths,
        data_root,
        policy,
        expected_contract,
        issues,
        notices,
    )
