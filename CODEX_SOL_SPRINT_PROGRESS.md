# Codex Sol Sprint Progress

Date: 2026-07-09

Repository: `/home/lfs/Projects/ai-sim-emergent-agents`

Objective: make the validated pilot dataset interpretable and plotted while reducing the cost of future runs.

## Phase 0 — Baseline inspection

Status: completed

- Initial worktree status: clean (`git status --short` produced no entries).
- Initial parent test status: `41 passed in 3.83s` from `python -m pytest -q`.
- Inspection is restricted to the requested simulator, runner, analysis, plotting, ablation, and test files. Multi-GB logs and manual chronicles are excluded.
- Existing code already contains logging-mode configuration, tests, an ablation runner, and a plotting script; each will be verified against the requested semantics before edits are made.
- Targeted inspection confirmed that parent pytest is scoped to `tests/`, the experiment verifier requires structured artifacts rather than raw text logs, and the simulator already records `log_mode` plus its optional-output policy in each run manifest.
- No simulation, analysis, or experiment code was changed during this phase.

## Ten-point execution plan

1. Establish the clean baseline, preserve the passing test result, and inspect only the explicitly relevant files and lightweight artifact inventories.
2. Verify all four logging modes end-to-end, including CLI help, configuration validation, manifest provenance, output suppression, and verifier expectations.
3. Make the smallest logging-mode corrections needed without changing simulation state transitions, event generation, RNG consumption, metrics, or seeded hashes.
4. Strengthen focused tests for accepted and rejected modes, required artifacts, suppressed text artifacts, and cross-mode state-hash equality; then run the parent suite.
5. Inventory existing logging-ablation outputs before running anything, reuse valid completed cells, and execute only missing bounded cells whose estimated runtime stays under the user’s limit.
6. Produce ablation result and summary CSVs plus a report that clearly separates completed evidence from skipped, interrupted, or partial cells.
7. Trace raid generation and effects through economy, faction, diplomacy, combat, structured-event, and logging paths; document semantics without changing behavior unless tests prove a bug.
8. Generate the requested core-replication figures exclusively from existing lightweight analysis CSVs, and document paired-seed interpretation and pilot-level caveats.
9. Copy only approved lightweight reports, CSVs, and sub-50-MB figures into the nested LLM Wiki, preserving source artifacts and status labels.
10. Run final parent tests and both Git status checks, then create a concise handoff covering results, caveats, defaults, and the next bounded task.

## Risk estimate

Overall risk: **moderate**.

- **Determinism risk — medium:** output gating can accidentally alter legacy event-log state or RNG-adjacent control flow. Mitigation: cross-mode seeded state-hash tests and no simulation-behavior refactor.
- **Runtime risk — medium/high:** prior no-combat cells were unexpectedly slow. Mitigation: inventory/reuse completed cells, run in ascending tick order, stop if a cell projects beyond roughly 20 minutes, and report partial results honestly.
- **Data-safety risk — low:** core outputs are read-only for this sprint; no deletion, rewriting, or multi-GB parsing is planned.
- **Analysis risk — medium:** five seeds and dirty-worktree provenance support pilot interpretation only. Reports and wiki status will retain those caveats.
- **Raid-semantics risk — medium:** the name “raid” may span economy, diplomacy, and combat concepts. Ambiguity will be documented rather than resolved through an unproven behavior change.
- **Nested-repo risk — low/medium:** wiki updates can affect a separate Git worktree. Only lightweight copies and targeted Markdown edits will be made, followed by independent status checks.

## Files expected to change

Expected or possible changes, subject to verification:

- `CODEX_SOL_SPRINT_PROGRESS.md`
- `src/thalren_vale/config.py`
- `src/thalren_vale/sim.py`
- `run_experiments.py`
- `tests/test_log_modes.py`
- `run_logging_ablation.py`
- `LOGGING_ABLATION_REPORT.md`
- `RAID_SEMANTICS_AUDIT.md`
- `plot_core_replication.py`
- `CORE_REPLICATION_PLOTS_REPORT.md`
- lightweight files under `experiment_runs/logging-ablation-v1/`
- figures under `experiment_runs/core-replication-v1/analysis/figures/`
- approved lightweight pages/artifacts under `LLM-Wiki/content/ai-simulation/thalren-vale/`
- `CODEX_SOL_SPRINT_HANDOFF.md`

No change will be made to generated core-replication analysis CSV contents or final validated run outputs.

## Phase 1 — Logging modes

Status: completed by verification; no implementation edit required.

- CLI help exposes `--log-mode {full,metrics_only,off,summary}` with an explicit output-policy description.
- `SimulationConfig` validates `full`, `summary`, `metrics_only`, and `off`, and rejects other values.
- `full` retains the legacy tee log, manual chronicle, era export, dashboard snapshots, per-tick render, progress, and final report.
- `summary` suppresses raw text artifacts and per-tick rendering while retaining filtered warnings/errors and the final summary.
- `metrics_only` and `off` suppress raw text artifacts, per-tick rendering, and the final narrative report while preserving the required structured research artifacts and manifest.
- Run manifests record both `log_mode` and the explicit written/suppressed optional-output policy.
- The state hash deliberately excludes the non-behavioral `condition` and `log_mode` configuration keys.
- `run_experiments.py` validates metrics, events, beliefs, run summary, and run manifest only; optional raw text outputs are not verifier requirements.
- Existing 5-tick smoke tests already demonstrate raw-output suppression and state-hash equality across modes. Phase 2 will add the missing explicit invalid-CLI assertion and rerun the full suite.

## Phase 2 — Logging-mode tests

Status: completed.

- Added an end-to-end subprocess test showing that `--log-mode verbose` exits nonzero and reports both `--log-mode` and `invalid choice`.
- Existing parameterized smoke tests execute all four valid modes and validate metrics, events, beliefs, run summary, and run manifest artifacts.
- Existing suppression tests confirm `summary`, `metrics_only`, and `off` create no raw log, manual chronicle, era export, or dashboard snapshot.
- Existing seeded determinism coverage confirms all four modes produce one identical final state hash.
- Parent verification after the added test: `42 passed in 3.76s`.
- `git diff --check` passed for the changed test and progress checkpoint.
- Longer existing ablation cells exposed scheduler-dependent seeded divergence that the 5-tick smoke test did not reach. Root cause: `_serial_mode` was recorded but ignored by `inhabitants_layer()`, which always launched four threads sharing the global PRNG.
- Fixed seeded Layer 1 execution to run on the calling thread while retaining threaded execution for unseeded interactive runs.
- Added a regression test that forbids worker-thread construction when `_serial_mode` is true.
- Parent verification after the determinism fix: `43 passed in 3.59s`.
- A fresh 100-tick no-combat seed-1 probe produced identical results in all modes: 734 structured events, final population 226, 61 factions, and state hash `f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04`.

## Phase 3 — Short logging ablation

Status: completed as a bounded partial benchmark (`needs-audit`).

- Reused and revalidated 12 existing cells: 100, 250, and 500 ticks across all four modes. Command: `python run_logging_ablation.py --ticks 100,250,500 --collect-existing`.
- Did not run the 1,000-tick cells. Existing 500-tick cells took 655.76–963.28 seconds, and nonlinear growth makes a 1,000-tick cell likely to exceed the roughly 20-minute task boundary.
- Generated/refreshed `experiment_runs/logging-ablation-v1/logging_ablation_results.csv`, `logging_ablation_summary.csv`, and the internal generated report.
- Updated the top-level `LOGGING_ABLATION_REPORT.md` with exact historical results, provenance, the nondeterminism diagnosis, and the post-fix same-state probe.
- At 500 ticks, `full` emitted 263.125 MiB of raw text and 266.088 MiB total; lower-output modes emitted zero raw text and only 2.626–2.707 MiB total.
- Historical lower-output cells were roughly 21–32% faster than `full`, but their state divergence makes that timing evidence suggestive rather than controlled.
- In the post-fix 100-tick same-state probe, `full` took 10.214 seconds and wrote 4.421 MiB; lower-output modes took 8.681–8.736 seconds and wrote about 0.095 MiB.
- Recommendation: `metrics_only` for research runs, `summary` when a human-readable terminal summary is useful, and `full` only for short diagnostics.

## Phase 4 — Raid semantics audit

Status: completed without a behavior change.

- Rewrote `RAID_SEMANTICS_AUDIT.md` from source code and lightweight event-count evidence only.
- Classified raids as combat-adjacent economic coercion with diplomatic consequences, distinct from formal war and battle resolution.
- Confirmed that disabling `combat` skips only `combat.combat_tick()`; economy-layer raids remain active.
- Confirmed direct effects on victim-tile resources, raider inventory/belief, rivalry, reputation, treaties, and emitted output. Raids do not directly damage health, kill inhabitants, remove territory, or dissolve factions.
- Across the pilot, raids were 5,513,353 of 5,559,667 no-combat events (99.167%), versus 38.340% of baseline and 45.873% of no-antistag events.
- The typed-event path excludes messages from legacy reclassification; a short-run key check found no duplicated raid rows. The volume is primarily real model output, not parser duplication.
- Identified quadratic faction-pair scanning, a 20% per-eligible-pair per-tick trigger, and per-event CSV flushing as computational/output risks.
- Recommended retaining `raid` for backward compatibility, adding explicit domain metadata later, and introducing a separate raid control for a future 2×2 combat × raids experiment.
- Corrected one stale source comment from “tension > 50” to the actual existing threshold `>35`; simulation behavior is unchanged.

## Phase 5 — Core-replication plots

Status: completed.

- Ran `python plot_core_replication.py` against existing lightweight analysis CSVs only.
- Regenerated seven requested figures: final population, final factions, elapsed time, output size, event count, paired-seed final-population deltas, and event-type composition.
- Regenerated `condition_plot_summary_table.csv` and `event_type_composition_table.csv` under the figures directory.
- Validated every figure as a readable PNG; all are under 64 KB and none exceeds the 50 MB wiki limit.
- Visually inspected the paired-delta and event-composition figures.
- Updated `CORE_REPLICATION_PLOTS_REPORT.md` with condition means, paired-seed deltas, raid shares, and the pilot interpretation boundary.
- Paired mean final-population deltas: baseline → no-antistag `-44.8`; baseline → no-combat `+456.2`, with the same direction in all five seeds.
- Retained caveats: five seeds, dirty-worktree provenance, raid semantics, logging confounding, and the fact that the pilot predates the seeded Layer 1 serial fix.

## Phase 6 — Light LLM-Wiki update

Status: completed.

- Refreshed the wiki logging ablation report and added `engineering/logging-ablation-results.md` with status `needs-audit`.
- Refreshed the raid semantics audit with status `needs-audit` and the core plot report with status `pilot-supported`.
- Copied the two logging-ablation CSVs into `evidence/lightweight-data/logging-ablation-v1/` and byte-compared them with their sources.
- Copied all seven generated PNG figures into `experiments/core-replication-v1/figures/` and byte-compared them with their sources.
- Updated wiki engineering, evidence, core-experiment, logging/observability, and ingest-manifest pages to link the new evidence and preserve interpretation boundaries.
- Largest copied figure: 63,847 bytes. No wiki file exceeds 50 MB.
- No raw logs, manual chronicles, run directories, or final validated outputs were copied, moved, deleted, or rewritten.
- Nested wiki changes are confined to Markdown, the two lightweight CSVs, and seven lightweight PNGs; no LLM-Wiki application code changed.

## Phase 7 — Final validation and handoff

Status: completed.

- Final parent test command: `python -m pytest -q`.
- Final parent test result: `43 passed in 3.57s`.
- Python and Markdown diff whitespace checks passed after removing report-only trailing spaces.
- Parent worktree changes are limited to the deterministic seeded Layer 1 fix, two focused test files, one corrected economy comment, three reports, and the two sprint handoff/progress documents.
- Nested wiki changes are limited to the documented Markdown refresh, two lightweight CSVs, and seven lightweight PNGs.
- Created `CODEX_SOL_SPRINT_HANDOFF.md` with implementation, evidence, caveats, wiki updates, and the exact next bounded task.
- No clean `core-replication-v2` is recommended yet. First add an explicit raid control, buffer structured event writes, and run a short post-fix 2×2 combat × raids pilot from a clean commit.
