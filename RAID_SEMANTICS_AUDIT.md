# Raid Semantics Audit

Question: `no_combat` recorded 5,513,353 `raid` events despite 0 wars. Are raids combat-adjacent, should they be suppressed under `--disable-layer combat`, and are they responsible for the no-combat event/log explosion?

## Findings

Raids are generated in the economy layer, not the combat layer.

Relevant code:

- `src/thalren_vale/economy.py`
  - `_faction_raids(active, t, event_log)`
  - Called from `economy_tick(...)` when `len(active) >= 2`
- `src/thalren_vale/sim.py`
  - `economy_layer(t)` runs when `economy` is not disabled.
  - `combat_layer(t)` is skipped when `combat` is disabled.
- `src/thalren_vale/technology.py`
  - Martial technology affects `raid_multiplier(faction)`.
- `src/thalren_vale/combat.py`
  - Combat logic can treat prior raids as a war/vengeance context.

The current `--disable-layer combat` behavior only suppresses `combat.combat_tick(...)`. It does not suppress economy-layer raids.

## What a raid does

In `_faction_raids(...)`, each active faction pair is eligible when rivalry/tension is above the threshold. A raid:

1. Selects a raider and victim faction.
2. Picks a tile from the victim's territory.
3. Steals a percentage of trade resources from that world tile.
4. Adds the stolen resources to a random raider member's inventory.
5. Adds the `the_strong_take` belief to that raider member.
6. Increases pair rivalry/tension by `+10`.
7. Emits a typed `raid` event.
8. Prints a legacy text log message in full logging mode.
9. Lowers raider diplomatic reputation.
10. Breaks an existing treaty between the raider and victim, if present.

Raids do not directly kill inhabitants and do not directly apply health damage. They are not war declarations or battles. They are hostile economic actions with diplomatic and tension side effects.

## Classification

Raids are best classified as combat-adjacent economy/diplomacy events.

They are not generic neutral faction interactions:

- The event text uses a combat symbol and "RAID".
- They represent hostile plunder.
- They increase rivalry/tension.
- They can break treaties.
- Martial technology increases raid loot.
- Combat logic can later interpret raids as a cause/context for conflict.

But they are also not the same as combat-layer wars:

- They are generated entirely in `economy.py`.
- They do not create active wars.
- They do not invoke battle resolution.
- They do not directly kill inhabitants.

## Are raids causing most of the no-combat event/log explosion?

Yes.

From `experiment_runs/core-replication-v1/analysis/event_type_counts.csv`, no-combat produced:

- Total structured events: 5,559,667
- Raid events: 5,513,353
- Raid share: about 99.17%

So raids are the dominant source of the no-combat structured event explosion and, in full logging mode, the dominant source of raw text expansion.

## Should `--disable-layer combat` suppress raids?

Not automatically, without a design decision.

There are two defensible interpretations:

1. Narrow interpretation: `no_combat` means no formal combat layer, no wars, no battles, no alliance calls, no surrender/tribute war resolution. Under this interpretation, economy-layer raids remain valid because they are economic predation rather than war.
2. Broad interpretation: `no_combat` means no hostile inter-faction violence or coercive plunder. Under this interpretation, raids should be disabled, reclassified, or controlled by a separate layer flag.

The current behavior matches the narrow interpretation. It is not clearly a code bug, but it is a major experimental-design ambiguity.

## Recommendation

Do not silently change `--disable-layer combat` semantics yet. That would alter the meaning of the completed `core-replication-v1` dataset.

Recommended next implementation:

1. Add a separate switch or layer:
   - `--disable-layer raids`, or
   - `--disable-raids`
2. Rename or subtype the event for clarity:
   - Keep event type `raid` for backward compatibility, but add metadata such as `"domain": "economy"` and `"combat_adjacent": true`, or
   - Introduce `economic_raid` in a schema-versioned event migration.
3. Add a new short ablation before any long replication:
   - `no_combat`
   - `no_combat_no_raids`
   - seed 1
   - 100, 250, 500, 1000 ticks
   - metrics-only logging
4. Consider aggregating high-frequency raid events in raw text output:
   - Keep structured event rows if needed for research.
   - In text logs, summarize per tick or per faction pair instead of printing every raid.

## Research implication

The completed no-combat result should be described carefully:

> Disabling the combat layer prevented formal wars but left economy-layer raids active. In no-combat runs, raids became the overwhelming majority of structured events. Therefore the observed no-combat slowdown and output growth combine at least three factors: larger surviving populations, many more active factions, and unbounded hostile economic raid logging/events.

This is stronger and more accurate than saying no-combat is slower purely because of emergent complexity.
