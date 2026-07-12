# Output directory layout

## Direct simulator run

The simulator writes relative to its process working directory:

```text
<run-cwd>/
├── data/
│   ├── metrics_<condition>_seed_<N>.csv
│   ├── faction_events_<condition>_seed_<N>.csv
│   ├── beliefs_<condition>_seed_<N>.csv
│   ├── run_summaries.csv
│   └── run_manifest_<condition>_seed_<N>.json
├── logs/                                      # full mode only
├── dashboard_data.json                       # full mode, cadence dependent
├── era_export_<condition>_seed_<N>.txt        # full mode, 50-tick cadence
└── manual_chronicle_<condition>_seed_<N>.txt # full mode, mythology disabled
```

The five files in `data/` are the required structured set. The manifest inventories the other four required artifacts and is atomically published last. Optional files are diagnostic and do not make a run valid.

Direct runs do not enforce an empty root. Reusing a directory can truncate per-run CSVs and replace the manifest while appending another row to `run_summaries.csv`, which strict validation rejects. Use a new directory per run.

## Generic batch root

```text
<output-root>/
├── experiment_manifest.json
├── run_index.csv
└── <condition>/
    └── seed_<N>/
        ├── data/
        │   └── <five required simulator artifacts>
        ├── runner_stderr.txt
        └── runner_stdout.txt
```

- `experiment_manifest.json` is the batch operational record.
- `run_index.csv` is a derived convenience projection.
- Each seed directory is the child working directory.
- `runner_stderr.txt` is retained when stderr is nonempty.
- `runner_stdout.txt` is retained only for unsuccessful children with stdout.

The current runner accepts only an absent or truly empty ordinary root. It rejects symlinks and every nonempty root without mutation.

## Authority boundaries

| Location | Authority |
| --- | --- |
| Per-cell `data/` plus valid run manifest | Canonical engineering evidence set |
| Batch manifest | Operational dispatch/result record; not independent scientific proof |
| Run index | Derived convenience file |
| Raw logs, dashboard, chronicles | Diagnostic |
| RA tracker files | Optional and unvalidated |
| Analysis tables and figures | Derived; trace back to validated cells |

See [artifact catalog](artifact-catalog.md) for schemas and [identifying valid runs](identifying-valid-runs.md) for acceptance rules.

## Implementation evidence

- Direct producers: `src/thalren_vale/metrics.py`, `src/thalren_vale/reproducibility.py`, `src/thalren_vale/sim.py`.
- Batch layout: `run_experiments.py`.
- Validation paths: `src/thalren_vale/artifact_validation.py::artifact_paths`.
- Tests: `tests/test_log_modes.py`, `tests/test_experiment_runner.py`.
