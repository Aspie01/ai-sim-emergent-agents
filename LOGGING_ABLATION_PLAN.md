# Logging Ablation Plan

Purpose: measure how much of the no-combat slowdown comes from text logging versus simulation-state complexity.

Do not treat the current no-combat slowdown as purely emergent complexity until this ablation is run. The completed core replication proves that no-combat is much slower and much larger on disk, but it does not isolate CPU/state growth from text I/O.

## Current evidence

From `experiment_runs/core-replication-v1/analysis/`:

- No-combat averaged `46,263.4` seconds per 10,000-tick run.
- Baseline averaged `2,279.4` seconds per 10,000-tick run.
- No-combat averaged `12.309` GiB of raw text output per run.
- Baseline averaged `0.131` GiB of raw text output per run.
- No-combat emitted about `84.4×` as many structured events as baseline.
- The largest files are no-combat `logs/run_*.txt` and `manual_chronicle_*.txt` files, up to `10.723` GiB for one full log and `5.209` GiB for one manual chronicle.

Conclusion: text logging is very likely a major bottleneck, but it needs a controlled benchmark.

## Benchmark target

Use a short no-combat benchmark only:

- Condition: no combat
- Seed: `1`
- Tick counts: `100`, `250`, `500`, `1000`
- Replicates: one per tick/mode combination initially
- No full 10,000-tick replication

Record per run:

- `elapsed_seconds`
- `ticks_per_second`
- total output bytes
- raw text bytes
- structured event count
- final population
- final faction count
- peak population
- state hash
- peak RAM

## Required logging modes

The current simulator has full text logging but does not yet expose a clean CLI switch for summary-only or metrics-only logging. Add an explicit logging mode before running the ablation.

Recommended CLI:

```text
--log-mode full|summary|metrics_only
```

Mode semantics:

- `full`: current behavior. Write full per-tick text log, manual chronicle, era export, dashboard JSON, structured metrics/events/beliefs, summary, and manifest.
- `summary`: suppress per-tick display text and manual chronicle growth; keep concise periodic/final status, structured metrics/events/beliefs, summary, and manifest.
- `metrics_only`: suppress full text log, manual chronicle, era export, and dashboard JSON; keep structured metrics/events/beliefs, summary, and manifest.

Avoid a true `off` mode for the first pass unless it still writes a run manifest and enough summary data to compare final population, event count, output size, and state hash.

## Suggested implementation steps

1. Add `--log-mode` to `src/thalren_vale/sim.py`.
2. Keep `full` as the default for backward compatibility.
3. In `summary` and `metrics_only`, avoid assigning `_event_log_fh` to a full log file.
4. In `summary` and `metrics_only`, skip `display.render(...)` per tick or route it to a sink.
5. In `metrics_only`, skip `export_era_data(...)`, `export_to_mythology_file(...)`, and dashboard writes.
6. Keep `MetricsLogger` active in all benchmark modes so structured event counts remain comparable.
7. Include `log_mode` in run configuration and run manifests.
8. Add tests that a 1-tick run in each mode completes and writes the expected artifact set.

## Suggested experiment plan

After `--log-mode` exists, create a short plan such as `experiments_logging_ablation_v1.json` with these 12 runs:

| Condition | Ticks | Extra args |
|---|---:|---|
| `no_combat_full_100` | 100 | `--disable-layer combat --log-mode full` |
| `no_combat_summary_100` | 100 | `--disable-layer combat --log-mode summary` |
| `no_combat_metrics_100` | 100 | `--disable-layer combat --log-mode metrics_only` |
| `no_combat_full_250` | 250 | `--disable-layer combat --log-mode full` |
| `no_combat_summary_250` | 250 | `--disable-layer combat --log-mode summary` |
| `no_combat_metrics_250` | 250 | `--disable-layer combat --log-mode metrics_only` |
| `no_combat_full_500` | 500 | `--disable-layer combat --log-mode full` |
| `no_combat_summary_500` | 500 | `--disable-layer combat --log-mode summary` |
| `no_combat_metrics_500` | 500 | `--disable-layer combat --log-mode metrics_only` |
| `no_combat_full_1000` | 1000 | `--disable-layer combat --log-mode full` |
| `no_combat_summary_1000` | 1000 | `--disable-layer combat --log-mode summary` |
| `no_combat_metrics_1000` | 1000 | `--disable-layer combat --log-mode metrics_only` |

Use `experiment_id: logging-ablation-v1` so the output stays separate from `core-replication-v1`.

## Analysis criteria

For each tick count, compare:

- `full` vs `summary`
- `full` vs `metrics_only`
- output bytes per tick
- elapsed seconds per tick
- event count per tick
- final population and state hash

Interpretation:

- If `metrics_only` is much faster with the same state hash, logging is a major causal bottleneck.
- If `metrics_only` is still slow with similar output size reduction, no-combat state complexity is the dominant bottleneck.
- If state hashes differ by logging mode, the logging switch is perturbing simulation behavior and must be fixed before drawing conclusions.
