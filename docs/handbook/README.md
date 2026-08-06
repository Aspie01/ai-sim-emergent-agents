# Living Technical Handbook v0.1

This is the authoritative technical handbook for the current Thalren Vale repository revision:

- Branch: `feature/lexical-evolution-v1`
- Base `HEAD` commit: `2855bf15a77dffc599f6a0f4ac08721f79a379d4`
- Documented implementation state: the approved, uncommitted Lexical Evolution
  v1 working tree on that branch
- Updated: 2026-07-28

The commit identifies the base revision; it does not by itself contain the
Lexical Evolution v1 implementation. The implementation and these handbook
updates remain uncommitted branch work until the owner creates the final
feature commit.

It is written for the project owner, new developers, future Codex sessions, researchers inspecting results, and reviewers auditing causal isolation, determinism, or evidence integrity. It explains executable behavior; it does not promote engineering tests or historical pilot outputs into research conclusions.

## Where do I begin?

1. Read the [plain-language overview](getting-started/overview.md).
2. Follow [safe operations](getting-started/operations.md) for help, prerequisites, one bounded run, and tests.
3. Use the [command reference](reference/command-reference.md) for exact commands.
4. Open [output directory layout](data/output-directory-layout.md) to find results.
5. Use [identifying valid runs](data/identifying-valid-runs.md) before trusting a result.

The simulator writes relative to its working directory. For a bounded direct run, use a new temporary directory and the explicit two-token seed form. Do not reuse a direct-run directory when artifact integrity matters.

## How do I understand one tick?

- [Architecture overview](architecture/architecture-overview.md)
- [Exact simulation and tick lifecycle](architecture/tick-lifecycle.md)
- [Tick-flow diagram](diagrams/tick-flow.md)
- [State ownership map](architecture/state-ownership-map.md)
- [System dependency and interaction map](architecture/system-dependency-map.md)
- [Data flow](architecture/data-flow.md)
- [Causal chains](architecture/causal-chains.md)
- [Determinism and RNG](architecture/determinism-and-rng.md)

The compact visual overview is the [full system map](diagrams/full-system-map.md). The [repository map](architecture/repository-map.md) tells developers where each implementation lives.

## How do the simulation systems work?

- [World and resources](systems/world-and-resources.md)
- [Agents and population](systems/agents-and-population.md)
- [Beliefs and formal factions](systems/beliefs-and-formal-factions.md)
- [Aid, trade, economy, and directed relationships](systems/aid-trade-and-relationships.md)
- [Informal coalitions](systems/informal-coalitions.md)
- [Endogenous language](systems/endogenous-language.md)
- [Coalition dialects](systems/coalition-dialects.md)
- [Language contact](systems/language-contact.md)
- [Intergenerational language](systems/intergenerational-language.md)
- [Lexical evolution](systems/lexical-evolution.md)
- [Compositional protolanguage](systems/compositional-protolanguage.md)
- [Grammar evolution](systems/grammar-evolution.md)
- [Language coevolution](systems/language-coevolution.md)
- [Language research readiness](systems/language-research-readiness.md)
- [Coalition intelligibility](systems/coalition-intelligibility.md)
- [Combat, technology, diplomacy, and religion](systems/conflict-technology-diplomacy-religion.md)
- [Events, observers, and plugins](systems/events-observers-and-plugins.md)

For the full social-to-language path, see the [social and language causal-chain diagram](diagrams/social-and-language-causal-chains.md).

## How do I run experiments and verify artifacts?

- [Runner and configurations](experiments/runner-and-configurations.md)
- [Run lifecycle and validation](experiments/run-lifecycle-and-validation.md)
- [Research readiness and authorization](experiments/research-readiness.md)
- [Experiment and artifact flow](diagrams/experiment-and-artifact-flow.md)
- [Characterization: language divergence](experiments/language-speciation-characterization.md)

The current batch runner is a fresh-root engineering runner. It rejects every nonempty root—even with `--resume` or `--overwrite`—and current real outputs cannot become `v2_ready`. Core Replication V2 has not been executed.

## Which outputs are authoritative?

- [Artifact catalog](data/artifact-catalog.md)
- [Identifying valid, incomplete, and failed runs](data/identifying-valid-runs.md)
- [Output directory layout](data/output-directory-layout.md)
- [Stale and superseded data](data/stale-and-superseded-data.md)
- [Event and metric reference](reference/events-and-metrics.md)

Canonical engineering evidence is the complete deeply validated per-run
structured set: metrics, structured event rows, belief snapshots, one run
summary row, and the schema-2 run manifest. Raw logs, dashboard JSON,
chronicles, RA outputs, batch indexes, derived tables, and figures are not
authoritative alone.

## Configuration, tests, and terminology

- [Configuration reference](reference/configuration-reference.md)
- [Test reference](reference/test-reference.md)
- [Glossary](reference/glossary.md)
- [Troubleshooting](troubleshooting/README.md)
- [Owner clarifications](OWNER_CLARIFICATIONS.md)
- [Handbook status and audit record](HANDBOOK_STATUS.md)

## Current feature status

| Feature family | Status at this revision |
| --- | --- |
| Core world/population/civilization layers | Implemented but experimental |
| Seeded serial reproducibility and schema-2 artifact infrastructure | Stable and verified engineering infrastructure |
| Directed social memory and partner bias | Implemented but experimental; Disabled by default; Engineering-only |
| Informal Coalition Emergence v1 | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/endogenous-language-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/coalition-dialects-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-contact-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/intergenerational-language-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/lexical-evolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/compositional-protolanguage-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/grammar-evolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| Generic experiment runner | Implemented fresh-root engineering runner; not research-ready |
| Core Replication V1 | Historical pilot material |
| Core Replication V2 evidence | Planned, not implemented |
| `feature/language-coevolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-research-readiness-v1` | Implemented but experimental; Disabled by default; Engineering-only |

The language milestone sequence is complete. Every further step is a
research authorization decision rather than an engineering one, and each
requires separate explicit authorization.

## Evidence standard

Major pages end with Implementation Evidence listing current source, tests, configuration, verification commands, status, and discrepancies. Claims were evaluated in this order:

1. bounded execution at the documented revision;
2. passing current tests;
3. current executable source;
4. active schemas and configuration validation;
5. current authoritative documentation;
6. plans and handoffs;
7. comments/docstrings;
8. historical prose and generated material.

The handbook preserves a visible distinction between source-verified behavior and inferred rationale. Unresolved intent is collected in [OWNER_CLARIFICATIONS](OWNER_CLARIFICATIONS.md), while safe provisional wording documents what the current program demonstrably does.

## Important boundaries

- A fixed-seed hash match is not a checkpoint or full replay proof.
- Passing tests do not establish scientific conclusions.
- Formal factions and informal coalitions are different systems.
- Coalition membership can influence language only through the enabled dialect
  and contact extensions; language cannot influence coalition lifecycle or any
  economic, social, or biological outcome.
- A successfully committed birth can provide bounded child comprehension of
  usable parental forms when Intergenerational Language v1 is enabled;
  language cannot affect reproduction or any social/material outcome.
- After an already committed transfer, Lexical Evolution v1 may derive one
  deterministic substitution from a pre-existing usable production form and
  emit the descendant. It consumes no RNG and cannot alter the transfer or any
  social/material state.
- Plugins are causal Python extensions, not sandboxed observers.
- The beliefs CSV’s `inhabitant_id` column contains display names in this schema revision.
- Known obsolete equilibrium JSON files must not be used as current evidence.

This handbook is versioned. Refresh it after any change to simulation behavior, configuration, schemas, events, metrics, runner lifecycle, validation, provenance, or output layout.
