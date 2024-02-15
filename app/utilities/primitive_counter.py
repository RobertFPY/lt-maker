from collections import Counter
from typing import Any

from app.utilities.type_checking import check_valid_type

class PrimitiveCounter():
    """A Counter which has type-checking on what types can be saved (namely, primitives and builtin containers of primitives)"""
    _internal: Counter

    def __init__(self) -> None:
        self._internal = Counter()

    def __setitem__(self, key: str, val: Any):
        if not check_valid_type(val):
            raise ValueError("Cannot put object of type %s in game or level vars: %s" % (str(type(val)), str(val)))
        self._internal[key] = val

    def __getitem__(self, key: str):
        return self._internal[key]

    def get(self, key: str, default=None):
        return self._internal.get(key, default)

    def clear(self):
        self._internal.clear()