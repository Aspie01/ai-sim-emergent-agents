# State ownership map

The simulator is midway between legacy module globals and explicit run-scoped state. `SimulationState` is the primary owner, but several world, cooldown, observer, and optional subsystem stores remain module-owned.

| State | Authoritative owner | Writers | Readers | Persistence | Artifact representation |
| --- | --- | --- | --- | --- | --- |
| Living inhabitants | `SimulationState.people` | Admission, births, deaths, combat, interventions, plugins | Nearly all layers | In-memory run only | Metrics counts; selected agent fields in final hash |
| Dead inhabitants | `SimulationState.all_dead` | Death paths | Beliefs, mythology, hash | In-memory run only | Counters/events; selected dead-agent fields in hash |
| Stable ID allocator | `SimulationState.next_inhabitant_id` | `_spawn` transaction | Identity validation | In-memory run only | Final hash payload when identity-aware features apply |
| Spatial occupancy | `world.grid_occupants` | Grid admission/move/remove | Inhabitants, plugins | Rebuilt per run | Not directly persisted |
| World grid/resources | `world.world` | Generation, regeneration, agents, economy, tech, events, plugins | Most causal layers | In-memory run only | Selected tile fields in final hash; `grid_size`/`season` metrics; no world-stock metric |
| Noise offsets/sea threshold | `world` module globals | `reseed_world` | Expansion/generation | In-memory run only | Omitted from artifacts/hash |
| Settlement index | `world._settlements_index` | Formal-faction settlement lifecycle | Movement, reproduction, religion, combat | In-memory run only | Settlement data through faction/hash projection only |
| Formal factions | `SimulationState.factions` | Faction, war, diplomacy, interventions | Economy/combat/tech/diplomacy/religion/observers | In-memory run only | Metrics/events and selected final-hash fields |
| Formal rivalry | `SimulationState.rivalries` alias | Factions, economy raids/trade, combat, diplomacy, interventions | Same | In-memory run only | Selected final-hash mapping |
| Wars/history | `SimulationState.active_wars`, `war_history` | Combat | Economy, tech, diplomacy, religion, metrics | In-memory run only | Selected wars in final hash; events/metrics |
| Treaties/reputation | `SimulationState.treaties`, `reputation` | Diplomacy, raids, combat | Economy/combat/religion/metrics | In-memory run only | Selected active state in final hash; events/metrics |
| Prices/currencies/routes | Economy stores aliased partly into `SimulationState` | Economy | Economy, metrics/technology in places | In-memory run only | Routes selected in hash; prices/currency definitions omitted |
| Legacy trust | Each `Inhabitant.trust` | Layer 1, factions, transfers, religion/tech | Reproduction, beliefs, factions, metrics | Agent lifetime | Selected trust values in hash; mean of stored values in metrics |
| Directed relationships | Each `Inhabitant.relationships` | Committed Layer-4 hooks; maintenance | Partner bias, informal coalitions, summaries/hash | Agent lifetime; cleared at death maintenance | Enabled final hash only; no standard metric |
| Informal coalitions | `SimulationState.coalitions` | Transactional end-of-tick transition | Hash, on-demand summary, next-tick dialect/contact snapshot | In-memory run only | Enabled final hash only |
| Per-agent language | `Inhabitant.language` | Transactional communication; maintenance | Communication, language/dialect/contact summaries, hash | Retained on living/dead agent until death cleanup | Enabled final hash, including contact metadata when enabled |
| Language runtime | `SimulationState.language` | Initialization, communication, maintenance | Validation, summaries, hash | In-memory run only | Enabled final hash and manifest controls |
| Dialect runtime | `SimulationState.dialect` | Dialect-classified communication | Validation, summary, hash | In-memory run only | Enabled final hash; no standard artifact |
| Language-contact runtime | `SimulationState.language_contact` | Different-coalition communication | Validation, on-demand summary, hash | In-memory run only | Enabled final hash; controls in manifest; no standard contact artifact |
| Event journal | `SimulationState.event_log` (`StructuredEventLog`) | All emitters | Observation, display, mythology | Narrative history pruned; journal drained per tick | Typed subset in event CSV |
| Metrics writer state | `MetricsLogger` | Observation/finalization | Manifest writer health | File-backed during run | Required CSVs and manifest health |
| Religion/holy wars | Religion module stores aliased partly into `SimulationState` | Religion | Combat/tech/religion | In-memory run only | Largely omitted from final hash |
| Plugin instances/state | `SimulationState.loaded_plugins` and plugin objects | Loader/plugins | Plugin layer/reset | In-memory/external side effects | No inventory or state hash |
| Dashboard reputation history | `dashboard_bridge` module global | Dashboard bridge | Dashboard serialization | Process-global; not fully reset | Diagnostic JSON only |
| Anti-stagnation trackers | Locals in `sim.run` | Main loop | Anti-stagnation block | In-memory run only | Mostly omitted from final hash |

## Ownership caveats

- `Faction.members` and `Inhabitant.faction` duplicate formal membership authority and lack a general invariant validator.
- Informal-coalition membership is more strictly centralized: active member tuples are authoritative and `member_to_coalition` must be an exact derived index.
- Contact exposure and borrowing provenance are association-owned bounded
  metadata, not coalition-owned registries. Historical source coalition IDs may
  outlive active coalition state.
- The canonical state hash covers a documented projection, not all future-affecting state shown above.
- Events and metrics observe state; they do not own it.
- Required CSVs are overwritten or appended by direct-run writers according to file type; they are not in-memory persistence or a resume checkpoint.

## Implementation evidence

- `src/thalren_vale/state.py::SimulationState`.
- Module-global aliases in `src/thalren_vale/sim.py` and owning domain modules.
- Hash projection: `src/thalren_vale/reproducibility.py::canonical_state_hash`.
- Reset tests: `tests/test_simulation_state.py`.
- Hidden-state fail-closed tests: `tests/test_reproducibility.py`, `tests/test_language_reproducibility.py`.
