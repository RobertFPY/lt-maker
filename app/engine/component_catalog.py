"""Build runtime component catalogs from explicitly active module namespaces."""
from __future__ import annotations

from collections import defaultdict
from types import ModuleType
from typing import Iterable, Type

from app.utilities.data import Data


class ComponentCatalogError(ValueError):
    """Raised when two active component definitions claim the same NID."""


def _origin(component_t: type) -> str:
    return f'{component_t.__module__}.{component_t.__qualname__}'


def build_component_catalog(
        base_type: Type,
        engine_modules: Iterable[ModuleType],
        custom_modules: Iterable[ModuleType],
        catalog_label: str,
) -> Data[type]:
    """Return component classes declared by the given active modules only.

    ``__subclasses__`` is process-global and therefore retains test imports and
    definitions from previously loaded projects.  Runtime catalog membership is
    instead defined by the engine modules and project modules active now.
    """
    seen: set[type] = set()
    components: list[type] = []
    for module in (*engine_modules, *custom_modules):
        for candidate in vars(module).values():
            if not isinstance(candidate, type) or candidate in seen:
                continue
            if candidate is base_type or not issubclass(candidate, base_type):
                continue
            if candidate.__module__ != module.__name__ or candidate.nid is None:
                continue
            seen.add(candidate)
            components.append(candidate)

    by_nid: dict[str, list[type]] = defaultdict(list)
    for component_t in components:
        by_nid[component_t.nid].append(component_t)
    collisions = {
        nid: component_types for nid, component_types in by_nid.items()
        if len(component_types) > 1
    }
    if collisions:
        details = '; '.join(
            f"{nid}: {', '.join(_origin(component_t) for component_t in component_types)}"
            for nid, component_types in collisions.items())
        raise ComponentCatalogError(f'Duplicate {catalog_label} component NID(s): {details}')
    return Data(components)
