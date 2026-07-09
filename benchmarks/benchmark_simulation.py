#!/usr/bin/env python3
"""Controlled population-scaling benchmarks for Thalren Vale."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from thalren_vale import __version__, sim, world  # noqa: E402
from thalren_vale.inhabitants import Inhabitant  # noqa: E402
from thalren_vale.reproducibility import _code_revision  # noqa: E402


def _setup_population(population: int, seed: int) -> None:
    """Create the same synthetic population for each measured mode."""
    sim.reset_runtime_state()
    random.seed(seed)
    world.reseed_world()
    habitable = [
        (r, c)
        for r, row in enumerate(world.world)
        for c, tile in enumerate(row)
        if tile["habitable"]
    ]
    if not habitable:
        raise RuntimeError("generated world has no habitable tiles")

    for index in range(population):
        r, c = habitable[index % len(habitable)]
        person = Inhabitant(f"Bench{index:05d}", r, c)
        person.inventory["food"] = 30
        sim.people.append(person)
        world.grid_add(person)


def benchmark_case(
    population: int,
    mode: str,
    ticks: int,
    warmup: int,
    seed: int,
) -> dict:
    """Measure inhabitants-layer latency without file or console I/O."""
    _setup_population(population, seed)
    sim._serial_mode = mode == "serial"
    sink = StringIO()

    with redirect_stdout(sink):
        for tick in range(1, warmup + 1):
            sim.inhabitants_layer(tick)

    tracemalloc.start()
    latencies = []
    with redirect_stdout(sink):
        for tick in range(warmup + 1, warmup + ticks + 1):
            started = time.perf_counter()
            sim.inhabitants_layer(tick)
            latencies.append((time.perf_counter() - started) * 1000)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    mean_ms = statistics.fmean(latencies)
    ordered = sorted(latencies)
    p95_index = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return {
        "population": population,
        "mode": mode,
        "ticks": ticks,
        "mean_ms_per_tick": round(mean_ms, 4),
        "median_ms_per_tick": round(statistics.median(latencies), 4),
        "p95_ms_per_tick": round(ordered[p95_index], 4),
        "ticks_per_second": round(1000.0 / mean_ms, 4) if mean_ms else None,
        "peak_traced_memory_mb": round(peak_bytes / (1024 * 1024), 4),
        "final_population": len(sim.people),
    }


def write_results(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        if payload["results"]:
            writer = csv.DictWriter(handle, fieldnames=payload["results"][0])
            writer.writeheader()
            writer.writerows(payload["results"])


def parse_populations(value: str) -> list[int]:
    populations = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not populations or any(population < 1 for population in populations):
        raise argparse.ArgumentTypeError("populations must be positive integers")
    return populations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--populations", type=parse_populations,
                        default=parse_populations("30,100,500,1000"))
    parser.add_argument("--modes", choices=("serial", "threaded"), nargs="+",
                        default=("serial", "threaded"))
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--output", type=Path,
                        default=Path("benchmarks/results/latest.json"))
    parser.add_argument("--max-ms-per-tick", type=float, default=None,
                        help="Fail if any mean tick latency exceeds this value")
    args = parser.parse_args()
    if args.ticks < 1 or args.warmup < 0:
        parser.error("ticks must be positive and warmup cannot be negative")

    results = [
        benchmark_case(population, mode, args.ticks, args.warmup, args.seed)
        for population in args.populations
        for mode in args.modes
    ]
    payload = {
        "schema_version": 1,
        "benchmark": "inhabitants_layer_population_scaling",
        "project_version": __version__,
        "seed": args.seed,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "code": _code_revision(),
        },
        "results": results,
    }
    write_results(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.max_ms_per_tick is not None:
        failures = [
            result for result in results
            if result["mean_ms_per_tick"] > args.max_ms_per_tick
        ]
        if failures:
            print(f"benchmark threshold exceeded: {failures}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
