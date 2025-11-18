from __future__ import annotations

from app.engine.utils.ltcache import ltcached
import logging

from app.engine import item_system, skill_system, text_funcs
from app.engine.help_menu import HelpDialog, ItemHelpDialog, SkillHelpDialog
from app.engine.info_menu.multi_desc_utils import InfoSource, Page, PageType, RawPages

from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from app.utilities.typing import NID
    from app.engine.objects.item import ItemObject
    from app.engine.objects.skill import SkillObject
    from app.engine.objects.unit import UnitObject

@ltcached
def build_dialog_list(obj: SkillObject | ItemObject,
                        page_type: PageType,
                        unit: Optional[UnitObject]=None) -> list[HelpDialog]:
    """
        Builds a tree of HelpDialog objects from the root object.
        Ltcached for better latency while scrolling through units.
        Args:
            obj: The object that the player hovered on and pressed R to initiate the help dialog.
            page_type: The type of page that the initial object corresponds to.
            unit: The unit used in the context of this help dialog.
    """
    boxes: list[HelpDialog] = []
    local_seen: set[Page] = set()
    root: InfoSource = InfoSource(obj, page_type)
        
    root_box = get_dlg_box(root, page_type, unit, is_first=True)   
    boxes.append(root_box)
    local_seen.add((root.nid, page_type))
    
    pages = _collect(root, page_type, unit)
    if not pages:
        return boxes
    
    for nid, p_type in pages:
        if nid is None:
            continue
        if (nid, p_type) in local_seen:
            continue
        
        box = get_dlg_box(InfoSource(nid, p_type), p_type, unit)
        if box:
            boxes.append(box)
        local_seen.add((nid, p_type))
    
    return boxes

def _collect(entry: InfoSource | NID, page_type: PageType, unit: Optional[UnitObject], visited:Optional[set[Page]]=None) -> list[Page]:
    """Recursively collect all pages from the first entry."""
    
    visited = visited or set()
    stack: list[Page] = []
        
    # coerce NID into an InfoSource so we exclusively deal with InfoSource objects inside the tree
    # well, if the entry is somehow None, there's no point in trying to eke out more nodes from it
    # so just return the stack
    if not isinstance(entry, InfoSource):
        entry: InfoSource = InfoSource(entry, page_type)
        if entry.type is None:
            return stack
    
    # if the entry has already been seen, then it will build the same tree, so just return the stack
    entry_id = (entry.nid, page_type)
    if entry_id in visited:
        return stack
    visited.add(entry_id)
    
    pages: list[RawPages] = _get_pages(entry, page_type, unit)
    
    for nid_list, page_type in pages:
        # solves python shadowing shenanigans!
        current_page_type = PageType(page_type) if page_type else page_type
        for nid in nid_list:
            if nid is None:
                continue
            stack.append((nid, current_page_type))
            stack.extend(_collect(nid, current_page_type, unit, visited))
        
    return stack

def _get_pages(source: InfoSource, page_type: PageType, unit: Optional[UnitObject]) -> list[RawPages]:
    """Returns the raw pages of the obj sourced from hooks, including itself."""
    pages: list[RawPages] = [([source.nid], page_type.value)]
    
    if source.type is None:
        return pages
    
    if page_type == PageType.SKILL:
        pages.extend(skill_system.get_multi_desc(source, unit))
    elif page_type == PageType.ITEM:
        pages.extend(item_system.get_multi_desc(source, unit))
    else: # if ever anything else gains pages, need to update logic
        pass
    
    return pages

def get_dlg_box(source: InfoSource, page_type: PageType, unit: Optional[UnitObject], is_first:bool=False) -> Optional[HelpDialog]:
    """
        Get the help box from a live instance of the object.
        Won't work in all cases, since we could be using eval.
    """
    if source.type is None:
        logging.warning(f"Cannot find Source: {source.origin} for Unit: {unit} in database, skipping...")
        return None
        
    if page_type == PageType.ITEM:
        return ItemHelpDialog(source, first=is_first, unit_override=unit)
    elif page_type == PageType.SKILL:
        return SkillHelpDialog(source, first=is_first, unit_override=unit)
    # TODO: Someday make specialized HelpDialog classes for these? Requires some refactors in other places.
    elif page_type == PageType.LORE:
        return HelpDialog(text_funcs.translate_and_text_evaluate(source.desc, unit=unit), source.name)
    elif page_type == PageType.AFFINITY:
        return HelpDialog(text_funcs.translate_and_text_evaluate(source.desc))
    elif page_type == PageType.KLASS:
        return HelpDialog(text_funcs.translate_and_text_evaluate(source.desc, unit=unit), source.name)
    else:
        return HelpDialog(text_funcs.translate_and_text_evaluate(source.desc, unit=unit), name=source.name)
