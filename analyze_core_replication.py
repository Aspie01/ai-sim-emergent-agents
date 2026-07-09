#!/usr/bin/env python3
"""Analyze nested Thalren Vale core-replication experiment outputs.

The core replication runner writes one directory per condition/seed:

    experiment_runs/<experiment_id>/<condition>/seed_<N>/

This script treats only final validated runs as research data.  It reads
run_index.csv, per-run manifests, run_summaries.csv, metrics CSVs, and event
CSVs, then emits compact analysis tables under
experiment_runs/<experiment_id>/analysis/ by default.

Large raw text logs are never loaded into memory.  Output sizes are measured by
walking the filesystem, and structured event counts are streamed row by row.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from run_experiments import (
    RESULT_COMPLETED,
    RESULT_SUPERSEDED,
    load_plan,
    parse_seed_range,
    validate_run_outputs,
)


BYTES_PER_MIB = 1024 * 1024
BYTES_PER_GIB = 1024 * 1024 * 1024

EVENT_COLUMNS = [
    "war_declared",
    "war_ended",
    "birth",
    "death",
    "faction_formed",
    "schism",
    "merger",
    "treaty_signed",
    "treaty_broken",
    "tech_researched",
    "settlement_founded",
    "era_shift",
    "stagnation_trigger",
    "raid",
    "world_event",
]

RUN_NUMERIC_FIELDS = [
    "elapsed_seconds",
    "final_population",
    "peak_population",
    "min_population",
    "final_faction_count",
    "peak_faction_count",
    "total_factions_formed",
    "total_wars",
    "total_deaths",
    "total_births",
    "total_schisms",
    "total_mergers",
    "total_treaties_formed",
    "total_treaties_broken",
    "stagnation_events",
    "era_count",
    "peak_ram_mb",
    "event_count",
    "output_gib",
    "raw_text_gib",
]

PAIR_METRICS = [
    "elapsed_seconds",
    "final_population",
    "peak_population",
    "final_faction_count",
    "peak_faction_count",
    "total_wars",
    "total_deaths",
    "total_schisms",
    "total_mergers",
    "event_count",
    "output_gib",
    "raw_text_gib",
    "peak_ram_mb",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _fmt_float(value: float) -> str:
    return f"{value:.6g}"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def _last_csv_row(path: Path) -> dict[str, str]:
    """Return the final non-empty CSV record without retaining all rows."""
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        last: dict[str, str] = {}
        for row in reader:
            if row:
                last = row
    return last


def _stream_event_counts(path: Path) -> Counter:
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event_type = row.get("event_type", "")
            if event_type:
                counts[event_type] += 1
    return counts


def _load_run_index(root: Path) -> dict[tuple[str, int], dict[str, str]]:
    path = root / "run_index.csv"
    if not path.is_file():
        return {}
    rows = _read_csv_rows(path)
    return {
        (row.get("condition", ""), _int(row.get("seed"))): row
        for row in rows
        if row.get("condition") and row.get("seed")
    }


def _file_inventory(run_dir: Path) -> tuple[dict[str, int], list[dict[str, object]]]:
    buckets: dict[str, int] = defaultdict(int)
    largest: list[dict[str, object]] = []

    for dirpath, _dirnames, filenames in os.walk(run_dir):
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue

            relative = path.relative_to(run_dir)
            parts = relative.parts
            buckets["output_bytes"] += size
            if parts and parts[0] == "data":
                buckets["data_bytes"] += size
            elif parts and parts[0] == "logs":
                buckets["full_log_bytes"] += size
                buckets["raw_text_bytes"] += size
            elif filename.startswith("manual_chronicle_"):
                buckets["manual_chronicle_bytes"] += size
                buckets["raw_text_bytes"] += size
            elif filename.startswith("era_export_"):
                buckets["era_export_bytes"] += size
                buckets["raw_text_bytes"] += size
            elif filename == "dashboard_data.json":
                buckets["dashboard_bytes"] += size
            elif filename.startswith("runner_"):
                buckets["runner_marker_bytes"] += size
            else:
                buckets["other_bytes"] += size

            largest.append({
                "path": str(path),
                "relative_path": str(relative),
                "bytes": size,
            })

    largest.sort(key=lambda row: int(row["bytes"]), reverse=True)
    return dict(buckets), largest


def _expected_run_paths(run_dir: Path, condition: str, seed: int) -> dict[str, Path]:
    data = run_dir / "data"
    suffix = f"{condition}_seed_{seed}"
    return {
        "metrics": data / f"metrics_{suffix}.csv",
        "events": data / f"faction_events_{suffix}.csv",
        "beliefs": data / f"beliefs_{suffix}.csv",
        "summary": data / "run_summaries.csv",
        "manifest": data / f"run_manifest_{suffix}.json",
    }


def _build_superseded_rows(
    root: Path,
    condition: str,
    seed: int,
    run_dir: Path,
    summary_rows: list[dict[str, str]],
    manifest_path: Path,
    final_valid: bool,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not final_valid:
        return rows

    try:
        manifest_mtime = manifest_path.stat().st_mtime
    except OSError:
        manifest_mtime = 0.0

    if len(summary_rows) > 1:
        rows.append({
            "condition": condition,
            "seed": seed,
            "result": RESULT_SUPERSEDED,
            "artifact": str((run_dir / "data" / "run_summaries.csv").relative_to(root)),
            "artifact_type": "summary_row",
            "bytes": "",
            "reason": (
                f"{len(summary_rows) - 1} earlier run_summaries.csv row(s) "
                "precede the final validated row"
            ),
            "dry_run_cleanup_action": (
                "do not delete file; if cleanup is approved, rewrite this CSV "
                "to keep only the header and final row after making a backup"
            ),
        })

    for marker in ("runner_stdout.txt", "runner_stderr.txt"):
        path = run_dir / marker
        if not path.is_file():
            continue
        try:
            marker_mtime = path.stat().st_mtime
            marker_size = path.stat().st_size
            snippet = path.read_text(encoding="utf-8", errors="replace")[:500]
        except OSError:
            continue
        if marker_mtime <= manifest_mtime:
            reason = "stale runner marker predates the final validated run manifest"
            if "timed out" in snippet or "timeout:" in snippet:
                reason = "stale wall_clock_limit marker from a superseded timeout attempt"
            rows.append({
                "condition": condition,
                "seed": seed,
                "result": RESULT_SUPERSEDED,
                "artifact": str(path.relative_to(root)),
                "artifact_type": "runner_marker",
                "bytes": marker_size,
                "reason": reason,
                "dry_run_cleanup_action": "delete file after final manifest is backed up",
            })

    log_files = sorted((run_dir / "logs").glob("*.txt"))
    if len(log_files) > 1:
        newest = max(log_files, key=lambda path: path.stat().st_mtime)
        for path in log_files:
            if path == newest:
                continue
            rows.append({
                "condition": condition,
                "seed": seed,
                "result": RESULT_SUPERSEDED,
                "artifact": str(path.relative_to(root)),
                "artifact_type": "text_log",
                "bytes": path.stat().st_size,
                "reason": "older log file for a condition/seed with a newer validated run",
                "dry_run_cleanup_action": "delete file after confirming it is not the final log",
            })

    return rows


def _write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _stats(values: list[float]) -> dict[str, str]:
    if not values:
        return {"mean": "", "median": "", "min": "", "max": "", "stdev": ""}
    return {
        "mean": _fmt_float(statistics.fmean(values)),
        "median": _fmt_float(statistics.median(values)),
        "min": _fmt_float(min(values)),
        "max": _fmt_float(max(values)),
        "stdev": _fmt_float(statistics.stdev(values) if len(values) > 1 else 0.0),
    }


def _condition_summary(run_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in run_rows:
        if row["validation_result"] == "valid":
            grouped[str(row["condition"])].append(row)

    rows: list[dict[str, object]] = []
    for condition in sorted(grouped):
        group = grouped[condition]
        out: dict[str, object] = {
            "condition": condition,
            "n_runs": len(group),
            "valid_runs": sum(1 for row in group if row["validation_result"] == "valid"),
            "state_hashes_unique": len({row["state_hash"] for row in group}),
        }
        for field in RUN_NUMERIC_FIELDS:
            values = [_float(row.get(field)) for row in group]
            for stat_name, stat_value in _stats(values).items():
                out[f"{field}_{stat_name}"] = stat_value
        rows.append(out)
    return rows


def _paired_rows(run_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    valid_by_key = {
        (str(row["condition"]), _int(row["seed"])): row
        for row in run_rows
        if row["validation_result"] == "valid"
    }
    conditions = sorted({condition for condition, _seed in valid_by_key})
    if {"baseline", "no_antistag", "no_combat"}.issubset(conditions):
        pairs = [
            ("baseline", "no_antistag"),
            ("baseline", "no_combat"),
            ("no_antistag", "no_combat"),
        ]
    else:
        pairs = [
            (left, right)
            for index, left in enumerate(conditions)
            for right in conditions[index + 1:]
        ]

    rows: list[dict[str, object]] = []
    for left, right in pairs:
        seeds = sorted({
            seed
            for condition, seed in valid_by_key
            if condition in {left, right}
        })
        for seed in seeds:
            left_row = valid_by_key.get((left, seed))
            right_row = valid_by_key.get((right, seed))
            if not left_row or not right_row:
                continue
            out: dict[str, object] = {
                "reference_condition": left,
                "comparison_condition": right,
                "seed": seed,
            }
            for field in PAIR_METRICS:
                left_value = _float(left_row.get(field))
                right_value = _float(right_row.get(field))
                out[f"{field}_reference"] = _fmt_float(left_value)
                out[f"{field}_comparison"] = _fmt_float(right_value)
                out[f"{field}_delta"] = _fmt_float(right_value - left_value)
                out[f"{field}_ratio"] = (
                    _fmt_float(right_value / left_value)
                    if left_value not in (0.0, -0.0) else ""
                )
            rows.append(out)

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["reference_condition"]), str(row["comparison_condition"]))].append(row)

    summary_rows: list[dict[str, object]] = []
    for (left, right), group in sorted(grouped.items()):
        out: dict[str, object] = {
            "reference_condition": left,
            "comparison_condition": right,
            "n_shared_seeds": len(group),
        }
        for field in PAIR_METRICS:
            deltas = [_float(row.get(f"{field}_delta")) for row in group]
            ratios = [
                _float(row.get(f"{field}_ratio"))
                for row in group
                if row.get(f"{field}_ratio") not in ("", None)
            ]
            out[f"{field}_delta_mean"] = _stats(deltas)["mean"]
            out[f"{field}_delta_median"] = _stats(deltas)["median"]
            out[f"{field}_ratio_mean"] = _stats(ratios)["mean"] if ratios else ""
        summary_rows.append(out)

    return rows, summary_rows


def analyze(plan_path: Path, root: Path, output_dir: Path) -> dict[str, object]:
    plan, plan_hash = load_plan(plan_path)
    run_index = _load_run_index(root)

    run_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    largest_file_rows: list[dict[str, object]] = []
    superseded_rows: list[dict[str, object]] = []

    for condition in plan["conditions"]:
        condition_name = condition["name"]
        seeds = parse_seed_range(str(condition.get("seeds", "1-5")))
        for seed in seeds:
            run_dir = root / condition_name / f"seed_{seed}"
            paths = _expected_run_paths(run_dir, condition_name, seed)
            valid, validation_errors = validate_run_outputs(run_dir, condition_name, seed)
            validation_result = "valid" if valid else "invalid_output"

            summary_rows = _read_csv_rows(paths["summary"]) if paths["summary"].is_file() else []
            final_summary = summary_rows[-1] if summary_rows else {}
            manifest = _read_json(paths["manifest"]) if paths["manifest"].is_file() else {}
            metrics_last = _last_csv_row(paths["metrics"]) if paths["metrics"].is_file() else {}
            event_counts = _stream_event_counts(paths["events"]) if paths["events"].is_file() else Counter()
            size_buckets, largest = _file_inventory(run_dir)
            index_row = run_index.get((condition_name, seed), {})

            largest_for_run = largest[0] if largest else {"path": "", "bytes": 0}
            state_hash = manifest.get("state_hash", index_row.get("state_hash", ""))
            raw_text_bytes = size_buckets.get("raw_text_bytes", 0)
            output_bytes = size_buckets.get("output_bytes", 0)

            row: dict[str, object] = {
                "condition": condition_name,
                "seed": seed,
                "validation_result": validation_result,
                "validation_errors": "; ".join(validation_errors),
                "result": RESULT_COMPLETED if valid else "invalid_output",
                "runner_index_status": index_row.get("status", ""),
                "runner_index_result": index_row.get("result", ""),
                "run_dir": str(run_dir.relative_to(root)),
                "final_tick": _int(metrics_last.get("tick")),
                "elapsed_seconds": _float(final_summary.get("wall_clock_seconds")),
                "final_population": _int(final_summary.get("final_population")),
                "metrics_last_population": _int(metrics_last.get("population")),
                "peak_population": _int(final_summary.get("peak_population")),
                "min_population": _int(final_summary.get("min_population")),
                "final_faction_count": _int(final_summary.get("final_faction_count")),
                "metrics_last_faction_count": _int(metrics_last.get("faction_count")),
                "peak_faction_count": _int(final_summary.get("peak_faction_count")),
                "total_factions_formed": _int(final_summary.get("total_factions_formed")),
                "total_wars": _int(final_summary.get("total_wars")),
                "total_deaths": _int(final_summary.get("total_deaths")),
                "total_births": _int(final_summary.get("total_births")),
                "total_schisms": _int(final_summary.get("total_schisms")),
                "total_mergers": _int(final_summary.get("total_mergers")),
                "total_treaties_formed": _int(final_summary.get("total_treaties_formed")),
                "total_treaties_broken": _int(final_summary.get("total_treaties_broken")),
                "stagnation_events": _int(final_summary.get("stagnation_events")),
                "era_count": _int(final_summary.get("era_count")),
                "peak_ram_mb": _float(final_summary.get("peak_ram_mb")),
                "event_count": sum(event_counts.values()),
                "output_bytes": output_bytes,
                "output_mib": round(output_bytes / BYTES_PER_MIB, 3),
                "output_gib": round(output_bytes / BYTES_PER_GIB, 6),
                "data_bytes": size_buckets.get("data_bytes", 0),
                "full_log_bytes": size_buckets.get("full_log_bytes", 0),
                "manual_chronicle_bytes": size_buckets.get("manual_chronicle_bytes", 0),
                "era_export_bytes": size_buckets.get("era_export_bytes", 0),
                "raw_text_bytes": raw_text_bytes,
                "raw_text_gib": round(raw_text_bytes / BYTES_PER_GIB, 6),
                "dashboard_bytes": size_buckets.get("dashboard_bytes", 0),
                "runner_marker_bytes": size_buckets.get("runner_marker_bytes", 0),
                "largest_file": largest_for_run.get("path", ""),
                "largest_file_bytes": largest_for_run.get("bytes", 0),
                "state_hash": state_hash,
                "code_commit": manifest.get("code", {}).get("commit", ""),
                "code_dirty": manifest.get("code", {}).get("dirty", ""),
                "summary_row_count": len(summary_rows),
                "superseded_summary_rows": max(0, len(summary_rows) - 1),
            }
            for event_type in EVENT_COLUMNS:
                row[f"event_{event_type}"] = event_counts.get(event_type, 0)
            run_rows.append(row)

            for event_type, count in sorted(event_counts.items()):
                event_rows.append({
                    "condition": condition_name,
                    "seed": seed,
                    "event_type": event_type,
                    "count": count,
                })

            for rank, file_row in enumerate(largest[:10], start=1):
                largest_file_rows.append({
                    "condition": condition_name,
                    "seed": seed,
                    "rank": rank,
                    "bytes": file_row["bytes"],
                    "mib": round(int(file_row["bytes"]) / BYTES_PER_MIB, 3),
                    "path": file_row["path"],
                    "relative_path": file_row["relative_path"],
                })

            superseded_rows.extend(_build_superseded_rows(
                root,
                condition_name,
                seed,
                run_dir,
                summary_rows,
                paths["manifest"],
                valid,
            ))

    condition_rows = _condition_summary(run_rows)
    paired_rows, paired_summary_rows = _paired_rows(run_rows)

    run_fields = [
        "condition",
        "seed",
        "validation_result",
        "validation_errors",
        "result",
        "runner_index_status",
        "runner_index_result",
        "run_dir",
        "final_tick",
        "elapsed_seconds",
        "final_population",
        "metrics_last_population",
        "peak_population",
        "min_population",
        "final_faction_count",
        "metrics_last_faction_count",
        "peak_faction_count",
        "total_factions_formed",
        "total_wars",
        "total_deaths",
        "total_births",
        "total_schisms",
        "total_mergers",
        "total_treaties_formed",
        "total_treaties_broken",
        "stagnation_events",
        "era_count",
        "peak_ram_mb",
        "event_count",
        *[f"event_{event_type}" for event_type in EVENT_COLUMNS],
        "output_bytes",
        "output_mib",
        "output_gib",
        "data_bytes",
        "full_log_bytes",
        "manual_chronicle_bytes",
        "era_export_bytes",
        "raw_text_bytes",
        "raw_text_gib",
        "dashboard_bytes",
        "runner_marker_bytes",
        "largest_file",
        "largest_file_bytes",
        "state_hash",
        "code_commit",
        "code_dirty",
        "summary_row_count",
        "superseded_summary_rows",
    ]

    condition_fields = ["condition", "n_runs", "valid_runs", "state_hashes_unique"]
    for field in RUN_NUMERIC_FIELDS:
        condition_fields.extend([
            f"{field}_mean",
            f"{field}_median",
            f"{field}_min",
            f"{field}_max",
            f"{field}_stdev",
        ])

    pair_fields = ["reference_condition", "comparison_condition", "seed"]
    for field in PAIR_METRICS:
        pair_fields.extend([
            f"{field}_reference",
            f"{field}_comparison",
            f"{field}_delta",
            f"{field}_ratio",
        ])

    pair_summary_fields = ["reference_condition", "comparison_condition", "n_shared_seeds"]
    for field in PAIR_METRICS:
        pair_summary_fields.extend([
            f"{field}_delta_mean",
            f"{field}_delta_median",
            f"{field}_ratio_mean",
        ])

    _write_csv(output_dir / "run_level_summary.csv", run_rows, run_fields)
    _write_csv(output_dir / "condition_summary.csv", condition_rows, condition_fields)
    _write_csv(output_dir / "paired_seed_comparisons.csv", paired_rows, pair_fields)
    _write_csv(output_dir / "paired_seed_comparison_summary.csv", paired_summary_rows, pair_summary_fields)
    _write_csv(output_dir / "event_type_counts.csv", event_rows, ["condition", "seed", "event_type", "count"])
    _write_csv(
        output_dir / "largest_files.csv",
        largest_file_rows,
        ["condition", "seed", "rank", "bytes", "mib", "path", "relative_path"],
    )
    _write_csv(
        output_dir / "superseded_attempts.csv",
        superseded_rows,
        [
            "condition",
            "seed",
            "result",
            "artifact",
            "artifact_type",
            "bytes",
            "reason",
            "dry_run_cleanup_action",
        ],
    )

    total_bytes = sum(_int(row["output_bytes"]) for row in run_rows)
    valid_runs = sum(1 for row in run_rows if row["validation_result"] == "valid")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": plan["experiment_id"],
        "plan_sha256": plan_hash,
        "root": str(root.resolve()),
        "output_dir": str(output_dir.resolve()),
        "valid_runs": valid_runs,
        "total_runs": len(run_rows),
        "total_output_bytes": total_bytes,
        "total_output_gib": round(total_bytes / BYTES_PER_GIB, 6),
        "tables": [
            "run_level_summary.csv",
            "condition_summary.csv",
            "paired_seed_comparisons.csv",
            "paired_seed_comparison_summary.csv",
            "event_type_counts.csv",
            "largest_files.csv",
            "superseded_attempts.csv",
        ],
    }
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=Path("experiments_replication_v1.json"))
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("experiment_runs/core-replication-v1"),
        help="Experiment output root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Analysis output directory. Defaults to <root>/analysis.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or args.root / "analysis"
    manifest = analyze(args.plan, args.root, output_dir)
    print(
        f"Wrote {len(manifest['tables'])} analysis tables to "
        f"{manifest['output_dir']}"
    )
    print(
        f"Validated dataset rows: {manifest['valid_runs']}/"
        f"{manifest['total_runs']}; total output "
        f"{manifest['total_output_gib']:.3f} GiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
