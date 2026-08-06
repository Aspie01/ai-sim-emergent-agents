# Core Replication V2 Plan

**Status:** Draft — implementation prerequisites unresolved; no execution authorized.
**Authorization boundary:** This plan does not authorize smoke, pilot, or full execution. S0 remains blocked until the runner and verifier prerequisites in this document are implemented and their failure/resume paths pass tests. Core Replication V1 remains historical pilot evidence; V2 neither replaces it retroactively nor permits V1 and V2 to be pooled.

## 1. Purpose

Core Replication V2 is intended to provide the preferred clean, tagged, post-fix successor evidence base while preserving Core Replication V1 as historical pilot evidence. V2 is a provenance and research-design correction, not merely a longer run.

The future design is based on:

- the seeded Layer 1 serial reproducibility fix;
- buffered `metrics_only` structured output;
- explicit, independent controls for formal combat and economy raids;
- the anti-stagnation intervention bundle as a separate factor;
- shared seed blocks across conditions;
- termination-aware manifests and deep artifact validation;
- immutable execution-attempt history; and
- a clean commit, annotated run-ready tag, and enforced `code_dirty: false` provenance.

The condition matrix, endpoints, contrasts, seed policy, budgets, validation contract, and analysis rules must be frozen at their required gates. No experiment JSON may be created under this revision task.

## 2. Relationship to prior evidence

| Dataset | Evidence role | Supported interpretation | Limitation |
|---|---|---|---|
| `core-replication-v1` | Validated historical pilot | Motivates persistence, population-regulation, combat, raid, and tractability questions | Dirty-worktree provenance; predates the seeded serial fix; historical `no_combat` meant formal combat off while economy raids remained on |
| `logging-ablation-v1` | Bounded partial benchmark | Shows that full text output is a major storage burden and likely runtime contributor | Pre-fix cells diverged in state; only a short post-fix same-state probe exists; not publication-grade and not a causal decomposition of all runtime costs |
| `raid-control-pilot-v1` | Implementation/control validation | Confirms combat and raid controls are independent, raids-off emits zero successful raids, and buffered event rows preserve order/content | Three seeds at 100/250 ticks; dirty-worktree provenance; not long-horizon evidence and not a buffer-speed benchmark |
| `core-replication-v2` | Future clean replication | Intended to estimate predeclared contrasts under post-fix code and fixed output policy | Not executed; no claim may cite it until an authorized tier validates |

V1 and V2 must be reported as separate datasets produced under different code and provenance regimes. V1 can motivate hypotheses and contextualize V2, but it is never an additional V2 replicate.

## 3. Factors, semantics, and research questions

### 3.1 Experimental factors

- **A — Anti-stagnation intervention bundle:** enabled or disabled. This bundle contains multiple rescue, disruption, traveler, faction, world-event, era, and singleton interventions. Its contrast estimates the total effect of the bundle; it cannot be attributed to any one constituent mechanism without a separate experiment.
- **C — Formal-combat policy:** enabled or disabled. This controls the formal war/battle-resolution mechanism.
- **R — Economy-raid policy:** enabled or disabled. Raids are economy-generated, combat-adjacent coercive interactions that transfer resources and affect beliefs, rivalry, reputation, and treaties; they are not formal wars or battles.

Each factor first describes **policy availability**. Realized **activation/exposure** is a manipulation check, not an assumption: combat enabled does not guarantee a war or battle occurs, and raids enabled does not guarantee any particular raid count.

Disabling both formal combat and raids disables only those two manipulated mechanisms. It does not disable rivalry, diplomatic conflict, religious conflict state, scarcity, or conflict-related anti-stagnation events. Such a condition must never be called hostility-free. Historical V1 `no_combat` remains historical terminology for formal combat off with raids on; no V2 evidence identifier uses bare `no_combat`.

### 3.2 Main research questions

1. Does disabling the anti-stagnation intervention bundle change long-horizon viability and population persistence under formal combat on and raids on after the seeded determinism fix?
2. What is the effect of disabling formal combat while raids remain enabled and anti-stagnation remains enabled?
3. What is the effect of disabling raids while formal combat remains enabled and anti-stagnation remains enabled?
4. How does disabling both manipulated coercive mechanisms differ from the all-enabled condition while anti-stagnation remains enabled?
5. If the complete factorial is retained beyond smoke, how do anti-stagnation-bundle effects vary across the formal-combat and raid policies?
6. Under fixed buffered `metrics_only` output, how do formal-combat and raid controls change event volume, state size, runtime, and storage, and how do those quantities covary?
7. At preapproved horizons, which conditions show persistence, near-extinction, extinction, high growth, or population-cap-limited trajectories, and how consistent are these outcomes across seed blocks?

Causal attribution to text logging or flush policy requires a fixed-workload microbenchmark or profiler study and is outside V2. V2 cannot causally separate historical full-text logging, structured I/O, faction-pair scanning, event generation, and simulation-state update costs.

## 4. Draft endpoint and estimand declaration — review and freeze required

The definitions in this section are **draft proposals for review**. The approved primary horizon, threshold, estimators, interval method, outcome hierarchy, and multiplicity policy must be frozen before any S0 result is inspected. S0 and S1 remain engineering/feasibility tiers, not evidence for selecting whichever biological endpoint looks favorable.

### 4.1 Proposed endpoint and contrast table

| Role | Draft proposed definition | Effect measure / handling |
|---|---|---|
| Primary viability endpoint | Final living population at the approved primary horizon, accompanied by completion/extinction status and population-cap exposure | Condition and per-seed values; mean difference is proposed, with all seed-level deltas reported. The primary horizon and uncertainty method remain review items that must be frozen before S0 inspection. |
| Primary computational endpoint | Elapsed seconds per completed tick | `elapsed_seconds / completed_ticks`; timed-out or cancelled attempts remain censored tractability evidence. Zero completed ticks yield a missing rate but retain elapsed/status evidence. |
| Primary contrast A | `antistag_off_combat_on_raids_on` minus `antistag_on_combat_on_raids_on` | Total effect of disabling the anti-stagnation intervention bundle under combat on/raids on; no component attribution |
| Primary contrast C | `antistag_on_combat_off_raids_on` minus `antistag_on_combat_on_raids_on` | Effect of disabling formal combat while raids remain on and anti-stagnation remains on |
| Primary contrast R | `antistag_on_combat_on_raids_off` minus `antistag_on_combat_on_raids_on` | Effect of disabling raids while formal combat remains on and anti-stagnation remains on |
| Primary joint contrast | `antistag_on_combat_off_raids_off` minus `antistag_on_combat_on_raids_on` | Joint effect of disabling formal combat and raids while anti-stagnation remains on; not “removing all hostility” |
| Secondary endpoints | Peak/minimum population, final/peak factions, births, deaths, wars, raids, event composition, resource/scarcity measures, output bytes, and peak memory | Report with predeclared labels and no silent promotion to primary |
| Exploratory endpoints | Factor interactions, trajectory shapes, event/state/runtime covariation, and intervention-subtype associations | Clearly labeled exploratory; multiplicity and model-selection boundaries frozen before inferential use |

All contrast signs are intervention-minus-reference as written. Shared-seed paired estimates use only complete blocks for the relevant contrast; condition-level/unpaired summaries use every eligible validated run and are reported alongside them.

### 4.2 Draft proposed outcome definitions

Let `H` be the approved horizon, `P0` the configured starting population, `Pcap` the configured population cap, and `T_NE = max(5, ceil(0.10 × P0))`. The formula for `T_NE` is a draft threshold and must be explicitly accepted or replaced before S0 inspection.

| Term | Draft proposed operational definition |
|---|---|
| Persistence | A deeply validated run reaches `H` with final population greater than `T_NE`. This is persistence under the configured intervention policy, not proof of intrinsic self-sufficiency. |
| Near-extinction | A deeply validated run reaches `H` with `0 < final_population <= T_NE`. |
| Extinction | Living population reaches zero and the manifest records the preregistered extinction terminal state at the last fully completed tick. |
| Valid natural terminal | A terminal reason on a preregistered allowlist, with internally consistent manifest and artifacts, accepted by deep validation despite `final_tick < requested_ticks`. The draft V2 allowlist contains extinction only; additions require plan review before execution. |
| Incomplete | The attempt neither reaches `H` nor satisfies a preregistered valid-natural-terminal rule. It supplies no final biological endpoint. |
| Cancelled | User or orchestrator cancellation is recorded explicitly; never treated as completed or resume-skipped. |
| Timed out | A wall-clock quota ends the process; retained as censored tractability evidence and excluded from final biological endpoints. |
| Invalid/exception | Execution or evidence integrity failed. Artifacts remain attempt-level audit evidence but are not scientific endpoint observations. |
| Population-cap contact | At least one authoritative end-of-tick population observation is greater than or equal to `Pcap`. |

Every accepted run must collect `first_population_cap_tick`, `ticks_at_population_cap`, and `proportion_at_population_cap = ticks_at_population_cap / completed_ticks`. A zero-contact run records no first tick, zero cap ticks, and proportion zero. Cap-limited trajectories must be described as cap-limited; they must never be called unbounded growth.

## 5. Experimental matrix

### 5.1 Canonical condition identifiers

| Condition | Anti-stagnation bundle | Formal combat | Raids | Design role |
|---|---:|---:|---:|---|
| `antistag_on_combat_on_raids_on` | on | on | on | All-enabled reference |
| `antistag_off_combat_on_raids_on` | off | on | on | Primary anti-stagnation-bundle contrast |
| `antistag_on_combat_off_raids_on` | on | off | on | Formal-combat contrast with raids on |
| `antistag_on_combat_on_raids_off` | on | on | off | Raid contrast with formal combat on |
| `antistag_on_combat_off_raids_off` | on | off | off | Joint manipulated-mechanism contrast |
| `antistag_off_combat_off_raids_on` | off | off | on | Factorial interaction cell |
| `antistag_off_combat_on_raids_off` | off | on | off | Factorial interaction cell |
| `antistag_off_combat_off_raids_off` | off | off | off | Factorial interaction cell |

S0 and S1 use all eight conditions to verify the complete 2 × 2 × 2 configuration surface. A practical five-condition P1 matrix would retain the first five rows and estimate conditional simple effects only. The eight-condition matrix is required for general factorial interactions. Any P1 reduction must be based on preregistered feasibility/tractability rules rather than favorable biological outcomes, and the selected matrix must be frozen before P1 execution.

### 5.2 Exact condition implementation contract

The future plan expander must generate these controls rather than trust free-form condition prose. `disabled_layers` uses the canonical ordering shown. The verifier must reject any CLI, manifest, plan, or effective-configuration mismatch.

| Condition | Exact CLI controls | Expected `anti_stagnation_enabled` | Expected `disabled_layers` | Expected `raids_enabled` | Expected `log_mode` |
|---|---|---:|---|---:|---|
| `antistag_on_combat_on_raids_on` | `--log-mode metrics_only` | `true` | `[]` | `true` | `metrics_only` |
| `antistag_off_combat_on_raids_on` | `--disable-antistag --log-mode metrics_only` | `false` | `[]` | `true` | `metrics_only` |
| `antistag_on_combat_off_raids_on` | `--disable-layer combat --log-mode metrics_only` | `true` | `[combat]` | `true` | `metrics_only` |
| `antistag_on_combat_on_raids_off` | `--disable-raids --log-mode metrics_only` | `true` | `[raids]` | `false` | `metrics_only` |
| `antistag_on_combat_off_raids_off` | `--disable-layer combat --disable-raids --log-mode metrics_only` | `true` | `[combat, raids]` | `false` | `metrics_only` |
| `antistag_off_combat_off_raids_on` | `--disable-antistag --disable-layer combat --log-mode metrics_only` | `false` | `[combat]` | `true` | `metrics_only` |
| `antistag_off_combat_on_raids_off` | `--disable-antistag --disable-raids --log-mode metrics_only` | `false` | `[raids]` | `false` | `metrics_only` |
| `antistag_off_combat_off_raids_off` | `--disable-antistag --disable-layer combat --disable-raids --log-mode metrics_only` | `false` | `[combat, raids]` | `false` | `metrics_only` |

Formal-combat availability must either be recorded explicitly as `combat_enabled` or derived canonically from `disabled_layers`; validation must prove the expected value either way. Free-form arguments must not be able to override runner-owned seed, tick, condition, log-mode, anti-stagnation, combat, or raid controls.

## 6. Exact proposed stages

These stages are design proposals, not execution authorization.

| Stage | Matrix | Seeds | Exact horizon | Cell count | Permitted interpretation |
|---|---|---|---:|---:|---|
| S0 | All 8 conditions | `1, 2` | 100 ticks | 16 fresh cells | Engineering/configuration validation only |
| S1 | All 8 conditions | `1, 2, 3` | 250 ticks | 24 fresh cells | Feasibility and manipulation-check evidence only |
| P1 | Matrix selected and frozen before execution | `1, 2, 3, 4, 5`, unless a reviewed alternative seed rule is approved | 1,000 ticks | 25 cells for five conditions or 40 for eight | Pilot evidence only; sentinel release gate applies |
| P2 | Separately approved and freshly executed frozen matrix | Frozen in a separate approved stage plan | 2,500 ticks | Depends on approved matrix/seeds | Separate pilot extension; never automatic continuation of P1 |
| Full | Separately frozen matrix | Count chosen by a precision target or simulation-based power/precision analysis | 10,000 ticks | TBD by approved matrix and seed analysis | Potential confirmatory evidence only after separate written authorization |

P1 begins with a preregistered sentinel seed (draft proposal: seed `1`) across every frozen condition. Remaining P1 seeds are released only after a registered feasibility review confirms deep validation, manipulation checks, reproducibility probes, runtime/storage/event/memory quotas, and disk headroom. That review may not select conditions because their biological outcomes look favorable.

P2 consists of fresh 2,500-tick cells unless a separately designed, validated checkpoint protocol exists; no such protocol is assumed here. Repeated horizons using the same seed are correlated observations, not additional independent replicates. Same-cell diagnostic reruns and superseded attempts are also not replicates.

### Stage gates

- S0 cannot begin until every prerequisite in §7 passes tests and the endpoint/estimand declaration is frozen.
- S1 requires all S0 cells to be deeply valid, configuration-conformant, reproducible, within approved quotas, and free of unexplained event/artifact behavior.
- P1 requires a reviewed, frozen matrix; approved numeric budgets; frozen analysis rules; and separate authorization.
- P2 requires a written analysis of P1 maxima and growth trends, not linear extrapolation from means.
- Full requires validated P1 and P2 envelopes, a precision-justified seed count, an archival provenance review, and separate written authorization.

## 7. Implementation prerequisites before S0

S0 remains blocked until all of the following are implemented and tested:

1. **Termination-aware manifests** recording `requested_ticks`, `final_tick` as the last fully completed tick, `termination_reason`, `result_status`, and `completed_normally`.
2. **Explicit valid-natural-terminal handling** that distinguishes preregistered extinction from timeout, cancellation, exception, crash, or invalid output.
3. **Deep streaming artifact validation** covering schemas, headers, non-header rows where required, tick monotonicity/coverage, exact summary rows, manifest consistency, artifact checksums, and unresolved write/flush failures without loading large files into memory.
4. **Exact condition-contract validation** against plan, CLI, effective controls, requested ticks, seed, `metrics_only`, commit/tag, and manifest values.
5. **Stop-on-first-noncompleted behavior** that persists the attempt and batch stop reason before dispatching no further cell.
6. **Immutable attempt directories** so retries never overwrite prior manifests, summaries, stderr, or structured artifacts.
7. **An append-only attempt ledger** with explicit selected/final attempt state and preservation of every outcome.
8. **Supersession without deletion:** a later deeply valid attempt may be selected and a prior selected attempt marked superseded, but failures and prior evidence remain immutable and never become extra replicates.
9. **Clean/tagged/expected-commit preflight** before first execution and every resume.
10. **Safe resume validation** against plan snapshot/hash, commit, tag, clean status, exact config, environment fingerprint, attempt status, and deep artifact validity.
11. **No destructive overwrite for V2.** V2 execution must reject overwrite semantics that remove attempt history.
12. **A nonexecuting matrix expansion/preflight command** that prints exact cells, order, commands, contracts, paths, budgets, and expected provenance without starting a process.
13. **Failure/resume test coverage** for cancellation/`KeyboardInterrupt`, ordinary exception, timeout, extinction/natural terminal, truncated and header-only CSVs, wrong final tick/config/commit/plan hash, dirty tree, stale resume artifacts, supersession, buffered-write/flush failures, fail-fast behavior, and deterministic state hashes.
14. **Diagnostic isolated-process reproducibility probes** for every S0 condition, recorded separately and excluded from scientific replicate counts.

Process exit success alone is never evidence completion. Resume may skip only the selected attempt whose terminal state and artifacts deeply validate against the exact frozen contract.

## 8. Metrics, manipulation checks, and required artifacts

Each attempt must record or derive, with definitions frozen in the V2 metrics dictionary:

- requested ticks, final tick, completed ticks, termination reason, result status, and completed-normally status;
- final, peak, and minimum population;
- final and peak active factions;
- births, deaths, war declarations, completed wars, and war durations;
- battle ticks or combat-resolution activations;
- combat-attributed deaths where available;
- successful emitted raid events and raid rate per completed tick;
- faction-pair opportunity exposure/denominator if it can be instrumented without adding RNG calls, changing iteration order, or changing simulation behavior;
- structured-event total and event-type composition;
- anti-stagnation intervention subtype counts where available;
- proximal resource/scarcity measures relevant to raid interpretation;
- first population-cap tick, ticks at cap, and proportion at cap;
- elapsed seconds, completed ticks, seconds per completed tick, output bytes, and peak memory with its measurement method;
- state hash, artifact checksums, unresolved writer-health failures, attempt ID, and validation result; and
- the exact condition controls and full provenance described in §10.

A raid event count means successful emitted raids. It is not the number of faction-pair scans, eligible pairs, attempted raids, or failed attempts. Combat/raid/bundle-enabled fields are availability checks; war declarations, battle activations, successful raids, and intervention-subtype counts are realized-exposure checks. If an exposure denominator cannot be added without perturbing RNG or behavior, it remains unavailable rather than being approximated from event counts.

Required research artifacts are structured metrics, events, beliefs under their explicit output policy, run summary, termination-aware manifest, validation report, artifact inventory/checksums, and attempt-ledger records. Full narrative/debug logs and manual chronicles are forbidden for V2 research cells.

## 9. Numeric budget placeholders and runtime/storage safeguards

Every value below must be replaced by an explicit reviewed value before any S0 JSON is created. No current entry authorizes a default.

| Budget/control field | Required approved value |
|---|---|
| Maximum wall time per cell | **TBD — requires explicit approval before execution** |
| Maximum wall time per tier | **TBD — requires explicit approval before execution** |
| Maximum bytes per cell | **TBD — requires explicit approval before execution** |
| Maximum bytes per tier | **TBD — requires explicit approval before execution** |
| Maximum structured events per cell | **TBD — requires explicit approval before execution** |
| Maximum peak memory | **TBD — requires explicit approval before execution** |
| Minimum free disk before dispatch | **TBD — requires explicit approval before execution** |
| Timeout handling | **TBD — requires explicit approval before execution** |
| Quota-breach result classification | **TBD — requires explicit approval before execution** |

The approved system must enforce applicable quotas during a cell or by a reviewed safe equivalent; between-cell observation alone is insufficient for pilot/full risk. A breached quota invalidates or censors the cell under the predeclared classification. It must stop safely, preserve attempt evidence, prevent subsequent dispatch under fail-fast policy, and never produce a silently truncated `completed` result.

Additional safeguards:

- Use buffered `metrics_only` for every cell; never generate full raw text logs or manual chronicles.
- Monitor structured-event growth, population, factions, throughput, memory, output bytes, and free disk without parsing giant logs.
- Base projections on observed maxima and nonlinear growth trends, not condition means or simple tick multiplication.
- Require sufficient disk headroom before each dispatch and stop before violating the approved reserve.
- Copy no artifact over 50 MB into LLM-Wiki; future documentation should link large evidence by path and provenance.
- Validate immediately after each attempt and before dispatching the next cell.

## 10. Provenance and preflight requirements

Before first execution and every resume, preflight must require and record:

- an empty parent-repository `git status --short`;
- a unique annotated run-ready tag resolving exactly to `HEAD`;
- the expected commit hash and tag frozen in the plan and matching `HEAD`;
- `code_dirty: false` in experiment and attempt provenance;
- an immutable plan snapshot and its SHA-256;
- Python implementation and version;
- the absolute Python executable;
- operating system, platform, and architecture;
- dependency, requirements, and/or lockfile hashes;
- the exact `PYTHONHASHSEED` policy/value;
- plugin policy and inventory, including an explicit empty/disabled inventory when applicable;
- runner, plan, manifest, event, metrics, summary, state-hash, and ledger schema versions;
- experiment ID, cell ID, attempt ID, seed, requested ticks, exact controls, and log mode;
- wall-clock and monotonic start/end timestamps;
- actual terminal state, process return information, and validation result; and
- deterministic/counterbalanced execution order and dispatch position.

Preflight must fail closed on a dirty, unknown, untagged, or mismatched revision; plan/config/environment mismatch; unsafe output root; or unverifiable attempt history. `--verify` and resume must enforce the same evidence contract as post-run validation. Any code/configuration change after tagging requires a new reviewed commit/tag and cannot be mixed under the same frozen experiment identity.

## 11. Analysis, seeds, and execution order

### 11.1 Seed interpretation

Shared seeds are blocking variables that align initialization. Treatment-specific branches consume RNG differently, so they are not permanently matched downstream random shocks and must not be described as common trajectories after divergence.

- Report paired seed deltas wherever complete blocks exist.
- Also report unpaired/condition-level means, medians, dispersion, individual seed values, validation counts, and missingness.
- Use seed—not ticks, events, horizons, attempts, or agents—as the independent replicate unit.
- Never count a same-seed rerun, repeated horizon, diagnostic hash probe, or superseded attempt as independent evidence.

### 11.2 Execution order

Condition execution order must be deterministically randomized or counterbalanced within seed/horizon blocks using a frozen, recorded schedule. Record actual dispatch order and timestamps so runtime comparisons can inspect machine-load, thermal, and temporal order effects. Resume must preserve the schedule identity and record deviations rather than silently regenerating order.

### 11.3 Planned summaries

- Primary contrasts use the sign and eligibility rules in §4.
- Smoke summaries are engineering-only; S1 summaries are feasibility/manipulation-check evidence only.
- Biological endpoints use only deeply valid completed horizons and registered valid natural terminals.
- Computational summaries retain completed and censored attempt outcomes with explicit statuses.
- Produce run- and condition-level tables, paired-delta and condition-level summaries, population/faction trajectories, endpoint/cap-exposure plots, event-type composition, raid share/rate, manipulation checks, and runtime/output/memory versus state/event-volume plots.
- Report conditional simple effects separately from factorial main effects/interactions.
- Freeze the uncertainty method, multiplicity policy, primary/secondary hierarchy, analysis code/version, and any matrix-pruning rule before the relevant outcomes are inspected.
- Keep V1, S0, S1, P1, P2, and Full results separated by evidence tier and provenance.

Interpret runtime under the fixed output policy as end-to-end tractability. Covariation between events/state and runtime is not by itself a causal decomposition of logging, scanning, or simulation costs.

## 12. Timeout, missingness, attempts, and validation policy

- Timeout, cancellation, exception, crash, invalid artifacts, and quota breaches remain preserved as attempt-level tractability/audit evidence.
- Incomplete attempts are excluded from final biological endpoints and paired biological contrasts.
- Incomplete attempts are not silently dropped from computational reporting; status, elapsed time, completed ticks, output, and censoring reason remain visible where valid.
- No cancelled, timed-out, exception, invalid, or otherwise incomplete attempt may be resume-skipped as completed.
- A valid natural terminal is eligible only under the preregistered rule and deep validation; extinction is a biological endpoint, not generic missingness.
- A later attempt never deletes or overwrites an earlier attempt. Selection/supersession is explicit in the append-only ledger, and only one deeply valid attempt may be authoritative for a cell.
- If a selected attempt is later found invalid, selection is revoked explicitly; the evidence is preserved and no replacement is assumed.
- Same-seed attempts are never pooled as replicate evidence.

Deep validation must reject missing, empty, header-only when data rows are required, truncated, schema-invalid, nonmonotonic, wrong-tick, wrong-condition, wrong-config, wrong-plan, wrong-revision, unresolved-writer-failure, and internally inconsistent artifacts. It must accept a zero-event file only when the schema/output contract and run behavior make zero events valid.

## 13. Stop/go rules

Stop the active tier before another cell is dispatched when:

- process outcome or deep validation is noncompleted/nonaccepted;
- the expected horizon is not reached and no registered valid natural terminal applies;
- any effective factor, seed, tick, log mode, plan hash, commit, tag, environment, or schema differs from contract;
- deterministic same-condition/seed isolated-process probes disagree in state hash;
- an approved wall-time, byte, event, memory, or disk quota is breached or projected headroom is inadequate;
- unresolved write/flush failure or artifact corruption appears;
- event/state growth suggests the matrix, horizon, storage model, or quotas require redesign; or
- continuing would require a code or simulation-dynamics change during the frozen tier.

Every stop records cell, attempt, dispatch order, requested/final tick, terminal status, validation errors, artifacts, resource measurements, and reason. Diagnose and review before authorizing a new immutable attempt. A tier proceeds only through a written gate decision based on registered engineering/tractability criteria.

## 14. Exact execution sequence

1. Revise and review this plan.
2. Implement termination-aware manifests.
3. Implement deep design-conformance validation.
4. Implement fail-fast orchestration.
5. Implement immutable attempt/resume history.
6. Implement clean-tag and environment preflight.
7. Implement nonexecuting matrix expansion.
8. Add and pass failure-path tests.
9. Re-run adversarial review.
10. Draft the S0 experiment JSON.
11. Review matrix expansion and budgets.
12. Commit and tag exact run-ready state.
13. Confirm clean tree.
14. Request separate S0 authorization.
15. Run S0 only.
16. Analyze registered engineering outcomes.
17. Decide whether S1 is authorized.

Step 10 is blocked until the §9 placeholders have explicit provisionally approved values; Step 11 is the final cross-check of those budgets against the nonexecuting expanded matrix. No step implicitly authorizes the next.

## 15. Explicit non-goals

Core Replication V2 is not intended to:

- prove or imply sentience, consciousness, AGI, moral patienthood, or human-equivalent agency;
- pool V1 and V2 as one dataset;
- redefine or retroactively relabel historical V1 `no_combat`;
- claim publication quality from tick count or seed count alone;
- attribute the anti-stagnation intervention bundle's effect to one constituent mechanism;
- causally decompose text logging, structured I/O, flush-policy, scanning, and simulation-update costs within V2;
- call formal-combat-off/raids-off hostility-free;
- treat cap-limited trajectories as unbounded growth;
- treat policy availability as proof of realized exposure;
- count events, ticks, horizons, retries, or superseded attempts as independent replicates;
- optimize, rebalance, or otherwise change simulation dynamics during the frozen replication; or
- continue through validation, provenance, reproducibility, runtime, memory, event, or storage failures merely to complete a matrix.

## 16. Final recommendation

V2 scientific planning should continue. S0 is not yet authorized. Runner/verifier prerequisites must be implemented and tested first. The revised plan must receive another adversarial review before JSON creation. Full 10,000-tick execution remains out of scope.
