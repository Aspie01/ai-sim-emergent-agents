# Lexical Evolution

## 1. Status and verified lexical-change gap

Lexical Evolution v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

The earlier language milestones already supported four distinct mechanisms:

- ordinary invention creates a signal when a sender has no usable production
  form for a meaning;
- ordinary and dialect-influenced learning copy an emitted signal exactly;
- Language Contact v1 can preserve contact evidence and later borrowing
  provenance for an exactly copied form;
- Intergenerational Language v1 copies bounded parental forms exactly into
  child comprehension.

Those mechanisms could create and select synonyms, but none changed the form of
an existing signal while preserving a direct source-form relationship. Lexical
Evolution v1 fills only that gap.

The implemented causal chain is:

```text
committed transfer
-> selected pre-existing usable production form
-> at most one deterministic substitution opportunity
-> descendant becomes the actual emitted signal
-> exact receiver learning
-> competition, promotion, forgetting, pruning, or extinction
```

This is genuine bounded signal-form descent, not relabelled invention or
ordinary synonym competition. It changes signals, not meanings, grammar,
social behavior, or material outcomes.

## 2. Authentic committed-transfer hook

`communicate()` is entered only through the existing language hook after a
Layer-4 individual or faction-mediated transfer has committed. Lexical
evolution creates an opportunity only when all of these are true:

- base language and lexical evolution are effectively enabled;
- the transfer has already committed;
- the sender already owns a usable production association selected by the
  authoritative production-selection rule.

A production association is usable exactly when:

```text
confidence >= MIN_USABLE_CONFIDENCE
```

`MIN_USABLE_CONFIDENCE` is `0.10`. For the intended `Meaning`,
`_select_production()` chooses greatest confidence and then the
lexicographically smallest `Signal` on a confidence tie. Selection happens
before lexical derivation. Descendant creation or collision does not trigger a
second selection or opportunity.

If no usable production exists, the ordinary invention path may run, but that
new invention creates no lexical opportunity in the same communication.
Failed or rolled-back transfers, births, all non-birth spawns,
intergenerational copying, maintenance, and background ticks create none.
There is at most one opportunity and one substitution attempt per authentic
communication.

## 3. Deterministic trigger and substitution derivation

Lexical evolution owns no RNG. Initialization freezes the domain-separated seed
identity:

```text
thalren-vale:lexical-evolution-v1|seed=<seed>
```

Both the trigger digest and substitution digest are SHA-256 records over these
canonical stable inputs:

- the lexical seed domain;
- the proposed mutation opportunity index;
- current tick;
- sender stable ID;
- receiver stable ID;
- canonical `Meaning.name`;
- source `Signal` length and ordered token tuple;
- one fixed purpose domain: `trigger` or `substitution`.

The derivation deliberately excludes coalition IDs,
`CoalitionCommunicationContext`, coalition snapshots, dialect state, contact
state, formal factions, relationships, Python hashes, mapping order, object
addresses, and every RNG state. From identical lexical state and participants,
toggling dialect or contact processing cannot change the trigger decision or
descendant signal. Those extensions may still apply their normal learning
rates and counters after the signal is emitted.

The rate decision compares the first eight trigger-digest bytes with the exact
finite `lexical_mutation_rate` ratio. A rate of `0.0` never triggers; `1.0`
always triggers when lineage depth permits.

## 4. One-token substitution operator

Lexical Evolution v1 implements only
`LexicalMutationOperation.SUBSTITUTION`. A permitted trigger:

1. chooses `digest[0] % source_length` as the position;
2. chooses `1 + digest[1] % (PHONEME_COUNT - 1)` as a nonzero token offset;
3. replaces that token with:

   ```text
   (source_token + offset) % PHONEME_COUNT
   ```

The descendant has the same length as the source, exactly the recorded
position differs, every token remains in `0..PHONEME_COUNT-1`, and the
descendant cannot equal the source. The existing signal length bounds remain
valid automatically. There is no deletion, insertion, shortening,
lengthening, retry loop, fallback search, or global uniqueness check.

For each eligible opportunity:

1. the proposed future-affecting opportunity index advances once;
2. a false trigger emits the exact source and records a not-triggered outcome
   while observability is unsaturated;
3. a true trigger at the configured lineage-depth cap emits the exact source
   and records a depth-limit outcome while unsaturated;
4. a permitted true trigger performs exactly one substitution and records one
   successful mutation.

The index commits only with the complete language proposal. Any proposal
failure restores it.

## 5. Actual descendant emission and receiver acquisition

On a successful mutation, the descendant—not the source—is the signal actually
emitted. The ordinary communication path uses that exact signal for:

- `CommunicationOutcome.produced_signal`;
- receiver comprehension lookup;
- `UNKNOWN_SIGNAL`, `MISUNDERSTANDING`, and `SUCCESS` classification;
- correction, learning, and reinforcement;
- dialect and contact result accounting;
- contact exposure;
- generic or contact-qualified promotion.

The source is not also emitted or taught. No synthetic communication, contact
attempt, or dialect classification is created.

The receiver still uses exact-signal semantics. A descendant is a new exact
`Signal` key unless the receiver already owns that key. There is no fuzzy,
phonetic, or edit-distance comprehension. New receiver comprehension is
learned in the ordinary comprehension channel, and later communication remains
responsible for production promotion.

## 6. Sender descendant production and competition

If the sender lacks the exact descendant production key, the proposal creates
one association with:

- the source `Meaning` and derived descendant `Signal`;
- `confidence = INVENTION_CONFIDENCE`;
- zero observations, successes, and failures before emitted-use accounting;
- `last_used_tick` equal to the current tick;
- `origin = AssociationOrigin.INVENTED`;
- `learned_from_id = None`;
- valid `LexicalEvolutionProvenance`.

The existing communication-result accounting then updates the emitted
descendant exactly once. This does not increment the ordinary
`invention_count`, because the form descends from a selected source rather than
filling an unsupported meaning.

If the sender already owns the descendant key, that association is reinforced
rather than duplicated. Its origin, `learned_from_id`,
`BorrowingProvenance`, and any established immutable lexical provenance remain
unchanged. The current direct edge attaches only when the existing association
has no lexical provenance.

Source and descendant forms may coexist and compete as ordinary synonymous
production associations. Descendants receive no hidden confidence, salience,
or retention advantage.

## 7. Direct-edge lexical provenance and lineage depth

`LexicalEvolutionProvenance` stores one immutable bounded direct mutation edge:

- `first_mutation_tick`;
- `direct_source_signal`;
- `direct_source_owner_id`;
- `direct_source_origin`;
- `mutation_operation`;
- `mutation_position`;
- `mutation_index`;
- `lineage_depth`;
- `source_form_was_borrowed`.

It embeds no prior provenance object. The source and descendant have equal
length and differ at exactly the recorded position; all other tokens agree.
Validation requires the exact provenance dataclass and enum types, an exact
Boolean borrowed-source flag, and exact non-Boolean bounded integers for tick,
owner, position, index, and depth. A borrowed source requires
`direct_source_origin = AssociationOrigin.LEARNED`.
The mutation index is positive and no greater than the committed
`mutation_derivation_index`. The first mutation tick cannot exceed the
association's last-used tick. Historical direct-source owners may be dead, but
whole-state validation requires their IDs to belong to the complete run-scoped
stable-ID cohort.

A source without lexical provenance has depth zero, so its descendant has depth
one. When a descendant later mutates, the current signal and current speaker
become the new direct source, the depth becomes the source depth plus one, and
the new association records only that new direct edge. Earlier history survives
only as the scalar depth. A source already at
`maximum_lexical_lineage_depth` cannot mutate; that opportunity emits the exact
source and does not update `last_mutation_tick`.

There is no recursive ancestry, descendant list, lineage graph, global
registry, or source-owner lookup during ordinary processing.

## 8. Provenance channel separation and exact copying

Lexical provenance describes how a signal form was created. The other
provenance fields describe acquisition channels:

- `learned_from_id` is the immediate teacher when an association was first
  learned;
- `ContactExposure` records qualifying cross-coalition comprehension exposure;
- `BorrowingProvenance` records later contact-qualified production adoption;
- `IntergenerationalProvenance` records direct parental exposure;
- `LexicalEvolutionProvenance` records the mutation edge that created the form.

Valid combinations are:

```text
comprehension:
    LexicalEvolutionProvenance
    optional ContactExposure
    optional IntergenerationalProvenance

production:
    LexicalEvolutionProvenance
    optional BorrowingProvenance
```

Production never carries `ContactExposure` or
`IntergenerationalProvenance`. Exact ordinary learning, dialect-influenced
learning, language contact, generic promotion, contact-qualified promotion,
and intergenerational transmission may copy an existing lexical record exactly
when the destination association has none. Exact copying or reinforcement
never overwrites a different established lexical record.

Intergenerational transmission creates no mutation opportunity. It copies the
parental signal and existing lexical provenance exactly into child
comprehension, while recording direct-parent facts separately and creating no
child production fluency.

## 9. Borrowed sources and collision semantics

A production association carrying `BorrowingProvenance` may be selected and
mutated. A newly created descendant:

- does not copy `BorrowingProvenance`, source coalition IDs, or lender
  identity;
- has `AssociationOrigin.INVENTED`;
- records `source_form_was_borrowed = True` with only the bounded direct source
  edge.

Later contact-qualified adoption by another inhabitant may independently add a
new `BorrowingProvenance` while preserving the lexical record.

Collisions use only existing local association semantics:

- same-as-source output is impossible;
- an existing sender descendant production reinforces rather than duplicates;
- existing receiver comprehension follows ordinary reinforcement;
- existing receiver production keeps its established provenance;
- the same signal under another meaning remains subject to current ambiguity
  and per-signal bounds;
- an identical signal elsewhere in the population is allowed.

A collision is still one successful mutation and one descendant reinforcement.
If an association keeps an earlier immutable lexical record, the new committed
mutation index may have no distinct retained provenance record. No population
scan or global lexicon is used.

## 10. Canonical retention, forgetting, and extinction

The proposal completes source-side and receiver-side updates before running the
existing canonical retention passes. Total, per-meaning, and per-signal
association caps remain authoritative and insertion-order independent.
Lexical descendants receive no provenance-based retention preference.

Every actually removed association increments
`LanguageRuntimeState.lost_association_count` exactly once. Removing an
association removes its lexical, contact, borrowing, and intergenerational
metadata with it. No archive reconstructs discarded provenance. A pruned form
may reappear through a later independent mutation or exact learning event, but
the deleted edge is not restored automatically.

Ordinary maintenance can weaken, forget, and prune source or descendant forms.
A lexical lineage becomes unrepresented when no current association retains
one of its direct-edge records.

## 11. Transaction and rollback boundary

The material transfer commits before `communicate()` begins. Lexical mutation
does not determine whether it succeeds.

For lexical-enabled communication, the language transaction independently
copies:

- sender `AgentLanguageState`;
- receiver `AgentLanguageState`;
- `LanguageRuntimeState`;
- `LexicalEvolutionRuntimeState`;
- `CoalitionDialectRuntimeState` when dialect processing is enabled;
- `LanguageContactRuntimeState` when contact processing is enabled.

It validates configurations and gates, participant IDs and language states,
source selection, trigger and substitution derivation, descendant creation or
collision, emitted-signal interpretation, receiver learning, channel
provenance, promotion, retention, counters, saturation, and cross-runtime
invariants before commit.

Any exception restores every copied language owner and the proposed derivation
index relative to `communicate()` entry. It consumes no RNG. Material,
relationship, trust, route, social-memory, and event effects already committed
before the call are not rolled back. This is deliberately not
material-language atomicity.

## 12. Runtime counters and synchronized saturation

`SimulationState.lexical_evolution` owns one constant-size
`LexicalEvolutionRuntimeState`. It stores the frozen seed identity and controls,
the future-affecting `mutation_derivation_index`, and:

- `eligible_mutation_opportunity_count` (`O`);
- `mutation_trigger_count` (`T`);
- `mutation_not_triggered_count` (`X`);
- `successful_mutation_count` (`M`);
- `lineage_depth_limit_count` (`H`);
- `substitution_count` (`U`);
- `descendant_production_creation_count` (`C`);
- `descendant_production_reinforcement_count` (`R`);
- `borrowed_source_mutation_count` (`B`);
- `maximum_observed_lineage_depth`;
- `last_mutation_tick`.

While cumulative observability is unsaturated:

```text
O == T + X
T == M + H
M == U
M == C + R
0 <= B <= M
mutation_derivation_index == O
0 <= maximum_observed_lineage_depth
     <= maximum_lexical_lineage_depth
```

At `MAX_LEXICAL_OBSERVATION_OPPORTUNITIES`, the nine cumulative counters
`O, T, X, M, H, U, C, R, B` freeze together. The
`mutation_derivation_index` does not freeze because it affects future variant
derivation. Trigger decisions, mutations, communication, acquisition,
competition, and canonical pruning continue. Maximum observed depth continues
to update after every committed successful mutation, even when the descendant
is immediately pruned. `last_mutation_tick` advances only after a committed
successful mutation, never after a non-triggered or depth-limited opportunity.

The derivation index has its own absolute bound and fails closed before
overflow.

## 13. One-pass lexical summary

`lexical_evolution_summary()` is bounded on-demand engineering observability,
not a standard event, metric, CSV, manifest field, or approved research
endpoint. It:

- accepts and consumes a one-shot population iterable exactly once;
- performs one bounded association scan per inhabitant;
- performs no source-owner lookup or population pairing;
- performs no ancestry traversal or global lineage reconstruction;
- performs no population-wide sort;
- mutates no state and consumes no RNG;
- remains `O(P x L)` for population `P` and bounded language state `L`.

The summary separately reports retained and usable:

- all lexical-descendant carriers and associations;
- production-descendant carriers and associations;
- comprehension-descendant carriers and associations;
- associations and carriers whose direct source form was borrowed;
- current associations carrying later `BorrowingProvenance`;
- contact and intergenerational channel coexistence.

`LexicalEvolutionProvenance.source_form_was_borrowed` means the direct source
used during mutation carried borrowing provenance.
`BorrowingProvenance` instead means the current production association was
later adopted through contact. The two measures are independent. A descendant
with `source_form_was_borrowed=True` and no `BorrowingProvenance` contributes
to borrowed-source aggregates, not later-adoption aggregates.

Usability always means `confidence >= MIN_USABLE_CONFIDENCE`. Carrier totals
count each inhabitant at most once per category. Other bounded aggregates cover
meanings, lineage depths, descendant signals, source/descendant coexistence,
direct-source branching keyed by meaning/source owner/source signal, selected
descendant production share, retained mutation indices, current retained
maximum depth, and the canonical runtime record.

The six-decimal survival rates are:

```text
retained mutation survival rate
    = distinct retained mutation indices / successful mutation count

usable mutation survival rate
    = distinct usable mutation indices / successful mutation count
```

They are `None` when the denominator is zero or cumulative lexical
observability has saturated. A collision mutation may commit an index without
leaving a distinct retained direct-edge record, so these rates are bounded
state-survival measures, not complete lineage reconstruction.

## 14. Configuration, normalization, and containment

| Field / CLI | Default | Exact validation |
| --- | ---: | --- |
| `lexical_evolution_enabled` / `--enable-lexical-evolution` | `False` | Exact Boolean; requires effective base language only |
| `--disable-lexical-evolution` | n/a | Explicitly leaves lexical evolution disabled |
| `lexical_mutation_rate` / `--lexical-mutation-rate` | exact float `0.05` | Exact finite float `0.0 <= x <= 1.0` |
| `maximum_lexical_lineage_depth` / `--maximum-lexical-lineage-depth` | `8` | Exact non-Boolean integer `1..32` |

The feature does not require intergenerational language, coalitions, dialects,
language contact, social memory, formal factions, or settlements.

A request without effective base language normalizes only the lexical gate to
false, preserves both numeric controls, records
`lexical_evolution_requested_without_language`, and sets
`lexical_evolution_controls_status` to `normalized_uncontracted`. Exact
disabled defaults use `disabled`; enabled or nondefault controls without
normalization use `engineering_only_uncontracted`.

Missing historical lexical fields remain schema-valid but never V2-ready.
Missing, enabled, normalized, or nondefault lexical controls veto V2 readiness,
and an `ExpectedRunContract` cannot override that veto. The generic experiment
runner rejects the complete four-option family—including exact, equals,
unambiguous-prefix, and ambiguous-prefix spellings—before output-root creation
or mutation, command construction, verification mutation, or child launch.
Simulator and runner parsers use `allow_abbrev=False`.

The milestone changes no event, metric, artifact, manifest, summary, belief,
CSV, or ledger schema-version constant. Its summary remains an internal
on-demand return value.

## 15. Hashing, reset, and historical source validation

When enabled, canonical hashing includes:

- exact effective lexical controls, status, and notices;
- the base-language lexical runtime gate;
- the complete lexical runtime, including the derivation index;
- canonical `LexicalEvolutionProvenance` on production and comprehension
  associations.

Serialization uses stable IDs, enum values, bounded signal tuples, and ordered
association records. It contains no live source object, object address, Python
hash value, unordered-map dependence, or RNG internals.

When disabled, the dedicated runtime must be pristine, the base gate must be
false, and no living or dead association may contain lexical provenance.
Controls, gate, runtime, and metadata are omitted from the behavioral payload.
Hidden disabled state fails closed, no helper is entered, the derivation index
does not advance, and all pre-feature pinned hashes remain unchanged.

Whole-state hashing and reset validate all living and retained-dead language
owners, direct-source IDs against the complete stable-ID cohort, retained
mutation indices against the committed runtime, and lineage depths against
effective frozen controls. A dead historical source remains valid. Reset
prevalidates every owner before mutation, clears associations and attached
metadata under the established language reset, and restores a pristine lexical
runtime without partial reset.

## 16. Causal isolation, limitations, and evidence

Lexical mutation can change the exact-signal language outcome because the
descendant is genuinely emitted. It cannot change the already committed
material transfer or any inventory, currency, trust, relationship, partner
choice, social memory, coalition, faction, combat, reproduction, health,
survival, movement, or population state. This milestone added no
language-to-social or language-to-material feedback. The single reverse edge
in the system belongs to
[Language Coevolution v1](language-coevolution.md) and is independent of
lexical mutation.

Signals remain associations owned by individual inhabitants. There is no
global, coalition, faction, family, generation, or settlement lexicon; no
population signal registry; and no lineage graph or ancestry tree.

Only one-token substitution is implemented. Lexical Evolution v1 does not add
deletion, insertion, shortening, lengthening, recombination, fuzzy matching,
phonology, morphology, cognate inference, multi-part messages, grammar,
language identities, prestige, schools, institutions, standardization, or
research conclusions.

Completed engineering milestones are:

- `feature/endogenous-language-v1`;
- `feature/coalition-dialects-v1`;
- `feature/language-contact-v1`;
- `feature/intergenerational-language-v1`;
- `feature/lexical-evolution-v1`;
- `feature/compositional-protolanguage-v1`;
- `feature/grammar-evolution-v1`;
- `feature/language-coevolution-v1`.

Planned, not implemented:


The language milestone sequence is complete. Every further step is a
research authorization decision rather than an engineering one, and each
requires separate explicit authorization.

**Primary implementation:**

- `src/thalren_vale/language.py`: operation/provenance types, deterministic
  derivation, communication transaction, validation, retention, runtime
  records, exact provenance copying, and summary;
- `src/thalren_vale/economy.py`: authentic committed-transfer language hooks;
- `src/thalren_vale/config.py`: controls, types, ranges, dependency
  normalization, notices, and statuses;
- `src/thalren_vale/state.py` and `src/thalren_vale/sim.py`: runtime ownership,
  initialization, lifecycle, and reset;
- `src/thalren_vale/reproducibility.py`: enabled/disabled canonical hashing and
  whole-state validation;
- `src/thalren_vale/artifact_validation.py` and `run_experiments.py`:
  validation/readiness and complete option-family containment.

**Primary tests:**

- `tests/test_lexical_evolution.py`;
- `tests/test_language_evolution.py`;
- `tests/test_language_contact.py`;
- `tests/test_intergenerational_language.py`;
- `tests/test_language_interaction_hooks.py`;
- `tests/test_language_reproducibility.py`;
- `tests/test_coalition_dialects.py`;
- `tests/test_config.py`;
- `tests/test_simulation_state.py`;
- `tests/test_reproducibility.py`;
- `tests/test_artifact_validation.py`;
- `tests/test_experiment_runner.py`;
- `tests/test_run_termination.py`.

The accepted working tree completed the current full engineering suite with
**1,476 passed** after the bounded summary correction. That is software
verification, not a simulation run, research tier, effect-size result, or
scientific conclusion.
