"""Authentic committed economy outcomes feed central social memory once."""

from types import SimpleNamespace

from thalren_vale import diplomacy, economy
from thalren_vale.config import SocialMemoryConfig
from thalren_vale.inhabitants import Inhabitant


MEMORY_ONLY = SocialMemoryConfig(True, False, 32, 25)


class PreserveOrderRandom:
    def shuffle(self, values):
        del values


def pair() -> tuple[Inhabitant, Inhabitant]:
    giver = Inhabitant("Giver", 0, 0)
    recipient = Inhabitant("Recipient", 0, 0)
    giver.inhabitant_id = 1
    recipient.inhabitant_id = 2
    for resource in economy.RES_TRADE:
        giver.inventory[resource] = 0
        recipient.inventory[resource] = 0
    return giver, recipient


def test_authentic_successful_aid_is_recorded_exactly_once():
    giver, recipient = pair()
    giver.inventory["food"] = 3

    economy._individual_barter(
        [giver, recipient],
        5,
        [],
        social_config=MEMORY_ONLY,
        rng=PreserveOrderRandom(),
    )

    assert giver.inventory["food"] == 2
    assert recipient.inventory["food"] == 1
    assert recipient.relationships[1].trust == 0.08
    assert recipient.relationships[1].obligation == 0.10
    assert recipient.relationships[1].interaction_count == 1
    assert giver.relationships[2].interaction_count == 1


def test_authentic_paid_individual_transfer_is_symmetric_trade():
    seller, buyer = pair()
    seller.inventory["food"] = 3
    buyer.currency = economy.BASE_PRICES["food"]

    economy._individual_barter(
        [seller, buyer],
        6,
        [],
        social_config=MEMORY_ONLY,
        rng=PreserveOrderRandom(),
    )

    assert seller.relationships[2].trust == 0.03
    assert buyer.relationships[1].trust == 0.03
    assert seller.relationships[2].familiarity == 0.08
    assert buyer.relationships[1].familiarity == 0.08
    assert seller.relationships[2].obligation == 0.0
    assert buyer.relationships[1].obligation == 0.0


def test_failed_individual_transfer_creates_no_relationship():
    giver, recipient = pair()
    giver.inventory["food"] = 2

    economy._individual_barter(
        [giver, recipient],
        5,
        [],
        social_config=MEMORY_ONLY,
        rng=PreserveOrderRandom(),
    )

    assert giver.relationships == {}
    assert recipient.relationships == {}
    assert giver.trade_count == recipient.trade_count == 0


def test_faction_mediated_committed_transfer_records_donor_and_taker_trade(
    monkeypatch,
):
    donor, taker = pair()
    donor.inventory["food"] = 5
    giver = SimpleNamespace(name="Givers", members=[donor])
    receiver = SimpleNamespace(name="Receivers", members=[taker])
    key = ("Givers", "Receivers")
    economy.trade_routes.clear()
    economy.faction_prices.clear()
    economy.RIVALRIES[key] = 0
    monkeypatch.setattr(economy, "add_belief", lambda *args: None)
    monkeypatch.setattr(economy.combat, "are_allied", lambda *args: False)
    monkeypatch.setattr(diplomacy, "trade_bonus", lambda *args: 1.0)

    committed = economy._do_trade(
        giver,
        receiver,
        "food",
        3,
        9,
        [],
        key,
        social_config=MEMORY_ONLY,
        active_ids=frozenset({1, 2}),
    )

    assert committed is True
    assert donor.relationships[2].trust == 0.03
    assert taker.relationships[1].trust == 0.03
    assert donor.relationships[2].interaction_count == 1
    assert taker.relationships[1].interaction_count == 1


def test_failed_faction_transfer_creates_no_relationship(monkeypatch):
    donor, taker = pair()
    donor.inventory["food"] = 2
    giver = SimpleNamespace(name="Givers", members=[donor])
    receiver = SimpleNamespace(name="Receivers", members=[taker])
    monkeypatch.setattr(economy, "add_belief", lambda *args: None)

    committed = economy._do_trade(
        giver,
        receiver,
        "food",
        3,
        9,
        [],
        ("Givers", "Receivers"),
        social_config=MEMORY_ONLY,
        active_ids=frozenset({1, 2}),
    )

    assert committed is False
    assert donor.relationships == {}
    assert taker.relationships == {}
