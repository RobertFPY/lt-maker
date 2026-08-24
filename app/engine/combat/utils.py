from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.engine.objects.item import ItemObject
    from app.engine.objects.unit import UnitObject


def resolve_weapon(unit: UnitObject) -> Optional[ItemObject]:
    if unit:
        return unit.get_weapon()
    return None


def get_current_strike_true_damage(playback, attacker: UnitObject,
                                   defender: UnitObject) -> int:
    """Return damage brushes belonging to the most recently resolved strike."""
    marker_nids = {'mark_hit', 'mark_crit', 'mark_miss'}
    damage_nids = {'damage_hit', 'damage_crit'}
    marker_index = next((idx for idx in range(len(playback) - 1, -1, -1)
                         if playback[idx].nid in marker_nids), None)
    if marker_index is None:
        return 0
    marker = playback[marker_index]
    if marker.nid == 'mark_miss' or marker.attacker is not attacker \
            or marker.defender is not defender:
        return 0

    damage = 0
    for idx in range(marker_index - 1, -1, -1):
        brush = playback[idx]
        if brush.nid in marker_nids:
            break
        if brush.nid in damage_nids and brush.attacker is attacker \
                and brush.defender is defender:
            damage += max(0, brush.true_damage)
    return damage
