# Events and Metrics Reference

This page documents the active structured observation schemas. Metrics are
recorded after all enabled tick layers, anti-stagnation work, and emergent
social/coalition/language maintenance. They describe the authoritative
end-of-tick state for each fully completed tick.

## Structured events

Event schema version: `1`.

Exact CSV header:

```text
event_schema_version,seed,tick,event_type,actor,target,detail
```

| Field | Meaning | Caveat |
| --- | --- | --- |
| `event_schema_version` | Row event schema; currently `1` | Must match the manifest and active event type registry |
| `seed` | Run seed | Validated against the expected run identity |
| `tick` | Tick in which the event was committed/observed | Must be positive, nondecreasing, and no greater than `final_tick` |
| `event_type` | Registered machine-readable type | Unknown or empty values invalidate strict evidence |
| `actor` | Primary participant or source, where applicable | Free text; semantics vary by type |
| `target` | Secondary participant or target, where applicable | Free text; may be empty |
| `detail` | Type-specific compact value | `tech_researched` must use a registered technology identifier |

The in-memory `SimulationEvent` also has `message` and `metadata`, but those
fields are not persisted in the canonical event CSV.

### Registered event types

| Event type | Implemented meaning |
| --- | --- |
| `war_declared` | A formal war declaration was emitted |
| `war_ended` | A formal war termination was emitted |
| `faction_formed` | A faction formation event was emitted |
| `faction_dissolved` | Reserved/allowed schema type; no current production emitter was found during source tracing |
| `schism` | Faction split event |
| `merger` | Faction merge event |
| `treaty_signed` | Treaty formation event |
| `treaty_broken` | Treaty termination/violation event |
| `tech_researched` | Completed technology; `detail` is the canonical technology identifier |
| `settlement_founded` | Settlement creation event |
| `birth` | Birth committed by the simulation |
| `death` | Death recorded by the simulation |
| `era_shift` | Era-classification transition event |
| `stagnation_trigger` | Anti-stagnation intervention trigger |
| `raid` | Successful emitted economy-layer raid event |
| `world_event` | Scheduled 200-tick event: Plague, Golden Age, Migration, Earthquake, or Discovery |

An event count is a count of emitted event rows. It is not automatically a
count of eligibility checks, pair scans, failed attempts, policy exposure, or
opportunities. In particular, raid rows count successful emitted raids.

### Exact-once observation path

`StructuredEventLog` maintains a per-tick journal in generation order. Typed
emitters journal a typed event and its narrative together. Legacy text can be
appended and later promoted with an opaque one-use token. Tokens reject wrong
owner, stale generation, wrong tick/text/type, and double promotion.

At the observation boundary, `sim.py` drains the journal once. Typed events go
directly to the writer. Untyped legacy text passes through a compatibility
regex classifier. The classifier is heuristic and catches errors broadly;
current producers should prefer typed events.

Narrative-list pruning does not prune the undrained structured journal. On a
failed partial tick, pending journal rows may be sealed as audit data, but
strict validation rejects rows later than the last fully completed tick.

Zero event rows are valid when the explicit sealed artifact policy permits
them; the current contract sets `allow_zero_events: true`.

## Tick metrics

Metrics schema version: `2`.

Timing contract: `end_of_tick_v2`.

Exact CSV header:

```text
seed,tick,population,faction_count,war_count,total_wars_declared,total_deaths,total_births,gini,mean_trust,mean_food,total_techs,total_treaties,max_generation,mean_generation,largest_faction_size,smallest_faction_size,total_schisms,total_mergers,peace_ticks,mean_reputation,reputation_variance,grid_size,season
```

| Metric | Current calculation and unit | Caveat |
| --- | --- | --- |
| `seed` | Integer run seed | Identity, not a measured outcome |
| `tick` | Fully completed tick, beginning at 1 | Strict runs require contiguous coverage through `final_tick` |
| `population` | Number of inhabitants in the authoritative active collection | End-of-tick count |
| `faction_count` | Factions with nonempty member collections | Formal factions, not informal coalitions |
| `war_count` | Currently active formal wars | Policy availability is separate from realized wars |
| `total_wars_declared` | Cumulative `war_declared` rows | Must equal final event count |
| `total_deaths` | Cumulative `death` rows | Event-based cumulative count |
| `total_births` | Cumulative `birth` rows | Event-based cumulative count |
| `gini` | Gini coefficient over nonnegative individual wealth; wealth is currency plus food×2, wood×3, ore×5, stone×4 | Recomputed using a population-wide sort; observer cost is `O(P log P)` |
| `mean_trust` | Mean of all values in inhabitants' legacy directed `trust` dictionaries | Not the newer `Relationship` trust field and not a mean over all possible pairs |
| `mean_food` | Mean individual food inventory | Resource units per active inhabitant |
| `total_techs` | Sum of technology-set sizes over active factions | The same technology in two factions counts twice |
| `total_treaties` | Current treaty collection size | Active stock, not cumulative formations |
| `max_generation` | Maximum authoritative inhabitant generation | No biological age metric exists |
| `mean_generation` | Arithmetic mean generation | Generation index, not age |
| `largest_faction_size` | Maximum active faction member count | Zero when no active faction |
| `smallest_faction_size` | Minimum active nonempty faction member count | Zero when no active faction |
| `total_schisms` | Cumulative `schism` rows | Must match events at final tick |
| `total_mergers` | Cumulative `merger` rows | Must match events at final tick |
| `peace_ticks` | Current tick minus the most recent tracked dynamic-event tick supplied by the simulator | Broader than time since formal war; name is potentially misleading |
| `mean_reputation` | Mean diplomacy reputation over active factions | Fallback zero on observer lookup failure |
| `reputation_variance` | Population variance over active faction reputations | Zero with no active factions |
| `grid_size` | Number of world rows | Current world is square; this is one side length |
| `season` | `1` for the fixed winter phase, otherwise `0` | Encoded integer, not a label |

Metrics write once per completed tick and flush every 100 ticks. A write or
flush failure is retained in `writer_health` and invalidates required evidence
unless the specifically recoverable buffered event-flush accounting is fully
resolved.

The metrics observer consumes no RNG and should not mutate simulation state.
Its computations still have runtime and memory cost; no scientific claim may
attribute simulation runtime differences to one observer component without a
separate controlled performance study.

## Belief snapshots

Beliefs schema version: `1`.

Exact CSV header:

```text
seed,tick,inhabitant_id,faction,beliefs
```

Rows are written every 100 ticks, one per inhabitant in the supplied active
population. Beliefs are sorted lexicographically and joined with semicolons.
The faction value is the current faction string or `none`.

Current implementation discrepancy: `inhabitant_id` contains
`Inhabitant.name`, not the authoritative stable inhabitant ID. The validator
checks only that identities are nonempty and unique within a tick. Interpret
this field as a display name in current artifacts.

A header-only beliefs file is valid before the first required cadence, or when
no cadence has living inhabitants. At a required cadence, row count must equal
the metrics population.

## Run summaries

Summary schema version: `1`.

Exact CSV header:

```text
seed,condition,final_population,peak_population,min_population,total_factions_formed,final_faction_count,peak_faction_count,first_faction_tick,total_wars,total_deaths,total_births,total_schisms,total_mergers,mean_gini,final_gini,peak_gini,total_unique_techs,mean_tech_count_per_faction,total_treaties_formed,total_treaties_broken,max_generation,mean_war_duration,stagnation_events,era_count,wall_clock_seconds,peak_ram_mb
```

The summary is written during required finalization. Strict run directories
must contain exactly one row. Principal semantics:

- final/peak/min population and faction counts aggregate metrics rows;
- `min_population` is the minimum positive observed population, with final
  population fallback when none was observed;
- cumulative wars, deaths, births, schisms, mergers, treaties, stagnation, and
  era counts come from structured events;
- unique technologies count distinct valid `tech_researched.detail` values;
- mean war duration uses matched emitted start/end events;
- `wall_clock_seconds` and `peak_ram_mb` are nondeterministic operational
  measurements, not canonical biological state.

Strict validation cross-checks summary values against metrics and events. A
summary file alone is never proof of a valid run.

## Language, coalition, and dialect observability

Current structured event and metrics schemas contain no dedicated endogenous
language, informal coalition, or coalition-dialect event/metric fields. Those
systems expose bounded runtime state, hashes, tests, and on-demand summaries,
but do not add research artifact schemas in the completed v1 milestones.

## Implementation evidence

- Event registry/journal: [`src/thalren_vale/events.py`](../../../src/thalren_vale/events.py)
- Metric writer: [`src/thalren_vale/metrics.py`](../../../src/thalren_vale/metrics.py)
- Schema constants: [`src/thalren_vale/artifact_contract.py`](../../../src/thalren_vale/artifact_contract.py)
- Observation boundary: [`src/thalren_vale/sim.py`](../../../src/thalren_vale/sim.py)
- Validation: [`src/thalren_vale/artifact_validation.py`](../../../src/thalren_vale/artifact_validation.py)
- Tests: [`tests/test_events.py`](../../../tests/test_events.py),
  [`tests/test_artifact_validation.py`](../../../tests/test_artifact_validation.py),
  [`tests/test_run_termination.py`](../../../tests/test_run_termination.py)
