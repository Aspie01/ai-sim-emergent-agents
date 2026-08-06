"""Versioned structured-artifact contracts for simulation evidence."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

RUN_MANIFEST_SCHEMA_VERSION = 2
METRICS_SCHEMA_VERSION = 2
BELIEFS_SCHEMA_VERSION = 1
RUN_SUMMARY_SCHEMA_VERSION = 1
METRICS_TIMING_CONTRACT = "end_of_tick_v2"
BELIEF_SNAPSHOT_INTERVAL = 100
BELIEF_SNAPSHOT_CARDINALITY = "one_row_per_living_inhabitant"
ALLOW_ZERO_EVENTS = True

TECHNOLOGY_IDENTIFIERS = frozenset({
    "tools", "farming", "sailing", "mining", "engineering", "currency",
    "scavenging", "metalwork", "weaponry", "masonry", "steel",
    "oral_tradition", "medicine", "writing", "code_of_laws",
})

SEASON_NON_WINTER = 0
SEASON_WINTER = 1
METRICS_SEASON_VALUES = frozenset({SEASON_NON_WINTER, SEASON_WINTER})

METRICS_HEADER = (
    "seed", "tick", "population", "faction_count", "war_count",
    "total_wars_declared", "total_deaths", "total_births",
    "gini", "mean_trust", "mean_food", "total_techs",
    "total_treaties", "max_generation", "mean_generation",
    "largest_faction_size", "smallest_faction_size",
    "total_schisms", "total_mergers", "peace_ticks",
    "mean_reputation", "reputation_variance", "grid_size", "season",
)

EVENTS_HEADER = (
    "event_schema_version", "seed", "tick", "event_type",
    "actor", "target", "detail",
)

BELIEFS_HEADER = (
    "seed", "tick", "inhabitant_id", "faction", "beliefs",
)

RUN_SUMMARY_HEADER = (
    "seed", "condition", "final_population", "peak_population",
    "min_population", "total_factions_formed", "final_faction_count",
    "peak_faction_count", "first_faction_tick", "total_wars",
    "total_deaths", "total_births", "total_schisms", "total_mergers",
    "mean_gini", "final_gini", "peak_gini", "total_unique_techs",
    "mean_tech_count_per_faction", "total_treaties_formed",
    "total_treaties_broken", "max_generation", "mean_war_duration",
    "stagnation_events", "era_count", "wall_clock_seconds", "peak_ram_mb",
)

METRICS_INTEGER_FIELDS = frozenset({
    "seed", "tick", "population", "faction_count", "war_count",
    "total_wars_declared", "total_deaths", "total_births", "total_techs",
    "total_treaties", "max_generation", "largest_faction_size",
    "smallest_faction_size", "total_schisms", "total_mergers",
    "peace_ticks", "grid_size", "season",
})
METRICS_FLOAT_FIELDS = frozenset({
    "gini", "mean_trust", "mean_food", "mean_generation",
    "mean_reputation", "reputation_variance",
})
METRICS_NONNEGATIVE_INTEGER_FIELDS = METRICS_INTEGER_FIELDS - {"seed"}
METRICS_NONNEGATIVE_FLOAT_FIELDS = frozenset({
    "mean_food", "mean_generation", "reputation_variance",
})
METRICS_UNIT_INTERVAL_FIELDS = frozenset({"gini"})
METRICS_CUMULATIVE_FIELDS = (
    "total_wars_declared", "total_deaths", "total_births",
    "total_schisms", "total_mergers",
)

SUMMARY_INTEGER_FIELDS = frozenset({
    "seed", "final_population", "peak_population", "min_population",
    "total_factions_formed", "final_faction_count", "peak_faction_count",
    "first_faction_tick", "total_wars", "total_deaths", "total_births",
    "total_schisms", "total_mergers", "total_unique_techs",
    "total_treaties_formed", "total_treaties_broken", "max_generation",
    "stagnation_events", "era_count",
})
SUMMARY_FLOAT_FIELDS = frozenset({
    "mean_gini", "final_gini", "peak_gini",
    "mean_tech_count_per_faction", "mean_war_duration",
    "wall_clock_seconds", "peak_ram_mb",
})
SUMMARY_NONNEGATIVE_INTEGER_FIELDS = SUMMARY_INTEGER_FIELDS - {"seed"}
SUMMARY_NONNEGATIVE_FLOAT_FIELDS = SUMMARY_FLOAT_FIELDS
SUMMARY_UNIT_INTERVAL_FIELDS = frozenset({
    "mean_gini", "final_gini", "peak_gini",
})

METRICS_EVENT_COUNT_FIELDS = {
    "total_wars_declared": "war_declared",
    "total_deaths": "death",
    "total_births": "birth",
    "total_schisms": "schism",
    "total_mergers": "merger",
}
SUMMARY_EVENT_COUNT_FIELDS = {
    "total_factions_formed": "faction_formed",
    "total_wars": "war_declared",
    "total_deaths": "death",
    "total_births": "birth",
    "total_schisms": "schism",
    "total_mergers": "merger",
    "total_treaties_formed": "treaty_signed",
    "total_treaties_broken": "treaty_broken",
    "stagnation_events": "stagnation_trigger",
    "era_count": "era_shift",
}


class EvidencePathError(ValueError):
    """Raised when required evidence does not use a contained regular path."""


def lexical_absolute(path: Path) -> Path:
    """Return an absolute path without following symlinks."""
    return Path(os.path.abspath(os.fspath(path)))


def _components(path: Path) -> list[Path]:
    absolute = lexical_absolute(path)
    parts = absolute.parts
    current = Path(parts[0])
    result = [current]
    for part in parts[1:]:
        current /= part
        result.append(current)
    return result


def require_real_directory(path: Path) -> Path:
    """Require an existing directory with no symlink in its lexical path."""
    absolute = lexical_absolute(path)
    for component in _components(absolute):
        try:
            mode = os.lstat(component).st_mode
        except OSError as exc:
            raise EvidencePathError(
                f"cannot inspect directory component {component}: {exc}"
            ) from exc
        if stat.S_ISLNK(mode):
            raise EvidencePathError(f"symlinked path component: {component}")
    if not stat.S_ISDIR(os.lstat(absolute).st_mode):
        raise EvidencePathError(f"not an ordinary directory: {absolute}")
    return absolute


def require_contained_regular_file(path: Path, root: Path) -> Path:
    """Require a non-symlink regular file physically contained below root."""
    root_abs = require_real_directory(root)
    path_abs = lexical_absolute(path)
    try:
        common = Path(os.path.commonpath((root_abs, path_abs)))
    except ValueError as exc:
        raise EvidencePathError(f"path is outside evidence root: {path}") from exc
    if common != root_abs:
        raise EvidencePathError(f"path is outside evidence root: {path}")
    for component in _components(path_abs):
        if component == root_abs or root_abs not in component.parents:
            continue
        try:
            mode = os.lstat(component).st_mode
        except OSError as exc:
            raise EvidencePathError(
                f"cannot inspect evidence component {component}: {exc}"
            ) from exc
        if stat.S_ISLNK(mode):
            raise EvidencePathError(f"symlinked evidence component: {component}")
    mode = os.lstat(path_abs).st_mode
    if not stat.S_ISREG(mode):
        raise EvidencePathError(f"not an ordinary file: {path_abs}")
    resolved = Path(os.path.realpath(path_abs))
    resolved_root = Path(os.path.realpath(root_abs))
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise EvidencePathError(f"resolved path is outside evidence root: {path}")
    return path_abs


def require_safe_manifest_target(path: Path, data_root: Path) -> Path:
    """Require a contained non-symlink manifest target and safe parent path."""
    data_abs = require_real_directory(data_root)
    target = lexical_absolute(path)
    if target.parent != data_abs:
        raise EvidencePathError(f"manifest target is outside data root: {path}")
    if target.exists() or target.is_symlink():
        require_contained_regular_file(target, data_abs)
    return target


def validate_inventory_relative_path(value: object, expected_name: str) -> bool:
    """Return whether an inventory path is one exact safe basename."""
    if type(value) is not str or not value or value != expected_name:
        return False
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        return False
    if "/" in value or "\\" in value:
        return False
    return value not in {".", ".."}
