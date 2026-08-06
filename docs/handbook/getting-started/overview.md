# Project overview

Thalren Vale is a tick-driven civilization simulation. Named inhabitants occupy a procedurally generated grid, gather and exchange resources, carry beliefs, form formal factions, research technologies, negotiate, fight, establish religions, reproduce, and die. Optional engineering-only layers retain directed social relationships, derive informal coalitions from those relationships, and let committed aid or trade teach individual signal vocabularies. Coalition Dialects v1 can increase language learning between members of the same prior-tick informal coalition. Language Contact v1 can strengthen positive acquisition and record borrowing between different active coalitions. Intergenerational Language v1 can seed bounded child comprehension from exact parents after a successful birth admission. Lexical Evolution v1 can derive one deterministic substitution from a pre-existing usable production form during authentic post-transfer communication. All four extensions are deliberately one-way into individual language state.

This handbook documents the approved, uncommitted Lexical Evolution v1 working
tree on branch `feature/lexical-evolution-v1`, based at commit
`2855bf15a77dffc599f6a0f4ac08721f79a379d4`. It describes implementation
behavior, not a claim that every mechanic is scientifically validated. The
repository contains strong tests for configuration, deterministic seeded
execution, structured artifacts, social memory, informal coalitions, endogenous
language, coalition dialects, language contact, intergenerational language, and
lexical evolution.
Several older civilization layers have only indirect regression coverage;
their pages say so explicitly.

## What happens in a run

```text
validated configuration
-> runtime reset
-> seed and world construction
-> population admission
-> ordered tick layers
-> end-of-tick events and metrics
-> termination and writer finalization
-> canonical selected-state hash
-> manifest publication
```

The simulation is not globally transactional. Individual admission, coalition transition, and language updates have focused rollback guarantees, but an exception partway through a tick may leave in-memory partial-tick mutations. `final_tick` identifies the last fully completed observation, and strict artifact validation rejects evidence that extends beyond it.

## Current feature status

| Area | Current status |
| --- | --- |
| World, inhabitants, beliefs, formal factions, economy, combat, technology, diplomacy, religion | Implemented but experimental |
| Seeded serial execution and schema-2 structured evidence | Stable and verified engineering infrastructure |
| Social memory and repeated-partner bias | Implemented but experimental; Disabled by default; Engineering-only |
| Informal coalitions | Implemented but experimental; Disabled by default; Engineering-only |
| Endogenous Language v1 | Implemented but experimental; Disabled by default; Contracted for readiness |
| Coalition Dialects v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Language Contact v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Intergenerational Language v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Lexical Evolution v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Compositional Protolanguage v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Grammar Evolution v1 | Implemented but experimental; Disabled by default; Engineering-only |
| Dashboard, raw narratives, RA tracker, mythology | Optional or diagnostic; not canonical evidence |
| Generic experiment runner | Fresh-root engineering runner; not V2 research-ready |
| Core Replication V2 execution and evidence | Planned, not implemented |

Language coevolution and language research readiness remain
**Planned, not implemented** as listed in
[research readiness](../experiments/research-readiness.md).

## Recommended reading paths

- Owner or first-time user: [operations](operations.md) -> [output layout](../data/output-directory-layout.md) -> [identifying valid runs](../data/identifying-valid-runs.md).
- Developer: [architecture overview](../architecture/architecture-overview.md) -> [tick lifecycle](../architecture/tick-lifecycle.md) -> [state ownership](../architecture/state-ownership-map.md).
- Research reviewer: [determinism](../architecture/determinism-and-rng.md) -> [artifact catalog](../data/artifact-catalog.md) -> [run lifecycle and validation](../experiments/run-lifecycle-and-validation.md).
- Social/language reviewer: [aid, trade, and relationships](../systems/aid-trade-and-relationships.md) -> [informal coalitions](../systems/informal-coalitions.md) -> [endogenous language](../systems/endogenous-language.md) -> [coalition dialects](../systems/coalition-dialects.md) -> [language contact](../systems/language-contact.md) -> [intergenerational language](../systems/intergenerational-language.md) -> [lexical evolution](../systems/lexical-evolution.md).

## Evidence boundaries

- A passing test proves the tested invariant, not a scientific result.
- A valid schema-2 run is not automatically `v2_ready`.
- A state-hash match compares the documented selected-state projection, not every future-affecting byte or RNG state.
- Raw logs, dashboard JSON, chronicles, and derived CSVs are not substitutes for the validated structured artifact set.
- Historical pilot material is not current Core Replication V2 evidence.

## Implementation evidence

- Source: `src/thalren_vale/sim.py`, `src/thalren_vale/config.py`, `src/thalren_vale/state.py`.
- Tests: `tests/test_reproducibility.py`, `tests/test_run_termination.py`, `tests/test_artifact_validation.py`.
- Verification entry points: `python -m thalren_vale --help`, `python run_experiments.py --help`, and `python -m pytest -q`.
- Status: source-verified at the documented commit; final handbook verification is recorded in [HANDBOOK_STATUS](../HANDBOOK_STATUS.md).
