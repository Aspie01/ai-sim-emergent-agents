# Events, Observers, and Plugins

## 1. Overview

Thalren Vale has an observation pipeline and a plugin extension layer at the
same broad integration boundary, but they have different causal roles:

- structured events, metrics, belief snapshots, logs, dashboard snapshots,
  manifests, and validation observe or serialize simulation state;
- plugins receive an immutable snapshot through the supported API, then may
  request validated commands that causally change population or resources.

Do not describe the plugin system as observational.

## 2. Why it exists

The observation pipeline provides machine-readable run records, human-readable
diagnostics, and enough cross-file integrity information to detect many forms
of incomplete or inconsistent evidence. The plugin layer provides a narrow
extension API for custom interventions without editing core modules.

The implementation proves these roles. Any broader intent—such as treating
plugins as trusted scientific treatments—would require a separately frozen
plugin and provenance policy.

## 3. Key terminology

- **Typed event:** immutable in-memory `SimulationEvent` with a registered
  `event_type`.
- **Narrative event:** human-readable text in the legacy event list.
- **Observation journal:** exact ordered per-tick sequence drained at the
  end-of-tick boundary.
- **Journal token:** opaque one-use capability for promoting an appended legacy
  message to a typed event exactly once.
- **Required artifact:** structured output whose failure affects run validity.
- **Diagnostic output:** optional display, narrative, dashboard, or exploratory
  record that is not sufficient evidence.
- **Simulation bridge:** detached immutable plugin view of selected live state.
- **Plugin command:** supported request for a validated state mutation.

## 4. Current status

- Structured event journal and required CSV writers: **Stable and verified**.
- Streaming artifact validation: **Stable and verified** as engineering
  infrastructure.
- Text logging/dashboard/RA/mythology observers: **Implemented but
  experimental**.
- Belief tracking and LLM mythology: **Disabled by default**.
- Plugin system: **Implemented but experimental** and causally active when
  plugins are loaded.
- V2 plugin inventory/provenance policy: **Planned, not implemented**.

## 5. State owned

| Owner | State |
| --- | --- |
| `StructuredEventLog` | Narrative list, typed event list, active per-tick journal, token owner/generation/sequence state |
| `MetricsLogger` | Required file handles, buffered event count, cumulative event counters, summary aggregates, writer-health accounting, timing and memory diagnostics |
| Dashboard bridge | Module-global bounded reputation-history deque and last JSON snapshot |
| `RATracker` | Open exploratory composition, annexation, and follow-up writers plus pending follow-up state |
| Mythology module | Chronicles, faction myths, epitaphs, cadence state, and optional external client settings |
| Plugin registry | Instantiated subclasses loaded from project-root `plugins/*.py` |

Observer state is not authoritative simulation state. Plugin commands mutate
authoritative world/population state through simulator helpers.

## 6. Inputs

Observers read the current tick, population, factions, formal wars, treaties,
legacy trust values, resources/currency, generations, diplomacy reputation,
world dimensions/biomes, event journal, beliefs, configuration, termination,
and writer state.

The plugin bridge snapshots:

- tick and population/cap;
- active faction names, member display names, beliefs, territory, reserves,
  technology, and settlement state;
- the complete world tile mapping with nested resource mappings detached;
- biome caps and habitable coordinates;
- last 20 narrative events.

## 7. Processing sequence

### Event and observation path

1. Simulation layers emit typed events or append narrative messages.
2. `StructuredEventLog` journals them in generation order.
3. Typed emitters carry structured fields; legacy text may be promoted once or
   left for compatibility regex classification.
4. After all tick mutations, the simulator drains the journal.
5. Structured events are written, followed by one metrics row and any required
   100-tick belief snapshot.
6. The tick becomes `last_completed_tick` only after observation.
7. Required finalization writes the summary, flushes/closes writers, checks
   writer health, computes the state hash, and publishes the run manifest.

### Plugin path

1. Startup scans sorted project-root `plugins/*.py`, excluding `__init__.py`.
2. Each file is imported as Python; concrete `ThalrenPlugin` subclasses are
   instantiated and receive `on_load()`.
3. Every tick with loaded plugins, the simulator constructs one immutable
   bridge snapshot of population, factions, world, caps, and recent events.
4. For each plugin whose clamped interval divides the tick, `on_trigger()` runs.
5. If true, `execute()` returns commands.
6. Only exact built-in `SpawnInhabitants` and `AdjustResource` command types
   are accepted; subclass-defined command types are ignored.
7. Valid commands mutate authoritative state synchronously.
8. Plugin or command exceptions are logged and processing continues.

The plugin layer runs after scheduled world events and before era shift,
housekeeping, anti-stagnation, emergent social/coalition/language maintenance,
and end-of-tick observation.

The checked-in `plugins/example_plugin.py` is executable default behavior, not
an inert template, because startup discovers it automatically:

- `EmergencyResettlement` is evaluated every 20 ticks. When population is
  below 8, it requests six new inhabitants on the habitable tile nearest the
  grid center.
- `ForestBloom` is evaluated every 100 ticks. At tick 100 or later, when at
  least two formal factions are active, it requests a 12-unit food increase on
  every forest tile, capped by the biome resource maximum.

Renaming the file so it no longer ends in `.py` or removing the plugin base
class would change behavior and provenance; neither action is an ordinary run
configuration control.

## 8. Outputs

Required outputs are metrics, structured events, belief snapshots, one run
summary, and the run manifest. Optional outputs include full text logs,
dashboard JSON, era/manual chronicles, generated mythology history, and RA
tracker CSVs. See the [Artifact catalog](../data/artifact-catalog.md).

Plugin commands produce state changes and narrative `[PLUGIN EVENT]` messages.
There is no registered `plugin_event` structured type. Plugin effects may be
visible only indirectly through later metrics, state hash, or narrative text.

## 9. Lifecycle position

| Stage | Activity |
| --- | --- |
| Initialization | Metrics writers open; event log begins; optional trackers initialize; plugins import and load |
| During tick layers | Producers journal events; optional mythology may add narratives |
| After scheduled world event | Plugin layer snapshots state and applies commands |
| Every 25 ticks in full mode | Dashboard snapshot is atomically replaced |
| End of tick | Journal drain, event rows, metrics row, periodic beliefs, completed-tick publication |
| Finalization | Required summary/writer close/hash/manifest, then optional reports/narratives |
| Reset | Most logger/plugin/mythology runtime state is cleared or unloaded; dashboard history has a caveat below |

## 10. Connections to other systems

| Connected system | Direction | Data exchanged | Timing | Effect |
| --- | --- | --- | --- | --- |
| All simulation layers | layers → event journal | Typed events and narrative text | During layer execution | Observational record |
| World/population/factions | state → metrics/dashboard/bridge | Current authoritative values | End of tick or plugin/dashboard cadence | Metrics/dashboard observe; plugins can later mutate via commands |
| Termination/finalization | simulator → manifest | Status, ticks, writer health, hash | End of run | Evidence sealing |
| Artifact validator | artifacts → report | Schemas, rows, checksums, cross-file values | On demand | Diagnostic classification; no simulation mutation |
| Dashboard process | JSON → UI | Latest compact snapshot | Polling | Diagnostic display only |
| Plugins | bridge → plugin; commands → simulator | Detached state snapshot and validated requests | Plugin layer | Causal population/resource mutation |
| Language/coalitions | runtime → state hash/on-demand summaries | Bounded runtime state | Hash/final inspection | No dedicated event or metrics schema |

## 11. Configuration

| Field/control | Type/default | Effect and validation | Status |
| --- | --- | --- | --- |
| `--log-mode` | enum, default `full` | `full`, `summary`, `metrics_only`, `off`; required structured output is always enabled | Active |
| Event flush interval | positive integer, default `1000` rows | Flushes buffered structured events; constructor rejects values below 1 | Internal active control |
| Belief snapshot interval | fixed `100` ticks | Sealed in artifact policy and checked by validator | Active contract |
| Dashboard interval | fixed `25` ticks | Full mode only | Experimental diagnostic |
| `--enable-belief-tracking` | Boolean flag, default false | Enables RA tracker files | Disabled by default |
| `MYTHOLOGY_ENABLED` | Boolean constant, default false | Enables external/generated mythology behavior | Disabled by default |
| `PLUGINS_DIR` | project-relative directory, current `plugins` convention | All matching Python files are scanned automatically | Experimental causal extension |

There is no CLI flag that disables all discovered plugins, and current run
provenance does not inventory plugin files.

## 12. Events

The active event schema contains war, faction, treaty, technology, settlement,
birth/death, era, stagnation, raid, and world-event types. Exact fields and
type semantics are in [Events and metrics reference](../reference/events-and-metrics.md).

`faction_dissolved` is allowed by the schema, but no current production emitter
was found. Plugin narratives do not become typed events because no plugin event
type or matching compatibility classification exists.

## 13. Metrics

Metrics are one end-of-tick row per completed tick. They include population,
formal factions/wars/treaties, cumulative structured-event counts, wealth
Gini, legacy trust mean, food, technologies, generations, faction sizes,
reputation, grid size, and season.

The metrics writer performs a population-wide wealth sort for Gini and
materializes legacy trust values. Metrics are observational but not free of
runtime/memory cost. They contain no dedicated social-memory, informal
coalition, language, or dialect fields.

## 14. Determinism and RNG

The event journal, metrics writer, dashboard serializer, and validator do not
intentionally draw simulation RNG. They should not alter causal state.

Plugins are different:

- imported plugin code can call any Python RNG or external service;
- the built-in `SpawnInhabitants` command uses deterministic traveler naming
  and nearest-tile selection and consumes no simulation RNG;
- imported plugin code may consume RNG, and any spawned/adjusted state can
  change later state-dependent draw paths;
- plugin order and code therefore affect state and may affect future RNG order;
- plugin files are not currently included in canonical state-hash
  configuration or manifest provenance.

Mythology may call an external model/service and creates nondeterministic
narrative output. Optional narratives are computed after the required state
hash where finalization calls them.

## 15. Failure and edge cases

- Journal tokens reject stale, foreign, wrong-tick/text/type, and reused
  promotions.
- Beginning a new observation tick while a prior journal is undrained fails.
- Required write/flush/close/finalization failures enter writer health and make
  strict evidence invalid; a recovered event flush is accounted separately.
- Zero events are allowed only by explicit policy.
- Failed partial-tick events can be preserved but invalidate strict evidence if
  beyond `final_tick`.
- Legacy narrative classification may fail to recognize a message; typed
  emission is authoritative where available.
- Optional dashboard/report/narrative failures do not repair or replace
  required evidence.
- Plugin imports, constructors, hooks, triggers, execution, and commands can
  fail; ordinary exceptions are reported and the simulation continues.
- A spawn request is clamped to 1–20 and population cap; invalid/uninhabitable
  locations fall back to the nearest habitable tile when one exists.
- Resource commands accept food, wood, ore, stone, or water and clamp each
  affected tile to `[0, biome maximum]`; food/water changes recompute
  habitability.

## 16. Tests and validation

`tests/test_events.py` proves journal ordering, exact-once promotion, token
ownership/generation, pruning isolation, typed fields, buffering, and recovered
flush accounting. `tests/test_artifact_validation.py` proves deep schemas,
cross-file constraints, path containment, bounded diagnostics, and streaming
behavior. `tests/test_log_modes.py` proves required structured outputs and
state-hash equivalence across modes.

`tests/test_plugin_security.py` proves bridge immutability/staleness and exact
command-type rejection. It does **not** prove process sandboxing or safety of
untrusted imported Python. There is no focused current test for dashboard
history reset/content, RA artifacts, mythology service behavior, plugin
inventory provenance, or every compatibility regex.

## 17. Worked example

Suppose a formal treaty is committed at tick 50:

1. The producer emits `treaty_signed` with actor, target, detail, and narrative.
2. The structured journal stores one typed record in generation order.
3. At the observation boundary, the event writer writes one schema-1 row.
4. Its cumulative treaty-formed counter increases once.
5. The tick-50 metrics row observes the current active treaty collection.
6. Final summary counts and strict validation cross-check the event stream.

By contrast, if `ForestBloom` fires at tick 100, it directly increases food on
all forest tiles through `AdjustResource`. The event log receives narrative
text, but no typed plugin row is written. Later metrics/state hash may reflect
the resource consequence.

## 18. Current limitations

- The beliefs `inhabitant_id` column stores display names.
- Dashboard `max_gen` parses Roman-numeral name suffixes rather than reading
  authoritative `generation`.
- Dashboard reputation history is module-global and is not visibly cleared by
  `reset_runtime_state()`, so repeated in-process runs can inherit diagnostic
  history.
- Equal-size dashboard faction ties inherit source insertion order.
- Dashboard, RA, narratives, and plugin inventory are not required manifest
  artifacts.
- The manifest's full-mode optional-output policy labels `manual_chronicle` as
  written based on log mode alone, although mythology-enabled finalization uses
  generated mythology output instead; treat that list as configured policy,
  not proof that every optional file exists.
- A complete world snapshot is built every tick whenever any plugin is loaded,
  even when no plugin interval is due.
- Plugin code is arbitrary process-level Python. The immutable bridge and
  command validation are an API discipline, not a security sandbox.
- Current provenance does not seal plugins despite their causal effects.
- There is no typed plugin event.
- “Off” log mode still writes required structured artifacts.

## 19. Future extensions

The active V2 plan requires a plugin policy/inventory and environment
fingerprint before research execution. Those are **Planned, not implemented**.
No plugin-based treatment should be treated as a registered V2 factor under the
current runner.

## 20. Implementation evidence

- Events: [`src/thalren_vale/events.py`](../../../src/thalren_vale/events.py)
- Metrics: [`src/thalren_vale/metrics.py`](../../../src/thalren_vale/metrics.py)
- Lifecycle and plugins: [`src/thalren_vale/sim.py`](../../../src/thalren_vale/sim.py)
- Plugin API: [`src/thalren_vale/plugin_api.py`](../../../src/thalren_vale/plugin_api.py)
- Checked-in plugins: [`plugins/example_plugin.py`](../../../plugins/example_plugin.py)
- Dashboard: [`src/thalren_vale/dashboard_bridge.py`](../../../src/thalren_vale/dashboard_bridge.py)
- Optional observers: [`src/thalren_vale/ra_tracker.py`](../../../src/thalren_vale/ra_tracker.py),
  [`src/thalren_vale/mythology.py`](../../../src/thalren_vale/mythology.py)
- Tests: [`tests/test_events.py`](../../../tests/test_events.py),
  [`tests/test_plugin_security.py`](../../../tests/test_plugin_security.py),
  [`tests/test_log_modes.py`](../../../tests/test_log_modes.py),
  [`tests/test_artifact_validation.py`](../../../tests/test_artifact_validation.py)
- Drafting verification: current source and tests inspected; no plugin,
  simulation, experiment, benchmark, or historical artifact scan was run.
