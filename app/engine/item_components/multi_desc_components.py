from __future__ import annotations
import logging

from app.data.database.components import ComponentType
from app.data.database.item_components import ItemComponent, ItemTags

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.engine.info_menu.multi_desc_utils import RawPages
    from app.engine.objects.item import ItemObject
    from app.engine.objects.unit import UnitObject

class MultiDescItem(ItemComponent):
    nid = 'multi_desc_item'
    desc = "Define a list of Item NIDs whose info boxes should be attached to this item's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Item)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]
    
class MultiDescSkill(ItemComponent):
    nid = 'multi_desc_skill'
    desc = "Define a list of Skill NIDs whose info boxes should be attached to this item's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Skill)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]

class MultiDescLore(ItemComponent):
    nid = 'multi_desc_lore'
    desc = "Define a list of Lore NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Lore)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]

class MultiDescAffinity(ItemComponent):
    nid = 'multi_desc_affinity'
    desc = "Define a list of Affinity NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Affinity)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]

class MultiDescKlass(ItemComponent):
    nid = 'multi_desc_klass'
    desc = "Define a list of Klass NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Class)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]

class MultiDescUnit(ItemComponent):
    nid = 'multi_desc_unit'
    desc = "Define a list of Unit NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = ItemTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Unit)
    
    def multi_desc(self, item: ItemObject, unit: UnitObject) -> RawPages:
        return self.value, self.expose[1]

class MultiDescNameOverride(ItemComponent):
    nid = 'multi_desc_name_override'
    desc = 'If set, and the item is not the first item in a sequence of multi desc boxes, show this evaluated string as its name instead. The name override also works if the name of the item is set to be visible through the `ShowItemName` component.'
    tag = ItemTags.MULTI_DESC
    
    author = 'Eretein'
    
    expose = ComponentType.String
    
    def multi_desc_name_override(self, unit: UnitObject, item: ItemObject) -> str:
        return self.value
    
class ShowItemName(ItemComponent):
    nid = 'show_item_name'
    desc = "The item's name is shown inside its help dialog box."
    tag = ItemTags.MULTI_DESC

    author = 'Eretein'
    
    def show_item_name_in_help_dlg(self, unit: UnitObject, item: ItemObject) -> bool:
        return True