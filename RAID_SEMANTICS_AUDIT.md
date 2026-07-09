# Raid Semantics Audit

Status: **needs-audit**

Date: 2026-07-09

Dataset: `core-replication-v1` (15/15 final runs validated)

## Conclusion

Raids are **combat-adjacent economic coercion with diplomatic effects**. They are not formal wars or battles, but they are not neutral faction interactions either. The current `--disable-layer combat` switch narrowly disables `combat.combat_tick()` and intentionally leaves the economy layer running, so raids still occur under the `no_combat` condition.

This is not clearly an implementation bug. It is an experimental-semantics ambiguity: “no combat” can mean either “no formal battle/war system” or “no hostile coercive interaction.” The completed pilot implements the first meaning.

## Generation and classification path

Raids originate in `src/thalren_vale/economy.py`:

1. `sim.economy_layer()` calls `economy.economy_tick()` unless the `economy` layer is disabled.
2. `economy_tick()` calls `_faction_raids()` every tick when at least two active factions exist.
3. `_faction_raids()` iterates every active faction pair.
4. A pair is eligible when its rivalry/tension is greater than 35.
5. Each eligible pair has a 20% raid attempt probability per tick.
6. A successful raid emits a typed `raid` event and a legacy message.

The combat-layer gate in `src/thalren_vale/sim.py` wraps only `combat_layer(t)`. No raid gate consults `_disabled_layers` for `combat`. A stale economy comment said raids required tension above 50; it was corrected to match the existing `>35` implementation without changing behavior.

Combat code consumes raid history as context: prior raids can motivate alliance recruitment and vengeance. Martial technology can multiply raid loot. These links make the feature combat-adjacent even though its producer is the economy layer.

## State effects of one raid

A successful raid:

- removes 20% of available food, wood, ore, and stone from a randomly selected victim-territory tile, multiplied by the raider’s technology modifier;
- adds the haul to one raider member’s inventory;
- adds the `the_strong_take` belief to that member;
- increases pair tension by 10;
- lowers the raider’s diplomatic reputation by 1;
- breaks an existing treaty between raider and victim, with the normal treaty-break reputation and third-party tension effects;
- appends raid history and emits one typed event plus one full-mode text message.

A raid does **not** directly reduce health, kill an inhabitant, start a war, resolve a battle, remove territory, or dissolve a faction. Resource removal can indirectly affect later hunger, scarcity, faction viability, diplomacy, and population outcomes.

## Event-volume evidence

The lightweight `experiment_runs/core-replication-v1/analysis/event_type_counts.csv` gives:

| Condition | Raid events | All structured events | Raid share |
|---|---:|---:|---:|
| baseline | 25,303 | 65,997 | 38.340% |
| no_antistag | 20,174 | 43,978 | 45.873% |
| no_combat | 5,513,353 | 5,559,667 | 99.167% |

No-combat raid counts by seed were 1,186,499; 1,234,028; 1,236,116; 953,037; and 903,673.

Raids therefore account for nearly all of the no-combat structured-event explosion. Because each raid also prints a full-mode message, they are very likely the dominant semantic source of raw-text growth, although this audit deliberately did not parse the multi-GB logs by event type.

The volume is structurally plausible rather than a legacy-parser duplication: typed event messages are excluded from text reclassification in `sim.py`, and a short-run duplicate-key check found no duplicate raid rows. The principal scaling risk is `_faction_raids()` iterating all faction pairs every tick. With hundreds of active factions, candidate work grows approximately with the square of faction count, and the code has no per-pair cooldown or global raid budget.

## Should no-combat suppress raids?

Do not silently redefine `--disable-layer combat`. That would invalidate comparisons with `core-replication-v1` and collapse two distinct causal factors.

Use explicit semantics instead:

- Preserve `combat` as formal war/battle resolution for backward compatibility.
- Add a separate future control such as `--disable-layer raids` or `--disable-raids`.
- Describe the existing pilot condition as **formal combat disabled; economic raids enabled**.
- For a clean causal design, use a 2×2 combat × raids experiment rather than treating the current condition as complete removal of hostility.

## Rename, reclassify, throttle, aggregate, or leave alone?

- **Rename:** keep event type `raid` for backward compatibility. A schema-versioned future event may use `economic_raid`, but a silent rename would break existing analysis.
- **Reclassify:** add explicit metadata such as `domain: economy`, `hostility: coercive`, and `combat_adjacent: true` in a future event-schema revision.
- **Suppress:** only behind a separate explicit raid control, not automatically under the existing combat flag.
- **Throttle simulation behavior:** do not do this without a dedicated research design; cooldowns or budgets would change dynamics.
- **Aggregate output:** recommended for human-readable logs. Preserve exact structured events when needed, but summarize text by tick or faction pair.
- **Buffer structured writes:** investigate next. `MetricsLogger.record_event()` currently flushes after each event, so millions of raids create substantial structured-I/O overhead even in `metrics_only` mode.

## Safest next experiment

Before any long replication, run a clean, post-determinism-fix, metrics-only pilot:

- conditions: combat on/raids on, combat off/raids on, combat on/raids off, combat off/raids off;
- 2–3 seeds;
- 100 and 250 ticks first;
- collect elapsed time, raid attempts/successes, structured events, population, factions, resource totals, and state hashes;
- extend to 500 ticks only if individual cells remain below the agreed runtime limit.

That design separates formal combat, economic coercion, logging volume, and faction-count scaling without rewriting the meaning of the validated pilot.
