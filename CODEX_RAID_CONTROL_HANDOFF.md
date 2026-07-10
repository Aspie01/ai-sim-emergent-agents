# Codex Raid Control Handoff

**Updated:** 2026-07-10T00:23:17-04:00  
**Repository:** `/home/lfs/Projects/ai-sim-emergent-agents`  
**Baseline revision:** `f8cb3857077400bd765fbf2832f83e95594b6b3f`  
**Status:** implementation and pilot complete; changes remain uncommitted

## Outcome

Explicit economy-raid control and buffered structured event writes are implemented and covered by tests. The bounded `raid-control-pilot-v1` matrix completed all 24 cells at 100 and 250 ticks with three shared seeds. The CSVs and every per-run artifact set validate. No 500-tick run, 10,000-tick replication, or `core-replication-v2` run was started.

## Code changes

- `src/thalren_vale/config.py`
  - Adds `raids` to valid disabled layers.
  - Merges the `--disable-raids` alias into `disabled_layers`.
  - Exposes `SimulationConfig.raids_enabled`.
  - Records `raids_enabled` in the manifest configuration.
- `src/thalren_vale/economy.py`
  - Adds a keyword-only `raids_enabled=True` argument to `economy_tick`.
  - Skips `_faction_raids` only when that explicit policy is false.
  - The default remains enabled for compatibility.
- `src/thalren_vale/sim.py`
  - Passes the explicit raid policy into the economy layer.
  - Adds `raids` to `--disable-layer` help.
  - Adds `--disable-raids` without coupling it to formal combat.
- `src/thalren_vale/metrics.py`
  - Buffers structured event writes with a default 1,000-row flush interval.
  - Flushes pending events during finalization and close.
  - Retains pending state after a non-fatal flush failure so a later flush can retry.
- `run_raid_control_pilot.py`
  - Defines the bounded 2-by-2 combat-by-raids matrix.
  - Uses `metrics_only`, validates each cell, supports safe resume/collection, and writes results incrementally.
- Tests
  - `tests/test_config.py`: raid controls, manifest recording, and combat-only compatibility.
  - `tests/test_raid_control.py`: simulation/economy gating and legacy default behavior.
  - `tests/test_events.py`: ordered buffered output, finalization, retry after flush failure, and interval validation.
  - `tests/test_reproducibility.py`: repeated raid-disabled seeded runs have the same state hash.
  - `tests/test_raid_control_pilot.py`: complete matrix definition and completed-only aggregation.

## Semantic guarantees

- Raids enabled: every one of the 12 pilot cells produced raid events.
- Raids disabled: every one of the 12 pilot cells produced zero raid events.
- Combat disabled with raids enabled: all six cells produced raid events.
- `--disable-layer combat` does not add `raids` to disabled layers.
- Calling `economy_tick` without a raid policy keeps raids enabled.
- Historical `no_combat` therefore retains its existing meaning: formal combat off, economy raids still on.

## Artifact validation

Read-only validation produced:

- `results.csv`: 24 rows, 24 unique matrix keys, no invalid statuses.
- `summary.csv`: eight rows, exactly recomputed from the result rows.
- Per-run verification: 24 of 24 passed `validate_run_outputs`.
- Structured events: 46,086 rows streamed and checked; schemas and tick order valid.
- Manifests: all use `metrics_only` and record the expected raid/combat policies.
- Dataset size: approximately 5.4 MiB; no large raw logs were created or inspected.

Artifacts:

- `RAID_CONTROL_PILOT_REPORT.md`
- `experiment_runs/raid-control-pilot-v1/results.csv`
- `experiment_runs/raid-control-pilot-v1/summary.csv`
- `experiment_runs/raid-control-pilot-v1/ticks_100/`
- `experiment_runs/raid-control-pilot-v1/ticks_250/`

## Key pilot findings

At 250 ticks, combat-off/raids-on averaged 5,865.7 events, 3,607.7 raids, 338 final inhabitants, 132.3 final factions, and 85.833 seconds. Combat-on/raids-on averaged 2,823.7 events, 865.7 raids, 208 final inhabitants, 57.3 final factions, and 41.610 seconds.

Both raids-off conditions averaged 2,084.3 events, zero raids, 375.7 final inhabitants, 112 final factions, and zero wars. Their aggregate simulation outcomes were identical at this short horizon, although their hashes differ because configuration is included in the canonical fingerprint.

These findings support treating formal combat and economy raids as separate factors. They do not establish a long-horizon effect or isolate the speedup from buffered event writes.

## Verification commands

Completed before this handoff:

```bash
python -m pytest -q
# 58 passed
```

The artifact validator also checked the entire 24-cell matrix, recomputed the summary, invoked the project verifier for each run, and streamed all structured event CSVs. It found no errors.

## Design decisions

- Existing `no_combat` semantics were preserved to keep historical runs interpretable.
- Raid control is available both as a layer name and as a clear convenience flag.
- Structured rows are buffered only at the file-flush boundary; row generation, content, order, counters, RNG calls, and simulation dynamics are unchanged.
- The pilot stopped at 250 ticks because its purpose was control validation, not another replication.
- The runner refuses to overwrite a populated output root unless explicitly resumed and persists CSV progress after each completed cell.

## Remaining caveats

- The pilot manifests record a dirty worktree at revision `f8cb3857077400bd765fbf2832f83e95594b6b3f`.
- There is no isolated immediate-flush versus buffered-flush benchmark, so no causal buffering speedup estimate should be quoted.
- Three seeds and 250 ticks are insufficient for publication-level dynamics claims.
- Cross-condition state hashes are intentionally different because the configuration is part of the hash input.

## Recommended next task

Review and commit this bounded change as one clean, tested revision. After that:

1. Copy only this report and the two small aggregate CSVs into the LLM Wiki; do not copy run directories or raw logs.
2. Update future experiment plans to name combat and raid settings separately.
3. If an isolated I/O estimate is needed, add a unit/microbenchmark that writes a fixed synthetic event stream with flush intervals 1 and 1,000. Keep it independent of simulation dynamics and under a few seconds.
4. Design any clean `core-replication-v2` only after choosing the scientific matrix and tagging a clean commit. No replication rerun is required to validate this implementation.
