"""Deterministic vertex-biconnected informal coalition emergence."""

from __future__ import annotations

import copy
import random
import sys

import pytest

from thalren_vale.coalitions import (
    CoalitionCandidate,
    CoalitionInvariantError,
    CoalitionRuntimeState,
    InformalCoalition,
    build_qualifying_reciprocal_graph,
    canonical_candidate_snapshot,
    canonical_coalition_snapshot,
    coalition_summary,
    resolve_exclusive_support_blocks,
    transition_informal_coalitions,
    validate_proposed_coalition_state,
    vertex_biconnected_support_blocks,
)
from thalren_vale.config import CoalitionConfig, SocialMemoryConfig
from thalren_vale.inhabitants import Inhabitant
from thalren_vale.social import Relationship, maintain_relationships


def coalition_config(
    *,
    persistence: int = 2,
    maximum_active: int = 32,
) -> CoalitionConfig:
    return CoalitionConfig(
        coalition_emergence_enabled=True,
        coalition_minimum_size=3,
        coalition_trust_threshold=0.24,
        coalition_familiarity_threshold=0.40,
        coalition_maximum_grievance=0.20,
        coalition_persistence_ticks=persistence,
        maximum_active_coalitions=maximum_active,
    )


def person(inhabitant_id: int) -> Inhabitant:
    inhabitant = Inhabitant(f"P{inhabitant_id}", 0, 0)
    inhabitant.inhabitant_id = inhabitant_id
    inhabitant.faction = None
    return inhabitant


def population(ids: tuple[int, ...] | range) -> dict[int, Inhabitant]:
    return {inhabitant_id: person(inhabitant_id) for inhabitant_id in ids}


def support(
    people: dict[int, Inhabitant],
    first: int,
    second: int,
    *,
    trust: float = 0.80,
    familiarity: float = 0.80,
    grievance: float = 0.0,
    tick: int = 0,
) -> None:
    people[first].relationships[second] = Relationship(
        trust=trust,
        familiarity=familiarity,
        grievance=grievance,
        interaction_count=1,
        last_interaction_tick=tick,
    )
    people[second].relationships[first] = Relationship(
        trust=trust,
        familiarity=familiarity,
        grievance=grievance,
        interaction_count=1,
        last_interaction_tick=tick,
    )


def connect(
    people: dict[int, Inhabitant],
    edges: tuple[tuple[int, int], ...] | list[tuple[int, int]],
) -> None:
    for first, second in edges:
        support(people, first, second)


def graph_blocks(
    people: dict[int, Inhabitant],
    *,
    tick: int = 1,
) -> tuple:
    graph = build_qualifying_reciprocal_graph(
        list(people.values()), tick=tick, config=coalition_config())
    blocks, articulations = vertex_biconnected_support_blocks(
        graph,
        tuple(people),
        minimum_size=3,
    )
    return graph, blocks, articulations


def active_state(
    members: tuple[int, ...],
    *,
    active_ids: tuple[int, ...] | None = None,
    last_tick: int = 1,
) -> CoalitionRuntimeState:
    active_ids = active_ids or members
    coalition = InformalCoalition(0, 1, members)
    return CoalitionRuntimeState(
        active_coalitions={0: coalition},
        member_to_coalition={member: 0 for member in members},
        next_coalition_id=1,
        candidate_formation_count=1,
        last_observation_tick=last_tick,
        last_active_inhabitant_ids=tuple(sorted(active_ids)),
    )


def test_no_relationships_produce_no_candidate():
    people = list(population((1, 2, 3)).values())

    result = transition_informal_coalitions(
        people, CoalitionRuntimeState(), tick=1, config=coalition_config())

    assert result.candidates == {}
    assert result.active_coalitions == {}
    assert coalition_summary(result).qualifying_reciprocal_edge_count == 0


def test_one_way_trust_produces_no_reciprocal_edge():
    people = population((1, 2, 3))
    people[1].relationships[2] = Relationship(
        trust=1.0,
        familiarity=1.0,
        interaction_count=10,
    )

    graph = build_qualifying_reciprocal_graph(
        list(people.values()), tick=1, config=coalition_config())

    assert graph.edge_count == 0


def test_legacy_integer_trust_never_supports_a_coalition():
    people = population((1, 2, 3))
    for first in people.values():
        for second in people.values():
            if first is not second:
                first.trust[second.name] = 1_000

    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    assert result.candidates == {}
    assert result.last_qualifying_reciprocal_edge_count == 0


@pytest.mark.parametrize(
    ("changes", "expected_edges"),
    [
        ({"trust": 0.23}, 2),
        ({"familiarity": 0.39}, 2),
        ({"grievance": 0.21}, 2),
    ],
    ids=("weak-trust", "low-familiarity", "high-grievance"),
)
def test_threshold_failure_removes_support_and_prevents_candidate(
    changes,
    expected_edges,
):
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    for owner, target in ((1, 2), (2, 1)):
        for name, value in changes.items():
            setattr(people[owner].relationships[target], name, value)

    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    assert result.last_qualifying_reciprocal_edge_count == expected_edges
    assert result.candidates == {}


@pytest.mark.parametrize(
    "edges",
    [
        [(1, 2), (2, 3)],
        [(1, 2), (1, 3), (1, 4), (1, 5)],
    ],
    ids=("chain", "star"),
)
def test_fragile_topologies_create_no_candidate(edges):
    people = population(tuple(sorted({member for edge in edges for member in edge})))
    connect(people, edges)

    _graph, blocks, _articulations = graph_blocks(people)
    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    assert blocks == ()
    assert result.candidates == {}


def test_long_sparse_chain_does_not_recurse_or_mutate_runtime_state():
    recursion_limit = sys.getrecursionlimit()
    n = recursion_limit + 10
    people = population(range(n))
    connect(people, [(index, index + 1) for index in range(n - 1)])
    current = CoalitionRuntimeState()
    before = copy.deepcopy(current)
    rng_before = random.getstate()

    result = transition_informal_coalitions(
        list(people.values()),
        current,
        tick=1,
        config=coalition_config(),
    )

    assert result.candidates == {}
    assert result.active_coalitions == {}
    assert result.candidate_formation_count == 0
    assert current == before
    assert random.getstate() == rng_before
    assert sys.getrecursionlimit() == recursion_limit


def test_long_cycle_is_one_canonical_insertion_independent_candidate():
    recursion_limit = sys.getrecursionlimit()
    n = recursion_limit + 10
    edges = [(index, (index + 1) % n) for index in range(n)]
    forward_people = population(range(n))
    reverse_people = population(range(n))
    connect(forward_people, edges)
    connect(reverse_people, list(reversed(edges)))
    rng_before = random.getstate()

    forward = transition_informal_coalitions(
        list(forward_people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )
    reverse = transition_informal_coalitions(
        list(reverse_people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    expected_members = tuple(range(n))
    assert tuple(forward.candidates) == (expected_members,)
    assert forward.candidates[expected_members].member_ids == expected_members
    assert forward.active_coalitions == {}
    assert canonical_candidate_snapshot(forward) == (
        canonical_candidate_snapshot(reverse)
    )
    assert random.getstate() == rng_before
    assert sys.getrecursionlimit() == recursion_limit


def test_triangle_creates_one_candidate_but_not_one_coalition_immediately():
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])

    first = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(persistence=2),
    )

    assert tuple(first.candidates) == ((1, 2, 3),)
    assert first.active_coalitions == {}
    assert first.candidates[(1, 2, 3)].consecutive_qualifying_observations == 1


def test_persistent_triangle_forms_exactly_once():
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    config = coalition_config(persistence=2)

    first = transition_informal_coalitions(
        list(people.values()), CoalitionRuntimeState(), tick=1, config=config)
    second = transition_informal_coalitions(
        list(people.values()), first, tick=2, config=config)
    third = transition_informal_coalitions(
        list(people.values()), second, tick=3, config=config)

    assert canonical_coalition_snapshot(second) == [{
        "coalition_id": 0,
        "formed_tick": 2,
        "member_ids": [1, 2, 3],
    }]
    assert second.candidate_formation_count == 1
    assert third.candidate_formation_count == 1
    assert third.next_coalition_id == 1


def test_identical_enabled_transitions_have_identical_snapshots():
    first_people = population((1, 2, 3, 4))
    connect(first_people, [(1, 2), (2, 3), (1, 3), (1, 4), (2, 4)])
    second_people = copy.deepcopy(first_people)
    config = coalition_config(persistence=2)
    first_state = CoalitionRuntimeState()
    second_state = CoalitionRuntimeState()

    for tick in (1, 2):
        first_state = transition_informal_coalitions(
            list(first_people.values()), first_state, tick=tick, config=config)
        second_state = transition_informal_coalitions(
            list(reversed(tuple(second_people.values()))),
            second_state,
            tick=tick,
            config=config,
        )

    assert canonical_candidate_snapshot(first_state) == (
        canonical_candidate_snapshot(second_state)
    )
    assert canonical_coalition_snapshot(first_state) == (
        canonical_coalition_snapshot(second_state)
    )


def test_two_triangles_connected_by_bridge_remain_two_candidates():
    people = population((1, 2, 3, 4, 5, 6))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
        (3, 4),
    ])

    _graph, blocks, articulations = graph_blocks(people)
    accepted = resolve_exclusive_support_blocks(blocks)
    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    assert [block.member_ids for block in accepted] == [
        (1, 2, 3),
        (4, 5, 6),
    ]
    assert articulations == (3, 4)
    assert tuple(result.candidates) == ((1, 2, 3), (4, 5, 6))


def test_bow_tie_resolves_to_one_exclusive_canonical_block():
    people = population((1, 2, 3, 4, 5))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (3, 4), (4, 5), (3, 5),
    ])

    _graph, blocks, articulations = graph_blocks(people)
    accepted = resolve_exclusive_support_blocks(blocks)

    assert {block.member_ids for block in blocks} == {
        (1, 2, 3),
        (3, 4, 5),
    }
    assert articulations == (3,)
    assert [block.member_ids for block in accepted] == [(1, 2, 3)]


def test_stronger_overlapping_block_wins_before_lexicographic_order():
    people = population((1, 2, 3, 4, 5))
    for edge in ((1, 2), (2, 3), (1, 3)):
        support(people, *edge, trust=0.50, familiarity=0.50)
    for edge in ((3, 4), (4, 5), (3, 5)):
        support(people, *edge, trust=0.90, familiarity=0.90)

    _graph, blocks, _articulations = graph_blocks(people)
    accepted = resolve_exclusive_support_blocks(blocks)

    assert [block.member_ids for block in accepted] == [(3, 4, 5)]


def test_insertion_order_does_not_change_blocks_or_exclusive_winner():
    edges = [
        (1, 2), (2, 3), (1, 3),
        (3, 4), (4, 5), (3, 5),
    ]

    def accepted(order):
        people = population((1, 2, 3, 4, 5))
        connect(people, order)
        reordered_people = [people[index] for index in (5, 3, 1, 4, 2)]
        graph = build_qualifying_reciprocal_graph(
            reordered_people, tick=1, config=coalition_config())
        blocks, _articulations = vertex_biconnected_support_blocks(
            graph, (5, 4, 3, 2, 1), minimum_size=3)
        return tuple(
            block.member_ids
            for block in resolve_exclusive_support_blocks(blocks)
        )

    assert accepted(edges) == accepted(list(reversed(edges))) == ((1, 2, 3),)


def test_one_support_does_not_join_but_two_supports_do():
    people = population((1, 2, 3, 4))
    connect(people, [(1, 2), (2, 3), (1, 3), (1, 4)])
    current = active_state((1, 2, 3), active_ids=(1, 2, 3, 4))

    one_support = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())
    assert one_support.active_coalitions[0].member_ids == (1, 2, 3)

    support(people, 2, 4)
    two_supports = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())
    assert two_supports.active_coalitions[0].member_ids == (1, 2, 3, 4)


def test_simultaneous_joiners_do_not_create_cascading_eligibility():
    people = population((1, 2, 3, 4, 5))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (1, 4), (2, 4),
        (1, 5), (4, 5),
    ])
    current = active_state((1, 2, 3), active_ids=(1, 2, 3, 4, 5))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions[0].member_ids == (1, 2, 3, 4)
    assert 5 not in result.member_to_coalition


def test_equal_valid_join_support_uses_lowest_coalition_id():
    people = population((1, 2, 3, 4, 5, 6, 7))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
        (1, 7), (2, 7),
        (4, 7), (5, 7),
    ])
    first = InformalCoalition(0, 1, (1, 2, 3))
    second = InformalCoalition(1, 1, (4, 5, 6))
    current = CoalitionRuntimeState(
        active_coalitions={0: first, 1: second},
        member_to_coalition={
            1: 0, 2: 0, 3: 0,
            4: 1, 5: 1, 6: 1,
        },
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=1,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5, 6, 7),
    )

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.member_to_coalition[7] == 0
    assert result.active_coalitions[0].member_ids == (1, 2, 3, 7)
    assert result.active_coalitions[1].member_ids == (4, 5, 6)


def test_two_supports_do_not_rescue_articulation_membership():
    people = population((1, 2, 3, 4, 5, 6))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (3, 4), (4, 5), (3, 5),
        (1, 6), (2, 6),
    ])
    graph = build_qualifying_reciprocal_graph(
        list(people.values()), tick=1, config=coalition_config())
    proposed = active_state((1, 2, 3, 4, 5, 6), last_tick=1)
    proposed.last_qualifying_reciprocal_edge_count = graph.edge_count

    with pytest.raises(
        CoalitionInvariantError,
        match="active_coalition_not_vertex_biconnected",
    ):
        validate_proposed_coalition_state(
            list(people.values()),
            proposed,
            tick=1,
            config=coalition_config(),
            graph=graph,
        )


def test_noncritical_edge_removal_leaves_vertex_biconnected_coalition():
    people = population((1, 2, 3, 4))
    connect(people, [
        (1, 2), (1, 3), (1, 4),
        (2, 3), (2, 4),
    ])  # K4 minus edge 3-4 remains vertex-biconnected.
    current = active_state((1, 2, 3, 4))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions[0].member_ids == (1, 2, 3, 4)
    assert result.split_event_count == 0
    assert result.dissolution_count == 0


def test_critical_support_loss_splits_canonically():
    people = population((1, 2, 3, 4, 5, 6))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
        (3, 4),
    ])
    current = active_state((1, 2, 3, 4, 5, 6))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions[0].member_ids == (1, 2, 3)
    assert result.active_coalitions[1].member_ids == (4, 5, 6)
    assert result.split_event_count == 1
    assert result.split_child_count == 1
    assert result.next_coalition_id == 2


def test_bow_tie_coalition_contracts_to_exclusive_winner():
    people = population((1, 2, 3, 4, 5))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (3, 4), (4, 5), (3, 5),
    ])
    current = active_state((1, 2, 3, 4, 5))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions[0].member_ids == (1, 2, 3)
    assert result.split_event_count == 0
    assert 4 not in result.member_to_coalition
    assert 5 not in result.member_to_coalition


def test_triangle_degraded_to_chain_dissolves():
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3)])
    current = active_state((1, 2, 3))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions == {}
    assert result.dissolution_count == 1
    assert result.next_coalition_id == 1


def test_dead_member_can_dissolve_minimum_size_coalition():
    people = population((1, 2))
    support(people, 1, 2)
    current = active_state((1, 2, 3), active_ids=(1, 2, 3))

    result = transition_informal_coalitions(
        list(people.values()), current, tick=2, config=coalition_config())

    assert result.active_coalitions == {}
    assert result.dissolution_count == 1


def test_relationship_decay_can_dissolve_coalition():
    people = population((1, 2, 3))
    for edge in ((1, 2), (2, 3), (1, 3)):
        support(
            people,
            *edge,
            trust=0.24,
            familiarity=0.40,
            tick=0,
        )
    current = active_state((1, 2, 3), last_tick=24)
    maintain_relationships(
        list(people.values()),
        [],
        tick=25,
        config=SocialMemoryConfig(True, False, 32, 25),
    )

    result = transition_informal_coalitions(
        list(people.values()), current, tick=25, config=coalition_config())

    assert result.last_qualifying_reciprocal_edge_count == 0
    assert result.active_coalitions == {}
    assert result.dissolution_count == 1


def test_split_overflow_becomes_fresh_candidate():
    people = population((1, 2, 3, 4, 5, 6))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
        (3, 4),
    ])
    current = active_state((1, 2, 3, 4, 5, 6))

    result = transition_informal_coalitions(
        list(people.values()),
        current,
        tick=2,
        config=coalition_config(persistence=3, maximum_active=1),
    )

    assert result.active_coalitions[0].member_ids == (1, 2, 3)
    assert tuple(result.candidates) == ((4, 5, 6),)
    assert result.candidates[(4, 5, 6)].consecutive_qualifying_observations == 1
    assert result.split_event_count == 1
    assert result.split_child_count == 0
    assert result.next_coalition_id == 1


def test_overflow_split_child_cannot_join_elsewhere_before_persistence():
    people = population((1, 2, 3, 4, 5, 6, 7, 8, 9))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
        (3, 4),
        (7, 8), (8, 9), (7, 9),
        (4, 7), (4, 8),
    ])
    current = CoalitionRuntimeState(
        active_coalitions={
            0: InformalCoalition(0, 1, (1, 2, 3, 4, 5, 6)),
            1: InformalCoalition(1, 1, (7, 8, 9)),
        },
        member_to_coalition={
            1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0,
            7: 1, 8: 1, 9: 1,
        },
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=1,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5, 6, 7, 8, 9),
    )

    result = transition_informal_coalitions(
        list(people.values()),
        current,
        tick=2,
        config=coalition_config(persistence=3, maximum_active=2),
    )

    assert result.active_coalitions[0].member_ids == (1, 2, 3)
    assert result.active_coalitions[1].member_ids == (7, 8, 9)
    assert tuple(result.candidates) == ((4, 5, 6),)
    assert result.candidates[(4, 5, 6)].consecutive_qualifying_observations == 1


def test_proposed_articulation_coalition_is_rejected():
    people = population((1, 2, 3, 4, 5))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (3, 4), (4, 5), (3, 5),
    ])
    graph = build_qualifying_reciprocal_graph(
        list(people.values()), tick=1, config=coalition_config())
    proposed = active_state((1, 2, 3, 4, 5), last_tick=1)
    proposed.last_qualifying_reciprocal_edge_count = graph.edge_count

    with pytest.raises(
        CoalitionInvariantError,
        match="active_coalition_not_vertex_biconnected",
    ):
        validate_proposed_coalition_state(
            list(people.values()),
            proposed,
            tick=1,
            config=coalition_config(),
            graph=graph,
        )


def test_corruption_rolls_back_and_consumes_no_rng():
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    current = active_state((1, 2, 3))
    current.member_to_coalition = {1: 0, 2: 0}
    before = copy.deepcopy(current)
    rng_before = random.getstate()

    with pytest.raises(
        CoalitionInvariantError,
        match="coalition_membership_index_mismatch",
    ):
        transition_informal_coalitions(
            list(people.values()), current, tick=2, config=coalition_config())

    assert current == before
    assert random.getstate() == rng_before


def test_successful_transition_consumes_no_rng_and_mutates_no_faction_state():
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    people[1].faction = "Formal A"
    people[2].faction = "Formal B"
    people[3].faction = None
    formal_before = tuple(inhabitant.faction for inhabitant in people.values())
    rng_before = random.getstate()

    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(),
    )

    assert result.candidates
    assert random.getstate() == rng_before
    assert tuple(inhabitant.faction for inhabitant in people.values()) == formal_before


@pytest.mark.parametrize(
    ("corrupt", "code"),
    [
        (lambda people: setattr(people[1], "inhabitant_id", None),
         "invalid_active_inhabitant_id"),
        (lambda people: setattr(people[1], "inhabitant_id", True),
         "invalid_active_inhabitant_id"),
        (lambda people: setattr(people[1], "inhabitant_id", -1),
         "invalid_active_inhabitant_id"),
        (lambda people: people[1].relationships.__setitem__(True, Relationship()),
         "invalid_relationship_target"),
        (lambda people: people[1].relationships.__setitem__("2", Relationship()),
         "invalid_relationship_target"),
        (lambda people: people[1].relationships.__setitem__(1, Relationship()),
         "self_targeted_relationship"),
        (lambda people: people[1].relationships.__setitem__(
            2, Relationship(trust=float("nan"))),
         "invalid_relationship_value"),
        (lambda people: people[1].relationships.__setitem__(
            2, Relationship(familiarity=1.01)),
         "invalid_relationship_value"),
    ],
)
def test_corrupt_graph_state_fails_closed(corrupt, code):
    people = population((1, 2, 3))
    corrupt(people)

    with pytest.raises(CoalitionInvariantError, match=code):
        transition_informal_coalitions(
            list(people.values()),
            CoalitionRuntimeState(),
            tick=1,
            config=coalition_config(),
        )


def test_duplicate_active_ids_fail_closed():
    first = person(1)
    duplicate = person(1)

    with pytest.raises(CoalitionInvariantError, match="duplicate_active_inhabitant_id"):
        transition_informal_coalitions(
            [first, duplicate],
            CoalitionRuntimeState(),
            tick=1,
            config=coalition_config(),
        )


def test_regressed_coalition_allocator_fails_closed():
    current = CoalitionRuntimeState(
        next_coalition_id=0,
        candidate_formation_count=1,
        last_observation_tick=1,
        last_active_inhabitant_ids=(),
    )

    with pytest.raises(CoalitionInvariantError, match="regressed_coalition_allocator"):
        transition_informal_coalitions(
            [], current, tick=2, config=coalition_config())


def test_proposed_state_cannot_reuse_a_retired_coalition_id():
    people = population((1, 2, 3, 4, 5, 6))
    connect(people, [
        (1, 2), (2, 3), (1, 3),
        (4, 5), (5, 6), (4, 6),
    ])
    previous_coalition = InformalCoalition(1, 1, (4, 5, 6))
    previous = CoalitionRuntimeState(
        active_coalitions={1: previous_coalition},
        member_to_coalition={4: 1, 5: 1, 6: 1},
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=1,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
    )
    proposed = CoalitionRuntimeState(
        active_coalitions={
            0: InformalCoalition(0, 2, (1, 2, 3)),
            1: previous_coalition,
        },
        member_to_coalition={
            1: 0, 2: 0, 3: 0,
            4: 1, 5: 1, 6: 1,
        },
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=2,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5, 6),
        last_qualifying_reciprocal_edge_count=6,
    )

    with pytest.raises(CoalitionInvariantError, match="reused_coalition_id"):
        validate_proposed_coalition_state(
            list(people.values()),
            proposed,
            tick=2,
            config=coalition_config(),
            previous_state=previous,
        )


def test_backward_observation_tick_is_rejected_without_mutation():
    current = CoalitionRuntimeState(
        last_observation_tick=2,
        last_active_inhabitant_ids=(),
    )
    before = copy.deepcopy(current)

    with pytest.raises(
        CoalitionInvariantError,
        match="nonincreasing_coalition_observation_tick",
    ):
        transition_informal_coalitions(
            [], current, tick=2, config=coalition_config())

    assert current == before


def test_candidate_state_remains_exclusive_and_bounded():
    people = population(range(30))
    for start in range(0, 30, 3):
        connect(people, [
            (start, start + 1),
            (start + 1, start + 2),
            (start, start + 2),
        ])

    result = transition_informal_coalitions(
        list(people.values()),
        CoalitionRuntimeState(),
        tick=1,
        config=coalition_config(persistence=5),
    )
    all_candidate_members = [
        member
        for candidate in result.candidates.values()
        for member in candidate.member_ids
    ]

    assert len(result.candidates) == 10
    assert len(all_candidate_members) == len(set(all_candidate_members)) == 30
    assert len(result.candidates) <= len(people) // 3


def test_candidate_membership_change_resets_persistence():
    people = population((1, 2, 3, 4))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    config = coalition_config(persistence=3)
    first = transition_informal_coalitions(
        list(people.values()), CoalitionRuntimeState(), tick=1, config=config)
    second = transition_informal_coalitions(
        list(people.values()), first, tick=2, config=config)
    support(people, 1, 4)
    support(people, 2, 4)

    changed = transition_informal_coalitions(
        list(people.values()), second, tick=3, config=config)

    assert tuple(changed.candidates) == ((1, 2, 3, 4),)
    assert changed.candidates[(1, 2, 3, 4)].consecutive_qualifying_observations == 1


def test_candidate_object_cannot_overlap_active_membership():
    current = active_state((1, 2, 3), active_ids=(1, 2, 3, 4, 5))
    current.candidates[(3, 4, 5)] = CoalitionCandidate(
        (3, 4, 5), 1, 1, 1)

    with pytest.raises(CoalitionInvariantError, match="candidate_active_overlap"):
        transition_informal_coalitions(
            list(population((1, 2, 3, 4, 5)).values()),
            current,
            tick=2,
            config=coalition_config(),
        )


@pytest.mark.parametrize(
    "members",
    [
        (2, 1, 3),
        (1, 1, 2),
    ],
    ids=("noncanonical", "duplicate"),
)
def test_malformed_coalition_member_tuples_fail_closed(members):
    current = active_state(members, active_ids=(1, 2, 3))

    with pytest.raises(CoalitionInvariantError, match="invalid_coalition_members"):
        transition_informal_coalitions(
            list(population((1, 2, 3)).values()),
            current,
            tick=2,
            config=coalition_config(),
        )


def test_duplicate_membership_across_coalitions_fails_closed():
    current = CoalitionRuntimeState(
        active_coalitions={
            0: InformalCoalition(0, 1, (1, 2, 3)),
            1: InformalCoalition(1, 1, (3, 4, 5)),
        },
        member_to_coalition={1: 0, 2: 0, 3: 0, 4: 1, 5: 1},
        next_coalition_id=2,
        candidate_formation_count=2,
        last_observation_tick=1,
        last_active_inhabitant_ids=(1, 2, 3, 4, 5),
    )

    with pytest.raises(CoalitionInvariantError, match="duplicate_coalition_membership"):
        transition_informal_coalitions(
            list(population((1, 2, 3, 4, 5)).values()),
            current,
            tick=2,
            config=coalition_config(),
        )


@pytest.mark.parametrize("record_type", ["candidate", "coalition"])
def test_proposed_membership_cannot_contain_inactive_ids(record_type):
    people = population((1, 2, 3))
    connect(people, [(1, 2), (2, 3), (1, 3)])
    if record_type == "candidate":
        proposed = CoalitionRuntimeState(
            candidates={
                (1, 2, 4): CoalitionCandidate((1, 2, 4), 1, 1, 1),
            },
            last_observation_tick=1,
            last_active_inhabitant_ids=(1, 2, 3),
            last_qualifying_reciprocal_edge_count=3,
        )
        expected = "inactive_candidate_member"
    else:
        proposed = CoalitionRuntimeState(
            active_coalitions={0: InformalCoalition(0, 1, (1, 2, 4))},
            member_to_coalition={1: 0, 2: 0, 4: 0},
            next_coalition_id=1,
            candidate_formation_count=1,
            last_observation_tick=1,
            last_active_inhabitant_ids=(1, 2, 3),
            last_qualifying_reciprocal_edge_count=3,
        )
        expected = "inactive_coalition_member"

    with pytest.raises(CoalitionInvariantError, match=expected):
        validate_proposed_coalition_state(
            list(people.values()),
            proposed,
            tick=1,
            config=coalition_config(),
        )
