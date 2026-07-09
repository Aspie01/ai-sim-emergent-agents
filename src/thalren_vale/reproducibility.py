"""Canonical simulation fingerprints and run manifests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from .events import EVENT_SCHEMA_VERSION


def _person_record(person) -> dict:
    religion = getattr(person, "religion", None)
    return {
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


def canonical_state_hash(state, world: list, configuration: dict) -> str:
    """Return a SHA-256 fingerprint of behaviorally relevant final state."""
    non_behavioral_keys = {"condition", "log_mode"}
    behavior_configuration = {
        key: value
        for key, value in configuration.items()
        if key not in non_behavioral_keys
    }
    payload = {
        "configuration": behavior_configuration,
        "people": sorted((_person_record(p) for p in state.people),
                         key=lambda record: record["name"]),
        "dead": sorted((_person_record(p) for p in state.all_dead),
                       key=lambda record: record["name"]),
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


def write_run_manifest(
    output_dir: str,
    *,
    seed: int,
    condition: str,
    configuration: dict,
    state_hash: str,
    execution_mode: str,
    log_mode: str = "full",
    required_outputs: list[str] | None = None,
    optional_outputs: dict | None = None,
) -> Path:
    """Write machine-readable provenance for one simulation run."""
    path = Path(output_dir) / f"run_manifest_{condition}_seed_{seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "seed": seed,
        "condition": condition,
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
        "code": _code_revision(),
    }
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
