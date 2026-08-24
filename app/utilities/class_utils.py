from typing import List, Optional, Set


def recursive_subclasses(ctype: type, _seen: Optional[Set[type]] = None) -> List[type]:
    """Return descendants once, retaining the previous depth-first order."""
    seen = _seen if _seen is not None else set()
    all_subclasses: List[type] = []
    for subclass in ctype.__subclasses__():
        if subclass in seen:
            continue
        seen.add(subclass)
        all_subclasses += recursive_subclasses(subclass, seen)
        all_subclasses.append(subclass)
    return all_subclasses
