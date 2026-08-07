"""Append-only execution-attempt history for experiment cells.

`CORE_REPLICATION_V2_PLAN.md` requires an append-only attempt ledger with an
explicit selected/final attempt state, preservation of every outcome, and
supersession without deletion. Those pull in opposite directions if records are
mutable: marking a previously selected attempt superseded would rewrite history
the ledger exists to preserve.

The ledger is therefore **event-sourced**. Events are appended and never
edited; the status of an attempt, and which attempt is currently selected, are
*derived* by folding the event stream. Supersession appends a new event rather
than altering the record it supersedes, so the file remains literally
append-only and every prior outcome stays readable exactly as written.

The module deliberately does not execute anything, allocate seeds, or know what
a simulation is. It records what happened and refuses to record histories that
could not have happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

LEDGER_SCHEMA_VERSION = 1

# Event kinds. Appended in this vocabulary only.
EVENT_STARTED = "attempt_started"
EVENT_FINISHED = "attempt_finished"
EVENT_SELECTED = "attempt_selected"
EVENT_SUPERSEDED = "attempt_superseded"

_EVENT_KINDS = frozenset({
    EVENT_STARTED, EVENT_FINISHED, EVENT_SELECTED, EVENT_SUPERSEDED})

# Derived attempt states.
STATUS_RUNNING = "running"
STATUS_FINISHED = "finished"
STATUS_SELECTED = "selected"
STATUS_SUPERSEDED = "superseded"


class LedgerError(ValueError):
    """The ledger was asked to record a history that cannot have happened."""


@dataclass(frozen=True)
class AttemptState:
    """Derived, never stored. Rebuilt from the event stream on every read."""

    attempt_id: int
    status: str
    result: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    directory: str | None = None
    state_hash: str | None = None
    superseded_by: int | None = None


def _require_positive_int(value: object, field_name: str) -> int:
    # Exact identity: `True` is an int in Python and would otherwise pass as
    # attempt 1, silently merging a boolean into the attempt sequence.
    if type(value) is not int or value < 1:
        raise LedgerError(f"{field_name} must be a positive integer")
    return value


def _require_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise LedgerError(f"{field_name} must be a nonempty string")
    return value


@dataclass
class AttemptLedger:
    """Append-only attempt history for a single cell.

    Construct empty, or `load()` from a JSONL file. Every mutating method
    appends exactly one event and validates it against the derived state
    first, so an invalid history is rejected before it can be written.
    """

    cell_id: str
    events: list[dict] = field(default_factory=list)

    # ── Derivation ──────────────────────────────────────────────────────────

    def derive(self) -> dict[int, AttemptState]:
        """Fold the event stream into current per-attempt state."""
        states: dict[int, AttemptState] = {}
        for event in self.events:
            kind = event["event"]
            attempt_id = event["attempt_id"]
            current = states.get(attempt_id)
            if kind == EVENT_STARTED:
                states[attempt_id] = AttemptState(
                    attempt_id=attempt_id,
                    status=STATUS_RUNNING,
                    started_at=event.get("at"),
                    directory=event.get("directory"),
                )
            elif kind == EVENT_FINISHED:
                states[attempt_id] = AttemptState(
                    **{**current.__dict__,
                       "status": STATUS_FINISHED,
                       "result": event.get("result"),
                       "finished_at": event.get("at"),
                       "state_hash": event.get("state_hash")})
            elif kind == EVENT_SELECTED:
                states[attempt_id] = AttemptState(
                    **{**current.__dict__, "status": STATUS_SELECTED})
            elif kind == EVENT_SUPERSEDED:
                states[attempt_id] = AttemptState(
                    **{**current.__dict__,
                       "status": STATUS_SUPERSEDED,
                       "superseded_by": event.get("superseded_by")})
        return states

    def selected_attempt(self) -> int | None:
        """The one attempt currently selected, if any."""
        selected = [
            state.attempt_id for state in self.derive().values()
            if state.status == STATUS_SELECTED
        ]
        if len(selected) > 1:
            # Unreachable through the append methods; a corrupted or
            # hand-edited file can still produce it, so fail closed on read.
            raise LedgerError(
                f"ledger has {len(selected)} selected attempts; at most one "
                "attempt may be selected")
        return selected[0] if selected else None

    def next_attempt_id(self) -> int:
        return max(self.derive(), default=0) + 1

    # ── Appending ───────────────────────────────────────────────────────────

    def _append(self, event: dict) -> dict:
        self.events.append(event)
        return event

    def start_attempt(self, attempt_id: int, *, directory: str,
                      at: str) -> dict:
        _require_positive_int(attempt_id, "attempt_id")
        _require_text(directory, "directory")
        _require_text(at, "at")
        states = self.derive()
        if attempt_id in states:
            raise LedgerError(
                f"attempt {attempt_id} already exists; attempt directories are "
                "immutable and ids are never reused")
        expected = self.next_attempt_id()
        if attempt_id != expected:
            raise LedgerError(
                f"attempts must be numbered consecutively; expected "
                f"{expected}, got {attempt_id}")
        running = [s.attempt_id for s in states.values()
                   if s.status == STATUS_RUNNING]
        if running:
            raise LedgerError(
                f"attempt {running[0]} is still running; finish it before "
                "starting another")
        return self._append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event": EVENT_STARTED, "cell_id": self.cell_id,
            "attempt_id": attempt_id, "directory": directory, "at": at,
        })

    def finish_attempt(self, attempt_id: int, *, result: str, at: str,
                       state_hash: str | None = None) -> dict:
        _require_text(result, "result")
        _require_text(at, "at")
        state = self.derive().get(attempt_id)
        if state is None:
            raise LedgerError(f"attempt {attempt_id} was never started")
        if state.status != STATUS_RUNNING:
            raise LedgerError(
                f"attempt {attempt_id} is {state.status}, not running; an "
                "outcome is recorded exactly once")
        return self._append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event": EVENT_FINISHED, "cell_id": self.cell_id,
            "attempt_id": attempt_id, "result": result, "at": at,
            "state_hash": state_hash,
        })

    def select_attempt(self, attempt_id: int, *, at: str) -> list[dict]:
        """Select an attempt, superseding the previously selected one.

        Supersession appends an event; it never edits the superseded record.
        The prior attempt's outcome, directory, and state hash stay exactly as
        written, which is what keeps a superseded attempt auditable without it
        becoming an extra replicate.
        """
        _require_text(at, "at")
        state = self.derive().get(attempt_id)
        if state is None:
            raise LedgerError(f"attempt {attempt_id} was never started")
        if state.status == STATUS_RUNNING:
            raise LedgerError(
                f"attempt {attempt_id} has not finished; a running attempt "
                "cannot be selected")
        if state.status == STATUS_SELECTED:
            raise LedgerError(f"attempt {attempt_id} is already selected")
        if state.status == STATUS_SUPERSEDED:
            raise LedgerError(
                f"attempt {attempt_id} was superseded; a superseded attempt "
                "cannot be reselected")

        appended: list[dict] = []
        previous = self.selected_attempt()
        if previous is not None:
            appended.append(self._append({
                "schema_version": LEDGER_SCHEMA_VERSION,
                "event": EVENT_SUPERSEDED, "cell_id": self.cell_id,
                "attempt_id": previous, "superseded_by": attempt_id, "at": at,
            }))
        appended.append(self._append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event": EVENT_SELECTED, "cell_id": self.cell_id,
            "attempt_id": attempt_id, "at": at,
        }))
        return appended

    # ── Persistence ─────────────────────────────────────────────────────────

    def write(self, path: Path) -> None:
        """Rewrite the whole file. Only valid for a ledger built in memory."""
        path.write_text(
            "".join(json.dumps(e, sort_keys=True) + "\n" for e in self.events),
            encoding="utf-8")

    def append_to(self, path: Path, events: list[dict]) -> None:
        """Append events to an existing file without reading or rewriting it.

        Opened in append mode so a partial write cannot truncate history, and
        so a concurrent reader never observes a rewritten prefix.
        """
        with path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path, *, cell_id: str | None = None) -> AttemptLedger:
        """Read a ledger, failing closed on anything it could not have written."""
        events: list[dict] = []
        seen_cells: set[str] = set()
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise LedgerError(
                    f"{path}:{number}: ledger line is not valid JSON") from error
            if type(event) is not dict:
                raise LedgerError(f"{path}:{number}: ledger line is not an object")
            if event.get("schema_version") != LEDGER_SCHEMA_VERSION:
                raise LedgerError(
                    f"{path}:{number}: ledger schema_version must be "
                    f"{LEDGER_SCHEMA_VERSION}")
            if event.get("event") not in _EVENT_KINDS:
                raise LedgerError(
                    f"{path}:{number}: unknown ledger event "
                    f"{event.get('event')!r}")
            _require_positive_int(event.get("attempt_id"), "attempt_id")
            seen_cells.add(_require_text(event.get("cell_id"), "cell_id"))
            events.append(event)

        if len(seen_cells) > 1:
            raise LedgerError(
                f"{path}: ledger mixes cells {sorted(seen_cells)}; one ledger "
                "records one cell")
        resolved = cell_id or (next(iter(seen_cells)) if seen_cells else "")
        if cell_id is not None and seen_cells and cell_id not in seen_cells:
            raise LedgerError(
                f"{path}: ledger records cell {next(iter(seen_cells))!r}, not "
                f"{cell_id!r}")

        ledger = cls(cell_id=resolved, events=events)
        ledger._validate_history(path)
        return ledger

    def _validate_history(self, path: Path) -> None:
        """Replay the stream and reject an order that cannot have occurred."""
        replay = AttemptLedger(cell_id=self.cell_id)
        for number, event in enumerate(self.events, start=1):
            kind = event["event"]
            try:
                if kind == EVENT_STARTED:
                    replay.start_attempt(
                        event["attempt_id"],
                        directory=event.get("directory", ""),
                        at=event.get("at", ""))
                elif kind == EVENT_FINISHED:
                    replay.finish_attempt(
                        event["attempt_id"],
                        result=event.get("result", ""),
                        at=event.get("at", ""),
                        state_hash=event.get("state_hash"))
                elif kind == EVENT_SELECTED:
                    # Replayed directly: the recorded stream already contains
                    # its own supersession events, so re-deriving them here
                    # would duplicate them.
                    replay._append(event)
                elif kind == EVENT_SUPERSEDED:
                    replay._append(event)
            except LedgerError as error:
                raise LedgerError(f"{path}:{number}: {error}") from error
        replay.selected_attempt()


def allocate_attempt_directory(cell_directory: Path, attempt_id: int) -> Path:
    """Create attempt_NNNN under a cell, refusing to reuse an existing one.

    Immutability is enforced by refusing to hand back a directory that already
    exists, rather than by permissions: a retry that reused a directory could
    overwrite the prior attempt's manifest, summary, and stderr, which is
    exactly what the attempt history exists to prevent.
    """
    _require_positive_int(attempt_id, "attempt_id")
    path = cell_directory / f"attempt_{attempt_id:04d}"
    if path.exists():
        raise LedgerError(
            f"attempt directory already exists and is immutable: {path}")
    path.mkdir(parents=True)
    return path
