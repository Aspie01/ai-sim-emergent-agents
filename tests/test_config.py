"""Validation tests for effective run configuration."""

from types import SimpleNamespace

import pytest

from thalren_vale.config import SimulationConfig


def cli_args(**overrides):
    values = {
        "condition": "baseline",
        "ticks": None,
        "pop_cap": None,
        "starting_pop": None,
        "faction_trust_threshold": None,
        "war_tension_threshold": None,
        "belief_sharing_prob": None,
        "disable_layer": "",
        "disable_raids": False,
        "disable_antistag": False,
        "enable_belief_tracking": False,
        "log_mode": "full",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_configuration_normalizes_disabled_layers():
    result = SimulationConfig.from_cli(
        cli_args(disable_layer=" religion,combat,religion ")
    )

    assert result.disabled_layers == ("combat", "religion")
    assert result.manifest_dict()["disabled_layers"] == ["combat", "religion"]
    assert result.manifest_dict()["raids_enabled"] is True


def test_explicit_raid_controls_are_normalized_and_recorded():
    alias = SimulationConfig.from_cli(cli_args(disable_raids=True))
    layer = SimulationConfig.from_cli(cli_args(disable_layer="raids"))

    assert alias.disabled_layers == ("raids",)
    assert layer.disabled_layers == ("raids",)
    assert alias.manifest_dict()["raids_enabled"] is False
    assert layer.manifest_dict()["raids_enabled"] is False


def test_disabling_combat_alone_keeps_raids_enabled():
    result = SimulationConfig.from_cli(cli_args(disable_layer="combat"))

    assert result.disabled_layers == ("combat",)
    assert result.raids_enabled is True
    assert result.manifest_dict()["raids_enabled"] is True


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"condition": "../escape"}, "condition"),
        ({"ticks": 0}, "ticks"),
        ({"pop_cap": 10, "starting_pop": 11}, "starting population"),
        ({"starting_pop": 136, "pop_cap": 200}, "135"),
        ({"faction_trust_threshold": -1}, "trust threshold"),
        ({"war_tension_threshold": 0}, "war tension"),
        ({"belief_sharing_prob": 1.01}, "probability"),
        ({"disable_layer": "combat,unknown"}, "unknown disabled layer"),
        ({"log_mode": "loud"}, "log mode"),
    ],
)
def test_invalid_configuration_is_rejected(override, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig.from_cli(cli_args(**override))
