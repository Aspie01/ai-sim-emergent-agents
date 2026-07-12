# Causal chains

## Survival and resources

```text
season + population pressure
-> tile-resource regeneration
-> inhabitant consumption and local gathering
-> hunger and movement
-> health loss
-> death checkpoint
-> population/faction cleanup
-> end-of-tick metrics
```

This chain is causal. Water exists in tiles/inventories but is not a survival need. Death is checked at specific points rather than immediately after every health mutation.

## Aid, trade, and directed relationships

```text
co-location + giver surplus + receiver deficit
-> committed one-unit Layer-4 transfer
-> inventory/currency and legacy-trust update
-> optional stable-ID aid/trade Relationship update
-> optional later repeated-partner preference
-> differentiated reciprocal social topology
```

This chain is causal. Layer-1 random swaps and formal-faction reserve distribution do not create stable-ID relationship records.

## Informal coalition emergence

```text
authentic committed Layer-4 aid/trade
-> bounded directed Relationship records
-> reciprocal threshold graph
-> vertex-biconnected support blocks
-> exact-membership persistence
-> active informal coalition IDs
-> growth, shrinkage, split, or dissolution
```

This chain is causal until coalition state is created. Current coalitions are otherwise descriptive: they do not choose actions, own resources, or affect formal factions. Active coalition merging is not implemented.

## Endogenous language learning

```text
already-committed aid/trade
-> sender selects or deterministically invents signal
-> receiver interprets from pre-learning comprehension
-> success / misunderstanding / unknown / no signal
-> language-only reinforcement, correction, learning, promotion and pruning
```

The communication is observational with respect to the transfer. An event that teaches an unknown signal remains `UNKNOWN_SIGNAL`; correction cannot create same-event success.

## Coalition dialects

```text
last fully committed coalition observation
-> one immutable membership snapshot before economy
-> stable-ID communication context
-> same-coalition adjusted learning/reinforcement rate
-> member-owned vocabulary update
```

This is a one-way causal extension. All non-same-coalition contexts use base Language-v1 rates; there is no out-group penalty. Language never changes coalition topology or lifecycle.

## Formal civilization chain

```text
agent experience
-> bounded beliefs
-> shared beliefs + legacy trust + proximity
-> formal factions
-> pooled resources / settlement / rivalry
-> economy, technology, diplomacy and combat
-> deaths, membership, territory, reputation and resource changes
```

This older chain is causal and RNG-driven. It is separate from informal coalitions and has substantially less focused behavioral test coverage.

## Experiment to artifact

```text
plan + code + environment
-> frozen cell command
-> isolated process
-> ordered completed ticks
-> required structured files
-> writer health + checksums + state fingerprint
-> atomic run manifest
-> deep validation
-> derived analysis
```

The generic runner currently records only part of the complete provenance shown. Clean-tag/environment/plugin preflight and immutable attempts are **Planned, not implemented**.

## Connection classification

| Connection | Classification |
| --- | --- |
| Resources -> survival | Causal |
| Committed transfers -> relationships | Causal |
| Relationships -> informal coalitions | Causal |
| Transfer -> language opportunity | Observational with language-only mutation |
| Coalition membership -> same-group language rates | Causal one-way |
| Language -> economy/coalitions/survival | Intentionally isolated |
| State -> metrics/events/dashboard | Diagnostic/observational |
| Plan -> child process/artifacts | Operational causal chain |
| Future language feedback/research contracts | Planned, not implemented |

## Implementation evidence

- Sources: `inhabitants.py`, `economy.py`, `social.py`, `coalitions.py`, `language.py`, `sim.py`, `run_experiments.py`.
- Tests: social, coalition, language, dialect, termination, and artifact suites listed in [test reference](../reference/test-reference.md).
