# Intergenerational Language

## 1. Status and scientific contribution

Intergenerational Language v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

It fills a specific gap left by ordinary language communication. Before this
milestone, a newborn began with empty production and comprehension maps and
could learn only through later successfully committed aid or trade. That later
learning can still transmit forms indirectly, but it does not identify the
child's actual birth parents or create a birth-qualified acquisition channel.

The implemented causal chain is:

```text
successful committed birth
-> bounded deterministic parental exposure
-> child comprehension acquisition
-> ordinary later reinforcement, forgetting, pruning, or production promotion
```

This is acquisition, not genetic inheritance. No complete parent vocabulary is
copied, no production association is created at birth, and no signal changes
form during transmission. A parental form may already carry bounded lexical
provenance from Lexical Evolution v1, but birth transmission copies that form
and record exactly and creates no mutation opportunity. The milestone makes
bounded vertical continuity and divergence observable without adding
birth-time mutation, composition, grammar, or language-to-society feedback.

## 2. Authoritative successful-birth hook

`sim.procreation_layer()` is the sole caller of
`transmit_intergenerational_language()`. The call occurs only after this
authoritative path has returned successfully:

```text
make_child(parent_a, parent_b, ...)
-> _spawn(child, memberships=...)
-> transmit_intergenerational_language(child, (parent_a, parent_b), ...)
```

At transmission entry, the exact child object is already:

- inserted into the living population;
- inserted into `grid_occupants`;
- inserted into an inherited formal faction's member list when applicable;
- assigned its committed stable ID, with the allocator advanced.

The exact two parent objects already selected by reproduction are passed
directly. The language helper performs no population scan and no parent lookup.
It never infers parents from display names, proximity, relationship strength,
coalition or faction membership, or linguistic similarity.

The hook is before religion inheritance and birth-event emission. A
transmission exception therefore prevents those later operations.

Founders, travelers, migration/disruption arrivals, plugin-created
inhabitants, and every other non-birth `_spawn()` path receive no parental
language exposure. Failed eligibility, naming, housing, child construction, or
admission also produces no transmission. Each successfully admitted child
enters the helper exactly once when the feature is effective.

## 3. Deterministic parental signal selection

The parents are required to be two distinct objects with distinct exact
nonnegative stable IDs. Both parent IDs must be lower than the committed child
ID. The helper sorts the parents by stable ID before validating their language
states for transmission, selecting forms, accounting, or constructing
provenance. Reversing the caller's tuple therefore cannot change child state,
counters, summary output, or the selected-state hash.

Each parent is a read-only source. Teaching does not alter parental confidence,
observations, success/failure counts, recency, production use, or any runtime
counter owned by ordinary communication.

A production association is eligible only when:

```text
confidence >= MIN_USABLE_CONFIDENCE
```

`MIN_USABLE_CONFIDENCE` is `0.10`. For each fixed `Meaning`, the existing
authoritative `_select_production()` rule selects at most one signal:

1. greatest confidence;
2. lexicographically smallest `Signal` on a confidence tie.

The selected per-meaning candidates are then ranked for the configured
per-parent cap by:

1. confidence descending;
2. successful uses descending;
3. failed uses ascending;
4. observation count descending;
5. last-used tick descending;
6. canonical `Meaning`;
7. lexicographic `Signal`.

The default cap is two meanings per parent. Selection is independent of mapping
insertion order, population order, faction order, coalition order,
`PYTHONHASHSEED`, and the simulation RNG.

## 4. Comprehension-only acquisition

Every selected parental form produces one child comprehension exposure.
Production is never created or reinforced by the birth hook.

For a missing `(Signal, Meaning)` comprehension key, the child receives:

- `origin = AssociationOrigin.LEARNED`;
- `learned_from_id` equal to the direct parent's stable ID;
- confidence equal to `intergenerational_learning_strength`;
- `observation_count = 1`;
- `successful_uses = 0`;
- `failed_uses = 0`;
- `last_used_tick` equal to the birth tick;
- one `IntergenerationalProvenance` record.

For an existing comprehension key, the implementation reuses the ordinary
observation-without-use update:

- confidence increases by the configured learning strength and is clamped and
  quantized by the base language rules;
- observation count increments;
- successful and failed use counts do not change;
- existing `origin` and `learned_from_id` remain unchanged;
- existing `ContactExposure` remains unchanged;
- immutable first-source intergenerational facts remain unchanged.

Birth exposure is not an ordinary communication event. It does not increment
communication attempts or outcomes, invention counters, generic
`learned_association_count`, dialect counters, or language-contact counters.
Later authentic communication remains responsible for successful-use
reinforcement and any ordinary production promotion.

## 5. Duplicate and competing parental forms

Duplicate and competing classifications are computed from both parents'
selected forms before child pruning.

For the same meaning and same signal:

- the one child comprehension association is created or reinforced twice;
- observation count represents both direct parental exposures;
- `parent_count` becomes `2`;
- `borrowed_parent_count` records whether zero, one, or both direct parental
  forms were borrowed;
- `duplicate_parent_form_count` increments once.

Because parents are processed by stable ID, the lower-ID parent supplies the
immutable first-source facts.

For the same meaning and different signals:

- two bounded child comprehension synonyms are proposed;
- `competing_parent_form_count` increments once for that meaning.

The duplicate and competing classifications are mutually exclusive for a
birth/meaning pair. Their runtime counters describe attempted bounded
acquisition even when canonical retention later removes one of the proposed
associations.

## 6. Intergenerational provenance

`IntergenerationalProvenance` is immutable bounded metadata attached only to a
child comprehension association. It records:

- `first_transmission_tick`;
- `first_parent_id`;
- `first_parent_signal_origin`;
- `first_parent_form_was_borrowed`;
- `parent_count`, either `1` or `2`;
- `borrowed_parent_count`, from `0` through `parent_count`.

Production associations may never carry this record. First-source fields never
change. A borrowed first-parent form must itself have a learned origin. The
first transmission tick cannot exceed the association's last-used tick, and
the first parent ID must be lower than the owning child's stable ID.

For a newly created association, `learned_from_id` equals `first_parent_id`.
An association that existed before the birth exposure may retain an earlier,
different `learned_from_id`; attaching the intergenerational channel does not
erase its first ordinary teacher. Later ordinary or contact learning preserves
the intergenerational record.

No parent list, family tree, teaching transcript, ancestor chain, or extinct
family archive is stored. Removing the association removes all its provenance;
there is no hidden transmission archive.

## 7. Borrowed parental forms and contact coexistence

A usable parental production association carrying `BorrowingProvenance` is
eligible under the same selection rules as any other usable form. The child
learns the unchanged signal directly from the parent.

The child does **not** receive the parent's:

- `BorrowingProvenance`;
- `ContactExposure`;
- historical source coalition ID;
- original lender identity.

Only the direct-parent facts
`first_parent_form_was_borrowed`, `borrowed_parent_count`, and the cumulative
`borrowed_parent_form_transmission_count` are recorded. Parental teaching is
not coalition contact and does not increment any dialect or contact runtime
field.

If the selected parental production association already carries
`LexicalEvolutionProvenance`, the child may receive that same bounded
direct-edge record on the exact copied comprehension association. This does not
copy `BorrowingProvenance`, create a new lexical edge, advance the lexical
derivation index, or reconstruct an ancestry chain.

Later authentic different-coalition communication may add `ContactExposure` to
the same comprehension association. `ContactExposure` and
`IntergenerationalProvenance` are independent bounded channels and may coexist
with `LexicalEvolutionProvenance`. Later production promotion does not copy
intergenerational provenance, but it may preserve the bounded lexical record;
it never inherits the parent's `BorrowingProvenance`.

## 8. Canonical retention, forgetting, and later promotion

The helper applies every parental exposure to a copied child state and then
runs the existing canonical retention pass exactly once. Existing total,
production-per-meaning, comprehension-per-meaning, and meanings-per-signal
bounds remain authoritative. Intergenerational associations receive no special
retention preference beyond their ordinary association fields.

Each association actually removed by retention increments
`LanguageRuntimeState.lost_association_count` exactly once. A rejected
candidate is not counted again, and its contact/intergenerational metadata
disappears with it.

Retained associations remain subject to normal weakening, forgetting, and
pruning. Ordinary successful communication may later reinforce them or promote
comprehension into production under the base/contact rules. No transmission
archive can restore a pruned form.

## 9. Exact-once sentinel and post-birth transaction

`IntergenerationalLanguageRuntimeState.last_transmission_child_id` is the
authoritative bounded duplicate-call sentinel. Every processed child ID must be
strictly greater than the prior value. Duplicate and out-of-order calls fail
before proposal mutation. Same-tick births remain valid because committed
stable IDs increase monotonically, and the same parent pair may teach multiple
different children.

The sentinel and `last_transmission_tick` both begin as `None`, advance only
when a proposal commits, and return to `None` on reset. They advance even when
neither parent has a usable form and after cumulative observability counters
saturate.

The language transaction begins **after** birth admission. It copies exactly:

- the child's `AgentLanguageState`;
- `LanguageRuntimeState`;
- `IntergenerationalLanguageRuntimeState`.

It validates exact controls, gates, frozen-control agreement, IDs, child and
parent language states, tick monotonicity, contact/borrowing metadata,
provenance, the duplicate sentinel, selection, acquisition, retention,
counters, and final cross-runtime invariants before commit. Parents remain
read-only. No RNG is consumed.

If proposal construction or commit fails:

- the exception propagates and fails the tick/run closed;
- the three language-owned mutable owners are restored relative to helper
  entry;
- parent language, dialect, contact, social, material, coalition, faction,
  population, and RNG state remain unchanged relative to helper entry;
- the child remains admitted;
- the consumed child ID remains consumed;
- parental food already deducted by reproduction remains deducted;
- religion inheritance and birth-event emission do not run.

Birth remains committed if transmission later fails. This is deliberately not
birth-language atomicity.

## 10. Runtime counters and synchronized saturation

`SimulationState.intergenerational_language` owns the constant-size dedicated
runtime. It freezes the effective meaning cap and learning strength and records:

- `successful_birth_transmission_attempt_count` (`A`);
- `parental_source_count` (`S`);
- `transmitted_signal_exposure_count` (`E`);
- `comprehension_association_creation_count` (`C`);
- `comprehension_association_reinforcement_count` (`R`);
- `parental_source_without_usable_signal_count` (`N`);
- `duplicate_parent_form_count` (`D`);
- `competing_parent_form_count` (`Q`);
- `borrowed_parent_form_transmission_count` (`B`);
- `last_transmission_tick`;
- `last_transmission_child_id`.

With `m = maximum_parental_meanings_per_parent`, unsaturated state must satisfy:

```text
S == 2A
E == C + R
0 <= N <= S
S - N <= E <= m(S - N)
0 <= B <= E
D >= 0
Q >= 0
D + Q <= floor(E / 2)
```

The cumulative counter family uses one synchronized saturation gate based on
`MAX_INTERGENERATIONAL_ATTEMPTS`. Once reached, all nine cumulative counters
freeze together. The feature still:

- performs actual acquisition;
- performs canonical pruning;
- advances `last_transmission_tick`;
- advances `last_transmission_child_id`;
- enforces duplicate-call protection.

This prevents partial counter saturation from violating the partition
invariants.

## 11. On-demand summary

`intergenerational_language_summary()` is bounded engineering observability,
not a standard event, metric, CSV, manifest field, or approved research
endpoint. It:

- consumes a one-shot population iterable exactly once;
- performs one population pass with bounded association work per inhabitant;
- performs no parent lookup or parent-child pairing;
- performs no genealogy traversal;
- performs no population-wide sort or inhabitant-pair enumeration;
- mutates no state and consumes no RNG;
- remains `O(P x L)` for population `P` and bounded language state `L`.

It reports population and retained/usable carrier counts, retained/usable
intergenerational association counts, retained/usable direct-parent source
exposures, single- and dual-parent associations, borrowed-parent source
exposures, fixed-meaning counts, agent/meaning slots with multiple retained
parental signals, generation-0/generation-1/generation-2+ cohorts, and the
canonical runtime record.

The two six-decimal rates are:

```text
retained exposure retention rate
    = retained parental source exposures / transmitted signal exposures

usable exposure retention rate
    = usable parental source exposures / transmitted signal exposures
```

Each rate is `None` when the denominator is zero. Retention does not prove
uninterrupted causal survival: later ordinary communication may reinforce the
same retained association.

## 12. Configuration, normalization, and containment

| Field / CLI | Default | Exact validation |
| --- | ---: | --- |
| `intergenerational_language_enabled` / `--enable-intergenerational-language` | `False` | Exact Boolean; requires effective base language |
| `--disable-intergenerational-language` | n/a | Explicitly leaves transmission disabled |
| `maximum_parental_meanings_per_parent` / `--maximum-parental-meanings-per-parent` | `2` | Exact non-Boolean integer `1..len(Meaning)`; currently `1..4` |
| `intergenerational_learning_strength` / `--intergenerational-learning-strength` | exact float `0.20` | Exact finite float `0.0 < x <= 1.0` |

The feature depends only on effective base language evolution. It does not
require coalitions, dialect influence, language contact, formal factions, or
settlements.

A request without effective base language normalizes only the
intergenerational gate to false, records
`intergenerational_language_requested_without_language`, and sets
`intergenerational_language_controls_status` to
`normalized_uncontracted`. Exact disabled defaults use `disabled`; enabled or
nondefault controls without normalization use
`engineering_only_uncontracted`.

Missing historical fields remain schema-valid but not V2-ready. Missing,
enabled, normalized, or nondefault intergenerational controls veto V2
readiness, and an `ExpectedRunContract` cannot override the veto. The generic
experiment runner rejects the complete four-option family—including exact,
equals, unambiguous-prefix, and ambiguous-prefix spellings—before output-root
creation or mutation, command construction, verification mutation, or child
launch. Both parsers retain `allow_abbrev=False`.

## 13. Hashing, reset, and historical parent IDs

When enabled, canonical hashing includes:

- exact effective controls, status, and notices;
- the base-language intergenerational runtime gate;
- complete dedicated runtime controls, counters, tick, and child sentinel;
- canonical `IntergenerationalProvenance` on comprehension associations.

Serialization uses stable integer IDs, fixed enum values, canonical signal
tuples, and ordered association records. It stores no live parent reference,
object address, Python hash value, unordered-map dependence, or RNG internals.

When disabled, the dedicated runtime must be pristine, the base gate must be
false, and no living or dead association may hide intergenerational metadata.
Controls, gate, runtime, and metadata are omitted from the behavioral hash
payload, preserving the pinned pre-feature hashes. Hidden disabled state fails
closed.

Historical `first_parent_id` remains valid after parental death. Whole-state
hashing and reset validate parent IDs against the complete authoritative
stable-ID cohort, including retained dead inhabitants; the parent need not
remain living. Ordinary birth transmission and language communication perform
no population lookup.

Reset validates every living and dead language owner, provenance parent IDs,
runtime gates, counters, and sentinels before mutation. A successful reset
clears associations and metadata and restores a pristine
`IntergenerationalLanguageRuntimeState`. Malformed hidden state fails before a
partial reset.

## 14. Causal isolation and ownership

Language remains agent-owned. Parents, families, generations, formal factions,
informal coalitions, and settlements do not own dictionaries, official
languages, synchronized vocabularies, or language policy.

Intergenerational language cannot affect:

- reproduction eligibility, fertility, parent selection, mate choice, or birth
  success;
- naming, housing, newborn health/needs, survival, or mortality;
- parental or child inventories, currency, resource allocation, aid, or trade;
- relationships, trust, partner choice, coalition formation/lifecycle, formal
  factions, or settlements;
- combat, technology, diplomacy, religion, movement, or population policy.

The implementation adds no genealogy, family registry, caregiver system,
adoption mechanism, school, institution, recurring childhood teaching
schedule, juvenile stage, or language identity.

## 15. Limitations and future milestones

This milestone still transmits existing signals unchanged and creates no
lexical opportunity during birth. Lexical Evolution v1 is now implemented
independently for authentic committed-transfer communication and supports only
same-length one-token substitution with bounded direct-edge provenance.
Compositional Protolanguage v1 is likewise implemented independently: when it
is effective, the parental forms copied at birth are composed
`(resource, modality)` signals, and transmission copies them exactly without
creating a composition opportunity of its own. Birth
transmission does not add copying errors, shortening, recombination, cognate
inference, or ancestry reconstruction.

Also **Planned, not implemented**:

- `feature/language-research-readiness-v1` — **Planned, not implemented**.

The next milestone is `feature/language-research-readiness-v1`: **Planned, not implemented**.

No research plan, matrix, tier, evidence run, hypothesis, estimand, or
scientific conclusion is introduced by Intergenerational Language v1.

## 16. Implementation evidence

**Implementation status:** source-, test-, verification-, and final
acceptance-verified engineering feature; not research-ready.

**Primary source:**

- `src/thalren_vale/language.py`: provenance, runtime, deterministic selection,
  transactional acquisition, validation, records, parent-reference checks,
  and summary;
- `src/thalren_vale/sim.py`: sole post-`_spawn(child)` hook, initialization,
  lifecycle ordering, and reset;
- `src/thalren_vale/inhabitants.py`: child construction and parental food
  deduction before admission;
- `src/thalren_vale/state.py`: dedicated runtime ownership and stable-ID
  allocator;
- `src/thalren_vale/config.py`: controls, validation, dependency normalization,
  notices, and statuses;
- `src/thalren_vale/reproducibility.py`: enabled/disabled canonical hashing;
- `src/thalren_vale/artifact_validation.py`: artifact validation and readiness
  veto;
- `run_experiments.py`: complete option-family containment.

**Primary tests:**

- `tests/test_intergenerational_language.py`;
- `tests/test_lexical_evolution.py`;
- `tests/test_language_evolution.py`;
- `tests/test_language_contact.py`;
- `tests/test_language_interaction_hooks.py`;
- `tests/test_language_reproducibility.py`;
- `tests/test_config.py`;
- `tests/test_simulation_state.py`;
- `tests/test_reproducibility.py`;
- `tests/test_artifact_validation.py`;
- `tests/test_experiment_runner.py`;
- `tests/test_run_termination.py`.

The approved full engineering suite completed with **1,310 passed**. That is a
verification result for the implementation contract, not a scientific
conclusion. No simulation, experiment, benchmark, matrix, or research tier was
needed for this handbook update.
