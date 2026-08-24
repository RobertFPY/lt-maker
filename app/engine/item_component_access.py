from functools import lru_cache
import sys
from types import ModuleType
from typing import List, Type

from app.data.database.components import ComponentType
from app.data.database.item_components import ItemComponent, ItemTags
from app.engine.component_catalog import build_component_catalog
from app.utilities.data import Data


def _engine_component_modules() -> tuple[ModuleType, ...]:
    from app.engine import item_components
    prefix = item_components.__name__ + '.'
    return tuple(module for name, module in sorted(sys.modules.items())
                 if name.startswith(prefix) and isinstance(module, ModuleType))


@lru_cache(1)
def get_cached_item_components(proj_dir: str):
    from app.data.resources.resources import RESOURCES
    catalog = build_component_catalog(
        ItemComponent, _engine_component_modules(),
        RESOURCES.get_loaded_custom_component_modules(), 'item')
    # Sort by tag
    return Data(sorted(catalog.values(),
                       key=lambda x: list(ItemTags).index(x.tag) if x.tag in list(ItemTags) else 100))

def get_item_components() -> Data[Type[ItemComponent]]:
    from app.data.database.database import DB
    return get_cached_item_components(DB.current_proj_dir)

def get_item_tags() -> List[ItemTags]:
    return list(ItemTags)

def get_component(nid):
    _item_components = get_item_components()
    base_class = _item_components.get(nid)
    if base_class:
        return base_class(base_class.value)
    return None

def restore_component(dat):
    nid, value = dat
    _item_components = get_item_components()
    base_class = _item_components.get(nid)
    if base_class:
        if isinstance(base_class.expose, tuple):
            if base_class.expose[0] == ComponentType.List:
                # Need to make a copy
                # so we don't keep the reference around
                copy = base_class(value.copy())
            elif base_class.expose[0] in (ComponentType.Dict, ComponentType.FloatDict):
                val = [v.copy() for v in value]
                copy = base_class(val)
            else:
                copy = base_class(value)
        else:
            copy = base_class(value)
        return copy
    return None

templates = {'Weapon Template': ('weapon', 'value', 'target_enemy', 'min_range', 'max_range', 'damage', 'hit', 'crit', 'weight', 'level_exp', 'weapon_type', 'weapon_rank', 'uses'),
             'Magic Weapon Template': ('weapon', 'value', 'target_enemy', 'min_range', 'max_range', 'damage', 'hit', 'crit', 'weight', 'level_exp', 'weapon_type', 'weapon_rank', 'magic', 'map_hit_add_blend', 'battle_cast_anim',  'uses', 'learn_spell_from_book'),
             'Spell Template': ('spell', 'value', 'min_range', 'max_range', 'weapon_type', 'weapon_rank', 'magic'),
             'Usable Template': ('usable', 'value', 'target_ally', 'uses')}

def get_templates():
    return templates.items()
