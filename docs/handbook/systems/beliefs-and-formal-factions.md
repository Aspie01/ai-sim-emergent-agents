# Beliefs, formal factions, and settlements

## 1. Overview

The legacy cultural-institutional path has two tightly connected systems:

1. Inhabitants acquire and share bounded string beliefs derived from lived events.
2. Groups of inhabitants with proximity, mutual legacy trust, and shared beliefs can form stateful formal `Faction` objects.

Formal factions pool food, reinforce trust, attract or reject members, create rivalries, split and merge, conduct economy and war, research technology, negotiate treaties, found religions, and possibly establish a settlement. They are materially causal institutions.

They are not the same as engineering-only informal coalitions. Formal factions use display-name-keyed legacy trust and belief compatibility; informal coalitions use stable inhabitant IDs and bounded directed `Relationship` state. Coalition dialect classification uses only informal coalition membership, never formal faction names.

## 2. Why it exists

The code makes beliefs a compact memory of conditions such as winter survival, death, migration, crowding, trade, terrain, scarcity, and combat. Formal factions then turn compatible beliefs and repeated trust into persistent collective state that can affect resources and later institutions.

The interpretation that beliefs are intended as a simplified ideology model is a reasonable **inference** from names and mechanics, not a validated scientific construct.

## 3. Key terminology

- **Belief key:** a canonical string such as `community_sustains`.
- **Tagged belief:** `heard_from_<name>:<core>`; `core_of()` takes the substring after the final colon.
- **Belief core:** the canonical comparison value used for duplicate suppression and faction compatibility.
- **Formal faction:** a `Faction` object with a name, member objects, shared beliefs, territory coordinates, reserve, history, and settlement state.
- **Active faction:** a faction whose `members` list is nonempty. Empty faction objects remain in the collection.
- **Territory:** the set-like list of coordinates currently or historically derived from members; it is not backed by `world.claimed_by`.
- **Proto-city:** `Faction.is_settled`, reached after 50 center-of-gravity snapshots fit within a 5 x 5 bounding box.
- **Permanent settlement:** a `Settlement` created only after 50 additional stable ticks and at least 50 members.
- **Rivalry:** integer tension in `factions.RIVALRIES`, keyed by a sorted pair of faction names.

## 4. Current status

**Implemented but experimental.** These systems are enabled by default and materially influence the run. Artifact schemas and some cross-system state are tested, but there is no focused beliefs, formal-factions, or settlements test module. Source comments and historical README prose contain stale thresholds and effects.

## 5. State owned

### Belief state

Each inhabitant owns an ordered `beliefs` list capped at eight entries. `add_belief()` suppresses duplicate cores and evicts the oldest entry before appending when full. The catalogue currently contains experience, location, social, scarcity, and combat keys. The list order matters for FIFO eviction and random sharing.

### Formal faction state

| State | Owner | Notes |
| --- | --- | --- |
| `name` | `Faction` | generated from common beliefs; mutable during some mergers |
| `members` | `Faction` | inhabitant object references; empty lists are retained |
| `shared_beliefs` | `Faction` | seeded at formation, extended by crowding/mergers; not recomputed every tick |
| `territory` | `Faction` | coordinate list, updated on selected membership/combat paths |
| `founded_tick` | `Faction` | creation time |
| `food_reserve` | `Faction` | pooled food float |
| `legends` | `Faction` | combat casualty records |
| settlement stability | `is_settled`, `settled_since`, `settled_ticks`, `_cog_snapshots` | proto-city history |
| permanent town | `settlement` | one `Settlement` reference or `None` |
| lazily attached systems | `techs`, `active_research`, `wealth`, `_priest_id`, `vassal_of`, `_council_tension` | later-layer additions |

`SimulationState.factions` owns the faction collection and `SimulationState.rivalries` owns the rivalry mapping. Compatibility aliases in `sim.py`, `factions.py`, and later modules refer to those same mutable collections.

### Settlement state

A settlement owns faction name, anchor coordinates, founding tick, status (`active` or `abandoned`), storage buffer, and housing capacity 100. An active settlement registers every coordinate in a radius-two square in the global spatial index.

## 6. Inputs

- Current population, positions, inventories, health changes, deaths, movement history, trades, crowd-control flags, faction tenure, and biome exposure.
- Name-keyed legacy trust and `trust_last_seen` state.
- World resources and biome types.
- Configuration for belief-sharing probability and faction trust threshold.
- Rivalry, reputation, combat, technology, economy, and settlement state.
- Process-wide RNG for belief sharing, faction naming, and some merger/name decisions.

## 7. Processing sequence

### Belief assignment: Layer 2

For each living inhabitant, `assign_beliefs()` evaluates current and accumulated conditions in a fixed order. A belief can be added when the inhabitant:

- survives the end of winter, with the result depending on food held;
- loses a friend trusted above 5 or witnesses a same-tile death;
- stands on a food-empty tile;
- moved and now holds food;
- has at least three same-tile neighbors, or is truly alone;
- has completed at least three legacy trades;
- crosses below 50 health this tick;
- was pushed by crowd control;
- moved to a tile holding at least three food;
- accumulates terrain exposure thresholds (forest 10, mountain/coast 5, desert 5 while health above 30);
- spends at least 20 ticks in a faction or was rejected;
- has zero personal food for at least three ticks; or
- holds at least ten food while a same-tile neighbor has none.

The source also adds combat beliefs from battle and post-war paths, leadership belief in the faction layer, and beliefs from selected technology, religion, and anti-stagnation paths.

### Belief sharing: Layer 2

`share_beliefs()` enumerates ordered sender/receiver pairs on the same tile. A sender proceeds only when its own legacy trust toward the receiver is greater than 10, it has at least one belief, and a random draw is below the configured probability (default 0.5). One sender belief is selected randomly. If the receiver lacks that core, the receiver appends `heard_from_<sender>:<core>`, evicting its oldest entry when already at eight.

Sharing is directional; mutual trust is not required. It is narrative-only and is not an endogenous-language communication event.

### Formal faction formation: Layer 3

Every fifth tick, `check_faction_formation()`:

1. Excludes inhabitants already present in any faction members list.
2. Enumerates every unordered trio of remaining inhabitants.
3. Requires every pair in the trio to be within Manhattan distance 2.
4. Requires both directions of legacy trust for every pair to be strictly greater than `FACTION_TRUST_THRESHOLD` (default 5).
5. Requires at least two belief cores shared by all three.
6. Generates a unique faction name from those shared cores, sets territory to member coordinates, assigns each member's `faction` string, appends the faction, and emits `faction_formed`.

Worst-case formation work is cubic in the eligible population. A nearby comment saying trust must exceed 8 is stale; the helper reads the effective configured threshold.

### Per-faction processing: every tick

For each nonempty faction, in source order:

1. Move `round(20% of each member's food)` into the faction reserve.
2. Add up to two reserve food when territory contains forest, plains, or coast, capped at eight reserve units per member.
3. If `trade_builds_bonds` is a shared belief, let every member withdraw one extra food from its tile when available.
4. Give one reserve food to hungry members (`hunger > 20`) in descending hunger order.
5. Add one bilateral legacy trust point to every member pair.
6. Update 50-snapshot center-of-gravity stability. If proto-city status is active, add another five trust in both directions to every member pair.
7. For an active settlement, deposit member food above five into storage up to 500, then give one stored food to hungry members inside its zone.
8. Pull members more than three Manhattan steps from the nearest territory coordinate one step toward it.
9. Consider unaffiliated inhabitants for joining. The candidate must be within distance 5 of territory, share at least two faction cores, have no defined ideological conflict, and trust at least one member strictly above the configured threshold. A trusted conflicting candidate is rejected and can gain `trust_no_group`.
10. Increment `faction_ticks`; give `the_wise_must_lead` to the member with greatest total legacy trust.
11. At size 8, add crowding to shared beliefs. Above size 10, members whose raw belief list contains `self_reliance` leave.

### Rivalry, split, merge, and settlement passes

After all individual faction passes:

- Every third tick, close territory, defined belief conflict, and same-tile cross-faction resource clashes add rivalry tension.
- Every 25 ticks, an ideological minority can split. The minority must be at least 30% of a mobile faction or 50% of a proto-city faction. One schism per checked faction creates a new faction and adds 20 rivalry.
- Every 10 ticks, adjacent solo factions can merge when mutual trust is above 5 and they share a stored faction belief.
- Every 50 ticks, small factions (each below five members) can merge when cross-member average trust is at least 8, rivalry at most 20, and beliefs do not conflict.
- Every 25 ticks, a separate reputation merger can combine factions whose reputation sum is at least 8, combined population is below 50, rivalry is below 15, and beliefs do not conflict.
- Every active faction without a settlement attempts founding.
- Empty factions with active settlements mark them abandoned, empty storage, and unregister the zone.
- A later reclaim loop searches the settlement index around a faction center; because abandonment removed the settlement from that index, normal reclaim is currently unreachable.

### Settlement founding

`update_settlement_status()` needs 50 center-of-gravity snapshots with row spread and column spread each at most 4. It then starts `settled_ticks` at zero. After 50 further stable ticks and once membership reaches 50, `_try_found_settlement()` anchors a single permanent settlement at rounded center of gravity, never on sea. A faction whose stored shared beliefs include trade or sea cores searches a bounded 9 x 9 area and prefers the greatest coast score. The registered 5 x 5 zone enables storage, walls, movement penalties, housing suppression, temple placement, and combat defense.

## 8. Outputs

- Mutated inhabitant beliefs, legacy trust, faction name, faction tenure, rejection flag, position, and inventories.
- Faction creation, membership, shared beliefs, territory, reserve, rivalry, settlement and later-layer state.
- Typed events: `faction_formed`, `schism`, `merger`, and `settlement_founded`.
- Narrative-only observations for belief sharing, joining, leaving, rejection, rivalry, research starts/pauses, and settlement abandonment/reclaim.
- End-of-tick faction, trust, technology, treaty, population and belief artifacts.
- Optional Reverse Assimilation diagnostic CSVs when belief tracking is enabled; these are not part of the required canonical artifact inventory.

## 9. Lifecycle position

Beliefs are Layer 2, after ordinary deaths/movement/gathering and before factions. Formal factions are Layer 3. Reproduction then may inherit faction membership. Economy, combat, technology, diplomacy, and religion all consume faction state. Map expansion and anti-stagnation occur later. Informal social/coalition/language maintenance runs near tick end and does not feed back from language into formal factions. Metrics observe final tick state.

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Inhabitants/world | bidirectional | experience, trust, beliefs, coordinates, food | Layers 1-3 | belief acquisition, formation, reserve and movement |
| Economy | bidirectional | faction membership, reserve, currency, prices, trade routes, raids | Layer 4 | causal material institution |
| Combat | bidirectional | rivalry, membership, territory, beliefs, legends | Layer 5 | war eligibility and consequences |
| Technology | bidirectional | shared beliefs, pooled resources, tech state | Layer 6 | research selection and passive effects |
| Diplomacy | bidirectional | names, beliefs, reputation, treaties, mergers | Layer 7/Layer 3 | collective decisions and consolidation |
| Religion | bidirectional | settled state, members, beliefs, temples, priests | religion layer | institutional religion and trust |
| Informal coalitions | intentionally isolated | none from formal faction topology | end-tick maintenance | separate stable-ID social construct |
| Endogenous language | observational hook only | faction-mediated committed trade can create authentic communication | Layer 4 | language learns; vocabulary does not drive faction state |
| Metrics/artifacts | observation | active membership, beliefs, event counts | end tick/finalization | evidence and summaries |

## 11. Configuration

See [Configuration reference](../reference/configuration-reference.md). Relevant controls are:

| Field/flag | Type | Default | Validation | Effect |
| --- | --- | ---: | --- | --- |
| `faction_trust_threshold` / `--faction-trust-threshold` | integer | `5` | nonnegative | strict trust gate for formation and joining |
| `belief_sharing_probability` / `--belief-sharing-prob` | float | `0.5` | 0.0 through 1.0 | per directional same-tile sharing opportunity |
| `belief_tracking_enabled` / `--enable-belief-tracking` | Boolean | `false` | flag | optional Reverse Assimilation diagnostics |
| `--disable-layer beliefs` | layer name | enabled by default | fixed allowlist | skips initial belief seeding and Layer-2 assignment/sharing; `add_belief()` also returns early |
| `--disable-layer factions` | layer name | enabled by default | fixed allowlist | skips formal formation and faction tick |
| anti-stagnation | Boolean | enabled | `--disable-antistag` | can force factions and mutate rivalry independently of ordinary formation |

Formation cadence 5, belief cap 8, sharing trust 10, and settlement thresholds are fixed constants rather than validated CLI fields.

## 12. Events

| Event type | Producer | Key fields/caveat |
| --- | --- | --- |
| `faction_formed` | `_announce()` | actor faction; sorted member names in metadata |
| `schism` | `_try_schism()` | new faction actor, parent target, conflict detail |
| `merger` | three merger paths | donor actor, keeper target |
| `settlement_founded` | `_try_found_settlement()` | actor faction, coordinate detail |
| `faction_dissolved` | none in current source | allowed by schema but no active producer |

Belief assignment usually emits no event. Sharing and many membership/settlement transitions remain narrative-only but can appear in full logs.

## 13. Metrics

| Metric/artifact field | Meaning | Frequency | Caveat |
| --- | --- | --- | --- |
| `faction_count` | nonempty formal factions | every tick | empty faction objects excluded |
| `largest_faction_size`, `smallest_faction_size` | active membership extrema | every tick | formal factions only |
| `total_schisms`, `total_mergers` | canonical event counts | cumulative | typed/recognized events |
| `total_factions_formed` | formation count | run summary | event-derived |
| `mean_trust` | legacy trust values | every tick | not stable-ID Relationship trust |
| belief snapshot `faction` | inhabitant's current faction string | every 100 ticks | writer header calls identity `inhabitant_id`, but current writer supplies display name |
| `mean_tech_count_per_faction` | final/run aggregate | summary | later technology state |

There is no canonical per-tick table of faction membership transitions, reserves, territories, settlement storage, or full rivalry values.

## 14. Determinism and RNG

Belief sharing uses RNG for its probability and selected belief. Faction naming randomly selects adjective/noun components. Some merger naming and later anti-stagnation formation also consume the shared RNG. Formation itself iterates trios in current population order, which Layer 1 has already shuffled. A fixed seed in serial mode reproduces that order and the resulting faction state.

Reserve, trust, joining, rivalry arithmetic, settlement stability, port search, and most split/merge eligibility checks consume no RNG. These systems have no dedicated RNG stream.

## 15. Failure and edge cases

- `core_of()` accepts any colon-containing string and treats the final segment as canonical; beliefs are not a typed enum.
- Direct appends in religion and inheritance paths can bypass `add_belief()` and its cap/duplicate policy.
- Formal membership uses object lists and display-name strings rather than stable IDs.
- Empty faction objects persist and remain available to name-keyed registries; no dissolution event is emitted.
- `shared_beliefs` can become stale relative to current members.
- Formation is worst-case O(P cubed); joining and multiple rivalry/merger paths perform population or cross-faction scans.
- Territory is not consistently recomputed after every movement or membership change.
- Renaming a keeper during merger does not comprehensively migrate every name-keyed external registry.
- Abandoned settlement reclaim cannot normally find the unregistered settlement.
- Settlement wall defense is implemented directly in combat; `technology.defense_bonus()` is a separate helper not called there.

## 16. Tests and validation

There is no `tests/test_beliefs.py`, `tests/test_factions.py`, or settlement-focused suite.

Indirect evidence includes:

- `tests/test_simulation_state.py`: faction/rivalry shared ownership and reset.
- `tests/test_events.py`: schema, ordered event recording, and generic event counters.
- `tests/test_artifact_validation.py`: faction/technology/belief artifact conformance and summary cross-checks.
- `tests/test_run_termination.py`: short end-to-end population/faction metric agreement.
- `tests/test_reproducibility.py`: same-seed state hash stability.
- `tests/test_language_interaction_hooks.py`: language communication cannot mutate formal faction state.
- `tests/test_informal_coalitions.py`: informal coalition transition consumes no RNG and leaves formal faction assignments unchanged.
- `tests/test_antistagnation.py`: traveler behavior with factions disabled.

These tests do **not** directly prove exact belief triggers/sharing, formation thresholds, joining/rejection, reserve accounting, rivalry growth, schism/merge rules, settlement founding, or reclaim. See [Test reference](../reference/test-reference.md).

## 17. Worked example

At tick 10, three unaffiliated inhabitants are all within Manhattan distance 2 of one another. Every directed legacy trust value among them is 6, above the default strict threshold of 5, and all three hold the cores `community_sustains` and `trade_builds_bonds`. The trio qualifies. A name is generated from those cores, their coordinates seed territory, and each inhabitant receives that faction's name. In later ticks each contributes rounded 20% food to the reserve; because the trade core is shared, each can also gather one extra tile food when available. None of this creates an informal coalition unless the separate stable-ID relationship and persistence rules also qualify.

## 18. Current limitations

- Beliefs are string labels with a simple eight-entry FIFO, not a probabilistic or semantic belief model.
- Sharing requires only the sender's trust; historical prose claiming mutual trust is stale.
- Formal faction formation is cubic and based on legacy name-keyed trust.
- Formal factions remain materially causal while newer informal coalitions are intentionally observational/engineering-only; users must not conflate them.
- Faction objects are never formally dissolved or removed.
- Settlement ownership and reclaim are incomplete.
- Several source comments/README claims use stale trust, distance, birth, settlement, or merger descriptions.
- Optional belief-composition tracking is diagnostic and unmanifested, not proof of reverse-assimilation causality.

## 19. Future extensions

Language-driven faction formation, faction languages, and diplomacy through language are **Planned, not implemented**. [Language Coevolution v1](language-coevolution.md) is implemented but touches only directed relationship ties and partner choice; it does not read or write faction state. `feature/language-research-readiness-v1` remains **Planned, not implemented** and must not be inferred from current faction behavior.

## 20. Implementation evidence

**Implementation status:** Implemented but experimental at branch `docs/technical-handbook-v0.1`, documented commit `23ef5dad78a86cbcf699dc0192373a3416eafc06`.

**Primary source**

- `src/thalren_vale/beliefs.py`: catalogue, cap, assignment and sharing.
- `src/thalren_vale/factions.py`: formal faction object, formation, tick, rivalry, split/merge, settlement lifecycle.
- `src/thalren_vale/world.py`: `Settlement` and spatial index.
- `src/thalren_vale/sim.py`: Layers 2-3, initialization, disabled-layer behavior and anti-stagnation additions.
- `src/thalren_vale/state.py`: authoritative faction/rivalry collections.
- `src/thalren_vale/metrics.py`: belief, faction and summary observations.
- `src/thalren_vale/ra_tracker.py`: optional diagnostic tracking.

**Primary tests**

- `tests/test_simulation_state.py`
- `tests/test_events.py`
- `tests/test_artifact_validation.py`
- `tests/test_run_termination.py`
- `tests/test_reproducibility.py`
- `tests/test_language_interaction_hooks.py`
- `tests/test_informal_coalitions.py`
- `tests/test_antistagnation.py`

**Bounded verification commands used for this handbook revision**

No beliefs/factions test or simulation command was run by this page's drafting agent. Claims were source-traced against the recorded commit. Repository-wide verification is recorded in `HANDBOOK_STATUS.md`.

**Unresolved discrepancies**

- Formation's nearby comment says trust above 8, while executable configuration defaults to a strict threshold above 5.
- The belief snapshot header says `inhabitant_id`, but `MetricsLogger.record_beliefs()` writes the display name.
- The source contains reclaim logic that cannot normally discover an abandoned settlement after unregistering it.
- Historical README descriptions of mutual sharing, join distance, settlement counts, and other faction behavior are not authoritative.
