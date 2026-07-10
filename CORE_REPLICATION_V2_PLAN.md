# Core Replication V2 Plan

**Status:** Draft — not yet executed  
**Authorization:** This document authorizes no experiment run by itself. The design, budgets, stop conditions, and later draft experiment JSON must be reviewed and explicitly approved before execution.

## 1. Purpose

Core Replication V2 is intended to replace the historical pilot as the project's clean, reproducible long-horizon evidence base. It should test the original persistence and viability questions against a tagged post-fix code revision while separating formal combat from economy raids.

V2 will use:

- the seeded Layer 1 serial reproducibility fix;
- `metrics_only` logging;
- explicit formal-combat control;
- explicit economy-raid control;
- buffered structured event writes;
- shared seeds across conditions;
- per-run validation and state hashes; and
- a clean Git commit and tag with `code_dirty: false` provenance.

V2 is not merely a longer run. It is a provenance and design correction: the conditions must have unambiguous meanings, computational costs must be bounded before scaling, and the exact matrix must be frozen before evidence collection.

## 2. Relationship to prior evidence

| Dataset | Role | What it supports | Important limitation |
|---|---|---|---|
| `core-replication-v1` | Historical pilot | Validated 15/15-run evidence that anti-stagnation, formal combat removal, population regulation, and tractability merit study | Dirty-worktree provenance; predates the seeded Layer 1 serial fix; historical `no_combat` left economy raids enabled |
| `logging-ablation-v1` | Partial bounded benchmark | Evidence that output policy matters and that future research should avoid giant narrative logs | Incomplete/partial, short-horizon, and not publication-grade; it does not isolate every runtime cause |
| `raid-control-pilot-v1` | Implementation and control validation | Confirms independent combat/raid controls, preserved historical semantics, metrics-only artifacts, and short-run interaction signals | Only 100/250 ticks and three seeds; not long-horizon evidence; dirty-worktree provenance |
| `core-replication-v2` | Future clean replication | Intended post-fix, tagged evidence for long-horizon comparisons and computational tractability | Not yet run; no claims may cite it until artifacts validate |

V1 and V2 must remain separate datasets. V1 may motivate hypotheses and provide historical context, but it must not be pooled with V2 as though all runs came from the same code, configuration semantics, or provenance regime.

## 3. Main research questions

1. Does anti-stagnation improve long-horizon population persistence and viability after the seeded determinism fix?
2. What are the separate effects of formal combat and economy raids on population regulation, faction formation, event volume, and computational cost?
3. Does removing all hostile coercion produce different outcomes from removing formal combat while leaving raids enabled?
4. When raids remain enabled, does formal combat regulate the faction and raid processes that expand after formal combat is removed?
5. When formal combat remains enabled, how does disabling economy raids affect wars, survival, population, and faction scaling?
6. How much of the historical `no_combat` explosion is associated with raids, formal-combat removal, growing population/faction state, or logging and structured-event I/O?
7. Are observed effects consistent across shared seeds, or dominated by a small number of trajectories?
8. At what horizons do conditions enter extinction, near-extinction, stable persistence, or unbounded-growth regimes?

The viability definition and any near-extinction threshold must be specified before the pilot-v2 tier. Runtime observations alone must not be described as emergent complexity without profiling or a design that isolates I/O from state-update work.

## 4. Proposed experimental matrix

The three controlled factors are:

- **A — Anti-stagnation:** on or off.
- **C — Formal combat:** on or off.
- **R — Economy raids:** on or off.

Historical compatibility requires that formal combat and raids remain independent. In particular, disabling formal combat must not silently disable raids.

### Practical minimal matrix

| Condition | Anti-stagnation | Formal combat | Raids | Primary role |
|---|---:|---:|---:|---|
| `baseline` | on | on | on | Reference condition |
| `no_antistag` | off | on | on | Direct replication of the anti-stagnation contrast |
| `no_formal_combat_raids_on` | on | off | on | Unambiguous successor to historical `no_combat` |
| `combat_on_raids_off` | on | on | off | Isolates raids while preserving formal combat |
| `no_hostility` | on | off | off | Removes both formal combat and raids |

This five-condition matrix is the recommended practical minimum. It reproduces the two central V1 contrasts with corrected naming and adds the two conditions required to distinguish formal combat from raids. It estimates hostility effects while anti-stagnation is enabled, but it cannot estimate how anti-stagnation interacts with every hostility regime.

### Expanded factorial matrix

Add these conditions to complete the 2 × 2 × 2 design:

| Additional condition | Anti-stagnation | Formal combat | Raids | Why include it |
|---|---:|---:|---:|---|
| `no_antistag_no_combat_raids_on` | off | off | on | Tests whether anti-stagnation moderates the formal-combat-removal regime |
| `no_antistag_combat_on_raids_off` | off | on | off | Tests whether anti-stagnation moderates raid removal |
| `no_antistag_no_hostility` | off | off | off | Tests anti-stagnation without either hostile mechanism |

The expanded eight-condition matrix supports all main effects and interactions. Its cost is 60% higher than the five-condition minimum and some cells may enter extreme-growth regimes. The expanded matrix is appropriate for the smoke tier. Before pilot-v2, select either the five-condition minimum or the complete factorial based on tractability and the preregistered scientific priority—not on which short-run effect looks most exciting.

## 5. Run scale options and gates

| Tier | Horizon | Seeds | Purpose | Gate to proceed |
|---|---:|---:|---|---|
| Smoke | 100–250 ticks | 2–3 shared seeds | Validate configuration, manifests, hashes, artifact policy, matrix semantics, and rough event/runtime growth | Every cell validates; repeated hash probe passes; no unexpected output class; projected pilot cost fits an approved budget |
| Pilot-v2 | 1,000–2,500 ticks | 5 shared seeds | Estimate medium-horizon dynamics, variance, nonlinear scaling, and whether the matrix is tractable | All cells validate; effects are interpretable; event/runtime/storage projections support a full tier; no redesign is required |
| Full-v2 | 10,000 ticks | 10 or more shared seeds | Long-horizon replication with stronger between-seed evidence | Separate explicit approval after pilot analysis, frozen analysis plan, sufficient disk/time budget, and clean tagged provenance |

Do not treat multiple horizons or same-seed reruns as independent replicates. If a later valid attempt supersedes an earlier attempt, mark the earlier attempt `superseded` and exclude it from inferential counts.

### Stop/go policy between tiers

1. Complete and validate the entire approved tier before deciding to scale.
2. Produce tier-level runtime, output, event-growth, and outcome summaries.
3. Recalculate projected cell and total costs using the slowest and largest observed cells, not only condition means.
4. Record a written go/no-go decision and any matrix change before creating the next tier's immutable plan.
5. Treat a matrix change as a new design version; do not silently mix changed conditions into the earlier tier.

## 6. Recommended default

Do not jump directly to 10,000 ticks. Start with a clean-tag smoke tier using `metrics_only` and the same two or three seeds in every condition. The expanded matrix is affordable enough to test all control combinations at smoke scale; the pilot-v2 matrix should then be frozen after reviewing tractability.

If smoke passes, begin pilot-v2 at 1,000 ticks with five shared seeds. Extension to 2,500 ticks requires its own go decision. Full-v2 should be considered only after pilot-v2 establishes that the slowest conditions, event volumes, and storage projections fit an explicitly approved budget.

## 7. Metrics and artifacts to collect

Each final validated run should provide:

- final and peak population;
- minimum population and extinction/final-tick status where available;
- final and peak active faction count;
- structured event count and event-type counts;
- raid event count and raid share of structured events;
- formal war count and war-duration summaries where available;
- deaths and births;
- output bytes, including structured-versus-text breakdown;
- elapsed seconds and ticks per second;
- peak memory if available without intrusive instrumentation;
- final tick count and explicit termination/result terminology;
- final state hash;
- manifest and configuration provenance; and
- artifact validation status and validation errors, if any.

Termination/result values should distinguish at least `completed`, `wall_clock_limit`, `exception`, `invalid_output`, `cancelled`, and `superseded`. Only final validated runs count toward the research dataset.

## 8. Runtime and storage safeguards

- Use `metrics_only` for every research cell.
- Do not create full raw narrative/debug logs or manual chronicles.
- Retain required structured metrics, events, beliefs, summaries, and manifests according to the verified output policy.
- Monitor structured event CSV growth because metrics-only output can still become large under raid/event explosions.
- Copy no artifact over 50 MB into the LLM Wiki; link large research artifacts by path and provenance instead.
- Set a per-cell timeout in every experiment plan. Use a provisional smoke ceiling of 15 minutes per cell; derive later ceilings from smoke measurements and approve them before scaling.
- Execute in resumable stages and write result/index state after every cell. Resume valid cells instead of overwriting them.
- Validate each cell immediately. Stop the tier on the first unexplained invalid result rather than launching the remaining queue blindly.
- Before each tier, estimate worst-case output and require free disk space comfortably above that projection, including room for retries. A minimum two-times projected headroom is recommended.
- Monitor tick throughput, event count, output bytes, and available disk between cells without reading giant logs into memory.
- Never count timeout, cancelled, invalid, or superseded attempts as independent evidence.

## 9. Provenance requirements

Before any V2 run:

1. Commit reviewed raid control, buffered writing, tests, this design, and the approved experiment plan.
2. Confirm `git status --short` is empty, including after generating the plan file.
3. Run the parent test suite and record its result.
4. Create an annotated tag for the exact run-ready commit.
5. Confirm the tag resolves to the same commit recorded by the runner.
6. Require every run manifest to record `code_dirty: false`.

Each manifest or experiment index should record:

- experiment ID and condition name;
- commit hash and tag;
- dirty-worktree flag;
- Python version and platform when supported;
- dependency/requirements identity when supported;
- complete effective configuration;
- disabled layers and explicit `raids_enabled` value;
- `log_mode`;
- seed and requested ticks;
- seeded serial execution mode and relevant hash-seed policy;
- schema versions;
- start/end timestamps, elapsed time, and result status;
- required and optional artifacts; and
- state hash and validation result.

The reviewed JSON plan should receive a checksum or be committed unchanged before execution. Any code or configuration change after tagging invalidates the run-ready state and requires a new commit/tag or a documented restart.

## 10. Analysis plan

### Primary comparisons

- `baseline` versus `no_antistag`.
- `baseline` versus `no_formal_combat_raids_on`.
- `baseline` versus `combat_on_raids_off`.
- `baseline` versus `no_hostility`.
- `no_formal_combat_raids_on` versus `no_hostility` to estimate the raid contrast when formal combat is off.
- `combat_on_raids_off` versus `no_hostility` to estimate the formal-combat contrast when raids are off.
- If the expanded matrix is used, estimate anti-stagnation contrasts within all four combat/raid combinations and report factor interactions.

### Statistical unit and summaries

- Use the seed as the independent unit; events and ticks are repeated observations within a run, not independent replicates.
- Pair conditions by shared seed and report per-seed deltas alongside condition means, medians, dispersion, and uncertainty intervals appropriate to the seed count.
- Keep smoke analyses descriptive. Five-seed pilot analyses remain pilot-level and should emphasize effect consistency and uncertainty rather than thresholded significance.
- Predefine viability, near-extinction, and persistence outcomes before pilot-v2.
- Analyze only final validated attempts and keep V1 separate from V2.

### Tables and figures

Generate:

- condition-level and run-level summary tables;
- paired-seed comparison tables;
- population and faction trajectories by condition;
- final/peak population and faction dot or interval plots;
- paired-delta plots for primary comparisons;
- event-type composition and raid-share plots;
- war, raid, death, and birth comparisons;
- elapsed-time, ticks-per-second, output-size, and peak-memory plots; and
- runtime/output plots against population, faction count, and event volume.

### Interpretation boundaries

- Attribute differences only to the explicitly manipulated configuration under the tagged code revision.
- Do not infer that runtime is purely emergent complexity when state size and I/O both vary.
- Do not treat high event counts as additional replication.
- Do not generalize beyond the tested horizons and seeds.
- Label unplanned analyses exploratory and distinguish them from frozen primary comparisons.

## 11. Stop conditions

Pause the active tier and do not automatically rerun when any of the following occurs:

- any required artifact is missing, corrupt, or fails validation;
- a manifest reports `code_dirty: true` when a clean run is expected;
- a repeated same-seed/config reproducibility probe produces a different state hash;
- a cell exceeds the agreed wall-clock threshold;
- output growth exceeds the per-cell or tier storage budget;
- projected remaining output would violate required disk headroom;
- event growth is explosive enough that the matrix, event representation, or horizon needs redesign;
- the effective combat, raid, anti-stagnation, logging, seed, or tick configuration differs from the plan;
- an exception, cancellation, or machine interruption makes final state validity uncertain; or
- continuing would require code changes during the replication.

For a stop, record the exact condition, seed, tick, status, artifacts, and reason. Diagnose before deciding whether a later attempt is justified. A later valid attempt may supersede the failed attempt, but never converts it into an additional replicate.

## 12. Recommended execution sequence

1. Write this draft design document. **Current step only.**
2. Review and revise the research questions, matrix, viability definition, budgets, and stop/go thresholds.
3. Commit the approved implementation and design, confirm tests pass, and establish clean provenance.
4. Create a draft experiment JSON that exactly represents the reviewed smoke tier; review it without executing it.
5. Tag the final run-ready commit and verify the clean status, tag, plan checksum, available disk, and runner dry-run output.
6. Run only the smoke tier.
7. Validate every smoke artifact and produce the predefined smoke analysis.
8. Record a written decision on the pilot-v2 matrix, horizon, timeouts, and storage budget.
9. If approved, create and run the 1,000-tick pilot-v2 tier with five shared seeds.
10. Analyze pilot-v2 and decide whether a separately approved 2,500-tick stage is warranted.
11. Freeze the full analysis plan and calculate full-v2 worst-case runtime/storage requirements.
12. Only then consider a separately authorized 10,000-tick, 10-or-more-seed full-v2.

No step should implicitly authorize the next one.

## 13. Explicit non-goals

Core Replication V2 is not intended to:

- prove or imply sentience, consciousness, moral patienthood, or human-equivalent agency;
- claim publication-grade inference from smoke runs or small seed counts;
- pool V1 and V2 as one homogeneous dataset;
- redefine or retroactively relabel historical `no_combat` runs;
- make formal combat automatically control economy raids;
- optimize or rebalance simulation behavior during the replication;
- use giant narrative logs as the primary research record;
- treat same-seed reruns or multiple horizons as independent evidence; or
- continue through validation, reproducibility, runtime, or storage failures merely to complete a matrix.

## 14. Final recommendation

Create and review the research plan now, then prepare—but do not execute—a draft smoke-tier JSON against a clean tagged commit. Run only the 100–250-tick smoke tier first with shared seeds and `metrics_only` logging.

Do not run a 10,000-tick Core Replication V2 until the smoke and pilot-v2 results demonstrate valid artifacts, deterministic hashes, interpretable condition behavior, and acceptable worst-case runtime, event volume, memory, and storage cost.
