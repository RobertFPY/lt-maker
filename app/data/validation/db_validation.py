from __future__ import annotations
from ast import Tuple
from typing import Any, List

from app.data.database.components import ComponentType
from app.data.database.database import Database
from app.data.database.database_types import DatabaseType
from app.data.database.database_validator import DatabaseValidatorEngine
from app.data.resources.resource_types import ResourceType
from app.data.resources.resources import Resources
from app.data.validation.validation_errors import (
    ComponentValidationError, ItemComponentValidationError, LevelValidationError, SkillComponentValidationError)
from app.events.python_eventing.preprocessor import Preprocessor


def validate_levels(database: Database, resources: Resources) -> List:
    validator = DatabaseValidatorEngine(database, resources)
    all_errors = []
    for level in database.levels:
        def _validate(dtype, attr, can_be_null=True):
            val = getattr(level, attr)
            if not val and can_be_null:
                return
            if not validator.validate(dtype, val):
                all_errors.append(LevelValidationError(level.nid, attr, val, dtype))
        # _validate(ResourceType.TILEMAPS, 'tilemap')
        # _validate(ResourceType.TILEMAPS, 'bg_tilemap')
        # _validate(DatabaseType.PARTIES, 'party')
    return all_errors


def validate_items_and_skills(database: Database, resources: Resources) -> List:
    validator = DatabaseValidatorEngine(database, resources)
    def _validate_component_type(obj_name: str, component_name: str, ctype: ComponentType | Tuple[ComponentType, ComponentType], cval, is_item=False) -> List[ComponentValidationError]:
        if is_item:
            error_cls = ItemComponentValidationError
        else:
            error_cls = SkillComponentValidationError
        types_and_values = []
        if isinstance(ctype, tuple):
            container = ctype[0]
            value_type = ctype[1]
            if container == ComponentType.List:
                # list of nids
                types_and_values = [(value_type, value) for value in cval]
            elif container in (ComponentType.Dict, ComponentType.FloatDict):
                # see elsewhere for usages: always dict of 'nid: int'
                types_and_values = [(value_type, key) for key, _ in cval]
            elif container == ComponentType.MultipleChoice:
                # short-circuit. we don't use DB validation for this
                if not cval in value_type:
                    return [error_cls(obj_name, component_name, ComponentType.MultipleChoice, cval)]
        else:
            types_and_values = [(ctype, cval)]

        errors = []
        for ctype, cvalue in types_and_values:
            if not validator.validate(ctype, cvalue):
                errors.append(error_cls(obj_name, component_name, ctype, cvalue))
        return errors

    all_errors = []
    for skill in database.skills:
        for component in skill.components:
            # attribute components convey info by being present; they don't have values
            if not component.expose:
                continue
            if component.expose == ComponentType.NewMultipleOptions:
                for option in component.options.keys():
                    all_errors += _validate_component_type(skill.nid, component.name, component.options[option], component.value[option])
            else:
                all_errors += _validate_component_type(skill.nid, component.name, component.expose, component.value)

    for item in database.items:
        for component in item.components:
            # attribute components convey info by being present; they don't have values
            if not component.expose:
                continue
            if component.expose == ComponentType.NewMultipleOptions:
                for option in component.options.keys():
                    all_errors += _validate_component_type(item.nid, component.name, component.options[option], component.value[option], True)
            else:
                all_errors += _validate_component_type(item.nid, component.name, component.expose, component.value, True)
    return all_errors

def validate_events(database: Database, resources: Resources) -> List:
    ppsr = Preprocessor(database.events)
    all_errors = []
    for event in database.events:
        if event.is_python_event():
            all_errors += ppsr.verify_event(event.nid, event.source)
    return all_errors

def validate_all(database: Database, resources: Resources) -> List:
    event_errors = validate_events(database, resources)
    skill_errors = validate_items_and_skills(database, resources)
    level_errors = validate_levels(database, resources)
    all_errors = event_errors + skill_errors + level_errors
    return all_errors