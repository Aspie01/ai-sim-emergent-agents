# Characterization: anti-stagnation and population viability

## 1. What this is, and what it is not

This is an **engineering characterization** of what the anti-stagnation
framework does once the inhabitant naming ceiling is removed. It exists because
the first attempt to answer "is anti-stagnation still needed?" was
uninterpretable: a naming bug guaranteed the simulation died without it, so
the answer was always yes for the wrong reason.

It is **not** research evidence. No experiment configuration was created and no
research cell was launched. The authorization boundary in root `AGENTS.md` is
unchanged.

## 2. The naming ceiling, and why it mattered here

`_make_traveler_name` stopped at generation suffix 9, so exactly
`len(NAMES) * 9` distinct names existed — 1215 by default. Both birth paths
build their `used` set from the living **and the dead**, so this was never a
limit on how many inhabitants could be alive at once. It was a limit on how
many a run could ever produce.

On reaching it the function returned `None`, both callers broke out of
procreation, and births stopped permanently. The population then died out.

The signature is arithmetic rather than dynamic, so it is identical on every
seed: births freeze at exactly **1185**, which is 1215 minus the 30 initial
inhabitants.

Measured at 1000 ticks with anti-stagnation disabled, before and after removing
the ceiling:

| Seed | Population before | Population after | Births before | Births after |
| --- | --- | --- | --- | --- |
| 42 | 4 | 263 | 1185 | 2507 |
| 7 | 12 | 216 | 1185 | 1749 |
| 123 | 8 | 200 | 1185 | 1747 |

**Anti-stagnation concealed this.** Its traveler waves and forced faction
spawns build their name pool from the living only, so they never exhausted, and
they kept refilling a population that could no longer reproduce. Of the eight
`_make_traveler_name` call sites, only the two birth paths pass the dead.

The fix is in `src/thalren_vale/sim.py`. Suffixes continue indefinitely; names
are still never recycled from the dead, because `trust`, `memory`, and
grievance are keyed by name and reuse would hand a dead inhabitant's social
history to a newborn.

## 3. With naming fixed: is anti-stagnation needed?

Three seeds, 700 ticks, anti-stagnation on and off. Same seeds, same
everything else.

| Seed | Arm | Final pop | Min pop | Mean pop | Births | Deaths | Factions | Max gen | Ticks extinct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | off | 201 | 30 | 187 | 1751 | 1580 | 61 | 33 | 0 |
| 7 | on | 202 | 30 | 190 | 1751 | 1603 | 52 | 32 | 0 |
| 42 | off | 255 | 30 | 203 | 1751 | 1526 | 71 | 33 | 0 |
| 42 | on | 269 | 30 | 194 | 1751 | 1512 | 86 | 34 | 0 |
| 123 | off | 215 | 30 | 185 | 1749 | 1564 | 69 | 33 | 0 |
| 123 | on | 276 | 30 | 216 | 1749 | 1511 | 90 | 34 | 0 |

**For population viability, no.** Neither arm goes extinct for a single tick,
and `min pop` is 30 in every run — the initial population — so the population
never falls below where it started.

Births are **identical between arms** at every seed. That is the clearest
single result here: at this horizon anti-stagnation does not change
reproduction at all.

## 4. Which interventions actually run

Anti-stagnation is **ten** separate interventions, not one mechanism and not
the five an earlier revision of this note listed. Six of them are nested inside
the single `t % 25 == 0` block, which is easy to read as one intervention.

| # | Intervention | Cadence | Gate |
| --- | --- | --- | --- |
| 1 | Solo-faction fragility | every 10 ticks | inhabitant alone in a faction |
| 2 | World event | every 200 ticks | — |
| 3 | Era shift | every 500 ticks | — |
| 4 | Traveler waves | every 40 ticks | `len(people) < 20` or active factions `< 3` |
| 5 | Faction-collapse prevention | every 25 ticks | factions `< 3` for 50 consecutive ticks |
| 6 | Great Migration disruption | every 150 ticks | `t > 100` and factions `< 4` |
| 7 | Stagnation-fallback disruption | every 25 ticks | 40+ ticks since any dynamic event |
| 8 | Peace escalation, 50 ticks | every 25 ticks | 50 ticks of peace |
| 9 | Peace escalation, 75 ticks | every 25 ticks | 75 ticks of peace |
| 10 | Peace escalation, 100 ticks | every 25 ticks | 100 ticks of peace |

Interventions 6 and 7 both call `disruption_event_layer`, which can trigger
CIVIL WAR, PLAGUE, GREAT MIGRATION, PROMISED LAND, or PROPHET — several of
which add or remove inhabitants. Interventions 8 to 10 write directly to
`combat.RIVALRIES`, manufacturing the tension that produces wars. Neither
group is population life support, and neither was named in the earlier list.

Counted from the full event log of one 700-tick run at seed 42, anti-stagnation
on and off:

| Intervention | On | Off |
| --- | --- | --- |
| 1 Solo-faction deaths | **54**, across 12 distinct ticks | 0 |
| 2 World events | **3** — ticks 200, 400, 600 | 0 |
| 3 Era shifts | **1** — tick 500 | 0 |
| 4 Traveler waves | 0 | 0 |
| 5 Faction-collapse spawns | 0 | 0 |
| 6-7 Disruption events | 0 | 0 |
| 8-10 Peace escalations | 0 | 0 |

**Three of the ten fire. Seven never do.**

The seven share one cause. Interventions 5 to 10 are all gated on the
simulation being quiet or shrinking — fewer than three or four factions, or 40
to 100 ticks without a dynamic event — and this simulation is neither. It
sustains 50 to 90 factions and produces hundreds of schisms per run, so
`_last_dynamic_t` is reset constantly and the peace counters never reach even
their first threshold of 50. Traveler waves need `len(people) < 20`, which
never occurs at all.

Of the three that do fire, only one touches population, and it *removes*
inhabitants rather than adding them: solo-faction fragility drains 10 health
every 10 ticks from anyone alone in a faction, killing 54 over 700 ticks. The
other two are world perturbations.

So no anti-stagnation mechanism adds a single inhabitant to a healthy run.

## 5. What the remaining interventions do change

The world perturbations are not inert. Across all three seeds:

| Quantity | off | on |
| --- | --- | --- |
| Treaties | 6, 7, 6 | 10, 10, 11 |
| Technologies | 113, 127, 103 | 95, 189, 163 |

Treaties are consistently higher with anti-stagnation on, at every seed.
Technology totals are higher on average but far more variable, and the `on`
range spans the `off` range, so seed-to-seed variation is the better
explanation there.

Wars, schisms, mergers, generations, and Gini are within seed-to-seed spread.

The intervention counts in section 4 narrow where the treaty difference can
come from. The obvious candidates would be interventions 8 to 10, which write
`combat.RIVALRIES` directly and exist precisely to manufacture conflict — but
they never fire. Nor does either disruption trigger. Whatever produces the
difference is therefore reachable through only three world events and one era
shift per 700-tick run, which is a small enough surface to test directly.
That test has not been run.

## 6. What this does not establish

- The intervention counts in section 4 come from the event log of **one** run
  at seed 42. The gating argument for why seven never fire generalizes — it
  rests on faction counts and dynamic-event frequency that hold across all
  three seeds — but the counts themselves were not repeated per seed.
- Nothing about horizons beyond 700 ticks, or about whether some slower
  stagnation appears later. The old collapse point was near tick 520, so this
  window clears it, but it is not a long-horizon result.
- Nothing about the treaty difference as an effect. Three seeds, one
  configuration, no estimator and no uncertainty method.
- Nothing about whether the remaining interventions are *desirable*. This
  measures what they do, not whether the simulation is better with them.
- Nothing about removing them. Solo-faction fragility in particular is a
  killing mechanism whose removal would change population dynamics in a
  direction this characterization did not test.
- Nothing about default population, grid size, or any control other than
  `--disable-antistag`.
- No estimand, contrast, estimator, or uncertainty method is defined, so no
  quantity here is an approved research endpoint.

## 7. Reproducing it

Set `PYTHONHASHSEED=0`, run `python -m thalren_vale --seed <n> --ticks 700
--condition <label> --log-mode metrics_only`, adding `--disable-antistag` for
the `off` arm, and read the final row of the emitted metrics CSV. The trigger
counts in section 4 come from the `population` and `faction_count` columns of
the same file.

Runs are independent processes; the simulation keeps run-scoped state in module
globals, so a fresh process per run is required.

## 8. Why this note exists

The stated goal is to move the simulation away from external scaffolding. The
first step was supposed to be removing anti-stagnation and measuring the
damage. Measuring first instead showed that the damage attributed to its
removal was a naming bug, and that with the bug fixed its two
population-propping interventions never run.

That reorders the work. Removing the scaffolding is now a smaller change than
it looked, because most of it is already unreachable — and the parts that still
do something are a killing mechanism and two world perturbations, which is a
different conversation from population life support.
