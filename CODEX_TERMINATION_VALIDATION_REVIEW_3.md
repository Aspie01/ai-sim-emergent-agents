# Codex Termination and Validation Review 3

**Review date:** 2026-07-10  
**Repository:** `/home/lfs/Projects/ai-sim-emergent-agents`  
**Branch:** `core-v2-runner-hardening`  
**Tree reviewed:** current uncommitted working tree, independently re-derived  
**Verdict:** **changes required**

## Executive assessment

The second correction pass resolves most of Review 2's concrete defects. Core manifest/control/inventory/writer-health values now use exact runtime types; schema `2.0`, integer booleans, boolean integers, malformed disabled-layer lists, and future manifest schemas cannot become V2-ready. Repeated narrative text is associated by an explicit token in normal use. Required writers, state hashing, stdout restoration, optional cleanup, inventory construction, and atomic publication precede manifest replacement; cancellation and `SystemExit` remain noncompleted and are re-raised. Public runner entry points reject nonempty roots. Valid event rows no longer retain arbitrary details, and every requested check passes.

There is no newly discovered path that publishes V2-ready evidence after a
fatal terminal condition, so no new blocker is assigned. Four major defects do
remain before commit:

1. The private fresh-batch capability is constructible/rebindable, allowing `_run_single_in_fresh_batch()` to add a cell to an arbitrary nonempty root.
2. `JournalToken` has no log/generation identity and `clear()` reuses sequences, so a stale or foreign token can claim a later matching record.
3. Malformed plan/revision/environment fields can still be reported as `valid=True, classification="schema2_valid"`.
4. One `ValidationIssue`, including invalid detail text, is retained per malformed row; memory is bounded for valid streams, not malformed row-heavy evidence.

These bounded fixes do not authorize immutable attempts, a ledger, fail-fast orchestration, provenance preflight, matrix expansion, or V2 execution.

## Model-routing disclosure

The operator selected **GPT-5.6 Sol Max**. No exact machine-readable `model=` or `reasoning_effort=` value is visible; instructions identify only Codex based on GPT-5, and standard model/reasoning environment values were unavailable. Such metadata is an environment identifier, not cryptographic attestation, so the selected label is recorded without attesting the serving model/tier.

## Findings requiring correction

### Major R3-M1 — The private fresh-batch capability is forgeable

Affected code:

- `run_experiments.py:49` — `_FRESH_BATCH_SECRET`
- `run_experiments.py:52-61` — `_FreshBatchContext.__init__()`
- `run_experiments.py:259-292` — `_run_single_in_fresh_batch()`
- `tests/test_experiment_runner.py:388-483`

Both the capability constructor and its supposed secret are ordinary module
attributes. A caller can pass `_FRESH_BATCH_SECRET` to `_FreshBatchContext`, or
mutate an existing context's writable `output_root` and `_secret` slots. The
private helper then checks only capability equality and that the target cell is
absent. It does not re-establish that the root was absent/empty before batch
initialization. Consequently, an ordinary caller can construct a matching
context for a nonempty unknown root whose requested cell is absent; line 292
then creates the cell and the helper launches a child in that adopted root.

The public `run_single()` and `run_from_plan()` paths themselves correctly
preflight absent/empty roots. The defect is the exact private-helper bypass the
correction request required to close. Existing direct-helper tests import and
exercise only public `run_single()`; none imports the private context/helper or
attempts construction, rebinding, or reuse. This is a major evidence-root
safety defect, although it does not by itself overwrite an already-existing
target cell.

Required correction: remove the constructible/rebindable capability boundary
or make the execution helper independently verify a runner-owned immutable
fresh-batch state that ordinary callers cannot manufacture. Add a child-launch
spy and byte/tree-preservation regression for a forged context against an
unknown nonempty root.

### Major R3-M2 — Journal tokens are not unique across clear/reset or logs

Affected code:

- `src/thalren_vale/events.py:30-35` — `JournalToken`
- `src/thalren_vale/events.py:45-50` — journal identity state
- `src/thalren_vale/events.py:62-86` — `_journal()`
- `src/thalren_vale/events.py:107-140` — `promote()`
- `src/thalren_vale/events.py:175-181` — `clear()`
- `tests/test_events.py:75-181`
- `tests/test_simulation_state.py:20-39`

Normal same-tick behavior is corrected: append returns the exact sequence;
typed, typed-only, promoted, and legacy-only records are exact-once; repeated
identical records can be promoted out of actor order while draining in
generation order; double, unknown-number, malformed, and wrong-tick claims
reject.

The token is nevertheless only `(tick, sequence)`. `clear()` resets
`_next_sequence` to zero and discards claim state. If a caller retains an old
token, clears/resets the same log, then appends the same text at the same tick,
the old token has the same tick/sequence and `promote()` accepts it. A token
from another `StructuredEventLog`, or a directly constructed token guessing an
active sequence, has the same problem. Text equality is now secondary rather
than authoritative, but it cannot distinguish these stale/foreign claims.

The reset test deliberately clears a pending journal but does not retain and
retry its token. The claim test uses sequence `999`; it does not test a stale or
foreign token whose numeric fields collide with an active record.

Required correction: bind tokens to an opaque log and reset generation (or an
equivalent nonreusable record identity), validate ownership by identity, and
add stale-after-clear, cross-log, and colliding-token regressions. Keep the
existing exact mixed-order and pruning behavior unchanged.

### Major R3-M3 — Malformed optional provenance can remain schema-2 valid

Affected code:

- `src/thalren_vale/artifact_validation.py:1224-1286` —
  `_readiness_issues()`
- `src/thalren_vale/artifact_validation.py:1289-1451` —
  `_validate_strict()`
- `tests/test_artifact_validation.py:586-623`

Core schema-2 fields are now exactly typed and invalid values become structured
issues. A complete external `ExpectedRunContract` also uses exact types and
canonical values, so malformed values cannot become `v2_ready=true`.

Plan identity/hash, code commit/tag/dirty state, and environment fingerprint
are different: `_validate_strict()` performs no conditional syntax/type check
when those fields are present. `_readiness_issues()` places mismatches only in
`readiness_issues`; with no external contract it returns immediately without
inspecting them. With a complete contract, `code.dirty=0`, `code.commit=7`,
`plan_identity=7`, or `environment_fingerprint=7` therefore remains eligible
for `valid=True` and `classification="schema2_valid"`, while correctly being
non-ready. The corresponding parameterized test intentionally asserts only
non-readiness and accepts either validity issues or readiness issues.

Absence of later-slice provenance must continue to mean valid-but-non-ready for
this bounded schema-2 slice. Presence of malformed provenance is different and
must be a validity error under the final review objective.

Required correction: conditionally validate the exact shape, type, and format
of every present plan/revision/environment field as part of strict validity,
without inferring absent values or making incomplete later provenance ready.
Strengthen the test to require `valid=false` for malformed present values.

### Major R3-M4 — Malformed-row diagnostics remain unbounded

Affected code:

- `src/thalren_vale/artifact_validation.py:329-336` — `_add()`
- `src/thalren_vale/artifact_validation.py:906-925` — event-row diagnostics
- all streamed row validators that append one issue per bad row
- `tests/test_artifact_validation.py:1584-1630`

The original Review 2 memory defect is fixed for valid rows. `CsvStats` retains
only finite event-type counters, first ticks, and recognized technology IDs;
world-event, raid, birth, death, and narrative details are discarded. The
technology set is bounded by `TECHNOLOGY_IDENTIFIERS`; `technology.py` checks at
import that it exactly matches `TECH_TREE`. CSV and checksum reads stream.

The implementation is not bounded for malformed row-heavy evidence. Every bad
event appends a distinct `ValidationIssue`; unknown technology issues embed
`repr(row["detail"])`. A file containing many unique invalid identifiers (or
other per-row violations) therefore retains data and an issue object
proportional to event-row count and detail diversity. Similar per-row issue
growth exists for metrics and beliefs. The current memory test uses valid
`world_event` rows, so it cannot expose this path.

Required correction: cap retained row diagnostics and record an aggregate
suppressed-issue count (or otherwise bound reporting state), then add an
independently measured malformed-event regression with unique details. The
validator must still inspect every row and return invalid.

## Review 2 blocker dispositions

### B1 — Validity, V2 readiness, and resume eligibility

**Disposition: original false-readiness blocker resolved; R3-M3 remains.**

- `valid` and `v2_ready` are independently computed.
- Schema-1 is never ready; schema-2 validity alone never implies readiness.
- No or incomplete external contract leaves readiness false.
- No expected value is inferred from artifact contents.
- Every required expected field is listed in
  `ExpectedRunContract.completeness_errors()` and checked with exact type and
  canonical constraints.
- Log mode, anti-stagnation, disabled layers, derived combat, raids, execution
  mode, plan identity/hash, commit/tag/dirty state, environment identity,
  zero-event policy, and belief cadence/cardinality all participate in exact
  readiness comparison.
- Generic verification accepts valid non-ready schema-2 evidence, prints
  `VALID SCHEMA-2 — not V2-ready`, and returns success for validity mode.
- No current public resume/overwrite path skips an existing root.
- Exact schema/control/inventory typing prevents Review 2's `2.0`, `1`, `0`,
  boolean-as-integer, and disabled-layer crash cases from becoming ready.

A synthetic complete contract cannot omit a required field through defaults or
nullable equality. The remaining problem is validity classification for
malformed *present* later-provenance fields, described in R3-M3.

### B2 — Exact-once event observation across pruning

**Disposition: original content-search defect resolved; token-lifetime defect
remains as R3-M2.**

`append()`, typed emit, typed-only emit, explicit promotion, and legacy-only
append each journal exactly once. Typed emit does not traverse the journaling
append path twice. Promotion uses a supplied sequence, not reverse content
search, and repeated identical same-generation records retain their intended
association. Slice pruning does not journal; drains preserve order and clear
per-tick lists/maps; `begin_observation_tick()` rejects undrained records. A
partial-tick exception produces noncompleted evidence, and rows beyond the
last completed tick are rejected. Narrative history is bounded at 200 at the
pruning boundary, while journal storage clears per tick.

The 50-tick regression injects more than 200 messages plus typed, explicitly
promoted repeated-identical, and legacy-only events. It asserts the exact four
sentinel row dictionaries and exact order, no duplicate sentinel rows, a
200-entry narrative bound, an empty journal, and an unchanged baseline state
hash. Token reuse across `clear()`/state reset is not covered and fails by
inspection.

### B3 — Authoritative manifest publication

**Disposition: resolved.**

The simulator classifies completion/early extinction/final-tick extinction,
ordinary exceptions, `KeyboardInterrupt`, and other `BaseException` values
before sealing. Required event finalization, logger finalize/close, writer
health, state hash, optional diagnostics/narrative, stdout restoration, and
optional log close occur before `write_run_manifest()`. Optional ordinary
exceptions remain diagnostics; optional `KeyboardInterrupt`/`SystemExit` are
caught only to retain terminal classification, then sealed noncompleted and
re-raised. Required-finalization interruptions retain the same terminal
semantics. A stdout restoration failure forces `sys.stdout` back to the real
stream and prevents completion.

`write_run_manifest()` streams inventory, writes a non-authoritative temporary
file, and performs `os.replace()` as its final fallible operation. No callback,
announcement, cleanup, or output follows successful replacement. On failure,
an older manifest survives; a temporary file is not authoritative. Tests inject
ordinary pre-seal failure, optional and required `KeyboardInterrupt` and
`SystemExit`, stdout restoration failure, an armed post-publication callback,
and atomic replacement failure preserving older bytes. All nonzero injected
outcomes that produce manifests seal them as noncompleted and strict-invalid.

Pre-`try` logger/output setup can fail without a sealed manifest, but it cannot
publish completed evidence; fresh runner roots make such remnants invalid.

### B4 — Writer health and zero-row/cadence semantics

**Disposition: resolved for the authentic writer contract.**

Every nonzero metrics write/flush, event row-write, belief write/flush,
summary-write, finalization, and close counter invalidates evidence. Event flush
total/recovered/unrecovered accounting, zero pending rows, finalized/closed
flags, empty unresolved failures, inventory counts, and checksums are all
required; clearing only `unresolved_failures` cannot forge health. Missing
zero-event policy fails closed, and caller/sealed policy conflicts are explicit.

Belief cadence populations come from streamed metrics. Every living cadence
requires exactly that count of unique nonempty identities; duplicates,
intermediate/final omissions, earlier omissions before extinction, and rows at
zero-population cadence reject. Header-only beliefs pass only when no cadence
requires rows. This proves cardinality, not membership in the actual living
roster.

## Review 2 major-finding dispositions

### M1 — Nonempty-root safety

**Disposition: public paths resolved; private-helper bypass remains R3-M1.**

Absent and genuinely empty ordinary roots proceed. Public `run_single()` and
`run_from_plan()` reject every nonempty root—including manifest/index,
matching-plan, schema-2/non-ready, partial, stale, extra-condition, unknown, and
symlink cases—before child launch or application writes, regardless of
ordinary/resume/overwrite mode. Snapshot tests preserve root timestamps, bytes,
directory structure, symlink targets/metadata represented by the snapshot, and
prove no child command is built. Batch cells must be absent. There is no stale
deletion, resume skip, retry, or supersession behavior.

The private context/helper boundary does not enforce the same guarantee.

### M2 — Path and symlink safety

**Disposition: resolved for non-hostile concurrent filesystems.**

Manifest, data root, required files, and inventory construction use lexical
containment, `lstat()` component checks, regular-file checks, and resolved
containment before reads. Symlinked/broken/nonregular paths, symlinked
ancestors, absolute paths, `..`, separators/multi-component inventory names,
unsafe condition components, and non-integer seeds reject. Normal contained
ordinary files work.

Tests directly cover symlinked manifest/data/required files, broken links,
nonregular files, absolute/traversal/Windows-style inventory strings,
symlinked inventory construction, and runner ancestors. The exact plain
multi-component inventory branch is enforced statically but lacks a dedicated
fixture.

There is a normal TOCTOU limitation: `lstat`, `stat`, checksum open, CSV open,
and final stat are separate operations. The patch makes no concurrent-hostile
replacement claim, so descriptor-relative `openat` hardening remains out of
scope.

### M3 — Numeric and cross-artifact semantics

**Disposition: resolved, apart from R3-M3 typing classification and R3-M4
diagnostic memory.**

Writers and validators share headers, schemas, cadence, season, artifact
policy, event allowlist, and finite technology identifiers; the real technology
tree has an executable equality assertion. Validators reject nonfinite values,
negative protected metrics/summary fields, invalid domains, decreasing
cumulatives, unknown/empty event types, unknown technology IDs, empty/duplicate
belief identities, and impossible ticks.

Derived checks cover final/positive-minimum/peak population,
final/peak factions, mean/final/peak Gini, births, deaths, wars, schisms,
mergers, faction formations/first tick, treaties formed/broken, stagnation,
era shifts, final maximum generation, supported event totals, unique
technologies, and final mean technologies per active faction. The authentic
schema-1 fixture, synthetic schema-2 fixture, authentic writer schema-2 fixture,
and final-tick extinction fixture are internally consistent.

Nonzero mean war duration remains syntax/domain-only when ended wars exist;
zero is derived only when no `war_ended` rows exist. The handoff states this
limitation accurately.

### M4 — Cancellation and timeout process behavior

**Disposition: resolved for the documented direct-child guarantee.**

`KeyboardInterrupt`, `-SIGINT`, and exit 130 map to cancellation; SIGTERM,
exit 143, ordinary nonzero exits, and `SystemExit` map to failure/exception;
timeout maps to `wall_clock_limit`. The timeout fixture launches a tiny
non-simulation Python child, leaves partial files, proves the direct PID is
reaped, obtains strict rejection, then proves resume rejection preserves every
snapshotted entry. The runner does not create a process group and therefore
does not guarantee descendant cleanup; the handoff narrows the claim correctly.

## Test-quality assessment

The tests generally target the original defects rather than merely traverse
branches:

- Core malformed JSON parameterization covers float/bool schema values,
  boolean integer fields, integer booleans, disabled-layer null/mixed/duplicate
  values, policy, writer-health, inventory values, and future manifest schema.
- Every `ExpectedRunContract` field appears in the exact-runtime-type
  parameterization. The correct-type mismatch table omits `code_dirty` and
  `belief_snapshot_cardinality`; their wrong canonical values are rejected by
  completeness checks, but explicit regressions would improve clarity.
- Repeated-identical and out-of-order promotion tests assert intended actor
  association; the 50-tick pruning test asserts exact CSV dictionaries/order.
- Optional and required finalization tests genuinely inject both
  `KeyboardInterrupt` and `SystemExit`; stdout, pre-seal, atomic replacement,
  and publication-last paths are separately injected.
- Public direct-run tests cover unknown roots, ordinary/schema-2/partial cells,
  manifest/sentinel roots, all three flag modes, symlinks, snapshots, and no
  child launch. They do not exercise the private context/helper.
- Writer-health combinations, belief cadence groups, authentic fixtures,
  technology catalog enforcement, and final-tick extinction are meaningful.
- The event-memory fixtures are fully created before tracing. Small and large
  cases use separate start/stop cycles with garbage collection, unique valid
  details, inventory row-count confirmation, a 32 MiB absolute ceiling, and a
  scaling bound that would detect the former detail set. They do not cover
  invalid-row issue accumulation.
- The frozen 5-tick and 40-tick state-hash assertions passed. The 50-tick
  pruning test separately compares injected and uninjected current-tree hashes.

Missing regressions correspond directly to R3-M1 through R3-M4: forged private
context, stale/cross-log token, invalidity of malformed present provenance, and
bounded malformed-row diagnostics.

## Handoff claim substantiation

Accurate claims:

- All nine implementation files, all six test files, and the handoff are
  listed.
- The focused total is 283 and the full total is 324.
- The 40-tick frozen anti-stagnation test and necessary 50-tick pruning test are
  described accurately.
- Frozen current-tree hashes are correctly distinguished from the previously
  reported manual comparison to unmodified `HEAD`; this review did not repeat
  that prohibited standalone comparison.
- Termination/publication, writer health, belief cardinality wording, nonzero
  war-duration limitation, direct-child timeout limitation, validation modes,
  and no-current-public-resume-skip claims match the implementation.
- `git status --short -- experiment_runs data logs` was empty after the tests;
  no research experiment output or tier was created in the repository.
- The model-routing disclosure is appropriately non-attesting.

Claims requiring correction or qualification:

- The handoff says the fresh-batch context is created only after
  `run_from_plan()` preflight and implies the private batch route cannot adopt
  nonempty output. `run_single()` also constructs it, and ordinary callers can
  forge/rebind it; R3-M1 makes the broader safety claim false.
- The journal description calls tick/sequence exact and unambiguous but omits
  sequence reuse after `clear()` and cross-log collisions (R3-M2).
- The bounded-memory wording is accurate for valid recognized rows, but not for
  malformed per-row diagnostics (R3-M4).
- The exact reported peaks (1,189,456 and 2,121,925 bytes) are plausible and
  the regression passes its bounds, but the required test command does not
  print peak values. This fresh review therefore substantiates the bounded test,
  not those exact historical byte measurements.

## Scope and research-impact assessment

The patch remains within termination-aware manifests and deep artifact
validation. It does not implement immutable attempts, a ledger, selection or
supersession, general stop-on-first-nonaccepted orchestration, full provenance
preflight, matrix expansion, or experiment configuration. No historical
evidence, nested `LLM-Wiki` content, tag, commit, index selection, or research
output was modified by this review.

The observation boundary moves structured recording after enabled layers and
anti-stagnation without adding RNG calls or reordering simulation layers.
Explicit starvation-token plumbing changes observation association, not agent
state transitions. Both frozen deterministic hashes pass. The patch changes
schema/timing and validation behavior as documented; it does not create V2
research evidence.

## Stable-tree verification

Before inspection and after all requested tests, SHA-256 values were identical:

```text
867ff1a12ada7f8a82b8ff3ee0592c53dc087271fe2ff887747ad46d79204d5e  AGENTS.md
a5f2c968a4d277833cccab2999daa967c6b8939528bbd22b91078fb880d89f34  CORE_REPLICATION_V2_PLAN.md
3fa35e6a8fa77d84cd97bfddd89941fc11abe81257d56e43b31b418f7330655b  CORE_REPLICATION_V2_PLAN_REVIEW.md
17eef858b61155a90896b12e21b9043dc58e396ae82a6b2e6330231a104fcf93  CORE_V2_RUNNER_HARDENING_BACKLOG.md
a668537bf254d6ce45f4b5e488fd4092ebbfd730a9652a055d09460676013ba2  CORE_V2_TEST_GAP_AUDIT.md
723593450e64b8e37f02144bc42096442df88f737efffa822ff191a1d80bb2a9  CODEX_TERMINATION_VALIDATION_HANDOFF.md
6d5be351200206bf33e6848e1daf2931e9c3826794fca0eebb9793d3fdd32273  CODEX_TERMINATION_VALIDATION_REVIEW.md
72aaa780d6e4370c484f81e7b6d285f904972415e08eb0a3c4a309005ae3ee17  CODEX_TERMINATION_VALIDATION_REVIEW_2.md
e8fcb0a3c5e12cc0c13caed414c979bb743262d030b0acf0fa489db965eaabe5  run_experiments.py
10ed7df71343ccfb8c5fef9ae0c71844c7812dd90f41ecc385de2ced85039dcd  src/thalren_vale/artifact_contract.py
606cd836cfdf807db0e149ad6712cd305fd59ae7b211f15477e11d63f043440c  src/thalren_vale/artifact_validation.py
402c4a6b6f3658f539c94502eb3c2f56d1c39ccb2236bcb3cbeb77562b80f25b  src/thalren_vale/events.py
09c9697191010e1da034a88adf680bf75cfbce843ef3f3e2f793225aced9e350  src/thalren_vale/inhabitants.py
1c3bc2e47efa1b80842a9f357a9407fb4bba911ced055872426d4589375e76d4  src/thalren_vale/metrics.py
b8f55d525dbb3d58c33970b9892f6ff9302bc982a3281147d8f6ad8219c55b2d  src/thalren_vale/reproducibility.py
8db604552e6012e8ea15bec489ce37d5c49f772bb1f32347229f030775ff5580  src/thalren_vale/sim.py
00b56b9fc230f8b1d6ee6112b2d3a83f179349bdf44811b35ccc820fe1487429  src/thalren_vale/technology.py
07701449fcc9a67f68ba933ed46557cd3b30d6ec52ed501ee8877e347a750aea  tests/test_artifact_validation.py
f1feac8a832819b3ebda645fb8d217590f9d0b8f772dc05c5bb2ef938ef12b28  tests/test_run_termination.py
c9af9e69c28c44c3492292a759b0e9f8634b69c6db233e5adaadbc2f781e6de9  tests/test_events.py
ca4c7d5b59d5c4e5a9fb6e21029ea4d139d1aabc57cee98f47e0a0c71d9a9e0a  tests/test_experiment_runner.py
c527ef33c8672163fac7589dd4865e5f72ec4b370ab7d4b6a0d506a5f43849cf  tests/test_reproducibility.py
bb1bee58d41c102a8de40bd1b3f3dcbf4dffdba00c3f1c6cacb245279a5aeab3  tests/test_simulation_state.py
```

The only subsequent input-tree change was creation of this Review 3 file, as
authorized.

## Commands and exact results

```text
python -m pytest -q tests/test_artifact_validation.py tests/test_run_termination.py tests/test_events.py tests/test_experiment_runner.py tests/test_reproducibility.py
283 passed in 10.39s

python -m pytest -q
324 passed in 13.60s

python -m compileall -q src run_experiments.py tests
exit 0; no output

git diff --check
exit 0; no output

python run_experiments.py --help
exit 0; displayed strict|auto|legacy validation modes and documented auto as default
```

Both frozen deterministic state-hash tests passed as members of the focused and
full suites:

```text
5 ticks:  3dcb25d98e634034da0814618bd8c28f3f6289491a536238950e866c5e75bc6f
40 ticks: ef15589175c3c1e48ddab9ba837429626c46423d2637b35e8120189e110a7163
```

No standalone simulator, experiment matrix, S0/S1/P1/P2/Full tier,
historical-evidence scan, package build, external service, or network operation
ran. The short simulator subprocesses embedded in the required tests did run,
including the stated 40-tick and 50-tick regressions.

## Required fixes before commit

1. Close the constructible/rebindable `_FreshBatchContext` bypass and add a
   direct private-helper preservation/no-child regression.
2. Give `JournalToken` opaque log/generation ownership so stale, cross-log, and
   colliding tokens reject; add those regressions.
3. Make malformed *present* plan/revision/environment provenance a strict
   validity error while preserving absent/incomplete as non-ready.
4. Bound per-row diagnostic retention for malformed streamed evidence and add
   an invalid-event memory regression that proves all rows were inspected.
5. Correct/qualify the affected handoff claims and rerun the same focused,
   full, compilation, diff, and help checks.

Do not modify either prior review. Do not advance to later runner-hardening
slices as part of these fixes.

## Final recommendation

**Do not commit this patch yet and do not advance to general fail-fast
orchestration.** Complete the four bounded corrections above, preserve the
frozen hashes, and request one final independent Sol review. No research tier,
experiment configuration, tag, or V2 execution is authorized.
