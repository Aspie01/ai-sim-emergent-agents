# AGENTS.md — Thalren Vale / AI Sandbox

## Mission

This repository contains the Thalren Vale emergent-agent simulation and its research
tooling. Optimize for:

1. Correct simulation semantics.
2. Deterministic and reproducible behavior.
3. Immutable, deeply validated research evidence.
4. Small, reviewable changes with focused regression tests.
5. Clear separation between implementation, engineering validation, pilot evidence, and
   confirmatory evidence.
6. Performance work supported by measurements rather than assumptions.

Do not trade research integrity or auditability for faster feature delivery.

## Current authorization boundary

`CORE_REPLICATION_V2_PLAN.md` is a draft implementation plan. It does **not** authorize
execution.

Until the user explicitly authorizes a later gate:

- Implement and test Core Replication V2 runner/verifier prerequisites only.
- Do not create an S0, S1, P1, P2, or Full experiment JSON.
- Do not launch S0, S1, P1, P2, Full, pilot, replication, or long-horizon cells.
- Do not treat the bounded 100-tick developer smoke command as authorization to run a
  research matrix.
- Do not freeze unresolved numeric budgets, endpoints, estimators, uncertainty methods,
  multiplicity rules, or matrix-pruning rules on the user's behalf.
- Do not tag a run-ready revision unless explicitly requested.
- Do not alter simulation dynamics merely to make V2 easier to execute or validate.
- Do not import or reorganize evidence into `LLM-Wiki/` unless explicitly requested.
- Do not imply that Core Replication V2 has produced evidence. It has not been executed.

The current implementation sequence is:

1. Termination-aware manifests.
2. Deep design-conformance and artifact validation.
3. Fail-fast orchestration.
4. Immutable attempt and resume history.
5. Clean-tag and environment preflight.
6. Nonexecuting matrix expansion.
7. Failure-path and reproducibility tests.
8. Adversarial review.
9. Only after separate approval: draft S0 configuration.

Completing one step never authorizes the next experimental gate.

## Source-of-truth order

When instructions or claims conflict, use this order:

1. The user's current explicit request.
2. A more-specific nested `AGENTS.md` for the files being changed.
3. This root `AGENTS.md`.
4. `CORE_REPLICATION_V2_PLAN.md` for Core Replication V2 work.
5. Current executable code and tests.
6. Validated manifests and raw artifacts tied to known code/configuration provenance.
7. Other current configuration and documentation.
8. Historical reports, README claims, old summaries, and unverified generated artifacts.

Documentation and generated summaries are not automatically authoritative. Verify
behavioral and research claims against current code, tests, and valid provenance.

The following legacy artifacts are known to be severely outdated and must not be used as
current evidence, defaults, baselines, fixtures, or documentation sources:

- `qtable_pop_300_300.json`
- `pop_equilibrium_summary.json`

Do not delete or migrate them unless the user explicitly requests that cleanup.

## Repository structure

- Core package: `src/thalren_vale/`
- Main layer orchestration: `src/thalren_vale/sim.py`
- Focused layer behavior: modules such as `economy.py`, `combat.py`, `factions.py`, and
  `metrics.py`
- Tests: `tests/`, organized to mirror behavior and features
- Batch and analysis entry points: repository root
- Bounded performance tools: `benchmarks/`
- Documentation and figures: `docs/` and `figures/`
- Generated evidence: `experiment_runs/`, `data/`, and `logs/`
- Separate nested repository: `LLM-Wiki/`

Keep layer-specific logic in its owning module. Keep `sim.py` focused on orchestration,
lifecycle, ordering, and cross-layer coordination. Do not turn it into a catch-all module.

Treat `LLM-Wiki/` as a separate repository with its own history and future nested
instructions. Do not accidentally include it in parent-repository bulk commits, cleanup,
formatting, or searches that mutate files.

## Development commands

Install contributor dependencies:

```bash
python -m pip install -e ".[dev,analysis,dashboard]"
```

Run the parent simulator test suite:

```bash
python -m pytest -q
```

Run a focused test first when possible:

```bash
python -m pytest -q tests/path/to/test_file.py
python -m pytest -q tests/path/to/test_file.py::test_specific_behavior
```

Run a bounded developer smoke test only when needed for the code change:

```bash
python -m thalren_vale --seed 42 --ticks 100 --log-mode metrics_only
```

Build distributions:

```bash
python -m build
```

Validate already-existing evidence without executing cells:

```bash
python run_experiments.py --plan <plan.json> --verify
```

For V2 tooling, prefer a nonexecuting expansion/preflight mode once implemented. It must
print the exact matrix, order, commands, contracts, paths, budgets, and provenance without
starting a simulation process.

Do not substitute a long run for a focused unit or integration test.

## Model-routing policy

The external Codex wrapper or operator must enforce routing. This file expresses policy;
it cannot switch models by itself. Use the exact model identifiers exposed by the active
Codex installation or API configuration. Never claim that a model performed or reviewed
work unless it actually did.

Do not silently downgrade to an older model family when a requested GPT-5.6 tier is
unavailable. Stop and report the unavailable model or use a user-approved fallback.

### GPT-5.6 Sol — consequential and high-risk work

Use `gpt-5.6-sol` for the hardest or most consequential tasks. Prefer its deepest
available reasoning mode when correctness matters more than latency.

Required for:

- Simulation semantics, tick ordering, state transitions, or layer interactions.
- Anti-stagnation, combat, raid, population, faction, economy, or resource behavior.
- RNG, seeding, state hashes, reproducibility, or parallelism.
- Experiment design, endpoint definitions, estimands, contrasts, or statistical claims.
- Runner lifecycle, process management, timeout, cancellation, resume, or fail-fast logic.
- Manifest, ledger, schema, persistence, provenance, or migration changes.
- Deep artifact validation and evidence selection or supersession.
- Security, secrets, external services, destructive operations, or data-loss risk.
- Cross-cutting architecture changes and major refactors.
- Performance changes that might alter timing, ordering, RNG consumption, or outputs.
- Adversarial review of Core Replication V2 prerequisites.
- Final review of consequential work initially produced by Terra, Luna, or the local
  model.

### GPT-5.6 Terra — default implementation model

Use `gpt-5.6-terra` as the normal default for substantive but bounded development work.

Appropriate for:

- Focused feature implementation with established requirements.
- Ordinary bug fixes with clear reproduction and expected behavior.
- Multi-file changes that do not alter research semantics or evidence contracts.
- Focused unit and integration tests.
- CLI, dashboard, analysis, and documentation work with bounded impact.
- Refactoring within one subsystem when invariants are already understood.
- Reviewing Luna or local-model output before it is accepted into ordinary code paths.
- Preparing a task for Sol review when escalation criteria are met.

Terra must escalate to Sol before approving any change listed in the Sol section.

### GPT-5.6 Luna — fast, low-risk work

Use `gpt-5.6-luna` for quick, inexpensive, and mechanically constrained tasks.

Appropriate for:

- Initial repository exploration and file discovery.
- Mechanical boilerplate.
- Small pure helper functions with explicit contracts.
- Localized type hints and docstrings.
- Straightforward test scaffolding.
- Formatting or repetitive cleanup limited to touched files.
- Documentation corrections that introduce no behavioral or research claims.
- Mechanical renames with fully discoverable references.
- Summarizing test output or assembling a bounded change inventory.

Luna must not make final decisions about simulation semantics, V2 evidence, schemas,
provenance, destructive actions, or research interpretation.

### Local Qwen fallback

`Qwen3-Coder-30B-A3B-Instruct-GGUF:UD-Q4_K_XL` may remain available as an offline
fallback for the same class of low-risk work assigned to Luna.

Local-model constraints:

- Use it only when local or offline execution is materially useful.
- Do not use it to replace Sol review.
- Terra must review ordinary code produced by it.
- Sol must review any output that becomes consequential or touches a Sol-only category.
- Local-model output must never approve itself.

### Escalation rules

Escalate Luna or Qwen work to Terra when:

- The change is no longer purely mechanical.
- More than a narrowly bounded subsystem is affected.
- A test failure is ambiguous or nondeterministic.
- The task requires design judgment rather than direct implementation.

Escalate Terra, Luna, or Qwen work to Sol when:

- The patch touches core simulation behavior or research evidence.
- RNG order, determinism, concurrency, persistence, or schema behavior may change.
- Runner lifecycle, resume, provenance, validation, or evidence selection is involved.
- The task expands beyond its original scope.
- The patch deletes, overwrites, migrates, or selects evidence.
- The model cannot clearly state the invariant being preserved.
- The proposed change has greater research or architectural impact than expected.

## Required task workflow

Before editing:

1. Read the relevant code, tests, configuration, this file, and the applicable plan section.
2. Run `git status --short`.
3. Preserve unrelated user changes; never reset or overwrite them.
4. Classify the task:
   - simulation semantics;
   - runner/lifecycle;
   - validation/provenance;
   - analysis/research design;
   - documentation;
   - low-risk maintenance.
5. Select or escalate to the required model tier.
6. Identify invariants and expected failure modes.
7. Prefer the smallest change that satisfies the task.

During implementation:

- Add or update a focused regression test with the behavior change.
- Use synthetic artifacts, `tmp_path`, deterministic seeds, and short subprocess
  timeouts.
- Do not make tests depend on multi-GB logs or existing research run directories.
- Do not launch an experimental tier.
- Do not silently broaden the patch into cleanup or refactoring.

Before completion:

1. Run the narrowest relevant tests.
2. Run the broader parent suite when warranted.
3. Review the diff for accidental artifact, evidence, or nested-repository changes.
4. Report what was and was not validated.
5. Clearly identify any remaining authorization gate.

## Coding style

- Use four-space indentation.
- Use `snake_case` for functions and variables.
- Use `PascalCase` for classes.
- Use `UPPER_CASE` for constants.
- Add type hints to new public helpers and changed public interfaces.
- Add concise docstrings where intent, invariants, or failure semantics are not obvious.
- Match nearby style; no repository-wide formatter or linter is currently enforced.
- Keep diffs focused and avoid mass formatting.
- Prefer explicit state and narrow interfaces over hidden global behavior.
- Avoid broad `except Exception` handling except at deliberate process boundaries.
- Preserve exception context and actionable diagnostics.
- Keep optional dashboards and external integrations out of the deterministic core path.
- Avoid adding dependencies when the standard library or current dependencies are
  sufficient.

## Simulation and determinism invariants

Unless a reviewed task explicitly changes them:

- A fixed seed and fixed effective configuration must reproduce the same state hash in the
  supported serial execution mode.
- Do not add RNG calls to instrumentation, validation, metrics, or logging code.
- Do not change RNG call order through unordered iteration, extra probing, or refactoring.
- Keep policy availability distinct from realized exposure.
- Formal combat and economy raids are independent controls.
- Disabling formal combat and raids does not create a hostility-free world.
- Historical V1 `no_combat` means formal combat off while raids remained on.
- Dead or removed agents must not continue acting.
- Populations, memberships, resources, and faction totals must remain internally
  consistent.
- No negative quantities are allowed unless an intentional mechanic explicitly permits
  them.
- End-of-tick metrics and `final_tick` must use a clearly defined authoritative point.
- Persistence round trips must not silently drop or reinterpret state.
- Evaluation code must not update training state unless explicitly configured to do so.

Any intentional determinism or semantic change requires:

- GPT-5.6 Sol review;
- a focused regression test;
- an explicit statement of research impact;
- documentation updates only after behavior is verified.

## Core Replication V2 condition semantics

V2 uses three independent factors:

- `A`: anti-stagnation intervention bundle availability;
- `C`: formal-combat policy availability;
- `R`: economy-raid policy availability.

The runner must generate exact controls from canonical condition identifiers. Do not trust
free-form prose or allow passthrough arguments to override runner-owned:

- seed;
- requested ticks;
- condition identity;
- log mode;
- anti-stagnation control;
- formal-combat control;
- raid control.

`disabled_layers` must use canonical ordering. Formal-combat availability must be recorded
explicitly or derived canonically and validated. Every V2 research cell uses buffered
`metrics_only` output.

Do not:

- call combat-off/raids-off “hostility-free”;
- treat enabled policy as proof of realized events;
- attribute the anti-stagnation bundle's total contrast to one constituent mechanism;
- infer scan opportunities or failed raid attempts from successful emitted raid events;
- causally attribute runtime changes to logging, scanning, or state updates without a
  separate fixed-workload benchmark or profiler study.

The full canonical matrix and exact CLI contract remain in
`CORE_REPLICATION_V2_PLAN.md`; do not duplicate or silently redefine them elsewhere.

## Runner and attempt-lifecycle requirements

V2 runner work must preserve these invariants:

### Termination-aware status

Every attempt records at least:

- `requested_ticks`;
- `final_tick`, defined as the last fully completed tick;
- `completed_ticks`;
- `termination_reason`;
- `result_status`;
- `completed_normally`;
- process return information;
- validation status.

Exit code zero alone is not completion evidence.

Distinguish at minimum:

- completed requested horizon;
- registered valid natural terminal;
- cancelled;
- timed out;
- exception/crash;
- invalid evidence;
- quota breach.

The current draft natural-terminal allowlist contains extinction only. Do not broaden it
without plan review.

### Immutable attempts

- Every execution attempt gets a unique immutable attempt directory.
- A retry never overwrites the prior manifest, stderr, summaries, or structured artifacts.
- Maintain an append-only attempt ledger.
- Preserve failed, cancelled, timed-out, invalid, and superseded attempts.
- Permit only one explicitly selected deeply valid attempt per cell.
- Supersession changes selection metadata; it never deletes history.
- A retry, repeated horizon, diagnostic probe, or superseded attempt is not a new
  scientific replicate.

### Fail-fast dispatch

Before dispatching another cell:

- persist the current attempt outcome;
- run deep validation;
- stop on the first nonaccepted result;
- record the batch stop reason and dispatch position.

Do not continue merely to complete the matrix.

### Safe resume

Resume may skip a cell only when its selected attempt deeply validates against the exact
frozen contract, including:

- plan snapshot and SHA-256;
- expected commit and tag;
- clean-tree status;
- seed, requested ticks, condition, and effective controls;
- log mode;
- schema versions;
- environment fingerprint;
- terminal status;
- artifact checksums and deep validation.

Cancelled, timed-out, exception, invalid, partial, stale, or mismatched attempts are never
resume-skipped as completed.

### No destructive overwrite

V2 must reject overwrite modes that erase attempt history. Do not retrofit destructive
cleanup into resume logic.

## Deep artifact-validation requirements

Validation must stream large files rather than loading them fully into memory.

Check, as applicable:

- expected files and schemas;
- valid headers;
- required non-header rows;
- tick monotonicity and coverage;
- exact final summary rows;
- manifest/artifact consistency;
- condition, seed, tick, plan, revision, and environment conformance;
- structured event and metrics schema versions;
- checksums and inventory;
- state hash;
- writer health and unresolved write/flush failures;
- terminal-state consistency.

Reject:

- missing, empty, truncated, or malformed required artifacts;
- header-only files when rows are required;
- nonmonotonic or wrong-tick data;
- wrong condition or effective controls;
- wrong plan hash, commit, tag, schema, or environment;
- unresolved writer failures;
- internally inconsistent summaries and manifests.

A zero-event artifact may be valid only when the schema is valid and zero events are
permitted by the run's exact contract and behavior.

`--verify` must enforce the same evidence contract as post-run validation. Verification
must never execute simulation cells.

## Required V2 failure-path tests

Runner/verifier changes require focused tests for all affected cases. The complete V2
prerequisite suite must cover:

- normal requested-horizon completion;
- registered extinction/natural terminal;
- cancellation and `KeyboardInterrupt`;
- ordinary exception and nonzero process exit;
- timeout;
- quota breach;
- truncated CSV or structured output;
- empty and header-only artifacts;
- zero-event valid artifacts where permitted;
- wrong final tick;
- wrong seed, condition, controls, log mode, plan hash, commit, or tag;
- dirty working tree;
- stale resume artifacts;
- immutable retry behavior;
- explicit selection and supersession;
- append-only ledger preservation;
- buffered write and flush failures;
- stop-on-first-nonaccepted behavior;
- deterministic isolated-process state hashes;
- nonexecuting matrix expansion that starts no child process.

Use short, synthetic, bounded tests. Do not disguise a real experiment as an integration
test.

## Provenance and preflight

Before any future V2 execution or resume, preflight must fail closed unless the frozen
contract requires and confirms:

- empty parent-repository `git status --short`;
- expected commit equal to `HEAD`;
- unique annotated run-ready tag resolving to `HEAD`;
- `code_dirty: false`;
- immutable plan snapshot and SHA-256;
- Python implementation, version, and absolute executable;
- OS, platform, and architecture;
- dependency or lockfile hashes;
- exact `PYTHONHASHSEED` policy;
- plugin policy and inventory;
- runner, plan, manifest, event, metrics, summary, state-hash, and ledger schema versions;
- experiment, cell, attempt, seed, tick, controls, and log-mode identities;
- wall-clock and monotonic timestamps;
- dispatch schedule identity and position;
- terminal process and validation outcome.

Do not invent missing provenance. Fail closed and report the missing field or mismatch.

## Research artifacts and data safety

Treat `experiment_runs/`, `data/`, and `logs/` as evidence-bearing generated data.

- Never overwrite validated evidence.
- Never delete evidence during routine development.
- Never run destructive cleanup without explicit approval.
- Never treat retries as independent replicates.
- Never pool V1 and V2.
- Keep V1 as historical pilot evidence.
- Keep S0 engineering-only and S1 feasibility/manipulation-check-only if later
  authorized.
- Keep P1, P2, and Full as separate tiers.
- Use seed, not ticks, events, agents, horizons, or attempts, as the replicate unit.
- Preserve individual seed values, missingness, validation status, and censoring status.
- Report timed-out and incomplete attempts as tractability evidence, not biological
  endpoints.
- Keep full narrative/debug logs and manual chronicles out of V2 research cells.
- Do not commit raw logs, chronicles, model artifacts, or large run directories.
- Do not copy an artifact larger than 50 MB into `LLM-Wiki/`; link it by path and
  provenance instead.
- Never commit secrets, `.env` files, API tokens, or private endpoints.

Do not use simple tick multiplication or condition means to project storage/runtime.
Use observed maxima, state/event growth, and nonlinear trends.

## Git and change discipline

Before work, inspect `git status --short`.

Never, unless explicitly requested:

- discard or overwrite unrelated user changes;
- run `git reset --hard`;
- run `git clean -fd`;
- force-push;
- rewrite published history;
- commit generated research evidence;
- commit or push;
- create or delete tags;
- mutate the nested `LLM-Wiki/` repository.

Commit subjects should be concise and imperative:

```text
<type>: <summary>
```

Examples:

```text
feat: add termination-aware attempt manifest
test: cover interrupted runner resume
docs: clarify V2 authorization gate
```

Keep commits logically scoped. Pull requests must describe:

- behavior changed;
- tests run;
- determinism impact;
- artifact or schema impact;
- research-design impact;
- migration or compatibility concerns;
- screenshots only for dashboard changes.

## Performance work

- Profile or benchmark before optimizing.
- Use bounded tools under `benchmarks/`.
- Record seed, configuration, workload, environment, and baseline.
- Preserve state hashes and semantic output unless behavior change is intentional.
- Measure absolute and relative changes.
- Distinguish end-to-end tractability from causal attribution.
- Treat concurrency as a determinism and evidence-integrity risk.
- Do not add instrumentation that changes RNG consumption or iteration order.
- Do not use historical README performance claims as current proof.

## Documentation and claims

- Use precise evidence-tier language.
- Label draft definitions as draft.
- Label unexecuted plans as unexecuted.
- Do not promote secondary or exploratory outcomes to primary after inspection.
- Do not call cap-limited growth unbounded growth.
- Do not imply sentience, consciousness, AGI, moral patienthood, or human-equivalent
  agency.
- Do not describe shared seeds as permanently matched downstream trajectories after
  condition-specific divergence.
- Separate policy availability from realized exposure.
- Separate historical pilot evidence from future V2 evidence.
- Cite raw manifests and validated artifacts rather than unsupported summaries.

## Completion report

At the end of a task, report:

1. What changed and why.
2. Files changed.
3. Tests and checks run, with results.
4. Checks not run, with reasons.
5. Determinism, schema, provenance, persistence, or research-impact effects.
6. Generated artifacts and their locations.
7. Which GPT-5.6 tier performed the work, whether Sol review was required, and whether it occurred.
8. Remaining authorization gates, assumptions, or unresolved risks.

Do not claim success when relevant validation failed or was not performed.
