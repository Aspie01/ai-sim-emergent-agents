"""Tests for explicit simulation state ownership and lifecycle."""

import sys

from thalren_vale import combat, diplomacy, economy, factions, religion, sim


def test_domain_modules_share_state_owned_collections():
    assert combat.active_wars is sim.state.active_wars
    assert combat.war_history is sim.state.war_history
    assert factions.RIVALRIES is sim.state.rivalries
    assert diplomacy._treaties is sim.state.treaties
    assert diplomacy.treaty_log is sim.state.treaty_log
    assert diplomacy._reputation is sim.state.reputation
    assert economy.faction_currencies is sim.state.faction_currencies
    assert economy.trade_routes is sim.state.trade_routes
    assert religion._religions is sim.state.religions
    assert religion._HOLY_WARS is sim.state.holy_wars


def test_reset_runtime_state_clears_core_and_domain_stores():
    sim.state.people.append(object())
    sim.state.event_log.append("event")
    combat.active_wars.append(object())
    economy.trade_routes[frozenset(("a", "b"))] = {}
    diplomacy._reputation["a"] = 5
    religion._HOLY_WARS.add(frozenset(("a", "b")))

    sim.reset_runtime_state()

    assert sim.people == []
    assert sim.event_log == []
    assert combat.active_wars == []
    assert economy.trade_routes == {}
    assert diplomacy._reputation == {}
    assert religion._HOLY_WARS == set()


def test_same_seed_is_repeatable_in_one_process(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "thalren-vale",
            "--seed",
            "321",
            "--ticks",
            "5",
            "--condition",
            "repeatable",
            "--disable-antistag",
        ],
    )

    metrics_path = tmp_path / "data" / "metrics_repeatable_seed_321.csv"

    sim.run()
    first_metrics = metrics_path.read_text(encoding="utf-8")

    sim.run()
    second_metrics = metrics_path.read_text(encoding="utf-8")

    assert second_metrics == first_metrics
