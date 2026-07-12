# World and resources

## 1. Overview

Thalren Vale uses one mutable, square tile grid as the physical world. Each tile has a biome, five resource quantities, a derived `habitable` flag, and an unused `claimed_by` field. Living inhabitants occupy grid coordinates and interact with the resources on their current or neighboring tiles. The world starts at 8 x 8 tiles and can expand, but never shrink.

The implemented biomes and resource caps are:

| Biome | Wood | Food | Ore | Stone | Water | Movement hunger |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `forest` | 80 | 28 | 10 | 20 | 30 | 10 |
| `plains` | 20 | 14 | 5 | 10 | 50 | 5 |
| `mountains` | 5 | 4 | 80 | 80 | 20 | 9 |
| `desert` | 5 | 3 | 30 | 40 | 5 | 7 |
| `coast` | 20 | 14 | 5 | 10 | 90 | 5 |
| `sea` | 0 | 0 | 0 | 0 | 100 | 8 |

See [Tick lifecycle](../architecture/tick-lifecycle.md) for the world layer's exact position and [Causal chains](../architecture/causal-chains.md) for the resource-to-survival chain.

## 2. Why it exists

The code demonstrably uses spatially uneven, renewable resources to create scarcity, movement pressure, gathering opportunities, territorial overlap, and settlement geography. It also supplies the shared physical state read by inhabitants, factions, technology, economy, religion, plugins, metrics, and anti-stagnation events.

The broader rationale that this geography is intended to produce emergent social organization is an **inference** from those connections, not a stated research contract.

## 3. Key terminology

- **Tile/chunk:** one dictionary in `world.world`, addressed by `(row, column)`.
- **Biome:** the categorical terrain type; both a string `biome` and compact integer `biome_id` are stored.
- **Habitable:** a mutable Boolean initially defined as food greater than zero. It is not a permanent terrain classification.
- **Resource cap:** the per-biome maximum in `BIOME_MAX`.
- **Spatial partition:** `grid_occupants`, an index from coordinates to living inhabitant objects.
- **Settlement index:** `_settlements_index`, mapping each tile in an active settlement's 5 x 5 zone to its `Settlement` object.
- **World expansion:** addition of rows and columns until the side length reaches `ceil(sqrt(population * 2.5))`, with a minimum of 8.

## 4. Current status

**Implemented but experimental.** The world is active in ordinary runs and is included in deterministic state hashing, but the repository has no focused world-generation, movement, regeneration, or settlement-index test module. Several comments and printed messages overstate current behavior; the executable rules below are authoritative.

## 5. State owned

| State | Authoritative location | Writers | Main readers |
| --- | --- | --- | --- |
| Tile grid | `world.world` | world generation, regeneration, gathering, technology, factions, world events, plugins | inhabitants, economy, factions, metrics, display |
| Current side length | `world.GRID` | `reseed_world()`, `update_map_bounds()` | movement, spawning, expansion, plugins |
| Noise offsets and sea threshold | `_NOISE_OFFSETS`, `_SEA_THRESHOLD` | `_generate_world()` | `_chunk_from_noise()` during initial generation and expansion |
| Occupancy index | `grid_occupants` | `grid_admit()`, `grid_add()`, `grid_move()`, `grid_remove()` | nearby-agent queries, settlement population checks, plugins |
| Settlement spatial index | `_settlements_index` | `settlement_register()`, `settlement_unregister()` | movement penalties, storage access, religion, settlement reclaim logic |
| Settlement object | `world.Settlement`, referenced by `Faction.settlement` | factions and combat-adjacent code | inhabitants, factions, religion, combat |

Every tile has this effective shape:

```text
{
  biome: string,
  biome_id: integer,
  resources: {wood, food, ore, stone, water},
  habitable: boolean,
  claimed_by: null
}
```

`claimed_by` is initialized but has no current authoritative territory-ownership role. Faction territory is instead a list of member coordinates.

## 6. Inputs

- The process-wide `random` generator supplies noise offsets and initial resource rolls.
- Population and population cap determine food-regeneration pressure.
- The tick number determines season through a 50-tick cycle.
- Inhabitant coordinates, sailing capability, faction name, hunger, and settlement ownership affect movement.
- Faction beliefs and center of gravity can affect where a settlement is anchored.
- Technology and anti-stagnation layers can directly alter resources or tile habitability.
- Plugin commands can request bounded resource adjustments through the simulation bridge.

## 7. Processing sequence

### Initialization

1. Importing `world.py` creates an initial 8 x 8 grid, but `sim.run()` later seeds `random` and calls `reseed_world()`; the latter is the authoritative run grid.
2. `_generate_world()` draws six noise offsets, evaluates the ocean-depth field for all 64 initial tiles, sorts those bounded depth samples, and selects the 25th-percentile sea threshold.
3. `_chunk_from_noise()` maps height, moisture, and depth fields to a biome and rolls every nonzero resource between half-cap and cap.
4. `sim.init_world()` identifies currently habitable tiles, rerolls food between half-cap and cap, and sets approximately one fifth of those tiles to zero food, subject to a minimum-one rule.
5. Initial inhabitants are placed on coordinates from that pre-depletion habitable list. Consequently a selected spawn tile can have been depleted after the list was formed.

### World layer at the start of every tick

1. `sim.world_layer()` computes winter status.
2. It appends narrative season-transition messages where applicable.
3. It calls `world.tick(regen_rate, pop=len(people), pop_cap=POP_CAP)`.
4. The base rate is `0.25` outside winter and `0.125` during winter.
5. Food regeneration is multiplied by `1 + 0.5 * min(1, population / cap)`. If population is below `max(2, 10% of cap)`, that multiplier is replaced by `2.0`.
6. For each non-sea tile and resource, regeneration adds `int((cap - current) * rate)`, capped at the biome maximum. Only food receives the population multiplier.
7. Each processed non-sea tile's `habitable` flag becomes `resources['food'] > 0`.

Despite the winter log text saying regeneration "pauses," winter uses a lower nonzero rate. Integer truncation can still produce zero change for small deficits.

### Movement and occupancy

1. `best_neighbor()` examines the 3 x 3 neighborhood and chooses the greatest food score adjusted by movement cost.
2. Non-sailors skip sea. Sailors may enter sea and receive a 2x score factor there.
3. An outsider scores an active enemy settlement tile at one third of its food value.
4. `force_move()` or normal movement uses `grid_move()` and charges the destination biome's hunger cost; entering enemy walls can add another 10 hunger.
5. Occupancy changes happen under `_grid_lock`; `grid_neighbors()` returns a snapshot after releasing the lock.

### Gathering

1. In the inhabitant layer, each non-priest takes up to one food from the current tile.
2. With probability `0.30`, the inhabitant takes one of wood, stone, or ore, weighted by current availability.
3. Faction and technology effects may perform additional withdrawals or direct generation later in the tick.

### Expansion

After religion/mythology and before anti-stagnation, every 25th tick calls `update_map_bounds(len(people))`. It computes the target side length as:

```text
max(8, ceil(sqrt(population * 2.5)))
```

New tiles reuse the run's stored noise offsets and sea threshold. Expansion adds columns to existing rows, then adds new rows. It never removes tiles.

## 8. Outputs

- Mutated resource quantities and `habitable` flags.
- Inhabitant coordinate and hunger changes through movement.
- Updated occupancy and settlement indices.
- Narrative winter, spring, and map-expansion records in the observation log.
- A typed `world_event` when an anti-stagnation world event fires; ordinary regeneration and expansion do not emit a typed event.
- End-of-tick metrics include `grid_size` and numeric `season`, but do not record per-tile resource amounts.
- Canonical state hashing includes the current world representation.

## 9. Lifecycle position

World construction occurs after run reset and seeding. Resource regeneration is Layer 0, before any inhabitant acts. Inhabitant gathering is in Layer 1. Faction, technology, world-event, plugin, and settlement logic can mutate world state later. Expansion occurs every 25 ticks after religion. End-of-tick metrics observe the resulting state.

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Configuration | input | population cap, seed, disabled layers | startup | bounds pressure and enabled mutators |
| Inhabitants | bidirectional | coordinates, food, terrain, occupancy | Layer 1 | movement, gathering, hunger, death pressure |
| Formal factions | bidirectional | territory coordinates, reserve withdrawals, settlements | Layer 3 | shared food, territorial pull, walls and storage |
| Economy | bidirectional | inventories, scarcity, raids, fishing effects | Layer 4 | transfers and resource pressure |
| Technology | mutation | farming floors, gathering, generated ore/stone, sailing | Layer 6 | changes resource availability and traversal |
| Religion | read/mutation | temple positions, priest movement | religion layer | movement and institutional location |
| Anti-stagnation | mutation | world events and traveler spawn positions | late tick | can change resources or habitability |
| Plugins | constrained mutation | resource snapshots and adjustment commands | plugin layer | external bounded changes |
| Metrics/hash | observation | grid size, season, complete tile state | end of tick/finalization | diagnostics and reproducibility |

## 11. Configuration

The full validated CLI surface is catalogued in [Configuration reference](../reference/configuration-reference.md). World-relevant values are:

| Field or constant | Type | Default | Validation/range | Effect |
| --- | --- | ---: | --- | --- |
| `population_cap` / `--pop-cap` | integer | `1000` | at least 1 | food pressure and population ceiling |
| `starting_population` / `--starting-pop` | integer | `30` | 1 through cap; at most 135 | initial inhabitants |
| seed / `--seed` | integer or absent | absent | argparse integer | controls world offsets and resource rolls; explicit seed enables serial inhabitant execution |
| `TILES_PER_PERSON` | float constant | `2.5` | not CLI-configurable | expansion target |
| `INITIAL_GRID` | integer constant | `8` | not CLI-configurable | initial/minimum side length |
| `_SEA_FRACTION` | float constant | `0.25` | not CLI-configurable | initial sea-threshold quantile |
| cycle/start/length | integer constants | `50 / 25 / 8` | not CLI-configurable | winter phase |
| normal/winter regeneration | float constants via `regen_rate()` | `0.25 / 0.125` | not CLI-configurable | per-resource fractional refill |

There is no supported CLI switch that disables the world or regeneration layer.

## 12. Events

The world layer itself records season changes as legacy/narrative observations.
The scheduled 200-tick event family emits schema-1 `world_event` rows for
Plague, Golden Age, Migration, Earthquake, and Discovery. Great Migration,
Plague Sweeps, Civil War, Promised Land, and Prophet disruptions emit
`stagnation_trigger`. `settlement_founded` is emitted by the faction layer.
Map expansion is narrative-only.

## 13. Metrics

| Metric | Meaning | Frequency | Destination/caveat |
| --- | --- | --- | --- |
| `grid_size` | current side length | every completed tick | metrics CSV; not tile count |
| `season` | `0` non-winter, `1` winter | every completed tick | metrics CSV |
| `mean_food` | mean personal food inventory | every completed tick | not remaining world food |
| `population` | living inhabitants | every completed tick | affects next tick's regeneration |
| state hash | selected final-state fingerprint including every tile's biome, habitability, and resources | run finalization | reproducibility, not a world-only metric or complete checkpoint |

No canonical artifact records the complete tile-by-tile resource trajectory each tick.

## 14. Determinism and RNG

World generation and expansion consume the process-wide Python RNG. A supplied seed is installed before `reseed_world()`, so identical effective configuration and seed reproduce the world in supported serial execution. Expansion consumes additional RNG for each new tile's resource rolls and therefore depends on the exact expansion history.

Regeneration, occupancy-index maintenance, totals, and metrics consume no RNG. Gathering's non-food branch, movement-independent spawn selection, technology choices, and world events do consume the shared RNG. There is no dedicated world RNG stream.

The occupancy and settlement indices are protected by locks, but seeded runs avoid Layer-1 thread interleaving to preserve RNG order.

## 15. Failure and edge cases

- `init_world()` asserts that at least one habitable tile exists.
- `grid_admit()` validates duplicate exposure and rolls back partial insertion and ID staging on failure.
- `grid_move()` does not itself check bounds, sea access, or settlement rules; correctness depends on its caller.
- `tile_is_sea()` returns `False` on an invalid index or type, which is fail-open for malformed coordinates.
- Integer regeneration can permanently leave a resource below cap when the remaining fractional increment truncates to zero.
- Sea tiles are skipped during `world.tick()`, so their `habitable` flag is not recomputed there.
- Expansion does not shrink after population loss.
- Settlement unregistering removes abandoned settlements from the same index that reclaim lookup uses; the current reclaim path therefore cannot normally rediscover an unregistered abandoned settlement.
- Some anti-stagnation paths can set a sea tile's `habitable` flag without changing its biome, creating a mismatch between passability and spawn eligibility.

## 16. Tests and validation

Direct coverage is limited:

- `tests/test_reproducibility.py` checks same-seed process-level state hashes and different-seed divergence; the hash includes world state.
- `tests/test_run_termination.py` exercises short complete, failed, interrupted, and extinction runs, indirectly covering construction and Layer 0.
- `tests/test_plugin_security.py` proves plugin snapshots do not expose mutable world dictionaries and do not change retroactively.
- `tests/test_simulation_state.py` verifies reset and repeatability of run-owned state, though the world itself is reset separately.
- `tests/test_antistagnation.py` checks traveler cadence and suppression, not general terrain/resource behavior.

These tests do **not** directly prove biome distribution, exact regeneration arithmetic, movement legality, occupancy consistency under every caller, expansion continuity, settlement reclaim, or long-run resource balance. See [Test reference](../reference/test-reference.md).

## 17. Worked example

Suppose a plains tile has 10 food out of a cap of 14, with population 500 and cap 1000 outside winter. Food pressure is `1 + 0.5 * 0.5 = 1.25`; the effective rate is `0.25 * 1.25 = 0.3125`. The tile gains `int((14 - 10) * 0.3125) = 1`, reaching 11. In winter the rate is `0.125 * 1.25 = 0.15625`; the same four-unit deficit produces `int(0.625) = 0`, so this particular tile does not change that tick even though the configured winter rate is nonzero.

## 18. Current limitations

- No focused world/resource regression suite exists.
- Resource regeneration uses shared constants rather than a validated world configuration object.
- `habitable` means current positive food in most paths, not intrinsically traversable terrain.
- Resource metrics observe inventories, not complete world stocks.
- The calibrated 25% sea threshold is exact only over the bounded initial depth samples; later expansion reuses the threshold rather than recalibrating.
- `claimed_by` is not an authoritative ownership mechanism.
- Fishing/economy and some technology paths can generate or duplicate resources outside normal tile-cap regeneration.
- Historical README statements that winter stops regeneration or that all movement is uniformly constrained are stale where they conflict with the source above.

## 19. Future extensions

No active plan establishes a revised world model. Configurable ecology, stricter passability enforcement, settlement-index repair, and fuller resource observability are **Planned, not implemented** only in the generic sense that they would require future authorized work; they are not current commitments.

## 20. Implementation evidence

**Implementation status:** Implemented but experimental at branch `docs/technical-handbook-v0.1`, documented commit `23ef5dad78a86cbcf699dc0192373a3416eafc06`.

**Primary source**

- `src/thalren_vale/world.py`: biomes, generation, expansion, regeneration, occupancy and settlement indices.
- `src/thalren_vale/inhabitants.py`: season helpers, movement, gathering, hunger and spatial-neighbor use.
- `src/thalren_vale/sim.py`: seeding, initialization, Layer 0, expansion, events and late world mutations.
- `src/thalren_vale/factions.py`: territory, settlement founding/storage/abandonment.
- `src/thalren_vale/technology.py`: terrain and resource effects.
- `src/thalren_vale/state.py`, `src/thalren_vale/reproducibility.py`: run state and hashing.

**Primary tests**

- `tests/test_reproducibility.py`
- `tests/test_run_termination.py`
- `tests/test_plugin_security.py`
- `tests/test_simulation_state.py`
- `tests/test_antistagnation.py`

**Bounded verification commands used for this handbook revision**

No world-specific test or simulation command was run by this page's drafting agent. Claims were source-traced against the recorded commit. Repository-wide verification is recorded in `HANDBOOK_STATUS.md`.

**Unresolved discrepancies**

- Winter narrative says regeneration pauses, while executable code uses `0.125`.
- Settlement reclaim is described in code but is unreachable through the normal index after unregistering.
- Historical README descriptions are not authoritative for current biome, movement, winter, and settlement behavior.
