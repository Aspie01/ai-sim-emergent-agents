"""
config.py — Shared configuration constants for the civilization simulation.
"""

from dataclasses import asdict, dataclass, field
import math
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
DEFAULT_LANGUAGE_EVOLUTION_ENABLED = False
DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS = 32
DEFAULT_MAXIMUM_SIGNAL_LENGTH = 3
DEFAULT_LANGUAGE_LEARNING_RATE = 0.20
DEFAULT_LANGUAGE_REINFORCEMENT_RATE = 0.10
DEFAULT_LANGUAGE_FORGETTING_INTERVAL = 25
DEFAULT_LANGUAGE_INVENTION_ENABLED = True
DEFAULT_COALITION_EMERGENCE_ENABLED = False
DEFAULT_COALITION_MINIMUM_SIZE = 3
DEFAULT_COALITION_TRUST_THRESHOLD = 0.24
DEFAULT_COALITION_FAMILIARITY_THRESHOLD = 0.40
DEFAULT_COALITION_MAXIMUM_GRIEVANCE = 0.20
DEFAULT_COALITION_PERSISTENCE_TICKS = 5
DEFAULT_MAXIMUM_ACTIVE_COALITIONS = 32
DEFAULT_COALITION_DIALECT_INFLUENCE_ENABLED = False
DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER = 1.50
DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER = 1.25
DEFAULT_LANGUAGE_CONTACT_ENABLED = False
DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER = 1.50
DEFAULT_BORROWING_EXPOSURE_THRESHOLD = 3
DEFAULT_BORROWING_CONFIDENCE_THRESHOLD = 0.50
DEFAULT_INTERGENERATIONAL_LANGUAGE_ENABLED = False
DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT = 2
DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH = 0.20
MAXIMUM_INTERGENERATIONAL_MEANINGS = 4
DEFAULT_LEXICAL_EVOLUTION_ENABLED = False
DEFAULT_LEXICAL_MUTATION_RATE = 0.05
DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH = 8
MAXIMUM_LEXICAL_LINEAGE_DEPTH = 32
DEFAULT_COMPOSITIONAL_PROTOLANGUAGE_ENABLED = False
DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH = 2
DEFAULT_MODALITY_MORPHEME_LENGTH = 1
MAXIMUM_RESOURCE_MORPHEME_LENGTH = 3
MAXIMUM_MODALITY_MORPHEME_LENGTH = 2
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

VALID_LANGUAGE_CONTROL_NOTICES = frozenset()
VALID_LANGUAGE_CONTROL_STATUSES = frozenset({
    'disabled',
    'engineering_only_uncontracted',
})

COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY = (
    'coalition_emergence_requested_without_social_memory'
)
VALID_COALITION_CONTROL_NOTICES = frozenset({
    COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY,
})
VALID_COALITION_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})

DIALECT_NOTICE_WITHOUT_LANGUAGE = (
    'dialect_influence_requested_without_language'
)
DIALECT_NOTICE_WITHOUT_COALITIONS = (
    'dialect_influence_requested_without_coalitions'
)
VALID_DIALECT_CONTROL_NOTICES = frozenset({
    DIALECT_NOTICE_WITHOUT_LANGUAGE,
    DIALECT_NOTICE_WITHOUT_COALITIONS,
})
VALID_DIALECT_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})

LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE = (
    'language_contact_requested_without_language'
)
LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS = (
    'language_contact_requested_without_coalitions'
)
VALID_LANGUAGE_CONTACT_CONTROL_NOTICES = frozenset({
    LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
})
VALID_LANGUAGE_CONTACT_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})

INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE = (
    'intergenerational_language_requested_without_language'
)
VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_NOTICES = frozenset({
    INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
})
VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})

LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE = (
    'lexical_evolution_requested_without_language'
)
VALID_LEXICAL_EVOLUTION_CONTROL_NOTICES = frozenset({
    LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE,
})
VALID_LEXICAL_EVOLUTION_CONTROL_STATUSES = frozenset({
    'disabled',
    'normalized_uncontracted',
    'engineering_only_uncontracted',
})

COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE = (
    'compositional_protolanguage_requested_without_language'
)
VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_NOTICES = frozenset({
    COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE,
})
VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_STATUSES = frozenset({
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
class LanguageEvolutionConfig:
    """Effective engineering-only controls for protolanguage evolution."""

    language_evolution_enabled: bool
    maximum_language_associations: int
    maximum_signal_length: int
    language_learning_rate: float
    language_reinforcement_rate: float
    language_forgetting_interval: int
    language_invention_enabled: bool


@dataclass(frozen=True)
class CoalitionConfig:
    """Effective engineering-only controls for informal coalition emergence."""

    coalition_emergence_enabled: bool
    coalition_minimum_size: int
    coalition_trust_threshold: float
    coalition_familiarity_threshold: float
    coalition_maximum_grievance: float
    coalition_persistence_ticks: int
    maximum_active_coalitions: int


@dataclass(frozen=True)
class CoalitionDialectConfig:
    """Effective engineering-only coalition-to-language controls."""

    coalition_dialect_influence_enabled: bool
    same_coalition_learning_multiplier: float
    same_coalition_reinforcement_multiplier: float


@dataclass(frozen=True)
class LanguageContactConfig:
    """Effective engineering-only cross-coalition language controls."""

    language_contact_enabled: bool
    cross_group_learning_multiplier: float
    borrowing_exposure_threshold: int
    borrowing_confidence_threshold: float


@dataclass(frozen=True)
class IntergenerationalLanguageConfig:
    """Effective engineering-only parental-language controls."""

    intergenerational_language_enabled: bool
    maximum_parental_meanings_per_parent: int
    intergenerational_learning_strength: float


@dataclass(frozen=True)
class LexicalEvolutionConfig:
    """Effective engineering-only lexical mutation controls."""

    lexical_evolution_enabled: bool
    lexical_mutation_rate: float
    maximum_lexical_lineage_depth: int


@dataclass(frozen=True)
class CompositionalProtolanguageConfig:
    """Effective engineering-only structured-meaning composition controls."""

    compositional_protolanguage_enabled: bool
    maximum_resource_morpheme_length: int
    modality_morpheme_length: int


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
    language_evolution_enabled: bool = DEFAULT_LANGUAGE_EVOLUTION_ENABLED
    maximum_language_associations: int = (
        DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS
    )
    maximum_signal_length: int = DEFAULT_MAXIMUM_SIGNAL_LENGTH
    language_learning_rate: float = DEFAULT_LANGUAGE_LEARNING_RATE
    language_reinforcement_rate: float = DEFAULT_LANGUAGE_REINFORCEMENT_RATE
    language_forgetting_interval: int = DEFAULT_LANGUAGE_FORGETTING_INTERVAL
    language_invention_enabled: bool = DEFAULT_LANGUAGE_INVENTION_ENABLED
    coalition_emergence_enabled: bool = DEFAULT_COALITION_EMERGENCE_ENABLED
    coalition_minimum_size: int = DEFAULT_COALITION_MINIMUM_SIZE
    coalition_trust_threshold: float = DEFAULT_COALITION_TRUST_THRESHOLD
    coalition_familiarity_threshold: float = (
        DEFAULT_COALITION_FAMILIARITY_THRESHOLD
    )
    coalition_maximum_grievance: float = DEFAULT_COALITION_MAXIMUM_GRIEVANCE
    coalition_persistence_ticks: int = DEFAULT_COALITION_PERSISTENCE_TICKS
    maximum_active_coalitions: int = DEFAULT_MAXIMUM_ACTIVE_COALITIONS
    coalition_dialect_influence_enabled: bool = (
        DEFAULT_COALITION_DIALECT_INFLUENCE_ENABLED
    )
    same_coalition_learning_multiplier: float = (
        DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER
    )
    same_coalition_reinforcement_multiplier: float = (
        DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER
    )
    language_contact_enabled: bool = DEFAULT_LANGUAGE_CONTACT_ENABLED
    cross_group_learning_multiplier: float = (
        DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER
    )
    borrowing_exposure_threshold: int = (
        DEFAULT_BORROWING_EXPOSURE_THRESHOLD
    )
    borrowing_confidence_threshold: float = (
        DEFAULT_BORROWING_CONFIDENCE_THRESHOLD
    )
    intergenerational_language_enabled: bool = (
        DEFAULT_INTERGENERATIONAL_LANGUAGE_ENABLED
    )
    maximum_parental_meanings_per_parent: int = (
        DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT
    )
    intergenerational_learning_strength: float = (
        DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH
    )
    lexical_evolution_enabled: bool = DEFAULT_LEXICAL_EVOLUTION_ENABLED
    lexical_mutation_rate: float = DEFAULT_LEXICAL_MUTATION_RATE
    maximum_lexical_lineage_depth: int = (
        DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH
    )
    compositional_protolanguage_enabled: bool = (
        DEFAULT_COMPOSITIONAL_PROTOLANGUAGE_ENABLED
    )
    maximum_resource_morpheme_length: int = (
        DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH
    )
    modality_morpheme_length: int = DEFAULT_MODALITY_MORPHEME_LENGTH
    social_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    language_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    coalition_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    dialect_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    language_contact_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    intergenerational_language_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    lexical_evolution_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)
    compositional_protolanguage_control_notices: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        notices: list[str] = []
        if not self.social_memory_enabled and self.social_partner_bias_enabled:
            object.__setattr__(self, 'social_partner_bias_enabled', False)
            notices.append(SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY)
        object.__setattr__(
            self, 'social_control_notices', tuple(sorted(notices)))

        object.__setattr__(self, 'language_control_notices', ())

        coalition_notices: list[str] = []
        if (
            self.social_memory_enabled is False
            and self.coalition_emergence_enabled is True
        ):
            object.__setattr__(self, 'coalition_emergence_enabled', False)
            coalition_notices.append(
                COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY)
        object.__setattr__(
            self,
            'coalition_control_notices',
            tuple(sorted(coalition_notices)),
        )

        dialect_notices: list[str] = []
        if self.coalition_dialect_influence_enabled is True:
            if self.language_evolution_enabled is False:
                dialect_notices.append(DIALECT_NOTICE_WITHOUT_LANGUAGE)
            if self.coalition_emergence_enabled is False:
                dialect_notices.append(DIALECT_NOTICE_WITHOUT_COALITIONS)
            if dialect_notices:
                object.__setattr__(
                    self, 'coalition_dialect_influence_enabled', False)
        object.__setattr__(
            self,
            'dialect_control_notices',
            tuple(sorted(dialect_notices)),
        )

        contact_notices: list[str] = []
        if self.language_contact_enabled is True:
            if self.language_evolution_enabled is False:
                contact_notices.append(
                    LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE)
            if self.coalition_emergence_enabled is False:
                contact_notices.append(
                    LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS)
            if contact_notices:
                object.__setattr__(self, 'language_contact_enabled', False)
        object.__setattr__(
            self,
            'language_contact_control_notices',
            tuple(sorted(contact_notices)),
        )

        intergenerational_notices: list[str] = []
        if (
            self.intergenerational_language_enabled is True
            and self.language_evolution_enabled is False
        ):
            object.__setattr__(
                self, 'intergenerational_language_enabled', False)
            intergenerational_notices.append(
                INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE)
        object.__setattr__(
            self,
            'intergenerational_language_control_notices',
            tuple(sorted(intergenerational_notices)),
        )

        lexical_notices: list[str] = []
        if (
            self.lexical_evolution_enabled is True
            and self.language_evolution_enabled is False
        ):
            object.__setattr__(self, 'lexical_evolution_enabled', False)
            lexical_notices.append(
                LEXICAL_EVOLUTION_NOTICE_WITHOUT_LANGUAGE)
        object.__setattr__(
            self,
            'lexical_evolution_control_notices',
            tuple(sorted(lexical_notices)),
        )

        compositional_notices: list[str] = []
        if (
            self.compositional_protolanguage_enabled is True
            and self.language_evolution_enabled is False
        ):
            object.__setattr__(
                self, 'compositional_protolanguage_enabled', False)
            compositional_notices.append(
                COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE)
        object.__setattr__(
            self,
            'compositional_protolanguage_control_notices',
            tuple(sorted(compositional_notices)),
        )

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
            language_evolution_enabled=(
                bool(getattr(args, 'enable_language_evolution', False))
                and not bool(getattr(args, 'disable_language_evolution', False))
            ),
            maximum_language_associations=(
                DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS
                if getattr(args, 'maximum_language_associations', None) is None
                else args.maximum_language_associations
            ),
            maximum_signal_length=(
                DEFAULT_MAXIMUM_SIGNAL_LENGTH
                if getattr(args, 'maximum_signal_length', None) is None
                else args.maximum_signal_length
            ),
            language_learning_rate=(
                DEFAULT_LANGUAGE_LEARNING_RATE
                if getattr(args, 'language_learning_rate', None) is None
                else args.language_learning_rate
            ),
            language_reinforcement_rate=(
                DEFAULT_LANGUAGE_REINFORCEMENT_RATE
                if getattr(args, 'language_reinforcement_rate', None) is None
                else args.language_reinforcement_rate
            ),
            language_forgetting_interval=(
                DEFAULT_LANGUAGE_FORGETTING_INTERVAL
                if getattr(args, 'language_forgetting_interval', None) is None
                else args.language_forgetting_interval
            ),
            language_invention_enabled=(
                not bool(getattr(args, 'disable_language_invention', False))
                if not bool(getattr(args, 'enable_language_invention', False))
                else True
            ),
            coalition_emergence_enabled=(
                bool(getattr(args, 'enable_coalition_emergence', False))
                and not bool(getattr(args, 'disable_coalition_emergence', False))
            ),
            coalition_minimum_size=(
                DEFAULT_COALITION_MINIMUM_SIZE
                if getattr(args, 'coalition_minimum_size', None) is None
                else args.coalition_minimum_size
            ),
            coalition_trust_threshold=(
                DEFAULT_COALITION_TRUST_THRESHOLD
                if getattr(args, 'coalition_trust_threshold', None) is None
                else args.coalition_trust_threshold
            ),
            coalition_familiarity_threshold=(
                DEFAULT_COALITION_FAMILIARITY_THRESHOLD
                if getattr(args, 'coalition_familiarity_threshold', None) is None
                else args.coalition_familiarity_threshold
            ),
            coalition_maximum_grievance=(
                DEFAULT_COALITION_MAXIMUM_GRIEVANCE
                if getattr(args, 'coalition_maximum_grievance', None) is None
                else args.coalition_maximum_grievance
            ),
            coalition_persistence_ticks=(
                DEFAULT_COALITION_PERSISTENCE_TICKS
                if getattr(args, 'coalition_persistence_ticks', None) is None
                else args.coalition_persistence_ticks
            ),
            maximum_active_coalitions=(
                DEFAULT_MAXIMUM_ACTIVE_COALITIONS
                if getattr(args, 'maximum_active_coalitions', None) is None
                else args.maximum_active_coalitions
            ),
            coalition_dialect_influence_enabled=(
                bool(getattr(
                    args, 'enable_coalition_dialect_influence', False))
                and not bool(getattr(
                    args, 'disable_coalition_dialect_influence', False))
            ),
            same_coalition_learning_multiplier=(
                DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER
                if getattr(
                    args, 'same_coalition_learning_multiplier', None) is None
                else args.same_coalition_learning_multiplier
            ),
            same_coalition_reinforcement_multiplier=(
                DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER
                if getattr(
                    args,
                    'same_coalition_reinforcement_multiplier',
                    None,
                ) is None
                else args.same_coalition_reinforcement_multiplier
            ),
            language_contact_enabled=(
                bool(getattr(args, 'enable_language_contact', False))
                and not bool(getattr(args, 'disable_language_contact', False))
            ),
            cross_group_learning_multiplier=(
                DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER
                if getattr(
                    args, 'cross_group_learning_multiplier', None) is None
                else args.cross_group_learning_multiplier
            ),
            borrowing_exposure_threshold=(
                DEFAULT_BORROWING_EXPOSURE_THRESHOLD
                if getattr(
                    args, 'borrowing_exposure_threshold', None) is None
                else args.borrowing_exposure_threshold
            ),
            borrowing_confidence_threshold=(
                DEFAULT_BORROWING_CONFIDENCE_THRESHOLD
                if getattr(
                    args, 'borrowing_confidence_threshold', None) is None
                else args.borrowing_confidence_threshold
            ),
            intergenerational_language_enabled=(
                bool(getattr(
                    args, 'enable_intergenerational_language', False))
                and not bool(getattr(
                    args, 'disable_intergenerational_language', False))
            ),
            maximum_parental_meanings_per_parent=(
                DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT
                if getattr(
                    args,
                    'maximum_parental_meanings_per_parent',
                    None,
                ) is None
                else args.maximum_parental_meanings_per_parent
            ),
            intergenerational_learning_strength=(
                DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH
                if getattr(
                    args,
                    'intergenerational_learning_strength',
                    None,
                ) is None
                else args.intergenerational_learning_strength
            ),
            lexical_evolution_enabled=(
                bool(getattr(args, 'enable_lexical_evolution', False))
                and not bool(getattr(
                    args, 'disable_lexical_evolution', False))
            ),
            lexical_mutation_rate=(
                DEFAULT_LEXICAL_MUTATION_RATE
                if getattr(args, 'lexical_mutation_rate', None) is None
                else args.lexical_mutation_rate
            ),
            maximum_lexical_lineage_depth=(
                DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH
                if getattr(
                    args, 'maximum_lexical_lineage_depth', None) is None
                else args.maximum_lexical_lineage_depth
            ),
            compositional_protolanguage_enabled=(
                bool(getattr(
                    args, 'enable_compositional_protolanguage', False))
                and not bool(getattr(
                    args, 'disable_compositional_protolanguage', False))
            ),
            maximum_resource_morpheme_length=(
                DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH
                if getattr(
                    args, 'maximum_resource_morpheme_length', None) is None
                else args.maximum_resource_morpheme_length
            ),
            modality_morpheme_length=(
                DEFAULT_MODALITY_MORPHEME_LENGTH
                if getattr(args, 'modality_morpheme_length', None) is None
                else args.modality_morpheme_length
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
        if type(self.language_evolution_enabled) is not bool:
            raise ValueError('language evolution setting must be boolean')
        if (
            type(self.maximum_language_associations) is not int
            or not 1 <= self.maximum_language_associations <= 40
        ):
            raise ValueError(
                'maximum language associations must be an integer from 1 to 40')
        if (
            type(self.maximum_signal_length) is not int
            or not 2 <= self.maximum_signal_length <= 4
        ):
            raise ValueError('maximum signal length must be an integer from 2 to 4')
        for value, label in (
            (self.language_learning_rate, 'language learning rate'),
            (self.language_reinforcement_rate, 'language reinforcement rate'),
        ):
            if (
                type(value) is not float
                or not math.isfinite(value)
                or not 0.0 < value <= 1.0
            ):
                raise ValueError(f'{label} must be a finite float in (0.0, 1.0]')
        if (
            type(self.language_forgetting_interval) is not int
            or self.language_forgetting_interval < 1
        ):
            raise ValueError(
                'language forgetting interval must be a positive integer')
        if type(self.language_invention_enabled) is not bool:
            raise ValueError('language invention setting must be boolean')
        if self.language_control_notices:
            raise ValueError('language control notices are not defined in v1')
        if type(self.coalition_emergence_enabled) is not bool:
            raise ValueError('coalition emergence setting must be boolean')
        if (
            type(self.coalition_minimum_size) is not int
            or not 3 <= self.coalition_minimum_size <= 1024
        ):
            raise ValueError(
                'coalition minimum size must be an integer from 3 to 1024')
        for value, label in (
            (self.coalition_trust_threshold, 'coalition trust threshold'),
            (self.coalition_familiarity_threshold, 'coalition familiarity threshold'),
            (self.coalition_maximum_grievance, 'coalition maximum grievance'),
        ):
            if (
                type(value) is not float
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f'{label} must be a finite float from 0.0 to 1.0')
        if (
            type(self.coalition_persistence_ticks) is not int
            or self.coalition_persistence_ticks < 2
        ):
            raise ValueError(
                'coalition persistence ticks must be an integer of at least 2')
        if (
            type(self.maximum_active_coalitions) is not int
            or not 1 <= self.maximum_active_coalitions <= 1024
        ):
            raise ValueError(
                'maximum active coalitions must be an integer from 1 to 1024')
        if any(
            notice not in VALID_COALITION_CONTROL_NOTICES
            for notice in self.coalition_control_notices
        ):
            raise ValueError('unknown coalition control normalization notice')
        if type(self.coalition_dialect_influence_enabled) is not bool:
            raise ValueError('coalition dialect influence setting must be boolean')
        if self.coalition_dialect_influence_enabled and (
            not self.language_evolution_enabled
            or not self.coalition_emergence_enabled
        ):
            raise ValueError(
                'coalition dialect influence requires language evolution and '
                'coalition emergence')
        for value, label in (
            (
                self.same_coalition_learning_multiplier,
                'same-coalition learning multiplier',
            ),
            (
                self.same_coalition_reinforcement_multiplier,
                'same-coalition reinforcement multiplier',
            ),
        ):
            if (
                type(value) is not float
                or not math.isfinite(value)
                or not 1.0 <= value <= 2.0
            ):
                raise ValueError(
                    f'{label} must be a finite float from 1.0 to 2.0')
        if any(
            notice not in VALID_DIALECT_CONTROL_NOTICES
            for notice in self.dialect_control_notices
        ):
            raise ValueError('unknown dialect control normalization notice')
        if self.dialect_control_notices and (
            self.coalition_dialect_influence_enabled
        ):
            raise ValueError(
                'dialect normalization notices require disabled influence')
        if type(self.language_contact_enabled) is not bool:
            raise ValueError('language contact setting must be boolean')
        if self.language_contact_enabled and (
            not self.language_evolution_enabled
            or not self.coalition_emergence_enabled
        ):
            raise ValueError(
                'language contact requires language evolution and coalition '
                'emergence')
        if (
            type(self.cross_group_learning_multiplier) is not float
            or not math.isfinite(self.cross_group_learning_multiplier)
            or not 1.0 <= self.cross_group_learning_multiplier <= 2.0
        ):
            raise ValueError(
                'cross-group learning multiplier must be a finite float from '
                '1.0 to 2.0')
        if (
            type(self.borrowing_exposure_threshold) is not int
            or not 2 <= self.borrowing_exposure_threshold <= 32
        ):
            raise ValueError(
                'borrowing exposure threshold must be an integer from 2 to 32')
        if (
            type(self.borrowing_confidence_threshold) is not float
            or not math.isfinite(self.borrowing_confidence_threshold)
            or not 0.10 <= self.borrowing_confidence_threshold <= 1.0
        ):
            raise ValueError(
                'borrowing confidence threshold must be a finite float from '
                '0.10 to 1.0')
        if any(
            notice not in VALID_LANGUAGE_CONTACT_CONTROL_NOTICES
            for notice in self.language_contact_control_notices
        ):
            raise ValueError(
                'unknown language contact control normalization notice')
        if (
            self.language_contact_control_notices
            and self.language_contact_enabled
        ):
            raise ValueError(
                'language contact normalization notices require disabled contact')
        if type(self.intergenerational_language_enabled) is not bool:
            raise ValueError(
                'intergenerational language setting must be boolean')
        if (
            self.intergenerational_language_enabled
            and not self.language_evolution_enabled
        ):
            raise ValueError(
                'intergenerational language requires language evolution')
        if (
            type(self.maximum_parental_meanings_per_parent) is not int
            or not 1
            <= self.maximum_parental_meanings_per_parent
            <= MAXIMUM_INTERGENERATIONAL_MEANINGS
        ):
            raise ValueError(
                'maximum parental meanings per parent must be an integer '
                f'from 1 to {MAXIMUM_INTERGENERATIONAL_MEANINGS}')
        if (
            type(self.intergenerational_learning_strength) is not float
            or not math.isfinite(self.intergenerational_learning_strength)
            or not 0.0 < self.intergenerational_learning_strength <= 1.0
        ):
            raise ValueError(
                'intergenerational learning strength must be a finite float '
                'in (0.0, 1.0]')
        if any(
            notice not in VALID_INTERGENERATIONAL_LANGUAGE_CONTROL_NOTICES
            for notice in self.intergenerational_language_control_notices
        ):
            raise ValueError(
                'unknown intergenerational language normalization notice')
        if (
            self.intergenerational_language_control_notices
            and self.intergenerational_language_enabled
        ):
            raise ValueError(
                'intergenerational language normalization notices require '
                'disabled transmission')
        if type(self.lexical_evolution_enabled) is not bool:
            raise ValueError('lexical evolution setting must be boolean')
        if (
            self.lexical_evolution_enabled
            and not self.language_evolution_enabled
        ):
            raise ValueError('lexical evolution requires language evolution')
        if (
            type(self.lexical_mutation_rate) is not float
            or not math.isfinite(self.lexical_mutation_rate)
            or not 0.0 <= self.lexical_mutation_rate <= 1.0
        ):
            raise ValueError(
                'lexical mutation rate must be a finite float from 0.0 to 1.0')
        if (
            type(self.maximum_lexical_lineage_depth) is not int
            or not 1
            <= self.maximum_lexical_lineage_depth
            <= MAXIMUM_LEXICAL_LINEAGE_DEPTH
        ):
            raise ValueError(
                'maximum lexical lineage depth must be an integer from 1 to '
                f'{MAXIMUM_LEXICAL_LINEAGE_DEPTH}')
        if any(
            notice not in VALID_LEXICAL_EVOLUTION_CONTROL_NOTICES
            for notice in self.lexical_evolution_control_notices
        ):
            raise ValueError(
                'unknown lexical evolution normalization notice')
        if (
            self.lexical_evolution_control_notices
            and self.lexical_evolution_enabled
        ):
            raise ValueError(
                'lexical evolution normalization notices require disabled '
                'lexical evolution')

        if type(self.compositional_protolanguage_enabled) is not bool:
            raise ValueError(
                'compositional protolanguage setting must be boolean')
        if (
            self.compositional_protolanguage_enabled
            and not self.language_evolution_enabled
        ):
            raise ValueError(
                'compositional protolanguage requires language evolution')
        if (
            type(self.maximum_resource_morpheme_length) is not int
            or not 1
            <= self.maximum_resource_morpheme_length
            <= MAXIMUM_RESOURCE_MORPHEME_LENGTH
        ):
            raise ValueError(
                'maximum resource morpheme length must be an integer from 1 '
                f'to {MAXIMUM_RESOURCE_MORPHEME_LENGTH}')
        if (
            type(self.modality_morpheme_length) is not int
            or not 1
            <= self.modality_morpheme_length
            <= MAXIMUM_MODALITY_MORPHEME_LENGTH
        ):
            raise ValueError(
                'modality morpheme length must be an integer from 1 to '
                f'{MAXIMUM_MODALITY_MORPHEME_LENGTH}')
        if (
            self.compositional_protolanguage_enabled
            and self.maximum_resource_morpheme_length
            + self.modality_morpheme_length
            > self.maximum_signal_length
        ):
            raise ValueError(
                'composed morpheme lengths must not exceed the effective '
                'maximum signal length')
        if any(
            notice not in VALID_COMPOSITIONAL_PROTOLANGUAGE_CONTROL_NOTICES
            for notice in self.compositional_protolanguage_control_notices
        ):
            raise ValueError(
                'unknown compositional protolanguage normalization notice')
        if (
            self.compositional_protolanguage_control_notices
            and self.compositional_protolanguage_enabled
        ):
            raise ValueError(
                'compositional protolanguage normalization notices require '
                'disabled compositional protolanguage')

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
        result.pop('language_control_notices', None)
        result.pop('coalition_control_notices', None)
        result.pop('dialect_control_notices', None)
        result.pop('language_contact_control_notices', None)
        result.pop('intergenerational_language_control_notices', None)
        result.pop('lexical_evolution_control_notices', None)
        result.pop('compositional_protolanguage_control_notices', None)
        result['disabled_layers'] = list(self.disabled_layers)
        result['raids_enabled'] = self.raids_enabled
        result['social_control_notices'] = list(self.social_control_notices)
        result['social_controls_status'] = self.social_controls_status
        result['language_control_notices'] = list(
            self.language_control_notices)
        result['language_controls_status'] = self.language_controls_status
        result['coalition_control_notices'] = list(
            self.coalition_control_notices)
        result['coalition_controls_status'] = self.coalition_controls_status
        result['dialect_control_notices'] = list(
            self.dialect_control_notices)
        result['dialect_controls_status'] = self.dialect_controls_status
        result['language_contact_control_notices'] = list(
            self.language_contact_control_notices)
        result['language_contact_controls_status'] = (
            self.language_contact_controls_status)
        result['intergenerational_language_control_notices'] = list(
            self.intergenerational_language_control_notices)
        result['intergenerational_language_controls_status'] = (
            self.intergenerational_language_controls_status)
        result['lexical_evolution_control_notices'] = list(
            self.lexical_evolution_control_notices)
        result['lexical_evolution_controls_status'] = (
            self.lexical_evolution_controls_status)
        result['compositional_protolanguage_control_notices'] = list(
            self.compositional_protolanguage_control_notices)
        result['compositional_protolanguage_controls_status'] = (
            self.compositional_protolanguage_controls_status)
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


    @property
    def language_controls_status(self) -> str:
        """Return provenance status for uncontracted language controls."""
        if (
            self.language_evolution_enabled
            or self.maximum_language_associations
            != DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS
            or self.maximum_signal_length != DEFAULT_MAXIMUM_SIGNAL_LENGTH
            or self.language_learning_rate != DEFAULT_LANGUAGE_LEARNING_RATE
            or self.language_reinforcement_rate
            != DEFAULT_LANGUAGE_REINFORCEMENT_RATE
            or self.language_forgetting_interval
            != DEFAULT_LANGUAGE_FORGETTING_INTERVAL
            or self.language_invention_enabled
            is not DEFAULT_LANGUAGE_INVENTION_ENABLED
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def language_evolution_config(self) -> LanguageEvolutionConfig:
        """Return immutable effective controls for language processing."""
        return LanguageEvolutionConfig(
            language_evolution_enabled=self.language_evolution_enabled,
            maximum_language_associations=self.maximum_language_associations,
            maximum_signal_length=self.maximum_signal_length,
            language_learning_rate=self.language_learning_rate,
            language_reinforcement_rate=self.language_reinforcement_rate,
            language_forgetting_interval=self.language_forgetting_interval,
            language_invention_enabled=self.language_invention_enabled,
        )

    @property
    def coalition_controls_status(self) -> str:
        """Return provenance status for uncontracted coalition controls."""
        if self.coalition_control_notices:
            return 'normalized_uncontracted'
        if (
            self.coalition_emergence_enabled
            or self.coalition_minimum_size != DEFAULT_COALITION_MINIMUM_SIZE
            or self.coalition_trust_threshold
            != DEFAULT_COALITION_TRUST_THRESHOLD
            or self.coalition_familiarity_threshold
            != DEFAULT_COALITION_FAMILIARITY_THRESHOLD
            or self.coalition_maximum_grievance
            != DEFAULT_COALITION_MAXIMUM_GRIEVANCE
            or self.coalition_persistence_ticks
            != DEFAULT_COALITION_PERSISTENCE_TICKS
            or self.maximum_active_coalitions
            != DEFAULT_MAXIMUM_ACTIVE_COALITIONS
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def coalition_config(self) -> CoalitionConfig:
        """Return immutable effective controls for coalition processing."""
        return CoalitionConfig(
            coalition_emergence_enabled=self.coalition_emergence_enabled,
            coalition_minimum_size=self.coalition_minimum_size,
            coalition_trust_threshold=self.coalition_trust_threshold,
            coalition_familiarity_threshold=self.coalition_familiarity_threshold,
            coalition_maximum_grievance=self.coalition_maximum_grievance,
            coalition_persistence_ticks=self.coalition_persistence_ticks,
            maximum_active_coalitions=self.maximum_active_coalitions,
        )

    @property
    def dialect_controls_status(self) -> str:
        """Return provenance status for uncontracted dialect controls."""
        if self.dialect_control_notices:
            return 'normalized_uncontracted'
        if (
            self.coalition_dialect_influence_enabled
            or self.same_coalition_learning_multiplier
            != DEFAULT_SAME_COALITION_LEARNING_MULTIPLIER
            or self.same_coalition_reinforcement_multiplier
            != DEFAULT_SAME_COALITION_REINFORCEMENT_MULTIPLIER
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def coalition_dialect_config(self) -> CoalitionDialectConfig:
        """Return immutable effective coalition-dialect controls."""
        return CoalitionDialectConfig(
            coalition_dialect_influence_enabled=(
                self.coalition_dialect_influence_enabled
            ),
            same_coalition_learning_multiplier=(
                self.same_coalition_learning_multiplier
            ),
            same_coalition_reinforcement_multiplier=(
                self.same_coalition_reinforcement_multiplier
            ),
        )

    @property
    def language_contact_controls_status(self) -> str:
        """Return provenance status for uncontracted contact controls."""
        if self.language_contact_control_notices:
            return 'normalized_uncontracted'
        if (
            self.language_contact_enabled
            or self.cross_group_learning_multiplier
            != DEFAULT_CROSS_GROUP_LEARNING_MULTIPLIER
            or self.borrowing_exposure_threshold
            != DEFAULT_BORROWING_EXPOSURE_THRESHOLD
            or self.borrowing_confidence_threshold
            != DEFAULT_BORROWING_CONFIDENCE_THRESHOLD
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def language_contact_config(self) -> LanguageContactConfig:
        """Return immutable effective language-contact controls."""
        return LanguageContactConfig(
            language_contact_enabled=self.language_contact_enabled,
            cross_group_learning_multiplier=(
                self.cross_group_learning_multiplier),
            borrowing_exposure_threshold=self.borrowing_exposure_threshold,
            borrowing_confidence_threshold=(
                self.borrowing_confidence_threshold),
        )

    @property
    def intergenerational_language_controls_status(self) -> str:
        """Return provenance status for uncontracted parental transmission."""
        if self.intergenerational_language_control_notices:
            return 'normalized_uncontracted'
        if (
            self.intergenerational_language_enabled
            or self.maximum_parental_meanings_per_parent
            != DEFAULT_MAXIMUM_PARENTAL_MEANINGS_PER_PARENT
            or self.intergenerational_learning_strength
            != DEFAULT_INTERGENERATIONAL_LEARNING_STRENGTH
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def intergenerational_language_config(
        self,
    ) -> IntergenerationalLanguageConfig:
        """Return immutable effective parental-language controls."""
        return IntergenerationalLanguageConfig(
            intergenerational_language_enabled=(
                self.intergenerational_language_enabled),
            maximum_parental_meanings_per_parent=(
                self.maximum_parental_meanings_per_parent),
            intergenerational_learning_strength=(
                self.intergenerational_learning_strength),
        )

    @property
    def lexical_evolution_controls_status(self) -> str:
        """Return provenance status for uncontracted lexical controls."""
        if self.lexical_evolution_control_notices:
            return 'normalized_uncontracted'
        if (
            self.lexical_evolution_enabled
            or self.lexical_mutation_rate != DEFAULT_LEXICAL_MUTATION_RATE
            or self.maximum_lexical_lineage_depth
            != DEFAULT_MAXIMUM_LEXICAL_LINEAGE_DEPTH
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def lexical_evolution_config(self) -> LexicalEvolutionConfig:
        """Return immutable effective lexical mutation controls."""
        return LexicalEvolutionConfig(
            lexical_evolution_enabled=self.lexical_evolution_enabled,
            lexical_mutation_rate=self.lexical_mutation_rate,
            maximum_lexical_lineage_depth=(
                self.maximum_lexical_lineage_depth),
        )

    @property
    def compositional_protolanguage_controls_status(self) -> str:
        """Return provenance status for uncontracted compositional controls."""
        if self.compositional_protolanguage_control_notices:
            return 'normalized_uncontracted'
        if (
            self.compositional_protolanguage_enabled
            or self.maximum_resource_morpheme_length
            != DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH
            or self.modality_morpheme_length
            != DEFAULT_MODALITY_MORPHEME_LENGTH
        ):
            return 'engineering_only_uncontracted'
        return 'disabled'

    @property
    def compositional_protolanguage_config(
        self,
    ) -> CompositionalProtolanguageConfig:
        """Return immutable effective structured-meaning composition controls."""
        return CompositionalProtolanguageConfig(
            compositional_protolanguage_enabled=(
                self.compositional_protolanguage_enabled),
            maximum_resource_morpheme_length=(
                self.maximum_resource_morpheme_length),
            modality_morpheme_length=self.modality_morpheme_length,
        )
