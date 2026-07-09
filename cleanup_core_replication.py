#!/usr/bin/env python3
"""Dry-run cleanup inventory for core-replication-v1 artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from run_experiments import load_plan, parse_seed_range, validate_run_outputs


DEFAULT_PLAN = Path("experiments_replication_v1.json")
DEFAULT_ROOT = Path("experiment_runs/core-replication-v1")


def _read_summary_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def _candidate(
    *,
    condition: str,
    seed: int,
    artifact: Path,
    root: Path,
    artifact_type: str,
    reason: str,
    action: str,
) -> dict[str, object]:
    return {
        "condition": condition,
        "seed": seed,
        "artifact": str(artifact.relative_to(root)),
        "artifact_type": artifact_type,
        "bytes": artifact.stat().st_size if artifact.is_file() else "",
        "reason": reason,
        "dry_run_action": action,
    }


def scan(root: Path, plan_path: Path) -> list[dict[str, object]]:
    plan, _plan_hash = load_plan(plan_path)
    rows: list[dict[str, object]] = []
    for condition in plan["conditions"]:
        condition_name = condition["name"]
        for seed in parse_seed_range(str(condition.get("seeds", "1-5"))):
            run_dir = root / condition_name / f"seed_{seed}"
            valid, _errors = validate_run_outputs(run_dir, condition_name, seed)
            if not valid:
                continue
            data_dir = run_dir / "data"
            manifest = data_dir / f"run_manifest_{condition_name}_seed_{seed}.json"
            manifest_mtime = manifest.stat().st_mtime if manifest.is_file() else 0.0

            summary_path = data_dir / "run_summaries.csv"
            summary_rows = _read_summary_rows(summary_path)
            if len(summary_rows) > 1:
                rows.append({
                    "condition": condition_name,
                    "seed": seed,
                    "artifact": str(summary_path.relative_to(root)),
                    "artifact_type": "superseded_summary_rows",
                    "bytes": summary_path.stat().st_size,
                    "reason": (
                        f"{len(summary_rows) - 1} earlier row(s) precede "
                        "the final validated row"
                    ),
                    "dry_run_action": (
                        "optional curation only: back up file, then rewrite "
                        "header plus final row"
                    ),
                })

            for marker_name in ("runner_stdout.txt", "runner_stderr.txt"):
                marker = run_dir / marker_name
                if not marker.is_file():
                    continue
                marker_mtime = marker.stat().st_mtime
                if marker_mtime <= manifest_mtime:
                    text = marker.read_text(
                        encoding="utf-8", errors="replace")[:500]
                    reason = "stale runner marker older than final manifest"
                    if "timed out" in text or "timeout:" in text:
                        reason = (
                            "stale wall_clock_limit marker from superseded "
                            "attempt"
                        )
                    rows.append(_candidate(
                        condition=condition_name,
                        seed=seed,
                        artifact=marker,
                        root=root,
                        artifact_type="stale_runner_marker",
                        reason=reason,
                        action="delete only after explicit approval",
                    ))

            error_files = sorted(data_dir.glob("run_manifest_*.error.txt"))
            for error_file in error_files:
                if error_file.stat().st_mtime <= manifest_mtime:
                    rows.append(_candidate(
                        condition=condition_name,
                        seed=seed,
                        artifact=error_file,
                        root=root,
                        artifact_type="stale_manifest_error",
                        reason="error trace older than final valid manifest",
                        action="delete only after explicit approval",
                    ))

            log_files = sorted((run_dir / "logs").glob("*.txt"))
            if len(log_files) > 1:
                newest = max(log_files, key=lambda path: path.stat().st_mtime)
                for log_file in log_files:
                    if log_file == newest:
                        continue
                    rows.append(_candidate(
                        condition=condition_name,
                        seed=seed,
                        artifact=log_file,
                        root=root,
                        artifact_type="older_text_log",
                        reason=(
                            "older log file for a condition/seed with a newer "
                            "validated run"
                        ),
                        action="delete only after explicit approval",
                    ))
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "condition",
        "seed",
        "artifact",
        "artifact_type",
        "bytes",
        "reason",
        "dry_run_action",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Required. Print candidates without deleting.")
    parser.add_argument("--output", type=Path,
                        default=DEFAULT_ROOT / "analysis" / "cleanup_dry_run.csv")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("this tool only supports --dry-run; no delete mode exists")

    rows = scan(args.root, args.plan)
    write_csv(args.output, rows)
    print(f"Dry-run cleanup candidates: {len(rows)}")
    for row in rows:
        print(
            f"- {row['artifact_type']}: {row['artifact']} "
            f"({row['reason']})"
        )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
