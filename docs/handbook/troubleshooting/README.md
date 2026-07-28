# Troubleshooting

## A direct run overwrote or invalidated previous files

Direct runs write fixed condition/seed filenames beneath the current directory. Metrics/events/beliefs and the manifest are replaced, while `run_summaries.csv` appends. Start every evidence-bearing direct run in a fresh directory. Do not repair mixed evidence by hand; rerun in a new isolated directory.

## `--resume` rejects my existing experiment root

That is current behavior. The generic runner rejects every nonempty root, even with `--resume` or `--overwrite`. Safe nonempty-root resume and immutable attempt history are **Planned, not implemented**. Preserve the root and choose a new empty output location.

## Verification says schema 2 is valid but not V2-ready

This is expected for current runner output. Schema validity checks the implemented run-artifact contract. V2 readiness additionally requires an exact external contract, plan/tag/environment/plugin provenance, and approved controls that current execution does not seal.

## A run has exit code zero but validation fails

Exit status is not completion evidence. Inspect the per-run manifest for terminal state and writer health, then the validator’s bounded issues. Common failures include wrong final tick, header-only required data, checksum mismatch, multiple summary rows, an unresolved writer error, or inconsistent event/summary totals.

## A manifest exists for a cancelled or failed run

The simulator attempts to seal diagnostic termination information even on cancellation or exception. Strict validation correctly rejects a noncompleted terminal status. Preserve it as failure/tractability evidence; do not relabel it completed.

## Repeating a seed gives a different result

Check all of:

- exact commit and dirty state;
- exact effective manifest configuration;
- `PYTHONHASHSEED=0`;
- use of `python -m thalren_vale --seed 42`, not the equals form unless the environment is already set;
- plugin directory contents and plugin side effects;
- Python/dependency/platform compatibility;
- explicit-seed serial mode.

The recorded seed of an unseeded threaded run is not sufficient to reproduce its scheduling.

## Output root or artifact path is rejected

The runner and validator reject symlinked components, path escapes, nonregular files, and changed directory identities. Use an ordinary absolute directory under your control. Do not replace condition/seed/data directories while a run is active.

## Event counts do not match narrative logs

Canonical event CSVs contain the registered typed/compatibility-classified subset. Many price, trade, religion, plugin, movement, and lifecycle messages remain text-only. Use structured events for defined counters and treat raw narrative parsing as derived diagnostics.

## Belief `inhabitant_id` values look like names

They are names in this schema revision. The producer/header mismatch is documented in [artifact catalog](../data/artifact-catalog.md) and [owner clarifications](../OWNER_CLARIFICATIONS.md). Do not join the column to integer stable IDs.

## Dashboard or raw logs disagree with canonical data

Dashboard JSON, raw logs, chronicles, and mythology are diagnostic and unvalidated. Revalidate the required structured set and use its end-of-tick semantics. Dashboard reputation history can persist across repeated in-process runs.

## A language feature is missing

Endogenous Language v1, Coalition Dialects v1, Language Contact v1, and
Intergenerational Language v1 are implemented engineering features. Lexical
Evolution v1 is also implemented: it can substitute exactly one token in a
pre-existing usable form during committed-transfer communication, with no RNG
or fuzzy comprehension. Compositional protolanguage, grammar, coevolution, and
research-readiness milestones are **Planned, not implemented**. Contact applies
only to authentic different-active-coalitions communication; assigned/unassigned
communication intentionally remains base Language v1 behavior. Birth
transmission applies only after successful child admission and creates bounded
comprehension, not production or a copied vocabulary.

## Lexical evolution was requested but stayed disabled

Lexical evolution depends only on effective base language. Requesting it while
`language_evolution_enabled` is false normalizes only the lexical gate off,
preserves the submitted rate and depth, and records
`lexical_evolution_requested_without_language` with
`normalized_uncontracted` status. Direct simulator parsing rejects
abbreviations. The generic experiment runner rejects the entire lexical option
family by design because these controls remain engineering-only and
non-V2-ready.

## Documentation appears inconsistent with source

Confirm `git rev-parse HEAD` matches the revision in [HANDBOOK_STATUS](../HANDBOOK_STATUS.md). If behavior/configuration/schema changed, the handbook needs a new versioned refresh. Record intent questions instead of editing historical evidence to match new behavior.
