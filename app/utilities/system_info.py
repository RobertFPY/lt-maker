import sys

def is_editor_engine_built_version() -> bool:
    return hasattr(sys, 'frozen')