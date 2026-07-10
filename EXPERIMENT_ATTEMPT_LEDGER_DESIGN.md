# Experiment Attempt Ledger Design

**Status:** Proposed architecture  
**Target:** `run_experiments.py` V2 runner schema  
**Scope:** Experiment, cell, attempt, selection, resume, validation, and audit history  
**Non-authorization:** This document does not authorize an experiment run or migration.

## 1. Design goals

The V2 runner must preserve every execution attempt without treating every attempt as an independent replicate. It must be possible to answer, from immutable evidence:

- What exact experiment and cell was requested?
- How many times was that cell attempted?
- What happened to each attempt?
- Which attempt, if any, is authoritative for research analysis?
- Why was a previously authoritative attempt superseded?
- Did resume reuse the same plan, code, environment, and condition contract?
- Was any evidence overwritten, silently adopted, or omitted after a crash?

The authoritative model is:

1. immutable experiment, cell, intent, artifact, and terminal-attempt records;
2. an append-only, hash-chained ledger of lifecycle and selection events; and
3. rebuildable selected-attempt and CSV views that are never authoritative.

Historical V1 outputs remain untouched and are accessed through a read-only compatibility adapter.

## 2. Identity model

### Experiment ID

`experiment_id` is the filename-safe identifier from the frozen plan and remains subject to the existing pattern:

```text
^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$
```

An experiment identity is the tuple:

```text
(experiment_id, exact_plan_sha256, expected_commit, expected_annotated_tag,
 environment_fingerprint, runner_schema_version)
```

Changing the plan bytes, scientific condition contract, requested horizon, timeout, expected commit/tag, or stable environment fingerprint creates a new experiment version and requires a new `experiment_id`. Resume never merges those changes into an existing experiment.

### Cell ID

A cell is one planned condition × seed × horizon assignment. Its canonical payload is:

```json
{
  "experiment_id": "core-replication-v2-smoke-s0",
  "plan_sha256": "4f5d...c821",
  "condition": "antistag_on_combat_off_raids_on",
  "seed": 1,
  "requested_ticks": 100,
  "condition_contract_sha256": "b9a4...34d2",
  "cell_role": "research"
}
```

`cell_id` is deterministic:

```text
cell_<first 24 lowercase hex characters of SHA-256(canonical cell payload)>
```

Canonical JSON uses UTF-8, sorted keys, no insignificant whitespace, and the same normalization rules as plan expansion. `cell_role` is `research` or `diagnostic`; diagnostic cells never enter the research replicate view.

### Attempt ID

Every process execution receives a globally unique attempt ID before launch:

```text
att_<32 lowercase hex characters from UUID4>
```

Attempt IDs are not counters and therefore do not require a race-prone global allocator. Ledger sequence numbers establish ordering. An attempt belongs to exactly one experiment and one cell and can never move between them.

## 3. Directory layout

```text
experiment_runs/
  <experiment_id>/
    experiment.json
    plan.json
    ledger/
      000000000001_experiment_created_<event_id>.json
      000000000002_cell_registered_<event_id>.json
      000000000003_attempt_started_<event_id>.json
      ...
    cells/
      <condition>/
        seed_<seed>/
          ticks_<ticks>__<cell_id>/
            cell.json
            attempts/
              <attempt_id>/
                intent.json
                runner_stdout.txt
                runner_stderr.txt
                data/
                  metrics_<condition>_seed_<seed>.csv
                  faction_events_<condition>_seed_<seed>.csv
                  beliefs_<condition>_seed_<seed>.csv
                  run_summaries.csv
                  run_manifest_<condition>_seed_<seed>.json
                attempt_manifest.json
    views/
      selected_attempts.json
      run_index.csv
      attempt_index.csv
      experiment_status.json
    .runner.lock
```

Rules:

- `experiment.json`, `plan.json`, `cell.json`, `intent.json`, committed ledger records, and `attempt_manifest.json` are immutable.
- Simulator outputs are writable only while their attempt is active. A committed `attempt_manifest.json` seals the attempt.
- No `latest` directory or symlink exists. Selection comes only from the ledger projection.
- `views/` files are disposable caches rebuilt atomically from immutable records.
- `.runner.lock` is operational coordination, not evidence. It may be recreated.
- V2 prohibits `--overwrite` and never deletes an attempt directory.

## 4. Attempt and selection states

Execution outcome and research selection are separate axes.

### Lifecycle and terminal outcome

| State | Meaning | Eligible for selection? |
|---|---|---:|
| `allocated` | Intent exists; process has not started | No |
| `running` | `attempt_started` is committed; no terminal record exists | No |
| `completed` | Process and accepted termination succeeded; deep validation passed | Yes |
| `invalid` | Artifacts, termination, contract, or validation failed regardless of process return code | No |
| `failed` | Process/runner ended by ordinary exception or infrastructure failure, excluding timeout/cancellation | No |
| `timed_out` | Runner wall-clock limit terminated the process | No |
| `cancelled` | Operator or user cancellation terminated execution | No |

`completed` is intentionally strict. It requires:

- process success;
- requested horizon or a plan-authorized natural terminal such as extinction;
- exact plan, condition, code, tag, environment, and log-mode conformance;
- deep streaming artifact validation;
- no unresolved metrics/event/belief writer failure; and
- a valid state hash and required artifact inventory.

### Selection state

| State | Meaning |
|---|---|
| `unselected` | Attempt exists but is not the authoritative research attempt |
| `selected` | This validated `completed` attempt is authoritative for its cell |
| `superseded` | This attempt was previously selected and was atomically replaced by a later validated `completed` attempt |

`superseded` is a projected selection state, not a rewritten execution outcome. A superseded attempt retains `outcome_status: completed` in its immutable manifest. Failed, invalid, timed-out, and cancelled attempts remain in their original outcome states; they are not mislabeled `superseded` merely because a later attempt succeeded.

For compatibility exports that require one status column, the derived effective status is:

- `superseded` when selection state is superseded;
- otherwise the immutable terminal outcome; or
- `running`/`allocated` when no terminal outcome exists.

## 5. Append-only ledger

### Storage format

The authoritative ledger is a directory of one immutable JSON file per record rather than a mutable JSONL file. This provides atomic append semantics using same-directory write-and-rename and avoids a partially appended final line.

Record filename:

```text
<12-digit-sequence>_<event_type>_<event_id>.json
```

Writers hold an exclusive `fcntl.flock` on `.runner.lock`, find and verify the current final sequence/hash, write the next record, and release the lock after file and directory `fsync`.

### Record schema

```json
{
  "ledger_schema_version": 1,
  "sequence": 7,
  "event_id": "evt_9ab1c7a923024f209bf98db3b0e88c73",
  "event_type": "attempt_finished",
  "recorded_at_utc": "2026-07-10T15:12:04.381Z",
  "experiment_id": "core-replication-v2-smoke-s0",
  "cell_id": "cell_37058a46eb0928517055700a",
  "attempt_id": "att_8a86bb0c767849a68e199406834e4d24",
  "payload": {},
  "writer": {
    "runner_schema_version": 2,
    "runner_version": "2.0.0"
  },
  "previous_record_sha256": "16be7fc8e98be842d1a89b862ef21dc65d80d5b88288f00a3d8f76ab672782d0",
  "record_sha256": "a401d35d771280af3f82d86a3207525688d9501dfcd91c73c94a9bf4defdf491"
}
```

Hashing rules:

- `record_sha256` is SHA-256 of canonical JSON with `record_sha256` omitted.
- The first record has `previous_record_sha256: null`.
- Every later record names the exact preceding record hash.
- Gaps, duplicate sequence numbers, invalid hashes, or a broken chain are fatal ledger-integrity errors.

### Event types

| Event type | Required payload |
|---|---|
| `experiment_created` | Plan/code/tag/environment identity and experiment paths |
| `cell_registered` | Cell contract, condition, seed, ticks, and role |
| `attempt_allocated` | Attempt path and immutable intent hash |
| `attempt_started` | Command hash, PID, start time, timeout |
| `attempt_finished` | Terminal outcome and attempt-manifest hash |
| `attempt_recovered` | Recovery finding and action after an interrupted runner |
| `validation_assessed` | Validator version, result, errors, artifact inventory hash |
| `attempt_selected` | Initially selected attempt and selection reason |
| `selection_replaced` | Old/new attempt IDs and explicit supersession reason |
| `selection_revoked` | Selected attempt removed after later validation invalidates it; no replacement yet |
| `batch_stopped` | Cell/attempt/result that triggered fail-fast behavior |
| `batch_completed` | All required research cells have selected attempts |

The ledger never records a mutable “current state.” Current state is deterministically projected by replaying valid records in sequence.

## 6. Attempt manifest

`attempt_manifest.json` is the immutable runner-level terminal record. It complements, but does not replace, the simulator's state/run manifest under `data/`.

### Schema

```json
{
  "attempt_manifest_schema_version": 1,
  "experiment_id": "core-replication-v2-smoke-s0",
  "cell_id": "cell_37058a46eb0928517055700a",
  "attempt_id": "att_8a86bb0c767849a68e199406834e4d24",
  "cell_role": "research",
  "condition": "antistag_on_combat_off_raids_on",
  "seed": 1,
  "requested_ticks": 100,
  "plan": {
    "sha256": "4f5d19f08e07655ac72a21e257e1928486e428b113d7d6590807acdb6369c821"
  },
  "condition_contract": {
    "anti_stagnation_enabled": true,
    "combat_enabled": false,
    "raids_enabled": true,
    "disabled_layers": ["combat"],
    "log_mode": "metrics_only",
    "sha256": "b9a4ce6c26df871f259dc6becf234b173046b75ba10b9ae87bbc451af78334d2"
  },
  "provenance": {
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "annotated_tag": "core-replication-v2-smoke-ready",
    "code_dirty": false,
    "environment_sha256": "2ae503cf3dd39a3c0715adae4c0c9e5f20bb69ca256bcbdd557d983b58c84f40"
  },
  "command": {
    "argv": ["python", "-m", "thalren_vale", "--seed", "1", "--ticks", "100"],
    "sha256": "4d807f5ca240f7d967f436a587299f3fe12419e8ba4b1856c483aca76e7aad01"
  },
  "timing": {
    "started_at_utc": "2026-07-10T15:10:00.000Z",
    "finished_at_utc": "2026-07-10T15:12:04.000Z",
    "elapsed_seconds": 124.0
  },
  "termination": {
    "outcome_status": "completed",
    "reason": "requested_ticks_reached",
    "returncode": 0,
    "requested_ticks": 100,
    "final_tick": 100,
    "completed_normally": true
  },
  "validation": {
    "validator_schema_version": 2,
    "status": "valid",
    "assessed_at_utc": "2026-07-10T15:12:04.250Z",
    "errors": [],
    "warnings": [],
    "artifact_inventory_sha256": "733d01484494e05780ae132c26466721ea3f7c74d4c03e47df596495a2162326"
  },
  "writer_health": {
    "unresolved_failures": 0,
    "recovered_failures": 0
  },
  "state_hash": {
    "algorithm": "sha256",
    "value": "b7e66dad9bb0d97818df0ea2d27d7619199bfa332697bca2d459fdb656827fb6"
  },
  "artifacts": [
    {
      "role": "metrics",
      "path": "data/metrics_antistag_on_combat_off_raids_on_seed_1.csv",
      "required": true,
      "bytes": 48211,
      "sha256": "cbf2cdcb88672cc8930298f51344ca5d1214627fe7d5fc83552e51bc03584dfb"
    }
  ],
  "recovered_after_runner_crash": false
}
```

Requirements:

- All artifact paths are relative to the attempt directory and cannot escape it.
- Artifact hashes are computed by streaming reads after all writers close.
- `outcome_status: completed` requires `validation.status: valid`.
- Failed/timed-out/cancelled attempts may have incomplete artifact inventories and no state hash.
- Initial validation is frozen in the manifest. Later validator reassessments are new `validation_assessed` ledger events and never mutate the manifest.

## 7. Ledger examples

### Failed timeout attempt

```json
{
  "ledger_schema_version": 1,
  "sequence": 12,
  "event_id": "evt_9dcf0c2bc83d4693a825d0367a579f3c",
  "event_type": "attempt_finished",
  "recorded_at_utc": "2026-07-10T16:00:00.000Z",
  "experiment_id": "core-replication-v2-smoke-s0",
  "cell_id": "cell_37058a46eb0928517055700a",
  "attempt_id": "att_31f8471c878446d28eb89ac8e483b147",
  "payload": {
    "outcome_status": "timed_out",
    "reason": "wall_clock_limit",
    "attempt_manifest_sha256": "9da6629ae602de72142b0fe695663a439ac602af8c2aab21595bc1e2a022a087",
    "eligible_for_selection": false
  },
  "writer": {
    "runner_schema_version": 2,
    "runner_version": "2.0.0"
  },
  "previous_record_sha256": "fc542cf9540e5eadc8240b8e6ddaa2e4532797b6d244ef70d9ab2066b623e46d",
  "record_sha256": "d021cc0f8ca2e9c933236fe800109f641928f5dc40fb77e1a483589370ad2b80"
}
```

### Initial authoritative selection

```json
{
  "ledger_schema_version": 1,
  "sequence": 18,
  "event_id": "evt_0d70c5d0e05e482d846f424109c2d19b",
  "event_type": "attempt_selected",
  "recorded_at_utc": "2026-07-10T16:12:10.000Z",
  "experiment_id": "core-replication-v2-smoke-s0",
  "cell_id": "cell_37058a46eb0928517055700a",
  "attempt_id": "att_8a86bb0c767849a68e199406834e4d24",
  "payload": {
    "selection_reason": "first_valid_completed_attempt",
    "attempt_manifest_sha256": "8cc05cf32ee3fbfc73e29468e05921a36a5ab46e2fb23a2a2a738b672c02be8e",
    "validator_schema_version": 2
  },
  "writer": {
    "runner_schema_version": 2,
    "runner_version": "2.0.0"
  },
  "previous_record_sha256": "5f2fd375477cb08806cec16fa20fd66305ec93adbab9297d9279cab0c6da0183",
  "record_sha256": "19578cc9d4bfda0f7eec1bfceee947662df52f3fdf428117a5c4f9ccbfd4bc93"
}
```

### Atomic selection replacement and supersession

```json
{
  "ledger_schema_version": 1,
  "sequence": 24,
  "event_id": "evt_b407646b151643f79643fb1ff66d1243",
  "event_type": "selection_replaced",
  "recorded_at_utc": "2026-07-10T17:20:00.000Z",
  "experiment_id": "core-replication-v2-smoke-s0",
  "cell_id": "cell_37058a46eb0928517055700a",
  "attempt_id": "att_a44c361fb2f047bdb6875b585aabbe38",
  "payload": {
    "superseded_attempt_id": "att_8a86bb0c767849a68e199406834e4d24",
    "selected_attempt_id": "att_a44c361fb2f047bdb6875b585aabbe38",
    "reason": "approved_replacement_after_prior_selection_revoked",
    "new_attempt_manifest_sha256": "5e576a05e16293b58165ebbb79005d1c2e42937093633666a68d975d852c932e",
    "validator_schema_version": 2
  },
  "writer": {
    "runner_schema_version": 2,
    "runner_version": "2.0.0"
  },
  "previous_record_sha256": "5644ef0c321c065bc961a4104c2bd8c7eeb61c40af0c7414c49d44afe57e26df",
  "record_sha256": "4b7ad8c043728b9000f03c3464c9e67173fc89e99f0f971d38d3350905a0d6f"
}
```

One `selection_replaced` record changes both projected selection states atomically: the old attempt becomes superseded and the new attempt becomes selected.

## 8. Selection and validation rules

Validation selects an authoritative attempt through these exact rules:

1. Replay and verify the complete ledger hash chain.
2. Load the immutable experiment and cell contracts and verify their hashes.
3. Enumerate attempts only from ledger events; unregistered directories are orphan evidence, not attempts eligible for selection.
4. Verify the attempt manifest hash named by `attempt_finished`.
5. Run deep streaming validation against the frozen cell, plan, code, tag, environment, and output contract.
6. Require terminal outcome `completed`, accepted termination, and no unresolved writer failure.
7. Append `validation_assessed` with the validator version and result.
8. If the cell has no selected attempt, append `attempt_selected` for the first valid completed attempt.
9. If a selected attempt already exists, do not auto-replace it. Resume skips the cell after revalidation.
10. Replacement requires an explicit operator-authorized action and one atomic `selection_replaced` record naming old and new attempt IDs and the reason.

`selected_attempts.json` and `run_index.csv` contain one row per research cell, not one row per attempt. They are rebuilt from the ledger. `attempt_index.csv` lists every attempt with `research_replicate: true` only for the currently selected research attempt; all others are false.

## 9. Resume rules

Resume is fail-closed and makes no filesystem mutation until all preflight checks pass.

1. Acquire the exclusive experiment lock.
2. Verify experiment ID, exact plan bytes/hash, expected commit/tag, clean tree, runner schema, and stable environment fingerprint.
3. Verify the ledger filename sequence, canonical hashes, and hash chain.
4. Verify all immutable experiment/cell/intent/terminal manifest hashes referenced by the ledger.
5. Recover incomplete attempts according to §12; never continue a simulator in an existing attempt directory.
6. Revalidate the selected attempt for every cell with the current approved validator.
7. If a selected attempt remains valid, skip that cell without rewriting its timing, status, or manifest.
8. If no selected attempt exists, allocate a new attempt only when explicit resume execution is requested.
9. If a selected attempt fails revalidation, abort. An explicit audit/repair operation must append `selection_revoked` before a replacement attempt can run.
10. Stop on the first new noncompleted attempt and record `batch_stopped`.

Resume refuses, without mutation:

- a nonempty root lacking a valid V2 experiment identity;
- plan, contract, seed, tick, timeout, commit, tag, or environment mismatch;
- an invalid ledger chain or sequence gap;
- a selected attempt whose manifest or artifacts changed;
- unknown schema versions; or
- concurrent runner ownership.

## 10. Supersession rules

- Only a currently selected, validated `completed` attempt can become superseded.
- Only a later, deeply validated `completed` attempt for the exact same cell can replace it.
- Invalid, failed, timed-out, and cancelled attempts are preserved as nonselected failure evidence; they are not relabeled superseded.
- A failed replacement never changes the existing selection.
- A selected attempt that later fails a newer validator is first revoked with `selection_revoked`; the cell then has no authoritative attempt.
- Replacement is never inferred from directory age, attempt ID, modification time, or “latest” naming.
- Selection replacement requires an operator reason and records both manifest hashes and validator version.
- Supersession changes only the ledger projection. No attempt manifest or artifact is edited.

## 11. Preserving failure evidence without creating replicates

All attempts remain available in `attempt_index.csv` and their immutable directories. Analysis uses two distinct views:

- **Research view:** exactly one selected, validated attempt per research cell.
- **Attempt/audit view:** every allocated/running/completed/invalid/failed/timed-out/cancelled/superseded attempt.

Rules for analysis:

- Biological/state endpoints come only from selected completed attempts.
- Timed-out and cancelled attempts may be reported as censored computational-tractability evidence, never as completed biological observations.
- Failed and invalid artifacts support diagnosis but contribute no endpoint values.
- Superseded attempts remain visible but have `research_replicate: false`.
- Same-seed retries, diagnostic probes, and different attempts never increase the replicate count.
- An unresolved cell remains explicitly unresolved; it is not silently dropped from matrix denominators.

## 12. Atomic writes and crash recovery

### Atomic-write strategy

For immutable JSON documents and ledger records:

1. hold the experiment lock when allocating IDs or appending ledger state;
2. write canonical UTF-8 JSON to a unique temporary file in the target directory;
3. flush and `fsync` the file;
4. use `os.replace()` to publish the final path;
5. `fsync` the containing directory; and
6. refuse to replace an existing immutable target.

For derived views, write/fsync/replace is allowed because they are rebuildable. CSV artifacts are written only inside the active attempt; after writers close, the runner hashes them and atomically commits `attempt_manifest.json`, sealing the directory.

The ledger uses one atomic file per record. There is no partially appended authoritative JSONL line. A generated JSONL export may exist under `views/`, but it is nonauthoritative.

### Crash recovery

After acquiring the exclusive lock, recovery performs these cases in order:

| Observed state | Recovery action |
|---|---|
| Intent exists, no `attempt_started` | Append `attempt_recovered` as abandoned-before-start; seal as `failed`; never launch in place |
| `attempt_started`, no terminal manifest | Inspect read-only artifacts, seal as `failed` with reason `runner_crash`, append recovery/finish records, then require a new attempt |
| Terminal manifest exists, no `attempt_finished` ledger record | Verify manifest and intent hashes; append `attempt_recovered` and matching `attempt_finished` |
| Ledger says finished but terminal manifest is absent or hash differs | Fatal integrity error; abort without selection or automatic repair |
| Temporary files remain after atomic write | Record orphan-temporary-file finding; ignore for state projection; do not delete without explicit cleanup |
| Ledger gap, duplicate sequence, or broken hash chain | Fatal integrity error; abort without mutation |
| Derived views are missing/corrupt | Rebuild atomically from the verified ledger |
| Selected attempt fails artifact revalidation | Append nothing automatically; abort and require explicit selection revocation/audit |

Recovery never resumes a simulation process from partial state and never writes into an existing sealed attempt.

## 13. V1 compatibility and migration

V1 artifacts are immutable historical evidence and are never moved, renamed, rewritten, or given an in-place V2 ledger.

Layout detection:

- A root with valid V2 `experiment.json`, plan snapshot, and ledger uses V2 rules.
- A root without those markers is handled by the existing legacy-layout adapter.
- Mixed V1/V2 structures in one experiment root are rejected.

The read-only V1 adapter projects each legacy condition/seed directory as one virtual attempt in memory:

```text
legacy_<first 24 hex of SHA-256(relative path + artifact inventory)>
```

Compatibility status mapping:

| V1 term | V2 projected outcome |
|---|---|
| `completed` | `completed` only if the legacy validator accepts it |
| `invalid_output` | `invalid` |
| `exception` | `failed` |
| `wall_clock_limit` | `timed_out` |
| `cancelled` | `cancelled` |
| `superseded` | selection state `superseded`, when supported by existing explicit evidence |

The adapter does not improve V1 provenance or combine V1 with V2. If a portable migration index is ever needed, it must be created outside the V1 root, reference original paths/checksums, use a new migration ID, and remain clearly labeled as a compatibility view rather than new evidence.

## 14. Required tests

### Identity and layout

- `test_cell_id_is_stable_for_canonical_contract`
- `test_cell_id_changes_when_plan_or_contract_changes`
- `test_attempt_id_is_unique_and_path_safe`
- `test_attempt_paths_cannot_escape_experiment_root`
- `test_sealed_attempt_is_never_modified`
- `test_v2_overwrite_is_rejected`

### Ledger integrity

- `test_ledger_append_preserves_prior_record_bytes`
- `test_ledger_sequence_and_hash_chain_validate`
- `test_ledger_rejects_gap_duplicate_or_broken_hash`
- `test_two_selected_attempts_for_one_cell_are_rejected`
- `test_selection_replaced_atomically_supersedes_old_and_selects_new`
- `test_malformed_or_orphan_record_is_not_silently_adopted`

### Attempt outcomes and manifests

- `test_completed_attempt_requires_deep_valid_artifacts`
- `test_invalid_attempt_is_never_selection_eligible`
- `test_failed_timed_out_and_cancelled_outcomes_remain_distinct`
- `test_attempt_manifest_seals_relative_artifact_hashes`
- `test_later_validation_is_appended_not_manifest_mutation`
- `test_unresolved_writer_failure_prevents_completed_outcome`

### Resume and supersession

- `test_resume_skips_only_selected_revalidated_attempt`
- `test_resume_refuses_plan_commit_tag_or_environment_mismatch`
- `test_resume_allocates_new_attempt_for_unresolved_cell`
- `test_failed_replacement_does_not_change_selection`
- `test_valid_replacement_preserves_and_supersedes_prior_selection`
- `test_same_seed_attempts_count_as_one_replicate`
- `test_selection_revocation_leaves_cell_unresolved`

### Atomicity and crash recovery

- `test_ledger_record_publish_is_atomic`
- `test_crash_after_intent_before_start_recovers_failed_attempt`
- `test_crash_after_start_never_resumes_attempt_in_place`
- `test_terminal_manifest_without_finish_event_is_recovered`
- `test_finish_event_without_manifest_is_fatal_integrity_error`
- `test_corrupt_derived_views_rebuild_from_ledger`
- `test_concurrent_runner_lock_prevents_second_writer`

### Compatibility

- `test_v1_layout_is_detected_without_mutation`
- `test_v1_statuses_map_to_v2_compatibility_terms`
- `test_v1_and_v2_attempts_are_never_pooled`
- `test_mixed_layout_is_rejected`

All tests should use synthetic artifacts, temporary directories, mocked subprocess outcomes, and temporary Git repositories. No research-scale simulation is required to validate this model.

## 15. Acceptance criteria

The design is implemented correctly only when:

- every execution has one immutable intent and at most one immutable terminal manifest;
- every ledger record is atomic, ordered, hash-chained, and append-only;
- every cell has zero or one selected attempt;
- only a deeply valid completed attempt can be selected;
- replacement atomically supersedes the old selection without changing either attempt's artifacts;
- failures remain visible but never increase replicate counts;
- resume cannot mix plan/code/tag/environment/condition identities or reuse partial attempts;
- crash recovery never guesses completion or resumes in place;
- derived views can be deleted and rebuilt without losing evidence; and
- V1 artifacts remain untouched, separate, and explicitly legacy-limited.
