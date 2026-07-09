# Logging Ablation Report

Experiment ID: `logging-ablation-v1`

Output root:

`experiment_runs/logging-ablation-v1/`

Generated files:

- `experiment_runs/logging-ablation-v1/logging_ablation_results.csv`
- `experiment_runs/logging-ablation-v1/logging_ablation_summary.csv`
- `experiment_runs/logging-ablation-v1/LOGGING_ABLATION_REPORT.md`

## Scope actually completed

Completed short no-combat seed-1 runs:

- ticks: `100`, `250`, `500`
- modes: `full`, `summary`, `metrics_only`, `off`
- rows: `12`

The requested 1000-tick cases were not run. The 500-tick full case took about 16 minutes and the lower-output 500-tick cases also took 11-13 minutes each. Running 1000-tick full would likely be materially expensive. It should be approved explicitly before running.

## Key results

| Ticks | Mode | Elapsed | Ticks/s | Output MiB | Raw text MiB | Events | Final pop | Final factions |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 100 | full | 10.34s | 9.671 | 4.332 | 4.221 | 720 | 216 | 63 |
| 100 | summary | 8.78s | 11.390 | 0.096 | 0.000 | 738 | 225 | 55 |
| 100 | metrics_only | 8.70s | 11.494 | 0.096 | 0.000 | 735 | 225 | 56 |
| 100 | off | 9.32s | 10.730 | 0.099 | 0.000 | 762 | 231 | 59 |
| 250 | full | 129.13s | 1.936 | 42.743 | 42.159 | 6,616 | 362 | 143 |
| 250 | summary | 109.55s | 2.282 | 0.530 | 0.000 | 6,685 | 369 | 154 |
| 250 | metrics_only | 94.74s | 2.639 | 0.483 | 0.000 | 5,986 | 334 | 130 |
| 250 | off | 122.28s | 2.044 | 0.638 | 0.000 | 8,443 | 381 | 166 |
| 500 | full | 963.28s | 0.519 | 266.088 | 263.125 | 39,894 | 488 | 222 |
| 500 | summary | 695.63s | 0.719 | 2.626 | 0.000 | 36,345 | 481 | 225 |
| 500 | metrics_only | 764.63s | 0.654 | 2.650 | 0.000 | 36,752 | 482 | 227 |
| 500 | off | 655.76s | 0.762 | 2.590 | 0.000 | 31,391 | 475 | 217 |

## Interpretation

The new log modes work as output controls:

- `summary`, `metrics_only`, and `off` eliminated raw text output in the ablation runs.
- At 500 ticks, full mode wrote `263.125 MiB` raw text, while the other modes wrote `0 MiB` raw text.
- At 500 ticks, total output dropped from `266.088 MiB` in full mode to about `2.6 MiB` in the lower-output modes.

Runtime improved, but not proportionally to disk savings:

- At 500 ticks, `full` took `963.28s`.
- `summary` took `695.63s`.
- `metrics_only` took `764.63s`.
- `off` took `655.76s`.

This shows full text logging is a major disk/output bottleneck and a runtime contributor. It does not show that logging is the only runtime bottleneck. No-combat state complexity and structured event volume remain expensive even with raw text disabled.

## Same-state caveat

The ablation is not a clean same-state timing comparison.

State hashes differed across log modes for 100, 250, and 500 ticks. A follow-up probe also showed that two separate 100-tick no-combat `metrics_only` runs with the same seed produced different state hashes. That means the divergence is broader simulation nondeterminism, not necessarily caused by log mode.

Therefore:

- Use this ablation as strong evidence that raw text logging dominates disk output.
- Use it as suggestive evidence that lower-output modes reduce runtime.
- Do not use it as a rigorous same-state performance comparison until no-combat determinism is fixed.

## Recommendation

For future long experiments, use `metrics_only` as the default experiment mode. It preserves structured metrics/events/beliefs/manifests and avoids giant raw text logs.

Use `summary` when a human-readable final report is needed.

Use `full` only for diagnostic runs or small demonstrations.

Before making publication-grade performance claims, fix or isolate the longer-run no-combat nondeterminism and rerun a smaller same-state benchmark.
