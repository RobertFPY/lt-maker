import json
import os
import unittest


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class DragonsWrathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}

    def test_all_tiers_apply_every_effect_only_when_foe_initiates(self):
        for tier, resist, bonus in ((1, 0.9, 0.05), (2, 0.85, 0.1),
                                    (3, 0.8, 0.15), (4, 0.75, 0.15)):
            with self.subTest(tier=tier):
                components = dict(self.skills['Dragons_Wrath_T%d' % tier][
                    'components'])
                self.assertEqual("mode == 'defense'",
                                 components['combat_condition'])
                self.assertEqual(resist, components['resist_first_strike'])
                self.assertIn(str(bonus), components['dynamic_damage'])


if __name__ == '__main__':
    unittest.main()
