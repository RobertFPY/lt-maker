import json
from pathlib import Path
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class SabotageFamilyTests(TestCase):
    def test_every_tier_uses_ranked_upkeep_and_legacy_events_are_unreferenced(self):
        skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        text = (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8')
        for stat in ('Strength', 'Magic', 'Speed', 'Defense', 'Resistance'):
            for tier in range(1, 4):
                components = dict(skills[f'Sabotage_{stat}_T{tier}']['components'])
                self.assertIn('ranked_sabotage_upkeep', components)
                self.assertNotIn('golden_upkeep_event', components)
                effect = dict(skills[f'Sabotage_{stat}_T{tier}_Effect']['components'])
                self.assertIn('exclusive_upkeep_effect', effect)
        self.assertNotIn('Global SkillSabotage', text)
