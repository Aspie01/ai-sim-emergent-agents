# Termination-Aware Lifecycle and Artifact Validation — Final Independent Review 4

Date: 2026-07-10  
Repository: `/home/lfs/Projects/ai-sim-emergent-agents`  
Branch: `core-v2-runner-hardening`  
Review scope: current uncommitted termination-aware lifecycle and artifact-validation patch

## Verdict

**changes required**

## Executive assessment

This review was re-derived from the current implementation, tests, plans, backlog, audit,
handoff, and prior review inputs. Three of Review 3's four major findings are resolved:
opaque journal-token ownership is enforced, malformed present provenance is invalid, and
malformed-row diagnostics are bounded by issue class. The reported focused and full suites
also pass.

The fresh-root authorization finding is not fully resolved. The old forgeable secret and
context objects are gone, and the internal orchestrator performs substantial fresh-root
validation. However, `_run_cells_in_fresh_root()` validates caller-owned cell mappings with
`dict.get()` and later consumes the same caller-owned objects with `dict.__getitem__()`.
Because those values are not copied into a frozen internal representation, an ordinary
caller can import the private helper and supply a `dict` subclass that presents safe values
during preflight and traversal values during execution. The resulting `run_dir` is not
independently proven to remain beneath the validated output root. This can direct directory
creation, output capture, and child execution into an unrelated nonempty sibling tree.

That remaining evidence-root containment defect is major and must be corrected before the
patch is committed as the completed termination/artifact-validation prerequisite.

## Model-routing disclosure

The operator selected **GPT-5.6 Sol Max** for this review. This is a consequential
runner-lifecycle, provenance, and artifact-validation review for which the repository policy
requires the Sol tier. Exact machine-readable model identifier and reasoning-effort metadata
were not exposed in this session, so this report cannot independently attest to a more
specific runtime model or reasoning setting. No model downgrade is claimed.

The visible environment identified the repository, branch, current date, timezone, shell,
working directory, and filesystem policy. That environment metadata is operational context,
not cryptographic attestation of model routing, source identity, or execution provenance.

## Disposition of Review 3 major findings

| Review 3 finding | Disposition | Assessment |
| --- | --- | --- |
| M1 — forgeable fresh-batch capability | **Not fully resolved** | `_FRESH_BATCH_SECRET` and `_FreshBatchContext` are removed, but the remaining importable private orchestrator validates and executes different observable views of caller-owned mappings and lacks an independent run-directory containment proof. |
| M2 — forgeable numeric `JournalToken` | **Resolved** | Token construction, ownership, generation, exact-record identity, copying, pickling, stale use, cross-log use, and double claims are rejected; valid promotion claims exactly one owned record. |
| M3 — malformed present provenance treated as readiness-only | **Resolved** | Absent or well-formed incomplete provenance may remain valid but non-ready; malformed present provenance creates stable validity issues and is invalid and non-ready. |
| M4 — unbounded malformed-row diagnostics | **Resolved** | Diagnostics are grouped by artifact and stable issue code, retain at most three capped representatives per group, account for all occurrences, and materialize one issue per group. |

## Findings

### R4-M1 — caller-controlled cell mappings can escape the validated fresh root

Severity: **major**

Affected implementation:

- `run_experiments.py::_run_cells_in_fresh_root()`
- `run_experiments.py::_safe_existing_ancestor()`
- the `run_dir` construction, creation, child launch, and output-capture path inside the
  nested `execute_cell()` function

Affected or missing regression coverage:

- `tests/test_experiment_runner.py::test_old_fresh_batch_capability_surface_is_removed`
- `tests/test_experiment_runner.py::test_private_fresh_root_orchestrator_rejects_nonempty_roots_read_only`
- `tests/test_experiment_runner.py::test_private_fresh_root_orchestrator_has_no_rebind_or_reuse_argument`
- `tests/test_experiment_runner.py::test_fresh_batch_revalidates_the_owned_layout_before_each_cell`
- the private-orchestrator symlink rejection tests
- no adversarial mutable/dual-behavior mapping test
- no successful multi-cell fresh-batch test

Mechanism:

1. The initial cell-validation pass reads caller-owned mappings with `cell.get(...)`.
2. The nested executor and later orchestration read the same objects with `cell[...]`.
3. Runtime annotations do not prevent a caller from passing a `dict` subclass. Such a
   mapping can return a safe canonical condition from `.get("condition")` and a traversal
   value such as `"../unrelated"` from `__getitem__("condition")`.
4. Preflight therefore validates and records an absent or empty intended output root using
   the safe view, while execution constructs `run_dir` using the second view.
5. `_safe_existing_ancestor(run_dir)` rejects symlink ancestors but does not establish that
   the lexical and resolved `run_dir` are descendants of the validated root.
6. If the escaped target cell itself is absent, `os.path.lexists(run_dir)` does not reject an
   already-nonempty unrelated parent. `run_dir.mkdir(parents=True)` can then create the cell
   there before launching the child and opening output files.

This is not a claim that a public CLI route naturally creates such a mapping. It is the
explicitly requested private-helper audit: an ordinary Python caller can import and invoke
the remaining private helper. The helper is therefore not a closed authorization boundary
for fresh-root execution.

The existing child-spy and tree-preservation tests use ordinary dictionaries. They prove
the expected rejection paths for stable values, but they do not prove that the values
validated are the same values later used. The exploit was established by source inspection;
it was not executed because this review was restricted to the authorized checks and must not
mutate an unrelated tree or launch an additional simulation subprocess.

Required correction:

1. Validate each cell once, copy its exact primitive values into a newly allocated internal
   immutable/closed representation, and use only that representation for every subsequent
   path, command, metadata, and loop decision.
2. Before any `mkdir`, file open, or child launch, independently prove that every lexical and
   resolved per-cell path is a strict descendant of the recorded root and revalidate the
   root's lexical path and device/inode.
3. Add an adversarial `dict`-subclass or mutable-mapping regression proving rejection,
   untouched child-launch spies, and byte-for-byte/tree-shape preservation of the unrelated
   target.
4. Add a successful multi-cell regression proving that the frozen representation still
   supports the intended one-invocation batch path.

### Other findings

No separate blocker or additional implementation major was found. The missing successful
multi-cell test is a test-quality gap tied directly to R4-M1 and should be addressed with the
major fix rather than treated as an independent cosmetic issue.

## Fresh-root runner authorization audit

Confirmed from the current tree:

- `_FRESH_BATCH_SECRET` no longer exists.
- `_FreshBatchContext` no longer exists.
- No replacement caller-constructible capability object was found.
- No module-level per-cell executor remains available for entering a batch midway; the
  immediate executor is a closure.
- `_run_cells_in_fresh_root()` itself rejects an initially nonempty root, records the root's
  lexical path and device/inode, rejects symlinked root components, and revalidates the owned
  layout between cells for ordinary stable mappings.
- Unknown root entries and unknown condition entries reject.
- Requested cells are required to be absent in the validated stable-mapping path.
- `run_single()` rejects every nonempty root regardless of resume or overwrite flags.
- `run_from_plan()` rejects every nonempty initial root.
- The public routes contain no resume skip, overwrite, stale deletion, retry, adoption, or
  supersession behavior.
- The old private capability symbols are tested as absent, public and private rejection
  paths keep child-launch spies untouched, and fresh one-cell execution succeeds.

Not confirmed, because of R4-M1:

- that the metadata and cell paths used for execution are necessarily the same metadata and
  cell paths validated for this invocation;
- that every per-cell directory remains below the validated output root;
- that directory creation, output capture, and child launch always occur only after
  validation of the exact values being used;
- that every adversarially rejected tree remains unchanged;
- that every remaining private entry rejects unsafe caller-controlled roots.

There is also no successful multi-cell execution test. The two-cell revalidation test
deliberately injects an unknown entry after the first cell and proves the second child is not
launched; it does not exercise a successful two-cell batch.

## Opaque `JournalToken` ownership audit

The current implementation and regressions support the required token invariants:

- The public constructor rejects.
- Tokens are allocated only through their owning `StructuredEventLog` path.
- Validity depends on opaque log-object ownership, reset-generation identity, and exact
  journal-record object identity, not tick/sequence values.
- Default identity equality and hashing cannot be forged from public numeric fields.
- Owner, generation, and record identities are not exposed by the token repr or ordinary
  public attributes.
- Copy, deep copy, and pickle reconstruction reject.
- Manually allocated, guessed, foreign-log, stale-generation, stale-after-clear, and
  double-claimed tokens reject.
- `reset_runtime_state()` invalidates old tokens; sequence reuse after `clear()` is harmless
  because generation and record identity must also match.
- A valid promotion claims exactly one journal record and verifies the exact tick and text.
- Wrong tick and wrong text reject.
- Repeated identical messages retain the intended actor association through exact token
  ownership.
- Typed, typed-only, promoted, and legacy-only records remain exact-once.
- Pruning creates no journal records.
- `begin_observation_tick()` cannot discard undrained records.
- `drain_observation_journal()` clears the bounded journal and token-record state.

The focused regressions explicitly cover stale, cross-log, guessed, copied, manually
allocated, wrong-record, wrong-text/tick, and double-claimed tokens. Frozen simulation-state
hash tests pass, and no added token path consumes RNG or changes simulation-state behavior.

## Present provenance validity audit

The validator now implements the required distinction:

- absent provenance can remain valid schema 2 but is not V2-ready;
- well-formed incomplete provenance can remain valid but non-ready;
- malformed present provenance is invalid and non-ready;
- complete, exact provenance can be V2-ready only when a complete expected contract is also
  supplied and matched.

`_validate_present_provenance()` validates `plan_identity`, lowercase 64-character
`plan_sha256`, the nested code object, lowercase 40-character hexadecimal commit, nonempty
tag, exact-boolean dirty state, and the nested environment fingerprint. Integer booleans are
not accepted. Null, scalar, list, numeric, malformed dictionary, alias, conflicting, unknown,
and unsupported future representations reject cleanly. Nested object shapes and supported
keys are closed rather than silently normalized from aliases.

Malformed fields create stable validity issue codes; they do not survive solely as readiness
mismatches, do not become V2-ready, and do not raise validator exceptions. The regressions
assert `valid is False`, `v2_ready is False`, invalid classification, and the expected stable
issue code for malformed-present cases. Exact-match and absent/incomplete cases are tested
separately.

## Bounded malformed-row diagnostics audit

`_IssueCollector` groups validity diagnostics by `(artifact, stable issue code)`, retains at
most three representative occurrences per group, caps representative messages at 160
characters, counts every occurrence, computes suppression as total minus retained, and
materializes one aggregate issue per group. It retains representative row numbers and capped
text rather than complete malformed rows. Unique bad values therefore do not create one
issue object each, while later distinct issue codes still receive their own buckets after an
earlier bucket reaches its representative cap.

Metrics, events, beliefs, summary, inventory, and manifest validation routes use the bounded
collector. Readiness mismatches remain separate from validity aggregation, preventing a
validity problem from being hidden by or incorrectly merged into readiness classification.
Streaming loops continue through all CSV rows, so row counts and checksums are completed even
after a diagnostic group reaches its cap.

The malformed-event memory regression has the requested structure:

- the 1,000-row and 65,000-row fixtures are generated before tracing begins;
- each size is measured independently;
- garbage collection occurs before each measurement and tracing is started and stopped for
  each measurement;
- rows contain unique invalid technology values that would reproduce the prior unbounded
  diagnostic defect;
- all rows contribute to the aggregate occurrence count;
- three representatives remain and suppression equals occurrences minus three;
- the result is invalid;
- the absolute peak bound is below 32 MiB and the large-case scaling bound is no more than
  three times the small peak plus 2 MiB;
- the final-row assertions prove the validator did not stop at the diagnostic cap.

The malformed metrics/beliefs cap regression and the retained valid metrics/events
row-heavy memory regressions also pass. The handoff reports exact malformed-event peaks of
1,386,683 bytes for 1,000 rows and 2,123,136 bytes for 65,000 rows. The authorized quiet
pytest invocation captured passing-test stdout, so those exact historical measurements were
not freshly emitted or independently re-measured in this review; what was freshly confirmed
is that the memory regression and its absolute/scaling assertions pass.

## Earlier invariant recheck

Code inspection and the passing focused/full suites support the following:

- exact manifest, control, and inventory typing;
- separation of `valid` from `v2_ready`, strict/auto/legacy modes, and schema 1 never becoming
  V2-ready;
- `final_tick` as the last fully completed tick;
- requested-horizon and registered-extinction semantics;
- distinct handling of `KeyboardInterrupt`, `SystemExit`, ordinary exceptions, and direct
  child timeouts;
- completed-manifest publication as the final fallible publication operation, without broad
  `BaseException` suppression;
- writer-health consistency and explicit zero-event policy;
- belief-cadence cardinality and end-of-tick observation;
- exact-once structured-event ordering;
- artifact inventory/checksum integrity, traversal and symlink rejection;
- finite numeric and domain validation plus deterministic cross-artifact checks;
- bounded valid-row validation;
- the documented direct-child-only timeout limitation;
- frozen 5-tick and 40-tick current-tree state hashes.

The frozen current-tree tests are the relevant regression evidence for this uncommitted
patch. The handoff clearly distinguishes those test constants from its earlier manual
comparison against `HEAD`; the manual comparison is not treated here as current-tree
execution evidence.

## Test-quality assessment

The test suite is unusually strong for the current lifecycle/validation scope. It uses
synthetic temporary artifacts, short subprocesses, launch spies, exact stable issue-code
assertions, state-hash freezes, strict type cases, path/symlink cases, malformed streaming
cases, and bounded memory checks. The focused suite covers the six requested files and the
full suite supplies a useful regression backstop.

The material weakness is the private fresh-root test model: stable built-in dictionaries do
not exercise a caller-owned object whose validated and executed views differ. The suite also
lacks a successful multi-cell batch test. Those gaps explain why the old capability symbols
could be removed while an importable private-helper bypass remained.

## Handoff substantiation

The handoff was checked claim by claim against the current tree and test results.

Substantiated:

- Its implementation and test file inventories are complete for the inspected patch.
- The focused total is exactly 324 passing tests.
- The full total is exactly 362 passing tests.
- Compileall, diff checking, and CLI help pass.
- Opaque token ownership, reset-generation invalidation, exact-record claims, and anti-copy /
  anti-pickle behavior match the implementation and regressions.
- Absent/incomplete versus malformed-present provenance semantics match the implementation
  and regressions.
- Bounded diagnostic grouping, representative caps, occurrence counts, and suppression
  behavior match the implementation and regressions.
- Valid-row and malformed-row-heavy memory tests pass their encoded bounds.
- Frozen current-tree hashes pass, and the handoff appropriately distinguishes them from the
  earlier manual `HEAD` comparison.
- No nonempty-root resume skip, adoption, destructive overwrite, stale deletion, retry, or
  supersession path was found in the public runner.
- No research experiment output is claimed, and no experiment output appeared during this
  review.
- The handoff's model-routing disclosure appropriately says routing is operator/wrapper
  controlled and does not present environment metadata as attestation.

Not fully substantiated or overstated:

- The claim that fresh-batch authorization is fully non-forgeable and that only cells created
  by the same invocation can be executed is stronger than the implementation supports,
  because `_run_cells_in_fresh_root()` reuses unfrozen caller-controlled mappings and lacks
  an independent per-cell containment proof.
- The exact 1,386,683-byte and 2,123,136-byte peaks remain reported handoff measurements. The
  passing quiet test confirms the encoded bounds and aggregation behavior, but it does not
  independently expose those exact values for comparison.

## Scope and research-integrity assessment

The patch remains within termination-aware lifecycle and deep artifact-validation work. It
does not create S0, S1, P1, P2, or Full configuration; does not implement later immutable
attempt, resume/ledger, clean-tag/environment-preflight, or matrix-expansion stages; and does
not establish that Core Replication V2 has produced evidence.

This review ran no standalone simulation, experiment plan, research tier, matrix, historical
evidence scan, or external service. Only the repository's authorized focused/full tests,
compile check, diff check, and help command were run. Short synthetic subprocesses launched
by tests are engineering validation, not research cells. `experiment_runs/`, `data/`, `logs/`,
and the nested `LLM-Wiki/` repository showed no status changes before or after verification.

## Commands and exact results

Focused six-file suite:

```text
python -m pytest -q tests/test_artifact_validation.py tests/test_run_termination.py tests/test_events.py tests/test_experiment_runner.py tests/test_reproducibility.py tests/test_simulation_state.py
324 passed in 12.42s
```

Full suite:

```text
python -m pytest -q
362 passed in 15.17s
```

Compilation:

```text
python -m compileall -q src run_experiments.py tests
exit 0; no output
```

Diff whitespace/error check:

```text
git diff --check
exit 0; no output
```

CLI help:

```text
python run_experiments.py --help
exit 0; help displayed successfully, including strict/auto/legacy validation modes and the documented auto default
```

No unauthorized check or research execution was substituted for these commands.

## Stable-tree verification

SHA-256 values were recorded before substantive inspection, recomputed after verification,
and recomputed again before this verdict. Every inspected input remained byte-identical:

```text
6d5be351200206bf33e6848e1daf2931e9c3826794fca0eebb9793d3fdd32273  CODEX_TERMINATION_VALIDATION_REVIEW.md
72aaa780d6e4370c484f81e7b6d285f904972415e08eb0a3c4a309005ae3ee17  CODEX_TERMINATION_VALIDATION_REVIEW_2.md
80b25fe82249fc54e39321d9c99fd23a74cb80a6331e8cabe13b5dd705341092  CODEX_TERMINATION_VALIDATION_REVIEW_3.md
3f388e65edb70e06d0f5cf2fd18b410bf1ae5a1f8b765d96b5a65e5b3a5e5dea  CODEX_TERMINATION_VALIDATION_HANDOFF.md
5ae298fbcb7330847d3f635dcc8dd5e74544f3287ec3a341f4f31f055664f8ff  run_experiments.py
10ed7df71343ccfb8c5fef9ae0c71844c7812dd90f41ecc385de2ced85039dcd  src/thalren_vale/artifact_contract.py
860c7a771208766e0a8de4794e1a68661d3b503e8bda9ddd87a5b6d7a02c45f7  src/thalren_vale/artifact_validation.py
42c459450c0b237f6f712ab6e04e1279e6c46d2a339efb409e2a4005237f7241  src/thalren_vale/events.py
09c9697191010e1da034a88adf680bf75cfbce843ef3f3e2f793225aced9e350  src/thalren_vale/inhabitants.py
1c3bc2e47efa1b80842a9f357a9407fb4bba911ced055872426d4589375e76d4  src/thalren_vale/metrics.py
b8f55d525dbb3d58c33970b9892f6ff9302bc982a3281147d8f6ad8219c55b2d  src/thalren_vale/reproducibility.py
8db604552e6012e8ea15bec489ce37d5c49f772bb1f32347229f030775ff5580  src/thalren_vale/sim.py
00b56b9fc230f8b1d6ee6112b2d3a83f179349bdf44811b35ccc820fe1487429  src/thalren_vale/technology.py
d946e5f3b63d34b00b07f183f60d667053bd0e16fde417c55a09978be7d7523b  tests/test_artifact_validation.py
f1feac8a832819b3ebda645fb8d217590f9d0b8f772dc05c5bb2ef938ef12b28  tests/test_run_termination.py
587b45c88dbf66dd3aa30950a270cdcf872017839a136201371cb19ae47a81f7  tests/test_events.py
180d20e1f17f495051834d20ec311ef56997c9f146401acb347526249d8876bc  tests/test_experiment_runner.py
c527ef33c8672163fac7589dd4865e5f72ec4b370ab7d4b6a0d506a5f43849cf  tests/test_reproducibility.py
76552261146da0a09fd7af28d4d522999437adfc32e1303dd58f2a45f1758f3a  tests/test_simulation_state.py
```

No input changed, so no rebaseline or affected-check repetition was necessary. This Review 4
file is the only newly created file.

## Required fixes before commit

1. Freeze validated cell data into a new closed internal representation and stop reading
   caller-owned mappings after validation.
2. Enforce lexical and resolved descendant containment for every per-cell path immediately
   before any directory creation, output-file creation, or child launch.
3. Add the adversarial mapping/tree-preservation/child-spy regression and a successful
   multi-cell execution regression.
4. Re-run the focused six-file suite, full suite, compileall, `git diff --check`, CLI help,
   frozen hash regressions, and stable-tree controls, followed by an independent review of
   the corrected tree.

## Final recommendation

Do not commit or treat this patch as completing the termination-aware lifecycle and artifact-
validation gate yet. Correct R4-M1 and its regression gap, then repeat the authorized checks
and final independent review. The three other Review 3 major findings are adequately resolved.
No later runner-hardening stage or Core Replication V2 experimental gate is authorized by
this review.
