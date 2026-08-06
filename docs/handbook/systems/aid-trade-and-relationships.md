# Aid, Trade, and Directed Relationships

## 1. Overview

Layer 4 moves resources through individual aid or paid exchange and through
faction-mediated trade. When social memory is enabled, a successfully committed
transfer also updates bounded, directed `Relationship` records between the two
inhabitants who actually gave and received the resource. Merely considering a
partner, failing an eligibility check, or attempting a transfer does not create
social memory.

This page covers the interaction boundary shared by economy, social memory, and
language. For its place in the complete tick, see
[Tick lifecycle](../architecture/tick-lifecycle.md).

## 2. Why it exists

The economy needs immediate resource movement. The optional social-memory layer
adds a persistent record of repeated authentic contact without replacing the
legacy integer `trust` mapping or changing the disabled baseline. Those directed
records can later bias an otherwise available barter opportunity and, when
coalitions are enabled, supply the only graph edges from which informal
coalitions emerge.

## 3. Key terminology

- **Committed transfer:** inventory and any payment have actually moved.
- **Individual aid:** a one-unit transfer for which the recipient pays no
  currency.
- **Individual paid trade:** the same one-unit transfer with a positive payment.
- **Faction-mediated trade:** a resource transfer between a donor selected from
  one formal faction and a taker selected from another.
- **Directed relationship:** one inhabitant's record about another, keyed by the
  target's stable inhabitant ID.
- **Legacy trust:** the older name-keyed integer mapping used by existing
  mechanics. It is distinct from `Relationship.trust`.
- **Partner bias:** a bounded redirection of an existing barter opportunity
  toward a known eligible partner; it is not a global partner search.

## 4. Current status

- Aid and trade economy mechanics: **Implemented but experimental**.
- Persistent social memory: **Implemented but experimental**, **Disabled by
  default**, and **Engineering-only**.
- Relationship-biased partner choice: **Implemented but experimental**,
  **Disabled by default**, and **Engineering-only**.
- Research status: not research-ready; the experiment runner rejects all social
  control flags.

## 5. State owned

Each inhabitant owns `relationships: dict[int, Relationship]`. Every relationship
contains:

| Field | Range or meaning |
| --- | --- |
| `trust` | `[-1.0, 1.0]` |
| `affinity` | `[-1.0, 1.0]` |
| `grievance` | `[0.0, 1.0]` |
| `obligation` | `[0.0, 1.0]` |
| `familiarity` | `[0.0, 1.0]` |
| `interaction_count` | Number of committed observations in this direction |
| `last_interaction_tick` | Most recent authentic update |

The economy separately owns inventories, inhabitant currency, faction currency
and prices, trade routes, raid/scarcity records, and the legacy trust and
`trade_count` effects. Social memory does not own those stores.

## 6. Inputs

Individual barter reads current positions, inventories, currency, stable IDs,
and—when partner bias is enabled—existing directed relationships. Faction trade
also reads formal faction membership, faction prices, diplomacy trade bonuses,
alliances, and rivalry tension.

Social recording accepts only `InteractionKind.AID` or
`InteractionKind.TRADE`, distinct active stable IDs, a nonnegative tick, a
finite magnitude in `(0.0, 1.0]`, and effective `SocialMemoryConfig` controls.

## 7. Processing sequence

### Individual transfer

1. Group co-located inhabitants and perform the existing one shuffle per
   nontrivial tile.
2. Consider adjacent baseline pairs. A giver must hold at least three units of a
   tradable resource and the recipient must hold zero.
3. If partner bias is enabled, redirect only an already valid baseline
   opportunity to a positively scored, co-located, currently eligible known
   partner. Every fourth `(tick + giver_id)` opportunity remains exploratory and
   retains the baseline partner.
4. Commit exactly one unit from giver to recipient.
5. Increment the legacy name-keyed trust and trade counters in both directions.
6. Transfer payment up to the resource's base price. Positive payment classifies
   the social outcome as trade; zero payment classifies it as aid.
7. After commitment, update social memory exactly once and invoke language
   communication exactly once when those features are enabled.

### Faction-mediated trade

1. Select an eligible resource and the donor with sufficient inventory.
2. Select a taker from the receiving formal faction.
3. Move inventory, apply diplomacy and route bonuses, transfer available
   currency, reduce rivalry tension, and update trade-route state.
4. Record one reciprocal personal trade relationship between the actual donor
   and taker.
5. Invoke one `FACTION_TRADE` language occurrence for those same inhabitants.

### Relationship maintenance

At the end-of-tick emergent-state pass, the simulation removes dead, inactive,
self, malformed, and unassigned-ID ties; decays inactive records on the configured
interval; and prunes each inhabitant to the configured cap. The authoritative
maintenance order is social, coalition, then language.

## 8. Outputs

Committed transfers can change inventory, currency, legacy trust, trade counts,
beliefs, rivalry tension, trade routes, and personal `Relationship` records.
Language state can also change through the post-commit hook, but interpretation
never controls whether the transfer succeeds.

Canonical hashing includes relationship records only when social memory is
enabled. If social memory is disabled, hidden relationship state is rejected
rather than silently omitted.

## 9. Lifecycle position

Individual and faction trades execute inside Layer 4, after procreation and
before combat. Relationship maintenance executes near the end of the same tick,
after all simulation and anti-stagnation work and before structured observation.
The wider causal ordering is documented in
[Causal chains](../architecture/causal-chains.md).

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Inhabitants/resources | Economy writes | Inventory and currency | Layer 4 | Commits transfer |
| Formal factions | Economy reads/writes | Members, prices, routes, rivalry | Layer 4 | Mediates inter-faction trade |
| Social memory | Economy → social | Actual giver, recipient, kind, tick | Post-commit | Updates directed ties |
| Partner choice | Social → economy | Positive relationship score | Future Layer 4 opportunities | May redirect one eligible baseline pair |
| Informal coalitions | Social → coalition | Reciprocal qualifying ties | End of tick | Supplies coalition graph only |
| Endogenous language | Economy → language | Actual communicators and resource meaning | Post-commit | Creates one authentic communication |
| Events/metrics | Economy → observation | Trade/route text and state | Layer 4/end of tick | Diagnostic and artifact observation |

Formal factions and informal coalitions are separate memberships. A
faction-mediated transfer can strengthen personal relationships but does not
directly assign either inhabitant to an informal coalition.

## 11. Configuration

| Field | Default | Valid range | Effect |
| --- | ---: | --- | --- |
| `social_memory_enabled` | `False` | Boolean | Enables persistent directed records |
| `social_partner_bias_enabled` | `False` | Boolean; requires social memory | Allows bounded redirection |
| `maximum_social_ties` | `32` | Integer 1–128 | Per-inhabitant cap |
| `relationship_decay_interval` | `25` | Positive integer | Maintenance cadence and inactivity threshold |

Requesting partner bias without social memory normalizes bias to false and adds
`partner_bias_requested_without_social_memory`. Any enabled or nondefault social
control is `engineering_only_uncontracted`. See
[Configuration reference](../reference/configuration-reference.md).

## 12. Events

Economy emits or appends trade, trade-route, scarcity, and raid observations.
Individual transfers intentionally remain internal state changes and do not
receive a dedicated event row. `record_interaction()` emits no event of its own;
its authoritative evidence is state plus tests and the enabled state hash.

## 13. Metrics

No dedicated social-memory columns are currently written to the standard metrics
CSV. `relationship_summary()` provides bounded on-demand counts of active,
positive, and negative directed ties plus mean trust and grievance. Canonical
relationship snapshots are ordered by stable IDs. These helpers are engineering
observability, not research endpoints.

## 14. Determinism and RNG

`social.py` imports no RNG. Relationship deltas, six-decimal quantization,
decay, salience, and pruning tie-breaks are deterministic. Layer 4 retains its
existing shuffle and taker-selection RNG calls; enabling empty social memory or
recording-only social memory does not add draws. Equal partner scores use the
existing shuffled rank and then stable ID. See
[Determinism and RNG](../architecture/determinism-and-rng.md).

## 15. Failure and edge cases

- Failed or ineligible transfers create no relationship or language occurrence.
- Inactive participants cause social recording to return false.
- Missing, negative, duplicate, self, or stale IDs fail or are removed during
  maintenance.
- Backdated interactions are rejected before record updates.
- Dead inhabitants' relationship dictionaries are cleared, and living ties to
  dead IDs are removed.
- Pruning removes lowest salience first using stable recency and ID tie-breaks.
- No baseline transfer opportunity means partner memory cannot initiate a global
  search.
- The economy transfer is committed before social/language observation; the
  language function is internally transactional, but the complete economy plus
  observation sequence is not a general rollback transaction.

## 16. Tests and validation

`tests/test_social_interaction_hooks.py` proves exact-once successful hooks and
zero hooks for failed individual and faction transfers.
`tests/test_social_relationships.py` covers directed/asymmetric aid, reciprocal
trade, clamping, decay, pruning, death cleanup, sparse caps, and RNG isolation.
`tests/test_social_partner_choice.py` covers the historical disabled path,
recording-only mode, bounded redirection, exploration, eligibility, tie-breaking,
and one-shuffle behavior. `tests/test_language_interaction_hooks.py` verifies the
shared post-commit language boundary and nonlanguage isolation. Test scope is
indexed in [Test reference](../reference/test-reference.md).

## 17. Worked example

Suppose inhabitant 12 has three food and co-located inhabitant 27 has none. The
transfer commits one food. If 27 has no currency, it is aid: 27's relationship
toward 12 gains `0.08` trust, `0.02` affinity, `0.10` obligation, and `0.08`
familiarity; 12's record toward 27 gains only `0.01` affinity and `0.04`
familiarity. If 27 pays a positive amount, both directions instead gain the
trade deltas: `0.03` trust, `0.01` affinity, and `0.08` familiarity. In either
case the corresponding language occurrence happens after the food has moved.

## 18. Current limitations

- Social memory observes only committed aid and trade.
- No combat, rejection, kinship, diplomacy, religion, proximity, or arbitrary
  conversation creates a `Relationship` record.
- Grievance has no authentic increasing hook in this v1 slice.
- Obligation is stored and decayed but is not part of partner preference.
- Partner bias redirects an opportunity; it does not plan exchanges or guarantee
  reciprocity.
- Standard artifact metrics do not expose relationship summaries.
- The feature is blocked from current research-runner plans.

## 19. Future extensions

No broader social mechanism is authorized by the current implementation. Any
new interaction kind, institutional relationship, or research endpoint requires
a separately reviewed milestone.

Language feedback into relationships and partner choice is implemented by
[Language Coevolution v1](language-coevolution.md), which is disabled by
default. When effective it adds one bounded `intelligibility` value per
directed tie and one term to `relationship_preference_score`; while disabled
that value is provably zero and every score is unchanged. No other language
feedback into relationships exists.

## 20. Implementation evidence

**Implementation status:** source- and test-verified engineering feature; not
research-ready.

**Primary source:**

- `src/thalren_vale/economy.py`: `_do_trade()`, `_commit_individual_transfer()`,
  `_attempt_individual_transfer()`, `_relationship_biased_barter()`,
  `economy_tick()`
- `src/thalren_vale/social.py`: `Relationship`, `record_interaction()`,
  `maintain_relationships()`, `relationship_summary()`
- `src/thalren_vale/sim.py`: `economy_layer()`, `maintain_emergent_state()`
- `src/thalren_vale/config.py`: `SocialMemoryConfig`, `SimulationConfig`

**Primary tests:**

- `tests/test_social_interaction_hooks.py`
- `tests/test_social_relationships.py`
- `tests/test_social_partner_choice.py`
- `tests/test_language_interaction_hooks.py`
- `tests/test_reproducibility.py`

**Bounded verification commands used by the handbook project:** the focused and
full commands are recorded in [Test reference](../reference/test-reference.md).
No simulation or experiment was run while drafting this page.

**Unresolved discrepancy:** standard metrics do not currently publish the
on-demand relationship summary; documentation must not imply that they do.
