from typing import List

def recursive_subclasses(ctype: type) -> List[type]:
    all_subclasses: List[type] = []
    subclasses = ctype.__subclasses__()
    for subclass in subclasses:
        all_subclasses += recursive_subclasses(subclass)
    all_subclasses += subclasses
    return all_subclasses
