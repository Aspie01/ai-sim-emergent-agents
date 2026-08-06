# Repository map

## Authoritative implementation areas

| Path | Role | Authority notes |
| --- | --- | --- |
| `src/thalren_vale/` | Installed package and current simulator implementation | Primary executable source |
| `src/thalren_vale/sim.py` | CLI, initialization, layer orchestration, termination, finalization | Exact lifecycle authority |
| `src/thalren_vale/config.py` | Defaults, validation, feature dependency normalization | Effective configuration authority |
| `src/thalren_vale/state.py` | Run-scoped core collection owner | Compatibility aliases still exist in modules |
| `src/thalren_vale/artifact_contract.py` | Structured CSV and manifest contract constants | Current schema definitions |
| `src/thalren_vale/artifact_validation.py` | Streaming deep artifact validation and readiness distinction | Validation authority |
| `run_experiments.py` | Generic fresh-root batch runner and verifier | Engineering runner, not V2 orchestrator |
| `tests/` | Default pytest suite | `pyproject.toml` limits discovery to this directory |
| `benchmarks/` | Bounded engineering performance harness | Not research evidence |
| `docs/handbook/` | Living Technical Handbook v0.1 | Authoritative prose for this recorded revision |

## Domain modules

| Module | Main responsibility |
| --- | --- |
| `world.py` | Grid, biomes, tile resources, spatial and settlement indexes |
| `inhabitants.py` | Needs, movement, harvesting, legacy trust/swaps, reproduction primitives |
| `beliefs.py` | Experience-derived bounded beliefs and sharing |
| `factions.py` | Formal factions, reserves, territory, settlement lifecycle, schisms and mergers |
| `economy.py` | Individual/faction transfers, currency, prices, routes, scarcity, raids |
| `social.py` | Optional stable-ID directed relationships and maintenance |
| `coalitions.py` | Optional deterministic informal-coalition graph and lifecycle |
| `language.py` | Optional individual signal production/comprehension, dialect context, language contact, and on-demand summaries |
| `combat.py` | Formal wars, battles, alliances, tribute and post-war changes |
| `technology.py` | Research tree and passive effects |
| `diplomacy.py` | Treaties, council votes, reputation, surrender terms |
| `religion.py` | Religions, temples, priests, conversion and holy-war markers |
| `events.py` | Ordered typed/narrative observation journal |
| `metrics.py` | Required CSV writers and run summary |
| `reproducibility.py` | Canonical selected-state hash and run manifest |
| `plugin_api.py` | Immutable bridge snapshots and validated plugin commands |
| `dashboard_bridge.py`, `dashboard.py`, `display.py` | Diagnostic presentation |
| `mythology.py`, `ra_tracker.py` | Optional narrative and belief-tracking observers |

`civilization.py` is a legacy standalone status path and is not called by `sim.run()`.

## Entry points

| Command | Current use |
| --- | --- |
| `python -m thalren_vale` | Preferred simulator entry, including explicit-seed hash-seed guard |
| `thalren-vale` | Installed console script calling `sim.run()` directly; set `PYTHONHASHSEED=0` yourself for reproducible use |
| `python run_experiments.py` | Fresh-root plan execution or existing-output verification |
| `streamlit run src/thalren_vale/dashboard.py` | Optional dashboard |

Root analysis, plotting, pilot, cleanup, and source-rewrite scripts are specialized, historical, or maintenance tools. They are not interchangeable with the current simulator or deep validator. See [stale and superseded data](../data/stale-and-superseded-data.md).

## Data-bearing paths

- Direct simulator required artifacts: working-directory `data/`.
- Direct full-mode diagnostics: working-directory `logs/`, chronicle, era-export, and dashboard files.
- Batch roots: normally `experiment_runs/<experiment_id>/`.
- Existing `experiment_runs/`, `data/`, and `logs/` may contain evidence-bearing user data. Do not clean, overwrite, or infer current behavior from them.
- `LLM-Wiki/` is a separate nested repository and outside this handbook run.

## Existing documentation status

The root `README.md` remains useful as historical project orientation but is materially stale for current thresholds, tick layers, social/language features, runner resume behavior, and several later-layer effects. This handbook records the executable revision without rewriting historical review documents.

## Implementation evidence

- Package metadata: `pyproject.toml`.
- Instruction authority: `AGENTS.md`.
- Current source inventory: `src/thalren_vale/`.
- Default tests: `pyproject.toml` `[tool.pytest.ini_options]`, `tests/`.
- Generated-data exclusions: `.gitignore`.
