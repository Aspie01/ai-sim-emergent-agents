"""Deterministic informal coalitions derived from authentic social topology.

Coalitions are descriptive engineering-only state.  This module consumes no
randomness and does not import or mutate formal faction behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Protocol

from .social import Relationship


class CoalitionConfig(Protocol):
    """Effective controls required by coalition processing."""

    coalition_emergence_enabled: bool
    coalition_minimum_size: int
    coalition_trust_threshold: float
    coalition_familiarity_threshold: float
    coalition_maximum_grievance: float
    coalition_persistence_ticks: int
    maximum_active_coalitions: int


class CoalitionInhabitant(Protocol):
    """Minimal inhabitant interface required by coalition processing."""

    inhabitant_id: int | None
    relationships: dict[int, Relationship]


class CoalitionInvariantError(ValueError):
    """Raised when relationship or coalition state violates a closed invariant."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class CoalitionCommunicationContext(str, Enum):
    """Closed coalition contexts for one authentic language occurrence."""

    SAME_ACTIVE_COALITION = "same_active_coalition"
    DIFFERENT_ACTIVE_COALITIONS = "different_active_coalitions"
    ASSIGNED_UNASSIGNED = "assigned_unassigned"
    BOTH_UNASSIGNED = "both_unassigned"


_COALITION_SNAPSHOT_FACTORY_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class CoalitionMembershipSnapshot:
    """Validated immutable coalition membership for one economy tick.

    Instances can be created only by ``build_coalition_membership_snapshot``.
    The mapping proxy owns a private copied dictionary; no caller-owned
    coalition collection or member tuple is retained.
    """

    snapshot_tick: int
    source_observation_tick: int | None
    active_coalition_ids: tuple[int, ...]
    active_inhabitant_ids: tuple[int, ...]
    lineage: tuple[int, int, int]
    _active_inhabitant_id_set: frozenset[int]
    _member_to_coalition: Mapping[int, int]
    _factory_token: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        _raise(
            "forged_coalition_membership_snapshot",
            "snapshot construction is restricted to the validated factory",
        )


def _create_coalition_membership_snapshot(
    *,
    snapshot_tick: int,
    source_observation_tick: int | None,
    active_coalition_ids: tuple[int, ...],
    active_inhabitant_ids: tuple[int, ...],
    lineage: tuple[int, int, int],
    member_to_coalition: dict[int, int],
) -> CoalitionMembershipSnapshot:
    """Create one capability after the public builder validates all inputs."""
    result = object.__new__(CoalitionMembershipSnapshot)
    private_membership = dict(member_to_coalition)
    object.__setattr__(result, "snapshot_tick", snapshot_tick)
    object.__setattr__(
        result, "source_observation_tick", source_observation_tick)
    object.__setattr__(
        result, "active_coalition_ids", tuple(active_coalition_ids))
    object.__setattr__(
        result, "active_inhabitant_ids", tuple(active_inhabitant_ids))
    object.__setattr__(result, "lineage", tuple(lineage))
    object.__setattr__(
        result,
        "_active_inhabitant_id_set",
        frozenset(active_inhabitant_ids),
    )
    object.__setattr__(
        result,
        "_member_to_coalition",
        MappingProxyType(private_membership),
    )
    object.__setattr__(
        result, "_factory_token", _COALITION_SNAPSHOT_FACTORY_TOKEN)
    return result


@dataclass(frozen=True, slots=True)
class CoalitionCommunicationClassification:
    """Constant-size result of classifying one sender and receiver."""

    context: CoalitionCommunicationContext
    sender_coalition_id: int | None
    receiver_coalition_id: int | None


@dataclass(frozen=True, slots=True)
class CoalitionCandidate:
    """Bounded persistence for one exact accepted support block."""

    member_ids: tuple[int, ...]
    first_qualified_tick: int
    consecutive_qualifying_observations: int
    last_qualified_tick: int


@dataclass(frozen=True, slots=True)
class InformalCoalition:
    """One active exclusive informal coalition."""

    coalition_id: int
    formed_tick: int
    member_ids: tuple[int, ...]


@dataclass(slots=True)
class CoalitionRuntimeState:
    """Complete run-scoped coalition state replaced atomically per observation."""

    candidates: dict[tuple[int, ...], CoalitionCandidate] = field(
        default_factory=dict
    )
    active_coalitions: dict[int, InformalCoalition] = field(
        default_factory=dict
    )
    member_to_coalition: dict[int, int] = field(default_factory=dict)
    next_coalition_id: int = 0
    candidate_formation_count: int = 0
    split_event_count: int = 0
    split_child_count: int = 0
    dissolution_count: int = 0
    last_observation_tick: int | None = None
    last_active_inhabitant_ids: tuple[int, ...] = ()
    last_qualifying_reciprocal_edge_count: int = 0


@dataclass(frozen=True, slots=True)
class CoalitionSummary:
    """Canonical bounded observability for tests and internal inspection."""

    qualifying_reciprocal_edge_count: int
    candidate_count: int
    active_coalition_count: int
    coalition_sizes: tuple[tuple[int, int], ...]
    coalition_memberships: tuple[tuple[int, tuple[int, ...]], ...]
    formation_count: int
    split_count: int
    dissolution_count: int


@dataclass(frozen=True, slots=True)
class SupportBlock:
    """One canonical maximal vertex-biconnected block."""

    member_ids: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    support_strength: int


@dataclass(frozen=True, slots=True)
class ReciprocalGraph:
    """Canonical sparse reciprocal support graph."""

    adjacency: dict[int, tuple[int, ...]]
    edge_strengths: dict[tuple[int, int], int]

    @property
    def edge_count(self) -> int:
        return len(self.edge_strengths)


@dataclass(slots=True)
class _TarjanFrame:
    """One explicit DFS activation for iterative Tarjan traversal."""

    vertex: int
    parent_vertex: int | None
    neighbors: tuple[int, ...]
    entered_edge: tuple[int, int] | None
    next_neighbor_index: int = 0
    child_count: int = 0


_RELATIONSHIP_DOMAINS = (
    ("trust", -1.0, 1.0),
    ("affinity", -1.0, 1.0),
    ("grievance", 0.0, 1.0),
    ("obligation", 0.0, 1.0),
    ("familiarity", 0.0, 1.0),
)


def _raise(code: str, detail: str) -> None:
    raise CoalitionInvariantError(code, detail)


def _is_exact_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _canonical_member_tuple(
    value: object,
    *,
    code: str,
) -> tuple[int, ...]:
    if type(value) is not tuple:
        _raise(code, "members must be an exact tuple")
    members = value
    if any(not _is_exact_nonnegative_int(member) for member in members):
        _raise(code, "members must be nonnegative integer IDs")
    if tuple(sorted(members)) != members or len(members) != len(set(members)):
        _raise(code, "members must be strictly increasing and unique")
    return members


def _validate_config(config: CoalitionConfig) -> None:
    if type(config.coalition_emergence_enabled) is not bool:
        _raise("invalid_coalition_config", "emergence setting must be boolean")
    if (
        type(config.coalition_minimum_size) is not int
        or not 3 <= config.coalition_minimum_size <= 1024
    ):
        _raise("invalid_coalition_config", "minimum size must be at least 3")
    for value, name in (
        (config.coalition_trust_threshold, "trust threshold"),
        (config.coalition_familiarity_threshold, "familiarity threshold"),
        (config.coalition_maximum_grievance, "maximum grievance"),
    ):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            _raise("invalid_coalition_config", f"{name} is invalid")
    if (
        type(config.coalition_persistence_ticks) is not int
        or config.coalition_persistence_ticks < 2
    ):
        _raise("invalid_coalition_config", "persistence must be at least 2")
    if (
        type(config.maximum_active_coalitions) is not int
        or not 1 <= config.maximum_active_coalitions <= 1024
    ):
        _raise("invalid_coalition_config", "active coalition cap must be positive")


def _validate_relationship_record(
    record: object,
    *,
    owner_id: int,
    target_id: int,
    observation_tick: int,
) -> Relationship:
    if not isinstance(record, Relationship):
        _raise(
            "invalid_relationship_record",
            f"relationship {owner_id}->{target_id} has an invalid record type",
        )
    for name, lower, upper in _RELATIONSHIP_DOMAINS:
        value = getattr(record, name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not lower <= float(value) <= upper
        ):
            _raise(
                "invalid_relationship_value",
                f"relationship {owner_id}->{target_id} has invalid {name}",
            )
    if (
        type(record.interaction_count) is not int
        or record.interaction_count < 0
    ):
        _raise(
            "invalid_relationship_interaction_count",
            f"relationship {owner_id}->{target_id} has an invalid interaction count",
        )
    if (
        type(record.last_interaction_tick) is not int
        or not 0 <= record.last_interaction_tick <= observation_tick
    ):
        _raise(
            "invalid_relationship_tick",
            f"relationship {owner_id}->{target_id} has an invalid interaction tick",
        )
    return record


def _validate_people_and_relationships(
    people: list[CoalitionInhabitant],
    *,
    observation_tick: int,
) -> dict[int, CoalitionInhabitant]:
    invalid_ids = [
        getattr(inhabitant, "inhabitant_id", None)
        for inhabitant in people
        if not _is_exact_nonnegative_int(
            getattr(inhabitant, "inhabitant_id", None)
        )
    ]
    if invalid_ids:
        rendered = sorted(
            (type(value).__name__, repr(value)) for value in invalid_ids
        )
        _raise("invalid_active_inhabitant_id", f"invalid IDs: {rendered}")

    ids = [inhabitant.inhabitant_id for inhabitant in people]
    id_counts: dict[int, int] = {}
    for inhabitant_id in ids:
        id_counts[inhabitant_id] = id_counts.get(inhabitant_id, 0) + 1
    duplicates = sorted(
        inhabitant_id
        for inhabitant_id, count in id_counts.items()
        if count > 1
    )
    if duplicates:
        _raise("duplicate_active_inhabitant_id", f"duplicate IDs: {duplicates}")

    by_id = {
        inhabitant.inhabitant_id: inhabitant
        for inhabitant in people
    }
    active_ids = frozenset(by_id)
    for owner_id in sorted(by_id):
        relationships = getattr(by_id[owner_id], "relationships", None)
        if type(relationships) is not dict:
            _raise(
                "invalid_relationship_store",
                f"inhabitant {owner_id} relationships must be an exact dict",
            )
        malformed_keys = [
            key
            for key in relationships
            if type(key) is not int or key < 0
        ]
        if malformed_keys:
            rendered = sorted(
                (type(value).__name__, repr(value))
                for value in malformed_keys
            )
            _raise(
                "invalid_relationship_target",
                f"inhabitant {owner_id} has malformed targets: {rendered}",
            )
        for target_id in sorted(relationships):
            if target_id == owner_id:
                _raise(
                    "self_targeted_relationship",
                    f"inhabitant {owner_id} targets itself",
                )
            if target_id not in active_ids:
                _raise(
                    "inactive_relationship_target",
                    f"relationship {owner_id}->{target_id} targets an inactive ID",
                )
            _validate_relationship_record(
                relationships[target_id],
                owner_id=owner_id,
                target_id=target_id,
                observation_tick=observation_tick,
            )
    return by_id


def _quantized(value: float) -> int:
    return int(round(value * 1_000_000))


def _edge_strength(first: Relationship, second: Relationship) -> int:
    return (
        _quantized(min(first.trust, second.trust))
        + _quantized(min(first.familiarity, second.familiarity))
        - _quantized(max(first.grievance, second.grievance))
    )


def _records_qualify(
    first: Relationship,
    second: Relationship,
    config: CoalitionConfig,
    intelligibility_threshold: float | None = None,
) -> bool:
    """Report whether one reciprocal tie may carry a coalition edge.

    ``intelligibility_threshold`` is supplied only when coalition
    intelligibility gating is effective. Both directions must clear it, so a
    pair that cannot understand each other does not coalesce, and a coalition
    whose members lose mutual intelligibility stops qualifying and dissolves
    through the ordinary persistence path rather than a separate teardown.

    The threshold is strictly positive by configuration, so a tie with no
    communication history sits at exactly 0.0 and silence never counts as
    understanding.
    """
    if not (
        first.interaction_count > 0
        and second.interaction_count > 0
        and first.trust >= config.coalition_trust_threshold
        and second.trust >= config.coalition_trust_threshold
        and first.familiarity >= config.coalition_familiarity_threshold
        and second.familiarity >= config.coalition_familiarity_threshold
        and first.grievance <= config.coalition_maximum_grievance
        and second.grievance <= config.coalition_maximum_grievance
    ):
        return False
    if intelligibility_threshold is None:
        return True
    return (
        first.intelligibility >= intelligibility_threshold
        and second.intelligibility >= intelligibility_threshold
    )


def build_qualifying_reciprocal_graph(
    people: list[CoalitionInhabitant],
    *,
    tick: int,
    config: CoalitionConfig,
    intelligibility_threshold: float | None = None,
) -> ReciprocalGraph:
    """Validate and build the canonical threshold-qualified reciprocal graph."""
    _validate_config(config)
    if not _is_exact_nonnegative_int(tick):
        _raise("invalid_observation_tick", "tick must be a nonnegative integer")
    by_id = _validate_people_and_relationships(
        people, observation_tick=tick)
    adjacency_sets = {inhabitant_id: set() for inhabitant_id in by_id}
    edge_strengths: dict[tuple[int, int], int] = {}
    for owner_id in sorted(by_id):
        owner = by_id[owner_id]
        for target_id in sorted(owner.relationships):
            if owner_id >= target_id:
                continue
            reciprocal = by_id[target_id].relationships.get(owner_id)
            if reciprocal is None:
                continue
            first = owner.relationships[target_id]
            if not _records_qualify(
                first, reciprocal, config, intelligibility_threshold
            ):
                continue
            edge = (owner_id, target_id)
            adjacency_sets[owner_id].add(target_id)
            adjacency_sets[target_id].add(owner_id)
            edge_strengths[edge] = _edge_strength(first, reciprocal)
    return ReciprocalGraph(
        adjacency={
            inhabitant_id: tuple(sorted(neighbors))
            for inhabitant_id, neighbors in sorted(adjacency_sets.items())
        },
        edge_strengths=dict(sorted(edge_strengths.items())),
    )


def vertex_biconnected_support_blocks(
    graph: ReciprocalGraph,
    member_ids: tuple[int, ...] | list[int] | set[int] | frozenset[int],
    *,
    minimum_size: int,
) -> tuple[tuple[SupportBlock, ...], tuple[int, ...]]:
    """Return canonical maximal vertex-biconnected blocks and articulations."""
    allowed = frozenset(member_ids)
    if any(type(member) is not int or member < 0 for member in allowed):
        _raise("invalid_block_vertex", "block vertices must be nonnegative IDs")
    if not allowed <= graph.adjacency.keys():
        _raise("inactive_block_vertex", "block vertices must exist in the graph")
    if type(minimum_size) is not int or minimum_size < 1:
        _raise("invalid_block_minimum", "minimum block size must be positive")

    discovery: dict[int, int] = {}
    low: dict[int, int] = {}
    parent: dict[int, int | None] = {}
    edge_stack: list[tuple[int, int]] = []
    blocks: list[SupportBlock] = []
    articulations: set[int] = set()
    counter = 0

    def emit_block(stop_edge: tuple[int, int]) -> None:
        popped: list[tuple[int, int]] = []
        while edge_stack:
            edge = edge_stack.pop()
            popped.append(edge)
            if edge == stop_edge:
                break
        if not popped or stop_edge not in popped:
            _raise("invalid_tarjan_stack", "support-block edge stack is inconsistent")
        edges = tuple(sorted(set(popped)))
        members = tuple(sorted({member for edge in edges for member in edge}))
        if len(members) < minimum_size:
            return
        blocks.append(SupportBlock(
            member_ids=members,
            edges=edges,
            support_strength=sum(graph.edge_strengths[edge] for edge in edges),
        ))

    def make_frame(
        vertex: int,
        parent_vertex: int | None,
        entered_edge: tuple[int, int] | None,
    ) -> _TarjanFrame:
        nonlocal counter
        counter += 1
        discovery[vertex] = counter
        low[vertex] = counter
        parent[vertex] = parent_vertex
        return _TarjanFrame(
            vertex=vertex,
            parent_vertex=parent_vertex,
            neighbors=tuple(sorted(
                neighbor
                for neighbor in graph.adjacency[vertex]
                if neighbor in allowed
            )),
            entered_edge=entered_edge,
        )

    def visit_iteratively(root: int) -> None:
        frames = [make_frame(root, None, None)]
        while frames:
            frame = frames[-1]
            vertex = frame.vertex
            if frame.next_neighbor_index < len(frame.neighbors):
                neighbor = frame.neighbors[frame.next_neighbor_index]
                frame.next_neighbor_index += 1
                edge = (min(vertex, neighbor), max(vertex, neighbor))
                if neighbor not in discovery:
                    frame.child_count += 1
                    edge_stack.append(edge)
                    frames.append(make_frame(neighbor, vertex, edge))
                elif (
                    neighbor != parent[vertex]
                    and discovery[neighbor] < discovery[vertex]
                ):
                    edge_stack.append(edge)
                    low[vertex] = min(low[vertex], discovery[neighbor])
                continue

            frames.pop()
            parent_vertex = frame.parent_vertex
            if parent_vertex is None:
                continue
            if not frames or frames[-1].vertex != parent_vertex:
                _raise(
                    "invalid_tarjan_stack",
                    "support-block DFS frame stack is inconsistent",
                )
            tree_edge = frame.entered_edge
            if tree_edge is None:
                _raise(
                    "invalid_tarjan_stack",
                    "support-block child frame has no entering edge",
                )
            parent_frame = frames[-1]
            low[parent_vertex] = min(low[parent_vertex], low[vertex])
            if low[vertex] >= discovery[parent_vertex]:
                if (
                    parent[parent_vertex] is not None
                    or parent_frame.child_count > 1
                ):
                    articulations.add(parent_vertex)
                emit_block(tree_edge)

    for root in sorted(allowed):
        if root in discovery:
            continue
        visit_iteratively(root)
        if edge_stack:
            _raise("invalid_tarjan_stack", "support-block edge stack was not drained")

    canonical_blocks = tuple(sorted(
        blocks,
        key=lambda block: (block.member_ids, block.edges),
    ))
    return canonical_blocks, tuple(sorted(articulations))


def _block_priority(block: SupportBlock) -> tuple[object, ...]:
    return (-len(block.member_ids), -block.support_strength, block.member_ids)


def resolve_exclusive_support_blocks(
    blocks: tuple[SupportBlock, ...] | list[SupportBlock],
) -> tuple[SupportBlock, ...]:
    """Accept highest-priority blocks without overlapping membership."""
    claimed: set[int] = set()
    accepted: list[SupportBlock] = []
    for block in sorted(blocks, key=_block_priority):
        if claimed.intersection(block.member_ids):
            continue
        accepted.append(block)
        claimed.update(block.member_ids)
    return tuple(accepted)


def _membership_is_one_support_block(
    graph: ReciprocalGraph,
    members: tuple[int, ...],
    *,
    minimum_size: int,
) -> bool:
    blocks, articulations = vertex_biconnected_support_blocks(
        graph, members, minimum_size=minimum_size)
    return (
        not articulations
        and len(blocks) == 1
        and blocks[0].member_ids == members
    )


def _validate_runtime_structure(
    runtime: CoalitionRuntimeState,
    *,
    allowed_ids: frozenset[int],
    config: CoalitionConfig,
    expected_last_tick: int | None,
) -> None:
    if not isinstance(runtime, CoalitionRuntimeState):
        _raise("invalid_coalition_runtime", "runtime has an invalid type")
    if type(runtime.candidates) is not dict:
        _raise("invalid_candidate_store", "candidate store must be an exact dict")
    if type(runtime.active_coalitions) is not dict:
        _raise("invalid_coalition_store", "active store must be an exact dict")
    if type(runtime.member_to_coalition) is not dict:
        _raise(
            "invalid_coalition_membership_index",
            "membership index must be an exact dict",
        )
    for value, name in (
        (runtime.next_coalition_id, "next coalition ID"),
        (runtime.candidate_formation_count, "candidate formation count"),
        (runtime.split_event_count, "split event count"),
        (runtime.split_child_count, "split child count"),
        (runtime.dissolution_count, "dissolution count"),
        (
            runtime.last_qualifying_reciprocal_edge_count,
            "qualifying reciprocal edge count",
        ),
    ):
        if not _is_exact_nonnegative_int(value):
            _raise("invalid_coalition_counter", f"{name} is invalid")
    if runtime.next_coalition_id != (
        runtime.candidate_formation_count + runtime.split_child_count
    ):
        _raise(
            "regressed_coalition_allocator",
            "next coalition ID disagrees with issued-ID counters",
        )
    if runtime.last_observation_tick != expected_last_tick:
        _raise(
            "invalid_coalition_observation_tick",
            "runtime observation tick is inconsistent",
        )
    active_snapshot = _canonical_member_tuple(
        runtime.last_active_inhabitant_ids,
        code="invalid_active_id_snapshot",
    )
    if frozenset(active_snapshot) != allowed_ids:
        _raise(
            "invalid_active_id_snapshot",
            "runtime active-ID snapshot is inconsistent",
        )
    if len(runtime.active_coalitions) > config.maximum_active_coalitions:
        _raise("coalition_capacity_exceeded", "active coalition cap exceeded")

    invalid_coalition_keys = [
        key
        for key in runtime.active_coalitions
        if not _is_exact_nonnegative_int(key)
    ]
    if invalid_coalition_keys:
        rendered = sorted(
            (type(value).__name__, repr(value))
            for value in invalid_coalition_keys
        )
        _raise("invalid_coalition_id", f"invalid coalition keys: {rendered}")

    claimed_active: set[int] = set()
    derived_membership: dict[int, int] = {}
    for coalition_id in sorted(runtime.active_coalitions):
        if not _is_exact_nonnegative_int(coalition_id):
            _raise("invalid_coalition_id", "coalition key is invalid")
        coalition = runtime.active_coalitions[coalition_id]
        if not isinstance(coalition, InformalCoalition):
            _raise("invalid_coalition_record", "active coalition record is invalid")
        if coalition.coalition_id != coalition_id:
            _raise("coalition_id_mismatch", "coalition key and record disagree")
        if coalition_id >= runtime.next_coalition_id:
            _raise("reused_coalition_id", "active coalition ID was not issued")
        if not _is_exact_nonnegative_int(coalition.formed_tick):
            _raise("invalid_coalition_formed_tick", "formed tick is invalid")
        if (
            expected_last_tick is not None
            and coalition.formed_tick > expected_last_tick
        ):
            _raise(
                "invalid_coalition_formed_tick",
                "formed tick follows the runtime observation",
            )
        members = _canonical_member_tuple(
            coalition.member_ids,
            code="invalid_coalition_members",
        )
        if len(members) < config.coalition_minimum_size:
            _raise("undersized_active_coalition", "active coalition is undersized")
        if not frozenset(members) <= allowed_ids:
            _raise("inactive_coalition_member", "coalition contains an unknown ID")
        overlap = claimed_active.intersection(members)
        if overlap:
            _raise(
                "duplicate_coalition_membership",
                f"members claimed more than once: {sorted(overlap)}",
            )
        claimed_active.update(members)
        derived_membership.update({member: coalition_id for member in members})

    invalid_membership_items = [
        (member, coalition_id)
        for member, coalition_id in runtime.member_to_coalition.items()
        if (
            not _is_exact_nonnegative_int(member)
            or not _is_exact_nonnegative_int(coalition_id)
        )
    ]
    if invalid_membership_items:
        _raise(
            "invalid_coalition_membership_index",
            "membership index contains malformed IDs",
        )
    if runtime.member_to_coalition != derived_membership:
        _raise(
            "coalition_membership_index_mismatch",
            "member-to-coalition index disagrees with active records",
        )

    canonical_candidate_keys = [
        _canonical_member_tuple(key, code="invalid_candidate_members")
        for key in runtime.candidates
    ]
    claimed_candidates: set[int] = set()
    for members in sorted(canonical_candidate_keys):
        key = members
        candidate = runtime.candidates[key]
        if not isinstance(candidate, CoalitionCandidate):
            _raise("invalid_candidate_record", "candidate record is invalid")
        if candidate.member_ids != members:
            _raise("candidate_key_mismatch", "candidate key and record disagree")
        if len(members) < config.coalition_minimum_size:
            _raise("undersized_candidate", "candidate is undersized")
        if not frozenset(members) <= allowed_ids:
            _raise("inactive_candidate_member", "candidate contains an unknown ID")
        if claimed_active.intersection(members):
            _raise("candidate_active_overlap", "candidate overlaps active membership")
        overlap = claimed_candidates.intersection(members)
        if overlap:
            _raise(
                "overlapping_candidates",
                f"candidates overlap at IDs: {sorted(overlap)}",
            )
        claimed_candidates.update(members)
        if (
            not _is_exact_nonnegative_int(candidate.first_qualified_tick)
            or not _is_exact_nonnegative_int(candidate.last_qualified_tick)
            or candidate.first_qualified_tick > candidate.last_qualified_tick
        ):
            _raise("invalid_candidate_tick", "candidate ticks are invalid")
        if expected_last_tick is not None and (
            candidate.last_qualified_tick != expected_last_tick
        ):
            _raise("stale_candidate_tick", "candidate was not observed last tick")
        if (
            type(candidate.consecutive_qualifying_observations) is not int
            or not 1
            <= candidate.consecutive_qualifying_observations
            <= config.coalition_persistence_ticks
        ):
            _raise(
                "invalid_candidate_persistence",
                "candidate persistence is out of bounds",
            )


def coalition_runtime_is_pristine(runtime: object) -> bool:
    """Return whether runtime has the exact pre-observation state."""
    return type(runtime) is CoalitionRuntimeState and (
        runtime.candidates == {}
        and runtime.active_coalitions == {}
        and runtime.member_to_coalition == {}
        and runtime.next_coalition_id == 0
        and type(runtime.next_coalition_id) is int
        and runtime.candidate_formation_count == 0
        and type(runtime.candidate_formation_count) is int
        and runtime.split_event_count == 0
        and type(runtime.split_event_count) is int
        and runtime.split_child_count == 0
        and type(runtime.split_child_count) is int
        and runtime.dissolution_count == 0
        and type(runtime.dissolution_count) is int
        and runtime.last_observation_tick is None
        and runtime.last_active_inhabitant_ids == ()
        and runtime.last_qualifying_reciprocal_edge_count == 0
        and type(runtime.last_qualifying_reciprocal_edge_count) is int
    )


def build_coalition_membership_snapshot(
    runtime: CoalitionRuntimeState,
    *,
    snapshot_tick: int,
    active_inhabitant_ids: tuple[int, ...],
    config: CoalitionConfig,
) -> CoalitionMembershipSnapshot:
    """Fully validate and privately copy membership once for an economy tick."""
    _validate_config(config)
    if not config.coalition_emergence_enabled:
        _raise(
            "coalition_processing_disabled",
            "dialect snapshots require effective coalition emergence",
        )
    if type(snapshot_tick) is not int or snapshot_tick < 1:
        _raise(
            "invalid_coalition_snapshot_tick",
            "snapshot tick must be a positive exact integer",
        )
    if type(active_inhabitant_ids) is not tuple:
        _raise(
            "invalid_coalition_snapshot_active_ids",
            "current active IDs must be supplied as an exact tuple",
        )
    if any(
        not _is_exact_nonnegative_int(member)
        for member in active_inhabitant_ids
    ):
        _raise(
            "invalid_coalition_snapshot_active_ids",
            "current active IDs must be nonnegative exact integers",
        )
    if len(active_inhabitant_ids) != len(set(active_inhabitant_ids)):
        _raise(
            "invalid_coalition_snapshot_active_ids",
            "current active IDs must be unique",
        )
    current_active_ids = tuple(sorted(
        member for member in active_inhabitant_ids
    ))
    if type(runtime) is not CoalitionRuntimeState:
        _raise("invalid_coalition_runtime", "runtime has an invalid exact type")
    previous_active_ids = _canonical_member_tuple(
        runtime.last_active_inhabitant_ids,
        code="invalid_active_id_snapshot",
    )
    _validate_runtime_structure(
        runtime,
        allowed_ids=frozenset(previous_active_ids),
        config=config,
        expected_last_tick=runtime.last_observation_tick,
    )

    if snapshot_tick == 1:
        if not coalition_runtime_is_pristine(runtime):
            _raise(
                "nonpristine_initial_coalition_snapshot",
                "the first dialect tick requires pristine coalition state",
            )
    elif runtime.last_observation_tick != snapshot_tick - 1:
        _raise(
            "stale_coalition_membership_snapshot",
            "coalition observation must be the immediately preceding tick",
        )

    return _create_coalition_membership_snapshot(
        snapshot_tick=snapshot_tick,
        source_observation_tick=runtime.last_observation_tick,
        active_coalition_ids=tuple(sorted(runtime.active_coalitions)),
        active_inhabitant_ids=current_active_ids,
        lineage=(
            runtime.next_coalition_id,
            runtime.candidate_formation_count,
            runtime.split_child_count,
        ),
        member_to_coalition=runtime.member_to_coalition,
    )


def validate_coalition_membership_snapshot(
    snapshot: object,
    *,
    tick: int,
) -> CoalitionMembershipSnapshot:
    """Perform only constant-time capability and freshness validation."""
    if type(snapshot) is not CoalitionMembershipSnapshot:
        _raise(
            "invalid_coalition_membership_snapshot",
            "snapshot must have the exact validated snapshot type",
        )
    if snapshot._factory_token is not _COALITION_SNAPSHOT_FACTORY_TOKEN:
        _raise(
            "forged_coalition_membership_snapshot",
            "snapshot lacks validated factory provenance",
        )
    if (
        type(snapshot.snapshot_tick) is not int
        or type(tick) is not int
        or tick < 1
        or snapshot.snapshot_tick != tick
    ):
        _raise(
            "stale_coalition_membership_snapshot",
            "snapshot tick does not match the communication tick",
        )
    if (
        (
            snapshot.source_observation_tick is not None
            and type(snapshot.source_observation_tick) is not int
        )
        or (tick == 1 and snapshot.source_observation_tick is not None)
        or (
            tick > 1
            and snapshot.source_observation_tick != tick - 1
        )
    ):
        _raise(
            "stale_coalition_membership_snapshot",
            "snapshot source observation is not immediately preceding",
        )
    if (
        type(snapshot.active_coalition_ids) is not tuple
        or type(snapshot.active_inhabitant_ids) is not tuple
        or type(snapshot.lineage) is not tuple
        or len(snapshot.lineage) != 3
        or type(snapshot._active_inhabitant_id_set) is not frozenset
        or type(snapshot._member_to_coalition) is not MappingProxyType
        or len(snapshot._active_inhabitant_id_set)
        != len(snapshot.active_inhabitant_ids)
    ):
        _raise(
            "forged_coalition_membership_snapshot",
            "snapshot immutable storage provenance is invalid",
        )
    return snapshot


def classify_coalition_communication(
    snapshot: CoalitionMembershipSnapshot,
    *,
    tick: int,
    sender_id: int,
    receiver_id: int,
) -> CoalitionCommunicationClassification:
    """Classify one pair with constant-time snapshot checks and lookups."""
    validated = validate_coalition_membership_snapshot(snapshot, tick=tick)
    if not _is_exact_nonnegative_int(sender_id):
        _raise("invalid_coalition_communicator", "sender ID is invalid")
    if not _is_exact_nonnegative_int(receiver_id):
        _raise("invalid_coalition_communicator", "receiver ID is invalid")
    if sender_id == receiver_id:
        _raise("invalid_coalition_communicator", "communicators must be distinct")
    if (
        sender_id not in validated._active_inhabitant_id_set
        or receiver_id not in validated._active_inhabitant_id_set
    ):
        _raise(
            "inactive_coalition_communicator",
            "both communicators must exist in the frozen active-ID snapshot",
        )

    sender_coalition_id = validated._member_to_coalition.get(sender_id)
    receiver_coalition_id = validated._member_to_coalition.get(receiver_id)
    if sender_coalition_id is None and receiver_coalition_id is None:
        context = CoalitionCommunicationContext.BOTH_UNASSIGNED
    elif sender_coalition_id is None or receiver_coalition_id is None:
        context = CoalitionCommunicationContext.ASSIGNED_UNASSIGNED
    elif sender_coalition_id == receiver_coalition_id:
        context = CoalitionCommunicationContext.SAME_ACTIVE_COALITION
    else:
        context = CoalitionCommunicationContext.DIFFERENT_ACTIVE_COALITIONS
    return CoalitionCommunicationClassification(
        context=context,
        sender_coalition_id=sender_coalition_id,
        receiver_coalition_id=receiver_coalition_id,
    )


def validate_proposed_coalition_state(
    people: list[CoalitionInhabitant],
    runtime: CoalitionRuntimeState,
    *,
    tick: int,
    config: CoalitionConfig,
    graph: ReciprocalGraph | None = None,
    previous_state: CoalitionRuntimeState | None = None,
    intelligibility_threshold: float | None = None,
) -> None:
    """Fail closed unless proposed state is canonical and vertex-biconnected.

    ``intelligibility_threshold`` must match the value the transition used, or
    the rebuilt graph would differ from the one that produced the state.
    """
    _validate_config(config)
    by_id = _validate_people_and_relationships(
        people, observation_tick=tick)
    active_ids = frozenset(by_id)
    _validate_runtime_structure(
        runtime,
        allowed_ids=active_ids,
        config=config,
        expected_last_tick=tick,
    )
    if previous_state is not None:
        _validate_transition_lineage(previous_state, runtime)
    if runtime.last_active_inhabitant_ids != tuple(sorted(active_ids)):
        _raise("invalid_active_id_snapshot", "proposed active IDs are not canonical")
    current_graph = graph or build_qualifying_reciprocal_graph(
        people, tick=tick, config=config,
        intelligibility_threshold=intelligibility_threshold)
    if runtime.last_qualifying_reciprocal_edge_count != current_graph.edge_count:
        _raise(
            "coalition_edge_count_mismatch",
            "proposed qualifying edge count is inconsistent",
        )
    for coalition_id in sorted(runtime.active_coalitions):
        members = runtime.active_coalitions[coalition_id].member_ids
        if not _membership_is_one_support_block(
            current_graph,
            members,
            minimum_size=config.coalition_minimum_size,
        ):
            _raise(
                "active_coalition_not_vertex_biconnected",
                f"coalition {coalition_id} is not one support block",
            )
    for members in sorted(runtime.candidates):
        if not _membership_is_one_support_block(
            current_graph,
            members,
            minimum_size=config.coalition_minimum_size,
        ):
            _raise(
                "candidate_not_vertex_biconnected",
                f"candidate {members} is not one support block",
            )


def _membership_index(
    active: dict[int, InformalCoalition],
) -> dict[int, int]:
    return {
        member: coalition_id
        for coalition_id in sorted(active)
        for member in active[coalition_id].member_ids
    }


def _validate_transition_lineage(
    previous: CoalitionRuntimeState,
    proposed: CoalitionRuntimeState,
) -> None:
    """Reject allocator regression, ID reuse, and counter rollback."""
    if not isinstance(previous, CoalitionRuntimeState):
        _raise("invalid_previous_coalition_runtime", "previous runtime is invalid")
    if proposed.next_coalition_id < previous.next_coalition_id:
        _raise("regressed_coalition_allocator", "next coalition ID moved backward")

    for name in (
        "candidate_formation_count",
        "split_event_count",
        "split_child_count",
        "dissolution_count",
    ):
        if getattr(proposed, name) < getattr(previous, name):
            _raise("regressed_coalition_counter", f"{name} moved backward")

    previous_ids = frozenset(previous.active_coalitions)
    proposed_ids = frozenset(proposed.active_coalitions)
    new_ids = tuple(sorted(proposed_ids - previous_ids))
    reused_ids = tuple(
        coalition_id
        for coalition_id in new_ids
        if coalition_id < previous.next_coalition_id
    )
    if reused_ids:
        _raise(
            "reused_coalition_id",
            f"retired coalition IDs were reintroduced: {reused_ids}",
        )

    issued_count = proposed.next_coalition_id - previous.next_coalition_id
    if issued_count != len(new_ids) or any(
        coalition_id != previous.next_coalition_id + offset
        for offset, coalition_id in enumerate(new_ids)
    ):
        _raise(
            "invalid_coalition_id_lineage",
            "new coalition IDs do not match the contiguous allocator range",
        )

    for coalition_id in sorted(previous_ids.intersection(proposed_ids)):
        if (
            proposed.active_coalitions[coalition_id].formed_tick
            != previous.active_coalitions[coalition_id].formed_tick
        ):
            _raise(
                "invalid_coalition_id_lineage",
                f"retained coalition {coalition_id} changed its formation tick",
            )


def transition_informal_coalitions(
    people: list[CoalitionInhabitant],
    current_state: CoalitionRuntimeState,
    *,
    tick: int,
    config: CoalitionConfig,
    intelligibility_threshold: float | None = None,
) -> CoalitionRuntimeState:
    """Return one validated proposed state without mutating current state."""
    _validate_config(config)
    if not config.coalition_emergence_enabled:
        _raise("coalition_processing_disabled", "enabled transition was not requested")
    if not _is_exact_nonnegative_int(tick):
        _raise("invalid_observation_tick", "tick must be a nonnegative integer")
    if (
        current_state.last_observation_tick is not None
        and tick <= current_state.last_observation_tick
    ):
        _raise(
            "nonincreasing_coalition_observation_tick",
            "observation ticks must increase strictly",
        )

    graph = build_qualifying_reciprocal_graph(
        people, tick=tick, config=config,
        intelligibility_threshold=intelligibility_threshold)
    active_ids = frozenset(graph.adjacency)
    prior_ids = frozenset(current_state.last_active_inhabitant_ids)
    _validate_runtime_structure(
        current_state,
        allowed_ids=prior_ids,
        config=config,
        expected_last_tick=current_state.last_observation_tick,
    )
    if current_state.last_observation_tick is None and (
        current_state.candidates
        or current_state.active_coalitions
        or current_state.member_to_coalition
        or current_state.next_coalition_id
        or current_state.candidate_formation_count
        or current_state.split_event_count
        or current_state.split_child_count
        or current_state.dissolution_count
        or current_state.last_active_inhabitant_ids
        or current_state.last_qualifying_reciprocal_edge_count
    ):
        _raise("nonempty_initial_coalition_state", "initial state is not pristine")

    next_id = current_state.next_coalition_id
    formation_count = current_state.candidate_formation_count
    split_event_count = current_state.split_event_count
    split_child_count = current_state.split_child_count
    dissolution_count = current_state.dissolution_count
    active: dict[int, InformalCoalition] = {}
    child_proposals: list[tuple[int, SupportBlock]] = []
    overflow_child_members: set[int] = set()

    for coalition_id in sorted(current_state.active_coalitions):
        previous = current_state.active_coalitions[coalition_id]
        survivors = tuple(
            member for member in previous.member_ids if member in active_ids)
        blocks, _articulations = vertex_biconnected_support_blocks(
            graph,
            survivors,
            minimum_size=config.coalition_minimum_size,
        )
        accepted = resolve_exclusive_support_blocks(blocks)
        if not accepted:
            dissolution_count += 1
            continue
        keeper = accepted[0]
        active[coalition_id] = InformalCoalition(
            coalition_id=coalition_id,
            formed_tick=previous.formed_tick,
            member_ids=keeper.member_ids,
        )
        if len(accepted) > 1:
            split_event_count += 1
            child_proposals.extend(
                (coalition_id, block) for block in accepted[1:])

    child_proposals.sort(key=lambda proposal: (
        proposal[0],
        -len(proposal[1].member_ids),
        -proposal[1].support_strength,
        proposal[1].member_ids,
    ))
    for _parent_id, block in child_proposals:
        if len(active) >= config.maximum_active_coalitions:
            overflow_child_members.update(block.member_ids)
            continue
        coalition_id = next_id
        next_id += 1
        split_child_count += 1
        active[coalition_id] = InformalCoalition(
            coalition_id=coalition_id,
            formed_tick=tick,
            member_ids=block.member_ids,
        )

    pre_growth_members = {
        coalition_id: coalition.member_ids
        for coalition_id, coalition in sorted(active.items())
    }
    pre_growth_claimed = {
        member
        for members in pre_growth_members.values()
        for member in members
    }
    pre_growth_membership = {
        member: coalition_id
        for coalition_id, members in pre_growth_members.items()
        for member in members
    }
    join_choices: dict[int, int] = {}
    joinable_ids = active_ids - pre_growth_claimed - overflow_child_members
    for inhabitant_id in sorted(joinable_ids):
        support_counts: dict[int, int] = {}
        support_strengths: dict[int, int] = {}
        for member in graph.adjacency[inhabitant_id]:
            coalition_id = pre_growth_membership.get(member)
            if coalition_id is None:
                continue
            support_counts[coalition_id] = support_counts.get(coalition_id, 0) + 1
            edge = (min(inhabitant_id, member), max(inhabitant_id, member))
            support_strengths[coalition_id] = (
                support_strengths.get(coalition_id, 0)
                + graph.edge_strengths[edge]
            )
        # Adding one vertex with edges to two distinct vertices of a
        # vertex-biconnected graph preserves vertex biconnectivity.  This lets
        # eligibility remain sparse; the combined simultaneous result is
        # still decomposed and validated once per coalition below.
        eligible = [
            (support_count, support_strengths[coalition_id], coalition_id)
            for coalition_id, support_count in sorted(support_counts.items())
            if support_count >= 2
        ]
        if eligible:
            support_count, support_strength, coalition_id = min(
                eligible,
                key=lambda option: (-option[0], -option[1], option[2]),
            )
            del support_count, support_strength
            join_choices[inhabitant_id] = coalition_id

    joiners_by_coalition: dict[int, list[int]] = {}
    for inhabitant_id, coalition_id in sorted(join_choices.items()):
        joiners_by_coalition.setdefault(coalition_id, []).append(inhabitant_id)
    grown: dict[int, InformalCoalition] = {}
    for coalition_id in sorted(active):
        coalition = active[coalition_id]
        members = tuple(sorted(
            (*coalition.member_ids, *joiners_by_coalition.get(coalition_id, ()))
        ))
        if not _membership_is_one_support_block(
            graph,
            members,
            minimum_size=config.coalition_minimum_size,
        ):
            _raise(
                "post_growth_not_vertex_biconnected",
                f"coalition {coalition_id} failed transactional growth validation",
            )
        grown[coalition_id] = InformalCoalition(
            coalition_id=coalition_id,
            formed_tick=coalition.formed_tick,
            member_ids=members,
        )
    active = grown

    claimed_active = {
        member
        for coalition in active.values()
        for member in coalition.member_ids
    }
    unassigned = tuple(sorted(active_ids - claimed_active))
    candidate_blocks, _candidate_articulations = (
        vertex_biconnected_support_blocks(
            graph,
            unassigned,
            minimum_size=config.coalition_minimum_size,
        )
    )
    accepted_candidates = resolve_exclusive_support_blocks(candidate_blocks)
    candidates: dict[tuple[int, ...], CoalitionCandidate] = {}
    mature: list[CoalitionCandidate] = []
    for block in sorted(accepted_candidates, key=lambda value: value.member_ids):
        members = block.member_ids
        previous = current_state.candidates.get(members)
        if previous is not None and previous.last_qualified_tick == tick - 1:
            first_tick = previous.first_qualified_tick
            consecutive = min(
                config.coalition_persistence_ticks,
                previous.consecutive_qualifying_observations + 1,
            )
        else:
            first_tick = tick
            consecutive = 1
        candidate = CoalitionCandidate(
            member_ids=members,
            first_qualified_tick=first_tick,
            consecutive_qualifying_observations=consecutive,
            last_qualified_tick=tick,
        )
        if consecutive >= config.coalition_persistence_ticks:
            mature.append(candidate)
        else:
            candidates[members] = candidate

    for candidate in sorted(
        mature,
        key=lambda value: (value.first_qualified_tick, value.member_ids),
    ):
        if len(active) >= config.maximum_active_coalitions:
            candidates[candidate.member_ids] = candidate
            continue
        coalition_id = next_id
        next_id += 1
        formation_count += 1
        active[coalition_id] = InformalCoalition(
            coalition_id=coalition_id,
            formed_tick=tick,
            member_ids=candidate.member_ids,
        )

    proposed = CoalitionRuntimeState(
        candidates=dict(sorted(candidates.items())),
        active_coalitions=dict(sorted(active.items())),
        member_to_coalition=_membership_index(active),
        next_coalition_id=next_id,
        candidate_formation_count=formation_count,
        split_event_count=split_event_count,
        split_child_count=split_child_count,
        dissolution_count=dissolution_count,
        last_observation_tick=tick,
        last_active_inhabitant_ids=tuple(sorted(active_ids)),
        last_qualifying_reciprocal_edge_count=graph.edge_count,
    )
    validate_proposed_coalition_state(
        people,
        proposed,
        tick=tick,
        config=config,
        graph=graph,
        previous_state=current_state,
    )
    return proposed


def canonical_candidate_snapshot(
    runtime: CoalitionRuntimeState,
) -> list[dict[str, object]]:
    """Return candidate persistence in canonical member order."""
    return [
        {
            "member_ids": list(candidate.member_ids),
            "first_qualified_tick": candidate.first_qualified_tick,
            "consecutive_qualifying_observations": (
                candidate.consecutive_qualifying_observations
            ),
            "last_qualified_tick": candidate.last_qualified_tick,
        }
        for _members, candidate in sorted(runtime.candidates.items())
    ]


def canonical_coalition_snapshot(
    runtime: CoalitionRuntimeState,
) -> list[dict[str, object]]:
    """Return active coalition identities and memberships canonically."""
    return [
        {
            "coalition_id": coalition.coalition_id,
            "formed_tick": coalition.formed_tick,
            "member_ids": list(coalition.member_ids),
        }
        for _coalition_id, coalition in sorted(
            runtime.active_coalitions.items())
    ]


def coalition_summary(runtime: CoalitionRuntimeState) -> CoalitionSummary:
    """Return bounded canonical coalition observability."""
    memberships = tuple(
        (coalition_id, coalition.member_ids)
        for coalition_id, coalition in sorted(runtime.active_coalitions.items())
    )
    return CoalitionSummary(
        qualifying_reciprocal_edge_count=(
            runtime.last_qualifying_reciprocal_edge_count
        ),
        candidate_count=len(runtime.candidates),
        active_coalition_count=len(runtime.active_coalitions),
        coalition_sizes=tuple(
            (coalition_id, len(members))
            for coalition_id, members in memberships
        ),
        coalition_memberships=memberships,
        formation_count=runtime.candidate_formation_count,
        split_count=runtime.split_event_count,
        dissolution_count=runtime.dissolution_count,
    )
