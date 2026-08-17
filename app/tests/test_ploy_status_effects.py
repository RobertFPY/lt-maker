import json
import os
import unittest

from app.events import event_commands


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')
STAT_NIDS = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')


class PloyStatusEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}
        with open(os.path.join(PROJECT_PATH, 'game_data', 'events.json'),
                  encoding='utf-8') as events_file:
            cls.events = {event['nid']: event for event in json.load(events_file)}

    def components(self, nid):
        return dict(self.skills[nid]['components'])

    @staticmethod
    def component_expression(event_source, effect_nid):
        command = next(line for line in event_source
                       if line.startswith('modify_skill_component;')
                       and (';%s;' % effect_nid) in line)
        return command.split(';', 4)[4]

    def test_sudden_panic_tiers_trigger_before_combat_for_only_the_target(self):
        expectations = ((1, 5, 3), (2, 3, 5), (3, 1, 7))
        for tier, hp_gap, radius in expectations:
            with self.subTest(tier=tier):
                components = self.components('Sudden_Panic_T%d' % tier)
                condition = components['combat_condition']
                self.assertEqual('Global SuddenPanicApply',
                                 components['event_before_combat'])
                self.assertNotIn('do_nothing', components)
                self.assertIn("target.get_hp() < unit.get_hp() - %d" % hp_gap,
                              condition)
                self.assertIn('<= %d' % radius, condition)
                self.assertIn('other is not target', condition)
                self.assertIn('target.position is not None', condition)
                self.assertIn('other.team == target.team', condition)
                self.assertNotIn('skill_system.check_ally(target, other)',
                                 condition)
                self.assertNotIn('start of turn',
                                 self.skills['Sudden_Panic_T%d' % tier]['desc'].lower())

    def test_effect_statuses_have_the_expected_lifetimes_and_visibility(self):
        for nid, visible, lifetime in (
                ('Sudden_Panic_Effect', True, 'event_on_wait'),
                ('Panic_Ploy_Effect', False, 'lost_on_end_combat2'),
                ('Wily_Fighter_Neutralize_Effect', False, 'lost_on_end_combat2'),
                ('Stall_Ploy_Effect', True, 'lost_on_endstep')):
            with self.subTest(effect=nid):
                components = self.components(nid)
                self.assertIn(lifetime, components)
                self.assertEqual(visible, 'hidden' not in components)
                self.assertIn('stat_change', components)

        self.assertEqual([['MOV', 0]],
                         self.components('Stall_Ploy_Effect')['stat_change'])
        self.assertEqual([[stat, 0] for stat in STAT_NIDS],
                         self.components('Sudden_Panic_Effect')['stat_change'])

    def test_sudden_panic_arms_after_application_combat_then_expires_on_next_action(self):
        effect = self.components('Sudden_Panic_Effect')
        self.assertEqual(1, effect['priority'])
        self.assertEqual('Global SuddenPanicExpire', effect['event_on_wait'])

        advance = self.events['Global SuddenPanicAdvance']
        self.assertEqual('combat_end', advance['trigger'])
        advance_source = '\n'.join(advance['_source'])
        self.assertIn(
            'Sudden_Panic_Effect;priority;3', advance_source)
        self.assertIn(
            'Sudden_Panic_Effect;priority;2', advance_source)
        self.assertIn(
            'remove_skill;{unit};Sudden_Panic_Effect', advance_source)
        self.assertIn(
            'remove_skill;{unit2};Sudden_Panic_Effect', advance_source)

        expire_source = '\n'.join(
            self.events['Global SuddenPanicExpire']['_source'])
        self.assertIn('Sudden_Panic_Effect;priority;2', expire_source)
        self.assertIn(
            'remove_skill;{unit};Sudden_Panic_Effect', expire_source)

    def test_ploy_events_use_per_instance_stat_change_not_base_stat_mutation(self):
        for event_nid in ('Global SuddenPanicApply', 'Global PanicPloySkill',
                          'Global WilyFighterSkill', 'Global StallPloySkill'):
            with self.subTest(event=event_nid):
                source = '\n'.join(self.events[event_nid]['_source'])
                self.assertIn('give_skill', source)
                self.assertIn('modify_skill_component', source)
                self.assertNotIn('change_stats', source)
                self.assertNotIn('level_var', source)

        self.assertIn('remove_skill;{unit};Sudden_Panic_Effect;;no_banner',
                      '\n'.join(self.events['Global SuddenPanicExpire']['_source']))

        self.assertIn('-2 * max(0, unit2.stat_bonus(stat))',
                      '\n'.join(self.events['Global SuddenPanicApply']['_source']))
        self.assertIn('-2 * max(0, unit2.stat_bonus(stat))',
                      '\n'.join(self.events['Global PanicPloySkill']['_source']))
        self.assertIn('-max(0, unit2.stat_bonus(stat))',
                      '\n'.join(self.events['Global WilyFighterSkill']['_source']))
        self.assertIn("-max(0, unit2.get_stat('MOV') - 1)",
                      '\n'.join(self.events['Global StallPloySkill']['_source']))

    def test_migrated_event_commands_parse_strictly(self):
        for event_nid in ('Global SuddenPanicApply', 'Global SuddenPanicAdvance',
                          'Global SuddenPanicExpire',
                          'Global PanicPloySkill', 'Global WilyFighterSkill',
                          'Global StallPloySkill'):
            depth = 0
            for line in self.events[event_nid]['_source']:
                with self.subTest(event=event_nid, line=line):
                    command, error_index = event_commands.parse_text_to_command(
                        line, strict=True)
                    self.assertIsNotNone(command, error_index)
                    if line.startswith('if;'):
                        depth += 1
                    elif line == 'end':
                        depth -= 1
                        self.assertGreaterEqual(depth, 0)
            self.assertEqual(0, depth, event_nid)

    def test_transform_formulae_convert_only_positive_bonus_snapshots(self):
        class Unit:
            def __init__(self, bonuses, mov):
                self.bonuses = bonuses
                self.mov = mov

            def stat_bonus(self, stat):
                return self.bonuses.get(stat, 0)

            def get_stat(self, stat):
                return self.mov if stat == 'MOV' else self.stat_bonus(stat)

        unit = Unit({'STR': 6, 'MAG': 0, 'SKL': -4}, 6)
        namespace = {'unit2': unit, 'max': max}
        sudden = self.component_expression(
            self.events['Global SuddenPanicApply']['_source'],
            'Sudden_Panic_Effect')
        panic = self.component_expression(
            self.events['Global PanicPloySkill']['_source'],
            'Panic_Ploy_Effect')
        wily = self.component_expression(
            self.events['Global WilyFighterSkill']['_source'],
            'Wily_Fighter_Neutralize_Effect')
        stall = self.component_expression(
            self.events['Global StallPloySkill']['_source'],
            'Stall_Ploy_Effect')

        for expression in (sudden, panic):
            values = dict(eval(expression, namespace))
            self.assertEqual(-12, values['STR'])
            self.assertEqual(0, values['MAG'])
            self.assertEqual(0, values['SKL'])
        values = dict(eval(wily, namespace))
        self.assertEqual(-6, values['STR'])
        self.assertEqual(0, values['MAG'])
        self.assertEqual(0, values['SKL'])
        self.assertEqual([('MOV', -5)], eval(stall, namespace))

    def test_legacy_restore_events_and_after_combat_hooks_are_removed(self):
        for event_nid in ('Global PanicPloySkill2', 'Global WilyFighterSkill2',
                          'Global StallPloySkill2'):
            self.assertNotIn(event_nid, self.events)

        for nid in ('Panic_Ploy_T1', 'Panic_Ploy_T2', 'Panic_Ploy_T3',
                    'Wily_Fighter_Effect_1',
                    'Dull_Close_T1', 'Dull_Close_T2', 'Dull_Close_T3',
                    'Dull_Ranged_T1', 'Dull_Ranged_T2', 'Dull_Ranged_T3'):
            self.assertNotIn('event_after_combat', self.components(nid), nid)
        for nid in ('Stall_Ploy_T1', 'Stall_Ploy_T2', 'Stall_Ploy_T3'):
            self.assertNotIn('give_status_after_combat', self.components(nid), nid)


if __name__ == '__main__':
    unittest.main()
