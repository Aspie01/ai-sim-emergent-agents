"""
config.py — Shared configuration constants for the civilization simulation.
"""

from dataclasses import asdict, dataclass, field
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
DEFAULT_SOCIAL_MEMORY_ENABLED = False
DEFAULT_SOCIAL_PARTNER_BIAS_ENABLED = False
DEFAULT_MAXIMUM_SOCIAL_TIES = 32
DEFAULT_RELATIONSHIP_DECAY_INTERVAL = 25
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
    'raids',
    'combat',
    'technology',
    'diplomacy',
    'religion',
    'mythology',
})

_CONDITION_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')

SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY = (
    'partner_bias_requested_without_social_memory'
)
VALID_SOCIAL_CONTROL_NOTICES = frozenset({
    SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY,
})
VALID_SOCIAL_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})


@dataclass(frozen=True)
class SocialMemoryConfig:
    """Effective social controls passed explicitly to simulation subsystems."""

    social_memory_enabled: bool
    social_partner_bias_enabled: bool
    maximum_social_ties: int
    relationship_decay_interval: int


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
    social_memory_enabled: bool = DEFAULT_SOCIAL_MEMORY_ENABLED
    social_partner_bias_enabled: bool = DEFAULT_SOCIAL_PARTNER_BIAS_ENABLED
    maximum_social_ties: int = DEFAULT_MAXIMUM_SOCIAL_TIES
    relationship_decay_interval: int = DEFAULT_RELATIONSHIP_DECAY_INTERVAL
    social_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        notices: list[str] = []
        if not self.social_memory_enabled and self.social_partner_bias_enabled:
            object.__setattr__(self, 'social_partner_bias_enabled', False)
            notices.append(SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY)
        object.__setattr__(self, 'social_control_notices', tuple(notices))

    @classmethod
    def from_cli(cls, args) -> 'SimulationConfig':
        disabled_set = {
            layer.strip()
            for layer in args.disable_layer.split(',')
            if layer.strip()
        }
        if getattr(args, 'disable_raids', False):
            disabled_set.add('raids')
        disabled = tuple(sorted(disabled_set))
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
            social_memory_enabled=(
                bool(getattr(args, 'enable_social_memory', False))
                and not bool(getattr(args, 'disable_social_memory', False))
            ),
            social_partner_bias_enabled=(
                bool(getattr(args, 'enable_social_partner_bias', False))
                and not bool(getattr(args, 'disable_social_partner_bias', False))
            ),
            maximum_social_ties=(
                DEFAULT_MAXIMUM_SOCIAL_TIES
                if getattr(args, 'maximum_social_ties', None) is None
                else args.maximum_social_ties
            ),
            relationship_decay_interval=(
                DEFAULT_RELATIONSHIP_DECAY_INTERVAL
                if getattr(args, 'relationship_decay_interval', None) is None
                else args.relationship_decay_interval
            ),
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
        if type(self.social_memory_enabled) is not bool:
            raise ValueError('social memory setting must be boolean')
        if type(self.social_partner_bias_enabled) is not bool:
            raise ValueError('social partner bias setting must be boolean')
        if self.social_partner_bias_enabled and not self.social_memory_enabled:
            raise ValueError('social partner bias requires social memory')
        if (
            type(self.maximum_social_ties) is not int
            or not 1 <= self.maximum_social_ties <= 128
        ):
            raise ValueError('maximum social ties must be an integer from 1 to 128')
        if (
            type(self.relationship_decay_interval) is not int
            or self.relationship_decay_interval < 1
        ):
            raise ValueError('relationship decay interval must be a positive integer')
        if any(
            notice not in VALID_SOCIAL_CONTROL_NOTICES
            for notice in self.social_control_notices
        ):
            raise ValueError('unknown social control normalization notice')

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

    @property
    def raids_enabled(self) -> bool:
        """Whether hostile economy-layer raids run for this configuration."""
        return 'raids' not in self.disabled_layers

    def manifest_dict(self) -> dict:
        result = asdict(self)
        result.pop('social_control_notices', None)
        result['disabled_layers'] = list(self.disabled_layers)
        result['raids_enabled'] = self.raids_enabled
        result['social_control_notices'] = list(self.social_control_notices)
        result['social_controls_status'] = self.social_controls_status
        return result

    @property
    def social_controls_status(self) -> str:
        """Return bounded provenance status for the uncontracted social controls."""
        if self.social_control_notices:
            return 'normalized_uncontracted'
        if (
            self.social_memory_enabled
            or self.social_partner_bias_enabled
            or self.maximum_social_ties != DEFAULT_MAXIMUM_SOCIAL_TIES
            or self.relationship_decay_interval
            != DEFAULT_RELATIONSHIP_DECAY_INTERVAL
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def social_memory_config(self) -> SocialMemoryConfig:
        """Return the immutable effective controls used by social subsystems."""
        return SocialMemoryConfig(
            social_memory_enabled=self.social_memory_enabled,
            social_partner_bias_enabled=self.social_partner_bias_enabled,
            maximum_social_ties=self.maximum_social_ties,
            relationship_decay_interval=self.relationship_decay_interval,
        )
