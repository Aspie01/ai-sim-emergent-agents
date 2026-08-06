# Codex Termination and Validation Review 2

**Review date:** 2026-07-10
**Repository/branch:** `/home/lfs/Projects/ai-sim-emergent-agents` / `core-v2-runner-hardening`
**Base revision:** `b42a2d406e29de38f1d598fdb25480201d084891`
**Patch state/verdict:** current uncommitted working tree / **changes required**

## Executive assessment

The correction pass materially improves the patch. Schema-2 validity is now
separate from V2 readiness; missing external contracts remain non-ready; the
stale pruning index is replaced by a per-tick journal; required writers close
before inventory and manifest publication; nonempty batch roots are rejected;
artifact paths are checked before opening; writer-health, belief cadence,
numeric domains, and cross-artifact checks are substantially deeper; and the
real-child timeout path is covered. The reported full and focused suites pass.

The patch is still not safe to commit. A complete external contract can produce
`v2_ready=true` for noncanonical artifact values because Python loose equality
accepts `2.0 == 2`, `1 == True`, and `0 == False`. A malformed disabled-layer
value can instead crash readiness evaluation. Direct `run_single()` calls can
overwrite an existing nonempty cell or adopt an unknown nonempty output root,
bypassing the batch preflight. Event validation retains every distinct event
detail and therefore grows with event-row count. Event promotion can also
reverse the association of repeated identical narrative records, and broad
`BaseException` catches can suppress a fresh cancellation or process-termination
exception during optional/post-publication work.

These are contract, evidence-integrity, lifecycle, and bounded-memory defects,
not documentation polish. No S0/S1/P1/P2/Full configuration or research run is
authorized.

## Model-routing disclosure

The operator selected **GPT-5.6 Sol Max** for this review. The current session's
machine-readable context visible to this reviewer identifies the agent only as
Codex based on GPT-5; it exposes no exact `model=` or `reasoning_effort=` field.
A targeted environment check found `CODEX_MODEL`, `CODEX_REASONING_EFFORT`,
`OPENAI_MODEL`, `MODEL`, and `REASONING_EFFORT` unset. I therefore cannot
independently verify `gpt-5.6-sol`/`max` from current visible metadata. The
operator selection and any platform model label are environment identifiers,
not cryptographic attestation. The first review's model statement describes
that earlier session and was not reused as attestation for this one.

## Original blocker dispositions

### B1 — Validity, V2 readiness, and resume eligibility

**Disposition: not resolved; blocker remains.**

What is correct:

- `ValidationReport.valid` and `v2_ready` are computed independently in
  `artifact_validation._validate_strict()`.
- Valid schema-2 evidence without an external contract is classified
  `schema2_valid`, not V2-ready.
- `ExpectedRunContract.completeness_errors()` requires all stated identity,
  control, plan, revision, environment, zero-event, and belief-cadence fields.
- `_readiness_issues()` compares log mode, anti-stagnation, disabled layers,
  derived combat availability, raids, execution mode, plan identity/hash,
  commit/tag/dirty state, environment fingerprint, and artifact policy.
- Generic verification reports valid schema-2 evidence as “not V2-ready” and
  returns success when evidence validity, rather than V2 readiness, is the
  requested contract.
- `run_from_plan()` currently performs no resume skip and rejects every
  nonempty batch root.

What remains unsafe:

- `inspect_run_outputs()` and `_validate_strict()` compare the manifest schema
  with ordinary equality, so JSON `2.0` is accepted as schema 2.
- `_validate_strict()` accepts `configuration.raids_enabled=1` as equivalent to
  `True`; `_readiness_issues()` accepts the same value against a boolean
  contract.
- `_readiness_issues()` accepts `code.dirty=0` against required `False`.
- Similar loose equality affects schema-version and integer inventory fields;
  booleans can satisfy expected integer value `1`.
- `_readiness_issues()` calls `tuple(config.get("disabled_layers", ()))` after
  strict validation has merely recorded a type issue. A JSON `null` value raises
  `TypeError` instead of returning an invalid/non-ready report. Mixed
  incomparable element types can also fail canonical sorting.

A bounded synthetic reproduction supplied a complete matching contract, then
set `schema_version=2.0`, `configuration.raids_enabled=1`, and `code.dirty=0`.
The result was:

```text
valid=True, v2_ready=True, classification='v2_ready', issues=[]
```

Changing `configuration.disabled_layers` to `null` raised:

```text
TypeError: 'NoneType' object is not iterable
```

Affected interfaces are `ExpectedRunContract.completeness_errors()`,
`_readiness_issues()`, `_validate_strict()`, `_validate_inventory()`, and
`inspect_run_outputs()` in `src/thalren_vale/artifact_validation.py`.

The complete-contract regression covers absence and ten mismatch families, but
does not parameterize every required field or malformed artifact-side types.
In particular, seed, condition, requested ticks, dirty state, zero-event policy,
belief cadence/cardinality, and malformed/future schema types are not all
covered as wrong-field cases.

### B2 — Exact-once event observation across pruning

**Disposition: partially resolved; exact assignment/order is not yet proven.**

The stale list-index defect is removed. Direct legacy append and typed emit each
create one journal record; typed emit bypasses the overridden `append()` and
does not double-journal; typed-only events receive a journal entry; typed
narrative messages are not reclassified as legacy; slice assignment during
pruning does not invoke journaling; draining preserves list order and clears
the per-tick journal; and the journal does not accumulate across ticks. Partial
tick events are drained as audit rows and strict validation rejects rows beyond
the last fully completed tick. Retained narrative history remains pruned.

However, `StructuredEventLog.record()` identifies a preexisting append only by
reverse content matching plus unclaimed state. It stores a sequence but does
not let the producer claim a specific sequence. With two identical unclaimed
messages followed by records for actors `first` then `second`, the journal
drains as:

```text
[(sequence=0, actor='second'), (sequence=1, actor='first')]
```

Thus repeated identical text can reverse typed-event association and row order.
The current simulator's only `append_text=False` caller normally uses
name-bearing death text, which reduces exposure, but the shared journal
contract itself does not satisfy the required sequence-safe guarantee.

The 50-tick pruning regression injects 201 filler messages, one typed event,
and one legacy-only event. It checks the two sentinel counts and their relative
types, not the exact relevant row dictionaries/order, a promoted preexisting
message at the pruning boundary, or repeated identical messages. The pure
journal test covers only one unique promoted message.

Affected code/tests are `StructuredEventLog.record()` and
`drain_observation_journal()` in `src/thalren_vale/events.py`,
`_record_observation_journal()` and `run()` in `src/thalren_vale/sim.py`, and
`test_pruning_boundary_records_typed_and_legacy_observations_once()` plus
`test_observation_journal_pairs_legacy_text_with_its_typed_event_once()`.

### B3 — Authoritative manifest publication

**Disposition: partially resolved; blocker remains for BaseException semantics.**

The normal control-flow ordering is substantially corrected. The result is
classified, the pending journal is handled, required writers finalize and
close, writer health is evaluated, the state hash is computed, optional report
and narrative work completes, stdout is restored, and the optional log closes
before `write_run_manifest()` inventories artifacts and atomically replaces the
manifest. After replacement, the announcement path catches ordinary output
failures. Existing main-loop `KeyboardInterrupt` and ordinary exceptions remain
active through `finally` and are re-raised after a cancelled/failed manifest is
sealed. A pre-seal manifest failure is fatal. An injected `os.replace()` failure
preserves an older manifest and leaves only a non-authoritative temporary file.

The remaining defect is the deliberate use of `except BaseException`:

- `run()._best_effort()` catches a fresh `KeyboardInterrupt`, `SystemExit`, or
  other process-termination exception from optional finalization and converts
  it into a diagnostic while allowing a completed manifest and successful
  return.
- The post-publication announcement also catches and suppresses every
  `BaseException`, so a fresh cancellation after replacement becomes success.
- Required-finalization and manifest catches convert a fresh interruption in
  those phases into an evidence-sealing `RuntimeError`/`exception`, rather than
  preserving cancellation semantics.
- A diagnostic such as `final_report_failed: KeyboardInterrupt` does not make
  strict validation fail; a complete external contract can still make that
  completed manifest V2-ready.

The existing post-publication and optional-final-report tests inject `OSError`,
not `KeyboardInterrupt` or `SystemExit`, so they do not protect this invariant.
The exact affected regions are `run()._best_effort()`, required-finalization
handlers, manifest publication, and the post-publication announcement in
`src/thalren_vale/sim.py`.

Normal stdout restoration succeeds in covered paths. If the restoration itself
fails, the code records a diagnostic, closes the optional log, and may leave
`sys.stdout` pointing at a proxy backed by a closed handle; no test asserts
global-state integrity for that injected failure.

### B4 — Writer health and zero-row/cadence semantics

**Disposition: resolved for the enforceable writer contract, with one handoff
qualification.**

`_validate_writer_health()` rejects every nonzero metrics write/flush, event
row-write, belief write/flush, summary-write, finalization, and close failure.
Recovered event flushes are accepted only when total equals recovered plus
unrecovered, unrecovered and pending counts are zero, the writer is finalized
and closed, unresolved failures are empty, and inventory/checksum/row counts
still match. Clearing `unresolved_failures` alone cannot hide a nonzero failure
counter. Sealed and caller policies conflict explicitly, and missing
zero-event/cadence/cardinality policy fails closed.

Belief requirements are derived from streamed metric populations at the shared
100-tick cadence. Each required group must contain exactly the population count
of unique nonempty identities; omitted intermediate/final groups, duplicates,
rows for zero-population cadence ticks, and extinction that omits earlier
living groups are rejected. Header-only beliefs are accepted only when no
living cadence required rows.

The validator cannot prove that the distinct identity strings are the actual
living inhabitants, because metrics expose only a population count, not the
living roster. The handoff should therefore say “exactly the required count of
unique nonempty identities,” not claim identity-level membership verification.

## Original major-finding dispositions

### M1 — Nonempty-root safety

**Disposition: not resolved; major finding remains.**

`run_from_plan()` correctly permits absent or truly empty ordinary roots and
rejects every nonempty root before batch-manifest/index writes, including
manifest-only, manifest-plus-index, matching-plan, schema-2/non-ready, unknown,
stale, extra-condition, partial-cell, and plan-mismatch roots. Its diagnostic
inspection performs no application writes. Root tests preserve file bytes,
directory shape, and symlink targets where exercised.

`run_single()` is a bypass. It rejects a nonempty cell only when `resume=True`.
With `resume=False`, it calls `mkdir(exist_ok=True)` and starts the child in an
existing cell, whose metrics writers open required artifacts with `w`. With
`resume=True`, it can also adopt an unknown nonempty output root when the target
cell itself is absent. A tiny non-simulation child reproduced the first case by
changing a preexisting sentinel from `original` to `overwritten`.

Affected code is `run_experiments.run_single()` around destination preflight and
directory creation. `test_direct_run_rejects_symlinked_condition_parent()`
covers a symlink but no ordinary nonempty cell/root helper bypass.

### M2 — Path and symlink safety

**Disposition: resolved for non-hostile-concurrency operation.**

`artifact_contract.require_real_directory()` and
`require_contained_regular_file()` enforce lexical containment, `lstat()` every
relevant component, reject symlinks/broken symlinks/nonregular files, and verify
resolved containment. Required paths are checked before checksum/read opens.
Manifest, data-root, required-file, ancestor, absolute/traversal, and inventory
construction paths are covered in code; expected condition names and seed types
are validated. Normal ordinary contained files pass.

Tests cover symlinked manifest/data/required files, broken links, nonregular
files, absolute and traversal inventory strings, symlinked inventory inputs,
and runner ancestors. They do not directly cover every safe-path helper branch,
such as a plain unexpected multi-component inventory string or an artifact-side
symlinked run ancestor, but the shared helper rejects both.

There remains an accurately bounded TOCTOU limitation: validation and inventory
perform `lstat`, checksum/open, CSV open, and final stat as separate operations.
A concurrently hostile filesystem actor could replace paths between checks.
The patch does not claim race-resistant `openat`/descriptor-relative security,
so that redesign is not required in this slice.

### M3 — Numeric and cross-artifact semantics

**Disposition: substantially resolved; canonical manifest typing remains B1.**

Writers and validators share headers, schema/timing/cadence constants, season
values, event schema/type allowlist, and artifact policy constants. Strict rows
reject nonfinite floats, negative population/faction/resource/timing/variance/
cumulative values, invalid season/Gini domains, decreasing cumulative counters,
unknown or empty event types, empty/duplicate belief identities, and impossible
ticks.

Derived comparisons cover final/positive-minimum/peak population,
final/peak factions, mean/final/peak Gini, births, deaths, wars, schisms,
mergers, faction formations and first tick, treaties formed/broken,
stagnation events, era shifts, final maximum generation, supported event totals,
unique researched technologies, and mean final technologies per active faction.
The synthetic base fixture is internally consistent, an authentic schema-1
shape exists, and an authentic `MetricsLogger` schema-2 fixture passes strict
validation.

`mean_war_duration` is only deterministically checked to be zero when no
`war_ended` row exists. Event CSVs do not preserve duration metadata, so a
nonzero value in a run with ended wars is only finite/nonnegative, not derived.
“Supported war-summary checks” is accurate only with that limitation. Event
counter semantics also remain duplicated between hardcoded writer branches and
validator mapping constants, although the current mappings agree.

### M4 — Cancellation and timeout process behavior

**Disposition: resolved for the documented direct-child guarantee, subject to
B3's finalization-time BaseException defect.**

The mappings are:

| Process outcome | Runner classification |
|---|---|
| simulator `KeyboardInterrupt` manifest | cancelled/user_cancelled, nonzero |
| `-SIGINT` or exit `130` | `cancelled` |
| `-SIGTERM` or exit `143` | `exception` |
| other ordinary nonzero exit | `exception` |
| `subprocess.TimeoutExpired` | `wall_clock_limit` |

The real timeout regression launches only a tiny Python child, writes a PID and
partial metrics file, sleeps, and never invokes the simulator. `subprocess.run`
terminates and waits for that direct child; the test proves it is gone, partial
files remain, strict validation fails, later resume rejects the nonempty root,
and the rejection preserves the tree snapshot. SIGINT has a separate tiny-child
test, and simulator `KeyboardInterrupt`/ordinary exception have bounded injected
lifecycle tests.

There is no process-group/session termination. Descendants created by a child
are not guaranteed to be terminated or reaped. Neither helper nor handoff
should claim more than cleanup of the direct `subprocess.run` child.

## New-risk and test-quality findings

### New major — Event validation is not bounded-memory

`CsvStats.event_details` and `_strict_artifacts().event_validator()` retain the
distinct `detail` value for every event type, although only
`tech_researched` details are later consulted. Birth, death, raid, world-event,
and other details are commonly unique, so memory can grow with event rows.

The existing memory regression creates zero event rows and scales only the
metrics CSV. It correctly starts `tracemalloc` after fixture creation, performs
independent small/large runs with garbage collection and reset, and would catch
accidental full loading of metrics, but it cannot detect event accumulation.

A post-fixture synthetic measurement with unique `world_event` details found:

```text
1,024 event rows:  1,179,544-byte peak
65,536 event rows: 7,308,032-byte peak
growth ratio:      6.20x
```

This violates the explicit requirement that large event validation use bounded
memory. Affected code is `CsvStats.event_details` and `event_validator()` in
`src/thalren_vale/artifact_validation.py`; the insufficient regression is
`test_validation_memory_scales_boundedly_with_large_csv()`.

### Test gaps that matter before commit

- The pruning test does not assert exact relevant row dictionaries/order across
  typed, promoted, legacy-only, and repeated-identical cases.
- Wrong-contract parameterization does not cover every required field or
  noncanonical artifact-side JSON type.
- No test proves caller/sealed policy conflicts for every policy field,
  duplicate belief identity, or zero-population belief rows, although code
  handles those cases.
- Nonempty-root snapshots do not exercise an unknown symlink entry's full
  metadata, and no test calls `run_single()` on an ordinary nonempty cell/root.
- Numeric tests sample representative fields rather than negative infinity,
  every nonnegative field, decreasing cumulative counters, and empty event type;
  shared loops cover them statically, but regressions are not exhaustive.
- No fresh `KeyboardInterrupt`/`SystemExit` is injected during optional or
  post-publication finalization.

## Handoff accuracy

| Handoff claim | Second-review assessment |
|---|---|
| Full suite `175 passed` | Confirmed: `175 passed in 11.15s` |
| Focused corrected suite `128 passed` | Confirmed for artifact-validation, termination, events, and runner tests: `128 passed in 7.83s` |
| Five requested focused test files together | Additional check: `134 passed in 8.43s` including reproducibility |
| Compileall and `git diff --check` pass | Confirmed |
| Validation modes appear in CLI help | Confirmed; `auto` is documented as default |
| 40-tick anti-stagnation and 50-tick pruning wording | Accurate |
| Fixed-seed hashes unchanged | Frozen current-value tests pass; the reported manual comparison with unmodified `HEAD` was not rerun because standalone simulation was prohibited |
| Original review unchanged | Confirmed by SHA-256 before/after this review |
| No current resume skip | True for `run_from_plan()`; unsafe direct `run_single()` mutation makes the broader helper-level safety claim false |
| No destructive `--overwrite` | True through the CLI/batch route; direct normal `run_single()` remains destructive on a nonempty cell |
| Writer-health and belief cadence claims | Substantially accurate, with identity-membership wording narrowed as above |
| Streaming/bounded validation | CSV iteration/checksums stream, but bounded-memory is false for unique event details |
| Cross-artifact validation | Accurate for listed supported fields; nonzero war duration is not derived |
| No experiment output | No research plan/tier/output was created; tests and diagnostics did create only temporary synthetic plans/artifacts and tiny children |
| Implementation file list | Inaccurate: modified `src/thalren_vale/events.py` is omitted |
| Baseline focused `27 passed` | Historical handoff claim; not reproducible from the current corrected tree alone |
| Model routing | Handoff correctly avoids a new identity claim, but it does not supply current-session attestation |

## Scope and research-impact assessment

The changed code remains within termination, observation, required-writer
health, artifact contracts/validation, reproducibility manifesting, and the
immediate nonempty-root guard. No intentional simulation-dynamics or RNG call
was added. Frozen state-hash regressions pass, but this review did not repeat the
manual unmodified-`HEAD` simulator comparison. Schema-2 manifests and metrics
timing are intentional compatibility changes; schema-1 remains read-only
legacy and never V2-ready.

The patch does not implement general fail-fast dispatch, immutable attempt
directories, an append-only ledger, selection/supersession, clean-tag or
environment preflight, nonexecuting matrix expansion, quota enforcement, or a
run-ready tag. Those remain later authorization gates. This review created no
research configuration, experiment cell, evidence directory, tag, commit,
stage, push, or `LLM-Wiki/` change.

## Checks performed

```text
python -m pytest -q tests/test_artifact_validation.py tests/test_run_termination.py tests/test_events.py tests/test_experiment_runner.py
128 passed in 7.83s

python -m pytest -q tests/test_artifact_validation.py tests/test_run_termination.py tests/test_events.py tests/test_experiment_runner.py tests/test_reproducibility.py
134 passed in 8.43s

python -m pytest -q
175 passed in 11.15s

python -m compileall -q src run_experiments.py tests
passed

git diff --check
passed

python run_experiments.py --help
passed; strict|auto|legacy shown, auto documented as default
```

Additional bounded synthetic checks reproduced the B1 canonicalization/crash,
repeated-message promotion reversal, direct nonempty-cell overwrite, and
event-row memory growth described above. They used temporary directories and a
tiny non-simulation child only. No standalone simulator, experiment matrix,
research tier, historical-evidence scan, package build, external service, or
network operation ran.

## Required fixes before commit

1. Enforce exact JSON/runtime types for manifest schema, seed, controls,
   revision dirty state, schema-version dictionaries, and inventory integers;
   safely normalize malformed disabled layers without throwing. Add complete
   field/type/future-schema readiness tests.
2. Make legacy-text promotion claim an explicit journal sequence (or an
   equivalently unambiguous token) so repeated identical messages preserve the
   intended typed association and generation order. Expand the pruning test to
   exact row dictionaries/order with typed, promoted, legacy-only, and repeated
   text beyond 200 messages.
3. Remove broad cancellation/process-termination suppression from optional,
   required, and post-publication paths while preserving the invariant that a
   nonzero process cannot leave completed valid evidence. Add finalization-time
   `KeyboardInterrupt` and `SystemExit` regressions.
4. Make `run_single()` reject every nonempty output root/cell before any child,
   directory, stderr/stdout, or artifact mutation, regardless of `resume`.
   Cover direct helper calls and preserve bytes, structure, and symlink metadata.
5. Stop retaining arbitrary event details in memory. Derive unique technology
   checks from a finite shared contract or another bounded strategy, and add an
   event-heavy `tracemalloc` test that starts after fixture generation and
   compares independently collected peaks.
6. Correct the handoff implementation list, bounded-memory claim, helper-level
   resume/overwrite claim, and belief-identity wording. Keep manual `HEAD`
   comparison distinct from frozen current-value tests.

## Final recommendation

Do not commit or advance to general fail-fast orchestration. Correct the
remaining B1/B2/B3 defects, M1 bypass, and event-memory issue with focused
regressions; rerun the focused and full suites; then request another independent
GPT-5.6 Sol review. S0 configuration and every V2 execution tier remain
unauthorized.
