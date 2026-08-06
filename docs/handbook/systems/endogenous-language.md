# Endogenous Language

## 1. Overview

Endogenous Language v1 is a bounded observational protolanguage learned only
when Layer 4 successfully commits an aid or trade transfer. Inhabitants own
independent production and comprehension lexicons. A sender selects or invents
an abstract signal for the transferred resource meaning; the receiver interprets
it from pre-learning comprehension state; only then does the event update
language confidence, learning, reinforcement, and counters.

Language never determines whether the transfer succeeds and does not alter
inventory, currency, relationships, factions, coalitions, combat, health,
movement, reproduction, survival, or population state. See
[Causal chains](../architecture/causal-chains.md). The independent
[Language Contact v1](language-contact.md) extension can strengthen positive
receiver acquisition and record borrowing only for authentic communication
between different active coalitions; it preserves this isolation boundary.
The independent
[Intergenerational Language v1](intergenerational-language.md) extension can
seed bounded child comprehension from the exact parents after a successful
birth admission. It also preserves the one-way isolation boundary.
The independent [Lexical Evolution v1](lexical-evolution.md) extension can
derive one deterministic substitution from a pre-existing usable production
form and emit the descendant during authentic post-transfer communication. It
does not change transfer success or any social/material state.

## 2. Why it exists

The feature provides a minimal endogenous communication mechanism grounded in
real simulation interactions. Repeated partners can converge because successful
and corrective observations modify their own lexicons, while disconnected groups
can retain different signals. The bounded design makes that emergence
deterministic and auditable without introducing grammar, institutions, or an
additional RNG stream.

## 3. Key terminology

- **Meaning:** one closed resource concept: `FOOD`, `WOOD`, `ORE`, or `STONE`.
- **Signal:** a tuple of phoneme IDs from 0–7, length 2–4.
- **Production association:** an inhabitant's confidence in using a signal for a
  meaning.
- **Comprehension association:** an inhabitant's confidence that a signal means a
  particular meaning.
- **Invention:** deterministic creation of a signal when the sender has no usable
  production association.
- **Unknown signal:** the receiver has no usable pre-event interpretation.
- **Misunderstanding:** the receiver's strongest pre-event interpretation is the
  wrong meaning.
- **Promotion:** a sufficiently successful comprehension association becomes a
  production association.
- **Lexical descendant:** a signal produced by the bounded one-token
  substitution of an already usable source form, not ordinary invention.

## 4. Current status

- `feature/endogenous-language-v1`: **Implemented but experimental**.
- **Disabled by default** and **Engineering-only** when enabled or configured
  nondefault.
- The implementation is test- and source-verified but not research-ready.
- The experiment runner rejects every language-control spelling and prefix.

## 5. State owned

Every inhabitant owns a distinct `AgentLanguageState`:

- `production`: `(Meaning, Signal) → LexicalAssociation`;
- `comprehension`: `(Signal, Meaning) → LexicalAssociation`;
- `next_invention_index`: per-inhabitant deterministic counter.

Each immutable `LexicalAssociation` records meaning, signal, confidence,
successful and failed uses, observation count, last-used tick, origin
(`invented` or `learned`), optional source inhabitant ID, and—when Language
Contact v1 is effective—optional bounded comprehension exposure or production
borrowing provenance—and, when Intergenerational Language v1 is effective,
optional bounded direct-parent provenance on comprehension—and, when Lexical
Evolution v1 is effective, optional bounded direct-edge lexical provenance on
either channel.

`SimulationState.language` owns `LanguageRuntimeState`: the seed-domain identity,
attempt/result counters, invention/learning/loss counters, last communication
and forgetting ticks, and the dialect, contact, intergenerational, and lexical
gates. Dedicated dialect, contact, intergenerational, and lexical runtimes carry
their own bounded counters. No lexicon is shared by a parent, family,
generation, faction, or coalition.

## 6. Inputs

One communication requires two distinct active stable IDs, one supported
resource `Meaning`, an authentic `CommunicationContext`, current tick, exact
active-ID set, effective `LanguageEvolutionConfig`, initialized runtime, and the
sender's and receiver's independent language states.

The only live contexts are:

- `AID_TRANSFER`;
- `PAID_TRADE`;
- `FACTION_TRADE`.

Timer passes, proximity, arbitrary pairings, raids, maintenance, failed
transfers, and the legacy layer-one swap do not create communication.

## 7. Processing sequence

1. Validate config, runtime, tick, active IDs, distinct identities, state caps,
   nonaliased ownership, and monotonic time.
2. Copy sender state, receiver state, and language runtime into a proposal. If
   dialect influence or contact is active, classify one frozen coalition
   context; validate and copy the enabled dialect/contact runtimes before
   learning. When lexical evolution is active, validate and copy its dedicated
   runtime without using coalition classification in mutation derivation.
3. Select the sender's strongest usable production association. If none exists
   and invention is enabled, derive one signal from SHA-256 over the run seed
   domain, inventor stable ID, meaning, and that inventor's next index.
   A pre-existing selected form instead gets at most one lexical opportunity;
   if substitution succeeds, its descendant becomes the actual emitted signal.
   Ordinary invention never creates an opportunity in the same communication.
4. Select the receiver's strongest usable comprehension for the produced signal.
   Finalize `NO_SIGNAL`, `UNKNOWN_SIGNAL`, `SUCCESS`, or `MISUNDERSTANDING` from
   this pre-learning state.
5. Update the proposal:
   - failed sender use weakens its selected production association;
   - unknown signals create or reinforce correct comprehension;
   - misunderstandings weaken the selected wrong meaning and create or reinforce
     the correct meaning;
   - success reinforces sender production and receiver comprehension;
   - an existing matching receiver production association receives half the
     learning rate;
   - generic promotion can create receiver production after confidence reaches
     `0.50` and comprehension has at least three successful uses;
   - enabled contact can apply stronger positive correct learning, retain
     bounded cross-coalition exposure, and promote a borrowed production form;
   - competing synonyms and meanings are weakened deterministically.
6. Apply canonical retention and pruning, count every lost association, and
   validate all proposed owners and counters.
7. Commit sender, receiver, runtime, and optional
   dialect/contact/lexical runtimes together. Any exception restores the
   original language-owned owners, including the lexical derivation index.

An unknown signal remains `UNKNOWN_SIGNAL` in the event that teaches it. A
misunderstanding remains `MISUNDERSTANDING` in the event that corrects it.
Learning cannot retroactively create same-event success.

Intergenerational acquisition does not call this communication sequence. Its
sole hook is after a successful `_spawn(child)` in reproduction, uses the exact
two parents as read-only sources, creates or reinforces comprehension only, and
does not increment ordinary communication, invention, or generic learning
counters.

Intergenerational exact copying may preserve existing lexical provenance, but
it creates no lexical opportunity and does not advance lexical runtime.

## 8. Outputs

`communicate()` returns a `CommunicationOutcome` containing tick, communicator
IDs, transfer context, intended meaning, produced signal, pre-learning
interpretation, result, and optional coalition classification. It updates only
language-owned state and counters.

When lexical mutation succeeds, `produced_signal` is the descendant, and every
receiver, dialect, and contact consequence uses that same exact signal. The
source is not also emitted.

Enabled lexicons, exact language controls, and runtime counters are included in
the final behavioral hash. Disabled language requires every inhabitant and
runtime to remain pristine; hidden state causes hashing to fail closed.

## 9. Lifecycle position

The run initializes the language seed domain immediately after seeding the core
simulation. Communication occurs only after successful Layer-4 transfers.
Optional intergenerational exposure occurs earlier in the tick, immediately
after a birth admission commits and before religion inheritance or birth-event
emission.
Lexical evolution occurs only within post-transfer communication and never
during birth exposure or maintenance.
`maintain_language_state()` runs once in the end-of-tick emergent pass, after
relationship and coalition maintenance and before authoritative observation.
See [Tick lifecycle](../architecture/tick-lifecycle.md).

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Aid/trade | Economy → language | Actual sender, receiver, resource meaning | After transfer commit | Creates one communication |
| Inventory/currency | Intentionally isolated | Language reads only grounded meaning | Layer 4 | Interpretation cannot alter transfer |
| Social relationships | Intentionally isolated | None from language | All times | No trust or partner-choice feedback |
| Informal coalitions | Coalition → optional dialect/contact context | Frozen stable-ID membership | Same economy tick | Can adjust language learning or qualify contact only |
| Language contact | Different-coalition context → language | Positive receiver learning and bounded exposure/provenance | After interpretation | Changes individual language state only |
| Birth/population | Successful birth → language | Exact child/parents and usable parental production | After `_spawn(child)` | Bounded child comprehension only |
| Lexical evolution | Committed transfer/source form → language | Stable event inputs and one substituted signal | Inside communication | Actual descendant emission and individual competition only |
| Death | Population → language maintenance | Newly dead owners | End of tick | Clears lexical associations |
| Hashing | Language → hash | Canonical lexicons/runtime | Finalization | Fingerprints enabled state |

## 11. Configuration

| Field | Default | Valid range | Effect |
| --- | ---: | --- | --- |
| `language_evolution_enabled` | `False` | Boolean | Enables communication and maintenance |
| `maximum_language_associations` | `32` | Integer 1–40 | Combined production/comprehension cap |
| `maximum_signal_length` | `3` | Integer 2–4 | Effective invention length ceiling |
| `language_learning_rate` | `0.20` | Exact finite float `(0.0, 1.0]` | New/corrective learning delta |
| `language_reinforcement_rate` | `0.10` | Exact finite float `(0.0, 1.0]` | Successful-use delta and base penalties |
| `language_forgetting_interval` | `25` | Positive integer | Forgetting cadence and inactivity age |
| `language_invention_enabled` | `True` | Boolean | Allows signal invention |

Hard structural caps additionally allow at most two production signals per
meaning, eight comprehension signals per meaning, and two comprehension meanings
per signal. See
[Configuration reference](../reference/configuration-reference.md).

## 12. Events

Language does not emit a standard structured event or narrative event. The
`CommunicationOutcome` is an internal return value, and runtime counters plus
canonical snapshots provide engineering observability. Economy events continue
to describe the committed transfer, not the receiver's interpretation.

## 13. Metrics

`LanguageRuntimeState` counts attempts, successes, misunderstandings, unknown
signals, no-signal outcomes, inventions, learned associations, lost
associations, and last communication/forgetting ticks.
`lexical_convergence_snapshot()` provides per-meaning speaker counts, active
signals, dominant signal, frequency records, pairwise agreement, and population
agreement. These are on-demand engineering summaries, not standard metrics-CSV
columns or approved research estimands.

`lexical_evolution_summary()` separately aggregates retained/usable production
and comprehension descendants, carriers, provenance channels, borrowed-source
descendants, direct-edge groupings, depths, selected shares, survival rates,
and the dedicated runtime in one `O(P x L)` population pass. See
[Lexical evolution](lexical-evolution.md).

## 14. Determinism and RNG

`language.py` imports no RNG. Invention uses a canonical SHA-256 record under
`thalren-vale:endogenous-language-v1`, not Python's salted `hash()` and not the
simulation PRNG. Per-inhabitant indices prevent one agent's invention from
perturbing another's signal. Confidence values are clamped and rounded to six
decimals, and selection/pruning use enum and signal ordering. Language hooks do
not change the core PRNG position. Birth transmission adds no RNG: parent order
and parental-form salience are canonical. Lexical mutation uses a separate
SHA-256 domain and monotonic opportunity index, with no RNG and no
coalition/dialect/contact derivation input. See
[Determinism and RNG](../architecture/determinism-and-rng.md).

## 15. Failure and edge cases

- Missing, wrong-type, inactive, duplicate, self, or aliased participants fail
  before mutation.
- Unsupported resources such as water have no language meaning.
- Invention disabled plus no usable production yields `NO_SIGNAL`.
- Stale ticks, malformed associations, cap violations, invalid source IDs, and
  counter overflow fail closed.
- A failed proposal leaves both lexicons, invention index, runtime, external
  state, and RNG unchanged.
- Forgetting runs only on exact configured boundaries; an empty boundary is a
  true no-op.
- Due maintenance validates and visits each active/dead owner, weakens inactive
  associations by half the base reinforcement rate, prunes canonically, and
  clears dead owners' associations while retaining their invention indices.
- Reset validates all living/dead language states and
  language/dialect/contact/intergenerational/lexical runtimes plus historical
  parent and lexical source IDs before clearing authoritative state.

## 16. Tests and validation

`tests/test_language_evolution.py` covers the closed meanings, pinned invention
vectors, caps, unknown learning, success, misunderstanding, collisions,
competition, promotion, pruning, proposal rollback, forgetting complexity,
death cleanup, convergence, RNG absence, and canonical ordering.
`tests/test_language_interaction_hooks.py` proves exact-once committed-transfer
hooks, zero failed hooks, role ordering, causal isolation, maintenance order, and
RNG preservation. `tests/test_language_reproducibility.py` covers hash-seed
independence, per-agent invention isolation, enabled hashing, insertion order,
and disabled fail-closed behavior. `tests/test_language_contact.py` covers the
approved different-coalition acquisition, exposure, borrowing, summary, and
isolation extension. `tests/test_intergenerational_language.py` covers the
post-admission birth hook, partial comprehension, parent ordering, duplicate
and competing forms, provenance, rollback, saturation, summary, hashing,
reset, and causal isolation. See
[Test reference](../reference/test-reference.md).

`tests/test_lexical_evolution.py` covers authentic opportunities, pinned
derivation vectors, actual descendant emission, direct-edge provenance,
copying/channel coexistence, collisions, depth, saturation, summary
aggregation, rollback, hashing, reset, and causal isolation.

## 17. Worked example

Sender 7 transfers food to receiver 12 and has no food signal. With invention
enabled, the sender derives a deterministic signal from its seed domain, stable
ID, `FOOD`, and invention index 0. Receiver 12 has never seen that signal, so the
event result is `UNKNOWN_SIGNAL`. The transfer remains successful, and only
after that result is fixed does receiver 12 gain a learned comprehension
association for `FOOD` at the learning rate. A later occurrence can succeed;
the teaching occurrence cannot.

## 18. Current limitations

- Meanings cover only food, wood, ore, and stone.
- Signals are abstract bounded phoneme tuples, not text or speech.
- No background conversation or vocabulary synchronization exists.
- Mixed borrowed and nonborrowed individual vocabularies can now arise under
  Language Contact v1, and bounded parental comprehension can arise under
  Intergenerational Language v1. Bounded same-length one-token substitution now
  creates lexical descendants under Lexical Evolution v1. There is still no
  complete vocabulary
  inheritance, migration identity, permanent bilingual label, grammar, syntax,
  deletion, insertion, shortening, lengthening, recombination, fuzzy
  comprehension, composition, teaching institution, prestige, or faction
  language.
- Comprehension has no effect on material transfer outcomes.
- Standard artifacts expose hashes and controls but no dedicated language event
  stream or research-ready metric contract.

## 19. Language roadmap

Completed engineering implementations:

- `feature/endogenous-language-v1`
- `feature/coalition-dialects-v1`
- `feature/language-contact-v1`
- `feature/intergenerational-language-v1`
- `feature/lexical-evolution-v1`
- `feature/compositional-protolanguage-v1`
- `feature/grammar-evolution-v1`
- `feature/language-coevolution-v1`

Planned, not implemented:


The language milestone sequence is complete. Every further step is a
research authorization decision rather than an engineering one, and each
requires separate explicit authorization.
The research-readiness milestone will define a later evidence contract; it does
not make the current engineering implementation research-ready.

## 20. Implementation evidence

**Implementation status:** source- and test-verified engineering feature; not
research-ready.

**Primary source:**

- `src/thalren_vale/language.py`: all language state, validation,
  `derive_invention_signal()`, `communicate()`, `maintain_language_state()`, and
  summaries
- `src/thalren_vale/economy.py`: authoritative committed-transfer hooks
- `src/thalren_vale/sim.py`: initialization and maintenance ordering
- `src/thalren_vale/config.py`: `LanguageEvolutionConfig`
- `src/thalren_vale/reproducibility.py`: canonical enabled/disabled hashing

**Primary tests:**

- `tests/test_language_evolution.py`
- `tests/test_language_interaction_hooks.py`
- `tests/test_language_contact.py`
- `tests/test_intergenerational_language.py`
- `tests/test_lexical_evolution.py`
- `tests/test_language_reproducibility.py`
- `tests/test_simulation_state.py`
- `tests/test_reproducibility.py`
- `tests/test_config.py`
- `tests/test_artifact_validation.py`
- `tests/test_experiment_runner.py`

**Bounded verification commands used by the handbook project:** recorded in
[Test reference](../reference/test-reference.md). No simulation or experiment
was run while drafting this page.

**Unresolved discrepancy:** language summaries and outcomes are richly
test-observable but are not yet first-class standard artifacts; they must not be
described as current research metrics.
