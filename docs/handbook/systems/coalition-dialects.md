# Coalition-Associated Dialects

## 1. Overview

Coalition Dialects v1 applies bounded learning and reinforcement multipliers to
an authentic language occurrence when both communicators belonged to the same
active informal coalition in one frozen pre-economy snapshot. It does not create
communication, vocabulary, or coalition membership. All lexicons remain
inhabitant-owned, and the dialect feature gives every non-same-coalition context
base language rates with no penalty. The independent
[Language Contact v1](language-contact.md) extension may add positive
receiver-side learning and borrowing evidence for
`DIFFERENT_ACTIVE_COALITIONS`; that is not a dialect penalty or
coalition-owned language.
The independent [Lexical Evolution v1](lexical-evolution.md) extension may
change the actually emitted signal before interpretation. Its trigger and
substitution derivation do not read the shared coalition classification,
dialect runtime, or contact state.

The causal direction is strictly one-way:

```text
committed social history → informal coalition membership
informal coalition snapshot → language learning context
```

There is no language → coalition, relationship, partner-choice, faction, or
material-outcome arrow. See
[Causal chains](../architecture/causal-chains.md).

## 2. Why it exists

The feature lets repeated in-group communication converge faster while retaining
agent-carried vocabularies across joining, leaving, splitting, and dissolution.
It therefore measures dialect-like association without inventing coalition-owned
languages, direct out-group penalties, background synchronization, or social
feedback from comprehension success.

## 3. Key terminology

- **Membership snapshot:** immutable, factory-created copy of authoritative
  coalition membership and active IDs for one economy tick.
- **Source observation:** the last fully committed coalition transition, normally
  the immediately preceding tick.
- **Same active coalition:** sender and receiver map to the same active coalition
  ID in the snapshot.
- **Different active coalitions:** both are assigned, to different IDs.
- **Assigned/unassigned:** exactly one is assigned.
- **Both unassigned:** neither is assigned, although both are frozen active IDs.
- **Rate application:** one specific learning or reinforcement delta that uses a
  same-coalition adjusted rate.
- **Language contact:** independent positive acquisition/provenance extension
  that qualifies only different-active-coalitions communication.
- **Lexical opportunity:** independent deterministic form-substitution step
  for a pre-existing usable production association; coalition context is not a
  derivation input.

## 4. Current status

- `feature/coalition-dialects-v1`: **Implemented but experimental** in the
  documented revision.
- **Disabled by default** and **Engineering-only** when enabled or nondefault.
- Source and focused tests verify the implementation, but it is not
  research-ready.
- `run_experiments.py` rejects the complete dialect option family, including
  equals forms and every proper prefix.

## 5. State owned

`SimulationState.dialect` owns one constant-size
`CoalitionDialectRuntimeState`:

- `same_coalition_communication_count`;
- `different_coalition_communication_count`;
- `assigned_unassigned_communication_count`;
- `both_unassigned_communication_count`;
- `same_coalition_rate_application_count`;
- `last_classification_tick`.

The four context counters exactly partition the shared language communication
attempt count. The snapshot is not runtime history: it is an immutable
tick-scoped capability containing snapshot tick, source observation tick,
sorted active coalition IDs, sorted active inhabitant IDs, a private active-ID
frozenset, a private copied membership mapping, and bounded lineage values.

Coalitions own no signal registry, vocabulary, official language, borrowing
registry, or shared lexicon. Each inhabitant retains independent production and
comprehension state.

## 6. Inputs

Enabled processing requires all of:

- effective `LanguageEvolutionConfig`;
- effective enabled `CoalitionDialectConfig`;
- initialized `LanguageRuntimeState` whose dialect gate is true;
- valid `CoalitionDialectRuntimeState`;
- a factory-created `CoalitionMembershipSnapshot` for the communication tick;
- distinct sender and receiver stable IDs present in the snapshot's frozen
  active-ID set.

Classification reads only those stable IDs and two O(1) membership lookups. It
does not read names, formal factions, relationship topology, candidates, current
mutable coalition state, inventory, or language results.

## 7. Processing sequence

### Once before Layer 4

1. If dialect influence or Language Contact v1 is enabled, `economy_layer()`
   builds one complete snapshot before any economy transfer.
2. Tick 1 requires pristine coalition runtime. Later ticks require
   `last_observation_tick == snapshot_tick - 1`.
3. The builder validates the entire coalition runtime and active IDs, then copies
   the membership mapping and canonical ID tuples. Caller-owned dictionaries and
   member tuples are not retained.
4. The same object is passed through every individual and faction trade in that
   tick. Later end-of-tick coalition changes cannot alter it.

### Per committed communication

1. Validate constant-time snapshot provenance and freshness, communicator IDs,
   and active presence.
2. Perform two membership lookups and choose exactly one of the four contexts.
3. Copy sender lexicon, receiver lexicon, language runtime, dialect runtime,
   independent lexical runtime when enabled, and independent contact runtime
   when enabled.
4. If lexical evolution is enabled, derive at most one opportunity from the
   selected source without reading dialect/contact context. Finalize the
   language result from pre-learning comprehension of the actual emitted
   source or descendant signal.
5. For `same_active_coalition` only, calculate:

   ```text
   effective learning = quantize(clamp(base learning × learning multiplier, 0, 1))
   effective reinforcement = quantize(clamp(base reinforcement × reinforcement multiplier, 0, 1))
   ```

6. Apply adjusted rates only to correct unknown-signal learning,
   misunderstanding correction, successful sender production reinforcement,
   successful receiver comprehension reinforcement, and half-learning
   reinforcement of an existing matching receiver production association.
7. Keep base rates for failed-sender penalties, wrong-comprehension weakening,
   synonym competition, promotion tests, and forgetting.
8. Validate the language/dialect attempt partition and every proposed owner,
   then commit all four owners together. Roll back all four on any exception.

Different-coalition, assigned/unassigned, and both-unassigned occurrences use
base rates under the dialect gate. When Language Contact v1 is independently
enabled, only different-active-coalitions communication can use its stronger
positive correct-learning rate and borrowing path. No cross-group penalty
exists.

## 8. Outputs

Each enabled communication adds one context classification to its internal
`CommunicationOutcome`, increments exactly one context counter when the shared
attempt counter advances, and may increment the adjusted-rate application
counter.

For same-coalition occurrences, expected application increments are:

| Result/update | Increment |
| --- | ---: |
| Unknown-signal correct learning | 1 |
| Misunderstanding correction | 1 |
| Success: sender production | 1 |
| Success: receiver comprehension | 1 |
| Success: existing receiver production | Additional 1 |

Classification alone, `NO_SIGNAL`, penalties, wrong-meaning weakening, synonym
competition, promotion, and forgetting do not increment that counter.

Enabled exact controls and dialect runtime are included in canonical hashing.
Disabled dialect runtime must be pristine or hashing/reset fails closed.

## 9. Lifecycle position

The snapshot is created at the start of the communication-producing economy
layer whenever dialect or contact needs it. Authentic classifications occur
after each successful transfer commit.
Coalition transition happens near the end of the tick, so it affects the next
tick's snapshot, never a communication already classified. Language forgetting
runs after that transition. See
[Tick lifecycle](../architecture/tick-lifecycle.md).

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Informal coalitions | Coalition → dialect | Frozen active IDs and membership | Before economy | Supplies context only |
| Aid/trade | Economy → dialect | Authentic committed communicator pair | Post-commit | Triggers one classification |
| Endogenous language | Dialect → language | Adjusted same-coalition learning/reinforcement rates | After interpretation | Changes language state only |
| Language contact | Shared classification → language | Different-coalition positive acquisition and bounded provenance | After interpretation | Independent language-only extension |
| Lexical evolution | Selected usable form → emitted signal | Context-independent SHA-256 opportunity and substitution | Before interpretation | Independent language-only form change |
| Coalition lifecycle | Intentionally isolated | No language result | End of tick | IDs/membership unaffected |
| Material/social systems | Intentionally isolated | None | All times | No transfer, trust, faction, survival, or RNG effect |
| Hashing | Dialect → hash | Exact controls and runtime | Finalization | Fingerprints enabled behavior |

## 11. Configuration

| Field | Default | Valid range | Effect |
| --- | ---: | --- | --- |
| `coalition_dialect_influence_enabled` | `False` | Boolean; requires effective language and coalitions | Enables snapshot/classification path |
| `same_coalition_learning_multiplier` | `1.50` | Exact finite float 1.0–2.0 | Scales contextual/corrective learning |
| `same_coalition_reinforcement_multiplier` | `1.25` | Exact finite float 1.0–2.0 | Scales successful reinforcement |

Missing language and/or coalition dependencies normalize requested influence to
false and add the exact sorted notice or notices
`dialect_influence_requested_without_language` and
`dialect_influence_requested_without_coalitions`. Any enabled influence or
nondefault multiplier is `engineering_only_uncontracted`. See
[Configuration reference](../reference/configuration-reference.md).

Language contact has its own gate, defaults, normalization notices, runtime,
and counters. Neither language extension requires the other, but both require
effective base language and coalition emergence and share one snapshot and
classification when both are enabled.

Lexical evolution requires only effective base language. It does not require
coalitions, dialects, or contact and never reads this subsystem's
classification when deriving a variant.

## 12. Events

No standalone dialect event is emitted. Classification is internal to an
already-authentic language occurrence. No timer, raid, proximity conversation,
maintenance pass, legacy transfer, or failed attempt creates a dialect event.

## 13. Metrics

The runtime counters provide bounded engineering observability. The on-demand
`coalition_dialect_summary()` returns:

- snapshot tick and active-coalition count;
- per-coalition active member count;
- per-meaning speaker and non-speaker counts;
- dominant selected production signal and canonical frequency table;
- within-coalition pairwise agreement and mean usable agreement;
- frequency-based between-coalition lexical distance;
- the same records for the unassigned population;
- the current dialect runtime record.

Fewer than two speakers yields `None` for dialect pairwise agreement. Between
distance is `None` unless at least two coalitions each have at least two speakers
for the meaning. These are on-demand engineering summaries, not standard
metrics-CSV columns or approved research estimands.

## 14. Determinism and RNG

Dialect processing and summary calculation consume no RNG. Per-communication
work consists of constant-time snapshot validation, two active-ID checks, two
membership lookups, constant-time classification, and the existing bounded
`O(L)` language update.

Snapshot construction performs the `O(C + M)` coalition validation/copy once per
tick. Many communications therefore remain `O(C + M + I × L)`, not
`O(I × M)`. The on-demand summary consumes the supplied population exactly once
and inspects at most the bounded association cap per inhabitant, giving
`O(P × L)` aggregation. It performs no inhabitant-pair or coalition-pair
enumeration. Post-pass ordering is limited to bounded coalition IDs, the fixed
`Meaning` enum, bounded signal-frequency keys, and fixed runtime fields. See
[Determinism and RNG](../architecture/determinism-and-rng.md).

When lexical evolution is enabled, the actual descendant signal can naturally
change the existing exact-signal result to which dialect rates apply. It does
not create a second communication or dialect classification, and toggling the
dialect gate cannot change the lexical trigger or descendant signal.

## 15. Failure and edge cases

- Missing, partial, wrong-type, forged, stale, future, or mismatched dialect
  inputs fail before language mutation.
- Snapshot construction is restricted to the validated factory; direct
  construction raises.
- Communicators absent from the frozen active-ID set fail even if they are live
  in later mutable state.
- A newly active unassigned inhabitant is classified unassigned only when its ID
  is present in the frozen snapshot.
- When influence is disabled, optional dialect arguments are rejected and no
  classification, adjusted-rate, or dialect-counter helper runs.
- Context counters cannot saturate independently: when the shared attempt count
  is saturated, neither it nor a context counter advances. The adjusted-rate
  counter saturates deterministically.
- Joining does not rewrite vocabulary; leaving, splitting, and dissolution do
  not erase it. A former member is summarized under its current coalition or the
  unassigned group.
- Dissolved coalition IDs are absent from a current summary.
- Summary input must contain each frozen active inhabitant exactly once; a
  one-shot iterable is supported.

## 16. Tests and validation

`tests/test_coalition_dialects.py` covers private immutable snapshots, all four
contexts, freshness and forgery rejection, dependency enforcement, disabled-path
isolation, exact adjusted updates and counters, saturation, four-owner rollback,
one snapshot per economy pass, constant-time classification, exact-once committed
hooks, material/lifecycle isolation, convergence, member-carried vocabularies,
one-pass linear summary work, insertion-order stability, frequency semantics, and
RNG/state isolation. `tests/test_language_reproducibility.py` covers enabled
dialect hashing and hash-seed independence. See
[Test reference](../reference/test-reference.md).

## 17. Worked example

At the start of tick 20, inhabitants 4 and 9 are frozen as members of coalition
3. A committed food transfer from 4 to 9 produces an unknown signal. The event
remains `UNKNOWN_SIGNAL`; receiver 9 learns the correct food association using
`quantize(clamp(0.20 × 1.50, 0, 1)) = 0.30`, and the same-coalition context and
rate-application counters each advance once. If coalition 3 dissolves during the
end-of-tick transition, that does not reclassify the tick-20 event or erase
either lexicon. Tick 21's snapshot lists both inhabitants according to the new
authoritative state.

## 18. Current limitations

- Coalition context changes rates only; it creates no exposure opportunity.
- No out-group penalty, intelligibility-dependent transfer, or same-event rescue
  exists.
- Coalitions own no language and exert no institutional pressure.
- Language Contact v1 now provides bounded different-coalition contact evidence
  and borrowing, but no spatial contact zone, permanent bilingual identity,
  migration label, prestige, schooling, leadership, diplomacy, faction
  language, grammar, or inherited dialect exists.
- Lexical Evolution v1 now provides bounded one-token substitution, but no
  fuzzy intelligibility, phonology, morphology, composition, or grammar.
- Current summaries are on-demand and store no history.
- The feature is blocked from research experiment plans and V2 readiness.

## 19. Language roadmap

Completed engineering implementations:

- `feature/endogenous-language-v1`
- `feature/coalition-dialects-v1`
- `feature/language-contact-v1`
- `feature/intergenerational-language-v1`
- `feature/lexical-evolution-v1`

Planned, not implemented:

- `feature/compositional-protolanguage-v1` — **Planned, not implemented**
- `feature/grammar-evolution-v1` — **Planned, not implemented**
- `feature/language-coevolution-v1` — **Planned, not implemented**
- `feature/language-research-readiness-v1` — **Planned, not implemented**

In particular, language-driven coalition lifecycle and relationship feedback are
part of coevolution, not current dialect behavior.

The next milestone is `feature/compositional-protolanguage-v1`: **Planned, not implemented**.

## 20. Implementation evidence

**Implementation status:** current revision contains the complete engineering
slice; not research-ready.

**Primary source:**

- `src/thalren_vale/coalitions.py`: `CoalitionMembershipSnapshot`,
  `build_coalition_membership_snapshot()`,
  `validate_coalition_membership_snapshot()`,
  `classify_coalition_communication()`
- `src/thalren_vale/language.py`: dialect runtime/config validation,
  `communicate()`, `coalition_dialect_runtime_record()`,
  `coalition_dialect_summary()`
- `src/thalren_vale/economy.py`: exact-once authentic hooks
- `src/thalren_vale/sim.py`: once-per-tick pre-economy snapshot construction
- `src/thalren_vale/config.py`: normalization and statuses
- `src/thalren_vale/reproducibility.py`: enabled/disabled hashing

**Primary tests:**

- `tests/test_coalition_dialects.py`
- `tests/test_language_contact.py`
- `tests/test_language_evolution.py`
- `tests/test_lexical_evolution.py`
- `tests/test_language_interaction_hooks.py`
- `tests/test_language_reproducibility.py`
- `tests/test_informal_coalitions.py`
- `tests/test_config.py`
- `tests/test_simulation_state.py`
- `tests/test_reproducibility.py`
- `tests/test_artifact_validation.py`
- `tests/test_experiment_runner.py`

**Bounded verification commands used by the handbook project:** recorded in
[Test reference](../reference/test-reference.md). No simulation or experiment
was run while drafting this page.

**Unresolved discrepancy:** none in the documented one-way causal boundary. The
summary is deliberately on-demand and absent from standard artifacts, so it must
not be presented as a historical or research-ready metric series.
