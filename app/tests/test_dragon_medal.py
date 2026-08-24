import importlib
import json
import os
import unittest
from types import SimpleNamespace

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')

MARTIN_DESC = (
    'This unit gains a Dragon-type class. This unit\'s attack will always be '
    'effective against "Dragon-type" units.')
DRAGON_DESC = 'Unit\'s attack is effective against "Dragon-type" units.'


class DragonMedalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'items.json'),
                  encoding='utf-8') as items_file:
            cls.items = {item['nid']: item for item in json.load(items_file)}
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}

        RESOURCES.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)
        DB.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)
        cls.custom_items = importlib.import_module('custom_components.custom_item_components')

    def _component_value(self, prefab, nid):
        return next(value for component_nid, value in prefab['components']
                    if component_nid == nid)

    def test_both_medals_use_the_same_restriction_and_effect(self):
        martin = SimpleNamespace(nid='Martin', tags=[])
        dragon_unit = SimpleNamespace(nid='Other', tags=['Dragon'])
        normal_unit = SimpleNamespace(nid='Other', tags=[])

        for item_nid in ('Dragon_Medal', 'Dragon_Medal_Pro2'):
            with self.subTest(item_nid=item_nid):
                item = self.items[item_nid]
                restriction_value = self._component_value(
                    item, 'prf_unit_or_tags')
                restriction = self.custom_items.PrfUnitOrTags(
                    restriction_value)
                statuses = self._component_value(
                    item, 'multi_status_on_equip')

                self.assertTrue(restriction.available(martin, item))
                self.assertTrue(restriction.available(dragon_unit, item))
                self.assertFalse(restriction.available(normal_unit, item))
                expected_statuses = ['Dragon_Medal_Effect', 'Dragonskin_T4']
                if item_nid == 'Dragon_Medal_Pro2':
                    expected_statuses.append('Renewal_T3')
                self.assertEqual(expected_statuses, statuses)

    def test_medal_description_changes_for_martin_and_other_dragons(self):
        for item_nid in ('Dragon_Medal', 'Dragon_Medal_Pro2'):
            item = self.items[item_nid]
            change_desc = self._component_value(
                item, 'change_desc_on_equip')

            self.assertEqual(['Martin', 'Martin_Clone'], change_desc['list_unit'])
            self.assertEqual(MARTIN_DESC, change_desc['desc_for_unit'])
            self.assertEqual(DRAGON_DESC, change_desc['desc_for_other'])

    def test_equipped_effect_grants_dragon_effectiveness(self):
        effect_skill = self.skills['Dragon_Medal_Effect']
        override_nid = self._component_value(effect_skill, 'item_override')
        self.assertEqual('Dragon_Medal_Override', override_nid)

        override_item = self.items[override_nid]
        effective = self._component_value(
            override_item, 'effective_damage')
        self.assertEqual(['Dragon'], effective['effective_tags'])
        self.assertEqual(3.0, effective['effective_multiplier'])
        self.assertEqual(0, effective['effective_bonus_damage'])


if __name__ == '__main__':
    unittest.main()
