from app.utilities.typing import NestedPrimitiveDict

MIGRATORS = {
}

def migrate_to_next(data: NestedPrimitiveDict, version: int) -> NestedPrimitiveDict:
    if version not in MIGRATORS:
        raise NotImplementedError("Migration to next version from {} not implemented".format(version))
    return MIGRATORS[version](data)