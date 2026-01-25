from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.data.database.components import ComponentType
from enum import Enum

from app.data.database.supports import Affinity
from app.engine import item_funcs

from app.data.database.database import DB
from app.engine.objects.item import ItemObject
from app.engine.objects.skill import SkillObject
from app.engine.objects.unit import UnitObject
from app.data.database.lore import Lore
from app.utilities.typing import NID
from app.data.database.klass import Klass

from typing import TYPE_CHECKING, Any, Callable, Optional, TypeAlias, Union, cast

import logging

class PageType(Enum):
    """Valid page types that the builder recognizes."""
    # alias ComponentType Enum, so we can source from hooks natively
    # just plug whatever here and update logic in the marked methods at the
    # bottom of the multidesc module.....
    # we alias, instead of just using component type, so devs / engine hackers
    # can someday easily add support for custom page types that don't rely on component type
    ITEM = ComponentType.Item
    SKILL = ComponentType.Skill
    LORE = ComponentType.Lore
    UNIT = ComponentType.Unit
    KLASS = ComponentType.Class
    AFFINITY = ComponentType.Affinity

# TODO: Update these when you add more objects that the builder recognizes...
Source = Union[SkillObject,
               ItemObject,
               Lore,
               UnitObject,
               Klass,
               Affinity,
               ]

RawPages: TypeAlias = tuple[list[NID], PageType]
Page: TypeAlias = tuple[NID, PageType]

@dataclass(init=True)
class InfoSource:
    """
    A unified wrapper around various data sources (e.g. skills, items, lore, klass),
    used by the multi desc builder to access descriptions and names without
    worrying about the specific structure of each object.

    This abstraction allows the engine to treat all sources uniformly when constructing
    chains of help dialogs, especially when multiple source types are mixed (e.g., items and skills).
    
    It supports both direct `Source` instances and NIDs that can be resolved to `Source`s.
    
    Attributes:
        obj (Source | None): The resolved object (e.g., SkillObject, Lore, etc.) or None if not found (ugh).
        _origin (tuple[NID, PageType]): Page where the source came from, stored as a tuple of the NID and its PageType (useful for logging/debugging!).
    
    Behavior:
        - If given a `Source`, `InfoSource` wraps it directly.
        - If given a `NID`, it attempts to resolve it to the appropriate object from the database.
        - If the object lacks common attributes like `desc`, `text`, or `name`, appropriate warnings are logged.
        - Acts transparently like the wrapped object via `__getattr__`, allowing attribute forwarding.
        - Equality is based on identity of the wrapped object, allowing comparison with either another `InfoSource` or the underlying object itself.
          
    """

    obj: Source | None
    _origin: Page
    
    def __init__(self, obj: NID | Source, page_type: PageType) -> None:
        if hasattr(obj, 'nid'):
            self.obj = cast(Source, obj)
            self._origin = (obj.nid, page_type)
        else:
            self.obj = self._to_source(obj, page_type)
            self._origin = (obj, page_type)

    @staticmethod
    def _to_source(entry: NID, page_type: PageType) -> Optional[Source]:
        """An NID to Source factory that uses a mapping table for extensibility."""
        from app.engine.game_state import game
        mapping: dict[PageType, Callable[[NID], Optional[Source]]] = {
            # just check if these NIDs still exist in the DB first, because some idiot could be deleting prefabs mid-playthrough and causing bad behaviour!...
            PageType.SKILL: lambda nid: (
                _get_skill(nid) if (nid in DB.skills) else None
            ),
            PageType.ITEM: lambda nid: (
                _get_item(nid) if (nid in DB.items) else None
            ),
            # don't need to instantiate for these types, so no need to check first
            PageType.LORE: lambda nid: DB.lore.get(nid),
            PageType.AFFINITY: lambda nid: DB.affinities.get(nid),
            PageType.KLASS: lambda nid: DB.classes.get(nid),
            # prefer a live instance of a unit, else fallback to prefab
            PageType.UNIT: lambda nid: game.get_unit(nid) or DB.units.get(nid)
        }

        resolver = mapping.get(page_type)
        return resolver(entry) if resolver else None

    @property
    def type(self) -> type | None:
        """Gets the underlying object's type."""
        if self.obj is None:
            return None
        return type(self.obj)
    
    @property
    def desc(self) -> str:
        if hasattr(self.obj, 'desc'):
            return self.obj.desc
        elif hasattr(self.obj, 'text'):
            return self.obj.text
        else:
            logging.warning(f"{self.type} from {self._origin} has neither 'desc' nor 'text'!")
            return ''    
        
    @property
    def nid(self) -> Optional[NID]:
        if hasattr(self.obj, 'nid'):
            return self.obj.nid
        else:
            logging.warning(f"{self.type} from {self._origin} has no 'nid'. Something has gone very wrong!")
            return None
    
    @property
    def name(self) -> str:
        if hasattr(self.obj, 'name'):
            return self.obj.name
        else:
            logging.warning(f"{self.type} from {self._origin} has no 'name'.")
            return ''
    
    @property
    def origin(self) -> tuple[NID, PageType]:
        return self._origin
    
    def __eq__(self, other: Any) -> bool:
        """
            For all intents, an `InfoSource` is equivalent to its underlying object, via attribute forwarding, and can be used interchangeably if needed. See how the multi_desc hooks and help dialogs are accessed via an `InfoSource` and not the underlying object.
        """
        if isinstance(other, InfoSource):
            return self.obj == other.obj
        else:
            return self.obj == other

    def __hash__(self):
        return hash(self.obj)
    
    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)
    
    def __bool__(self) -> bool:
        return bool(self.obj)
            
    def __getattr__(self, name: str):
        return getattr(self.obj, name)

def _get_skill(nid: NID) -> SkillObject:
    """
        Instantiates an anonymous copy of a skill from an NID.
    """
    skill = item_funcs.create_skill(None, nid)
    return skill

def _get_item(nid: NID) -> ItemObject:
    """
        Instantiates an anonymous copy of an item from an NID.
    """
    item = item_funcs.create_item(None, nid, assign_ownership=False)
    return item