"""Pure selection and scoped combat context for Save interception."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple


Position = Tuple[int, int]


@dataclass(frozen=True)
class SaveOffer:
    provider: Any
    skill: Any
    kind: str
    radius: int
    rank: int
    stats: Tuple[Tuple[str, int], ...]
    damage: int
    requires_armored: bool = True
    consume_once_per_turn: bool = False


@dataclass(frozen=True)
class SaveRequest:
    attacker: Any
    protected: Any
    item: Any
    attack_distance: int
    units: Sequence[Any]
    is_enemy: Callable[[Any, Any], bool]
    is_ally: Callable[[Any, Any], bool]
    is_armored: Callable[[Any], bool]
    traversable: Callable[[Any, Position], bool]


@dataclass(frozen=True)
class SaveInterception:
    request: SaveRequest
    offer: SaveOffer

    @property
    def savior(self) -> Any:
        return self.offer.provider

    @property
    def protected(self) -> Any:
        return self.request.protected


_active_save_interception: Optional[SaveInterception] = None
_save_cleanup_active = False


def get_active_save_interception() -> Optional[SaveInterception]:
    return _active_save_interception


def set_active_save_interception(interception: Optional[SaveInterception]) -> None:
    global _active_save_interception
    _active_save_interception = interception


@contextmanager
def active_save_interception(interception: Optional[SaveInterception]):
    old_interception = get_active_save_interception()
    set_active_save_interception(interception)
    try:
        yield interception
    finally:
        set_active_save_interception(old_interception)


def is_save_cleanup_active() -> bool:
    return _save_cleanup_active


def set_save_cleanup_active(active: bool) -> None:
    global _save_cleanup_active
    _save_cleanup_active = active


def make_restored_save_interception(savior: Any, protected: Any, skill: Any, kind: str,
                                    radius: int, rank: int, stats: Tuple[Tuple[str, int], ...],
                                    damage: int) -> SaveInterception:
    """Rebuild the active-only Save context from reversible action primitives."""
    request = SaveRequest(
        attacker=None, protected=protected, item=None, attack_distance=0,
        units=(savior, protected),
        is_enemy=lambda left, right: False,
        is_ally=lambda left, right: False,
        is_armored=lambda unit: False,
        traversable=lambda unit, pos: False,
    )
    offer = SaveOffer(savior, skill, kind, radius, rank, stats, damage)
    return SaveInterception(request, offer)


def can_attempt_save_interception(attacker: Any, item: Any, target_positions: Sequence[Any],
                                  main_targets: Sequence[Any], splashes: Sequence[Sequence[Any]], *,
                                  script: Optional[Sequence[Any]] = None, arena_combat: bool = False,
                                  event_combat: bool = False) -> bool:
    """Gate every preview and controller lookup to legal single-target weapon combat."""
    from app.engine import item_system

    return bool(attacker and item and item_system.is_weapon(attacker, item) and
                not getattr(item, 'sequence_item', False) and not script and
                not arena_combat and not event_combat and len(target_positions) == 1 and
                not isinstance(target_positions[0], list) and len(main_targets) == 1 and
                main_targets[0] and len(splashes) == 1 and not splashes[0])


def _distance(first: Position, second: Position) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def _alive_on_map(unit: Any) -> bool:
    get_hp = getattr(unit, 'get_hp', None)
    return bool(unit and getattr(unit, 'position', None) is not None and
                not getattr(unit, 'dead', False) and not getattr(unit, 'is_dying', False) and
                callable(get_hp) and get_hp() > 0 and 'Tile' not in getattr(unit, 'tags', ()))


def _matches_attack_kind(offer: SaveOffer, attack_distance: int) -> bool:
    return offer.kind == 'any' or (offer.kind == 'near' and attack_distance == 1) or \
           (offer.kind == 'far' and attack_distance > 1)


def resolve_save_interception(request: SaveRequest, offers: Iterable[SaveOffer]) -> Optional[SaveInterception]:
    """Select one legal Save offer without moving or mutating any game object."""
    attacker = request.attacker
    protected = request.protected
    if not (_alive_on_map(attacker) and _alive_on_map(protected)):
        return None
    if not request.is_enemy(attacker, protected):
        return None

    indexed_units = {id(unit): index for index, unit in enumerate(request.units)}
    valid = []
    for offer in offers:
        provider = offer.provider
        if id(provider) not in indexed_units or not _alive_on_map(provider):
            continue
        if (offer.requires_armored and not request.is_armored(provider)) or \
                not request.is_ally(provider, protected):
            continue
        if not _matches_attack_kind(offer, request.attack_distance):
            continue
        if _distance(provider.position, protected.position) > offer.radius:
            continue
        if not request.traversable(provider, protected.position):
            continue
        valid.append(offer)

    if not valid:
        return None
    valid.sort(key=lambda offer: (
        -offer.rank,
        _distance(offer.provider.position, protected.position),
        indexed_units[id(offer.provider)],
        getattr(offer.skill, 'nid', ''),
        str(getattr(offer.skill, 'uid', '')),
    ))
    return SaveInterception(request, valid[0])


def find_save_interception(attacker: Any, protected: Any, item: Any,
                           attack_distance: int) -> Optional[SaveInterception]:
    """Collect engine offers, then delegate deterministic selection to pure resolver."""
    from app.data.database.database import DB
    from app.engine import skill_system
    from app.engine.game_state import game
    from app.engine.movement import movement_funcs

    units = game.get_all_units()
    offers = set()
    for provider in units:
        offers.update(skill_system.save_intercept_offers(
            provider, attacker, protected, item, attack_distance))

    def is_armored(unit: Any) -> bool:
        klass = DB.classes.get(unit.klass)
        return bool(klass and klass.movement_group == 'Armors')

    request = SaveRequest(
        attacker=attacker, protected=protected, item=item,
        attack_distance=attack_distance, units=units,
        is_enemy=skill_system.check_enemy,
        is_ally=skill_system.check_ally,
        is_armored=is_armored,
        traversable=movement_funcs.check_traversable,
    )
    return resolve_save_interception(request, offers)
