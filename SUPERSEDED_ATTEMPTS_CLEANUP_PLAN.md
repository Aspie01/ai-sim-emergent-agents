# Superseded Attempts Cleanup Plan

This is a dry-run cleanup plan for `experiment_runs/core-replication-v1/`.

No files have been deleted. Final validated outputs must be preserved unless a separate cleanup step is explicitly approved.

## Final validated dataset

The final research dataset is the 15 validated condition/seed runs listed in `EXPERIMENT_COMPLETION_REPORT.md` and `experiment_runs/core-replication-v1/analysis/run_level_summary.csv`.

Verification command:

```bash
python run_experiments.py --plan experiments_replication_v1.json --verify
```

Verification result:

```text
✓ All expected outputs are present and valid.
```

Final validated run directories:

- `experiment_runs/core-replication-v1/baseline/seed_1/`
- `experiment_runs/core-replication-v1/baseline/seed_2/`
- `experiment_runs/core-replication-v1/baseline/seed_3/`
- `experiment_runs/core-replication-v1/baseline/seed_4/`
- `experiment_runs/core-replication-v1/baseline/seed_5/`
- `experiment_runs/core-replication-v1/no_antistag/seed_1/`
- `experiment_runs/core-replication-v1/no_antistag/seed_2/`
- `experiment_runs/core-replication-v1/no_antistag/seed_3/`
- `experiment_runs/core-replication-v1/no_antistag/seed_4/`
- `experiment_runs/core-replication-v1/no_antistag/seed_5/`
- `experiment_runs/core-replication-v1/no_combat/seed_1/`
- `experiment_runs/core-replication-v1/no_combat/seed_2/`
- `experiment_runs/core-replication-v1/no_combat/seed_3/`
- `experiment_runs/core-replication-v1/no_combat/seed_4/`
- `experiment_runs/core-replication-v1/no_combat/seed_5/`

Do not delete any final run directory, `data/` directory, final `logs/run_*.txt`, final `manual_chronicle_*.txt`, final `dashboard_data.json`, or final `era_export_*.txt` as part of this cleanup.

## Delete candidates after approval

These files are stale timeout markers from earlier no-combat attempts. Each final no-combat run has a newer valid run manifest, final run summary, metrics CSV, event CSV, and belief CSV.

| Candidate | Size | Why safe to delete after approval |
|---|---:|---|
| `experiment_runs/core-replication-v1/no_combat/seed_1/runner_stderr.txt` | 211 bytes | Stale `wall_clock_limit` marker from a superseded 20,000-second timeout attempt. |
| `experiment_runs/core-replication-v1/no_combat/seed_2/runner_stderr.txt` | 211 bytes | Stale `wall_clock_limit` marker from a superseded 20,000-second timeout attempt. |
| `experiment_runs/core-replication-v1/no_combat/seed_3/runner_stderr.txt` | 211 bytes | Stale `wall_clock_limit` marker from a superseded 20,000-second timeout attempt. |
| `experiment_runs/core-replication-v1/no_combat/seed_4/runner_stderr.txt` | 211 bytes | Stale `wall_clock_limit` marker from a superseded 20,000-second timeout attempt. |
| `experiment_runs/core-replication-v1/no_combat/seed_5/runner_stderr.txt` | 211 bytes | Stale `wall_clock_limit` marker from a superseded 20,000-second timeout attempt. |

Dry-run deletion command to review before executing:

```bash
printf '%s\n' \
  experiment_runs/core-replication-v1/no_combat/seed_1/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_2/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_3/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_4/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_5/runner_stderr.txt
```

Actual deletion should only happen after approval. If approved:

```bash
rm \
  experiment_runs/core-replication-v1/no_combat/seed_1/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_2/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_3/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_4/runner_stderr.txt \
  experiment_runs/core-replication-v1/no_combat/seed_5/runner_stderr.txt
```

Then re-run:

```bash
python run_experiments.py --plan experiments_replication_v1.json --verify
python analyze_core_replication.py --plan experiments_replication_v1.json --root experiment_runs/core-replication-v1
```

Expected effect: verification should still pass. The analysis table `superseded_attempts.csv` should no longer list these five runner markers after regeneration.

## Non-delete cleanup candidates

Three final run summary files contain one superseded row before the final validated row:

| File | Superseded content | Safe action |
|---|---:|---|
| `experiment_runs/core-replication-v1/baseline/seed_3/data/run_summaries.csv` | 1 earlier summary row | Do not delete the file. If cleanup is approved, back it up and rewrite it to keep only the header and final row. |
| `experiment_runs/core-replication-v1/no_antistag/seed_2/data/run_summaries.csv` | 1 earlier summary row | Do not delete the file. If cleanup is approved, back it up and rewrite it to keep only the header and final row. |
| `experiment_runs/core-replication-v1/no_antistag/seed_4/data/run_summaries.csv` | 1 earlier summary row | Do not delete the file. If cleanup is approved, back it up and rewrite it to keep only the header and final row. |

Current analysis already ignores the earlier rows and uses the final row only. Rewriting these source files is optional and should be treated as data curation, not raw artifact deletion.

## No other superseded artifacts identified

The inventory found:

- One final log file per condition/seed.
- One final run manifest per condition/seed.
- One final metrics CSV per condition/seed.
- One final event CSV per condition/seed.
- One final beliefs CSV per condition/seed.
- No `run_manifest_*.error.txt` files.
- No `runner_stdout.txt` files.

The very large no-combat log and manual chronicle files appear to be final validated run artifacts, not superseded attempts. They should not be deleted under this plan.
