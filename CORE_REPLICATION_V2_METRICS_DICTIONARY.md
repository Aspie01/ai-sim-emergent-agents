# Core Replication V2 Metrics Dictionary

**Status:** Proposed canonical V2 schema  
**Scope:** Selected run-level research records and attempt-level audit records  
**Evidence policy:** Only a selected, deeply validated attempt contributes biological or completed-run computational endpoints  
**Non-authorization:** This dictionary does not authorize a V2 run.

## 1. Conventions

### Canonical timing

V2 defines an **end-of-tick snapshot** as the state after every enabled simulation and anti-stagnation layer for that tick has completed. `final_*` fields use the last fully completed end-of-tick snapshot. `peak_*` and population-cap fields are calculated over all fully completed end-of-tick snapshots from tick 1 through `final_tick`.

This is stricter than the current implementation, where the per-tick metrics row is written before some post-metrics anti-stagnation and housekeeping behavior. Before V2 evidence collection, metrics timing and the terminal summary must be aligned or a separate authoritative end-of-tick snapshot must be added. A run is invalid if its terminal summary and authoritative final snapshot disagree.

### Missing values

- JSON uses `null`; CSV exports use an empty field.
- Strings such as `NA`, `N/A`, `none`, `unknown`, and numeric sentinels such as `-1` are forbidden.
- Zero is a valid measured value for counts and must never mean missing.
- Attempt-level endpoints may be null for `failed`, `timed_out`, `cancelled`, or `invalid` attempts.
- Selected `completed` attempts may contain null only where this dictionary explicitly permits structural missingness.

### Roles

- **Primary:** Prespecified principal biological or computational endpoint.
- **Secondary:** Prespecified supporting outcome.
- **Exploratory:** Mechanistic or newly instrumented quantity not used as a primary claim.
- **Provenance:** Identity, completion, configuration, or audit information.
- **Manipulation check:** Confirms whether an enabled mechanism was actually exercised.

`final_population` and `elapsed_seconds` are designated primary V2 fields here. That designation must still be repeated in the reviewed experiment/analysis plan before execution; this dictionary alone is not a preregistration.

### Authoritative artifacts

| Artifact | Authority |
|---|---|
| Frozen `cell.json` / plan snapshot | Requested assignment and condition controls |
| Per-tick metrics CSV | End-of-tick population, factions, cap exposure, and cumulative counts |
| Structured event CSV | Typed event counts such as raids, wars, births, and deaths |
| Simulator run manifest | Final state hash and effective simulation configuration |
| Runner `attempt_manifest.json` | Termination, timing, artifact inventory, validation, code, tag, environment, and writer health |
| Append-only attempt ledger | Attempt lifecycle, selected/final attempt, and supersession |
| `run_index.csv` | Rebuildable selected-attempt view only; never authoritative over the artifacts above |

## 2. Canonical-name migration map

| Canonical V2 name | Current/legacy aliases |
|---|---|
| `final_factions` | `final_faction_count` |
| `peak_factions` | `peak_faction_count` |
| `births` | `total_births` |
| `deaths` | `total_deaths` |
| `wars` | `total_wars`, `total_wars_declared` |
| `raid_events` | `event_raid`, `raid_event_count` |
| `structured_events` | `event_count`, `structured_event_count` |
| `peak_memory_bytes` | `peak_ram_mb` (legacy value is MiB from `tracemalloc`, not RAM/RSS) |
| `state_hash` | `final_state_hash` |
| `validation_result` | `validation_result`, shallow legacy `status`/`ok` combinations |

V2 writers emit only the canonical names. Compatibility readers may map aliases but must retain the original schema/version and never rewrite historical CSVs.

## 3. Design and termination fields

### `requested_ticks`

- **Type / units:** Integer; ticks.
- **Source artifact:** Frozen cell contract, copied into `attempt_manifest.json`.
- **Measurement timing:** Before attempt allocation; immutable for the experiment cell.
- **Role:** Provenance.
- **Valid missing values:** None for any allocated attempt.
- **Validation rule:** Integer ≥ 1; exactly equals plan, cell, command, simulator configuration, and attempt manifest. A timeout change requires a new experiment plan but does not change this field.
- **Interpretation warning:** Requested ticks are an intended horizon, not evidence that they were completed.
- **Current availability:** Present as `configuration.ticks`; V2 must promote it to a top-level authoritative attempt field.

### `final_tick`

- **Type / units:** Integer; one-based tick index.
- **Source artifact:** Termination-aware simulator manifest, confirmed by the last authoritative end-of-tick metrics row and attempt manifest.
- **Measurement timing:** At termination; last fully completed tick.
- **Role:** Provenance.
- **Valid missing values:** `null` only when no tick completed or termination occurred before authoritative tick tracking initialized; otherwise 0 represents no completed ticks only in attempt-level audit data.
- **Validation rule:** `0 <= final_tick <= requested_ticks`; equals the maximum contiguous metrics tick. For `requested_ticks_reached`, it must equal `requested_ticks`; for authorized extinction it may be lower.
- **Interpretation warning:** It is not the tick that merely started or raised an exception.
- **Current availability:** Derived by analysis from the last metrics row; absent from the current run manifest.

### `completed_ticks`

- **Type / units:** Integer; count of fully completed ticks.
- **Source artifact:** Deep validator count of contiguous authoritative end-of-tick metrics rows.
- **Measurement timing:** During post-attempt validation.
- **Role:** Provenance and computational denominator.
- **Valid missing values:** None after validation assessment; 0 is valid.
- **Validation rule:** Integer in `[0, requested_ticks]`; with current from-scratch runs it must equal `final_tick`. Future checkpoint/resume schemas may differ only after a schema-versioned definition change.
- **Interpretation warning:** Tick rows are repeated observations within one run, not independent replicates.
- **Current availability:** Derivable but not emitted canonically.

### `termination_reason`

- **Type / units:** Closed-vocabulary string; unitless.
- **Source artifact:** Simulator termination manifest for graceful exits; runner attempt manifest/ledger for timeout, cancellation, or runner failure.
- **Measurement timing:** At process/attempt termination.
- **Role:** Provenance.
- **Valid missing values:** `null` only for `allocated` or currently `running` attempts.
- **Validation rule:** One of `requested_ticks_reached`, `extinction`, `wall_clock_limit`, `user_cancelled`, `exception`, `runner_error`, `runner_crash`, or `invalid_output`. Must be consistent with process return code and result status.
- **Interpretation warning:** Termination reason describes why execution stopped, not whether its artifacts passed validation. A process can reach requested ticks and still be `invalid`.
- **Current availability:** Not emitted authoritatively; existing runner terms are inferred from return code/timeout.

### `result_status`

- **Type / units:** Closed-vocabulary string; unitless.
- **Source artifact:** Attempt manifest plus append-only ledger selection projection.
- **Measurement timing:** Terminal outcome at finalization; selection status may later project `superseded` without mutating the attempt.
- **Role:** Provenance.
- **Valid missing values:** None in a terminal attempt record. Allocated/running attempts use their lifecycle state rather than null.
- **Validation rule:** One of `completed`, `invalid`, `failed`, `timed_out`, `cancelled`, or `superseded`. Only deeply valid completed attempts can be selected. `superseded` preserves the original completed outcome in the immutable attempt manifest.
- **Interpretation warning:** Failed/timed-out/cancelled attempts remain tractability evidence but provide no completed biological endpoint.
- **Current availability:** Legacy terms are `completed`, `invalid_output`, `exception`, `wall_clock_limit`, `cancelled`, and `superseded`; V2 normalizes them.

## 4. Population and faction fields

### `final_population`

- **Type / units:** Integer; living inhabitants.
- **Source artifact:** Final authoritative end-of-tick metrics row and terminal run summary.
- **Measurement timing:** End of `final_tick` after all enabled layers.
- **Role:** Primary biological endpoint.
- **Valid missing values:** `null` for nonselected/noncompleted attempts; 0 is valid extinction.
- **Validation rule:** Integer in `[0, population_cap]`; terminal summary and final metrics row must agree exactly.
- **Interpretation warning:** A terminal snapshot is not persistence, time-integrated viability, or intrinsic viability; anti-stagnation can directly add/rescue inhabitants.
- **Current availability:** Current summary and analysis field; current metrics timing must be aligned for V2.

### `peak_population`

- **Type / units:** Integer; living inhabitants.
- **Source artifact:** Maximum `population` across authoritative end-of-tick metrics rows.
- **Measurement timing:** Derived after completion over ticks 1 through `final_tick`.
- **Role:** Secondary biological endpoint.
- **Valid missing values:** `null` when `completed_ticks == 0` or attempt is not eligible for research analysis.
- **Validation rule:** Integer in `[final_population, population_cap]`; equals streamed maximum, not only the run-summary cache.
- **Interpretation warning:** End-of-tick peak can miss transient within-tick population changes; the timing convention must remain fixed across conditions.
- **Current availability:** Emitted by run summary from current pre-post-layer sampling; V2 must use aligned end-of-tick sampling.

### `final_factions`

- **Type / units:** Integer; active factions with at least one living member.
- **Source artifact:** Final authoritative metrics row and terminal summary.
- **Measurement timing:** End of `final_tick`.
- **Role:** Secondary outcome.
- **Valid missing values:** `null` for nonselected/noncompleted attempts; 0 is valid.
- **Validation rule:** Integer ≥ 0, exactly matches both sources, and must not exceed `final_population` under the one-membership model.
- **Interpretation warning:** Counts active factions, not all historically formed factions, settlements, or ideological groups.
- **Current availability:** Current alias `final_faction_count`.

### `peak_factions`

- **Type / units:** Integer; active factions.
- **Source artifact:** Maximum `faction_count` over authoritative end-of-tick metrics rows.
- **Measurement timing:** Derived after completion.
- **Role:** Secondary outcome and computational-scaling context.
- **Valid missing values:** `null` when no tick completed or attempt is not eligible; 0 is valid.
- **Validation rule:** Integer ≥ `final_factions`; equals streamed maximum.
- **Interpretation warning:** High faction count increases pairwise opportunity/work but is not itself cultural diversity or social complexity.
- **Current availability:** Current alias `peak_faction_count`.

### `first_population_cap_tick`

- **Type / units:** Nullable integer; one-based tick index.
- **Source artifact:** First authoritative metrics row where `population >= population_cap`.
- **Measurement timing:** Derived after completion.
- **Role:** Secondary cap-censoring outcome.
- **Valid missing values:** `null` means the cap was never reached; 0 is forbidden.
- **Validation rule:** If non-null, within `[1, final_tick]`, final/peak metrics must contain at least one cap row, and it equals the first such row.
- **Interpretation warning:** Cap contact indicates censored high growth, not equilibrium or unbounded growth.
- **Current availability:** Derivable from metrics but not currently summarized.

### `ticks_at_population_cap`

- **Type / units:** Integer; completed ticks.
- **Source artifact:** Count of authoritative metrics rows with `population >= population_cap`.
- **Measurement timing:** Derived after completion.
- **Role:** Secondary cap-censoring outcome.
- **Valid missing values:** None after validation; 0 is valid.
- **Validation rule:** Integer in `[0, completed_ticks]`; must be 0 exactly when `first_population_cap_tick` is null.
- **Interpretation warning:** Counts sampled end-of-tick cap exposure, not time spent at cap within a tick.
- **Current availability:** Planned derived field.

### `proportion_at_population_cap`

- **Type / units:** Nullable float; proportion in `[0, 1]`.
- **Source artifact:** Derived as `ticks_at_population_cap / completed_ticks`.
- **Measurement timing:** After validation.
- **Role:** Secondary cap-censoring outcome.
- **Valid missing values:** `null` only when `completed_ticks == 0`; otherwise 0.0 is valid.
- **Validation rule:** Formula must match within `1e-12`; value in `[0, 1]`.
- **Interpretation warning:** This is exposure under an imposed cap, not the unconstrained growth rate.
- **Current availability:** Planned derived field.

## 5. Demographic and hostile-mechanism fields

### `births`

- **Type / units:** Integer; recorded birth events.
- **Source artifact:** Count of typed `birth` rows, cross-checked with final cumulative metrics/summary.
- **Measurement timing:** Cumulative through `final_tick`.
- **Role:** Secondary demographic outcome.
- **Valid missing values:** `null` for nonvalidated attempts; 0 is valid.
- **Validation rule:** Nonnegative integer; typed-event count, final cumulative metric, and summary must agree.
- **Interpretation warning:** Population accounting also includes starting inhabitants, anti-stagnation traveler immigration, and deaths; births alone cannot reconstruct population change.
- **Current availability:** Current alias `total_births`.

### `deaths`

- **Type / units:** Integer; recorded death events.
- **Source artifact:** Count of typed `death` rows, cross-checked with final cumulative metrics/summary.
- **Measurement timing:** Cumulative through `final_tick`.
- **Role:** Secondary demographic outcome.
- **Valid missing values:** `null` for nonvalidated attempts; 0 is valid.
- **Validation rule:** Nonnegative integer; all authoritative sources agree.
- **Interpretation warning:** Aggregate deaths do not distinguish hunger, age/health, combat, or anti-stagnation singleton mortality; cause-specific claims require typed cause fields.
- **Current availability:** Current alias `total_deaths`.

### `wars`

- **Type / units:** Integer; formal war declarations.
- **Source artifact:** Count of typed `war_declared` event rows, cross-checked with final `total_wars_declared`/summary.
- **Measurement timing:** Cumulative through `final_tick`.
- **Role:** Secondary outcome and formal-combat manipulation check.
- **Valid missing values:** `null` for nonvalidated attempts; 0 is valid even when formal combat is enabled.
- **Validation rule:** Nonnegative integer; event and cumulative counts agree; must be 0 when the formal-combat layer is disabled.
- **Interpretation warning:** Counts declarations, not concurrent wars, war duration, battle intensity, or casualties. Zero in a combat-enabled run means the mechanism was available but not activated.
- **Current availability:** Current aliases `total_wars` and `total_wars_declared`.

### `battle_activations`

- **Type / units:** Integer; war-tick combat-resolution activations.
- **Source artifact:** Planned typed `battle_activated` instrumentation or an equivalent deterministic combat counter.
- **Measurement timing:** Increment once for each active formal war processed by combat resolution on a tick; cumulative through `final_tick`.
- **Role:** Manipulation check and exploratory workload measure.
- **Valid missing values:** `null` only for legacy/uninstrumented schemas; 0 is valid.
- **Validation rule:** Nonnegative integer; equals typed activation rows/counter; must be 0 when formal combat is disabled; may exceed `wars` because one war can activate across many ticks.
- **Interpretation warning:** This is not unique battles, deaths, victories, or computational time spent in combat.
- **Current availability:** Not currently emitted; requires behavior-neutral instrumentation before V2 tagging.

### `raid_events`

- **Type / units:** Integer; successful typed raid events.
- **Source artifact:** Count of `event_type == "raid"` rows in the structured event CSV.
- **Measurement timing:** Cumulative through `final_tick`.
- **Role:** Secondary outcome and raid manipulation check.
- **Valid missing values:** `null` for nonvalidated attempts; 0 is valid.
- **Validation rule:** Nonnegative integer; equals event-type count; must be 0 when raids are disabled.
- **Interpretation warning:** Counts successful resource-transferring emitted raids, not eligible faction pairs, random attempts, failed/no-loot attempts, or pair-scan work.
- **Current availability:** Current aliases `event_raid` and `raid_event_count`.

### `raid_rate`

- **Type / units:** Nullable float; successful raids per 1,000 active faction-pair-ticks.
- **Source artifact:** `raid_events` plus per-tick active `faction_count` from the metrics CSV.
- **Measurement timing:** Derived after completion using all authoritative ticks.
- **Role:** Exploratory mechanism-normalized outcome and manipulation check.
- **Valid missing values:** `null` when total active faction-pair exposure is zero or the required time series is unavailable; 0.0 is valid when exposure exists and no raid succeeds.
- **Validation rule:** Let `pair_ticks = sum_t(faction_count_t * (faction_count_t - 1) / 2)`. Require `raid_rate = 1000 * raid_events / pair_ticks` within `1e-12`; if `pair_ticks == 0`, raid events must be 0 and rate null.
- **Interpretation warning:** Normalizes by all active faction pairs, not tension-eligible pairs; it is not the 20% attempt probability or a causal raid propensity.
- **Current availability:** Current reports expose raw raid share and count, not this canonical exposure-normalized rate.

## 6. Computational fields

### `structured_events`

- **Type / units:** Integer; structured event rows excluding the header.
- **Source artifact:** Streamed row count of the structured event CSV.
- **Measurement timing:** After writers close and before attempt sealing.
- **Role:** Secondary computational/output outcome.
- **Valid missing values:** `null` for unreadable/unvalidated attempts; 0 is valid.
- **Validation rule:** Nonnegative integer; every row has the expected schema/seed and tick in `[1, final_tick]`; equals sum of event-type counts.
- **Interpretation warning:** Depends on schema and instrumentation. Events are repeated within-run observations, not replicates or direct measures of complexity.
- **Current availability:** Current aliases `event_count` and `structured_event_count`.

### `elapsed_seconds`

- **Type / units:** Float; seconds.
- **Source artifact:** Runner attempt timing using `time.perf_counter()` around child launch-to-exit/timeout; recorded in attempt manifest.
- **Measurement timing:** Starts immediately before subprocess launch and ends when the child exits or timeout handling completes; excludes queue wait, deep validation, artifact hashing, and later analysis.
- **Role:** Primary computational endpoint.
- **Valid missing values:** `null` only when an allocated attempt never launched or the monotonic clock failed; otherwise a nonnegative value is required for every terminal attempt.
- **Validation rule:** Finite float ≥ 0; terminal attempts that launched must have a value; timing endpoints and exclusions recorded by schema.
- **Interpretation warning:** Hardware, system load, execution order, Python/environment, state size, and metrics-only I/O all affect it. Timed-out attempts are right-censored tractability evidence.
- **Current availability:** Runner and summary timings both exist; V2 makes runner monotonic timing canonical.

### `seconds_per_completed_tick`

- **Type / units:** Nullable float; seconds per completed tick.
- **Source artifact:** Derived from `elapsed_seconds / completed_ticks`.
- **Measurement timing:** After validation.
- **Role:** Secondary computational endpoint.
- **Valid missing values:** `null` when elapsed is missing or `completed_ticks == 0`.
- **Validation rule:** Exact formula within `1e-12`; finite and nonnegative.
- **Interpretation warning:** Arithmetic averaging hides nonlinear within-run slowdown and includes fixed process startup/finalization overhead.
- **Current availability:** Similar current alias `ticks_per_second` uses the reciprocal and often requested rather than completed ticks; V2 standardizes the completed-tick denominator.

### `output_bytes`

- **Type / units:** Integer; bytes.
- **Source artifact:** Sum of sealed output artifacts listed in `attempt_manifest.json`.
- **Measurement timing:** After all writers close, before terminal attempt manifest publication.
- **Role:** Secondary computational/storage endpoint.
- **Valid missing values:** `null` when an attempt cannot be inventoried; 0 is invalid for a completed attempt.
- **Validation rule:** Nonnegative integer equal to the sum of listed artifact byte sizes. Excludes `intent.json`, `attempt_manifest.json`, ledger records, and derived views; includes required structured outputs and any runner stdout/stderr captured for that attempt.
- **Interpretation warning:** Depends on output policy, event schema, compression policy, and failure diagnostics; it is not disk allocation size.
- **Current availability:** Current analysis/pilot field, but directory-sum boundaries vary; V2 freezes the inventory definition.

### `peak_memory_bytes`

- **Type / units:** Nullable integer; bytes.
- **Source artifact:** Metrics/run summary plus a required `memory_measurement_method` provenance field.
- **Measurement timing:** Peak over child simulation execution.
- **Role:** Secondary computational endpoint.
- **Valid missing values:** `null` only when instrumentation is unavailable or failed and the plan permits it; 0 must not stand for missing.
- **Validation rule:** Integer ≥ 0; convert legacy MiB using `round(value * 1024 * 1024)` only in compatibility readers; measurement method must be nonempty and stable across compared runs.
- **Interpretation warning:** Current `tracemalloc` measures traced Python allocations, not total process RSS, shared memory, GPU memory, or system peak RAM. Cross-method comparisons are invalid.
- **Current availability:** Current `peak_ram_mb` is actually `tracemalloc` peak MiB and must be relabeled on migration.

## 7. Reproducibility and assignment fields

### `state_hash`

- **Type / units:** Nullable lowercase hexadecimal string; SHA-256 digest.
- **Source artifact:** Simulator run manifest, copied and checked in the attempt manifest.
- **Measurement timing:** At terminal state finalization after the last fully completed tick.
- **Role:** Provenance and deterministic-reproducibility check.
- **Valid missing values:** `null` for attempts without a trustworthy final state; none for selected completed attempts.
- **Validation rule:** Exactly 64 lowercase hexadecimal characters; algorithm recorded as SHA-256; copied values agree; diagnostic identical seed/config/code runs must match.
- **Interpretation warning:** A matching hash is not semantic proof, artifact identity, or cross-configuration comparability. Different behaviorally relevant controls intentionally change the hash payload.
- **Current availability:** Current run manifest field; current reports also use `final_state_hash`.

### `condition_controls`

- **Type / units:** JSON object; unitless.
- **Source artifact:** Frozen cell contract, effective simulator configuration, and attempt manifest.
- **Measurement timing:** Frozen before launch and rechecked after termination.
- **Role:** Provenance and manipulation assignment.
- **Valid missing values:** None for allocated V2 attempts.
- **Canonical value:** Must contain at least `anti_stagnation_enabled` (bool), `combat_enabled` (bool), `raids_enabled` (bool), canonical sorted `disabled_layers` (array of strings), `log_mode` (must be `metrics_only` for V2 research), `population_cap` (int), and `starting_population` (int).
- **Validation rule:** Exact canonical equality across plan/cell/command-derived expectation/simulator manifest/attempt manifest. `combat_enabled` must equal `"combat" not in disabled_layers`; `raids_enabled` must equal `"raids" not in disabled_layers`.
- **Interpretation warning:** Enabled means available, not necessarily activated. Combat-enabled runs may have zero wars; raids-enabled runs may have zero successful raids. Disabling both does not make the simulation hostility-free.
- **Current availability:** Partially present in `configuration`; `combat_enabled` is currently derived rather than explicit.

### `code_commit`

- **Type / units:** Lowercase hexadecimal Git object ID string; unitless.
- **Source artifact:** Clean-tag preflight, experiment identity, attempt manifest.
- **Measurement timing:** Immediately before attempt allocation and rechecked before launch/resume.
- **Role:** Provenance.
- **Valid missing values:** None for V2; legacy/unknown attempts use null and cannot be archival-grade.
- **Validation rule:** Full object ID (currently 40 hex; accept repository-native full length), equals expected plan commit and `HEAD`, and remains unchanged through attempt sealing.
- **Interpretation warning:** Commit identity does not capture uncommitted files, environment, external services, or mutable tags by itself.
- **Current availability:** Current aliases `code_commit` and `code.commit`.

### `code_tag`

- **Type / units:** String; annotated Git tag name.
- **Source artifact:** Preflight and attempt manifest.
- **Measurement timing:** Before attempt allocation/resume.
- **Role:** Provenance.
- **Valid missing values:** None for V2; null allowed only for explicitly legacy evidence.
- **Validation rule:** Filename-safe configured tag exists as an annotated tag object and resolves to `code_commit`; tag object ID should also be recorded in provenance.
- **Interpretation warning:** The immutable commit/object IDs are the real anchors; a tag name can be force-moved outside the dataset after capture.
- **Current availability:** Not currently recorded.

### `code_dirty`

- **Type / units:** Boolean; unitless.
- **Source artifact:** Parent-repository preflight and attempt manifest.
- **Measurement timing:** Before experiment/root mutation, before every new attempt, and at attempt sealing.
- **Role:** Provenance.
- **Valid missing values:** None for V2; null means provenance lookup failed and is rejection, not “clean.”
- **Validation rule:** Must be `false` at all required checkpoints; Git lookup failure or mismatch invalidates/prevents the attempt.
- **Interpretation warning:** Must use the documented Git status policy, including relevant untracked files and submodule/plugin policy; ignored runtime outputs do not imply source dirtiness.
- **Current availability:** Current aliases `code_dirty` and `code.dirty`; recorded but not enforced.

### `attempt_id`

- **Type / units:** String; immutable attempt identifier.
- **Source artifact:** Attempt intent, manifest, directory, and ledger.
- **Measurement timing:** Allocated before process launch.
- **Role:** Provenance.
- **Valid missing values:** None in attempt-level records; null is allowed in a cell-level selected view only when the cell has no authoritative attempt.
- **Validation rule:** Matches `^att_[0-9a-f]{32}$`; globally unique within the experiment store; identical across all attempt records and paths.
- **Interpretation warning:** Attempt IDs identify executions, not replicate numbers, chronology, quality, or selection.
- **Current availability:** Not currently implemented.

### `validation_result`

- **Type / units:** Closed-vocabulary string; unitless.
- **Source artifact:** Deep validator result in attempt manifest and later append-only validation ledger events.
- **Measurement timing:** After writers close; may be reassessed by a newer approved validator without mutating the attempt manifest.
- **Role:** Provenance and evidence-eligibility gate.
- **Valid missing values:** No null. Use `not_assessed` for allocated/running/crash-recovered attempts not yet validated.
- **Validation rule:** One of `valid`, `invalid`, or `not_assessed`; selected attempt must be `valid`; validator schema/version, timestamp, and error list are required.
- **Interpretation warning:** Valid means conformant to a particular validator version and frozen contract; it does not establish scientific truth or publication readiness.
- **Current availability:** Current analyses emit `validation_result`, but the existing validator is shallow; V2 requires deep validation.

## 8. Cross-field validation rules

A selected V2 research row is valid only if all of these hold:

1. `result_status == "completed"` and `validation_result == "valid"`.
2. `attempt_id`, cell, plan, commit, tag, environment, and `condition_controls` match the ledger-selected attempt exactly.
3. `completed_ticks == final_tick` for from-scratch V2 runs.
4. Requested-horizon completion has `final_tick == requested_ticks`; authorized extinction may end earlier with `final_population == 0`.
5. Final/peak population and factions match streamed end-of-tick metrics and terminal summary.
6. `peak_population >= final_population` and `peak_factions >= final_factions`.
7. Birth, death, war, raid, and structured-event counts agree across typed events and cumulative summaries.
8. Raid-disabled and combat-disabled manipulation checks are zero for their respective event/activation fields.
9. Cap fields satisfy their formulas and the frozen `population_cap`.
10. Timing, per-tick rate, output inventory, memory method, and state hash pass their field rules.
11. `code_dirty is false`, tag/commit preflight passes, and no unresolved writer failure exists.
12. Exactly one selected attempt exists for the research cell; all other attempts have `research_replicate: false`.

## 9. Interpretation boundaries

- The seed is the independent replication unit; ticks and events are within-run observations.
- Same-seed conditions are blocks, not matched downstream random shocks after treatments alter RNG consumption.
- Population-cap exposure is censoring of high-growth trajectories.
- Formal combat and raids are separate controls; raids are successful economy-generated coercive events, not formal wars.
- Runtime is end-to-end under one hardware/environment/output policy and must not be attributed solely to emergent simulation complexity.
- Attempt-level failure outcomes must remain visible for tractability analysis, while biological comparisons use selected completed attempts only.
- V1 aliases may be translated for historical analysis, but V1 and V2 remain separate datasets.
