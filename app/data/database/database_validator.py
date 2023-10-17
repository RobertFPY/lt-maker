from __future__ import annotations
from app.data.database.components import ComponentType
from app.data.database.database_types import DatabaseType
from app.data.database.weapons import WexpGain
from dataclasses import dataclass
import logging
from app.data.database.database import Database
from app.data.resources.resource_types import ResourceType
from app.data.resources.resources import Resources
from app.utilities.data import Data
from app.utilities.typing import NID
import re
from typing import Any, Callable, Dict, List, Set

@dataclass
class ValidationError():
    category: str
    owner: str
    where: str
    what: str

    def __str__(self) -> str:
        return "Error in %s:%s:%s - %s" % self.category, self.owner, self.where, self.what

    @classmethod
    def does_not_exist(self, nid):
        return "%s does not exist" % nid

def _nid_in_data(data: Data):
    return lambda nid: nid in data.keys()

class DatabaseValidatorEngine():
    def __init__(self, db: Database, resources: Resources):
        self.db = db
        self.resources = resources
        self._vmap: Dict[ComponentType | ResourceType | DatabaseType, Callable[[NID], bool]] = {
            ComponentType.WeaponType: _nid_in_data(db.weapons),
            ComponentType.WeaponRank: _nid_in_data(db.weapon_ranks),
            ComponentType.Unit: _nid_in_data(db.units),
            ComponentType.Class: _nid_in_data(db.classes),
            ComponentType.Tag: _nid_in_data(db.tags),
            ComponentType.Item: _nid_in_data(db.items),
            ComponentType.Skill: _nid_in_data(db.skills),
            ComponentType.Stat: _nid_in_data(db.stats),
            ComponentType.MapAnimation: _nid_in_data(resources.animations),
            ComponentType.Equation: _nid_in_data(db.equations),
            ComponentType.MovementType: lambda mtype: mtype in db.mcost.get_unit_types(),
            ComponentType.Sound: _nid_in_data(resources.sfx),
            ComponentType.AI: _nid_in_data(db.ai),
            ComponentType.Music: _nid_in_data(resources.music),
            ComponentType.CombatAnimation: _nid_in_data(resources.combat_anims),
            ComponentType.EffectAnimation: _nid_in_data(resources.combat_effects),
            ComponentType.Affinity: _nid_in_data(db.affinities),
            ComponentType.Terrain: _nid_in_data(db.terrain),
            ComponentType.Event: _nid_in_data(db.events),
        }

        # native types, don't really need to check these
        for ctype in (ComponentType.Bool, ComponentType.Int, ComponentType.Float, ComponentType.String,
                      ComponentType.Color3, ComponentType.Color4, ComponentType.StringDict, ComponentType.MultipleOptions):
            def _trivial_type(val):
                return True
            self._vmap[ctype] = _trivial_type

        # we shouldn't be validating these types. instead we should parse their elements and validate separately
        for ctype in (ComponentType.List, ComponentType.Dict, ComponentType.FloatDict,
                      ComponentType.MultipleChoice, ComponentType.NewMultipleOptions):
            def should_not_be_validating(nid):
                raise ValueError('%s should not be validated. Validate contents instead' % ctype)
            self._vmap[ctype] = should_not_be_validating

    def validate(self, dtype: ComponentType | ResourceType | DatabaseType, value: Any):
        return self._vmap[dtype](value)

    def validate_units(self):
        errors: List[ValidationError] = []
        for unit in self.db.units:
            if not self.validate_class(unit.klass):
                errors.append(ValidationError("Units", unit.nid, "klass", ValidationError.does_not_exist(unit.klass)))
        return errors

    def fill_and_trim(self, data_dict: dict, expected_keys: set, real_keys: set, default_value_factory: Callable):
        missing_keys = expected_keys - real_keys
        extraneous_keys = real_keys - expected_keys
        for key in missing_keys:
            data_dict[key] = default_value_factory()
        for key in extraneous_keys:
            del data_dict[key]

    def repair_units(self):
        all_weapon_types = set(self.db.weapons.keys())
        all_stats = set(self.db.stats.keys())
        for unit in self.db.units:
            # make sure each unit has an entry for every weapon type, and no extraneous ones
            self.fill_and_trim(unit.wexp_gain, all_weapon_types, set(unit.wexp_gain.keys()), lambda: WexpGain(False, 0, 0))
            # make sure each unit has an entry for every stat, and no extraneous ones
            self.fill_and_trim(unit.bases, all_stats, set(unit.bases.keys()), lambda: 0)
            self.fill_and_trim(unit.growths, all_stats, set(unit.growths.keys()), lambda: 0)

    def repair_klasses(self):
        all_weapon_types = set(self.db.weapons.keys())
        all_stats = set(self.db.stats.keys())
        for klass in self.db.classes:
            # make sure each klass has an entry for every weapon type, and no extraneous ones
            self.fill_and_trim(klass.wexp_gain, all_weapon_types, set(klass.wexp_gain.keys()), lambda: WexpGain(False, 0, 0))
            # make sure each klass has an entry for every stat in all dicts
            self.fill_and_trim(klass.bases, all_stats, set(klass.bases.keys()), lambda: 0)
            self.fill_and_trim(klass.growths, all_stats, set(klass.growths.keys()), lambda: 0)
            self.fill_and_trim(klass.growth_bonus, all_stats, set(klass.growth_bonus.keys()), lambda: 0)
            self.fill_and_trim(klass.promotion, all_stats, set(klass.promotion.keys()), lambda: 0)
            self.fill_and_trim(klass.max_stats, all_stats, set(klass.max_stats.keys()), lambda: 0)

    def repair_levels(self):
        for level in self.db.levels:
            all_level_units = set(level.units.keys())
            travelers: Dict[NID, NID] = {}
            for unit in level.units:
                # fix phantom travelers
                unit_traveler = unit.starting_traveler
                if unit_traveler and unit_traveler == unit.nid:
                    logging.error("Unit %s is its own traveler", unit.nid)
                    unit.starting_traveler = None
                    continue
                if unit_traveler and unit_traveler in travelers:
                    logging.error("Found traveler %s originally on unit %s, found duplicate on unit %s in level %s",
                                  unit_traveler, travelers[unit_traveler], unit.nid, level.nid)
                    unit.starting_traveler = None
                    continue
                if unit_traveler and unit_traveler not in all_level_units:
                    logging.error("Found traveler %s on unit %s in level %s that does not exist",
                                  unit_traveler, unit.nid, level.nid)
                    unit.starting_traveler = None
                    continue
                if unit_traveler and level.units.get(unit_traveler) and level.units.get(unit_traveler).starting_position:
                    logging.error("Traveler %s on unit %s is already on map", unit_traveler, unit.nid)
                    unit.starting_traveler = None
                    continue
                travelers[unit_traveler] = unit.nid

    def repair(self):
        """Only obvious repairs should be done here.
        """
        self.repair_units()
        self.repair_klasses()
        self.repair_levels()