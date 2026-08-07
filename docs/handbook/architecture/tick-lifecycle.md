# Simulation and tick lifecycle

This page records the executable order in the current `main` working tree. The
handbook's v0.1 base revision is commit
`2855bf15a77dffc599f6a0f4ac08721f79a379d4`; the milestones merged since it are
listed in [handbook status](../HANDBOOK_STATUS.md). Layer-number comments in
older prose are not authoritative when they differ from this sequence.

## Initialization

1. Parse CLI with abbreviations disabled.
2. Build, normalize, and validate `SimulationConfig`.
3. Apply compatibility globals.
4. Validate all existing language owners plus language/dialect/contact/intergenerational/lexical runtimes, historical parent IDs, and historical lexical source IDs, then reset run state. Validation happens before clearing so malformed hidden state cannot cause a partial reset.
5. Choose the explicit seed, or draw and record one for an unseeded run.
6. Seed the process-global `random` generator.
7. Initialize the deterministic language seed domain and enabled
   dialect/contact/intergenerational/lexical runtimes when language is enabled.
8. Select serial Layer 1 for an explicit seed; otherwise select threaded Layer 1.
9. `reseed_world()` regenerates world and spatial indexes in place.
10. Construct `MetricsLogger`, which creates and headers required CSVs.
11. Initialize world food and obtain spawnable coordinates.
12. Create initial inhabitants and transactionally admit stable IDs.
13. Discover and load sorted `plugins/*.py` modules.

## Exact tick order

For tick `t`:

| Order | Stage | Principal reads and writes |
| ---: | --- | --- |
| 1 | Open observation journal; compute season transition | Event journal and winter flags |
| 2 | World layer | Regenerate non-sea resources; optional winter-end message |
| 3 | Inhabitant layer | Shuffle; hunger, health, consumption, movement, gathering, legacy trust/swaps; commit deaths |
| 4 | Belief layer, unless disabled | Experience-derived beliefs and directed sharing |
| 5 | Formal-faction layer, unless disabled | Formation, reserves, recruitment, territory/settlements, rivalry, schism/merge; then remove same-tick dead members |
| 6 | Procreation | Up to three births, cap/winter/housing permitting; optional exact-once parental comprehension exposure after each successful `_spawn(child)` |
| 7 | Economy, unless disabled | Build one coalition-language snapshot first when dialect or contact is enabled; currency, prices, scarcity, Layer-4 transfers, optional lexical descendant emission, faction trade, raids |
| 8 | Formal combat, unless disabled | War declaration, battle, resolution, tribute |
| 9 | Technology, unless disabled | Research progress/completion and passive effects |
| 10 | Diplomacy, unless disabled | Treaty lifecycle, proposals, reputation, aid |
| 11 | Religion and optional mythology/manual chronicle | Institutions and narrative observation |
| 12 | Map expansion and optional dashboard | Every 25 ticks; dashboard only in full mode |
| 13 | Dynamic-activity scan | Inspect messages produced so far this tick |
| 14 | Optional belief/annexation tracker | Diagnostic; broad exceptions are swallowed |
| 15 | Solo-faction fragility | Anti-stagnation-dependent health/death path |
| 16 | Scheduled world event | Every 200 ticks when anti-stagnation is enabled |
| 17 | Plugin layer | Validated commands can spawn inhabitants or adjust resources |
| 18 | Era shift | Every 500 ticks when anti-stagnation is enabled |
| 19 | Housekeeping | Every 50 ticks: prune narrative history, archive empty factions, trim memories, optional era export |
| 20 | Anti-stagnation block | Traveler waves, low-faction forcing, disruptions, peace escalation |
| 21 | Emergent maintenance | Directed relationships -> informal coalitions -> language forgetting/death cleanup |
| 22 | Authoritative observation | Drain journal; write events; write metrics; write cadence belief snapshot |
| 23 | Completion boundary | Set `_last_completed_tick = t` |
| 24 | Diagnostic timing/rendering | Optional display and progress |
| 25 | Extinction check | Stop normally if no living inhabitants remain |

## Timing consequences

- Layer-1 deaths are observed during agent work and committed after the complete serial/worker pass.
- A child born at stage 6 does not act, receive normal belief/faction processing, or move in that tick. It is visible to economy and all later stages. When intergenerational language is enabled, the exact child and parents enter one deterministic comprehension-only hook after admission and before religion inheritance or birth-event emission.
- A transmission exception fails the tick/run closed and rolls back child/base/intergenerational language owners, but the child remains admitted, its stable ID remains consumed, and parental food remains deducted. This is not birth-language atomicity.
- Economy reads combat/diplomacy state from the prior tick because those layers run afterward.
- Same-tick successful Layer-4 transfers can update relationships, and those relationships can affect the coalition transition at stage 21.
- Dialect/contact classification at stage 7 uses one frozen snapshot of the
  last fully committed coalition observation, normally tick `t-1`; the
  stage-21 coalition transition cannot reclassify earlier communication.
- Lexical evolution needs no coalition snapshot. After a transfer commits, a
  pre-existing usable production form gets at most one deterministic
  opportunity. A successful substitution becomes the actual emitted signal;
  no opportunity arises from ordinary invention.
- World events occur after the dynamic scan, so their messages do not refresh `_last_dynamic_t` during that scan.
- End-of-tick metrics include plugin, world-event, era-shift, anti-stagnation, and emergent-maintenance changes.

## Finalization and termination

Normal terminal reasons are:

- `requested_ticks_reached` at the requested horizon;
- registered `extinction` before the horizon.

Cancellation and exceptions produce nonaccepted result states even if a manifest can be sealed.

Finalization order is:

1. Drain any pending partial-tick journal records.
2. Finalize summary/event writers.
3. Close required writers and capture writer health.
4. Compute the canonical selected-state hash.
5. Produce optional narrative/RA reports according to policy.
6. Restore stdout and close the raw text log.
7. Build artifact checksums/inventory.
8. Atomically publish the run manifest last.

`final_tick` and `completed_ticks` are the last fully completed tick. A failure after partial state mutation is not rolled back; strict validation rejects event/metric rows outside the declared completed horizon.

## Worked timing example

Suppose tick 12 contains a paid individual transfer between two inhabitants:

1. Their inventories and currency commit in economy.
2. Optional directed relationships update exact-once.
3. Optional language communication runs exact-once using the tick-12 frozen
   coalition snapshot. Only a pair in different active coalitions can enter
   Language Contact v1; assigned/unassigned pairs stay on the base language
   path.
4. If lexical evolution is enabled and the sender already has a usable
   production form, one SHA-256 opportunity may substitute one token. The
   descendant is the actual signal used by receiver, dialect, and contact
   processing; the transfer remains committed regardless of language outcome.
5. Combat and later causal layers run.
6. Relationship maintenance sees the new tie.
7. Coalition transition for observation 12 may use it.
8. Tick-12 metrics observe the resulting state.
9. Tick-13 dialect/contact classification can use the newly committed coalition membership.

For a successful birth in tick 12, `_spawn(child)` first commits the child to
the grid, population, optional inherited faction, and stable-ID allocator. Only
then can the enabled intergenerational helper read the exact two parents and
propose bounded child comprehension. Founders, travelers, disruption arrivals,
plugins, and other `_spawn()` callers never enter that hook.

## Implementation evidence

- Source: `src/thalren_vale/sim.py::run`, `economy_layer`, `maintain_emergent_state`.
- Population staging: `src/thalren_vale/inhabitants.py`, `src/thalren_vale/state.py`.
- Tests: `tests/test_language_interaction_hooks.py`,
  `tests/test_language_contact.py`, `tests/test_run_termination.py`,
  `tests/test_simulation_state.py`, `tests/test_coalition_dialects.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_lexical_evolution.py`.
- Tests establish focused ordering and completion semantics; the complete order above is source-verified.
