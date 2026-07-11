# Codex Termination and Validation Handoff

**Updated:** final runner-containment correction after Review 4 (uncommitted)  
**Base revision:** `b42a2d406e29de38f1d598fdb25480201d084891`  
**Status:** bounded lifecycle/deep-validation slice corrected and validated; uncommitted  
**V2 authorization:** no S0, experiment JSON, matrix, pilot, or replication is authorized

## Outcome

The simulator seals schema-2 termination-aware manifests, records structured observations at the authoritative end-of-tick boundary, surfaces required-writer health, and inventories four required structured artifacts. The runner has streaming `strict`, `auto`, and `legacy` validation, rejects unsafe evidence paths, freezes exact cell inputs before root creation, and uses a fail-closed nonempty-root posture for every current public or private execution path, regardless of resume or overwrite flags.

No experiment plan, experiment output directory, historical evidence, LLM-Wiki content, tag, attempt ledger, or research matrix was created or modified.

## Termination semantics

New manifests record:

- `requested_ticks`
- `final_tick`
- `completed_ticks`
- `termination_reason`
- `result_status`
- `completed_normally`

Implemented outcomes:

| Outcome | Result | Normal | Reason | Final tick |
|---|---|---:|---|---|
| Requested horizon reached | `completed` | `true` | `requested_ticks_reached` | Requested ticks |
| Extinction before horizon | `completed` | `true` | `extinction` | Last completed extinction tick |
| Extinction on final requested tick | `completed` | `true` | `requested_ticks_reached` | Requested ticks |
| `KeyboardInterrupt` | `cancelled` | `false` | `user_cancelled` | Last fully completed tick |
| Simulation/required-finalization exception | `failed` | `false` | `exception` | Last fully completed tick |
| Timeout | Runner-level `wall_clock_limit` | — | — | Never accepted as complete |

Cancellation and exceptions re-propagate after evidence sealing and therefore return nonzero. A fresh `KeyboardInterrupt` during optional or required finalization is sealed as cancelled and re-raised. A fresh `SystemExit` or other `BaseException` is sealed as noncompleted and re-raised rather than converted into success. Optional finalization suppresses only ordinary `Exception` failures as diagnostics. Required writer closure, state hashing, stdout restoration, and optional cleanup all finish before publication; completed-manifest replacement is the final explicit operation, with no post-publication announcement.

The timeout regression proves that `subprocess.run()` terminates and reaps its direct tiny child. The runner does not create or terminate a process group, so it does not claim cleanup of descendants independently spawned by that child.

## End-of-tick timing contract

Typed-event observation, legacy event classification, per-tick metrics, belief snapshots, and structured flushes now occur after all enabled simulation and anti-stagnation processing. Simulation layers and event generation were not reordered, and no RNG calls were added.

`StructuredEventLog.append()` returns an opaque `JournalToken` bound by identity to one log instance, one reset generation, one record, one tick, and one sequence. Its ownership identities are not public attributes, its representation discloses no token state, public construction is rejected, and copying/serialization is rejected. A typed promotion must claim the exact registered token once; stale-after-clear/reset, cross-log, guessed, malformed, unknown, already-claimed, wrong-tick, or wrong-text claims fail. Numeric tick/sequence equality alone never authorizes a claim. Typed emit, typed-only emit, promoted legacy text, repeated-identical text, and legacy-only text each produce exactly one ordered journal record. Housekeeping pruning uses slice replacement without journaling and retains at most 200 narrative messages at the pruning boundary; the per-tick observation journal is drained and cleared at the authoritative end-of-tick boundary.

New manifests record:

- `schema_version: 2`
- `metrics_timing_contract: end_of_tick_v2`
- `artifact_schema_versions.metrics: 2`

The event-row schema remains version 1 because its columns did not change. Historical artifacts retain their original timing and schemas and were not rewritten.

## Validation behavior

`run_experiments.py` exposes:

```text
--validation-mode strict|auto|legacy
```

- `strict` requires schema 2, expected ticks, valid completion semantics, end-of-tick contract, writer health, artifact inventory, safe contained paths, and deterministic cross-artifact consistency. It is mandatory after new execution.
- `auto` is the default for generic `--verify`. Schema-2 runs receive strict validation; schema-1 runs may validate as historical `legacy` evidence but always report `v2_ready=false`.
- `legacy` accepts only recognized schema-1 evidence and never upgrades or marks it V2-ready.

Schema-2 validity and `v2_ready` are deliberately distinct. `v2_ready=true` requires a caller-supplied complete `ExpectedRunContract` that exactly matches the artifact's seed, condition, ticks, effective controls, log mode, execution mode, plan identity/SHA-256, code commit/tag/clean state, environment fingerprint, and artifact policy. Python loose equality is not used for these fields: booleans, integers, strings, lists, dictionaries, schema versions, identifiers, and inventory values require their exact contract types. Malformed/null/mixed/duplicate disabled layers return an invalid/non-ready report rather than raising.

Later-slice plan, revision, and environment provenance may be absent; absence leaves otherwise sound schema-2 evidence valid but non-V2-ready. Any such field that is present is conditionally validated as strict evidence. Malformed plan identifiers or SHA-256 values, malformed or unexpectedly shaped code identity, non-string commit/tag values, non-boolean dirty state, malformed environment fingerprint, unsupported nesting/aliases, and conflicting duplicate representations make the artifact invalid and non-ready. Well-formed but incomplete provenance can remain valid and non-ready; it is never inferred from the artifact or promoted to ready without the complete external contract.

Strict validation streams CSV and checksum reads. Arbitrary event details are discarded after each row; only counts, first ticks, and a bounded set drawn from the shared finite technology catalog are retained. Validation diagnostics are aggregated by stable artifact/issue code. Each aggregate keeps at most three representative line numbers and messages, truncates representative text to 160 characters, records total occurrences, and reports the number of additional suppressed occurrences. Every row is still inspected and contributes to checksum and row-count validation; neither arbitrary details nor one issue object per malformed row are retained. It checks:

- exact headers, column counts, UTF-8, and strict CSV parsing;
- finite typed values, domains, seed/condition, schema versions, and lowercase SHA-256 state hash;
- contiguous metrics ticks through `final_tick`;
- nondecreasing event/belief ticks and no rows beyond `final_tick`;
- exactly one strict summary row;
- final/peak/positive-minimum population, factions, Gini, technology, cumulative-event, treaty, and supported war-summary agreement;
- registered early extinction with final population zero;
- writer/finalization health, including consistent recovered-vs-unrecovered flush accounting; and
- inventory paths, sizes, row counts, checksums, and versions.

For war duration, zero is derived and enforced when there are no `war_ended` rows. A nonzero mean in a run with ended wars is checked only for finite/nonnegative syntax because event rows do not preserve individual durations.

Header-only metrics and summary files are rejected. Header-only events require a sealed or caller-supplied explicit zero-event policy. Belief coverage is derived from streamed metrics: every cadence tick with living inhabitants requires the required count of unique nonempty identities, including before a later extinction. Metrics do not expose the living roster, so validation does not claim identity-level roster membership. Accepted zero-row artifacts emit a specific validation notice.

## Artifact inventory and writer health

The manifest inventories only:

- metrics
- events
- beliefs
- summary

Each entry contains an exact safe data-directory basename, byte size, SHA-256, data-row count, and schema version. Required evidence must be an ordinary non-symlink file physically contained under a non-symlink run/data root. The manifest does not inventory itself, optional narrative output, environment provenance, attempts, or historical artifacts.

Writer health records row-write failures, recovered flush failures, pending event rows, summary failures, close failures, finalized/closed state, and unresolved failures. A recovered flush may validate when nothing remains pending; unresolved failures invalidate the run.

## Resume behavior

This bounded slice intentionally does not skip or retry any existing output. `--resume` permits only an absent or truly empty output root. Every nonempty root—including a valid schema-2/non-ready run, manifest-only root, manifest-plus-index root, unknown file, stale temporary, extra condition, partial cell, or plan-hash mismatch—raises before any batch manifest or index write and preserves every byte and tree entry unchanged. Nonempty `--overwrite` is also rejected. Public/direct `run_single()` applies the same absent-or-empty-root requirement before `mkdir`, output capture, child creation, or artifact access; `resume=False`, `resume=True`, and `overwrite=True` cannot bypass it.

The former module-level fresh-batch secret/context capability was removed. `run_from_plan()` passes the full planned cell list into one private fresh-root orchestrator. Before root creation, that orchestrator requires an exact built-in cell list containing exact built-in dictionaries with only the five required keys and optional `announcement`. It shallow-copies each dictionary once, rejects dict subclasses, custom mappings, mapping proxies, missing or unexpected keys, nonexact string/list/integer values, nonexact boolean orchestration flags, unsafe condition components, and bool-as-integer values, and copies nested `extra_args` into an immutable tuple. The resulting frozen dataclass records are the only values used for condition/seed selection, path and command construction, announcements, metadata/results, iteration, and execution. The original list, dictionaries, and nested argument lists are not retained or reread after freezing; a regression mutates and clears exact caller-owned containers after preflight begins and proves execution still uses the frozen values.

The orchestrator independently preflights and creates the root, records its lexical and resolved paths plus device/inode, and keeps cell execution closure-bound. Before condition-directory creation, run-directory creation, diagnostic output creation, batch-manifest/index creation, artifact inspection, and every child launch, it revalidates the root path/identity, rejects symlinked components, requires the exact runner-owned root layout, and proves strict lexical and resolved containment. It tracks device/inode ownership for runner metadata, condition directories, and run directories, requires each target run directory to be absent before creation, and detects ordinary-directory replacement as well as symlink replacement. Direct imports or calls to the private orchestrator perform the same checks; no public or private execution path can adopt or escape into a nonempty unrelated root. Symlinked output roots, ancestors, cells, condition directories, data roots, manifests, and required artifacts are rejected.

A bounded two-cell regression uses only tiny Python marker children and a stub validation report. It proves both frozen cells execute exactly once in one invocation, the first cell plus runner-created manifest/index are accepted during second-cell revalidation, commands and paths use the frozen values, and every run directory remains below the initialized root. Separate child-spy/tree-snapshot regressions reject the Review 4 dual-view dict subclass, a mutating-after-read dict, an ordinary dict subclass, a custom mapping, a mapping proxy, malformed primitive types, condition replacement, ancestor symlink replacement, and unknown between-cell root entries before another launch. Preexisting bytes, shape, timestamps captured by the snapshot helper, and symlink metadata remain unchanged on preflight rejection.

The former stale summary/manifest/stderr deletion path was removed. Immutable attempt allocation, selected-attempt resume, and retry history remain deferred to their separately authorized slices.

## Determinism result

The current frozen 5-tick regression uses:

```text
seed=456
condition=termination_baseline
anti-stagnation=off
log_mode=metrics_only
```

Its state hash was:

```text
3dcb25d98e634034da0814618bd8c28f3f6289491a536238950e866c5e75bc6f
```

The frozen test passed after the final correction. Existing cross-process/cross-log-mode determinism tests also pass. Structured metric/event content intentionally follows the new timing contract; this is an observation correction, not a state transition.

The current 40-tick anti-stagnation regression also passed and freezes:

```text
ef15589175c3c1e48ddab9ba837429626c46423d2637b35e8120189e110a7163
```

Separately, during an earlier correction pass, a manual comparison reportedly ran unmodified `HEAD` and that working tree with this 40-tick configuration and found the same value. This final correction pass did not repeat that manual unmodified-`HEAD` comparison; it re-ran the frozen current-tree tests only.

## Files changed

Implementation:

- `run_experiments.py`
- `src/thalren_vale/artifact_contract.py` (new)
- `src/thalren_vale/artifact_validation.py` (new)
- `src/thalren_vale/events.py`
- `src/thalren_vale/inhabitants.py`
- `src/thalren_vale/metrics.py`
- `src/thalren_vale/reproducibility.py`
- `src/thalren_vale/sim.py`
- `src/thalren_vale/technology.py`

Tests:

- `tests/test_artifact_validation.py` (new)
- `tests/test_run_termination.py` (new)
- `tests/test_events.py`
- `tests/test_experiment_runner.py`
- `tests/test_reproducibility.py`
- `tests/test_simulation_state.py`

Documentation:

- `CODEX_TERMINATION_VALIDATION_HANDOFF.md` (new)

## Validation performed

The earlier handoff recorded this historical baseline before the original
patch; it was not re-run during the final correction:

```text
27 passed in 2.02s
```

Required six-file focused suite after the final correction pass:

```text
358 passed
```

Final parent suite:

```text
396 passed
```

Additional checks:

- `python -m compileall -q src run_experiments.py tests` — passed
- `git diff --check` — passed
- `python run_experiments.py --help` — exposes the three validation modes and documents `auto` as default

The tests use synthetic `tmp_path` artifacts, a bounded 32,768-row metrics memory fixture, independent 1,000-row and 65,000-row valid unique-event-detail fixtures, independent 1,000-row and 65,000-row malformed unique-technology fixtures, a 1,000-row malformed-metrics diagnostic-cap fixture, tiny timeout/cancellation/containment children, and short injected simulator subprocesses (including the necessary 50-tick pruning boundary and existing 40-tick anti-stagnation boundary). `tracemalloc` starts after fixture creation and is reset with garbage collection between cases. The prior Review 3 correction session reported malformed-event validation peaks of 1,386,683 bytes for 1,000 rows and 2,123,136 bytes for 65,000 rows. This containment session re-ran the regression through quiet pytest, so those exact values were not freshly emitted; the absolute/scaling ceilings and all aggregation assertions passed. The valid-row memory regressions also passed their absolute and scaling ceilings; no exact valid-row peak is claimed for this session. Both valid and malformed row-heavy evidence are therefore covered by bounded-memory regressions. No research experiment, experiment matrix, or long benchmark ran, and no experiment output was created.

All four review documents remained byte-for-byte unchanged. Their SHA-256 values after verification were:

```text
6d5be351200206bf33e6848e1daf2931e9c3826794fca0eebb9793d3fdd32273  CODEX_TERMINATION_VALIDATION_REVIEW.md
72aaa780d6e4370c484f81e7b6d285f904972415e08eb0a3c4a309005ae3ee17  CODEX_TERMINATION_VALIDATION_REVIEW_2.md
80b25fe82249fc54e39321d9c99fd23a74cb80a6331e8cabe13b5dd705341092  CODEX_TERMINATION_VALIDATION_REVIEW_3.md
1f2686f7e6dd48eb5840cf810cadb9fe543e6c88218aa1247e1dcf28a5ba6aee  CODEX_TERMINATION_VALIDATION_REVIEW_4.md
```

## Checks intentionally not run

- No Core Replication V1 full verification scan: legacy behavior is covered synthetically without streaming the completed large dataset.
- No S0/S1/P1/P2/Full run or configuration.
- No experiment matrix, long benchmark, package build, LLM-Wiki operation, tag, commit, or push.

## Model-routing disclosure

The operator selected **GPT-5.6 Sol Max** for this consequential work. In this active implementation session, the machine-readable context visible to the assistant identifies only Codex based on GPT-5 and exposes no exact `model=` or `reasoning_effort=` value. That visible label is an environment identifier, not cryptographic attestation, so the handoff does not attest that the serving model was the selected exact model/tier. A fresh independent Sol review of the corrected uncommitted patch remains required before any experimental authorization gate.

## Remaining gates

Still unimplemented and unauthorized:

1. General stop-on-first-nonaccepted orchestration.
2. Immutable attempt directories.
3. Append-only attempt ledger and explicit selection/supersession.
4. Clean-tag, expected-commit, and environment preflight.
5. Nonexecuting matrix expansion.
6. Remaining failure/resume/provenance tests tied to those slices.
7. Adversarial review of all V2 prerequisites.
8. Numeric budget and endpoint approval.
9. S0 JSON creation or execution.

The next recommended task is a verified Sol review of this bounded slice, followed—only if accepted—by the separately scoped general fail-fast orchestration slice.
