# Owner clarifications

These questions cannot be answered from current executable evidence. The handbook documents present behavior without silently selecting a new design. None blocks using the handbook for the recorded revision.

## Reproduction accounting and reuse

- **Affected system:** inhabitants and population.
- **Observed implementation:** parents qualify at mutual legacy trust at least 5, hunger below 30, same tile, and positive food. Up to three births can occur per tick. Parent busy flags are cleared after each attempt, so a parent can be selected again. `make_child()` always gives ten food while each parent loses at most its current amount up to five.
- **Conflicting or missing intent:** the older README describes higher trust/food thresholds and one birth per tick; a function comment implies a parent remains unavailable for the tick.
- **Why clarification matters:** these choices materially affect population and resource dynamics.
- **Provisional wording:** the handbook states the exact current executable thresholds, reuse, and low-food creation behavior as implementation limitations.

## Death checkpoints and medicine plague resistance

- **Affected system:** needs, survival, technology, anti-stagnation.
- **Observed implementation:** health at or below zero is removed only at explicit checkpoints; some later-layer health mutations leave a zero-health agent until the next Layer-1 body. Medicine writes `_plague_resist`, but neither plague implementation reads it.
- **Conflicting or missing intent:** README prose describes active plague resistance and more immediate biological semantics.
- **Why clarification matters:** survival timing and technology effect interpretation are causal mechanics.
- **Provisional wording:** the handbook describes checkpointed removal and says plague resistance is stored but has no implemented effect.

## Belief snapshot identity column

- **Affected system:** metrics and artifacts.
- **Observed implementation:** `BELIEFS_HEADER` calls the third field `inhabitant_id`; `MetricsLogger.record_beliefs()` writes the display name, and validation accepts a nonempty unique string.
- **Conflicting or missing intent:** it is unclear whether the producer or header is intended to change in a future schema.
- **Why clarification matters:** users could wrongly join belief rows to stable integer IDs.
- **Provisional wording:** the current field is documented as display name despite its header; no schema change is made.

## Plugin baseline and provenance policy

- **Affected system:** plugins, determinism, manifests.
- **Observed implementation:** sorted `plugins/*.py` files are automatically imported, including the checked-in example, and arbitrary plugin Python can consume RNG or external state. Manifests record no plugin policy, inventory, or hash.
- **Conflicting or missing intent:** no effective configuration says whether the checked-in example is intended as part of every repository-root baseline.
- **Why clarification matters:** plugins are causal and can invalidate reproducibility assumptions.
- **Provisional wording:** reproducibility requires a controlled plugin directory; plugins are not sandboxed or sealed provenance.

## State-hash completeness language

- **Affected system:** reproducibility and evidence.
- **Observed implementation:** the hash canonically covers a selected projection, while multiple future-affecting caches, plugin/RNG state, spatial/noise state, and later-layer stores are omitted.
- **Conflicting or missing intent:** a source docstring calls the projection behaviorally relevant, which can be read as complete future-state equivalence.
- **Why clarification matters:** a hash match must not be mistaken for a checkpoint or replay proof.
- **Provisional wording:** “canonical selected-state fingerprint,” with omissions listed explicitly.

## Legacy report labels versus executable values

- **Affected system:** economy and anti-stagnation.
- **Observed implementation:** scarcity destroys 15% of the selected resource while a report says 30%; the 50-tick peace escalation updates each unordered faction pair twice, producing +20 rather than its +10 message.
- **Conflicting or missing intent:** source behavior and displayed labels disagree.
- **Why clarification matters:** user-visible interpretation and downstream manual log analysis can be wrong.
- **Provisional wording:** the handbook uses executable 15% and +20 values and labels the prose/report text stale.

## Formal-faction and later-layer legacy quirks

- **Affected system:** formal factions, settlements, combat, technology, diplomacy, religion.
- **Observed implementation:** examples include unreachable normal settlement reclaim after unregistering; unused Masonry defense and Medicine plague-resistance helpers; Steel not preventing exhaustion; inactive council-tension feedback; religion markers not declaring formal wars; and several name-based registries that do not follow faction renames.
- **Conflicting or missing intent:** older README claims describe intended effects that current call paths do not implement.
- **Why clarification matters:** these are causal simulation semantics, but changing them is outside a documentation task.
- **Provisional wording:** each system page records current behavior and test gaps, without presenting the stale effect as active.
