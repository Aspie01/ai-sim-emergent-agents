# Codex Post-Experiment Handoff

## Status

The full core replication experiment completed and validates.

Command run:

```bash
python run_experiments.py --plan experiments_replication_v1.json --verify
```

Result:

```text
✓ All expected outputs are present and valid.
```

Validated final dataset:

- `baseline`: 5 seeds × 10,000 ticks
- `no_antistag`: 5 seeds × 10,000 ticks
- `no_combat`: 5 seeds × 10,000 ticks
- Total: 15/15 final runs valid

No full 10,000-tick rerun is currently needed.

## Key result summary

Research framing:

> How do anti-stagnation mechanisms and combat affect long-horizon persistence, viability, population regulation, and computational tractability in Thalren Vale?

Condition means across five seeds:

| Condition | Mean final population | Final population range | Mean final factions | Mean elapsed | Mean output | Mean raw text |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 51.6 | 29-73 | 5.2 | 2,279.4s | 0.134 GiB | 0.131 GiB |
| no_antistag | 6.8 | 2-14 | 1.0 | 2,171.9s | 0.101 GiB | 0.099 GiB |
| no_combat | 507.8 | 415-589 | 213.4 | 46,263.4s | 12.398 GiB | 12.309 GiB |

Interpretation:

- Anti-stagnation mechanisms are important for long-horizon viability. Removing them drives the system toward near-extinction across all seeds.
- Combat appears to act as a population/faction pressure valve. Removing combat allows much higher populations and hundreds of factions to persist.
- No-combat is dramatically less tractable in this run set, but the cause is not yet isolated. It produced enormous raw text logs, so logging overhead must be measured before claiming the slowdown is caused by emergent complexity alone.

## Generated files and tables

New analysis and documentation files:

- `analyze_core_replication.py`
- `EXPERIMENT_COMPLETION_REPORT.md`
- `SUPERSEDED_ATTEMPTS_CLEANUP_PLAN.md`
- `LOGGING_ABLATION_PLAN.md`
- `CODEX_POST_EXPERIMENT_HANDOFF.md`

Generated analysis tables:

- `experiment_runs/core-replication-v1/analysis/run_level_summary.csv`
- `experiment_runs/core-replication-v1/analysis/condition_summary.csv`
- `experiment_runs/core-replication-v1/analysis/paired_seed_comparisons.csv`
- `experiment_runs/core-replication-v1/analysis/paired_seed_comparison_summary.csv`
- `experiment_runs/core-replication-v1/analysis/event_type_counts.csv`
- `experiment_runs/core-replication-v1/analysis/largest_files.csv`
- `experiment_runs/core-replication-v1/analysis/superseded_attempts.csv`
- `experiment_runs/core-replication-v1/analysis/analysis_manifest.json`

No plots were generated in this pass. The existing plotting script targets older flat `results.csv` / `run_event_summary.csv` inputs, not the nested core replication layout.

## Dataset suitability for a first paper or pilot paper

Suitable for a first pilot paper: yes, with caveats.

Strengths:

- All 15 final condition/seed runs validate.
- Shared seeds support paired condition comparisons.
- Each run has metrics, events, beliefs, run summary, run manifest, and state hash.
- The effect sizes are large and directionally clear.

Caveats:

- Only five seeds per condition; keep statistical claims modest.
- Experiment manifests record a dirty worktree. For stronger archival/paper provenance, rerun from a clean tagged commit under a new experiment ID.
- No-combat computational tractability is confounded by logging volume until the logging ablation is run.
- Three source `run_summaries.csv` files contain one superseded earlier row; the generated analysis tables use only the final row.

## Rerun guidance

Do not rerun `core-replication-v1` unless verification later fails or a source artifact is intentionally cleaned and needs revalidation.

No immediate reruns are needed for the current pilot result.

Recommended future reruns:

1. Optional clean-provenance rerun: repeat the same plan from a clean tagged commit with a new experiment ID, such as `core-replication-v2`.
2. Logging ablation: short no-combat seed 1 runs at 100, 250, 500, and 1000 ticks after a `--log-mode` switch is implemented.
3. Larger-N replication only after logging and performance issues are understood.

## Logging bottleneck findings

Total final output:

- `67,821,097,590` bytes
- `63.163` GiB
- `du -sh experiment_runs/core-replication-v1` reports `64G`

Largest files are no-combat text logs/manual chronicles:

- `no_combat/seed_3/logs/run_no_combat_seed_3_20260707_145205.txt`: `10.723` GiB
- `no_combat/seed_2/logs/run_no_combat_seed_2_20260706_231536.txt`: `10.228` GiB
- `no_combat/seed_1/logs/run_no_combat_seed_1_20260706_104017.txt`: `8.107` GiB
- `no_combat/seed_5/logs/run_no_combat_seed_5_20260709_040359.txt`: `6.270` GiB
- `no_combat/seed_1/manual_chronicle_no_combat_seed_1.txt`: `5.209` GiB

Conclusion: text logging is likely a major bottleneck, but not proven as the sole cause. See `LOGGING_ABLATION_PLAN.md`.

## Superseded attempts and cleanup recommendations

Final validated outputs should not be deleted.

Safe cleanup candidates after explicit approval:

- `experiment_runs/core-replication-v1/no_combat/seed_1/runner_stderr.txt`
- `experiment_runs/core-replication-v1/no_combat/seed_2/runner_stderr.txt`
- `experiment_runs/core-replication-v1/no_combat/seed_3/runner_stderr.txt`
- `experiment_runs/core-replication-v1/no_combat/seed_4/runner_stderr.txt`
- `experiment_runs/core-replication-v1/no_combat/seed_5/runner_stderr.txt`

These are stale timeout markers from superseded no-combat attempts. They are not final output artifacts.

Non-delete cleanup candidates:

- `baseline/seed_3/data/run_summaries.csv`
- `no_antistag/seed_2/data/run_summaries.csv`
- `no_antistag/seed_4/data/run_summaries.csv`

Each contains one superseded earlier summary row before the final validated row. The analysis tables already use the final row only. If cleaning source artifacts, back up and rewrite these files; do not delete them.

Full dry-run cleanup details are in `SUPERSEDED_ATTEMPTS_CLEANUP_PLAN.md`.

## Code changes made in this pass

- Added `analyze_core_replication.py`, a nested-layout analysis script that streams metrics/events and stats file sizes without loading multi-GB text logs.
- Updated `run_experiments.py` to classify outcomes explicitly:
  - `completed`
  - `wall_clock_limit`
  - `exception`
  - `invalid_output`
  - `cancelled`
  - `superseded`
- Updated `tests/test_experiment_runner.py` for the explicit result terminology.

Validation run:

```bash
python -m pytest tests/test_experiment_runner.py -q
```

Result:

```text
4 passed in 0.12s
```

## Exact next development steps

1. Review `EXPERIMENT_COMPLETION_REPORT.md` for factual wording and publication framing.
2. Decide whether to keep or delete the stale no-combat `runner_stderr.txt` timeout markers listed in `SUPERSEDED_ATTEMPTS_CLEANUP_PLAN.md`.
3. Implement `--log-mode full|summary|metrics_only` in `src/thalren_vale/sim.py`.
4. Add smoke tests for each logging mode.
5. Run the short logging ablation described in `LOGGING_ABLATION_PLAN.md`.
6. If logging dominates runtime, make `metrics_only` or `summary` the default for experiment plans and reserve full logs for diagnostic runs.
7. Add nested-layout plotting support using `experiment_runs/core-replication-v1/analysis/run_level_summary.csv` and `event_type_counts.csv`.
8. If paper-grade provenance is required, commit the current fixes, tag a clean revision, and run `core-replication-v2` from that clean state.
