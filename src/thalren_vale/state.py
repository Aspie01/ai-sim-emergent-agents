"""Runtime state container for a single simulation run."""

from dataclasses import dataclass, field

from .coalitions import CoalitionRuntimeState
from .language import (
    CoalitionDialectRuntimeState,
    CompositionalProtolanguageRuntimeState,
    IntergenerationalLanguageRuntimeState,
    LanguageContactRuntimeState,
    LanguageRuntimeState,
    LexicalEvolutionRuntimeState,
)


@dataclass
class SimulationState:
    """Own the mutable core collections used by the simulation loop.

    Domain modules still access compatibility aliases during the incremental
    migration away from module globals. Clearing collections in place keeps
    those aliases valid across repeated in-process runs.
    """

    people: list = field(default_factory=list)
    factions: list = field(default_factory=list)
    all_dead: list = field(default_factory=list)
    event_log: list = field(default_factory=list)
    loaded_plugins: list = field(default_factory=list)
    era_summaries: list = field(default_factory=list)
    key_events_archive: list = field(default_factory=list)
    dead_factions: list = field(default_factory=list)
    active_wars: list = field(default_factory=list)
    war_history: list = field(default_factory=list)
    rivalries: dict = field(default_factory=dict)
    treaties: dict = field(default_factory=dict)
    treaty_log: list = field(default_factory=list)
    reputation: dict = field(default_factory=dict)
    faction_currencies: dict = field(default_factory=dict)
    faction_prices: dict = field(default_factory=dict)
    price_history: dict = field(default_factory=dict)
    trade_routes: dict = field(default_factory=dict)
    raid_log: list = field(default_factory=list)
    scarcity_events: list = field(default_factory=list)
    religions: list = field(default_factory=list)
    holy_wars: set = field(default_factory=set)
    next_inhabitant_id: int = 0
    coalitions: CoalitionRuntimeState = field(
        default_factory=CoalitionRuntimeState)
    language: LanguageRuntimeState = field(
        default_factory=LanguageRuntimeState)
    dialect: CoalitionDialectRuntimeState = field(
        default_factory=CoalitionDialectRuntimeState)
    language_contact: LanguageContactRuntimeState = field(
        default_factory=LanguageContactRuntimeState)
    intergenerational_language: IntergenerationalLanguageRuntimeState = field(
        default_factory=IntergenerationalLanguageRuntimeState)
    lexical_evolution: LexicalEvolutionRuntimeState = field(
        default_factory=LexicalEvolutionRuntimeState)
    compositional_protolanguage: CompositionalProtolanguageRuntimeState = field(
        default_factory=CompositionalProtolanguageRuntimeState)

    def stage_inhabitant_id(self, inhabitant, candidate: int) -> None:
        """Assign, but do not yet consume, the next authoritative run ID."""
        if getattr(inhabitant, "inhabitant_id", None) is not None:
            raise ValueError("inhabitant already has an assigned ID")
        if type(candidate) is not int or candidate != self.next_inhabitant_id:
            raise ValueError("candidate inhabitant ID is no longer current")
        inhabitant.inhabitant_id = candidate

    def commit_inhabitant_id(self, inhabitant, candidate: int) -> None:
        """Consume a staged ID only after authoritative insertion succeeds."""
        if getattr(inhabitant, "inhabitant_id", None) != candidate:
            raise ValueError("staged inhabitant ID changed before commit")
        if candidate != self.next_inhabitant_id:
            raise ValueError("staged inhabitant ID is no longer current")
        self.next_inhabitant_id += 1

    def rollback_inhabitant_id(self, inhabitant, candidate: int) -> None:
        """Restore the allocator and candidate after failed admission."""
        if self.next_inhabitant_id == candidate + 1:
            self.next_inhabitant_id = candidate
        elif self.next_inhabitant_id != candidate:
            raise RuntimeError("cannot safely roll back inhabitant ID allocator")
        if getattr(inhabitant, "inhabitant_id", None) == candidate:
            inhabitant.inhabitant_id = None

    def reset(self) -> None:
        """Clear this run's collections without invalidating aliases."""
        self.people.clear()
        self.factions.clear()
        self.all_dead.clear()
        self.event_log.clear()
        self.loaded_plugins.clear()
        self.era_summaries.clear()
        self.key_events_archive.clear()
        self.dead_factions.clear()
        self.active_wars.clear()
        self.war_history.clear()
        self.rivalries.clear()
        self.treaties.clear()
        self.treaty_log.clear()
        self.reputation.clear()
        self.faction_currencies.clear()
        self.faction_prices.clear()
        self.price_history.clear()
        self.trade_routes.clear()
        self.raid_log.clear()
        self.scarcity_events.clear()
        self.religions.clear()
        self.holy_wars.clear()
        self.next_inhabitant_id = 0
        self.coalitions = CoalitionRuntimeState()
        self.language = LanguageRuntimeState()
        self.dialect = CoalitionDialectRuntimeState()
        self.language_contact = LanguageContactRuntimeState()
        self.intergenerational_language = IntergenerationalLanguageRuntimeState()
        self.lexical_evolution = LexicalEvolutionRuntimeState()
        self.compositional_protolanguage = (
            CompositionalProtolanguageRuntimeState())
