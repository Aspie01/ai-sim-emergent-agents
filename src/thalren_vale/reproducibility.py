"""Canonical simulation fingerprints and run manifests."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from .artifact_contract import (
    ALLOW_ZERO_EVENTS,
    BELIEFS_SCHEMA_VERSION,
    BELIEF_SNAPSHOT_CARDINALITY,
    BELIEF_SNAPSHOT_INTERVAL,
    EvidencePathError,
    METRICS_SCHEMA_VERSION,
    METRICS_TIMING_CONTRACT,
    RUN_MANIFEST_SCHEMA_VERSION,
    RUN_SUMMARY_SCHEMA_VERSION,
    lexical_absolute,
    require_contained_regular_file,
    require_real_directory,
    require_safe_manifest_target,
)
from .events import EVENT_SCHEMA_VERSION
from .config import LanguageEvolutionConfig
from .social import relationship_records
from .coalitions import (
    CoalitionRuntimeState,
    canonical_candidate_snapshot,
    canonical_coalition_snapshot,
)
from .language import (
    AgentLanguageState,
    LanguageInvariantError,
    LanguageRuntimeState,
    agent_language_record,
    language_runtime_is_pristine,
    language_runtime_record,
    validate_language_config,
)


def _person_record(
    person,
    *,
    include_social: bool = False,
    include_language: bool = False,
    language_config=None,
) -> dict:
    religion = getattr(person, "religion", None)
    record = {
        "name": person.name,
        "position": [person.r, person.c],
        "health": person.health,
        "hunger": person.hunger,
        "inventory": dict(person.inventory),
        "beliefs": sorted(person.beliefs),
        "trust": dict(person.trust),
        "faction": person.faction,
        "currency": person.currency,
        "generation": person.generation,
        "religion": getattr(religion, "name", None),
        "is_priest": person.is_priest,
    }
    if include_social or include_language:
        inhabitant_id = getattr(person, "inhabitant_id", None)
        if type(inhabitant_id) is not int or inhabitant_id < 0:
            raise ValueError(
                "enabled social state requires assigned inhabitant IDs")
        record["inhabitant_id"] = inhabitant_id
    if include_social:
        record["relationships"] = relationship_records(person)
    if include_language:
        if language_config is None:
            raise ValueError("enabled language hashing requires effective controls")
        language = agent_language_record(person, config=language_config)
        record["language"] = {
            key: value
            for key, value in language.items()
            if key != "inhabitant_id"
        }
    return record


def _faction_record(faction) -> dict:
    settlement = getattr(faction, "settlement", None)
    return {
        "name": faction.name,
        "members": sorted(member.name for member in faction.members),
        "shared_beliefs": sorted(faction.shared_beliefs),
        "territory": sorted([list(tile) for tile in faction.territory]),
        "founded_tick": faction.founded_tick,
        "food_reserve": faction.food_reserve,
        "legends": sorted(str(legend) for legend in faction.legends),
        "is_settled": faction.is_settled,
        "settled_since": faction.settled_since,
        "settled_ticks": faction.settled_ticks,
        "settlement": (
            {
                "owner_faction": settlement.owner_faction,
                "position": [getattr(settlement, "r", None),
                             getattr(settlement, "c", None)],
                "founded_tick": settlement.founded_tick,
                "status": settlement.status,
                "storage_buffer": settlement.storage_buffer,
                "housing_capacity": settlement.housing_capacity,
            }
            if settlement is not None else None
        ),
        "techs": sorted(getattr(faction, "techs", set())),
        "researching": getattr(faction, "researching", None),
        "research_progress": getattr(faction, "research_progress", None),
    }


def _war_record(war) -> dict:
    return {
        "attacker": war.attacker.name,
        "defender": war.defender.name,
        "cause": war.cause,
        "started_tick": war.started_tick,
        "tick_count": war.tick_count,
        "allied_with_attacker": sorted(f.name for f in war.allied_with_a),
        "allied_with_defender": sorted(f.name for f in war.allied_with_d),
        "ended": war.ended,
        "outcome": war.outcome,
        "tribute_remaining": war.tribute_remaining,
    }


def _mapping_records(mapping: dict) -> list:
    """Represent mappings with non-string keys in deterministic order."""
    records = []
    for key, value in mapping.items():
        if isinstance(key, (set, frozenset, tuple)):
            normalized_key = sorted(key)
        else:
            normalized_key = key
        records.append({"key": normalized_key, "value": value})
    return sorted(records, key=lambda record: json.dumps(record["key"], sort_keys=True))


def _json_safe(value):
    """Convert supported state values into deterministic JSON primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [_json_safe(item) for item in value]
        return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, Path):
        return str(value)
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return {"object_type": type(value).__name__, "name": name}
    raise TypeError(f"unsupported canonical state value: {type(value).__name__}")


def _require_empty_disabled_relationships(state) -> None:
    """Reject social state that the historical disabled hash would omit."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            relationships = getattr(inhabitant, "relationships", {})
            if not relationships:
                continue
            name = getattr(inhabitant, "name", None)
            inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
            raise ValueError(
                "disabled social memory requires empty relationships: "
                f"{cohort}[{index}] name={name!r} "
                f"inhabitant_id={inhabitant_id!r} has "
                f"{len(relationships)} relationship(s)"
            )


def _require_empty_disabled_coalition_state(state) -> None:
    """Reject coalition state omitted from the coalition-disabled hash."""
    runtime = getattr(state, "coalitions", None)
    if runtime is None:
        return
    if not isinstance(runtime, CoalitionRuntimeState):
        raise ValueError("disabled coalition state has an invalid runtime type")
    unexpected = {
        "candidates": bool(runtime.candidates),
        "active_coalitions": bool(runtime.active_coalitions),
        "member_to_coalition": bool(runtime.member_to_coalition),
        "next_coalition_id": runtime.next_coalition_id != 0,
        "candidate_formation_count": runtime.candidate_formation_count != 0,
        "split_event_count": runtime.split_event_count != 0,
        "split_child_count": runtime.split_child_count != 0,
        "dissolution_count": runtime.dissolution_count != 0,
        "last_observation_tick": runtime.last_observation_tick is not None,
        "last_active_inhabitant_ids": bool(runtime.last_active_inhabitant_ids),
        "last_qualifying_reciprocal_edge_count": (
            runtime.last_qualifying_reciprocal_edge_count != 0
        ),
    }
    populated = sorted(name for name, present in unexpected.items() if present)
    if populated:
        raise ValueError(
            "disabled coalition emergence requires pristine coalition state: "
            + ", ".join(populated)
        )


def _require_pristine_disabled_language_state(state) -> None:
    """Reject every language field omitted from the disabled behavioral hash."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled language requires explicit pristine agent state: "
                    f"{cohort}[{index}] is missing AgentLanguageState",
                )
            if (
                language.production
                or language.comprehension
                or language.next_invention_index != 0
                or type(language.next_invention_index) is not int
            ):
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_agent_language_state",
                    "disabled language evolution requires pristine agent state: "
                    f"{cohort}[{index}] inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "language", None)
    if type(runtime) is not LanguageRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_language_runtime",
            "disabled language runtime is missing or invalid",
        )
    if not language_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_language_runtime",
            "disabled language evolution requires pristine runtime state",
        )


def _coalition_state_record(runtime: CoalitionRuntimeState) -> dict:
    """Return the complete coalition runtime in canonical JSON-safe form."""
    return {
        "candidates": canonical_candidate_snapshot(runtime),
        "active_coalitions": canonical_coalition_snapshot(runtime),
        "member_to_coalition": [
            {"inhabitant_id": inhabitant_id, "coalition_id": coalition_id}
            for inhabitant_id, coalition_id in sorted(
                runtime.member_to_coalition.items())
        ],
        "next_coalition_id": runtime.next_coalition_id,
        "candidate_formation_count": runtime.candidate_formation_count,
        "split_event_count": runtime.split_event_count,
        "split_child_count": runtime.split_child_count,
        "dissolution_count": runtime.dissolution_count,
        "last_observation_tick": runtime.last_observation_tick,
        "last_active_inhabitant_ids": list(runtime.last_active_inhabitant_ids),
        "last_qualifying_reciprocal_edge_count": (
            runtime.last_qualifying_reciprocal_edge_count
        ),
    }


def _language_hash_config(configuration: dict) -> LanguageEvolutionConfig:
    """Build the exact effective language controls required by state records."""
    required = (
        "language_evolution_enabled",
        "maximum_language_associations",
        "maximum_signal_length",
        "language_learning_rate",
        "language_reinforcement_rate",
        "language_forgetting_interval",
        "language_invention_enabled",
        "language_controls_status",
        "language_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled language hashing lacks controls: " + ", ".join(missing))
    if configuration["language_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled language hashing requires engineering-only status")
    if (
        type(configuration["language_control_notices"]) is not list
        or configuration["language_control_notices"]
    ):
        raise ValueError(
            "enabled language hashing requires exact empty language notices")
    result = LanguageEvolutionConfig(
        language_evolution_enabled=configuration["language_evolution_enabled"],
        maximum_language_associations=configuration[
            "maximum_language_associations"],
        maximum_signal_length=configuration["maximum_signal_length"],
        language_learning_rate=configuration["language_learning_rate"],
        language_reinforcement_rate=configuration[
            "language_reinforcement_rate"],
        language_forgetting_interval=configuration[
            "language_forgetting_interval"],
        language_invention_enabled=configuration[
            "language_invention_enabled"],
    )
    validate_language_config(result, require_enabled=True)
    return result


def canonical_state_hash(state, world: list, configuration: dict) -> str:
    """Return a SHA-256 fingerprint of behaviorally relevant final state."""
    social_memory_enabled = configuration.get("social_memory_enabled") is True
    coalition_emergence_enabled = (
        configuration.get("coalition_emergence_enabled") is True
    )
    if (
        "language_evolution_enabled" in configuration
        and type(configuration["language_evolution_enabled"]) is not bool
    ):
        raise ValueError("language evolution configuration must be boolean")
    language_evolution_enabled = configuration.get(
        "language_evolution_enabled", False)
    non_behavioral_keys = {
        "condition",
        "log_mode",
        "social_controls_status",
        "social_control_notices",
    }
    if not social_memory_enabled:
        _require_empty_disabled_relationships(state)
        # The disabled feature is a direct historical baseline. Run IDs,
        # allocator state, and all social controls/state are intentionally
        # absent from the behavioral payload so frozen hashes stay unchanged.
        non_behavioral_keys.update({
            "social_memory_enabled",
            "social_partner_bias_enabled",
            "maximum_social_ties",
            "relationship_decay_interval",
        })
    language_configuration_keys = {
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
    if not language_evolution_enabled:
        _require_pristine_disabled_language_state(state)
        non_behavioral_keys.update(language_configuration_keys)
    coalition_configuration_keys = {
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
    if not coalition_emergence_enabled:
        _require_empty_disabled_coalition_state(state)
        non_behavioral_keys.update(coalition_configuration_keys)
    elif not social_memory_enabled:
        raise ValueError("enabled coalition emergence requires social memory")
    behavior_configuration = {
        key: value
        for key, value in configuration.items()
        if key not in non_behavioral_keys
    }
    language_hash_config = (
        _language_hash_config(configuration)
        if language_evolution_enabled else None
    )
    people_records = [
        _person_record(
            person,
            include_social=social_memory_enabled,
            include_language=language_evolution_enabled,
            language_config=language_hash_config,
        )
        for person in state.people
    ]
    dead_records = [
        _person_record(
            person,
            include_social=social_memory_enabled,
            include_language=language_evolution_enabled,
            language_config=language_hash_config,
        )
        for person in state.all_dead
    ]
    identity_enabled = social_memory_enabled or language_evolution_enabled
    if language_evolution_enabled:
        identities = [
            record["inhabitant_id"]
            for record in (*people_records, *dead_records)
        ]
        if len(identities) != len(set(identities)):
            raise LanguageInvariantError(
                "duplicate_language_identity",
                "enabled language hashing requires unique inhabitant IDs",
            )
    person_sort_key = (
        (lambda record: record["inhabitant_id"])
        if identity_enabled
        else (lambda record: record["name"])
    )
    payload = {
        "configuration": behavior_configuration,
        "people": sorted(people_records, key=person_sort_key),
        "dead": sorted(dead_records, key=person_sort_key),
        "factions": sorted((_faction_record(f) for f in state.factions),
                           key=lambda record: record["name"]),
        "active_wars": sorted((_war_record(w) for w in state.active_wars),
                              key=lambda record: (record["started_tick"],
                                                  record["attacker"],
                                                  record["defender"])),
        "war_history": sorted((_war_record(w) for w in state.war_history),
                              key=lambda record: (record["started_tick"],
                                                  record["attacker"],
                                                  record["defender"])),
        "rivalries": _mapping_records(state.rivalries),
        "treaties": _mapping_records(state.treaties),
        "reputation": state.reputation,
        "trade_routes": _mapping_records(state.trade_routes),
        "world": [
            [
                {
                    "biome": tile["biome"],
                    "habitable": tile["habitable"],
                    "resources": tile["resources"],
                }
                for tile in row
            ]
            for row in world
        ],
    }
    if identity_enabled:
        next_inhabitant_id = getattr(state, "next_inhabitant_id", None)
        if type(next_inhabitant_id) is not int or next_inhabitant_id < 0:
            raise ValueError(
                "enabled social state requires a nonnegative ID allocator")
        payload["next_inhabitant_id"] = next_inhabitant_id
    if language_evolution_enabled:
        runtime = getattr(state, "language", None)
        if type(runtime) is not LanguageRuntimeState:
            raise ValueError("enabled language state requires a valid runtime")
        payload["language_state"] = language_runtime_record(runtime)
    if coalition_emergence_enabled:
        runtime = getattr(state, "coalitions", None)
        if not isinstance(runtime, CoalitionRuntimeState):
            raise ValueError("enabled coalition state requires a valid runtime")
        payload["coalition_state"] = _coalition_state_record(runtime)
    encoded = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _code_revision() -> dict:
    project_root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip())
        return {"commit": revision, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def _artifact_inventory_entry(
    path: Path,
    schema_version: int,
    *,
    data_root: Path,
) -> dict:
    """Return a streaming checksum and CSV row count for one sealed artifact."""
    path = require_contained_regular_file(path, data_root)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, strict=True)
        next(reader)
        data_rows = sum(1 for _row in reader)

    return {
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "data_rows": data_rows,
        "schema_version": schema_version,
    }


def build_artifact_inventory(
    output_dir: str,
    *,
    seed: int,
    condition: str,
) -> tuple[dict[str, dict], list[str]]:
    """Inventory only required structured artifacts, preserving any errors."""
    root = lexical_absolute(Path(output_dir))
    try:
        root = require_real_directory(root)
    except EvidencePathError as exc:
        return {}, [f"data_root: EvidencePathError: {exc}"]
    artifacts = {
        "metrics": (
            root / f"metrics_{condition}_seed_{seed}.csv",
            METRICS_SCHEMA_VERSION,
        ),
        "events": (
            root / f"faction_events_{condition}_seed_{seed}.csv",
            EVENT_SCHEMA_VERSION,
        ),
        "beliefs": (
            root / f"beliefs_{condition}_seed_{seed}.csv",
            BELIEFS_SCHEMA_VERSION,
        ),
        "summary": (root / "run_summaries.csv", RUN_SUMMARY_SCHEMA_VERSION),
    }
    inventory: dict[str, dict] = {}
    errors: list[str] = []
    for label, (path, schema_version) in artifacts.items():
        try:
            inventory[label] = _artifact_inventory_entry(
                path, schema_version, data_root=root)
        except (
            OSError, UnicodeError, csv.Error, StopIteration, EvidencePathError,
        ) as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    return inventory, errors


def write_run_manifest(
    output_dir: str,
    *,
    seed: int,
    condition: str,
    configuration: dict,
    state_hash: str,
    execution_mode: str,
    requested_ticks: int,
    final_tick: int,
    termination_reason: str,
    result_status: str,
    completed_normally: bool,
    writer_health: dict,
    artifact_policy: dict | None = None,
    finalization_diagnostics: list[str] | None = None,
    log_mode: str = "full",
    required_outputs: list[str] | None = None,
    optional_outputs: dict | None = None,
) -> Path:
    """Write machine-readable provenance for one simulation run."""
    root = lexical_absolute(Path(output_dir))
    if root.exists() or root.is_symlink():
        root = require_real_directory(root)
    else:
        require_real_directory(root.parent)
        root.mkdir()
        root = require_real_directory(root)
    path = require_safe_manifest_target(
        root / f"run_manifest_{condition}_seed_{seed}.json",
        root,
    )
    inventory, inventory_errors = build_artifact_inventory(
        output_dir, seed=seed, condition=condition)
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
        "seed": seed,
        "condition": condition,
        "requested_ticks": requested_ticks,
        "final_tick": final_tick,
        "completed_ticks": final_tick,
        "termination_reason": termination_reason,
        "result_status": result_status,
        "completed_normally": completed_normally,
        "configuration": configuration,
        "execution_mode": execution_mode,
        "log_mode": log_mode,
        "required_outputs": required_outputs or [
            "metrics",
            "events",
            "beliefs",
            "run_summary",
            "run_manifest",
        ],
        "optional_outputs": optional_outputs or {},
        "state_hash_algorithm": "sha256",
        "state_hash": state_hash,
        "writer_health": writer_health,
        "artifact_policy": artifact_policy or {
            "allow_zero_events": ALLOW_ZERO_EVENTS,
            "belief_snapshot_interval": BELIEF_SNAPSHOT_INTERVAL,
            "belief_snapshot_cardinality": BELIEF_SNAPSHOT_CARDINALITY,
        },
        "finalization_diagnostics": list(finalization_diagnostics or []),
        "artifact_inventory": inventory,
        "artifact_inventory_errors": inventory_errors,
        "code": _code_revision(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    require_safe_manifest_target(temporary, root)
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path
