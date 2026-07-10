#!/usr/bin/env python3
"""Run and summarize the bounded 2x2 combat x raids pilot."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median

from run_experiments import (
    expected_outputs,
    parse_seed_range,
    run_single,
    validate_run_outputs,
)


EXPERIMENT_ID = "raid-control-pilot-v1"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path("experiment_runs") / EXPERIMENT_ID
DEFAULT_TICKS = (100, 250)
DEFAULT_SEEDS = (1, 2, 3)
DEFAULT_TIMEOUT_SECONDS = 1200

CONDITIONS = (
    {
        "name": "combat_on_raids_on",
        "combat_enabled": True,
        "raids_enabled": True,
        "extra_args": [],
    },
    {
        "name": "combat_off_raids_on",
        "combat_enabled": False,
        "raids_enabled": True,
        "extra_args": ["--disable-layer", "combat"],
    },
    {
        "name": "combat_on_raids_off",
        "combat_enabled": True,
        "raids_enabled": False,
        "extra_args": ["--disable-raids"],
    },
    {
        "name": "combat_off_raids_off",
        "combat_enabled": False,
        "raids_enabled": False,
        "extra_args": ["--disable-layer", "combat", "--disable-raids"],
    },
)
CONDITION_BY_NAME = {condition["name"]: condition for condition in CONDITIONS}
CONDITION_ORDER = {
    condition["name"]: index for index, condition in enumerate(CONDITIONS)
}


def _int(value: object, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_ticks(value: str) -> tuple[int, ...]:
    ticks = tuple(dict.fromkeys(
        int(part.strip()) for part in value.split(",") if part.strip()
    ))
    if not ticks or any(tick < 1 for tick in ticks):
        raise argparse.ArgumentTypeError("ticks must be positive integers")
    return ticks


def _parse_conditions(value: str) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(
        part.strip() for part in value.split(",") if part.strip()
    ))
    unknown = set(names) - set(CONDITION_BY_NAME)
    if not names or unknown:
        valid = ", ".join(CONDITION_BY_NAME)
        invalid = ", ".join(sorted(unknown)) or "empty selection"
        raise argparse.ArgumentTypeError(
            f"unknown condition(s): {invalid}; valid conditions: {valid}"
        )
    return names


def _last_csv_row(path: Path) -> dict[str, str]:
    last: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if row:
                last = row
    return last


def _event_counts(path: Path) -> tuple[int, int]:
    total = 0
    raids = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            total += 1
            if row.get("event_type") == "raid":
                raids += 1
    return total, raids


def _directory_size(path: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        base = Path(dirpath)
        for filename in filenames:
            try:
                total += (base / filename).stat().st_size
            except OSError:
                pass
    return total


def collect_case(root: Path, ticks: int, condition_name: str, seed: int) -> dict:
    condition = CONDITION_BY_NAME[condition_name]
    run_dir = root / f"ticks_{ticks}" / condition_name / f"seed_{seed}"
    valid, errors = validate_run_outputs(run_dir, condition_name, seed)
    outputs = expected_outputs(run_dir, condition_name, seed)
    summary = (
        _last_csv_row(outputs["run_summary"])
        if outputs["run_summary"].is_file()
        else {}
    )
    manifest = {}
    if outputs["run_manifest"].is_file():
        try:
            manifest = json.loads(
                outputs["run_manifest"].read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            pass
    event_count, raid_count = (0, 0)
    if outputs["events"].is_file():
        event_count, raid_count = _event_counts(outputs["events"])
    elapsed = _float(summary.get("wall_clock_seconds"))
    code = manifest.get("code", {})
    configuration = manifest.get("configuration", {})

    return {
        "experiment_id": EXPERIMENT_ID,
        "condition": condition_name,
        "combat_enabled": condition["combat_enabled"],
        "raids_enabled": condition["raids_enabled"],
        "seed": seed,
        "ticks": ticks,
        "status": "completed" if valid else "invalid_output",
        "validation_errors": "; ".join(errors),
        "log_mode": manifest.get("log_mode", ""),
        "elapsed_seconds": elapsed,
        "ticks_per_second": round(ticks / elapsed, 6) if elapsed else "",
        "output_bytes": _directory_size(run_dir) if run_dir.is_dir() else 0,
        "structured_event_count": event_count,
        "raid_event_count": raid_count,
        "raid_event_share": round(raid_count / event_count, 8)
        if event_count
        else 0.0,
        "final_population": _int(summary.get("final_population")),
        "peak_population": _int(summary.get("peak_population")),
        "final_factions": _int(summary.get("final_faction_count")),
        "peak_factions": _int(summary.get("peak_faction_count")),
        "total_wars": _int(summary.get("total_wars")),
        "total_deaths": _int(summary.get("total_deaths")),
        "total_births": _int(summary.get("total_births")),
        "peak_ram_mb": _float(summary.get("peak_ram_mb")),
        "final_state_hash": manifest.get("state_hash", ""),
        "manifest_raids_enabled": configuration.get("raids_enabled", ""),
        "disabled_layers": ";".join(configuration.get("disabled_layers", [])),
        "code_commit": code.get("commit", ""),
        "code_dirty": code.get("dirty", ""),
        "run_dir": str(run_dir),
    }


def _row_key(row: dict) -> tuple[int, str, int]:
    return (
        _int(row.get("ticks")),
        str(row.get("condition", "")),
        _int(row.get("seed")),
    )


def _sort_key(row: dict) -> tuple[int, int, int]:
    return (
        _int(row.get("ticks")),
        CONDITION_ORDER.get(str(row.get("condition", "")), 999),
        _int(row.get("seed")),
    )


def collect_existing(root: Path) -> list[dict]:
    rows = []
    for ticks_dir in sorted(root.glob("ticks_*")):
        try:
            ticks = int(ticks_dir.name.removeprefix("ticks_"))
        except ValueError:
            continue
        for condition in CONDITIONS:
            condition_dir = ticks_dir / condition["name"]
            for seed_dir in sorted(condition_dir.glob("seed_*")):
                try:
                    seed = int(seed_dir.name.removeprefix("seed_"))
                except ValueError:
                    continue
                rows.append(collect_case(root, ticks, condition["name"], seed))
    return sorted(rows, key=_sort_key)


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(_int(row["ticks"]), str(row["condition"]))].append(row)

    summary_rows = []
    for (ticks, condition_name), group in sorted(
        groups.items(),
        key=lambda item: (item[0][0], CONDITION_ORDER.get(item[0][1], 999)),
    ):
        completed = [row for row in group if row["status"] == "completed"]
        condition = CONDITION_BY_NAME[condition_name]
        elapsed = [_float(row["elapsed_seconds"]) for row in completed]
        events = [_int(row["structured_event_count"]) for row in completed]
        raids = [_int(row["raid_event_count"]) for row in completed]

        def mean(field: str) -> float:
            values = [_float(row[field]) for row in completed]
            return round(fmean(values), 6) if values else 0.0

        summary_rows.append({
            "experiment_id": EXPERIMENT_ID,
            "condition": condition_name,
            "combat_enabled": condition["combat_enabled"],
            "raids_enabled": condition["raids_enabled"],
            "ticks": ticks,
            "requested_runs": len(group),
            "completed_runs": len(completed),
            "mean_elapsed_seconds": round(fmean(elapsed), 6) if elapsed else 0.0,
            "median_elapsed_seconds": round(median(elapsed), 6) if elapsed else 0.0,
            "aggregate_ticks_per_second": round(
                ticks * len(completed) / sum(elapsed), 6
            ) if elapsed and sum(elapsed) else 0.0,
            "mean_output_bytes": round(mean("output_bytes"), 3),
            "mean_structured_events": round(fmean(events), 3) if events else 0.0,
            "mean_raid_events": round(fmean(raids), 3) if raids else 0.0,
            "aggregate_raid_share": round(
                sum(raids) / sum(events), 8
            ) if events and sum(events) else 0.0,
            "mean_final_population": mean("final_population"),
            "mean_peak_population": mean("peak_population"),
            "mean_final_factions": mean("final_factions"),
            "mean_peak_factions": mean("peak_factions"),
            "mean_total_wars": mean("total_wars"),
            "mean_total_deaths": mean("total_deaths"),
            "mean_peak_ram_mb": mean("peak_ram_mb"),
        })
    return summary_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_outputs(root: Path, rows: list[dict]) -> None:
    ordered = sorted(rows, key=_sort_key)
    write_csv(root / "results.csv", ordered)
    write_csv(root / "summary.csv", summarize(ordered))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--ticks", type=_parse_ticks, default=DEFAULT_TICKS)
    parser.add_argument("--seeds", default="1-3")
    parser.add_argument(
        "--conditions",
        type=_parse_conditions,
        default=tuple(CONDITION_BY_NAME),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-cell timeout; default 1200 seconds",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--collect-existing",
        action="store_true",
        help="Regenerate CSVs from existing cells without simulations",
    )
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        seeds = tuple(parse_seed_range(args.seeds))
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))

    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()) and not (
        args.resume or args.collect_existing
    ):
        parser.error(f"{root} is not empty; use --resume")
    root.mkdir(parents=True, exist_ok=True)

    existing = collect_existing(root)
    rows_by_key = {_row_key(row): row for row in existing}
    if args.collect_existing:
        if not rows_by_key:
            parser.error(f"no existing run cells found under {root}")
        _write_outputs(root, list(rows_by_key.values()))
        print(f"Collected {len(rows_by_key)} existing cells under {root}")
        return 0 if all(
            row["status"] == "completed" for row in rows_by_key.values()
        ) else 1

    requested_keys = []
    for ticks in args.ticks:
        tick_root = root / f"ticks_{ticks}"
        for condition_name in args.conditions:
            condition = CONDITION_BY_NAME[condition_name]
            extra_args = [*condition["extra_args"], "--log-mode", "metrics_only"]
            for seed in seeds:
                key = (ticks, condition_name, seed)
                requested_keys.append(key)
                run_single(
                    seed,
                    condition_name,
                    ticks,
                    extra_args,
                    tick_root,
                    resume=args.resume,
                    timeout_seconds=args.timeout_seconds,
                )
                rows_by_key[key] = collect_case(
                    root, ticks, condition_name, seed
                )
                _write_outputs(root, list(rows_by_key.values()))

    print(f"Wrote {len(rows_by_key)} pilot rows under {root}")
    return 0 if all(
        rows_by_key[key]["status"] == "completed" for key in requested_keys
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
