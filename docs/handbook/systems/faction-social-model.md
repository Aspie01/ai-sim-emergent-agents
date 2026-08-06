# Faction Social Model

## 1. Status and the seam it addresses

Faction Relationship Trust is:

- **Implemented but experimental**;
- **Disabled by default**;
- **Engineering-only**.

The simulation carries two social models, and until this milestone the faction
layer could only read one of them.

| | Legacy `trust` | `relationships` |
| --- | --- | --- |
| Shape | name-keyed integer counter | id-keyed `Relationship` records |
| Written | on every committed transfer, unconditionally | only when social memory is effective |
| Range | unbounded, monotonically rising | bounded to `[-1, 1]`, decays |
| Read by | factions | social memory, coalitions, coevolution |

Everything built since social memory — coalitions, dialects, contact,
coevolution, intelligibility gating — reads `relationships`. Factions read
`trust`. That seam is why a language-to-faction channel has no clean route.

This milestone lets the faction layer read either, selected by an explicit
flag.

## 2. Why it cannot simply be switched

`relationships` is populated only when social memory is enabled, and social
memory is **disabled by default**. Measured on a default 120-tick run: 72
legacy trust entries and **zero** relationship records.

Reading `relationships` unconditionally would therefore mean no faction ever
forms in a default run. The flag is not caution about scope; it is what keeps
the baseline simulation working.

## 3. The models disagree, and that is the point

They measure different things, so swapping one for the other changes which
ties qualify — in both directions:

| Legacy count | Relationship trust | Legacy verdict | Relationship verdict |
| --- | --- | --- | --- |
| 9 | 0.10 | qualifies | rejected |
| 2 | 0.90 | rejected | qualifies |
| 9 | 0.90 | qualifies | qualifies |
| 2 | 0.10 | rejected | rejected |

Many shallow interactions are not the same as a trusted tie, and a strong tie
does not require many interactions. Selecting the relationship model is a
change in what a faction *means*, not a refactor, which is why it is gated and
why enabling it moves the state hash.

## 4. The threshold equivalence

Legacy faction trust requires an interaction count strictly above `5`. Aid
adds `+0.08` of relationship trust per interaction, so the nearest equivalent
is `0.40`, which is the default.

That number comes from arithmetic, not tuning. It makes the two models roughly
comparable at the boundary; it does not make them behave alike, as the table
above shows.

## 5. What was changed

One helper, `_directed_trust_qualifies`, encapsulates the choice. The three
faction read sites — mutual trust during formation, the rejection check, and
the join check — all route through it. No faction logic beyond trust lookup
was touched: shared core beliefs, blocked-belief pairs, and group size rules
are unchanged.

Both faction entry points accept the selector. Threading only one of them left
the other raising `NameError` at runtime, which the suite caught immediately;
a test now asserts that both accept it.

## 6. Configuration

| Control | Default |
| --- | --- |
| `faction_relationship_trust_enabled` | `False` |
| `faction_relationship_trust_threshold` | `0.40` |

The feature requires social memory. Requesting it without social memory
normalizes the gate to false, emits a dependency notice, and leaves factions on
the legacy model.

## 7. Hashing and disabled-state behaviour

This family owns no runtime state — it selects which existing store is read —
so its configuration keys simply leave the behavioural payload while the
legacy model is in use. Every pinned hash is unchanged with the flag off.

With the flag on, faction membership can differ, so the state hash differs.
That is the intended consequence of changing what a faction means.

## 8. Causal isolation and non-goals

The selector changes which ties qualify for faction purposes. It does not
change how either store is written, add a language-to-faction channel, unify
the two models, or remove either one.

It specifically does **not** make language causal for factions. Relationship
records carry `intelligibility` when coevolution is effective, and faction
qualification reads only `trust`, so no language signal reaches factions
through this path.

## 9. Known limitations

- The two models still coexist. This selects between them rather than
  reconciling them, and the legacy store keeps being written either way.
- `civilization.py` is a standalone legacy script that calls the faction
  entry points without a selector, so it always uses the legacy model. It is
  not imported by the simulation.
- The threshold equivalence is arithmetic at the boundary only. No scenario
  has been run showing the two models produce comparable faction populations.
- No faction-model event, metrics column, artifact schema, or approved
  estimand exists. The family is vetoed from V2 readiness.

## 10. Implementation evidence

- `src/thalren_vale/factions.py` — `_directed_trust_qualifies`, `_mutual_trust`,
  and the three read sites
- `src/thalren_vale/config.py` — controls and the social dependency
- `src/thalren_vale/sim.py` — CLI, notices, faction-layer threading
- `src/thalren_vale/reproducibility.py` — behavioural-payload exclusion
- `src/thalren_vale/artifact_validation.py` — manifest validation, readiness
  veto
- `run_experiments.py` — option-family containment
- `tests/test_faction_social_model.py` — 39 tests, mutation-verified
