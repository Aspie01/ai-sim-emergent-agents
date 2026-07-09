# Codex Logging and Plots Handoff

## What changed

Implemented log modes:

```text
--log-mode full|summary|metrics_only|off
```

Files changed or added:

- `src/thalren_vale/config.py`
  - Added `VALID_LOG_MODES`.
  - Added `SimulationConfig.log_mode`.
  - Validates CLI log mode.
- `src/thalren_vale/reproducibility.py`
  - Added manifest fields:
    - `log_mode`
    - `required_outputs`
    - `optional_outputs`
  - Excluded `log_mode` from the behavioral state hash.
- `src/thalren_vale/sim.py`
  - Added `--log-mode`.
  - Added output policy helpers.
  - Added filtered stdout for lower-output modes.
  - Gated full raw log, per-tick render, dashboard snapshots, manual chronicles, era exports, progress text, and final text reports by mode.
  - Kept structured metrics/events/beliefs/run summaries/manifests active.
- `tests/test_log_modes.py`
  - Added smoke tests for all log modes.
  - Verifies required structured artifacts exist.
  - Verifies non-full modes suppress raw text artifacts.
  - Verifies 5-tick state hashes match across modes.
- `run_logging_ablation.py`
  - Added short no-combat logging ablation runner.
  - Added `--collect-existing` mode to regenerate CSV/report from completed run directories without rerunning expensive cases.
- `plot_core_replication.py`
  - Added nested-layout plotting from `core-replication-v1/analysis/*.csv`.
- `cleanup_core_replication.py`
  - Added dry-run-only cleanup inventory scanner.
- `LOGGING_ABLATION_REPORT.md`
- `RAID_SEMANTICS_AUDIT.md`
- `CORE_REPLICATION_PLOTS_REPORT.md`
- `CODEX_LOGGING_AND_PLOTS_HANDOFF.md`

Generated artifacts:

- `experiment_runs/logging-ablation-v1/logging_ablation_results.csv`
- `experiment_runs/logging-ablation-v1/logging_ablation_summary.csv`
- `experiment_runs/logging-ablation-v1/LOGGING_ABLATION_REPORT.md`
- `experiment_runs/core-replication-v1/analysis/figures/*.png`
- `experiment_runs/core-replication-v1/analysis/figures/condition_plot_summary_table.csv`
- `experiment_runs/core-replication-v1/analysis/figures/event_type_composition_table.csv`
- `experiment_runs/core-replication-v1/analysis/CORE_REPLICATION_PLOTS_REPORT.md`
- `experiment_runs/core-replication-v1/analysis/cleanup_dry_run.csv`

## Tests run and results

Targeted tests run during implementation:

```bash
python -m pytest tests/test_log_modes.py -q
```

Result:

```text
9 passed
```

Additional targeted tests:

```bash
python -m pytest tests/test_log_modes.py tests/test_config.py tests/test_reproducibility.py -q
```

Result:

```text
23 passed
```

Final full validation should be checked in the current terminal state after reading this handoff.

## Logging ablation findings

Completed rows:

- no-combat
- seed `1`
- ticks `100`, `250`, `500`
- modes `full`, `summary`, `metrics_only`, `off`

The requested 1000-tick cases were not run. The 500-tick full case took `963.28s`, and the user interrupted the prior waiting loop because it consumed too much context. Running 1000-tick full should require explicit approval.

Key results:

| Ticks | Full raw text | Lower-output raw text | Full elapsed | Best lower-output elapsed |
|---:|---:|---:|---:|---:|
| 100 | 4.221 MiB | 0 MiB | 10.34s | 8.70s |
| 250 | 42.159 MiB | 0 MiB | 129.13s | 94.74s |
| 500 | 263.125 MiB | 0 MiB | 963.28s | 655.76s |

Interpretation:

- Raw text logging is clearly a major disk/output bottleneck.
- Lower-output modes reduce runtime, but not enough to explain the whole no-combat slowdown.
- Structured event volume and state complexity remain significant.

## Same-state warning

The ablation is not a clean same-state performance comparison.

Although the 5-tick smoke test produced identical state hashes across log modes, the 100/250/500 no-combat ablation rows did not. A follow-up probe also found that two separate 100-tick no-combat `metrics_only` runs with the same seed produced different hashes.

Conclusion: longer no-combat runs currently have broader nondeterminism. Fix or isolate this before making publication-grade timing claims.

## Should metrics_only/summary become the experiment default?

Yes for future long experiments:

- Use `metrics_only` as the default for research batches.
- Use `summary` when a human-readable final report is needed.
- Use `full` only for diagnostics, demos, and short runs.

Reason: `metrics_only` preserves structured metrics/events/beliefs/manifests while preventing giant raw text logs. It does not solve all runtime cost, but it prevents the multi-GB-per-seed text explosion.

## Raid semantics finding

See `RAID_SEMANTICS_AUDIT.md`.

Summary:

- Raids are generated in `src/thalren_vale/economy.py`, not `src/thalren_vale/combat.py`.
- `--disable-layer combat` disables formal wars/battles, but does not disable economy-layer raids.
- Raids are combat-adjacent economic/diplomatic events:
  - steal resources from victim territory,
  - add resources to a raider member,
  - add `the_strong_take` belief,
  - increase rivalry/tension,
  - lower reputation,
  - can break treaties,
  - do not directly kill inhabitants.
- In `core-replication-v1`, no-combat produced `5,513,353` raid events out of `5,559,667` total structured events.

Recommendation:

- Do not silently change `--disable-layer combat`.
- Add a separate `--disable-raids` or `--disable-layer raids` switch in a future task.
- Consider reclassifying/metadata-tagging raids as economic/combat-adjacent events.
- Consider aggregating high-frequency raid text output.

## Plots generated

Generated under:

`experiment_runs/core-replication-v1/analysis/figures/`

Files:

- `final_population_by_condition.png`
- `final_factions_by_condition.png`
- `elapsed_time_by_condition.png`
- `output_size_by_condition.png`
- `event_count_by_condition.png`
- `paired_seed_final_population_deltas.png`
- `event_type_composition_by_condition.png`
- `condition_plot_summary_table.csv`
- `event_type_composition_table.csv`

Report:

- `CORE_REPLICATION_PLOTS_REPORT.md`
- `experiment_runs/core-replication-v1/analysis/CORE_REPLICATION_PLOTS_REPORT.md`

## Cleanup recommendations

Dry-run scanner:

```bash
python cleanup_core_replication.py --dry-run
```

Generated:

`experiment_runs/core-replication-v1/analysis/cleanup_dry_run.csv`

Found eight candidates:

- Three `run_summaries.csv` files with one superseded earlier row before the final validated row.
- Five stale no-combat `runner_stderr.txt` timeout markers.

No final validated outputs were deleted.

## Exact next recommended task

Fix or isolate deterministic replay for no-combat longer than trivial smoke tests.

Recommended approach:

1. Add a deterministic replay test for no-combat at 100 ticks using `--log-mode metrics_only`.
2. Run it twice in separate subprocesses with `PYTHONHASHSEED=0`.
3. Compare final manifests, metrics tails, and selected serialized state components.
4. Identify the first divergent tick by adding optional deterministic checkpoint hashes every N ticks.
5. Only after deterministic replay is fixed, rerun the logging ablation at 100/250/500 and decide whether 1000-tick full is worth the cost.
