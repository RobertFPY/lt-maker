import json
import os
import unittest


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class NoFamilyDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}

    def components(self, nid):
        return dict(self.skills[nid]['components'])

    def test_renewal_uses_flat_upkeep_healing_and_tier_priority(self):
        for tier, healing in ((1, '10'), (2, '15'), (3, '20')):
            with self.subTest(tier=tier):
                components = self.components('Renewal_T%d' % tier)
                self.assertEqual(tier - 1, components['priority'])
                self.assertEqual(healing, components['eval_regeneration'])
                self.assertNotIn('regeneration', components)

    def test_pegasus_flight_requires_strict_speed_advantage(self):
        for tier in range(1, 5):
            with self.subTest(tier=tier):
                condition = self.components('Pegasus_Flight_T%d' % tier)[
                    'combat_condition']
                self.assertIn("unit.get_stat('SPD') >", condition)
                self.assertNotIn("unit.get_stat('SPD') >=", condition)


if __name__ == '__main__':
    unittest.main()
