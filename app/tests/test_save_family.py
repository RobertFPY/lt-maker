import json
import unittest
from pathlib import Path

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
SKILLS_PATH = PROJECT / 'game_data' / 'skills.json'


class SaveFamilyDataTests(unittest.TestCase):
    def tearDown(self):
        RESOURCES.load(str(Path(__file__).resolve().parents[2] / 'default.ltproj'), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(Path(__file__).resolve().parents[2] / 'default.ltproj'), CURRENT_SERIALIZATION_VERSION)

    def test_all_twenty_four_save_parents_use_the_exact_interceptor_contract(self):
        skills = {skill['nid']: skill for skill in json.loads(SKILLS_PATH.read_text(encoding='utf-8'))}
        stat_pairs = {'A_S': (('SPD',), True), 'A_D': (('DEF',), True),
                      'A_R': (('RES',), True), 'D_R': (('DEF', 'RES'), False)}
        for prefix, (stats, has_damage) in stat_pairs.items():
            for kind in ('Near', 'Far'):
                for tier in range(1, 4):
                    nid = f'{prefix}_{kind}_Save_T{tier}'
                    if prefix == 'D_R' and kind == 'Near':
                        nid = f'D_R_near_Save_T{tier}'
                    components = dict(skills[nid]['components'])
                    self.assertNotIn('do_nothing', components, nid)
                    self.assertIn('save_interceptor', components, nid)
                    value = components['save_interceptor']
                    self.assertEqual(kind.lower(), value['kind'])
                    self.assertEqual(1 if tier == 1 else 2, value['radius'])
                    self.assertEqual(tier, value['rank'])
                    self.assertEqual(tier + 1 if has_damage else 0, value['damage'])
                    self.assertEqual({stat: tier + 1 for stat in stats}, dict(value['stats']))

    def test_resources_and_database_load_all_twenty_four_save_interceptors(self):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        from app.engine import skill_component_access

        self.assertEqual('custom_components.custom_skill_components',
                         skill_component_access.get_component('save_interceptor').__class__.__module__)
        save_parents = [skill for skill in DB.skills if skill.nid in {
            *[f'{prefix}_{kind}_Save_T{tier}' for prefix in ('A_S', 'A_D', 'A_R', 'D_R')
              for kind in ('Near', 'Far') for tier in range(1, 4)],
            *[f'D_R_near_Save_T{tier}' for tier in range(1, 4)],
        }]
        self.assertEqual(24, len(save_parents))
        self.assertTrue(all(any(component.nid == 'save_interceptor' for component in skill.components)
                            for skill in save_parents))


if __name__ == '__main__':
    unittest.main()
