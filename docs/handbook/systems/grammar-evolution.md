# Grammar Evolution

## 1. Status and verified grammatical gap

Grammar Evolution v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

[Compositional Protolanguage v1](compositional-protolanguage.md) gave every
speaker a systematic way to build a signal from two morphemes, but it fixed the
*arrangement* of those morphemes globally. Every speaker in every run emitted
the resource morpheme first. Nothing about a speaker's ordering could differ
from another's, so nothing about ordering could be learned, disagreed over, or
converged upon.

Grammar Evolution v1 fills only that gap. Constituent order becomes a
**per-speaker rule** that starts divergent across the population and can change
through observation. The implemented causal chain is:

```text
speaker derives an initial constituent order (no RNG)
-> composed signal emitted in that speaker's order
-> hearer comprehends it correctly
-> hearer compares two signals it already knows (a minimal pair)
-> the shared run and its position reveal the speaker's order
-> repeated, consecutive opposing evidence flips the hearer's own order
```

This is a learnable ordering rule, not a grammar. There is no parser, no
constituent tree, no recursion, no agreement, no inflection, and no
generalization to unseen combinations.

## 2. The closed order space

Constituent order is a closed two-member enum:

| Order | Emitted arrangement |
| --- | --- |
| `RESOURCE_FIRST` | `[resource morpheme][modality morpheme]` |
| `MODALITY_FIRST` | `[modality morpheme][resource morpheme]` |

There is no third option and no "unset but effective" state. An agent either
holds one of these two orders or holds `None` and has not yet spoken.

## 3. Grounding: order is a speaker property, not a world fact

The simulation contains no authentic event that *tells* an agent which order to
use. Order is therefore not derived from the world; it is an arbitrary
convention each speaker starts with and may revise. This is the honest
position: word order in natural language is likewise arbitrary, and the
interesting behavior is convergence, not correctness.

Two consequences follow, and both are deliberate:

- **No order is "right."** The runtime records agreement and conflict counts
  but never labels an order as correct.
- **Convergence is not guaranteed.** A population may stay split. The summary
  reports counts per order rather than a dominance ratio precisely so the
  reader decides what counts as agreement.

## 4. Deterministic initial order

A speaker's starting order is derived on first use from a dedicated domain:

```text
thalren-vale:grammar-evolution-v1|seed=<run seed>|speaker_id=<id>
```

The low bit of the SHA-256 digest selects the order. No RNG is consumed, so
enabling grammar cannot perturb morpheme derivation, partner selection, or any
other stream.

Derivation is **lazy**: it happens inside the communication transaction the
first time a speaker actually speaks, not at spawn. Founders, births,
travelers, and plugin-created inhabitants are therefore all covered by one code
path, and no state is written outside the rollback boundary.

## 5. Minimal-pair inference

A hearer cannot segment an opaque signal, and its own morphemes are
speaker-specific so they almost never match a foreign form. What it *can* do is
compare two signals it has already learned which differ in exactly one semantic
dimension. The part they share is the morpheme for the shared dimension, and
its position reveals the order.

| Learned pair differs in | Shared run is | Shared run leading | Shared run trailing |
| --- | --- | --- | --- |
| modality (resource same) | the resource morpheme | `RESOURCE_FIRST` | `MODALITY_FIRST` |
| resource (modality same) | the modality morpheme | `MODALITY_FIRST` | `RESOURCE_FIRST` |

Inference abstains — returns nothing — in every ambiguous case:

- no minimal pair exists in the hearer's comprehension (the common case early
  in a run);
- the two signals differ in both dimensions, or in neither;
- the overlap is absent, or present at **both** ends, so position is
  undetermined;
- two minimal pairs disagree. Contradiction yields no inference rather than a
  guess.

Inference reads only already-finalized state, is bounded by the association
cap, is exact-match only, and mutates nothing.

## 6. Inference runs only on success

Order inference is gated on `CommunicationResult.SUCCESS`. A hearer knows which
composite meaning a signal encodes only when it understood correctly; inferring
from a misunderstanding would be inventing information the agent does not have.

This gate is why a run can show many communication attempts and zero inference
attempts. That is the mechanism behaving correctly, not a failure.

## 7. Consecutive-evidence adoption

An agent adopts an observed order only after `order_adoption_threshold`
**consecutive** observations opposing its current order. A single agreeing
observation resets the counter to zero.

Consecutiveness matters: a cumulative counter would eventually flip any agent
in a mixed population regardless of what it mostly hears, which would produce
drift rather than convergence.

## 8. Runtime counters

`GrammarEvolutionRuntimeState` is fixed size. Unsaturated state satisfies:

```text
order_inference_attempt_count == order_inferred_count
                                 + order_not_inferred_count
order_agreement_count + order_conflict_count == order_inferred_count
order_adoption_count <= order_conflict_count
```

These partitions are validated on every commit, so a counter that drifts out of
partition fails the run rather than producing a quietly wrong artifact.

## 9. Transaction and rollback boundary

Grammar joins the existing copy-validate-commit transaction over all language
owners. The proposed grammar runtime and the proposed receiver state are
validated together before any commit, and both are discarded on failure.

Order state lives on `AgentLanguageState`, which is reconstructed in several
places during normal operation. Every reconstruction site carries the order
fields forward; a site that forgets one silently erases learned grammar without
failing any invariant. This is the single most fragile aspect of the feature.

## 10. On-demand summary

`grammar_evolution_summary` consumes the population iterable exactly once with
bounded work per inhabitant, performs no population-wide sort or pair
enumeration, mutates nothing, and consumes no RNG. It reports population,
ordered carriers, carriers with pending opposing evidence, and a count per
order. It is engineering observability, not an approved research endpoint.

## 11. Configuration, normalization, and containment

| Control | Default |
| --- | --- |
| `grammar_evolution_enabled` | `False` |
| `order_adoption_threshold` | `3` |

Grammar has a **dual dependency**: it requires language evolution *and*
compositional protolanguage. Each dependency carries its own notice, so a
manifest records exactly which requirement was unmet rather than a single
generic message. Requesting grammar without either dependency normalizes the
gate to false and emits the corresponding notices.

The dependency is enforced at three levels: configuration normalization, the
language runtime gate, and the canonical hash builder.

The experiment runner rejects the entire option family — exact spellings,
`=`-forms, and every unambiguous prefix — at both containment sites, before any
output root is created.

## 12. Hashing, reset, and pristine state

When grammar is effective, the canonical state hash includes each agent's
`constituent_order` and `opposing_order_evidence`, plus the grammar runtime
record. Both are gated on the effective flag, so every pinned pre-grammar hash
keeps its exact payload.

When grammar is disabled, the pristine guard scans the living **and**
retained-dead cohorts for any agent carrying an order or pending evidence, and
separately requires the runtime itself to be pristine. A disabled feature must
be provably absent, not merely unused.

## 13. Causal isolation and non-goals

Grammar changes the arrangement of morphemes within an emitted signal and the
order rule an agent holds. It cannot change the already committed material
transfer or any inventory, currency, trust, relationship, partner choice,
social memory, coalition, faction, combat, reproduction, health, survival,
movement, or population state.

Grammar Evolution v1 does **not** add a parser, constituent structure,
recursion, agreement, inflection, arity beyond two, phrase-level ordering,
prestige, standardization, teaching institutions, or research conclusions.

## 14. Known limitations

- Minimal pairs require a hearer to have learned two composite meanings from
  the **same** speaker differing in exactly one dimension. Morphemes are
  speaker-specific, so pairs assembled across speakers share nothing and are
  correctly discarded. Populations where each hearer only ever receives one
  resource from one giver produce no inference at all.
- Individual barter is gift-only; exchange modality arises from faction trade.
  A run without faction trade can only form same-modality minimal pairs.
- Adoption is order-only. Agents never revise the morphemes themselves.
- The summary is internal and on demand; no grammar event, metrics column,
  artifact schema, or approved estimand exists.

## 15. Language roadmap

Implemented: Endogenous Language, Coalition Dialects, Language Contact,
Intergenerational Language, Lexical Evolution, Compositional Protolanguage,
Grammar Evolution.

Everything beyond this point is **Planned, not implemented**.

## 16. Implementation evidence

- `src/thalren_vale/language.py` — order space, derivation, inference,
  adoption, runtime, record, summary
- `src/thalren_vale/config.py` — controls, dual-dependency normalization
- `src/thalren_vale/economy.py` — owner threading to the communication sites
- `src/thalren_vale/reproducibility.py` — hash config, payload, pristine guard
- `src/thalren_vale/artifact_validation.py` — manifest validation
- `run_experiments.py` — option-family containment
- `tests/test_grammar_evolution.py` — 86 tests, mutation-verified
