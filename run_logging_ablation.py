#!/usr/bin/env python3
"""Run short logging-mode ablations for no-combat Thalren Vale runs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from run_experiments import validate_run_outputs


PROJECT_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ID = "logging-ablation-v1"
DEFAULT_TICKS = (100, 250, 500, 1000)
LOG_MODES = ("full", "summary", "metrics_only", "off")
SEED = 1
CONDITION = "no_combat"
BYTES_PER_MIB = 1024 * 1024
csv.field_size_limit(sys.maxsize)


def _int(value: object, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _last_csv_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        last: dict[str, str] = {}
        for row in reader:
            if row:
                last = row
    return last


def _count_events(path: Path) -> int:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        return sum(1 for _row in reader)


def _sizes(run_dir: Path) -> tuple[int, int]:
    output_bytes = 0
    raw_text_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(run_dir):
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue
            output_bytes += size
            relative = path.relative_to(run_dir)
            if (
                relative.parts[:1] == ("logs",)
                or filename.startswith("manual_chronicle_")
                or filename.startswith("era_export_")
            ):
                raw_text_bytes += size
    return output_bytes, raw_text_bytes


def _paths(run_dir: Path) -> dict[str, Path]:
    data = run_dir / "data"
    suffix = f"{CONDITION}_seed_{SEED}"
    return {
        "summary": data / "run_summaries.csv",
        "manifest": data / f"run_manifest_{suffix}.json",
        "events": data / f"faction_events_{suffix}.csv",
    }


def run_case(root: Path, ticks: int, mode: str, timeout_seconds: int) -> dict:
    run_dir = root / f"ticks_{ticks}" / mode
    run_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "thalren_vale",
        "--seed",
        str(SEED),
        "--condition",
        CONDITION,
        "--ticks",
        str(ticks),
        "--disable-layer",
        "combat",
        "--log-mode",
        mode,
    ]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get(
        "PYTHONPATH", "")

    print(f"  ticks={ticks:<4} mode={mode:<12}", end="", flush=True)
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=run_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        returncode = process.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        process = None
        returncode = -1
        timed_out = True
        (run_dir / "runner_stderr.txt").write_text(
            f"timeout: {exc}\n", encoding="utf-8")

    elapsed = round(time.perf_counter() - started, 6)
    if process and process.returncode != 0:
        (run_dir / "runner_stdout.txt").write_text(
            process.stdout, encoding="utf-8")
        (run_dir / "runner_stderr.txt").write_text(
            process.stderr, encoding="utf-8")

    valid, errors = validate_run_outputs(run_dir, CONDITION, SEED)
    paths = _paths(run_dir)
    summary = _last_csv_row(paths["summary"]) if paths["summary"].is_file() else {}
    manifest = (
        json.loads(paths["manifest"].read_text(encoding="utf-8"))
        if paths["manifest"].is_file()
        else {}
    )
    event_count = _count_events(paths["events"]) if paths["events"].is_file() else 0
    output_bytes, raw_text_bytes = _sizes(run_dir)

    status = "completed" if returncode == 0 and valid else "invalid_output"
    if timed_out:
        status = "wall_clock_limit"
    elif returncode not in (0, None):
        status = "exception"

    row = {
        "experiment_id": EXPERIMENT_ID,
        "condition": CONDITION,
        "seed": SEED,
        "ticks": ticks,
        "log_mode": mode,
        "status": status,
        "returncode": returncode,
        "validation_errors": "; ".join(errors),
        "elapsed_seconds": elapsed,
        "summary_wall_clock_seconds": _float(
            summary.get("wall_clock_seconds"), elapsed),
        "ticks_per_second": round(ticks / elapsed, 6) if elapsed else "",
        "output_bytes": output_bytes,
        "output_mib": round(output_bytes / BYTES_PER_MIB, 6),
        "raw_text_bytes": raw_text_bytes,
        "raw_text_mib": round(raw_text_bytes / BYTES_PER_MIB, 6),
        "structured_event_count": event_count,
        "events_per_tick": round(event_count / ticks, 6),
        "final_population": _int(summary.get("final_population")),
        "final_factions": _int(summary.get("final_faction_count")),
        "peak_population": _int(summary.get("peak_population")),
        "peak_ram_mb": _float(summary.get("peak_ram_mb")),
        "final_state_hash": manifest.get("state_hash", ""),
        "run_dir": str(run_dir),
    }
    (run_dir / "runner_result.json").write_text(
        json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f" {status} {elapsed:.3f}s {output_bytes / BYTES_PER_MIB:.3f} MiB")
    return row


def collect_case(root: Path, ticks: int, mode: str) -> dict | None:
    run_dir = root / f"ticks_{ticks}" / mode
    if not run_dir.is_dir():
        return None
    valid, errors = validate_run_outputs(run_dir, CONDITION, SEED)
    paths = _paths(run_dir)
    if not paths["summary"].is_file() or not paths["manifest"].is_file():
        return {
            "experiment_id": EXPERIMENT_ID,
            "condition": CONDITION,
            "seed": SEED,
            "ticks": ticks,
            "log_mode": mode,
            "status": "invalid_output",
            "returncode": "",
            "validation_errors": "; ".join(errors) or "missing final summary or manifest",
            "elapsed_seconds": "",
            "summary_wall_clock_seconds": "",
            "ticks_per_second": "",
            "output_bytes": _sizes(run_dir)[0],
            "output_mib": round(_sizes(run_dir)[0] / BYTES_PER_MIB, 6),
            "raw_text_bytes": _sizes(run_dir)[1],
            "raw_text_mib": round(_sizes(run_dir)[1] / BYTES_PER_MIB, 6),
            "structured_event_count": (
                _count_events(paths["events"]) if paths["events"].is_file() else 0
            ),
            "events_per_tick": "",
            "final_population": "",
            "final_factions": "",
            "peak_population": "",
            "peak_ram_mb": "",
            "final_state_hash": "",
            "run_dir": str(run_dir),
        }

    summary = _last_csv_row(paths["summary"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    event_count = _count_events(paths["events"]) if paths["events"].is_file() else 0
    output_bytes, raw_text_bytes = _sizes(run_dir)
    elapsed = _float(summary.get("wall_clock_seconds"))
    return {
        "experiment_id": EXPERIMENT_ID,
        "condition": CONDITION,
        "seed": SEED,
        "ticks": ticks,
        "log_mode": mode,
        "status": "completed" if valid else "invalid_output",
        "returncode": 0 if valid else "",
        "validation_errors": "; ".join(errors),
        "elapsed_seconds": elapsed,
        "summary_wall_clock_seconds": elapsed,
        "ticks_per_second": round(ticks / elapsed, 6) if elapsed else "",
        "output_bytes": output_bytes,
        "output_mib": round(output_bytes / BYTES_PER_MIB, 6),
        "raw_text_bytes": raw_text_bytes,
        "raw_text_mib": round(raw_text_bytes / BYTES_PER_MIB, 6),
        "structured_event_count": event_count,
        "events_per_tick": round(event_count / ticks, 6),
        "final_population": _int(summary.get("final_population")),
        "final_factions": _int(summary.get("final_faction_count")),
        "peak_population": _int(summary.get("peak_population")),
        "peak_ram_mb": _float(summary.get("peak_ram_mb")),
        "final_state_hash": manifest.get("state_hash", ""),
        "run_dir": str(run_dir),
    }


def collect_existing(root: Path, ticks_values: tuple[int, ...]) -> list[dict]:
    rows: list[dict] = []
    for ticks in ticks_values:
        for mode in LOG_MODES:
            row = collect_case(root, ticks, mode)
            if row is not None:
                rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_mode[row["log_mode"]].append(row)

    summary_rows: list[dict] = []
    for mode in LOG_MODES:
        group = by_mode.get(mode, [])
        if not group:
            continue
        total_ticks = sum(_int(row["ticks"]) for row in group)
        total_elapsed = sum(_float(row["elapsed_seconds"]) for row in group)
        total_output = sum(_int(row["output_bytes"]) for row in group)
        total_raw = sum(_int(row["raw_text_bytes"]) for row in group)
        total_events = sum(_int(row["structured_event_count"]) for row in group)
        hashes = {row["final_state_hash"] for row in group}
        summary_rows.append({
            "experiment_id": EXPERIMENT_ID,
            "log_mode": mode,
            "n_runs": len(group),
            "all_completed": all(row["status"] == "completed" for row in group),
            "state_hashes_unique": len(hashes),
            "total_ticks": total_ticks,
            "total_elapsed_seconds": round(total_elapsed, 6),
            "mean_ticks_per_second": (
                round(total_ticks / total_elapsed, 6) if total_elapsed else ""),
            "total_output_bytes": total_output,
            "output_bytes_per_tick": (
                round(total_output / total_ticks, 6) if total_ticks else ""),
            "total_raw_text_bytes": total_raw,
            "raw_text_bytes_per_tick": (
                round(total_raw / total_ticks, 6) if total_ticks else ""),
            "total_structured_events": total_events,
            "structured_events_per_tick": (
                round(total_events / total_ticks, 6) if total_ticks else ""),
            "mean_peak_ram_mb": round(
                sum(_float(row["peak_ram_mb"]) for row in group) / len(group), 6),
        })
    return summary_rows


def write_report(root: Path, rows: list[dict], summary_rows: list[dict]) -> None:
    by_tick = defaultdict(dict)
    for row in rows:
        by_tick[_int(row["ticks"])][row["log_mode"]] = row

    tick_values = sorted({_int(row["ticks"]) for row in rows})
    lines = [
        "# Logging Ablation Report",
        "",
        f"- Experiment ID: `{EXPERIMENT_ID}`",
        f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Condition: `{CONDITION}`",
        f"- Seed: `{SEED}`",
        f"- Tick counts: `{', '.join(str(tick) for tick in tick_values)}`",
        f"- Log modes: `{', '.join(LOG_MODES)}`",
        "",
        "This is a short benchmark only. It is not a full 10,000-tick replication.",
        "",
        "## Per-run results",
        "",
        "| Ticks | Mode | Status | Elapsed | Ticks/s | Output MiB | Raw text MiB | Events | Final pop | Final factions | State hash |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['ticks']} | {row['log_mode']} | {row['status']} | "
            f"{_float(row['elapsed_seconds']):.3f}s | "
            f"{_float(row['ticks_per_second']):.3f} | "
            f"{_float(row['output_mib']):.3f} | "
            f"{_float(row['raw_text_mib']):.3f} | "
            f"{_int(row['structured_event_count']):,} | "
            f"{row['final_population']} | {row['final_factions']} | "
            f"`{str(row['final_state_hash'])[:12]}…` |"
        )

    lines.extend([
        "",
        "## Mode summary",
        "",
        "| Mode | Runs | Mean ticks/s | Output bytes/tick | Raw text bytes/tick | Events/tick | Unique hashes |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in summary_rows:
        lines.append(
            f"| {row['log_mode']} | {row['n_runs']} | "
            f"{_float(row['mean_ticks_per_second']):.3f} | "
            f"{_float(row['output_bytes_per_tick']):.1f} | "
            f"{_float(row['raw_text_bytes_per_tick']):.1f} | "
            f"{_float(row['structured_events_per_tick']):.3f} | "
            f"{row['state_hashes_unique']} |"
        )

    lines.extend([
        "",
        "## Same-state check",
        "",
    ])
    mismatches = []
    for ticks, modes in sorted(by_tick.items()):
        hashes = {row["final_state_hash"] for row in modes.values()}
        if len(hashes) != 1:
            mismatches.append(ticks)
    if mismatches:
        lines.append(
            "State hashes differed across log modes for ticks: "
            + ", ".join(str(tick) for tick in mismatches)
            + ". Treat timing results as invalid until investigated."
        )
    else:
        lines.append(
            "For every tested tick count, all log modes produced the same "
            "final state hash. The logging mode did not perturb simulated state "
            "in this benchmark."
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "Use `logging_ablation_results.csv` for exact values. If summary, "
        "metrics-only, or off modes reduce elapsed time while preserving state "
        "hashes, full raw text logging is a causal performance contributor. "
        "If elapsed time remains close to full mode after raw text is removed, "
        "simulation-state complexity is the stronger explanation.",
        "",
    ])
    (root / "LOGGING_ABLATION_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8")


def parse_ticks(value: str) -> tuple[int, ...]:
    ticks = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not ticks or any(tick < 1 for tick in ticks):
        raise argparse.ArgumentTypeError("ticks must be positive integers")
    return ticks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path,
                        default=Path("experiment_runs") / EXPERIMENT_ID)
    parser.add_argument("--ticks", type=parse_ticks,
                        default=DEFAULT_TICKS)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--collect-existing", action="store_true",
                        help="Write CSV/report from existing run directories without running simulations.")
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")

    root = args.output_root
    if args.collect_existing:
        rows = collect_existing(root, args.ticks)
        if not rows:
            parser.error(f"no existing run artifacts found under {root}")
        summary_rows = summarize(rows)
        write_csv(root / "logging_ablation_results.csv", rows)
        write_csv(root / "logging_ablation_summary.csv", summary_rows)
        write_report(root, rows, summary_rows)
        print(f"Collected {len(rows)} existing logging ablation rows from {root}")
        return 0 if all(row["status"] == "completed" for row in rows) else 1

    if root.exists() and any(root.iterdir()):
        if not args.overwrite:
            parser.error(f"{root} is not empty; use --overwrite")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    rows = [
        run_case(root, ticks, mode, args.timeout_seconds)
        for ticks in args.ticks
        for mode in LOG_MODES
    ]
    summary_rows = summarize(rows)
    write_csv(root / "logging_ablation_results.csv", rows)
    write_csv(root / "logging_ablation_summary.csv", summary_rows)
    write_report(root, rows, summary_rows)
    print(f"Wrote logging ablation results to {root}")
    return 0 if all(row["status"] == "completed" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
