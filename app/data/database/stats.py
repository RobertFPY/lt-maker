from __future__ import annotations

from dataclasses import dataclass

from app.utilities.data import Data, Prefab
from app.utilities import NID, str_utils

from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from app.data.database.database import Database

@dataclass
class StatPrefab(Prefab):
    nid: str = None
    name: str = None
    maximum: int = 30
    desc: str = ""
    position: str = "left"
    
    growth_colors: bool = False
    hidden_stat: bool = False

    def __repr__(self) -> str:
        return self.nid

    def restore_attr(self, name: str, value: Any) -> Any:
        if name == 'position' and not value:
            return 'left'
        return value

class StatCatalog(Data[StatPrefab]):
    datatype = StatPrefab

    def add_new_default(self, db: Database) -> StatPrefab:
        nid = str_utils.get_next_name("New Stat", self.keys())
        new_stat = StatPrefab(nid, nid)
        self.append(new_stat)
        return new_stat

    def create_new(self, db: Database) -> StatPrefab:
        new_stat = self.add_new_default(db)
        nid = new_stat.nid
        for klass in db.classes:
            for stat_list in klass.get_stat_lists():
                if nid not in stat_list:
                    stat_list[nid] = 0
            klass.max_stats[nid] = new_stat.maximum
        for unit in db.units:
            for stat_list in unit.get_stat_lists():
                if nid not in stat_list:
                    stat_list[nid] = 0
        return new_stat

    def get_visible_stats(self) -> dict[NID, StatPrefab]:
        return {nid: stat for nid, stat in self.as_dict().items() if not stat.hidden_stat}
    