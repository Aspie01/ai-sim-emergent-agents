# Core V2 Test Gap Audit

**Audit date:** 2026-07-10  
**Scope:** Core V2 runner, termination, artifact validation, provenance, attempts, resume, and event-writer health  
**Status:** Documentation audit; no tests or simulations were run

## 1. Executive summary

**Overall verdict:** The existing suite is a useful foundation but does not yet prove that a Core V2 run is termination-aware, assignment-conformant, fail-fast, provenance-clean, or safely resumable.

The strongest current coverage is:

- seeded serial execution and same-seed state-hash repeatability;
- raid-control configuration and legacy combat-off/raids-on semantics;
- log-mode artifact policy and cross-mode state hashes;
- basic plan parsing, valid-run resume, and pure result classification;
- buffered event row content/order, finalization, and one recoverable flush failure.

The critical gaps are end-to-end termination semantics, deep streamed artifact validation, exact plan-to-manifest conformance, fail-fast orchestration, immutable attempts, append-only history, supersession, Git preflight, environment identity, and nonexecuting matrix expansion. The current `validate_run_outputs()` can accept nonempty header-only or partial artifacts, and the current valid-resume test does not protect against stale or exception-finalized artifacts.

The previously reported parent suite result was 58 passing tests. This audit did not rerun the suite and makes no claim that the current tree was retested.

### Coverage vocabulary

- **Covered:** Existing tests directly verify the complete prerequisite.
- **Partial:** Existing tests verify a component or pure classification, but not the end-to-end guarantee.
- **Missing:** No current test meaningfully verifies the prerequisite.

## 2. Existing test inventory

| Existing file | Relevant coverage | Boundary of current coverage |
|---|---|---|
| `tests/test_experiment_runner.py` | Seed parsing, plan schema rejection, refusal to overwrite, valid resume, result-term mapping | No real timeout/cancellation/exception lifecycle, fail-fast, deep validation, stale resume, attempts, supersession, Git enforcement, or plan-mismatch test |
| `tests/test_events.py` | Typed events, exact buffered row content/order, final flush, one fail-once retry | No persistent/unresolved writer failure, manifest health propagation, or validator rejection |
| `tests/test_reproducibility.py` | Seeded serial Layer 1, canonical serialization, same-seed hashes, raid-disabled determinism, manifest code fields | No termination fields, dirty-tree enforcement, expected commit/tag, plan hash, environment fingerprint, or cancellation/exception process result |
| `tests/test_log_modes.py` | Required structured outputs, optional text suppression, state hashes across modes, invalid CLI mode | Uses the shallow validator; does not test truncated/header-only artifacts, final tick, or contract conformance |
| `tests/test_config.py` | Disabled-layer normalization, explicit raids, combat-only compatibility, invalid values | No plan-to-effective-config comparison or controlled-argument override rejection |
| `tests/test_raid_control.py` | Economy raid gate and legacy default | No runner condition contract or manifest rejection path |
| `tests/test_raid_control_pilot.py` | Complete 2×2 pilot matrix and completed-only aggregation | Tests the pilot helper, not V2 plan expansion or runner enforcement |
| `tests/test_antistagnation.py` | Traveler cadence and disable flag | Does not verify the full anti-stagnation bundle as a V2 condition contract |
| `tests/test_simulation_state.py` | Shared state/reset and same-seed in-process behavior | No process-level termination or runner artifact classification |

## 3. Master coverage matrix

| V2 prerequisite | Status | Recommended test file | Primary recommended test | Subprocess isolation |
|---|---|---|---|---|
| Requested-horizon termination manifest | Missing | `tests/test_run_termination.py` | `test_requested_horizon_records_completed_termination` | Optional tiny integration |
| `KeyboardInterrupt` | Missing | `tests/test_run_termination.py` | `test_keyboard_interrupt_records_cancelled_and_exits_nonzero` | **Required** |
| Ordinary exception | Partial | `tests/test_run_termination.py` | `test_unhandled_exception_records_exception_and_exits_nonzero` | **Required** |
| Timeout | Partial | `tests/test_experiment_runner.py` | `test_timeout_records_wall_clock_limit_and_stops_queue` | Mock plus one tiny child recommended |
| Extinction/natural termination | Missing | `tests/test_run_termination.py` | `test_extinction_records_allowed_natural_termination` | No, if lifecycle is injectable |
| Truncated CSV | Missing | `tests/test_artifact_validation.py` | `test_rejects_truncated_structured_csv` | No |
| Header-only CSV | Missing | `tests/test_artifact_validation.py` | `test_rejects_header_only_metrics_for_completed_run` | No |
| Wrong final tick | Missing | `tests/test_artifact_validation.py` | `test_rejects_manifest_and_metrics_final_tick_mismatch` | No |
| Wrong condition configuration | Partial | `tests/test_condition_contracts.py` | `test_rejects_effective_configuration_mismatch` | No |
| Wrong plan hash | Partial implementation, missing test | `tests/test_resume_and_attempts.py` | `test_resume_refuses_plan_hash_mismatch_without_mutation` | No |
| Wrong expected commit | Missing | `tests/test_runner_preflight.py` | `test_preflight_rejects_wrong_expected_commit` | No; temporary Git repository |
| Dirty Git tree | Partial recording, missing enforcement | `tests/test_runner_preflight.py` | `test_preflight_rejects_dirty_worktree_before_output_creation` | No; temporary Git repository |
| Stale resume artifacts | Missing | `tests/test_resume_and_attempts.py` | `test_resume_never_reuses_stale_partial_attempt` | No |
| Immutable attempt directories | Missing | `tests/test_resume_and_attempts.py` | `test_retry_allocates_new_immutable_attempt_directory` | No |
| Append-only attempt ledger | Missing | `tests/test_attempt_ledger.py` | `test_attempt_ledger_preserves_prior_records_byte_for_byte` | No |
| Superseded-attempt preservation | Missing | `tests/test_resume_and_attempts.py` | `test_valid_replacement_preserves_and_supersedes_prior_attempt` | No |
| Buffered-write recovery | Covered locally, partial end-to-end | `tests/test_event_writer_health.py` | `test_writer_health_records_recovered_flush_failure` | No |
| Unresolved flush failure | Missing | `tests/test_event_writer_health.py` | `test_unresolved_flush_failure_invalidates_artifacts` | No |
| Stop on first failure | Missing | `tests/test_experiment_runner.py` | `test_noncompleted_cell_stops_before_next_cell` | No |
| Environment fingerprint | Missing | `tests/test_runner_preflight.py` | `test_environment_fingerprint_is_stable_and_secret_free` | No |
| Nonexecuting matrix expansion | Missing | `tests/test_plan_expansion.py` | `test_expand_plan_is_deterministic_and_has_no_side_effects` | No |

## 4. Detailed prerequisite audit

### 4.1 Termination-aware manifests

**Existing coverage:** Partial. `classify_result()` has direct unit coverage for numeric return codes, and short successful subprocess runs produce manifests. No test proves that simulator lifecycle state and process exit agree.

**Partially covered behavior:** Ordinary nonzero return-code classification is mapped to `exception`; negative return codes map to `cancelled`. These are pure-function assertions, not termination integration tests.

**Missing tests and expected assertions:**

| Behavior | Recommended function | Required fixture | Expected assertions | Isolation |
|---|---|---|---|---|
| Requested horizon | `test_requested_horizon_records_completed_termination` | `isolated_cli_env`, tiny deterministic lifecycle fixture | `requested_ticks == final_tick`; reason is requested horizon reached; status `completed`; `completed_normally is True`; process result zero; metrics end at `final_tick` | Optional tiny subprocess |
| `KeyboardInterrupt` | `test_keyboard_interrupt_records_cancelled_and_exits_nonzero` | test child that raises `KeyboardInterrupt` after a known completed tick | Nonzero process result; status/reason `cancelled`; `completed_normally is False`; `final_tick` is last full tick; partial artifacts are not reusable as completed | **Required** |
| Ordinary exception | `test_unhandled_exception_records_exception_and_exits_nonzero` | test child/injected lifecycle fault at a known tick | Nonzero process result; status/reason `exception`; final tick excludes the failed tick; best-effort artifacts remain explicitly partial; exception attempt fails validation | **Required** |
| Extinction | `test_extinction_records_allowed_natural_termination` | lifecycle state with population becoming empty at a known completed tick | reason `extinction`; final tick matches metrics; status is accepted only when contract permits natural termination; never confused with cancellation | No if helper is injectable |

**Failure cases to include:** interrupt before tick 1; exception before logger creation; exception during manifest write; exception during metrics finalization; extinction on requested final tick; termination-only metadata changing a state hash.

**Recommended filename:** `tests/test_run_termination.py`.

### 4.2 Deep artifact validation

**Existing coverage:** Missing. Log-mode tests call the existing presence validator, but no test adversarially corrupts artifacts.

**Partially covered behavior:** Valid short-run artifact names and nonempty files are exercised. Typed event field values and buffering order are checked separately.

**Missing tests:**

| Behavior | Recommended function | Fixture | Expected assertions | Isolation |
|---|---|---|---|---|
| Truncated CSV | `test_rejects_truncated_structured_csv` | `artifact_factory(truncate="events")` | Validation false; stable malformed/truncated-CSV error code; no full-file load; resume cannot select attempt | No |
| Header-only metrics | `test_rejects_header_only_metrics_for_completed_run` | `artifact_factory(metrics_rows=[])` | Completed positive-tick attempt rejected even though file is nonempty | No |
| Legitimate header-only events | `test_accepts_header_only_events_when_no_events_are_declared` | zero-event manifest plus headers | Event file accepted only when event count/contract permits zero rows | No |
| Pre-100-tick beliefs | `test_accepts_header_only_beliefs_before_snapshot_cadence` | final tick below first belief cadence | Belief headers accepted; validator does not invent required rows | No |
| Wrong final tick | `test_rejects_manifest_and_metrics_final_tick_mismatch` | manifest final tick 10 with metrics ending 9 and 11 variants | Explicit final-tick mismatch; attempt invalid | No |
| Tick order | `test_rejects_noncontiguous_metrics_and_regressing_event_ticks` | reordered/gapped CSV rows | Detect metrics gap and event regression; report file and row | No |
| Summary mismatch | `test_rejects_duplicate_or_wrong_attempt_summary` | duplicate/wrong seed summary rows | Exactly one matching attempt summary required | No |

**Failure cases:** invalid UTF-8 replacement hiding corruption; unterminated quoted field; extra columns; wrong schema version; event tick beyond final tick; valid empty event stream; bounded memory on a large synthetic stream.

**Recommended filename:** `tests/test_artifact_validation.py`.

### 4.3 Exact condition-contract validation

**Existing coverage:** Partial. `test_config.py` verifies normalized disabled layers and raid semantics; `test_raid_control.py` verifies the economy gate.

**Missing guarantee:** No test compares a frozen plan cell with the manifest's effective anti-stagnation, combat, raid, disabled-layer, log-mode, seed, and tick configuration.

**Recommended tests:**

- `tests/test_condition_contracts.py::test_all_factorial_conditions_expand_to_expected_contracts`
- `tests/test_condition_contracts.py::test_rejects_effective_configuration_mismatch`
- `tests/test_condition_contracts.py::test_controlled_flags_cannot_be_overridden_by_extra_args`
- `tests/test_condition_contracts.py::test_combat_off_does_not_implicitly_disable_raids`

**Required fixtures:** `condition_contract_factory`, canonical eight-condition matrix, manifest factory with field overrides.

**Expected assertions:** Exact booleans; canonical sorted `disabled_layers`; `log_mode == "metrics_only"`; runner-owned seed/ticks/condition cannot be duplicated or overridden; mismatch produces a stable contract error and invalidates resume.

**Subprocess isolation:** No. Test plan expansion, command construction, and manifest comparison as pure data.

### 4.4 Stop-on-first-failure

**Existing coverage:** Missing. The current loop proceeds after each `run_single()` result.

**Recommended tests:**

- `tests/test_experiment_runner.py::test_noncompleted_cell_stops_before_next_cell`
- `tests/test_experiment_runner.py::test_failure_is_persisted_before_batch_returns`
- `tests/test_experiment_runner.py::test_valid_natural_terminal_does_not_trigger_fail_fast`
- Parameterize timeout, exception, cancellation, and invalid output.

**Required fixtures:** `fake_run_single` with invocation counter; temporary batch manifest/index; fake append-only ledger; deterministic clock.

**Expected assertions:** First nonaccepted result is persisted; batch `complete` is false; stop reason identifies cell/attempt/result; runner returns nonzero; invocation count proves no later cell launched; previously completed cells remain recorded.

**Subprocess isolation:** No. Mock cell results so this test cannot start a simulator.

### 4.5 Immutable attempt directories

**Existing coverage:** Missing. The current runner reuses one condition/seed directory and removes stale files on resume.

**Recommended tests:**

- `tests/test_resume_and_attempts.py::test_retry_allocates_new_immutable_attempt_directory`
- `tests/test_resume_and_attempts.py::test_retry_never_mutates_prior_attempt_files`
- `tests/test_resume_and_attempts.py::test_attempt_allocation_recovers_after_incomplete_start`
- `tests/test_resume_and_attempts.py::test_v2_rejects_overwrite`

**Required fixtures:** `attempt_tree_factory`, file-content checksum helper, deterministic attempt allocator, output-root escape cases.

**Expected assertions:** Attempts receive distinct monotonically allocated paths; attempt 1 bytes/checksums remain identical after attempt 2; selected path comes from metadata rather than newest-directory guessing; path stays below output root; historical layout remains readable.

**Subprocess isolation:** No.

### 4.6 Append-only attempt ledger

**Existing coverage:** Missing. Batch JSON and `run_index.csv` are rewritten views, not append-only history.

**Recommended tests:**

- `tests/test_attempt_ledger.py::test_attempt_ledger_preserves_prior_records_byte_for_byte`
- `tests/test_attempt_ledger.py::test_started_without_finished_remains_incomplete`
- `tests/test_attempt_ledger.py::test_ledger_rejects_two_selected_attempts_for_one_cell`
- `tests/test_attempt_ledger.py::test_malformed_trailing_record_is_not_silently_ignored`

**Required fixtures:** `attempt_ledger_factory`, deterministic timestamps/sequence numbers, partial-line fixture, ledger reconstruction helper.

**Expected assertions:** Appends never rewrite earlier bytes; sequence is monotonic; unfinished attempt stays visible; malformed record produces an audit error; exactly one validated attempt can be selected; derived index matches ledger state.

**Subprocess isolation:** No.

### 4.7 Safe resume and supersession

**Existing coverage:** Partial. `test_batch_refuses_overwrite_and_resumes_valid_run` verifies a simple valid skip and plan hash existence, but not adversarial resume conditions.

**Missing tests:**

| Behavior | Recommended function | Fixture | Expected assertions | Isolation |
|---|---|---|---|---|
| Wrong plan hash | `test_resume_refuses_plan_hash_mismatch_without_mutation` | attempt tree plus changed plan bytes | Raises/refuses before mutation; original tree and ledger unchanged | No |
| Stale partial artifacts | `test_resume_never_reuses_stale_partial_attempt` | header-only/exception-finalized attempt | Old attempt not skipped; remains preserved; new attempt allocated only after explicit resume | No |
| Successful replacement | `test_valid_replacement_preserves_and_supersedes_prior_attempt` | invalid attempt then valid attempt | Both directories remain; prior marked superseded only after replacement validates; one evidence selection | No |
| Failed replacement | `test_failed_replacement_does_not_supersede_selected_attempt` | selected valid attempt plus failed retry | Existing selection unchanged; failed attempt retained but unselected | No |
| History preservation | `test_resume_preserves_original_elapsed_status_and_errors` | completed and failed records | Original elapsed/status/errors unchanged; skipped view does not replace them with zero | No |

**Required fixtures:** `attempt_tree_factory`, `attempt_ledger_factory`, deep validator stub/result factory, plan/commit/environment fingerprints.

**Failure cases:** nonempty root without experiment manifest; commit/tag/environment mismatch; config/tick/log-mode mismatch; old failure deleted; same-seed retry counted twice.

**Recommended filename:** `tests/test_resume_and_attempts.py`.

### 4.8 Clean-tag, expected-commit, and plan preflight

**Existing coverage:** Partial. Manifest tests assert the presence of `commit` and `dirty`; runner code checks plan SHA on one resume path. No test enforces clean/tagged provenance before mutation.

**Recommended tests:**

- `tests/test_runner_preflight.py::test_preflight_rejects_dirty_worktree_before_output_creation`
- `tests/test_runner_preflight.py::test_preflight_rejects_wrong_expected_commit`
- `tests/test_runner_preflight.py::test_preflight_rejects_missing_or_wrong_annotated_tag`
- `tests/test_runner_preflight.py::test_preflight_fails_closed_when_git_lookup_fails`
- `tests/test_resume_and_attempts.py::test_resume_refuses_plan_hash_mismatch_without_mutation`

**Required fixtures:** `temporary_git_repo(tmp_path)` with initial commit and annotated tag; helpers for tracked/untracked dirtiness, tag retargeting, detached HEAD, and Git command failure.

**Expected assertions:** Preflight fails before output-root creation; expected commit equals `HEAD`; annotated tag resolves to that commit; dirty/unknown state is rejected; plan hash mismatch leaves all artifacts unchanged; no tag is auto-created.

**Subprocess isolation:** No Python/simulation subprocess is needed. Git commands run only inside the temporary repository.

### 4.9 Environment fingerprinting

**Existing coverage:** Missing. Tests set `PYTHONHASHSEED=0`, but no environment identity is produced or compared.

**Recommended tests:**

- `tests/test_runner_preflight.py::test_environment_fingerprint_is_stable_and_secret_free`
- `tests/test_runner_preflight.py::test_environment_fingerprint_changes_for_dependency_or_plugin_change`
- `tests/test_runner_preflight.py::test_resume_reports_environment_fingerprint_difference`

**Required fixtures:** mocked `sys`/`platform`/package metadata; requirements and plugin trees under `tmp_path`; environment containing sentinel secret values.

**Expected assertions:** Canonical sorted output and stable SHA-256; Python implementation/version/executable, platform/architecture, schemas, dependency inputs, plugin policy/inventory, and child `PYTHONHASHSEED` included; timestamps/hostname/secrets excluded; resume reports specific differing fields.

**Subprocess isolation:** No.

### 4.10 Nonexecuting matrix expansion

**Existing coverage:** Missing. Pilot matrix tests cover `run_raid_control_pilot.py`, not a V2 plan expansion path.

**Recommended tests:**

- `tests/test_plan_expansion.py::test_expand_plan_is_deterministic_and_has_no_side_effects`
- `tests/test_plan_expansion.py::test_expands_all_factorial_cells_with_shared_seeds`
- `tests/test_plan_expansion.py::test_rejects_duplicate_cells_and_controlled_flag_overrides`
- `tests/test_plan_expansion.py::test_execution_consumes_the_same_expanded_cell_objects`

**Required fixtures:** canonical V2 plan dictionary, temporary nonexistent output path, subprocess-launch spy that raises if called, stable JSON snapshot.

**Expected assertions:** Exact ordered cells/commands/contracts/paths/timeouts/counts; plan SHA present; `metrics_only` explicit; duplicate keys rejected; output root remains absent; no simulator subprocess or temporary inline plan created; repeated expansion byte-identical.

**Subprocess isolation:** No. Assert subprocess execution is never invoked.

### 4.11 Buffered-write and unresolved-flush health

**Existing coverage:** Partial-to-covered for local recovery. `test_event_buffer_flushes_in_order_during_finalize` verifies exact row order/content, and `test_event_flush_failure_is_nonfatal_and_retryable` verifies one failed flush followed by success.

**Missing guarantee:** The recovered failure is not surfaced as run health, and a persistent failure is neither manifested nor rejected by validation.

**Recommended tests:**

- `tests/test_event_writer_health.py::test_writer_health_records_recovered_flush_failure`
- `tests/test_event_writer_health.py::test_persistent_flush_failure_remains_unresolved`
- `tests/test_event_writer_health.py::test_unresolved_flush_failure_invalidates_artifacts`
- `tests/test_event_writer_health.py::test_close_does_not_clear_unresolved_failure_state`

**Required fixtures:** existing `FailOnceHandle` promoted to shared helper; `AlwaysFailHandle`; manifest/logger-health collector; synthetic validator contract.

**Expected assertions:** A recovered failure increments total failures but leaves zero unresolved failures; persistent failure leaves pending rows/unresolved health; close/finalize cannot falsely reset it; manifest exposes health; deep validation rejects any unresolved writer failure; row order remains unchanged after recovery.

**Subprocess isolation:** No.

## 5. Shared fixture design

Create reusable fixtures rather than duplicating ad hoc files:

- `artifact_factory(tmp_path)`: emits a valid V2 artifact set and supports header-only, truncation, schema, tick, seed, condition, summary, termination, and writer-health overrides.
- `termination_manifest_factory`: emits requested-horizon, extinction, cancelled, exception, timeout-partial, and invalid-output records.
- `condition_contract_factory`: emits canonical anti-stagnation/combat/raids/log-mode expectations.
- `attempt_tree_factory`: creates immutable attempts with selectable validity and byte snapshots.
- `attempt_ledger_factory`: appends lifecycle events and reconstructs selected/superseded state.
- `temporary_git_repo`: creates commits and annotated tags and introduces tracked or untracked dirtiness.
- `fake_run_single`: returns controlled outcomes and records calls without starting a simulator.
- `isolated_cli_env`: supplies only deterministic `PYTHONPATH` and `PYTHONHASHSEED=0` inputs needed by tiny process tests.
- `FailOnceHandle` and `AlwaysFailHandle`: model recovered and unresolved flush failures.

Keep fixtures close to their test modules unless three or more modules share them; only then promote them to `tests/conftest.py` or a small `tests/helpers/` module.

## 6. Subprocess-isolation policy

| Scenario | Policy | Reason |
|---|---|---|
| `KeyboardInterrupt` | Required | Must prove top-level process return code and partial-finalization semantics |
| Ordinary exception | Required | Must prove exception propagation after best-effort cleanup |
| Timeout | Unit mock required; one tiny child recommended | Unit test owns deterministic orchestration; tiny child confirms timeout integration without simulation |
| Natural extinction | Prefer injected lifecycle unit; tiny process optional | Scientific simulation is unnecessary to test terminal classification |
| CSV corruption/final tick/config | Not required | Pure synthetic artifact validation is faster and more exhaustive |
| Git/plan/environment preflight | Not required | Temporary Git repository and mocked environment are sufficient |
| Attempts/ledger/resume/fail-fast | Not required | Filesystem fixtures and controlled outcome stubs provide deterministic coverage |
| Buffered writer failures | Not required | File-handle wrappers directly exercise failure paths |

No recommended test should run a research-scale simulation. Diagnostic subprocesses must be fixed to a few seconds and use injected/test-fixture failure behavior.

## 7. Recommended test implementation order

1. Termination manifest and process-exit tests.
2. Synthetic deep artifact validation tests.
3. Exact condition-contract tests.
4. Environment and Git preflight tests needed by attempt provenance.
5. Immutable attempt-directory tests.
6. Append-only ledger tests.
7. Stop-on-first-failure tests.
8. Resume and supersession tests.
9. Nonexecuting matrix-expansion tests and execution/expansion identity.
10. Cross-feature integration tests using synthetic artifacts and tiny fixture processes only.

## 8. V2 test-readiness acceptance checklist

- [ ] Every termination path records requested/final tick, reason, status, and completion flag.
- [ ] Cancellation and exception exit nonzero and cannot resume-skip as completed.
- [ ] Natural extinction has a predeclared acceptance rule.
- [ ] Deep validation rejects truncation, header-only metrics, wrong ticks, wrong contracts, and unresolved writer failures.
- [ ] Zero-event and pre-belief-cadence files remain valid when contractually correct.
- [ ] Plan hash, expected commit/tag, clean tree, environment, and exact condition contract are enforced before mutation.
- [ ] A noncompleted cell is persisted and stops the queue before the next invocation.
- [ ] Every retry receives an immutable attempt directory.
- [ ] Attempt history is append-only and reconstructable after interruption.
- [ ] Supersession preserves all attempts and selects exactly one validated replicate.
- [ ] Resume refuses stale, partial, wrong-plan, wrong-code, wrong-environment, and wrong-config artifacts.
- [ ] Buffered recovery preserves rows; unresolved flush failure invalidates evidence.
- [ ] Matrix expansion is deterministic, machine-readable, and produces no filesystem or subprocess side effects.
- [ ] All new tests remain bounded and run without research experiments.

Until every item is satisfied, the suite should be described as supporting pilot engineering but not proving Core V2 runner readiness.
