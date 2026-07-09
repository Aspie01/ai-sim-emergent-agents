"""Security boundaries for untrusted simulation plugins."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from thalren_vale import sim
from thalren_vale.plugin_api import SimulationBridge, SpawnInhabitants


def make_bridge():
    person = SimpleNamespace(name="Arin")
    faction = SimpleNamespace(
        name="North",
        members=[person],
        shared_beliefs=["community_sustains"],
        territory=[(0, 0)],
        founded_tick=2,
        food_reserve=12,
        techs={"tools"},
        is_settled=False,
    )
    world = [[{
        "biome": "plains",
        "habitable": True,
        "resources": {"food": 5, "water": 5},
    }]]
    bridge = SimulationBridge(
        tick=3,
        people=[person],
        factions=[faction],
        world=world,
        pop_cap=100,
        biome_max={"plains": {"food": 10, "water": 10}},
        event_log=["event"],
    )
    return bridge, faction, world


def test_bridge_does_not_expose_mutable_engine_objects():
    bridge, faction, world = make_bridge()
    snapshot = bridge.active_factions[0]

    with pytest.raises(FrozenInstanceError):
        snapshot.name = "Compromised"
    with pytest.raises(TypeError):
        bridge.biome_map[0][0]["habitable"] = False
    with pytest.raises(TypeError):
        bridge.tile_resources(0, 0)["food"] = 0
    with pytest.raises(AttributeError):
        bridge.active_factions.append(snapshot)

    assert faction.name == "North"
    assert world[0][0]["habitable"] is True
    assert world[0][0]["resources"]["food"] == 5


def test_snapshot_does_not_change_when_engine_state_changes():
    bridge, faction, world = make_bridge()
    faction.members.clear()
    world[0][0]["resources"]["food"] = 0

    assert bridge.active_factions[0].members == ("Arin",)
    assert bridge.tile_resources(0, 0)["food"] == 5


def test_subclassed_builtin_command_is_rejected():
    class UntrustedSpawn(SpawnInhabitants):
        pass

    sim.reset_runtime_state()
    command = UntrustedSpawn(count=20, location=(0, 0))

    sim._execute_plugin_command(command, t=1)

    assert sim.people == []
