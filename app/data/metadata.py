from dataclasses import dataclass, asdict

from app.data.serialization.dataclass_serialization import dataclass_from_dict
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION

@dataclass
class Metadata():
    date: str = ""
    engine_version: str = ""
    serialization_version: int = CURRENT_SERIALIZATION_VERSION
    project: str = ""
    has_fatal_errors: bool = False
    as_chunks: bool = False

    def save(self):
        return asdict(self)

    def restore(self, d):
        if not d:
            return
        restored = dataclass_from_dict(self.__class__, d)
        self.__dict__ = restored.__dict__