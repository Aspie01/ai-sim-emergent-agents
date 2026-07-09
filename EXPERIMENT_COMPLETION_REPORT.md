# Core Replication Experiment Completion Report

## Verification result

Experiment `core-replication-v1` is complete and validates.

Verification command:

```bash
python run_experiments.py --plan experiments_replication_v1.json --verify
```

Result:

```text
✓ All expected outputs are present and valid.
```

All 15 final condition/seed runs validate. No final run is missing required metrics, event, belief, run-summary, or run-manifest artifacts.

## Experiment identity and provenance

- Experiment ID: `core-replication-v1`
- Plan: `experiments_replication_v1.json`
- Plan SHA-256: `66c28ca1170137379dddbd19268b258a8df90f0a548e5dd7614ccc8f0aa84587`
- Output root: `experiment_runs/core-replication-v1/`
- Code revision recorded by the experiment manifest: `5ea0c50bc1ecd04e201addbb55a82d4a79e95396`
- Dirty worktree recorded by the experiment manifest: `true`
- Current code revision checked during this report: `5ea0c50bc1ecd04e201addbb55a82d4a79e95396`
- Current worktree status: dirty
- Experiment manifest completed at: `2026-07-09T18:22:29.114460+00:00`

The dataset is usable as a pilot replication dataset, but provenance should state that the runs were produced from a dirty worktree. If a publication-grade clean-revision dataset is required, rerun from a tagged clean commit under a new experiment ID.

## Generated analysis artifacts

Nested-layout analysis was generated with:

```bash
python analyze_core_replication.py --plan experiments_replication_v1.json --root experiment_runs/core-replication-v1
```

Generated tables:

- `experiment_runs/core-replication-v1/analysis/run_level_summary.csv`
- `experiment_runs/core-replication-v1/analysis/condition_summary.csv`
- `experiment_runs/core-replication-v1/analysis/paired_seed_comparisons.csv`
- `experiment_runs/core-replication-v1/analysis/paired_seed_comparison_summary.csv`
- `experiment_runs/core-replication-v1/analysis/event_type_counts.csv`
- `experiment_runs/core-replication-v1/analysis/largest_files.csv`
- `experiment_runs/core-replication-v1/analysis/superseded_attempts.csv`
- `experiment_runs/core-replication-v1/analysis/analysis_manifest.json`

The analysis treats only final validated runs as the research dataset. Superseded timeout markers and earlier duplicate summary rows are not counted as independent evidence.

## Condition × seed status

Elapsed time is from each final run's `data/run_summaries.csv` `wall_clock_seconds`. Final population and peak population are also from `run_summaries.csv`. Event count is streamed from the structured `faction_events_*.csv` file. Output size is the per-run directory size.

| Condition | Seed | Status | Elapsed | Final tick | Final pop | Peak pop | Final factions | Events | Output | State hash |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 1 | valid | 2,106.43s | 10000 | 29 | 298 | 6 | 11,891 | 0.160 GiB | `92c291daa8da…` |
| baseline | 2 | valid | 2,673.04s | 10000 | 62 | 307 | 4 | 14,454 | 0.129 GiB | `ced8a37deafa…` |
| baseline | 3 | valid | 2,348.16s | 10000 | 63 | 308 | 2 | 13,691 | 0.138 GiB | `5040c1b6fd0e…` |
| baseline | 4 | valid | 2,606.46s | 10000 | 31 | 259 | 7 | 13,424 | 0.123 GiB | `bc4af4b5a74b…` |
| baseline | 5 | valid | 1,662.97s | 10000 | 73 | 216 | 7 | 12,537 | 0.117 GiB | `0b5f260a5c79…` |
| no_antistag | 1 | valid | 2,488.26s | 10000 | 14 | 276 | 1 | 8,845 | 0.094 GiB | `22bb29f8fdbf…` |
| no_antistag | 2 | valid | 2,425.99s | 10000 | 2 | 284 | 1 | 9,022 | 0.095 GiB | `5e506cf353e9…` |
| no_antistag | 3 | valid | 1,755.51s | 10000 | 3 | 294 | 1 | 8,337 | 0.134 GiB | `8a0d038b2ddd…` |
| no_antistag | 4 | valid | 1,962.46s | 10000 | 6 | 294 | 1 | 8,508 | 0.092 GiB | `62e4ab6a1b8c…` |
| no_antistag | 5 | valid | 2,227.52s | 10000 | 9 | 285 | 1 | 9,266 | 0.090 GiB | `4ec8d2af7d4f…` |
| no_combat | 1 | valid | 45,315.10s | 10000 | 510 | 509 | 212 | 1,196,111 | 13.411 GiB | `452df8dbaa77…` |
| no_combat | 2 | valid | 56,184.12s | 10000 | 589 | 592 | 248 | 1,244,133 | 14.980 GiB | `b23665809080…` |
| no_combat | 3 | valid | 64,688.04s | 10000 | 567 | 606 | 250 | 1,245,946 | 15.467 GiB | `93e09562838e…` |
| no_combat | 4 | valid | 28,022.93s | 10000 | 415 | 426 | 169 | 961,033 | 7.749 GiB | `e34497345a9f…` |
| no_combat | 5 | valid | 37,106.75s | 10000 | 458 | 463 | 188 | 912,444 | 10.384 GiB | `ee5ae2e86093…` |

Note: no-combat seed 1 reports final population 510 and peak population 509. The peak is the MetricsLogger tick-observed peak, while final population is measured during finalization; this off-by-one indicates a finalization/tick-observation timing difference, not a validation failure.

## Condition-level summary

| Condition | n | Mean elapsed | Mean final pop | Final pop range | Mean peak pop | Mean final factions | Mean events | Mean output | Mean raw text | Mean wars |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 2,279.4s | 51.6 | 29-73 | 277.6 | 5.2 | 13,199 | 0.134 GiB | 0.131 GiB | 71.8 |
| no_antistag | 5 | 2,171.9s | 6.8 | 2-14 | 286.6 | 1.0 | 8,796 | 0.101 GiB | 0.099 GiB | 21.4 |
| no_combat | 5 | 46,263.4s | 507.8 | 415-589 | 519.2 | 213.4 | 1,111,930 | 12.398 GiB | 12.309 GiB | 0.0 |

Paired seed comparisons:

- `baseline → no_antistag`: mean final population delta `-44.8`; mean elapsed ratio `0.986×`; mean output ratio `0.761×`; mean event-count ratio `0.670×`.
- `baseline → no_combat`: mean final population delta `+456.2`; mean elapsed ratio `20.629×`; mean output ratio `92.605×`; mean event-count ratio `84.408×`.
- `no_antistag → no_combat`: mean final population delta `+501.0`; mean elapsed ratio `21.832×`; mean output ratio `123.212×`; mean event-count ratio `126.801×`.

## Event counts by condition

Across all five seeds per condition:

- Baseline: 65,997 structured events; 359 wars declared and 359 wars ended; 5,925 births; 7,859 deaths; 3,798 schisms; 1,907 mergers; 4,589 treaties signed; 25,303 raids; 94 stagnation triggers; 100 era shifts.
- No anti-stagnation: 43,978 structured events; 107 wars declared and 107 wars ended; 5,925 births; 6,041 deaths; 2,791 schisms; 1,622 mergers; 577 treaties signed; 20,174 raids; 0 stagnation triggers; 0 era shifts.
- No combat: 5,559,667 structured events; 0 wars; 5,925 births; 4,080 deaths; 5,164 schisms; 2,793 mergers; 1,254 treaties signed; 5,513,353 raids; 100 era shifts.

## State hashes

| Condition | Seed | State hash |
|---|---:|---|
| baseline | 1 | `92c291daa8daf9cc761eecead6a08d52616798e5e8a5a6eb1bfe62e1ef00a5f0` |
| baseline | 2 | `ced8a37deafaa84121cdc31816405384ac9f4aa8f2f7a4930541b5b79008e03e` |
| baseline | 3 | `5040c1b6fd0e56c7486d9ec37207a3a3a0066bedb951c0a190f063de0eee8c94` |
| baseline | 4 | `bc4af4b5a74bfceb370e8b1aae8708ecd9d875ce2e5f476025b7c7aa4fd64bba` |
| baseline | 5 | `0b5f260a5c790785ce836282183c4e0e695a4633b90a53cafa9e863fbfd466dd` |
| no_antistag | 1 | `22bb29f8fdbf1f66aa388ea1b99191581d7264c602265c90832b7eb8293abf1e` |
| no_antistag | 2 | `5e506cf353e95881cf3e9350594da4ad9008cf059f40da9c2ee90214d3354048` |
| no_antistag | 3 | `8a0d038b2ddd370428023afc69af2aa0e3c38ccd5a47e2ebe66e5c3dc7e40121` |
| no_antistag | 4 | `62e4ab6a1b8c0b73906fd104f3265f9cab45b29bf94a8288dc41ac3097271720` |
| no_antistag | 5 | `4ec8d2af7d4f8897da32ba55c8b0e458965a28a33b1b36d5a0d5581a2537b635` |
| no_combat | 1 | `452df8dbaa774575e2c37fa140869dd86954209b45c3dc8ea0e4a6ac8032a4a4` |
| no_combat | 2 | `b23665809080563a5d1ddc861d722a352e441953ace2a7d715a4a4c8585ec77e` |
| no_combat | 3 | `93e09562838e8c6680d4b1ff15638a77aa54ecce5c80be5624013f0872291cf4` |
| no_combat | 4 | `e34497345a9fe76b64ab58637507a415731bfd0a62dee44eb772ccc668093465` |
| no_combat | 5 | `ee5ae2e86093f553a3ebc371a4a446baa4b982487a7d545c4a3aea5a33bead6b` |

## Output size and logging overhead risk

Total final output size:

- `67,821,097,590` bytes
- `63.163` GiB by binary units
- `du -sh experiment_runs/core-replication-v1` reports `64G`

Largest files:

| Size | Run | File |
|---:|---|---|
| 10.723 GiB | no_combat seed 3 | `logs/run_no_combat_seed_3_20260707_145205.txt` |
| 10.228 GiB | no_combat seed 2 | `logs/run_no_combat_seed_2_20260706_231536.txt` |
| 8.107 GiB | no_combat seed 1 | `logs/run_no_combat_seed_1_20260706_104017.txt` |
| 6.270 GiB | no_combat seed 5 | `logs/run_no_combat_seed_5_20260709_040359.txt` |
| 5.209 GiB | no_combat seed 1 | `manual_chronicle_no_combat_seed_1.txt` |
| 5.161 GiB | no_combat seed 4 | `logs/run_no_combat_seed_4_20260708_085018.txt` |
| 4.652 GiB | no_combat seed 2 | `manual_chronicle_no_combat_seed_2.txt` |
| 4.644 GiB | no_combat seed 3 | `manual_chronicle_no_combat_seed_3.txt` |
| 4.039 GiB | no_combat seed 5 | `manual_chronicle_no_combat_seed_5.txt` |
| 2.513 GiB | no_combat seed 4 | `manual_chronicle_no_combat_seed_4.txt` |

Text logging appears likely to be a major bottleneck. The no-combat condition averaged `12.309` GiB of raw text output per run, compared with `0.131` GiB for baseline and `0.099` GiB for no-antistag. No-combat also emitted about `84.4×` as many structured events as baseline and took about `20.6×` as much wall time.

This does not prove the slowdown is caused only by logging. The no-combat runs also have much larger living populations and faction counts. A logging ablation is required before attributing the slowdown to emergent simulation complexity rather than I/O volume.

## Timeouts, crashes, invalid outputs, and superseded attempts

Final validated runs:

- Timeouts: none
- Crashes: none
- Invalid outputs: none
- Missing artifacts: none

Superseded historical artifacts still present:

- Five stale no-combat `runner_stderr.txt` timeout markers from earlier 20,000-second wall-clock-limit attempts.
- Three `run_summaries.csv` files contain one earlier summary row followed by the final validated row:
  - `baseline/seed_3/data/run_summaries.csv`
  - `no_antistag/seed_2/data/run_summaries.csv`
  - `no_antistag/seed_4/data/run_summaries.csv`

The analysis output uses the final row only for those summary files. See `SUPERSEDED_ATTEMPTS_CLEANUP_PLAN.md` for the dry-run cleanup list.

## Interpretation

The primary research framing was:

> How do anti-stagnation mechanisms and combat affect long-horizon persistence, viability, population regulation, and computational tractability in Thalren Vale?

Short interpretation:

- Baseline remains viable for 10,000 ticks but ends at low population: final populations range from 29 to 73, with 2 to 7 final active factions. Anti-stagnation mechanisms appear to keep the society from collapsing completely while combat and diplomacy continue to regulate population and faction structure.
- Removing anti-stagnation sharply reduces long-horizon viability: final populations range from 2 to 14, every seed ends with one active faction, and there are no recorded stagnation-trigger or era-shift events. This supports the conclusion that anti-stagnation mechanisms materially improve persistence.
- Removing combat produces much larger late-run populations and faction counts: final populations range from 415 to 589, with 169 to 250 active factions. This condition emits enormous raid/event/text volume and is computationally much less tractable. Combat appears to function as a population/faction pressure valve, but the computational effect must be separated from logging overhead before making a causal performance claim.

Bottom line: the experiment supports the research claim that anti-stagnation improves persistence and combat materially changes population regulation. The no-combat tractability result is real at the artifact/runtime level, but the cause remains partly confounded by text logging until the logging ablation is run.
