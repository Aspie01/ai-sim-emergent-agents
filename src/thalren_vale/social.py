"""Bounded, deterministic inhabitant relationship state.

Only authentic committed aid and trade outcomes are live in the first
Endogenous Social Order slice.  This module intentionally contains no random
number generation and no faction-, combat-, or institution-level behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Protocol


class SocialConfig(Protocol):
    """Configuration fields required by relationship operations."""

    social_memory_enabled: bool
    social_partner_bias_enabled: bool
    maximum_social_ties: int
    relationship_decay_interval: int


class SocialInhabitant(Protocol):
    """Minimal inhabitant interface used by the social subsystem."""

    inhabitant_id: int | None
    relationships: dict[int, "Relationship"]


class InteractionKind(str, Enum):
    """Closed set of authentic interaction outcomes implemented in v1."""

    AID = "aid"
    TRADE = "trade"


@dataclass(slots=True)
class Relationship:
    """One directed, bounded relationship from an inhabitant to a target."""

    trust: float = 0.0
    affinity: float = 0.0
    grievance: float = 0.0
    obligation: float = 0.0
    familiarity: float = 0.0
    intelligibility: float = 0.0
    interaction_count: int = 0
    last_interaction_tick: int = 0


@dataclass(frozen=True)
class RelationshipSummary:
    """Bounded deterministic observability for tests and internal inspection."""

    active_directed_ties: int
    positive_trust_ties: int
    negative_trust_ties: int
    mean_trust: float
    mean_grievance: float


_AID_RECIPIENT_DELTA = {
    "trust": 0.08,
    "affinity": 0.02,
    "obligation": 0.10,
    "familiarity": 0.08,
}
_AID_HELPER_DELTA = {
    "affinity": 0.01,
    "familiarity": 0.04,
}
INTELLIGIBILITY_PREFERENCE_WEIGHT = 0.40
_TRADE_DELTA = {
    "trust": 0.03,
    "affinity": 0.01,
    "familiarity": 0.08,
}


def _assigned_id(inhabitant: SocialInhabitant, role: str) -> int:
    inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
    if type(inhabitant_id) is not int or inhabitant_id < 0:
        raise ValueError(f"{role} must have an assigned nonnegative inhabitant ID")
    return inhabitant_id


def _validate_tick(tick: object) -> int:
    if type(tick) is not int or tick < 0:
        raise ValueError("interaction tick must be a nonnegative integer")
    return tick


def _validate_magnitude(magnitude: object) -> float:
    if isinstance(magnitude, bool) or not isinstance(magnitude, (int, float)):
        raise TypeError("interaction magnitude must be a finite number")
    value = float(magnitude)
    if not math.isfinite(value) or not 0.0 < value <= 1.0:
        raise ValueError("interaction magnitude must be in (0.0, 1.0]")
    return value


def _quantize(value: float) -> float:
    return round(value, 6)


def _clamp(value: float, lower: float, upper: float) -> float:
    return _quantize(max(lower, min(upper, value)))


def _validate_record_tick(
    owner: SocialInhabitant,
    target_id: int,
    tick: int,
) -> None:
    current = owner.relationships.get(target_id)
    if current is not None and tick < current.last_interaction_tick:
        raise ValueError("interaction tick cannot precede the existing relationship tick")


def _apply_delta(
    owner: SocialInhabitant,
    target_id: int,
    delta: dict[str, float],
    *,
    tick: int,
    magnitude: float,
) -> None:
    record = owner.relationships.get(target_id)
    if record is None:
        record = Relationship(last_interaction_tick=tick)
        owner.relationships[target_id] = record

    record.trust = _clamp(
        record.trust + delta.get("trust", 0.0) * magnitude, -1.0, 1.0)
    record.affinity = _clamp(
        record.affinity + delta.get("affinity", 0.0) * magnitude, -1.0, 1.0)
    record.grievance = _clamp(
        record.grievance + delta.get("grievance", 0.0) * magnitude, 0.0, 1.0)
    record.obligation = _clamp(
        record.obligation + delta.get("obligation", 0.0) * magnitude, 0.0, 1.0)
    record.familiarity = _clamp(
        record.familiarity + delta.get("familiarity", 0.0) * magnitude, 0.0, 1.0)
    record.interaction_count += 1
    record.last_interaction_tick = tick


def relationship_preference_score(record: Relationship) -> float:
    """Return the bounded partner-choice score for one directed tie."""
    return _quantize(
        0.65 * record.trust
        + 0.25 * record.familiarity
        + 0.10 * record.affinity
        - 0.50 * record.grievance
        # Zero unless language coevolution is effective, so this term leaves
        # every pre-coevolution score bit-identical.
        + INTELLIGIBILITY_PREFERENCE_WEIGHT * record.intelligibility
    )


def relationship_salience(
    record: Relationship,
    *,
    current_tick: int,
    decay_interval: int,
) -> float:
    """Return deterministic retention salience for pruning and inspection."""
    age = max(0, current_tick - record.last_interaction_tick)
    recency = max(0.0, 1.0 - age / (4.0 * decay_interval))
    return _quantize(
        2.0 * abs(record.trust)
        + abs(record.affinity)
        + 2.0 * record.grievance
        + 1.5 * record.obligation
        + 0.5 * record.familiarity
        + 0.5 * recency
    )


def prune_relationships(
    inhabitant: SocialInhabitant,
    *,
    current_tick: int,
    maximum_ties: int,
    decay_interval: int,
) -> None:
    """Prune lowest-salience ties with stable ordering until within the cap."""
    while len(inhabitant.relationships) > maximum_ties:
        target_id = min(
            inhabitant.relationships,
            key=lambda candidate: (
                relationship_salience(
                    inhabitant.relationships[candidate],
                    current_tick=current_tick,
                    decay_interval=decay_interval,
                ),
                inhabitant.relationships[candidate].last_interaction_tick,
                candidate,
            ),
        )
        del inhabitant.relationships[target_id]


def record_interaction(
    actor: SocialInhabitant,
    target: SocialInhabitant,
    kind: InteractionKind,
    *,
    tick: int,
    magnitude: float = 1.0,
    active_ids: set[int] | frozenset[int],
    config: SocialConfig,
) -> bool:
    """Record one committed interaction using the documented actor roles.

    ``AID`` uses helper/giver as actor and recipient as target. ``TRADE`` uses
    donor/seller as actor and taker/buyer as target.
    """
    actor_id = _assigned_id(actor, "actor")
    target_id = _assigned_id(target, "target")
    if actor_id == target_id:
        raise ValueError("self-interactions are not permitted")
    if type(kind) is not InteractionKind:
        raise TypeError("interaction kind must be an InteractionKind")
    validated_tick = _validate_tick(tick)
    validated_magnitude = _validate_magnitude(magnitude)

    if actor_id not in active_ids or target_id not in active_ids:
        return False
    if not config.social_memory_enabled:
        return False

    _validate_record_tick(actor, target_id, validated_tick)
    _validate_record_tick(target, actor_id, validated_tick)

    if kind is InteractionKind.AID:
        _apply_delta(
            target,
            actor_id,
            _AID_RECIPIENT_DELTA,
            tick=validated_tick,
            magnitude=validated_magnitude,
        )
        _apply_delta(
            actor,
            target_id,
            _AID_HELPER_DELTA,
            tick=validated_tick,
            magnitude=validated_magnitude,
        )
    else:
        _apply_delta(
            actor,
            target_id,
            _TRADE_DELTA,
            tick=validated_tick,
            magnitude=validated_magnitude,
        )
        _apply_delta(
            target,
            actor_id,
            _TRADE_DELTA,
            tick=validated_tick,
            magnitude=validated_magnitude,
        )

    for owner in (actor, target):
        prune_relationships(
            owner,
            current_tick=validated_tick,
            maximum_ties=config.maximum_social_ties,
            decay_interval=config.relationship_decay_interval,
        )
    return True


def _toward_zero(value: float, amount: float) -> float:
    if value > 0.0:
        return _quantize(max(0.0, value - amount))
    if value < 0.0:
        return _quantize(min(0.0, value + amount))
    return 0.0


def _decay_record(record: Relationship) -> None:
    record.trust = _toward_zero(record.trust, 0.01)
    record.affinity = _toward_zero(record.affinity, 0.01)
    record.grievance = _clamp(record.grievance - 0.02, 0.0, 1.0)
    record.obligation = _clamp(record.obligation - 0.02, 0.0, 1.0)
    record.familiarity = _clamp(record.familiarity - 0.005, 0.0, 1.0)


def maintain_relationships(
    people: list[SocialInhabitant],
    newly_dead: list[SocialInhabitant],
    *,
    tick: int,
    config: SocialConfig,
) -> None:
    """Remove invalid ties, decay inactive records, and enforce the cap."""
    validated_tick = _validate_tick(tick)
    if not config.social_memory_enabled:
        return

    active_ids: set[int] = set()
    for inhabitant in people:
        inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
        if type(inhabitant_id) is not int or inhabitant_id < 0:
            continue
        if inhabitant_id in active_ids:
            raise ValueError(f"duplicate active inhabitant ID: {inhabitant_id}")
        active_ids.add(inhabitant_id)

    for inhabitant in newly_dead:
        inhabitant.relationships.clear()

    decay_due = validated_tick % config.relationship_decay_interval == 0
    for inhabitant in people:
        owner_id = getattr(inhabitant, "inhabitant_id", None)
        if type(owner_id) is not int or owner_id < 0:
            inhabitant.relationships.clear()
            continue

        invalid = [
            target_id
            for target_id in inhabitant.relationships
            if (
                type(target_id) is not int
                or target_id < 0
                or target_id == owner_id
                or target_id not in active_ids
            )
        ]
        for target_id in invalid:
            del inhabitant.relationships[target_id]

        if decay_due:
            for record in inhabitant.relationships.values():
                if validated_tick - record.last_interaction_tick >= config.relationship_decay_interval:
                    _decay_record(record)

        prune_relationships(
            inhabitant,
            current_tick=validated_tick,
            maximum_ties=config.maximum_social_ties,
            decay_interval=config.relationship_decay_interval,
        )


def apply_intelligibility_feedback(
    sender: SocialInhabitant,
    receiver: SocialInhabitant,
    *,
    understood: bool,
    tick: int,
    reward: float,
    penalty: float,
    active_ids: set[int] | frozenset[int],
) -> bool:
    """Fold one communication outcome into both directed ties.

    Both parties already update their own language state from this outcome:
    the sender reinforces or weakens the production form it used, and the
    receiver updates comprehension. Reading the same outcome here therefore
    invents no information channel that the simulation did not already model.

    The update is symmetric because intelligibility is a property of the pair
    and neither side is modeled as having better evidence than the other.
    Returns whether the ties were updated.
    """
    sender_id = _assigned_id(sender, "sender")
    receiver_id = _assigned_id(receiver, "receiver")
    if sender_id == receiver_id:
        raise ValueError("self-communication is not permitted")
    if type(understood) is not bool:
        raise TypeError("understood must be an exact boolean")
    validated_tick = _validate_tick(tick)
    for name, value in (("reward", reward), ("penalty", penalty)):
        if type(value) is not float or not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be a float in (0.0, 1.0]")
    if sender_id not in active_ids or receiver_id not in active_ids:
        return False

    delta = reward if understood else -penalty
    for owner, target_id in (
        (sender, receiver_id),
        (receiver, sender_id),
    ):
        record = owner.relationships.get(target_id)
        if record is None:
            record = Relationship(last_interaction_tick=validated_tick)
            owner.relationships[target_id] = record
        record.intelligibility = _clamp(
            record.intelligibility + delta, -1.0, 1.0)
    return True


def relationship_records(
    inhabitant: SocialInhabitant,
    *,
    include_intelligibility: bool = False,
) -> list[dict[str, int | float]]:
    """Return one inhabitant's relationships in canonical target-ID order."""
    records = []
    for target_id, record in sorted(inhabitant.relationships.items()):
        entry: dict[str, int | float] = {
            "target_id": target_id,
            "trust": record.trust,
            "affinity": record.affinity,
            "grievance": record.grievance,
            "obligation": record.obligation,
            "familiarity": record.familiarity,
            "interaction_count": record.interaction_count,
            "last_interaction_tick": record.last_interaction_tick,
        }
        if include_intelligibility:
            # Emitted only when coevolution is effective, so every pinned
            # pre-coevolution payload is unchanged.
            entry["intelligibility"] = record.intelligibility
        records.append(entry)
    return records


def canonical_relationship_snapshot(
    people: list[SocialInhabitant],
) -> list[dict[str, object]]:
    """Return canonical social state without retaining interaction history."""
    ordered = sorted(people, key=lambda inhabitant: _assigned_id(inhabitant, "inhabitant"))
    return [
        {
            "inhabitant_id": _assigned_id(inhabitant, "inhabitant"),
            "relationships": relationship_records(inhabitant),
        }
        for inhabitant in ordered
    ]


def relationship_summary(people: list[SocialInhabitant]) -> RelationshipSummary:
    """Summarize active directed ties deterministically."""
    records = [
        record
        for inhabitant in people
        for record in inhabitant.relationships.values()
    ]
    if not records:
        return RelationshipSummary(0, 0, 0, 0.0, 0.0)
    return RelationshipSummary(
        active_directed_ties=len(records),
        positive_trust_ties=sum(record.trust > 0.0 for record in records),
        negative_trust_ties=sum(record.trust < 0.0 for record in records),
        mean_trust=_quantize(sum(record.trust for record in records) / len(records)),
        mean_grievance=_quantize(
            sum(record.grievance for record in records) / len(records)
        ),
    )


def strongest_relationship_targets(
    inhabitant: SocialInhabitant,
    *,
    current_tick: int,
    decay_interval: int,
    limit: int = 3,
) -> tuple[int, ...]:
    """Return strongest target IDs using salience and stable final ordering."""
    if type(limit) is not int or limit < 0:
        raise ValueError("relationship target limit must be nonnegative")
    ordered = sorted(
        inhabitant.relationships.items(),
        key=lambda item: (
            -relationship_salience(
                item[1],
                current_tick=current_tick,
                decay_interval=decay_interval,
            ),
            item[0],
        ),
    )
    return tuple(target_id for target_id, _record in ordered[:limit])
