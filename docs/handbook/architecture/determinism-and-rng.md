# Determinism, RNG, and reproducibility

## Supported guarantee

Within the current compatible environment, an explicit seed, identical effective configuration, controlled plugin set, `PYTHONHASHSEED=0`, and the serial execution path reproduce the tested selected-state hash. This is narrower than “all runs are deterministic.”

Use the complete fresh-directory, bounded command in
[safe operations](../getting-started/operations.md). The module wrapper
automatically supplies the hash seed for the two-token `--seed 42` form, but
not `--seed=42`. The installed `thalren-vale` entry point calls `sim.run()`
directly and also needs the environment variable set explicitly.

## RNG ownership

| Owner | Mechanism | Uses |
| --- | --- | --- |
| Core simulation | One process-global `random` generator | Terrain offsets/resources, population, interactions, factions, economy, combat, technology, diplomacy, religion, interventions |
| Seeded Layer 1 | Same generator, serial processing | Fixed draw ownership/order |
| Unseeded Layer 1 | Same generator, up to four worker threads | Scheduling can change which actor receives a draw |
| Endogenous language | SHA-256 counter derivation, no RNG object | Per-agent signal invention |
| Social/coalition maintenance | No RNG | Stable-ID canonical transitions |
| Dialect classification/summary | No RNG | Snapshot lookup and frequency arithmetic |
| Language contact/summary | No RNG | Positive learning arithmetic, bounded metadata, aggregate frequencies |
| Intergenerational language/summary | No RNG | Stable-ID parent order, salience ranking, bounded comprehension exposure |
| Lexical evolution/summary | SHA-256 counter derivation, no RNG object | Mutation trigger, one-token substitution, direct-edge aggregation |
| Events/metrics/hash/validation | No intended RNG | Observation only |
| Plugins | Arbitrary Python | May consume global RNG, time, network, or other entropy |
| Mythology | External local-model request | Optional nondeterministic prose, outside canonical hash |

## Language RNG isolation

The invention domain is:

```text
thalren-vale:endogenous-language-v1|seed=<seed>
```

Signal derivation additionally uses inventor stable ID, meaning, and that agent’s next invention index. One inhabitant’s invention does not advance another’s stream, and enabling language, dialects, contact, or intergenerational transmission does not consume simulation RNG.

Birth transmission also consumes no RNG. Reproduction has already selected the
parents and constructed/admitted the child before the language hook begins.
The hook sorts the exact parents by stable ID, reuses canonical usable-production
selection, ranks meanings by bounded association salience, and never samples a
form.

Lexical evolution uses the separate domain:

```text
thalren-vale:lexical-evolution-v1|seed=<seed>
```

Its trigger and substitution records contain only the domain, opportunity
index, tick, sender/receiver stable IDs, canonical meaning, source signal, and
fixed purpose token. They exclude coalition communication context, coalition
IDs, dialect/contact/relationship state, Python hashes, mapping order, object
addresses, and RNG state. A permitted substitution chooses one digest-derived
position and one nonzero offset modulo `PHONEME_COUNT`; it has no retry loop.
Tests pin exact trigger/substitution vectors and dialect/contact-gate
independence.

## Canonical ordering

The selected-state hash and newer summaries explicitly sort or canonically traverse identities, mappings, relationships, coalition records, meanings, and signals. JSON uses sorted keys before SHA-256. Coalition algorithms use stable IDs and quantized edge strength; dialect/contact summaries aggregate commutatively and sort only bounded result keys. Contact summaries consume the population once and use frequency-square arithmetic rather than pair enumeration. The intergenerational summary also consumes the population once and performs no parent lookup, population-wide sort, or inhabitant-pair enumeration. The lexical summary consumes the population once, scans bounded associations, groups direct edges by meaning/source owner/source signal, and performs no source-owner lookup, population sort, pair scan, or ancestry reconstruction.

## What the final hash proves

A matching hash proves equality of the selected canonical payload and effective hashed controls. It is useful for regression detection and fixed-environment comparison.

It does not prove:

- identical RNG state;
- identical event logs, timings, dashboard, or narrative outputs;
- equality of omitted future-affecting state;
- byte-identical dependencies/platform behavior;
- replayability or safe continuation.

Important omitted categories include plugin internal state, RNG state, world noise offsets, several economy/diplomacy/religion caches, spatial indexes, anti-stagnation locals, and dashboard history. Two equal fingerprints may diverge if execution continues.

In-progress research is no longer omitted. The payload previously read `faction.researching` and `faction.research_progress`, which nothing assigns, so both were permanently `None`; it now reads the authoritative `active_research` mapping owned by `technology.py`, whose `tech`, `progress`, `started`, and `paused` fields all discriminate. Plugin *identity* is still outside the hash, but it is sealed separately: the run manifest's `environment_fingerprint` digests the SHA-256 of every loadable plugin alongside the interpreter and platform.

## Reset behavior

Repeated in-process runs call `reset_runtime_state()`. It validates all unique living/dead agent language states and language/dialect/contact/intergenerational/lexical runtimes before clearing core state. Intergenerational parent IDs and lexical direct-source owner IDs are checked against the complete stable-ID cohort, including retained dead inhabitants. Retained mutation indices and lineage depths are validated against the committed runtime and effective controls. Hidden disabled contact, intergenerational, or lexical metadata fails before mutation. Normal `run()` then reseeds and regenerates the world. Dashboard reputation history is not cleared by this reset, but it is diagnostic and excluded from the hash.

## Pinned compatibility values

The tests pin short-run hashes and language invention vectors as regression fixtures. They are software-compatibility sentinels, not scientific baselines or expected population outcomes.

## Reproduction workflow

1. Record exact commit and dirty status.
2. Use `python -m thalren_vale` with the two-token seed form and explicit `PYTHONHASHSEED=0`.
3. Preserve the exact effective manifest configuration.
4. Use an isolated working directory and fixed plugin contents.
5. Deep-validate the complete structured artifact set.
6. Compare `state_hash` only after validation and within the documented environment boundary.

Same seeds across different conditions are replicate identifiers, not permanently matched trajectories after the first condition-specific divergence.

## Limitations and future work

- No dependency or lockfile hash. Direct run manifests do carry an
  `environment_fingerprint` over the Python version, implementation, system,
  machine, and plugin inventory, but installed third-party distributions are
  deliberately excluded because packaging metadata varies by install method.
- No per-tick hashes, RNG serialization, checkpoint, restore, or event replay.
- No deterministic-parallelism guarantee.
- Clean-tag/environment preflight and checkpoint/replay are **Planned, not implemented**.

## Implementation evidence

- Seed wrapper: `src/thalren_vale/__main__.py`.
- RNG/serial setup: `src/thalren_vale/sim.py::run`, `inhabitants_layer`.
- Hash projection: `src/thalren_vale/reproducibility.py`.
- Language derivation: `src/thalren_vale/language.py`.
- Tests: `tests/test_reproducibility.py`,
  `tests/test_language_reproducibility.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_lexical_evolution.py`, `tests/test_log_modes.py`,
  `tests/test_simulation_state.py`.
