"""Explicit economy-raid control and compatibility tests."""

from types import SimpleNamespace

import pytest

from thalren_vale import economy, sim


@pytest.mark.parametrize(
    ("disabled_layers", "expected"),
    [
        (set(), True),
        ({"combat"}, True),
        ({"raids"}, False),
        ({"combat", "raids"}, False),
    ],
)
def test_sim_economy_layer_passes_explicit_raid_policy(
    monkeypatch, disabled_layers, expected
):
    captured = []
    monkeypatch.setattr(sim, "people", [])
    monkeypatch.setattr(sim, "factions", [])
    monkeypatch.setattr(sim, "event_log", [])
    monkeypatch.setattr(sim, "_disabled_layers", disabled_layers)
    monkeypatch.setattr(
        sim.economy,
        "economy_tick",
        lambda people, factions, tick, event_log, *, raids_enabled: (
            captured.append(raids_enabled)
        ),
    )

    sim.economy_layer(12)

    assert captured == [expected]


@pytest.mark.parametrize("raids_enabled", [True, False])
def test_economy_tick_runs_raids_only_when_enabled(monkeypatch, raids_enabled):
    active = [
        SimpleNamespace(members=[object()]),
        SimpleNamespace(members=[object()]),
    ]
    raid_calls = []
    monkeypatch.setattr(economy, "_individual_barter", lambda *args: None)
    monkeypatch.setattr(
        economy,
        "_faction_raids",
        lambda factions, tick, event_log: raid_calls.append(
            (factions, tick, event_log)
        ),
    )

    event_log = []
    economy.economy_tick(
        [], active, 1, event_log, raids_enabled=raids_enabled
    )

    assert bool(raid_calls) is raids_enabled


def test_economy_tick_default_keeps_legacy_raids_enabled(monkeypatch):
    active = [
        SimpleNamespace(members=[object()]),
        SimpleNamespace(members=[object()]),
    ]
    raid_calls = []
    monkeypatch.setattr(economy, "_individual_barter", lambda *args: None)
    monkeypatch.setattr(
        economy,
        "_faction_raids",
        lambda *args: raid_calls.append(args),
    )

    economy.economy_tick([], active, 1, [])

    assert len(raid_calls) == 1
