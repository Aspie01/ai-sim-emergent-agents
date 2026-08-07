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

This is a one-way causal extension. The dialect feature applies no out-group
penalty. Non-same-coalition contexts use base Language v1 rates unless the
independent Language Contact v1 gate qualifies a different-active-coalitions
event. Language never changes coalition topology or lifecycle.

## Language contact

```text
authentic different-coalition communication
-> stronger receiver-side acquisition
-> bounded cross-boundary exposure evidence
-> contact-qualified borrowing promotion
-> mixed individual vocabularies
-> measurable contact-driven convergence or continued divergence
```

Only `DIFFERENT_ACTIVE_COALITIONS` follows this extension. Assigned/unassigned
and both-unassigned communication remain base-rate language behavior. Contact
changes only inhabitant-owned language state; coalitions do not own languages,
and language cannot change transfers, relationships, partner choice, coalition
lifecycle, factions, combat, survival, or population state. See
[Language contact](../systems/language-contact.md).

## Intergenerational language

```text
successful make_child() and committed _spawn(child)
-> exact two parent objects sorted by stable ID
-> bounded deterministic usable parental production selection
-> child comprehension-only exposure
-> canonical retention
-> later ordinary reinforcement, forgetting, pruning, or production promotion
```

This is a one-way post-birth extension. It copies no complete vocabulary,
creates no production at birth, consumes no RNG, and cannot change whether the
birth occurred or any parent, material, social, faction, coalition, combat,
health, survival, or population outcome. A failed transmission leaves the
already admitted child and consumed stable ID committed while rolling back the
three language-owned mutable owners. See
[Intergenerational language](../systems/intergenerational-language.md).

## Lexical evolution

```text
already-committed aid/trade
-> authoritative pre-existing usable production selection
-> one deterministic lexical opportunity
-> exact source emission when not triggered or depth-limited
   OR one-token descendant substitution and actual descendant emission
-> exact receiver interpretation and learning
-> ordinary competition, promotion, forgetting, pruning, or extinction
```

Ordinary invention is not a lexical opportunity. The substitution derivation
uses stable lexical-event inputs and SHA-256, not coalition/dialect/contact
state or RNG. The descendant may coexist with or replace its source through
ordinary bounded association rules. The transfer has already committed and no
language result feeds back into material, social, biological, faction, or
coalition state. See [Lexical evolution](../systems/lexical-evolution.md).

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
| Different active coalitions -> positive contact acquisition/borrowing | Causal one-way within language |
| Committed birth + exact parents -> child comprehension | Causal one-way within language after birth admission |
| Committed transfer + selected usable form -> lexical descendant emission | Causal one-way within language after transfer commit |
| Language -> economy/combat/diplomacy/religion/survival | Intentionally isolated |
| Utterance outcome -> directed relationship ties -> partner choice | Causal when language coevolution is effective; the first deliberate break in language isolation |
| Mutual intelligibility -> coalition edge qualification | Causal when coalition intelligibility is effective; gating only ever narrows |
| State -> metrics/events/dashboard | Diagnostic/observational |
| Plan -> child process/artifacts | Operational causal chain |
| Research analysis contracts | Planned, not implemented |

## Implementation evidence

- Sources: `inhabitants.py`, `economy.py`, `social.py`, `coalitions.py`, `language.py`, `sim.py`, `run_experiments.py`.
- Tests: social, coalition, language, dialect, contact, intergenerational, lexical,
  termination, and artifact suites listed in
  [test reference](../reference/test-reference.md).
