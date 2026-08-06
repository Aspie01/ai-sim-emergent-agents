# Review 5 — Final Runner-Containment Acceptance Review

Date: 2026-07-10  
Repository: `/home/lfs/Projects/ai-sim-emergent-agents`  
Branch: `core-v2-runner-hardening`  
Scope: read-only acceptance review of the Review 4 R4-M1 correction

## Verdict

**approve**

## Executive assessment

Review 4 finding R4-M1 is fully corrected. The current private fresh-root
orchestrator accepts only an exact built-in list of exact built-in cell
dictionaries, snapshots each accepted dictionary once, validates exact keys and
primitive types, copies nested arguments into tuples, and executes only immutable
`_FrozenCell` records. The Review 4 dual-view `dict.get()` versus
`dict.__getitem__()` authorization gap no longer exists.

The runner independently proves lexical and resolved containment for condition,
run, metadata, temporary-metadata, and diagnostic paths. After initializing the
fresh root, it revalidates the root's lexical path, resolved path, device/inode,
symlink-free ancestry, exact runner-owned layout, and owned metadata/condition/cell
directory identities before filesystem mutation, output creation, artifact
inspection, and child launch. Target cell directories must be absent before
creation. No resume skip, adoption, destructive overwrite, retry, stale deletion,
or supersession path was introduced.

The focused suite passed 358 tests and the full suite passed 396 tests. Compileall,
`git diff --check`, and CLI help passed. Every inspected input remained
byte-identical through verification, both frozen state-hash regressions passed,
and no experiment or evidence output was created.

No blocker, major finding, or minor finding was reproduced.

## Disposition of R4-M1

**Resolved and accepted.**

1. `_run_cells_in_fresh_root()` requires `type(cells) is list` and
   `_freeze_cell()` requires `type(cell) is dict` before any root creation.
2. Dict subclasses, the Review 4 dual-view dict, mutating dict subclasses,
   custom `Mapping` implementations, mapping proxies, and ordinary-looking dict
   subclasses reject without invoking their mapping methods.
3. `_freeze_cell()` copies the exact dict with `dict.copy()`, validates the
   closed required/optional key set, and returns a frozen dataclass.
4. The outer list is copied once for freezing; `extra_args` is copied to an
   immutable tuple. Local references to the caller list and dictionaries are
   discarded before preflight, and no later code reads an original cell object.
5. Condition, seed, ticks, timeout, extra arguments, announcement, identity,
   paths, command inputs, results metadata, logging, and loop decisions are read
   only from `_FrozenCell` instances.
6. The external-mutation regression changes condition, seed, ticks, nested
   `extra_args`, and clears the original list after freezing; execution still
   uses the original frozen `baseline`, seed 1, tick 1, and empty tuple.
7. `_strict_lexical_descendant()` rejects nonabsolute, equal-parent, escaping,
   `..`, and alternate lexical spellings. `_cell_paths()` additionally requires
   the condition and run paths to consist of their exact canonical components.
8. `_validate_contained_path()` rejects symlink components and proves resolved
   condition/run paths remain strictly beneath their resolved parents and root.
9. `_validate_root_anchor()` rechecks lexical identity, symlink-free ancestry,
   root type, device/inode, and resolved-root equality. The orchestrator calls it
   through `validate_root()` immediately at every post-initialization mutation,
   output, inspection, and launch boundary.
10. `_validate_initialized_root()` permits only invocation-owned metadata,
    conditions, and cells, with stored device/inode identities. Unknown entries,
    ordinary condition replacement, condition symlinking, and root-ancestor
    symlinking stop after the first child and before any second launch.
11. `validate_cell(..., require_run_absent=True)` runs immediately before every
    run-directory creation. Existing cell paths reject without deletion or reuse.
12. `run_single()`, `run_from_plan()`, and direct imports of
    `_run_cells_in_fresh_root()` all converge on the same fresh-root preflight.
    Every nonempty initial root rejects for ordinary, resume, and overwrite
    routes; no execution helper can enter midway through a batch.
13. The two-cell tiny-child regression proves same-invocation metadata and the
    first completed cell are accepted, both cells launch exactly once, frozen
    commands and paths are retained, and both resolved run directories remain
    beneath the initialized root.

## Findings

No reproducible blocker, major defect, or minor defect was found.

The ordinary caller-owned objects used in the Review 4 exploit are rejected
before root mutation. The corrected code does not depend on a secret, token,
caller-constructible capability, or differing mapping access methods. The only
per-cell executor remains a closure over the invocation-owned root state and
frozen cells.

## Affected files and functions inspected

Primary correction:

- `run_experiments.py::_FrozenCell`
- `run_experiments.py::_freeze_cell()`
- `run_experiments.py::_safe_existing_ancestor()`
- `run_experiments.py::_strict_lexical_descendant()`
- `run_experiments.py::_validate_contained_path()`
- `run_experiments.py::_validate_root_anchor()`
- `run_experiments.py::_preflight_fresh_output_root()`
- `run_experiments.py::_validate_initialized_root()`
- `run_experiments.py::_cell_paths()`
- `run_experiments.py::_ordinary_identity()`
- `run_experiments.py::_run_cells_in_fresh_root()` and its closure-bound
  validation/write/execute helpers
- `run_experiments.py::run_single()`
- `run_experiments.py::run_from_plan()`
- `run_experiments.py::_atomic_json()`
- `run_experiments.py::_write_index()`

Primary regression file:

- `tests/test_experiment_runner.py`

Unchanged lifecycle/validation implementation and regression inputs were also
rechecked by source inspection, stable hashes, and the focused/full suites:

- `src/thalren_vale/artifact_contract.py`
- `src/thalren_vale/artifact_validation.py`
- `src/thalren_vale/events.py`
- `src/thalren_vale/inhabitants.py`
- `src/thalren_vale/metrics.py`
- `src/thalren_vale/reproducibility.py`
- `src/thalren_vale/sim.py`
- `src/thalren_vale/technology.py`
- `tests/test_artifact_validation.py`
- `tests/test_run_termination.py`
- `tests/test_events.py`
- `tests/test_reproducibility.py`
- `tests/test_simulation_state.py`

## Test-quality assessment

The R4-M1 regression coverage is direct and adversarial rather than symbolic:

- `EscapingDict` returns a safe condition from `.get()` and traversal from
  `__getitem__()`; it rejects with zero reads.
- `MutatingAfterReadDict`, `OrdinaryLookingDictSubclass`, `ProxyCell`, and
  `MappingProxyType` all reject with no child launch or root creation.
- Tree snapshots include file bytes, directory/file modes, directory/file
  nanosecond mtimes, symlink targets, symlink modes, and symlink mtimes.
- The nonexact-mapping test snapshots the entire temporary tree and proves the
  intended root stays absent and the nonempty unrelated sibling is unchanged.
- The exact-dict mutation test mutates every relevant caller container after
  freezing and proves command arguments, result identity, and run path remain
  frozen while the unrelated tree is unchanged.
- Parameterized cases cover traversal, absolute paths, slash and alternate
  separators, string/list subclasses, bool seed/ticks/timeout, noninteger and
  nonpositive integer fields, malformed argument elements, malformed
  announcement, wrong keys, and nonboolean orchestration flags.
- Child spies prove nonempty roots, unknown entries, replaced condition
  directories, and symlinked root ancestors stop before another launch.
- The successful two-cell test launches only tiny Python marker children,
  accepts invocation-owned manifest/index and the first cell, verifies exact
  frozen command inputs, and proves each resolved run directory is below root.

The implementation session's reported runner-only result was 89 passed. This
acceptance review did not run a separate runner-only command because it was not
in the authorized command list; all runner tests were included in both the
358-test focused suite and the 396-test full suite.

## Regression assessment

The containment-only correction did not alter simulation dynamics, RNG calls,
layer ordering, artifact schemas, provenance schemas, or historical evidence.
The non-runner implementation/test inputs retained the same hashes recorded by
Review 4. Passing focused and full suites reconfirm:

- termination manifests and last-fully-completed-tick semantics;
- completed-manifest publication as the last explicit fallible operation;
- strict/auto/legacy separation and schema 1 never becoming V2-ready;
- separation of validity from V2 readiness and exact manifest/provenance types;
- opaque `JournalToken` owner/generation/record identity and exact-once claims;
- bounded valid-row and malformed-diagnostic memory behavior;
- writer-health consistency and explicit zero-event policy;
- belief-cadence cardinality;
- traversal and symlink rejection;
- authoritative end-of-tick observation; and
- frozen 5-tick and 40-tick state hashes.

## Handoff substantiation

`CODEX_TERMINATION_VALIDATION_HANDOFF.md` accurately describes the accepted
correction:

- its exact-list/exact-dict and immutable-freezing claims match the source;
- its claim that caller cell containers are not reread after freezing matches
  the execution path and the external-mutation regression;
- its lexical/resolved containment and inode-ownership claims match the helpers
  and every filesystem/launch boundary;
- its successful two-cell and adversarial test descriptions match the tests;
- its 358 focused and 396 full totals were reproduced;
- its compileall, diff-check, help, and frozen-hash claims were reproduced;
- its four prior-review hashes match this review's before/after controls;
- its no-skip/adoption/retry/overwrite and no-experiment-output claims match the
  code, status checks, and review scope.

The handoff correctly attributes the exact malformed-event memory peaks to the
prior Review 3 correction session and says quiet pytest did not freshly emit
them. This review confirms the encoded bounded-memory assertions pass; it does
not relabel the historical exact peaks as new measurements.

No handoff wording was found to be materially stronger than the implementation
or tests.

## Exact commands and results

Focused six-file suite:

```text
python -m pytest -q tests/test_artifact_validation.py tests/test_run_termination.py tests/test_events.py tests/test_experiment_runner.py tests/test_reproducibility.py tests/test_simulation_state.py
358 passed in 12.26s
```

Full suite:

```text
python -m pytest -q
396 passed in 14.89s
```

Compilation:

```text
python -m compileall -q src run_experiments.py tests
exit 0; no output
```

Diff validation:

```text
git diff --check
exit 0; no output
```

CLI help:

```text
python run_experiments.py --help
exit 0; help displayed successfully, including strict/auto/legacy and the documented auto default
```

No standalone simulation, research plan, experiment matrix, V2 tier,
historical-evidence scan, or external service was run. Short simulator and tiny
child subprocesses invoked by the authorized tests are bounded engineering
regressions, not research execution.

## Stable-tree verification

SHA-256 was recorded before inspection and recomputed after all authorized
checks and before this verdict. Every inspected input was byte-identical:

```text
6d5be351200206bf33e6848e1daf2931e9c3826794fca0eebb9793d3fdd32273  CODEX_TERMINATION_VALIDATION_REVIEW.md
72aaa780d6e4370c484f81e7b6d285f904972415e08eb0a3c4a309005ae3ee17  CODEX_TERMINATION_VALIDATION_REVIEW_2.md
80b25fe82249fc54e39321d9c99fd23a74cb80a6331e8cabe13b5dd705341092  CODEX_TERMINATION_VALIDATION_REVIEW_3.md
1f2686f7e6dd48eb5840cf810cadb9fe543e6c88218aa1247e1dcf28a5ba6aee  CODEX_TERMINATION_VALIDATION_REVIEW_4.md
e69492952e78c45848f410edf85d099d51e9eba11ac056fecc98a25f0acff066  CODEX_TERMINATION_VALIDATION_HANDOFF.md
0bf539b9b5c617e8646d544164e7a52e9016a4737fd4e767c55087bcedcdb37d  run_experiments.py
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
90e5f91bf8a6e4ee5eed15201a03ec4593f6a53b2f3d866cac9d0f31680e13b6  tests/test_experiment_runner.py
c527ef33c8672163fac7589dd4865e5f72ec4b370ab7d4b6a0d506a5f43849cf  tests/test_reproducibility.py
76552261146da0a09fd7af28d4d522999437adfc32e1303dd58f2a45f1758f3a  tests/test_simulation_state.py
```

`experiment_runs/`, `data/`, `logs/`, and the nested `LLM-Wiki/` repository
showed no status changes. No input required rebaselining. This Review 5 file is
the only newly created file.

## Model-routing disclosure

The operator's established selection for this consequential review is **GPT-5.6
Sol Max**. The machine-readable session context exposes Codex based on GPT-5 but
does not expose an exact `model=` identifier or `reasoning_effort=` value. This
report therefore does not claim independently verifiable runtime routing beyond
the operator selection. Visible environment metadata is operational context,
not cryptographic attestation.

## Final recommendation

Accept R4-M1 as closed and approve the current uncommitted termination-aware
lifecycle and artifact-validation patch for commit review. No correction is
required before commit for this bounded slice.

This approval does not authorize immutable attempts, ledger/supersession,
general fail-fast, clean-tag/environment preflight, matrix expansion, S0/S1/P1/
P2/Full configuration, or any Core Replication V2 execution. Those remain
separate authorization gates.
