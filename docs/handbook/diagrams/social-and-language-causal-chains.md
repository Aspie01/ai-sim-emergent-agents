# Social and language causal chains

```mermaid
flowchart LR
    TRANSFER[Successfully committed Layer-4 aid or trade]
    REL[Directed Relationship update]
    BIAS[Optional repeated-partner bias]
    GRAPH[Reciprocal qualifying graph]
    COAL[Informal coalition transition]
    SNAP[Frozen prior-observation membership]
    COMM[Authentic communication]
    INTERP[Pre-learning interpretation]
    UPDATE[Individual language update]
    SUMMARY[On-demand dialect summary]
    NOCOAL[No language feedback to coalition lifecycle]
    NOTRANSFER[No language feedback to transfer success]

    TRANSFER --> REL
    REL --> BIAS
    BIAS --> TRANSFER
    REL --> GRAPH
    GRAPH --> COAL
    COAL --> SNAP
    TRANSFER --> COMM
    SNAP -->|same-coalition rates only| COMM
    COMM --> INTERP
    INTERP --> UPDATE
    UPDATE -. frequency observation .-> SUMMARY

    UPDATE -. intentional isolation .-> NOCOAL
    UPDATE -. intentional isolation .-> NOTRANSFER
```

The dotted isolation edges document that vocabulary and interpretation do not
affect coalition lifecycle or transfer success. Layer-1 swaps, raids,
proximity alone, timers, and maintenance passes do not create authentic
language communication.
