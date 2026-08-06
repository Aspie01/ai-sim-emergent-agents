"""Factions selecting between the legacy and relationship social models."""

from __future__ import annotations

import pytest

import run_experiments
from thalren_vale import factions as factions_module
from thalren_vale.config import (
    FACTION_RELATIONSHIP_TRUST_NOTICE_WITHOUT_SOCIAL,
    FACTION_TRUST_THRESHOLD,
    FactionRelationshipTrustConfig,
    SimulationConfig,
)
from thalren_vale.factions import _directed_trust_qualifies, _mutual_trust
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.social import Relationship

LEGACY = None
MODERN = FactionRelationshipTrustConfig(True, 0.40)


def pair(*, legacy=0, relationship=None, reverse_relationship=None):
    first = Inhabitant("A", 0, 0)
    first.inhabitant_id = 1
    second = Inhabitant("B", 0, 0)
    second.inhabitant_id = 2
    first.trust["B"] = legacy
    second.trust["A"] = legacy
    if relationship is not None:
        first.relationships[2] = Relationship(trust=relationship)
        second.relationships[1] = Relationship(
            trust=relationship if reverse_relationship is None
            else reverse_relationship)
    return first, second


# ── The legacy model is untouched ───────────────────────────────────────────

def test_legacy_model_reads_the_interaction_counter():
    below, _ = pair(legacy=FACTION_TRUST_THRESHOLD)
    above, other = pair(legacy=FACTION_TRUST_THRESHOLD + 1)
    assert _directed_trust_qualifies(below, other, LEGACY) is False
    assert _directed_trust_qualifies(above, other, LEGACY) is True


def test_legacy_model_ignores_relationship_records():
    """Selecting no config must reproduce historical behaviour exactly."""
    first, second = pair(legacy=99, relationship=-1.0)
    assert _directed_trust_qualifies(first, second, LEGACY) is True
    first, second = pair(legacy=0, relationship=1.0)
    assert _directed_trust_qualifies(first, second, LEGACY) is False


def test_disabled_config_behaves_as_the_legacy_model():
    disabled = FactionRelationshipTrustConfig(False, 0.40)
    first, second = pair(legacy=99, relationship=-1.0)
    assert _directed_trust_qualifies(first, second, disabled) is True


# ── The models genuinely disagree ───────────────────────────────────────────

def test_high_interaction_count_can_fail_the_relationship_threshold():
    """Many shallow interactions are not the same as a trusted tie."""
    first, second = pair(legacy=9, relationship=0.10)
    assert _directed_trust_qualifies(first, second, LEGACY) is True
    assert _directed_trust_qualifies(first, second, MODERN) is False


def test_few_interactions_can_still_clear_the_relationship_threshold():
    first, second = pair(legacy=2, relationship=0.90)
    assert _directed_trust_qualifies(first, second, LEGACY) is False
    assert _directed_trust_qualifies(first, second, MODERN) is True


def test_relationship_threshold_is_inclusive():
    at, other = pair(relationship=0.40)
    below, _ = pair(relationship=0.3999)
    assert _directed_trust_qualifies(at, other, MODERN) is True
    assert _directed_trust_qualifies(below, other, MODERN) is False


# ── Absent records ──────────────────────────────────────────────────────────

def test_absent_relationship_never_qualifies():
    """The default run has no records at all; this is why the flag exists.

    Reading relationships unconditionally would stop every faction forming,
    because social memory is disabled by default and nothing populates them.
    """
    first = Inhabitant("A", 0, 0)
    first.inhabitant_id = 1
    second = Inhabitant("B", 0, 0)
    second.inhabitant_id = 2
    first.trust["B"] = 99
    assert _directed_trust_qualifies(first, second, MODERN) is False
    assert _directed_trust_qualifies(first, second, LEGACY) is True


def test_absent_inhabitant_id_never_qualifies():
    first, second = pair(relationship=0.90)
    second.inhabitant_id = None
    assert _directed_trust_qualifies(first, second, MODERN) is False


# ── Mutual trust ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("config", [LEGACY, MODERN])
def test_mutual_trust_requires_both_directions(config):
    first, second = pair(
        legacy=9, relationship=0.90, reverse_relationship=0.10)
    if config is LEGACY:
        # Legacy is symmetric by construction here, so make it asymmetric.
        second.trust["A"] = 0
    assert _mutual_trust(first, second, config) is False


def test_mutual_trust_holds_when_both_directions_qualify():
    first, second = pair(legacy=9, relationship=0.90)
    assert _mutual_trust(first, second, LEGACY) is True
    assert _mutual_trust(first, second, MODERN) is True


# ── Both faction entry points accept the selector ───────────────────────────

@pytest.mark.parametrize("name", ["check_faction_formation", "faction_tick"])
def test_faction_entry_points_accept_the_selector(name):
    """Threading only one entry point left the other with an undefined name."""
    import inspect

    signature = inspect.signature(getattr(factions_module, name))
    assert "faction_trust_config" in signature.parameters


# ── Dependency cascade ──────────────────────────────────────────────────────

def test_without_social_memory_the_request_normalizes():
    config = SimulationConfig(faction_relationship_trust_enabled=True)
    config.validate()
    assert config.faction_relationship_trust_enabled is False
    assert FACTION_RELATIONSHIP_TRUST_NOTICE_WITHOUT_SOCIAL in (
        config.faction_relationship_trust_control_notices)


def test_with_social_memory_the_request_holds():
    config = SimulationConfig(
        social_memory_enabled=True, faction_relationship_trust_enabled=True)
    config.validate()
    assert config.faction_relationship_trust_enabled is True
    assert config.faction_relationship_trust_control_notices == ()


@pytest.mark.parametrize("threshold", [0.0, -0.1, 1.5, 1, True, None])
def test_config_rejects_invalid_thresholds(threshold):
    with pytest.raises(ValueError):
        config = SimulationConfig(
            faction_relationship_trust_threshold=threshold)
        config.validate()


# ── Runner containment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argument", [
    "--enable-faction-relationship-trust",
    "--disable-faction-relationship-trust",
    "--faction-relationship-trust-threshold",
    "--faction-relationship-trust-threshold=0.5",
    "--enable-faction-relationship",
    "--faction-relationship",
])
def test_runner_rejects_the_complete_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_faction_relationship_trust_args(
            (argument,))


@pytest.mark.parametrize("argument", ["--ticks=10", "--seed=1", "--log-mode"])
def test_runner_still_accepts_unrelated_options(argument):
    run_experiments._reject_uncontracted_faction_relationship_trust_args(
        (argument,))


# ── Artifact validation ─────────────────────────────────────────────────────

def collect(config: dict):
    from thalren_vale.artifact_validation import (
        _IssueCollector,
        _validate_faction_relationship_trust_configuration,
    )

    issues = _IssueCollector()
    _validate_faction_relationship_trust_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = SimulationConfig(
        social_memory_enabled=True, faction_relationship_trust_enabled=True)
    enabled.validate()
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"faction_relationship_trust_enabled": True,
     "social_memory_enabled": False},
    {"faction_relationship_trust_threshold": 0.0},
    {"faction_relationship_trust_threshold": 1.5},
    {"faction_relationship_trust_threshold": 1},
    {"faction_relationship_trust_controls_status": "bogus"},
    {"faction_relationship_trust_threshold": 0.7,
     "faction_relationship_trust_controls_status": "disabled"},
    {"faction_relationship_trust_controls_status": "normalized_uncontracted",
     "faction_relationship_trust_control_notices": []},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)


def test_nondefault_controls_are_not_v2_ready():
    from thalren_vale.artifact_validation import _readiness_issues

    config = SimulationConfig(faction_relationship_trust_threshold=0.7)
    config.validate()
    issues = _readiness_issues({"configuration": config.manifest_dict()}, None)
    assert "faction_relationship_trust_controls_not_v2_ready" in {
        issue.code for issue in issues}
