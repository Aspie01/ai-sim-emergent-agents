# Raid Control Pilot Report

**Experiment:** `raid-control-pilot-v1`  
**Run date:** 2026-07-09 to 2026-07-10  
**Recorded code revision:** `f8cb3857077400bd765fbf2832f83e95594b6b3f` with a dirty worktree  
**Evidence status:** pilot-supported; not archival-grade  

## Executive result

The explicit raid control works and preserves the project's historical semantics. Economy raids remain enabled by default and when formal combat alone is disabled. Passing `--disable-raids` or `--disable-layer raids` suppresses raids independently of formal combat.

All 24 requested pilot cells completed and validate: four combat-by-raids conditions, two horizons (100 and 250 ticks), and three shared seeds. Every raids-on cell produced raid events, every raids-off cell produced zero raid events, and every combat-off/raids-on cell continued to produce raids. The experiment used `metrics_only` logging and occupies approximately 5.4 MiB.

The pilot also confirms that raids and formal combat interact. At 250 ticks, combat-off/raids-on runs generated substantially more raids, structured events, population, and factions than combat-on/raids-on runs. With raids disabled, the combat-on and combat-off conditions had identical recorded event counts and population/faction/war outcomes at this horizon. These are short-run, three-seed findings and should not be generalized to 10,000 ticks without a clean, preregistered follow-up.

## Design

The bounded matrix was:

| Condition | Formal combat | Economy raids | CLI control |
|---|---:|---:|---|
| `combat_on_raids_on` | on | on | default |
| `combat_off_raids_on` | off | on | `--disable-layer combat` |
| `combat_on_raids_off` | on | off | `--disable-raids` |
| `combat_off_raids_off` | off | off | `--disable-layer combat --disable-raids` |

Each cell used seeds 1, 2, and 3; 100- and 250-tick horizons; and `--log-mode metrics_only`. No 500-tick or full replication run was performed.

## Validation

Read-only validation of the completed artifacts found:

- 24 result rows and 24 unique condition/horizon/seed keys.
- Eight condition-level summary rows, exactly reproducible from `results.csv`.
- All 24 per-run artifact sets passed `validate_run_outputs`.
- All 46,086 structured event rows had the expected schema and nondecreasing tick order.
- All state hashes were present as 64-character hexadecimal values.
- 12 of 12 raids-on cells contained raid events.
- 12 of 12 raids-off cells contained zero raid events.
- Six of six combat-off/raids-on cells contained raid events.
- Every manifest recorded `metrics_only`, the expected disabled layers, and the expected `raids_enabled` value.

Primary artifacts:

- `experiment_runs/raid-control-pilot-v1/results.csv`
- `experiment_runs/raid-control-pilot-v1/summary.csv`
- `experiment_runs/raid-control-pilot-v1/ticks_100/`
- `experiment_runs/raid-control-pilot-v1/ticks_250/`

## Condition summaries

Means below are over the three shared seeds.

| Ticks | Condition | Seconds | Events | Raids | Raid share | Final population | Final factions | Wars |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 100 | combat on / raids on | 7.223 | 684.3 | 99.0 | 14.47% | 193.7 | 52.3 | 0.33 |
| 100 | combat off / raids on | 7.360 | 681.0 | 98.3 | 14.44% | 199.3 | 53.7 | 0.00 |
| 100 | combat on / raids off | 7.333 | 569.3 | 0.0 | 0.00% | 207.0 | 50.3 | 0.00 |
| 100 | combat off / raids off | 7.400 | 569.3 | 0.0 | 0.00% | 207.0 | 50.3 | 0.00 |
| 250 | combat on / raids on | 41.610 | 2,823.7 | 865.7 | 30.66% | 208.0 | 57.3 | 4.67 |
| 250 | combat off / raids on | 85.833 | 5,865.7 | 3,607.7 | 61.50% | 338.0 | 132.3 | 0.00 |
| 250 | combat on / raids off | 70.990 | 2,084.3 | 0.0 | 0.00% | 375.7 | 112.0 | 0.00 |
| 250 | combat off / raids off | 69.727 | 2,084.3 | 0.0 | 0.00% | 375.7 | 112.0 | 0.00 |

## Shared-seed comparisons at 250 ticks

Because all conditions use seeds 1, 2, and 3, the mean differences below are paired by seed.

- Disabling formal combat while leaving raids on added 44.223 seconds, 3,042 structured events, 2,742 raids, 130 final inhabitants, and 75 final factions per run on average. Mean wars fell from 4.67 to zero.
- Disabling raids while leaving formal combat on removed 739.3 structured events and 865.7 raids, but the resulting runs ended with 167.7 more inhabitants and 54.7 more factions. Their mean elapsed time was 29.380 seconds higher, consistent with more surviving state to update; this is not evidence that raid logging is free.
- Disabling raids when formal combat was already off removed 3,781.3 structured events and 3,607.7 raids, reduced mean elapsed time by 16.107 seconds, and ended with 37.7 more inhabitants but 20.3 fewer factions.
- With raids off, toggling formal combat changed none of the recorded event, population, faction, or war outcomes at 250 ticks. The 1.263-second mean timing difference is small enough to treat as runtime noise in this pilot.

The direction of the runtime effect therefore depends on the dynamics induced by the controls. Raid suppression removes event-writing work, but it can also preserve a larger population and hence increase simulation work. A dedicated writer microbenchmark would be needed to estimate the isolated performance benefit of buffering.

## Buffered structured event writes

Structured event CSV writes now flush after 1,000 pending rows instead of after every row. Finalization and close explicitly flush pending events. A failed flush is non-fatal, retains the pending count, and can be retried.

Tests confirm that buffered rows retain exact CSV content and insertion order, including quoted detail fields; finalization drains the pending buffer; a simulated first flush failure is safely retried; and same-seed runs remain deterministic. The completed pilot's event files also passed schema, count, and tick-order checks across all 46,086 rows.

This pilot has no otherwise-identical pre-buffering control, so it cannot quantify the buffering speedup or attribute the historical `no_combat` slowdown to a single cause.

## Interpretation and recommendation

Raids are economy-generated, combat-adjacent coercive interactions, not formal wars. The evidence supports retaining them as an independent experimental factor:

1. Keep current defaults: combat on, raids on.
2. Keep `--disable-layer combat` limited to formal combat so historical `no_combat` semantics remain reproducible.
3. Use `--disable-raids` or `--disable-layer raids` when the research question requires suppressing economic raids.
4. Name future conditions explicitly, such as `combat_off_raids_on`, instead of relying on the ambiguous label `no_combat`.
5. Continue using `metrics_only` for research runs; reserve full text logging for short debugging sessions.

## Caveats

- Three seeds and at most 250 ticks support engineering validation and pilot interpretation only.
- The manifests record a dirty worktree, so this dataset is not archival-grade.
- State hashes intentionally incorporate configuration. Hashes from different control conditions are not expected to match even if their headline metrics match.
- The pilot does not isolate event-buffer performance from changed population, faction, and event dynamics.
- No conclusion here supersedes the validated historical `core-replication-v1` dataset; the new controls describe future experiments and do not reinterpret old manifests.
