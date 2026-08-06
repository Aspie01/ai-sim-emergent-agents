# Informal Coalitions

## 1. Overview

Informal coalitions are persistent, exclusive clusters inferred from reciprocal
personal relationships. They are not formal factions, governments, alliances,
or language communities. Each end-of-tick transition builds a canonical graph
from currently active inhabitants and admits only resilient
vertex-biconnected support blocks that meet configured trust, familiarity, and
grievance thresholds in both directions.

The coalition layer reads social state and writes only coalition runtime. Its
position in the whole run is shown in
[Tick lifecycle](../architecture/tick-lifecycle.md).

## 2. Why it exists

The system turns repeated authentic person-to-person exchange into an emergent
group structure while preventing a single bridge inhabitant from holding an
otherwise fragile cluster together. Persistence and stable IDs let the
simulation observe formation, growth, split, and dissolution without making
coalitions authoritative over agents' inventories, factions, relationships, or
language.

## 3. Key terminology

- **Qualifying reciprocal edge:** both directed `Relationship` records contain
  at least one interaction, meet trust and familiarity minima, and remain at or
  below the grievance maximum.
- **Support block:** a maximal vertex-biconnected subgraph of at least the
  configured minimum size.
- **Articulation vertex:** a member whose removal disconnects a graph; an active
  coalition cannot depend on one.
- **Candidate:** an exclusive support block accumulating consecutive qualifying
  observations.
- **Active coalition:** a formed coalition with an integer ID, formation tick,
  and canonical stable-ID member tuple.
- **Formal faction:** the separate faction system identified by faction names;
  it neither owns nor defines informal-coalition membership.

## 4. Current status

- **Implemented but experimental**.
- **Disabled by default**.
- **Engineering-only** when enabled or configured nondefault.
- Not research-ready; coalition options are rejected by `run_experiments.py`.

## 5. State owned

`SimulationState.coalitions` owns one `CoalitionRuntimeState`:

| State | Purpose |
| --- | --- |
| `candidates` | Exact member tuple → persistence record |
| `active_coalitions` | Coalition ID → `InformalCoalition` |
| `member_to_coalition` | O(1) exclusive membership index |
| `next_coalition_id` | Monotonic allocator; retired IDs are not reused |
| formation/split/dissolution counters | Bounded lifecycle observability |
| `last_observation_tick` | Freshness and monotonicity boundary |
| `last_active_inhabitant_ids` | Population identity represented by prior state |
| `last_qualifying_reciprocal_edge_count` | Latest graph-size observation |

Candidates and active memberships are canonical tuples of stable inhabitant IDs.
Coalitions own no vocabulary, inventory, currency, territory, leader, official
language, or shared lexicon.

## 6. Inputs

The transition reads:

- current living inhabitants and their exact stable IDs;
- each inhabitant's directed `relationships` mapping;
- the previous `CoalitionRuntimeState`;
- the current observation tick;
- effective `CoalitionConfig`.

It does not read legacy integer trust, display names, formal faction membership,
language state, communication outcomes, inventory, currency, combat, health,
movement, reproduction, or candidate prose.

## 7. Processing sequence

1. Validate configuration, tick monotonicity, stable IDs, every relationship
   record, and the previous runtime.
2. Build a canonical undirected graph. An edge exists only when both directed
   records qualify.
3. Re-evaluate each existing coalition using iterative Tarjan-style
   vertex-biconnected block decomposition.
4. If no qualifying block remains, dissolve the coalition. Otherwise the
   highest-priority surviving block keeps the existing ID and formation tick.
   Additional accepted blocks become split children with new IDs, subject to the
   active-coalition cap.
5. Evaluate currently unassigned inhabitants against a frozen pre-growth
   membership. A joiner needs qualifying edges to at least two distinct members.
   More supports win, then greater summed support strength, then lower coalition
   ID. Simultaneous joiners cannot bootstrap one another.
6. Validate the combined grown membership as one support block.
7. Decompose remaining unassigned inhabitants into exclusive candidate blocks.
   Overlap resolution prefers larger blocks, then stronger total support, then
   lexicographically lower member tuples.
8. Continue persistence only for an identical candidate seen on the immediately
   preceding observation. Mature candidates form in deterministic order while
   capacity remains.
9. Construct and deeply validate a complete proposed runtime, then return it.
   The caller replaces authoritative state only after success.

There is no direct active-coalition merge transition. Growth and fresh candidate
formation exist, but two established IDs are not combined into one retained ID.

## 8. Outputs

The transition outputs a new canonical `CoalitionRuntimeState`, including
membership, candidates, lineage, counters, and observation metadata. Enabled
coalition state and controls are included in the final behavioral hash.

The layer emits no simulation event and mutates no inhabitant or formal-faction
object. Its summaries are on-demand engineering observations.

## 9. Lifecycle position

Coalition transition runs once per enabled tick in the end-of-tick emergent-state
pass. Relationship maintenance runs first, coalition transition second, and
language maintenance third. Consequently the next tick's shared
coalition-language snapshot sees the last fully committed coalition
observation whenever dialect or contact classification needs it. See
[Causal chains](../architecture/causal-chains.md).

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Aid/trade relationships | Social → coalition | Reciprocal directed records | End of tick | Sole edge source |
| Population/death | Population → coalition | Active stable IDs | End of tick | Removes dead members and can split/dissolve |
| Formal factions | Intentionally isolated | None | All times | Memberships may overlap arbitrarily |
| Coalition dialects | Coalition → dialect | Frozen IDs and membership | Next tick before economy | Classifies authentic communication |
| Language contact | Coalition → language context | Frozen different-coalition classification | Next tick economy communication | May strengthen acquisition and record borrowing only |
| Language | Intentionally one-way | Coalition membership may adjust or qualify language learning | Economy communication | Language never changes coalition lifecycle |
| Hashing | Coalition → manifest hash | Canonical runtime | Finalization | Detects enabled state changes |

## 11. Configuration

| Field | Default | Valid range | Effect |
| --- | ---: | --- | --- |
| `coalition_emergence_enabled` | `False` | Boolean; requires social memory | Enables transition |
| `coalition_minimum_size` | `3` | Integer 3–1024 | Minimum block and active size |
| `coalition_trust_threshold` | `0.24` | Exact finite float 0.0–1.0 | Required in both directions |
| `coalition_familiarity_threshold` | `0.40` | Exact finite float 0.0–1.0 | Required in both directions |
| `coalition_maximum_grievance` | `0.20` | Exact finite float 0.0–1.0 | Maximum in both directions |
| `coalition_persistence_ticks` | `5` | Integer at least 2 | Consecutive candidate observations |
| `maximum_active_coalitions` | `32` | Integer 1–1024 | Formation/split-child capacity |

Requesting emergence without social memory normalizes it off and records
`coalition_emergence_requested_without_social_memory`. See
[Configuration reference](../reference/configuration-reference.md).

## 12. Events

No coalition formation, join, split, or dissolution event is written to the
standard structured event artifact. Lifecycle counters and canonical snapshots
are the current internal observability. Documentation and analyses must not infer
coalition events from faction events.

## 13. Metrics

`coalition_summary()` reports candidate count, active coalition count, assigned
and unassigned counts, largest size, qualifying reciprocal edge count, and
formation, split, and dissolution counters. `canonical_candidate_snapshot()` and
`canonical_coalition_snapshot()` provide deterministic records. These values are
not currently columns in the standard metrics CSV and are not approved research
endpoints.

## 14. Determinism and RNG

Coalition code imports no RNG and consumes no random state. IDs, vertices,
neighbors, edges, blocks, candidate formation, join choices, and lifecycle
transitions use explicit stable ordering. The biconnected decomposition uses an
iterative DFS frame stack, so long chains and cycles do not depend on Python's
recursion limit. See
[Determinism and RNG](../architecture/determinism-and-rng.md).

## 15. Failure and edge cases

- One-way trust and legacy integer trust create no edge.
- Chains, trees, and other articulation-dependent structures create no active
  coalition.
- Candidate membership changes reset persistence.
- One qualifying support does not permit joining; two distinct supports can.
- A critical edge loss can split or dissolve; a noncritical loss can preserve a
  valid block.
- Dead members are removed through the active-ID graph and may trigger lifecycle
  changes.
- Split children beyond the cap return to fresh candidate processing; they do
  not immediately join another coalition.
- Duplicate IDs, malformed tuples, overlap, stale ticks, allocator regression,
  reused retired IDs, and invalid lineage fail closed.
- Transition failure leaves the caller's runtime, formal factions, RNG, and
  inhabitants unchanged.

## 16. Tests and validation

`tests/test_informal_coalitions.py` covers reciprocal thresholds, legacy-trust
isolation, long chains/cycles, triangles, persistence, bridge and bow-tie
topologies, overlap priority, joining, simultaneous joins, splitting,
dissolution, death, decay, capacity overflow, rollback, IDs, bounded state, and
RNG/faction isolation. `tests/test_language_interaction_hooks.py` verifies the
social → coalition → language maintenance order. `tests/test_coalition_dialects.py`
and `tests/test_language_contact.py` prove language results cannot affect the
next coalition transition. See
[Test reference](../reference/test-reference.md).

## 17. Worked example

Three inhabitants form a triangle of reciprocal qualifying relationships. The
first end-of-tick observation creates one candidate, not a coalition. If the
same exact triangle qualifies for five consecutive observations under default
controls, the fifth observation allocates the next coalition ID and forms one
active coalition. If one edge later disappears, the remaining three-vertex
chain is not vertex-biconnected and the coalition dissolves. Their personal
relationships, vocabularies, factions, and inventories are not erased.

## 18. Current limitations

- Only reciprocal social-memory records support coalitions.
- No leaders, hierarchy, prestige, institutions, enforcement, territory, group
  inventory, or official language exists.
- No explicit established-coalition merge operation exists.
- Coalition lifecycle has no direct event artifact or standard metric columns.
- No language, faction, combat, health, reproduction, or movement feedback is
  implemented.
- The feature remains blocked from experiment plans and research readiness.

## 19. Future extensions

Language-driven coalition formation or lifecycle is **Planned, not
implemented**. [Language Coevolution v1](language-coevolution.md) is
implemented, but it feeds intelligibility only into directed relationship ties
and partner choice; it does not read or write coalition state. No current plan
authorizes leaders, institutions, diplomacy, coalition-owned resources, or
official languages.

## 20. Implementation evidence

**Implementation status:** source- and test-verified engineering feature; not
research-ready.

**Primary source:**

- `src/thalren_vale/coalitions.py`: `CoalitionRuntimeState`,
  `build_qualifying_reciprocal_graph()`,
  `vertex_biconnected_support_blocks()`,
  `resolve_exclusive_support_blocks()`, `transition_informal_coalitions()`,
  `coalition_summary()`
- `src/thalren_vale/social.py`: `Relationship`
- `src/thalren_vale/sim.py`: `maintain_emergent_state()`
- `src/thalren_vale/config.py`: `CoalitionConfig`
- `src/thalren_vale/reproducibility.py`: enabled/disabled coalition hashing

**Primary tests:**

- `tests/test_informal_coalitions.py`
- `tests/test_language_interaction_hooks.py`
- `tests/test_coalition_dialects.py`
- `tests/test_language_contact.py`
- `tests/test_reproducibility.py`
- `tests/test_config.py`
- `tests/test_artifact_validation.py`
- `tests/test_experiment_runner.py`

**Bounded verification commands used by the handbook project:** recorded in
[Test reference](../reference/test-reference.md). No simulation or experiment
was run while drafting this page.

**Unresolved discrepancy:** the source implements formation, growth, splitting,
and dissolution, but not a named merge transition; broad descriptions that list
coalition merging as current behavior are stale or overgeneralized.
