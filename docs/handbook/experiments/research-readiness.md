# Research readiness and authorization boundaries

## Current conclusion

The repository contains strong engineering validation for deterministic seeded execution, termination-aware structured artifacts, deep validation, social memory, informal coalitions, endogenous language, coalition dialects, Language Contact v1, Intergenerational Language v1, Lexical Evolution v1, Compositional Protolanguage v1, Grammar Evolution v1, and Language Coevolution v1. It does not contain executed Core Replication V2 evidence or a complete V2 orchestration/provenance workflow.

Valid engineering evidence and research-ready evidence are different states:

| State | Meaning |
| --- | --- |
| `invalid` | Safety, schema, identity, termination, checksum, writer-health, or cross-artifact contract failed |
| `legacy` | Readable schema-1 evidence; never V2-ready |
| `schema2_valid` | Current deep structured contract passes, but the complete external readiness contract is absent or fails |
| `v2_ready` | Valid schema-2 evidence plus an exact complete `ExpectedRunContract` |

Current real runner output cannot reach `v2_ready`: child manifests omit plan identity/hash, code tag, and environment/plugin fingerprint, and the runner does not supply a complete expected contract.

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

- `feature/endogenous-language-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/coalition-dialects-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/language-contact-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/intergenerational-language-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/lexical-evolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/compositional-protolanguage-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/grammar-evolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.
- `feature/language-coevolution-v1`: Implemented but experimental; Disabled by default; Engineering-only.

Future milestones:

| Milestone | Status |
| --- | --- |
| `feature/compositional-protolanguage-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/grammar-evolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-coevolution-v1` | Implemented but experimental; Disabled by default; Engineering-only |
| `feature/language-research-readiness-v1` | Planned, not implemented |

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
language-to-coalition feedback, language-driven faction or coalition
lifecycle, or a finalized language research contract. Language-to-social
feedback is implemented, but only as bounded intelligibility feeding partner
choice. On-demand contact, intergenerational, lexical, compositional, grammar,
and coevolution summaries are not approved research endpoints. Retained parental exposure does not prove uninterrupted
inheritance because later ordinary communication may reinforce the same
association, and retained lexical indices do not reconstruct a full lineage.
This handbook does not invent hypotheses, estimands, uncertainty rules, or
research conclusions for these mechanisms.

The next language milestone is `feature/language-research-readiness-v1`: **Planned, not implemented**.

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

Artifact validation makes missing, enabled, normalized, or nondefault
intergenerational or lexical controls non-V2-ready, and an
`ExpectedRunContract` cannot override either veto. The generic runner rejects
the complete intergenerational and lexical option families before output-root
or child-process activity. Both parsers retain `allow_abbrev=False`.

## Criteria for a future research-readiness revision

The later `feature/language-research-readiness-v1` milestone is **Planned, not implemented** and is expected to update this handbook only after source implements and tests an approved contract. At minimum, documentation would need to record exact approved controls, canonical metrics/artifacts, provenance, validation, estimands, run lifecycle, and authorization status. It must not retroactively reinterpret current engineering summaries as research evidence.

## Implementation evidence

- Plan: `CORE_REPLICATION_V2_PLAN.md` and root `AGENTS.md` authorization boundary.
- Validator: `src/thalren_vale/artifact_validation.py::ExpectedRunContract`, `inspect_run_outputs`.
- Runner: `run_experiments.py`.
- Tests: `tests/test_artifact_validation.py`,
  `tests/test_experiment_runner.py`, `tests/test_reproducibility.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_lexical_evolution.py`.
