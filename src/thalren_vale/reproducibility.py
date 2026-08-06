"""Canonical simulation fingerprints and run manifests."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from .artifact_contract import (
    ALLOW_ZERO_EVENTS,
    BELIEFS_SCHEMA_VERSION,
    BELIEF_SNAPSHOT_CARDINALITY,
    BELIEF_SNAPSHOT_INTERVAL,
    EvidencePathError,
    METRICS_SCHEMA_VERSION,
    METRICS_TIMING_CONTRACT,
    RUN_MANIFEST_SCHEMA_VERSION,
    RUN_SUMMARY_SCHEMA_VERSION,
    lexical_absolute,
    require_contained_regular_file,
    require_real_directory,
    require_safe_manifest_target,
)
from .events import EVENT_SCHEMA_VERSION
from .config import (
    CoalitionDialectConfig,
    CompositionalProtolanguageConfig,
    GrammarEvolutionConfig,
    IntergenerationalLanguageConfig,
    LanguageCoevolutionConfig,
    LanguageContactConfig,
    LanguageEvolutionConfig,
    LexicalEvolutionConfig,
)
from .social import relationship_records
from .coalitions import (
    CoalitionRuntimeState,
    canonical_candidate_snapshot,
    canonical_coalition_snapshot,
)
from .language import (
    AgentLanguageState,
    CoalitionDialectRuntimeState,
    CompositeMeaning,
    CompositionalProtolanguageRuntimeState,
    GrammarEvolutionRuntimeState,
    IntergenerationalLanguageRuntimeState,
    LanguageCoevolutionRuntimeState,
    LanguageContactRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalEvolutionRuntimeState,
    agent_language_record,
    coalition_dialect_runtime_record,
    compositional_protolanguage_runtime_is_pristine,
    compositional_protolanguage_runtime_record,
    contact_runtime_is_pristine,
    dialect_runtime_is_pristine,
    grammar_evolution_runtime_is_pristine,
    grammar_evolution_runtime_record,
    language_coevolution_runtime_is_pristine,
    language_coevolution_runtime_record,
    intergenerational_language_runtime_record,
    intergenerational_runtime_is_pristine,
    lexical_evolution_runtime_is_pristine,
    lexical_evolution_runtime_record,
    language_contact_runtime_record,
    language_runtime_is_pristine,
    language_runtime_record,
    validate_coalition_dialect_config,
    validate_intergenerational_language_config,
    validate_intergenerational_language_runtime,
    validate_intergenerational_parent_references,
    validate_language_contact_config,
    validate_language_contact_runtime,
    validate_language_config,
    validate_lexical_evolution_config,
    validate_lexical_evolution_runtime,
)


def _person_record(
    person,
    *,
    include_social: bool = False,
    include_language: bool = False,
    include_contact: bool = False,
    include_intergenerational: bool = False,
    include_lexical_evolution: bool = False,
    include_grammar_evolution: bool = False,
    include_language_coevolution: bool = False,
    language_config=None,
    contact_config=None,
    lexical_config=None,
) -> dict:
    religion = getattr(person, "religion", None)
    record = {
        "name": person.name,
        "position": [person.r, person.c],
        "health": person.health,
        "hunger": person.hunger,
        "inventory": dict(person.inventory),
        "beliefs": sorted(person.beliefs),
        "trust": dict(person.trust),
        "faction": person.faction,
        "currency": person.currency,
        "generation": person.generation,
        "religion": getattr(religion, "name", None),
        "is_priest": person.is_priest,
    }
    if include_social or include_language:
        inhabitant_id = getattr(person, "inhabitant_id", None)
        if type(inhabitant_id) is not int or inhabitant_id < 0:
            raise ValueError(
                "enabled social state requires assigned inhabitant IDs")
        record["inhabitant_id"] = inhabitant_id
    if include_social:
        record["relationships"] = relationship_records(
            person, include_intelligibility=include_language_coevolution)
    if include_language:
        if language_config is None:
            raise ValueError("enabled language hashing requires effective controls")
        language = agent_language_record(
            person,
            config=language_config,
            include_contact=include_contact,
            contact_config=contact_config,
            include_intergenerational=include_intergenerational,
            include_lexical_evolution=include_lexical_evolution,
            lexical_config=lexical_config,
            include_grammar_evolution=include_grammar_evolution,
        )
        record["language"] = {
            key: value
            for key, value in language.items()
            if key != "inhabitant_id"
        }
    return record


def _active_research_record(faction) -> dict | None:
    """Return one faction's in-progress research in canonical field order.

    `technology.py` owns research state as a dynamically assigned
    ``active_research`` dict. The earlier payload read ``researching`` and
    ``research_progress``, which nothing ever assigns, so both fields were
    permanently ``None`` and in-progress research was invisible to the hash:
    two factions researching different technologies produced identical
    fingerprints. Reading the authoritative dict closes that gap.
    """
    research = getattr(faction, "active_research", None)
    if research is None:
        return None
    if not isinstance(research, Mapping):
        raise ValueError("active research must be a mapping or absent")
    return {
        "tech": research.get("tech"),
        "progress": research.get("progress"),
        "started": research.get("started"),
        "paused": research.get("paused"),
    }


def _faction_record(faction) -> dict:
    settlement = getattr(faction, "settlement", None)
    return {
        "name": faction.name,
        "members": sorted(member.name for member in faction.members),
        "shared_beliefs": sorted(faction.shared_beliefs),
        "territory": sorted([list(tile) for tile in faction.territory]),
        "founded_tick": faction.founded_tick,
        "food_reserve": faction.food_reserve,
        "legends": sorted(str(legend) for legend in faction.legends),
        "is_settled": faction.is_settled,
        "settled_since": faction.settled_since,
        "settled_ticks": faction.settled_ticks,
        "settlement": (
            {
                "owner_faction": settlement.owner_faction,
                "position": [getattr(settlement, "r", None),
                             getattr(settlement, "c", None)],
                "founded_tick": settlement.founded_tick,
                "status": settlement.status,
                "storage_buffer": settlement.storage_buffer,
                "housing_capacity": settlement.housing_capacity,
            }
            if settlement is not None else None
        ),
        "techs": sorted(getattr(faction, "techs", set())),
        "active_research": _active_research_record(faction),
    }


def _war_record(war) -> dict:
    return {
        "attacker": war.attacker.name,
        "defender": war.defender.name,
        "cause": war.cause,
        "started_tick": war.started_tick,
        "tick_count": war.tick_count,
        "allied_with_attacker": sorted(f.name for f in war.allied_with_a),
        "allied_with_defender": sorted(f.name for f in war.allied_with_d),
        "ended": war.ended,
        "outcome": war.outcome,
        "tribute_remaining": war.tribute_remaining,
    }


def _mapping_records(mapping: dict) -> list:
    """Represent mappings with non-string keys in deterministic order."""
    records = []
    for key, value in mapping.items():
        if isinstance(key, (set, frozenset, tuple)):
            normalized_key = sorted(key)
        else:
            normalized_key = key
        records.append({"key": normalized_key, "value": value})
    return sorted(records, key=lambda record: json.dumps(record["key"], sort_keys=True))


def _json_safe(value):
    """Convert supported state values into deterministic JSON primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [_json_safe(item) for item in value]
        return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, Path):
        return str(value)
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return {"object_type": type(value).__name__, "name": name}
    raise TypeError(f"unsupported canonical state value: {type(value).__name__}")


def _require_empty_disabled_relationships(state) -> None:
    """Reject social state that the historical disabled hash would omit."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            relationships = getattr(inhabitant, "relationships", {})
            if not relationships:
                continue
            name = getattr(inhabitant, "name", None)
            inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
            raise ValueError(
                "disabled social memory requires empty relationships: "
                f"{cohort}[{index}] name={name!r} "
                f"inhabitant_id={inhabitant_id!r} has "
                f"{len(relationships)} relationship(s)"
            )


def _require_empty_disabled_coalition_state(state) -> None:
    """Reject coalition state omitted from the coalition-disabled hash."""
    runtime = getattr(state, "coalitions", None)
    if runtime is None:
        return
    if not isinstance(runtime, CoalitionRuntimeState):
        raise ValueError("disabled coalition state has an invalid runtime type")
    unexpected = {
        "candidates": bool(runtime.candidates),
        "active_coalitions": bool(runtime.active_coalitions),
        "member_to_coalition": bool(runtime.member_to_coalition),
        "next_coalition_id": runtime.next_coalition_id != 0,
        "candidate_formation_count": runtime.candidate_formation_count != 0,
        "split_event_count": runtime.split_event_count != 0,
        "split_child_count": runtime.split_child_count != 0,
        "dissolution_count": runtime.dissolution_count != 0,
        "last_observation_tick": runtime.last_observation_tick is not None,
        "last_active_inhabitant_ids": bool(runtime.last_active_inhabitant_ids),
        "last_qualifying_reciprocal_edge_count": (
            runtime.last_qualifying_reciprocal_edge_count != 0
        ),
    }
    populated = sorted(name for name, present in unexpected.items() if present)
    if populated:
        raise ValueError(
            "disabled coalition emergence requires pristine coalition state: "
            + ", ".join(populated)
        )


def _require_pristine_disabled_language_state(state) -> None:
    """Reject every language field omitted from the disabled behavioral hash."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled language requires explicit pristine agent state: "
                    f"{cohort}[{index}] is missing AgentLanguageState",
                )
            if (
                language.production
                or language.comprehension
                or language.next_invention_index != 0
                or type(language.next_invention_index) is not int
            ):
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_agent_language_state",
                    "disabled language evolution requires pristine agent state: "
                    f"{cohort}[{index}] inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "language", None)
    if type(runtime) is not LanguageRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_language_runtime",
            "disabled language runtime is missing or invalid",
        )
    if not language_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_language_runtime",
            "disabled language evolution requires pristine runtime state",
        )


def _require_pristine_disabled_dialect_state(state) -> None:
    """Reject dialect state omitted from the dialect-disabled payload."""
    runtime = getattr(state, "dialect", None)
    if type(runtime) is not CoalitionDialectRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_dialect_runtime",
            "disabled dialect influence requires an explicit runtime",
        )
    if not dialect_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_dialect_runtime",
            "disabled dialect influence requires pristine runtime state",
        )


def _require_pristine_disabled_contact_state(state) -> None:
    """Reject contact state omitted from the contact-disabled payload."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled contact requires explicit agent language state: "
                    f"{cohort}[{index}] is missing AgentLanguageState",
                )
            hidden = [
                (store_name, association)
                for store_name, store in (
                    ("production", language.production),
                    ("comprehension", language.comprehension),
                )
                for association in store.values()
                if (
                    getattr(association, "contact_exposure", None) is not None
                    or getattr(association, "borrowing_provenance", None) is not None
                )
            ]
            if hidden:
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_contact_metadata",
                    "disabled language contact cannot conceal association metadata: "
                    f"{cohort}[{index}] inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "language_contact", None)
    if type(runtime) is not LanguageContactRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_contact_runtime",
            "disabled language contact requires an explicit runtime",
        )
    if not contact_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_contact_runtime",
            "disabled language contact requires pristine runtime state",
        )


def _require_pristine_disabled_intergenerational_state(state) -> None:
    """Reject transmission state omitted from the disabled behavioral payload."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled intergenerational language requires explicit "
                    f"agent language state: {cohort}[{index}]",
                )
            hidden = [
                (store_name, association)
                for store_name, store in (
                    ("production", language.production),
                    ("comprehension", language.comprehension),
                )
                for association in store.values()
                if getattr(
                    association, "intergenerational_provenance", None
                ) is not None
            ]
            if hidden:
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_intergenerational_metadata",
                    "disabled intergenerational language cannot conceal "
                    "association metadata: "
                    f"{cohort}[{index}] inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "intergenerational_language", None)
    if type(runtime) is not IntergenerationalLanguageRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_intergenerational_runtime",
            "disabled intergenerational language requires an explicit runtime",
        )
    if not intergenerational_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_intergenerational_runtime",
            "disabled intergenerational language requires pristine runtime state",
        )


def _require_pristine_disabled_coevolution_state(state) -> None:
    """Reject intelligibility feedback while language coevolution is off.

    Intelligibility is directed relationship state rather than language state,
    so this scans every directed tie across the living and retained-dead
    cohorts. A nonzero value would silently shift partner choice through
    ``relationship_preference_score`` while being absent from the payload.
    """
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            relationships = getattr(inhabitant, "relationships", None)
            if relationships is None:
                continue
            for target_id, record in relationships.items():
                if getattr(record, "intelligibility", 0.0) != 0.0:
                    inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                    raise LanguageInvariantError(
                        "nonpristine_disabled_language_coevolution_state",
                        "disabled language coevolution cannot conceal "
                        f"intelligibility: {cohort}[{index}] "
                        f"inhabitant_id={inhabitant_id!r} "
                        f"target_id={target_id!r}",
                    )
    runtime = getattr(state, "language_coevolution", None)
    if type(runtime) is not LanguageCoevolutionRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_language_coevolution_runtime",
            "disabled language coevolution requires an explicit runtime",
        )
    if not language_coevolution_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_language_coevolution_runtime",
            "disabled language coevolution requires pristine runtime state",
        )


def _require_pristine_disabled_grammar_state(state) -> None:
    """Reject constituent-order rule state while grammar evolution is off.

    Order is speaker-level rule state rather than association metadata, so this
    checks the per-agent fields across the living and retained-dead cohorts.
    """
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled grammar evolution requires explicit agent "
                    f"language state: {cohort}[{index}]",
                )
            if (
                language.constituent_order is not None
                or language.opposing_order_evidence != 0
            ):
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_grammar_evolution_state",
                    "disabled grammar evolution cannot conceal constituent "
                    f"order state: {cohort}[{index}] "
                    f"inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "grammar_evolution", None)
    if type(runtime) is not GrammarEvolutionRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_grammar_evolution_runtime",
            "disabled grammar evolution requires an explicit runtime",
        )
    if not grammar_evolution_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_grammar_evolution_runtime",
            "disabled grammar evolution requires pristine runtime state",
        )


def _require_pristine_disabled_compositional_state(state) -> None:
    """Reject composed meanings omitted from the disabled behavioral payload.

    A disabled feature must be provably absent, not merely unused. Composite
    meanings are structural rather than attached metadata, so this scans every
    production and comprehension key across the living and retained-dead
    cohorts and fails closed on any hidden composed state.
    """
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled compositional protolanguage requires explicit "
                    f"agent language state: {cohort}[{index}]",
                )
            hidden = [
                association
                for store in (
                    language.production,
                    language.comprehension,
                )
                for association in store.values()
                if type(getattr(association, "meaning", None))
                is CompositeMeaning
            ]
            hidden_keys = [
                key
                for store in (language.production, language.comprehension)
                for key in store
                if type(key) is tuple
                and any(type(part) is CompositeMeaning for part in key)
            ]
            if hidden or hidden_keys:
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_compositional_protolanguage_meaning",
                    "disabled compositional protolanguage cannot conceal "
                    f"composed meanings: {cohort}[{index}] "
                    f"inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "compositional_protolanguage", None)
    if type(runtime) is not CompositionalProtolanguageRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_compositional_protolanguage_runtime",
            "disabled compositional protolanguage requires an explicit "
            "runtime",
        )
    if not compositional_protolanguage_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_compositional_protolanguage_runtime",
            "disabled compositional protolanguage requires pristine runtime "
            "state",
        )


def _require_pristine_disabled_lexical_state(state) -> None:
    """Reject lexical state omitted from the disabled behavioral payload."""
    for cohort, inhabitants in (
        ("living", state.people),
        ("dead", state.all_dead),
    ):
        for index, inhabitant in enumerate(inhabitants):
            language = getattr(inhabitant, "language", None)
            if type(language) is not AgentLanguageState:
                raise LanguageInvariantError(
                    "missing_disabled_agent_language_state",
                    "disabled lexical evolution requires explicit agent "
                    f"language state: {cohort}[{index}]",
                )
            hidden = [
                association
                for store in (
                    language.production,
                    language.comprehension,
                )
                for association in store.values()
                if getattr(
                    association, "lexical_evolution_provenance", None
                ) is not None
            ]
            if hidden:
                inhabitant_id = getattr(inhabitant, "inhabitant_id", None)
                raise LanguageInvariantError(
                    "nonpristine_disabled_lexical_evolution_metadata",
                    "disabled lexical evolution cannot conceal association "
                    f"metadata: {cohort}[{index}] "
                    f"inhabitant_id={inhabitant_id!r}",
                )
    runtime = getattr(state, "lexical_evolution", None)
    if type(runtime) is not LexicalEvolutionRuntimeState:
        raise LanguageInvariantError(
            "missing_disabled_lexical_evolution_runtime",
            "disabled lexical evolution requires an explicit runtime",
        )
    if not lexical_evolution_runtime_is_pristine(runtime):
        raise LanguageInvariantError(
            "nonpristine_disabled_lexical_evolution_runtime",
            "disabled lexical evolution requires pristine runtime state",
        )


def _coalition_state_record(runtime: CoalitionRuntimeState) -> dict:
    """Return the complete coalition runtime in canonical JSON-safe form."""
    return {
        "candidates": canonical_candidate_snapshot(runtime),
        "active_coalitions": canonical_coalition_snapshot(runtime),
        "member_to_coalition": [
            {"inhabitant_id": inhabitant_id, "coalition_id": coalition_id}
            for inhabitant_id, coalition_id in sorted(
                runtime.member_to_coalition.items())
        ],
        "next_coalition_id": runtime.next_coalition_id,
        "candidate_formation_count": runtime.candidate_formation_count,
        "split_event_count": runtime.split_event_count,
        "split_child_count": runtime.split_child_count,
        "dissolution_count": runtime.dissolution_count,
        "last_observation_tick": runtime.last_observation_tick,
        "last_active_inhabitant_ids": list(runtime.last_active_inhabitant_ids),
        "last_qualifying_reciprocal_edge_count": (
            runtime.last_qualifying_reciprocal_edge_count
        ),
    }


def _language_hash_config(configuration: dict) -> LanguageEvolutionConfig:
    """Build the exact effective language controls required by state records."""
    required = (
        "language_evolution_enabled",
        "maximum_language_associations",
        "maximum_signal_length",
        "language_learning_rate",
        "language_reinforcement_rate",
        "language_forgetting_interval",
        "language_invention_enabled",
        "language_controls_status",
        "language_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled language hashing lacks controls: " + ", ".join(missing))
    # Enabled base language is either contracted (approved values) or
    # engineering-only (any other value). Both are hashable; only the
    # readiness gate distinguishes them.
    if configuration["language_controls_status"] not in (
        "contracted", "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled language hashing requires contracted or engineering-only "
            "status")
    if (
        type(configuration["language_control_notices"]) is not list
        or configuration["language_control_notices"]
    ):
        raise ValueError(
            "enabled language hashing requires exact empty language notices")
    result = LanguageEvolutionConfig(
        language_evolution_enabled=configuration["language_evolution_enabled"],
        maximum_language_associations=configuration[
            "maximum_language_associations"],
        maximum_signal_length=configuration["maximum_signal_length"],
        language_learning_rate=configuration["language_learning_rate"],
        language_reinforcement_rate=configuration[
            "language_reinforcement_rate"],
        language_forgetting_interval=configuration[
            "language_forgetting_interval"],
        language_invention_enabled=configuration[
            "language_invention_enabled"],
    )
    validate_language_config(result, require_enabled=True)
    return result


def _dialect_hash_config(configuration: dict) -> CoalitionDialectConfig:
    """Build exact enabled dialect controls for behavioral hashing."""
    required = (
        "coalition_dialect_influence_enabled",
        "same_coalition_learning_multiplier",
        "same_coalition_reinforcement_multiplier",
        "dialect_controls_status",
        "dialect_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled dialect hashing lacks controls: " + ", ".join(missing))
    if configuration["dialect_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled dialect hashing requires engineering-only status")
    if (
        type(configuration["dialect_control_notices"]) is not list
        or configuration["dialect_control_notices"]
    ):
        raise ValueError(
            "enabled dialect hashing requires exact empty notices")
    result = CoalitionDialectConfig(
        coalition_dialect_influence_enabled=configuration[
            "coalition_dialect_influence_enabled"],
        same_coalition_learning_multiplier=configuration[
            "same_coalition_learning_multiplier"],
        same_coalition_reinforcement_multiplier=configuration[
            "same_coalition_reinforcement_multiplier"],
    )
    validate_coalition_dialect_config(result)
    if not result.coalition_dialect_influence_enabled:
        raise ValueError("enabled dialect hashing requires effective influence")
    return result


def _contact_hash_config(configuration: dict) -> LanguageContactConfig:
    """Build exact enabled contact controls for behavioral hashing."""
    required = (
        "language_contact_enabled",
        "cross_group_learning_multiplier",
        "borrowing_exposure_threshold",
        "borrowing_confidence_threshold",
        "language_contact_controls_status",
        "language_contact_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled language contact hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["language_contact_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled language contact hashing requires engineering-only status"
        )
    if (
        type(configuration["language_contact_control_notices"]) is not list
        or configuration["language_contact_control_notices"]
    ):
        raise ValueError(
            "enabled language contact hashing requires exact empty notices"
        )
    result = LanguageContactConfig(
        language_contact_enabled=configuration["language_contact_enabled"],
        cross_group_learning_multiplier=configuration[
            "cross_group_learning_multiplier"
        ],
        borrowing_exposure_threshold=configuration[
            "borrowing_exposure_threshold"
        ],
        borrowing_confidence_threshold=configuration[
            "borrowing_confidence_threshold"
        ],
    )
    validate_language_contact_config(result)
    if not result.language_contact_enabled:
        raise ValueError("enabled contact hashing requires effective contact")
    return result


def _intergenerational_hash_config(
    configuration: dict,
) -> IntergenerationalLanguageConfig:
    """Build exact enabled transmission controls for behavioral hashing."""
    required = (
        "intergenerational_language_enabled",
        "maximum_parental_meanings_per_parent",
        "intergenerational_learning_strength",
        "intergenerational_language_controls_status",
        "intergenerational_language_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled intergenerational language hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["intergenerational_language_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled intergenerational language hashing requires "
            "engineering-only status"
        )
    if (
        type(configuration["intergenerational_language_control_notices"])
        is not list
        or configuration["intergenerational_language_control_notices"]
    ):
        raise ValueError(
            "enabled intergenerational language hashing requires exact empty "
            "notices"
        )
    result = IntergenerationalLanguageConfig(
        intergenerational_language_enabled=configuration[
            "intergenerational_language_enabled"
        ],
        maximum_parental_meanings_per_parent=configuration[
            "maximum_parental_meanings_per_parent"
        ],
        intergenerational_learning_strength=configuration[
            "intergenerational_learning_strength"
        ],
    )
    validate_intergenerational_language_config(result, require_enabled=True)
    return result


def _compositional_hash_config(
    configuration: dict,
) -> CompositionalProtolanguageConfig:
    """Build exact enabled composition controls for behavioral hashing."""
    required = (
        "compositional_protolanguage_enabled",
        "maximum_resource_morpheme_length",
        "modality_morpheme_length",
        "compositional_protolanguage_controls_status",
        "compositional_protolanguage_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled compositional protolanguage hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["compositional_protolanguage_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled compositional protolanguage hashing requires "
            "engineering-only status"
        )
    if (
        type(configuration["compositional_protolanguage_control_notices"])
        is not list
        or configuration["compositional_protolanguage_control_notices"]
    ):
        raise ValueError(
            "enabled compositional protolanguage hashing requires exact "
            "empty notices"
        )
    return CompositionalProtolanguageConfig(
        compositional_protolanguage_enabled=configuration[
            "compositional_protolanguage_enabled"],
        maximum_resource_morpheme_length=configuration[
            "maximum_resource_morpheme_length"],
        modality_morpheme_length=configuration[
            "modality_morpheme_length"],
    )


def _coevolution_hash_config(
    configuration: dict,
) -> LanguageCoevolutionConfig:
    """Build exact enabled coevolution controls for behavioral hashing."""
    required = (
        "language_coevolution_enabled",
        "intelligibility_reward",
        "intelligibility_penalty",
        "language_coevolution_controls_status",
        "language_coevolution_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled language coevolution hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["language_coevolution_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled language coevolution hashing requires engineering-only "
            "status"
        )
    if (
        type(configuration["language_coevolution_control_notices"])
        is not list
        or configuration["language_coevolution_control_notices"]
    ):
        raise ValueError(
            "enabled language coevolution hashing requires exact empty "
            "notices"
        )
    return LanguageCoevolutionConfig(
        language_coevolution_enabled=configuration[
            "language_coevolution_enabled"],
        intelligibility_reward=configuration["intelligibility_reward"],
        intelligibility_penalty=configuration["intelligibility_penalty"],
    )


def _grammar_hash_config(configuration: dict) -> GrammarEvolutionConfig:
    """Build exact enabled grammar controls for behavioral hashing."""
    required = (
        "grammar_evolution_enabled",
        "order_adoption_threshold",
        "grammar_evolution_controls_status",
        "grammar_evolution_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled grammar evolution hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["grammar_evolution_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled grammar evolution hashing requires engineering-only "
            "status"
        )
    if (
        type(configuration["grammar_evolution_control_notices"]) is not list
        or configuration["grammar_evolution_control_notices"]
    ):
        raise ValueError(
            "enabled grammar evolution hashing requires exact empty notices"
        )
    return GrammarEvolutionConfig(
        grammar_evolution_enabled=configuration["grammar_evolution_enabled"],
        order_adoption_threshold=configuration["order_adoption_threshold"],
    )


def _lexical_hash_config(configuration: dict) -> LexicalEvolutionConfig:
    """Build exact enabled lexical controls for behavioral hashing."""
    required = (
        "lexical_evolution_enabled",
        "lexical_mutation_rate",
        "maximum_lexical_lineage_depth",
        "lexical_evolution_controls_status",
        "lexical_evolution_control_notices",
    )
    missing = [name for name in required if name not in configuration]
    if missing:
        raise ValueError(
            "enabled lexical evolution hashing lacks controls: "
            + ", ".join(missing)
        )
    if configuration["lexical_evolution_controls_status"] != (
        "engineering_only_uncontracted"
    ):
        raise ValueError(
            "enabled lexical evolution hashing requires engineering-only status"
        )
    if (
        type(configuration["lexical_evolution_control_notices"]) is not list
        or configuration["lexical_evolution_control_notices"]
    ):
        raise ValueError(
            "enabled lexical evolution hashing requires exact empty notices"
        )
    result = LexicalEvolutionConfig(
        lexical_evolution_enabled=configuration[
            "lexical_evolution_enabled"],
        lexical_mutation_rate=configuration["lexical_mutation_rate"],
        maximum_lexical_lineage_depth=configuration[
            "maximum_lexical_lineage_depth"],
    )
    validate_lexical_evolution_config(result, require_enabled=True)
    return result


def canonical_state_hash(state, world: list, configuration: dict) -> str:
    """Return a SHA-256 fingerprint of behaviorally relevant final state."""
    social_memory_enabled = configuration.get("social_memory_enabled") is True
    coalition_emergence_enabled = (
        configuration.get("coalition_emergence_enabled") is True
    )
    if (
        "language_evolution_enabled" in configuration
        and type(configuration["language_evolution_enabled"]) is not bool
    ):
        raise ValueError("language evolution configuration must be boolean")
    language_evolution_enabled = configuration.get(
        "language_evolution_enabled", False)
    if (
        "coalition_dialect_influence_enabled" in configuration
        and type(configuration["coalition_dialect_influence_enabled"]) is not bool
    ):
        raise ValueError("coalition dialect influence must be boolean")
    dialect_influence_enabled = configuration.get(
        "coalition_dialect_influence_enabled", False)
    if (
        "language_contact_enabled" in configuration
        and type(configuration["language_contact_enabled"]) is not bool
    ):
        raise ValueError("language contact setting must be boolean")
    language_contact_enabled = configuration.get(
        "language_contact_enabled", False)
    if (
        "intergenerational_language_enabled" in configuration
        and type(configuration["intergenerational_language_enabled"]) is not bool
    ):
        raise ValueError("intergenerational language setting must be boolean")
    intergenerational_language_enabled = configuration.get(
        "intergenerational_language_enabled", False)
    if (
        "lexical_evolution_enabled" in configuration
        and type(configuration["lexical_evolution_enabled"]) is not bool
    ):
        raise ValueError("lexical evolution setting must be boolean")
    lexical_evolution_enabled = configuration.get(
        "lexical_evolution_enabled", False)
    if (
        "compositional_protolanguage_enabled" in configuration
        and type(configuration["compositional_protolanguage_enabled"])
        is not bool
    ):
        raise ValueError(
            "compositional protolanguage setting must be boolean")
    compositional_protolanguage_enabled = configuration.get(
        "compositional_protolanguage_enabled", False)
    if (
        "grammar_evolution_enabled" in configuration
        and type(configuration["grammar_evolution_enabled"]) is not bool
    ):
        raise ValueError("grammar evolution setting must be boolean")
    grammar_evolution_enabled = configuration.get(
        "grammar_evolution_enabled", False)
    if (
        "language_coevolution_enabled" in configuration
        and type(configuration["language_coevolution_enabled"]) is not bool
    ):
        raise ValueError("language coevolution setting must be boolean")
    language_coevolution_enabled = configuration.get(
        "language_coevolution_enabled", False)
    social_partner_bias_enabled = configuration.get(
        "social_partner_bias_enabled") is True
    non_behavioral_keys = {
        "condition",
        "log_mode",
        "social_controls_status",
        "social_control_notices",
    }
    if not social_memory_enabled:
        _require_empty_disabled_relationships(state)
        # The disabled feature is a direct historical baseline. Run IDs,
        # allocator state, and all social controls/state are intentionally
        # absent from the behavioral payload so frozen hashes stay unchanged.
        non_behavioral_keys.update({
            "social_memory_enabled",
            "social_partner_bias_enabled",
            "maximum_social_ties",
            "relationship_decay_interval",
        })
    language_configuration_keys = {
        "language_evolution_enabled",
        "maximum_language_associations",
        "maximum_signal_length",
        "language_learning_rate",
        "language_reinforcement_rate",
        "language_forgetting_interval",
        "language_invention_enabled",
        "language_controls_status",
        "language_control_notices",
    }
    if not language_evolution_enabled:
        _require_pristine_disabled_language_state(state)
        non_behavioral_keys.update(language_configuration_keys)
    coalition_configuration_keys = {
        "coalition_emergence_enabled",
        "coalition_minimum_size",
        "coalition_trust_threshold",
        "coalition_familiarity_threshold",
        "coalition_maximum_grievance",
        "coalition_persistence_ticks",
        "maximum_active_coalitions",
        "coalition_controls_status",
        "coalition_control_notices",
    }
    dialect_configuration_keys = {
        "coalition_dialect_influence_enabled",
        "same_coalition_learning_multiplier",
        "same_coalition_reinforcement_multiplier",
        "dialect_controls_status",
        "dialect_control_notices",
    }
    contact_configuration_keys = {
        "language_contact_enabled",
        "cross_group_learning_multiplier",
        "borrowing_exposure_threshold",
        "borrowing_confidence_threshold",
        "language_contact_controls_status",
        "language_contact_control_notices",
    }
    intergenerational_configuration_keys = {
        "intergenerational_language_enabled",
        "maximum_parental_meanings_per_parent",
        "intergenerational_learning_strength",
        "intergenerational_language_controls_status",
        "intergenerational_language_control_notices",
    }
    lexical_configuration_keys = {
        "lexical_evolution_enabled",
        "lexical_mutation_rate",
        "maximum_lexical_lineage_depth",
        "lexical_evolution_controls_status",
        "lexical_evolution_control_notices",
    }
    grammar_configuration_keys = {
        "grammar_evolution_enabled",
        "order_adoption_threshold",
        "grammar_evolution_controls_status",
        "grammar_evolution_control_notices",
    }
    coevolution_configuration_keys = {
        "language_coevolution_enabled",
        "intelligibility_reward",
        "intelligibility_penalty",
        "language_coevolution_controls_status",
        "language_coevolution_control_notices",
    }
    compositional_configuration_keys = {
        "compositional_protolanguage_enabled",
        "maximum_resource_morpheme_length",
        "modality_morpheme_length",
        "compositional_protolanguage_controls_status",
        "compositional_protolanguage_control_notices",
    }
    if not dialect_influence_enabled:
        _require_pristine_disabled_dialect_state(state)
        non_behavioral_keys.update(dialect_configuration_keys)
    elif not language_evolution_enabled or not coalition_emergence_enabled:
        raise ValueError(
            "enabled coalition dialect influence requires language and coalitions")
    if not language_contact_enabled:
        _require_pristine_disabled_contact_state(state)
        non_behavioral_keys.update(contact_configuration_keys)
    elif not language_evolution_enabled or not coalition_emergence_enabled:
        raise ValueError(
            "enabled language contact requires language and coalitions")
    if not intergenerational_language_enabled:
        _require_pristine_disabled_intergenerational_state(state)
        non_behavioral_keys.update(intergenerational_configuration_keys)
    elif not language_evolution_enabled:
        raise ValueError(
            "enabled intergenerational language requires language evolution")
    if not lexical_evolution_enabled:
        _require_pristine_disabled_lexical_state(state)
        non_behavioral_keys.update(lexical_configuration_keys)
    elif not language_evolution_enabled:
        raise ValueError(
            "enabled lexical evolution requires language evolution")
    if not compositional_protolanguage_enabled:
        _require_pristine_disabled_compositional_state(state)
        non_behavioral_keys.update(compositional_configuration_keys)
    elif not language_evolution_enabled:
        raise ValueError(
            "enabled compositional protolanguage requires language evolution")
    if not language_coevolution_enabled:
        _require_pristine_disabled_coevolution_state(state)
        non_behavioral_keys.update(coevolution_configuration_keys)
    elif not language_evolution_enabled:
        raise ValueError(
            "enabled language coevolution requires language evolution")
    elif not social_partner_bias_enabled:
        raise ValueError(
            "enabled language coevolution requires social partner bias")
    if not grammar_evolution_enabled:
        _require_pristine_disabled_grammar_state(state)
        non_behavioral_keys.update(grammar_configuration_keys)
    elif not language_evolution_enabled:
        raise ValueError(
            "enabled grammar evolution requires language evolution")
    elif not compositional_protolanguage_enabled:
        raise ValueError(
            "enabled grammar evolution requires compositional protolanguage")
    if not coalition_emergence_enabled:
        _require_empty_disabled_coalition_state(state)
        non_behavioral_keys.update(coalition_configuration_keys)
    elif not social_memory_enabled:
        raise ValueError("enabled coalition emergence requires social memory")
    behavior_configuration = {
        key: value
        for key, value in configuration.items()
        if key not in non_behavioral_keys
    }
    language_hash_config = (
        _language_hash_config(configuration)
        if language_evolution_enabled else None
    )
    if dialect_influence_enabled:
        _dialect_hash_config(configuration)
    contact_hash_config = (
        _contact_hash_config(configuration)
        if language_contact_enabled else None
    )
    intergenerational_hash_config = (
        _intergenerational_hash_config(configuration)
        if intergenerational_language_enabled else None
    )
    lexical_hash_config = (
        _lexical_hash_config(configuration)
        if lexical_evolution_enabled else None
    )
    compositional_hash_config = (
        _compositional_hash_config(configuration)
        if compositional_protolanguage_enabled else None
    )
    grammar_hash_config = (
        _grammar_hash_config(configuration)
        if grammar_evolution_enabled else None
    )
    coevolution_hash_config = (
        _coevolution_hash_config(configuration)
        if language_coevolution_enabled else None
    )
    coevolution_runtime = None
    if language_coevolution_enabled:
        coevolution_runtime = getattr(state, "language_coevolution", None)
        if type(coevolution_runtime) is not LanguageCoevolutionRuntimeState:
            raise ValueError(
                "enabled language coevolution requires a valid runtime")
    compositional_runtime = None
    if compositional_protolanguage_enabled:
        compositional_runtime = getattr(
            state, "compositional_protolanguage", None)
        if type(compositional_runtime) is not (
            CompositionalProtolanguageRuntimeState
        ):
            raise ValueError(
                "enabled compositional protolanguage requires a valid runtime")
    grammar_runtime = None
    if grammar_evolution_enabled:
        grammar_runtime = getattr(state, "grammar_evolution", None)
        if type(grammar_runtime) is not GrammarEvolutionRuntimeState:
            raise ValueError(
                "enabled grammar evolution requires a valid runtime")
    intergenerational_runtime = None
    if intergenerational_language_enabled:
        intergenerational_runtime = getattr(
            state, "intergenerational_language", None)
        if type(intergenerational_runtime) is not (
            IntergenerationalLanguageRuntimeState
        ):
            raise ValueError(
                "enabled intergenerational language requires a valid runtime")
        validate_intergenerational_language_runtime(
            intergenerational_runtime,
            config=intergenerational_hash_config,
            language_runtime=state.language,
        )
    lexical_runtime = None
    if lexical_evolution_enabled:
        lexical_runtime = getattr(state, "lexical_evolution", None)
        if type(lexical_runtime) is not LexicalEvolutionRuntimeState:
            raise ValueError(
                "enabled lexical evolution requires a valid runtime")
        validate_lexical_evolution_runtime(
            lexical_runtime,
            config=lexical_hash_config,
            language_runtime=state.language,
        )
    if language_evolution_enabled:
        validate_intergenerational_parent_references(
            state.people,
            state.all_dead,
            language_config=language_hash_config,
            contact_config=contact_hash_config,
            intergenerational_enabled=intergenerational_language_enabled,
            intergenerational_runtime=intergenerational_runtime,
            lexical_config=lexical_hash_config,
            lexical_runtime=lexical_runtime,
        )
    people_records = [
        _person_record(
            person,
            include_social=social_memory_enabled,
            include_language=language_evolution_enabled,
            include_contact=language_contact_enabled,
            include_intergenerational=intergenerational_language_enabled,
            include_lexical_evolution=lexical_evolution_enabled,
            include_grammar_evolution=grammar_evolution_enabled,
            include_language_coevolution=language_coevolution_enabled,
            language_config=language_hash_config,
            contact_config=contact_hash_config,
            lexical_config=lexical_hash_config,
        )
        for person in state.people
    ]
    dead_records = [
        _person_record(
            person,
            include_social=social_memory_enabled,
            include_language=language_evolution_enabled,
            include_contact=language_contact_enabled,
            include_intergenerational=intergenerational_language_enabled,
            include_lexical_evolution=lexical_evolution_enabled,
            include_grammar_evolution=grammar_evolution_enabled,
            include_language_coevolution=language_coevolution_enabled,
            language_config=language_hash_config,
            contact_config=contact_hash_config,
            lexical_config=lexical_hash_config,
        )
        for person in state.all_dead
    ]
    identity_enabled = social_memory_enabled or language_evolution_enabled
    if language_evolution_enabled:
        identities = [
            record["inhabitant_id"]
            for record in (*people_records, *dead_records)
        ]
        if len(identities) != len(set(identities)):
            raise LanguageInvariantError(
                "duplicate_language_identity",
                "enabled language hashing requires unique inhabitant IDs",
            )
    person_sort_key = (
        (lambda record: record["inhabitant_id"])
        if identity_enabled
        else (lambda record: record["name"])
    )
    payload = {
        "configuration": behavior_configuration,
        "people": sorted(people_records, key=person_sort_key),
        "dead": sorted(dead_records, key=person_sort_key),
        "factions": sorted((_faction_record(f) for f in state.factions),
                           key=lambda record: record["name"]),
        "active_wars": sorted((_war_record(w) for w in state.active_wars),
                              key=lambda record: (record["started_tick"],
                                                  record["attacker"],
                                                  record["defender"])),
        "war_history": sorted((_war_record(w) for w in state.war_history),
                              key=lambda record: (record["started_tick"],
                                                  record["attacker"],
                                                  record["defender"])),
        "rivalries": _mapping_records(state.rivalries),
        "treaties": _mapping_records(state.treaties),
        "reputation": state.reputation,
        "trade_routes": _mapping_records(state.trade_routes),
        "world": [
            [
                {
                    "biome": tile["biome"],
                    "habitable": tile["habitable"],
                    "resources": tile["resources"],
                }
                for tile in row
            ]
            for row in world
        ],
    }
    if identity_enabled:
        next_inhabitant_id = getattr(state, "next_inhabitant_id", None)
        if type(next_inhabitant_id) is not int or next_inhabitant_id < 0:
            raise ValueError(
                "enabled social state requires a nonnegative ID allocator")
        payload["next_inhabitant_id"] = next_inhabitant_id
    if language_evolution_enabled:
        runtime = getattr(state, "language", None)
        if type(runtime) is not LanguageRuntimeState:
            raise ValueError("enabled language state requires a valid runtime")
        if runtime.coalition_dialect_influence_enabled is not (
            dialect_influence_enabled
        ):
            raise LanguageInvariantError(
                "dialect_runtime_gate_mismatch",
                "language runtime dialect gate disagrees with effective controls",
            )
        if runtime.language_contact_enabled is not language_contact_enabled:
            raise LanguageInvariantError(
                "contact_runtime_gate_mismatch",
                "language runtime contact gate disagrees with effective controls",
            )
        if runtime.intergenerational_language_enabled is not (
            intergenerational_language_enabled
        ):
            raise LanguageInvariantError(
                "intergenerational_runtime_gate_mismatch",
                "language runtime intergenerational gate disagrees with "
                "effective controls",
            )
        if runtime.lexical_evolution_enabled is not lexical_evolution_enabled:
            raise LanguageInvariantError(
                "lexical_evolution_runtime_gate_mismatch",
                "language runtime lexical gate disagrees with effective "
                "controls",
            )
        if runtime.grammar_evolution_enabled is not grammar_evolution_enabled:
            raise LanguageInvariantError(
                "grammar_evolution_runtime_gate_mismatch",
                "language runtime grammar gate disagrees with effective "
                "controls",
            )
        if runtime.language_coevolution_enabled is not (
            language_coevolution_enabled
        ):
            raise LanguageInvariantError(
                "language_coevolution_runtime_gate_mismatch",
                "language runtime coevolution gate disagrees with effective "
                "controls",
            )
        payload["language_state"] = language_runtime_record(runtime)
    if coalition_emergence_enabled:
        runtime = getattr(state, "coalitions", None)
        if not isinstance(runtime, CoalitionRuntimeState):
            raise ValueError("enabled coalition state requires a valid runtime")
        payload["coalition_state"] = _coalition_state_record(runtime)
    if dialect_influence_enabled:
        dialect_runtime = getattr(state, "dialect", None)
        if type(dialect_runtime) is not CoalitionDialectRuntimeState:
            raise ValueError("enabled dialect state requires a valid runtime")
        payload["coalition_dialect_state"] = coalition_dialect_runtime_record(
            dialect_runtime,
            language_runtime=state.language,
        )
    if language_contact_enabled:
        contact_runtime = getattr(state, "language_contact", None)
        if type(contact_runtime) is not LanguageContactRuntimeState:
            raise ValueError("enabled contact state requires a valid runtime")
        validate_language_contact_runtime(
            contact_runtime,
            config=contact_hash_config,
            language_runtime=state.language,
            dialect_runtime=(state.dialect if dialect_influence_enabled else None),
        )
        payload["language_contact_state"] = language_contact_runtime_record(
            contact_runtime,
            language_runtime=state.language,
            dialect_runtime=(state.dialect if dialect_influence_enabled else None),
        )
    if intergenerational_language_enabled:
        assert intergenerational_runtime is not None
        payload["intergenerational_language_state"] = (
            intergenerational_language_runtime_record(
                intergenerational_runtime,
                config=intergenerational_hash_config,
                language_runtime=state.language,
            )
        )
    if lexical_evolution_enabled:
        assert lexical_runtime is not None
        payload["lexical_evolution_state"] = lexical_evolution_runtime_record(
            lexical_runtime,
            config=lexical_hash_config,
            language_runtime=state.language,
        )
    if compositional_protolanguage_enabled:
        assert compositional_runtime is not None
        payload["compositional_protolanguage_state"] = (
            compositional_protolanguage_runtime_record(
                compositional_runtime,
                config=compositional_hash_config,
                language_runtime=state.language,
            )
        )
    if grammar_evolution_enabled:
        assert grammar_runtime is not None
        payload["grammar_evolution_state"] = grammar_evolution_runtime_record(
            grammar_runtime,
            config=grammar_hash_config,
            language_runtime=state.language,
        )
    if language_coevolution_enabled:
        assert coevolution_runtime is not None
        payload["language_coevolution_state"] = (
            language_coevolution_runtime_record(
                coevolution_runtime,
                config=coevolution_hash_config,
                language_runtime=state.language,
            )
        )
    encoded = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _code_revision() -> dict:
    project_root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip())
        return {"commit": revision, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def _artifact_inventory_entry(
    path: Path,
    schema_version: int,
    *,
    data_root: Path,
) -> dict:
    """Return a streaming checksum and CSV row count for one sealed artifact."""
    path = require_contained_regular_file(path, data_root)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, strict=True)
        next(reader)
        data_rows = sum(1 for _row in reader)

    return {
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "data_rows": data_rows,
        "schema_version": schema_version,
    }


def build_artifact_inventory(
    output_dir: str,
    *,
    seed: int,
    condition: str,
) -> tuple[dict[str, dict], list[str]]:
    """Inventory only required structured artifacts, preserving any errors."""
    root = lexical_absolute(Path(output_dir))
    try:
        root = require_real_directory(root)
    except EvidencePathError as exc:
        return {}, [f"data_root: EvidencePathError: {exc}"]
    artifacts = {
        "metrics": (
            root / f"metrics_{condition}_seed_{seed}.csv",
            METRICS_SCHEMA_VERSION,
        ),
        "events": (
            root / f"faction_events_{condition}_seed_{seed}.csv",
            EVENT_SCHEMA_VERSION,
        ),
        "beliefs": (
            root / f"beliefs_{condition}_seed_{seed}.csv",
            BELIEFS_SCHEMA_VERSION,
        ),
        "summary": (root / "run_summaries.csv", RUN_SUMMARY_SCHEMA_VERSION),
    }
    inventory: dict[str, dict] = {}
    errors: list[str] = []
    for label, (path, schema_version) in artifacts.items():
        try:
            inventory[label] = _artifact_inventory_entry(
                path, schema_version, data_root=root)
        except (
            OSError, UnicodeError, csv.Error, StopIteration, EvidencePathError,
        ) as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    return inventory, errors


def language_endpoint_record(
    language_runtime,
    *,
    final_tick: int,
) -> dict:
    """Return the contracted primary endpoint for one run.

    Language Research Readiness v1 contracts one endpoint: comprehension
    success rate, the share of committed-transfer utterances the receiver
    interpreted correctly, measured at the run's final tick.

    The rate is ``None`` rather than ``0.0`` when no utterance occurred. A
    control arm with language disabled attempts no communication, so its rate
    is genuinely undefined; reporting zero would assert a measured failure
    that never happened.

    This records the endpoint. It defines no estimand, contrast, estimator,
    uncertainty method, or multiplicity rule; those remain unspecified and are
    a separate authorization gate.
    """
    if type(final_tick) is not int or final_tick < 0:
        raise ValueError("endpoint final tick must be a nonnegative integer")
    attempts = getattr(language_runtime, "communication_attempt_count", 0)
    successes = getattr(
        language_runtime, "successful_interpretation_count", 0)
    if type(attempts) is not int or type(successes) is not int:
        raise ValueError("endpoint counters must be exact integers")
    if attempts < 0 or successes < 0 or successes > attempts:
        raise ValueError("endpoint counters violate their partition")
    rate = None if attempts == 0 else round(successes / attempts, 12)
    return {
        "name": "comprehension_success_rate",
        "definition": (
            "successful_interpretation_count / communication_attempt_count"
        ),
        "communication_attempt_count": attempts,
        "successful_interpretation_count": successes,
        "comprehension_success_rate": rate,
        "measured_at_tick": final_tick,
        "analysis_contract": "unspecified",
    }


def write_run_manifest(
    output_dir: str,
    *,
    seed: int,
    condition: str,
    configuration: dict,
    state_hash: str,
    language_endpoint: dict | None = None,
    execution_mode: str,
    requested_ticks: int,
    final_tick: int,
    termination_reason: str,
    result_status: str,
    completed_normally: bool,
    writer_health: dict,
    artifact_policy: dict | None = None,
    finalization_diagnostics: list[str] | None = None,
    log_mode: str = "full",
    required_outputs: list[str] | None = None,
    optional_outputs: dict | None = None,
) -> Path:
    """Write machine-readable provenance for one simulation run."""
    root = lexical_absolute(Path(output_dir))
    if root.exists() or root.is_symlink():
        root = require_real_directory(root)
    else:
        require_real_directory(root.parent)
        root.mkdir()
        root = require_real_directory(root)
    path = require_safe_manifest_target(
        root / f"run_manifest_{condition}_seed_{seed}.json",
        root,
    )
    inventory, inventory_errors = build_artifact_inventory(
        output_dir, seed=seed, condition=condition)
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "artifact_schema_versions": {
            "metrics": METRICS_SCHEMA_VERSION,
            "events": EVENT_SCHEMA_VERSION,
            "beliefs": BELIEFS_SCHEMA_VERSION,
            "summary": RUN_SUMMARY_SCHEMA_VERSION,
        },
        "metrics_timing_contract": METRICS_TIMING_CONTRACT,
        "seed": seed,
        "condition": condition,
        "requested_ticks": requested_ticks,
        "final_tick": final_tick,
        "completed_ticks": final_tick,
        "termination_reason": termination_reason,
        "result_status": result_status,
        "completed_normally": completed_normally,
        "configuration": configuration,
        "execution_mode": execution_mode,
        "log_mode": log_mode,
        "required_outputs": required_outputs or [
            "metrics",
            "events",
            "beliefs",
            "run_summary",
            "run_manifest",
        ],
        "optional_outputs": optional_outputs or {},
        "state_hash_algorithm": "sha256",
        "state_hash": state_hash,
        "language_endpoint": language_endpoint,
        "writer_health": writer_health,
        "artifact_policy": artifact_policy or {
            "allow_zero_events": ALLOW_ZERO_EVENTS,
            "belief_snapshot_interval": BELIEF_SNAPSHOT_INTERVAL,
            "belief_snapshot_cardinality": BELIEF_SNAPSHOT_CARDINALITY,
        },
        "finalization_diagnostics": list(finalization_diagnostics or []),
        "artifact_inventory": inventory,
        "artifact_inventory_errors": inventory_errors,
        "code": _code_revision(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    require_safe_manifest_target(temporary, root)
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path
