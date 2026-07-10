# Core V2 Runner Hardening Backlog

**Status:** Draft implementation backlog  
**Scope:** Runner, manifests, validation, provenance, and orchestration only  
**Non-authorization:** This document authorizes no simulation or Core Replication V2 run.

## Purpose and invariants

This backlog decomposes the prerequisites identified by `CORE_REPLICATION_V2_PLAN_REVIEW.md` into ten bounded, independently testable slices. The goal is to make a future V2 smoke tier termination-aware, configuration-conformant, fail-fast, resumable, and auditable.

Every slice must preserve these invariants:

- Do not change simulation dynamics, RNG consumption, or behaviorally relevant state hashes.
- Keep historical V1 artifacts readable and verifiable; introduce schema-versioned V2 behavior rather than rewriting history.
- Never accept file presence alone as proof of a completed run.
- Stream large CSV validation; never load event files fully into memory.
- Preserve every attempt and distinguish attempts from final selected replicates.
- Never treat retries, diagnostic hash probes, or superseded attempts as additional evidence.
- Keep all tests bounded; runner failure tests should use synthetic artifacts, mocks, or tiny subprocess fixtures rather than research experiments.

## Current gaps that drive the work

- `sim.py` catches `KeyboardInterrupt`, finalizes artifacts, and may exit successfully without reaching the requested tick.
- `validate_run_outputs()` currently checks nonempty files, seed, condition, and hash length, but not termination, achieved ticks, effective controls, logging mode, provenance, or CSV integrity.
- `run_from_plan()` continues after failed cells.
- Resume can skip shallowly valid partial artifacts, deletes prior finalization/error files, and rewrites batch history.
- Commit/dirty state is recorded but not enforced; tag and environment identity are not captured.
- No nonexecuting matrix-expansion command exists.

## Recommended implementation sequence

| Order | Slice | Why here |
|---:|---|---|
| 1 | Termination-aware manifests | Establishes the authoritative completion model used everywhere else |
| 2 | Environment fingerprinting | Defines stable provenance data before contracts and preflight consume it |
| 3 | Nonexecuting matrix expansion | Produces the canonical expected cell/command contracts without running anything |
| 4 | Exact condition-contract validation | Binds each expanded cell to expected effective configuration |
| 5 | Deep artifact validation | Validates termination, contract, provenance, and streamed artifacts together |
| 6 | Immutable attempt directories | Establishes a non-destructive physical layout before history is recorded |
| 7 | Append-only attempt ledger | Records immutable attempt lifecycle events and final selections |
| 8 | Clean-tag and expected-commit preflight | Adds the fail-closed execution gate before orchestration is finalized |
| 9 | Stop-on-first-failure behavior | Stops safely after persisting a failed attempt and batch state |
| 10 | Safe resume and supersession | Integrates validation, attempts, ledger, fail-fast, and provenance checks |

Dependency shorthand:

```text
termination ────────────────────────────────┐
matrix ─> condition contract ───────────────┼─> deep validation ─┐
immutable attempts ─> attempt ledger ────────────────────────────┼─> fail-fast ─> safe resume
environment + matrix ─> clean-tag execution preflight ──────────┘
```

## Slice 1 — Termination-aware manifests

**Goal:** Make the per-run manifest authoritative about what was requested, how far execution progressed, and why it stopped. Define `final_tick` as the last fully completed tick, not the tick that merely started.

**Affected files:**

- `src/thalren_vale/sim.py`
- `src/thalren_vale/reproducibility.py`
- `src/thalren_vale/metrics.py` only if logger-health/summary fields are surfaced
- `tests/test_reproducibility.py`
- new focused termination tests or additions to `tests/test_experiment_runner.py`

**Required tests:** requested horizon reached; natural extinction; cancellation/`KeyboardInterrupt`; injected mid-tick exception; exception during finalization; manifest atomicity; state hash unchanged for a normal seeded run. Assert fields including `requested_ticks`, `final_tick`, `termination_reason`, `result_status`, `completed_normally`, timestamps, and logger-health status.

**Failure cases:** cancellation exits zero; partial tick reported complete; exception artifacts labeled completed; manifest write failure hidden; natural extinction confused with cancellation; termination-only fields accidentally enter the state-hash payload.

**Dependencies:** None. This is the foundational slice.

**Estimated risk:** High. It touches the simulation lifecycle and must preserve best-effort cleanup while returning the correct process result.

**Recommended implementation order:** 1 of 10.

**Acceptance criteria:**

- Requested-horizon completion, registered natural termination, cancellation, and exception are distinguishable.
- Cancellation and exception propagate a non-success process result after best-effort flushing.
- A partial manifest can exist without ever claiming scientific completion.
- Natural extinction is accepted only under an explicit policy later supplied to validation.
- Normal same-seed state hashes remain unchanged.

## Slice 2 — Deep artifact validation

**Goal:** Replace boolean presence validation with a structured, streaming validation result that proves termination, schema, content consistency, effective assignment, and provenance.

**Affected files:**

- `run_experiments.py`, preferably extracting validation into a small dedicated module
- `src/thalren_vale/metrics.py` for exported schema constants or logger-health reporting
- `tests/test_experiment_runner.py`
- `tests/test_log_modes.py`
- new synthetic artifact fixtures/helpers

**Required tests:** missing/empty files; header-only metrics; malformed JSON; malformed CSV quoting; wrong headers; wrong seed/condition; noncontiguous metrics ticks; regressing event ticks; events beyond `final_tick`; duplicate/wrong summary rows; wrong terminal status; unresolved flush/write errors; wrong output policy; valid zero-event and pre-100-tick belief files; large synthetic CSV validated with bounded memory.

**Failure cases:** truncated CSV accepted; header-only file accepted as a completed multi-tick run; valid zero-event run rejected; validator loads millions of rows; checksum/config error reduced to a generic message; exception-finalized artifacts accepted on resume.

**Dependencies:** Slices 1 and 3. Termination fields and the expected condition contract must exist first.

**Estimated risk:** High. Strict validation can invalidate legacy assumptions, so schema-aware V1 read-only compatibility and V2 evidence rules must be explicit.

**Recommended implementation order:** 5 of 10.

**Acceptance criteria:**

- Returns a typed result with stable error codes and human-readable details.
- Streams metrics/events/beliefs and uses bounded memory.
- Requires contiguous metrics through the accepted `final_tick`, schema-valid event/belief rows, exactly one attempt summary, exact manifest contract, and zero unresolved writer failures.
- Distinguishes `completed`, valid registered natural terminal, and invalid/incomplete outcomes.
- `--verify` and resume use the same deep validator.

## Slice 3 — Exact condition-contract validation

**Goal:** Bind every condition to explicit factor values and generate controlled CLI arguments from those values, preventing a condition label from silently executing another intervention.

**Affected files:**

- `run_experiments.py`
- `src/thalren_vale/config.py` if shared contract normalization is extracted there
- plan-schema constants/validation, likely with a new schema version
- `tests/test_experiment_runner.py`
- `tests/test_config.py`
- `tests/test_raid_control.py`

**Required tests:** all eight anti-stagnation × combat × raids contracts; deterministic disabled-layer ordering; `metrics_only` required; manifest match/mismatch; forbidden factor overrides inside `extra_args`; duplicate `--seed`, `--ticks`, `--condition`, or `--log-mode`; combat-off/raids-on compatibility; schema-1 historical plan remains readable but is not accepted as a V2 evidence contract.

**Failure cases:** `no_*` name with opposite flags; combat implicitly disables raids; aliases create duplicate/conflicting flags; free-form args override runner-owned values; manifest lacks enough information to derive combat policy.

**Dependencies:** Slice 10's matrix-expansion model should be designed first; implementation order places nonexecuting expansion before this slice. Slice 1 supplies authoritative manifest fields.

**Estimated risk:** Medium-high. A plan-schema bump affects runner inputs but need not affect simulation behavior.

**Recommended implementation order:** 4 of 10.

**Acceptance criteria:**

- V2 plan cells declare `anti_stagnation_enabled`, `combat_enabled`, `raids_enabled`, and `log_mode` explicitly.
- Runner-owned CLI flags are generated rather than trusted from condition prose.
- Controlled flags cannot be overridden through `extra_args`.
- Expected manifest values are canonical and machine-comparable.
- Any effective-config mismatch makes the attempt invalid.

## Slice 4 — Stop-on-first-failure behavior

**Goal:** Persist the current attempt and batch failure, then stop before launching another cell after any noncompleted result.

**Affected files:**

- `run_experiments.py`
- `tests/test_experiment_runner.py`

**Required tests:** fail on first cell; fail after one success; timeout, exception, cancellation, and invalid output; ledger/index persisted before stop; no subsequent `run_single()` call; process returns nonzero; explicit opt-out rejected for V2 evidence plans.

**Failure cases:** next cell launches before failure persistence; batch marked complete; failure details lost; `KeyboardInterrupt` bypasses ledger finalization; a valid registered natural terminal triggers an incorrect abort.

**Dependencies:** Slices 2, 5, 6, and 8; the outcome must be deeply classified and durably recorded in an immutable attempt and ledger after execution preflight passes.

**Estimated risk:** Medium. Loop control is simple, but ordering of durable writes is research-critical.

**Recommended implementation order:** 9 of 10.

**Acceptance criteria:**

- V2 defaults to stop on the first result not accepted as complete.
- Attempt result, validation errors, batch stop reason, and incomplete status are persisted before return.
- No later cell starts.
- Resume requires an explicit later action and never occurs implicitly.

## Slice 5 — Immutable attempt directories

**Goal:** Give every execution its own directory so retries never overwrite structured artifacts, manifests, stderr, or timing evidence.

**Affected files:**

- `run_experiments.py`
- `run_raid_control_pilot.py` only if it adopts the shared V2 layout; historical artifacts remain untouched
- analysis/index path consumers that must read selected attempt paths
- `tests/test_experiment_runner.py`

**Required tests:** first/second attempt allocation; failure followed by retry; no unlink/rmtree of prior attempts; collision handling; interrupted allocation; selected path in index; schema-1 historical path discovery; `--overwrite` prohibited for V2.

**Failure cases:** two executions share a directory; attempt counter reused after crash; relative paths escape the output root; retry mutates attempt 1; analysis guesses the newest directory instead of using selection metadata.

**Dependencies:** Slice 1 defines attempt outcome metadata. Coordinate the layout with Slice 6 before merging.

**Estimated risk:** High. Output layout changes affect resume, verification, indexes, and downstream analysis.

**Recommended implementation order:** 6 of 10.

**Acceptance criteria:**

- A cell has immutable `attempt_0001`, `attempt_0002`, and so on under a stable condition/seed path.
- Attempts are allocated atomically and never edited after finalization except for explicitly append-only metadata.
- Final selection is represented by an index/ledger record, not by deleting, moving, or guessing.
- Historical V1 layouts remain read-only compatible.

## Slice 6 — Append-only attempt ledger

**Goal:** Record attempt lifecycle and selection/supersession events without rewriting history.

**Affected files:**

- `run_experiments.py`, preferably a dedicated ledger module
- `tests/test_experiment_runner.py`

**Required tests:** `attempt_started`, `attempt_finished`, validation, selected, and superseded records; monotonic sequence; flush/fsync behavior; crash leaving started without finished; malformed/truncated ledger line; reconstruction of current state; existing records byte-identical after append.

**Failure cases:** ledger entry written after next cell begins; earlier record rewritten; partial line silently ignored; two attempts both selected; secret/environment values leaked; batch manifest treated as authoritative over the ledger.

**Dependencies:** Slice 5's attempt IDs/layout and Slice 1's outcome vocabulary.

**Estimated risk:** Medium-high. Append-only state is simple, but crash recovery and single-selection invariants need careful tests.

**Recommended implementation order:** 7 of 10.

**Acceptance criteria:**

- JSONL or equivalent append-only records identify experiment, cell, attempt, timestamps, plan/code/environment fingerprints, result, validation, and paths.
- An unfinished attempt remains visibly incomplete.
- Exactly one final validated attempt can be selected per cell.
- `run_index.csv` and batch summaries are derived views; the ledger remains authoritative.

## Slice 7 — Safe resume and supersession

**Goal:** Resume only exact matching experiments, reuse only deeply validated selected attempts, and create a new immutable attempt for every retry.

**Affected files:**

- `run_experiments.py`
- ledger/validation modules introduced above
- `tests/test_experiment_runner.py`

**Required tests:** matching resume skip; plan-hash mismatch; commit/tag/environment mismatch; config/tick/log-mode mismatch; nonempty root without experiment manifest; incomplete prior attempt; invalid prior attempt; exception-finalized artifacts; successful replacement; old attempt marked superseded only after new validation; elapsed/history preserved; same-seed retry excluded from replicate count.

**Failure cases:** shallowly valid partial attempt skipped; resume mixes revisions; old evidence deleted; failed replacement supersedes the only valid attempt; batch history reset; output root adopted accidentally.

**Dependencies:** Slices 2, 3, 4, 5, 6, and 8. It consumes both stop-on-failure behavior and the preflight interface.

**Estimated risk:** High. Resume is where validation, provenance, attempts, and selection rules converge.

**Recommended implementation order:** 10 of 10.

**Acceptance criteria:**

- Resume refuses unknown/nonmatching roots without modifying them.
- A cell is skipped only when its selected attempt deeply validates against the current frozen contract and provenance.
- Retry always creates a new attempt.
- Supersession is explicit, append-only, and occurs only after a later attempt validates.
- Original timing, errors, and artifacts remain available.

## Slice 8 — Clean-tag and expected-commit preflight

**Goal:** Fail closed before execution or resume unless the parent repository is clean, the expected commit equals `HEAD`, and a unique annotated V2 run-ready tag resolves to that commit.

**Affected files:**

- `run_experiments.py`, preferably a dedicated provenance/preflight module
- plan schema for expected commit/tag
- `tests/test_experiment_runner.py` plus temporary-Git-repository tests

**Required tests:** clean expected commit/tag; dirty tracked file; untracked file; detached HEAD; wrong commit; lightweight tag rejected if annotated is required; tag points elsewhere; multiple acceptable tags policy; Git unavailable/timeout; commit changes before resume; preflight runs before output-root creation.

**Failure cases:** unknown provenance accepted; tag name recorded without verifying target/type; output directory created before failure; resume checks only plan hash; Git error converted to `dirty: null` and allowed.

**Dependencies:** Slices 9 and 10 provide environment and expanded-plan expectations; Slice 7 uses this gate during resume.

**Estimated risk:** Medium-high. Git checks are bounded, but fail-closed behavior and test isolation must be precise.

**Recommended implementation order:** 8 of 10, before fail-fast and resume integration.

**Acceptance criteria:**

- Preflight runs before any experiment directory or attempt is created and before every resume/new attempt.
- Dirty, unknown, untagged, or mismatched revision aborts without filesystem mutation.
- Expected commit and annotated tag are frozen in the plan and recorded in batch/per-run/ledger provenance.
- The tag is never created automatically by the runner.

## Slice 9 — Environment fingerprinting

**Goal:** Capture a deterministic, non-secret fingerprint of the interpreter, platform, dependency inputs, schemas, hash-seed policy, and plugin inventory that can be compared on resume.

**Affected files:**

- new small environment/provenance helper module
- `run_experiments.py`
- `src/thalren_vale/reproducibility.py`
- provenance tests, likely in `tests/test_reproducibility.py`

**Required tests:** stable output under fixed mocked environment; change in Python/dependency/plugin input changes fingerprint; sorted canonical serialization; missing requirements file; package metadata lookup failure; no arbitrary environment variables/secrets captured; volatile fields excluded from the stable hash.

**Failure cases:** `pip freeze` ordering instability; hostname/timestamp makes every resume differ; credentials copied from environment; plugin code omitted; Python executable/version absent; `PYTHONHASHSEED` claimed rather than read from the child environment.

**Dependencies:** None beyond existing canonical JSON/hash helpers. Its schema should be frozen before Slice 8.

**Estimated risk:** Low-medium. It is additive if stable and volatile provenance are separated.

**Recommended implementation order:** 2 of 10.

**Acceptance criteria:**

- Records Python implementation/version/executable, platform/architecture, `PYTHONHASHSEED`, schema versions, dependency/lock hashes, and plugin policy/inventory without secrets.
- Produces canonical JSON plus a stable SHA-256 fingerprint.
- Batch, per-run, and ledger records use the same fingerprint.
- Resume reports exact fingerprint differences rather than a generic mismatch.

## Slice 10 — Nonexecuting matrix expansion

**Goal:** Add a dry-run/preflight mode that expands the plan into exact cells, commands, contracts, paths, timeouts, and counts without launching a simulator or creating an output root.

**Affected files:**

- `run_experiments.py`, preferably separating plan parsing/expansion from execution
- plan-schema tests in `tests/test_experiment_runner.py`

**Required tests:** deterministic text/JSON expansion; exact eight-cell factor matrix; shared seed expansion; duplicate cell rejection; controlled-flag override rejection; unsafe names/paths; totals by condition/horizon; plan SHA output; invalid timeout; output root remains absent; subprocess execution is never called.

**Failure cases:** dry run creates directories/temp plan files; expansion differs from executed commands; conditions silently omit `metrics_only`; duplicate seed/cell keys; relative path escapes root; output ordering varies between runs.

**Dependencies:** Design the explicit V2 plan-contract schema jointly with Slice 3. Implementation should land first so Slice 3 validates one canonical expansion model.

**Estimated risk:** Low-medium. The main risk is maintaining separate expansion and execution logic; execution must consume the expansion result directly.

**Recommended implementation order:** 3 of 10.

**Acceptance criteria:**

- `--dry-run` or `--expand-plan` performs zero simulation and zero output-root mutation.
- Output includes plan hash, experiment ID, total cells, exact seeds/ticks, condition factors, canonical CLI, expected manifest contract, timeout, attempt-root template, expected commit/tag, and environment fingerprint.
- Machine-readable output is stable enough to review and checksum.
- The execution path consumes the same expanded cell objects; it does not rebuild commands separately.

## Cross-slice integration acceptance gate

The hardening program is complete only when all of the following hold:

- A cancelled, exception, timeout, invalid, natural-terminal, and requested-horizon run are classified distinctly.
- No incomplete or mismatched attempt can pass deep validation or be skipped on resume.
- Every V2 condition is generated from and checked against an explicit factor contract.
- Any noncompleted result is persisted and stops the queue before the next cell.
- Every retry has an immutable directory and append-only history.
- Exactly one validated attempt per cell is selected as evidence; earlier attempts remain auditable and may be marked superseded.
- Execution and resume fail before mutation on dirty, unknown, untagged, wrong-commit, wrong-plan, or wrong-environment provenance.
- Matrix expansion is deterministic, reviewable, and nonexecuting.
- Historical V1 verification remains available without upgrading or rewriting V1 artifacts.
- The parent unit/integration suite passes, including all synthetic failure paths, without launching research-scale experiments.

Only after this gate passes should the V2 research plan be revised, a draft smoke JSON be created and reviewed, and a separate request authorize smoke execution.
