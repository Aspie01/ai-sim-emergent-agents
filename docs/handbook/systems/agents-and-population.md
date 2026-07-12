# Agents and population

## 1. Overview

The simulated population consists of `Inhabitant` objects. An inhabitant is a stateful individual with a run-scoped stable integer ID, display name, position, health, hunger, resource inventory, beliefs, two distinct social-memory representations, optional faction/religion roles, and optional language state. Each living inhabitant acts once in the Layer-1 population pass, unless a later layer creates or removes it during the same tick.

The implementation has birth and death, but no age clock, sex categories, fixed lifespan, genetic inheritance, childhood stage, or intergenerational language transmission. Generation depth is recorded as an integer lineage counter only.

See [Tick lifecycle](../architecture/tick-lifecycle.md) for execution order and [Causal chains](../architecture/causal-chains.md) for the survival and reproduction paths.

## 2. Why it exists

The population is the main carrier of simulation state. Individuals convert world resources into survival, social contact, beliefs, faction membership, communication, and descendants. The source directly establishes these mechanics.

It is an **inference**, not a formal research claim, that individual state is intended to make aggregate institutions emerge from repeated local interactions.

## 3. Key terminology

- **Living population:** `SimulationState.people`; only these objects receive the normal inhabitant pass.
- **Dead archive:** `SimulationState.all_dead`; removed inhabitants remain available for summaries, mythology, ID uniqueness, and hashing.
- **Stable inhabitant ID:** a monotonically allocated integer assigned by authoritative admission. It is distinct from the display name.
- **Legacy trust:** `Inhabitant.trust`, a display-name-keyed integer map used by older movement, faction, belief, reproduction, religion, and diplomacy mechanics.
- **Directed relationship:** `Inhabitant.relationships`, the newer stable-ID-keyed bounded social-memory state. It is documented separately from legacy trust.
- **Generation:** `0` for initial/traveler inhabitants; a child receives `max(parent generations) + 1`.
- **Authoritative admission:** `_spawn()` plus `grid_admit()` and `SimulationState.stage/commit_inhabitant_id()`.
- **Population cap:** the maximum number of living inhabitants, default 1000.

## 4. Current status

**Implemented but experimental.** Stable identity admission, social-memory behavior, deterministic seeded execution, termination, and artifact accounting have focused tests. The older hunger, movement, reproduction, inheritance, and legacy-trust lifecycle has little direct unit coverage and contains important edge cases documented below.

## 5. State owned

### Inhabitant state

| Category | Fields | Meaning |
| --- | --- | --- |
| Identity | `name`, `inhabitant_id` | display identity and exact run-scoped identity |
| Spatial/survival | `r`, `c`, `health`, `hunger`, `prev_health` | position and immediate survival state |
| Material | `inventory`, `currency`, `trade_count`, `zero_food_ticks` | five-resource holdings, currency and scarcity history |
| Legacy social | `trust`, `trust_last_seen`, `memory` | name-keyed trust and remembered food coordinates |
| Emergent social | `relationships` | stable-ID-keyed directed `Relationship` records |
| Culture | `beliefs`, `language` | bounded beliefs and independent production/comprehension language state |
| Institution | `faction`, `faction_ticks`, `was_rejected`, `religion`, `is_priest`, `role` | formal faction and religion state |
| Movement/context | `was_pushed`, `biome_ticks`, `_can_sail` | crowd-control and terrain exposure |
| Lifecycle | `is_procreating`, `generation` | birth lock flag and lineage depth |
| Technology effects | `_medicine_buffer`, `_plague_resist`, `_prev_hp_medicine` | lazily attached passive-effect state |

Every new inhabitant begins with health 100, hunger 0, three food, zero of the other four inventory resources, zero currency, empty beliefs/trust/relationships/memory, an empty language state, no faction or religion, and generation 0.

### Population-level state

`SimulationState` owns `people`, `all_dead`, the next-ID allocator, and the collections that refer to inhabitants. `sim.py` retains module aliases for compatibility. `world.grid_occupants` is the authoritative spatial index and faction `members` lists are additional authoritative membership collections for formal factions.

## 6. Inputs

- Effective population cap, starting population, seed, disabled layers, and anti-stagnation policy.
- Current tile biome/resources and settlement ownership/storage.
- Other inhabitants in the 3 x 3 occupancy neighborhood.
- Legacy trust, faction membership, beliefs, technology and religion roles.
- Process-wide RNG for shuffle, gathering, trades, pair choice, inheritance, and birth religion.
- Later systems can mutate health, membership, position, inventories, beliefs, religion, and death status.

## 7. Processing sequence

### Initial population

1. `init_inhabitants()` takes `min(starting_population, len(NAMES))` unique base names. Configuration validation caps the requested starting population at 135.
2. If beliefs are enabled, 30% of the selected population receives `self_reliance`, 30% receives `community_sustains`, and the remaining 40% starts without a belief; the assignment list is shuffled.
3. Each inhabitant is placed on a randomly selected coordinate from the initialization-time habitable list.
4. `_spawn()` validates capacity and ID uniqueness, stages the next integer ID, inserts into the spatial index and population, commits the allocator, and rolls back all parts if admission fails.

### Layer-1 preamble

1. The living `people` list is shuffled in place.
2. `was_pushed` and `was_rejected` are reset.
3. Each occupied tile is grouped. If more than five inhabitants share it, the group is sorted by total legacy trust; all but the five highest are forced to neighboring cells and marked pushed.
4. Legacy trust entries not seen for more than 500 ticks are removed.

### One inhabitant's action

For each inhabitant in the shuffled order:

1. Copy current health to `prev_health`.
2. Increase hunger by 7. Above hunger 40, consume one medicine buffer if present; otherwise lose 10 health.
3. Remember the current coordinate if it has food.
4. Eat one food and reduce hunger by 7; if hunger remains above 30, eat a second unit when available.
5. If personal food is empty, first try one unit from an owned active settlement store. Otherwise force a move and pay movement hunger, plus an enemy-wall surcharge where applicable.
6. If not a priest and current tile food is below 3, move to the best cost-adjusted neighboring food score.
7. If not a priest, gather up to one food. With probability 0.30, gather one available wood, stone, or ore selected by availability weight.
8. Snapshot inhabitants in the 3 x 3 neighborhood. For each visible neighbor, add one name-keyed trust point and refresh `trust_last_seen`.
9. For a same-tile neighbor, with probability 0.5, select one resource held by each and commit a one-unit inventory swap. This legacy Layer-1 swap is distinct from economy-layer aid/trade and emits no language communication hook.
10. Increment time in the current biome and update consecutive zero-food ticks.
11. If health is now zero or below, create a death observation paired with a journal token.

With an explicit seed, the action loop is serial to preserve shared-RNG order. Without a seed, the shuffled list is partitioned across up to four worker threads. The main thread joins the workers, validates death journal tokens, removes dead inhabitants from the grid and living list, appends them to `all_dead`, and emits typed deaths.

### Beliefs, factions, and reproduction

Belief assignment and formal faction processing occur after Layer 1. `procreation_layer()` then runs even if beliefs or factions are disabled:

1. It returns immediately during winter or at the population cap.
2. Up to three times, it enumerates unordered living pairs and keeps pairs on the same tile with mutual legacy trust at least 5, hunger strictly below 30, at least one food each, and neither already claimed for a birth.
3. It selects one eligible pair randomly, enters `procreation_lock`, revalidates all conditions and capacity, and marks both parents busy.
4. If the pair is inside its own active settlement and local population has reached the settlement's housing capacity of 100, it suppresses the birth.
5. `make_child()` chooses a unique name, sets generation to the maximum parent generation plus one, and randomly selects half of the ordered union of parent beliefs (at least one if the union is nonempty).
6. The child receives legacy trust 30 toward each parent and 10 food. Each parent loses up to five food through `max(0, food - 5)`.
7. A shared parental faction is inherited; otherwise parent A's faction is inherited when present. Admission inserts the child into both the living population and that faction's members list transactionally.
8. Near a parent-faction temple, religion is inherited with probability 0.95.
9. Busy flags are cleared in `finally`; a successful birth emits a typed `birth` event.

### Other creation and removal paths

- Anti-stagnation traveler waves can admit generation-0 outsiders with 30 food and a biome belief.
- Plugin commands can request validated admissions.
- Combat removes casualties from the grid, population, and faction, then adds them to `all_dead`.
- Late solo-faction fragility can reduce health and remove an isolated member.
- Ordinary starvation removal occurs before beliefs and factions; the faction layer removes the dead names from member lists later in the same tick.

## 8. Outputs

- Mutations to every individual state category listed above.
- World resource withdrawals and occupancy changes.
- Additions/removals in living, dead, and faction collections.
- Typed schema-1 `birth` and `death` events plus narrative movement, trade, belief, membership, and other messages.
- End-of-tick population, death, birth, generation, food, trust, and inequality metrics.
- Belief snapshots every 100 ticks when structured output is enabled.
- Canonical state-hash input, including living/dead state and allocator values where enabled by the hash contract.

## 9. Lifecycle position

Population construction follows world initialization. The inhabitant pass is Layer 1, immediately after regeneration. Beliefs and factions observe its movements and deaths. Reproduction runs after factions and before economy, so newborns can be seen by all later layers in their birth tick but do not execute the normal Layer-1 body until the next tick. Combat, religion, plugins, and anti-stagnation can make additional same-tick changes. Metrics observe the final completed-tick population.

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| World/resources | bidirectional | position, occupancy, resources, movement cost | Layer 1 | hunger, inventory, mobility |
| Beliefs | bidirectional | lived conditions and bounded belief list | Layer 2/later layers | interpretation of experience and institutional choices |
| Formal factions | bidirectional | name-based membership, reserves, territory | Layer 3 onward | food, trust, movement, conflict, inheritance |
| Economy/social memory | bidirectional | inventories, committed transfers, stable IDs, relationships | Layer 4/end maintenance | material exchange and directed ties |
| Language | bidirectional but causally isolated | independent lexicons and authentic communication | economy/maintenance | language state only; no survival effect |
| Combat | mutation | faction membership, death, beliefs | Layer 5 | casualties and post-war changes |
| Technology | mutation | gather, health buffers, sailing | Layer 6 | survival and movement advantages |
| Religion | mutation | roles, movement, trust, beliefs, inherited religion | religion/procreation | institutional identity and priest behavior |
| Metrics/artifacts | observation | living/dead state and counters | end tick/finalization | canonical records and diagnostics |

## 11. Configuration

See [Configuration reference](../reference/configuration-reference.md) for the complete CLI. Population-relevant controls are:

| Field/flag | Type | Default | Validation | Effect |
| --- | --- | ---: | --- | --- |
| `ticks` / `--ticks` | integer | `5000` | at least 1 | requested run horizon |
| `population_cap` / `--pop-cap` | integer | `1000` | at least 1 | hard living-population ceiling |
| `starting_population` / `--starting-pop` | integer | `30` | 1 through cap; at most 135 | initial population |
| seed / `--seed` | integer or absent | absent | argparse integer | shared RNG seed and serial-vs-threaded Layer 1 |
| `anti_stagnation_enabled` / `--disable-antistag` | Boolean | `true` | flag | traveler and solo-fragility interventions among others |
| `--disable-layer` | comma-separated names | empty | names from fixed allowlist | can disable beliefs/factions/economy/combat/etc.; there is no inhabitant-layer disable name |

Core constants not exposed through validated configuration include five gatherers per tile, 500-tick trust pruning, hunger thresholds 30/40, three births per tick, and mutual procreation trust 5.

## 12. Events

- `birth`: parents are actor/target; child name is detail; metadata includes child, generation, and faction.
- `death`: ordinary starvation and late solo-faction removal emit typed events. Combat appends a legacy casualty message; the ordered observation-journal classifier recognizes `fell in battle` and records it as a schema-1 death artifact row.
- Layer-1 legacy swaps, moves, crowd eviction, and eating/gathering are not typed events.
- Belief sharing, faction joining/leaving, and several religion actions are narrative-only observations.

## 13. Metrics

| Metric | Interpretation | Frequency | Caveat |
| --- | --- | --- | --- |
| `population` | living objects at completed tick end | every tick | includes same-tick births, excludes all removals |
| `total_births` | typed birth events observed | every tick/cumulative | event-derived |
| `total_deaths` | typed or recognized legacy death observations | every tick/cumulative | depends on the exact observation-journal classifier |
| `mean_food` | mean personal food inventory | every tick | excludes world, faction reserve, settlement storage |
| `mean_trust` | mean values in legacy name-keyed trust maps | every tick | not the newer directed `Relationship.trust` |
| `max_generation`, `mean_generation` | descendant depth | every tick | not biological age |
| `gini` | inventory/currency wealth inequality | every tick | uses fixed resource prices |

Run summaries include final/peak/minimum population, births, deaths, and maximum generation.

## 14. Determinism and RNG

Initial names/positions/beliefs, population shuffling, non-food gathering, legacy swaps, pair selection, belief inheritance, name selection, and religion inheritance use the process-wide RNG. Explicitly seeded runs force the inhabitant layer to execute serially; this is the supported deterministic mode. Unseeded interactive runs use worker threads and are not promised to consume RNG in a reproducible order.

Stable IDs are deterministic monotonic integers within a run and consume no RNG. Admission is protected by `_admission_lock`, while births use `procreation_lock`, world mutation uses `_world_lock`, swaps use `_trade_lock`, and narrative writes use `_log_lock`.

Language owns a deterministic seed-domain identity and per-agent invention
counters, not an RNG object or RNG state. Population and inheritance mechanics
do not use those counters, and language is not inherited in the current
revision.

## 15. Failure and edge cases

- Admission rejects an already assigned ID, duplicate object, reused next ID, or population overflow and attempts full rollback.
- Display names can repeat across history, but living names are made unique; stable IDs remain the authoritative newer-system identity.
- Procreation eligibility requires only one food each, while construction removes at most five each and gives the child ten. Parents with fewer than five therefore create net food.
- The eligible-pair construction is quadratic in current population and repeats up to three times per tick.
- There is no age or maximum lifespan; absent starvation, combat, and interventions, an inhabitant does not die of age.
- Priests skip normal gathering and rely on faction reserve feeding; an empty reserve adds hunger.
- `grid_move()` trusts callers to supply valid/passable coordinates. Some diplomacy/religion paths bypass or catch spatial errors inconsistently.
- Legacy trust is name-keyed and can conflate historical identity if a display name is reused; newer social relationships use stable IDs.
- Death paths reach artifact accounting through both direct typed events and recognized legacy-message classification.

## 16. Tests and validation

- `tests/test_social_identity.py` directly exercises staged/committed stable IDs, rollback, concurrent admission, duplicate IDs, and same-name/different-ID identity.
- `tests/test_simulation_state.py` verifies authoritative collection aliases, reset behavior, journal invalidation, and same-process repeatability.
- `tests/test_reproducibility.py` verifies seeded Layer 1 does not start worker threads and checks cross-process state hashes.
- `tests/test_run_termination.py` exercises short subprocess runs, extinction, terminal accounting, final metrics, and state hashes.
- `tests/test_events.py` verifies typed birth/death accounting infrastructure, not complete biological semantics.
- `tests/test_antistagnation.py` verifies traveler cadence and disabling.
- Social, coalition, and language suites use `Inhabitant` fixtures to verify
  focused isolation boundaries—for example, language communication preserves
  tested health/inventory/faction snapshots and coalition transitions preserve
  tested formal-faction state. They do not prove universal population or
  faction noncorruption across every path.

The suite does **not** directly prove exact hunger/eating sequences, birth eligibility and inheritance, population-cap behavior under full simulation contention, the three-birth maximum, housing suppression, every death path, or absence of net resource creation. See [Test reference](../reference/test-reference.md).

## 17. Worked example

Two inhabitants share a tile. Each has mutual legacy trust 5, hunger 20, and one food. They are eligible because the checks are `trust >= 5`, `hunger < 30`, and `food > 0`. If selected, each parent's food becomes zero because `max(0, 1 - 5)` is zero, while the child begins with ten food. The child gets a new stable ID and generation one. If both parents share a faction, the child is inserted into that faction; its language production and comprehension maps still begin empty.

## 18. Current limitations

- The individual lifecycle has no aging and no age-related death.
- Reproduction does not model sex, pair bonds, gestation, or parent availability beyond a same-call busy flag.
- Beliefs are sampled at birth, but language is not inherited.
- Legacy Layer-1 swaps are separate from the authenticated economy communication hooks and are not typed events.
- Reproduction can create food and performs population-wide pair enumeration.
- Direct focused tests for hunger, gathering, movement, birth, and inheritance are absent.
- Historical README thresholds and birth descriptions are stale where they differ from the executable rules above.

## 19. Future extensions

`feature/intergenerational-language-v1` and any inherited-vocabulary behavior are **Planned, not implemented**. Age, demographic roles, migration identity, or genetic inheritance are also **Planned, not implemented** unless a future authorized milestone adds and tests them.

## 20. Implementation evidence

**Implementation status:** Implemented but experimental at branch `docs/technical-handbook-v0.1`, documented commit `23ef5dad78a86cbcf699dc0192373a3416eafc06`.

**Primary source**

- `src/thalren_vale/inhabitants.py`: individual state, movement, hunger, gathering, legacy interaction, death observations, child construction.
- `src/thalren_vale/sim.py`: admission, initialization, Layer 1 orchestration, reproduction, traveler and solo-death paths.
- `src/thalren_vale/state.py`: authoritative population/death collections and stable-ID allocator.
- `src/thalren_vale/world.py`: atomic grid admission and occupancy changes.
- `src/thalren_vale/metrics.py`: population, generation, food, trust, death and birth observations.
- `src/thalren_vale/reproducibility.py`: canonical serialization and hashing.

**Primary tests**

- `tests/test_social_identity.py`
- `tests/test_simulation_state.py`
- `tests/test_reproducibility.py`
- `tests/test_run_termination.py`
- `tests/test_events.py`
- `tests/test_antistagnation.py`

**Bounded verification commands used for this handbook revision**

No population-specific test or simulation command was run by this page's drafting agent. Claims were source-traced against the recorded commit. Repository-wide verification is recorded in `HANDBOOK_STATUS.md`.

**Unresolved discrepancies**

- Combat casualties rely on legacy-message classification rather than direct `emit_event()` calls.
- Reproduction's food precondition and child endowment do not conserve inventory.
- Historical prose describing age, one birth per tick, different hunger thresholds, or inherited language is not current source truth.
