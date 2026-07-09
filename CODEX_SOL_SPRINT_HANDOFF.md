# Codex Sol Sprint Handoff

Date: 2026-07-09

Parent revision at start of handoff: `a29e2fa055e8a62e2498352a096094ac2a6d0e62`

Nested LLM-Wiki revision at start of handoff: `43a6a54ac6e3435a5677ee99ef950dd65c96cd1d`

## Outcome

The pilot dataset is now plotted and accompanied by explicit interpretation boundaries. Four logging modes are verified, the seeded nondeterminism underlying the old ablation was fixed, short logging evidence was consolidated, raid semantics were audited, and lightweight results were refreshed in the nested LLM Wiki.

No full 10,000-tick run, long benchmark, raw-log parse, raw-log copy, or final-output deletion occurred.

## Code and test changes

- Verified existing `full`, `summary`, `metrics_only`, and `off` implementations, CLI help, config validation, manifest provenance, optional-output policy, and verifier behavior.
- Added an end-to-end invalid-CLI-mode test.
- Fixed a seeded reproducibility bug in `src/thalren_vale/sim.py`: `_serial_mode` was recorded but ignored, so Layer 1 always launched four workers sharing Python’s global PRNG. Seeded runs now process Layer 1 serially; unseeded interactive runs retain threading.
- Added a regression test that forbids worker-thread construction in serial mode.
- Corrected one stale raid-threshold comment in `src/thalren_vale/economy.py` from `>50` to the existing behavior `>35`. Raid behavior did not change.
- Final parent test result: `43 passed in 3.57s` from `python -m pytest -q`.

## Logging-mode behavior

- `full`: legacy text log, chronicle, era export, dashboard snapshots, per-tick rendering, progress, final report, and structured artifacts.
- `summary`: warnings/errors and final report, with structured artifacts and without raw narrative files.
- `metrics_only`: metrics, events, beliefs, run summary, and manifest; no raw narrative/debug artifacts.
- `off`: no non-fatal text output; required structured artifacts and manifest remain.

The state hash excludes non-behavioral `condition` and `log_mode` keys. A fresh 100-tick no-combat seed-1 probe produced the same 734 events, final population 226, 61 factions, and state hash in all modes:

`f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04`

## Logging ablation

Revalidated the 12 existing 100/250/500-tick cells with:

```bash
python run_logging_ablation.py --ticks 100,250,500 --collect-existing
```

The 1,000-tick cells were intentionally not run. The 500-tick cells took 655.76–963.28 seconds each, and a 1,000-tick no-combat cell was likely to exceed the sprint’s roughly 20-minute boundary.

At 500 ticks:

| Mode | Elapsed | Total output | Raw text |
|---|---:|---:|---:|
| full | 963.28s | 266.088 MiB | 263.125 MiB |
| summary | 695.63s | 2.626 MiB | 0 MiB |
| metrics_only | 764.63s | 2.650 MiB | 0 MiB |
| off | 655.76s | 2.707 MiB | 0 MiB |

These historical cells predate the serial fix and diverged in state, so their disk evidence is strong while their runtime comparison is suggestive. The post-fix 100-tick same-state probe took 10.214 seconds in `full` and 8.681–8.736 seconds in lower-output modes.

Recommendation: use `metrics_only` for research runs, `summary` when a human-readable terminal summary is needed, and `full` only for short diagnostics.

Artifacts:

- `LOGGING_ABLATION_REPORT.md`
- `experiment_runs/logging-ablation-v1/logging_ablation_results.csv`
- `experiment_runs/logging-ablation-v1/logging_ablation_summary.csv`

## Raid semantics

Raids are economy-generated, combat-adjacent coercive events. They remove victim-tile resources, transfer loot, reinforce an aggressive belief, increase rivalry, lower reputation, and can break treaties. They do not directly damage health, kill inhabitants, start wars, remove territory, or dissolve factions.

`--disable-layer combat` suppresses formal combat resolution, not raids. In no-combat, raids were 5,513,353 of 5,559,667 structured events (99.167%). This is not obvious parser duplication: typed messages are excluded from legacy reclassification, and a short-run duplicate-key check found none.

Do not silently change existing combat semantics. Add a separate raid control and test a short 2×2 combat × raids design. See `RAID_SEMANTICS_AUDIT.md`.

## Core-replication plots

Ran:

```bash
python plot_core_replication.py
```

Generated under `experiment_runs/core-replication-v1/analysis/figures/`:

- final population by condition;
- final factions by condition;
- elapsed time by condition;
- output size by condition;
- event count by condition;
- paired baseline/no-antistag and baseline/no-combat final-population deltas;
- event-type composition by condition;
- two lightweight plot tables.

All seven PNGs validate and are under 64 KB. Paired mean final-population deltas are `-44.8` for baseline → no-antistag and `+456.2` for baseline → no-combat, with consistent direction across all five seeds. See `CORE_REPLICATION_PLOTS_REPORT.md`.

## LLM-Wiki refresh

Only lightweight evidence was copied into `LLM-Wiki/content/ai-simulation/thalren-vale/`:

- refreshed logging ablation and raid audit pages;
- added `engineering/logging-ablation-results.md`;
- refreshed the core plots report;
- copied two logging-ablation CSVs;
- copied seven generated PNG figures;
- updated engineering/evidence/core-experiment indexes and the ingest manifest.

Logging ablation and raid semantics are marked `needs-audit`. Core-replication plots remain `pilot-supported`. No LLM-Wiki application code, raw logs, chronicles, run directories, or files over 50 MB were copied.

## Remaining caveats

- `core-replication-v1` remains pilot-supported, not archival-grade: its manifests record a dirty worktree and only five seeds per condition.
- The pilot predates the seeded Layer 1 serial fix. Preserve it as historical evidence; do not pool it silently with post-fix runs.
- The old logging ablation is partial and not same-state. The new same-state evidence covers only 100 ticks and one seed.
- The no-combat condition means formal combat disabled while economic raids remain enabled.
- Structured event writes flush every event; millions of raids can remain expensive even in `metrics_only` mode.
- Raid candidate scanning grows approximately with the square of active faction count.

## Exact next recommended task

Do not start `core-replication-v2` yet. First complete one bounded engineering/research slice:

1. Add an explicit raid control without changing existing `combat` semantics.
2. Buffer structured event CSV writes while preserving row content, order, validation, and state hashes.
3. Add tests for the raid flag, buffered writer finalization, exception-safe flushing, and deterministic hashes.
4. Run a clean metrics-only 2×2 combat × raids pilot at 100 and 250 ticks with 2–3 seeds.
5. Stop before 500 ticks unless observed cell runtimes justify extension.

After that slice passes from a clean tagged commit, a clean `core-replication-v2` becomes worthwhile. Its plan should use `metrics_only`, explicit combat/raid condition names, more seeds if feasible, and no full-text logging.

## Progress record

Phase-by-phase commands, evidence, and risk notes are preserved in `CODEX_SOL_SPRINT_PROGRESS.md`.
