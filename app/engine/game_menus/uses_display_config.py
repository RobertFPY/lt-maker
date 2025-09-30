from enum import Enum
from typing import Callable, Optional
from dataclasses import dataclass


from app.engine import item_system
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
    get_curr_uses: Callable[[ItemObject, UnitObject], str]
    delim: str
    get_max_uses: Callable[[ItemObject, UnitObject], str]
    get_uses_color: Callable[[ItemObject, UnitObject], str]

    unit: Optional[UnitObject]
    item: Optional[ItemObject]

    def get_uses(self) -> str:
        return str(self.get_curr_uses(self.unit, self.item))

    def get_max(self) -> str:
        return str(self.get_max_uses(self.unit, self.item))

    def get_color(self) -> str:
        return self.get_uses_color(self.unit, self.item)

    @staticmethod
    def from_item(item: ItemObject):
        if not item:
            return None

        owner = game.get_unit(item.owner_nid)
        if not owner:
            return None

        return item_system.item_uses_display(owner, item)