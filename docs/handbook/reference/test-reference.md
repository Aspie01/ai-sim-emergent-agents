# Test Reference

## Running the suite

`pyproject.toml` configures:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Therefore the normal parent suite is:

```bash
python -m pytest -q
```

It collects tests under `tests/` and excludes the root-level
`test_parse_logs.py`. Run that legacy parser suite explicitly when needed:

```bash
python -m pytest -q test_parse_logs.py
```

Compilation and patch hygiene checks are separate:

```bash
python -m compileall -q src run_experiments.py tests
git diff --check
```

## Suite map

| Test file | Primary evidence | What it does not prove |
| --- | --- | --- |
| `tests/test_config.py` | CLI/effective configuration validation, normalization, defaults, provenance statuses/notices | Scientific suitability of any control or condition |
| `tests/test_simulation_state.py` | Runtime reset and state-collection invariants | Long-horizon lifecycle correctness |
| `tests/test_antistagnation.py` | Bounded cadence/gating behavior for anti-stagnation mechanisms | Effectiveness or causal impact in research outcomes |
| `tests/test_raid_control.py` | Formal combat and economy-raid control separation | A no-hostility condition or exposure denominators |
| `tests/test_raid_control_pilot.py` | Synthetic pilot-control wiring and bounded scenarios | New pilot evidence; test execution is not a research run |
| `tests/test_social_identity.py` | Stable social identity/admission/reset invariants | Semantic correctness of display names as artifact IDs |
| `tests/test_social_relationships.py` | Directed relationship validation, bounds, decay, and reset | Population-level social conclusions |
| `tests/test_social_interaction_hooks.py` | Exact committed aid/trade relationship hooks and rollback isolation | Every possible future interaction hook |
| `tests/test_social_partner_choice.py` | Bounded relationship-biased partner ordering and disabled behavior | Long-run network effects |
| `tests/test_informal_coalitions.py` | Coalition graph inputs, persistence/lifecycle, hashing, reset, complexity regressions | Language-driven coalition feedback, which is intentionally absent |
| `tests/test_coalition_dialects.py` | Snapshot provenance/freshness, exact contexts/counters/rates, transactional isolation, summaries, one-pass complexity, lifecycle vocabulary persistence | Inheritance, grammar, or research-ready dialect metrics |
| `tests/test_language_contact.py` | Different-coalition qualification, positive acquisition, bounded exposure/provenance, promotion precedence, rollback, summaries, one-pass complexity and causal isolation | Population-level contact effects or research-ready convergence endpoints |
| `tests/test_intergenerational_language.py` | Sole post-admission birth hook, exact-once sentinel, partial comprehension, parent ordering/salience, duplicate/competing forms, borrowed-form isolation, rollback, saturation, summary complexity, hashing and reset | Long-run intergenerational effect sizes, lexical mutation, genealogy, or research-ready retention endpoints |
| `tests/test_lexical_evolution.py` | Authentic post-transfer opportunities, pinned SHA-256 vectors, actual descendant emission, provenance copying/coexistence, collisions, depth cap, synchronized saturation, transactionality, one-pass summary and corrected channel/borrowed-source carriers, hashing/reset and containment | Long-run lexical drift, cognate reconstruction, phonology, morphology, grammar, or research-ready lexical endpoints |
| `tests/test_compositional_protolanguage.py` | Structured `(resource, modality)` meanings, systematic morpheme composition, bounded lengths, hashing and reset | Productive syntax, or research-ready compositionality endpoints |
| `tests/test_grammar_evolution.py` | Constituent order inferred from minimal pairs, adoption threshold, disabled-state guard, hashing and reset | Parsing, or that agents comprehend order rather than record it |
| `tests/test_language_coevolution.py` | Bounded intelligibility reward/penalty fed into partner choice, gating, hashing and reset | Population-level coevolution effects or research-ready endpoints |
| `tests/test_coalition_intelligibility.py` | Coalition edges gated on mutual intelligibility, dependency normalization, runner rejection | That intelligibility-gated coalitions are more realistic or better |
| `tests/test_production_trial.py` | Interval-scheduled runner-up production, adoption-deadlock behaviour, determinism | Long-run adoption dynamics or research-ready endpoints |
| `tests/test_faction_social_model.py` | Faction selection between the legacy trust model and `Relationship` records, threshold and normalization | Which social model is more faithful; both are engineering-only |
| `tests/test_feature_registration.py` | Structural coverage: every control family declared, and every declared hook reached by the dispatch site that matters | Behavioural correctness of any individual family |
| `tests/test_technology.py` | Research selection and its ordering properties, resource pooling and cost deduction, prerequisites, duration discount, and the bonuses `combat.py` reads | Whether the tech tree's costs, tiers, or bonus magnitudes are well balanced |
| `tests/test_language_evolution.py` | Language states, signals, learning, reinforcement, forgetting, pruning, transactionality | Scientific claims about language emergence |
| `tests/test_language_interaction_hooks.py` | Exact authentic committed-transfer communication hooks | Proximity/background conversation, which is intentionally absent |
| `tests/test_language_reproducibility.py` | Language determinism, hashing, RNG/state isolation | General reproducibility across unrecorded environments/plugins |
| `tests/test_events.py` | Typed/legacy journal exact-once behavior, token safety, event writer buffering/recovery | Completeness of every narrative regex classification |
| `tests/test_log_modes.py` | Required structured outputs in every mode, optional-output suppression, state-hash equivalence | No runtime overhead; no such performance conclusion follows |
| `tests/test_reproducibility.py` | Same-seed isolated-process hashes, different-seed divergence, configuration provenance, disabled-state fail-closed hashing | V2-ready provenance or cross-platform bit-for-bit guarantees |
| `tests/test_run_termination.py` | Requested horizon, extinction, cancellation, exceptions, writer/finalization failure, manifest-last publication, pinned hashes | Runner immutable attempts, fail-fast dispatch, or safe resume |
| `tests/test_artifact_validation.py` | Streaming deep validation, schema/domain/cadence/cross-file checks, bounded diagnostics, readiness gates | Correctness of scientific endpoints or source semantics not represented in artifacts |
| `tests/test_experiment_runner.py` | Plan/flag rejection, fresh-root containment, symlink/replacement defenses, timeout/SIGINT classification, frozen cells, read-only nonempty-root rejection | Functional resume, overwrite, attempt ledger, fail-fast, or V2 execution |
| `tests/test_plugin_security.py` | Bridge snapshot immutability/staleness and rejection of plugin-defined command subclasses | Process sandboxing or safety of untrusted plugin Python |
| `tests/test_benchmark.py` | Deterministic bounded benchmark harness shape/output and threshold plumbing | Current performance targets or causal attribution without actually running a controlled benchmark |
| `test_parse_logs.py` | Legacy narrative parser filename, line-pattern, file, sorting, and CLI behavior | Canonical structured artifact validity; excluded from default suite |

## Focused commands

Use focused tests before the full suite when changing one subsystem:

```bash
python -m pytest -q tests/test_coalition_dialects.py
python -m pytest -q tests/test_language_contact.py
python -m pytest -q tests/test_intergenerational_language.py
python -m pytest -q tests/test_lexical_evolution.py
python -m pytest -q tests/test_language_evolution.py tests/test_language_interaction_hooks.py
python -m pytest -q tests/test_compositional_protolanguage.py tests/test_grammar_evolution.py
python -m pytest -q tests/test_language_coevolution.py tests/test_coalition_intelligibility.py
python -m pytest -q tests/test_production_trial.py tests/test_faction_social_model.py
python -m pytest -q tests/test_feature_registration.py
python -m pytest -q tests/test_artifact_validation.py tests/test_experiment_runner.py
python -m pytest -q tests/test_run_termination.py tests/test_reproducibility.py
```

These commands are engineering verification. They do not launch S0/S1/P1/P2/
Full tiers and must not be reported as experimental evidence.

## Determinism evidence

The suite uses deterministic seeds, subprocess isolation, canonical state
hashes, reset tests, and pinned disabled-path hashes. It also checks that
language/coalition/dialect/contact/intergenerational/lexical instrumentation
does not consume unrelated RNG or alter disabled baselines. Lexical tests also
pin trigger/substitution derivation and prove independence from
dialect/contact feature gates and `PYTHONHASHSEED`.

This supports implementation reproducibility under the tested environment and
contracts. Every run manifest now records a `code` block with commit, dirty
status, and the annotated tag naming `HEAD` exactly (`null` when no tag does),
plus an `environment_fingerprint` over interpreter, platform, and plugin
digests, so those are no longer unrecorded. What is still unsealed:

- a *clean* annotated tag — the tag and dirty status are recorded, never
  enforced, and nothing refuses to run on a dirty tree;
- a dependency or lockfile hash, which `environment_fingerprint` deliberately
  excludes;
- every platform or Python implementation;
- scientific replicate independence.

## Artifact and lifecycle evidence

Validator tests use synthetic temporary artifacts rather than existing
research roots. They cover normal horizon completion, registered extinction,
noncompleted manifests, malformed/truncated/header-only files, zero-event
policy, belief cadence/cardinality, writer health, checksums, path containment,
cross-artifact totals, and bounded memory/diagnostics.

Runner tests use temporary roots and tiny child processes. They prove current
fresh-root safety and explicit failure classifications. They also intentionally
prove that every nonempty root is rejected unchanged, including under
`--resume` or `--overwrite`.

## Structural coverage checks

Most tests here assert behaviour: given this input, the code does that. Three
milestones in a row shipped a defect those tests could not see, because each
mechanism reached the layer its author was thinking about and silently missed
the next one out — composition reached `communicate` but not one barter
branch; grammar reached the hash but not the disabled-state guard; three
control families reached artifact validation but not the V2-readiness veto.
The suite stayed green every time.

`tests/test_feature_registration.py` asserts coverage instead. For every
control family it checks that the family is declared, that each declared hook
exists, and that each hook is actually reached by the dispatch site that
matters:

| Layer | Requirement |
| --- | --- |
| Declaration | Every `*_controls_status` manifest key has a registration entry, and no entry is stale |
| Disabled-state guard | `canonical_state_hash` calls the family's pristine guard |
| Artifact validation | `_validate_strict` calls the family's configuration validator |
| Runner containment | Both `_freeze_cell` and `load_plan` call the family's rejector |
| Readiness gate | The family's status key reaches `_readiness_issues` |
| Economy threading | No call site drops an owner family its callee accepts |

Each is verified by recreating the corresponding historical defect and
confirming the check fails. The economy-threading check reproduces the
original partner-bias omission by name and line.

`docs/handbook/validate_handbook.py` applies the same idea to documentation.
It maps each milestone to the configuration gate whose presence in source
proves the mechanism exists, then reports a milestone documented as planned
while its gate exists, a milestone whose pages contradict each other, a
milestone slug that appears in the handbook without being declared, and a
declared gate that no longer exists in `SimulationConfig`. Checking pages
against each other alone would not catch a status every page agrees on and
source disproves. Its milestone pattern matches any `-v<n>` suffix, not only
`-v1`; anchoring on `-v1` had silently exempted every milestone past the first
revision of a line.

## Important coverage gaps

Current tests do not establish:

- a functional immutable attempt/resume/supersession lifecycle;
- stop-on-first-failure batch dispatch;
- complete V2 clean-tag/environment/plugin preflight;
- V2 matrix expansion, budgets, quotas, or research execution;
- a dashboard state-reset contract or every dashboard field;
- RA tracker artifact validity;
- mythology/network-provider reproducibility;
- plugin process isolation;
- performance claims without an authorized controlled benchmark;
- final language research contracts. Language coevolution, language research
  readiness, coalition intelligibility, and production trials are implemented
  and covered by the files above; what remains unbuilt is the analysis
  contract, not the mechanisms.

Each accepted milestone recorded its own full-suite result in
[HANDBOOK_STATUS](../HANDBOOK_STATUS.md) at the time of acceptance. No total is
repeated here, because the suite grows with every milestone and a number copied
into this page is stale the moment the next test lands. Run `python -m pytest
-q` for the current count. Whatever it reports verifies tested software
contracts only; it is not a simulation run, a research tier, or a scientific
result.

## Evidence standard for documentation

A passing test supports only the behavior asserted by that test. It does not
override contradictory production source without investigation, and it does
not turn an engineering mechanism into a scientific conclusion. Each handbook
system page lists both source and tests so a reviewer can trace the claim.

## Implementation evidence

- Test configuration: [`pyproject.toml`](../../../pyproject.toml)
- Default tests: [`tests/`](../../../tests)
- Legacy parser test: [`test_parse_logs.py`](../../../test_parse_logs.py)
- Related operations: [Operating Thalren Vale safely](../getting-started/operations.md)
- Handbook drafting did not execute tests; final handbook verification is
  reported centrally in handbook status/completion records.
