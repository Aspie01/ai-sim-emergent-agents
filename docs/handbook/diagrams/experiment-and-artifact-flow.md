# Experiment and artifact flow

```mermaid
flowchart TD
    PLAN[Schema-1 plan JSON]
    FREEZE[Validate and freeze ordered cells]
    ROOT[Require absent or empty contained root]
    CHILD[Launch one seeded simulator child]
    STATE[Authoritative final state and hashed controls]
    CSV[Metrics, events, beliefs, summary]
    HASH[Selected-state SHA-256]
    HEALTH[Writer health]
    INVENTORY[Checksums and artifact inventory]
    MANIFEST[Run manifest published last]
    VALIDATE[Streaming strict validation]
    RESULT[Batch manifest result]
    INDEX[Derived run index]
    ANALYSIS[Optional derived analysis]

    PLAN -->|raw-byte SHA-256| FREEZE
    FREEZE --> ROOT
    ROOT --> CHILD
    CHILD --> CSV
    CHILD --> STATE
    CHILD --> HEALTH
    STATE --> HASH
    CSV --> INVENTORY
    HASH --> MANIFEST
    HEALTH --> MANIFEST
    INVENTORY --> MANIFEST
    MANIFEST --> VALIDATE
    CSV --> VALIDATE
    VALIDATE --> RESULT
    RESULT --> INDEX
    VALIDATE --> ANALYSIS
```

Current limitations: no immutable attempt directory, append-only ledger, selected attempt, safe nonempty-root resume, fail-fast dispatch, environment/plugin preflight, or V2-ready execution contract. All are **Planned, not implemented**.
