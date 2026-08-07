# Language Research Readiness

## 1. What this milestone does and does not do

Language Research Readiness v1 makes exactly one language mechanism —
[Endogenous Language v1](endogenous-language.md) — eligible to appear in
evidence classified `v2_ready`, and records one contracted endpoint.

It does **not** authorize execution. No S0, S1, P1, P2, or Full experiment
configuration exists, no research cell has been launched, and no research
result exists. `AGENTS.md` states that completing one step never authorizes
the next gate, and that boundary is unchanged by this milestone. What changed
is that the repository can now *certify* a run, not that any run was made.

It also does **not** define an estimand, contrast, estimator, uncertainty
method, or multiplicity rule. Those remain unspecified and are a separate
authorization gate. `v2_ready` here means evidence integrity — provenance,
schema, determinism, and approved controls — not that an analysis plan exists.

## 2. The contracted mechanism

Only base language is contracted. The nine later language milestones —
coalition dialects, language contact, intergenerational language, lexical
evolution, compositional protolanguage, grammar evolution, language
coevolution, coalition intelligibility, and production trials — remain
engineering-only and continue to veto V2 readiness, as does the non-language
faction relationship-trust model.

A first contract admitting one mechanism is defensible; one admitting several
interacting mechanisms would make any observed effect impossible to attribute.

### Approved control values

The gate itself may take **either** value, so one run can serve as treatment
and another as control. Every other base-language control is pinned:

| Control | Approved value |
| --- | --- |
| `language_evolution_enabled` | `False` or `True` |
| `maximum_language_associations` | `32` |
| `maximum_signal_length` | `3` |
| `language_learning_rate` | `0.20` |
| `language_reinforcement_rate` | `0.10` |
| `language_forgetting_interval` | `25` |
| `language_invention_enabled` | `True` |

Any other value of any control makes the run engineering-only and vetoed. A
run with an arbitrary learning rate is not "research-ready" in any useful
sense, so the contract does not pretend otherwise.

### The new provenance status

`language_controls_status` gains `contracted` alongside `disabled` and
`engineering_only_uncontracted`:

| Situation | Status |
| --- | --- |
| Language on, all approved values | `contracted` |
| Language off, all approved values | `disabled` |
| Any non-approved control value | `engineering_only_uncontracted` |

`disabled` is deliberately unchanged. It is the historical baseline every
pre-contract pinned hash was recorded against, and it stays untouched.

## 3. The contracted endpoint

One endpoint is recorded, in every run manifest:

```json
"language_endpoint": {
  "name": "comprehension_success_rate",
  "definition": "successful_interpretation_count / communication_attempt_count",
  "communication_attempt_count": 436,
  "successful_interpretation_count": 24,
  "comprehension_success_rate": 0.055045871560,
  "measured_at_tick": 40,
  "analysis_contract": "unspecified"
}
```

The rate is `null`, not `0.0`, when no utterance occurred. A control arm with
language disabled attempts no communication, so its rate is genuinely
undefined; reporting zero would assert a measured communicative failure that
never happened. That distinction is enforced by validation, not merely by
convention.

`analysis_contract` is `"unspecified"` and says so explicitly rather than
leaving the omission to be inferred.

## 4. What the readiness gate now requires

A run reaches `v2_ready` only if all of the following hold, in addition to
every pre-existing schema, checksum, and termination requirement:

- every control family sits at approved or safe values;
- `language_controls_status` is `contracted` when language is on and
  `disabled` when it is off;
- a well-formed `language_endpoint` is present and internally consistent.

The last requirement correctly excludes every artifact recorded before this
milestone. Evidence that predates a contract cannot satisfy it.

## 5. Two defects this milestone repaired

### The readiness veto had holes

The veto covered seven control families. Compositional protolanguage, grammar
evolution, and language coevolution were added later and were never added to
it, so a run could set a nondefault morpheme length, adoption threshold, or
feedback rate and still classify `v2_ready` while carrying an uncontracted
engineering-only control.

All three are now covered. A structural test asserts that **every**
`*_controls_status` manifest key reaches the readiness gate, so a future
milestone cannot repeat the omission silently.

### In-progress research was invisible to the hash

The canonical payload read `faction.researching` and
`faction.research_progress`. Nothing in the simulation assigns either
attribute, so both fields were permanently `None`, while the authoritative
`active_research` mapping owned by `technology.py` never entered the hash at
all. Two factions researching different technologies produced identical
fingerprints.

The payload now reads the authoritative mapping, and all four of its fields
(`tech`, `progress`, `started`, `paused`) discriminate.

## 6. Deliberate hash changes

This milestone intentionally moves two sets of fingerprints. Both were
verified to be precisely scoped rather than assumed.

**The contracted status.** Only language-*enabled* runs move, because
`language_controls_status` is excluded from the behavioural payload when
language is off. A disabled run hashes identically before and after. Forcing
the status string back to its old value reproduces the previous hash exactly,
which proves the status field is the sole cause.

**The research repair.** Only runs long enough to begin research move. The
5-tick termination baseline is unchanged; the 40-tick anti-stagnation baseline
moved, and its previous value is recorded beside the new one in
`tests/test_run_termination.py`.

Any hash recorded outside this repository for a language-enabled or
research-reaching run no longer matches. That is the intended cost of the
repair, not a regression.

## 7. Deliberately not versioned

The run manifest gained a field without a `RUN_MANIFEST_SCHEMA_VERSION` bump.
The manifest key set is open — no validator rejects unknown keys — so existing
artifacts remain *valid*. They simply cannot be `v2_ready`, which was already
true of them. Bumping the version would have invalidated every existing
artifact in strict mode for no gain.

## 8. Remaining gates

The following are **Planned, not implemented** and each requires separate,
explicit authorization:

- estimand, contrast, estimator, uncertainty method, multiplicity rules;
- immutable attempt directories, append-only attempt ledger, and
  contract-matched resume;
- clean annotated-tag and environment preflight;
- nonexecuting V2 matrix expansion and quota enforcement;
- any execution of an S0, S1, P1, P2, Full, pilot, or replication cell.

Child-manifest provenance is **no longer** on that list. Every run manifest now
carries `plan_identity`, `plan_sha256`, `environment_fingerprint`, and a `code`
record with commit, annotated tag, and dirty status; the runner passes
`--plan-identity` and `--plan-sha256` to each child, and
`environment_fingerprint` digests the interpreter, platform, and the SHA-256 of
every loadable plugin. A direct run leaves the two plan fields `null`, which is
why a direct run still cannot be `v2_ready`.

A run cannot presently reach `v2_ready` through the generic runner, because
the runner does not yet supply a complete `ExpectedRunContract` — it accepts
one but never constructs it. The contract machinery is testable today; the
orchestration that would satisfy it is not built.

## 9. Language roadmap

Implemented: Endogenous Language, Coalition Dialects, Language Contact,
Intergenerational Language, Lexical Evolution, Compositional Protolanguage,
Grammar Evolution, Language Coevolution, Language Research Readiness,
Coalition Intelligibility, Production Trials.

The language milestone sequence is complete. Every further step is a research
authorization decision rather than an engineering one.

## 10. Implementation evidence

- `src/thalren_vale/config.py` — `APPROVED_LANGUAGE_CONTROLS`, the
  `contracted` status
- `src/thalren_vale/artifact_validation.py` — contract-aware language veto,
  the three added control families, endpoint validation
- `src/thalren_vale/reproducibility.py` — `language_endpoint_record`,
  `_active_research_record`
- `src/thalren_vale/sim.py` — endpoint recorded in every run manifest
- `tests/test_artifact_validation.py` — veto coverage, structural guard,
  endpoint readiness
- `tests/test_reproducibility.py` — endpoint semantics, research payload
- `tests/test_config.py` — contracted status
- `tests/test_run_termination.py` — repinned baseline with its provenance
