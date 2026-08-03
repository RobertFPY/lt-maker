import json
from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).parents[2]
PROJECT = PROJECT_ROOT / 'Fire Emblem Tales of The Golden Knight.ltproj'


class DifficultySetupProjectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(
            encoding='utf-8'))
        cls.event = next(event for event in events
                         if event['nid'] == '0 DieuChinhTheoDoKho')

    def test_difficulty_event_targets_the_real_enemy_unit_nids(self):
        source = '\n'.join(self.event['_source'])

        self.assertNotRegex(source, r'\b(?:Hard|Lunatic|Nightmare)_\d+\b')
        expected = {f'Enemy_{index}' for index in range(18)}
        actual = set(re.findall(r';(Enemy_\d+);', source))
        self.assertTrue(actual)
        self.assertTrue(actual <= expected)

    def test_each_difficulty_branch_only_mutates_its_declared_group(self):
        levels = json.loads((PROJECT / 'game_data' / 'levels.json').read_text(
            encoding='utf-8'))
        level_zero = next(level for level in levels if level['nid'] == '0')
        groups = {group['nid']: set(group['units'])
                  for group in level_zero['unit_groups']}
        active_group = None

        for source_line in self.event['_source']:
            line = source_line.strip()
            for difficulty in ('Hard', 'Lunatic', 'Nightmare'):
                if "game.mode.nid == '%s'" % difficulty in line:
                    active_group = groups['Enemy1' + difficulty]
                    break
            else:
                if not line or active_group is None:
                    continue
                parts = line.split(';')
                if parts[0] not in {
                    'set_stats', 'modify_item_component', 'change_item_name',
                }:
                    continue
                self.assertIn(parts[1], active_group, line)


if __name__ == '__main__':
    unittest.main()
