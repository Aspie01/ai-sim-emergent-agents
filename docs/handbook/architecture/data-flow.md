# Data flow

## Configuration to state

```text
argv
-> argparse namespace
-> frozen SimulationConfig
-> dependency normalization/notices
-> validation
-> legacy compatibility globals + explicit subconfigs
-> runtime initialization
```

The manifest stores the effective normalized configuration, not the original spelling of every flag.

## Tick state flow

```text
world tiles
-> inhabitant needs, movement, inventory and death
-> beliefs and formal factions
-> reproduction
-> economy/resources/currency/relationships/language and contact exposure
-> combat, technology, diplomacy, religion
-> scheduled interventions and plugins
-> social/coalition/language maintenance
-> authoritative observation
```

State changes are direct Python object mutations except where a focused subsystem proposes and validates replacement state. The event journal records the order in which observations were produced; it is not the mutation transport.

When Language Contact v1 is effective, one pre-economy coalition snapshot feeds
the shared communication classification. Only authentic
`DIFFERENT_ACTIVE_COALITIONS` communication can flow into multiplied positive
receiver learning, bounded `ContactExposure`, and contact-qualified
`BorrowingProvenance`. Assigned/unassigned and both-unassigned communication
remain on the base language path. Contact state flows only into individual
language state, on-demand summaries, and the selected-state hash; it has no
return path into social or material state.

## Observation to artifacts

```text
ordered journal + authoritative end-of-tick state
-> event, metrics, belief and terminal-summary rows
-> required CSVs
-> streaming checksums and artifact inventory

required-writer lifecycle
-> writer health

authoritative final state + hashed effective controls
-> selected-state SHA-256

termination + configuration + code provenance
+ selected-state SHA-256 + writer health + artifact inventory
-> atomic run manifest publication

run manifest + required CSVs
-> deep validator
```

The selected-state SHA-256 is computed directly from authoritative in-memory
state and hashed controls after required writers close. It is not derived from
the CSV contents. Checksums independently bind the required CSV bytes into the
manifest inventory.

Enabled contact hashing includes exact effective controls, bounded contact
runtime, comprehension exposure metadata, and production borrowing provenance.
Disabled contact controls are omitted only when runtime and association state
are pristine; hidden contact state fails closed. Contact adds no standard event
or metrics artifact fields.

The current belief CSV header says `inhabitant_id`, but the producer writes the inhabitant display name. The deep validator verifies a nonempty unique string at each snapshot tick; it does not reinterpret it as the stable integer ID.

## Plan to batch result

```text
plan JSON bytes
-> schema validation + SHA-256
-> frozen ordered cells
-> absent/empty contained root
-> one isolated child per condition/seed
-> strict per-cell artifact validation
-> batch result record
-> rewritten run index
```

The batch manifest knows the plan path/hash. Child run manifests do not contain plan identity or an environment fingerprint, which is one reason current runner output is valid engineering evidence at most, not `v2_ready`.

## Downstream analysis

Canonical analysis should begin with revalidation of the raw structured set. Derived CSVs, figures, narrative parses, and batch indexes inherit authority only from the validated cells and recorded transformations. Current validation emits an in-memory/CLI report; it does not create a durable validation certificate.

## Implementation evidence

- `src/thalren_vale/events.py`, `metrics.py`, `language.py`, `reproducibility.py`.
- `src/thalren_vale/artifact_validation.py`.
- `run_experiments.py`.
- Tests: `tests/test_events.py`, `tests/test_language_contact.py`,
  `tests/test_language_reproducibility.py`, `tests/test_artifact_validation.py`,
  `tests/test_experiment_runner.py`.
