# System dependency and interaction map

## Direct dependencies

| System | Direct upstream state | Direct downstream effects |
| --- | --- | --- |
| World/resources | Seed, population pressure, season, technology, events/plugins | Needs, movement, beliefs, economy, settlements, metrics |
| Inhabitants | World, settlement/faction/religion/technology state | Beliefs, factions, economy, combat population, metrics |
| Beliefs | Agent experience, legacy trust, position, RNG | Formal factions, technology, diplomacy, religion, combat modifiers |
| Formal factions | Beliefs, legacy trust, proximity, rivalry | Reserves, settlements, economy, combat, technology, diplomacy, religion |
| Economy | Inventories, positions, formal factions, wars/treaties, RNG | Resources/currency, legacy trust, relationships, language opportunities, rivalry/raids |
| Directed relationships | Committed Layer-4 transfers | Optional partner bias, informal-coalition graph |
| Informal coalitions | Reciprocal relationship topology | Prior-membership dialect context and enabled hash |
| Endogenous language | Committed transfer opportunities, per-agent lexicons | Per-agent vocabulary and enabled hash only |
| Coalition dialects | Prior committed coalition snapshot | Language learning/reinforcement rates only |
| Language contact | Authentic different-coalition communication, prior committed coalition snapshot | Positive receiver acquisition, bounded exposure/borrowing metadata, enabled hash only |
| Intergenerational language | Successfully admitted child, exact two birth parents, usable parental production | Bounded child comprehension/provenance and enabled hash only |
| Combat | Formal factions, rivalry, treaties, technology, religion | Deaths, faction/territory/reputation/tribute state |
| Technology | Factions, beliefs, pooled resources, war state | Resources, health, movement, combat/raid modifiers, diplomacy |
| Diplomacy | Factions, beliefs, rivalry, wars, reputation | Treaties, reputation, surrender/membership state |
| Religion | Beliefs, factions/settlements, trust, reputation | Priests, temples, trust/hunger/movement, combat markers |
| Anti-stagnation | Population/faction/dynamic-event state | Population, resources, health, factions, rivalry, technology |
| Plugins | Immutable bridge snapshot plus arbitrary Python | Validated population/resource commands and external side effects |
| Observation | All committed state and journal entries | Structured artifacts; no intended causal feedback |

## Cross-system interaction matrix

Legend: `C` direct causal call/mutation; `R` reads shared state; `E` event/observation only; `H` final-hash/on-demand observation; `-` intentionally absent.

| Producer / consumer | World | Agents | Formal factions | Economy | Relationships | Coalitions | Language | Combat/civics | Observation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| World | C | C | R | R | - | - | - | R | E/H |
| Agents | C | C | C | R | identity | identity | identity/state | R/C | E/H |
| Formal factions | C | C | C | C | - | - | - | C | E/H |
| Economy | C | C | C | C | C | - | C opportunity | C rivalry/treaty | E/H |
| Relationships | - | C | - | C partner bias | C | C | - | - | H |
| Informal coalitions | - | - | - | - | R | C | C dialect/contact context only | - | H |
| Language/dialects/contact/intergenerational | - | - | - | - | - | - | C | - | H |
| Combat/civics | C | C | C | C | - | - | - | C | E/H |
| Plugins | C | C | R snapshot | - | - | - | - | - | E/H |
| Observation | E | E | E | E | H | H | H | E | C artifacts |

## Intentionally absent paths

- Language, dialect, contact, or intergenerational state -> transfer success, partner choice,
  relationships, formal factions, coalitions, combat, health, reproduction,
  movement, survival, population.
- Informal coalition -> economy eligibility/success, relationship update, formal-faction lifecycle, combat, resources, survival.
- Metrics/logging/dashboard -> authoritative simulation decisions.
- Formal-faction identity -> informal-coalition eligibility.
- Proximity/legacy Layer-1 swap -> authentic language communication or stable-ID social-memory update.

## Timing-sensitive dependencies

- Economy precedes combat/diplomacy, so current-tick war and treaty changes generally affect economy next tick.
- Social maintenance precedes coalition transition, so death cleanup/decay applies before graph detection.
- Current coalition transition happens after economy, while dialect/contact
  communication uses the frozen prior observation.
- Intergenerational transmission occurs only after the birth's `_spawn(child)`
  admission commits and before religion inheritance/birth-event emission. A
  language failure does not undo population, grid, faction, allocator, or
  parental-food effects already committed by reproduction.
- Observation happens after anti-stagnation and emergent maintenance.

## Implementation evidence

- Exact calls: `src/thalren_vale/sim.py`.
- Authentic hooks: `src/thalren_vale/economy.py`.
- Isolation tests: `tests/test_language_interaction_hooks.py`,
  `tests/test_coalition_dialects.py`, `tests/test_language_contact.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_informal_coalitions.py`.
