"""Run-scoped stable identity is allocated only by atomic admission."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from thalren_vale import sim
from thalren_vale.config import SocialMemoryConfig
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.social import InteractionKind, record_interaction


@pytest.fixture(autouse=True)
def isolated_admission_state():
    original_people = sim.people
    original_all_dead = sim.all_dead
    sim.people = sim.state.people
    sim.all_dead = sim.state.all_dead
    sim.grid_occupants.clear()
    sim.reset_runtime_state()
    yield
    sim.people = sim.state.people
    sim.all_dead = sim.state.all_dead
    sim.grid_occupants.clear()
    sim.reset_runtime_state()
    sim.people = original_people
    sim.all_dead = original_all_dead


def test_temporary_and_discarded_candidates_never_consume_ids():
    temporary = Inhabitant("Temporary", 0, 0)
    discarded = Inhabitant("Discarded", 0, 0)

    assert temporary.inhabitant_id is None
    assert discarded.inhabitant_id is None
    assert sim.state.next_inhabitant_id == 0

    admitted = Inhabitant("Admitted", 0, 0)
    sim._spawn(admitted)

    assert admitted.inhabitant_id == 0
    assert sim.state.next_inhabitant_id == 1


def test_precondition_failure_mutates_no_store_and_consumes_no_id():
    candidate = Inhabitant("Rejected", 0, 0)
    candidate.inhabitant_id = 99

    with pytest.raises(ValueError, match="assigned ID"):
        sim._spawn(candidate)

    assert sim.people == []
    assert sim.grid_occupants == {}
    assert sim.state.next_inhabitant_id == 0


def test_failure_after_id_assignment_rolls_back_candidate_and_allocator(
    monkeypatch,
):
    candidate = Inhabitant("Candidate", 0, 0)

    def fail_before_insertion(inhabitant, people, **kwargs):
        kwargs["on_validated"]()
        assert inhabitant.inhabitant_id == 0
        assert people == []
        raise RuntimeError("injected admission failure")

    monkeypatch.setattr(sim, "grid_admit", fail_before_insertion)

    with pytest.raises(RuntimeError, match="injected"):
        sim._spawn(candidate)

    assert candidate.inhabitant_id is None
    assert sim.state.next_inhabitant_id == 0
    assert sim.people == []
    assert sim.grid_occupants == {}


def test_failure_after_authoritative_collection_mutation_rolls_back_everything(
    monkeypatch,
):
    class FailingPopulation(list):
        def append(self, value):
            raise RuntimeError("population append failed")

    candidate = Inhabitant("Candidate", 0, 0)
    membership = []
    failing_people = FailingPopulation()
    monkeypatch.setattr(sim, "people", failing_people)

    with pytest.raises(RuntimeError, match="population append"):
        sim._spawn(candidate, memberships=(membership,))

    assert candidate.inhabitant_id is None
    assert sim.state.next_inhabitant_id == 0
    assert failing_people == []
    assert membership == []
    assert all(
        candidate not in occupants
        for occupants in sim.grid_occupants.values()
    )


def test_allocator_commit_failure_removes_fully_inserted_candidate(monkeypatch):
    candidate = Inhabitant("Candidate", 0, 0)
    membership = []

    def fail_commit(inhabitant, candidate_id):
        assert inhabitant is candidate
        assert candidate_id == 0
        assert candidate in sim.people
        assert candidate in membership
        sim.state.next_inhabitant_id += 1
        raise RuntimeError("commit failed")

    monkeypatch.setattr(sim.state, "commit_inhabitant_id", fail_commit)

    with pytest.raises(RuntimeError, match="commit failed"):
        sim._spawn(candidate, memberships=(membership,))

    assert candidate.inhabitant_id is None
    assert sim.state.next_inhabitant_id == 0
    assert candidate not in sim.people
    assert candidate not in membership
    assert all(
        candidate not in occupants
        for occupants in sim.grid_occupants.values()
    )


def test_concurrent_admissions_receive_unique_monotonic_ids():
    candidates = [Inhabitant(f"P{index}", 0, 0) for index in range(24)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(sim._spawn, candidates))

    assigned = sorted(candidate.inhabitant_id for candidate in candidates)
    assert assigned == list(range(24))
    assert sim.state.next_inhabitant_id == 24
    assert len(sim.people) == 24


def test_ids_are_never_reused_and_repeated_display_names_do_not_alias():
    original = Inhabitant("Reused Name", 0, 0)
    sim._spawn(original)
    sim.grid_remove(original)
    sim.people.remove(original)
    sim.all_dead.append(original)

    replacement = Inhabitant("Reused Name", 0, 0)
    friend = Inhabitant("Friend", 0, 0)
    sim._spawn(replacement)
    sim._spawn(friend)
    record_interaction(
        friend,
        replacement,
        InteractionKind.TRADE,
        tick=1,
        active_ids=frozenset({replacement.inhabitant_id, friend.inhabitant_id}),
        config=SocialMemoryConfig(True, False, 32, 25),
    )

    assert original.inhabitant_id == 0
    assert replacement.inhabitant_id == 1
    assert friend.inhabitant_id == 2
    assert tuple(friend.relationships) == (1,)
    assert 0 not in friend.relationships


def test_reset_clears_social_state_and_restores_allocator_deterministically():
    first = Inhabitant("First", 0, 0)
    second = Inhabitant("Second", 0, 0)
    sim._spawn(first)
    sim._spawn(second)
    first.relationships[second.inhabitant_id] = object()

    sim.reset_runtime_state()
    sim.grid_occupants.clear()

    assert first.relationships == {}
    assert sim.state.next_inhabitant_id == 0
    assert sim.people == []
    replacement = Inhabitant("New Run", 0, 0)
    sim._spawn(replacement)
    assert replacement.inhabitant_id == 0
