# Compositional Protolanguage

## 1. Status and verified compositional gap

Compositional Protolanguage v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

The earlier language milestones all treated meaning as one closed atom. A
signal stood for `FOOD`, `WOOD`, `ORE`, or `STONE` and nothing else. Invention
produced whole signals with no internal structure, and two forms belonging to
one speaker bore no systematic relationship to each other.

Compositional Protolanguage v1 fills only that gap. Meaning becomes a
fixed-arity structured pair, and an emitted signal is assembled from one
morpheme per semantic dimension. The implemented causal chain is:

```text
committed transfer
-> resource meaning and transfer modality
-> one closed composite meaning
-> speaker-stable resource morpheme + modality morpheme
-> composed signal emitted
-> exact receiver interpretation and learning
```

This is systematic form-meaning correspondence, not grammar. There is no
parser, no generalization to unseen combinations, no recursion, and no open
semantic space.

## 2. The closed composite meaning space

`Meaning` is unchanged: `FOOD`, `WOOD`, `ORE`, `STONE`. A new closed `Modality`
adds the second dimension:

| Modality | Meaning |
| --- | --- |
| `GIFT` | The committed transfer moved no payment |
| `EXCHANGE` | The committed transfer moved a positive payment |

`CompositeMeaning` is the closed product of the two, giving exactly eight
members in canonical resource-major order:

```text
FOOD_GIFT, FOOD_EXCHANGE, WOOD_GIFT, WOOD_EXCHANGE,
ORE_GIFT, ORE_EXCHANGE, STONE_GIFT, STONE_EXCHANGE
```

Arity is fixed at two. No composite meaning exists that a committed transfer
cannot ground, and no mechanism constructs new dimensions at runtime.

`CompositeMeaning` is an enum rather than a dataclass so that the existing
identity comparisons in production selection and synonym competition keep
working unchanged, and so canonical serialization keeps using the established
`.name` path.

## 3. Grounding: where the modality comes from

The modality dimension carries **only** information the economy layer already
computes for its own reasons. `_commit_individual_transfer()` derives the
transfer context from whether payment occurred, and `communicate()` has always
received that context. Composition reads it and nothing else:

| Committed context | Modality |
| --- | --- |
| `AID_TRANSFER` | `GIFT` |
| `PAID_TRADE` | `EXCHANGE` |
| `FACTION_TRADE` | `EXCHANGE` |

Two consequences follow from the grounding rule rather than from convenience:

- **Quantity is not available.** Every individual transfer moves exactly one
  unit, so quantity is structurally constant and can carry no information.
- **Mediation identity is not semantic.** `FACTION_TRADE` describes who
  mediated, not whether payment occurred. It maps to `EXCHANGE` and remains
  event metadata.

Because the context was already a parameter of `communicate()`, no economy call
site changed for this milestone.

## 4. Speaker-stable morphemes

Composition owns no RNG. Initialization freezes the domain-separated seed
identity:

```text
thalren-vale:compositional-protolanguage-v1|seed=<seed>
```

Each morpheme is a canonical SHA-256 record over the seed domain, the speaker's
stable ID, a fixed component token, the component value, and the requested
extent. The record deliberately excludes tick, receiver, invention index,
coalition membership, dialect state, contact state, RNG state, Python hashes,
and mapping order.

That exclusion is what makes the lexicon systematic. One speaker reuses one
morpheme per resource across both modalities and one morpheme per modality
across all four resources. A worked example for speaker `7` under the default
controls and run seed `42`:

| Component | Morpheme |
| --- | --- |
| `FOOD` | `(3, 3)` |
| `WOOD` | `(4, 3)` |
| `ORE` | `(7)` |
| `STONE` | `(3, 6)` |
| `GIFT` | `(1)` |
| `EXCHANGE` | `(5)` |

Composed emission is the concatenation, so `FOOD_GIFT` is `(3, 3, 1)` and
`FOOD_EXCHANGE` is `(3, 3, 5)`. Resource morpheme **length** is itself derived
per speaker and resource, which is why `ORE` occupies one phoneme above while
the others occupy two.

Different speakers derive independent inventories, so divergence and
convergence remain observable without any randomness.

## 5. Signal bounds

Composed signals reuse the existing `Signal` contract without relaxing it. A
composed length is `resource morpheme + modality morpheme`, bounded by:

```text
1 + modality_morpheme_length
    <= composed length
    <= maximum_resource_morpheme_length + modality_morpheme_length
    <= maximum_signal_length
```

Effective configuration validation rejects controls whose sum exceeds the
effective `maximum_signal_length`, so a composed signal can never violate
`MIN_SIGNAL_LENGTH` or `MAX_SIGNAL_LENGTH`. Nothing about invention length
derivation, lexical substitution position selection, or previously pinned
signal vectors changes.

## 6. Production composes; comprehension does not

The emitted composed signal is used by the ordinary communication path for
`CommunicationOutcome.produced_signal`, receiver comprehension lookup, result
classification, correction and learning, and dialect and contact accounting.

The receiver still performs **exact-key lookup on the whole composed signal**.
There is no fuzzy matching, no phonetic distance, no segmentation, and no
morpheme-level inference. A receiver that has heard `FOOD_GIFT` and
`ORE_EXCHANGE` therefore holds evidence of the `FOOD` morpheme and the
`EXCHANGE` morpheme, yet does **not** recognize the unheard `FOOD_EXCHANGE`
combination.

This asymmetry is the milestone's defining boundary: composition is a property
of emitted form, not of interpretation.

## 7. Interaction with the earlier language slices

Composition replaces the meaning key. It does not change any other slice's
rules:

- **Coalition dialects** still apply same-coalition rate multipliers, now keyed
  by composite meaning.
- **Language contact** still qualifies only different-active-coalitions
  communication and records the same bounded provenance.
- **Lexical evolution** still substitutes exactly one token of a pre-existing
  usable production form. A composed signal can be mutated like any other, and
  the descendant is the actual emitted signal.
- **Intergenerational language** still copies bounded parental forms into child
  comprehension exactly, including composed forms, and creates no composition
  opportunity of its own.

Structural association caps continue to apply per meaning, which under
composition means per composite meaning.

## 8. Runtime counters

`SimulationState.compositional_protolanguage` owns one constant-size
`CompositionalProtolanguageRuntimeState` holding the frozen seed identity, the
frozen morpheme controls, and:

- `composed_utterance_count`;
- `gift_utterance_count`;
- `exchange_utterance_count`;
- `composed_invention_count`;
- `observed_composite_meaning_mask`;
- `last_composition_tick`.

Unsaturated state satisfies:

```text
composed_utterance_count == gift_utterance_count + exchange_utterance_count
composed_invention_count <= composed_utterance_count
0 <= observed_composite_meaning_mask < 2 ** 8
```

The observed-meaning field is a bounded bitmask rather than a set, so the
runtime stays constant size while still recording **which** of the closed
composite space a run exercised. Modality counters advance together with the
total or not at all.

## 9. Transaction and rollback boundary

The material transfer commits before `communicate()` begins, and composition
does not determine whether it succeeds. Counters mutate a copied runtime,
which is validated against the partition invariants before commit, then
committed alongside the sender state, receiver state, base language runtime,
and any enabled dialect, contact, and lexical runtimes.

Any exception restores every copied language owner relative to `communicate()`
entry. The already committed transfer is not rolled back. This is deliberately
not material-language atomicity.

## 10. On-demand summary

`compositional_protolanguage_summary()` is bounded engineering observability,
not a standard event, metric, CSV, manifest field, or approved research
endpoint. It accepts a one-shot population iterable and consumes it exactly
once, performs bounded association work per inhabitant, performs no
population-wide sort, pair enumeration, or morpheme reconstruction, mutates
nothing, and consumes no RNG. It remains `O(P x L)`.

It reports population, composed carriers, retained and usable composed
production totals, composed comprehension totals, per-composite-meaning
production counts, per-modality production counts, and the canonical runtime
record.

## 11. Configuration, normalization, and containment

| Field / CLI | Default | Exact validation |
| --- | ---: | --- |
| `compositional_protolanguage_enabled` / `--enable-compositional-protolanguage` | `False` | Exact Boolean; requires effective base language only |
| `--disable-compositional-protolanguage` | n/a | Explicitly leaves composition disabled |
| `maximum_resource_morpheme_length` / `--maximum-resource-morpheme-length` | `2` | Exact non-Boolean integer `1..3` |
| `modality_morpheme_length` / `--modality-morpheme-length` | `1` | Exact non-Boolean integer `1..2` |

The feature depends only on effective base language evolution. It does not
require coalitions, dialect influence, language contact, intergenerational
language, lexical evolution, social memory, formal factions, or settlements.

A request without effective base language normalizes only the compositional
gate to false, preserves both submitted numeric controls, records
`compositional_protolanguage_requested_without_language`, and sets
`compositional_protolanguage_controls_status` to `normalized_uncontracted`.
Exact disabled defaults use `disabled`; enabled or nondefault controls without
normalization use `engineering_only_uncontracted`.

Enabled, normalized, or nondefault compositional controls veto V2 readiness.
The generic experiment runner rejects the complete four-option family,
including exact, equals, unambiguous-prefix, and ambiguous-prefix spellings,
before output-root creation or mutation, command construction, verification
mutation, or child launch. Both parsers retain `allow_abbrev=False`.

This milestone changes no event, metric, artifact, manifest, summary, belief,
CSV, or ledger schema-version constant.

## 12. Hashing, reset, and pristine state

When enabled, canonical hashing includes exact effective controls, status and
notices, the base-language compositional gate, the complete dedicated runtime,
and the composite meanings carried by production and comprehension keys.

When disabled, the compositional controls are omitted from the behavioral
payload so previously pinned pre-feature hashes are unchanged. Because a
composite meaning is a structural key component rather than optional attached
metadata, the disabled guard scans both association records and dictionary
keys across the living and retained-dead cohorts. Hidden composed state fails
closed, and a nonpristine dedicated runtime fails closed.

Base `Meaning` retains canonical ordering indices `0..3`; composite meanings are
appended, never renumbered.

Reset prevalidates every language owner and the dedicated runtime before any
mutation, then restores a pristine
`CompositionalProtolanguageRuntimeState`.

## 13. Causal isolation and non-goals

Composition changes which signal is emitted and which key stores it. It cannot
change the already committed material transfer or any inventory, currency,
trust, relationship, partner choice, social memory, coalition, faction,
combat, reproduction, health, survival, movement, or population state. No
language-to-social or language-to-material feedback was added.

Signals and meanings remain associations owned by individual inhabitants. There
is no global, coalition, faction, family, generation, or settlement lexicon.

Compositional Protolanguage v1 does **not** add compositional parsing,
generalization to unseen combinations, segmentation of a heard signal during
comprehension, open or recursive semantic structure, syntax, agreement,
inflection, arity beyond two, prestige, standardization, teaching institutions,
or research conclusions.

Comprehension remains exact whole-signal key lookup at every stage. A later
milestone, [Grammar Evolution v1](grammar-evolution.md), lets a hearer compare
two signals it has **already learned** to infer the constituent order its
speaker used. That inference reads finalized state and never segments the
signal being comprehended, so the comprehension non-goal above is unchanged;
only the blanket "no word order" claim was narrowed.

## 14. Known limitations

- Modality is the only available second dimension, because quantity is
  structurally constant and mediation identity is not semantic.
- A speaker that forgets and later re-invents a form for the same composite
  meaning produces the identical signal. This differs from base Language v1,
  where the per-agent invention index made each invention distinct. Stability
  is inherent to systematic composition and is directly tested.
- The summary is internal and on demand; no compositional event, metrics
  column, artifact schema, or approved estimand exists.
- Systematicity is a property of emitted production only. Nothing measures
  whether a population has converged on shared morphemes.

## 15. Language roadmap

Completed engineering implementations:

- `feature/endogenous-language-v1`
- `feature/coalition-dialects-v1`
- `feature/language-contact-v1`
- `feature/intergenerational-language-v1`
- `feature/lexical-evolution-v1`
- `feature/compositional-protolanguage-v1`
- `feature/grammar-evolution-v1`

Remaining milestones:

- `feature/language-coevolution-v1` — **Planned, not implemented**
- `feature/language-research-readiness-v1` — **Planned, not implemented**

The next milestone is `feature/language-coevolution-v1`: **Planned, not implemented**.

## 16. Implementation evidence

**Implementation status:** source- and test-verified engineering feature; not
research-ready.

**Primary source:**

- `src/thalren_vale/language.py`: `Modality`, `CompositeMeaning`, morpheme
  derivation, composed emission, dedicated runtime, validation, records, and
  summary;
- `src/thalren_vale/economy.py`: unchanged committed-transfer hooks that
  already supplied the transfer context;
- `src/thalren_vale/config.py`: controls, ranges, dependency normalization,
  notices, and statuses;
- `src/thalren_vale/state.py` and `src/thalren_vale/sim.py`: runtime ownership,
  CLI, initialization, lifecycle, and reset;
- `src/thalren_vale/reproducibility.py`: enabled and disabled canonical
  hashing;
- `src/thalren_vale/artifact_validation.py` and `run_experiments.py`:
  configuration validation and complete option-family containment.

**Primary tests:**

- `tests/test_compositional_protolanguage.py`
- `tests/test_language_evolution.py`
- `tests/test_lexical_evolution.py`
- `tests/test_intergenerational_language.py`
- `tests/test_language_contact.py`
- `tests/test_coalition_dialects.py`
- `tests/test_language_reproducibility.py`
- `tests/test_reproducibility.py`
- `tests/test_config.py`
- `tests/test_artifact_validation.py`
- `tests/test_experiment_runner.py`

Related pages: [Endogenous language](endogenous-language.md),
[Lexical evolution](lexical-evolution.md),
[Tick lifecycle](../architecture/tick-lifecycle.md),
[Causal chains](../architecture/causal-chains.md),
[Determinism and RNG](../architecture/determinism-and-rng.md),
[Configuration reference](../reference/configuration-reference.md),
[Test reference](../reference/test-reference.md).

No research plan, matrix, tier, evidence run, hypothesis, estimand, or
scientific conclusion is introduced by Compositional Protolanguage v1.
