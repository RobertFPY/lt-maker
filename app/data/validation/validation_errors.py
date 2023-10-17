from dataclasses import dataclass
from typing import Any
from app.data.database.components import ComponentType
from app.events.python_eventing.errors import ERROR_TEMPLATE
from app.utilities.typing import NID

@dataclass
class ComponentValidationError():
    nid: NID
    component: str
    expected_type: ComponentType
    value: Any
    object_type = "Unknown"
    error_template = \
"""
    In {type} '{nid}':
        Type mismatch in Component '{component}':
    No {component_type} with name '{value}'
"""

    def __str__(self) -> str:
        return self.error_template.format(type=self.object_type, nid=self.nid,
                                          component=self.component, value=str(self.value),
                                          component_type=self.expected_type.name)

class ItemComponentValidationError(ComponentValidationError):
    object_type = "Item"

class SkillComponentValidationError(ComponentValidationError):
    object_type = "Skill"