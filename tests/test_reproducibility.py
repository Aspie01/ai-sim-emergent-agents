"""Independent-process reproducibility guarantees."""

import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_seeded_layer_one_does_not_spawn_worker_threads(monkeypatch):
    from thalren_vale import sim

    person = SimpleNamespace(name="A", r=2, c=3)
    calls = []

    monkeypatch.setattr(sim, "people", [person])
    monkeypatch.setattr(sim, "all_dead", [])
    monkeypatch.setattr(sim, "_serial_mode", True)
    monkeypatch.setattr(sim, "do_tick_preamble", lambda people, tick: None)
    monkeypatch.setattr(
        sim,
        "process_inhabitants_chunk",
        lambda inhabitants, all_people, tick, bucket: calls.append(
            (list(inhabitants), all_people, tick, bucket)
        ),
    )

    class ForbiddenThread:
        def __init__(self, *args, **kwargs):
            raise AssertionError("serial mode must not construct worker threads")

    monkeypatch.setattr(sim.threading, "Thread", ForbiddenThread)

    deaths, previous_positions = sim.inhabitants_layer(7)

    assert deaths == []
    assert previous_positions == {"A": (2, 3)}
    assert len(calls) == 1
    assert calls[0][0] == [person]
    assert calls[0][1] is sim.people
    assert calls[0][2] == 7


def test_canonical_serializer_handles_runtime_container_types():
    from thalren_vale.reproducibility import _json_safe

    value = {
        "resources": defaultdict(int, {"food": 3}),
        "beliefs": {"trade_builds_bonds", "self_reliance"},
        "route": ("A", "B"),
    }

    converted = _json_safe(value)

    assert converted["resources"] == {"food": 3}
    assert converted["beliefs"] == ["self_reliance", "trade_builds_bonds"]
    assert converted["route"] == ["A", "B"]


def run_and_read_manifest(
    run_dir: Path, seed: int, extra_args: tuple[str, ...] = ()
) -> dict:
    run_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            str(seed),
            "--ticks",
            "5",
            "--condition",
            "repro",
            "--disable-antistag",
            "--log-mode",
            "metrics_only",
            *extra_args,
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    path = run_dir / "data" / f"run_manifest_repro_seed_{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_same_seed_has_same_hash_across_processes(tmp_path):
    first = run_and_read_manifest(tmp_path / "first", 456)
    second = run_and_read_manifest(tmp_path / "second", 456)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["execution_mode"] == second["execution_mode"] == "serial"


def test_explicit_disabled_social_controls_preserve_baseline_hash(tmp_path):
    baseline = run_and_read_manifest(tmp_path / "baseline", 456)
    disabled = run_and_read_manifest(
        tmp_path / "disabled",
        456,
        ("--disable-social-memory", "--disable-social-partner-bias"),
    )

    assert disabled["state_hash"] == baseline["state_hash"]
    assert disabled["configuration"] == baseline["configuration"]
    assert disabled["configuration"]["social_controls_status"] == "disabled"


def test_enabled_social_state_hash_is_stable_across_processes(tmp_path):
    extra_args = (
        "--enable-social-memory",
        "--enable-social-partner-bias",
    )
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["configuration"]["social_memory_enabled"] is True
    assert first["configuration"]["social_partner_bias_enabled"] is True
    assert first["configuration"]["social_controls_status"] == (
        "engineering_only_uncontracted"
    )


def test_enabled_coalition_state_hash_is_stable_across_processes(tmp_path):
    extra_args = (
        "--enable-social-memory",
        "--enable-coalition-emergence",
    )
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["configuration"]["coalition_emergence_enabled"] is True
    assert first["configuration"]["coalition_controls_status"] == (
        "engineering_only_uncontracted"
    )


def test_enabled_language_state_hash_is_stable_across_processes(tmp_path):
    extra_args = ("--enable-language-evolution",)
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"] == second["configuration"]
    assert first["configuration"]["language_evolution_enabled"] is True
    assert first["configuration"]["language_controls_status"] == "contracted"
    assert first["configuration"]["language_control_notices"] == []


def test_enabled_language_observation_preserves_existing_simulation_artifacts(
    tmp_path,
):
    baseline_root = tmp_path / "baseline"
    enabled_root = tmp_path / "enabled"
    baseline = run_and_read_manifest(baseline_root, 456)
    enabled = run_and_read_manifest(
        enabled_root, 456, ("--enable-language-evolution",))

    for artifact in ("metrics", "events", "beliefs"):
        baseline_path = baseline_root / "data" / baseline[
            "artifact_inventory"
        ][artifact]["path"]
        enabled_path = enabled_root / "data" / enabled[
            "artifact_inventory"
        ][artifact]["path"]
        assert enabled_path.read_bytes() == baseline_path.read_bytes()

    def biological_summary(root, manifest):
        path = root / "data" / manifest["artifact_inventory"]["summary"][
            "path"
        ]
        with path.open("r", encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        row.pop("wall_clock_seconds")
        row.pop("peak_ram_mb")
        return row

    assert biological_summary(enabled_root, enabled) == biological_summary(
        baseline_root, baseline)
    assert enabled["state_hash"] != baseline["state_hash"]


def test_raid_disabled_runs_are_deterministic_and_record_policy(tmp_path):
    extra_args = ("--disable-raids",)
    first = run_and_read_manifest(tmp_path / "first", 456, extra_args)
    second = run_and_read_manifest(tmp_path / "second", 456, extra_args)

    assert first["state_hash"] == second["state_hash"]
    assert first["configuration"]["disabled_layers"] == ["raids"]
    assert first["configuration"]["raids_enabled"] is False
    assert first["log_mode"] == "metrics_only"


def test_different_seeds_have_different_hashes(tmp_path):
    first = run_and_read_manifest(tmp_path / "first", 456)
    second = run_and_read_manifest(tmp_path / "second", 457)

    assert first["state_hash"] != second["state_hash"]


def test_manifest_records_code_provenance(tmp_path):
    manifest = run_and_read_manifest(tmp_path / "run", 456)

    assert manifest["schema_version"] == 2
    assert manifest["event_schema_version"] == 1
    assert manifest["metrics_timing_contract"] == "end_of_tick_v2"
    assert manifest["requested_ticks"] == manifest["final_tick"] == 5
    assert manifest["termination_reason"] == "requested_ticks_reached"
    assert manifest["result_status"] == "completed"
    assert manifest["completed_normally"] is True
    assert manifest["state_hash_algorithm"] == "sha256"
    assert len(manifest["state_hash"]) == 64
    # The expected-run contract has always required this exact shape; the
    # writer previously omitted `tag`, which is one reason runner output could
    # not reach v2_ready.
    assert set(manifest["code"]) == {"commit", "tag", "dirty"}
    tag = manifest["code"]["tag"]
    assert tag is None or (type(tag) is str and tag.strip())
    # A direct run carries no plan, but the fields must exist so their absence
    # is recorded rather than merely missing.
    assert manifest["plan_identity"] is None
    assert manifest["plan_sha256"] is None
    assert len(manifest["environment_fingerprint"]) == 64
    assert set(manifest["artifact_inventory"]) == {
        "metrics", "events", "beliefs", "summary",
    }
    assert manifest["configuration"]["social_memory_enabled"] is False
    assert manifest["configuration"]["social_partner_bias_enabled"] is False
    assert manifest["configuration"]["maximum_social_ties"] == 32
    assert manifest["configuration"]["relationship_decay_interval"] == 25
    assert manifest["configuration"]["social_controls_status"] == "disabled"
    assert manifest["configuration"]["social_control_notices"] == []
    assert manifest["configuration"]["language_evolution_enabled"] is False
    assert manifest["configuration"]["maximum_language_associations"] == 32
    assert manifest["configuration"]["maximum_signal_length"] == 3
    assert manifest["configuration"]["language_learning_rate"] == 0.20
    assert manifest["configuration"]["language_reinforcement_rate"] == 0.10
    assert manifest["configuration"]["language_forgetting_interval"] == 25
    assert manifest["configuration"]["language_invention_enabled"] is True
    assert manifest["configuration"]["language_controls_status"] == "disabled"
    assert manifest["configuration"]["language_control_notices"] == []
    assert manifest["configuration"]["coalition_emergence_enabled"] is False
    assert manifest["configuration"]["coalition_minimum_size"] == 3
    assert manifest["configuration"]["coalition_trust_threshold"] == 0.24
    assert manifest["configuration"]["coalition_familiarity_threshold"] == 0.40
    assert manifest["configuration"]["coalition_maximum_grievance"] == 0.20
    assert manifest["configuration"]["coalition_persistence_ticks"] == 5
    assert manifest["configuration"]["maximum_active_coalitions"] == 32
    assert manifest["configuration"]["coalition_controls_status"] == "disabled"
    assert manifest["configuration"]["coalition_control_notices"] == []


def test_cli_normalization_warns_and_preserves_requested_bias_provenance(tmp_path):
    run_dir = tmp_path / "normalized"
    run_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            "123",
            "--ticks",
            "1",
            "--condition",
            "normalized",
            "--disable-antistag",
            "--log-mode",
            "metrics_only",
            "--enable-social-partner-bias",
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "normalized to false" in result.stderr
    manifest_path = (
        run_dir / "data" / "run_manifest_normalized_seed_123.json")
    configuration = json.loads(
        manifest_path.read_text(encoding="utf-8"))["configuration"]
    assert configuration["social_memory_enabled"] is False
    assert configuration["social_partner_bias_enabled"] is False
    assert configuration["social_controls_status"] == "normalized_uncontracted"
    assert configuration["social_control_notices"] == [
        "partner_bias_requested_without_social_memory"
    ]


def test_coalition_cli_normalization_warns_with_separate_provenance(tmp_path):
    run_dir = tmp_path / "normalized-coalition"
    run_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "thalren_vale",
            "--seed",
            "123",
            "--ticks",
            "1",
            "--condition",
            "coalition-normalized",
            "--disable-antistag",
            "--log-mode",
            "metrics_only",
            "--enable-coalition-emergence",
        ],
        cwd=run_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "effective coalition emergence normalized to false" in result.stderr
    manifest_path = (
        run_dir
        / "data"
        / "run_manifest_coalition-normalized_seed_123.json"
    )
    configuration = json.loads(
        manifest_path.read_text(encoding="utf-8"))["configuration"]
    assert configuration["coalition_emergence_enabled"] is False
    assert configuration["coalition_controls_status"] == "normalized_uncontracted"
    assert configuration["coalition_control_notices"] == [
        "coalition_emergence_requested_without_social_memory"
    ]
    assert configuration["social_controls_status"] == "disabled"
    assert configuration["social_control_notices"] == []


def _social_hash_fixture(*, owner_is_dead: bool = False):
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.state import SimulationState

    inhabitant = Inhabitant("Stable", 0, 0)
    inhabitant.faction = None
    inhabitant.inhabitant_id = 7
    state = SimulationState(
        people=[] if owner_is_dead else [inhabitant],
        all_dead=[inhabitant] if owner_is_dead else [],
        next_inhabitant_id=9,
    )
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 1,
        "social_memory_enabled": False,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "disabled",
        "social_control_notices": [],
    }
    return inhabitant, state, world, configuration


def test_disabled_hash_ignores_allocator_ids_with_empty_social_mappings():
    from thalren_vale.reproducibility import canonical_state_hash

    inhabitant, state, world, configuration = _social_hash_fixture()

    before = canonical_state_hash(state, world, configuration)
    inhabitant.inhabitant_id = 70
    state.next_inhabitant_id = 90
    after = canonical_state_hash(state, world, configuration)

    assert inhabitant.relationships == {}
    assert before == after


@pytest.mark.parametrize(
    ("owner_is_dead", "cohort"),
    [(False, "living"), (True, "dead")],
)
def test_disabled_hash_rejects_hidden_relationship_state(
    owner_is_dead,
    cohort,
):
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import Relationship

    inhabitant, state, world, configuration = _social_hash_fixture(
        owner_is_dead=owner_is_dead)
    inhabitant.relationships[8] = Relationship(trust=0.9)

    with pytest.raises(
        ValueError,
        match=rf"{cohort}\[0\] name='Stable' inhabitant_id=7",
    ):
        canonical_state_hash(state, world, configuration)


def test_different_social_histories_change_enabled_state_hash():
    from thalren_vale.config import SocialMemoryConfig
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import InteractionKind, record_interaction
    from thalren_vale.state import SimulationState

    first = Inhabitant("A", 0, 0)
    second = Inhabitant("B", 0, 0)
    first.faction = None
    second.faction = None
    first.inhabitant_id = 1
    second.inhabitant_id = 2
    state = SimulationState(
        people=[first, second], next_inhabitant_id=3)
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 1,
        "social_memory_enabled": True,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "engineering_only_uncontracted",
        "social_control_notices": [],
    }

    before = canonical_state_hash(state, world, configuration)
    record_interaction(
        first,
        second,
        InteractionKind.TRADE,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=SocialMemoryConfig(True, False, 32, 25),
    )
    after = canonical_state_hash(state, world, configuration)

    assert before != after


def _committed_social_hash_fixture():
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.state import SimulationState

    first = Inhabitant("A", 0, 0)
    second = Inhabitant("B", 0, 0)
    for inhabitant, inhabitant_id in ((first, 1), (second, 2)):
        inhabitant.faction = None
        inhabitant.inhabitant_id = inhabitant_id
    state = SimulationState(people=[first, second], next_inhabitant_id=3)
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 1,
        "social_memory_enabled": True,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "engineering_only_uncontracted",
        "social_control_notices": [],
    }
    return first, second, state, world, configuration


def _coalition_disabled_defaults():
    return {
        "coalition_emergence_enabled": False,
        "coalition_minimum_size": 3,
        "coalition_trust_threshold": 0.24,
        "coalition_familiarity_threshold": 0.40,
        "coalition_maximum_grievance": 0.20,
        "coalition_persistence_ticks": 5,
        "maximum_active_coalitions": 32,
        "coalition_controls_status": "disabled",
        "coalition_control_notices": [],
    }


def test_coalition_disabled_preserves_committed_social_memory_hashes():
    from thalren_vale.config import SocialMemoryConfig
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import InteractionKind, record_interaction

    first, second, state, world, configuration = _committed_social_hash_fixture()
    with_defaults = {**configuration, **_coalition_disabled_defaults()}

    empty_before = canonical_state_hash(state, world, configuration)
    empty_after = canonical_state_hash(state, world, with_defaults)
    assert empty_before == empty_after == (
        "1c9df3586cbec2c93cf83f00541fb9380acc2a320f8c8b917749a6b6a89b0b5a"
    )

    record_interaction(
        first,
        second,
        InteractionKind.TRADE,
        tick=1,
        active_ids=frozenset({1, 2}),
        config=SocialMemoryConfig(True, False, 32, 25),
    )
    trade_before = canonical_state_hash(state, world, configuration)
    trade_after = canonical_state_hash(state, world, with_defaults)
    assert trade_before == trade_after == (
        "d467dad5a9efe93f2d69c06998747f01c0b74997039c2c77b95744f10bbdc70b"
    )


def test_disabled_hash_rejects_hidden_coalition_state():
    from thalren_vale.coalitions import CoalitionCandidate
    from thalren_vale.reproducibility import canonical_state_hash

    _first, _second, state, world, configuration = (
        _committed_social_hash_fixture())
    configuration.update(_coalition_disabled_defaults())
    state.coalitions.candidates[(1, 2, 3)] = CoalitionCandidate(
        (1, 2, 3), 1, 1, 1)

    with pytest.raises(ValueError, match="pristine coalition state"):
        canonical_state_hash(state, world, configuration)


def test_enabled_coalition_runtime_changes_canonical_hash():
    from thalren_vale.coalitions import transition_informal_coalitions
    from thalren_vale.config import CoalitionConfig
    from thalren_vale.inhabitants import Inhabitant
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.social import Relationship
    from thalren_vale.state import SimulationState

    people = [Inhabitant(name, 0, 0) for name in ("A", "B", "C")]
    for inhabitant_id, inhabitant in enumerate(people, start=1):
        inhabitant.inhabitant_id = inhabitant_id
        inhabitant.faction = None
    for first, second in ((0, 1), (1, 2), (0, 2)):
        people[first].relationships[people[second].inhabitant_id] = Relationship(
            trust=0.8, familiarity=0.8, interaction_count=1)
        people[second].relationships[people[first].inhabitant_id] = Relationship(
            trust=0.8, familiarity=0.8, interaction_count=1)
    coalition_config = CoalitionConfig(True, 3, 0.24, 0.40, 0.20, 2, 32)
    state = SimulationState(people=people, next_inhabitant_id=4)
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 1},
    }]]
    configuration = {
        "ticks": 2,
        "social_memory_enabled": True,
        "social_partner_bias_enabled": False,
        "maximum_social_ties": 32,
        "relationship_decay_interval": 25,
        "social_controls_status": "engineering_only_uncontracted",
        "social_control_notices": [],
        **_coalition_disabled_defaults(),
        "coalition_emergence_enabled": True,
        "coalition_persistence_ticks": 2,
        "coalition_controls_status": "engineering_only_uncontracted",
    }

    state.coalitions = transition_informal_coalitions(
        people, state.coalitions, tick=1, config=coalition_config)
    candidate_hash = canonical_state_hash(state, world, configuration)
    state.coalitions = transition_informal_coalitions(
        people, state.coalitions, tick=2, config=coalition_config)
    formed_hash = canonical_state_hash(state, world, configuration)

    assert candidate_hash != formed_hash


# ── Source encoding discipline ──────────────────────────────────────────────

def test_source_files_keep_their_committed_byte_order_mark_state():
    """Reject accidental BOM drift introduced by rewriting whole files.

    A tool that reads with ``utf-8-sig`` and writes with ``utf-8-sig`` adds a
    BOM to files that never had one. Python still imports such a file, so the
    change is invisible to every behavioral test; only ``ast.parse`` on raw
    text fails. `economy.py` is the one module that legitimately carries a BOM.
    """
    import pathlib

    project_root = pathlib.Path(__file__).resolve().parents[1]
    # The legacy modules that have carried a BOM since before the language
    # milestones. Every other module is plain UTF-8.
    expected_bom = {
        "civilization.py",
        "combat.py",
        "diplomacy.py",
        "economy.py",
        "factions.py",
        "mythology.py",
    }
    offenders = []
    for path in sorted((project_root / "src").rglob("*.py")):
        has_bom = path.read_bytes().startswith(b"\xef\xbb\xbf")
        if has_bom != (path.name in expected_bom):
            offenders.append((str(path.relative_to(project_root)), has_bom))
    for name in ("run_experiments.py",):
        path = project_root / name
        if path.read_bytes().startswith(b"\xef\xbb\xbf"):
            offenders.append((name, True))
    assert not offenders, f"unexpected BOM state: {offenders}"


# ── Active research payload ─────────────────────────────────────────────────

def _faction_hash_with_research(research):
    """Hash one otherwise-identical faction holding the given research."""
    import random

    from thalren_vale import world
    from thalren_vale.config import SimulationConfig
    from thalren_vale.factions import Faction
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.state import SimulationState

    random.seed(42)
    world.reseed_world()
    config = SimulationConfig()
    config.validate()
    state = SimulationState()
    faction = Faction("Iron Shore", [], set(), set(), 0)
    faction.techs = {"tools"}
    faction.active_research = research
    state.factions.append(faction)
    return canonical_state_hash(state, world.world, config.manifest_dict())


def test_in_progress_research_is_visible_to_the_canonical_hash():
    """Two factions researching different things must not share a hash.

    The payload previously read `researching` and `research_progress`, which
    nothing ever assigns, so both were permanently None and every distinct
    research state collapsed to one fingerprint.
    """
    idle = _faction_hash_with_research(None)
    early = _faction_hash_with_research(
        {"tech": "oral_tradition", "progress": 5, "started": 10,
         "paused": False})
    other = _faction_hash_with_research(
        {"tech": "masonry", "progress": 5, "started": 10, "paused": False})
    assert idle != early
    assert early != other


@pytest.mark.parametrize("field, value", [
    ("progress", 6),
    ("started", 11),
    ("paused", True),
])
def test_every_research_field_reaches_the_hash(field, value):
    base = {"tech": "oral_tradition", "progress": 5, "started": 10,
            "paused": False}
    changed = dict(base)
    changed[field] = value
    assert _faction_hash_with_research(base) != _faction_hash_with_research(
        changed)


def test_absent_research_attribute_is_accepted():
    """Factions created before technology runs simply have no research."""
    import random

    from thalren_vale import world
    from thalren_vale.config import SimulationConfig
    from thalren_vale.factions import Faction
    from thalren_vale.reproducibility import canonical_state_hash
    from thalren_vale.state import SimulationState

    random.seed(42)
    world.reseed_world()
    config = SimulationConfig()
    config.validate()
    state = SimulationState()
    faction = Faction("Iron Shore", [], set(), set(), 0)
    faction.techs = set()
    state.factions.append(faction)
    assert canonical_state_hash(state, world.world, config.manifest_dict())


# ── Contracted primary endpoint ─────────────────────────────────────────────

class _Runtime:
    """Minimal stand-in exposing only the two contracted counters."""

    def __init__(self, attempts, successes):
        self.communication_attempt_count = attempts
        self.successful_interpretation_count = successes


def test_endpoint_reports_the_comprehension_success_rate():
    from thalren_vale.reproducibility import language_endpoint_record

    record = language_endpoint_record(_Runtime(200, 50), final_tick=40)
    assert record["name"] == "comprehension_success_rate"
    assert record["communication_attempt_count"] == 200
    assert record["successful_interpretation_count"] == 50
    assert record["comprehension_success_rate"] == pytest.approx(0.25)
    assert record["measured_at_tick"] == 40


def test_unattempted_run_reports_no_rate_rather_than_zero():
    """A control arm attempts nothing, so its rate is undefined.

    Reporting 0.0 would assert a measured communicative failure that never
    occurred, which is a different claim from "no measurement exists".
    """
    from thalren_vale.reproducibility import language_endpoint_record

    record = language_endpoint_record(_Runtime(0, 0), final_tick=40)
    assert record["comprehension_success_rate"] is None
    assert record["communication_attempt_count"] == 0


def test_endpoint_records_no_analysis_contract():
    """Estimand, estimator, and uncertainty method remain unspecified."""
    from thalren_vale.reproducibility import language_endpoint_record

    record = language_endpoint_record(_Runtime(10, 5), final_tick=1)
    assert record["analysis_contract"] == "unspecified"


@pytest.mark.parametrize("attempts, successes", [
    (10, 11),      # successes exceed attempts
    (-1, 0),       # negative attempts
    (10, -1),      # negative successes
])
def test_endpoint_rejects_counters_violating_their_partition(
    attempts, successes,
):
    from thalren_vale.reproducibility import language_endpoint_record

    with pytest.raises(ValueError):
        language_endpoint_record(_Runtime(attempts, successes), final_tick=1)


def test_endpoint_rejects_an_invalid_final_tick():
    from thalren_vale.reproducibility import language_endpoint_record

    for tick in (-1, 1.0, True, None):
        with pytest.raises(ValueError):
            language_endpoint_record(_Runtime(10, 5), final_tick=tick)


def test_endpoint_rate_is_deterministic_across_processes():
    """Floating division must not vary with process state."""
    import os
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        from thalren_vale.reproducibility import language_endpoint_record

        class R:
            communication_attempt_count = 4363
            successful_interpretation_count = 1237

        print(repr(language_endpoint_record(R(), final_tick=40)))
        """
    )
    project_root = str(Path(__file__).resolve().parents[1])

    def run(hash_seed):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed,
                   PYTHONPATH=os.path.join(project_root, "src"))
        done = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True, timeout=60,
                              env=env, cwd=project_root)
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    first = run("0")
    assert first
    assert first == run("7") == run("12345")


# ── Runner provenance ───────────────────────────────────────────────────────

def test_environment_fingerprint_is_deterministic():
    from thalren_vale.reproducibility import environment_fingerprint

    first = environment_fingerprint()
    assert len(first) == 64
    assert first == environment_fingerprint()


def test_environment_fingerprint_tracks_plugin_content(tmp_path):
    """A changed plugin must change the fingerprint.

    Plugins can mutate simulation state directly, so a fingerprint blind to
    them would call two materially different environments identical.
    """
    from thalren_vale.reproducibility import environment_fingerprint

    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "__init__.py").write_text("", encoding="utf-8")
    plugin = plugins / "sample.py"

    plugin.write_text("VALUE = 1\n", encoding="utf-8")
    before = environment_fingerprint(tmp_path)
    plugin.write_text("VALUE = 2\n", encoding="utf-8")
    after = environment_fingerprint(tmp_path)
    assert before != after

    plugin.unlink()
    assert environment_fingerprint(tmp_path) not in (before, after)


def test_plugin_inventory_mirrors_the_loader_scan_rule(tmp_path):
    """`load_plugins` reads plugins/*.py excluding __init__.py."""
    from thalren_vale.reproducibility import plugin_inventory

    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "__init__.py").write_text("", encoding="utf-8")
    (plugins / "beta.py").write_text("B = 1\n", encoding="utf-8")
    (plugins / "alpha.py").write_text("A = 1\n", encoding="utf-8")
    (plugins / "notes.txt").write_text("ignored\n", encoding="utf-8")

    entries = plugin_inventory(tmp_path)
    assert [entry["name"] for entry in entries] == ["alpha.py", "beta.py"]
    assert all(len(entry["sha256"]) == 64 for entry in entries)


def test_absent_plugin_directory_is_an_empty_inventory(tmp_path):
    from thalren_vale.reproducibility import plugin_inventory

    assert plugin_inventory(tmp_path) == []


def test_code_revision_reports_the_expected_shape():
    """The expected-run contract compares exactly these three keys."""
    from thalren_vale.reproducibility import _code_revision

    code = _code_revision()
    assert set(code) == {"commit", "tag", "dirty"}
    assert code["tag"] is None or (
        type(code["tag"]) is str and code["tag"].strip())


def test_runner_passes_plan_provenance_on_the_child_command_line():
    """Plan identity must travel on argv so provenance is auditable."""
    import run_experiments

    command = run_experiments._simulation_command(
        456, "baseline", 3, ("--log-mode", "metrics_only"),
        plan_identity="demo-plan", plan_sha256="a" * 64,
    )
    assert "--plan-identity" in command
    assert command[command.index("--plan-identity") + 1] == "demo-plan"
    assert "--plan-sha256" in command
    assert command[command.index("--plan-sha256") + 1] == "a" * 64
    # Cell arguments must still follow, unmodified.
    assert command[-2:] == ["--log-mode", "metrics_only"]


def test_direct_run_command_omits_plan_provenance():
    """A run with no plan must not fabricate identity."""
    import run_experiments

    command = run_experiments._simulation_command(456, "baseline", 3, ())
    assert "--plan-identity" not in command
    assert "--plan-sha256" not in command


def test_annotated_tag_requires_an_exact_match(tmp_path):
    """A descendant of a tagged commit is not itself tagged.

    Plain `git describe --tags` reports the nearest ancestor tag with a
    distance suffix, which would record an untagged development revision as
    though it were the tagged release.
    """
    import subprocess

    from thalren_vale.reproducibility import _annotated_tag

    def git(*args):
        subprocess.run(
            ["git", *args], cwd=tmp_path, check=True,
            capture_output=True, text=True, timeout=10)

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-qm", "first")
    git("tag", "-a", "v1.0", "-m", "release")

    assert _annotated_tag(tmp_path) == "v1.0"

    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-qm", "second")

    assert _annotated_tag(tmp_path) is None


def test_annotated_tag_is_none_outside_a_repository(tmp_path):
    from thalren_vale.reproducibility import _annotated_tag

    assert _annotated_tag(tmp_path) is None
