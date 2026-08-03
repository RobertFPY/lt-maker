from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType
from typing import Iterable, List


def import_submodules(
    package_name: str,
    package_paths: Iterable[str],
    *,
    reload_existing: bool = False,
) -> List[ModuleType]:
    """Import every direct module in a package from source or bytecode.

    Android packaging compiles project Python files to flat ``.pyc`` files and
    removes the corresponding ``.py`` sources.  ``pkgutil`` delegates discovery
    to Python's import machinery, so it supports both layouts.
    """
    discovered = sorted(
        (
            module_info
            for module_info in pkgutil.iter_modules(list(package_paths))
            if not module_info.ispkg and not module_info.name.startswith("_")
        ),
        key=lambda module_info: module_info.name,
    )
    imported: List[ModuleType] = []
    for module_info in discovered:
        qualified_name = f"{package_name}.{module_info.name}"
        was_loaded = qualified_name in sys.modules
        module = importlib.import_module(qualified_name)
        if reload_existing and was_loaded:
            module = importlib.reload(module)
        imported.append(module)
    return imported
