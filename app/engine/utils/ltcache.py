import functools
import uuid

class LTCache():
    _state: uuid.UUID
    def __init__(self):
        self._state = uuid.uuid1()

    def alter_state(self):
        self._state = uuid.uuid1()

    def get_state(self) -> uuid.UUID:
        return self._state

LT_CACHE = None
def init() -> LTCache:
    """Init the LTCache instance."""
    global LT_CACHE
    if LT_CACHE is None:
        LT_CACHE = LTCache()
    return LT_CACHE

def get_state() -> uuid.UUID:
    """Get the current state of the LTCache."""
    global LT_CACHE
    if LT_CACHE is None:
        return uuid.uuid1()
    return LT_CACHE.get_state()

def alter_state():
    """Alter the state of the LTCache."""
    global LT_CACHE
    if LT_CACHE is not None:
        LT_CACHE.alter_state()

def ltcached(func):
    """Decorator to cache the result of a function."""
    func = functools.lru_cache()(func)
    prev_state = get_state()
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal prev_state
        curr_state = get_state()
        if curr_state != prev_state:
            func.cache_clear()
            prev_state = curr_state
        return func(*args, **kwargs)
    return wrapper