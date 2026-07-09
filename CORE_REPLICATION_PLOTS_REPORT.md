# Core Replication Plots Report

Plots and plot-summary tables were generated from the validated nested-layout analysis CSVs under:

`experiment_runs/core-replication-v1/analysis/`

Figures were saved under:

`experiment_runs/core-replication-v1/analysis/figures/`

## Generated figures

- `final_population_by_condition.png`
- `final_factions_by_condition.png`
- `elapsed_time_by_condition.png`
- `output_size_by_condition.png`
- `event_count_by_condition.png`
- `paired_seed_final_population_deltas.png`
- `event_type_composition_by_condition.png`

## Generated tables

- `condition_plot_summary_table.csv`
- `event_type_composition_table.csv`

## Condition summary

| Condition | n | Mean final pop | Mean final factions | Mean elapsed s | Mean output GiB | Mean events |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 51.60 | 5.20 | 2279.41 | 0.134 | 13,199 |
| no_antistag | 5 | 6.80 | 1.00 | 2171.95 | 0.101 | 8,796 |
| no_combat | 5 | 507.80 | 213.40 | 46263.39 | 12.398 | 1,111,933 |

## Notes

The no-combat condition dominates elapsed time, output size, and event count. The event-composition plot uses a log-scaled y-axis because no-combat is overwhelmingly dominated by `raid` events.

The analysis-local copy of this report is:

`experiment_runs/core-replication-v1/analysis/CORE_REPLICATION_PLOTS_REPORT.md`
