# Stale, Historical, and Superseded Data

The repository contains current code beside historical plans, logs, pilot
outputs, derived analyses, and two severely outdated JSON files. Presence in
the repository is not proof that an artifact describes the current revision.

## Classification rules

| Classification | Meaning | Safe use |
| --- | --- | --- |
| Current authoritative | Complete current structured run set that passes the required validator and matches its declared use | Engineering interpretation within the validated contract |
| Current but experimental | Current output from an implemented engineering-only feature or optional observer | Development and diagnostics, not unregistered research claims |
| Historical evidence | Output tied to an older documented revision/design | Historical context only; keep provenance and tier separate |
| Derived | Table, figure, report, or narrative computed from other artifacts | Use only with identified, validated inputs and transformation |
| Stale | Does not match the plan, code, config, schema, environment, plugin policy, or question now being evaluated | Do not substitute for current evidence |
| Superseded | Explicitly replaced by an authoritative immutable selection record | Current runner cannot establish this state |
| Obsolete/misleading | Known not to represent current behavior | Do not use as evidence, defaults, fixtures, or baselines |

## Known obsolete files

The following files are severely outdated:

- `qtable_pop_300_300.json` — stale and non-authoritative.
- `pop_equilibrium_summary.json` — stale and non-authoritative.

They must not be used as current evidence, defaults, baselines, fixtures, or
documentation sources. Their presence is historical only. Do not delete or
migrate them without explicit owner authorization.

## Core Replication V1

`experiments_replication_v1.json` and
`experiment_runs/core-replication-v1/` belong to historical pilot work. Keep
V1 separate from any future V2 data. In particular, historical V1
`no_combat` disabled formal combat while raids remained enabled; it is not a
hostility-free condition and is not a canonical V2 identifier.

Historical V1 analysis tables and figures under its `analysis/` directory are
derived products. They do not become current merely because plotting scripts
can still read them.

## Other generated roots

Repository-root `data/`, `logs/`, logging-ablation output, raid-control pilot
output, and other `experiment_runs/` directories should be treated according
to their own recorded provenance. This handbook did not rescan or revalidate
historical generated output. Do not infer completion or validity from directory
names.

Direct simulator runs overwrite condition/seed metrics, events, and beliefs in
the same working directory and append to `run_summaries.csv`. Reusing a working
directory can therefore produce stale mixtures or multiple summary rows that
strict validation rejects. Use a new temporary or attempt directory for each
engineering run.

## Derived legacy tools

The following scripts remain useful for explicitly historical or diagnostic
work, but their output is not canonical current evidence:

- `parse_logs.py`: regex/TUI parsing from narrative `run_*.txt` into
  `results.csv`;
- `analyze_logs.py`: regex-derived event counts and narrative report;
- `extract_stats.py`: hard-coded statistics from `results.csv` and
  `run_event_summary.csv`;
- `generate_figures.py`: hard-coded 100-run publication figures;
- `plot_core_replication.py`: V1-specific analysis plots;
- `analyze_ra.py`: exploratory RA tracker analysis;
- `build_pdf.py`: publication rendering, not evidence validation.

Prefer structured CSVs plus strict validation for current engineering runs.

## Supersession is not implemented

The generic runner declares a `superseded` result constant, and historical
analysis may contain a `superseded_attempts.csv`, but the current runner has no:

- immutable attempt ID/directory;
- append-only attempt ledger;
- selected-attempt field;
- revocation or supersession transaction;
- rule proving exactly one authoritative attempt per cell.

Accordingly, no current batch file can authoritatively mark one same-seed rerun
as superseding another. Preserve each run separately and describe any manual
selection explicitly as manual, nonauthoritative curation.

## Detecting staleness

For each proposed use, compare:

1. exact plan bytes and hash;
2. condition, seed, requested horizon, and effective controls;
3. schema versions and metrics timing contract;
4. commit, tag, and clean-tree status;
5. environment and dependency identity;
6. plugin policy and inventory;
7. terminal status, writer health, inventory, and deep validation;
8. evidence tier and analysis version.

The current run manifest records only part of this set. Missing provenance can
leave an artifact schema-valid but non-V2-ready. Do not fill missing values by
inference from nearby files or README prose.

## Preservation rules

- Never overwrite or delete validated or potentially evidence-bearing output
  during routine development.
- Never pool V1 and future V2.
- Never count retries, repeated horizons, diagnostic probes, or manually
  selected attempts as new seed replicates.
- Preserve incomplete, failed, cancelled, timed-out, and invalid attempts as
  audit/tractability material when they matter.
- Store new bounded developer output outside canonical research roots.
- Treat logs and narratives as diagnostics, not substitutes for structured
  artifacts.

## Current V2 status

Core Replication V2 has not run. S0, S1, P1, P2, and Full are unauthorized.
Immutable attempt and supersession infrastructure is **Planned, not
implemented**. No current artifact should be labeled V2 evidence.

## Implementation evidence

- Runner limitations: [`run_experiments.py`](../../../run_experiments.py)
- Active unexecuted plan:
  [`CORE_REPLICATION_V2_PLAN.md`](../../../CORE_REPLICATION_V2_PLAN.md)
- Legacy tools: [`parse_logs.py`](../../../parse_logs.py),
  [`analyze_logs.py`](../../../analyze_logs.py),
  [`plot_core_replication.py`](../../../plot_core_replication.py)
- Related: [Artifact catalog](artifact-catalog.md),
  [Identifying valid runs](identifying-valid-runs.md)
- Review method: current source and directory names only; no historical output
  content scan or experiment execution was performed.
