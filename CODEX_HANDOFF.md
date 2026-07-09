# Codex Project Handoff

## Project purpose

Thalren Vale is a Python 3.10+ emergent-civilization simulation. It starts with individual inhabitants operating on local survival heuristics and layers beliefs, factions, economy, combat, technology, diplomacy, religion, settlements, anti-stagnation interventions, optional LLM mythology, metrics, plugins, and a Streamlit dashboard on top.

The project also supports academic experiments. Seeded runs are intended to be reproducible and produce tick metrics, structured faction events, belief snapshots, run summaries, logs, chronicles, state hashes, and provenance manifests.

## Architecture

- `src/thalren_vale/sim.py`: main orchestration loop and CLI. Runs world, inhabitants, beliefs, factions, procreation, economy, combat, technology, diplomacy, religion, mythology/export, plugins, metrics, and anti-stagnation layers.
- Domain modules: `world.py`, `inhabitants.py`, `beliefs.py`, `factions.py`, `economy.py`, `combat.py`, `technology.py`, `diplomacy.py`, and `religion.py`.
- `state.py`: incremental replacement for module-global state. `SimulationState` owns core and cross-domain collections; old globals remain compatibility aliases.
- `events.py`: typed event stream with legacy text-log compatibility.
- `metrics.py`: tick/event/belief CSV logging and run summaries.
- `reproducibility.py`: canonical final-state SHA-256 and run provenance manifests.
- `plugin_api.py`: immutable plugin snapshots and validated commands.
- `run_experiments.py`: versioned, isolated, resumable batch runner.
- `benchmarks/benchmark_simulation.py`: controlled inhabitants-layer scaling benchmark.
- `.github/workflows/ci.yml`: Python 3.10–3.13 tests plus package build/install checks.

## Work completed in this session

### Anti-stagnation correctness

The original `--disable-antistag` flag did not disable traveler injection. Travelers were also injected every tick when fewer than three factions existed, despite documentation saying every 40 ticks.

The loop now:

- Evaluates traveler waves only every 40 ticks.
- Suppresses travelers under `--disable-antistag`.
- Also gates solo-faction attrition, world events, era shifts, disruption events, and peace escalation under that flag.

Verified behavior:

- Baseline ticks 1–3 remain at the initial population instead of receiving 10 travelers per tick.
- A traveler wave occurs at tick 40 when factions are disabled and anti-stagnation is enabled.
- No traveler wave occurs through tick 40 with `--disable-antistag`.

### Tests and dependencies

- Added `pytest>=8,<10` to the `dev` optional dependency and installed it.
- Configured pytest to import from `src/`.
- Added tests for anti-stagnation, state reset/repeatability, configuration validation, reproducibility, structured events, plugin security, benchmark output, and experiment running.
- Latest result: **48 tests passed in 2.44 seconds**.

### Explicit state lifecycle

- Added `SimulationState`.
- It owns inhabitants, factions, deaths, text events, plugins, era/archive state, wars, rivalries, treaties, reputation, economy stores, religions, and holy wars.
- Added `reset_runtime_state()` to clear state leaked by combat, economy, diplomacy, factions, religion, mythology, display, and plugins.
- Every `run()` starts from a clean state.
- Tested two same-seed runs in one interpreter; complete metrics output matches.

### Reproducibility

Every completed run writes:

```text
data/run_manifest_<condition>_seed_<seed>.json
```

It contains effective validated configuration, seed, condition, serial/threaded mode, canonical state hash, event schema, Git commit, and dirty-worktree status.

Tests prove:

- Same seed/configuration yields the same hash across independent processes.
- Different seeds yield different hashes.
- Seeded CLI runs are serial because threaded code shares the global PRNG.

Threaded execution is deliberately recorded but is **not claimed deterministic**.

### Typed configuration and CLI validation

- Added frozen `SimulationConfig` in `config.py`.
- Added immutable default constants and legacy mutable aliases.
- Validates ticks, population cap, starting population, name-pool limit, trust/war thresholds, belief-sharing probability, condition names, and disabled layers.
- Unknown CLI arguments and unknown layer names fail before outputs are created.
- `religion` and `mythology` are now genuinely disableable layers.
- Conditions are filename-safe, preventing path traversal through output names.
- Run manifests store the validated effective configuration.

### Structured events

- Added `SimulationEvent`, `StructuredEventLog`, and event schema version 1.
- Metrics now consume typed fields directly for wars, births, deaths, factions, treaties, raids, technology, settlements, schisms, mergers, world events, era shifts, and disruptions.
- Legacy human-readable logs remain unchanged.
- The typed queue is drained each tick to bound memory.
- Final-tick events are flushed before logger finalization.
- A 50-tick smoke run emitted 185 event rows with zero exact duplicates.
- Regex classification remains as a compatibility fallback for rare unmigrated legacy events.

### Packaging and CI

- Added GitHub Actions for Python 3.10, 3.11, 3.12, and 3.13.
- CI compiles sources, runs tests, smoke-runs the benchmark, builds wheel/sdist, runs `twine check`, checks wheel contents, installs the wheel in a clean venv, and runs a three-tick simulation.
- Single-sourced package version from `thalren_vale.__version__`; current version is `1.1.1`.
- Split dependencies:
  - core: `noise`
  - `dashboard`: Streamlit, autorefresh, Plotly, NumPy
  - `analysis`: pandas, Plotly, NumPy
  - `dev`: pytest, build, twine
  - `all`: all user-facing optional dependencies
- Updated to SPDX `PolyForm-Noncommercial-1.0.0` metadata.
- Removed tracked generated `src/thalren_vale_simulation.egg-info/PKG-INFO`; egg-info is ignored.
- Local wheel and sdist builds passed `twine check`.
- Wheel contained no datasets/dashboard snapshots.
- Isolated wheel installation and CLI smoke test succeeded.
- GitHub Actions itself has not yet run on GitHub; only its equivalent commands were exercised locally.

### Plugin security

- `SimulationBridge` no longer exposes live factions/world dictionaries.
- Added frozen `FactionSnapshot`, tuple collections, and nested read-only mapping proxies.
- Snapshots remain unchanged if engine state later mutates.
- Only exact built-in `SpawnInhabitants` and `AdjustResource` command types are accepted.
- Plugin-defined subclasses are rejected.
- Hostile mutation and command-injection tests pass.

### Performance benchmark

Added a JSON/CSV benchmark covering populations 30/100/500/1,000 in serial and threaded modes. It records mean/median/p95 tick latency, throughput, traced peak memory, seed, Python/platform information, project version, Git revision, and dirty status.

Observed three-tick inhabitants-layer measurements on this machine:

| Population | Serial mean | Threaded mean | Traced peak memory |
|---:|---:|---:|---:|
| 30 | 2.36 ms | 2.18 ms | ~0.02 MB |
| 100 | 10.62 ms | 9.55 ms | ~0.06 MB |
| 500 | 185.86 ms | 166.38 ms | ~3.1 MB |
| 1,000 | 701.81 ms | 699.34 ms | ~14.9 MB |

Threading provides little benefit at 1,000 inhabitants. The benchmark covers the inhabitants layer, not full end-to-end simulation or process RSS.

### Experiment pipeline

`run_experiments.py` was rewritten to:

- Require plan `schema_version` and `experiment_id`.
- Isolate each run under `<output>/<condition>/seed_<N>/`.
- Refuse non-empty output directories unless `--resume` or `--overwrite` is explicit.
- Resume only runs whose five required outputs and state hash validate.
- Reject resume when the plan SHA-256 differs.
- Atomically checkpoint `experiment_manifest.json` after every run.
- Write `run_index.csv` for analysis.
- Record commands, elapsed time, return codes, state hashes, validation errors, plan hash, revision, timestamps, and completion status.

Created `experiments_replication_v1.json`:

- baseline, seeds 1–5, 10,000 ticks
- no anti-stagnation, seeds 1–5, 10,000 ticks
- no combat, seeds 1–5, 10,000 ticks

## Current experiment status

Output root:

```text
experiment_runs/core-replication-v1/
```

At the most recent inspection:

- Baseline seed 1 completed: 10,000 rows, final population 29, elapsed 2,106.632 seconds, hash `92c291daa8daf9cc761eecead6a08d52616798e5e8a5a6eb1bfe62e1ef00a5f0`.
- Baseline seed 2 completed: 10,000 rows, final population 54, elapsed 2,673.26 seconds, hash `ced8a37deafaa84121cdc31816405384ac9f4aa8f2f7a4930541b5b79008e03e`.
- Baseline seed 3 was partial: 4,800 metric rows, final observed population 15.
- Experiment manifest had `resume_count: 1`, `completed_at: null`, and no final `complete` value.
- No active runner process was visible from the current sandbox during the latest inspection. Confirm externally before starting another runner.

Measured completed baseline runtimes are approximately 35 and 45 minutes, faster than the earlier conservative 15–25 hour batch estimate. No-combat may still be slower if population stays high.

Commands:

```bash
# Continue incomplete/invalid runs
python run_experiments.py --plan experiments_replication_v1.json --resume

# Validate everything without running
python run_experiments.py --plan experiments_replication_v1.json --verify
```

Important scientific caveat: these experiment manifests report a **dirty worktree**. For publication-grade reproducibility, commit the implementation first and rerun under a new experiment ID (recommended `core-replication-v2`) from a clean revision. A dirty flag plus commit does not uniquely preserve the patch.

## Files created

- `.github/workflows/ci.yml`
- `benchmarks/benchmark_simulation.py`
- `experiments_replication_v1.json`
- `src/thalren_vale/events.py`
- `src/thalren_vale/reproducibility.py`
- `src/thalren_vale/state.py`
- `tests/test_antistagnation.py`
- `tests/test_benchmark.py`
- `tests/test_config.py`
- `tests/test_events.py`
- `tests/test_experiment_runner.py`
- `tests/test_plugin_security.py`
- `tests/test_reproducibility.py`
- `tests/test_simulation_state.py`
- `CODEX_HANDOFF.md` (this document)

## Files changed

- `.gitignore`
- `README.md`
- `experiments.json` (added plan schema and experiment ID)
- `pyproject.toml`
- `run_experiments.py`
- `src/thalren_vale/__init__.py`
- `src/thalren_vale/combat.py`
- `src/thalren_vale/config.py`
- `src/thalren_vale/diplomacy.py`
- `src/thalren_vale/economy.py`
- `src/thalren_vale/factions.py`
- `src/thalren_vale/metrics.py`
- `src/thalren_vale/plugin_api.py`
- `src/thalren_vale/sim.py`
- `src/thalren_vale/technology.py`

## File deleted

- `src/thalren_vale_simulation.egg-info/PKG-INFO` (generated packaging artifact; now ignored)

## Pre-existing or user-owned untracked files

Do not assume these were created by this session or delete them without confirmation:

- `poetry.lock`
- `run.py`
- `resume_codex`
- `verify_runs`

At session start, `sim.py` already contained user modifications; those were preserved and subsequent work was layered on top.

## Important commands and outcomes

```bash
pip3 install -r requirements.txt
```

Installed runtime/dashboard dependencies successfully. Before this, `python -m thalren_vale --help` failed because `noise` was absent.

```bash
pip3 install 'pytest>=8,<10'
pip3 install -e '.[dev]'
```

Installed pytest and packaging tools successfully.

```bash
python -m pytest -q
```

Latest: 48 passed. Earlier milestones were 22, 24, 25, 28, 37, 41, 44, and 45 passing tests as functionality accumulated.

```bash
python -m compileall -q src tests benchmarks
git diff --check
```

Passed after changes.

```bash
python -m build --outdir /tmp/thalren-dist
python -m twine check /tmp/thalren-dist/*
```

Initial isolated build failed because sandbox network access could not fetch setuptools. It succeeded when rerun with approved network escalation. Final no-isolation build and `twine check` passed.

```bash
/tmp/thalren-wheel-test/bin/pip install /tmp/thalren-dist/thalren_vale_simulation-1.1.1-py3-none-any.whl
/tmp/thalren-wheel-test/bin/thalren-vale --seed 7 --ticks 3 --condition local_ci --disable-antistag
```

First install attempt failed because the isolated environment could not fetch `noise`; approved network escalation fixed it. The installed-wheel smoke run passed and wrote a state hash/manifest.

```bash
python benchmarks/benchmark_simulation.py --populations 30,100,500,1000 --modes serial threaded --ticks 3 --warmup 1 --output /tmp/benchmark-full-smoke.json
```

Completed successfully; results summarized above.

```bash
python run_experiments.py --seeds 1 --condition pipeline_smoke --ticks 2 --output-dir /tmp/thalren-pipeline-smoke --overwrite
python run_experiments.py --seeds 1 --condition pipeline_smoke --ticks 2 --output-dir /tmp/thalren-pipeline-smoke --resume
python run_experiments.py --seeds 1 --condition pipeline_smoke --ticks 2 --output-dir /tmp/thalren-pipeline-smoke --verify
```

Fresh run, validated skip-on-resume, and verification all passed.

## Failures and unresolved issues

1. **Publication runs use a dirty worktree.** Commit and rerun under a fresh experiment ID before treating results as archival evidence.
2. **Threaded mode is nondeterministic.** It shares Python's global PRNG; seeded CLI runs deliberately switch to serial mode.
3. **Legacy regex event classifier remains.** Most metrics events are typed, but rare legacy strings still use `_classify_and_record_events()`.
4. **Broad exception suppression remains.** Metrics, mythology, and several lifecycle paths use `except Exception: pass`, which can hide instrumentation failures.
5. **`sim.py` remains large and coupled.** State migration is incremental; module-global compatibility aliases still exist.
6. **Benchmark scope is limited.** It measures the inhabitants layer with `tracemalloc`, not full-run RSS, metrics/dashboard/logging overhead, or every layer independently.
7. **CI has not run remotely.** Local equivalent steps passed, but GitHub Actions status is unknown until changes are pushed.
8. **Partial baseline seed 3 exists.** `--resume` should rerun it because required completion outputs are absent.
9. **Experiment analysis aggregation is not yet updated.** `run_index.csv` exists, but figure/statistics scripts still need to consume the new nested experiment layout.
10. **Persistent cross-run history remains the README roadmap feature** and has not been implemented.
11. A piped smoke command once produced `BrokenPipeError` when `rg` was unavailable inside a re-executed `/tmp` shell. This is not fixed; normal CLI execution works.

## Model or training configuration

No model was trained, fine-tuned, or changed.

Existing optional Ollama configuration remains:

- `GAME_MODEL = "phi3:3.8b-mini-4k-instruct-q4_0"`
- `NARRATIVE_MODEL = "internlm2:1.8b-chat-v2.5-q4_K_M"`
- `MYTHOLOGY_ENABLED = False`

The mythology layer remains disabled by default and can now also be excluded with `--disable-layer mythology`. No prompts, model weights, training data, temperature, token limit, or Ollama endpoint were changed.

Simulation configuration changed substantially through `SimulationConfig`, but this is runtime validation/configuration, not ML training configuration.

## Recommended exact next steps

1. Stop/confirm there is no external experiment process still running.
2. Review the dirty diff carefully, especially `sim.py`, `config.py`, `events.py`, `plugin_api.py`, `run_experiments.py`, and tests.
3. Commit the engineering changes so the code revision is reconstructible.
4. Copy the replication plan to `experiments_replication_v2.json`, change `experiment_id` to `core-replication-v2`, and run it from the clean commit:

   ```bash
   python run_experiments.py --plan experiments_replication_v2.json
   ```

5. Let the full 15-run batch complete; use `--resume` after interruption.
6. Validate:

   ```bash
   python run_experiments.py --plan experiments_replication_v2.json --verify
   ```

7. Update `analyze_logs.py`, `generate_figures.py`, and related analysis scripts to read `run_index.csv` and nested run directories.
8. Generate condition-level tables with uncertainty across the five shared seeds; directly compare baseline/no-antistagnation/no-combat using paired seeds.
9. Reassess all research claims affected by the previously broken anti-stagnation ablation and single-seed no-combat result.
10. Finish migrating rare legacy events, then remove regex metrics classification and replace broad exception swallowing with explicit logged failures.
11. Push to GitHub and confirm the Python 3.10–3.13 Actions matrix is green.

## Where to start reading

1. `CODEX_HANDOFF.md` — this state summary.
2. `src/thalren_vale/sim.py` — orchestration, reset lifecycle, CLI, anti-stagnation, event/metrics flow.
3. `src/thalren_vale/config.py` — effective configuration and validation.
4. `src/thalren_vale/state.py` — state ownership and compatibility migration.
5. `src/thalren_vale/events.py` and `src/thalren_vale/metrics.py` — structured instrumentation.
6. `src/thalren_vale/reproducibility.py` — canonical hashes and run manifests.
7. `run_experiments.py` and `experiments_replication_v1.json` — research batch execution.
8. `src/thalren_vale/plugin_api.py` and `tests/test_plugin_security.py` — plugin boundary.
9. `benchmarks/benchmark_simulation.py` — scaling benchmark.
10. `.github/workflows/ci.yml` and `pyproject.toml` — CI, packaging, dependency groups.
11. `tests/` — executable behavioral contract for all session changes.
