from app.data.serialization.migration import migrate_to_next
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.utilities.typing import NestedPrimitiveDict
from app.data.serialization.loaders import loader0

LOADERS = {
    0: loader0.load_as_dict,
}

def _dispatch_load(data_dir: str, version: int) -> NestedPrimitiveDict:
    if version < 0:
        raise ValueError("Unsupported serialization version {}".format(version))
    while version not in LOADERS:
        version -= 1
    return LOADERS[version](data_dir)

def load(data_dir: str, version: int) -> NestedPrimitiveDict:
    current_version = CURRENT_SERIALIZATION_VERSION
    loaded = _dispatch_load(data_dir, version)
    while version < current_version:
        loaded = migrate_to_next(loaded, version)
        version += 1
    return loaded