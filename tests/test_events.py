"""Structured event stream and metrics integration tests."""

import csv
from types import SimpleNamespace

import pytest

from thalren_vale import diplomacy
from thalren_vale.events import StructuredEventLog, emit_event
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

    path = tmp_path / "faction_events_flaky_seed_3.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["event_type"] for row in rows] == ["birth"]


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
