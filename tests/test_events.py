"""Structured event stream and metrics integration tests."""

import csv
from types import SimpleNamespace

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
