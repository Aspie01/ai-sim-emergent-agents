# Handbook status

## Recorded revision

- Handbook: Living Technical Handbook v0.1
- Documented branch: `feature/lexical-evolution-v1`
- Base `HEAD` commit: `2855bf15a77dffc599f6a0f4ac08721f79a379d4`
- Documented implementation state: approved Lexical Evolution v1 source and
  tests in the uncommitted branch working tree
- Update date: 2026-07-28 (Canada/Eastern)
- Working-tree caveat: the commit identifies the base revision and does not by
  itself contain Lexical Evolution v1. The feature implementation, tests, and
  handbook updates remain uncommitted branch work until the final feature
  commit. Existing non-handbook changes are intentionally preserved.

This handbook is authoritative for the recorded branch working-tree state and
base commit described above. It remains explicitly versioned and must be
refreshed when current behavior changes.

## Source-of-truth hierarchy

1. Executed current code and bounded observed behavior.
2. Passing current tests.
3. Current executable source.
4. Active schemas and configuration validation.
5. Current authoritative project documentation.
6. Active plans and handoffs.
7. Comments and docstrings.
8. Historical plans, reports, logs, and generated material.

When these conflict, the handbook uses executable behavior, records the discrepancy, and does not silently rewrite historical evidence.

## Systems documented

| System | Status recorded in the handbook |
| --- | --- |
| Initialization, reset, world and resources | Implemented but experimental |
| Inhabitants, needs, survival, reproduction and death | Implemented but experimental |
| Beliefs, formal factions and settlements | Implemented but experimental |
| Economy, aid, trade, raids and legacy trust | Implemented but experimental |
| Directed social memory and partner bias | Implemented but experimental; Disabled by default; Engineering-only |
| Informal coalitions | Implemented but experimental; Disabled by default; Engineering-only |
| Endogenous Language v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Coalition Dialects v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Language Contact v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Intergenerational Language v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Lexical Evolution v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Combat, technology, diplomacy and religion | Implemented but experimental |
| Structured events, metrics, manifests and deep validation | Stable and verified engineering infrastructure |
| Dashboard, RA tracker and mythology | Optional/diagnostic; mythology and RA disabled by default |
| Plugins | Implemented causal extension system; not sandboxed or provenance-sealed |
| Generic experiment runner | Fresh-root engineering runner; not V2 research-ready |

## Systems absent or planned

| Capability | Status |
| --- | --- |
| Active informal-coalition merging | Planned, not implemented |
| Biological age/senescence/family model | Planned, not implemented only as a possibility; no active contract exists |
| Checkpoint, PRNG restoration or event replay | Planned, not implemented |
| Immutable experiment attempts, ledger, selection and safe resume | Planned, not implemented |
| Clean-tag/environment/plugin preflight and V2 matrix orchestration | Planned, not implemented |
| `feature/compositional-protolanguage-v1` | Planned, not implemented |
| `feature/grammar-evolution-v1` | Planned, not implemented |
| `feature/language-coevolution-v1` | Planned, not implemented |
| `feature/language-research-readiness-v1` | Planned, not implemented |

No final language research hypotheses, estimands, metrics, evidence contracts, or readiness claims are defined here.

## Language roadmap

Completed engineering implementations:

- `feature/endogenous-language-v1`
- `feature/coalition-dialects-v1`
- `feature/language-contact-v1`
- `feature/intergenerational-language-v1`
- `feature/lexical-evolution-v1`

Planned, not implemented:

- `feature/compositional-protolanguage-v1` — **Planned, not implemented**
- `feature/grammar-evolution-v1` — **Planned, not implemented**
- `feature/language-coevolution-v1` — **Planned, not implemented**
- `feature/language-research-readiness-v1` — **Planned, not implemented**

The next milestone is `feature/compositional-protolanguage-v1`: **Planned, not implemented**.

## Current branch work

The branch working tree contains the approved Lexical Evolution v1 implementation
and tests. This handbook pass changes only `docs/handbook/`; it does not change
simulation behavior, configuration, artifact schemas, runner behavior, or
research output. The handbook files are themselves uncommitted branch work
until the final feature commit.

## Unresolved questions

Material intent questions are isolated in [OWNER_CLARIFICATIONS](OWNER_CLARIFICATIONS.md). They include reproduction accounting/reuse, health/death checkpoints, the beliefs identity-column mismatch, plugin provenance policy, selected-state-hash wording, and legacy display labels that disagree with executable values.

## Audit record

The first complete draft was independently cross-reviewed in Wave 4 for:

- technical behavior and test-evidence accuracy;
- user operations, commands, output paths, and artifact lifecycle;
- architecture consistency, causal direction, staleness, navigation, and internal links.

Final result:

- Blockers: none.
- High findings: all resolved. Corrections added a direct-run validator,
  bounded structured-artifact/two-condition inspection, safe bounded command
  references, independent state-hash versus checksum/inventory data flow,
  correct scheduled-world-event versus disruption taxonomy, and selected-state
  rather than complete-state hash wording.
- Medium findings: resolved. Corrections covered Mermaid syntax, language RNG
  wording, initial depletion fraction, world-stock metric absence, current
  partner-bias status, focused test-evidence scope, deterministic built-in
  plugin spawning, and research-reserve clamping.
- Low findings: resolved where practical, including prerequisites, era-export
  cadence, dashboard symbol, and structured-event terminology.
- Scoped auditor rechecks passed after correction.

## Initial v0.1 verification record

```bash
python docs/handbook/validate_handbook.py
python -m thalren_vale --help
python run_experiments.py --help
python -m pytest -q tests/test_coalition_dialects.py tests/test_language_evolution.py tests/test_language_interaction_hooks.py tests/test_informal_coalitions.py tests/test_social_relationships.py tests/test_reproducibility.py tests/test_artifact_validation.py tests/test_experiment_runner.py tests/test_run_termination.py
python -m pytest -q
python -m compileall -q src run_experiments.py tests
git diff --check
```

Results at completion:

- Handbook validator: passed, 39 Markdown pages; required links and repository
  references resolved.
- Simulator and runner help: both exited 0.
- Focused emergence/evidence chain: 718 passed in 16.15 seconds.
- Default complete suite: 852 passed in 19.37 seconds. Per pytest
  configuration, this does not collect root `test_parse_logs.py`.
- Compilation: passed.
- One-tick smoke: explicit seed 42, `metrics_only`, anti-stagnation disabled,
  in a new `/tmp` working directory. It completed tick 1 and direct strict
  validation returned `schema2_valid`, `valid=True`, `v2_ready=False`.
- The smoke directory was removed after inspection.
- `git diff --check`: passed.

No plan, experiment matrix, research tier, benchmark, historical evidence scan,
or canonical repository evidence root was executed or created by this
initial documentation run.

## Language Contact v1 handbook refresh verification

```bash
python docs/handbook/validate_handbook.py
python -m compileall -q docs/handbook
git diff --check
```

Results on 2026-07-18:

- Handbook validator: passed, 40 Markdown pages; all required links and
  repository references resolved.
- Handbook Python compilation: passed.
- `git diff --check`: passed.
- No simulator, experiment, matrix, benchmark, historical scan, research tier,
  or canonical-output command was run. No research output was created.

## Intergenerational Language v1 acceptance and handbook refresh

The implementation completed focused verification, full-suite verification,
and final read-only acceptance before this documentation pass. The approved
full-suite result was **1,310 passed**; this is engineering verification, not a
scientific result.

This handbook refresh is verified with:

```bash
python docs/handbook/validate_handbook.py
python -m compileall -q docs/handbook
git diff --check
```

No simulator, experiment, matrix, benchmark, historical scan, research tier, or
canonical-output command is part of this refresh.

## Lexical Evolution v1 acceptance and handbook refresh

Lexical Evolution v1 completed implementation, the bounded summary correction,
verification, and final read-only acceptance before this documentation pass.
The earlier accepted implementation suite reported **1,474 passed**. After the
summary correction, the authoritative current full-suite result is **1,476 passed**.
These are engineering verification results, not simulations,
experiments, effect-size estimates, or scientific conclusions.

This handbook refresh is verified with:

```bash
python docs/handbook/validate_handbook.py
python -m compileall -q docs/handbook
git diff --check
```

No simulator, experiment, matrix, benchmark, historical scan, evidence
analysis, research tier, or canonical-output command is part of this refresh.

## Known documentation limitations

- Many older core mechanics lack focused unit tests; those pages are source-verified and label the gap.
- The handbook records current quirks rather than changing simulation behavior to align with stale prose.
- State hashing is documented as a selected-state fingerprint, not complete persistence.
- Optional dashboard, RA, mythology, and plugin behavior lacks complete provenance/validation.
- Line-level source references are avoided where symbol names are more stable; the recorded commit is the precision boundary.
- Model-tier routing is external to repository evidence and must be reported truthfully by the completion agent.

## Update criteria

Create a new handbook revision after any change to:

- initialization, tick order, state ownership, or causal boundaries;
- configuration fields/defaults/normalization;
- RNG use, canonical ordering, reset, or state-hash payload;
- events, metrics, summaries, manifests, schemas, or output layout;
- runner lifecycle, resume, attempts, validation, provenance, or readiness;
- social, coalition, language, or dialect behavior;
- plugin policy, inventory, or observer behavior;
- authorization of a new experiment or language milestone.

The later `feature/language-research-readiness-v1` milestone is **Planned, not implemented** and will produce the research-readiness revision; it does not retroactively make this implementation-level handbook unnecessary or scientifically authoritative beyond its recorded scope.
