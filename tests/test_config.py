"""Validation tests for effective run configuration."""

from types import SimpleNamespace

import pytest

from thalren_vale.config import (
    COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY,
    DIALECT_NOTICE_WITHOUT_COALITIONS,
    DIALECT_NOTICE_WITHOUT_LANGUAGE,
    INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
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
        "enable_language_evolution": False,
        "disable_language_evolution": False,
        "maximum_language_associations": None,
        "maximum_signal_length": None,
        "language_learning_rate": None,
        "language_reinforcement_rate": None,
        "language_forgetting_interval": None,
        "enable_language_invention": False,
        "disable_language_invention": False,
        "enable_coalition_emergence": False,
        "disable_coalition_emergence": False,
        "coalition_minimum_size": None,
        "coalition_trust_threshold": None,
        "coalition_familiarity_threshold": None,
        "coalition_maximum_grievance": None,
        "coalition_persistence_ticks": None,
        "maximum_active_coalitions": None,
        "enable_coalition_dialect_influence": False,
        "disable_coalition_dialect_influence": False,
        "same_coalition_learning_multiplier": None,
        "same_coalition_reinforcement_multiplier": None,
        "enable_language_contact": False,
        "disable_language_contact": False,
        "cross_group_learning_multiplier": None,
        "borrowing_exposure_threshold": None,
        "borrowing_confidence_threshold": None,
        "enable_intergenerational_language": False,
        "disable_intergenerational_language": False,
        "maximum_parental_meanings_per_parent": None,
        "intergenerational_learning_strength": None,
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


def test_language_controls_default_to_exact_research_safe_values():
    manifest = SimulationConfig.from_cli(cli_args()).manifest_dict()

    assert manifest["language_evolution_enabled"] is False
    assert manifest["maximum_language_associations"] == 32
    assert manifest["maximum_signal_length"] == 3
    assert manifest["language_learning_rate"] == 0.20
    assert manifest["language_reinforcement_rate"] == 0.10
    assert manifest["language_forgetting_interval"] == 25
    assert manifest["language_invention_enabled"] is True
    assert manifest["language_controls_status"] == "disabled"
    assert manifest["language_control_notices"] == []


def test_enabled_or_nondefault_language_controls_are_engineering_only():
    enabled = SimulationConfig.from_cli(
        cli_args(enable_language_evolution=True))
    nondefault = SimulationConfig.from_cli(cli_args(
        maximum_language_associations=12,
        maximum_signal_length=2,
        language_learning_rate=0.30,
        language_reinforcement_rate=0.25,
        language_forgetting_interval=5,
        disable_language_invention=True,
    ))

    assert enabled.language_evolution_enabled is True
    assert enabled.language_controls_status == "engineering_only_uncontracted"
    assert nondefault.language_invention_enabled is False
    assert nondefault.language_controls_status == "engineering_only_uncontracted"


def test_coalition_controls_default_to_exact_research_safe_values():
    result = SimulationConfig.from_cli(cli_args())
    manifest = result.manifest_dict()

    assert manifest["coalition_emergence_enabled"] is False
    assert manifest["coalition_minimum_size"] == 3
    assert type(manifest["coalition_trust_threshold"]) is float
    assert manifest["coalition_trust_threshold"] == 0.24
    assert manifest["coalition_familiarity_threshold"] == 0.40
    assert manifest["coalition_maximum_grievance"] == 0.20
    assert manifest["coalition_persistence_ticks"] == 5
    assert manifest["maximum_active_coalitions"] == 32
    assert manifest["coalition_controls_status"] == "disabled"
    assert manifest["coalition_control_notices"] == []


def test_disabled_coalition_defaults_do_not_reject_small_population_caps():
    result = SimulationConfig.from_cli(cli_args(
        pop_cap=2,
        starting_pop=2,
    ))

    assert result.population_cap == 2
    assert result.coalition_emergence_enabled is False
    assert result.coalition_minimum_size == 3
    assert result.maximum_active_coalitions == 32


def test_coalition_without_memory_normalizes_with_separate_provenance():
    result = SimulationConfig.from_cli(
        cli_args(enable_coalition_emergence=True))
    manifest = result.manifest_dict()

    assert result.coalition_emergence_enabled is False
    assert manifest["coalition_controls_status"] == "normalized_uncontracted"
    assert manifest["coalition_control_notices"] == [
        COALITION_NOTICE_EMERGENCE_WITHOUT_SOCIAL_MEMORY
    ]
    assert manifest["social_controls_status"] == "disabled"
    assert manifest["social_control_notices"] == []


def test_enabled_or_nondefault_coalition_controls_are_engineering_only():
    enabled = SimulationConfig.from_cli(cli_args(
        enable_social_memory=True,
        enable_coalition_emergence=True,
    ))
    nondefault = SimulationConfig.from_cli(cli_args(
        coalition_minimum_size=4,
        coalition_trust_threshold=0.30,
    ))

    assert enabled.coalition_emergence_enabled is True
    assert enabled.coalition_controls_status == "engineering_only_uncontracted"
    assert nondefault.coalition_controls_status == "engineering_only_uncontracted"
    assert enabled.social_controls_status == "engineering_only_uncontracted"


def test_dialect_controls_default_to_exact_research_safe_values():
    manifest = SimulationConfig.from_cli(cli_args()).manifest_dict()

    assert manifest["coalition_dialect_influence_enabled"] is False
    assert manifest["same_coalition_learning_multiplier"] == 1.50
    assert manifest["same_coalition_reinforcement_multiplier"] == 1.25
    assert manifest["dialect_controls_status"] == "disabled"
    assert manifest["dialect_control_notices"] == []


def test_dialect_request_normalizes_against_each_effective_dependency():
    neither = SimulationConfig.from_cli(cli_args(
        enable_coalition_dialect_influence=True))
    no_coalitions = SimulationConfig.from_cli(cli_args(
        enable_language_evolution=True,
        enable_coalition_dialect_influence=True,
    ))

    assert neither.coalition_dialect_influence_enabled is False
    assert neither.dialect_controls_status == "normalized_uncontracted"
    assert neither.dialect_control_notices == tuple(sorted((
        DIALECT_NOTICE_WITHOUT_LANGUAGE,
        DIALECT_NOTICE_WITHOUT_COALITIONS,
    )))
    assert no_coalitions.dialect_control_notices == (
        DIALECT_NOTICE_WITHOUT_COALITIONS,
    )


def test_enabled_or_nondefault_dialect_controls_are_engineering_only():
    enabled = SimulationConfig.from_cli(cli_args(
        enable_social_memory=True,
        enable_language_evolution=True,
        enable_coalition_emergence=True,
        enable_coalition_dialect_influence=True,
    ))
    nondefault = SimulationConfig.from_cli(cli_args(
        same_coalition_learning_multiplier=1.75,
    ))

    assert enabled.coalition_dialect_influence_enabled is True
    assert enabled.dialect_control_notices == ()
    assert enabled.dialect_controls_status == "engineering_only_uncontracted"
    assert nondefault.coalition_dialect_influence_enabled is False
    assert nondefault.dialect_controls_status == "engineering_only_uncontracted"


def test_language_contact_controls_default_to_exact_research_safe_values():
    result = SimulationConfig.from_cli(cli_args())
    manifest = result.manifest_dict()

    assert manifest["language_contact_enabled"] is False
    assert type(manifest["cross_group_learning_multiplier"]) is float
    assert manifest["cross_group_learning_multiplier"] == 1.50
    assert type(manifest["borrowing_exposure_threshold"]) is int
    assert manifest["borrowing_exposure_threshold"] == 3
    assert type(manifest["borrowing_confidence_threshold"]) is float
    assert manifest["borrowing_confidence_threshold"] == 0.50
    assert manifest["language_contact_controls_status"] == "disabled"
    assert manifest["language_contact_control_notices"] == []


def test_language_contact_request_normalizes_against_effective_dependencies():
    neither = SimulationConfig.from_cli(cli_args(
        enable_language_contact=True))
    no_coalitions = SimulationConfig.from_cli(cli_args(
        enable_language_evolution=True,
        enable_language_contact=True,
    ))
    no_language = SimulationConfig.from_cli(cli_args(
        enable_social_memory=True,
        enable_coalition_emergence=True,
        enable_language_contact=True,
    ))

    assert neither.language_contact_enabled is False
    assert neither.language_contact_controls_status == "normalized_uncontracted"
    assert neither.language_contact_control_notices == tuple(sorted((
        LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
        LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    )))
    assert no_coalitions.language_contact_control_notices == (
        LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    )
    assert no_language.language_contact_control_notices == (
        LANGUAGE_CONTACT_NOTICE_WITHOUT_LANGUAGE,
    )


def test_language_contact_uses_effective_coalition_after_its_normalization():
    result = SimulationConfig.from_cli(cli_args(
        enable_language_evolution=True,
        enable_coalition_emergence=True,
        enable_language_contact=True,
    ))

    assert result.coalition_emergence_enabled is False
    assert result.coalition_control_notices == (
        "coalition_emergence_requested_without_social_memory",
    )
    assert result.language_contact_enabled is False
    assert result.language_contact_control_notices == (
        LANGUAGE_CONTACT_NOTICE_WITHOUT_COALITIONS,
    )


def test_enabled_contact_is_independent_of_coalition_dialect_influence():
    result = SimulationConfig.from_cli(cli_args(
        enable_social_memory=True,
        enable_language_evolution=True,
        enable_coalition_emergence=True,
        enable_language_contact=True,
    ))

    assert result.language_contact_enabled is True
    assert result.language_contact_control_notices == ()
    assert result.language_contact_controls_status == (
        "engineering_only_uncontracted"
    )
    assert result.coalition_dialect_influence_enabled is False
    assert result.dialect_controls_status == "disabled"


def test_nondefault_contact_controls_are_engineering_only_without_normalization():
    result = SimulationConfig.from_cli(cli_args(
        cross_group_learning_multiplier=1.75,
        borrowing_exposure_threshold=4,
        borrowing_confidence_threshold=0.60,
    ))

    assert result.language_contact_enabled is False
    assert result.language_contact_control_notices == ()
    assert result.language_contact_controls_status == (
        "engineering_only_uncontracted"
    )
    assert result.language_controls_status == "disabled"
    assert result.coalition_controls_status == "disabled"
    assert result.dialect_controls_status == "disabled"


def test_intergenerational_controls_default_to_exact_safe_values():
    result = SimulationConfig.from_cli(cli_args())
    manifest = result.manifest_dict()

    assert manifest["intergenerational_language_enabled"] is False
    assert type(manifest["maximum_parental_meanings_per_parent"]) is int
    assert manifest["maximum_parental_meanings_per_parent"] == 2
    assert type(manifest["intergenerational_learning_strength"]) is float
    assert manifest["intergenerational_learning_strength"] == 0.20
    assert (
        manifest["intergenerational_language_controls_status"] == "disabled"
    )
    assert manifest["intergenerational_language_control_notices"] == []


def test_intergenerational_request_normalizes_only_against_base_language():
    normalized = SimulationConfig.from_cli(cli_args(
        enable_intergenerational_language=True,
    ))
    independent = SimulationConfig.from_cli(cli_args(
        enable_language_evolution=True,
        enable_intergenerational_language=True,
    ))

    assert normalized.intergenerational_language_enabled is False
    assert normalized.intergenerational_language_control_notices == (
        INTERGENERATIONAL_LANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    )
    assert normalized.intergenerational_language_controls_status == (
        "normalized_uncontracted"
    )
    assert independent.intergenerational_language_enabled is True
    assert independent.intergenerational_language_control_notices == ()
    assert independent.intergenerational_language_controls_status == (
        "engineering_only_uncontracted"
    )
    assert independent.coalition_emergence_enabled is False
    assert independent.coalition_dialect_influence_enabled is False
    assert independent.language_contact_enabled is False


def test_nondefault_intergenerational_controls_are_engineering_only():
    result = SimulationConfig.from_cli(cli_args(
        maximum_parental_meanings_per_parent=3,
        intergenerational_learning_strength=0.35,
    ))

    assert result.intergenerational_language_enabled is False
    assert result.intergenerational_language_control_notices == ()
    assert result.intergenerational_language_controls_status == (
        "engineering_only_uncontracted"
    )


def test_intergenerational_controls_reject_nonboolean_gate():
    with pytest.raises(ValueError, match="intergenerational language setting"):
        SimulationConfig(intergenerational_language_enabled=1).validate()


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
        ({"maximum_language_associations": 0}, "language associations"),
        ({"maximum_signal_length": 5}, "signal length"),
        ({"language_learning_rate": 0.0}, "learning rate"),
        ({"language_reinforcement_rate": float("nan")}, "reinforcement rate"),
        ({"language_forgetting_interval": 0}, "forgetting interval"),
        ({"coalition_minimum_size": 2}, "coalition minimum size"),
        ({"coalition_trust_threshold": 1}, "finite float"),
        ({"coalition_familiarity_threshold": float("nan")}, "finite float"),
        ({"coalition_maximum_grievance": 1.1}, "finite float"),
        ({"coalition_persistence_ticks": 1}, "persistence ticks"),
        ({"maximum_active_coalitions": 0}, "maximum active coalitions"),
        ({"same_coalition_learning_multiplier": 1}, "finite float"),
        ({"same_coalition_learning_multiplier": 2.1}, "finite float"),
        ({"same_coalition_reinforcement_multiplier": float("nan")}, "finite float"),
        ({"cross_group_learning_multiplier": 1}, "finite float"),
        ({"cross_group_learning_multiplier": 2.1}, "finite float"),
        ({"cross_group_learning_multiplier": float("nan")}, "finite float"),
        ({"borrowing_exposure_threshold": True}, "exposure threshold"),
        ({"borrowing_exposure_threshold": 1}, "exposure threshold"),
        ({"borrowing_exposure_threshold": 33}, "exposure threshold"),
        ({"borrowing_confidence_threshold": 1}, "finite float"),
        ({"borrowing_confidence_threshold": 0.09}, "finite float"),
        ({"borrowing_confidence_threshold": float("inf")}, "finite float"),
        ({"maximum_parental_meanings_per_parent": True}, "parental meanings"),
        ({"maximum_parental_meanings_per_parent": 0}, "parental meanings"),
        ({"maximum_parental_meanings_per_parent": 5}, "parental meanings"),
        ({"intergenerational_learning_strength": 1}, "learning strength"),
        ({"intergenerational_learning_strength": 0.0}, "learning strength"),
        (
            {"intergenerational_learning_strength": float("nan")},
            "learning strength",
        ),
    ],
)
def test_invalid_configuration_is_rejected(override, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig.from_cli(cli_args(**override))
