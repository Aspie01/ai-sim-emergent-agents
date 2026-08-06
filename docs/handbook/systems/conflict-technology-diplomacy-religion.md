# Conflict, technology, diplomacy, religion, and late interventions

## 1. Overview

After the economy pass, Thalren Vale runs a connected sequence of formal conflict, research, diplomacy, and religion. These systems act on formal factions and can materially change population, resources, trust, beliefs, territory, membership, and institutional state.

Two adjacent mechanisms also run in the latter part of a tick:

- mythology, an LLM-backed narrative observer that is disabled by default; and
- anti-stagnation, an enabled-by-default intervention bundle that can inject people, factions, shocks, rivalry, and eras.

Formal combat is distinct from economy-layer raids. Disabling combat does not disable raids; disabling raids does not disable formal war. Informal coalitions and language do not drive any of the systems on this page.

## 2. Why it exists

The source demonstrably uses these layers to make faction rivalry consequential, let collective resources unlock capabilities, allow formal agreements and surrender terms, add religious institutions, and prevent long quiet periods from leaving the simulation static.

Descriptions such as "civilizational progress," "state formation," or "cultural meaning" are **inferences**. The implementation does not establish scientific validity for those concepts.

## 3. Key terminology

- **Formal war:** a multi-tick `combat.War` between formal factions, possibly with allies.
- **Rivalry/tension:** the integer score in `RIVALRIES` that gates declaration.
- **Economy raid:** a separate economy-layer hostile transfer with its own enable control.
- **Technology:** one of 15 identifiers in a three-branch prerequisite graph.
- **Active research:** a faction dictionary containing technology, progress, start tick, and paused status.
- **Reputation:** a faction-name-keyed integer clamped from -10 to +10.
- **Treaty:** one active record keyed by the unordered pair of faction names.
- **Piousness:** number of distinct raw belief strings held by at least 60% of faction members.
- **Religion:** an object with name, founder faction name, founding tick, and temple-coordinate set.
- **Holy war:** a pair marker in `_HOLY_WARS`; it is not itself a `combat.War`.
- **Anti-stagnation bundle:** late-tick interventions controlled together by `anti_stagnation_enabled`.

## 4. Current status

- Formal combat: **Implemented but experimental**.
- Technology: **Implemented but experimental**.
- Diplomacy: **Implemented but experimental**.
- Religion: **Implemented but experimental**.
- Mythology: **Disabled by default**.
- Anti-stagnation: **Implemented but experimental** and enabled by default.

All are current executable code. None is documented here as research-ready. Direct behavioral test coverage is sparse, and several advertised effects are absent or internally inconsistent.

## 5. State owned

### Combat

`SimulationState.active_wars`, `war_history`, and `rivalries` are authoritative shared stores. A `War` holds primary attacker/defender faction objects, cause, start/tick count, pre-war primary sizes, allied faction lists, outcome, and tribute fields. `combat._alliances` is a compatibility registry reset separately from `SimulationState`.

### Technology

Technology state is attached lazily to formal faction objects as `techs: set[str]` and `active_research: dict | None`. Additional passive fields such as `wealth`, `_laws_rep_applied`, and member medicine/sailing fields are also attached dynamically.

The implemented graph contains 15 technologies:

| Branch | Technologies in prerequisite order |
| --- | --- |
| Industrial | `tools`; `farming`, `sailing`, `mining`; `engineering`; `currency` |
| Martial | `scavenging`; `metalwork`; `weaponry`, `masonry`; `steel` |
| Civic | `oral_tradition`; `medicine`, `writing`; `code_of_laws` |

There are 16 belief-to-branch affinity mappings.

### Diplomacy

`SimulationState.treaties`, `treaty_log`, and `reputation` are authoritative shared stores. Module-local cooldown dictionaries track proposals, breaks, and last negative-reputation ticks. Treaty types are Non-Aggression Pact, Trade Agreement, Mutual Defense Pact, and Tribute Pact; each lasts 50 ticks.

### Religion

`SimulationState.religions` and `holy_wars` are authoritative. Each inhabitant may point to a `Religion` object and hold priest/role flags. Factions can carry a cached priest object ID. Temple tiles belong to the religion object; they refer to, but are not the same as, settlement state.

### Mythology and anti-stagnation

Mythology owns in-memory chronicles, per-faction myths, epitaphs, generation bookkeeping, and an LLM-fired flag. Anti-stagnation uses ordinary population, faction, world, rivalry, event, and era state rather than a dedicated runtime object; several control variables live inside the simulation loop.

## 6. Inputs

| System | Main inputs |
| --- | --- |
| Combat | rivalry, active faction members, beliefs, technology, settlement zones, treaties, religion markers, RNG |
| Technology | faction members/shared beliefs, pooled inventories/reserve, active wars, trade routes, world, RNG |
| Diplomacy | faction size/beliefs, rivalry, active wars, trade routes, reputation, treaties, RNG |
| Religion | faction members/beliefs/settled ticks/settlement, reputation, positions, trust, RNG |
| Mythology | narrative event log, factions, wars/treaties, dead archive, local Ollama endpoint |
| Anti-stagnation | recent narrative activity, population/faction counts, world resources, rivalry, technology, RNG |

## 7. Processing sequence

### Layer 5: formal combat

`combat_tick()` runs after economy:

1. Build the list of nonempty factions and scan rivalry entries for new declarations.
2. A rivalry must first reach configured tension (default 200). Beliefs can raise or lower an effective threshold by 50. A faction of at least three members holds a council vote; a failed vote blocks declaration unless tension is another 80 above the effective threshold.
3. The declared attacker loses one reputation point. A `War` is created, mutual-defense treaty allies are recruited, and additional alliances may be requested.
4. For every active war, increment duration, check alliances, compute side strengths, and resolve casualties.
5. Strength is member count multiplied by morale and `technology.combat_bonus()`. Defenders receive morale and proportional active-settlement wall bonuses. Holy-war membership can upgrade Metalwork's 1.30 multiplier to 1.60.
6. The stronger side has per-faction casualty probability 0.08 and the weaker side 0.25. A successful draw removes one random member from that faction, the grid, and the living population; it archives the casualty, adds a legend, and gives surviving faction members combat beliefs.
7. No war resolves before five battle ticks. Thereafter surrender can follow loss/territory conditions, both sides can cease fire after heavy loss, annihilation resolves, and tick 40 forces exhaustion.
8. Ending emits `war_ended`, applies winner/loser beliefs, territory and trust effects, asks diplomacy to select surrender terms, and may absorb remnants.
9. Ended wars move from active history to resolved history.
10. Tribute payments for prior wars are processed.

The declaration code checks a nonexistent technology identifier `weapons`; the implemented identifier is `weaponry`. Therefore the advertised threshold fear/emboldening adjustment does not activate for Weaponry.

### Layer 6: technology

For every nonempty faction:

1. Ensure `techs` and `active_research` exist.
2. If research is active, pause it while any side of an active war contains the faction. On peace, unpause, advance one tick when membership is at least two, and apply `max(0.0, reserve - 1.0)`. Progress therefore advances even with an empty reserve, while reserve cannot become negative.
3. Complete when progress reaches base duration, reduced to 80% (minimum five) by Engineering; emit `tech_researched`.
4. If idle, at peace, and at least two members strong, enumerate prerequisite-satisfied affordable technologies.
5. Score candidates by tier plus shared-belief branch affinity; choose randomly among top ties.
6. Deduct the full start cost from reserve first and then member inventories, and create the active-research record.
7. Apply passive effects every tick:

| Technology | Executable effect |
| --- | --- |
| Tools | each member can take one extra tile food on even ticks |
| Farming | add up to three reserve food; floor faction-territory food at five |
| Sailing | mark members able to enter sea; every third tick near coast, add one tile food up to cap and also add one personal food |
| Mining | generate one ore and one stone for one rotating member |
| Engineering | double Mining generation and reduce future durations by 20% |
| Currency | increment a faction `wealth` attribute by one |
| Scavenging/Weaponry/Steel | multiply economy-raid loot by 2/3/4 |
| Metalwork/Weaponry/Steel | combat strength multiplier 1.30/1.50/1.80 |
| Masonry/Steel | `defense_bonus()` returns 1.20, but current combat does not call it |
| Oral Tradition | every third tick, attempt one random intra-faction belief copy |
| Medicine | heal selected hunger damage, replenish a five-use buffer, set `_plague_resist` |
| Writing | random intra-faction and trade-route belief transmission |
| Code of Laws | every fifth tick add internal trust unless in holy war; apply a one-time reputation increase |

### Layer 7: diplomacy

`diplomacy_tick()`:

1. Cap active non-aggression pairs at tension 100.
2. Expire treaties whose end tick has arrived; both signatories gain one reputation.
3. Every 25 ticks, recover one reputation toward +10 after at least 25 ticks without a recorded negative event.
4. Break a treaty when its signatories fight; the breaker loses three reputation and receives a ten-tick cooldown.
5. Every fifth tick, sample up to six active factions and inspect unordered candidate pairs.
6. Apply proposal eligibility: reputation, 20-tick proposal rate limit, break cooldown, no existing treaty/war, faction-size ratio, shared enemy, trade route, and tension band.
7. The receiving faction uses belief modifiers, reputation, a council vote when size is at least three, and an RNG draw to accept. A successful treaty emits `treaty_signed`.
8. Every 30 ticks, a faction with reserve above twelve food per member may give up to ten food (5% of reserve) to a needy faction and gain two reputation.

Council votes are deterministic for explicit belief positions but use RNG for undecided members. A close result increments `_council_tension`; no current faction code consumes that field.

On a decisive war end, `resolve_surrender()` cancels combat's default 20-tick tribute and chooses one of four terms from winner beliefs or RNG:

- `ANNEX`: move loser members into the winner;
- `TRIBUTE`: set 30 ticks of tribute;
- `EXILE`: move loser members at least five Manhattan cells when candidates exist;
- `VASSALIZE`: attach `vassal_of` to the loser.

### Religion layer

Religion runs after diplomacy:

1. Every ten ticks, each faction may found a religion if it has at least three members, `settled_ticks >= 10`, no current faction religion, and piousness at least three. Founding assigns the religion pointer to current members and creates a temple at an active settlement.
2. Every 100 ticks, ensure one cached priest for each religious faction by choosing greatest average legacy trust. Other ticks only invalidate a cache when that object left the faction.
3. Every tick, feed each priest one faction-reserve food and reduce hunger, or add five hunger if reserve is empty. Priests skip normal gathering.
4. Every fifth tick, any inhabitant within Chebyshev distance 3 of any temple gets +1 on every existing legacy trust entry, capped at 100.
5. Every fifth tick, priests move toward low-trust faction members, select a nearby low-trust target of another religion when possible, and attempt conversion with probability 0.70 inside the faction or 0.25 across faction lines. Conversion changes religion, boosts priest-target trust, and can append the faction's dominant belief.
6. Every tick, inspect pairs of religious factions within Chebyshev center-of-gravity distance 25. Distinct religions and either faction reputation at or below -5 create a holy-war pair marker.
7. Remove holy-war markers when a faction name is absent from the faction collection.

Holy-war detection does not declare or schedule formal combat. It only changes current combat/Code-of-Laws modifiers when a formal war independently exists.

### Mythology observer

When `MYTHOLOGY_ENABLED` is true and the layer is not disabled, mythology checks battle deaths each tick, requests a chronicle every 50 ticks, and requests faction myths every 100 ticks. Requests are synchronous HTTP POSTs to the configured local Ollama endpoint; failures return empty text and trigger deterministic fallback prose. Finalization can request a narrative history. The subsystem stores narrative history and writes output, but does not intentionally mutate simulation decisions.

With mythology disabled (the default), full-log mode instead appends a manual, non-LLM chronicle every 50 ticks. These narrative files are optional diagnostics, not canonical research artifacts.

### Late anti-stagnation bundle

When enabled:

1. Every tenth tick an isolated one-member formal faction loses 10 health; zero-health members are removed.
2. Every 200 ticks a weighted world event chooses plague, golden age, migration, earthquake, or free discovery.
3. Every 500 ticks an era shift halves rivalries and adds one third of biome food cap to each tile.
4. Every 40 ticks, low population or fewer than three active factions can spawn five or ten travelers.
5. Every 25 ticks, prolonged low faction count can force two new factions; inactivity beyond 40 ticks triggers a disruption event.
6. Disruptions choose great migration, plague, civil war, promised land, or prophet, directly mutating population, factions, health, food, rivalry, beliefs, or tile habitability.
7. Peace milestones attempt rivalry escalation at 50, 75, and 100 quiet ticks.

Because the aggressive-migration condition `tick % 30 == 0` is nested inside a `tick % 25 == 0` block, that branch can run only every 150 ticks. The 50-tick peace loop visits both ordered faction directions and therefore adds 20, not the printed +10, to each unordered rivalry pair. The 100-tick incident prints that a selected inhabitant was found dead but does not remove or damage that inhabitant.

## 8. Outputs

- Combat: population/faction removal, war histories, rivalry, beliefs, territory, tribute, legends, reputation, surrender state.
- Technology: inventories/reserves, world resources, beliefs/trust, movement capability, health buffers, tech and research state.
- Diplomacy: treaty/reputation/cooldown state, reserve sharing, rivalry, faction membership/position changes after surrender.
- Religion: religion pointers, temples, priests, hunger, trust, beliefs, holy-war markers.
- Mythology: stdout/log narrative, in-memory prose, and optional manual chronicle/final-history files.
- Anti-stagnation: direct world/population/faction/technology/rivalry mutations and typed world/era/stagnation events.
- Metrics and summaries observe selected aggregates; no canonical artifact contains every internal field above.

## 9. Lifecycle position

The order is economy -> combat -> technology -> diplomacy -> religion (and mythology if enabled). Map expansion and activity detection follow. Solo fragility and world events occur before plugins; era shifts and housekeeping follow plugins; traveler/low-faction/peace anti-stagnation logic follows housekeeping. Social, informal-coalition, and language maintenance runs after these causal layers. End-of-tick metrics observe the final state. See [Tick lifecycle](../architecture/tick-lifecycle.md).

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| Formal factions/beliefs | bidirectional | membership, rivalry, shared/individual beliefs, reserves | all four core layers | decisions and mutations |
| Economy | bidirectional | raids, trade routes, reserves, treaty bonus, tribute | before/after combat | material causes and consequences |
| World/population | mutation | resources, health, positions, deaths, movement capability | technology/religion/late layer | survival and geography |
| Settlements | bidirectional | walls, temple anchor, food storage, settled ticks | combat/religion | defense and institution founding |
| Events/metrics | output/observation | typed events and aggregates | throughout/end tick | audit trail |
| Informal coalitions | intentionally isolated | no membership input | end tick | no war/diplomacy/religion effect |
| Endogenous language | intentionally isolated | none | economy communication only | language never changes these systems |
| Mythology | observation/output | narrative event/state summaries | late/final | diagnostics, no intended core feedback |
| Anti-stagnation | direct mutation | ordinary core state | late tick | explicit intervention, not observation |

## 11. Configuration

See [Configuration reference](../reference/configuration-reference.md).

| Field/flag | Type | Default | Validation | Effect |
| --- | --- | ---: | --- | --- |
| `war_tension_threshold` / `--war-tension-threshold` | integer | `200` | at least 1 | base formal-war declaration threshold |
| `--disable-layer combat` | Boolean layer name | enabled | fixed allowlist | disables formal combat only |
| `--disable-raids` or `--disable-layer raids` | Boolean layer name | raids enabled | fixed allowlist | disables economy raids only |
| `--disable-layer technology` | Boolean layer name | enabled | fixed allowlist | skips research and passive effects |
| `--disable-layer diplomacy` | Boolean layer name | enabled | fixed allowlist | skips treaty/reputation tick; combat can still call diplomacy helpers |
| `--disable-layer religion` | Boolean layer name | enabled | fixed allowlist | skips religion tick; stored state/helpers remain |
| `--disable-layer mythology` | Boolean layer name | enabled at layer level | fixed allowlist | suppresses LLM/manual mythology path |
| `anti_stagnation_enabled` / `--disable-antistag` | Boolean | `true` | flag | enables/disables the whole late intervention bundle |
| `MYTHOLOGY_ENABLED` | source constant | `False` | not CLI-configurable | gates LLM mythology |
| `NARRATIVE_MODEL` | string constant | `internlm2:1.8b-chat-v2.5-q4_K_M` | not validated | Ollama model |
| `OLLAMA_URL` | string constant | `http://localhost:11434/api/generate` | not validated | local narrative endpoint |
| `OLLAMA_TIMEOUT` | seconds | `150` | not validated | per-call timeout |

War lengths (minimum 5, maximum 40), treaty duration 50, technology costs/durations, religion thresholds, and anti-stagnation cadences are fixed source constants.

## 12. Events

| Event type | Producers | Notes |
| --- | --- | --- |
| `war_declared`, `war_ended` | combat | direct typed events |
| `death` | combat casualty legacy classifier and direct death paths | casualty source is a recognized narrative record |
| `tech_researched` | technology | completion only; starts/pauses/resumes are narrative |
| `treaty_signed`, `treaty_broken` | diplomacy | direct typed events |
| `world_event` | 200-tick world event | typed |
| `era_shift` | 500-tick era shift | typed |
| `stagnation_trigger` | disruption | typed |

Religion founding, temples, conversion, holy-war declaration/end, food sharing, surrender terms, research starts, and many alliance messages are narrative-only. Mythology produces no canonical structured event type.

## 13. Metrics

| Metric | Interpretation | Frequency/caveat |
| --- | --- | --- |
| `war_count` | currently active formal wars | every completed tick |
| `total_wars_declared` | cumulative declaration events | every tick |
| `total_techs` | sum of technology counts over active factions | every tick; duplicates count |
| `total_treaties` | active treaties | every tick |
| `mean_reputation`, `reputation_variance` | active-faction global reputation distribution | every tick |
| `total_wars`, `mean_war_duration` | run-summary war aggregates | final summary |
| `total_unique_techs`, `mean_tech_count_per_faction` | run-summary technology aggregates | final summary |
| `total_treaties_formed/broken` | event-derived totals | final summary |
| `stagnation_events`, `era_count` | intervention event totals | final summary |

There are no canonical religion, conversion, temple, holy-war, mythology, research-progress, alliance, tribute, or vassal metrics.

## 14. Determinism and RNG

All core systems on this page use the process-wide RNG. Combat uses it for undecided council votes, alliances, casualties, and targets. Technology uses it for research tie-breaking and belief spread. Diplomacy uses it for votes, acceptance, candidate sampling, food recipients, and default surrender terms. Religion uses it for conversion and birth inheritance. Anti-stagnation uses it extensively. Explicitly seeded serial runs are intended to reproduce the shared draw order.

Mythology does not use the Python RNG for simulation choices, but an external generative model is not deterministic evidence and can change wall-clock behavior or output independently of the seed.

Canonical hashing has a material gap: faction serialization records obsolete `researching` and `research_progress` attributes rather than the live `active_research` dictionary. Research progress is future-affecting but is not represented by those current hash fields.

## 15. Failure and edge cases

### Combat and technology

- Declaration checks `weapons` while the tree defines `weaponry`.
- `technology.defense_bonus()` is not applied by `_side_strength()`; Masonry's advertised defense effect is absent except for settlement walls.
- Steel does not bypass the 40-tick exhaustion rule despite its description.
- War pre-size fields count only primary factions, while later loss fractions use primary plus allies, distorting loss ratios when allies join.
- Currency increments `faction.wealth`, but economy wealth calculations ignore that field and the advertised +2 trade gold is absent.
- Medicine sets `_plague_resist`, but current plague event code does not read it.
- Sailing fishing adds one food to the tile and independently one to inventory, creating food rather than transferring one unit.
- Live active-research progress is missing from canonical faction hashing.

### Diplomacy

- `ANNEX` assigns `member.faction` to the winner `Faction` object, while the rest of the legacy system expects a faction-name string.
- `EXILE` assigns `r`/`c` directly instead of using `grid_move()`, leaving `grid_occupants` stale.
- `vassal_of` has no current downstream consumer.
- `_council_tension` has no current downstream consumer.
- Faction renaming during merger does not comprehensively migrate every external name-keyed registry.

### Religion and interventions

- Piousness compares raw tagged belief strings rather than canonical cores.
- Temple trust applies to every nearby inhabitant and every existing trust edge, regardless of religion or faction.
- Conversion directly appends a belief and can exceed the normal eight-belief cap.
- Prior priests are not comprehensively demoted when faction/religion circumstances change.
- Holy-war cleanup considers an empty retained faction object still present, so a marker can persist after effective dissolution.
- Promised Land can mark a sea tile habitable.
- A normal 200-tick plague ignores Medicine resistance; plague health is clamped to at least one there, while disruption plague can reach zero and only immediately removes selected solo members.
- The printed peace `+10` differs from executed +20 per unordered pair; incidents do not kill their named victim.

### Mythology

- Network/model failures are swallowed into fallback prose.
- Synchronous calls can each wait up to 150 seconds.
- Narrative files and model/environment provenance are not part of the required canonical artifact inventory.

## 16. Tests and validation

There are no focused `test_combat.py`, `test_technology.py`, `test_diplomacy.py`, `test_religion.py`, or mythology tests.

Current indirect evidence includes:

- `tests/test_simulation_state.py`: shared ownership and reset for wars, rivalries, treaties, reputation, religions, and holy wars.
- `tests/test_events.py`: typed-event ordering and the treaty sign/break lifecycle.
- `tests/test_artifact_validation.py`: technology identifier allowlist, metrics/event/summary consistency, and rejection of unknown tech identifiers.
- `tests/test_reproducibility.py`: same-seed subprocess hashes and raid-control determinism.
- `tests/test_raid_control.py`: formal-combat and raid controls remain independent.
- `tests/test_antistagnation.py`: only traveler cadence and suppression.
- `tests/test_run_termination.py`: bounded end-to-end terminal and metric consistency.
- `tests/test_language_interaction_hooks.py`: communication cannot mutate wars or formal factions.

These tests do **not** prove war strength/resolution, alliance loss math, every passive technology, research persistence/hashing, treaty proposal semantics, surrender consistency, religion founding/conversion/holy wars, mythology isolation, or the full anti-stagnation bundle. See [Test reference](../reference/test-reference.md).

## 17. Worked example

Suppose rivalry between factions A and B reaches 200. If A has no threshold-changing belief and its three-member council passes, A can declare war. B's active Mutual Defense Pact may recruit C. On each battle tick, side strength includes members, morale, martial multiplier, and B-side settlement walls. Technology research for A, B, and C pauses in the next Layer-6 pass. After at least five battle ticks, a decisive loss can end the war; diplomacy then replaces combat's initial tribute setup with a belief-selected surrender term. A holy-war marker between A and B would modify Metalwork/Code-of-Laws effects, but it would not have caused this war declaration.

## 18. Current limitations

- These older layers are broad, causal, and lightly unit-tested.
- Source descriptions for several technologies do not match executable effects.
- Research progress is absent from current canonical hash representation.
- Diplomacy uses faction names as registry identity while merger and surrender paths can rename or mistype that identity.
- Holy war is a modifier marker, not a formal diplomacy/combat lifecycle.
- Religion has no canonical metrics or typed event family.
- Anti-stagnation combines many distinct interventions behind one control and contains cadence/message mismatches.
- Mythology is optional diagnostic narration without canonical provenance.
- Historical README claims of 16 technologies, active Masonry defense, Steel exhaustion immunity, Medicine plague resistance, currency trade bonuses, council-driven schism, or automatic holy-war combat are stale where they conflict with source.

## 19. Future extensions

Language-driven combat, diplomacy, religion, and formal faction identity are
**Planned, not implemented**. Language Contact v1, Intergenerational Language
v1, Lexical Evolution v1, Compositional Protolanguage v1, Grammar Evolution v1,
and Language Coevolution v1 are implemented, and all are causally isolated from
every system on this page. Coevolution's one reverse edge reaches directed
relationship ties and partner choice only; it does not touch combat,
technology, diplomacy, or religion. The future milestones
are:

- `feature/language-research-readiness-v1` — **Planned, not implemented**.

No final research contract, hypothesis, or research-ready claim is established for the systems on this page.

## 20. Implementation evidence

**Implementation status:** Mixed statuses listed above in the documented
Language Contact v1 working tree; contact adds no causal path into these
systems. See [Handbook status](../HANDBOOK_STATUS.md) for branch and base-commit
metadata.

**Primary source**

- `src/thalren_vale/combat.py`
- `src/thalren_vale/technology.py`
- `src/thalren_vale/diplomacy.py`
- `src/thalren_vale/religion.py`
- `src/thalren_vale/mythology.py`
- `src/thalren_vale/sim.py`: layer order, world/era/disruption/peace interventions and mythology calls.
- `src/thalren_vale/factions.py`, `src/thalren_vale/economy.py`, `src/thalren_vale/world.py`: upstream/downstream institutional state.
- `src/thalren_vale/state.py`: authoritative mutable stores.
- `src/thalren_vale/reproducibility.py`: current faction hash representation.
- `src/thalren_vale/artifact_contract.py`, `src/thalren_vale/metrics.py`: event/metric contracts.

**Primary tests**

- `tests/test_simulation_state.py`
- `tests/test_events.py`
- `tests/test_artifact_validation.py`
- `tests/test_reproducibility.py`
- `tests/test_raid_control.py`
- `tests/test_antistagnation.py`
- `tests/test_run_termination.py`
- `tests/test_language_interaction_hooks.py`

**Bounded verification commands used for this handbook revision**

No late-layer test or simulation command was run by this page's drafting agent. Claims were source-traced against the recorded commit. Repository-wide verification is recorded in `HANDBOOK_STATUS.md`.

**Unresolved discrepancies**

- Live `active_research` is not the research state serialized by the canonical faction hash helper.
- Several technology descriptions advertise effects that have no active consumer.
- Diplomacy surrender can violate faction-field and spatial-index invariants.
- Religion and anti-stagnation observations have incomplete typed/canonical coverage.
- Historical README and source comments must not override the executable behavior and gaps documented above.
