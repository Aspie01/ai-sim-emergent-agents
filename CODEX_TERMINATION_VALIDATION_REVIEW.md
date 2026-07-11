# Codex Termination and Validation Review

**Review date:** 2026-07-10  
**Repository:** `/home/lfs/Projects/ai-sim-emergent-agents`  
**Branch:** `core-v2-runner-hardening`  
**Patch state:** uncommitted  
**Verdict:** **changes required**

## Model-routing disclosure

The operator selected GPT-5.6 Sol Max for this review. The active Codex session
metadata machine-readably records `model=gpt-5.6-sol` and
`reasoning_effort=max`. The environment therefore exposed a machine-verifiable
model identifier and reasoning tier for this session. This is an environment
record, not an independent cryptographic attestation, and this report makes no
broader identity claim.

## Executive assessment

The patch establishes a useful foundation: termination state is explicit,
required structured writers are closed before manifest inventory, manifest
publication uses an atomic replacement, CSV and checksum reads are streaming,
current fixed-seed hashes pass, and strict/auto/legacy modes are separated.
The full suite and the two permitted static checks pass.

The slice is not safe to commit yet. Four defects can allow incomplete,
misassigned, or process-failed output to be sealed or later resume-skipped as
acceptable evidence. The most direct simulation-observation defect is a stale
list index across event-log pruning, which can omit legacy events while leaving
the run strictly valid. The strict validator also labels schema-2 artifacts
`v2_ready` and allows resume skipping without validating the effective controls,
log mode, plan, revision, or environment required by the frozen contract.

No S0 configuration or research matrix was created or executed. No historical
evidence, generated research directory, tag, commit, remote, or `LLM-Wiki/`
content was modified by this review.

## Blocker findings

### B1. Strict validation and resume can accept the wrong effective run contract

**Affected code:**

- `src/thalren_vale/artifact_validation.py` — `_validate_strict()` and
  `inspect_run_outputs()`
- `run_experiments.py` — `run_single()` and `run_from_plan()`
- `tests/test_artifact_validation.py` and `tests/test_experiment_runner.py`

`_validate_strict()` compares only the manifest seed, condition, requested
ticks, and `configuration.ticks`/`configuration.condition` from the effective
configuration. It does not validate the top-level or configured `log_mode`,
anti-stagnation policy, disabled layers/formal-combat policy, raid policy,
execution mode, plan SHA-256, code revision, tag, or environment identity.
Nevertheless, a passing report is classified as `v2_ready`, and both resume
paths skip a cell solely on `report.valid and report.v2_ready`.

Consequently, a schema-2 run with the correct label/seed/tick count but the
wrong intervention controls or output policy can be skipped as completed. This
conflicts with the V2 condition and safe-resume invariants. The fact that exact
condition contracts and provenance preflight are later backlog slices does not
make the current skip safe.

**Required before commit:** fail closed within this slice. Either validate an
exact caller-supplied frozen contract before setting `v2_ready` and skipping, or
keep schema-2 artifact validity distinct from V2 readiness and disable resume
skipping until the condition/provenance prerequisites land. Add wrong-log-mode
and wrong-effective-control tests proving that no skip occurs.

### B2. End-of-tick observation can silently omit legacy events at pruning ticks

**Affected code:**

- `src/thalren_vale/sim.py` — `run()` and `_prune_event_log()`
- `tests/test_events.py` and `tests/test_run_termination.py`

`run()` records `_log_len_before` at tick start. It then calls
`_prune_event_log()` during 50-tick housekeeping before the new authoritative
observation block. Pruning replaces `event_log[:]` with its last 200 entries,
but the observation block later computes
`event_log[_log_len_before:]` using the pre-prune index. If the log exceeded 200
entries, that index no longer identifies this tick's entries and may produce a
partial or empty slice.

Typed events survive separately in `event_log.events`, but legacy-only entries
handled by `_classify_and_record_events()` can be missed. The manifest then
inventories and validates the incomplete event file because the validator has
no independent expected-event count. State hashes remain unchanged, so the
current determinism tests cannot expose this evidence loss.

**Required before commit:** collect legacy entries in a stable tick-local buffer
that is not invalidated by pruning, while still recording all structured
observations at the authoritative end-of-tick boundary. Add a regression test
with more than 200 log entries at a pruning tick and assert exact typed and
legacy event rows, no duplicates, and unchanged state hash.

### B3. A process can fail after a completed manifest has already been sealed

**Affected code:**

- `src/thalren_vale/sim.py` — the `finally` block in `run()`
- `run_experiments.py` — `run_single()` and resume validation
- `tests/test_run_termination.py`

The required logger is finalized and closed before `write_run_manifest()`,
which is correct. However, the completed manifest is published before later
operations that can still raise: summary output around manifest reporting,
`display.final_report()`, mythology/chronicle finalization, stdout restoration,
and full-log closure. An exception after manifest replacement yields a nonzero
process result while leaving `result_status=completed` and
`completed_normally=true` in a strictly valid manifest.

`run_single()` correctly classifies that immediate process as an exception, but
a later resume sees only the sealed artifacts and can skip it as completed.
The existing required-finalization test injects failure before manifest sealing
and therefore does not cover this path.

**Required before commit:** ensure no operation capable of changing process
success remains after the authoritative terminal manifest is published, or
make post-seal optional operations explicitly nonfatal and separately
diagnosed. Add a subprocess regression that injects a post-seal failure and
proves the attempt cannot appear completed or be resume-skipped.

### B4. Strict validation can accept incomplete artifacts and inconsistent writer health

**Affected code:**

- `src/thalren_vale/metrics.py` — `writer_health()`, `record_tick()`,
  `record_beliefs()`, `finalize()`, and `close()`
- `src/thalren_vale/artifact_validation.py` — `_validate_strict()`
- `tests/test_artifact_validation.py` and `tests/test_events.py`

The validator checks writer-health counters only for nonnegative integer type.
It permits `metrics_write_failures`, `event_write_failures`,
`belief_write_failures`, `summary_write_failures`, or `close_failures` to be
nonzero when `unresolved_failures` is forged or accidentally empty. Those
failure classes are not recoverable evidence writes and must never be treated
like a recovered flush.

Belief coverage is also insufficient. A header-only belief file is accepted
whenever final population is zero, even if earlier cadence ticks had living
inhabitants and therefore required snapshots. A nonempty file can omit an
entire later cadence because only row cadence/order is checked, not required
cadence coverage. Metrics already provide enough streamed population
information to detect whether a cadence required rows.

Finally, `ValidationPolicy.allow_zero_events` defaults to `True`, and post-run
and resume callers provide no sealed per-run policy. Thus a zero-event stream is
accepted globally rather than only under an explicit frozen artifact contract.

**Required before commit:** reject every nonzero write/summary/close failure;
allow only demonstrably recovered flush failures; derive required belief
cadences from streamed metrics; and require a recorded or caller-supplied exact
zero-event policy. Add adversarial tests for each internally inconsistent
combination and for extinction after at least one living belief cadence.

## Major findings

### M1. Resume can adopt and mutate an unknown nonempty output root

**Affected code:** `run_experiments.py` — `run_from_plan()`.

The read-only resume preflight inspects only expected condition/seed
directories. If an output root contains unrelated files or directories but no
recognized cell artifacts and no `experiment_manifest.json`, the code proceeds
to create a new experiment manifest and execute into that nonempty destination.
This is neither an absent nor a truly empty destination and is not proven to
belong to the requested plan.

Require a matching batch manifest for every nonempty root and reject unknown or
extra content before any write. Add byte-for-byte preservation tests for an
unknown root, extra cells, stale root-level files, and plan-hash mismatch.

### M2. Artifact paths can follow symlinks outside the run directory

**Affected code:**

- `src/thalren_vale/artifact_validation.py` — `artifact_paths()`,
  `_stream_csv()`, `_read_manifest()`, and inventory checking in
  `_validate_strict()`
- `src/thalren_vale/reproducibility.py` — `build_artifact_inventory()`

Manifest inventory path strings are compared to expected basenames, which
rejects a literal `../` entry. The actual filesystem paths are opened with
normal `Path` operations that follow symlinks. An expected artifact name, the
`data` directory, or the manifest itself can therefore resolve outside the run
root and be inventoried or validated as external evidence.

Resolve and enforce containment below the intended data root, and reject
symlinked required evidence. Cover file symlinks, a symlinked data directory,
literal traversal inventory paths, and normal in-root paths.

### M3. CSV type and cross-artifact semantic checks remain too shallow

**Affected code:** `src/thalren_vale/artifact_validation.py` — `_parse_float()`,
the strict row validators, and summary comparisons in `_validate_strict()`.

The parser accepts `NaN` and infinities, does not reject negative populations or
cumulative counts, and does not constrain simple domains such as season. Event
rows validate schema/seed/tick but not a nonempty or recognized event type.
Belief rows validate seed/tick but not meaningful inhabitant identity.

Summary comparison covers final/peak population and factions plus cumulative
wars, deaths, and births, but leaves collected `gini_sum`/`max_gini` unused and
does not cross-check minimum population, mean/peak Gini, schisms, mergers,
faction formations, treaties, or event-type counts where the writer contract
makes equality expected. A syntactically valid but semantically impossible
artifact set can therefore be marked valid.

Require finite numbers, nonnegative/domain constraints, and all deterministic
cross-checks supported by the artifacts. Clearly document any field that is
only syntactically validated.

### M4. Cancellation and timeout tests do not cover the full process contract

**Affected code:**

- `run_experiments.py` — `classify_result()` and `run_single()`
- `tests/test_experiment_runner.py` and `tests/test_run_termination.py`

KeyboardInterrupt/SIGINT is covered, but a typical orchestrator cancellation
such as SIGTERM is classified as `exception`; no owned cancellation mechanism
or supported signal set is defined. The timeout test replaces
`subprocess.run()` with a direct exception and proves only result mapping. It
does not prove child termination, partial-artifact preservation, strict
rejection, or later resume refusal.

Define the supported cancellation contract and add one tiny real-child timeout
test plus cancellation/resume tests. These must remain bounded and must not
launch a simulation or research cell.

## Minor findings

- **Atomicity test:** `write_run_manifest()` uses a sibling temporary file and
  `os.replace()`, but the test only checks that no `.tmp` remains after success.
  Add fault injection proving no partial manifest becomes authoritative and a
  prior manifest remains unchanged. Specify `fsync` only if crash durability,
  beyond atomic visibility, is required.
- **Unrealistic valid fixture:**
  `tests/test_artifact_validation.py::make_artifacts()` emits one birth event
  while metrics/summary claim a birth every tick, and grows factions without
  formation events. Make the base fixture internally realistic.
- **Synthetic legacy coverage:** legacy tests downgrade a new schema-2 manifest.
  This proves mode dispatch, not authentic schema-1 compatibility. Add a small
  hand-constructed historical-schema fixture without touching old evidence.
- **Handoff qualification:** the handoff says subprocess tests use one to five
  ticks, but the bounded anti-stagnation hash test runs 40. Frozen constants
  confirm current hashes; only the reported manual comparison, not the suite,
  compares them with unmodified HEAD.
- **No memory bound test:** code streams checksums in 1 MiB chunks and processes
  CSV rows iteratively, but no large synthetic test measures peak memory as the
  backlog requires.

## Termination and sealing assessment

- Requested-horizon completion and registered early extinction are consistent
  in covered paths. Final-tick extinction has the right validator rule but only
  synthetic coverage.
- KeyboardInterrupt, pre-seal exceptions, and required logger-finalization
  failure produce nonzero/noncompleted outcomes in their injected tests.
- `final_tick` advances only after required end-of-tick observation, correctly
  excluding earlier tick failures. B3 still permits a later process failure to
  conflict with the already sealed result.
- Partial hashes are rejected when status is honestly failed/cancelled; B1 and
  B3 expose misleading-contract/status paths.

## Observation timing and determinism assessment

The patch does not reorder simulation layers and adds no RNG call. Moving
structured observation after the anti-stagnation phase corrects final metric
timing without changing the canonical state payload. Current regression tests
cover anti-stagnation disabled at five ticks and enabled through the 40-tick
traveler boundary, and both frozen hashes pass.

Those hash tests do not prove structured event completeness. B2 is an
observation-only defect that can leave the state hash unchanged. No current
test exercises exact typed/legacy deduplication after pruning or across a late
anti-stagnation event.

## Strict, auto, legacy, and resume assessment

Strict refuses schema 1 and checks known schema-2 termination, timing, health,
and inventory structures. Auto applies strict handling to schema 2 and labels
readable schema 1 as legacy with `v2_ready=false`; legacy invents no termination
guarantees. Generic verify defaults to auto, while post-run and resume call
strict. The stale per-cell deletion path is removed, but B1 means strict is not
yet the exact contract required for safe skipping. Preexisting destructive
`--overwrite` must remain unavailable to future V2 plans.

## Test and handoff claim substantiation

| Claim | Assessment |
|---|---|
| Full suite is 93 passing | Confirmed: `93 passed in 5.08s` |
| Compileall passes | Confirmed |
| `git diff --check` passes | Confirmed for the tracked diff |
| No new/reordered RNG calls | Supported by diff inspection and frozen hashes |
| Both anti-stagnation boundaries retain hashes | Confirmed for current code and frozen constants |
| Manifest uses atomic replacement after required writer close | Supported by code; failure-path test missing |
| CSV/checksum validation streams | Supported by code; bounded-memory test missing |
| Failed/cancelled attempts cannot look completed | Not fully substantiated; B3 is a counterexample |
| No typed/legacy events are missed or duplicated | Not substantiated; B2 is a counterexample |
| Recovered failures cannot hide data loss | Not fully substantiated; B4 accepts inconsistent health combinations |
| Zero-row policy is explicit and safe | Not substantiated for events or belief cadence coverage |
| Resume is fail-closed and nonmutating for blocked roots | Partially substantiated only for one downgraded legacy cell; B1 and M1 remain |
| Historical schema-1 evidence remains readable | Mode behavior is tested; authentic legacy fixture coverage is missing |
| No V2/research experiment ran | Confirmed from patch/status; pytest ran only its bounded engineering fixtures |

## Scope assessment

The implementation changes stayed within the requested lifecycle,
observation, writer-health, artifact-contract, validator, and immediate resume
guard slice. No simulation dynamics or RNG source was intentionally changed.
The patch did not implement or claim completion of fail-fast queue stopping,
immutable attempt directories, append-only ledgers, supersession, clean-tag
preflight, environment fingerprinting, or nonexecuting matrix expansion. Those
remain separate authorization gates.

At the boundary, `v2_ready` and safe resume are stronger claims than the
validated contract supports. Correct B1 without silently pulling all later
prerequisites into this commit.

## Files inspected

Every requested file was inspected: runner, contract/validator, metrics,
reproducibility, simulation, five test files, and handoff. The review also
applied `AGENTS.md`, the V2 documents, hardening backlog, and test-gap audit.

## Checks performed

```text
python -m pytest -q                                      93 passed in 5.08s
python -m compileall -q src run_experiments.py tests     passed
git diff --check                                         passed
```

Static inspection found no added RNG call. No standalone simulation, experiment
matrix, package build, historical-evidence scan, or external operation ran.

## Required fixes before commit

1. Prevent `v2_ready` classification and resume skip without an exact frozen
   effective contract, or keep resume disabled until that contract exists.
2. Replace the stale post-pruning legacy-event slice with stable per-tick event
   capture and add exact pruning-boundary coverage.
3. Eliminate process-failing work after completed-manifest publication and test
   post-seal failure behavior.
4. Enforce writer-health consistency, explicit zero-event policy, and complete
   belief-cadence requirements.
5. Reject symlinked/out-of-root artifacts and unknown nonempty resume roots
   without changing their bytes.
6. Strengthen finite/domain and deterministic summary/event cross-checks, and
   make the base synthetic artifact fixture internally realistic.
7. Add the focused high-risk regressions identified above and correct the two
   handoff validation descriptions.

## Final recommendation

Do not commit, tag, or advance to general fail-fast yet. Fix the blockers with
focused tests, rerun the focused and full suites, and request another GPT-5.6
Sol review. S0 configuration and every V2 execution tier remain unauthorized.
