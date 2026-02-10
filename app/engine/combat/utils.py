from typing import Optional
from app.engine.objects.item import ItemObject
from app.engine.objects.unit import UnitObject


def resolve_weapon(unit: UnitObject) -> Optional[ItemObject]:
    if unit:
        return unit.get_weapon()
    return None
