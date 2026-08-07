# Research readiness and authorization boundaries

## Current conclusion

The repository contains strong engineering validation for deterministic seeded execution, termination-aware structured artifacts, deep validation, social memory, informal coalitions, endogenous language, coalition dialects, Language Contact v1, Intergenerational Language v1, Lexical Evolution v1, Compositional Protolanguage v1, Grammar Evolution v1, and Language Coevolution v1. It does not contain executed Core Replication V2 evidence or a complete V2 orchestration/provenance workflow.

Valid engineering evidence and research-ready evidence are different states:

| State | Meaning |
| --- | --- |
| `invalid` | Safety, schema, identity, termination, checksum, writer-health, or cross-artifact contract failed |
| `legacy` | Readable schema-1 evidence; never V2-ready |
| `schema2_valid` | Current deep structured contract passes, but the complete external readiness contract is absent or fails |
| `v2_ready` | Valid schema-2 evidence, an exact complete `ExpectedRunContract`, approved controls, and the contracted language endpoint |

Child manifests now record plan identity and SHA-256, the annotated tag, and an environment/plugin fingerprint, so every field the contract compares is present. Current real runner output still cannot reach `v2_ready`: the runner does not supply a complete expected contract, and readiness additionally requires a clean, annotated-tagged revision.

## Current runner gate

The generic runner is suitable for fresh-root engineering batches. It:

- validates/freeze-copies all cells before root creation;
- requires an absent or empty nonsymlink root;
- launches explicit-seed children with `PYTHONHASHSEED=0`;
- deep-validates each cell after completion;
- records operational results in a batch manifest and index.

It does not yet implement:

- immutable attempt directories or append-only attempt ledger;
- explicit selected/superseded attempt state;
- safe contract-matched resume;
- stop-on-first-nonaccepted dispatch;
- clean annotated-tag and environment/plugin preflight;
- nonexecuting V2 matrix expansion;
- quota enforcement;
- runner-owned V2 A/C/R control generation.

These remain **Planned, not implemented**. The current `--resume` and `--overwrite` flags do not allow nonempty-root continuation or replacement.

## Language milestone status

Completed engineering implementations at the documented revision:

- `feature/endogenous-language-v1`: Implemented but experimental; Disabled by default; Contracted for readiness.
- `feature/coalition-dialects-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/language-contact-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/intergenerational-language-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/lexical-evolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/compositional-protolanguage-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/grammar-evolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/language-coevolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.

The remaining milestones, all implemented:

| Milestone | Status |
| --- | --- |
| `feature/compositional-protolanguage-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/grammar-evolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-coevolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-research-readiness-v1` | Implemented; contracts base language; authorizes no execution |

Current source implements bounded different-coalition acquisition, exposure,
and contact-qualified borrowing plus bounded comprehension-only transmission
from exact birth parents. It also implements deterministic same-length
one-token lexical descendants with bounded direct-edge provenance during
authentic committed-transfer communication. It further implements fixed-arity
composed `(resource, modality)` signals built from speaker-stable morphemes,
and a per-speaker constituent-order rule that a hearer can infer from a minimal
pair it has already learned. It does not implement complete vocabulary
inheritance, deletion/insertion, ancestry reconstruction, phonology, cognates,
comprehension-time segmentation, parsing, syntax, agreement, inflection,
language-driven faction formation or lifecycle, or a finalized language
research contract. Language-to-social feedback is implemented as bounded
intelligibility feeding partner choice, and language-to-coalition feedback as
an intelligibility threshold that can only narrow which reciprocal ties carry
a coalition edge. Both are disabled by default and vetoed from readiness. On-demand contact, intergenerational, lexical, compositional, grammar,
and coevolution summaries are not approved research endpoints. Retained parental exposure does not prove uninterrupted
inheritance because later ordinary communication may reinforce the same
association, and retained lexical indices do not reconstruct a full lineage.
This handbook does not invent hypotheses, estimands, uncertainty rules, or
research conclusions for these mechanisms.

The language milestone sequence is complete. Every further step is a
research authorization decision rather than an engineering one, and each
requires separate explicit authorization.

## Core Replication V2 authorization

`CORE_REPLICATION_V2_PLAN.md` is an unexecuted plan. Completing handbook or engineering work does not authorize S0, S1, P1, P2, Full, pilot, replication, or long-horizon execution. Existing V1 results remain historical pilot material and cannot be pooled with a future V2.

## What tests establish

Tests establish implementation contracts such as:

- explicit-seed short-run reproducibility in the current environment;
- authentic exact-once social/language hooks;
- deterministic coalition graph/lifecycle behavior;
- one-way dialect influence and causal isolation;
- different-coalition contact qualification, borrowing provenance, one-pass
  summaries, hashing, and causal isolation;
- successful-birth-only parental exposure, comprehension-only acquisition,
  exact-once sentinels, rollback boundaries, one-pass summaries, hashing, and
  causal isolation;
- post-transfer lexical opportunities, pinned deterministic substitutions,
  actual descendant emission, direct-edge provenance, collision/depth/saturation
  semantics, transactional rollback, one-pass summaries, hashing, and causal
  isolation;
- termination and manifest sealing;
- artifact streaming, checksums, cross-file consistency, and readiness vetoes;
- runner containment and timeout/cancellation classification.

They do not establish natural long-run effect sizes, scientific hypotheses, external validity, full environment portability, or V2 research readiness.

Artifact validation makes missing, normalized, or nondefault controls
non-V2-ready for **every** control family, and an `ExpectedRunContract` cannot
override any of those vetoes. A structural test asserts that each
`*_controls_status` manifest key reaches the readiness gate, so a new family
cannot be omitted silently.

Base language is the one exception: under
[Language Research Readiness v1](../systems/language-research-readiness.md) it
is contracted, so `language_evolution_enabled` may take either value while
every other base-language control stays pinned to its approved value. All
twelve other language and social families remain engineering-only and vetoed:
social memory, informal coalitions, coalition dialects, language contact,
intergenerational language, lexical evolution, compositional protolanguage,
grammar evolution, language coevolution, coalition intelligibility, production
trials, and the faction relationship-trust model. The generic runner rejects
each engineering-only option family before output-root or child-process
activity. Both parsers retain `allow_abbrev=False`.

## What the language contract does and does not settle

[Language Research Readiness v1](../systems/language-research-readiness.md) is
implemented. It records exact approved controls for Endogenous Language v1, one
canonical endpoint, its provenance, and its validation.

It settles nothing about analysis. Estimand, contrast, estimator, uncertainty
method, and multiplicity rules remain **Planned, not implemented**, and the
recorded endpoint carries `analysis_contract: "unspecified"` rather than
leaving that omission to be inferred. `v2_ready` certifies evidence integrity
— provenance, schema, determinism, approved controls — not that an analysis
plan exists.

It also authorizes nothing. No S0, S1, P1, P2, or Full configuration exists and
no research cell has been launched. Current engineering summaries must not be
retroactively reinterpreted as research evidence.

## Implementation evidence

- Plan: `CORE_REPLICATION_V2_PLAN.md` and root `AGENTS.md` authorization boundary.
- Validator: `src/thalren_vale/artifact_validation.py::ExpectedRunContract`, `inspect_run_outputs`.
- Runner: `run_experiments.py`.
- Tests: `tests/test_artifact_validation.py`,
  `tests/test_experiment_runner.py`, `tests/test_reproducibility.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_lexical_evolution.py`.
