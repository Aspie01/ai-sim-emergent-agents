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
| `tests/test_coalition_dialects.py` | Snapshot provenance/freshness, exact contexts/counters/rates, transactional isolation, summaries, one-pass complexity, lifecycle vocabulary persistence | Language contact, inheritance, grammar, or research-ready dialect metrics |
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
python -m pytest -q tests/test_language_evolution.py tests/test_language_interaction_hooks.py
python -m pytest -q tests/test_artifact_validation.py tests/test_experiment_runner.py
python -m pytest -q tests/test_run_termination.py tests/test_reproducibility.py
```

These commands are engineering verification. They do not launch S0/S1/P1/P2/
Full tiers and must not be reported as experimental evidence.

## Determinism evidence

The suite uses deterministic seeds, subprocess isolation, canonical state
hashes, reset tests, and pinned disabled-path hashes. It also checks that
language/coalition instrumentation does not consume unrelated RNG or alter
disabled baselines.

This supports implementation reproducibility under the tested environment and
contracts. It does not seal:

- a clean annotated tag;
- an environment/dependency fingerprint;
- plugin inventory;
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
- final language research contracts or planned future language milestones.

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
