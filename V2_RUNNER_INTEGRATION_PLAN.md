# Draft plan: wiring attempts and resume into the runner

**Status: draft for review. Does not authorize execution.** No step here creates
an S0/S1/P1/P2/Full experiment JSON or launches a research cell. The
authorization boundary in root `AGENTS.md` is unchanged, and completing any
phase below never authorizes the next experimental gate.

## 1. What this integrates, and why it is being planned rather than written

Five Core Replication V2 prerequisites are merged and green:

| Piece | Where | State |
| --- | --- | --- |
| Revision preflight | `run_experiments.py` | enforced, opt-in |
| Environment/plugin preflight | `run_experiments.py` | enforced, opt-in |
| Nonexecuting matrix expansion | `run_experiments.py --expand` | live |
| Fail-fast dispatch | `run_experiments.py` | live, opt-in |
| Attempt ledger | `src/thalren_vale/attempt_ledger.py` | **machinery only** |
| Safe-resume decision | `src/thalren_vale/safe_resume.py` | **machinery only** |

The last two are not connected to anything. The runner still refuses every
nonempty output root, so nothing retries and nothing resumes.

Everything merged so far was **additive**: new modules, opt-in gates, extra
recorded provenance. None of it could damage evidence, which is why it was safe
to build quickly. This step is categorically different. It removes the guard
that makes it impossible for the runner to touch a populated output root, and
its two failure modes are:

- **silently skipping** a cell that never produced valid evidence; and
- **re-running over** evidence that already existed.

`AGENTS.md` ranks *"Immutable, deeply validated research evidence"* third in the
mission and says not to trade auditability for delivery speed. So this is
planned before it is written.

## 2. Two problems the specification does not mention

### 2.1 Attempt directories break the artifact layout

Artifacts live at `<root>/<condition>/seed_<N>/data/*` today.
`artifact_paths()` builds that from a `run_dir`, and `verify_outputs()`
**hardcodes** `output_root / condition / f'seed_{seed}'` at
`run_experiments.py:1708`.

Requirement 6 wants immutable attempt directories, which implies
`<root>/<condition>/seed_<N>/attempt_0001/data/*`. Introducing that naively
makes every previously produced run directory unreadable by the tools that
validate it, and makes every reader ambiguous: given a cell directory, is
`data/` the artifacts, or is it a legacy run that predates attempts?

**Decision:** readers never guess. A cell directory is legacy if it contains
`data/` and no `attempts.jsonl`; it is attempt-structured if it contains
`attempts.jsonl`. Resolution goes through one function, and both shapes stay
readable. New runs are attempt-structured; nothing rewrites an existing
directory, ever.

### 2.2 Nothing on disk currently identifies a resumable batch

`safe_resume.decide_resume` compares a *recorded* `ResumeContract` against a
current one. No batch manifest contains that record — `revision_contract` and
`environment_contract` exist as separate blocks, and `config_fingerprint` does
not exist at all.

**Decision:** phase 0 writes the contract, and no resume is attempted against
any root that predates it. A root without a recorded contract is refused, which
`decide_resume` already does.

## 3. Phases

Each phase is independently mergeable, independently testable, and leaves the
runner in a correct state. The fresh-root guard is not touched until phase 3,
and only phase 4 can skip work.

### Phase 0 — record the resume contract and the frozen schedule

*No behaviour change. Recording only.*

- Add `config_fingerprint`: a digest over the exact per-cell controls
  (condition, seed, ticks, extra args), so a plan edit that changes what a cell
  runs is detectable even when the plan hash is unchanged by, say, reordering.
- Write a `resume_contract` block into the batch manifest carrying exactly the
  `ResumeContract` fields, sourced from the existing revision and environment
  records.
- Freeze and record the dispatch schedule (§11.2: *"Resume must preserve the
  schedule identity and record deviations rather than silently regenerating
  order"*). Record a `schedule_id` digest over the ordered cell list, plus the
  actual dispatch order and timestamps.

**Verify:** manifest round-trips; `config_fingerprint` changes when any control
changes and not otherwise; `schedule_id` is stable across processes and changes
when order changes. Mutation: drop a field from the digest, confirm a test
fails.

### Phase 1 — write attempt ledgers, keep the current layout

*No layout change. One attempt per cell, artifacts stay in `data/`.*

- On each cell, create `attempts.jsonl` in the cell directory and record
  `attempt_started` / `attempt_finished`, then `attempt_selected` when the cell
  validates.
- `directory` in the ledger records `.` for this phase — the cell directory
  itself — which is what makes phase 2 a pure additive change.

This proves ledger writing under real execution while every existing reader
still works.

**Verify:** a completed batch leaves a well-formed ledger per cell that
`AttemptLedger.load` accepts; a failed cell records `attempt_finished` and no
selection. Mutation: skip the selection write, confirm a test fails.

### Phase 2 — attempt directories for new runs

*Layout change for new runs only. Still no resume.*

- Allocate `attempt_0001/` via `allocate_attempt_directory` and run the child
  into it.
- Add `resolve_cell_artifacts(cell_dir)` returning the directory a reader
  should use: the selected attempt's directory when `attempts.jsonl` exists,
  else the cell directory itself for legacy runs.
- Route `verify_outputs` and `inspect_run_outputs` call sites through it.
  `run_experiments.py:1708`'s hardcoded path is the one that must change.

**Verify:** a legacy fixture directory still validates unchanged; a new run
validates through the attempt path; a cell with a ledger but no selected
attempt is reported as unvalidatable rather than silently falling back to the
cell directory. That last one is the trap — a fallback that "helpfully" reads
`data/` when no attempt is selected would resurrect exactly the ambiguity
§2.1 exists to remove.

### Phase 3 — relax the fresh-root guard, for resume only

*The dangerous phase. Nothing is skipped yet.*

- `_preflight_fresh_output_root` gains a resume path that accepts a nonempty
  root **only** when all of: `--resume` was passed; the root contains a batch
  manifest with a `resume_contract`; `decide_resume` returns a non-refused
  plan; and every cell directory is either absent or attempt-structured.
- Any other nonempty root is refused exactly as today.
- Overwrite stays rejected outright (requirement 11: *"V2 execution must reject
  overwrite semantics that remove attempt history"*).
- Nothing is deleted, moved, or truncated on any path. New work only ever
  creates a new attempt directory.

**Verify:** the existing fresh-root and symlink defences still hold; a
nonempty root without a contract is refused; a contract mismatch is refused; a
legacy-layout root is refused; a resumable root is accepted and **no existing
file's bytes or mtime change** — snapshot the tree before and after.

### Phase 4 — act on the resume decision

- Skip cells whose decision is `SKIP`; run a new attempt for `REATTEMPT`,
  appending to the existing ledger and superseding the prior selection only
  when the new attempt validates.
- Record skipped cells in the manifest as skipped-with-reason, never as freshly
  completed.
- Record schedule deviations rather than regenerating order.
- Implement the regression escalation from §5.3: extend `CellEvidence` with a
  count of prior completed-but-invalid attempts, and let a second such attempt
  escalate the whole `ResumePlan` to `REFUSE`. This is the only place a
  per-cell condition produces a batch-level refusal, so it needs its own test
  that the refusal names the cell and both failures.

**Verify:** a batch resumed after a partial failure re-runs exactly the failed
cells; a resumed skip does not create an attempt directory; supersession leaves
the prior attempt's artifacts byte-identical; the batch manifest distinguishes
skipped from executed; one validation regression re-attempts and a second
refuses the batch.

### Phase 5 — failure-path coverage

Requirement 13 enumerates what must be covered: cancellation and
`KeyboardInterrupt`, ordinary exception, timeout, extinction and natural
terminal, truncated and header-only CSVs, wrong final tick, wrong config,
wrong commit, wrong plan hash, dirty tree, stale resume artifacts,
supersession, buffered-write and flush failures, fail-fast behaviour, and
deterministic state hashes.

Several already exist in `tests/test_experiment_runner.py`; this phase closes
the gaps against that list explicitly rather than by feel.

## 4. Standing rules for every phase

- **Nothing is ever deleted, moved, or overwritten.** New evidence goes in a
  new attempt directory. A phase that cannot satisfy this is wrong.
- **Refusal is the default.** Any state a phase cannot positively classify as
  safe is refused, not guessed.
- **Legacy directories are readable forever** and never rewritten in place.
- **Every phase is mutation-verified**, and any mutation that survives is
  documented in place rather than reported as covered.
- **Snapshot tests on real trees.** Phases 3 and 4 assert that pre-existing
  files are byte-identical afterwards; that is the property that actually
  matters, and it is cheap to check.

## 5. Resolved decisions

The four open questions were put to the owner. Two were answered directly; two
came back "unsure" and are decided here with the reasoning, to be overridden if
the reasoning is wrong.

### 5.1 `--resume` stays the trigger — *decided here*

Making the existing flag live cannot change any invocation that works today.
On a nonempty root `--resume` is currently **refused**, so after this change it
either succeeds under a valid contract or fails as before. No
previously-succeeding command behaves differently.

A second spelling would leave an inert `--resume` in the CLI as a trap for
anyone who reads the README, and the safety here comes from the contract
checks, not from the flag's name.

### 5.2 The attempt layout applies to all new runs — *decided here*

Two layouts would be a permanent tax on every reader: the same tool would face
both shapes forever, and every future path bug would have two variants. Legacy
directories stay readable either way — that is already the design in §2.1 — so
the choice is only about what *new* runs look like, and one shape is easier to
reason about and to test.

The cost is a slightly deeper path for engineering runs, which is cosmetic.

### 5.3 A validation regression escalates to batch refusal — *owner decision*

**Re-attempt once; if the re-attempt also fails validation, refuse the batch.**

This is stricter than what `safe_resume.py` does today, which re-attempts a
regressed cell indefinitely. Evidence that validated once and no longer does is
a different kind of event from a cell that never validated: it points at the
artifacts, the reader, or the environment rather than at the run, and grinding
through re-attempts would bury that.

**Design implication — this changes the decision module.** `_decide_cell`
currently sees only the selected attempt. To distinguish "first regression"
from "regressed again after a re-attempt" it must see the attempt history, and
a per-cell outcome must be able to escalate to a batch-level refusal:

- `CellEvidence` gains a count of prior attempts that completed but failed
  validation.
- A cell with a completed-but-invalid selected attempt and **no** prior such
  attempt returns `REATTEMPT`, as now.
- A cell with a completed-but-invalid selected attempt and **at least one**
  prior such attempt escalates the whole `ResumePlan` to `REFUSE`, naming the
  cell and both failures.

This lands in phase 4, and the existing refusal tests already establish that a
refused plan hands back no work.

### 5.4 `config_fingerprint` stays over per-cell controls — *decided here*

The owner's condition was "if covering the full `SimulationConfig` provides
further emergence". It does not. `config_fingerprint` is a provenance
mechanism; it changes what mismatches are *detected* and has no effect on
simulation dynamics or on what emerges.

On detection strength it is also nearly redundant. The fuller version would
catch a case where identical CLI arguments resolve to a different effective
configuration — which happens when a default changes in source. But `commit` is
already in the resume contract, so that case is already refused by a commit
mismatch. The fuller fingerprint would add a child-manifest read per cell to
detect something already detected.

Per-cell controls it is. If a future change lets effective configuration drift
*without* a source change, this decision should be revisited.

## 6. What this plan does not cover

Quota enforcement during a cell, checkpoint/replay, dependency and lockfile
hashing, counterbalanced execution order beyond recording it, and any S0
configuration. Each is separate work behind its own gate.
