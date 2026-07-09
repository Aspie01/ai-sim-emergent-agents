# Core Replication Plots Report

Status: **pilot-supported**

Experiment: `core-replication-v1`

Validated final runs: 15/15

## Inputs and outputs

The plots were regenerated exclusively from lightweight CSVs under `experiment_runs/core-replication-v1/analysis/`. No raw logs or manual chronicles were opened.

Figures are under `experiment_runs/core-replication-v1/analysis/figures/`:

- `final_population_by_condition.png`
- `final_factions_by_condition.png`
- `elapsed_time_by_condition.png`
- `output_size_by_condition.png`
- `event_count_by_condition.png`
- `paired_seed_final_population_deltas.png`
- `event_type_composition_by_condition.png`

Companion tables:

- `condition_plot_summary_table.csv`
- `event_type_composition_table.csv`

All seven figures validated as PNG files. Each is under 64 KB and therefore safe for the lightweight wiki ingest.

## Condition-level results

| Condition | Runs | Mean final population | Mean final factions | Mean elapsed seconds | Mean output GiB | Mean events |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 51.60 | 5.20 | 2,279.41 | 0.134 | 13,199 |
| no_antistag | 5 | 6.80 | 1.00 | 2,171.95 | 0.101 | 8,796 |
| no_combat | 5 | 507.80 | 213.40 | 46,263.39 | 12.398 | 1,111,933 |

The distributions support three pilot-level observations:

1. Removing anti-stagnation sharply reduces long-horizon viability: every shared-seed final population is below baseline.
2. Disabling formal combat greatly increases surviving population and active factions in every shared seed.
3. No-combat also raises runtime, output, and event volume by orders of magnitude, but those computational effects remain confounded by raid and logging behavior.

## Paired-seed results

Using the same five seeds for each comparison:

| Comparison | Mean final-population delta | Median delta | Mean population ratio |
|---|---:|---:|---:|
| baseline → no_antistag | -44.8 | -60 | 0.176× |
| baseline → no_combat | +456.2 | +481 | 11.150× |

The paired plot shows the direction is consistent across all five seeds, which is more informative than comparing condition means alone. Five pairs are still too few for strong publication-grade inference.

## Event composition

| Condition | Raid events | Total events | Raid share |
|---|---:|---:|---:|
| baseline | 25,303 | 65,997 | 38.340% |
| no_antistag | 20,174 | 43,978 | 45.873% |
| no_combat | 5,513,353 | 5,559,667 | 99.167% |

The composition plot uses a logarithmic count axis because no-combat raids otherwise visually erase every other event type. The exact within-condition fractions remain available in `event_type_composition_table.csv`.

## Interpretation boundary

These figures make the validated pilot dataset interpretable, but they do not make it archival-grade:

- manifests recorded a dirty worktree;
- there are only five seeds per condition;
- the original no-combat condition disabled formal combat but retained economy-layer raids;
- full text and per-event structured logging confound runtime;
- the completed dataset predates the fix that made seeded Layer 1 execution genuinely serial.

The figures are appropriate for a pilot report and for designing the next experiment. A clean tagged replication should follow only after raid controls and cheaper structured event writing are tested at short horizons.
