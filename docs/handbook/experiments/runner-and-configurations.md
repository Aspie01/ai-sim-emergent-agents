# Experiment Runner and Configurations

## Overview

`run_experiments.py` is a generic engineering batch runner. It turns a schema-1
JSON plan into ordered condition/seed cells, launches one isolated Python child
per cell, and validates each child's structured output. It is fresh-root-only
and is not a completed Core Replication V2 orchestrator.

## Why it exists

The runner centralizes repeatable child commands, seed expansion, output
layout, timeout handling, batch metadata, and post-child artifact validation.
It reduces manual command drift, but the current implementation does not yet
seal all inputs needed for research-ready provenance.

## Current status

- Generic plan execution: **Implemented but experimental**.
- Fresh-root path and symlink containment: **Stable and verified**.
- Nonempty-root resume and overwrite: **Planned, not implemented**.
- Core Replication V2 matrix generation and execution: **Planned, not
  implemented**.
- V2 S0/S1/P1/P2/Full: unauthorized and unperformed.

## Plan schema

The accepted plan schema version is `1`:

```json
{
  "schema_version": 1,
  "experiment_id": "bounded-engineering-example",
  "default_ticks": 5,
  "timeout_seconds": 60,
  "conditions": [
    {
      "name": "baseline",
      "seeds": "1-2",
      "extra_args": ["--log-mode", "metrics_only"]
    }
  ]
}
```

This example illustrates syntax only. It is not a frozen research contract and
does not authorize execution.

| Field | Type/current default | Validation and effect |
| --- | --- | --- |
| `schema_version` | integer; required | Must equal `1`. |
| `experiment_id` | string; required | Filename-safe, 1–64 characters. Used by the default output root. |
| `default_ticks` | integer-like; `5000` | Must convert to a positive integer. |
| `timeout_seconds` | integer-like or `null`; `86400` | Default child timeout; positive when set. |
| `conditions` | nonempty list | Expanded in listed order. Names must be unique. |
| condition `name` | string | Filename-safe and unique. |
| condition `seeds` | string-like; `1-5` | Single seed, comma list, or ascending inclusive range. Duplicates are removed while first-occurrence order is retained. |
| condition `ticks` | integer-like | Overrides `default_ticks`. |
| condition `extra_args` | string or list of strings | String form is parsed by `shlex.split`; passed after runner-owned child arguments. |
| condition `timeout_seconds` | integer-like or `null` | Overrides the plan timeout. |

The loader rejects the complete social-memory, coalition, language,
coalition-dialect, and language-contact option families—including recognized
proper prefixes and `--flag=value` forms—before root creation. These controls
are engineering-only and not contracted for research-runner use.

## Cell construction and command

Every expanded cell is copied into an exact frozen record containing:

- condition;
- seed;
- tick horizon;
- detached tuple of extra arguments;
- timeout;
- optional display announcement.

Duplicate `(condition, seed)` cells and malformed caller-owned cell objects are
rejected before root creation. The child command is:

```text
<current-python> -m thalren_vale
  --seed <seed>
  --condition <condition>
  --ticks <ticks>
  <extra_args...>
```

The child runs with its run directory as `cwd`, project `src` prepended to
`PYTHONPATH`, and `PYTHONHASHSEED=0`.

Current `extra_args` are not a complete ownership boundary. They can still
repeat runner-owned seed, condition, tick, log-mode, anti-stagnation, combat,
or raid options. Seed/condition/tick overrides generally cause expected-file or
identity validation failure, but other control overrides can remain
schema-valid because the runner supplies no external expected-run contract.
This is one reason the runner is not V2-ready.

## Output-root contract

Default plan output:

```text
experiment_runs/<experiment_id>/
```

Explicit `--output-dir` is recommended. Before any child starts, the runner:

1. converts the requested root to a lexical absolute path;
2. rejects symlinked path components and non-directory targets;
3. requires the root to be absent or truly empty;
4. creates and records the root filesystem identity;
5. constructs only canonical `<condition>/seed_<N>` descendants;
6. revalidates root, metadata, condition, and cell identities throughout the
   invocation;
7. rejects unknown, missing, replaced, or symlinked entries.

`--resume` and `--overwrite` do not relax this contract. On a nonempty root,
both fail without changing existing bytes. Their only successful case is an
absent or empty root, where every cell is executed as new.

## Batch metadata

`experiment_manifest.json` uses runner schema 1 and records:

- experiment and plan schema identities;
- SHA-256 of the exact raw plan bytes;
- absolute plan path;
- current commit and dirty flag;
- start and completion timestamps;
- `resume_count`, currently always zero;
- full per-cell result dictionaries;
- final `complete` flag.

`run_index.csv` is a reduced projection of results. The batch manifest is
atomically replaced after each persisted result; the index is directly
rewritten. Neither is an append-only attempt ledger.

## Result classification

| Runner result | Meaning |
| --- | --- |
| `completed` | Child returned zero and strict run-artifact validation passed. |
| `wall_clock_limit` | Per-cell subprocess timeout expired. |
| `cancelled` | Child returned a SIGINT-style status. |
| `exception` | Child returned another nonzero status. |
| `invalid_output` | Process status was not enough to establish valid artifacts. |
| `superseded` | Constant exists, but no current lifecycle implements it. |

Batch `complete: true` means every cell met the runner's `completed` rule. It
does not mean any cell is `v2_ready`.

## Configuration boundaries

The simulator creates a validated effective `SimulationConfig` from CLI
arguments. The run manifest records this effective configuration, including
normalization notices. Strict validation rejects malformed or contradictory
present controls. Readiness applies an additional temporary veto: social
memory, informal coalitions, endogenous language, coalition dialects, and
language contact must all remain at exact disabled defaults. Enabled language
milestones are engineering-only and valid-but-nonready.

The runner currently has no canonical A/C/R condition generator and does not
enforce `metrics_only`, exact anti-stagnation/combat/raid controls, budgets, or
registered estimands. Those requirements remain in the unexecuted V2 plan.

## Supported verification-only workflow

```bash
python run_experiments.py \
  --plan /absolute/path/to/plan.json \
  --output-dir /absolute/path/to/output-root \
  --verify \
  --validation-mode strict
```

This does not launch children. It checks expected cells only; it does not
validate root-level batch metadata, unknown extra runs, a plan snapshot, the
current revision, or an environment fingerprint. It also returns success for
valid but non-V2-ready evidence.

## Limitations and planned work

The current runner lacks fail-fast dispatch, immutable attempts, an append-only
ledger, explicit attempt selection/supersession, clean annotated-tag and
environment/plugin preflight, quota enforcement, safe resume, and nonexecuting
matrix expansion. Each is **Planned, not implemented**. No V2 plan JSON or
research tier has been authorized or run.

## Implementation evidence

- Source: [`run_experiments.py`](../../../run_experiments.py),
  [`src/thalren_vale/config.py`](../../../src/thalren_vale/config.py)
- Tests: [`tests/test_experiment_runner.py`](../../../tests/test_experiment_runner.py),
  [`tests/test_config.py`](../../../tests/test_config.py)
- Active unexecuted plan:
  [`CORE_REPLICATION_V2_PLAN.md`](../../../CORE_REPLICATION_V2_PLAN.md)
- Related operations: [Operating Thalren Vale safely](../getting-started/operations.md)
- Drafting verification: current source and tests inspected; no plan, child, or
  experiment was executed.
