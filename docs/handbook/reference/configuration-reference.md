# Configuration reference

`SimulationConfig` is a frozen effective configuration. The simulator parses with `allow_abbrev=False`, normalizes feature dependencies, validates values, updates a small set of compatibility globals, and passes explicit frozen subconfigurations to the newer social, coalition, language, dialect, contact, intergenerational-language, lexical-evolution, compositional-protolanguage, grammar-evolution, language-coevolution, coalition-intelligibility, production-trial, and faction-relationship-trust systems.

## Core fields

| Field / CLI | Type | Default | Validation and effect |
| --- | --- | ---: | --- |
| `condition` / `--condition` | string | `baseline` | 1–64 filename-safe characters, starting alphanumeric |
| `ticks` / `--ticks` | integer | 5000 | At least 1 |
| `population_cap` / `--pop-cap` | integer | 1000 | At least 1 |
| `starting_population` / `--starting-pop` | integer | 30 | 1..population cap and at most 135 |
| `faction_trust_threshold` / `--faction-trust-threshold` | integer | 5 | Nonnegative; formal-faction comparisons are strict `>` |
| `war_tension_threshold` / `--war-tension-threshold` | integer | 200 | At least 1 |
| `belief_sharing_probability` / `--belief-sharing-prob` | float | 0.5 | Inclusive 0..1 |
| `anti_stagnation_enabled` / `--disable-antistag` | boolean | true | Flag disables the complete intervention bundle |
| `belief_tracking_enabled` / `--enable-belief-tracking` | boolean | false | Enables optional RA outputs |
| `log_mode` / `--log-mode` | enum | `full` | `full`, `summary`, `metrics_only`, `off`; all retain required structured artifacts |

## Disabled layers

`--disable-layer` accepts a comma-separated canonical subset:

| Value | Effect |
| --- | --- |
| `beliefs` | Skips initial and per-tick belief processing |
| `factions` | Skips formal-faction layer |
| `economy` | Skips currency, prices, individual/faction transfers, scarcity, and raids |
| `raids` | Suppresses only economy raids |
| `combat` | Suppresses formal combat; raids remain independent |
| `technology` | Skips technology layer |
| `diplomacy` | Skips diplomacy layer |
| `religion` | Skips religion layer |
| `mythology` | Skips mythology tick/final narrative path |

`--disable-raids` is an alias that adds `raids`. World, inhabitants, procreation, plugins, structured observation, and feature maintenance are not disabled-layer entries.

## Social-memory controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `social_memory_enabled` | false | Engineering master gate |
| `social_partner_bias_enabled` | false | Requires effective social memory |
| `maximum_social_ties` | 32 | Integer 1..128 |
| `relationship_decay_interval` | 25 | Positive integer |

Requesting partner bias without memory normalizes bias to false and records `partner_bias_requested_without_social_memory`.

## Endogenous-language controls

| Field | Default | Valid range |
| --- | ---: | --- |
| `language_evolution_enabled` | false | Boolean engineering gate |
| `maximum_language_associations` | 32 | Integer 1..40 |
| `maximum_signal_length` | 3 | Integer 2..4 |
| `language_learning_rate` | exact float 0.20 | `(0,1]` |
| `language_reinforcement_rate` | exact float 0.10 | `(0,1]` |
| `language_forgetting_interval` | 25 | Positive integer |
| `language_invention_enabled` | true | Boolean |

Language v1 defines no dependency-normalization notices.

## Informal-coalition controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `coalition_emergence_enabled` | false | Requires effective social memory |
| `coalition_minimum_size` | 3 | Integer 3..1024 |
| `coalition_trust_threshold` | exact float 0.24 | Inclusive 0..1 |
| `coalition_familiarity_threshold` | exact float 0.40 | Inclusive 0..1 |
| `coalition_maximum_grievance` | exact float 0.20 | Inclusive 0..1 |
| `coalition_persistence_ticks` | 5 | Integer at least 2 |
| `maximum_active_coalitions` | 32 | Integer 1..1024 |

Requesting emergence without social memory normalizes it off and records `coalition_emergence_requested_without_social_memory`.

## Coalition-dialect controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `coalition_dialect_influence_enabled` | false | Requires effective language and coalitions |
| `same_coalition_learning_multiplier` | exact float 1.50 | Inclusive 1..2 |
| `same_coalition_reinforcement_multiplier` | exact float 1.25 | Inclusive 1..2 |

Missing dependencies normalize influence off and record the sorted applicable notices:

- `dialect_influence_requested_without_language`
- `dialect_influence_requested_without_coalitions`

## Language-contact controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `language_contact_enabled` | false | Requires effective language and coalitions; independent of dialect influence |
| `cross_group_learning_multiplier` | exact float 1.50 | Inclusive 1..2 |
| `borrowing_exposure_threshold` | 3 | Integer 2..32 |
| `borrowing_confidence_threshold` | exact float 0.50 | Inclusive 0.10..1.0 |

CLI forms are `--enable-language-contact`, `--disable-language-contact`,
`--cross-group-learning-multiplier`, `--borrowing-exposure-threshold`, and
`--borrowing-confidence-threshold`. Missing effective dependencies normalize
contact off and record the sorted applicable notices:

- `language_contact_requested_without_language`
- `language_contact_requested_without_coalitions`

Only authentic `DIFFERENT_ACTIVE_COALITIONS` communication uses these controls.
Assigned/unassigned and both-unassigned communication stays at base Language v1
rates.

## Intergenerational-language controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `intergenerational_language_enabled` | `False` | Exact Boolean; requires only effective base language evolution |
| `maximum_parental_meanings_per_parent` | `2` | Exact non-Boolean integer `1..len(Meaning)`; currently `1..4` |
| `intergenerational_learning_strength` | exact float `0.20` | Exact finite float `0.0 < x <= 1.0` |

CLI forms are `--enable-intergenerational-language`,
`--disable-intergenerational-language`,
`--maximum-parental-meanings-per-parent`, and
`--intergenerational-learning-strength`.

Requesting transmission without effective base language normalizes only the
intergenerational gate off and records:

- `intergenerational_language_requested_without_language`

The feature does not depend on coalitions, dialect influence, language contact,
formal factions, or settlements.

## Lexical-evolution controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `lexical_evolution_enabled` | `False` | Exact Boolean; requires only effective base language evolution |
| `lexical_mutation_rate` | exact float `0.05` | Exact finite float in inclusive `0.0..1.0` |
| `maximum_lexical_lineage_depth` | `8` | Exact non-Boolean integer `1..32` |

CLI forms are `--enable-lexical-evolution`,
`--disable-lexical-evolution`, `--lexical-mutation-rate`, and
`--maximum-lexical-lineage-depth`.

Requesting lexical evolution without effective base language normalizes only
the lexical gate off, preserves both submitted numeric controls, and records:

- `lexical_evolution_requested_without_language`

The feature does not depend on intergenerational language, coalitions, dialect
influence, language contact, social memory, formal factions, or settlements.

## Compositional-protolanguage controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `compositional_protolanguage_enabled` | `False` | Exact Boolean; requires effective base language evolution |
| `maximum_resource_morpheme_length` | `2` | Exact non-Boolean integer `1..3` |
| `modality_morpheme_length` | `1` | Exact non-Boolean integer `1..2` |

CLI forms are `--enable-compositional-protolanguage`,
`--disable-compositional-protolanguage`,
`--maximum-resource-morpheme-length`, and `--modality-morpheme-length`.

When composition is effectively enabled, the two morpheme lengths must also sum
to at most the effective `maximum_signal_length`; a composed signal that could
not fit in a legal signal is rejected rather than truncated. Requesting
composition without effective base language normalizes only the composition
gate off and records:

- `compositional_protolanguage_requested_without_language`

## Grammar-evolution controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `grammar_evolution_enabled` | `False` | Exact Boolean; requires effective base language **and** effective compositional protolanguage |
| `order_adoption_threshold` | `3` | Exact non-Boolean integer `1..32` |

CLI forms are `--enable-grammar-evolution`, `--disable-grammar-evolution`, and
`--order-adoption-threshold`.

Normalization runs after composition, so a composition gate that was itself
normalized off cascades here. Missing effective dependencies normalize grammar
off and record the sorted applicable notices:

- `grammar_evolution_requested_without_language`
- `grammar_evolution_requested_without_composition`

## Language-coevolution controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `language_coevolution_enabled` | `False` | Exact Boolean; requires effective base language **and** effective social partner bias |
| `intelligibility_reward` | exact float `0.06` | Exact finite float `0.0 < x <= 0.25` |
| `intelligibility_penalty` | exact float `0.04` | Exact finite float `0.0 < x <= 0.25` |

CLI forms are `--enable-language-coevolution`,
`--disable-language-coevolution`, `--intelligibility-reward`, and
`--intelligibility-penalty`.

Partner bias is a dependency because coevolution's only effect is to feed
intelligibility into partner choice; without bias there is nothing for it to
change. Missing effective dependencies normalize coevolution off and record the
sorted applicable notices:

- `language_coevolution_requested_without_language`
- `language_coevolution_requested_without_partner_bias`

## Coalition-intelligibility controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `coalition_intelligibility_enabled` | `False` | Exact Boolean; requires effective coalition emergence **and** effective language coevolution |
| `coalition_intelligibility_threshold` | exact float `0.50` | Exact finite float `0.0 < x <= 1.0` |

CLI forms are `--enable-coalition-intelligibility`,
`--disable-coalition-intelligibility`, and
`--coalition-intelligibility-threshold`.

The threshold is strictly positive by validation: a tie with no communication
history sits at exactly `0.0`, and silence must not count as understanding.
Normalization runs after coevolution, so an implicitly disabled coevolution
cascades. Missing effective dependencies normalize the gate off and record the
sorted applicable notices:

- `coalition_intelligibility_requested_without_coalitions`
- `coalition_intelligibility_requested_without_coevolution`

## Production-trial controls

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `production_trial_enabled` | `False` | Exact Boolean; requires effective base language evolution |
| `production_trial_interval` | `8` | Exact non-Boolean integer `2..64` |

CLI forms are `--enable-production-trial`, `--disable-production-trial`, and
`--production-trial-interval`.

The interval floor is 2 rather than 1: an interval of 1 would trial the
runner-up form on every utterance, which is substitution rather than variation.
Requesting trials without effective base language normalizes only the trial
gate off and records:

- `production_trial_requested_without_language`

## Faction relationship-trust controls

This family is not a language family. It selects which social model the formal
faction layer reads.

| Field | Default | Valid range / dependency |
| --- | ---: | --- |
| `faction_relationship_trust_enabled` | `False` | Exact Boolean; requires effective social memory. `False` retains the legacy faction trust model |
| `faction_relationship_trust_threshold` | exact float `0.40` | Exact finite float `0.0 < x <= 1.0` |

CLI forms are `--enable-faction-relationship-trust`,
`--disable-faction-relationship-trust`, and
`--faction-relationship-trust-threshold`.

The threshold applies only to the relationship model; the legacy model keeps
using the integer `faction_trust_threshold` documented under core fields.
Requesting the relationship model without effective social memory normalizes it
back to the legacy model and records:

- `faction_relationship_trust_requested_without_social_memory`

## Provenance status

Each newer feature family records one of:

- `disabled`: exact defaults, feature gate false, no notices;
- `normalized_uncontracted`: an invalid dependency request was normalized off and notices record why;
- `engineering_only_uncontracted`: a feature is enabled or any control is nondefault, without normalization notices.
- `contracted`: base language only. Every base-language control holds its
  approved value and the mechanism is active, so the run may reach V2
  readiness. See
  [Language research readiness](../systems/language-research-readiness.md).

These are provenance classifications, not alternate runtime switches. Lexical
controls use exactly the same statuses:

- exact disabled defaults use `disabled`;
- a normalized request uses `normalized_uncontracted`;
- an enabled gate or either nondefault numeric control without normalization
  uses `engineering_only_uncontracted`.

The generic experiment runner rejects all social, coalition, language, dialect,
contact, intergenerational, lexical, compositional, grammar, coevolution,
coalition-intelligibility, production-trial, and faction-relationship-trust
option families—including exact, equals, unambiguous-prefix, and
ambiguous-prefix forms—before output-root creation or mutation, command
construction, verification mutation, or child launch. Both simulator and runner
parsers reject option abbreviations through `allow_abbrev=False`.

Present contradictions are artifact-invalid. Historically missing fields for a
family added after an artifact was written remain schema-valid, but missing,
enabled, normalized, or nondefault controls in any family veto V2 readiness. An
`ExpectedRunContract` cannot override any of those vetoes.

## Seed and entry-point caveats

Seed is not a `SimulationConfig` field. Prefer the two-token `--seed 42` form.
The module wrapper sees the literal `--seed` token and starts a child with
`PYTHONHASHSEED=0`. `--seed=42` is accepted by `argparse` but bypasses that
wrapper check. The installed `thalren-vale` console script also bypasses it.
Use the complete fresh-directory, bounded command in
[safe operations](../getting-started/operations.md); do not run a seed-only
example from the repository directory.

## Implementation evidence

- Source: `src/thalren_vale/config.py`, `src/thalren_vale/sim.py::run`, `src/thalren_vale/__main__.py`.
- Tests: `tests/test_config.py`, `tests/test_language_contact.py`,
  `tests/test_intergenerational_language.py`,
  `tests/test_lexical_evolution.py`,
  `tests/test_compositional_protolanguage.py`,
  `tests/test_grammar_evolution.py`, `tests/test_language_coevolution.py`,
  `tests/test_coalition_intelligibility.py`,
  `tests/test_production_trial.py`, `tests/test_faction_social_model.py`,
  `tests/test_feature_registration.py`,
  `tests/test_language_reproducibility.py`, `tests/test_reproducibility.py`,
  `tests/test_artifact_validation.py`, `tests/test_experiment_runner.py`.
- Verified help: `python -m thalren_vale --help`.
- Current status: Stable and verified configuration machinery; newer emergence controls remain Engineering-only.
