from __future__ import annotations
from enum import Enum
from app.data.database.components import Component, ComponentType, get_objs_using

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from app.engine.objects.skill import SkillObject

class SkillTags(Enum):
    ATTRIBUTE = 'attribute'
    BASE = 'base'
    MOVEMENT = 'movement'
    COMBAT = 'combat'
    COMBAT2 = 'combat2'
    DYNAMIC = 'dynamic'
    FORMULA = 'formula'
    STATUS = 'status'
    TIME = 'time'
    CHARGE = 'charge'
    AESTHETIC = 'aesthetic'
    ADVANCED = 'advanced'
    EXTRA = 'extra'
    MULTI_DESC = 'multi_desc'

    CUSTOM = 'custom'
    HIDDEN = 'hidden'
    DEPRECATED = 'deprecated'

class SkillComponent(Component):
    skill: Optional[SkillObject] = None
    ignore_conditional: bool = False

def get_skills_using(expose: ComponentType, value, db) -> list:
    return get_objs_using(db.skills.values(), expose, value)
