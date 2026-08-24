import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import action
from app.engine.ai_controller import PrimaryAI
from app.engine.combat.base_combat import BaseCombat
from app.engine.combat.simple_combat import SimpleCombat
from app.engine.combat.save_intercept import (SaveInterception, SaveOffer, SaveRequest,
                                              can_attempt_save_interception, get_active_save_interception, is_save_cleanup_active, resolve_save_interception,
                                              set_active_save_interception, set_save_cleanup_active)


class SaveInterceptionResolverTests(unittest.TestCase):
    def setUp(self):
        self.attacker = self.unit('attacker', (0, 0), team='enemy')
        self.protected = self.unit('protected', (2, 0))
        self.first = self.unit('first', (1, 0))
        self.second = self.unit('second', (0, 2))
        self.units = [self.attacker, self.protected, self.first, self.second]

    @staticmethod
    def unit(nid, position, team='player', hp=20, tags=()):
        return SimpleNamespace(nid=nid, position=position, team=team, dead=False,
                               is_dying=False, tags=set(tags), get_hp=lambda: hp)

    def request(self, distance=1, traversable=True):
        return SaveRequest(
            attacker=self.attacker,
            protected=self.protected,
            item=object(),
            attack_distance=distance,
            units=self.units,
            is_enemy=lambda left, right: left.team != right.team,
            is_ally=lambda left, right: left.team == right.team,
            is_armored=lambda unit: unit is not self.second,
            traversable=lambda unit, pos: traversable,
        )

    def offer(self, provider, kind='near', rank=1, skill_nid='Save', uid=1, radius=2):
        skill = SimpleNamespace(nid=skill_nid, uid=uid)
        return SaveOffer(provider, skill, kind, radius, rank, (('DEF', 2),), 2)

    def test_selects_highest_rank_then_shortest_then_game_order_then_skill_identity(self):
        best = self.offer(self.first, rank=3, skill_nid='Z', uid=9)
        same_rank_farther = self.offer(self.second, rank=3, skill_nid='A', uid=1)
        same_distance_later_skill = self.offer(self.first, rank=3, skill_nid='ZZ', uid=1)

        chosen = resolve_save_interception(
            self.request(), [same_rank_farther, same_distance_later_skill, best])

        self.assertIs(best, chosen.offer)

    def test_invalid_higher_rank_falls_back_and_near_far_do_not_cross(self):
        invalid = self.offer(self.second, rank=3)
        lower = self.offer(self.first, rank=2)

        self.assertIs(lower, resolve_save_interception(self.request(), [invalid, lower]).offer)
        self.assertIsNone(resolve_save_interception(self.request(distance=2), [lower]))
        far = self.offer(self.first, kind='far', rank=2)
        self.assertIs(far, resolve_save_interception(self.request(distance=2), [far]).offer)

    def test_non_armored_class_save_offer_can_intercept_but_normal_save_cannot(self):
        self.first.team = self.protected.team
        self.second.team = self.protected.team
        self.second.position = (1, 0)
        non_armored = SaveOffer(
            self.second, SimpleNamespace(nid='Dark_Gift_T1', uid=2),
            'near', 1, 4, (('SKL', 0),), 0, requires_armored=False)
        normal = self.offer(self.second, kind='near', rank=5)

        chosen = resolve_save_interception(self.request(), [normal, non_armored])
        self.assertIs(non_armored, chosen.offer)

    def test_rejects_non_armored_dead_offboard_tile_non_ally_and_untraversable_candidates(self):
        valid = self.offer(self.first)
        self.assertIsNone(resolve_save_interception(self.request(traversable=False), [valid]))
        self.first.dead = True
        self.assertIsNone(resolve_save_interception(self.request(), [valid]))
        self.first.dead = False
        self.first.position = None
        self.assertIsNone(resolve_save_interception(self.request(), [valid]))
        self.first.position = (1, 0)
        self.protected.tags.add('Tile')
        self.assertIsNone(resolve_save_interception(self.request(), [valid]))

    def test_begin_and_end_actions_restore_positions_fow_and_unit_turn_state(self):
        savior = self.unit('savior', (0, 1))
        protected = self.unit('protected', (1, 1))
        for unit, prior, movement, moved, finished in ((savior, (0, 0), 3, True, True),
                                                        (protected, (1, 0), 4, False, False)):
            unit.previous_position = prior
            unit.movement_left = movement
            unit.has_moved = moved
            unit.finished = finished
        board = SimpleNamespace(
            fow_vantage_point={'savior': (0, 0), 'protected': (1, 0)},
            get_fog_of_war_radius=lambda team: 0,
            update_fow=lambda pos, unit, sight: board.fow_vantage_point.__setitem__(unit.nid, pos),
        )
        fake_game = SimpleNamespace(
            board=board,
            boundary=SimpleNamespace(reset_fog_of_war=lambda: None),
            leave=lambda unit: setattr(unit, 'position', None),
            arrive=lambda unit, pos: setattr(unit, 'position', pos),
            on_alter_game_state=lambda: None,
        )
        offer = self.offer(savior)
        interception = SaveInterception(SimpleNamespace(protected=protected), offer)
        with patch.object(action, 'game', fake_game), patch.object(action.skill_system, 'sight_range', return_value=0):
            begin = action.BeginSaveInterception(interception)
            begin.do()
            self.assertEqual((1, 1), savior.position)
            self.assertIsNone(protected.position)
            self.assertIs(savior, get_active_save_interception().savior)
            self.assertIs(protected, get_active_save_interception().protected)

            action.EndSaveInterception(begin).do()

            end = action.EndSaveInterception(begin)
            end.reverse()
            self.assertEqual((1, 1), savior.position)
            self.assertIsNone(protected.position)
            begin.reverse()
            self.assertEqual((0, 1), savior.position)
            begin.execute()
            end.execute()

        self.assertEqual((0, 1), savior.position)
        self.assertEqual((1, 1), protected.position)
        self.assertEqual((0, 0), board.fow_vantage_point['savior'])
        self.assertEqual((1, 0), board.fow_vantage_point['protected'])
        self.assertEqual(((0, 0), 3, True, True),
                         (savior.previous_position, savior.movement_left, savior.has_moved, savior.finished))
        set_active_save_interception(None)

    def test_begin_save_action_round_trip_serializes_only_primitives_and_rebuilds_context(self):
        class SavedUnit(SimpleNamespace):
            pass

        class SavedSkill(SimpleNamespace):
            pass

        savior = SavedUnit(nid='savior', team='player', position=(0, 1), previous_position=(0, 0),
                           movement_left=3, has_moved=True, finished=True)
        protected = SavedUnit(nid='protected', team='player', position=(1, 1), previous_position=(1, 0),
                              movement_left=4, has_moved=False, finished=False)
        skill = SavedSkill(nid='A_S_near_Save_T1', uid=37)
        board = SimpleNamespace(
            fow_vantage_point={'savior': (0, 0), 'protected': (1, 0)},
            get_fog_of_war_radius=lambda team: 0,
            update_fow=lambda pos, unit, sight: board.fow_vantage_point.__setitem__(unit.nid, pos),
        )
        units = {unit.nid: unit for unit in (savior, protected)}
        fake_game = SimpleNamespace(
            board=board,
            boundary=SimpleNamespace(reset_fog_of_war=lambda: None),
            get_unit=lambda nid: units[nid],
            get_skill=lambda uid: skill if uid == skill.uid else None,
            leave=lambda unit: setattr(unit, 'position', None),
            arrive=lambda unit, pos: setattr(unit, 'position', pos),
            on_alter_game_state=lambda: None,
        )
        offer = SaveOffer(savior, skill, 'near', 1, 1, (('SPD', 2),), 2)
        interception = SaveInterception(SimpleNamespace(protected=protected), offer)
        with patch.object(action, 'game', fake_game), \
                patch.object(action, 'UnitObject', SavedUnit), \
                patch.object(action, 'SkillObject', SavedSkill), \
                patch.object(action.skill_system, 'sight_range', return_value=0):
            begin = action.BeginSaveInterception(interception)
            name, serialized = begin.save()
            self.assertEqual('BeginSaveInterception', name)
            self.assertNotIn('interception', serialized)
            self.assertEqual(('skill', 37), serialized['save_skill'])

            restored = action.BeginSaveInterception.restore(serialized)
            restored.do()
            context = get_active_save_interception()
            self.assertIs(savior, context.savior)
            self.assertIs(protected, context.protected)
            self.assertIs(skill, context.offer.skill)
            self.assertEqual((('SPD', 2),), context.offer.stats)
            restored.reverse()

            _, end_serialized = action.EndSaveInterception(restored).save()
            restored_end = action.EndSaveInterception.restore(end_serialized)
            restored_end.reverse()
            self.assertIs(skill, get_active_save_interception().offer.skill)
            restored_end.do()

        self.assertIsNone(get_active_save_interception())

    def test_save_cleanup_suppresses_forced_teleport_and_swap_without_mutating_positions(self):
        unit = self.unit('savior', (0, 0))
        other = self.unit('other', (1, 0))
        fake_game = SimpleNamespace(
            on_alter_game_state=lambda: None,
            leave=lambda unit: self.fail('movement must be suppressed'),
            arrive=lambda unit, pos: self.fail('movement must be suppressed'),
        )
        with patch.object(action, 'game', fake_game):
            set_save_cleanup_active(True)
            action.ForcedMovement(unit, (2, 0)).do()
            action.Teleport(unit, (2, 0)).do()
            action.Swap(unit, other).do()
        set_save_cleanup_active(False)
        self.assertEqual((0, 0), unit.position)
        self.assertEqual((1, 0), other.position)

    def test_end_save_clears_context_when_restore_fails(self):
        savior = self.unit('savior', (0, 1))
        protected = self.unit('protected', (1, 1))
        for unit in (savior, protected):
            unit.previous_position = unit.position
            unit.movement_left = 4
            unit.has_moved = False
            unit.finished = False
        board = SimpleNamespace(
            fow_vantage_point={'savior': (0, 1), 'protected': (1, 1)},
            get_fog_of_war_radius=lambda team: 0,
            update_fow=lambda pos, unit, sight: None,
        )
        fake_game = SimpleNamespace(
            board=board,
            boundary=SimpleNamespace(reset_fog_of_war=lambda: None),
            leave=lambda unit: setattr(unit, 'position', None),
            arrive=lambda unit, pos: setattr(unit, 'position', pos),
            on_alter_game_state=lambda: None,
        )
        interception = SaveInterception(SimpleNamespace(protected=protected), self.offer(savior))
        with patch.object(action, 'game', fake_game), patch.object(action.skill_system, 'sight_range', return_value=0):
            begin = action.BeginSaveInterception(interception)
            begin.do()
            with patch.object(begin, '_restore_fow', side_effect=RuntimeError('restore failed')):
                with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                    action.EndSaveInterception(begin).do()

        self.assertIsNone(get_active_save_interception())

    def test_ai_priority_uses_savior_and_does_not_leak_preview_context(self):
        controller = PrimaryAI.__new__(PrimaryAI)
        controller.unit = self.attacker
        controller.behaviour_targets = {(2, 0)}
        protected = self.protected
        savior = self.first
        interception = SaveInterception(SimpleNamespace(protected=protected), self.offer(savior))
        fake_game = SimpleNamespace(board=SimpleNamespace(get_unit=lambda pos: protected))
        with patch('app.engine.ai_controller.game', fake_game), \
                patch('app.engine.combat.save_intercept.find_save_interception', return_value=interception), \
                patch('app.engine.item_system.is_weapon', return_value=True), \
                patch('app.engine.ai_controller.item_system.ai_priority', side_effect=lambda unit, item, target, move: 7 if target is savior else 0), \
                patch('app.engine.ai_controller.skill_system.ai_priority_multiplier', return_value=1), \
                patch('app.engine.ai_controller.item_system.damage', return_value=None):
            priority = controller.compute_priority((2, 0), [], (0, 0), object())

        self.assertEqual(7, priority)
        self.assertIsNone(get_active_save_interception())

    def test_shared_eligibility_rejects_nonweapon_multi_splash_sequence_and_scripted_combat(self):
        weapon = SimpleNamespace(sequence_item=False)
        with patch('app.engine.item_system.is_weapon', return_value=True):
            self.assertTrue(can_attempt_save_interception(self.attacker, weapon, [(1, 0)], [(1, 0)], [[]]))
            self.assertFalse(can_attempt_save_interception(self.attacker, weapon, [[(1, 0)]], [(1, 0)], [[]]))
            self.assertFalse(can_attempt_save_interception(self.attacker, weapon, [(1, 0)], [(1, 0)], [[(2, 0)]]))
            self.assertFalse(can_attempt_save_interception(self.attacker, SimpleNamespace(sequence_item=True), [(1, 0)], [(1, 0)], [[]]))
            self.assertFalse(can_attempt_save_interception(self.attacker, weapon, [(1, 0)], [(1, 0)], [[]], script=['hit1']))
        with patch('app.engine.item_system.is_weapon', return_value=False):
            self.assertFalse(can_attempt_save_interception(self.attacker, weapon, [(1, 0)], [(1, 0)], [[]]))

    def test_end_combat_enables_save_movement_suppression_before_end_hooks_and_restores_afterward(self):
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.save_begin_action = object()
        combat.attacker = SimpleNamespace(strike_partner=None)
        combat.defender = None
        combat.main_item = object()
        combat.initial_random_state = object()
        combat.defenders = []
        combat.def_items = []
        combat.all_splash = []
        combat.full_playback = []
        unit = self.unit('moved', (0, 0))
        fake_game = SimpleNamespace(on_alter_game_state=lambda: None,
                                    leave=lambda unit: self.fail('end-combat forced move was not suppressed'),
                                    arrive=lambda unit, pos: self.fail('end-combat forced move was not suppressed'))
        seen = []

        def end_hook(*args):
            seen.append(is_save_cleanup_active())
            action.ForcedMovement(unit, (1, 0)).do()

        with patch.object(action, 'game', fake_game), \
                patch('app.engine.combat.simple_combat.skill_system.end_combat', side_effect=end_hook), \
                patch('app.engine.combat.simple_combat.item_system.end_combat'), \
                patch('app.engine.combat.simple_combat.skill_system.deactivate_all_combat_arts'), \
                patch('app.engine.combat.simple_combat.skill_system.post_combat'), \
                patch('app.engine.combat.simple_combat.action.RecordRandomState', return_value=SimpleNamespace(do=lambda: None)), \
                patch('app.engine.combat.simple_combat.action.EndSaveInterception', return_value=SimpleNamespace(do=lambda: None)), \
                patch('app.engine.combat.simple_combat.action.do', side_effect=lambda queued: queued.do()):
            combat.end_combat()

        self.assertTrue(all(seen))
        self.assertEqual((0, 0), unit.position)
        self.assertFalse(is_save_cleanup_active())

    def test_end_combat_exception_clears_save_context_and_restores_interception(self):
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.save_begin_action = object()
        combat.attacker = SimpleNamespace(strike_partner=None)
        combat.defender = None
        combat.main_item = object()
        combat.defenders = []
        combat.def_items = []
        combat.all_splash = []
        combat.full_playback = []
        restored = []
        with patch('app.engine.combat.simple_combat.skill_system.end_combat', side_effect=RuntimeError('hook failed')), \
                patch('app.engine.combat.simple_combat.action.EndSaveInterception', return_value=SimpleNamespace(do=lambda: restored.append(True))), \
                patch('app.engine.combat.simple_combat.action.do', side_effect=lambda queued: queued.do()):
            with self.assertRaisesRegex(RuntimeError, 'hook failed'):
                combat.end_combat()

        self.assertEqual([True], restored)
        self.assertFalse(is_save_cleanup_active())

    def test_base_combat_end_hook_suppresses_save_cleanup_movement(self):
        combat = BaseCombat.__new__(BaseCombat)
        combat.save_begin_action = object()
        combat.attacker = SimpleNamespace(strike_partner=None)
        combat.defender = SimpleNamespace(strike_partner=None, get_weapon=lambda: None)
        combat.main_item = object()
        combat.def_item = None
        combat.full_playback = []
        combat.initial_random_state = object()
        unit = self.unit('moved', (0, 0))
        seen = []
        fake_game = SimpleNamespace(on_alter_game_state=lambda: None,
                                    leave=lambda unit: self.fail('base-combat forced move was not suppressed'),
                                    arrive=lambda unit, pos: self.fail('base-combat forced move was not suppressed'))

        def end_hook(*args):
            seen.append(is_save_cleanup_active())
            action.ForcedMovement(unit, (1, 0)).do()

        with patch.object(action, 'game', fake_game), \
                patch('app.engine.combat.base_combat.skill_system.end_combat', side_effect=end_hook), \
                patch('app.engine.combat.base_combat.item_system.end_combat'), \
                patch('app.engine.combat.base_combat.skill_system.deactivate_all_combat_arts'), \
                patch('app.engine.combat.base_combat.skill_system.post_combat'), \
                patch('app.engine.combat.base_combat.action.RecordRandomState', return_value=SimpleNamespace(do=lambda: None)), \
                patch('app.engine.combat.base_combat.action.EndSaveInterception', return_value=SimpleNamespace(do=lambda: None)), \
                patch('app.engine.combat.base_combat.action.do', side_effect=lambda queued: queued.do()):
            combat.end_combat()

        self.assertTrue(all(seen))
        self.assertEqual((0, 0), unit.position)
        self.assertFalse(is_save_cleanup_active())


if __name__ == '__main__':
    unittest.main()
