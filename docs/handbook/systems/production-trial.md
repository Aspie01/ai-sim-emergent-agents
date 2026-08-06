# Production Trial

## 1. Status and the deadlock it breaks

Production Trial v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

A production form earns confidence when it is spoken successfully, and it is
spoken only when it already leads its meaning on confidence. That is a
deadlock, and it is why a form could be acquired from another group, promoted
into production, and still never uttered.

The project's own counter recorded it. With
[Language Contact v1](language-contact.md) enabled, borrowing promotion fired
14 times in a measured scenario while `borrowed_production_use_count` stayed
at **0**: forms were being borrowed and never used.

Production Trial breaks the deadlock by occasionally uttering the runner-up.

## 2. The mechanism

On roughly one production in `production_trial_interval`, a speaker emits its
**second**-ranked usable form for that meaning instead of its best. Everything
else about communication is unchanged: the receiver interprets normally, and
success or failure updates both parties by the ordinary rules.

Trials require a genuine runner-up. A meaning with one usable form is never
trialed, and a form below `MIN_USABLE_CONFIDENCE` is not a candidate.

This is variation, not replacement. The leading form still dominates
production; the runner-up simply gets occasional airtime.

## 3. Why this is self-correcting

A trial is not a free gift to the challenger. Trialing a borrowed form on
someone who does not know it **fails**, and the speaker's confidence in that
form drops. Trialing it on someone who does know it succeeds, and the form
earns the full use-reinforcement it could never otherwise obtain.

So trials propagate a form exactly in the population where it already works,
and suppress it where it does not. No rule says "prefer foreign words"; the
outcome falls out of ordinary comprehension.

## 4. Determinism

Trial occasions are derived from a dedicated domain:

```text
thalren-vale:production-trial-v1|seed=<run seed>|speaker_id=<id>|meaning=<name>|tick=<t>
```

No RNG is consumed, so enabling trials cannot perturb any other random stream.
Including the speaker and meaning in the record keeps speakers from trialing in
lockstep, which is asserted by test rather than assumed.

## 5. Measured effect

Two groups evolve language in isolation for 160 ticks, then merge for 900,
with rotating resource roles so every inhabitant both gives and receives each
type. Contact is enabled in both columns; only trials vary.

| Measurement | Trials off | Trials on |
| --- | --- | --- |
| `borrowed_production_use_count` | 0 | **245** |
| Foreign forms selected as dominant | 0 | 6 |
| Peak foreign production confidence | 0.55 | **1.00** |
| Cross-group lexicon overlap | 0.00 | **0.50** |

Half the meanings converge across the two groups. Peak confidence reaches the
ceiling because a spoken form earns full reinforcement, which passive hearing
alone never supplied.

These are one scenario at one seed. The properties asserted by the tests are
structural — that the runner-up is what gets trialed, that occasions are
deterministic, that the leader still dominates — not these numbers.

## 6. Rotating roles matter, and why

The same scenario with **fixed** resource roles shows no effect at all,
because an inhabitant only produces the meaning for the resource it gives and
only hears the meaning for what it receives. Borrowed forms are then always
for meanings that inhabitant never speaks, so no runner-up exists at
production time. Across 2,874 production moments in that setup, every single
one had exactly one usable candidate.

That is a property of the scenario, not of the mechanism, and it is recorded
here because it is easy to conclude the feature is broken when it is simply
never reachable. See
[the characterization note](../experiments/language-speciation-characterization.md).

## 7. Configuration

| Control | Default |
| --- | --- |
| `production_trial_enabled` | `False` |
| `production_trial_interval` | `8` |

The interval must be at least 2. An interval of 1 would trial every utterance,
which is substitution rather than variation.

Trials require language evolution. Requesting them without it normalizes the
gate to false and emits a dependency notice.

## 8. Hashing and disabled-state behaviour

This family owns no runtime state: each trial occasion is derived per
utterance from a seed domain, so there is nothing to hold pristine. Its
configuration keys leave the behavioural payload while disabled, and a test
asserts the no-state claim rather than accepting it, so a future version that
grows state cannot silently skip the disabled-state guard.

## 9. Causal isolation and non-goals

Trials change which known form a speaker emits. They cannot change the already
committed material transfer or any inventory, currency, coalition, faction,
combat, reproduction, health, survival, movement, or population state.

Production Trial v1 does **not** add invention, forms the speaker does not
already know, third-ranked or lower alternatives, prestige, imitation of
specific speakers, or research conclusions.

## 10. Known limitations

- Only the runner-up is trialed. A third-ranked form can rise only by first
  becoming the runner-up.
- The interval is uniform across speakers and meanings. There is no notion of
  a speaker being more or less experimental.
- Measured convergence comes from one scenario; populations that rarely
  achieve a second usable form per meaning will see no effect.
- No trial event, metrics column, artifact schema, or approved estimand
  exists. The family is vetoed from V2 readiness.

## 11. Implementation evidence

- `src/thalren_vale/language.py` — `_select_trial_production`, both
  communication paths, and the contact delegation
- `src/thalren_vale/config.py` — controls and dependency normalization
- `src/thalren_vale/economy.py` — owner threading
- `src/thalren_vale/sim.py` — CLI, notices, economy wiring
- `src/thalren_vale/reproducibility.py` — behavioural-payload exclusion
- `src/thalren_vale/artifact_validation.py` — manifest validation, readiness
  veto
- `run_experiments.py` — option-family containment
- `tests/test_production_trial.py` — 41 tests, mutation-verified
