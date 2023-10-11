from typing import Type

from app.engine.codegen.codegen_utils import get_codegen_header
from app.events.event_commands import ALL_EVENT_COMMANDS, EventCommand, Tags
from app.events.python_eventing.utils import FORBIDDEN_PYTHON_COMMAND_NIDS


def create_wrapper_func(command_name: str, command_t: Type[EventCommand]):
    command_param_names = command_t.keywords
    command_params = ', '.join(command_param_names)
    if command_params:
        command_params += ', '

    command_params_list = '[' + ', '.join([f'"{param}"' for param in command_param_names]) + ']'

    command_optional_param_names = command_t.optional_keywords
    command_optional_params = ', '.join(["%s=None" % param for param in command_optional_param_names])
    if command_optional_params:
        command_optional_params += ', '

    command_param_dict_str = ', '.join(['"%s": %s' % (param, param) for param in command_param_names + command_optional_param_names])
    command_param_dict_str = '{' + command_param_dict_str + '}'
    func = \
"""
def {command_name}({command_params}{command_optional_params}):
    parameters = {command_param_dict}
    parameters = dict(filter(optional_value_filter({command_params_list}), parameters.items()))
    return event_commands.{command_type}(parameters=parameters).FLAGS('from_python')
""".format(command_name=command_name, command_type=command_t.__name__, command_params_list=command_params_list,
           command_params=command_params, command_optional_params=command_optional_params,
           command_param_dict=command_param_dict_str)
    return func

def generate_event_command_python_wrappers():
    import os
    dir_path = os.path.dirname(os.path.realpath(__file__))
    generated_event_wrappers = open(os.path.join(dir_path, 'python_event_command_wrappers.py'), 'w')

    generated_event_wrappers.writelines(get_codegen_header())

    with open(os.path.join(dir_path, 'python_event_commands_base.py'), 'r') as event_commands_base:
        # copy item system base
        for line in event_commands_base.readlines():
            generated_event_wrappers.write(line)

    for command_name, command_t in ALL_EVENT_COMMANDS.items():
        if not command_t.tag in [Tags.HIDDEN, Tags.FLOW_CONTROL]:
            if not command_t.nid in FORBIDDEN_PYTHON_COMMAND_NIDS:
                func_str = create_wrapper_func(command_name, command_t)
                generated_event_wrappers.write(func_str)


    generated_event_wrappers.close()