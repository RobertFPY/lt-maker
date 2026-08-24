from functools import lru_cache
import sys
from types import ModuleType

from app.data.database.components import ComponentType
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine.component_catalog import build_component_catalog
from app.utilities.data import Data


def _engine_component_modules() -> tuple[ModuleType, ...]:
    from app.engine import skill_components
    prefix = skill_components.__name__ + '.'
    return tuple(module for name, module in sorted(sys.modules.items())
                 if name.startswith(prefix) and isinstance(module, ModuleType))


@lru_cache(1)
def get_cached_skill_components(proj_dir: str):
    from app.data.resources.resources import RESOURCES
    catalog = build_component_catalog(
        SkillComponent, _engine_component_modules(),
        RESOURCES.get_loaded_custom_component_modules(), 'skill')
    # Sort by tag
    return Data(sorted(catalog.values(),
                       key=lambda x: list(SkillTags).index(x.tag) if x.tag in list(SkillTags) else 100))

def get_skill_components():
    from app.data.database.database import DB
    return get_cached_skill_components(DB.current_proj_dir)

def get_skill_tags():
    return list(SkillTags)

def get_component(nid):
    _skill_components = get_skill_components()
    base_class = _skill_components.get(nid)
    if base_class:
        return base_class(base_class.value)
    return None

def restore_component(dat):
    nid, value = dat
    _skill_components = get_skill_components()
    base_class = _skill_components.get(nid)
    if base_class:
        if isinstance(base_class.expose, tuple):
            if base_class.expose[0] == ComponentType.List:
                # Need to make a copy
                # so we don't keep the reference around
                copy = base_class(value.copy())
            elif base_class.expose[0] in (ComponentType.Dict, ComponentType.FloatDict, ComponentType.StringDict):
                val = [v.copy() for v in value]
                copy = base_class(val)
            elif base_class.expose[0] == ComponentType.MultipleChoice:
                copy = base_class(value)
        else:
            copy = base_class(value)
        return copy
    return None

templates = {}

def get_templates():
    return templates.items()
