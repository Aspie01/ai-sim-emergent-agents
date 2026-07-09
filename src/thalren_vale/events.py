"""Structured simulation events with legacy text-log compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SimulationEvent:
    tick: int
    event_type: str
    actor: str = ""
    target: str = ""
    detail: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class StructuredEventLog(list):
    """Text log that also retains typed events emitted by simulation layers."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[SimulationEvent] = []

    def emit(self, event: SimulationEvent) -> None:
        self.events.append(event)
        super().append(event.message or event.detail)

    def record(self, event: SimulationEvent) -> None:
        """Record a typed event whose legacy text was already appended."""
        self.events.append(event)

    def clear(self) -> None:
        super().clear()
        self.events.clear()


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
            event_log.emit(event)
        else:
            event_log.record(event)
    elif append_text:
        event_log.append(message)
    return event
