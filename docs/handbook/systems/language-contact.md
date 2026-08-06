# Language Contact

## 1. Overview

Language Contact v1 is an implemented but experimental, disabled-by-default,
engineering-only extension to [Endogenous Language v1](endogenous-language.md)
and [Coalition Dialects v1](coalition-dialects.md). It adds stronger positive
receiver-side acquisition and bounded borrowing evidence to authentic
communication between inhabitants assigned to different active informal
coalitions. It does not add communication opportunities or make language
causal for any social or material outcome.

The verified causal boundary is exactly:

```text
authentic different-coalition communication
-> stronger receiver-side acquisition
-> bounded cross-boundary exposure evidence
-> contact-qualified borrowing promotion
-> mixed individual vocabularies
-> measurable contact-driven convergence or continued divergence
```

Language Contact v1 applies only to
`DIFFERENT_ACTIVE_COALITIONS`. Assigned/unassigned and both-unassigned
communication remain base-rate Language v1 behavior. Same-coalition
communication remains base Language v1 behavior unless the independent
Coalition Dialects v1 gate is enabled.

The independent [Lexical Evolution v1](lexical-evolution.md) extension may
substitute the selected sender form before interpretation. The one shared
contact classification still governs accounting while the receiver learns the
actual emitted descendant under the existing exact-signal rules.
Coalition/contact state is not an input to lexical derivation, and no extra
contact attempt is created.

## 2. Verified gap beyond the earlier language slices

Base Language v1 grounds communication only in successfully committed aid and
trade, resolves interpretation from pre-learning state, and updates individual
lexicons. Coalition Dialects v1 can accelerate learning and reinforcement for
members of the same frozen coalition, but deliberately gives every other
coalition context base rates.

Before Language Contact v1, different-coalition communication therefore had no
distinct positive acquisition rate, cross-boundary exposure record, or
contact-qualified production provenance. Language Contact v1 fills only that
gap. It reuses the same authentic communication, immutable coalition snapshot,
four-way coalition classification, bounded language associations, and
transaction boundary.

## 3. Sole contact source and classification

Contact can arise only inside an authentic `communicate()` call produced after
a successfully committed Layer-4 individual or faction-mediated transfer. The
same frozen `CoalitionMembershipSnapshot` used for dialect classification is
built once before the complete economy pass whenever dialect influence or
language contact is effective.

One shared classification places the sender and receiver in exactly one
context:

- `SAME_ACTIVE_COALITION`;
- `DIFFERENT_ACTIVE_COALITIONS`;
- `ASSIGNED_UNASSIGNED`;
- `BOTH_UNASSIGNED`.

Only `DIFFERENT_ACTIVE_COALITIONS` creates contact exposure, advances contact
outcome counters, applies the cross-group learning multiplier, or permits
contact-qualified borrowing. Proximity, timers, maintenance, raids, failed
transfers, Layer-1 swaps, and arbitrary population pairing create no language
contact.

## 4. Positive cross-group comprehension learning

The receiver's interpretation result is finalized from pre-learning state as
`SUCCESS`, `MISUNDERSTANDING`, `UNKNOWN_SIGNAL`, or `NO_SIGNAL`. Contact cannot
retroactively turn a teaching event into success.

For qualifying different-coalition communication, the effective learning rate
is:

```text
quantize(clamp(base language learning rate
               * cross-group learning multiplier, 0, 1))
```

This positive rate applies to the correct association learned after an unknown
signal or misunderstanding and to the half-learning update of an already
matching receiver production association after success. Successful sender and
receiver reinforcement remains at the base reinforcement rate. Failed-use
penalties, wrong-meaning weakening, synonym competition, pruning, and
forgetting also remain at base Language v1 rates. There is no out-group penalty.

## 5. Bounded contact evidence

`ContactExposure` is immutable metadata attached only to a comprehension
association. It records:

- first contact tick;
- first source speaker stable ID;
- first source coalition ID;
- bounded exposure count;
- bounded successful-comprehension count.

The first-source facts never change while that association survives. Counts
advance only for qualifying contact involving that exact signal and intended
meaning, saturate at the language-counter cap, and must remain subsets of the
association's observation and successful-use counts. Historical source
coalition IDs need not remain active.

Production associations cannot carry `ContactExposure`, and comprehension
associations cannot carry borrowing provenance. Hidden contact metadata while
contact is disabled fails closed.

The same comprehension association may independently carry
`IntergenerationalProvenance`. Later authentic contact can add or reinforce
`ContactExposure` without changing the association's immutable direct-parent
facts.

A comprehension association may also carry
`LexicalEvolutionProvenance`. Contact learning copies that bounded signal-form
record exactly when the destination has none while `ContactExposure`
independently records the immediate cross-coalition acquisition channel.

## 6. Contact-qualified borrowing provenance

`BorrowingProvenance` is immutable historical metadata attached only when a
new learned production association is promoted through the contact rule. It
captures the first-contact facts plus adoption tick, adoption speaker and
coalition, and the exposure and success counts at adoption.

An existing production association with the same meaning and signal is
reinforced but never retroactively relabelled as borrowed. A dissolved or absent
source coalition does not invalidate provenance. There is no global coalition
language registry or permanent historical-source registry.

## 7. Exact default three-contact progression

With the defaults—base learning `0.20`, cross-group multiplier `1.50`, exposure
threshold `3`, borrowing confidence threshold `0.50`, and base reinforcement
`0.10`—three repeated qualifying uses of one previously unknown signal produce:

| Contact | Pre-learning result | Comprehension confidence after update | Exposure / successes | Production |
| ---: | --- | ---: | ---: | --- |
| 1 | `UNKNOWN_SIGNAL` | `0.30` | `1 / 0` | None |
| 2 | `SUCCESS` | `0.40` | `2 / 1` | None |
| 3 | `SUCCESS` | `0.50` | `3 / 2` | Contact-qualified borrowed production |

The first unknown event remains unknown. Promotion is evaluated only after a
pre-learning `SUCCESS`, so merely reaching thresholds during misunderstanding
or unknown-signal correction cannot activate production in that same event.

## 8. Contact versus generic promotion

On a successful communication with no exact receiver production association,
the implementation evaluates both promotion routes:

- contact eligibility requires qualifying contact, retained `ContactExposure`,
  the configured exposure threshold, and the configured confidence threshold;
- generic eligibility requires confidence at least `0.50` and at least three
  successful comprehension uses.

Contact qualification has provenance precedence. If both rules qualify on the
same event, exactly one production association is created, exactly one learned
association is counted, and contact `BorrowingProvenance` is attached. If only
the generic rule qualifies, production has no borrowing provenance. Promotion
is exact-once for an existing key.

Generic and contact-qualified promotion preserve an existing bounded lexical
record. Production still cannot carry `ContactExposure` or
`IntergenerationalProvenance`; a contact-qualified production may carry both
its lexical direct-edge record and its separate `BorrowingProvenance`.

## 9. Mixed individual vocabularies, pruning, and relearning

All production and comprehension associations remain inhabitant-owned. An
individual may carry usable borrowed and nonborrowed forms, including synonyms
for the same meaning, within the existing structural and total association
caps. No permanent bilingual or mixed-language label is stored. The on-demand
summary calls an inhabitant mixed only when at least one same `Meaning` has both
a usable borrowed production association and a usable nonborrowed one.

Contact metadata does not protect an association from weakening or canonical
pruning. If an association is removed, its attached exposure or provenance is
removed with it. Later acquisition follows the same deterministic bounded
rules: surviving comprehension exposure may support a later production
promotion, while a newly recreated comprehension association starts new
first-contact evidence. There is no unbounded history and no stochastic
relearning path.

A parent may teach a form whose production association is contact-borrowed.
That birth exposure records only bounded direct-parent intergenerational facts:
it copies neither `BorrowingProvenance` nor `ContactExposure`, creates no
contact attempt, and does not treat the original source coalition as the
child's source. If that form already has lexical provenance, the birth path
copies the signal and bounded lexical record exactly without creating a new
mutation opportunity.

## 10. Runtime counters and invariants

`SimulationState.language_contact` owns one constant-size
`LanguageContactRuntimeState` with frozen effective controls and these bounded
observability fields:

- cross-coalition contact attempts;
- success, misunderstanding, unknown-signal, and no-signal outcomes;
- cross-group learning-rate applications;
- borrowing-candidate creations;
- borrowing promotions;
- borrowed-production uses;
- last contact tick.

The four result counters exactly partition contact attempts. Contact attempts
are a subset of base language communication attempts and, when dialect runtime
is also enabled, equal its different-coalition context count. Runtime controls
must exactly match effective configuration. The last contact tick cannot exceed
the last language communication tick. When the shared attempt counter is
saturated, partition counters freeze together while the last contact tick may
still advance.

All sender, receiver, base-language, optional dialect, and contact proposals are
validated before committing. A late exception restores every language-owned
owner. The already committed material transfer remains outside this language
transaction, as it was in base Language v1.

## 11. One-pass contact summaries

`language_contact_summary()` is an internal on-demand engineering summary. It
validates runtime partitions before calculation, accepts a one-shot population
iterable, and consumes it exactly once. During that pass it validates each
inhabitant once and aggregates commutative counts and bounded maps. It performs
no population-wide inhabitant sort, second population scan, inhabitant-pair
enumeration, or coalition-pair enumeration.

A production association is usable exactly when
`confidence >= MIN_USABLE_CONFIDENCE` (`0.10`). That rule governs usable totals,
borrowed totals and share, borrowed carriers, same-meaning mixed carriers,
selected production, selected borrowed-signal frequencies, source-coalition
diversity, and lexical distance. Below-threshold provenance remains valid state
but is inactive in current summary semantics.

The summary reports:

- usable and usable-borrowed production totals and six-decimal borrowed share;
- borrowed and same-meaning mixed carrier counts;
- the currently selected borrowed signal per meaning, using greatest
  confidence and lexicographically smallest signal on ties;
- distinct historical source coalitions from
  `BorrowingProvenance.first_source_coalition_id`;
- cross-coalition comprehension success over success, misunderstanding, and
  unknown signal, explicitly excluding `NO_SIGNAL`;
- per-meaning between-coalition lexical distance plus the mean of defined
  distances;
- separate current-coalition and unassigned aggregates and bounded runtime
  records.

Lexical distance uses coalition signal-frequency squares to count total and
matching ordered cross-coalition speaker pairs. It never enumerates inhabitants
or coalition pairs. Post-pass canonical sorting is limited to fixed meanings,
bounded active coalition IDs, bounded signals, historical source IDs represented
in current metadata, and fixed runtime fields. The result is invariant to
population, association, and membership-map insertion order and consumes no
RNG.

## 12. Configuration and normalization

| Field / CLI | Default | Valid range / dependency |
| --- | ---: | --- |
| `language_contact_enabled` / `--enable-language-contact` | `False` | Requires effective language evolution and coalition emergence |
| `--disable-language-contact` | n/a | Explicitly leaves contact disabled |
| `cross_group_learning_multiplier` / `--cross-group-learning-multiplier` | exact float `1.50` | Inclusive `1.0`–`2.0` |
| `borrowing_exposure_threshold` / `--borrowing-exposure-threshold` | `3` | Integer `2`–`32` |
| `borrowing_confidence_threshold` / `--borrowing-confidence-threshold` | exact float `0.50` | Inclusive `0.10`–`1.0` |

A contact request without effective base language and/or coalition emergence
normalizes contact off and records the sorted applicable notices:

- `language_contact_requested_without_language`;
- `language_contact_requested_without_coalitions`.

Enabled contact or any nondefault contact control is
`engineering_only_uncontracted`; a normalized request is
`normalized_uncontracted`; exact disabled defaults are `disabled`. Contact does
not require Coalition Dialects v1 and may be enabled independently of it. The
generic experiment runner rejects the complete contact option family before
root creation or child launch, and enabled/nondefault contact controls block
V2 readiness.

## 13. Lifecycle and reset

When contact is effective, initialization sets the contact gate in
`LanguageRuntimeState` and copies effective contact controls into the dedicated
runtime. The economy layer builds one coalition snapshot when either dialect or
contact classification needs it and threads the same object through all
authentic communication in that pass. End-of-tick language maintenance
validates contact-aware associations before forgetting, pruning, and dead-owner
cleanup.

`reset_runtime_state()` validates base-language, dialect, contact runtime, and
all living/dead contact metadata before any reset mutation. Disabled contact
requires a pristine runtime and no hidden association metadata. A successful
reset replaces the dedicated contact runtime with a pristine
`LanguageContactRuntimeState` and clears language associations under the
existing reset contract.

## 14. Reproducibility and hashing

Language Contact v1 imports or consumes no RNG. Its learning arithmetic is
clamped and quantized to six decimals; selection, pruning, serialization, and
summaries use canonical enum, stable-ID, coalition-ID, and signal ordering.

When contact is enabled, exact effective contact controls, runtime counters,
`ContactExposure`, and `BorrowingProvenance` participate in the selected-state
hash. Population and mapping insertion order and `PYTHONHASHSEED` do not alter
the canonical result. When contact is disabled, exact default controls are
nonbehavioral and omitted; hidden contact runtime or association metadata makes
hashing fail closed. This is still a selected-state fingerprint, not a
checkpoint or complete persistence format.

## 15. Causal isolation and non-goals

Coalitions do not own languages, lexicons, signals, borrowing registries, or
language policy. Language Contact v1 cannot affect:

- whether a transfer commits or what it transfers;
- relationships, trust, grievances, obligations, or partner choice;
- informal-coalition formation, persistence, split, dissolution, or membership;
- formal factions, settlements, diplomacy, technology, religion, or combat;
- inventory, currency, resources, health, movement, reproduction, survival, or
  population state.

The feature stores no migration identity, prestige, schooling, official
language, permanent bilingual label, or population-level language history.
Intergenerational transmission is now an independent implemented
comprehension-only birth extension; it does not change contact classification
or counters. Lexical Evolution v1 is an independent implemented substitution
extension whose derivation does not read contact classification. Compositional
Protolanguage v1 and Grammar Evolution v1 are likewise independent implemented
extensions that do not read contact classification. Language coevolution
remains planned rather than implemented.

## 16. Language roadmap

Completed engineering implementations:

- `feature/endogenous-language-v1`;
- `feature/coalition-dialects-v1`;
- `feature/language-contact-v1`;
- `feature/intergenerational-language-v1`;
- `feature/lexical-evolution-v1`;
- `feature/compositional-protolanguage-v1`;
- `feature/grammar-evolution-v1`;
- `feature/language-coevolution-v1`.

Planned, not implemented:

- `feature/language-research-readiness-v1` — **Planned, not implemented**.

The next milestone is `feature/language-research-readiness-v1`: **Planned, not implemented**.

## 17. Implementation evidence

**Implementation status:** source-, test-, correction-, and acceptance-verified
engineering feature; not research-ready.

**Primary source:**

- `src/thalren_vale/language.py`: contact metadata, runtime, transaction,
  maintenance validation, canonical records, and summary;
- `src/thalren_vale/coalitions.py`: immutable membership snapshot and shared
  communication classification;
- `src/thalren_vale/economy.py`: exact-once authentic transfer hooks and shared
  snapshot threading;
- `src/thalren_vale/config.py`: defaults, dependencies, normalization, and
  provenance status;
- `src/thalren_vale/sim.py` and `src/thalren_vale/state.py`: initialization,
  lifecycle, state ownership, and reset;
- `src/thalren_vale/reproducibility.py`: enabled and disabled hashing;
- `src/thalren_vale/artifact_validation.py` and `run_experiments.py`:
  validation/readiness and engineering-runner vetoes.

**Primary tests:**

- `tests/test_language_contact.py`;
- `tests/test_intergenerational_language.py`;
- `tests/test_lexical_evolution.py`;
- `tests/test_language_evolution.py`;
- `tests/test_language_interaction_hooks.py`;
- `tests/test_language_reproducibility.py`;
- `tests/test_coalition_dialects.py`;
- `tests/test_informal_coalitions.py`;
- `tests/test_config.py`;
- `tests/test_simulation_state.py`;
- `tests/test_artifact_validation.py`;
- `tests/test_experiment_runner.py`.

The contact summary is internal and on demand. No contact-specific standard
event, metrics column, research artifact schema, approved estimand, or executed
research evidence is introduced by this milestone.
