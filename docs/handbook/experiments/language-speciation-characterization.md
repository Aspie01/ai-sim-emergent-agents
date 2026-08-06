# Characterization: language divergence under isolation and contact

## 1. What this is, and what it is not

This is an **engineering characterization** of one synthetic scenario, run to
find out what the existing language stack does when its parts are combined. It
exists because the alternative was adding a fourth coevolution mechanism
without knowing whether the third one mattered.

It is **not** research evidence. Specifically it is not:

- a research result, hypothesis, estimand, or effect size;
- a claim about the simulation in general, or about language in general;
- executed under the research runner, or part of any experiment plan;
- reproducible across parameter settings — every number below comes from one
  scenario, one seed, and one population size.

No experiment configuration was created and no research cell was launched. The
authorization boundary in root `AGENTS.md` is unchanged.

The right way to read the numbers is as *existence claims about this
configuration*: the behaviour described did occur, at least once, under these
exact settings. Nothing more.

## 2. The scenario

Twelve inhabitants in two groups of six. The economy pairs traders strictly by
grid cell, so placing groups in different cells makes them separate
communication communities.

| Phase | Ticks | Arrangement |
| --- | --- | --- |
| Isolation | 1–159 | Group A in cell `(0,0)`, group B in cell `(1,0)` |
| Contact | 160–1059 | Both groups moved to cell `(0,0)` |

Every inhabitant is replenished each tick with a resource its neighbours lack,
so committed transfers — and therefore communication — continue indefinitely.

Effective controls: social memory, partner bias, coalition emergence, language
evolution, and language coevolution. Seed 42 throughout.

Coalition intelligibility gating was varied as the independent factor in every
run. Coalition dialect influence was varied only in a shorter 359-tick version
of the same scenario; the table in §3 is dialect influence **off**. In that
shorter run, enabling dialects raised end-of-run within-group intelligibility
from `0.800` to `0.833` and left every cross-group quantity unchanged, which
is consistent with dialect multipliers acting only inside a coalition.

Measured quantities:

- **within** / **across** — mean `intelligibility` over directed ties whose
  endpoints are in the same group, or in different groups;
- **lexicon overlap** — the share of base meanings where both groups' modal
  dominant production form is the same signal;
- **base-eligible cross ties** — cross-group directed records clearing trust,
  familiarity, and grievance, ignoring intelligibility.

## 3. What happened

| Tick | within | across | lexicon overlap | cross ties: base / intelligibility |
| --- | --- | --- | --- | --- |
| 159 (isolation ends) | 0.687 | — | 0.00 | 0 / 0 |
| 360 | 0.800 | −0.053 | 0.00 | 19 / 0 |
| 660 | 0.833 | +0.026 | 0.00 | 35 / 2 |
| 1059 (end) | 0.851 | +0.037 | 0.00 | 36 / 6 |

Three things occurred.

**Isolated groups produced disjoint vocabularies.** Lexicon overlap was `0.00`
at the end of isolation. With no shared communication events there is no
mechanism that would have made them agree, so this is expected rather than
surprising, and it is recorded because everything downstream depends on it.

**Contact initially failed.** Cross-group intelligibility went *negative*
(`−0.053`) once the groups were merged. Coevolution reads real communication
outcomes, and early cross-group utterances were not understood.

**Comprehension recovered; production did not converge.** Cross-group
intelligibility climbed back to `+0.037`, while lexicon overlap remained
`0.00` for the entire 900-tick contact phase. The groups learned to understand
each other's forms without adopting them.

That asymmetry is the most interesting observation here and it was not
predicted. It was subsequently traced through the code and measured; see
§4 below.

## 4. Why production does not converge

The asymmetry above was investigated by instrumenting the contact phase. The
original guess — that an entrenched native form keeps winning production
selection — turned out to be the *last* of several filters rather than the
explanation, and two intermediate guesses were wrong outright.

Measured over the 900-tick contact phase:

| Stage | Measurement |
| --- | --- |
| Cross-group communication | 508 events, 21.1% of all communication |
| Cross-group success rate | 216 of 508 (42.5%), against 94.0% within-group |
| Successes clearing promotion | 6 of 216 |
| Foreign forms reaching production | peak 2 at once, present on 301 of 900 ticks |
| Peak foreign production confidence | 0.650, against ~0.965 native |
| Foreign forms ever **selected** | 0 |

Reading the chain in order:

**Contact is not rare.** One in five communications crossed groups. An early
guess that speciation held because the groups barely spoke was wrong.

**Promotion filters almost everything.** A heard form enters production only
after its comprehension entry clears both `PROMOTION_CONFIDENCE` (0.50) and
`PROMOTION_SUCCESS_COUNT` (3). Confidence is the binding criterion: across the
216 cross-group successes, comprehension confidence averaged 0.292 and cleared
0.50 only six times, while the success count cleared 3 sixty-nine times.

**The gate is not the whole story either.** Lowering `PROMOTION_CONFIDENCE`
to 0.40, 0.20, and even 0.05 in an intervention run left lexicon overlap at
`0.00`, so promotion alone does not produce adoption.

**Selection is where adoption actually dies.** Foreign forms did reach
production and did become usable, holding a slot on a third of all contact
ticks and peaking at 0.650 confidence. They were selected **zero** times.
`_select_production` takes the highest-confidence usable form, and the native
sits near the 0.965 ceiling.

A foreign form gains confidence passively when heard again, so this is a rate
race rather than a strict deadlock: it gains on cross-group hearings and is
weakened whenever the native is reinforced. With within-group communication
running roughly four times as often, the foreign form stalls well short of the
incumbent, is never selected, and is eventually evicted. Final foreign
production count is zero.

So the original hypothesis is confirmed only in its narrowest form —
entrenched natives do win selection — but it describes the final step of a
chain in which promotion has already discarded 210 of 216 opportunities.

## 5. The negative result

Coalition intelligibility gating changed nothing in this scenario.

Trajectories were identical with gating on and off at every measured tick.
The final partition was the same in both conditions — each original group
became exactly one coalition. Only the coalition *identifiers* differed, which
indicates gating perturbed formation order without changing the outcome.

This is not because the gate is inert. A threshold sweep on a well-mixed
population shows it binding clearly: at `0.50` first coalition formation is
delayed from tick 113 to 182, and at `0.95` coalitions never form. See
[Coalition Intelligibility](../systems/coalition-intelligibility.md).

It is because in *this* scenario the structural constraints bind first. At tick
660 gating excluded 33 base-eligible cross-group ties and the partition was
unaffected, because cross-group coalitions were already prevented by minimum
support-block size, biconnectivity, and the persistence requirement — all of
which are consulted independently of language.

The practical consequence: **the divergence-and-separation behaviour above is
produced by base language and coevolution v1. Coalition gating is not
load-bearing for it.**

## 6. What this does not establish

- Nothing about other population sizes, group counts, seeds, thresholds, or
  contact schedules. One scenario was run.
- Nothing about whether the same behaviour appears in a full simulation with
  births, deaths, migration, factions, and combat active. That was not run, so
  it is untested in either direction.
- Nothing about whether lexicon overlap would eventually rise given a longer
  contact phase. It was flat for 900 ticks, which is evidence of persistence
  over that window and not of permanence. The rate argument in §4 suggests it
  would stay flat, but that was reasoned from measured rates rather than run.
- Nothing about whether different promotion or reinforcement constants would
  permit adoption. The intervention in §4 varied `PROMOTION_CONFIDENCE` only,
  and did so by patching a module constant in a probe, not by changing source.
- Nothing about coalition gating's value in general. It shows only that gating
  did not contribute to this particular behaviour.
- No estimand, contrast, estimator, or uncertainty method is defined, so no
  quantity here is an approved research endpoint.

## 7. Reproducing it

The scenario is a scripted in-process probe rather than a committed fixture,
because promoting it to a fixture would imply a stability guarantee that one
scenario does not support. To rebuild it, drive `economy_tick` and
`transition_informal_coalitions` in the tick order the simulation uses —
economy first, coalition maintenance second — with the controls in §2, and
sample the quantities listed there.

The tick order matters. Communication updates intelligibility during the
economy layer, and coalitions recompute from it during maintenance, so
sampling between those two steps reports a different state than sampling after
both.

## 8. Why this note exists

Three coevolution milestones were built in sequence. Before adding a fourth,
the stack was run to find out what it already did. The answer was that the
most interesting available behaviour was already reachable, and that the most
recent mechanism did not contribute to it.

Recording a negative result about recently added work is cheaper than
discovering it later from a mechanism built on the assumption that the
previous one mattered.
