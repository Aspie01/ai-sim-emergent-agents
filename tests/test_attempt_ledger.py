"""Append-only attempt history, supersession, and immutable attempt directories."""

from __future__ import annotations

import json

import pytest

from thalren_vale.attempt_ledger import (
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    LEDGER_SCHEMA_VERSION,
    STATUS_FINISHED,
    STATUS_RUNNING,
    STATUS_SELECTED,
    STATUS_SUPERSEDED,
    AttemptLedger,
    LedgerError,
    allocate_attempt_directory,
)


def ledger(cell_id="baseline/seed_1"):
    return AttemptLedger(cell_id=cell_id)


def run_attempt(book, attempt_id, result="completed", state_hash=None):
    book.start_attempt(attempt_id, directory=f"attempt_{attempt_id:04d}",
                       at=f"t{attempt_id}-start")
    book.finish_attempt(attempt_id, result=result, at=f"t{attempt_id}-end",
                        state_hash=state_hash)


# ── Append-only ─────────────────────────────────────────────────────────────

def test_events_are_only_ever_appended():
    book = ledger()
    run_attempt(book, 1, result="exception")
    snapshot = [dict(e) for e in book.events]

    run_attempt(book, 2)
    book.select_attempt(2, at="t")
    run_attempt(book, 3)
    book.select_attempt(3, at="t")

    assert book.events[:len(snapshot)] == snapshot, (
        "existing events must never be rewritten")


def test_supersession_appends_rather_than_editing_the_superseded_record():
    book = ledger()
    run_attempt(book, 1, state_hash="first")
    book.select_attempt(1, at="t")
    finished_event = dict(
        [e for e in book.events if e["event"] == "attempt_finished"][0])

    run_attempt(book, 2, state_hash="second")
    book.select_attempt(2, at="t")

    still_there = [e for e in book.events if e["event"] == "attempt_finished"][0]
    assert still_there == finished_event
    assert any(e["event"] == EVENT_SUPERSEDED for e in book.events)


def test_a_superseded_attempt_keeps_its_outcome():
    """Supersession must not erase evidence; it only changes which is selected."""
    book = ledger()
    run_attempt(book, 1, result="completed", state_hash="abc")
    book.select_attempt(1, at="t")
    run_attempt(book, 2, result="completed", state_hash="def")
    book.select_attempt(2, at="t")

    superseded = book.derive()[1]
    assert superseded.status == STATUS_SUPERSEDED
    assert superseded.result == "completed"
    assert superseded.state_hash == "abc"
    assert superseded.superseded_by == 2
    assert superseded.directory == "attempt_0001"


def test_failed_attempts_are_preserved_and_never_selected():
    book = ledger()
    run_attempt(book, 1, result="exception")
    run_attempt(book, 2, result="wall_clock_limit")
    run_attempt(book, 3, result="completed")
    book.select_attempt(3, at="t")

    states = book.derive()
    assert states[1].result == "exception"
    assert states[2].result == "wall_clock_limit"
    assert states[1].status == STATUS_FINISHED
    assert book.selected_attempt() == 3


# ── Selection invariants ────────────────────────────────────────────────────

def test_at_most_one_attempt_is_selected():
    book = ledger()
    for attempt_id in (1, 2, 3):
        run_attempt(book, attempt_id)
        book.select_attempt(attempt_id, at="t")
    selected = [s for s in book.derive().values()
                if s.status == STATUS_SELECTED]
    assert len(selected) == 1
    assert book.selected_attempt() == 3


def test_a_running_attempt_cannot_be_selected():
    book = ledger()
    book.start_attempt(1, directory="attempt_0001", at="t")
    with pytest.raises(LedgerError, match="has not finished"):
        book.select_attempt(1, at="t")


def test_a_superseded_attempt_cannot_be_reselected():
    book = ledger()
    run_attempt(book, 1)
    book.select_attempt(1, at="t")
    run_attempt(book, 2)
    book.select_attempt(2, at="t")
    with pytest.raises(LedgerError, match="superseded"):
        book.select_attempt(1, at="t")


def test_reselecting_the_current_attempt_is_refused():
    book = ledger()
    run_attempt(book, 1)
    book.select_attempt(1, at="t")
    with pytest.raises(LedgerError, match="already selected"):
        book.select_attempt(1, at="t")


def test_selecting_an_unknown_attempt_is_refused():
    with pytest.raises(LedgerError, match="never started"):
        ledger().select_attempt(1, at="t")


# ── Attempt sequencing ──────────────────────────────────────────────────────

def test_attempt_ids_must_be_consecutive():
    book = ledger()
    run_attempt(book, 1)
    with pytest.raises(LedgerError, match="consecutively"):
        book.start_attempt(3, directory="d", at="t")


def test_an_attempt_id_is_never_reused():
    book = ledger()
    run_attempt(book, 1)
    with pytest.raises(LedgerError, match="already exists"):
        book.start_attempt(1, directory="d", at="t")


def test_two_attempts_cannot_run_at_once():
    book = ledger()
    book.start_attempt(1, directory="attempt_0001", at="t")
    with pytest.raises(LedgerError, match="still running"):
        book.start_attempt(2, directory="attempt_0002", at="t")


def test_finishing_requires_starting():
    with pytest.raises(LedgerError, match="never started"):
        ledger().finish_attempt(1, result="completed", at="t")


def test_an_outcome_is_recorded_exactly_once():
    book = ledger()
    run_attempt(book, 1)
    with pytest.raises(LedgerError, match="exactly once"):
        book.finish_attempt(1, result="completed", at="t")


@pytest.mark.parametrize("attempt_id", [0, -1, True, 1.0, "1", None])
def test_attempt_ids_must_be_positive_integers(attempt_id):
    # True is an int in Python and would otherwise pass as attempt 1.
    with pytest.raises(LedgerError):
        ledger().start_attempt(attempt_id, directory="d", at="t")


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_directory_and_timestamp_must_be_present(bad):
    with pytest.raises(LedgerError):
        ledger().start_attempt(1, directory=bad, at="t")
    with pytest.raises(LedgerError):
        ledger().start_attempt(1, directory="d", at=bad)


def test_next_attempt_id_follows_the_history():
    book = ledger()
    assert book.next_attempt_id() == 1
    run_attempt(book, 1)
    assert book.next_attempt_id() == 2


# ── Persistence, fail-closed on read ────────────────────────────────────────

def test_round_trip_preserves_history(tmp_path):
    book = ledger()
    run_attempt(book, 1, result="exception")
    run_attempt(book, 2, state_hash="abc")
    book.select_attempt(2, at="t")
    path = tmp_path / "ledger.jsonl"
    book.write(path)

    reloaded = AttemptLedger.load(path)
    assert reloaded.cell_id == book.cell_id
    assert reloaded.events == book.events
    assert reloaded.selected_attempt() == 2
    assert reloaded.derive()[1].result == "exception"


def test_appending_does_not_rewrite_the_file(tmp_path):
    path = tmp_path / "ledger.jsonl"
    book = ledger()
    run_attempt(book, 1)
    book.write(path)
    first_bytes = path.read_bytes()

    events = book.select_attempt(1, at="t")
    book.append_to(path, events)

    assert path.read_bytes().startswith(first_bytes), (
        "appending must leave the existing prefix byte-identical")
    assert AttemptLedger.load(path).selected_attempt() == 1


@pytest.mark.parametrize("line", [
    "{not json",
    '["not", "an", "object"]',
    json.dumps({"schema_version": 999, "event": "attempt_started",
                "attempt_id": 1, "cell_id": "c"}),
    json.dumps({"schema_version": LEDGER_SCHEMA_VERSION, "event": "nonsense",
                "attempt_id": 1, "cell_id": "c"}),
    json.dumps({"schema_version": LEDGER_SCHEMA_VERSION,
                "event": "attempt_started", "attempt_id": 0, "cell_id": "c"}),
    json.dumps({"schema_version": LEDGER_SCHEMA_VERSION,
                "event": "attempt_started", "attempt_id": 1, "cell_id": ""}),
])
def test_malformed_ledger_lines_fail_closed(tmp_path, line):
    path = tmp_path / "ledger.jsonl"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        AttemptLedger.load(path)


def test_a_ledger_records_exactly_one_cell(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text("\n".join(
        json.dumps({"schema_version": LEDGER_SCHEMA_VERSION,
                    "event": "attempt_started", "attempt_id": n,
                    "cell_id": cell, "directory": "d", "at": "t"})
        for n, cell in ((1, "alpha"), (2, "beta"))) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="mixes cells"):
        AttemptLedger.load(path)


def test_load_rejects_a_cell_id_that_does_not_match(tmp_path):
    book = ledger("alpha")
    run_attempt(book, 1)
    path = tmp_path / "ledger.jsonl"
    book.write(path)
    with pytest.raises(LedgerError, match="records cell"):
        AttemptLedger.load(path, cell_id="beta")


def test_load_rejects_an_impossible_ordering(tmp_path):
    """A finish before its start cannot have happened, so it cannot load."""
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps({
        "schema_version": LEDGER_SCHEMA_VERSION, "event": "attempt_finished",
        "attempt_id": 1, "cell_id": "c", "result": "completed", "at": "t",
    }) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="never started"):
        AttemptLedger.load(path)


def test_load_rejects_two_selected_attempts(tmp_path):
    """Hand-editing a file can produce what the append methods cannot."""
    path = tmp_path / "ledger.jsonl"
    lines = []
    for attempt_id in (1, 2):
        lines.append({"schema_version": LEDGER_SCHEMA_VERSION,
                      "event": "attempt_started", "attempt_id": attempt_id,
                      "cell_id": "c", "directory": "d", "at": "t"})
        lines.append({"schema_version": LEDGER_SCHEMA_VERSION,
                      "event": "attempt_finished", "attempt_id": attempt_id,
                      "cell_id": "c", "result": "completed", "at": "t"})
        lines.append({"schema_version": LEDGER_SCHEMA_VERSION,
                      "event": EVENT_SELECTED, "attempt_id": attempt_id,
                      "cell_id": "c", "at": "t"})
    path.write_text("".join(json.dumps(l) + "\n" for l in lines),
                    encoding="utf-8")
    with pytest.raises(LedgerError, match="selected attempts"):
        AttemptLedger.load(path)


def test_blank_lines_are_tolerated(tmp_path):
    book = ledger()
    run_attempt(book, 1)
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        "\n".join(json.dumps(e) for e in book.events) + "\n\n\n",
        encoding="utf-8")
    assert len(AttemptLedger.load(path).events) == 2


def test_an_empty_ledger_loads_as_empty(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text("", encoding="utf-8")
    book = AttemptLedger.load(path)
    assert book.events == []
    assert book.selected_attempt() is None
    assert book.next_attempt_id() == 1


# ── Immutable attempt directories ───────────────────────────────────────────

def test_attempt_directories_are_zero_padded_and_created(tmp_path):
    path = allocate_attempt_directory(tmp_path, 7)
    assert path.name == "attempt_0007"
    assert path.is_dir()


def test_allocating_an_existing_attempt_directory_is_refused(tmp_path):
    allocate_attempt_directory(tmp_path, 1)
    with pytest.raises(LedgerError, match="immutable"):
        allocate_attempt_directory(tmp_path, 1)


def test_allocation_refuses_to_reuse_a_directory_holding_evidence(tmp_path):
    """A retry that reused a directory would overwrite the prior manifest."""
    first = allocate_attempt_directory(tmp_path, 1)
    (first / "run_manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(LedgerError):
        allocate_attempt_directory(tmp_path, 1)
    assert (first / "run_manifest.json").read_text(encoding="utf-8") == "{}"


@pytest.mark.parametrize("attempt_id", [0, -1, True, "1"])
def test_allocation_validates_the_attempt_id(tmp_path, attempt_id):
    with pytest.raises(LedgerError):
        allocate_attempt_directory(tmp_path, attempt_id)
