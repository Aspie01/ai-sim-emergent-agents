# Language Coevolution

## 1. Status and the isolation break

Language Coevolution v1 is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

Every earlier language milestone was **causally isolated**: language read the
simulation but never wrote back to it. Those pages state the non-goal plainly,
and it held for six milestones.

This is the first milestone that breaks that isolation, and it does so in
exactly one place. When language coevolution is effective, the outcome of a
committed-transfer utterance adjusts the two participants' directed
relationship ties, and those ties already drive partner choice. The implemented
causal chain is:

```text
committed transfer
-> utterance understood or not
-> both directed ties gain or lose intelligibility
-> relationship_preference_score shifts
-> partner bias picks differently next tick
-> different partners, different vocabulary exposure
```

That last arrow is what makes it coevolution rather than instrumentation:
language changes who talks, and who talks changes language.

Nothing else feeds back. Coalitions, factions, combat, diplomacy, religion,
reproduction, and movement remain completely isolated from language.

## 2. Grounding: no new information channel

The natural objection is that a speaker cannot know whether it was understood,
so feeding comprehension back to the speaker would invent information.

It does not, because the simulation already models exactly that. Since Language
v1, the sender's production association has been reinforced on `SUCCESS` and
weakened otherwise:

```python
proposed_sender.production[production_key] = _selected_use(
    selected_production,
    succeeded=result is CommunicationResult.SUCCESS,
    confidence_delta=(
        reinforcement if result is CommunicationResult.SUCCESS
        else -base_reinforcement / 2.0
    ),
)
```

The sender is therefore already treated as knowing the outcome. Coevolution
reads the same finalized result and adds no channel that was not already there.

This also decides the direction question. The **giver** is both the speaker and
the agent whose outgoing preferences drive `_relationship_biased_barter`. If
only the receiver's tie changed, the loop would never close.

## 3. Symmetric update

Both directed ties are updated by the same amount:

| Outcome | Effect on both ties |
| --- | --- |
| `SUCCESS` | `+ intelligibility_reward` |
| `MISUNDERSTANDING` | `- intelligibility_penalty` |
| `UNKNOWN_SIGNAL` | `- intelligibility_penalty` |
| `NO_SIGNAL` | none; counted as skipped |

`NO_SIGNAL` means nothing was said. Silence is not evidence of failure, so it
must not erode a tie; it is recorded as a skipped outcome instead.

The update is symmetric because intelligibility is a property of the pair and
neither participant is modeled as having better evidence than the other. An
asymmetric weighting would need a justification the simulation does not supply.

## 4. Bounds

`intelligibility` is one float per directed tie, clamped to `[-1.0, 1.0]` and
quantized like every other relationship field. Both rates are validated to
`(0.0, MAXIMUM_INTELLIGIBILITY_RATE]`, so a single utterance can move a tie by
at most a fixed bounded step and the feedback cannot run away.

## 5. Why the preference term needs no gate

`relationship_preference_score` gains one term:

```python
+ INTELLIGIBILITY_PREFERENCE_WEIGHT * record.intelligibility
```

This is deliberately **not** gated on the coevolution flag. While coevolution
is disabled, `intelligibility` is provably `0.0`, so the term contributes
exactly zero and every pre-coevolution score is bit-identical. The
disabled-state pristine guard proves that precondition rather than assuming
it: it scans every directed tie across the living and retained-dead cohorts and
fails closed on any nonzero value.

## 6. Dual dependency

Coevolution requires language evolution **and** social partner bias. Partner
bias itself already implies social memory.

The partner-bias requirement is not incidental. Intelligibility only reaches a
decision through `_relationship_biased_barter`; with partner bias off the
feature would still write to relationships while changing nothing, which is a
one-way write dressed up as a loop. Requesting it without either dependency
normalizes the gate to false and emits that dependency's own notice.

The requirement is enforced at configuration normalization, the language
runtime gate, and the canonical hash builder.

## 7. Runtime counters

`LanguageCoevolutionRuntimeState` is fixed size and holds the frozen rates plus:

```text
intelligibility_update_count == reinforcing_update_count
                                + eroding_update_count
skipped_outcome_count counts outcomes that carried no evidence
```

Counter updates use copy-validate-commit, so a partition violation cannot leave
the runtime in a state the validator would reject.

## 8. Transaction boundary

The feedback is applied **after** `communicate()` has committed. That ordering
is required — the outcome does not exist until then — and it means coevolution
observes a finalized result and never changes it.

Both mutations are total once their inputs validate: a clamped float add and an
integer increment. Inputs are therefore validated before either runs, so there
is no partially-applied state to roll back.

## 9. On-demand summary

`language_coevolution_summary` consumes the population iterable exactly once
with work bounded by the social tie cap, mutates nothing, and consumes no RNG.
It reports population, directed ties, intelligible / unintelligible / neutral
tie counts, and carriers. Counts rather than a convergence ratio, so the reader
decides what counts as mutual intelligibility. Engineering observability, not
an approved research endpoint.

## 10. Configuration and containment

| Control | Default |
| --- | --- |
| `language_coevolution_enabled` | `False` |
| `intelligibility_reward` | `0.06` |
| `intelligibility_penalty` | `0.04` |

Reward exceeds penalty by default, so a pair that mostly understands each other
drifts together faster than an occasional failure pulls them apart. That is a
tuning choice, not a claim about language.

The experiment runner rejects the entire option family — exact spellings,
`=`-forms, and every unambiguous prefix — at both containment sites, before any
output root is created.

## 11. Hashing, reset, and pristine state

When coevolution is effective, each directed tie's `intelligibility` and the
coevolution runtime record enter the canonical hash. Both are gated on the
effective flag, so every pinned pre-coevolution hash keeps its exact payload.

When disabled, the guard requires every tie to be zero **and** the runtime to
be pristine.

## 12. Causal isolation and non-goals

Coevolution changes directed relationship ties and, through them, partner
choice. It cannot change the already committed material transfer or any
inventory, currency, coalition, faction, combat, reproduction, health,
survival, movement, or population state.

Language Coevolution v1 does **not** add language-driven coalition formation or
lifecycle, faction languages, official languages, leaders, institutions,
diplomacy through language, prestige, standardization, or research
conclusions.

## 13. Known limitations

- Divergence is reachable but not guaranteed; a population may simply converge.
  The summary reports counts, never a verdict.
- The update is symmetric. A model where the receiver has stronger evidence
  than the sender is defensible but would need grounding this milestone does
  not have.
- Feedback applies only to committed-transfer communication, so populations
  that rarely trade barely coevolve.
- `trust` and `familiarity` are untouched. Intelligibility is a separate
  bounded field so its effect stays attributable.
- The summary is internal and on demand; no coevolution event, metrics column,
  artifact schema, or approved estimand exists.

## 14. Language roadmap

Implemented: Endogenous Language, Coalition Dialects, Language Contact,
Intergenerational Language, Lexical Evolution, Compositional Protolanguage,
Grammar Evolution, Language Coevolution.

Everything beyond this point is **Planned, not implemented**.

## 15. Implementation evidence

- `src/thalren_vale/social.py` — `intelligibility`, the feedback function, the
  preference term
- `src/thalren_vale/language.py` — runtime, validation, counters, record,
  summary
- `src/thalren_vale/config.py` — controls, dual-dependency normalization
- `src/thalren_vale/economy.py` — the applier at both communication sites
- `src/thalren_vale/reproducibility.py` — hash config, payload, pristine guard
- `src/thalren_vale/artifact_validation.py` — manifest validation
- `run_experiments.py` — option-family containment
- `tests/test_language_coevolution.py` — 83 tests, mutation-verified
