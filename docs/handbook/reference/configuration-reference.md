# Configuration reference

`SimulationConfig` is a frozen effective configuration. The simulator parses with `allow_abbrev=False`, normalizes feature dependencies, validates values, updates a small set of compatibility globals, and passes explicit frozen subconfigurations to the newer social, coalition, language, dialect, contact, and intergenerational-language systems.

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

## Provenance status

Each newer feature family records one of:

- `disabled`: exact defaults, feature gate false, no notices;
- `normalized_uncontracted`: an invalid dependency request was normalized off and notices record why;
- `engineering_only_uncontracted`: a feature is enabled or any control is nondefault, without normalization notices.

These are provenance classifications, not alternate runtime switches. The generic experiment runner rejects all social, coalition, language, dialect, contact, and intergenerational option families—including exact, equals, unambiguous-prefix, and ambiguous-prefix forms—before output-root creation or mutation, command construction, verification mutation, or child launch.

Present contradictions are artifact-invalid. Historically missing
intergenerational fields remain schema-valid, but missing, enabled, normalized,
or nondefault intergenerational controls veto V2 readiness. An
`ExpectedRunContract` cannot override that veto.

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
  `tests/test_language_reproducibility.py`, `tests/test_reproducibility.py`,
  `tests/test_artifact_validation.py`, `tests/test_experiment_runner.py`.
- Verified help: `python -m thalren_vale --help`.
- Current status: Stable and verified configuration machinery; newer emergence controls remain Engineering-only.
