# Full system map

```mermaid
flowchart TB
    CLI[CLI and SimulationConfig]
    SEED[Seed, hash seed, reset]
    WORLD[World, biomes, resources]
    AGENT[Inhabitants, needs, reproduction]
    BELIEF[Beliefs]
    FACTION[Formal factions and settlements]
    ECON[Economy, aid, trade, raids]
    SOCIAL[Directed relationships]
    COAL[Informal coalitions]
    LANG[Endogenous language]
    DIALECT[Coalition dialect context]
    CONTACT[Language contact context]
    INTERGEN[Intergenerational language]
    COMBAT[Formal combat]
    TECH[Technology]
    DIPLO[Diplomacy]
    RELIGION[Religion]
    INTERVENE[Anti-stagnation and world events]
    PLUGIN[Plugins]
    OBS[Events and end-of-tick metrics]
    ART[Required structured CSVs]
    HASH[Selected-state hash]
    HEALTH[Writer health]
    INV[Checksums and inventory]
    MANIFEST[Run manifest]
    RUNNER[Experiment runner]
    VALIDATE[Deep artifact validator]

    CLI -->|configuration input| SEED
    SEED -->|initializes state| WORLD
    SEED -->|admits population| AGENT
    WORLD -->|state mutation/read| AGENT
    AGENT -->|experience| BELIEF
    BELIEF -->|shared cores| FACTION
    AGENT -->|inventory and position| ECON
    FACTION -->|membership and reserves| ECON
    ECON -->|committed interactions| SOCIAL
    SOCIAL -->|reciprocal graph| COAL
    ECON -->|communication opportunity| LANG
    COAL -->|frozen membership| DIALECT
    DIALECT -->|rate adjustment only| LANG
    ECON -->|authentic communicator pair| CONTACT
    COAL -->|frozen different membership| CONTACT
    CONTACT -->|positive acquisition and provenance| LANG
    AGENT -->|committed birth + exact parents| INTERGEN
    INTERGEN -->|bounded child comprehension only| LANG
    FACTION --> COMBAT
    ECON --> COMBAT
    COMBAT --> TECH
    TECH --> DIPLO
    DIPLO --> RELIGION
    INTERVENE -->|causal mutation| WORLD
    INTERVENE -->|causal mutation| AGENT
    INTERVENE -->|causal mutation| FACTION
    PLUGIN -->|validated causal commands| WORLD
    PLUGIN -->|validated causal commands| AGENT

    WORLD -. metric observation .-> OBS
    AGENT -. event and metric observation .-> OBS
    FACTION -. event and metric observation .-> OBS
    ECON -. event and metric observation .-> OBS
    COMBAT -. event and metric observation .-> OBS
    SOCIAL -. hash/on-demand only .-> HASH
    COAL -. hash/on-demand only .-> HASH
    LANG -. hash/on-demand only .-> HASH
    WORLD -. selected state .-> HASH
    AGENT -. selected state .-> HASH
    FACTION -. selected state .-> HASH
    ECON -. selected state .-> HASH
    COMBAT -. selected state .-> HASH
    CLI -. hashed controls .-> HASH
    OBS -->|required rows| ART
    OBS -->|logger lifecycle| HEALTH
    ART -->|streaming checksums| INV
    HASH --> MANIFEST
    HEALTH --> MANIFEST
    INV --> MANIFEST
    MANIFEST --> VALIDATE
    ART --> VALIDATE
    RUNNER -->|launches isolated child| CLI
    RUNNER -->|validates cell| VALIDATE
```

## Edge interpretation

- Solid labeled edges show configuration or causal state flow.
- Dotted edges show observation without intended feedback.
- The selected-state hash is computed directly from authoritative state and
  hashed controls; required CSV contents do not produce it.
- The `COAL -> DIALECT -> LANG` and `COAL/ECON -> CONTACT -> LANG` paths are
  one-way; no language-to-coalition, social, or material edge exists.
- The `AGENT -> INTERGEN -> LANG` path begins only after successful child
  admission. It has no reverse edge into reproduction, population, health,
  resources, factions, or relationships.
- Plugins are causal even though their advertised bridge snapshots are immutable.

See [architecture overview](../architecture/architecture-overview.md) and [system dependency map](../architecture/system-dependency-map.md).
