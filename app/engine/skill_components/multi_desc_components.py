from __future__ import annotations
import logging

from app.data.database.components import ComponentType
from app.data.database.skill_components import SkillComponent, SkillTags

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.engine.info_menu.multi_desc_utils import RawPages
    from app.engine.objects.skill import SkillObject
    from app.engine.objects.unit import UnitObject
    from app.utilities.typing import NID

class MultiDescSkill(SkillComponent):
    nid = 'multi_desc_skill'
    desc = "Define a list of Skill NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    author = 'Eretein'
    
    expose = (ComponentType.List, ComponentType.Skill)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]

class MultiDescItem(SkillComponent):
    nid = 'multi_desc_item'
    desc = "Define a list of Item NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Item)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]
    
class MultiDescLore(SkillComponent):
    nid = 'multi_desc_lore'
    desc = "Define a list of Lore NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Lore)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]

class MultiDescAffinity(SkillComponent):
    nid = 'multi_desc_affinity'
    desc = "Define a list of Affinity NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Affinity)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]

class MultiDescKlass(SkillComponent):
    nid = 'multi_desc_klass'
    desc = "Define a list of Class NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Class)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]

class MultiDescUnit(SkillComponent):
    nid = 'multi_desc_unit'
    desc = "Define a list of Unit NIDs whose info boxes should be attached to this skill's multi desc info box."
    tag = SkillTags.MULTI_DESC
    
    author = "Eretein"
    
    expose = (ComponentType.List, ComponentType.Unit)
    
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self.value, self.expose[1]

class EvalMultiDescSkill(SkillComponent):
    nid = 'eval_multi_desc_skill'
    desc = "Use eval to define a list of Skill NIDs whose info boxes should be attached to this skill's multi desc info box. The eval must resolve to a list of valid skill NIDs."
    tag = SkillTags.MULTI_DESC
    author = 'Eretein'
    
    expose = ComponentType.String
    
    def _eval_nids(self, skill: SkillObject, unit: UnitObject) -> list[NID]:
        from app.engine.evaluate import evaluate
        try:
            nids: list[NID] = evaluate(self.value, unit, local_args={'skill': skill})
            return nids
        except Exception as e:
            logging.error(f"Unable to evaluate {self.value}, {e}")
            return []
        
    def multi_desc(self, skill: SkillObject, unit: UnitObject) ->  RawPages:
        return self._eval_nids(skill, unit), ComponentType.Skill

class MultiDescNameOverride(SkillComponent):
    nid = 'multi_desc_name_override'
    desc = 'If set, and the skill is not the first skill in a sequence of multi desc boxes, show this evaluated string as its name instead.'
    tag = SkillTags.MULTI_DESC
    
    author = 'Eretein'
    
    expose = ComponentType.String
    
    def multi_desc_name_override(self, unit: UnitObject, skill: SkillObject) -> str:
        return self.value
    