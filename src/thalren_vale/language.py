"""Bounded deterministic protolanguage learned from committed transfers.

Language v1 is observational: communication outcomes update only language
state.  Signal invention is counter based and uses one canonical SHA-256
digest; this module imports no random-number generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from enum import Enum
import hashlib
import math
from typing import Iterable, Protocol

from .coalitions import (
    CoalitionCommunicationContext,
    CoalitionMembershipSnapshot,
    classify_coalition_communication,
    validate_coalition_membership_snapshot,
)
from .config import CoalitionDialectConfig, LanguageContactConfig


LANGUAGE_DOMAIN = "thalren-vale:endogenous-language-v1"
PHONEME_COUNT = 8
MIN_SIGNAL_LENGTH = 2
MAX_SIGNAL_LENGTH = 4
MAX_PRODUCTION_SIGNALS_PER_MEANING = 2
MAX_COMPREHENSION_SIGNALS_PER_MEANING = 8
MAX_COMPREHENSION_MEANINGS_PER_SIGNAL = 2
MAX_LANGUAGE_ASSOCIATIONS = 40
MAX_LANGUAGE_COUNTER = (1 << 63) - 1
MIN_USABLE_CONFIDENCE = 0.10
INVENTION_CONFIDENCE = 0.50
PROMOTION_CONFIDENCE = 0.50
PROMOTION_SUCCESS_COUNT = 3


class LanguageInvariantError(ValueError):
    """Raised when canonical language state or a proposed update is invalid."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class Meaning(str, Enum):
    """Closed resource meanings grounded by committed economy transfers."""

    FOOD = "FOOD"
    WOOD = "WOOD"
    ORE = "ORE"
    STONE = "STONE"

    def __hash__(self) -> int:
        """Return a stable small hash independent of salted string hashing."""
        value = 0
        for character in self.name:
            value = value * 37 + ord(character)
        return value


MEANING_ORDER = {meaning: index for index, meaning in enumerate(Meaning)}
RESOURCE_MEANINGS = {
    "food": Meaning.FOOD,
    "wood": Meaning.WOOD,
    "ore": Meaning.ORE,
    "stone": Meaning.STONE,
}


class CommunicationContext(str, Enum):
    """Authentic committed-transfer contexts used by language v1."""

    AID_TRANSFER = "aid_transfer"
    PAID_TRADE = "paid_trade"
    FACTION_TRADE = "faction_trade"


class CommunicationResult(str, Enum):
    """Interpretation result determined before observational learning."""

    SUCCESS = "success"
    MISUNDERSTANDING = "misunderstanding"
    UNKNOWN_SIGNAL = "unknown_signal"
    NO_SIGNAL = "no_signal"


class AssociationOrigin(str, Enum):
    """Bounded provenance for one lexical association."""

    INVENTED = "invented"
    LEARNED = "learned"


@dataclass(frozen=True, slots=True)
class Signal:
    """One canonical abstract signal from a closed phoneme inventory."""

    phoneme_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.phoneme_ids) is not tuple:
            raise LanguageInvariantError(
                "invalid_signal", "phoneme IDs must be an exact tuple")
        if not MIN_SIGNAL_LENGTH <= len(self.phoneme_ids) <= MAX_SIGNAL_LENGTH:
            raise LanguageInvariantError(
                "invalid_signal",
                f"signal length must be {MIN_SIGNAL_LENGTH}..{MAX_SIGNAL_LENGTH}",
            )
        if any(
            type(phoneme_id) is not int
            or not 0 <= phoneme_id < PHONEME_COUNT
            for phoneme_id in self.phoneme_ids
        ):
            raise LanguageInvariantError(
                "invalid_signal",
                f"phoneme IDs must be exact integers from 0 to {PHONEME_COUNT - 1}",
            )

    def __hash__(self) -> int:
        """Return a stable collision-free hash for the bounded signal domain."""
        value = len(self.phoneme_ids)
        for phoneme_id in self.phoneme_ids:
            value = value * (PHONEME_COUNT + 1) + phoneme_id + 1
        return value


@dataclass(frozen=True, slots=True)
class ContactExposure:
    """Bounded first-source facts and cross-coalition comprehension evidence."""

    first_contact_tick: int
    first_source_speaker_id: int
    first_source_coalition_id: int
    exposure_count: int
    successful_comprehension_count: int


@dataclass(frozen=True, slots=True)
class BorrowingProvenance:
    """Immutable historical facts captured when contact activates production."""

    first_contact_tick: int
    first_source_speaker_id: int
    first_source_coalition_id: int
    adoption_tick: int
    adoption_source_speaker_id: int
    adoption_source_coalition_id: int
    exposure_count_at_adoption: int
    successful_comprehension_count_at_adoption: int


@dataclass(frozen=True, slots=True)
class LexicalAssociation:
    """One immutable production or comprehension association."""

    meaning: Meaning
    signal: Signal
    confidence: float
    successful_uses: int = 0
    failed_uses: int = 0
    observation_count: int = 0
    last_used_tick: int = 0
    origin: AssociationOrigin = AssociationOrigin.INVENTED
    learned_from_id: int | None = None
    contact_exposure: ContactExposure | None = None
    borrowing_provenance: BorrowingProvenance | None = None


@dataclass(slots=True)
class AgentLanguageState:
    """Separate bounded production and comprehension state for one agent."""

    production: dict[
        tuple[Meaning, Signal], LexicalAssociation
    ] = field(default_factory=dict)
    comprehension: dict[
        tuple[Signal, Meaning], LexicalAssociation
    ] = field(default_factory=dict)
    next_invention_index: int = 0


@dataclass(slots=True)
class LanguageRuntimeState:
    """Run-scoped language counters and canonical seed-domain identity."""

    seed_domain: str | None = None
    seed_domain_fingerprint: str | None = None
    communication_attempt_count: int = 0
    successful_interpretation_count: int = 0
    misunderstanding_count: int = 0
    unknown_signal_count: int = 0
    no_signal_count: int = 0
    invention_count: int = 0
    learned_association_count: int = 0
    lost_association_count: int = 0
    last_communication_tick: int | None = None
    last_forgetting_tick: int | None = None
    coalition_dialect_influence_enabled: bool = False
    language_contact_enabled: bool = False


@dataclass(slots=True)
class CoalitionDialectRuntimeState:
    """Constant-size attempt partition and adjusted-rate observability."""

    same_coalition_communication_count: int = 0
    different_coalition_communication_count: int = 0
    assigned_unassigned_communication_count: int = 0
    both_unassigned_communication_count: int = 0
    same_coalition_rate_application_count: int = 0
    last_classification_tick: int | None = None


@dataclass(slots=True)
class LanguageContactRuntimeState:
    """Bounded contact controls, attempt subset, and borrowing observability."""

    cross_group_learning_multiplier: float | None = None
    borrowing_exposure_threshold: int | None = None
    borrowing_confidence_threshold: float | None = None
    cross_coalition_contact_attempt_count: int = 0
    cross_coalition_success_count: int = 0
    cross_coalition_misunderstanding_count: int = 0
    cross_coalition_unknown_signal_count: int = 0
    cross_coalition_no_signal_count: int = 0
    cross_group_learning_rate_application_count: int = 0
    borrowing_candidate_creation_count: int = 0
    borrowing_promotion_count: int = 0
    borrowed_production_use_count: int = 0
    last_contact_tick: int | None = None


@dataclass(frozen=True, slots=True)
class CommunicationOutcome:
    """One transient communication result; no outcome history is retained."""

    tick: int
    sender_id: int
    receiver_id: int
    context: CommunicationContext
    intended_meaning: Meaning
    produced_signal: Signal | None
    interpreted_meaning: Meaning | None
    result: CommunicationResult
    coalition_context: CoalitionCommunicationContext | None = None
    sender_coalition_id: int | None = None
    receiver_coalition_id: int | None = None


class LanguageConfig(Protocol):
    """Effective controls required by language operations."""

    language_evolution_enabled: bool
    maximum_language_associations: int
    maximum_signal_length: int
    language_learning_rate: float
    language_reinforcement_rate: float
    language_forgetting_interval: int
    language_invention_enabled: bool


class LanguageInhabitant(Protocol):
    """Minimal stable-identity interface used by the language subsystem."""

    inhabitant_id: int | None
    language: AgentLanguageState


def _raise(code: str, detail: str) -> None:
    raise LanguageInvariantError(code, detail)


def _exact_nonnegative_int(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_LANGUAGE_COUNTER


def _language_state_identity(state: AgentLanguageState) -> int:
    """Return identity used only to reject aliased per-agent language state."""
    return id(state)


def _increment(value: int, *, field_name: str) -> int:
    if not _exact_nonnegative_int(value):
        _raise("invalid_language_counter", f"{field_name} is invalid")
    if value == MAX_LANGUAGE_COUNTER:
        _raise("language_counter_overflow", f"{field_name} cannot be incremented")
    return value + 1


def _saturating_add(value: int, amount: int, *, field_name: str) -> int:
    if not _exact_nonnegative_int(value):
        _raise("invalid_language_counter", f"{field_name} is invalid")
    if type(amount) is not int or amount < 0:
        _raise("invalid_language_counter", f"{field_name} delta is invalid")
    return min(MAX_LANGUAGE_COUNTER, value + amount)


def _quantize(value: float) -> float:
    return round(value, 6)


def _confidence(value: float) -> float:
    return _quantize(max(0.0, min(1.0, value)))


_DIALECT_CONTEXT_COUNTER_FIELDS = {
    CoalitionCommunicationContext.SAME_ACTIVE_COALITION: (
        "same_coalition_communication_count"
    ),
    CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS: (
        "different_coalition_communication_count"
    ),
    CoalitionCommunicationContext.ASSIGNED_UNASSIGNED: (
        "assigned_unassigned_communication_count"
    ),
    CoalitionCommunicationContext.BOTH_UNASSIGNED: (
        "both_unassigned_communication_count"
    ),
}


def validate_coalition_dialect_config(config: object) -> CoalitionDialectConfig:
    """Validate exact effective controls used by dialect communication."""
    if type(config) is not CoalitionDialectConfig:
        _raise("invalid_dialect_config", "dialect config has an invalid exact type")
    if type(config.coalition_dialect_influence_enabled) is not bool:
        _raise("invalid_dialect_config", "dialect influence must be boolean")
    for value, label in (
        (
            config.same_coalition_learning_multiplier,
            "same-coalition learning multiplier",
        ),
        (
            config.same_coalition_reinforcement_multiplier,
            "same-coalition reinforcement multiplier",
        ),
    ):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 1.0 <= value <= 2.0
        ):
            _raise(
                "invalid_dialect_config",
                f"{label} must be a finite float from 1.0 to 2.0",
            )
    return config


def validate_language_contact_config(config: object) -> LanguageContactConfig:
    """Validate exact effective controls used by contact communication."""
    if type(config) is not LanguageContactConfig:
        _raise(
            "invalid_language_contact_config",
            "contact config has an invalid exact type",
        )
    if type(config.language_contact_enabled) is not bool:
        _raise(
            "invalid_language_contact_config",
            "language contact setting must be boolean",
        )
    if (
        type(config.cross_group_learning_multiplier) is not float
        or not math.isfinite(config.cross_group_learning_multiplier)
        or not 1.0 <= config.cross_group_learning_multiplier <= 2.0
    ):
        _raise(
            "invalid_language_contact_config",
            "cross-group learning multiplier must be a finite float from 1.0 to 2.0",
        )
    if (
        type(config.borrowing_exposure_threshold) is not int
        or not 2 <= config.borrowing_exposure_threshold <= 32
    ):
        _raise(
            "invalid_language_contact_config",
            "borrowing exposure threshold must be an integer from 2 to 32",
        )
    if (
        type(config.borrowing_confidence_threshold) is not float
        or not math.isfinite(config.borrowing_confidence_threshold)
        or not 0.10 <= config.borrowing_confidence_threshold <= 1.0
    ):
        _raise(
            "invalid_language_contact_config",
            "borrowing confidence threshold must be a finite float from 0.10 to 1.0",
        )
    return config


_CONTACT_RESULT_COUNTER_FIELDS = (
    "cross_coalition_success_count",
    "cross_coalition_misunderstanding_count",
    "cross_coalition_unknown_signal_count",
    "cross_coalition_no_signal_count",
)


def contact_runtime_is_pristine(runtime: object) -> bool:
    """Return whether contact runtime is exactly disabled and untouched."""
    return type(runtime) is LanguageContactRuntimeState and (
        runtime.cross_group_learning_multiplier is None
        and runtime.borrowing_exposure_threshold is None
        and runtime.borrowing_confidence_threshold is None
        and all(
            type(getattr(runtime, name)) is int and getattr(runtime, name) == 0
            for name in (
                "cross_coalition_contact_attempt_count",
                *_CONTACT_RESULT_COUNTER_FIELDS,
                "cross_group_learning_rate_application_count",
                "borrowing_candidate_creation_count",
                "borrowing_promotion_count",
                "borrowed_production_use_count",
            )
        )
        and runtime.last_contact_tick is None
    )


def validate_language_contact_runtime(
    runtime: object,
    *,
    config: LanguageContactConfig | None = None,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
) -> LanguageContactRuntimeState:
    """Fail closed unless contact controls, counters, and cross-runtime state agree."""
    if type(runtime) is not LanguageContactRuntimeState:
        _raise("invalid_language_contact_runtime", "contact runtime type is invalid")
    for name in (
        "cross_coalition_contact_attempt_count",
        *_CONTACT_RESULT_COUNTER_FIELDS,
        "cross_group_learning_rate_application_count",
        "borrowing_candidate_creation_count",
        "borrowing_promotion_count",
        "borrowed_production_use_count",
    ):
        if not _exact_nonnegative_int(getattr(runtime, name)):
            _raise("invalid_language_contact_runtime", f"{name} is invalid")
    result_total = sum(
        getattr(runtime, name) for name in _CONTACT_RESULT_COUNTER_FIELDS)
    if result_total != runtime.cross_coalition_contact_attempt_count:
        _raise(
            "contact_attempt_partition_mismatch",
            "contact result counters do not partition contact attempts",
        )
    if runtime.last_contact_tick is not None and (
        type(runtime.last_contact_tick) is not int
        or runtime.last_contact_tick < 0
    ):
        _raise(
            "invalid_language_contact_runtime",
            "last contact tick is invalid",
        )
    initialized_controls = (
        runtime.cross_group_learning_multiplier,
        runtime.borrowing_exposure_threshold,
        runtime.borrowing_confidence_threshold,
    )
    if all(value is None for value in initialized_controls):
        if not contact_runtime_is_pristine(runtime):
            _raise(
                "nonpristine_language_contact_runtime",
                "uninitialized contact runtime retains contact state",
            )
    elif any(value is None for value in initialized_controls):
        _raise(
            "invalid_language_contact_runtime",
            "contact runtime controls are only partially initialized",
        )
    else:
        runtime_config = LanguageContactConfig(
            language_contact_enabled=True,
            cross_group_learning_multiplier=(
                runtime.cross_group_learning_multiplier
            ),
            borrowing_exposure_threshold=runtime.borrowing_exposure_threshold,
            borrowing_confidence_threshold=(
                runtime.borrowing_confidence_threshold
            ),
        )
        validate_language_contact_config(runtime_config)
        if config is not None:
            validated_config = validate_language_contact_config(config)
            if not validated_config.language_contact_enabled:
                _raise(
                    "invalid_language_contact_config",
                    "initialized contact runtime requires enabled controls",
                )
            if runtime_config != validated_config:
                _raise(
                    "language_contact_runtime_config_mismatch",
                    "contact runtime controls disagree with effective configuration",
                )
    if language_runtime is not None:
        validated_language = validate_language_runtime(
            language_runtime, initialized=True)
        initialized = runtime.cross_group_learning_multiplier is not None
        if validated_language.language_contact_enabled is not initialized:
            _raise(
                "language_contact_runtime_gate_mismatch",
                "language runtime contact gate disagrees with contact runtime",
            )
        attempts = runtime.cross_coalition_contact_attempt_count
        if attempts > validated_language.communication_attempt_count:
            _raise(
                "contact_attempt_subset_mismatch",
                "contact attempts exceed language communication attempts",
            )
        if attempts > 0 and runtime.last_contact_tick is None:
            _raise(
                "invalid_language_contact_runtime",
                "recorded contact attempts require a last contact tick",
            )
        if (
            attempts == 0
            and runtime.last_contact_tick is not None
            and validated_language.communication_attempt_count
            < MAX_LANGUAGE_COUNTER
        ):
            _raise(
                "invalid_language_contact_runtime",
                "contact tick without counters requires saturated attempts",
            )
        if runtime.last_contact_tick is not None and (
            validated_language.last_communication_tick is None
            or runtime.last_contact_tick
            > validated_language.last_communication_tick
        ):
            _raise(
                "invalid_language_contact_runtime",
                "last contact tick exceeds language communication history",
            )
        if dialect_runtime is not None:
            validated_dialect = validate_coalition_dialect_runtime(
                dialect_runtime,
                language_runtime=validated_language,
            )
            if attempts != (
                validated_dialect.different_coalition_communication_count
            ):
                _raise(
                    "contact_dialect_context_mismatch",
                    "contact attempts disagree with the dialect context partition",
                )
    return runtime


def initialize_language_contact_runtime(
    runtime: LanguageContactRuntimeState,
    config: LanguageContactConfig,
) -> None:
    """Initialize authoritative contact controls without constructing entropy."""
    validate_language_contact_runtime(runtime)
    validated = validate_language_contact_config(config)
    if not validated.language_contact_enabled:
        _raise(
            "language_contact_processing_disabled",
            "contact runtime initialization requires enabled controls",
        )
    runtime.cross_group_learning_multiplier = (
        validated.cross_group_learning_multiplier)
    runtime.borrowing_exposure_threshold = (
        validated.borrowing_exposure_threshold)
    runtime.borrowing_confidence_threshold = (
        validated.borrowing_confidence_threshold)
    validate_language_contact_runtime(runtime, config=validated)


def dialect_runtime_is_pristine(runtime: object) -> bool:
    """Return whether dialect runtime is exactly disabled and untouched."""
    return type(runtime) is CoalitionDialectRuntimeState and (
        runtime.same_coalition_communication_count == 0
        and type(runtime.same_coalition_communication_count) is int
        and runtime.different_coalition_communication_count == 0
        and type(runtime.different_coalition_communication_count) is int
        and runtime.assigned_unassigned_communication_count == 0
        and type(runtime.assigned_unassigned_communication_count) is int
        and runtime.both_unassigned_communication_count == 0
        and type(runtime.both_unassigned_communication_count) is int
        and runtime.same_coalition_rate_application_count == 0
        and type(runtime.same_coalition_rate_application_count) is int
        and runtime.last_classification_tick is None
    )


def validate_coalition_dialect_runtime(
    runtime: object,
    *,
    language_runtime: LanguageRuntimeState | None = None,
) -> CoalitionDialectRuntimeState:
    """Fail closed unless dialect counters partition language attempts."""
    if type(runtime) is not CoalitionDialectRuntimeState:
        _raise("invalid_dialect_runtime", "dialect runtime type is invalid")
    context_fields = tuple(_DIALECT_CONTEXT_COUNTER_FIELDS.values())
    for name in (
        *context_fields,
        "same_coalition_rate_application_count",
    ):
        if not _exact_nonnegative_int(getattr(runtime, name)):
            _raise("invalid_dialect_runtime", f"{name} is invalid")
    total = sum(getattr(runtime, name) for name in context_fields)
    if total > MAX_LANGUAGE_COUNTER:
        _raise("invalid_dialect_runtime", "context counter total exceeds the cap")
    if total == 0:
        if runtime.last_classification_tick is not None:
            _raise(
                "invalid_dialect_runtime",
                "empty dialect history has a last classification tick",
            )
    elif (
        type(runtime.last_classification_tick) is not int
        or runtime.last_classification_tick < 0
    ):
        _raise(
            "invalid_dialect_runtime",
            "dialect history lacks a valid last classification tick",
        )
    if language_runtime is not None:
        validated_language = validate_language_runtime(
            language_runtime, initialized=True)
        if total != validated_language.communication_attempt_count:
            _raise(
                "dialect_attempt_partition_mismatch",
                "dialect context counters do not partition language attempts",
            )
        if runtime.last_classification_tick != (
            validated_language.last_communication_tick
        ):
            _raise(
                "dialect_tick_mismatch",
                "dialect and language last communication ticks disagree",
            )
    return runtime


def _effective_dialect_rate(base_rate: float, multiplier: float) -> float:
    """Return one clamped six-decimal coalition-adjusted rate."""
    return _confidence(base_rate * multiplier)


def _validate_tick(tick: object) -> int:
    if type(tick) is not int or tick < 0:
        _raise("invalid_language_tick", "tick must be a nonnegative integer")
    return tick


def _validate_config(config: LanguageConfig, *, require_enabled: bool) -> None:
    if type(config.language_evolution_enabled) is not bool:
        _raise("invalid_language_config", "evolution setting must be boolean")
    if require_enabled and not config.language_evolution_enabled:
        _raise("language_processing_disabled", "enabled language processing was not requested")
    if (
        type(config.maximum_language_associations) is not int
        or not 1
        <= config.maximum_language_associations
        <= MAX_LANGUAGE_ASSOCIATIONS
    ):
        _raise(
            "invalid_language_config",
            f"association cap must be an integer from 1 to {MAX_LANGUAGE_ASSOCIATIONS}",
        )
    if (
        type(config.maximum_signal_length) is not int
        or not MIN_SIGNAL_LENGTH
        <= config.maximum_signal_length
        <= MAX_SIGNAL_LENGTH
    ):
        _raise(
            "invalid_language_config",
            f"maximum signal length must be {MIN_SIGNAL_LENGTH}..{MAX_SIGNAL_LENGTH}",
        )
    for value, label in (
        (config.language_learning_rate, "learning rate"),
        (config.language_reinforcement_rate, "reinforcement rate"),
    ):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 < value <= 1.0
        ):
            _raise(
                "invalid_language_config",
                f"{label} must be a finite float in (0.0, 1.0]",
            )
    if (
        type(config.language_forgetting_interval) is not int
        or config.language_forgetting_interval < 1
    ):
        _raise(
            "invalid_language_config",
            "forgetting interval must be a positive integer",
        )
    if type(config.language_invention_enabled) is not bool:
        _raise("invalid_language_config", "invention setting must be boolean")


def validate_language_config(
    config: LanguageConfig,
    *,
    require_enabled: bool = False,
) -> None:
    """Validate exact effective language controls for external callers."""
    _validate_config(config, require_enabled=require_enabled)


def meaning_for_resource(resource: object) -> Meaning:
    """Return the one closed meaning grounded by a transferable resource."""
    if type(resource) is not str or resource not in RESOURCE_MEANINGS:
        _raise("invalid_language_resource", f"unsupported resource: {resource!r}")
    return RESOURCE_MEANINGS[resource]


def _validate_association(
    association: object,
    *,
    store: str,
    maximum_signal_length: int,
    contact_config: LanguageContactConfig | None,
) -> LexicalAssociation:
    if type(association) is not LexicalAssociation:
        _raise("invalid_language_association", "association record type is invalid")
    if type(association.meaning) is not Meaning:
        _raise("invalid_language_association", "meaning must be a Meaning")
    if type(association.signal) is not Signal:
        _raise("invalid_language_association", "signal record type is invalid")
    if len(association.signal.phoneme_ids) > maximum_signal_length:
        _raise(
            "invalid_language_association",
            "signal exceeds the effective maximum length",
        )
    if (
        type(association.confidence) is not float
        or not math.isfinite(association.confidence)
        or not 0.0 < association.confidence <= 1.0
        or _quantize(association.confidence) != association.confidence
    ):
        _raise(
            "invalid_language_association",
            "confidence must be a positive six-decimal float at most 1.0",
        )
    for name in ("successful_uses", "failed_uses", "observation_count"):
        if not _exact_nonnegative_int(getattr(association, name)):
            _raise("invalid_language_association", f"{name} is invalid")
    if type(association.last_used_tick) is not int or association.last_used_tick < 0:
        _raise("invalid_language_association", "last-used tick is invalid")
    if type(association.origin) is not AssociationOrigin:
        _raise("invalid_language_association", "association origin is invalid")
    if association.origin is AssociationOrigin.INVENTED:
        if association.learned_from_id is not None:
            _raise(
                "invalid_language_association",
                "invented associations cannot have a learned-from ID",
            )
    elif not _exact_nonnegative_int(association.learned_from_id):
        _raise(
            "invalid_language_association",
            "learned associations require a stable learned-from ID",
        )
    contact_enabled = (
        contact_config is not None and contact_config.language_contact_enabled
    )
    if not contact_enabled and (
        association.contact_exposure is not None
        or association.borrowing_provenance is not None
    ):
        _raise(
            "hidden_disabled_language_contact_metadata",
            "disabled contact processing cannot retain association metadata",
        )
    if store == "production":
        if association.contact_exposure is not None:
            _raise(
                "invalid_language_contact_metadata",
                "production associations cannot retain comprehension exposure",
            )
        provenance = association.borrowing_provenance
        if provenance is not None:
            if type(provenance) is not BorrowingProvenance:
                _raise(
                    "invalid_language_contact_metadata",
                    "borrowing provenance type is invalid",
                )
            if association.origin is not AssociationOrigin.LEARNED:
                _raise(
                    "invalid_language_contact_metadata",
                    "only learned production can carry borrowing provenance",
                )
            for name in (
                "first_contact_tick",
                "first_source_speaker_id",
                "first_source_coalition_id",
                "adoption_tick",
                "adoption_source_speaker_id",
                "adoption_source_coalition_id",
                "exposure_count_at_adoption",
                "successful_comprehension_count_at_adoption",
            ):
                if not _exact_nonnegative_int(getattr(provenance, name)):
                    _raise(
                        "invalid_language_contact_metadata",
                        f"borrowing provenance {name} is invalid",
                    )
            if provenance.adoption_tick < provenance.first_contact_tick:
                _raise(
                    "invalid_language_contact_metadata",
                    "borrowing adoption precedes first contact",
                )
            if provenance.adoption_tick > association.last_used_tick:
                _raise(
                    "invalid_language_contact_metadata",
                    "borrowing adoption exceeds production history",
                )
            assert contact_config is not None
            if provenance.exposure_count_at_adoption < (
                contact_config.borrowing_exposure_threshold
            ):
                _raise(
                    "invalid_language_contact_metadata",
                    "borrowing adoption lacks the required contact exposures",
                )
            if provenance.successful_comprehension_count_at_adoption > (
                provenance.exposure_count_at_adoption
            ):
                _raise(
                    "invalid_language_contact_metadata",
                    "borrowing successes exceed adoption exposures",
                )
    elif store == "comprehension":
        if association.borrowing_provenance is not None:
            _raise(
                "invalid_language_contact_metadata",
                "comprehension associations cannot carry borrowing provenance",
            )
        exposure = association.contact_exposure
        if exposure is not None:
            if type(exposure) is not ContactExposure:
                _raise(
                    "invalid_language_contact_metadata",
                    "contact exposure type is invalid",
                )
            for name in (
                "first_contact_tick",
                "first_source_speaker_id",
                "first_source_coalition_id",
                "exposure_count",
                "successful_comprehension_count",
            ):
                if not _exact_nonnegative_int(getattr(exposure, name)):
                    _raise(
                        "invalid_language_contact_metadata",
                        f"contact exposure {name} is invalid",
                    )
            if exposure.exposure_count == 0:
                _raise(
                    "invalid_language_contact_metadata",
                    "contact exposure count must be positive",
                )
            if exposure.exposure_count > association.observation_count:
                _raise(
                    "invalid_language_contact_metadata",
                    "contact exposures exceed association observations",
                )
            if exposure.successful_comprehension_count > exposure.exposure_count:
                _raise(
                    "invalid_language_contact_metadata",
                    "contact successes exceed exposures",
                )
            if exposure.successful_comprehension_count > (
                association.successful_uses
            ):
                _raise(
                    "invalid_language_contact_metadata",
                    "contact successes exceed association successful uses",
                )
            if exposure.first_contact_tick > association.last_used_tick:
                _raise(
                    "invalid_language_contact_metadata",
                    "first contact exceeds association history",
                )
    else:
        _raise("invalid_language_store", "association store is invalid")
    return association


def validate_agent_language_state(
    state: object,
    *,
    config: LanguageConfig,
    contact_config: LanguageContactConfig | None = None,
) -> AgentLanguageState:
    """Fail closed unless one agent state is canonical and within every cap."""
    _validate_config(config, require_enabled=False)
    if contact_config is not None:
        validate_language_contact_config(contact_config)
    if type(state) is not AgentLanguageState:
        _raise("invalid_agent_language_state", "agent language state is missing or invalid")
    if type(state.production) is not dict or type(state.comprehension) is not dict:
        _raise("invalid_agent_language_state", "language mappings must be exact dicts")
    if not _exact_nonnegative_int(state.next_invention_index):
        _raise("invalid_invention_index", "next invention index is invalid")

    production_counts: dict[Meaning, int] = {}
    comprehension_meaning_counts: dict[Meaning, int] = {}
    comprehension_signal_counts: dict[Signal, int] = {}

    for key, association in state.production.items():
        if (
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not Meaning
            or type(key[1]) is not Signal
        ):
            _raise("invalid_production_key", "production key is not canonical")
        validated = _validate_association(
            association,
            store="production",
            maximum_signal_length=config.maximum_signal_length,
            contact_config=contact_config,
        )
        if key != (validated.meaning, validated.signal):
            _raise("production_key_mismatch", "production key and record disagree")
        production_counts[validated.meaning] = (
            production_counts.get(validated.meaning, 0) + 1
        )

    for key, association in state.comprehension.items():
        if (
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not Signal
            or type(key[1]) is not Meaning
        ):
            _raise("invalid_comprehension_key", "comprehension key is not canonical")
        validated = _validate_association(
            association,
            store="comprehension",
            maximum_signal_length=config.maximum_signal_length,
            contact_config=contact_config,
        )
        if key != (validated.signal, validated.meaning):
            _raise("comprehension_key_mismatch", "comprehension key and record disagree")
        if validated.origin is not AssociationOrigin.LEARNED:
            _raise(
                "invalid_comprehension_origin",
                "comprehension associations must be observationally learned",
            )
        comprehension_meaning_counts[validated.meaning] = (
            comprehension_meaning_counts.get(validated.meaning, 0) + 1
        )
        comprehension_signal_counts[validated.signal] = (
            comprehension_signal_counts.get(validated.signal, 0) + 1
        )

    if any(
        count > MAX_PRODUCTION_SIGNALS_PER_MEANING
        for count in production_counts.values()
    ):
        _raise("language_cap_exceeded", "production-per-meaning cap is exceeded")
    if any(
        count > MAX_COMPREHENSION_SIGNALS_PER_MEANING
        for count in comprehension_meaning_counts.values()
    ):
        _raise("language_cap_exceeded", "comprehension-per-meaning cap is exceeded")
    if any(
        count > MAX_COMPREHENSION_MEANINGS_PER_SIGNAL
        for count in comprehension_signal_counts.values()
    ):
        _raise("language_cap_exceeded", "meanings-per-signal cap is exceeded")
    if len(state.production) + len(state.comprehension) > (
        config.maximum_language_associations
    ):
        _raise("language_cap_exceeded", "total association cap is exceeded")
    return state


def language_runtime_is_pristine(runtime: object) -> bool:
    """Return whether a runtime has the exact disabled/uninitialized state."""
    return type(runtime) is LanguageRuntimeState and (
        runtime.seed_domain is None
        and runtime.seed_domain_fingerprint is None
        and runtime.communication_attempt_count == 0
        and type(runtime.communication_attempt_count) is int
        and runtime.successful_interpretation_count == 0
        and type(runtime.successful_interpretation_count) is int
        and runtime.misunderstanding_count == 0
        and type(runtime.misunderstanding_count) is int
        and runtime.unknown_signal_count == 0
        and type(runtime.unknown_signal_count) is int
        and runtime.no_signal_count == 0
        and type(runtime.no_signal_count) is int
        and runtime.invention_count == 0
        and type(runtime.invention_count) is int
        and runtime.learned_association_count == 0
        and type(runtime.learned_association_count) is int
        and runtime.lost_association_count == 0
        and type(runtime.lost_association_count) is int
        and runtime.last_communication_tick is None
        and runtime.last_forgetting_tick is None
        and runtime.coalition_dialect_influence_enabled is False
        and runtime.language_contact_enabled is False
    )


def validate_language_runtime(
    runtime: object,
    *,
    initialized: bool,
) -> LanguageRuntimeState:
    """Fail closed unless runtime identity, counters, and totals are canonical."""
    if type(runtime) is not LanguageRuntimeState:
        _raise("invalid_language_runtime", "language runtime type is invalid")
    for name in (
        "communication_attempt_count",
        "successful_interpretation_count",
        "misunderstanding_count",
        "unknown_signal_count",
        "no_signal_count",
        "invention_count",
        "learned_association_count",
        "lost_association_count",
    ):
        if not _exact_nonnegative_int(getattr(runtime, name)):
            _raise("invalid_language_runtime", f"{name} is invalid")
    if type(runtime.coalition_dialect_influence_enabled) is not bool:
        _raise(
            "invalid_language_runtime",
            "coalition dialect runtime gate must be boolean",
        )
    if type(runtime.language_contact_enabled) is not bool:
        _raise(
            "invalid_language_runtime",
            "language contact runtime gate must be boolean",
        )
    if runtime.communication_attempt_count != (
        runtime.successful_interpretation_count
        + runtime.misunderstanding_count
        + runtime.unknown_signal_count
        + runtime.no_signal_count
    ):
        _raise("invalid_language_runtime", "attempt and outcome counters disagree")
    for name in ("last_communication_tick", "last_forgetting_tick"):
        value = getattr(runtime, name)
        if value is not None and (type(value) is not int or value < 0):
            _raise("invalid_language_runtime", f"{name} is invalid")
    if runtime.communication_attempt_count == 0:
        if runtime.last_communication_tick is not None:
            _raise(
                "invalid_language_runtime",
                "empty communication history has a last communication tick",
            )
    elif runtime.last_communication_tick is None:
        _raise("invalid_language_runtime", "communication history lacks a last tick")

    if initialized:
        prefix = f"{LANGUAGE_DOMAIN}|seed="
        if (
            type(runtime.seed_domain) is not str
            or not runtime.seed_domain.startswith(prefix)
        ):
            _raise("invalid_language_runtime", "seed domain is not initialized canonically")
        try:
            runtime.seed_domain.encode("ascii")
        except UnicodeEncodeError:
            _raise("invalid_language_runtime", "seed domain must be ASCII")
        seed_text = runtime.seed_domain[len(prefix):]
        try:
            parsed_seed = int(seed_text)
        except (TypeError, ValueError):
            _raise("invalid_language_runtime", "seed domain contains an invalid seed")
        if str(parsed_seed) != seed_text:
            _raise("invalid_language_runtime", "seed domain seed is not canonical")
        expected = hashlib.sha256(runtime.seed_domain.encode("ascii")).hexdigest()
        if runtime.seed_domain_fingerprint != expected:
            _raise("invalid_language_runtime", "seed-domain fingerprint mismatch")
    elif not language_runtime_is_pristine(runtime):
        _raise("nonpristine_language_runtime", "disabled language runtime is not pristine")
    return runtime


def initialize_language_runtime(
    runtime: LanguageRuntimeState,
    run_seed: int,
    *,
    coalition_dialect_influence_enabled: bool = False,
    language_contact_enabled: bool = False,
) -> None:
    """Initialize only the canonical seed domain; no entropy is constructed."""
    validate_language_runtime(runtime, initialized=False)
    if type(run_seed) is not int:
        _raise("invalid_language_seed", "run seed must be an exact integer")
    if type(coalition_dialect_influence_enabled) is not bool:
        _raise(
            "invalid_dialect_config",
            "language runtime dialect gate must be boolean",
        )
    if type(language_contact_enabled) is not bool:
        _raise(
            "invalid_language_contact_config",
            "language runtime contact gate must be boolean",
        )
    seed_domain = f"{LANGUAGE_DOMAIN}|seed={run_seed}"
    runtime.seed_domain = seed_domain
    runtime.seed_domain_fingerprint = hashlib.sha256(
        seed_domain.encode("ascii")
    ).hexdigest()
    runtime.coalition_dialect_influence_enabled = (
        coalition_dialect_influence_enabled
    )
    runtime.language_contact_enabled = language_contact_enabled
    validate_language_runtime(runtime, initialized=True)


def derive_invention_signal(
    runtime: LanguageRuntimeState,
    *,
    inventor_id: int,
    meaning: Meaning,
    invention_index: int,
    maximum_signal_length: int,
) -> Signal:
    """Derive one signal from a single canonical SHA-256 counter record."""
    validate_language_runtime(runtime, initialized=True)
    if not _exact_nonnegative_int(inventor_id):
        _raise("invalid_language_identity", "inventor ID is invalid")
    if type(meaning) is not Meaning:
        _raise("invalid_language_meaning", "meaning must be a Meaning")
    if not _exact_nonnegative_int(invention_index):
        _raise("invalid_invention_index", "invention index is invalid")
    if (
        type(maximum_signal_length) is not int
        or not MIN_SIGNAL_LENGTH <= maximum_signal_length <= MAX_SIGNAL_LENGTH
    ):
        _raise("invalid_signal_length", "effective maximum signal length is invalid")
    record = (
        f"{runtime.seed_domain}|inventor_id={inventor_id}"
        f"|meaning={meaning.name}|index={invention_index}"
    )
    digest = hashlib.sha256(record.encode("ascii")).digest()
    length = MIN_SIGNAL_LENGTH + digest[0] % (
        maximum_signal_length - MIN_SIGNAL_LENGTH + 1
    )
    return Signal(tuple(digest[index + 1] & 0x07 for index in range(length)))


def _copy_agent_state(state: AgentLanguageState) -> AgentLanguageState:
    return AgentLanguageState(
        production=dict(state.production),
        comprehension=dict(state.comprehension),
        next_invention_index=state.next_invention_index,
    )


def _validate_state_tick(
    state: AgentLanguageState,
    *,
    tick: int,
) -> None:
    if any(
        association.last_used_tick > tick
        for association in (
            *state.production.values(),
            *state.comprehension.values(),
        )
    ):
        _raise(
            "nonmonotonic_language_tick",
            "association state contains a future last-used tick",
        )


def _association_sort_key(
    store: str,
    association: LexicalAssociation,
) -> tuple:
    # Best first: confidence, successes, fewer failures, observations,
    # recency, production before comprehension, meaning, then signal.
    return (
        -association.confidence,
        -association.successful_uses,
        association.failed_uses,
        -association.observation_count,
        -association.last_used_tick,
        0 if store == "production" else 1,
        MEANING_ORDER[association.meaning],
        association.signal.phoneme_ids,
    )


def _retain_canonical(
    state: AgentLanguageState,
    *,
    config: LanguageConfig,
) -> tuple[AgentLanguageState, int]:
    """Apply every vocabulary cap in one canonical greedy retention pass."""
    candidates = [
        ("production", key, association)
        for key, association in state.production.items()
    ] + [
        ("comprehension", key, association)
        for key, association in state.comprehension.items()
    ]
    candidates.sort(key=lambda item: _association_sort_key(item[0], item[2]))

    retained_production: dict[tuple[Meaning, Signal], LexicalAssociation] = {}
    retained_comprehension: dict[tuple[Signal, Meaning], LexicalAssociation] = {}
    production_counts: dict[Meaning, int] = {}
    comprehension_meaning_counts: dict[Meaning, int] = {}
    comprehension_signal_counts: dict[Signal, int] = {}
    retained_total = 0

    for store, key, association in candidates:
        if association.confidence <= 0.0:
            continue
        if retained_total >= config.maximum_language_associations:
            continue
        if store == "production":
            count = production_counts.get(association.meaning, 0)
            if count >= MAX_PRODUCTION_SIGNALS_PER_MEANING:
                continue
            retained_production[key] = association
            production_counts[association.meaning] = count + 1
        else:
            meaning_count = comprehension_meaning_counts.get(
                association.meaning, 0)
            signal_count = comprehension_signal_counts.get(
                association.signal, 0)
            if meaning_count >= MAX_COMPREHENSION_SIGNALS_PER_MEANING:
                continue
            if signal_count >= MAX_COMPREHENSION_MEANINGS_PER_SIGNAL:
                continue
            retained_comprehension[key] = association
            comprehension_meaning_counts[association.meaning] = meaning_count + 1
            comprehension_signal_counts[association.signal] = signal_count + 1
        retained_total += 1

    retained = AgentLanguageState(
        production=dict(sorted(
            retained_production.items(),
            key=lambda item: (
                MEANING_ORDER[item[0][0]], item[0][1].phoneme_ids),
        )),
        comprehension=dict(sorted(
            retained_comprehension.items(),
            key=lambda item: (
                item[0][0].phoneme_ids, MEANING_ORDER[item[0][1]]),
        )),
        next_invention_index=state.next_invention_index,
    )
    removed = len(candidates) - retained_total
    return retained, removed


def _select_production(
    state: AgentLanguageState,
    meaning: Meaning,
) -> LexicalAssociation | None:
    candidates = [
        association
        for (candidate_meaning, _signal), association in state.production.items()
        if candidate_meaning is meaning
        and association.confidence >= MIN_USABLE_CONFIDENCE
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda association: (
            -association.confidence, association.signal.phoneme_ids),
    )


def _select_comprehension(
    state: AgentLanguageState,
    signal: Signal,
) -> LexicalAssociation | None:
    candidates = [
        association
        for (candidate_signal, _meaning), association in state.comprehension.items()
        if candidate_signal == signal
        and association.confidence >= MIN_USABLE_CONFIDENCE
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda association: (
            -association.confidence, MEANING_ORDER[association.meaning]),
    )


def _selected_use(
    association: LexicalAssociation,
    *,
    tick: int,
    succeeded: bool,
    confidence_delta: float,
) -> LexicalAssociation:
    if tick < association.last_used_tick:
        _raise("nonmonotonic_language_tick", "association use moved backward in time")
    return replace(
        association,
        confidence=_confidence(association.confidence + confidence_delta),
        successful_uses=(
            _increment(association.successful_uses, field_name="successful_uses")
            if succeeded else association.successful_uses
        ),
        failed_uses=(
            association.failed_uses
            if succeeded
            else _increment(association.failed_uses, field_name="failed_uses")
        ),
        observation_count=_increment(
            association.observation_count, field_name="observation_count"),
        last_used_tick=tick,
    )


def _observed_without_use(
    association: LexicalAssociation,
    *,
    tick: int,
    confidence_delta: float,
) -> LexicalAssociation:
    if tick < association.last_used_tick:
        _raise("nonmonotonic_language_tick", "association observation moved backward")
    return replace(
        association,
        confidence=_confidence(association.confidence + confidence_delta),
        observation_count=_increment(
            association.observation_count, field_name="observation_count"),
        last_used_tick=tick,
    )


def _weaken_only(
    association: LexicalAssociation,
    amount: float,
) -> LexicalAssociation:
    return replace(
        association,
        confidence=_confidence(association.confidence - amount),
    )


def _increment_runtime(runtime: LanguageRuntimeState, name: str) -> None:
    setattr(
        runtime,
        name,
        _increment(getattr(runtime, name), field_name=name),
    )


def _commit_runtime(
    target: LanguageRuntimeState,
    proposed: LanguageRuntimeState,
) -> None:
    for item in fields(LanguageRuntimeState):
        setattr(target, item.name, getattr(proposed, item.name))


def _commit_dialect_runtime(
    target: CoalitionDialectRuntimeState,
    proposed: CoalitionDialectRuntimeState,
) -> None:
    for item in fields(CoalitionDialectRuntimeState):
        setattr(target, item.name, getattr(proposed, item.name))


def _commit_contact_runtime(
    target: LanguageContactRuntimeState,
    proposed: LanguageContactRuntimeState,
) -> None:
    for item in fields(LanguageContactRuntimeState):
        setattr(target, item.name, getattr(proposed, item.name))


def _effective_contact_rate(base_rate: float, multiplier: float) -> float:
    """Return one clamped six-decimal cross-coalition learning rate."""
    return _confidence(base_rate * multiplier)


def _record_contact_exposure(
    association: LexicalAssociation,
    *,
    tick: int,
    source_speaker_id: int,
    source_coalition_id: int,
    succeeded: bool,
) -> tuple[LexicalAssociation, bool]:
    """Attach one exposure while preserving immutable first-contact facts."""
    existing = association.contact_exposure
    if existing is None:
        exposure = ContactExposure(
            first_contact_tick=tick,
            first_source_speaker_id=source_speaker_id,
            first_source_coalition_id=source_coalition_id,
            exposure_count=1,
            successful_comprehension_count=1 if succeeded else 0,
        )
        created = True
    else:
        exposure = replace(
            existing,
            exposure_count=_saturating_add(
                existing.exposure_count,
                1,
                field_name="contact exposure count",
            ),
            successful_comprehension_count=_saturating_add(
                existing.successful_comprehension_count,
                1 if succeeded else 0,
                field_name="contact successful comprehension count",
            ),
        )
        created = False
    return replace(association, contact_exposure=exposure), created


_CONTACT_OUTCOME_COUNTER_FIELDS = {
    CommunicationResult.SUCCESS: "cross_coalition_success_count",
    CommunicationResult.MISUNDERSTANDING: (
        "cross_coalition_misunderstanding_count"
    ),
    CommunicationResult.UNKNOWN_SIGNAL: "cross_coalition_unknown_signal_count",
    CommunicationResult.NO_SIGNAL: "cross_coalition_no_signal_count",
}


def _record_contact_outcome(
    runtime: LanguageContactRuntimeState,
    *,
    result: CommunicationResult,
    tick: int,
    attempt_incremented: bool,
) -> None:
    """Record one committed qualifying contact with shared-counter saturation."""
    if attempt_incremented:
        runtime.cross_coalition_contact_attempt_count = _increment(
            runtime.cross_coalition_contact_attempt_count,
            field_name="cross_coalition_contact_attempt_count",
        )
        field_name = _CONTACT_OUTCOME_COUNTER_FIELDS[result]
        setattr(
            runtime,
            field_name,
            _increment(getattr(runtime, field_name), field_name=field_name),
        )
    runtime.last_contact_tick = tick


def communicate(
    sender: LanguageInhabitant,
    receiver: LanguageInhabitant,
    intended_meaning: Meaning,
    *,
    context: CommunicationContext,
    tick: int,
    active_ids: set[int] | frozenset[int],
    config: LanguageConfig,
    runtime: LanguageRuntimeState,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
) -> CommunicationOutcome:
    """Apply one complete communication transaction or leave all state unchanged."""
    contact_required = (
        type(runtime) is LanguageRuntimeState
        and runtime.language_contact_enabled is True
    )
    if contact_required:
        return _communicate_with_contact(
            sender,
            receiver,
            intended_meaning,
            context=context,
            tick=tick,
            active_ids=active_ids,
            config=config,
            runtime=runtime,
            dialect_config=dialect_config,
            dialect_runtime=dialect_runtime,
            contact_config=contact_config,
            contact_runtime=contact_runtime,
            coalition_membership_snapshot=coalition_membership_snapshot,
        )
    if contact_config is not None or contact_runtime is not None:
        _raise(
            "unexpected_language_contact_transaction_inputs",
            "disabled language runtime cannot enter contact processing",
        )
    _validate_config(config, require_enabled=True)
    validated_tick = _validate_tick(tick)
    if type(intended_meaning) is not Meaning:
        _raise("invalid_language_meaning", "intended meaning must be a Meaning")
    if type(context) is not CommunicationContext:
        _raise("invalid_communication_context", "context must be canonical")
    dialect_required = (
        type(runtime) is LanguageRuntimeState
        and runtime.coalition_dialect_influence_enabled is True
    )
    if type(active_ids) not in (set, frozenset):
        _raise("invalid_active_language_ids", "active IDs must be canonical integers")
    if not dialect_required and any(
        not _exact_nonnegative_int(inhabitant_id) for inhabitant_id in active_ids
    ):
        _raise("invalid_active_language_ids", "active IDs must be canonical integers")
    sender_id = getattr(sender, "inhabitant_id", None)
    receiver_id = getattr(receiver, "inhabitant_id", None)
    if not _exact_nonnegative_int(sender_id):
        _raise("invalid_language_identity", "sender lacks an assigned exact ID")
    if not _exact_nonnegative_int(receiver_id):
        _raise("invalid_language_identity", "receiver lacks an assigned exact ID")
    if sender_id == receiver_id or sender is receiver:
        _raise("invalid_language_identity", "sender and receiver must be distinct")
    if sender_id not in active_ids or receiver_id not in active_ids:
        _raise("inactive_language_identity", "sender and receiver must both be active")
    sender_state = validate_agent_language_state(sender.language, config=config)
    receiver_state = validate_agent_language_state(receiver.language, config=config)
    _validate_state_tick(sender_state, tick=validated_tick)
    _validate_state_tick(receiver_state, tick=validated_tick)
    if sender_state is receiver_state:
        _raise("aliased_agent_language_state", "agents cannot share language state")
    validate_language_runtime(runtime, initialized=True)
    if any(
        last_tick is not None and validated_tick < last_tick
        for last_tick in (
            runtime.last_communication_tick,
            runtime.last_forgetting_tick,
        )
    ):
        _raise("nonmonotonic_language_tick", "communication tick moved backward")

    dialect_inputs = (
        dialect_config,
        dialect_runtime,
        coalition_membership_snapshot,
    )
    classification = None
    proposed_dialect = None
    if dialect_required:
        if any(value is None for value in dialect_inputs):
            _raise(
                "missing_dialect_transaction_inputs",
                "enabled dialect communication requires config, runtime, and snapshot",
            )
        validated_dialect_config = validate_coalition_dialect_config(
            dialect_config)
        if not validated_dialect_config.coalition_dialect_influence_enabled:
            _raise(
                "invalid_dialect_config",
                "language runtime requires effective dialect influence",
            )
        validated_dialect_runtime = validate_coalition_dialect_runtime(
            dialect_runtime,
            language_runtime=runtime,
        )
        classification = classify_coalition_communication(
            coalition_membership_snapshot,
            tick=validated_tick,
            sender_id=sender_id,
            receiver_id=receiver_id,
        )
        proposed_dialect = replace(validated_dialect_runtime)
    elif any(value is not None for value in dialect_inputs):
        _raise(
            "unexpected_dialect_transaction_inputs",
            "disabled language runtime cannot enter dialect processing",
        )

    proposed_sender = _copy_agent_state(sender_state)
    proposed_receiver = _copy_agent_state(receiver_state)
    proposed_runtime = replace(runtime)
    selected_production = _select_production(
        proposed_sender, intended_meaning)
    if selected_production is None and config.language_invention_enabled:
        signal = derive_invention_signal(
            proposed_runtime,
            inventor_id=sender_id,
            meaning=intended_meaning,
            invention_index=proposed_sender.next_invention_index,
            maximum_signal_length=config.maximum_signal_length,
        )
        key = (intended_meaning, signal)
        existing = proposed_sender.production.get(key)
        if existing is None:
            selected_production = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=INVENTION_CONFIDENCE,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.INVENTED,
            )
        else:
            selected_production = replace(
                existing, confidence=INVENTION_CONFIDENCE)
        proposed_sender.next_invention_index = _increment(
            proposed_sender.next_invention_index,
            field_name="next_invention_index",
        )
        _increment_runtime(proposed_runtime, "invention_count")

    if dialect_required:
        attempt_incremented = (
            proposed_runtime.communication_attempt_count < MAX_LANGUAGE_COUNTER
        )
    else:
        _increment_runtime(proposed_runtime, "communication_attempt_count")
        attempt_incremented = True
    if dialect_required and attempt_incremented:
        _increment_runtime(proposed_runtime, "communication_attempt_count")
        if classification is None or proposed_dialect is None:
            _raise(
                "invalid_dialect_transaction",
                "dialect proposal lacks its validated classification",
            )
        context_counter = _DIALECT_CONTEXT_COUNTER_FIELDS[
            classification.context]
        setattr(
            proposed_dialect,
            context_counter,
            _increment(
                getattr(proposed_dialect, context_counter),
                field_name=context_counter,
            ),
        )
    proposed_runtime.last_communication_tick = validated_tick
    if proposed_dialect is not None:
        proposed_dialect.last_classification_tick = validated_tick

    if selected_production is None:
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "no_signal_count")
        validate_agent_language_state(proposed_sender, config=config)
        validate_agent_language_state(proposed_receiver, config=config)
        validate_language_runtime(proposed_runtime, initialized=True)
        if proposed_dialect is not None:
            validate_coalition_dialect_runtime(
                proposed_dialect,
                language_runtime=proposed_runtime,
            )
        original_runtime = replace(runtime)
        if proposed_dialect is None:
            try:
                _commit_runtime(runtime, proposed_runtime)
            except BaseException:
                _commit_runtime(runtime, original_runtime)
                raise
        else:
            original_sender = sender.language
            original_receiver = receiver.language
            original_dialect = replace(dialect_runtime)
            try:
                sender.language = proposed_sender
                receiver.language = proposed_receiver
                _commit_runtime(runtime, proposed_runtime)
                _commit_dialect_runtime(dialect_runtime, proposed_dialect)
            except BaseException:
                sender.language = original_sender
                receiver.language = original_receiver
                _commit_runtime(runtime, original_runtime)
                _commit_dialect_runtime(dialect_runtime, original_dialect)
                raise
        return CommunicationOutcome(
            tick=validated_tick,
            sender_id=sender_id,
            receiver_id=receiver_id,
            context=context,
            intended_meaning=intended_meaning,
            produced_signal=None,
            interpreted_meaning=None,
            result=CommunicationResult.NO_SIGNAL,
            coalition_context=(
                classification.context if classification is not None else None
            ),
            sender_coalition_id=(
                classification.sender_coalition_id
                if classification is not None else None
            ),
            receiver_coalition_id=(
                classification.receiver_coalition_id
                if classification is not None else None
            ),
        )

    signal = selected_production.signal
    selected_comprehension = _select_comprehension(
        proposed_receiver, signal)
    interpreted = (
        selected_comprehension.meaning
        if selected_comprehension is not None else None
    )
    if interpreted is None:
        result = CommunicationResult.UNKNOWN_SIGNAL
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "unknown_signal_count")
    elif interpreted is intended_meaning:
        result = CommunicationResult.SUCCESS
        if attempt_incremented:
            _increment_runtime(
                proposed_runtime, "successful_interpretation_count")
    else:
        result = CommunicationResult.MISUNDERSTANDING
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "misunderstanding_count")

    base_reinforcement = config.language_reinforcement_rate
    base_learning = config.language_learning_rate
    same_coalition = (
        classification is not None
        and classification.context
        is CoalitionCommunicationContext.SAME_ACTIVE_COALITION
    )
    if same_coalition:
        reinforcement = _effective_dialect_rate(
            base_reinforcement,
            dialect_config.same_coalition_reinforcement_multiplier,
        )
        learning = _effective_dialect_rate(
            base_learning,
            dialect_config.same_coalition_learning_multiplier,
        )
    else:
        reinforcement = base_reinforcement
        learning = base_learning
    rate_applications = 0
    production_key = (intended_meaning, signal)
    proposed_sender.production[production_key] = _selected_use(
        selected_production,
        tick=validated_tick,
        succeeded=result is CommunicationResult.SUCCESS,
        confidence_delta=(
            reinforcement
            if result is CommunicationResult.SUCCESS
            else -base_reinforcement / 2.0
        ),
    )
    if same_coalition and result is CommunicationResult.SUCCESS:
        rate_applications += 1
    for key, association in tuple(proposed_sender.production.items()):
        if key != production_key and association.meaning is intended_meaning:
            proposed_sender.production[key] = _weaken_only(
                association, base_reinforcement / 4.0)

    if result is CommunicationResult.SUCCESS:
        assert selected_comprehension is not None
        comprehension_key = (signal, intended_meaning)
        updated_comprehension = _selected_use(
            selected_comprehension,
            tick=validated_tick,
            succeeded=True,
            confidence_delta=reinforcement,
        )
        proposed_receiver.comprehension[comprehension_key] = updated_comprehension
        if same_coalition:
            rate_applications += 1
        for key, association in tuple(proposed_receiver.comprehension.items()):
            if key == comprehension_key:
                continue
            if association.signal == signal:
                proposed_receiver.comprehension[key] = _weaken_only(
                    association, base_reinforcement)
            elif association.meaning is intended_meaning:
                proposed_receiver.comprehension[key] = _weaken_only(
                    association, base_reinforcement / 4.0)

        receiver_production_key = (intended_meaning, signal)
        receiver_production = proposed_receiver.production.get(
            receiver_production_key)
        production_activated = False
        if receiver_production is not None:
            proposed_receiver.production[receiver_production_key] = (
                _observed_without_use(
                    receiver_production,
                    tick=validated_tick,
                    confidence_delta=learning / 2.0,
                )
            )
            production_activated = True
            if same_coalition:
                rate_applications += 1
        elif (
            updated_comprehension.confidence >= PROMOTION_CONFIDENCE
            and updated_comprehension.successful_uses >= PROMOTION_SUCCESS_COUNT
        ):
            proposed_receiver.production[receiver_production_key] = (
                LexicalAssociation(
                    meaning=intended_meaning,
                    signal=signal,
                    confidence=updated_comprehension.confidence,
                    observation_count=1,
                    last_used_tick=validated_tick,
                    origin=AssociationOrigin.LEARNED,
                    learned_from_id=updated_comprehension.learned_from_id,
                )
            )
            _increment_runtime(proposed_runtime, "learned_association_count")
            production_activated = True
        if production_activated:
            for key, association in tuple(proposed_receiver.production.items()):
                if key != receiver_production_key and (
                    association.meaning is intended_meaning
                ):
                    proposed_receiver.production[key] = _weaken_only(
                        association, base_reinforcement / 4.0)

    elif result is CommunicationResult.MISUNDERSTANDING:
        assert selected_comprehension is not None
        wrong_key = (signal, selected_comprehension.meaning)
        proposed_receiver.comprehension[wrong_key] = _selected_use(
            selected_comprehension,
            tick=validated_tick,
            succeeded=False,
            confidence_delta=-base_reinforcement,
        )
        correct_key = (signal, intended_meaning)
        correct = proposed_receiver.comprehension.get(correct_key)
        if correct is None:
            proposed_receiver.comprehension[correct_key] = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=_confidence(learning),
                observation_count=1,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.LEARNED,
                learned_from_id=sender_id,
            )
            _increment_runtime(proposed_runtime, "learned_association_count")
        else:
            proposed_receiver.comprehension[correct_key] = _observed_without_use(
                correct,
                tick=validated_tick,
                confidence_delta=learning,
            )
        if same_coalition:
            rate_applications += 1

    else:
        correct_key = (signal, intended_meaning)
        correct = proposed_receiver.comprehension.get(correct_key)
        if correct is None:
            proposed_receiver.comprehension[correct_key] = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=_confidence(learning),
                observation_count=1,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.LEARNED,
                learned_from_id=sender_id,
            )
            _increment_runtime(proposed_runtime, "learned_association_count")
        else:
            proposed_receiver.comprehension[correct_key] = _observed_without_use(
                correct,
                tick=validated_tick,
                confidence_delta=learning,
            )
        if same_coalition:
            rate_applications += 1

    if proposed_dialect is not None and rate_applications:
        proposed_dialect.same_coalition_rate_application_count = _saturating_add(
            proposed_dialect.same_coalition_rate_application_count,
            rate_applications,
            field_name="same_coalition_rate_application_count",
        )

    proposed_sender, sender_lost = _retain_canonical(
        proposed_sender, config=config)
    proposed_receiver, receiver_lost = _retain_canonical(
        proposed_receiver, config=config)
    for _ in range(sender_lost + receiver_lost):
        _increment_runtime(proposed_runtime, "lost_association_count")

    validate_agent_language_state(proposed_sender, config=config)
    validate_agent_language_state(proposed_receiver, config=config)
    validate_language_runtime(proposed_runtime, initialized=True)
    if proposed_dialect is not None:
        validate_coalition_dialect_runtime(
            proposed_dialect,
            language_runtime=proposed_runtime,
        )

    original_sender = sender.language
    original_receiver = receiver.language
    original_runtime = replace(runtime)
    original_dialect = (
        replace(dialect_runtime) if proposed_dialect is not None else None
    )
    try:
        sender.language = proposed_sender
        receiver.language = proposed_receiver
        _commit_runtime(runtime, proposed_runtime)
        if proposed_dialect is not None:
            _commit_dialect_runtime(dialect_runtime, proposed_dialect)
    except BaseException:
        sender.language = original_sender
        receiver.language = original_receiver
        _commit_runtime(runtime, original_runtime)
        if original_dialect is not None:
            _commit_dialect_runtime(dialect_runtime, original_dialect)
        raise

    return CommunicationOutcome(
        tick=validated_tick,
        sender_id=sender_id,
        receiver_id=receiver_id,
        context=context,
        intended_meaning=intended_meaning,
        produced_signal=signal,
        interpreted_meaning=interpreted,
        result=result,
        coalition_context=(
            classification.context if classification is not None else None
        ),
        sender_coalition_id=(
            classification.sender_coalition_id
            if classification is not None else None
        ),
        receiver_coalition_id=(
            classification.receiver_coalition_id
            if classification is not None else None
        ),
    )


def _communicate_with_contact(
    sender: LanguageInhabitant,
    receiver: LanguageInhabitant,
    intended_meaning: Meaning,
    *,
    context: CommunicationContext,
    tick: int,
    active_ids: set[int] | frozenset[int],
    config: LanguageConfig,
    runtime: LanguageRuntimeState,
    dialect_config: CoalitionDialectConfig | None,
    dialect_runtime: CoalitionDialectRuntimeState | None,
    contact_config: LanguageContactConfig | None,
    contact_runtime: LanguageContactRuntimeState | None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None,
) -> CommunicationOutcome:
    """Apply one contact-enabled transaction using one frozen classification."""
    _validate_config(config, require_enabled=True)
    validated_tick = _validate_tick(tick)
    if type(intended_meaning) is not Meaning:
        _raise("invalid_language_meaning", "intended meaning must be a Meaning")
    if type(context) is not CommunicationContext:
        _raise("invalid_communication_context", "context must be canonical")
    if type(active_ids) not in (set, frozenset):
        _raise("invalid_active_language_ids", "active IDs must be canonical integers")
    sender_id = getattr(sender, "inhabitant_id", None)
    receiver_id = getattr(receiver, "inhabitant_id", None)
    if not _exact_nonnegative_int(sender_id):
        _raise("invalid_language_identity", "sender lacks an assigned exact ID")
    if not _exact_nonnegative_int(receiver_id):
        _raise("invalid_language_identity", "receiver lacks an assigned exact ID")
    if sender_id == receiver_id or sender is receiver:
        _raise("invalid_language_identity", "sender and receiver must be distinct")
    if sender_id not in active_ids or receiver_id not in active_ids:
        _raise("inactive_language_identity", "sender and receiver must both be active")

    validated_runtime = validate_language_runtime(runtime, initialized=True)
    if not validated_runtime.language_contact_enabled:
        _raise(
            "language_contact_processing_disabled",
            "contact proposal requires the authoritative runtime gate",
        )
    if contact_config is None or contact_runtime is None:
        _raise(
            "missing_language_contact_transaction_inputs",
            "enabled contact communication requires config, runtime, and snapshot",
        )
    validated_contact_config = validate_language_contact_config(contact_config)
    if not validated_contact_config.language_contact_enabled:
        _raise(
            "invalid_language_contact_config",
            "language runtime requires effective contact processing",
        )
    if coalition_membership_snapshot is None:
        _raise(
            "missing_language_contact_transaction_inputs",
            "enabled contact communication requires config, runtime, and snapshot",
        )

    dialect_required = validated_runtime.coalition_dialect_influence_enabled
    validated_dialect_runtime = None
    if dialect_required:
        if dialect_config is None or dialect_runtime is None:
            _raise(
                "missing_dialect_transaction_inputs",
                "enabled dialect communication requires config, runtime, and snapshot",
            )
        validated_dialect_config = validate_coalition_dialect_config(
            dialect_config)
        if not validated_dialect_config.coalition_dialect_influence_enabled:
            _raise(
                "invalid_dialect_config",
                "language runtime requires effective dialect influence",
            )
        validated_dialect_runtime = validate_coalition_dialect_runtime(
            dialect_runtime,
            language_runtime=validated_runtime,
        )
    elif dialect_config is not None or dialect_runtime is not None:
        _raise(
            "unexpected_dialect_transaction_inputs",
            "disabled dialect runtime cannot enter dialect processing",
        )

    classification = classify_coalition_communication(
        coalition_membership_snapshot,
        tick=validated_tick,
        sender_id=sender_id,
        receiver_id=receiver_id,
    )
    validated_contact_runtime = validate_language_contact_runtime(
        contact_runtime,
        config=validated_contact_config,
        language_runtime=validated_runtime,
        dialect_runtime=(
            validated_dialect_runtime if dialect_required else None
        ),
    )
    sender_state = validate_agent_language_state(
        sender.language,
        config=config,
        contact_config=validated_contact_config,
    )
    receiver_state = validate_agent_language_state(
        receiver.language,
        config=config,
        contact_config=validated_contact_config,
    )
    _validate_state_tick(sender_state, tick=validated_tick)
    _validate_state_tick(receiver_state, tick=validated_tick)
    if sender_state is receiver_state:
        _raise("aliased_agent_language_state", "agents cannot share language state")
    if any(
        last_tick is not None and validated_tick < last_tick
        for last_tick in (
            validated_runtime.last_communication_tick,
            validated_runtime.last_forgetting_tick,
        )
    ):
        _raise("nonmonotonic_language_tick", "communication tick moved backward")

    proposed_sender = _copy_agent_state(sender_state)
    proposed_receiver = _copy_agent_state(receiver_state)
    proposed_runtime = replace(validated_runtime)
    proposed_contact = replace(validated_contact_runtime)
    proposed_dialect = (
        replace(validated_dialect_runtime) if dialect_required else None
    )
    selected_production = _select_production(
        proposed_sender, intended_meaning)
    if selected_production is None and config.language_invention_enabled:
        signal = derive_invention_signal(
            proposed_runtime,
            inventor_id=sender_id,
            meaning=intended_meaning,
            invention_index=proposed_sender.next_invention_index,
            maximum_signal_length=config.maximum_signal_length,
        )
        key = (intended_meaning, signal)
        existing = proposed_sender.production.get(key)
        if existing is None:
            selected_production = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=INVENTION_CONFIDENCE,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.INVENTED,
            )
        else:
            selected_production = replace(
                existing, confidence=INVENTION_CONFIDENCE)
        proposed_sender.next_invention_index = _increment(
            proposed_sender.next_invention_index,
            field_name="next_invention_index",
        )
        _increment_runtime(proposed_runtime, "invention_count")

    attempt_incremented = (
        proposed_runtime.communication_attempt_count < MAX_LANGUAGE_COUNTER
    )
    if attempt_incremented:
        _increment_runtime(proposed_runtime, "communication_attempt_count")
        if proposed_dialect is not None:
            context_counter = _DIALECT_CONTEXT_COUNTER_FIELDS[
                classification.context]
            setattr(
                proposed_dialect,
                context_counter,
                _increment(
                    getattr(proposed_dialect, context_counter),
                    field_name=context_counter,
                ),
            )
    proposed_runtime.last_communication_tick = validated_tick
    if proposed_dialect is not None:
        proposed_dialect.last_classification_tick = validated_tick
    qualifying_contact = (
        classification.context
        is CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS
    )

    if selected_production is None:
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "no_signal_count")
        if qualifying_contact:
            _record_contact_outcome(
                proposed_contact,
                result=CommunicationResult.NO_SIGNAL,
                tick=validated_tick,
                attempt_incremented=attempt_incremented,
            )
        _validate_contact_proposal(
            proposed_sender,
            proposed_receiver,
            proposed_runtime,
            proposed_dialect,
            proposed_contact,
            language_config=config,
            contact_config=validated_contact_config,
        )
        _commit_contact_proposal(
            sender,
            receiver,
            runtime,
            dialect_runtime,
            contact_runtime,
            proposed_sender=proposed_sender,
            proposed_receiver=proposed_receiver,
            proposed_runtime=proposed_runtime,
            proposed_dialect=proposed_dialect,
            proposed_contact=proposed_contact,
        )
        return CommunicationOutcome(
            tick=validated_tick,
            sender_id=sender_id,
            receiver_id=receiver_id,
            context=context,
            intended_meaning=intended_meaning,
            produced_signal=None,
            interpreted_meaning=None,
            result=CommunicationResult.NO_SIGNAL,
            coalition_context=classification.context,
            sender_coalition_id=classification.sender_coalition_id,
            receiver_coalition_id=classification.receiver_coalition_id,
        )

    signal = selected_production.signal
    if selected_production.borrowing_provenance is not None:
        proposed_contact.borrowed_production_use_count = _saturating_add(
            proposed_contact.borrowed_production_use_count,
            1,
            field_name="borrowed_production_use_count",
        )
    selected_comprehension = _select_comprehension(
        proposed_receiver, signal)
    interpreted = (
        selected_comprehension.meaning
        if selected_comprehension is not None else None
    )
    if interpreted is None:
        result = CommunicationResult.UNKNOWN_SIGNAL
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "unknown_signal_count")
    elif interpreted is intended_meaning:
        result = CommunicationResult.SUCCESS
        if attempt_incremented:
            _increment_runtime(
                proposed_runtime, "successful_interpretation_count")
    else:
        result = CommunicationResult.MISUNDERSTANDING
        if attempt_incremented:
            _increment_runtime(proposed_runtime, "misunderstanding_count")
    if qualifying_contact:
        _record_contact_outcome(
            proposed_contact,
            result=result,
            tick=validated_tick,
            attempt_incremented=attempt_incremented,
        )

    base_reinforcement = config.language_reinforcement_rate
    base_learning = config.language_learning_rate
    same_coalition = (
        dialect_required
        and classification.context
        is CoalitionCommunicationContext.SAME_ACTIVE_COALITION
    )
    if same_coalition:
        assert dialect_config is not None
        reinforcement = _effective_dialect_rate(
            base_reinforcement,
            dialect_config.same_coalition_reinforcement_multiplier,
        )
        learning = _effective_dialect_rate(
            base_learning,
            dialect_config.same_coalition_learning_multiplier,
        )
    elif qualifying_contact:
        reinforcement = base_reinforcement
        learning = _effective_contact_rate(
            base_learning,
            validated_contact_config.cross_group_learning_multiplier,
        )
    else:
        reinforcement = base_reinforcement
        learning = base_learning

    dialect_rate_applications = 0
    contact_rate_applications = 0
    production_key = (intended_meaning, signal)
    proposed_sender.production[production_key] = _selected_use(
        selected_production,
        tick=validated_tick,
        succeeded=result is CommunicationResult.SUCCESS,
        confidence_delta=(
            reinforcement
            if result is CommunicationResult.SUCCESS
            else -base_reinforcement / 2.0
        ),
    )
    if same_coalition and result is CommunicationResult.SUCCESS:
        dialect_rate_applications += 1
    for key, association in tuple(proposed_sender.production.items()):
        if key != production_key and association.meaning is intended_meaning:
            proposed_sender.production[key] = _weaken_only(
                association, base_reinforcement / 4.0)

    sender_coalition_id = classification.sender_coalition_id
    if qualifying_contact and sender_coalition_id is None:
        _raise(
            "invalid_coalition_communication",
            "cross-coalition contact lacks a source coalition",
        )

    if result is CommunicationResult.SUCCESS:
        assert selected_comprehension is not None
        comprehension_key = (signal, intended_meaning)
        updated_comprehension = _selected_use(
            selected_comprehension,
            tick=validated_tick,
            succeeded=True,
            confidence_delta=reinforcement,
        )
        if qualifying_contact:
            updated_comprehension, candidate_created = (
                _record_contact_exposure(
                    updated_comprehension,
                    tick=validated_tick,
                    source_speaker_id=sender_id,
                    source_coalition_id=sender_coalition_id,
                    succeeded=True,
                )
            )
            if candidate_created:
                proposed_contact.borrowing_candidate_creation_count = (
                    _saturating_add(
                        proposed_contact.borrowing_candidate_creation_count,
                        1,
                        field_name="borrowing_candidate_creation_count",
                    )
                )
        proposed_receiver.comprehension[comprehension_key] = updated_comprehension
        if same_coalition:
            dialect_rate_applications += 1
        for key, association in tuple(proposed_receiver.comprehension.items()):
            if key == comprehension_key:
                continue
            if association.signal == signal:
                proposed_receiver.comprehension[key] = _weaken_only(
                    association, base_reinforcement)
            elif association.meaning is intended_meaning:
                proposed_receiver.comprehension[key] = _weaken_only(
                    association, base_reinforcement / 4.0)

        receiver_production_key = (intended_meaning, signal)
        receiver_production = proposed_receiver.production.get(
            receiver_production_key)
        production_activated = False
        if receiver_production is not None:
            proposed_receiver.production[receiver_production_key] = (
                _observed_without_use(
                    receiver_production,
                    tick=validated_tick,
                    confidence_delta=learning / 2.0,
                )
            )
            production_activated = True
            if same_coalition:
                dialect_rate_applications += 1
            elif qualifying_contact:
                contact_rate_applications += 1
        else:
            exposure = updated_comprehension.contact_exposure
            contact_eligible = (
                qualifying_contact
                and exposure is not None
                and exposure.exposure_count
                >= validated_contact_config.borrowing_exposure_threshold
                and updated_comprehension.confidence
                >= validated_contact_config.borrowing_confidence_threshold
            )
            generic_eligible = (
                updated_comprehension.confidence >= PROMOTION_CONFIDENCE
                and updated_comprehension.successful_uses
                >= PROMOTION_SUCCESS_COUNT
            )
            borrowing_provenance = None
            if contact_eligible:
                assert exposure is not None
                borrowing_provenance = BorrowingProvenance(
                    first_contact_tick=exposure.first_contact_tick,
                    first_source_speaker_id=exposure.first_source_speaker_id,
                    first_source_coalition_id=exposure.first_source_coalition_id,
                    adoption_tick=validated_tick,
                    adoption_source_speaker_id=sender_id,
                    adoption_source_coalition_id=sender_coalition_id,
                    exposure_count_at_adoption=exposure.exposure_count,
                    successful_comprehension_count_at_adoption=(
                        exposure.successful_comprehension_count
                    ),
                )
            if contact_eligible or generic_eligible:
                proposed_receiver.production[receiver_production_key] = (
                    LexicalAssociation(
                        meaning=intended_meaning,
                        signal=signal,
                        confidence=updated_comprehension.confidence,
                        observation_count=1,
                        last_used_tick=validated_tick,
                        origin=AssociationOrigin.LEARNED,
                        learned_from_id=updated_comprehension.learned_from_id,
                        borrowing_provenance=borrowing_provenance,
                    )
                )
                _increment_runtime(
                    proposed_runtime, "learned_association_count")
                if contact_eligible:
                    proposed_contact.borrowing_promotion_count = (
                        _saturating_add(
                            proposed_contact.borrowing_promotion_count,
                            1,
                            field_name="borrowing_promotion_count",
                        )
                    )
                production_activated = True
        if production_activated:
            for key, association in tuple(proposed_receiver.production.items()):
                if key != receiver_production_key and (
                    association.meaning is intended_meaning
                ):
                    proposed_receiver.production[key] = _weaken_only(
                        association, base_reinforcement / 4.0)

    elif result is CommunicationResult.MISUNDERSTANDING:
        assert selected_comprehension is not None
        wrong_key = (signal, selected_comprehension.meaning)
        proposed_receiver.comprehension[wrong_key] = _selected_use(
            selected_comprehension,
            tick=validated_tick,
            succeeded=False,
            confidence_delta=-base_reinforcement,
        )
        correct_key = (signal, intended_meaning)
        correct = proposed_receiver.comprehension.get(correct_key)
        if correct is None:
            updated_correct = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=_confidence(learning),
                observation_count=1,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.LEARNED,
                learned_from_id=sender_id,
            )
            _increment_runtime(proposed_runtime, "learned_association_count")
        else:
            updated_correct = _observed_without_use(
                correct,
                tick=validated_tick,
                confidence_delta=learning,
            )
        if qualifying_contact:
            updated_correct, candidate_created = _record_contact_exposure(
                updated_correct,
                tick=validated_tick,
                source_speaker_id=sender_id,
                source_coalition_id=sender_coalition_id,
                succeeded=False,
            )
            contact_rate_applications += 1
            if candidate_created:
                proposed_contact.borrowing_candidate_creation_count = (
                    _saturating_add(
                        proposed_contact.borrowing_candidate_creation_count,
                        1,
                        field_name="borrowing_candidate_creation_count",
                    )
                )
        proposed_receiver.comprehension[correct_key] = updated_correct
        if same_coalition:
            dialect_rate_applications += 1

    else:
        correct_key = (signal, intended_meaning)
        correct = proposed_receiver.comprehension.get(correct_key)
        if correct is None:
            updated_correct = LexicalAssociation(
                meaning=intended_meaning,
                signal=signal,
                confidence=_confidence(learning),
                observation_count=1,
                last_used_tick=validated_tick,
                origin=AssociationOrigin.LEARNED,
                learned_from_id=sender_id,
            )
            _increment_runtime(proposed_runtime, "learned_association_count")
        else:
            updated_correct = _observed_without_use(
                correct,
                tick=validated_tick,
                confidence_delta=learning,
            )
        if qualifying_contact:
            updated_correct, candidate_created = _record_contact_exposure(
                updated_correct,
                tick=validated_tick,
                source_speaker_id=sender_id,
                source_coalition_id=sender_coalition_id,
                succeeded=False,
            )
            contact_rate_applications += 1
            if candidate_created:
                proposed_contact.borrowing_candidate_creation_count = (
                    _saturating_add(
                        proposed_contact.borrowing_candidate_creation_count,
                        1,
                        field_name="borrowing_candidate_creation_count",
                    )
                )
        proposed_receiver.comprehension[correct_key] = updated_correct
        if same_coalition:
            dialect_rate_applications += 1

    if proposed_dialect is not None and dialect_rate_applications:
        proposed_dialect.same_coalition_rate_application_count = (
            _saturating_add(
                proposed_dialect.same_coalition_rate_application_count,
                dialect_rate_applications,
                field_name="same_coalition_rate_application_count",
            )
        )
    if contact_rate_applications:
        proposed_contact.cross_group_learning_rate_application_count = (
            _saturating_add(
                proposed_contact.cross_group_learning_rate_application_count,
                contact_rate_applications,
                field_name="cross_group_learning_rate_application_count",
            )
        )

    proposed_sender, sender_lost = _retain_canonical(
        proposed_sender, config=config)
    proposed_receiver, receiver_lost = _retain_canonical(
        proposed_receiver, config=config)
    for _ in range(sender_lost + receiver_lost):
        _increment_runtime(proposed_runtime, "lost_association_count")

    _validate_contact_proposal(
        proposed_sender,
        proposed_receiver,
        proposed_runtime,
        proposed_dialect,
        proposed_contact,
        language_config=config,
        contact_config=validated_contact_config,
    )
    _commit_contact_proposal(
        sender,
        receiver,
        runtime,
        dialect_runtime,
        contact_runtime,
        proposed_sender=proposed_sender,
        proposed_receiver=proposed_receiver,
        proposed_runtime=proposed_runtime,
        proposed_dialect=proposed_dialect,
        proposed_contact=proposed_contact,
    )
    return CommunicationOutcome(
        tick=validated_tick,
        sender_id=sender_id,
        receiver_id=receiver_id,
        context=context,
        intended_meaning=intended_meaning,
        produced_signal=signal,
        interpreted_meaning=interpreted,
        result=result,
        coalition_context=classification.context,
        sender_coalition_id=classification.sender_coalition_id,
        receiver_coalition_id=classification.receiver_coalition_id,
    )


def _validate_contact_proposal(
    proposed_sender: AgentLanguageState,
    proposed_receiver: AgentLanguageState,
    proposed_runtime: LanguageRuntimeState,
    proposed_dialect: CoalitionDialectRuntimeState | None,
    proposed_contact: LanguageContactRuntimeState,
    *,
    language_config: LanguageConfig,
    contact_config: LanguageContactConfig,
) -> None:
    """Validate every owner and cross-runtime invariant before contact commit."""
    validate_agent_language_state(
        proposed_sender,
        config=language_config,
        contact_config=contact_config,
    )
    validate_agent_language_state(
        proposed_receiver,
        config=language_config,
        contact_config=contact_config,
    )
    validate_language_runtime(proposed_runtime, initialized=True)
    if proposed_dialect is not None:
        validate_coalition_dialect_runtime(
            proposed_dialect,
            language_runtime=proposed_runtime,
        )
    validate_language_contact_runtime(
        proposed_contact,
        config=contact_config,
        language_runtime=proposed_runtime,
        dialect_runtime=proposed_dialect,
    )


def _commit_contact_proposal(
    sender: LanguageInhabitant,
    receiver: LanguageInhabitant,
    runtime: LanguageRuntimeState,
    dialect_runtime: CoalitionDialectRuntimeState | None,
    contact_runtime: LanguageContactRuntimeState,
    *,
    proposed_sender: AgentLanguageState,
    proposed_receiver: AgentLanguageState,
    proposed_runtime: LanguageRuntimeState,
    proposed_dialect: CoalitionDialectRuntimeState | None,
    proposed_contact: LanguageContactRuntimeState,
) -> None:
    """Commit or restore the complete language/dialect/contact owner set."""
    original_sender = sender.language
    original_receiver = receiver.language
    original_runtime = replace(runtime)
    original_contact = replace(contact_runtime)
    original_dialect = (
        replace(dialect_runtime) if proposed_dialect is not None else None
    )
    try:
        sender.language = proposed_sender
        receiver.language = proposed_receiver
        _commit_runtime(runtime, proposed_runtime)
        if proposed_dialect is not None:
            assert dialect_runtime is not None
            _commit_dialect_runtime(dialect_runtime, proposed_dialect)
        _commit_contact_runtime(contact_runtime, proposed_contact)
    except BaseException:
        sender.language = original_sender
        receiver.language = original_receiver
        _commit_runtime(runtime, original_runtime)
        if original_dialect is not None:
            assert dialect_runtime is not None
            _commit_dialect_runtime(dialect_runtime, original_dialect)
        _commit_contact_runtime(contact_runtime, original_contact)
        raise


def maintain_language_state(
    people: list[LanguageInhabitant],
    newly_dead: list[LanguageInhabitant],
    *,
    tick: int,
    config: LanguageConfig,
    runtime: LanguageRuntimeState,
    contact_config: LanguageContactConfig | None = None,
) -> None:
    """Forget and prune once at the authoritative end-of-tick boundary."""
    _validate_config(config, require_enabled=True)
    validated_tick = _validate_tick(tick)
    validated_runtime = validate_language_runtime(runtime, initialized=True)
    if validated_runtime.language_contact_enabled:
        validated_contact_config = validate_language_contact_config(
            contact_config)
        if not validated_contact_config.language_contact_enabled:
            _raise(
                "invalid_language_contact_config",
                "contact-enabled maintenance requires effective controls",
            )
    elif contact_config is not None:
        _raise(
            "unexpected_language_contact_transaction_inputs",
            "contact-disabled maintenance cannot receive contact controls",
        )
    else:
        validated_contact_config = None

    if any(
        last_tick is not None and validated_tick < last_tick
        for last_tick in (
            runtime.last_communication_tick,
            runtime.last_forgetting_tick,
        )
    ):
        _raise("nonmonotonic_language_tick", "maintenance tick moved backward")

    due = (
        validated_tick > 0
        and validated_tick % config.language_forgetting_interval == 0
    )
    if due and runtime.last_forgetting_tick == validated_tick:
        _raise("duplicate_language_maintenance", "forgetting already ran for this tick")
    if not due and not newly_dead:
        return

    active_ids: set[int] = set()
    dead_ids: set[int] = set()
    seen_state_identities: set[int] = set()
    active_states: list[tuple[LanguageInhabitant, AgentLanguageState]] = []
    dead_states: list[tuple[LanguageInhabitant, AgentLanguageState]] = []
    has_active_associations = False
    for inhabitant in people:
        inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
        if not _exact_nonnegative_int(inhabitant_id):
            _raise("invalid_language_identity", "maintenance requires assigned IDs")
        if inhabitant_id in active_ids:
            _raise("duplicate_language_identity", f"duplicate active ID {inhabitant_id}")
        active_ids.add(inhabitant_id)
        validated_state = validate_agent_language_state(
            inhabitant.language,
            config=config,
            contact_config=validated_contact_config,
        )
        _validate_state_tick(validated_state, tick=validated_tick)
        state_identity = _language_state_identity(validated_state)
        if state_identity in seen_state_identities:
            _raise("aliased_agent_language_state", "agents cannot share language state")
        seen_state_identities.add(state_identity)
        active_states.append((inhabitant, validated_state))
        has_active_associations = has_active_associations or bool(
            validated_state.production or validated_state.comprehension)
    for inhabitant in newly_dead:
        inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
        if not _exact_nonnegative_int(inhabitant_id):
            _raise("invalid_language_identity", "maintenance requires assigned IDs")
        if inhabitant_id in active_ids:
            _raise("active_dead_language_identity", "dead inhabitant remains active")
        if inhabitant_id in dead_ids:
            _raise("duplicate_language_identity", f"duplicate dead ID {inhabitant_id}")
        dead_ids.add(inhabitant_id)
        validated_state = validate_agent_language_state(
            inhabitant.language,
            config=config,
            contact_config=validated_contact_config,
        )
        _validate_state_tick(validated_state, tick=validated_tick)
        state_identity = _language_state_identity(validated_state)
        if state_identity in seen_state_identities:
            _raise("aliased_agent_language_state", "agents cannot share language state")
        seen_state_identities.add(state_identity)
        dead_states.append((inhabitant, validated_state))

    if due and not newly_dead and not has_active_associations:
        # An interval boundary with no lexical candidates is a true no-op.
        return

    proposed_runtime = replace(runtime)
    proposed_states: list[
        tuple[LanguageInhabitant, AgentLanguageState, AgentLanguageState]
    ] = []
    forgetting_delta = config.language_reinforcement_rate / 2.0

    for inhabitant, current_state in active_states:
        proposed = _copy_agent_state(current_state)
        if due:
            for key, association in tuple(proposed.production.items()):
                if (
                    validated_tick - association.last_used_tick
                    >= config.language_forgetting_interval
                ):
                    proposed.production[key] = _weaken_only(
                        association, forgetting_delta)
            for key, association in tuple(proposed.comprehension.items()):
                if (
                    validated_tick - association.last_used_tick
                    >= config.language_forgetting_interval
                ):
                    proposed.comprehension[key] = _weaken_only(
                        association, forgetting_delta)
        proposed, lost = _retain_canonical(proposed, config=config)
        for _ in range(lost):
            _increment_runtime(proposed_runtime, "lost_association_count")
        validate_agent_language_state(
            proposed,
            config=config,
            contact_config=validated_contact_config,
        )
        proposed_states.append((inhabitant, current_state, proposed))

    for inhabitant, current_state in dead_states:
        lost = len(current_state.production) + len(current_state.comprehension)
        for _ in range(lost):
            _increment_runtime(proposed_runtime, "lost_association_count")
        proposed_states.append((
            inhabitant,
            current_state,
            AgentLanguageState(
                next_invention_index=current_state.next_invention_index),
        ))

    if due:
        proposed_runtime.last_forgetting_tick = validated_tick
    validate_language_runtime(proposed_runtime, initialized=True)

    original_runtime = replace(runtime)
    try:
        for inhabitant, _original, proposed in proposed_states:
            inhabitant.language = proposed
        _commit_runtime(runtime, proposed_runtime)
    except BaseException:
        for inhabitant, original, _proposed in proposed_states:
            inhabitant.language = original
        _commit_runtime(runtime, original_runtime)
        raise


def _contact_exposure_record(exposure: ContactExposure) -> dict[str, int]:
    """Return immutable comprehension-contact facts as JSON-safe integers."""
    return {
        "first_contact_tick": exposure.first_contact_tick,
        "first_source_speaker_id": exposure.first_source_speaker_id,
        "first_source_coalition_id": exposure.first_source_coalition_id,
        "exposure_count": exposure.exposure_count,
        "successful_comprehension_count": (
            exposure.successful_comprehension_count
        ),
    }


def _borrowing_provenance_record(
    provenance: BorrowingProvenance,
) -> dict[str, int]:
    """Return immutable production-borrowing facts as JSON-safe integers."""
    return {
        "first_contact_tick": provenance.first_contact_tick,
        "first_source_speaker_id": provenance.first_source_speaker_id,
        "first_source_coalition_id": provenance.first_source_coalition_id,
        "adoption_tick": provenance.adoption_tick,
        "adoption_source_speaker_id": provenance.adoption_source_speaker_id,
        "adoption_source_coalition_id": provenance.adoption_source_coalition_id,
        "exposure_count_at_adoption": provenance.exposure_count_at_adoption,
        "successful_comprehension_count_at_adoption": (
            provenance.successful_comprehension_count_at_adoption
        ),
    }


def association_record(
    association: LexicalAssociation,
    *,
    include_contact: bool = False,
) -> dict[str, object]:
    """Return one association using only canonical JSON-safe primitives."""
    result: dict[str, object] = {
        "meaning": association.meaning.name,
        "signal": list(association.signal.phoneme_ids),
        "confidence": association.confidence,
        "successful_uses": association.successful_uses,
        "failed_uses": association.failed_uses,
        "observation_count": association.observation_count,
        "last_used_tick": association.last_used_tick,
        "origin": association.origin.value,
        "learned_from_id": association.learned_from_id,
    }
    if include_contact:
        result["contact_exposure"] = (
            _contact_exposure_record(association.contact_exposure)
            if association.contact_exposure is not None else None
        )
        result["borrowing_provenance"] = (
            _borrowing_provenance_record(association.borrowing_provenance)
            if association.borrowing_provenance is not None else None
        )
    return result


def agent_language_record(
    inhabitant: LanguageInhabitant,
    *,
    config: LanguageConfig,
    include_contact: bool = False,
    contact_config: LanguageContactConfig | None = None,
) -> dict[str, object]:
    """Return one agent's complete language state in canonical order."""
    if type(include_contact) is not bool:
        _raise(
            "invalid_language_contact_config",
            "contact serialization gate must be boolean",
        )
    if include_contact:
        validated_contact = validate_language_contact_config(contact_config)
        if not validated_contact.language_contact_enabled:
            _raise(
                "language_contact_processing_disabled",
                "contact serialization requires effective contact processing",
            )
    elif contact_config is not None:
        _raise(
            "unexpected_language_contact_transaction_inputs",
            "disabled contact serialization cannot receive contact controls",
        )
    inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
    if not _exact_nonnegative_int(inhabitant_id):
        _raise("invalid_language_identity", "snapshot requires an assigned ID")
    state = validate_agent_language_state(
        inhabitant.language,
        config=config,
        contact_config=contact_config if include_contact else None,
    )
    return {
        "inhabitant_id": inhabitant_id,
        "next_invention_index": state.next_invention_index,
        "production": [
            association_record(association, include_contact=include_contact)
            for _key, association in sorted(
                state.production.items(),
                key=lambda item: (
                    MEANING_ORDER[item[0][0]], item[0][1].phoneme_ids),
            )
        ],
        "comprehension": [
            association_record(association, include_contact=include_contact)
            for _key, association in sorted(
                state.comprehension.items(),
                key=lambda item: (
                    item[0][0].phoneme_ids, MEANING_ORDER[item[0][1]]),
            )
        ],
    }


def canonical_language_snapshot(
    people: Iterable[LanguageInhabitant],
    *,
    config: LanguageConfig,
) -> list[dict[str, object]]:
    """Return canonical bounded language state for tests and inspection."""
    records = [agent_language_record(inhabitant, config=config) for inhabitant in people]
    identities = [record["inhabitant_id"] for record in records]
    if len(identities) != len(set(identities)):
        _raise("duplicate_language_identity", "snapshot inhabitant IDs must be unique")
    return sorted(records, key=lambda record: record["inhabitant_id"])


def language_runtime_record(runtime: LanguageRuntimeState) -> dict[str, object]:
    """Return enabled runtime state without implementation-specific objects."""
    validate_language_runtime(runtime, initialized=True)
    result = {
        "seed_domain_fingerprint": runtime.seed_domain_fingerprint,
        "communication_attempt_count": runtime.communication_attempt_count,
        "successful_interpretation_count": runtime.successful_interpretation_count,
        "misunderstanding_count": runtime.misunderstanding_count,
        "unknown_signal_count": runtime.unknown_signal_count,
        "no_signal_count": runtime.no_signal_count,
        "invention_count": runtime.invention_count,
        "learned_association_count": runtime.learned_association_count,
        "lost_association_count": runtime.lost_association_count,
        "last_communication_tick": runtime.last_communication_tick,
        "last_forgetting_tick": runtime.last_forgetting_tick,
    }
    if runtime.coalition_dialect_influence_enabled:
        result["coalition_dialect_influence_enabled"] = True
    if runtime.language_contact_enabled:
        result["language_contact_enabled"] = True
    return result


def coalition_dialect_runtime_record(
    runtime: CoalitionDialectRuntimeState,
    *,
    language_runtime: LanguageRuntimeState,
) -> dict[str, object]:
    """Return canonical bounded dialect counters for enabled hashing."""
    validate_coalition_dialect_runtime(
        runtime,
        language_runtime=language_runtime,
    )
    return {
        "same_coalition_communication_count": (
            runtime.same_coalition_communication_count
        ),
        "different_coalition_communication_count": (
            runtime.different_coalition_communication_count
        ),
        "assigned_unassigned_communication_count": (
            runtime.assigned_unassigned_communication_count
        ),
        "both_unassigned_communication_count": (
            runtime.both_unassigned_communication_count
        ),
        "same_coalition_rate_application_count": (
            runtime.same_coalition_rate_application_count
        ),
        "last_classification_tick": runtime.last_classification_tick,
    }


def language_contact_runtime_record(
    runtime: LanguageContactRuntimeState,
    *,
    language_runtime: LanguageRuntimeState,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
) -> dict[str, object]:
    """Return canonical bounded contact controls and observability state."""
    validate_language_contact_runtime(
        runtime,
        language_runtime=language_runtime,
        dialect_runtime=dialect_runtime,
    )
    return {
        "cross_group_learning_multiplier": (
            runtime.cross_group_learning_multiplier
        ),
        "borrowing_exposure_threshold": runtime.borrowing_exposure_threshold,
        "borrowing_confidence_threshold": (
            runtime.borrowing_confidence_threshold
        ),
        "cross_coalition_contact_attempt_count": (
            runtime.cross_coalition_contact_attempt_count
        ),
        "cross_coalition_success_count": runtime.cross_coalition_success_count,
        "cross_coalition_misunderstanding_count": (
            runtime.cross_coalition_misunderstanding_count
        ),
        "cross_coalition_unknown_signal_count": (
            runtime.cross_coalition_unknown_signal_count
        ),
        "cross_coalition_no_signal_count": (
            runtime.cross_coalition_no_signal_count
        ),
        "cross_group_learning_rate_application_count": (
            runtime.cross_group_learning_rate_application_count
        ),
        "borrowing_candidate_creation_count": (
            runtime.borrowing_candidate_creation_count
        ),
        "borrowing_promotion_count": runtime.borrowing_promotion_count,
        "borrowed_production_use_count": runtime.borrowed_production_use_count,
        "last_contact_tick": runtime.last_contact_tick,
    }


def lexical_convergence_snapshot(
    people: Iterable[LanguageInhabitant],
    *,
    config: LanguageConfig,
    inhabitant_ids: Iterable[int] | None = None,
) -> dict[str, object]:
    """Calculate local or population agreement without pairwise enumeration."""
    selected_ids = None
    if inhabitant_ids is not None:
        selected = tuple(inhabitant_ids)
        if any(not _exact_nonnegative_int(item) for item in selected):
            _raise("invalid_language_identity", "subset IDs are invalid")
        if len(selected) != len(set(selected)):
            _raise("invalid_language_identity", "subset IDs must be unique")
        selected_ids = frozenset(selected)

    ordered_people = sorted(
        people,
        key=lambda inhabitant: getattr(inhabitant, "inhabitant_id", -1),
    )
    ordered_ids = [getattr(inhabitant, "inhabitant_id", None) for inhabitant in ordered_people]
    if len(ordered_ids) != len(set(ordered_ids)):
        _raise("duplicate_language_identity", "summary inhabitant IDs must be unique")
    by_meaning: list[dict[str, object]] = []
    agreement_values: list[float] = []
    for meaning in Meaning:
        counts: dict[Signal, int] = {}
        active_signals: set[Signal] = set()
        for inhabitant in ordered_people:
            inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
            if not _exact_nonnegative_int(inhabitant_id):
                _raise("invalid_language_identity", "summary requires assigned IDs")
            if selected_ids is not None and inhabitant_id not in selected_ids:
                continue
            state = validate_agent_language_state(inhabitant.language, config=config)
            active_signals.update(
                association.signal
                for association in state.production.values()
                if association.meaning is meaning
                and association.confidence >= MIN_USABLE_CONFIDENCE
            )
            strongest = _select_production(state, meaning)
            if strongest is not None:
                counts[strongest.signal] = counts.get(strongest.signal, 0) + 1
        speakers = sum(counts.values())
        if speakers >= 2:
            numerator = sum(count * (count - 1) for count in counts.values())
            agreement = _quantize(numerator / (speakers * (speakers - 1)))
            agreement_values.append(agreement)
        else:
            agreement = 0.0
        dominant = (
            min(counts, key=lambda signal: (-counts[signal], signal.phoneme_ids))
            if counts else None
        )
        by_meaning.append({
            "meaning": meaning.name,
            "speaker_count": speakers,
            "active_signal_count": len(active_signals),
            "dominant_signal": (
                list(dominant.phoneme_ids) if dominant is not None else None
            ),
            "signal_frequencies": [
                {"signal": list(signal.phoneme_ids), "count": count}
                for signal, count in sorted(
                    counts.items(), key=lambda item: item[0].phoneme_ids)
            ],
            "pairwise_agreement": agreement,
        })
    population_agreement = (
        _quantize(sum(agreement_values) / len(agreement_values))
        if agreement_values else 0.0
    )
    return {
        "meanings": by_meaning,
        "population_agreement": population_agreement,
    }


def _dialect_meaning_summary(
    counts: dict[Signal, int],
    *,
    meaning: Meaning,
    member_count: int,
) -> dict[str, object]:
    speakers = sum(counts.values())
    agreement = None
    if speakers >= 2:
        numerator = sum(count * (count - 1) for count in counts.values())
        agreement = _quantize(numerator / (speakers * (speakers - 1)))
    dominant = (
        min(counts, key=lambda signal: (-counts[signal], signal.phoneme_ids))
        if counts else None
    )
    return {
        "meaning": meaning.name,
        "speaker_count": speakers,
        "non_speaker_count": member_count - speakers,
        "dominant_signal": (
            list(dominant.phoneme_ids) if dominant is not None else None
        ),
        "signal_frequencies": [
            {"signal": list(signal.phoneme_ids), "count": count}
            for signal, count in sorted(
                counts.items(), key=lambda item: item[0].phoneme_ids)
        ],
        "pairwise_agreement": agreement,
    }


def coalition_dialect_summary(
    people: Iterable[LanguageInhabitant],
    *,
    snapshot: CoalitionMembershipSnapshot,
    language_config: LanguageConfig,
    dialect_config: CoalitionDialectConfig,
    language_runtime: LanguageRuntimeState,
    dialect_runtime: CoalitionDialectRuntimeState,
) -> dict[str, object]:
    """Summarize current agent lexicons by frozen coalition in O(P x L)."""
    _validate_config(language_config, require_enabled=True)
    validated_dialect = validate_coalition_dialect_config(dialect_config)
    if not validated_dialect.coalition_dialect_influence_enabled:
        _raise(
            "dialect_processing_disabled",
            "dialect summaries require effective influence",
        )
    if type(snapshot) is not CoalitionMembershipSnapshot:
        validate_coalition_membership_snapshot(snapshot, tick=1)
    validated_snapshot = validate_coalition_membership_snapshot(
        snapshot,
        tick=snapshot.snapshot_tick,
    )
    runtime_record = coalition_dialect_runtime_record(
        dialect_runtime,
        language_runtime=language_runtime,
    )

    coalition_ids = validated_snapshot.active_coalition_ids
    coalition_id_set = frozenset(coalition_ids)
    member_counts = {coalition_id: 0 for coalition_id in coalition_ids}
    signal_counts = {
        coalition_id: {meaning: {} for meaning in Meaning}
        for coalition_id in coalition_ids
    }
    unassigned_member_count = 0
    unassigned_counts: dict[Meaning, dict[Signal, int]] = {
        meaning: {} for meaning in Meaning
    }
    remaining_active_ids = set(
        validated_snapshot._active_inhabitant_id_set)

    for inhabitant in people:
        inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
        if not _exact_nonnegative_int(inhabitant_id):
            _raise(
                "invalid_language_identity",
                "dialect summary requires assigned IDs",
            )
        if inhabitant_id not in validated_snapshot._active_inhabitant_id_set:
            _raise(
                "dialect_summary_snapshot_mismatch",
                "summary inhabitants must equal the frozen active-ID snapshot",
            )
        if inhabitant_id not in remaining_active_ids:
            _raise(
                "duplicate_language_identity",
                "dialect summary IDs must be unique",
            )
        remaining_active_ids.remove(inhabitant_id)
        coalition_id = validated_snapshot._member_to_coalition.get(
            inhabitant_id)
        if coalition_id is not None and coalition_id not in coalition_id_set:
            _raise(
                "invalid_coalition_membership_snapshot",
                "snapshot membership references an inactive coalition",
            )
        state = validate_agent_language_state(
            inhabitant.language,
            config=language_config,
        )
        if coalition_id is None:
            unassigned_member_count += 1
            destination = unassigned_counts
        else:
            member_counts[coalition_id] += 1
            destination = signal_counts[coalition_id]
        for meaning in Meaning:
            strongest = _select_production(state, meaning)
            if strongest is None:
                continue
            counts = destination[meaning]
            counts[strongest.signal] = counts.get(strongest.signal, 0) + 1

    if remaining_active_ids:
        _raise(
            "dialect_summary_snapshot_mismatch",
            "summary inhabitants must equal the frozen active-ID snapshot",
        )

    coalition_records: list[dict[str, object]] = []
    for coalition_id in coalition_ids:
        meanings = [
            _dialect_meaning_summary(
                signal_counts[coalition_id][meaning],
                meaning=meaning,
                member_count=member_counts[coalition_id],
            )
            for meaning in Meaning
        ]
        usable_agreements = [
            record["pairwise_agreement"]
            for record in meanings
            if record["pairwise_agreement"] is not None
        ]
        coalition_records.append({
            "coalition_id": coalition_id,
            "active_member_count": member_counts[coalition_id],
            "meanings": meanings,
            "mean_agreement": (
                _quantize(sum(usable_agreements) / len(usable_agreements))
                if usable_agreements else None
            ),
        })

    between_records: list[dict[str, object]] = []
    for meaning in Meaning:
        eligible = [
            signal_counts[coalition_id][meaning]
            for coalition_id in coalition_ids
            if sum(signal_counts[coalition_id][meaning].values()) >= 2
        ]
        distance = None
        if len(eligible) >= 2:
            speaker_totals = [sum(counts.values()) for counts in eligible]
            total_speakers = sum(speaker_totals)
            cross_pairs = (
                total_speakers * total_speakers
                - sum(total * total for total in speaker_totals)
            ) // 2
            aggregate: dict[Signal, int] = {}
            within_signal_squares: dict[Signal, int] = {}
            for counts in eligible:
                for signal, count in counts.items():
                    aggregate[signal] = aggregate.get(signal, 0) + count
                    within_signal_squares[signal] = (
                        within_signal_squares.get(signal, 0) + count * count
                    )
            matching_cross_pairs = sum(
                aggregate[signal] * aggregate[signal]
                - within_signal_squares[signal]
                for signal in aggregate
            ) // 2
            distance = _quantize(
                (cross_pairs - matching_cross_pairs) / cross_pairs)
        between_records.append({
            "meaning": meaning.name,
            "sufficient_coalition_count": len(eligible),
            "lexical_distance": distance,
        })

    unassigned_meanings = [
        _dialect_meaning_summary(
            unassigned_counts[meaning],
            meaning=meaning,
            member_count=unassigned_member_count,
        )
        for meaning in Meaning
    ]
    return {
        "snapshot_tick": validated_snapshot.snapshot_tick,
        "active_coalition_count": len(coalition_ids),
        "coalitions": coalition_records,
        "between_coalitions": between_records,
        "unassigned": {
            "member_count": unassigned_member_count,
            "meanings": unassigned_meanings,
        },
        "runtime": runtime_record,
    }


def _contact_summary_group_record(
    aggregate: dict[str, object],
) -> dict[str, object]:
    """Render one commutatively aggregated current-membership group."""
    signal_counts = aggregate["selected_borrowed_signal_counts"]
    assert type(signal_counts) is dict
    usable_total = aggregate["usable_production_association_count"]
    usable_borrowed = aggregate[
        "usable_borrowed_production_association_count"
    ]
    borrowed_frequencies = [
        {
            "meaning": meaning.name,
            "signals": [
                {
                    "signal": list(signal.phoneme_ids),
                    "count": count,
                }
                for signal, count in sorted(
                    signal_counts[meaning].items(),
                    key=lambda item: item[0].phoneme_ids,
                )
            ],
        }
        for meaning in Meaning
    ]
    return {
        "member_count": aggregate["member_count"],
        "contact_exposed_comprehension_count": (
            aggregate["contact_exposed_comprehension_count"]
        ),
        "contact_exposure_count": aggregate["contact_exposure_count"],
        "successful_contact_comprehension_count": (
            aggregate["successful_contact_comprehension_count"]
        ),
        "usable_production_association_count": usable_total,
        "usable_borrowed_production_association_count": usable_borrowed,
        # Retained compatibility field, now using the required usable rule.
        "borrowed_production_count": usable_borrowed,
        "borrowed_production_carrier_count": aggregate[
            "borrowed_production_carrier_count"
        ],
        "mixed_production_carrier_count": aggregate[
            "mixed_production_carrier_count"
        ],
        "borrowed_association_share": (
            _quantize(usable_borrowed / usable_total)
            if usable_total else None
        ),
        # The compatibility name and explicit name both describe selected,
        # currently usable borrowed production rather than every synonym.
        "borrowed_production_frequencies": borrowed_frequencies,
        "selected_borrowed_signal_frequencies": borrowed_frequencies,
    }


def _new_contact_summary_group() -> dict[str, object]:
    """Return one constant-shape mutable aggregate for a current group."""
    return {
        "member_count": 0,
        "contact_exposed_comprehension_count": 0,
        "contact_exposure_count": 0,
        "successful_contact_comprehension_count": 0,
        "usable_production_association_count": 0,
        "usable_borrowed_production_association_count": 0,
        "borrowed_production_carrier_count": 0,
        "mixed_production_carrier_count": 0,
        "selected_borrowed_signal_counts": {
            meaning: {} for meaning in Meaning
        },
    }


def language_contact_summary(
    people: Iterable[LanguageInhabitant],
    *,
    snapshot: CoalitionMembershipSnapshot,
    language_config: LanguageConfig,
    contact_config: LanguageContactConfig,
    language_runtime: LanguageRuntimeState,
    contact_runtime: LanguageContactRuntimeState,
) -> dict[str, object]:
    """Aggregate current contact and borrowing state in one O(P x L) pass.

    Historical source diversity canonically uses borrowing provenance's
    ``first_source_coalition_id``; current coalition activity is irrelevant.
    """
    _validate_config(language_config, require_enabled=True)
    validated_contact_config = validate_language_contact_config(contact_config)
    if not validated_contact_config.language_contact_enabled:
        _raise(
            "language_contact_processing_disabled",
            "contact summaries require effective contact processing",
        )
    validated_language_runtime = validate_language_runtime(
        language_runtime,
        initialized=True,
    )
    if not validated_language_runtime.language_contact_enabled:
        _raise(
            "language_contact_runtime_gate_mismatch",
            "contact summary requires the authoritative runtime gate",
        )
    validate_language_contact_runtime(
        contact_runtime,
        config=validated_contact_config,
        language_runtime=validated_language_runtime,
    )
    if type(snapshot) is not CoalitionMembershipSnapshot:
        validate_coalition_membership_snapshot(snapshot, tick=1)
    validated_snapshot = validate_coalition_membership_snapshot(
        snapshot,
        tick=snapshot.snapshot_tick,
    )

    coalition_ids = validated_snapshot.active_coalition_ids
    coalition_id_set = frozenset(coalition_ids)
    groups = {
        coalition_id: _new_contact_summary_group()
        for coalition_id in coalition_ids
    }
    unassigned = _new_contact_summary_group()
    remaining_active_ids = set(
        validated_snapshot._active_inhabitant_id_set)
    source_coalition_counts: dict[int, dict[str, int]] = {}
    usable_borrowing_source_coalition_ids: set[int] = set()
    coalition_selected_signal_counts = {
        coalition_id: {meaning: {} for meaning in Meaning}
        for coalition_id in coalition_ids
    }

    for inhabitant in people:
        inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
        if not _exact_nonnegative_int(inhabitant_id):
            _raise(
                "invalid_language_identity",
                "contact summary requires assigned IDs",
            )
        if inhabitant_id not in validated_snapshot._active_inhabitant_id_set:
            _raise(
                "language_contact_summary_snapshot_mismatch",
                "summary inhabitants must equal the frozen active-ID snapshot",
            )
        if inhabitant_id not in remaining_active_ids:
            _raise(
                "duplicate_language_identity",
                "contact summary IDs must be unique",
            )
        remaining_active_ids.remove(inhabitant_id)
        coalition_id = validated_snapshot._member_to_coalition.get(
            inhabitant_id)
        if coalition_id is not None and coalition_id not in coalition_id_set:
            _raise(
                "invalid_coalition_membership_snapshot",
                "snapshot membership references an inactive coalition",
            )
        aggregate = unassigned if coalition_id is None else groups[coalition_id]
        aggregate["member_count"] += 1

        state = validate_agent_language_state(
            inhabitant.language,
            config=language_config,
            contact_config=validated_contact_config,
        )
        for association in state.comprehension.values():
            exposure = association.contact_exposure
            if exposure is None:
                continue
            aggregate["contact_exposed_comprehension_count"] += 1
            aggregate["contact_exposure_count"] += exposure.exposure_count
            aggregate["successful_contact_comprehension_count"] += (
                exposure.successful_comprehension_count
            )
            source_counts = source_coalition_counts.setdefault(
                exposure.first_source_coalition_id,
                {
                    "first_contact_association_count": 0,
                    "borrowed_production_count": 0,
                },
            )
            source_counts["first_contact_association_count"] += 1

        selected_by_meaning: dict[Meaning, LexicalAssociation] = {}
        borrowed_meanings: set[Meaning] = set()
        nonborrowed_meanings: set[Meaning] = set()
        for association in state.production.values():
            if association.confidence < MIN_USABLE_CONFIDENCE:
                continue
            aggregate["usable_production_association_count"] += 1
            provenance = association.borrowing_provenance
            if provenance is None:
                nonborrowed_meanings.add(association.meaning)
            else:
                borrowed_meanings.add(association.meaning)
                aggregate[
                    "usable_borrowed_production_association_count"
                ] += 1
                # first_source_coalition_id is the canonical historical source
                # field for current borrowing-diversity observability.
                usable_borrowing_source_coalition_ids.add(
                    provenance.first_source_coalition_id
                )
                source_counts = source_coalition_counts.setdefault(
                    provenance.first_source_coalition_id,
                    {
                        "first_contact_association_count": 0,
                        "borrowed_production_count": 0,
                    },
                )
                source_counts["borrowed_production_count"] += 1

            selected = selected_by_meaning.get(association.meaning)
            if selected is None or (
                -association.confidence,
                association.signal.phoneme_ids,
            ) < (
                -selected.confidence,
                selected.signal.phoneme_ids,
            ):
                selected_by_meaning[association.meaning] = association

        if borrowed_meanings:
            aggregate["borrowed_production_carrier_count"] += 1
        if borrowed_meanings.intersection(nonborrowed_meanings):
            aggregate["mixed_production_carrier_count"] += 1

        selected_borrowed_counts = aggregate[
            "selected_borrowed_signal_counts"
        ]
        assert type(selected_borrowed_counts) is dict
        for meaning, selected in selected_by_meaning.items():
            if selected.borrowing_provenance is not None:
                meaning_counts = selected_borrowed_counts[meaning]
                meaning_counts[selected.signal] = (
                    meaning_counts.get(selected.signal, 0) + 1
                )
            if coalition_id is not None:
                coalition_meaning_counts = (
                    coalition_selected_signal_counts[coalition_id][meaning]
                )
                coalition_meaning_counts[selected.signal] = (
                    coalition_meaning_counts.get(selected.signal, 0) + 1
                )

    if remaining_active_ids:
        _raise(
            "language_contact_summary_snapshot_mismatch",
            "summary inhabitants must equal the frozen active-ID snapshot",
        )

    totals = _new_contact_summary_group()
    for aggregate in (*groups.values(), unassigned):
        for name in (
            "member_count",
            "contact_exposed_comprehension_count",
            "contact_exposure_count",
            "successful_contact_comprehension_count",
            "usable_production_association_count",
            "usable_borrowed_production_association_count",
            "borrowed_production_carrier_count",
            "mixed_production_carrier_count",
        ):
            totals[name] += aggregate[name]
        total_signal_counts = totals["selected_borrowed_signal_counts"]
        group_signal_counts = aggregate["selected_borrowed_signal_counts"]
        assert type(total_signal_counts) is dict
        assert type(group_signal_counts) is dict
        for meaning in Meaning:
            for signal, count in group_signal_counts[meaning].items():
                total_signal_counts[meaning][signal] = (
                    total_signal_counts[meaning].get(signal, 0) + count
                )

    between_coalition_records: list[dict[str, object]] = []
    defined_distances: list[float] = []
    for meaning in Meaning:
        eligible_coalition_count = 0
        selected_speaker_count = 0
        sum_coalition_squares = 0
        aggregate_signal_counts: dict[Signal, int] = {}
        within_coalition_signal_squares: dict[Signal, int] = {}
        for coalition_id in coalition_ids:
            counts = coalition_selected_signal_counts[coalition_id][meaning]
            coalition_speakers = sum(counts.values())
            if coalition_speakers == 0:
                continue
            eligible_coalition_count += 1
            selected_speaker_count += coalition_speakers
            sum_coalition_squares += coalition_speakers * coalition_speakers
            for signal, count in counts.items():
                aggregate_signal_counts[signal] = (
                    aggregate_signal_counts.get(signal, 0) + count
                )
                within_coalition_signal_squares[signal] = (
                    within_coalition_signal_squares.get(signal, 0)
                    + count * count
                )

        total_cross_pairs = (
            selected_speaker_count * selected_speaker_count
            - sum_coalition_squares
        )
        distance = None
        if eligible_coalition_count >= 2 and total_cross_pairs > 0:
            matching_cross_pairs = sum(
                count * count - within_coalition_signal_squares[signal]
                for signal, count in aggregate_signal_counts.items()
            )
            distance = _quantize(
                1.0 - matching_cross_pairs / total_cross_pairs
            )
            defined_distances.append(distance)
        between_coalition_records.append({
            "meaning": meaning.name,
            "eligible_coalition_count": eligible_coalition_count,
            "selected_speaker_count": selected_speaker_count,
            "lexical_distance": distance,
        })

    comprehension_denominator = (
        contact_runtime.cross_coalition_success_count
        + contact_runtime.cross_coalition_misunderstanding_count
        + contact_runtime.cross_coalition_unknown_signal_count
    )
    comprehension_success_rate = (
        _quantize(
            contact_runtime.cross_coalition_success_count
            / comprehension_denominator
        )
        if comprehension_denominator else None
    )

    return {
        "snapshot_tick": validated_snapshot.snapshot_tick,
        "active_coalition_count": len(coalition_ids),
        "totals": _contact_summary_group_record(totals),
        "coalitions": [
            {
                "coalition_id": coalition_id,
                **_contact_summary_group_record(groups[coalition_id]),
            }
            for coalition_id in sorted(coalition_ids)
        ],
        "unassigned": _contact_summary_group_record(unassigned),
        "source_coalition_diversity_count": len(
            usable_borrowing_source_coalition_ids
        ),
        "cross_coalition_comprehension_success_rate": (
            comprehension_success_rate
        ),
        "between_coalitions": between_coalition_records,
        "mean_between_coalition_lexical_distance": (
            _quantize(sum(defined_distances) / len(defined_distances))
            if defined_distances else None
        ),
        "historical_source_coalitions": [
            {
                "coalition_id": coalition_id,
                **source_coalition_counts[coalition_id],
            }
            for coalition_id in sorted(source_coalition_counts)
        ],
        "runtime": language_contact_runtime_record(
            contact_runtime,
            language_runtime=validated_language_runtime,
        ),
    }
