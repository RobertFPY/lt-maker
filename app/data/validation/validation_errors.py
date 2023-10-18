from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.data.database.components import ComponentType
from app.data.database.database_types import DatabaseType
from app.data.resources.resource_types import ResourceType
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


@dataclass
class ObjectFieldValidationError():
    nid: NID
    field_name: str
    field_value: str
    field_type: ResourceType | DatabaseType
    object_type = "Unknown"
    error_template = \
"""
    In {type} '{nid}':
        Error in field {field_name}:
    No {field_type} with name '{field_value}'
"""

    def __str__(self) -> str:
        return self.error_template.format(type=self.object_type, nid=self.nid,
                                          field_name=self.field_name, field_value=str(self.field_value),
                                          field_type=self.field_type.name)

class LevelValidationError(ObjectFieldValidationError):
    object_type = "Level"