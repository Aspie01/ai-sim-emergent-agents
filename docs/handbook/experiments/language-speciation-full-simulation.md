# Characterization: language in the full simulation

## 1. What this is, and what it is not

This is an **engineering characterization** of the existing language stack
running inside the complete simulation — births, deaths, migration, factions,
combat, and the anti-stagnation machinery all active. It answers the question
the previous note left open, and which that note explicitly listed as untested
in either direction.

It is **not** research evidence. Specifically it is not:

- a research result, hypothesis, estimand, or effect size;
- a claim about the simulation in general, or about language in general;
- executed under the research runner, or part of any experiment plan;
- a tuned or optimized configuration.

No experiment configuration was created and no research cell was launched. The
authorization boundary in root `AGENTS.md` is unchanged.

Read the numbers as *existence claims about these configurations*: the
behaviour described did occur under these exact settings. Nothing more.

The companion note is
[language-speciation-characterization.md](language-speciation-characterization.md),
which characterized the same stack in a synthetic two-group scenario. This note
is written to be read against it.

## 2. The scenario

The full simulation, driven through its real tick loop by `sim.run()` with no
scripted intervention and no scaffolding. Two arms:

| Arm | Effective controls |
| --- | --- |
| `base` | social memory, partner bias, language evolution, language coevolution |
| `intergen` | the above plus intergenerational language |

`base` is the closest full-simulation analogue of the previous note's control
set. `intergen` adds the one mechanism that could plausibly carry language
across the population turnover the full simulation has and the synthetic
scenario did not.

Run lengths 100, 200, 400, 700, and 1000 ticks at seed 42, plus 400-tick runs
at seeds 7, 123, and 2026. Each length is a separate process: the simulation is
deterministic, so a 400-tick run's first 100 ticks are identical to the
100-tick run, and the series is a time course rather than five unrelated runs.

**Grouping differs by necessity.** The previous scenario imposed two groups by
placing them in different grid cells. The full simulation imposes nothing, so
factions play that role — they are the durable social partition the simulation
itself produces. Measured quantities otherwise match the previous note: mean
`intelligibility` over within-group and cross-group directed ties, and lexicon
overlap as the share of shared meanings where both groups' modal dominant
production form is the same signal.

Two quantities are added, because the failure mode here is different:

- **competing forms per meaning** — distinct dominant production signals across
  the population, per meaning. `1.0` means the population agrees on one form.
- **turnover** — how many agents ever existed, and how long social groups last.

## 3. What happened

Seed 42, both arms. `n` is the tie count each mean is taken over.

| Arm | Tick | Living | Dead | Factions | Success | within (n) | across (n) | Overlap | Forms/meaning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | 100 | 149 | 120 | 48 | 4.3% | −0.047 (43) | −0.042 (1564) | 0.00 | 84.8 |
| base | 200 | 131 | 390 | 34 | 4.3% | −0.043 (74) | −0.041 (876) | 0.00 | 63.2 |
| base | 400 | 170 | 855 | 50 | 4.3% | −0.042 (68) | −0.042 (1458) | 0.00 | 77.2 |
| base | 700 | 16 | 1199 | 6 | 4.9% | −0.060 (2) | −0.045 (34) | 0.00 | 8.5 |
| base | 1000 | 33 | 1206 | 5 | 6.0% | 0.060 (4) | 0.292 (80) | 0.25 | 5.2 |
| intergen | 100 | 147 | 122 | 38 | 5.1% | −0.041 (54) | −0.041 (1458) | 0.00 | 81.0 |
| intergen | 200 | 152 | 369 | 31 | 5.5% | −0.028 (71) | −0.041 (1361) | 0.00 | 76.8 |
| intergen | 400 | 250 | 775 | 80 | 5.9% | −0.012 (92) | −0.039 (3816) | 0.00 | 116.8 |
| intergen | 700 | 14 | 1201 | 7 | 6.3% | 0.020 (2) | −0.027 (61) | 0.25 | 8.0 |
| intergen | 1000 | 29 | 1226 | 8 | 6.6% | 0.066 (14) | −0.031 (146) | 0.00 | 14.2 |

**Rows at 700 and 1000 ticks are degenerate and must not be read as
convergence.** Section 5 explains why.

In the viable window the result is flat and seed-stable. Four seeds at 400
ticks:

| Seed | Living | Dead | Factions | Success | Overlap | Forms/meaning |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | 170 | 855 | 50 | 4.3% | 0.00 | 77.2 |
| 7 | 174 | 859 | 57 | 4.7% | 0.00 | 86.2 |
| 123 | 220 | 811 | 73 | 4.9% | 0.00 | 96.0 |
| 2026 | 244 | 794 | 70 | 4.3% | 0.00 | 109.8 |

The contrast with the synthetic scenario is not marginal:

| | Synthetic scenario | Full simulation |
| --- | --- | --- |
| Within-group communication success | 94.0% | ~4.5% overall |
| Lexicon overlap between groups | 0.00, from converged group lexicons | 0.00, from no group lexicon at all |
| Competing forms per meaning | converged within groups | 77–110 |

Both report a lexicon overlap of `0.00`, and they mean opposite things. In the
synthetic scenario each group had converged on its own forms and the groups
disagreed — divergence. Here no group ever converges on anything, so there is
nothing to disagree about. All four meanings (`FOOD`, `WOOD`, `ORE`, `STONE`)
are in use, so this is not a coverage problem; roughly ninety forms compete for
each of them.

## 4. Why language does not cohere

The synthetic scenario needed 159 ticks of stable isolation before two
six-agent groups held divergent vocabularies. The full simulation does not hold
a group together for anything like that long.

Measured over 400 ticks at seed 42:

| Quantity | Value |
| --- | --- |
| Agents that ever existed | 1025 |
| Died / still living | 855 / 170 |
| Generations elapsed | median 13, max 32 |
| Ticks an agent spends inside a faction | median 46, mean 58.4 |
| Age of factions with living members | median 25, mean 35.9, max 170 |

The median faction with living members is **25 ticks old**, against the 159
ticks the synthetic scenario required. Group *size* is not the obstacle — the
largest faction holds 7 to 15 members and the synthetic groups held six.
Persistence is.

Learning cannot outrun this. Over the same run the population invented 854
associations, learned 3101, and lost 2055, while achieving 138 successful
interpretations. Vocabulary is being generated and destroyed far faster than it
is being shared.

**This structure is not caused by language.** A control run with every language
control disabled produces the same population shape:

| | No-language control, 400 ticks | `base` arm, 400 ticks |
| --- | --- | --- |
| Living / dead | 187 / 838 | 170 / 855 |
| Factions with living members | 57 | 50 |
| Largest faction | 8 | 7 |

Turnover and fragmentation are properties of the simulation. Language is
observing them, not producing them.

## 5. The collapse, and why late ticks are an artifact

Between ticks 400 and 700 the population collapses. Births stop entirely at
roughly tick 520 — the cumulative birth counter freezes at 1185 and never moves
again — and the population falls from 173 to 16.

Population then *rises* again, to 33 by tick 1000, while both the birth and
death counters stay frozen. Those agents are not being born. They are being
force-spawned by the anti-stagnation machinery, which introduces groups of
three carrying fixed shared beliefs.

That matters for measurement, because it manufactures precisely the small,
belief-homogeneous groups that make language look like it is converging. The
tick-1000 `base` row — overlap `0.25`, 5.2 forms per meaning — is that
artifact, not a result.

Disabling anti-stagnation makes the point unambiguous. Same seed, same
controls, 1000 ticks, `--disable-antistag`:

| Living | Dead | Factions | Overlap | Forms/meaning |
| --- | --- | --- | --- | --- |
| 4 | 1211 | 2 | **1.00** | 1.5 |

A lexicon overlap of `1.00` with four surviving agents is four agents agreeing,
not a language converging. Whether the small population arrives by collapse or
by force-spawning, every quantity here degenerates once the population is small
— note the tie counts of `n=2` and `n=4` behind the 700- and 1000-tick
intelligibility means.

**The analysis window is therefore ticks 1 to roughly 500.** Within it the
result is flat, and the flatness is the finding.

## 6. Intergenerational transmission

`intergen` is measurably different from `base` and the difference is small.
Communication success is higher at every length (5.1–5.9% against a flat 4.3%),
and mean within-faction intelligibility rises across the series (−0.041 →
−0.028 → −0.012) where `base` stays flat near −0.042.

The direction is what the mechanism predicts. The magnitude does not change the
conclusion: overlap stays `0.00` and competing forms per meaning stays high,
reaching 116.8 at 400 ticks.

This comparison is **confounded and is not offered as an effect**. The
`intergen` arm also sustains a larger population at 400 ticks (250 against
170), and population size plausibly drives both the fragmentation and the tie
counts the means are taken over. Separating transmission from population size
would need a design this characterization does not have.

## 7. What this does not establish

- Nothing about whether language *could* cohere in the full simulation under
  different parameters. Learning rates, reinforcement, forgetting interval, and
  invention were all left at defaults; only the enable gates were varied.
- Nothing about the other language milestones. Contact, lexical evolution,
  compositional protolanguage, grammar evolution, coalition dialects, coalition
  intelligibility, and production trials were all off. Production trials in
  particular are the mechanism that broke the adoption deadlock in the previous
  note, and they were not exercised here.
- Nothing about horizons beyond the collapse. Ticks past ~500 are an
  anti-stagnation regime, so the question of what a long-lived stable
  population would do is untouched — such a population did not occur.
- Nothing about the intergenerational effect as an effect, for the confound in
  section 6.
- Nothing about seeds beyond the four run at 400 ticks, or about population
  sizes and world sizes other than the defaults.
- The within/cross split is weak here. Factions are small enough that
  within-faction ties number in the tens against thousands of cross-faction
  ties, so the within-group mean rests on a thin sample even inside the viable
  window.
- No estimand, contrast, estimator, or uncertainty method is defined, so no
  quantity here is an approved research endpoint.

## 8. Reproducing it

Like the previous note, the harness is a scripted in-process probe rather than
a committed fixture, because promoting it to a fixture would imply a stability
guarantee these runs do not support.

To rebuild it: set `PYTHONHASHSEED=0`, set `sys.argv` to the flags for the arm
you want plus `--seed`, `--ticks`, and `--log-mode metrics_only`, call
`thalren_vale.sim.run()` in a fresh process, and measure the committed state
afterwards from `sim.people`, `sim.all_dead`, `sim.factions`, and
`sim.state.language`.

A fresh process per run is required. The simulation holds run-scoped state in
module globals, so reusing an interpreter lets one run's state reach the next.

Per-agent language lives at `inhabitant.language` as an `AgentLanguageState`
with `production` and `comprehension` mappings; intelligibility lives at
`inhabitant.relationships[other_id].intelligibility`. Dominant production form
is the highest-confidence production association for a meaning.

## 9. Why this note exists

The previous note characterized the language stack in a scenario built to let
language work: a fixed population, imposed groups, and resources replenished so
communication never stopped. It found interesting behaviour and said plainly
that whether the behaviour survived the full simulation was untested.

It does not survive, and the reason is not in the language stack. The full
simulation's population turns over roughly five times in 400 ticks and its
social groups last a median of 25 ticks, so the stable communication community
every language mechanism assumes does not exist long enough to form one.

Recording that is cheaper than building a ninth language mechanism on the
assumption that the eight existing ones do anything here.
