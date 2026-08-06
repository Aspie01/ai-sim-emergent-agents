# Coalition Intelligibility

## 1. Status and the second isolation break

Language Coevolution v2 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

[Language Coevolution v1](language-coevolution.md) broke causal isolation once,
feeding mutual intelligibility into directed relationship ties. This breaks it
a second time, and differently: v1 wrote into a layer social memory already
owned, whereas this changes **which coalitions can exist**.

When gating is effective, a reciprocal tie carries a coalition edge only if
both directions clear an intelligibility threshold. Agents who cannot
understand each other do not coalesce.

## 2. One condition, two behaviours

The entire mechanism is one added condition in `_records_qualify`. A tie must
still clear trust, familiarity, and grievance; it must now also clear
intelligibility in **both** directions.

That single change gives formation and dissolution together. A coalition whose
members lose mutual intelligibility stops qualifying and unwinds through the
existing persistence machinery — there is no separate teardown path, which is
what keeps the change small enough to reason about.

Gating only ever narrows. It cannot admit a tie the base thresholds reject.

## 3. Grounding

No new information is introduced. `intelligibility` is written by coevolution
v1 from real communication outcomes; this reads the same field. No new event,
no new channel, no new RNG.

The threshold is strictly positive by configuration. A pair that has never
communicated sits at exactly `0.0`, and silence must not count as
understanding — an untested pair cannot coalesce on the strength of never
having failed.

## 4. The loop, and why it stays deterministic

Coalitions already influence language through dialect multipliers. Gating
coalitions on intelligibility closes that into a two-way loop between layers,
which is the kind of structure that quietly breaks determinism. It does not
here, because the two halves run at different points in the tick:

```text
tick t   economy      communication updates intelligibility
tick t   maintenance  coalitions recompute from that intelligibility
tick t+1 economy      dialects read those coalitions, altering learning rates
```

The lag is one tick and the order within a tick is strictly sequential, so
there is no within-tick circularity to resolve.

## 5. What this demonstrates

Measured on a synthetic twelve-agent scenario, holding everything else fixed
and varying only the threshold:

| Threshold | First coalition | Active | Qualifying edges |
| --- | --- | --- | --- |
| gating off | tick 113 | 2 | 25 |
| `0.10` | tick 113 | 2 | 15 |
| `0.50` | tick 182 | 1 | 11 |
| `0.95` | never | 0 | 6 |

Raising the bar delays coalescence and then prevents it. **Coalition formation
gated on having invented a shared language** is the claim this milestone
supports, and the delay from 113 to 182 is what makes it quantitative rather
than rhetorical.

The edge count falls monotonically, which is the property actually asserted by
the tests; the specific tick numbers are one scenario, not a general result.

## 6. Configuration

| Control | Default |
| --- | --- |
| `coalition_intelligibility_enabled` | `False` |
| `coalition_intelligibility_threshold` | `0.50` |

The default threshold is deliberately not the smallest workable value. At
`0.10` the gate prunes roughly forty percent of qualifying edges yet coalitions
still form on the same tick, so a user enabling the feature would see nothing
happen and reasonably conclude it was broken. `0.50` is the value at which the
mechanism is visible. It was measured on one synthetic scenario and should be
treated as a starting point rather than a tuned constant.

Gating has a **dual dependency**: coalition emergence and language coevolution.
Coevolution in turn already requires language evolution and social partner
bias. Each dependency carries its own notice, so a manifest records exactly
which requirement was unmet.

Without coevolution every tie would sit at `0.0` and a positive threshold would
silently forbid every coalition. The dependency prevents that from looking like
an emergent result.

## 7. Hashing and disabled-state behaviour

This family owns no runtime state. It reads the intelligibility coevolution
writes and acts on the coalition graph, so there is nothing to hold pristine;
its configuration keys simply leave the behavioural payload while disabled. A
test asserts that the no-state claim is true rather than assumed, so a future
version that grows state cannot silently skip the disabled-state guard.

Disabled runs are unaffected twice over: `intelligibility` is provably `0.0`
while coevolution is off, and gating has its own flag on top of that.

## 8. Causal isolation and non-goals

Gating changes which reciprocal ties carry coalition edges, and through that
which coalitions form and persist. It cannot change committed material
transfers, inventories, currency, factions, combat, reproduction, health,
survival, movement, or population state.

Language Coevolution v2 does **not** add coalition-owned resources, leaders,
institutions, official languages, faction languages, diplomacy through
language, prestige, or standardization. It does not make coalitions
language-defined: trust, familiarity, and grievance still gate every edge, and
intelligibility only narrows further.

## 9. Known limitations

- The measured numbers come from one synthetic scenario with a stable trade
  gradient. Real populations may never reach the threshold at all.
- Trust, familiarity, and intelligibility all rise from the same committed
  transfers, so the constraints are correlated. At low thresholds the gate is
  largely redundant with the ones already present — which is exactly why the
  default is not low.
- Dissolution is inherited from the persistence machinery rather than modelled
  directly, so a coalition losing intelligibility decays on the ordinary
  schedule instead of reacting sharply.
- No coalition-intelligibility event, metrics column, artifact schema, or
  approved estimand exists. The feature is vetoed from V2 readiness.

## 10. Implementation evidence

- `src/thalren_vale/coalitions.py` — `_records_qualify`, graph builder
- `src/thalren_vale/config.py` — controls, dual-dependency normalization
- `src/thalren_vale/sim.py` — threshold supplied during maintenance
- `src/thalren_vale/reproducibility.py` — behavioural-payload exclusion
- `src/thalren_vale/artifact_validation.py` — manifest validation, readiness
  veto
- `run_experiments.py` — option-family containment
- `tests/test_coalition_intelligibility.py` — 41 tests, mutation-verified
