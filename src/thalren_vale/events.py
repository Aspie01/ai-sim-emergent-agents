"""Structured simulation events with legacy text-log compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVENT_SCHEMA_VERSION = 1
EVENT_TYPES_BY_SCHEMA = {
    1: frozenset({
        "war_declared", "war_ended", "faction_formed",
        "faction_dissolved", "schism", "merger", "treaty_signed",
        "treaty_broken", "tech_researched", "settlement_founded", "birth",
        "death", "era_shift", "stagnation_trigger", "raid", "world_event",
    }),
}


@dataclass(frozen=True)
class SimulationEvent:
    tick: int
    event_type: str
    actor: str = ""
    target: str = ""
    detail: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class JournalToken:
    """Opaque identity handle created only by ``StructuredEventLog``."""

    __slots__ = (
        "__owner_identity",
        "__generation_identity",
        "__record_identity",
        "__tick",
        "__sequence",
    )

    def __new__(cls, *args, **kwargs):
        raise TypeError("JournalToken values are created only by StructuredEventLog")

    @property
    def tick(self) -> int:
        return self.__tick

    @property
    def sequence(self) -> int:
        return self.__sequence

    def __repr__(self) -> str:
        return "<JournalToken>"

    def __reduce__(self):
        raise TypeError("JournalToken values cannot be serialized")

    def __reduce_ex__(self, protocol):
        raise TypeError("JournalToken values cannot be serialized")


class JournalClaimError(ValueError):
    """Raised when a typed event cannot claim the requested journal record."""


class StructuredEventLog(list):
    """Text log that also retains typed events emitted by simulation layers."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[SimulationEvent] = []
        self._observation_journal: list[dict[str, Any]] = []
        self.__journal_owner = object()
        self.__journal_generation = object()
        self._journal_by_token: dict[
            JournalToken, tuple[object, dict[str, Any]]
        ] = {}
        self._next_sequence = 0
        self._active_tick: int | None = None

    def begin_observation_tick(self, tick: int) -> None:
        """Open one tick without discarding any unobserved prior records."""
        if type(tick) is not int or tick < 1:
            raise JournalClaimError("observation tick must be a positive integer")
        if self._observation_journal:
            raise JournalClaimError(
                "cannot begin a new observation tick with undrained records")
        self._active_tick = tick

    def _journal(
        self,
        *,
        message: str = "",
        event: SimulationEvent | None = None,
        tick: int | None = None,
    ) -> JournalToken:
        journal_tick = self._active_tick if tick is None else tick
        if type(journal_tick) is not int or journal_tick < 1:
            raise JournalClaimError("no valid observation tick is active")
        if self._active_tick is not None and journal_tick != self._active_tick:
            raise JournalClaimError(
                f"event tick {journal_tick} does not match active tick "
                f"{self._active_tick}")
        record_identity = object()
        token = object.__new__(JournalToken)
        object.__setattr__(
            token, "_JournalToken__owner_identity", self.__journal_owner)
        object.__setattr__(
            token,
            "_JournalToken__generation_identity",
            self.__journal_generation,
        )
        object.__setattr__(
            token, "_JournalToken__record_identity", record_identity)
        object.__setattr__(token, "_JournalToken__tick", journal_tick)
        object.__setattr__(
            token, "_JournalToken__sequence", self._next_sequence)
        entry = {
            "sequence": self._next_sequence,
            "tick": journal_tick,
            "message": message,
            "event": event,
        }
        self._observation_journal.append(entry)
        self._journal_by_token[token] = (record_identity, entry)
        self._next_sequence += 1
        return token

    def append(self, message: str) -> JournalToken:
        """Append one legacy message and journal it exactly once."""
        if type(message) is not str:
            raise TypeError("event-log messages must be strings")
        token = self._journal(message=message)
        super().append(message)
        return token

    def emit(self, event: SimulationEvent) -> None:
        message = event.message or event.detail
        self._journal(message=message, event=event, tick=event.tick)
        self.events.append(event)
        super().append(message)

    def record_typed(self, event: SimulationEvent) -> None:
        """Record a typed-only event without creating narrative text."""
        self._journal(event=event, tick=event.tick)
        self.events.append(event)

    def promote(self, token: JournalToken, event: SimulationEvent) -> None:
        """Claim exactly one existing narrative record for a typed event."""
        if type(token) is not JournalToken:
            raise JournalClaimError("promotion requires an exact JournalToken")
        try:
            token_owner = token._JournalToken__owner_identity
            token_generation = token._JournalToken__generation_identity
            token_record = token._JournalToken__record_identity
            token_tick = token.tick
            token_sequence = token.sequence
        except AttributeError as exc:
            raise JournalClaimError("unknown opaque journal token") from exc
        if type(token_tick) is not int or type(token_sequence) is not int:
            raise JournalClaimError(
                "journal token fields must be exact nonnegative integers")
        if token_tick < 1 or token_sequence < 0:
            raise JournalClaimError(
                "journal token fields must be exact nonnegative integers")
        if type(event.tick) is not int or event.tick < 1:
            raise JournalClaimError("typed event tick must be a positive integer")
        if token_tick != event.tick:
            raise JournalClaimError(
                f"journal token tick {token_tick} does not match event tick "
                f"{event.tick}")
        if self._active_tick is not None and token_tick != self._active_tick:
            raise JournalClaimError(
                f"journal token tick {token_tick} does not match active tick "
                f"{self._active_tick}")
        if (
            token_owner is not self.__journal_owner
            or token_generation is not self.__journal_generation
        ):
            raise JournalClaimError(
                "journal token belongs to a different log or reset generation")
        registered = self._journal_by_token.get(token)
        if registered is None:
            raise JournalClaimError(f"unknown journal sequence {token_sequence}")
        record_identity, entry = registered
        if record_identity is not token_record or entry["tick"] != token_tick:
            raise JournalClaimError(f"unknown journal sequence {token_sequence}")
        if entry["event"] is not None:
            raise JournalClaimError(
                f"journal sequence {token_sequence} is already claimed")
        message = event.message or event.detail
        if entry["message"] != message:
            raise JournalClaimError(
                f"journal sequence {token_sequence} belongs to different text")
        entry["event"] = event
        self.events.append(event)

    def record(
        self,
        event: SimulationEvent,
        token: JournalToken | None = None,
    ) -> None:
        """Promote an explicit record, or record a typed-only event."""
        if token is None:
            self.record_typed(event)
        else:
            self.promote(token, event)

    def discard_observation_journal(self) -> None:
        """Close an empty observation window; never discard pending records."""
        if self._observation_journal:
            raise JournalClaimError("cannot discard undrained observation records")
        self._active_tick = None

    def observation_messages(self) -> list[str]:
        """Return journaled narrative messages without advancing the cursor."""
        return [
            entry["message"]
            for entry in self._observation_journal
            if entry["message"]
        ]

    def drain_observation_journal(self) -> list[dict[str, Any]]:
        """Return pending records in generation order and clear the journal."""
        pending = self._observation_journal
        self._observation_journal = []
        self._journal_by_token = {}
        self._active_tick = None
        return pending

    def clear(self) -> None:
        super().clear()
        self.events.clear()
        self._observation_journal.clear()
        self._journal_by_token.clear()
        self.__journal_generation = object()
        self._next_sequence = 0
        self._active_tick = None


def emit_event(
    event_log: list,
    *,
    tick: int,
    event_type: str,
    actor: str = "",
    target: str = "",
    detail: str = "",
    message: str,
    metadata: dict[str, Any] | None = None,
    append_text: bool = True,
    journal_token: JournalToken | None = None,
) -> SimulationEvent:
    """Emit a typed event, falling back to text for legacy list consumers."""
    event = SimulationEvent(
        tick=tick,
        event_type=event_type,
        actor=actor,
        target=target,
        detail=detail,
        message=message,
        metadata=metadata or {},
    )
    if isinstance(event_log, StructuredEventLog):
        if append_text:
            if journal_token is not None:
                raise JournalClaimError(
                    "typed emit cannot also claim a journal token")
            event_log.emit(event)
        else:
            event_log.record(event, journal_token)
    elif append_text:
        event_log.append(message)
    return event
