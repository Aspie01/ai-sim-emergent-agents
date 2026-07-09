"""
config.py — Shared configuration constants for the civilization simulation.
"""

from dataclasses import asdict, dataclass
import re

# ── Ollama / LLM settings ─────────────────────────────────────────────────
GAME_MODEL       = "phi3:3.8b-mini-4k-instruct-q4_0"      # Fast, for agent decisions
NARRATIVE_MODEL  = "internlm2:1.8b-chat-v2.5-q4_K_M"          # Quality, for mythology only
OLLAMA_URL       = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT   = 150           # seconds per LLM call
MYTHOLOGY_ENABLED = False       # set True to enable LLM chronicle layer

# ── Simulation length ───────────────────────────────────────────────────
DEFAULT_TICKS = 5000
TICKS = DEFAULT_TICKS    # mutable compatibility alias

# ── Population cap ──────────────────────────────────────────────────────
DEFAULT_POP_CAP = 1000
POP_CAP = DEFAULT_POP_CAP   # mutable compatibility alias

# ── LLM generation parameters ────────────────────────────────────────────
LLM_TEMPERATURE  = 0.7
LLM_MAX_TOKENS   = 200   # default; overridden per-call          # num_predict passed to Ollama

# ── Plugin system ────────────────────────────────────────────────────────
PLUGINS_DIR          = 'plugins'      # directory scanned by load_plugins()
PLUGIN_TICK_INTERVAL = 10             # default cadence; each plugin can override via tick_interval

# ── Experimentally tuneable parameters ──────────────────────────────────
# These are the **current** defaults extracted from the hardcoded values in
# factions.py, combat.py, beliefs.py, and sim.py.  CLI arguments in run()
# override them at runtime so the sim is identical when none are passed.
DEFAULT_FACTION_TRUST_THRESHOLD = 5
DEFAULT_WAR_TENSION_THRESHOLD = 200
DEFAULT_BELIEF_SHARING_PROBABILITY = 0.5
DEFAULT_STARTING_INHABITANTS = 30
FACTION_TRUST_THRESHOLD = DEFAULT_FACTION_TRUST_THRESHOLD
WAR_TENSION_THRESHOLD = DEFAULT_WAR_TENSION_THRESHOLD
BELIEF_SHARING_PROBABILITY = DEFAULT_BELIEF_SHARING_PROBABILITY
STARTING_INHABITANTS = DEFAULT_STARTING_INHABITANTS

# ── Reverse Assimilation instrumentation ────────────────────────────────
BELIEF_TRACKING_ENABLED = False   # --enable-belief-tracking turns this on

VALID_LOG_MODES = frozenset({
    'full',
    'summary',
    'metrics_only',
    'off',
})

VALID_DISABLE_LAYERS = frozenset({
    'beliefs',
    'factions',
    'economy',
    'combat',
    'technology',
    'diplomacy',
    'religion',
    'mythology',
})

_CONDITION_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')


@dataclass(frozen=True)
class SimulationConfig:
    """Validated effective configuration for one simulation run."""

    condition: str = 'baseline'
    ticks: int = DEFAULT_TICKS
    population_cap: int = DEFAULT_POP_CAP
    starting_population: int = DEFAULT_STARTING_INHABITANTS
    faction_trust_threshold: int = DEFAULT_FACTION_TRUST_THRESHOLD
    war_tension_threshold: int = DEFAULT_WAR_TENSION_THRESHOLD
    belief_sharing_probability: float = DEFAULT_BELIEF_SHARING_PROBABILITY
    disabled_layers: tuple[str, ...] = ()
    anti_stagnation_enabled: bool = True
    belief_tracking_enabled: bool = False
    log_mode: str = 'full'

    @classmethod
    def from_cli(cls, args) -> 'SimulationConfig':
        disabled = tuple(sorted({
            layer.strip()
            for layer in args.disable_layer.split(',')
            if layer.strip()
        }))
        unknown = set(disabled) - VALID_DISABLE_LAYERS
        if unknown:
            choices = ', '.join(sorted(VALID_DISABLE_LAYERS))
            invalid = ', '.join(sorted(unknown))
            raise ValueError(
                f"unknown disabled layer(s): {invalid}; valid layers: {choices}")

        instance = cls(
            condition=args.condition,
            ticks=DEFAULT_TICKS if args.ticks is None else args.ticks,
            population_cap=(
                DEFAULT_POP_CAP if args.pop_cap is None else args.pop_cap
            ),
            starting_population=(
                DEFAULT_STARTING_INHABITANTS
                if args.starting_pop is None else args.starting_pop
            ),
            faction_trust_threshold=(
                DEFAULT_FACTION_TRUST_THRESHOLD
                if args.faction_trust_threshold is None
                else args.faction_trust_threshold
            ),
            war_tension_threshold=(
                DEFAULT_WAR_TENSION_THRESHOLD
                if args.war_tension_threshold is None
                else args.war_tension_threshold
            ),
            belief_sharing_probability=(
                DEFAULT_BELIEF_SHARING_PROBABILITY
                if args.belief_sharing_prob is None
                else args.belief_sharing_prob
            ),
            disabled_layers=disabled,
            anti_stagnation_enabled=not args.disable_antistag,
            belief_tracking_enabled=args.enable_belief_tracking,
            log_mode=getattr(args, 'log_mode', 'full'),
        )
        instance.validate()
        return instance

    def validate(self) -> None:
        if not _CONDITION_RE.fullmatch(self.condition):
            raise ValueError(
                'condition must be 1-64 filename-safe characters and start '
                'with an ASCII letter or digit')
        if self.ticks < 1:
            raise ValueError('ticks must be at least 1')
        if self.population_cap < 1:
            raise ValueError('population cap must be at least 1')
        if not 1 <= self.starting_population <= self.population_cap:
            raise ValueError(
                'starting population must be between 1 and population cap')
        if self.starting_population > 135:
            raise ValueError('starting population cannot exceed 135 unique base names')
        if self.faction_trust_threshold < 0:
            raise ValueError('faction trust threshold cannot be negative')
        if self.war_tension_threshold < 1:
            raise ValueError('war tension threshold must be at least 1')
        if not 0.0 <= self.belief_sharing_probability <= 1.0:
            raise ValueError('belief sharing probability must be between 0 and 1')
        if self.log_mode not in VALID_LOG_MODES:
            choices = ', '.join(sorted(VALID_LOG_MODES))
            raise ValueError(
                f'log mode must be one of: {choices}')

    def apply_legacy_globals(self) -> None:
        """Keep modules using legacy constants synchronized during migration."""
        global TICKS, POP_CAP, STARTING_INHABITANTS
        global FACTION_TRUST_THRESHOLD, WAR_TENSION_THRESHOLD
        global BELIEF_SHARING_PROBABILITY, BELIEF_TRACKING_ENABLED

        TICKS = self.ticks
        POP_CAP = self.population_cap
        STARTING_INHABITANTS = self.starting_population
        FACTION_TRUST_THRESHOLD = self.faction_trust_threshold
        WAR_TENSION_THRESHOLD = self.war_tension_threshold
        BELIEF_SHARING_PROBABILITY = self.belief_sharing_probability
        BELIEF_TRACKING_ENABLED = self.belief_tracking_enabled

    def manifest_dict(self) -> dict:
        result = asdict(self)
        result['disabled_layers'] = list(self.disabled_layers)
        return result
