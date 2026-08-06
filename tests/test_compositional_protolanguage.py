"""Structured (resource, modality) meanings and systematic morpheme composition."""

from __future__ import annotations

from dataclasses import asdict, replace
import os
import random
import subprocess
import sys
import textwrap

import pytest

import run_experiments
from thalren_vale import economy, language as language_module, world
from thalren_vale.config import (
    COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    CompositionalProtolanguageConfig,
    DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH,
    DEFAULT_MODALITY_MORPHEME_LENGTH,
    LanguageEvolutionConfig,
    SimulationConfig,
    SocialMemoryConfig,
)
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.language import (
    COMPOSITE_MEANING_BY_PARTS,
    COMPOSITE_MEANING_MODALITY,
    COMPOSITE_MEANING_RESOURCE,
    MEANING_ORDER,
    MODALITY_FOR_CONTEXT,
    AgentLanguageState,
    CommunicationContext,
    CommunicationResult,
    CompositeMeaning,
    CompositionalProtolanguageRuntimeState,
    LanguageInvariantError,
    LanguageRuntimeState,
    LexicalAssociation,
    Meaning,
    Modality,
    Signal,
    communicate,
    compositional_protolanguage_runtime_is_pristine,
    compositional_protolanguage_runtime_record,
    compositional_protolanguage_summary,
    derive_composed_signal,
    initialize_compositional_protolanguage_runtime,
    initialize_language_runtime,
    validate_compositional_protolanguage_config,
    validate_compositional_protolanguage_runtime,
)
from thalren_vale.reproducibility import canonical_state_hash
from thalren_vale.state import SimulationState


LANGUAGE = LanguageEvolutionConfig(True, 32, 3, 0.20, 0.10, 25, True)
COMPOSITIONAL = CompositionalProtolanguageConfig(True, 2, 1)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def person(inhabitant_id: int) -> Inhabitant:
    result = Inhabitant(f"P{inhabitant_id}", 0, 0)
    result.inhabitant_id = inhabitant_id
    result.faction = None
    result.language = AgentLanguageState()
    return result


def runtimes(seed: int = 42):
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(
        language_runtime, seed, compositional_protolanguage_enabled=True)
    compositional_runtime = CompositionalProtolanguageRuntimeState()
    initialize_compositional_protolanguage_runtime(
        compositional_runtime, COMPOSITIONAL, seed)
    return language_runtime, compositional_runtime


def speak(sender, receiver, meaning, context, tick, language_runtime,
          compositional_runtime, active_ids=frozenset({7, 9})):
    return communicate(
        sender,
        receiver,
        meaning,
        context=context,
        tick=tick,
        active_ids=active_ids,
        config=LANGUAGE,
        runtime=language_runtime,
        compositional_config=COMPOSITIONAL,
        compositional_runtime=compositional_runtime,
    )


# ── Closed meaning space and canonical ordering ─────────────────────────────

def test_composite_meaning_space_is_closed_and_fixed_arity():
    assert len(Modality) == 2
    assert len(CompositeMeaning) == len(Meaning) * len(Modality) == 8
    for composite in CompositeMeaning:
        resource = COMPOSITE_MEANING_RESOURCE[composite]
        modality = COMPOSITE_MEANING_MODALITY[composite]
        assert COMPOSITE_MEANING_BY_PARTS[(resource, modality)] is composite
        assert composite.name == f"{resource.name}_{modality.name}"


def test_base_meaning_order_indices_are_unchanged_by_composition():
    # Pre-feature canonical orderings and pinned hashes depend on these.
    assert [MEANING_ORDER[meaning] for meaning in Meaning] == [0, 1, 2, 3]
    composite_indices = [MEANING_ORDER[c] for c in CompositeMeaning]
    assert composite_indices == list(range(len(Meaning), len(Meaning) + 8))


def test_modality_is_derived_only_from_committed_transfer_context():
    assert MODALITY_FOR_CONTEXT[
        CommunicationContext.AID_TRANSFER] is Modality.GIFT
    assert MODALITY_FOR_CONTEXT[
        CommunicationContext.PAID_TRADE] is Modality.EXCHANGE
    assert MODALITY_FOR_CONTEXT[
        CommunicationContext.FACTION_TRADE] is Modality.EXCHANGE
    assert set(MODALITY_FOR_CONTEXT) == set(CommunicationContext)


def test_composite_meaning_hash_is_independent_of_process_hash_seed():
    # Member names longer than about twelve characters overflow Py_ssize_t and
    # are truncated by hash(), so formula equality holds only for short names.
    # The property that actually matters is seed independence across the whole
    # closed set, so verify that directly in isolated processes.
    script = (
        "from thalren_vale.language import CompositeMeaning\n"
        "print([hash(member) for member in CompositeMeaning])\n"
    )

    def run(hash_seed: str) -> str:
        environment = dict(
            os.environ,
            PYTHONHASHSEED=hash_seed,
            PYTHONPATH=os.path.join(PROJECT_ROOT, "src"),
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=60, env=environment,
            cwd=PROJECT_ROOT,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    first = run("0")
    assert first
    assert first == run("7") == run("12345")


# ── Configuration ───────────────────────────────────────────────────────────

def test_configuration_defaults_are_exact_and_disabled():
    config = SimulationConfig()
    assert config.compositional_protolanguage_enabled is False
    assert config.maximum_resource_morpheme_length == 2
    assert config.modality_morpheme_length == 1
    assert config.compositional_protolanguage_control_notices == ()
    assert config.compositional_protolanguage_controls_status == "disabled"


def test_request_without_language_normalizes_only_the_gate():
    config = SimulationConfig(compositional_protolanguage_enabled=True)
    assert config.compositional_protolanguage_enabled is False
    assert config.compositional_protolanguage_control_notices == (
        COMPOSITIONAL_PROTOLANGUAGE_NOTICE_WITHOUT_LANGUAGE,
    )
    assert config.compositional_protolanguage_controls_status == (
        "normalized_uncontracted")
    # Submitted numeric controls are preserved, not reset.
    assert config.maximum_resource_morpheme_length == (
        DEFAULT_MAXIMUM_RESOURCE_MORPHEME_LENGTH)
    assert config.modality_morpheme_length == DEFAULT_MODALITY_MORPHEME_LENGTH


def test_enabled_or_nondefault_controls_are_engineering_only():
    enabled = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
    )
    enabled.validate()
    assert enabled.compositional_protolanguage_controls_status == (
        "engineering_only_uncontracted")
    nondefault = SimulationConfig(modality_morpheme_length=2)
    nondefault.validate()
    assert nondefault.compositional_protolanguage_controls_status == (
        "engineering_only_uncontracted")


@pytest.mark.parametrize("overrides", [
    {"maximum_resource_morpheme_length": 0},
    {"maximum_resource_morpheme_length": 4},
    {"maximum_resource_morpheme_length": True},
    {"modality_morpheme_length": 0},
    {"modality_morpheme_length": 3},
    {"modality_morpheme_length": 1.0},
])
def test_invalid_morpheme_controls_are_rejected(overrides):
    config = SimulationConfig(**overrides)
    with pytest.raises(ValueError):
        config.validate()


def test_composed_morphemes_may_not_exceed_effective_signal_length():
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
        maximum_signal_length=2,
    )
    with pytest.raises(ValueError):
        config.validate()


def test_disabled_defaults_tolerate_a_small_maximum_signal_length():
    # A disabled feature must never make an otherwise valid config invalid.
    SimulationConfig(maximum_signal_length=2).validate()


# ── Deterministic systematic composition ────────────────────────────────────

def test_pinned_composed_signal_vectors():
    _language_runtime, compositional_runtime = runtimes()
    observed = {
        composite.name: derive_composed_signal(
            compositional_runtime,
            speaker_id=7,
            composite_meaning=composite,
            config=COMPOSITIONAL,
        ).phoneme_ids
        for composite in CompositeMeaning
    }
    assert observed == {
        "FOOD_GIFT": (3, 3, 1),
        "FOOD_EXCHANGE": (3, 3, 5),
        "WOOD_GIFT": (4, 3, 1),
        "WOOD_EXCHANGE": (4, 3, 5),
        "ORE_GIFT": (7, 1),
        "ORE_EXCHANGE": (7, 5),
        "STONE_GIFT": (3, 6, 1),
        "STONE_EXCHANGE": (3, 6, 5),
    }


def test_morphemes_are_systematic_within_one_speaker():
    _language_runtime, compositional_runtime = runtimes()

    def signal(composite):
        return derive_composed_signal(
            compositional_runtime,
            speaker_id=7,
            composite_meaning=composite,
            config=COMPOSITIONAL,
        ).phoneme_ids

    modality_length = COMPOSITIONAL.modality_morpheme_length
    for resource in Meaning:
        gift = signal(CompositeMeaning[f"{resource.name}_GIFT"])
        exchange = signal(CompositeMeaning[f"{resource.name}_EXCHANGE"])
        assert gift[:-modality_length] == exchange[:-modality_length]
    for modality in Modality:
        suffixes = {
            signal(COMPOSITE_MEANING_BY_PARTS[(resource, modality)])[
                -modality_length:]
            for resource in Meaning
        }
        assert len(suffixes) == 1


def test_speakers_derive_independent_morpheme_inventories():
    _language_runtime, compositional_runtime = runtimes()
    first = derive_composed_signal(
        compositional_runtime, speaker_id=7,
        composite_meaning=CompositeMeaning.FOOD_GIFT, config=COMPOSITIONAL)
    second = derive_composed_signal(
        compositional_runtime, speaker_id=9,
        composite_meaning=CompositeMeaning.FOOD_GIFT, config=COMPOSITIONAL)
    assert first != second


def test_composed_signals_respect_configured_morpheme_bounds():
    _language_runtime, compositional_runtime = runtimes()
    for composite in CompositeMeaning:
        signal = derive_composed_signal(
            compositional_runtime, speaker_id=7,
            composite_meaning=composite, config=COMPOSITIONAL)
        length = len(signal.phoneme_ids)
        assert 1 + COMPOSITIONAL.modality_morpheme_length <= length
        assert length <= (
            COMPOSITIONAL.maximum_resource_morpheme_length
            + COMPOSITIONAL.modality_morpheme_length
        )
        assert all(0 <= token < language_module.PHONEME_COUNT
                   for token in signal.phoneme_ids)


def test_derivation_requires_enabled_controls_and_a_composite_meaning():
    _language_runtime, compositional_runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        derive_composed_signal(
            compositional_runtime, speaker_id=7,
            composite_meaning=Meaning.FOOD, config=COMPOSITIONAL)
    with pytest.raises(LanguageInvariantError):
        derive_composed_signal(
            compositional_runtime, speaker_id=7,
            composite_meaning=CompositeMeaning.FOOD_GIFT,
            config=replace(
                COMPOSITIONAL, compositional_protolanguage_enabled=False),
        )


# ── Authentic grounding and comprehension semantics ─────────────────────────

def test_communication_uses_the_composite_meaning_for_its_context():
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    gift = speak(sender, receiver, Meaning.FOOD,
                 CommunicationContext.AID_TRANSFER, 1,
                 language_runtime, compositional_runtime)
    exchange = speak(sender, receiver, Meaning.FOOD,
                     CommunicationContext.PAID_TRADE, 2,
                     language_runtime, compositional_runtime)
    assert gift.intended_meaning is CompositeMeaning.FOOD_GIFT
    assert exchange.intended_meaning is CompositeMeaning.FOOD_EXCHANGE
    assert gift.produced_signal != exchange.produced_signal
    assert all(type(meaning) is CompositeMeaning
               for meaning, _signal in sender.language.production)


def test_teaching_event_stays_unknown_and_a_repeat_succeeds():
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    first = speak(sender, receiver, Meaning.FOOD,
                  CommunicationContext.AID_TRANSFER, 1,
                  language_runtime, compositional_runtime)
    second = speak(sender, receiver, Meaning.FOOD,
                   CommunicationContext.AID_TRANSFER, 2,
                   language_runtime, compositional_runtime)
    assert first.result is CommunicationResult.UNKNOWN_SIGNAL
    assert second.result is CommunicationResult.SUCCESS


def test_receiver_does_not_generalize_to_unseen_combinations():
    """Production composes; comprehension stays exact-key lookup."""
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    for tick, (meaning, context) in enumerate(
        [
            (Meaning.FOOD, CommunicationContext.AID_TRANSFER),
            (Meaning.ORE, CommunicationContext.PAID_TRADE),
        ] * 3,
        start=1,
    ):
        speak(sender, receiver, meaning, context, tick,
              language_runtime, compositional_runtime)
    known = {signal.phoneme_ids
             for signal, _meaning in receiver.language.comprehension}
    unseen = derive_composed_signal(
        compositional_runtime, speaker_id=7,
        composite_meaning=CompositeMeaning.FOOD_EXCHANGE,
        config=COMPOSITIONAL,
    )
    # The receiver has heard the FOOD morpheme and the EXCHANGE morpheme, but
    # never their combination, and must not infer it.
    assert unseen.phoneme_ids not in known


def test_disabled_composition_keeps_base_resource_meanings():
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(language_runtime, 42)
    sender, receiver = person(7), person(9)
    outcome = communicate(
        sender, receiver, Meaning.FOOD,
        context=CommunicationContext.AID_TRANSFER, tick=1,
        active_ids=frozenset({7, 9}), config=LANGUAGE, runtime=language_runtime,
    )
    assert outcome.intended_meaning is Meaning.FOOD
    assert all(type(meaning) is Meaning
               for meaning, _signal in sender.language.production)


def test_disabled_composition_rejects_compositional_inputs():
    language_runtime = LanguageRuntimeState()
    initialize_language_runtime(language_runtime, 42)
    _unused, compositional_runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        communicate(
            person(7), person(9), Meaning.FOOD,
            context=CommunicationContext.AID_TRANSFER, tick=1,
            active_ids=frozenset({7, 9}), config=LANGUAGE,
            runtime=language_runtime,
            compositional_config=COMPOSITIONAL,
            compositional_runtime=compositional_runtime,
        )


# ── Runtime counters and transaction ────────────────────────────────────────

def test_modality_counters_partition_composed_utterances():
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    sequence = [
        (Meaning.FOOD, CommunicationContext.AID_TRANSFER),
        (Meaning.FOOD, CommunicationContext.PAID_TRADE),
        (Meaning.ORE, CommunicationContext.AID_TRANSFER),
        (Meaning.FOOD, CommunicationContext.AID_TRANSFER),
    ]
    for tick, (meaning, context) in enumerate(sequence, start=1):
        speak(sender, receiver, meaning, context, tick,
              language_runtime, compositional_runtime)
    assert compositional_runtime.composed_utterance_count == 4
    assert compositional_runtime.gift_utterance_count == 3
    assert compositional_runtime.exchange_utterance_count == 1
    assert (
        compositional_runtime.composed_utterance_count
        == compositional_runtime.gift_utterance_count
        + compositional_runtime.exchange_utterance_count
    )
    # One invention per distinct composite meaning; the repeat invents nothing.
    assert compositional_runtime.composed_invention_count == 3
    assert compositional_runtime.last_composition_tick == 4


def test_observed_meaning_mask_records_exercised_meanings_only():
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    speak(sender, receiver, Meaning.FOOD, CommunicationContext.AID_TRANSFER,
          1, language_runtime, compositional_runtime)
    speak(sender, receiver, Meaning.ORE, CommunicationContext.PAID_TRADE,
          2, language_runtime, compositional_runtime)
    mask = compositional_runtime.observed_composite_meaning_mask
    assert bin(mask).count("1") == 2
    assert mask < 2 ** len(CompositeMeaning)


def test_late_failure_restores_runtime_and_lexicons(monkeypatch):
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    speak(sender, receiver, Meaning.FOOD, CommunicationContext.AID_TRANSFER,
          1, language_runtime, compositional_runtime)
    before_runtime = replace(compositional_runtime)
    before_production = dict(sender.language.production)
    before_comprehension = dict(receiver.language.comprehension)

    def boom(*_args, **_kwargs):
        raise RuntimeError("injected late failure")

    monkeypatch.setattr(language_module, "_commit_runtime", boom)
    with pytest.raises(RuntimeError):
        speak(sender, receiver, Meaning.ORE, CommunicationContext.PAID_TRADE,
              2, language_runtime, compositional_runtime)
    assert compositional_runtime == before_runtime
    assert dict(sender.language.production) == before_production
    assert dict(receiver.language.comprehension) == before_comprehension


def test_runtime_validation_rejects_a_broken_partition():
    _language_runtime, compositional_runtime = runtimes()
    compositional_runtime.composed_utterance_count = 5
    compositional_runtime.gift_utterance_count = 1
    compositional_runtime.exchange_utterance_count = 1
    with pytest.raises(LanguageInvariantError):
        validate_compositional_protolanguage_runtime(compositional_runtime)


def test_runtime_validation_rejects_a_forged_seed_fingerprint():
    _language_runtime, compositional_runtime = runtimes()
    compositional_runtime.seed_domain_fingerprint = "0" * 64
    with pytest.raises(LanguageInvariantError):
        validate_compositional_protolanguage_runtime(compositional_runtime)


def test_runtime_config_mismatch_is_rejected():
    _language_runtime, compositional_runtime = runtimes()
    with pytest.raises(LanguageInvariantError):
        validate_compositional_protolanguage_runtime(
            compositional_runtime,
            config=replace(COMPOSITIONAL, modality_morpheme_length=2),
        )


# ── Summary ─────────────────────────────────────────────────────────────────

def test_summary_is_one_pass_and_bounded():
    language_runtime, compositional_runtime = runtimes()
    sender, receiver = person(7), person(9)
    speak(sender, receiver, Meaning.FOOD, CommunicationContext.AID_TRANSFER,
          1, language_runtime, compositional_runtime)
    speak(sender, receiver, Meaning.ORE, CommunicationContext.PAID_TRADE,
          2, language_runtime, compositional_runtime)
    # A one-shot iterable must be consumed exactly once.
    summary = compositional_protolanguage_summary(
        iter([sender, receiver]),
        runtime=compositional_runtime,
        config=COMPOSITIONAL,
        language_runtime=language_runtime,
    )
    assert summary["population"] == 2
    assert summary["composed_carriers"] == 2
    assert summary["composed_production_total"] == 2
    assert summary["production_by_modality"] == {"GIFT": 1, "EXCHANGE": 1}
    assert set(summary["production_by_composite_meaning"]) == {
        composite.name for composite in CompositeMeaning
    }
    assert summary["runtime"] == compositional_protolanguage_runtime_record(
        compositional_runtime,
        config=COMPOSITIONAL,
        language_runtime=language_runtime,
    )


# ── Hashing, pristine state, and reset ──────────────────────────────────────

def build_state(*, enabled: bool):
    state = SimulationState()
    initialize_language_runtime(
        state.language, 42, compositional_protolanguage_enabled=enabled)
    if enabled:
        initialize_compositional_protolanguage_runtime(
            state.compositional_protolanguage, COMPOSITIONAL, 42)
    people = [person(7), person(9)]
    state.people.extend(people)
    return state, people


def test_disabled_composition_is_omitted_from_the_behavioral_payload():
    from thalren_vale import world

    state, _people = build_state(enabled=False)
    baseline = SimulationConfig(language_evolution_enabled=True)
    baseline.validate()
    config = baseline.manifest_dict()
    reference = canonical_state_hash(state, world.world, config)
    # Nondefault disabled controls must not change the behavioral payload.
    shifted = dict(config)
    shifted["maximum_resource_morpheme_length"] = 1
    shifted["modality_morpheme_length"] = 2
    shifted["compositional_protolanguage_controls_status"] = (
        "engineering_only_uncontracted")
    assert canonical_state_hash(state, world.world, shifted) == reference


def test_hidden_composite_meaning_fails_closed_while_disabled():
    from thalren_vale import world

    state, people = build_state(enabled=False)
    signal = Signal((3, 3, 1))
    people[0].language.production[
        (CompositeMeaning.FOOD_GIFT, signal)
    ] = LexicalAssociation(
        meaning=CompositeMeaning.FOOD_GIFT, signal=signal, confidence=0.5)
    config = SimulationConfig(language_evolution_enabled=True)
    config.validate()
    with pytest.raises(LanguageInvariantError) as excinfo:
        canonical_state_hash(state, world.world, config.manifest_dict())
    assert excinfo.value.code == (
        "nonpristine_disabled_compositional_protolanguage_meaning")


def test_hidden_runtime_state_fails_closed_while_disabled():
    from thalren_vale import world

    state, _people = build_state(enabled=False)
    state.compositional_protolanguage = (
        CompositionalProtolanguageRuntimeState(
            composed_utterance_count=1, gift_utterance_count=1))
    config = SimulationConfig(language_evolution_enabled=True)
    config.validate()
    with pytest.raises(LanguageInvariantError) as excinfo:
        canonical_state_hash(state, world.world, config.manifest_dict())
    assert excinfo.value.code == (
        "nonpristine_disabled_compositional_protolanguage_runtime")


def test_enabled_hashing_requires_engineering_only_status():
    from thalren_vale import world

    state, _people = build_state(enabled=True)
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
    )
    config.validate()
    payload = config.manifest_dict()
    payload["compositional_protolanguage_controls_status"] = "disabled"
    with pytest.raises(ValueError):
        canonical_state_hash(state, world.world, payload)


def test_pristine_helper_matches_a_fresh_runtime():
    runtime = CompositionalProtolanguageRuntimeState()
    assert compositional_protolanguage_runtime_is_pristine(runtime)
    runtime.composed_utterance_count = 1
    assert not compositional_protolanguage_runtime_is_pristine(runtime)
    assert not compositional_protolanguage_runtime_is_pristine(object())


def test_state_reset_restores_a_pristine_compositional_runtime():
    state, _people = build_state(enabled=True)
    state.compositional_protolanguage.composed_utterance_count = 3
    state.compositional_protolanguage.gift_utterance_count = 3
    state.reset()
    assert compositional_protolanguage_runtime_is_pristine(
        state.compositional_protolanguage)


def test_enabled_hash_is_independent_of_the_process_hash_seed():
    script = textwrap.dedent(
        """
        import random
        from thalren_vale import world
        from thalren_vale.config import SimulationConfig
        from thalren_vale.language import (
            CommunicationContext, Meaning, communicate,
            initialize_compositional_protolanguage_runtime,
            initialize_language_runtime,
        )
        from thalren_vale.inhabitants import Inhabitant
        from thalren_vale.language import AgentLanguageState
        from thalren_vale.reproducibility import canonical_state_hash
        from thalren_vale.state import SimulationState

        random.seed(42)
        world.reseed_world()
        config = SimulationConfig(
            language_evolution_enabled=True,
            compositional_protolanguage_enabled=True,
        )
        config.validate()
        state = SimulationState()
        initialize_language_runtime(
            state.language, 42, compositional_protolanguage_enabled=True)
        initialize_compositional_protolanguage_runtime(
            state.compositional_protolanguage,
            config.compositional_protolanguage_config, 42)
        people = []
        for identifier in (7, 9):
            person = Inhabitant(f"P{identifier}", 0, 0)
            person.inhabitant_id = identifier
            person.faction = None
            person.language = AgentLanguageState()
            state.people.append(person)
            people.append(person)
        for tick, (meaning, context) in enumerate([
            (Meaning.FOOD, CommunicationContext.AID_TRANSFER),
            (Meaning.ORE, CommunicationContext.PAID_TRADE),
        ], start=1):
            communicate(
                people[0], people[1], meaning, context=context, tick=tick,
                active_ids=frozenset({7, 9}),
                config=config.language_evolution_config,
                runtime=state.language,
                compositional_config=(
                    config.compositional_protolanguage_config),
                compositional_runtime=state.compositional_protolanguage,
            )
        print(canonical_state_hash(
            state, world.world, config.manifest_dict()))
        """
    )

    def run(hash_seed: str) -> str:
        environment = dict(
            os.environ,
            PYTHONHASHSEED=hash_seed,
            PYTHONPATH=os.path.join(PROJECT_ROOT, "src"),
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120, env=environment,
            cwd=PROJECT_ROOT,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    first = run("0")
    assert first
    assert first == run("7") == run("12345")


# ── Runner containment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argument", [
    "--enable-compositional-protolanguage",
    "--disable-compositional-protolanguage",
    "--maximum-resource-morpheme-length",
    "--maximum-resource-morpheme-length=2",
    "--modality-morpheme-length",
    "--modality-morpheme-length=1",
    "--enable-compositional-proto",
    "--modality-morph",
    "--m",
])
def test_runner_rejects_the_complete_compositional_option_family(argument):
    with pytest.raises(ValueError):
        run_experiments._reject_uncontracted_compositional_protolanguage_args(
            (argument,))


def test_runner_rejects_a_plan_before_creating_any_output_root(tmp_path):
    import json

    plan_path = tmp_path / "plan.json"
    root = tmp_path / "never-created-root"
    plan_path.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "containment",
        "default_ticks": 2,
        "conditions": [{
            "name": "a",
            "seeds": "1",
            "extra_args": [
                "--log-mode", "metrics_only",
                "--enable-compositional-protolanguage",
            ],
        }],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        run_experiments.load_plan(plan_path)
    assert not root.exists()


def test_runner_still_accepts_a_contracted_plan(tmp_path):
    import json

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "contracted",
        "default_ticks": 2,
        "conditions": [{
            "name": "a",
            "seeds": "1",
            "extra_args": ["--log-mode", "metrics_only"],
        }],
    }), encoding="utf-8")
    plan, digest = run_experiments.load_plan(plan_path)
    assert plan["experiment_id"] == "contracted"
    assert len(digest) == 64


# ── Artifact validation ─────────────────────────────────────────────────────

def collect(config: dict):
    from thalren_vale.artifact_validation import (
        _IssueCollector,
        _validate_compositional_protolanguage_configuration,
    )

    issues = _IssueCollector()
    _validate_compositional_protolanguage_configuration(config, issues)
    return issues


def test_valid_configurations_produce_no_artifact_issues():
    disabled = SimulationConfig()
    disabled.validate()
    assert not collect(disabled.manifest_dict())
    enabled = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
    )
    enabled.validate()
    assert not collect(enabled.manifest_dict())


@pytest.mark.parametrize("overrides", [
    {"compositional_protolanguage_enabled": True,
     "language_evolution_enabled": False},
    {"maximum_resource_morpheme_length": 9},
    {"modality_morpheme_length": True},
    {"modality_morpheme_length": 2,
     "compositional_protolanguage_controls_status": "disabled"},
    {"compositional_protolanguage_control_notices": ["z", "a"]},
])
def test_contradictory_manifest_controls_are_invalid(overrides):
    config = SimulationConfig()
    config.validate()
    payload = dict(config.manifest_dict())
    payload.update(overrides)
    assert collect(payload)


def test_composed_morphemes_exceeding_signal_length_are_invalid():
    config = SimulationConfig(
        language_evolution_enabled=True,
        compositional_protolanguage_enabled=True,
    )
    config.validate()
    payload = dict(config.manifest_dict())
    payload["maximum_signal_length"] = 2
    assert collect(payload)


# ── Economy reachability across both individual-barter paths ────────────────

def _composed_economy_pass(*, social_partner_bias_enabled: bool) -> dict:
    """Drive a bounded economy pass and report composition counters.

    ``_individual_barter`` forks on partner bias, so composition owners must
    reach ``communicate`` down both branches. Exercising only one branch lets
    the other silently lose an owner and fail closed mid-run.
    """
    random.seed(42)
    world.reseed_world()
    state = SimulationState()
    social = SocialMemoryConfig(True, social_partner_bias_enabled, 8, 25)
    initialize_language_runtime(
        state.language, 42, compositional_protolanguage_enabled=True)
    initialize_compositional_protolanguage_runtime(
        state.compositional_protolanguage, COMPOSITIONAL, 42)

    people = []
    for index in range(24):
        inhabitant = person(index)
        inhabitant.r, inhabitant.c = index % 3, 0
        inhabitant.inventory = {
            'food': 3 if index % 2 == 0 else 0,
            'wood': 3 if index % 2 else 0,
            'ore': 1, 'stone': 1, 'water': 1,
        }
        people.append(inhabitant)
    state.next_inhabitant_id = len(people)
    state.people.extend(people)

    event_log: list = []
    for tick in range(1, 40):
        economy.economy_tick(
            people, [], tick, event_log,
            social_config=social,
            language_config=LANGUAGE,
            language_runtime=state.language,
            compositional_config=COMPOSITIONAL,
            compositional_runtime=state.compositional_protolanguage,
            raids_enabled=False,
        )
    return asdict(state.compositional_protolanguage)


@pytest.mark.parametrize("social_partner_bias_enabled", [False, True])
def test_composition_reaches_both_individual_barter_paths(
    social_partner_bias_enabled,
):
    runtime = _composed_economy_pass(
        social_partner_bias_enabled=social_partner_bias_enabled)
    assert runtime["composed_utterance_count"] > 0
    assert (
        runtime["composed_utterance_count"]
        == runtime["gift_utterance_count"] + runtime["exchange_utterance_count"]
    )
