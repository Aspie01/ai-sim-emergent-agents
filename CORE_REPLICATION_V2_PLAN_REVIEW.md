# Core Replication V2 Plan Review

**Review date:** 2026-07-10  
**Plan reviewed:** `CORE_REPLICATION_V2_PLAN.md`  
**Review mode:** Adversarial, multi-reviewer, documentation only  
**Execution status:** No tests, simulations, experiments, or output directories were run or created

## 1. Executive summary

**Overall verdict:** Revise first  
**Final disposition:** **Needs implementation changes before smoke tier**  
**Confidence:** High

The plan has the right scientific backbone: it separates formal combat from economy raids, treats anti-stagnation as a factor, uses shared seeds, keeps V1 and V2 distinct, adopts `metrics_only`, and gates longer horizons. It is not ready to authorize even the smoke tier, however. The name `no_hostility` overstates what the code disables; primary estimands and viability outcomes are not operationalized; the proposed matrix cannot causally decompose historical logging overhead; and the tier ranges do not define exact cells, seeds, or budgets. More seriously, the current runner/verifier cannot enforce several guarantees the plan assumes: it is not fail-fast, validation is too shallow to prove the requested configuration or final tick, interrupted/exception-finalized artifacts can later be resume-skipped as completed, and retry behavior overwrites attempt provenance. The next step should be a plan revision plus bounded runner/verifier hardening—not a simulation run.

### Strong parts to retain

- V1 remains validated historical pilot evidence and is not pooled with V2.
- Formal combat and economy raids remain independent factors.
- `metrics_only`, buffered event writes, shared seeds, and clean tagged provenance are appropriate defaults.
- Smoke → pilot → full staging is the correct general strategy.
- Same-seed reruns and multiple horizons are not treated as independent evidence.
- Full 10,000-tick execution requires separate approval.

### Review method

Five independent specialist reviews were synthesized:

1. Experimental Design Reviewer
2. Runtime and Storage Risk Reviewer
3. Simulation Semantics Reviewer
4. Reproducibility and Provenance Reviewer
5. Skeptical Peer Reviewer

The review inspected the requested plan, reports, runner, raid-pilot runner, configuration, simulation, economy, metrics, and tests. It also inspected the narrowly relevant manifest implementation and runner tests. No raw logs or full experiment directories were opened.

The initial working-tree check was:

```text
?? CORE_REPLICATION_V2_PLAN.md
```

That is acceptable for review, but it means a V2 run now would not satisfy the clean-provenance requirement.

## 2. Top 10 issues

### 1. Blocker — `no_hostility` is not the implemented intervention

**Affected sections:** §3 research question 3; §4 minimal and expanded matrices; §10 comparisons and interpretation.

**Why it matters:** Disabling formal combat and economy raids does not disable rivalry accumulation, diplomatic conflict, scarcity, anti-stagnation conflict incidents, or religion's holy-war state. The label would create a construct-validity error in filenames, manifests, plots, and any paper using it. The code only gates formal combat in `sim.py` and `_faction_raids()` in `economy.py`.

**Recommended fix:**

- Rename `no_hostility` to `combat_off_raids_off` or `antistag_on_combat_off_raids_off`.
- Rename `no_antistag_no_hostility` to `antistag_off_combat_off_raids_off`.
- Rename `no_antistag_no_combat_raids_on` to `antistag_off_combat_off_raids_on`.
- Replace “all hostile coercion” with “both manipulated mechanisms: formal combat and economy raids.”
- Never use bare `no_combat` as a V2 condition identifier.

### 2. Blocker — completion and validation can misclassify interrupted or wrong runs

**Affected sections:** §§5, 7–9, 11–12.

**Why it matters:** `sim.py:2100-2154` catches `KeyboardInterrupt`, then writes a normal state hash, manifest, and summary. The process can exit successfully even though it did not reach the requested tick. Ordinary exceptions also execute finalization before returning nonzero. `validate_run_outputs()` checks nonempty files, seed, condition, and hash length only (`run_experiments.py:109-128`). On resume, any artifact set passing that shallow check is skipped as completed (`run_experiments.py:168-181`). Header-only CSVs can also be nonempty.

**Recommended fix:** Before smoke, require and test:

- `requested_ticks`, `final_tick`, `termination_reason`, `result_status`, and `completed_normally` in the manifest;
- a nonzero/cancelled result for user interruption;
- an explicit valid-natural-terminal rule for extinction;
- deep streaming validation of schemas, row consistency, monotonic ticks, exact summary row, expected final tick or registered natural terminal, and zero unresolved write failures; and
- resume-skipping only for a deeply validated `completed` run.

### 3. Blocker — fail-fast and attempt-safe resume are promised but not implemented

**Affected sections:** §§5, 8, 11, 12.

**Why it matters:** `run_from_plan()` continues to the next cell after a timeout, exception, or invalid output (`run_experiments.py:328-348`). Resume deletes stale summaries, manifests, and error markers in place (`run_experiments.py:183-203`), resets batch results, and can replace original elapsed/status data with a zero-second “skipped” record. `RESULT_SUPERSEDED` exists but is not used. This contradicts the plan's fail-fast and supersession policy and weakens auditability.

**Recommended fix:**

- Add tested stop-on-first-noncompleted behavior, or dispatch smoke as one-cell stages until it exists.
- Use immutable attempt directories and an append-only attempt ledger.
- Select one final validated attempt and mark older attempts `superseded` without deleting them.
- Forbid `--overwrite` for V2.
- Resume only when plan hash, commit/tag, clean provenance, and complete effective configuration match.

### 4. Blocker — primary estimands and viability outcomes are not operationalized

**Affected sections:** §§3, 5, 7, 10.

**Why it matters:** The plan lists many questions, outcomes, contrasts, horizons, and possible interactions without one primary viability endpoint, one primary computational endpoint, effect measures, or a multiplicity policy. “Final population” is not itself persistence. Definitions are deferred until before pilot-v2, allowing smoke outcomes to influence them. In addition, “unbounded growth” is impossible under `DEFAULT_POP_CAP = 1000`; cap contact censors population differences.

**Recommended fix:** Before any smoke outcomes are reviewed, freeze:

- target seed distribution and exact seed list;
- primary biological/viability endpoint and primary computational endpoint;
- exact primary contrasts, delta direction, and evaluation horizon;
- persistence, near-extinction, extinction, and valid early-terminal rules;
- secondary versus exploratory outcomes and multiplicity policy; and
- population-cap handling, including first cap tick, ticks at cap, and proportion of run at cap.

Replace “unbounded-growth regimes” with “high-growth or cap-limited regimes.” Declare smoke engineering-only.

### 5. Major — condition names are not bound to an exact machine-checkable contract

**Affected sections:** §4 matrix; §§8–9 validation/provenance.

**Why it matters:** The plan gives factor states in prose but not exact CLI arguments and required manifest values. The runner accepts free-form `extra_args`, and the current validator does not compare effective anti-stagnation, disabled layers, raid policy, logging mode, ticks, or commit to the design. A well-named condition can therefore execute the wrong intervention and still appear valid.

**Recommended fix:** Add a condition implementation contract containing the exact flags and expected manifest values for all eight cells. Require validation to reject any mismatch. Either add an explicit `combat_enabled` manifest field or derive it from `disabled_layers` in the validator.

### 6. Blocker — the historical slowdown decomposition is not identifiable

**Affected sections:** §3 research question 6; §10 interpretation boundaries.

**Why it matters:** Every V2 cell fixes logging at buffered `metrics_only`. The matrix can estimate end-to-end runtime and storage under that policy and associate cost with state/event outcomes. It cannot causally apportion historical V1 slowdown among full text logging, structured I/O, event generation, faction-pair scanning, and state updates. Event volume is treatment-dependent, and the raid-control pilot explicitly did not isolate buffering speedup.

**Recommended fix:** Replace question 6 with:

> Under fixed buffered `metrics_only` output, how do formal-combat and raid controls change event volume, state size, runtime, and storage, and how do those quantities covary?

Add:

> Causal attribution to text logging or flush policy requires a separate fixed-workload microbenchmark or profiler study and is outside V2's confirmatory estimands.

### 7. Major — tier ranges conceal exact horizons, cell counts, and seed policy

**Affected sections:** §§5–6, 10, 12.

**Why it matters:** “100–250” and “1,000–2,500” do not say whether both endpoints run, whether the longer horizon is a fresh run, or which exact seeds are used. If both smoke horizons run, the minimal matrix contains 20–30 cells and the factorial 32–48 cells. At one pilot horizon, the matrices contain 25 or 40 cells; running both pilot horizons doubles those counts. Full V2 has at least 50 cells for the minimal matrix or 80 for the factorial at ten seeds. Same-seed horizons are correlated, not extra replication.

**Recommended fix:** Freeze exact stages, exact seed identities, seed-selection rule, per-stage matrix, and cell counts. Treat 2,500 ticks as a separately approved fresh horizon unless checkpoint continuation is implemented. Determine the full seed count from a predeclared precision target or simulation-based power analysis, not “10+” alone.

### 8. Major — runtime/storage gates are not enforceable budgets

**Affected sections:** §§5–6, 8, 11.

**Why it matters:** `metrics_only` and buffered flushing reduce overhead but do not bound structured-event rows or pair-scan work. Between-cell monitoring cannot stop one runaway cell, and “exceeds budget” is undefined without numeric limits. The 50 MB Wiki rule is a publication-copy constraint, not an experiment-storage budget. Raid-enabled/formal-combat-off cells risk event growth, while raid-disabled cells can retain more population and factions and remain computationally expensive.

**Recommended fix:** Before JSON creation, approve a tier budget table covering maximum wall time per cell/tier, bytes per cell/tier, structured events per cell, peak memory, and minimum free disk. Require active quotas/watchdogs for pilot/full or a safe equivalent. A breached cap must stop and invalidate/censor the cell; it must never silently truncate structured evidence and label the result complete.

### 9. Major — claimed provenance exceeds recorded and enforced provenance

**Affected sections:** §§9, 11–12.

**Why it matters:** The runner records commit and dirty state but does not abort on dirty, unknown, or mismatched provenance. Resume checks the batch plan hash but not the current commit/tag. Per-run manifests do not currently record tag, Python implementation/version, platform/architecture, dependency identity, plan hash, timestamps, actual termination, attempt ID, or validation result. The plan also requests “runner dry-run output,” but `run_experiments.py` has no `--dry-run` option.

**Recommended fix:** Make clean/tag/commit preflight mandatory before first execution and every resume. Add a nonexecuting matrix expansion/preflight command or remove the unsupported dry-run claim. Store a portable plan snapshot/hash and mandatory environment fingerprint. Standardize whether the field is called `code_dirty` or `code.dirty`.

### 10. Major — factor interpretation and inferential safeguards are incomplete

**Affected sections:** §§3–4, 7, 10.

**Why it matters:** `--disable-antistag` toggles a bundle of traveler, faction-rescue, disruption, world-event, era-shift, and singleton mechanisms; it is not one mechanism. “Combat enabled” and “raids enabled” describe policy availability, not realized exposure—short combat-enabled cells can contain zero wars. Raid events count successful emitted raids, not eligible pairs, attempts, failed attempts, or pair-scan work. Shared seeds align initialization but treatment-specific RNG consumption diverges downstream. Finally, condition-major execution can confound runtime comparisons with machine load or thermal order.

**Recommended fix:**

- Call factor A the “anti-stagnation intervention bundle” and prohibit component-level attribution.
- Add manipulation checks for intervention subtypes, war declarations/battle ticks/combat deaths, successful raids, and—if added without altering RNG—eligible/attempted raids.
- Report raid rates per tick and relevant faction-pair exposure, not raw counts alone.
- Describe shared seeds as blocking variables, not matched downstream random shocks; report paired and unpaired summaries.
- Counterbalance or deterministically randomize execution order for runtime analysis and record that order.

## 3. Reviewer reports

### 3.1 Experimental Design Reviewer

**Findings**

- The three-factor causal structure is promising and the expanded matrix is mathematically complete.
- The five-condition minimum estimates selected conditional contrasts, not general three-factor main effects.
- The plan does not define primary estimands, endpoint hierarchy, exact horizons, seed identities, sample-size rule, or cap handling.
- RQ6 is not identifiable under one fixed logging policy.

**Risks**

- Outcome-adaptive matrix/horizon selection after smoke.
- Treating arbitrary seed counts as inferential justification.
- Mistaking factor availability for factor activation.
- Interpreting correlated horizons or repeated seeds as additional evidence.

**Missing details**

- Exact seed-generating/list policy.
- Viability/persistence thresholds and primary horizon.
- Sign convention and uncertainty method for primary contrasts.
- Missing/timeout handling and complete-block paired analysis policy.
- Manipulation checks, event-rate denominators, and execution order.

**Recommended changes**

- Freeze an endpoint/estimand table before smoke outcomes are inspected.
- Use the full eight-cell matrix for smoke semantics; keep smoke engineering-only.
- Use the five-cell matrix later only if the registered questions are explicitly conditional.
- Make 1,000 and 2,500 ticks separate decisions, and use pilot variance to justify full-tier seeds.

### 3.2 Runtime and Storage Risk Reviewer

**Findings**

- The current runner is not fail-fast and exact resume validation is insufficient.
- The plan omits total cell counts and numeric tier budgets.
- Buffered `metrics_only` does not bound event rows or output bytes.
- Combat-off/raids-on and raids-off conditions pose different scaling hazards.

**Risks**

- Nonlinear faction-pair work and event growth.
- Large surviving populations/faction state even with raids disabled.
- One runaway cell exhausting time/disk before between-cell monitoring.
- Informative timeouts concentrated in the most extreme conditions.

**Missing details**

- Active byte/event/disk enforcement.
- Maximum cell/tier wall time and output.
- Required peak-memory measurement.
- Sentinel release rule before all pilot seeds.

**Recommended changes**

- Add a numeric budget table and active enforcement policy.
- Use a preregistered sentinel seed across all approved conditions before releasing remaining pilot seeds.
- Base projections on maxima and growth trends, never condition means or linear tick scaling alone.
- State that the expanded matrix is a smoke candidate, not presumed affordable.

### 3.3 Simulation Semantics Reviewer

**Findings**

- Explicit combat and raid controls behave independently as intended.
- Historical formal-combat-off/raids-on semantics are preserved.
- `no_hostility` is false as a condition description because other conflict-like dynamics remain.
- Anti-stagnation is a composite policy bundle.
- A `raid` event represents a successful resource-transferring raid, not total raid workload.

**Risks**

- Freezing misleading condition names into permanent evidence.
- Claiming a combat effect when the combat mechanism never activates.
- Treating raid event counts as pair-scan or attempt counts.
- Retroactively redefining historical `no_combat` through imprecise language.

**Missing details**

- Exact CLI/manifest contract per condition.
- Realized-exposure checks.
- Explicit statement that raids-off does not disable rivalry, diplomacy, religion, or adverse anti-stagnation events.

**Recommended changes**

- Use factor-explicit names and machine-check the mapping.
- Describe raid contrasts as total downstream effects of the raid subsystem.
- Keep V1's `no_combat` label only as historical terminology.

### 3.4 Reproducibility and Provenance Reviewer

**Findings**

- Positive foundations exist: raw-byte plan SHA-256, batch persistence after each cell, `PYTHONHASHSEED=0`, seeded serial execution, canonical state encoding, and independent-process tests.
- Interruption/exception finalization, shallow validation, and resume skipping can mislabel evidence.
- Clean/tag/commit provenance is recorded partially but not enforced.
- Retry and resume behavior does not preserve immutable attempt history.

**Risks**

- Mixed revisions under one experiment ID.
- Header-only/truncated structured artifacts passing presence validation.
- Persistent event flush/write failures remaining silent.
- A cancelled run appearing as a completed scientific replicate.

**Missing details**

- Termination-aware manifest fields and actual final tick.
- Tag, environment, dependency, plugin, plan, attempt, and validation provenance.
- Deep verify behavior and failure-path tests.
- Nonexecuting effective-matrix preflight.

**Recommended changes**

- Make termination-aware manifests, deep validation, fail-fast, clean-tag enforcement, and attempt-safe resume prerequisites for smoke.
- Require duplicate isolated-process diagnostic probes for each smoke condition; exclude them from replicate counts.
- Surface unresolved metrics/event/belief write failures and reject affected artifacts.

### 3.5 Skeptical Peer Reviewer

**Findings**

- Clean Git provenance is necessary but not sufficient for publication readiness.
- The plan has no confirmatory endpoint hierarchy, directional hypotheses, or multiplicity policy.
- Shared seeds are useful blocks but not common-random-number controls after treatment-specific RNG divergence.
- Timeouts are informative computational outcomes, not ignorable missingness.

**Risks**

- Selecting favorable outcomes from many metrics and contrasts.
- Calling five or ten seeds publication-grade without a precision rationale.
- Excluding the slowest/highest-growth cells and biasing tractability claims.
- Claiming intrinsic viability when anti-stagnation actively injects/rescues population and factions.

**Missing details**

- Target seed distribution, precision target, and power/sample-size rule.
- Metric data dictionary and measurement timing.
- Frozen analysis code and primary/secondary/exploratory labels.
- Counterbalanced execution order and timeout censoring policy.

**Recommended changes**

- Frame the anti-stagnation contrast as the total effect of a bundled rescue/intervention policy.
- Retain timed-out/cancelled attempts as censored tractability evidence while excluding incomplete biological endpoints.
- Report V1, smoke, pilot, and confirmatory V2 separately.
- Do not call V2 publication-grade solely because it reaches 10,000 ticks or ten seeds.

## 4. Matrix critique

### Minimal matrix

The five-condition minimum is coherent for two purposes:

1. one anti-stagnation-bundle contrast at combat-on/raids-on; and
2. the complete 2 × 2 formal-combat × raids square while anti-stagnation is on.

It does **not** estimate general combat, raid, or anti-stagnation main effects across all factor levels, nor any interactions involving anti-stagnation outside the baseline setting. Conclusions must be described as conditional simple effects.

### Expanded matrix

The eight-condition design is the correct complete 2 × 2 × 2 factorial. It is appropriate for smoke-level configuration and tractability validation. With only three smoke seeds it is not an interaction study, and with five pilot seeds interaction estimates will remain uncertain. If three-factor interactions are confirmatory objectives, the expanded matrix must remain through the inferential tier or the question must be narrowed.

### Is the factorial too large?

- For smoke: not inherently, but only after exact stages, budgets, fail-fast, and deep validation exist.
- For pilot: potentially. One horizon requires 40 cells at five seeds; a second fresh horizon requires another 40.
- For full: high risk. Ten seeds require 80 cells, including the conditions most likely to grow nonlinearly.

The matrix should be pruned only by predeclared feasibility rules assessed without selecting on favorable biological outcomes. An intractable cell is itself censored tractability evidence and must not disappear from reporting.

### Recommended canonical names

| Anti-stagnation bundle | Formal combat | Raids | Recommended identifier |
|---:|---:|---:|---|
| on | on | on | `antistag_on_combat_on_raids_on` |
| off | on | on | `antistag_off_combat_on_raids_on` |
| on | off | on | `antistag_on_combat_off_raids_on` |
| on | on | off | `antistag_on_combat_on_raids_off` |
| on | off | off | `antistag_on_combat_off_raids_off` |
| off | off | on | `antistag_off_combat_off_raids_on` |
| off | on | off | `antistag_off_combat_on_raids_off` |
| off | off | off | `antistag_off_combat_off_raids_off` |

Short aliases such as `baseline` may remain in prose, but evidence identifiers should not rely on implicit settings.

### Staged design judgment

Smoke → pilot → full is appropriate. Replace ranges with exact, separately authorized stages. One defensible structure for later plan revision is:

- S0: eight conditions × two frozen shared seeds × 100 ticks = 16 cells.
- S1, only after S0 passes: eight conditions × three frozen shared seeds × 250 ticks = 24 cells.
- P1: frozen matrix × five frozen shared seeds × exactly 1,000 ticks.
- P2, separately reviewed: frozen matrix × five shared seeds × exactly 2,500 ticks.
- Full: frozen matrix × a precision-justified seed count × 10,000 ticks.

This is a design recommendation, not authorization to execute those stages.

## 5. Runtime critique

### 100-tick smoke — low-to-moderate relative risk

Suitable for CLI, manifest, condition-contract, artifact, and hash checks. It cannot validate every anti-stagnation mechanism because some activate at later cadences, and it provides no long-horizon scientific evidence.

### 250-tick smoke — moderate relative risk

Existing bounded evidence already shows divergent faction, event, and state growth. Run sequentially, validate every cell, and treat observed outcomes as engineering/feasibility evidence only.

### 1,000-tick pilot — high relative risk

Short-run growth is nonlinear, so direct tick multiplication is unsafe. Release a preregistered sentinel seed across the frozen conditions first, inspect only registered feasibility metrics, then decide whether the remaining seeds fit the approved budget.

### 2,500-tick pilot — very high relative risk

This is a separate fresh-run cost unless checkpoint continuation exists. It should have a new immutable plan and written approval after the 1,000-tick tier.

### 10,000-tick full replication — extreme relative risk

The minimum matrix requires at least 50 cells at ten seeds and the factorial 80. Metrics-only eliminates giant raw text output, but not event rows, faction-pair scanning, or large population/faction state. Full V2 should wait for validated 1,000- and 2,500-tick envelopes, active storage safeguards, a precision-based seed count, and separate authorization.

## 6. Provenance checklist before any V2 run

- [ ] `CORE_REPLICATION_V2_PLAN.md`, runner/verifier prerequisites, tests, and reviewed draft JSON are committed.
- [ ] `git status --short` is empty immediately before first execution and every resume.
- [ ] A unique annotated parent-repository V2 run-ready tag exists and resolves exactly to `HEAD`.
- [ ] The expected commit and tag are frozen in the plan and enforced by preflight.
- [ ] Parent tests pass, including dirty/unknown revision, commit-change resume, timeout, cancellation, exception, truncated/header-only CSV, config mismatch, plan mismatch, and fail-fast paths.
- [ ] `code.dirty`/`code_dirty` is expected and verified as `false` in batch and per-run provenance.
- [ ] Python implementation/version, executable, platform/architecture, `PYTHONHASHSEED=0`, dependency/lock hashes, schema versions, and plugin policy/inventory are recorded.
- [ ] The exact plan snapshot and SHA-256 match the batch manifest and every selected run.
- [ ] Every condition expands to an reviewed exact contract: anti-stagnation, formal combat, raids, disabled layers, `log_mode=metrics_only`, seeds, and ticks.
- [ ] Shared seed identities and selection rule are frozen across all conditions.
- [ ] Diagnostic repeated-hash probes pass for every smoke condition and are excluded from scientific replicate counts.
- [ ] Output root is absent/empty, or resume is proven plan-, commit-, tag-, config-, and attempt-safe.
- [ ] V2 forbids destructive `--overwrite` and preserves an append-only attempt ledger.
- [ ] Validation is enabled and checks actual final tick/terminal reason, exact config/provenance, CSV schemas/order/content, summary consistency, and unresolved write failures.
- [ ] Stop-on-first-noncompleted behavior is enabled and tested.
- [ ] `metrics_only` is explicit in every condition; full logs/manual chronicles are absent.
- [ ] Per-cell/tier runtime, bytes, event, memory, and free-disk budgets are filled and approved.
- [ ] Cell execution order is counterbalanced or deterministically randomized and recorded.
- [ ] Analysis code, primary estimands, endpoint definitions, timeout handling, and multiplicity policy are frozen.

## 7. Recommended edits to `CORE_REPLICATION_V2_PLAN.md`

Do not execute these edits implicitly; apply them in a later explicit revision task.

### §1 Purpose

Replace “replace the historical pilot” with:

> provide the preferred clean post-fix successor evidence base while preserving Core Replication V1 as historical pilot evidence.

Add an implementation-readiness gate: smoke is unauthorized until termination-aware manifests, deep validation, fail-fast, clean-tag preflight, and attempt-safe resume are implemented and tested.

### §3 Main research questions

- Replace “all hostile coercion” with “formal combat and economy raids, the two manipulated mechanisms.”
- Replace RQ6 with the fixed-`metrics_only` association question in Top Issue 6.
- Replace “unbounded-growth” with “high-growth or cap-limited.”
- Add a pre-specified estimand/endpoint table before the matrix.
- Define anti-stagnation as a bundled intervention policy, not intrinsic viability.

### §4 Experimental matrix

- Replace all ambiguous identifiers with the canonical names in §4 of this review.
- State that the minimum estimates conditional simple effects only.
- Add this condition contract before any JSON is drafted:

| Condition | Required CLI controls | Expected `anti_stagnation_enabled` | Expected `disabled_layers` | Expected `raids_enabled` |
|---|---|---:|---|---:|
| `antistag_on_combat_on_raids_on` | `--log-mode metrics_only` | true | `[]` | true |
| `antistag_off_combat_on_raids_on` | `--disable-antistag --log-mode metrics_only` | false | `[]` | true |
| `antistag_on_combat_off_raids_on` | `--disable-layer combat --log-mode metrics_only` | true | `[combat]` | true |
| `antistag_on_combat_on_raids_off` | `--disable-raids --log-mode metrics_only` | true | `[raids]` | false |
| `antistag_on_combat_off_raids_off` | `--disable-layer combat --disable-raids --log-mode metrics_only` | true | `[combat, raids]` | false |
| `antistag_off_combat_off_raids_on` | `--disable-antistag --disable-layer combat --log-mode metrics_only` | false | `[combat]` | true |
| `antistag_off_combat_on_raids_off` | `--disable-antistag --disable-raids --log-mode metrics_only` | false | `[raids]` | false |
| `antistag_off_combat_off_raids_off` | `--disable-antistag --disable-layer combat --disable-raids --log-mode metrics_only` | false | `[combat, raids]` | false |

Require the verifier to reject any condition-contract mismatch.

### §§5–6 Run tiers and default

- Replace horizon/seed ranges with exact named stages, seed lists, and cell counts.
- State whether longer horizons are fresh runs or checkpoints.
- Define feasibility-only, predeclared matrix-pruning rules.
- Replace “expanded matrix is affordable enough” with “expanded matrix is a smoke candidate whose authorization depends on approved budgets.”
- Add a sentinel-seed gate before releasing all pilot seeds.
- Base the full seed count on a target interval width or simulation-based precision analysis.

### §7 Metrics and artifacts

Add:

- requested/final tick, termination reason, completed-normally status, attempt/supersession IDs;
- first tick at population cap, ticks/proportion at cap;
- intervention subtype counts;
- war declarations, battle ticks, completed wars, combat-attributed deaths;
- successful raids and appropriate faction-pair opportunity denominators;
- resource/scarcity proximal outcomes if raid mechanisms are interpreted;
- artifact checksums and unresolved write/flush failure counts; and
- a data dictionary distinguishing `tracemalloc` peak from operating-system RSS.

### §8 Runtime and storage safeguards

- Require abort-before-next-cell on any noncompleted result.
- Require exact config/provenance validation before resume-skipping.
- Forbid V2 `--overwrite`; preserve immutable attempts.
- Add numeric per-cell/tier time, byte, event, memory, and disk budgets.
- Require active cap/watchdog/quota enforcement for pilot/full; never silently truncate a valid run.
- Counterbalance or deterministically randomize condition order for runtime comparisons.

### §9 Provenance

- Make Python/platform/dependency capture mandatory rather than “when supported.”
- Require preflight to abort on dirty, unknown, untagged, or mismatched revision.
- Record tag, expected commit, plan SHA/snapshot, environment, attempt, actual terminal state, and validation result per run.
- Verify the same invariants on resume and `--verify`.

### §10 Analysis

- Define one primary viability endpoint and one primary computational endpoint.
- Freeze exact contrasts, effect measures, uncertainty method, and multiplicity policy.
- State that shared seeds are blocking variables whose downstream RNG streams diverge by treatment.
- Report paired and unpaired summaries.
- Treat timeouts as censored tractability evidence; do not use incomplete biological endpoints.
- Label factorial effects, conditional simple effects, secondary outcomes, and exploratory analyses separately.

### §11 Stop conditions

Define acceptance as process success plus deep manifest/artifact validation and expected final tick, except for an explicitly registered natural terminal such as extinction. State that timeout, exception, and cancellation artifacts can never be resume-skipped as completed. Preserve them in the attempt ledger.

### §12 Execution sequence

Insert before JSON creation:

1. implement and test termination-aware manifests;
2. implement deep design-conformance validation;
3. implement fail-fast and immutable attempt/resume history;
4. implement clean-tag/environment preflight and nonexecuting matrix expansion;
5. revise and re-review this plan.

Only then draft the smoke JSON. Remove the unsupported runner dry-run reference unless that feature is implemented.

### §13 Non-goals

Add:

- not attributing the anti-stagnation bundle effect to one constituent mechanism;
- not causally decomposing logging/I/O cost inside V2;
- not calling formal-combat-off/raids-off “hostility-free”; and
- not treating cap-saturated trajectories as evidence of unbounded growth.

## 8. Final recommendation

**Choice:** **Needs implementation changes before smoke tier**

The scientific concept should proceed, but no V2 smoke run should start yet. First revise the plan to fix condition semantics, estimands, exact stages, seeds, and budgets. Then make bounded runner/verifier changes for termination-aware completion, deep design-conformance validation, fail-fast behavior, clean-tag enforcement, and immutable attempt history. These are research-integrity and orchestration changes; they do not require rebalancing simulation dynamics.

After those prerequisites pass tests, create a draft smoke JSON, review its nonexecuting matrix expansion, commit and tag the exact run-ready state, confirm a clean tree, and request separate authorization for smoke. Full 10,000-tick V2 should remain out of scope until validated smoke and pilot tiers justify it.
