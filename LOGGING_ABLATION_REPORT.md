# Logging Ablation Report

Status: **needs-audit (bounded partial benchmark)**

Experiment ID: `logging-ablation-v1`

Condition: `no_combat`

Seed: `1`

## Scope and validity

Twelve existing cells completed and validate for 100, 250, and 500 ticks across `full`, `summary`, `metrics_only`, and `off`. The requested 1,000-tick cells were not run: the 500-tick cells took 10.9–16.1 minutes each, population and event growth are nonlinear, and a 1,000-tick cell was therefore likely to exceed the sprint’s roughly 20-minute per-task limit.

The original twelve cells were produced from commit `5ea0c50bc1ecd04e201addbb55a82d4a79e95396` with a dirty worktree. Their manifests label execution as serial, but investigation found that Layer 1 still launched four threads sharing Python’s global PRNG. This caused state divergence across modes and even between repeated same-mode runs. Treat their disk measurements as strong evidence and their timing measurements as suggestive, not as a controlled same-state comparison.

Exact generated data:

- `experiment_runs/logging-ablation-v1/logging_ablation_results.csv`
- `experiment_runs/logging-ablation-v1/logging_ablation_summary.csv`
- `experiment_runs/logging-ablation-v1/LOGGING_ABLATION_REPORT.md`

## Original bounded ablation results

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
| 500 | off | 655.76s | 0.762 | 2.707 | 0.000 | 37,091 | 475 | 217 |

At 500 ticks, lower-output modes reduced total output by roughly 98–101× and eliminated all measured raw text. They were roughly 21–32% faster than `full`, but the pre-fix state divergence prevents treating those percentages as clean causal estimates.

## Nondeterminism root cause and fix

Seeded CLI runs set `_serial_mode = True`, and manifests recorded `execution_mode: serial`, but `inhabitants_layer()` did not consult `_serial_mode`. It always started four workers. Those workers consumed the shared module-level PRNG in scheduler-dependent order while also updating inhabitants and world state.

The fix makes seeded Layer 1 execution genuinely serial while retaining the threaded path for unseeded interactive runs. A regression test now fails if serial mode constructs a worker thread.

## Post-fix same-state probe

A fresh 100-tick, no-combat, seed-1 probe ran all four modes after the fix:

| Mode | Elapsed | Output MiB | Raw text MiB | Events | Final pop | Final factions | State hash |
|---|---:|---:|---:|---:|---:|---:|---|
| full | 10.214s | 4.421 | 4.310 | 734 | 226 | 61 | `f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04` |
| summary | 8.736s | 0.095 | 0.000 | 734 | 226 | 61 | `f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04` |
| metrics_only | 8.681s | 0.095 | 0.000 | 734 | 226 | 61 | `f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04` |
| off | 8.723s | 0.095 | 0.000 | 734 | 226 | 61 | `f8125fddef160af38e3b443fc95432b4e50f26d1f1e1b66b0d95c845c435ce04` |

This confirms that log-mode output gating no longer perturbs simulated state in the tested horizon. It also reinforces that full text logging is a disk bottleneck and a runtime contributor. The probe is one seed and one short horizon, so it does not establish the long-run magnitude of the runtime effect.

## Recommendation

Use `metrics_only` as the default for future research experiments. It preserves structured metrics, events, beliefs, summaries, and manifests while avoiding raw narrative/debug output. Use `summary` when terminal-visible warnings and a final human-readable report are useful. Reserve `full` for short diagnostics and demonstrations.

Before publication-grade performance claims, run a clean, post-fix logging ablation at 100 and 250 ticks with multiple seeds. A 500- or 1,000-tick extension should require explicit approval based on observed runtime.
