"""Structured event stream and metrics integration tests."""

import copy
import csv
import pickle
from types import SimpleNamespace

import pytest

from thalren_vale import diplomacy
from thalren_vale import sim
from thalren_vale.events import (
    JournalClaimError,
    JournalToken,
    SimulationEvent,
    StructuredEventLog,
    emit_event,
)
from thalren_vale.metrics import MetricsLogger


def test_typed_event_preserves_legacy_text_log():
    log = StructuredEventLog()

    event = emit_event(
        log,
        tick=12,
        event_type="war_declared",
        actor="North",
        target="South",
        detail="territory",
        message="Tick 012: WAR DECLARED — North vs South",
        metadata={"tension": 220},
    )

    assert log == ["Tick 012: WAR DECLARED — North vs South"]
    assert log.events == [event]
    assert event.metadata == {"tension": 220}


def test_clearing_text_log_also_clears_typed_events():
    log = StructuredEventLog()
    emit_event(log, tick=1, event_type="birth", message="birth")

    log.clear()

    assert log == []
    assert log.events == []


def test_observation_journal_pairs_legacy_text_with_its_typed_event_once():
    log = StructuredEventLog()
    message = "Tick 008: WORLD EVENT — paired observation"

    log.begin_observation_tick(8)
    token = log.append(message)
    event = emit_event(
        log,
        tick=8,
        event_type="world_event",
        detail="paired observation",
        message=message,
        append_text=False,
        journal_token=token,
    )

    entries = log.drain_observation_journal()

    assert entries == [{
        "sequence": 0,
        "tick": 8,
        "message": message,
        "event": event,
    }]
    assert log.drain_observation_journal() == []


def test_identical_messages_promote_by_explicit_sequence_in_generation_order():
    log = StructuredEventLog()
    message = "Tick 009: repeated observation"
    log.begin_observation_tick(9)
    first_token = log.append(message)
    second_token = log.append(message)

    first_event = emit_event(
        log,
        tick=9,
        event_type="world_event",
        actor="first",
        detail="first detail",
        message=message,
        append_text=False,
        journal_token=first_token,
    )
    second_event = emit_event(
        log,
        tick=9,
        event_type="world_event",
        actor="second",
        detail="second detail",
        message=message,
        append_text=False,
        journal_token=second_token,
    )

    assert log.drain_observation_journal() == [
        {
            "sequence": 0,
            "tick": 9,
            "message": message,
            "event": first_event,
        },
        {
            "sequence": 1,
            "tick": 9,
            "message": message,
            "event": second_event,
        },
    ]


def test_identical_messages_can_be_promoted_out_of_order_without_reassociation():
    log = StructuredEventLog()
    message = "Tick 010: identical actor-neutral text"
    log.begin_observation_tick(10)
    actor_a_token = log.append(message)
    actor_b_token = log.append(message)

    actor_b_event = emit_event(
        log,
        tick=10,
        event_type="death",
        actor="B",
        detail="B detail",
        message=message,
        append_text=False,
        journal_token=actor_b_token,
    )
    actor_a_event = emit_event(
        log,
        tick=10,
        event_type="death",
        actor="A",
        detail="A detail",
        message=message,
        append_text=False,
        journal_token=actor_a_token,
    )

    entries = log.drain_observation_journal()
    assert [entry["event"] for entry in entries] == [actor_a_event, actor_b_event]
    assert [entry["event"].actor for entry in entries] == ["A", "B"]


def test_journal_promotion_rejects_double_unknown_and_wrong_tick_claims():
    log = StructuredEventLog()
    log.begin_observation_tick(11)
    token = log.append("Tick 011: claim")
    event = emit_event(
        log,
        tick=11,
        event_type="world_event",
        detail="claim",
        message="Tick 011: claim",
        append_text=False,
        journal_token=token,
    )
    assert event.actor == ""

    with pytest.raises(JournalClaimError, match="already claimed"):
        log.promote(token, event)
    guessed = object.__new__(JournalToken)
    object.__setattr__(guessed, "_JournalToken__tick", 11)
    object.__setattr__(guessed, "_JournalToken__sequence", token.sequence)
    with pytest.raises(JournalClaimError, match="unknown opaque journal token"):
        log.promote(guessed, event)
    wrong_tick_event = SimulationEvent(
        tick=12,
        event_type="world_event",
        detail="claim",
        message="Tick 011: claim",
    )
    with pytest.raises(JournalClaimError, match="does not match event tick"):
        log.promote(token, wrong_tick_event)


def test_journal_token_constructor_repr_copy_and_serialization_are_opaque():
    with pytest.raises(TypeError, match="created only"):
        JournalToken(tick=1, sequence=0)

    log = StructuredEventLog()
    log.begin_observation_tick(1)
    token = log.append("opaque")

    assert repr(token) == "<JournalToken>"
    with pytest.raises(TypeError):
        copy.copy(token)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(token)


def test_stale_cross_log_and_colliding_tokens_cannot_claim_records():
    message = "Tick 013: identical ownership text"
    log = StructuredEventLog()
    log.begin_observation_tick(13)
    stale = log.append(message)
    log.clear()
    log.begin_observation_tick(13)
    current = log.append(message)
    event = SimulationEvent(
        tick=13,
        event_type="world_event",
        detail="ownership",
        message=message,
    )

    with pytest.raises(JournalClaimError, match="reset generation"):
        log.promote(stale, event)

    other = StructuredEventLog()
    other.begin_observation_tick(13)
    foreign = other.append(message)
    assert foreign.tick == current.tick
    assert foreign.sequence == current.sequence
    with pytest.raises(JournalClaimError, match="different log"):
        log.promote(foreign, event)

    guessed = object.__new__(JournalToken)
    object.__setattr__(guessed, "_JournalToken__tick", current.tick)
    object.__setattr__(guessed, "_JournalToken__sequence", current.sequence)
    with pytest.raises(JournalClaimError, match="unknown opaque journal token"):
        log.promote(guessed, event)

    log.promote(current, event)
    assert log.drain_observation_journal()[0]["event"] is event


def test_journal_promotion_rejects_wrong_text_for_valid_token():
    log = StructuredEventLog()
    log.begin_observation_tick(14)
    token = log.append("expected text")
    event = SimulationEvent(
        tick=14,
        event_type="world_event",
        detail="different text",
        message="different text",
    )

    with pytest.raises(JournalClaimError, match="different text"):
        log.promote(token, event)


def test_typed_typed_only_and_legacy_only_records_are_exact_once_and_ordered():
    log = StructuredEventLog()
    log.begin_observation_tick(12)

    emitted = emit_event(
        log,
        tick=12,
        event_type="birth",
        actor="emitted",
        detail="emitted detail",
        message="emitted narrative",
    )
    typed_only = emit_event(
        log,
        tick=12,
        event_type="death",
        actor="typed-only",
        detail="typed-only detail",
        message="typed-only narrative",
        append_text=False,
    )
    legacy_token = log.append("legacy only")

    assert legacy_token.tick == 12
    assert legacy_token.sequence == 2
    assert log.drain_observation_journal() == [
        {
            "sequence": 0,
            "tick": 12,
            "message": "emitted narrative",
            "event": emitted,
        },
        {
            "sequence": 1,
            "tick": 12,
            "message": "",
            "event": typed_only,
        },
        {
            "sequence": 2,
            "tick": 12,
            "message": "legacy only",
            "event": None,
        },
    ]
    assert log == ["emitted narrative", "legacy only"]
    assert log.events == [emitted, typed_only]
    assert log.drain_observation_journal() == []


def test_pruning_keeps_retained_narrative_history_bounded():
    log = sim.event_log
    saved_text = list(log)
    saved_events = list(log.events)
    try:
        log.clear()
        log.begin_observation_tick(50)
        for index in range(205):
            log.append(f"narrative filler {index:03d}")
        assert len(log._observation_journal) == 205

        sim._prune_event_log(50)

        drained = log.drain_observation_journal()
        assert len(drained) == 205
        assert [entry["sequence"] for entry in drained] == list(range(205))
        assert drained[0]["message"] == "narrative filler 000"
        assert drained[-1]["message"] == "narrative filler 204"
        assert log.drain_observation_journal() == []
        assert len(log) == 200
        assert log[0] == "narrative filler 005"
        assert log[-1] == "narrative filler 204"
    finally:
        log.clear()
        log.extend(saved_text)
        log.events.extend(saved_events)


def test_metrics_records_typed_event_fields(tmp_path):
    log = StructuredEventLog()
    event = emit_event(
        log,
        tick=7,
        event_type="treaty_signed",
        actor="A",
        target="B",
        detail="Trade Agreement",
        message="wording may change without affecting metrics",
    )
    logger = MetricsLogger(seed=1, condition="events", output_dir=str(tmp_path))

    logger.record_simulation_events([event])
    logger.close()

    path = tmp_path / "faction_events_events_seed_1.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{
        "event_schema_version": "1",
        "seed": "1",
        "tick": "7",
        "event_type": "treaty_signed",
        "actor": "A",
        "target": "B",
        "detail": "Trade Agreement",
    }]


def test_event_buffer_flushes_in_order_during_finalize(tmp_path):
    logger = MetricsLogger(
        seed=2,
        condition="buffered",
        output_dir=str(tmp_path),
        event_flush_interval=100,
    )
    logger.record_event(3, "raid", "A", "B", "2 ore, 1 wood")
    logger.record_event(4, "treaty_broken", "B", "A", 'said "enough"')

    assert logger._pending_event_rows == 2
    logger.finalize([], [], [])
    assert logger._pending_event_rows == 0

    path = tmp_path / "faction_events_buffered_seed_2.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    logger.close()

    assert [(row["tick"], row["event_type"], row["detail"]) for row in rows] == [
        ("3", "raid", "2 ore, 1 wood"),
        ("4", "treaty_broken", 'said "enough"'),
    ]


def test_event_flush_failure_is_nonfatal_and_retryable(tmp_path):
    logger = MetricsLogger(
        seed=3,
        condition="flaky",
        output_dir=str(tmp_path),
        event_flush_interval=100,
    )
    real_handle = logger._events_fh

    class FailOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.failures_remaining = 1

        def flush(self):
            if self.failures_remaining:
                self.failures_remaining -= 1
                raise OSError("simulated flush failure")
            return self.wrapped.flush()

        def close(self):
            return self.wrapped.close()

    logger._events_fh = FailOnce(real_handle)
    logger.record_event(5, "birth", "A", "B", "child")

    logger.finalize([], [], [])

    assert logger.total_births == 1
    assert logger._event_flush_failures == 1
    assert logger._pending_event_rows == 1
    assert logger.flush_events() is True
    assert logger._pending_event_rows == 0
    logger.close()
    health = logger.writer_health()
    assert health["event_flush_failures"] == 1
    assert health["unresolved_failures"] == []

    path = tmp_path / "faction_events_flaky_seed_3.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["event_type"] for row in rows] == ["birth"]


def test_unresolved_event_flush_failure_remains_observable(tmp_path):
    logger = MetricsLogger(
        seed=5,
        condition="always_flaky",
        output_dir=str(tmp_path),
        event_flush_interval=100,
    )
    real_handle = logger._events_fh

    class AlwaysFail:
        def flush(self):
            raise OSError("persistent flush failure")

        def close(self):
            return real_handle.close()

    logger._events_fh = AlwaysFail()
    logger.record_event(1, "raid", "A", "B", "food")

    assert logger.finalize([], [], []) is False
    assert logger.close() is False
    health = logger.writer_health()

    assert health["pending_event_rows"] == 1
    assert health["event_flush_failures"] >= 2
    assert health["close_failures"] == 1
    assert health["unresolved_failures"]
    real_handle.close()


def test_event_flush_interval_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="event_flush_interval"):
        MetricsLogger(
            seed=4,
            condition="invalid",
            output_dir=str(tmp_path),
            event_flush_interval=0,
        )


def test_treaty_lifecycle_emits_typed_events():
    diplomacy._treaties.clear()
    diplomacy.treaty_log.clear()
    log = StructuredEventLog()
    faction_a = SimpleNamespace(name="A")
    faction_b = SimpleNamespace(name="B")

    diplomacy._sign_treaty(
        faction_a,
        faction_b,
        diplomacy.TRADE_AGREEMENT,
        10,
        log,
    )
    diplomacy.break_treaty("A", "B", 11, log)

    assert [event.event_type for event in log.events] == [
        "treaty_signed",
        "treaty_broken",
    ]
    assert log.events[1].actor == "A"
    assert log.events[1].target == "B"
