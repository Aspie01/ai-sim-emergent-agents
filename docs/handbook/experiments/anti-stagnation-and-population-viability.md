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

## 4. Why: the spawn interventions never fire

Anti-stagnation is five separate interventions, not one mechanism.

| Intervention | Cadence | Gate |
| --- | --- | --- |
| Solo-faction fragility | every 10 ticks | inhabitant alone in a faction |
| Traveler waves | every 40 ticks | `len(people) < 20` or active factions `< 3` |
| Faction-collapse prevention | every 25 ticks | factions `< 3` for 50 consecutive ticks |
| World event | every 200 ticks | — |
| Era shift | every 500 ticks | — |

Measured over the three `on` runs:

- ticks with `len(people) < 20`: **0**, in all three seeds;
- ticks with active factions `< 3`: **9 to 14**, all at the very start, before
  any faction has formed. Factions reach three by tick 10 to 15.

Traveler waves are first evaluated at tick 40, by which point factions are
well above three. Faction-collapse prevention needs a 50-tick streak below
three, and the longest streak is 14.

**Neither population-propping intervention executes at all.** They are
unreachable in the fixed simulation, not merely unnecessary.

What remains active is one mechanism that *removes* inhabitants — solo-faction
fragility, which drains 10 health every 10 ticks from anyone alone in a faction
— and two world perturbations.

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

## 6. What this does not establish

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
