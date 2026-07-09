---
title: "Wiki Ingest Handoff"
status: "draft"
project: "Thalren Vale"
tags:
  - ai-simulation
  - thalren-vale
  - handoff
  - wiki-ingest
---

# Wiki Ingest Handoff

## Summary

The Thalren Vale / `ai-sim-emergent-agents` documentation and lightweight research evidence have been organized into:

`LLM-Wiki/content/ai-simulation/thalren-vale/`

This was done as a non-destructive wiki ingest. Source documentation remains in place; final validated experiment outputs were not moved or deleted.

## Directory structure created

- `LLM-Wiki/content/ai-simulation/thalren-vale/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/experiments/core-replication-v1/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/experiments/core-replication-v1/artifacts/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/experiments/pop-equilibrium/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/experiments/pop-equilibrium/artifacts/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/engineering/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/handoffs/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/decisions/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/evidence/lightweight-data/logging-ablation-v1/`
- `LLM-Wiki/content/ai-simulation/thalren-vale/publication/`

## Files copied

Documentation was copied with `cp -a`, not moved:

- `CODEX_HANDOFF.md`
- `CODEX_POST_EXPERIMENT_HANDOFF.md`
- `EXPERIMENT_COMPLETION_REPORT.md`
- `SUPERSEDED_ATTEMPTS_CLEANUP_PLAN.md`
- `LOGGING_ABLATION_PLAN.md`
- `LOGGING_ABLATION_REPORT.md`
- `CORE_REPLICATION_PLOTS_REPORT.md`
- `RAID_SEMANTICS_AUDIT.md`
- `CODEX_LOGGING_AND_PLOTS_HANDOFF.md`

Core replication lightweight artifacts copied:

- `run_level_summary.csv`
- `condition_summary.csv`
- `paired_seed_comparisons.csv`
- `paired_seed_comparison_summary.csv`
- `event_type_counts.csv`
- `largest_files.csv`
- `superseded_attempts.csv`
- `analysis_manifest.json`

Logging ablation lightweight artifacts copied:

- `logging_ablation_results.csv`
- `logging_ablation_summary.csv`

## Files excluded

The ingest intentionally excluded:

- Full `experiment_runs/core-replication-v1/` run directories.
- Multi-GB no-combat raw logs.
- Manual chronicles.
- Raw text logs over 50 MB.
- Structured event files over 50 MB.
- Runtime caches and simulator-generated bulk outputs.

These files should remain referenced by path, not copied into the wiki.

## New wiki pages created

Key pages include:

- `index.md`
- `project-overview.md`
- `architecture.md`
- `research-roadmap.md`
- `research-operating-system.md`
- `current-status.md`
- `open-questions.md`
- `ethics-and-boundaries.md`
- `experiments/index.md`
- `experiments/core-replication-v1/index.md`
- `experiments/core-replication-v1/analysis-artifacts.md`
- `experiments/core-replication-v1/interpretation.md`
- `experiments/core-replication-v1/caveats.md`
- `experiments/pop-equilibrium/index.md`
- `engineering/index.md`
- `engineering/reproducibility.md`
- `engineering/experiment-runner.md`
- `engineering/logging-and-observability.md`
- `engineering/plugin-security.md`
- `engineering/state-lifecycle.md`
- `handoffs/index.md`
- `decisions/index.md`
- `evidence/index.md`
- `publication/index.md`
- `publication/pilot-paper-outline.md`
- `wiki-ingest-manifest.md`

## Missing source files

These requested files were not present in the project root during ingest:

- `THALREN_VALE_ULTIMATE_ROADMAP.md`
- `THALREN_VALE_RESEARCH_OPERATING_SYSTEM.md`

Population equilibrium artifacts were also not found:

- `qtable_pop_300_300.json`
- `pop_equilibrium_summary.json`

## Status and interpretation policy

- `core-replication-v1` is represented as `pilot-supported`, not archival-grade.
- The wiki notes preserve the caveats: dirty-worktree provenance, logging overhead unresolved, raid semantics unresolved/needs audit, and five seeds per condition.
- Raw logs are intentionally excluded from the wiki because the no-combat condition produced multi-GB text output.

## Validation

Validation commands requested for this handoff:

```bash
find LLM-Wiki/content/ai-simulation/thalren-vale -maxdepth 6 -type f | sort
du -h --max-depth=4 LLM-Wiki/content/ai-simulation/thalren-vale | sort -h | tail -30
git status --short
python -m pytest -q
```

Results recorded on `2026-07-09`:

- `find LLM-Wiki/content/ai-simulation/thalren-vale -maxdepth 6 -type f | sort` listed the expected wiki pages plus copied lightweight CSV/JSON artifacts.
- `du -h --max-depth=4 LLM-Wiki/content/ai-simulation/thalren-vale | sort -h | tail -30` reported `316K` total for the Thalren Vale wiki content tree, confirming no huge raw logs were copied.
- `git status --short` shows the parent simulation repo was already dirty and now includes `?? LLM-Wiki/` and `?? WIKI_INGEST_HANDOFF.md`.
- `git -C LLM-Wiki status --short` shows `?? content/`.
- `python -m pytest -q` failed during collection because it picked up nested `LLM-Wiki/tests` without the `llm_wiki` package installed on the parent repo test path: `ModuleNotFoundError: No module named 'llm_wiki'`.
- Simulator-scoped fallback passed: `python -m pytest tests test_parse_logs.py -q` produced `60 passed in 3.60s`.

## Post-ingest pytest discovery fix

- The initial parent `python -m pytest -q` failure was a discovery issue: pytest recursed into `LLM-Wiki/tests`, where `llm_wiki` is not importable from the simulation repository environment.
- Parent pytest configuration in `pyproject.toml` now sets `testpaths = ["tests"]` and excludes `LLM-Wiki`, `experiment_runs`, `.git`, `.venv`, `build`, and `dist` through `norecursedirs`.
- Final parent verification passed: `python -m pytest -q` produced `41 passed in 3.57s`. This is the canonical simulator suite under `tests/`; the root-level `test_parse_logs.py` remains runnable explicitly when that utility is being changed.

## Next recommended wiki additions

1. Decide whether `LLM-Wiki/content/` is the long-term content root or whether these pages should be imported into the LLM Wiki app's `workspace/wiki/approved/` flow.
2. Add source manifests for the copied experiment reports and CSV summaries if the wiki app will ingest them through its canonical source pipeline.
3. Add a short page mapping each generated figure/table to its source CSV.
4. Add a clean provenance note once a clean-tagged replication is available.
5. Add a dedicated no-combat nondeterminism investigation page after that work is complete.
