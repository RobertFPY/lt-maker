from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.engine.objects.item import ItemObject
    from app.engine.objects.unit import UnitObject


def resolve_weapon(unit: UnitObject) -> Optional[ItemObject]:
    if unit:
        return unit.get_weapon()
    return None
