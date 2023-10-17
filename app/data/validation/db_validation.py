
from ast import Tuple
from typing import Any, List
from app.data.database.components import ComponentType
from app.data.database.database import Database
from app.data.database.database_validator import DatabaseValidatorEngine
from app.data.resources.resources import Resources
from app.data.validation.validation_errors import ItemComponentValidationError, SkillComponentValidationError
from app.events.python_eventing.preprocessor import Preprocessor


def validate_skills(database: Database, resources: Resources) -> List:
    validator = DatabaseValidatorEngine(database, resources)
    all_errors = []
    for skill in database.skills:
        for component in skill.components:
            # attribute components convey info by being present; they don't have values
            if not component.expose:
                continue
            types_and_values: List[Tuple[ComponentType, Any]] = []
            if component.expose == ComponentType.NewMultipleOptions:
                types_and_values = [(component.options[option], component.value[option]) for option in component.options.keys()]
            elif isinstance(component.expose, tuple):
                container = component.expose[0]
                value_type = component.expose[1]
                if container == ComponentType.List:
                    # list of nids
                    types_and_values = [(value_type, value) for value in component.value]
                elif container in (ComponentType.Dict, ComponentType.FloatDict):
                    # see elsewhere for usages: always dict of 'nid: int'
                    types_and_values = [(value_type, key) for key, _ in component.value]
                elif container == ComponentType.MultipleChoice:
                    # short-circuit. we don't use DB validation for this
                    if not component.value in value_type:
                        all_errors.append(SkillComponentValidationError(skill.nid, component.name, value_type, component.value))
                    continue
            else:
                types_and_values = [(component.expose, component.value)]
            for ctype, cvalue in types_and_values:
                if not validator.validate(ctype, cvalue):
                    all_errors.append(SkillComponentValidationError(skill.nid, component.name, ctype, cvalue))
    for item in database.items:
        for component in item.components:
            # attribute components convey info by being present; they don't have values
            if not component.expose:
                continue
            types_and_values: List[Tuple[ComponentType, Any]] = []
            if component.expose == ComponentType.NewMultipleOptions:
                types_and_values = [(component.options[option], component.value[option]) for option in component.options.keys()]
            elif isinstance(component.expose, tuple):
                container = component.expose[0]
                value_type = component.expose[1]
                if container == ComponentType.List:
                    # list of nids
                    types_and_values = [(value_type, value) for value in component.value]
                elif container in (ComponentType.Dict, ComponentType.FloatDict):
                    # see elsewhere for usages: always dict of 'nid: int'
                    types_and_values = [(value_type, key) for key, _ in component.value]
                elif container == ComponentType.MultipleChoice:
                    # short-circuit. we don't use DB validation for this
                    if not component.value in value_type:
                        all_errors.append(ItemComponentValidationError(item.nid, component.name, value_type, component.value))
                    continue
            else:
                types_and_values = [(component.expose, component.value)]
            for ctype, cvalue in types_and_values:
                if not validator.validate(ctype, cvalue):
                    all_errors.append(ItemComponentValidationError(item.nid, component.name, ctype, cvalue))
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
    skill_errors = validate_skills(database, resources)
    all_errors = event_errors + skill_errors
    return all_errors