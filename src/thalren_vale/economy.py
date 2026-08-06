# (c) 2026 (KriaetvAspie / AspieTheBard)
# Licensed under the Polyform Noncommercial License 1.0.0
"""
economy.py — Layer 4: currency, dynamic pricing, trade, raids, wealth.

Call order each tick:
    economy_tick(people, factions, t, event_log)

End of run:
    economy_report(factions, people, ticks)
"""
import sys, random
sys.stdout.reconfigure(encoding='utf-8')

from collections  import defaultdict
from dataclasses import dataclass
from itertools    import combinations
from .world        import world, GRID
from .beliefs      import inh_cores, add_belief
from .factions     import RIVALRIES
from . import combat
from .events import emit_event
from .config import (
    CoalitionDialectConfig,
    DEFAULT_LANGUAGE_FORGETTING_INTERVAL,
    DEFAULT_LANGUAGE_INVENTION_ENABLED,
    DEFAULT_LANGUAGE_LEARNING_RATE,
    DEFAULT_LANGUAGE_REINFORCEMENT_RATE,
    DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS,
    DEFAULT_MAXIMUM_SIGNAL_LENGTH,
    DEFAULT_MAXIMUM_SOCIAL_TIES,
    DEFAULT_RELATIONSHIP_DECAY_INTERVAL,
    GrammarEvolutionConfig,
    LanguageContactConfig,
    LanguageEvolutionConfig,
    CompositionalProtolanguageConfig,
    LexicalEvolutionConfig,
    SocialMemoryConfig,
)
from .coalitions import CoalitionMembershipSnapshot
from .social import (
    InteractionKind,
    record_interaction,
    relationship_preference_score,
)
from .language import (
    CoalitionDialectRuntimeState,
    CommunicationContext,
    GrammarEvolutionRuntimeState,
    LanguageContactRuntimeState,
    LanguageRuntimeState,
    CompositionalProtolanguageRuntimeState,
    LexicalEvolutionRuntimeState,
    communicate,
    meaning_for_resource,
)

# ── Module-level state ─────────────────────────────────────────────────────
faction_currencies: dict  = {}           # faction_name → {'name': str}
faction_prices:     dict  = {}           # faction_name → {res: float}
price_history:      dict  = {}           # faction_name → {res: [float…]}
trade_routes:       dict  = {}           # frozenset({a,b}) → RouteData dict
raid_log:           list  = []           # [(t, raider, victim, haul_str)]
scarcity_events:    list  = []           # [(t, resource)]

BASE_PRICES = {'food': 2, 'wood': 3, 'ore': 5, 'stone': 4}
RES_TRADE   = ['food', 'wood', 'ore', 'stone']   # exclude water from economy
_last_shock_res: str = ''                         # never repeat same resource twice

_DISABLED_SOCIAL_CONFIG = SocialMemoryConfig(
    social_memory_enabled=False,
    social_partner_bias_enabled=False,
    maximum_social_ties=DEFAULT_MAXIMUM_SOCIAL_TIES,
    relationship_decay_interval=DEFAULT_RELATIONSHIP_DECAY_INTERVAL,
)
_DISABLED_LANGUAGE_CONFIG = LanguageEvolutionConfig(
    language_evolution_enabled=False,
    maximum_language_associations=DEFAULT_MAXIMUM_LANGUAGE_ASSOCIATIONS,
    maximum_signal_length=DEFAULT_MAXIMUM_SIGNAL_LENGTH,
    language_learning_rate=DEFAULT_LANGUAGE_LEARNING_RATE,
    language_reinforcement_rate=DEFAULT_LANGUAGE_REINFORCEMENT_RATE,
    language_forgetting_interval=DEFAULT_LANGUAGE_FORGETTING_INTERVAL,
    language_invention_enabled=DEFAULT_LANGUAGE_INVENTION_ENABLED,
)


def _coalition_language_kwargs(
    *,
    dialect_config: CoalitionDialectConfig | None,
    dialect_runtime: CoalitionDialectRuntimeState | None,
    contact_config: LanguageContactConfig | None,
    contact_runtime: LanguageContactRuntimeState | None,
    lexical_config: LexicalEvolutionConfig | None,
    lexical_runtime: LexicalEvolutionRuntimeState | None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None,
) -> dict[str, object]:
    """Pass only effective coalition-language owners into communication."""
    result: dict[str, object] = {}
    coalition_context_required = False
    if (
        dialect_config is not None
        and dialect_config.coalition_dialect_influence_enabled
    ):
        result["dialect_config"] = dialect_config
        result["dialect_runtime"] = dialect_runtime
        coalition_context_required = True
    if contact_config is not None and contact_config.language_contact_enabled:
        result["contact_config"] = contact_config
        result["contact_runtime"] = contact_runtime
        coalition_context_required = True
    if lexical_config is not None and lexical_config.lexical_evolution_enabled:
        result["lexical_config"] = lexical_config
        result["lexical_runtime"] = lexical_runtime
    if (
        compositional_config is not None
        and compositional_config.compositional_protolanguage_enabled
    ):
        result["compositional_config"] = compositional_config
        result["compositional_runtime"] = compositional_runtime
    if (
        grammar_config is not None
        and grammar_config.grammar_evolution_enabled
    ):
        result["grammar_config"] = grammar_config
        result["grammar_runtime"] = grammar_runtime
    if coalition_context_required:
        result["coalition_membership_snapshot"] = (
            coalition_membership_snapshot
        )
    return result


@dataclass(frozen=True)
class _FrozenSocialEconomyInputs:
    """One economy pass's deterministic, bounded social selection inputs."""

    active_ids: frozenset[int]
    inhabitant_by_id: dict[int, object]
    shuffled_groups: tuple[tuple[object, ...], ...]
    shuffled_rank: dict[int, int]
    zero_resource_ids: dict[tuple[int, int, str], frozenset[int]]
    surplus_resources: dict[int, tuple[str, ...]]
    positive_preferences: dict[int, tuple[tuple[int, float], ...]]

_CURRENCY_NAMES = [
    'shells', 'iron bits', 'marked stones', 'bone chips', 'carved tokens',
    'clay seals', 'dried herbs', 'scored bark', 'knotted cord', 'amber beads',
    'tide pearls', 'copper seeds', 'fired clay', 'pine resin', 'salt blocks',
]


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _faction_supply(faction) -> dict:
    """Sum of resources held by members + food reserve."""
    totals = {k: 0 for k in RES_TRADE}
    for m in faction.members:
        for k in RES_TRADE:
            totals[k] += m.inventory.get(k, 0)
    totals['food'] += int(faction.food_reserve)
    return totals


def _faction_demand(faction, supply) -> dict:
    """Rough demand estimate: how much the faction currently lacks."""
    n = max(1, len(faction.members))
    # Need roughly 3 food per member, 1 of others per 4 members
    needs = {
        'food':  n * 3,
        'wood':  max(1, n // 4),
        'ore':   max(1, n // 4),
        'stone': max(1, n // 4),
    }
    return {k: max(0, needs[k] - supply[k]) for k in RES_TRADE}


def _invent_currency(faction, t, event_log):
    if faction.name in faction_currencies:
        return
    cores = set()
    for m in faction.members:
        cores.update(inh_cores(m))
    if 'trade_builds_bonds' not in cores:
        return
    used  = {v['name'] for v in faction_currencies.values()}
    picks = [c for c in _CURRENCY_NAMES if c not in used]
    cname = random.choice(picks) if picks else f"tokens of {faction.name[:6]}"
    faction_currencies[faction.name] = {'name': cname}
    for m in faction.members:
        m.currency = getattr(m, 'currency', 0) + 10
    msg = (f"Tick {t:03d}: 💰 {faction.name} invents currency — "
           f"'{cname}' (each member receives 10)")
    event_log.append(msg)
    print(msg)


def _update_prices(faction, t, event_log):
    supply = _faction_supply(faction)
    demand = _faction_demand(faction, supply)
    name   = faction.name

    if name not in faction_prices:
        faction_prices[name]  = dict(BASE_PRICES)
    if name not in price_history:
        price_history[name] = {k: [] for k in RES_TRADE}

    for res in RES_TRADE:
        base      = BASE_PRICES[res]
        d, s      = demand[res], max(supply[res], 1)
        ratio     = max(0.5, min(4.0, (d + 1) / s))
        new_price = round(base * ratio, 1)
        old_price = faction_prices[name].get(res, base)

        if abs(new_price - old_price) >= 1.0:
            direction = 'scarce' if new_price > old_price else 'surplus'
            msg = (f"Tick {t:03d}: {name} {res} price: "
                   f"{old_price:.0f}→{new_price:.0f} ({direction})")
            event_log.append(msg)
            print(msg)

        faction_prices[name][res] = new_price
        price_history[name][res].append(new_price)


# ══════════════════════════════════════════════════════════════════════════════
# Trade helpers
# ══════════════════════════════════════════════════════════════════════════════

def _do_trade(
    giver,
    receiver,
    res,
    amount,
    t,
    event_log,
    key,
    *,
    social_config=_DISABLED_SOCIAL_CONFIG,
    language_config=_DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    active_ids=frozenset(),
):
    donors = [m for m in giver.members if m.inventory.get(res, 0) >= amount]
    if not donors or not receiver.members:
        return False
    donor = max(donors, key=lambda m: m.inventory.get(res, 0))
    taker = random.choice(receiver.members)

    from . import diplomacy as _dip
    _trade_bonus = _dip.trade_bonus(giver.name, receiver.name)
    donor.inventory[res] -= amount
    taker.inventory[res] += int(amount * _trade_bonus)

    # Currency payment if receiver has currency
    price     = faction_prices.get(receiver.name, BASE_PRICES).get(res, BASE_PRICES[res])
    payment   = min(getattr(taker, 'currency', 0), round(amount * price))
    if payment > 0:
        taker.currency   = getattr(taker, 'currency', 0) - payment
        donor.currency   = getattr(donor, 'currency', 0) + payment

    # Tension reduction
    RIVALRIES[key] = max(0, RIVALRIES.get(key, 0) - 5)

    # Beliefs
    add_belief(donor, 'trade_builds_bonds')
    add_belief(taker, 'trade_builds_bonds')

    # Route tracking
    route_key = frozenset([giver.name, receiver.name])
    if route_key not in trade_routes:
        trade_routes[route_key] = {
            'count': 0, 'resources': defaultdict(int), 'active': False,
            'names': (giver.name, receiver.name),
        }
    trade_routes[route_key]['count']            += 1
    trade_routes[route_key]['resources'][res]   += amount

    # Route established at 3 successful trades
    if trade_routes[route_key]['count'] == 3 and not trade_routes[route_key]['active']:
        trade_routes[route_key]['active'] = True
        res_str = ', '.join(trade_routes[route_key]['resources'].keys())
        msg = (f"Tick {t:03d}: 🛤 Trade route established: "
               f"{giver.name} ↔ {receiver.name} ({res_str})")
        event_log.append(msg)
        print(msg)

    # 10% bonus from established route
    if trade_routes[route_key]['active']:
        bonus = max(1, round(amount * 0.10))
        taker.inventory[res] += bonus

    # 20% bonus for allied factions
    if combat.are_allied(giver.name, receiver.name):
        ally_bonus = max(1, round(amount * 0.20))
        taker.inventory[res] += ally_bonus

    if social_config.social_memory_enabled:
        record_interaction(
            donor,
            taker,
            InteractionKind.TRADE,
            tick=t,
            active_ids=active_ids,
            config=social_config,
        )

    tension = RIVALRIES.get(key, 0)
    msg = (f"Tick {t:03d}: 🤝 Trade: {giver.name} → {receiver.name}  "
           f"{amount} {res}  (tension now {tension})")
    event_log.append(msg)

    if language_config.language_evolution_enabled:
        if language_runtime is None:
            raise ValueError('enabled language trade requires a runtime')
        communicate(
            donor,
            taker,
            meaning_for_resource(res),
            context=CommunicationContext.FACTION_TRADE,
            tick=t,
            active_ids=active_ids,
            config=language_config,
            runtime=language_runtime,
            **_coalition_language_kwargs(
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
            ),
        )
    return True


def _faction_trade(
    active,
    t,
    event_log,
    *,
    social_config=_DISABLED_SOCIAL_CONFIG,
    language_config=_DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    active_ids=frozenset(),
):
    for fa, fb in combinations(active, 2):
        key     = tuple(sorted([fa.name, fb.name]))
        tension = RIVALRIES.get(key, 0)

        if combat.is_at_war(fa.name, fb.name):
            continue  # at war — no trade

        if tension >= 35:
            continue  # hostile — raiding only

        if tension >= 30:
            # Occasional failed negotiation
            if random.random() < 0.08:
                RIVALRIES[key] = RIVALRIES.get(key, 0) + 3
                msg = (f"Tick {t:03d}: 🚫 Trade talks between "
                       f"{fa.name} & {fb.name} collapsed (+3 tension)")
                event_log.append(msg)
            continue

        sup_a = _faction_supply(fa)
        sup_b = _faction_supply(fb)

        for res in RES_TRADE:
            amount = 3
            if trade_routes.get(frozenset([fa.name, fb.name]), {}).get('active'):
                amount = 4   # route bonus handled inside _do_trade
            if sup_a[res] >= 5 and sup_a[res] >= sup_b[res] * 2:
                _do_trade(
                    fa, fb, res, amount, t, event_log, key,
                    social_config=social_config,
                    language_config=language_config,
                    language_runtime=language_runtime,
                    dialect_config=dialect_config,
                    dialect_runtime=dialect_runtime,
                    contact_config=contact_config,
                    contact_runtime=contact_runtime,
                    lexical_config=lexical_config,
                    lexical_runtime=lexical_runtime,
                    compositional_config=compositional_config,
                    compositional_runtime=compositional_runtime,
                    grammar_config=grammar_config,
                    grammar_runtime=grammar_runtime,
                    coalition_membership_snapshot=(
                        coalition_membership_snapshot
                    ),
                    active_ids=active_ids)
                break
            elif sup_b[res] >= 5 and sup_b[res] >= sup_a[res] * 2:
                _do_trade(
                    fb, fa, res, amount, t, event_log, key,
                    social_config=social_config,
                    language_config=language_config,
                    language_runtime=language_runtime,
                    dialect_config=dialect_config,
                    dialect_runtime=dialect_runtime,
                    contact_config=contact_config,
                    contact_runtime=contact_runtime,
                    lexical_config=lexical_config,
                    lexical_runtime=lexical_runtime,
                    compositional_config=compositional_config,
                    compositional_runtime=compositional_runtime,
                    grammar_config=grammar_config,
                    grammar_runtime=grammar_runtime,
                    coalition_membership_snapshot=(
                        coalition_membership_snapshot
                    ),
                    active_ids=active_ids)
                break
        else:
            # No natural trade trigger — random small negotiation failure
            if random.random() < 0.04 and tension < 20:
                RIVALRIES[key] = RIVALRIES.get(key, 0) + 3
                msg = (f"Tick {t:03d}: 🚫 Trade negotiations between "
                       f"{fa.name} & {fb.name} failed (+3 tension)")
                event_log.append(msg)


def _faction_raids(active, t, event_log):
    for fa, fb in combinations(active, 2):
        key     = tuple(sorted([fa.name, fb.name]))
        tension = RIVALRIES.get(key, 0)
        if tension <= 35:
            continue
        if random.random() > 0.20:   # 20% triggered per eligible pair per tick
            continue

        raider, victim = (fa, fb) if random.random() < 0.5 else (fb, fa)
        if not victim.territory or not raider.members:
            continue

        target_pos  = random.choice(victim.territory)
        chunk       = world[target_pos[0]][target_pos[1]]
        haul        = {}
        from . import technology as _tech
        raid_mult   = _tech.raid_multiplier(raider)
        for res in RES_TRADE:
            steal = int(chunk['resources'][res] * 0.20) * raid_mult
            if steal > 0:
                chunk['resources'][res] -= steal
                haul[res] = steal

        if not haul:
            continue

        lucky = random.choice(raider.members)
        for res, amt in haul.items():
            lucky.inventory[res] = lucky.inventory.get(res, 0) + amt
        add_belief(lucky, 'the_strong_take')
        RIVALRIES[key] = RIVALRIES.get(key, 0) + 10

        haul_str = ', '.join(f"{v} {k}" for k, v in haul.items())
        raid_log.append((t, raider.name, victim.name, haul_str))
        msg = (f"Tick {t:03d}: ⚔ RAID: {raider.name} plundered "
               f"{victim.name}'s territory — seized {haul_str} (+10 tension)")
        emit_event(
            event_log,
            tick=t,
            event_type='raid',
            actor=raider.name,
            target=victim.name,
            detail=haul_str,
            message=msg,
            metadata={'haul': dict(haul)},
        )
        print(msg)
        from . import diplomacy as _dip
        _dip.adjust_rep(raider.name, -1, 'raid', t)
        # Break any existing treaty if a faction raids its signatory
        if _dip.has_treaty(raider.name, victim.name):
            _dip.break_treaty(raider.name, victim.name, t, event_log,
                              [f for f in active if f.members])


def _assigned_active_ids(people) -> tuple[frozenset[int], dict[int, object]]:
    active_ids: set[int] = set()
    inhabitant_by_id: dict[int, object] = {}
    for inhabitant in people:
        inhabitant_id = getattr(inhabitant, 'inhabitant_id', None)
        if type(inhabitant_id) is not int or inhabitant_id < 0:
            raise ValueError(
                'enabled emergent-state economy requires assigned inhabitant IDs')
        if inhabitant_id in active_ids:
            raise ValueError(f'duplicate active inhabitant ID: {inhabitant_id}')
        active_ids.add(inhabitant_id)
        inhabitant_by_id[inhabitant_id] = inhabitant
    return frozenset(active_ids), inhabitant_by_id


def _commit_individual_transfer(
    giver,
    recipient,
    res: str,
    *,
    t: int,
    social_config: SocialMemoryConfig,
    language_config: LanguageEvolutionConfig = _DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    active_ids: frozenset[int],
) -> None:
    """Commit one existing individual transfer, then record its social outcome."""
    giver.inventory[res] -= 1
    recipient.inventory[res] += 1
    giver.trust[recipient.name] = giver.trust.get(recipient.name, 0) + 1
    recipient.trust[giver.name] = recipient.trust.get(giver.name, 0) + 1
    giver.trade_count = getattr(giver, 'trade_count', 0) + 1
    recipient.trade_count = getattr(recipient, 'trade_count', 0) + 1

    pay = min(getattr(recipient, 'currency', 0), BASE_PRICES.get(res, 1))
    if pay > 0:
        recipient.currency = getattr(recipient, 'currency', 0) - pay
        giver.currency = getattr(giver, 'currency', 0) + pay

    if social_config.social_memory_enabled:
        kind = InteractionKind.TRADE if pay > 0 else InteractionKind.AID
        record_interaction(
            giver,
            recipient,
            kind,
            tick=t,
            active_ids=active_ids,
            config=social_config,
        )

    if language_config.language_evolution_enabled:
        if language_runtime is None:
            raise ValueError('enabled individual language transfer requires a runtime')
        communicate(
            giver,
            recipient,
            meaning_for_resource(res),
            context=(
                CommunicationContext.PAID_TRADE
                if pay > 0 else CommunicationContext.AID_TRANSFER
            ),
            tick=t,
            active_ids=active_ids,
            config=language_config,
            runtime=language_runtime,
            **_coalition_language_kwargs(
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
            ),
        )


def _attempt_individual_transfer(
    giver,
    recipient,
    *,
    t: int,
    social_config: SocialMemoryConfig,
    language_config: LanguageEvolutionConfig = _DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    active_ids: frozenset[int],
) -> bool:
    for res in RES_TRADE:
        if giver.inventory.get(res, 0) >= 3 and recipient.inventory.get(res, 0) == 0:
            _commit_individual_transfer(
                giver,
                recipient,
                res,
                t=t,
                social_config=social_config,
                language_config=language_config,
                language_runtime=language_runtime,
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
                active_ids=active_ids,
            )
            return True
    return False


def _historical_barter(
    people,
    t,
    *,
    social_config: SocialMemoryConfig,
    language_config: LanguageEvolutionConfig = _DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    active_ids: frozenset[int],
    rng,
) -> None:
    """Execute the historical shuffled adjacent-pair algorithm exactly."""
    chunk_map = defaultdict(list)
    for p in people:
        chunk_map[(p.r, p.c)].append(p)

    for group in chunk_map.values():
        if len(group) < 2:
            continue
        rng.shuffle(group)
        for i in range(0, len(group) - 1, 2):
            a, b = group[i], group[i + 1]
            _attempt_individual_transfer(
                a,
                b,
                t=t,
                social_config=social_config,
                language_config=language_config,
                language_runtime=language_runtime,
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
                active_ids=active_ids,
            )


def _freeze_social_economy_inputs(people, rng) -> _FrozenSocialEconomyInputs:
    active_ids, inhabitant_by_id = _assigned_active_ids(people)
    chunk_map = defaultdict(list)
    for inhabitant in people:
        chunk_map[(inhabitant.r, inhabitant.c)].append(inhabitant)

    shuffled_groups: list[tuple[object, ...]] = []
    shuffled_rank: dict[int, int] = {}
    zero_resource_ids: dict[tuple[int, int, str], frozenset[int]] = {}
    surplus_resources: dict[int, tuple[str, ...]] = {}
    positive_preferences: dict[int, tuple[tuple[int, float], ...]] = {}

    for group in chunk_map.values():
        if len(group) < 2:
            continue
        rng.shuffle(group)
        frozen_group = tuple(group)
        shuffled_groups.append(frozen_group)
        for rank, inhabitant in enumerate(frozen_group):
            shuffled_rank[inhabitant.inhabitant_id] = rank

        tile = (frozen_group[0].r, frozen_group[0].c)
        for res in RES_TRADE:
            zero_resource_ids[(tile[0], tile[1], res)] = frozenset(
                inhabitant.inhabitant_id
                for inhabitant in frozen_group
                if inhabitant.inventory.get(res, 0) == 0
            )

    for inhabitant in people:
        inhabitant_id = inhabitant.inhabitant_id
        surplus_resources[inhabitant_id] = tuple(
            res for res in RES_TRADE if inhabitant.inventory.get(res, 0) >= 3
        )
        preferences = []
        for target_id, relationship in inhabitant.relationships.items():
            score = relationship_preference_score(relationship)
            if score > 0.0:
                preferences.append((target_id, score))
        positive_preferences[inhabitant_id] = tuple(preferences)

    return _FrozenSocialEconomyInputs(
        active_ids=active_ids,
        inhabitant_by_id=inhabitant_by_id,
        shuffled_groups=tuple(shuffled_groups),
        shuffled_rank=shuffled_rank,
        zero_resource_ids=zero_resource_ids,
        surplus_resources=surplus_resources,
        positive_preferences=positive_preferences,
    )


def _known_eligible_partner(
    giver,
    baseline_target,
    available_ids: set[int],
    frozen: _FrozenSocialEconomyInputs,
):
    candidates = []
    for target_id, score in frozen.positive_preferences.get(
        giver.inhabitant_id, ()
    ):
        if target_id not in available_ids or target_id == giver.inhabitant_id:
            continue
        target = frozen.inhabitant_by_id.get(target_id)
        if target is None or (target.r, target.c) != (giver.r, giver.c):
            continue
        if not any(
            target_id in frozen.zero_resource_ids.get((giver.r, giver.c, res), ())
            for res in frozen.surplus_resources.get(giver.inhabitant_id, ())
        ):
            continue
        candidates.append((target, score))

    if not candidates:
        return baseline_target
    return min(
        candidates,
        key=lambda item: (
            -item[1],
            frozen.shuffled_rank.get(item[0].inhabitant_id, sys.maxsize),
            item[0].inhabitant_id,
        ),
    )[0]


def _relationship_biased_barter(
    people,
    t,
    *,
    social_config: SocialMemoryConfig,
    language_config: LanguageEvolutionConfig = _DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    rng,
) -> frozenset[int]:
    frozen = _freeze_social_economy_inputs(people, rng)

    for group in frozen.shuffled_groups:
        available_ids = {inhabitant.inhabitant_id for inhabitant in group}
        for index in range(0, len(group) - 1, 2):
            giver = group[index]
            baseline_target = group[index + 1]
            giver_id = giver.inhabitant_id
            baseline_id = baseline_target.inhabitant_id

            if giver_id not in available_ids or baseline_id not in available_ids:
                available_ids.discard(giver_id)
                available_ids.discard(baseline_id)
                continue

            selected = baseline_target
            exploration = (t + giver_id) % 4 == 0
            baseline_opportunity = any(
                baseline_id in frozen.zero_resource_ids.get(
                    (giver.r, giver.c, res), ()
                )
                for res in frozen.surplus_resources.get(giver_id, ())
            )
            if baseline_opportunity and not exploration:
                selected = _known_eligible_partner(
                    giver,
                    baseline_target,
                    available_ids,
                    frozen,
                )

            selected_id = selected.inhabitant_id
            if selected_id != baseline_id:
                redirected = _attempt_individual_transfer(
                    giver,
                    selected,
                    t=t,
                    social_config=social_config,
                    language_config=language_config,
                    language_runtime=language_runtime,
                    dialect_config=dialect_config,
                    dialect_runtime=dialect_runtime,
                    contact_config=contact_config,
                    contact_runtime=contact_runtime,
                    lexical_config=lexical_config,
                    lexical_runtime=lexical_runtime,
                    compositional_config=compositional_config,
                    compositional_runtime=compositional_runtime,
                    grammar_config=grammar_config,
                    grammar_runtime=grammar_runtime,
                    coalition_membership_snapshot=(
                        coalition_membership_snapshot
                    ),
                    active_ids=frozen.active_ids,
                )
                if redirected:
                    available_ids.discard(giver_id)
                    available_ids.discard(selected_id)
                    available_ids.discard(baseline_id)
                    continue

            _attempt_individual_transfer(
                giver,
                baseline_target,
                t=t,
                social_config=social_config,
                language_config=language_config,
                language_runtime=language_runtime,
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
                active_ids=frozen.active_ids,
            )
            available_ids.discard(giver_id)
            available_ids.discard(baseline_id)
    return frozen.active_ids


def _individual_barter(
    people,
    t,
    event_log,
    *,
    social_config=_DISABLED_SOCIAL_CONFIG,
    language_config=_DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    rng=random,
) -> frozenset[int]:
    del event_log  # Individual transfers intentionally remain internal state changes.
    if (
        not social_config.social_memory_enabled
        and not language_config.language_evolution_enabled
    ):
        _historical_barter(
            people,
            t,
            social_config=social_config,
            active_ids=frozenset(),
            rng=rng,
        )
        return frozenset()

    active_ids, _inhabitant_by_id = _assigned_active_ids(people)
    if not social_config.social_partner_bias_enabled:
        _historical_barter(
            people,
            t,
            social_config=social_config,
            language_config=language_config,
            language_runtime=language_runtime,
            dialect_config=dialect_config,
            dialect_runtime=dialect_runtime,
            contact_config=contact_config,
            contact_runtime=contact_runtime,
            lexical_config=lexical_config,
            lexical_runtime=lexical_runtime,
            compositional_config=compositional_config,
            compositional_runtime=compositional_runtime,
            grammar_config=grammar_config,
            grammar_runtime=grammar_runtime,
            coalition_membership_snapshot=coalition_membership_snapshot,
            active_ids=active_ids,
            rng=rng,
        )
        return active_ids

    return _relationship_biased_barter(
        people,
        t,
        social_config=social_config,
        language_config=language_config,
        language_runtime=language_runtime,
        dialect_config=dialect_config,
        dialect_runtime=dialect_runtime,
        contact_config=contact_config,
        contact_runtime=contact_runtime,
        lexical_config=lexical_config,
        lexical_runtime=lexical_runtime,
        compositional_config=compositional_config,
        compositional_runtime=compositional_runtime,
        grammar_config=grammar_config,
        grammar_runtime=grammar_runtime,
        coalition_membership_snapshot=coalition_membership_snapshot,
        rng=rng,
    )


def _scarcity_shock(people, t, event_log):
    global _last_shock_res
    choices = [r for r in RES_TRADE if r != _last_shock_res]
    res = random.choice(choices)
    _last_shock_res = res
    scarcity_events.append((t, res))
    for row in world:
        for chunk in row:
            chunk['resources'][res] = max(0, int(chunk['resources'][res] * 0.85))
    line = '!' * 56
    msg  = f"Tick {t:03d}: 📉 {res.upper()} SHORTAGE — {res} running low across the land"
    event_log.append(msg)
    print(f"\n{line}\n{msg}\n{line}")


# ══════════════════════════════════════════════════════════════════════════════
# Wealth metrics
# ══════════════════════════════════════════════════════════════════════════════

def inhabitant_wealth(inh) -> float:
    return (sum(inh.inventory.get(k, 0) * BASE_PRICES.get(k, 1) for k in RES_TRADE)
            + getattr(inh, 'currency', 0))


def faction_wealth(faction) -> float:
    return (sum(inhabitant_wealth(m) for m in faction.members)
            + faction.food_reserve * BASE_PRICES['food'])


def gini_coefficient(people) -> float:
    vals = sorted(max(0.0, inhabitant_wealth(p)) for p in people)
    n    = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    total = sum(vals)
    cum   = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return cum / (n * total)


def wealth_summary_line(factions, people) -> str:
    """One-line economy state for the live display."""
    active = [f for f in factions if f.members]
    if not active:
        return ''
    w_most  = max(active, key=faction_wealth)
    w_least = min(active, key=faction_wealth)
    g       = gini_coefficient(people)
    routes  = sum(1 for r in trade_routes.values() if r['active'])
    raids   = len(raid_log)
    return (f"💰 Wealthiest: {w_most.name[:20]}  "
            f"Poorest: {w_least.name[:20]}  "
            f"Gini:{g:.2f}  Routes:{routes}  Raids:{raids}")


# ══════════════════════════════════════════════════════════════════════════════
# Public tick function
# ══════════════════════════════════════════════════════════════════════════════

def economy_tick(
    people,
    factions,
    t,
    event_log,
    *,
    raids_enabled=True,
    social_config=_DISABLED_SOCIAL_CONFIG,
    language_config=_DISABLED_LANGUAGE_CONFIG,
    language_runtime: LanguageRuntimeState | None = None,
    dialect_config: CoalitionDialectConfig | None = None,
    dialect_runtime: CoalitionDialectRuntimeState | None = None,
    contact_config: LanguageContactConfig | None = None,
    contact_runtime: LanguageContactRuntimeState | None = None,
    lexical_config: LexicalEvolutionConfig | None = None,
    lexical_runtime: LexicalEvolutionRuntimeState | None = None,
    compositional_config: CompositionalProtolanguageConfig | None = None,
    compositional_runtime: (
        CompositionalProtolanguageRuntimeState | None
    ) = None,
    grammar_config: GrammarEvolutionConfig | None = None,
    grammar_runtime: GrammarEvolutionRuntimeState | None = None,
    coalition_membership_snapshot: CoalitionMembershipSnapshot | None = None,
    rng=random,
):
    """Run one economy tick, optionally suppressing hostile faction raids."""
    active = [f for f in factions if f.members]

    # 1. Currency invention (tick 50+)
    if t >= 50:
        for faction in active:
            _invent_currency(faction, t, event_log)

    # 2. Dynamic price updates (every 5 ticks to reduce spam)
    if t % 5 == 0:
        for faction in active:
            _update_prices(faction, t, event_log)

    # 3. Scarcity shock (every 50 ticks) with 5-tick advance warning
    if t % 50 == 45 and t > 0:
        msg = f"Tick {t:03d}: 📣 Rumors of coming shortage spread through the land..."
        event_log.append(msg)
        print(msg)
    if t % 50 == 0 and t > 0:
        _scarcity_shock(people, t, event_log)

    # 4. Individual barter
    feature_context_enabled = (
        social_config.social_memory_enabled
        or language_config.language_evolution_enabled
    )
    if not feature_context_enabled:
        active_ids = _individual_barter(people, t, event_log)
    else:
        active_ids = _individual_barter(
            people,
            t,
            event_log,
            social_config=social_config,
            language_config=language_config,
            language_runtime=language_runtime,
            dialect_config=dialect_config,
            dialect_runtime=dialect_runtime,
            contact_config=contact_config,
            contact_runtime=contact_runtime,
            lexical_config=lexical_config,
            lexical_runtime=lexical_runtime,
            compositional_config=compositional_config,
            compositional_runtime=compositional_runtime,
            grammar_config=grammar_config,
            grammar_runtime=grammar_runtime,
            coalition_membership_snapshot=coalition_membership_snapshot,
            rng=rng,
        )

    # 5. Inter-faction trade (every 3 ticks to avoid log spam)
    if t % 3 == 0 and len(active) >= 2:
        if not feature_context_enabled:
            _faction_trade(active, t, event_log)
        else:
            _faction_trade(
                active,
                t,
                event_log,
                social_config=social_config,
                language_config=language_config,
                language_runtime=language_runtime,
                dialect_config=dialect_config,
                dialect_runtime=dialect_runtime,
                contact_config=contact_config,
                contact_runtime=contact_runtime,
                lexical_config=lexical_config,
                lexical_runtime=lexical_runtime,
                compositional_config=compositional_config,
                compositional_runtime=compositional_runtime,
                grammar_config=grammar_config,
                grammar_runtime=grammar_runtime,
                coalition_membership_snapshot=coalition_membership_snapshot,
                active_ids=active_ids,
            )

    # 6. Raiding (tension > 35; see _faction_raids)
    if raids_enabled and len(active) >= 2:
        _faction_raids(active, t, event_log)


# ══════════════════════════════════════════════════════════════════════════════
# Final report
# ══════════════════════════════════════════════════════════════════════════════

def economy_report(factions, people, ticks):
    sep    = '─' * 72
    active = [f for f in factions if f.members]
    print(f"\n{sep}")
    print(f"ECONOMY SUMMARY — {ticks} ticks")
    print(sep)

    # Currency issued
    print("  Currencies:")
    issued = False
    for f in factions:
        if f.name in faction_currencies:
            cname = faction_currencies[f.name]['name']
            total = sum(getattr(m, 'currency', 0) for m in f.members) if f.members else 0
            print(f"    {f.name:<30}  '{cname}'  ({total} in circulation)")
            issued = True
    if not issued:
        print("    (none invented — no faction reached tick 50 with trade_builds_bonds)")

    # Wealth
    print()
    if active:
        wealthiest = max(active, key=faction_wealth)
        poorest    = min(active, key=faction_wealth)
        print(f"  Wealthiest faction : {wealthiest.name}  "
              f"(wealth {faction_wealth(wealthiest):.0f})")
        print(f"  Poorest faction    : {poorest.name}  "
              f"(wealth {faction_wealth(poorest):.0f})")
    if people:
        g = gini_coefficient(people)
        label = 'high inequality' if g > 0.5 else 'moderate' if g > 0.3 else 'low inequality'
        print(f"  Gini coefficient   : {g:.3f}  ({label})")

    # Trade routes
    n_routes = sum(1 for r in trade_routes.values() if r['active'])
    print(f"\n  Trade routes : {n_routes}")
    for route_key, data in trade_routes.items():
        if data['active']:
            na, nb    = data['names']
            res_parts = ', '.join(data['resources'].keys())
            print(f"    {na} ↔ {nb}  ({res_parts}, {data['count']} trades)")

    # Raids
    print(f"\n  Total raids  : {len(raid_log)}")
    for entry in raid_log[-8:]:
        rt, raider, victim, haul = entry
        print(f"    Tick {rt:03d}: {raider:<28} raided {victim:<28}  {haul}")

    # Scarcity events
    print(f"\n  Scarcity shocks: {len(scarcity_events)}")
    for st, sres in scarcity_events:
        print(f"    Tick {st:03d}: {sres.upper()} shortage (−30% global)")

    # Price history peaks
    print(f"\n  Peak prices reached (vs base):")
    any_peak = False
    for fname, hist in sorted(price_history.items()):
        peaks = {k: max(v) for k, v in hist.items() if v}
        high  = {k: v for k, v in peaks.items() if v > BASE_PRICES.get(k, 1) * 1.4}
        if high:
            parts = '  '.join(f"{k}:{BASE_PRICES.get(k,1)}→{v:.1f}" for k, v in high.items())
            print(f"    {fname:<30}  {parts}")
            any_peak = True
    if not any_peak:
        print("    (prices stayed near base — plentiful supply)")

    print(sep)
