from __future__ import annotations

from enum import Enum
from typing import Callable, Optional
from dataclasses import dataclass


from app.engine import item_funcs, item_system
from app.engine.game_state import game

from app.engine.objects.unit import UnitObject
from app.engine.objects.item import ItemObject

class ItemOptionModes(Enum):
    NO_USES = 0
    USES = 1
    FULL_USES = 2
    FULL_USES_AND_REPAIR = 3
    VALUE = 4
    STOCK_AND_VALUE = 5
    CUSTOM = 6

@dataclass
class UsesDisplayConfig:
    get_curr_uses: Callable[[ItemObject, UnitObject], str] = None
    delim: str = ''
    get_max_uses: Callable[[ItemObject, UnitObject], str] = None
    get_uses_color: Callable[[ItemObject, UnitObject], str] = None

    unit: Optional[UnitObject] = None
    item: Optional[ItemObject] = None

    def __add__(self, other: UsesDisplayConfig) -> UsesDisplayConfig:
        return UsesDisplayConfig(
            get_curr_uses=other.get_curr_uses if other.get_curr_uses is not None else self.get_curr_uses,
            delim=other.delim if other.delim is not None else self.delim,
            get_max_uses=other.get_max_uses if other.get_max_uses is not None else self.get_max_uses,
            get_uses_color=other.get_uses_color if other.get_uses_color is not None else self.get_uses_color,
            unit=self.unit,
            item=self.item
        )

    def get_uses(self) -> str:
        curr_uses = self.get_curr_uses(self.unit, self.item) if self.get_curr_uses else None
        return str(curr_uses) if curr_uses is not None else None

    def get_max(self) -> str:
        max_uses = self.get_max_uses(self.unit, self.item) if self.get_max_uses else None
        return str(max_uses) if max_uses is not None else None

    def get_color(self) -> str:
        # Grab Custom Color If It Exists
        return self.get_uses_color(self.unit, self.item) if self.get_uses_color else None

    @staticmethod
    def from_item(item: ItemObject, owner: Optional[UnitObject] = None):
        if not item:
            return None

        owner = game.get_unit(item.owner_nid) if owner is None else owner
        if not owner:
            return None

        return item_system.item_uses_display(owner, item)