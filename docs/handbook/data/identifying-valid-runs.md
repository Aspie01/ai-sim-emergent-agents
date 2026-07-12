# Identifying Valid Runs

Do not infer validity from a process return code, a state hash, a manifest, a
summary row, or a batch `complete` flag alone. The current evidence unit is the
complete run directory checked under an explicit validation mode.

## Fast decision table

| Observation | Current classification | Safe interpretation |
| --- | --- | --- |
| Schema-2 run passes strict validation, no external contract | `schema2_valid` | Complete engineering evidence under the schema; not V2-ready |
| Schema-2 run passes strict validation and a complete exact external contract | `v2_ready` | Validator readiness gate passed; current runner does not provide this path |
| Schema-1 run passes legacy/auto validation | `legacy` | Readable historical evidence; never V2-ready |
| Any required file/field/check fails | `invalid` | Do not use as a completed biological endpoint |
| Runner timeout | `wall_clock_limit` | Censored tractability/audit information; partial artifacts are not final endpoints |
| Child SIGINT | `cancelled` | Audit information only; never resume-skipped as completed |
| Other nonzero child exit | `exception` | Failure evidence only |
| Zero exit with invalid artifacts | `invalid_output` | Process success did not establish evidence success |
| Historical table says “superseded” | No current authoritative lifecycle | Do not infer selection without an immutable ledger—which does not exist yet |

## Run-directory checklist

For condition `<condition>` and seed `<N>`, confirm the directory contains:

```text
data/metrics_<condition>_seed_<N>.csv
data/faction_events_<condition>_seed_<N>.csv
data/beliefs_<condition>_seed_<N>.csv
data/run_summaries.csv
data/run_manifest_<condition>_seed_<N>.json
```

Then use the plan-based read-only verifier:

```bash
python run_experiments.py \
  --plan /absolute/path/to/plan.json \
  --output-dir /absolute/path/to/output-root \
  --verify \
  --validation-mode strict
```

This starts no child when `--plan` is supplied. It validates expected cells but
does not validate root-level batch metadata, unknown extra cells, current
commit/tag/environment, or V2 readiness.

For a direct-run directory rather than a batch cell, call the run-level
validator on that directory itself:

```bash
REPO=/home/lfs/Projects/ai-sim-emergent-agents
RUN_DIR=/absolute/path/to/direct-run
CONDITION=handbook-smoke
SEED=42
TICKS=5
PYTHONPATH="$REPO/src" python - "$RUN_DIR" "$CONDITION" "$SEED" "$TICKS" <<'PY'
from pathlib import Path
import sys
from thalren_vale.artifact_validation import inspect_run_outputs

run_dir, condition, seed, ticks = sys.argv[1:]
report = inspect_run_outputs(
    Path(run_dir),
    condition,
    int(seed),
    expected_ticks=int(ticks),
    mode="strict",
)
print(f"{report.classification}: valid={report.valid}, v2_ready={report.v2_ready}")
for error in report.errors:
    print(error)
raise SystemExit(0 if report.valid else 1)
PY
```

The direct validator expects required files under `$RUN_DIR/data/`; the
plan-based verifier expects the condition/seed batch hierarchy.

## What strict validation establishes

A strict valid result establishes all of the following for the inspected
files:

- ordinary contained nonsymlink paths;
- schema-2 termination and configuration structure;
- a completed requested horizon or registered early extinction;
- end-of-tick metrics coverage through `final_tick`;
- event and belief tick/cadence constraints;
- one summary row and cross-artifact aggregate agreement;
- matching artifact inventory sizes, SHA-256 values, row counts, and versions;
- finalized/closed writer health with no unresolved required failures;
- a well-formed manifest state hash and present provenance.

It does not establish:

- scientific validity of an endpoint or causal claim;
- correctness of unobserved simulation semantics;
- recomputation of the state hash from CSVs;
- freshness against the current checkout unless an external contract is
  supplied;
- plugin identity;
- a clean tagged revision or environment fingerprint;
- V2 authorization or execution.

## Inspect the manifest

After validation, inspect these fields together:

| Field | Required interpretation |
| --- | --- |
| `requested_ticks` | Intended horizon recorded by the child |
| `final_tick` / `completed_ticks` | Last fully completed tick; currently equal |
| `termination_reason` | `requested_ticks_reached` or registered `extinction` for strict completion |
| `result_status` | Must be `completed` |
| `completed_normally` | Must be `true` |
| `writer_health` | Finalized/closed, zero pending rows, no unresolved/nonrecoverable failures |
| `artifact_inventory` | Must match required structured files |
| `configuration` | Effective controls, not merely requested CLI text |
| `state_hash` | Canonical final-state SHA-256 shape; compare only under exact behavior/configuration provenance |
| `code` | Current manifest stores commit and dirty flag, but not tag |

An extinction on the requested final tick is recorded as
`requested_ticks_reached`; early extinction uses `extinction` and must end with
population zero.

## Valid is not V2-ready

`ExpectedRunContract` is a separate programmatic readiness input. It requires
exact seed/condition/ticks/log mode, anti-stagnation/combat/raid controls,
disabled layers, execution mode, plan identity/hash, commit/tag/clean state,
environment fingerprint, and artifact policy. The current runner never supplies
it, and current run manifests omit several required fields.

Therefore:

- `--verify` can exit zero for `schema2_valid` evidence;
- `--verify --validation-mode auto` can also exit zero for `legacy` evidence;
- neither exit status means V2-ready;
- the current runner cannot produce authoritative V2 evidence.

## Incomplete and failed runs

An incomplete or failed run commonly has one or more of:

- missing manifest;
- noncompleted status;
- `final_tick` below the requested horizon without registered extinction;
- metrics ending at the wrong tick;
- partial/header-only/truncated CSVs;
- rows from a failed partial tick beyond `final_tick`;
- pending/unresolved writer failures;
- checksum/row-count mismatch;
- runner timeout, cancellation, or exception diagnostics.

Preserve these files as audit or tractability information. Do not promote them
to completed endpoints and do not silently drop their status from operational
reporting.

## Stale runs

A run is stale relative to a proposed use when its plan, configuration,
revision, environment, schema, or plugin context differs. Present malformed
provenance is invalid, but missing later-slice provenance may remain
schema-valid. The current CLI has no complete freshness comparison.

Before comparing state hashes or outcomes, manually retain the exact plan
bytes, commit, dirty state, Python environment, controls, plugin inventory,
seed, and horizon. If any is unknown, label the comparison limited rather than
assuming equivalence.

## Batch metadata caveats

`experiment_manifest.json` and `run_index.csv` help locate results, but current
deep validation checks run directories, not those root files. Batch
`complete: true` means every child had return code zero and valid strict
artifacts. It does not prove a frozen plan snapshot, immutable attempts,
fail-fast behavior, clean-tag provenance, or V2 readiness.

## Implementation evidence

- Validator: [`src/thalren_vale/artifact_validation.py`](../../../src/thalren_vale/artifact_validation.py)
- Contract: [`src/thalren_vale/artifact_contract.py`](../../../src/thalren_vale/artifact_contract.py)
- Runner: [`run_experiments.py`](../../../run_experiments.py)
- Tests: [`tests/test_artifact_validation.py`](../../../tests/test_artifact_validation.py),
  [`tests/test_experiment_runner.py`](../../../tests/test_experiment_runner.py),
  [`tests/test_run_termination.py`](../../../tests/test_run_termination.py)
- Related: [Artifact catalog](artifact-catalog.md),
  [Stale and superseded data](stale-and-superseded-data.md)
