"""Validation tests for effective run configuration."""

from types import SimpleNamespace

import pytest

from thalren_vale.config import (
    SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY,
    SimulationConfig,
)


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
        "enable_social_memory": False,
        "disable_social_memory": False,
        "enable_social_partner_bias": False,
        "disable_social_partner_bias": False,
        "maximum_social_ties": None,
        "relationship_decay_interval": None,
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


def test_social_controls_default_to_exact_research_safe_values():
    result = SimulationConfig.from_cli(cli_args())
    manifest = result.manifest_dict()

    assert manifest["social_memory_enabled"] is False
    assert manifest["social_partner_bias_enabled"] is False
    assert manifest["maximum_social_ties"] == 32
    assert manifest["relationship_decay_interval"] == 25
    assert manifest["social_controls_status"] == "disabled"
    assert manifest["social_control_notices"] == []


def test_bias_without_memory_normalizes_false_with_preserved_provenance():
    result = SimulationConfig.from_cli(
        cli_args(
            disable_social_memory=True,
            enable_social_partner_bias=True,
        )
    )
    manifest = result.manifest_dict()

    assert result.social_memory_enabled is False
    assert result.social_partner_bias_enabled is False
    assert manifest["social_control_notices"] == [
        SOCIAL_NOTICE_BIAS_WITHOUT_MEMORY
    ]
    assert manifest["social_controls_status"] == "normalized_uncontracted"


def test_enabled_or_nondefault_social_controls_are_engineering_only():
    enabled = SimulationConfig.from_cli(
        cli_args(
            enable_social_memory=True,
            enable_social_partner_bias=True,
        )
    )
    nondefault = SimulationConfig.from_cli(
        cli_args(maximum_social_ties=16, relationship_decay_interval=10)
    )

    assert enabled.social_partner_bias_enabled is True
    assert enabled.manifest_dict()["social_controls_status"] == (
        "engineering_only_uncontracted"
    )
    assert nondefault.manifest_dict()["social_controls_status"] == (
        "engineering_only_uncontracted"
    )


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
        ({"maximum_social_ties": 0}, "maximum social ties"),
        ({"relationship_decay_interval": 0}, "decay interval"),
    ],
)
def test_invalid_configuration_is_rejected(override, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig.from_cli(cli_args(**override))
