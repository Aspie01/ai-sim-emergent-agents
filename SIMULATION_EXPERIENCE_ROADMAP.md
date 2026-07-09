# Simulation Experience Roadmap: Next 25 Improvements + Optimization Workstream

This document is an implementation-oriented roadmap for improving how Thalren Vale feels to run, observe, understand, replay, scale, profile, optimize, and extend. Items are ordered roughly by user impact and dependency. Code samples are written for Python 3.10+ and are intended as reference implementations to integrate behind tests before enabling them by default. Performance work should be measurement-driven: profile first, change one bottleneck at a time, then benchmark and compare.

## Engineering principles

- Preserve seeded reproducibility. Any new randomness must come from simulation-owned RNG state.
- Keep narrative presentation separate from authoritative state.
- Emit structured events first; render text, metrics, and UI notifications from those events.
- Make expensive observation optional and measurable.
- Prefer explicit configuration over hidden constants.
- Introduce features behind defaults that preserve current experimental behavior.
- Optimize from measurements, not guesses. Every performance change should have a before/after benchmark.
- Prefer algorithmic improvements before lower-level acceleration. Fix `O(n²)` scans before adding threads or compilers.
- Keep optimization deterministic. Faster runs must not silently change seeded outcomes unless the change is intentional and documented.

---

## 1. Add pause, resume, and single-step controls

Interactive control is the highest-value usability improvement. A thread-safe controller should allow the dashboard or terminal to pause without corrupting state.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Condition


@dataclass
class SimulationController:
    _paused: bool = False
    _stopped: bool = False
    _steps_remaining: int = 0
    _condition: Condition = field(default_factory=Condition)

    def pause(self) -> None:
        with self._condition:
            self._paused = True

    def resume(self) -> None:
        with self._condition:
            self._paused = False
            self._steps_remaining = 0
            self._condition.notify_all()

    def step(self, count: int = 1) -> None:
        if count < 1:
            raise ValueError("count must be positive")
        with self._condition:
            self._paused = True
            self._steps_remaining += count
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    def before_tick(self) -> bool:
        """Block while paused; return False when the loop should stop."""
        with self._condition:
            while self._paused and self._steps_remaining == 0 and not self._stopped:
                self._condition.wait()
            if self._stopped:
                return False
            if self._steps_remaining:
                self._steps_remaining -= 1
            return True
```

Acceptance criteria:

- Pausing never occurs midway through a tick.
- Stepping advances exactly the requested number of ticks.
- Seeded results are identical with and without pauses.

## 2. Add checkpoint save and deterministic restore

Long simulations need resumable state, not only resumable batches. Use a versioned schema and atomic replacement.

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CHECKPOINT_SCHEMA_VERSION = 1


def write_checkpoint(path: Path, *, tick: int, seed: int,
                     rng_state: Any, state_payload: dict) -> None:
    document = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "tick": tick,
        "seed": seed,
        "rng_state": rng_state,
        "state": state_payload,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_checkpoint(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    version = document.get("schema_version")
    if version != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(f"unsupported checkpoint schema: {version!r}")
    return document
```

Store stable identifiers rather than object references. Test uninterrupted and restored runs for identical final state hashes.

## 3. Add selectable simulation speeds

Expose `paused`, `1×`, `2×`, `5×`, `10×`, and `unlimited` presentation modes. Speed must affect pacing only, never simulation rules.

```python
import time


TICK_DELAYS = {
    "1x": 1.0,
    "2x": 0.5,
    "5x": 0.2,
    "10x": 0.1,
    "unlimited": 0.0,
}


def pace_tick(mode: str, elapsed_seconds: float) -> None:
    try:
        target = TICK_DELAYS[mode]
    except KeyError as exc:
        raise ValueError(f"unknown speed mode: {mode}") from exc
    remaining = target - elapsed_seconds
    if remaining > 0:
        time.sleep(remaining)
```

## 4. Add a concise terminal mode

Users should be able to choose `quiet`, `events`, `progress`, or `full` output. This reduces I/O overhead and makes overnight runs readable.

```python
from enum import IntEnum


class Verbosity(IntEnum):
    QUIET = 0
    EVENTS = 1
    PROGRESS = 2
    FULL = 3


def should_render(level: Verbosity, required: Verbosity) -> bool:
    return level >= required
```

All output decisions should be centralized rather than embedded as scattered `print()` calls.

## 5. Add event importance and dashboard notifications

Structured events should carry severity so users can filter routine activity from turning points.

```python
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Importance(IntEnum):
    TRACE = 10
    ROUTINE = 20
    NOTABLE = 30
    MAJOR = 40
    CRITICAL = 50


@dataclass(frozen=True)
class UserFacingEvent:
    tick: int
    event_type: str
    message: str
    importance: Importance = Importance.ROUTINE
    actors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
```

Recommended defaults: births are routine, technologies notable, factions major, wars major, extinction critical.

## 6. Build a searchable event timeline

The dashboard should filter by tick range, faction, inhabitant, event type, and importance. Store normalized events as newline-delimited JSON for streaming access.

```python
import json
from pathlib import Path


def append_jsonl(path: Path, event: UserFacingEvent) -> None:
    row = {
        "tick": event.tick,
        "event_type": event.event_type,
        "message": event.message,
        "importance": int(event.importance),
        "actors": list(event.actors),
        "metadata": event.metadata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
```

## 7. Add an inhabitant inspector

Clicking an inhabitant should show health, hunger, inventory, generation, faction, religion, beliefs, strongest relationships, movement history, and notable life events. Use immutable snapshots so observation cannot mutate the simulation.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class InhabitantView:
    name: str
    position: tuple[int, int]
    health: int
    hunger: int
    generation: int
    faction: str | None
    religion: str | None
    beliefs: tuple[str, ...]
    inventory: tuple[tuple[str, float], ...]
    strongest_relationships: tuple[tuple[str, int], ...]


def strongest_relationships(trust: dict[str, int], limit: int = 5):
    return tuple(sorted(trust.items(), key=lambda item: (-item[1], item[0]))[:limit])
```

## 8. Add a faction inspector

Show membership history, dominant beliefs, territory, settlements, treasury, technologies, treaties, rivals, wars, religion, and leadership indicators. Include deltas over the last 25/100 ticks rather than only current values.

## 9. Add relationship graph exploration

Visualize trust, faction allegiance, treaties, rivalry, trade, and religious influence as independently toggleable edge types. Cap displayed nodes and aggregate low-importance inhabitants to keep rendering responsive.

```python
def bounded_edges(edges: list[dict], *, limit: int = 500) -> list[dict]:
    """Keep the most important edges with deterministic tie-breaking."""
    return sorted(
        edges,
        key=lambda edge: (
            -abs(float(edge.get("weight", 0))),
            str(edge.get("source", "")),
            str(edge.get("target", "")),
        ),
    )[:limit]
```

## 10. Add map layers and a legend

The map should toggle terrain, resources, population density, faction territory, settlement zones, trade routes, war fronts, religion, and recent deaths. Every color and marker needs a visible legend and colorblind-safe palette.

## 11. Add historical map replay

Persist compact map deltas every configurable interval. Users should scrub backward without rewinding authoritative simulation state.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TileDelta:
    tick: int
    row: int
    column: int
    changed: tuple[tuple[str, object], ...]


def mapping_delta(before: dict, after: dict) -> tuple[tuple[str, object], ...]:
    keys = sorted(before.keys() | after.keys())
    return tuple((key, after.get(key)) for key in keys if before.get(key) != after.get(key))
```

## 12. Add bookmarks and named moments

Users should bookmark ticks such as “First War” or “Founding of the Tidal League.” Store bookmarks separately from simulation state so they do not affect hashes.

```python
from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Bookmark:
    tick: int
    title: str
    note: str = ""


def save_bookmarks(path: Path, bookmarks: list[Bookmark]) -> None:
    path.write_text(
        json.dumps([asdict(item) for item in bookmarks], indent=2) + "\n",
        encoding="utf-8",
    )
```

## 13. Add guided scenario presets

Offer presets such as “Harsh Winter,” “Island World,” “Trade Renaissance,” “Religious Schism,” and “Resource Collapse.” Presets must compile into ordinary validated configuration and record their expanded values in manifests.

```python
SCENARIO_PRESETS: dict[str, dict[str, object]] = {
    "harsh_winter": {
        "winter_length": 15,
        "winter_regeneration_multiplier": 0.05,
    },
    "trade_renaissance": {
        "war_tension_threshold": 350,
        "trade_route_threshold": 2,
    },
}


def expand_preset(name: str, overrides: dict[str, object]) -> dict[str, object]:
    if name not in SCENARIO_PRESETS:
        raise ValueError(f"unknown scenario preset: {name}")
    return {**SCENARIO_PRESETS[name], **overrides}
```

## 14. Add a configuration preview and validation report

Before a run begins, print the effective configuration, derived values, disabled systems, estimated output volume, and warnings. Add `--dry-run` to validate without creating files.

## 15. Add deterministic named RNG streams

Separate world, inhabitants, beliefs, diplomacy, combat, and presentation randomness. This allows local feature changes without perturbing unrelated random sequences.

```python
import hashlib
import random


def derive_seed(master_seed: int, stream_name: str) -> int:
    payload = f"{master_seed}:{stream_name}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


class RandomStreams:
    def __init__(self, master_seed: int) -> None:
        self._master_seed = master_seed
        self._streams: dict[str, random.Random] = {}

    def get(self, name: str) -> random.Random:
        return self._streams.setdefault(
            name, random.Random(derive_seed(self._master_seed, name)))
```

This is a prerequisite for deterministic parallelism.

## 16. Add deterministic parallel inhabitant updates

Replace shared global random calls in worker threads with per-agent or per-layer streams. Partition work deterministically and apply mutations in a stable commit phase. Do not claim threaded reproducibility until final-state hashes match serial execution under a documented contract.

## 17. Add adaptive spatial indexing

The population benchmark shows poor high-population scaling. Ensure every neighbor/trust interaction queries bounded spatial buckets rather than scanning all inhabitants.

```python
from collections import defaultdict


class SpatialIndex:
    def __init__(self) -> None:
        self._cells: dict[tuple[int, int], list[object]] = defaultdict(list)

    def rebuild(self, inhabitants) -> None:
        self._cells.clear()
        for inhabitant in inhabitants:
            self._cells[(inhabitant.r, inhabitant.c)].append(inhabitant)

    def within(self, row: int, column: int, radius: int):
        for r in range(row - radius, row + radius + 1):
            for c in range(column - radius, column + radius + 1):
                yield from self._cells.get((r, c), ())
```

Add benchmark thresholds before and after integration.

## 18. Add automatic performance regression comparison

Compare benchmark output against a committed baseline by ratio, not absolute machine-specific time.

```python
def regression_failures(current: list[dict], baseline: list[dict],
                        tolerance: float = 0.20) -> list[str]:
    baseline_by_key = {
        (row["population"], row["mode"]): row for row in baseline
    }
    failures = []
    for row in current:
        key = (row["population"], row["mode"])
        reference = baseline_by_key.get(key)
        if reference is None:
            continue
        ratio = row["mean_ms_per_tick"] / reference["mean_ms_per_tick"]
        if ratio > 1 + tolerance:
            failures.append(f"{key}: {ratio:.2f}x baseline")
    return failures
```

## 19. Add run comparison in the dashboard

Load two manifests and align population, factions, wars, Gini, tension, technologies, and interventions by tick. Explicitly display configuration differences before presenting outcome differences.

## 20. Add experiment progress and ETA reporting

The batch runner should report current tick, tick rate, rolling ETA, completed seeds, and total ETA. Write progress atomically so another process can monitor without reading large logs.

```python
def estimate_seconds_remaining(current_tick: int, total_ticks: int,
                               recent_tick_seconds: list[float]) -> float | None:
    if not recent_tick_seconds or current_tick >= total_ticks:
        return 0.0 if current_tick >= total_ticks else None
    sample = recent_tick_seconds[-100:]
    return (total_ticks - current_tick) * (sum(sample) / len(sample))
```

## 21. Add disk-space and output-volume guards

Before long batches, estimate storage from recent bytes per tick and refuse to start when free space is below a configurable safety margin.

```python
import shutil
from pathlib import Path


def ensure_free_space(path: Path, required_bytes: int,
                      safety_factor: float = 1.25) -> None:
    if required_bytes < 0 or safety_factor < 1:
        raise ValueError("invalid storage estimate")
    free = shutil.disk_usage(path).free
    needed = int(required_bytes * safety_factor)
    if free < needed:
        raise RuntimeError(
            f"insufficient disk space: need {needed:,} bytes, have {free:,}")
```

## 22. Add controlled interventions through the UI

Allow users to trigger resource changes, migrations, disasters, and diplomatic shocks through the same validated command system used by plugins. Mark every intervention as exogenous in structured events and manifests so research runs remain distinguishable.

## 23. Add accessibility and display preferences

Support colorblind palettes, reduced motion, high contrast, scalable text, ASCII-only terminal output, and emoji-free logs. Presentation preferences must never alter simulation state hashes.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayPreferences:
    palette: str = "colorblind_safe"
    reduced_motion: bool = False
    high_contrast: bool = False
    ascii_only: bool = False
    show_emoji: bool = True
```

## 24. Add persistent cross-run legends

Implement the existing roadmap item: selected factions, settlements, technologies, and heroes from completed runs can become read-only legends in later runs. This must be opt-in and disabled for controlled experiments.

Use a versioned archive containing only immutable summaries. Never import live state or advantages unless a scenario explicitly requests them.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalLegend:
    source_state_hash: str
    name: str
    kind: str
    summary: str
    source_tick: int
```

## 25. Add an end-of-run story and evidence report

Generate a deterministic, non-LLM report that combines:

- A chronological timeline of major events.
- Population and faction turning points.
- Longest wars and alliances.
- Most influential inhabitants and factions.
- Intervention counts and endogenous/exogenous labels.
- Configuration, revision, state hash, and data-quality warnings.

The optional LLM mythology should consume this report as source material, never raw mutable state. This gives users a satisfying conclusion while preserving evidence traceability.

---

## Performance optimization workstream

This section turns the general optimization ideas into concrete engineering tasks. It is intentionally separate from the user-facing experience items above because many performance changes should happen underneath existing behavior. Treat this as a recurring workstream that supports items 4, 15, 16, 17, 18, 20, and 21.

### P1. Add a repeatable profiler command

Before changing algorithms, create one blessed command that profiles a representative run and writes artifacts to a predictable location.

```bash
python -m cProfile -o artifacts/profiles/latest.prof run_experiment.py --preset benchmark --ticks 10000 --seed 1
python -m pstats artifacts/profiles/latest.prof
```

Recommended interactive inspection:

```bash
pip install snakeviz
snakeviz artifacts/profiles/latest.prof
```

Acceptance criteria:

- A documented command profiles the same seeded scenario every time.
- The profile artifact is ignored by Git unless intentionally archived.
- The top 30 functions by cumulative time are copied into a short performance note.
- No optimization PR is accepted without identifying the measured hotspot it addresses.

### P2. Add lightweight tick timing instrumentation

`cProfile` is good for deep inspection, but normal experiment runs also need cheap timing around major systems.

```python
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class TimingCollector:
    totals: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    @contextmanager
    def measure(self, name: str):
        start = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - start
            self.totals[name] = self.totals.get(name, 0.0) + elapsed
            self.counts[name] = self.counts.get(name, 0) + 1

    def report(self) -> list[tuple[str, float, float]]:
        rows = []
        for name, total in sorted(self.totals.items(), key=lambda item: -item[1]):
            count = self.counts[name]
            rows.append((name, total, total / count))
        return rows
```

Example integration:

```python
with timings.measure("inhabitants.decide"):
    update_inhabitant_decisions(world)

with timings.measure("factions.tick"):
    update_factions(world)
```

Acceptance criteria:

- Timing can be enabled with a config flag such as `--timings`.
- Timing is disabled by default for controlled experiments unless explicitly requested.
- Reports include total time, call count, and mean time per call.
- Timing output does not alter state hashes.

### P3. Audit algorithmic complexity before micro-optimization

Search for all-agent-vs-all-agent loops, repeated full-map scans, repeated sorting, and repeated recomputation of values that only change once per tick.

Bad pattern:

```python
for inhabitant in inhabitants:
    for other in inhabitants:
        if inhabitant is not other and distance(inhabitant, other) <= radius:
            maybe_interact(inhabitant, other)
```

Preferred pattern:

```python
index.rebuild(inhabitants)
for inhabitant in inhabitants:
    for other in index.within(inhabitant.r, inhabitant.c, radius):
        if inhabitant is not other:
            maybe_interact(inhabitant, other)
```

Acceptance criteria:

- Every known `O(population²)` path is listed in `docs/performance/complexity-audit.md`.
- Each item states whether it is acceptable, bounded, cached, spatially indexed, or scheduled for replacement.
- High-population benchmarks include at least one case where the old behavior was visibly poor.

### P4. Centralize logging and reduce I/O overhead

Large text logs can become one of the slowest parts of a simulation. Structured events should be recorded once, then rendered into terminal output, dashboards, summaries, or reports as needed.

```python
class EventSink:
    def __init__(self, *, min_importance: Importance) -> None:
        self.min_importance = min_importance

    def accept(self, event: UserFacingEvent) -> bool:
        return event.importance >= self.min_importance
```

Implementation tasks:

- Replace scattered `print()` calls with event emission.
- Add `quiet`, `events`, `progress`, and `full` output modes.
- Add log rotation or per-run output directories.
- Ensure low-importance trace events can be disabled for overnight batches.
- Write progress to a compact status file rather than forcing users to inspect huge logs.

Acceptance criteria:

- A 10,000-tick benchmark can run in quiet mode without generating massive logs.
- Event JSONL and human-readable logs can be configured independently.
- The same simulation state hash is produced regardless of terminal verbosity.

### P5. Integrate adaptive spatial indexing as the first major algorithmic win

Item 17 defines the basic spatial index. The optimization workstream should make it measurable and mandatory for proximity queries.

```python
from collections.abc import Iterable


def nearby_inhabitants(index: SpatialIndex, inhabitant, radius: int) -> Iterable[object]:
    return (
        other for other in index.within(inhabitant.r, inhabitant.c, radius)
        if other is not inhabitant
    )
```

Implementation tasks:

- Identify every proximity query: social interaction, trade, combat, disease, local rumors, religious influence, mating, migration, and rescue/help behavior.
- Replace direct population scans with `SpatialIndex` queries.
- Rebuild the index once per tick after movement, not inside each query.
- Benchmark low, medium, and high population cases.

Acceptance criteria:

- Proximity systems no longer scan the entire population unless explicitly justified.
- Benchmarks show better scaling at high population.
- Results remain deterministic for the same seed.

### P6. Vectorize simple numeric state with NumPy where appropriate

NumPy is useful for repeated numeric updates that do not need rich Python object behavior.

Good candidates:

- Hunger, energy, health, age, morale, cooldowns, fertility, and simple resource counters.
- Per-tile resource regeneration.
- Population-wide thresholds such as starvation, illness, or exhaustion masks.

Example:

```python
import numpy as np


def update_needs(hunger: np.ndarray, energy: np.ndarray) -> None:
    hunger += 1.0
    energy -= 0.5
```

Mask example:

```python
starving = hunger >= 100.0
health[starving] -= 2.0
```

Implementation tasks:

- Do not rewrite the entire simulation immediately.
- Start with one isolated numeric subsystem.
- Keep stable ID mapping between inhabitants and array rows.
- Add tests proving object-state and array-state views stay consistent.

Acceptance criteria:

- At least one numeric subsystem runs from arrays with no behavior change.
- Tests cover creation, death/removal, serialization, checkpoint restore, and deterministic replay.
- Benchmarks show whether the vectorization actually helped.

### P7. Compile numeric hot paths with Numba or Cython only after profiling

Compilation is worthwhile only when the hot path is numeric, stable, and difficult to vectorize cleanly. Prefer Numba first for experiments because it has a lower integration cost.

```python
from numba import njit
import numpy as np


@njit
def update_needs_compiled(hunger: np.ndarray, energy: np.ndarray) -> None:
    for i in range(hunger.shape[0]):
        hunger[i] += 1.0
        energy[i] -= 0.5
```

Good candidates:

- Numeric resource diffusion/regeneration.
- Hunger/energy/health updates.
- Tile scoring.
- Simple path cost calculations.
- Batch combat math.

Poor candidates:

- Python objects and dataclasses.
- Dictionaries of memories.
- Strings, generated text, beliefs, rumors, and narrative rendering.
- Logging and event formatting.

Acceptance criteria:

- The target function is already identified as a top hotspot.
- A pure Python reference implementation remains for correctness tests.
- The compiled implementation produces identical outputs for fixed inputs.
- The dependency is optional or clearly documented in installation instructions.

### P8. Parallelize experiments across seeds before parallelizing one world

The safest use of many CPU cores is independent process-level parallelism: seed 1, seed 2, baseline, no-antistag, parameter sweeps, and scenario batches.

```python
from multiprocessing import Pool


def run_case(case: dict) -> dict:
    return run_simulation(
        seed=case["seed"],
        ticks=case["ticks"],
        config=case["config"],
    )


if __name__ == "__main__":
    cases = [
        {"seed": seed, "ticks": 10000, "config": "baseline"}
        for seed in [1, 2, 3, 4, 5]
    ]
    with Pool() as pool:
        results = pool.map(run_case, cases)
```

Implementation tasks:

- Make each run write to its own output directory.
- Include seed, config hash, Git revision, and start time in the manifest.
- Avoid shared writable state between workers.
- Add a top-level batch progress file.

Acceptance criteria:

- Running five seeds in parallel produces the same per-seed final hashes as running them serially.
- One failed seed does not corrupt the other seed outputs.
- The batch runner can resume or skip already validated runs.

### P9. Treat intra-tick parallelism as advanced and deterministic-only

Updating inhabitants in parallel inside one world can be fast, but it can also create race conditions if agents mutate shared world state directly. Use a two-phase design: compute proposed changes in parallel, then apply them in a stable serial commit order.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProposedMutation:
    priority: tuple[int, str]
    target_id: str
    field: str
    value: object


def commit_mutations(mutations: list[ProposedMutation]) -> None:
    for mutation in sorted(mutations, key=lambda item: item.priority):
        apply_mutation(mutation)
```

Implementation tasks:

- Remove shared global RNG calls from parallel workers.
- Use deterministic named streams or per-agent streams.
- Workers return proposed mutations, not direct state changes.
- Commit in deterministic order.

Acceptance criteria:

- Serial and parallel modes have a documented reproducibility contract.
- Final-state hashes match when the contract says they should match.
- If parallel mode intentionally changes ordering, the manifest clearly records that.

### P10. Introduce a hybrid entity/component architecture when object overhead becomes limiting

A full ECS rewrite is not necessary at first. Use a hybrid model: keep rich Python objects for identity, memories, beliefs, and narrative state, while moving simple repeated stats into dense tables or arrays.

Object-heavy style:

```python
class Inhabitant:
    def __init__(self, inhabitant_id: str) -> None:
        self.id = inhabitant_id
        self.health = 100.0
        self.hunger = 0.0
        self.energy = 100.0
```

Hybrid style:

```python
@dataclass
class InhabitantRecord:
    inhabitant_id: str
    row: int


health = np.full(max_inhabitants, 100.0)
hunger = np.zeros(max_inhabitants)
energy = np.full(max_inhabitants, 100.0)
```

Implementation tasks:

- Add stable entity IDs.
- Add an ID-to-row table for array-backed components.
- Start with `NeedsComponent` or `VitalsComponent` only.
- Keep serialization explicit and versioned.
- Defer full ECS until benchmarks show object overhead dominates.

Acceptance criteria:

- Existing gameplay behavior remains unchanged.
- Removed/dead inhabitants do not leave invalid active rows.
- Checkpoint restore recreates the same ID-to-row mappings.
- Tests cover adding, removing, querying, and serializing entities.

### P11. Reduce memory churn and repeated allocations

Even when CPU time looks acceptable, repeated allocation can slow long runs and increase garbage collection pauses.

Implementation tasks:

- Reuse temporary lists for per-tick scratch work where safe.
- Avoid creating large intermediate dictionaries inside inner loops.
- Cache derived values that only change once per tick.
- Avoid sorting large collections repeatedly when a bounded heap or cached ranking is enough.
- Store immutable lookup tables for terrain, resources, and constants.

Acceptance criteria:

- Profiling notes identify at least one allocation-heavy path.
- The optimized path is easier or equally easy to reason about.
- Memory usage over long runs is stable, or growth is explained by retained history/events.

### P12. Add performance budgets and regression gates

Item 18 compares benchmark output to a baseline. Extend that into a small performance budget system so optimization does not regress silently.

Example benchmark fields:

```json
{
  "scenario": "baseline",
  "population": 500,
  "ticks": 10000,
  "mean_ms_per_tick": 1.42,
  "p95_ms_per_tick": 2.10,
  "events_per_tick": 0.8,
  "bytes_written_per_tick": 95
}
```

Implementation tasks:

- Record benchmark JSON after representative runs.
- Compare by ratio rather than absolute time.
- Track `mean_ms_per_tick`, `p95_ms_per_tick`, output bytes per tick, and peak memory.
- Keep machine-specific raw results out of strict correctness tests unless normalized.

Acceptance criteria:

- A regression warning triggers when a benchmark is more than the configured tolerance slower.
- Output volume regressions are detected separately from CPU regressions.
- Performance results are attached to optimization PRs or build records.

### P13. Keep optimization choices visible in manifests

Optimizations should be traceable. A result should say whether it used spatial indexing, vectorized needs, compiled hot paths, process-level parallelism, or deterministic intra-tick parallelism.

```json
{
  "optimization_flags": {
    "spatial_index": true,
    "vectorized_needs": false,
    "compiled_needs": false,
    "parallel_batch": true,
    "parallel_inhabitants": false
  }
}
```

Acceptance criteria:

- Every run manifest records optimization flags.
- Experimental comparisons refuse to compare incompatible modes unless the user explicitly allows it.
- Final evidence reports include relevant optimization flags.

## Recommended delivery sequence

### Milestone A: Control and observation

Implement items 1–8: pause/step, checkpoints, speed, verbosity, importance, timeline, and inspectors.

### Milestone B: Historical exploration

Implement items 9–14: graph/map layers, replay, bookmarks, presets, and dry-run previews.

### Milestone C: scale and reproducibility

Implement items 15–21 plus optimization tasks P1–P5 and P12–P13: RNG streams, deterministic parallelism, spatial indexing, regression comparison, run comparison, ETA, disk guards, profiling, complexity audits, logging reduction, and performance manifests.

### Milestone D: polished simulation experience

Implement items 22–25 plus optimization tasks P6–P11 as needed: interventions, accessibility, persistent legends, final evidence-backed storytelling, selective NumPy vectorization, optional compiled hot paths, seed-level parallel batches, deterministic intra-tick parallelism, hybrid ECS/data-oriented storage, and memory-churn reduction.

For every item and optimization task, require unit tests, one integration test where applicable, unchanged seeded hashes when the feature is disabled, updated manifests/configuration schemas when applicable, and benchmark evidence for changes in hot paths. Prefer proof of correctness first, then proof of speed.
