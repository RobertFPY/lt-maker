import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine.combat import animation_combat as animation_combat_module
from app.engine.combat import base_combat as base_combat_module
from app.engine.combat import simple_combat as simple_combat_module
from app.engine.combat.animation_combat import AnimationCombat
from app.engine.combat.base_combat import BaseCombat
from app.engine.combat.simple_combat import SimpleCombat


class _OrderedSolver:
    def __init__(self, order):
        self.order = order
        self.phase = 0

    def get_state(self):
        return self.phase < 2

    def do(self):
        phase = self.phase
        self.order.append(f'solver.do.{phase}')
        return [f'action.{phase}'], [SimpleNamespace(nid=f'playback.{phase}')]

    def setup_next_state(self):
        self.order.append(f'solver.advance.{self.phase}')
        self.phase += 1


class _ObservedBaseCombat(BaseCombat):
    order = None

    def start_combat(self):
        self.order.append('hooks.start')

    def start_event(self, full_animation=False):
        self.order.append(('event.CombatStart', full_animation))


class BaseCombatTransactionTests(unittest.TestCase):
    def test_constructor_runs_hooks_and_combat_start_synchronously(self):
        order = []
        attacker = SimpleNamespace(strike_partner=None, get_weapon=lambda: None)
        defender = SimpleNamespace(
            strike_partner=None, position=(1, 0), get_weapon=lambda: None)
        _ObservedBaseCombat.order = order

        with patch.object(base_combat_module, 'CombatPhaseSolver', return_value=Mock()):
            combat = _ObservedBaseCombat(attacker, object(), defender, [])

        self.assertEqual([
            'hooks.start',
            ('event.CombatStart', False),
        ], order)
        self.assertEqual(0, combat._counter)
        self.assertEqual('init', combat.state)

    def test_first_update_drains_all_phases_before_cleanup_updates(self):
        order = []
        solver = _OrderedSolver(order)
        combat = BaseCombat.__new__(BaseCombat)
        combat._counter = 0
        combat.state = 'init'
        combat.state_machine = solver
        combat.full_playback = []
        combat.actions = []
        combat.playback = []
        combat.start_combat = Mock()
        combat.start_event = Mock()
        combat._apply_actions = lambda: [
            order.append(f'apply.{act}') for act in combat.actions
        ]
        combat.clean_up0 = Mock(side_effect=lambda: order.append('cleanup0'))
        combat.clean_up1 = Mock(side_effect=lambda: order.append('cleanup1'))
        combat.clean_up2 = Mock(side_effect=lambda: order.append('cleanup2'))

        self.assertFalse(combat.update())

        self.assertEqual([
            'solver.do.0',
            'apply.action.0',
            'solver.advance.0',
            'solver.do.1',
            'apply.action.1',
            'solver.advance.1',
        ], order)
        self.assertFalse(solver.get_state())
        self.assertEqual(
            ['playback.0', 'playback.1'],
            [brush.nid for brush in combat.full_playback])

        self.assertFalse(combat.update())
        self.assertEqual('cleanup1', combat.state)
        self.assertFalse(combat.update())
        self.assertEqual('cleanup2', combat.state)
        self.assertTrue(combat.update())
        self.assertEqual([
            'solver.do.0',
            'apply.action.0',
            'solver.advance.0',
            'solver.do.1',
            'apply.action.1',
            'solver.advance.1',
            'cleanup0',
            'cleanup1',
            'cleanup2',
        ], order)

    def test_cleanup_override_runs_attacker_and_defender_skill_and_item_hooks(self):
        order = []
        combat = BaseCombat.__new__(BaseCombat)
        combat.attacker = object()
        combat.defender = object()
        combat.main_item = object()
        combat.def_item = object()
        combat.full_playback = []

        with (
                patch.object(
                    base_combat_module, 'resolve_weapon',
                    return_value=combat.def_item),
                patch.object(
                    base_combat_module.skill_system, 'cleanup_combat',
                    side_effect=lambda *_args: order.append('skill')),
                patch.object(
                    base_combat_module.item_system, 'cleanup_combat',
                    side_effect=lambda *_args: order.append('item')),
        ):
            combat.cleanup_combat()

        self.assertEqual(['skill', 'item', 'skill', 'item'], order)

    def test_base_combat_remains_no_turn(self):
        combat = BaseCombat.__new__(BaseCombat)

        with patch.object(SimpleCombat, 'handle_state_stack') as tactical_policy:
            self.assertIsNone(combat.handle_state_stack())

        self.assertFalse(BaseCombat.finalizes_turn)
        tactical_policy.assert_not_called()


def _animation_combat_for_state(state):
    combat = AnimationCombat.__new__(AnimationCombat)
    combat.state = state
    combat.last_update = 0
    combat._skip = False
    combat.arena_combat = False
    combat.playback = []
    combat.full_playback = []
    combat.actions = []
    combat.proc_icons = []
    combat.left_hp_bar = Mock()
    combat.left_hp_bar.done.return_value = True
    combat.right_hp_bar = Mock()
    combat.right_hp_bar.done.return_value = True
    combat.left = SimpleNamespace(
        get_hp=lambda: 10, is_dying=False, sprite=Mock())
    combat.right = SimpleNamespace(
        get_hp=lambda: 10, is_dying=False, sprite=Mock())
    combat.attacker = SimpleNamespace(sprite=Mock())
    combat.defender = SimpleNamespace(sprite=Mock())
    combat.left_battle_anim = Mock()
    combat.left_battle_anim.done.return_value = True
    combat.left_battle_anim.is_transform.return_value = False
    combat.right_battle_anim = Mock()
    combat.right_battle_anim.done.return_value = True
    combat.right_battle_anim.is_transform.return_value = False
    combat.lp_battle_anim = None
    combat.rp_battle_anim = None
    combat.current_battle_anim = Mock()
    combat.current_battle_anim.state = 'idle'
    combat.update_anims = Mock()
    combat.ui_should_be_hidden = Mock(return_value=False)
    return combat


class AnimationCombatTransactionTests(unittest.TestCase):
    def _update(self, combat):
        with (
                patch.object(
                    animation_combat_module.engine, 'get_time',
                    return_value=1000),
                patch.object(
                    animation_combat_module,
                    'is_android_render_optimization_enabled',
                    return_value=False),
        ):
            return combat.update()

    def test_resource_preinit_states_do_not_advance_gameplay(self):
        for state, expected_state, expected_order in (
                ('animation_setup', 'paint_setup', ['animations']),
                ('paint_setup', 'init', ['paint', 'stats'])):
            with self.subTest(state=state):
                order = []
                combat = _animation_combat_for_state(state)
                combat.setup_battle_animations = Mock(
                    side_effect=lambda: order.append('animations'))
                combat.initial_paint_setup = Mock(
                    side_effect=lambda: order.append('paint'))
                combat._set_stats = Mock(
                    side_effect=lambda _playback: order.append('stats'))
                combat.start_combat = Mock()
                combat.start_event = Mock()
                combat.state_machine = Mock()
                combat.clean_up0 = Mock()
                combat.clean_up1 = Mock()
                combat.clean_up2 = Mock()
                fake_game = SimpleNamespace(
                    state=SimpleNamespace(change=Mock()))

                with patch.object(animation_combat_module, 'game', fake_game):
                    self.assertFalse(self._update(combat))

                self.assertEqual(expected_order, order)
                self.assertEqual(expected_state, combat.state)
                self.assertEqual([], combat.actions)
                self.assertEqual([], combat.full_playback)
                fake_game.state.change.assert_not_called()
                combat.start_combat.assert_not_called()
                combat.start_event.assert_not_called()
                combat.state_machine.do.assert_not_called()
                combat.clean_up0.assert_not_called()
                combat.clean_up1.assert_not_called()
                combat.clean_up2.assert_not_called()

    def test_normal_init_keeps_hooks_visual_setup_and_stats_in_one_update(self):
        order = []
        combat = _animation_combat_for_state('init')
        combat._skip = False
        combat.view_pos = (3, 4)
        combat.start_combat = Mock(
            side_effect=lambda: order.append('hooks.start'))
        combat.attacker.sprite.change_state.side_effect = \
            lambda state: order.append(f'attacker.{state}')
        combat.defender.sprite.change_state.side_effect = \
            lambda state: order.append(f'defender.{state}')
        combat._set_stats = Mock(
            side_effect=lambda _playback: order.append('stats'))
        fake_game = SimpleNamespace(
            cursor=SimpleNamespace(
                combat_show=lambda: order.append('cursor.show'),
                set_pos=lambda pos: order.append(('cursor.pos', pos))),
            state=SimpleNamespace(
                change=lambda state: order.append(('state.change', state))),
        )

        with patch.object(animation_combat_module, 'game', fake_game):
            self.assertFalse(self._update(combat))

        self.assertEqual([
            'hooks.start',
            'attacker.combat_attacker',
            'defender.combat_defender',
            'cursor.show',
            ('cursor.pos', (3, 4)),
            ('state.change', 'move_camera'),
            'stats',
        ], order)
        self.assertEqual('red_cursor', combat.state)

    def test_arena_init_keeps_hooks_stats_pairing_and_offsets_in_one_update(self):
        order = []
        combat = _animation_combat_for_state('arena_init')
        combat.arena_combat = True
        combat.start_combat = Mock(
            side_effect=lambda: order.append('hooks.start'))
        combat._set_stats = Mock(
            side_effect=lambda _playback: order.append('stats'))
        combat.pair_battle_animations = Mock(
            side_effect=lambda frames: order.append(('pair', frames)))

        self.assertFalse(self._update(combat))

        self.assertEqual([
            'hooks.start', 'stats', ('pair', 0),
        ], order)
        self.assertEqual(1, combat.bar_offset)
        self.assertEqual(1, combat.name_offset)
        self.assertEqual(1, combat.platform_offset)
        self.assertEqual('arena_fade_in', combat.state)

    def test_init_pause_runs_combat_start_event_before_music_state(self):
        order = []
        combat = _animation_combat_for_state('init_pause')
        combat._skip = True
        combat.battle_background = Mock()
        combat.start_event = Mock(
            side_effect=lambda full: order.append(('event', full)))

        self.assertFalse(self._update(combat))

        self.assertEqual([('event', True)], order)
        combat.battle_background.set_normal.assert_called_once_with()
        self.assertEqual('battle_music', combat.state)

    def test_battle_music_checks_and_initiates_transform_in_one_update(self):
        order = []
        combat = _animation_combat_for_state('battle_music')
        combat.start_battle_music = Mock(
            side_effect=lambda: order.append('music'))
        combat.left_battle_anim.is_transform.return_value = True
        combat.left_battle_anim.initiate_transform.side_effect = \
            lambda: order.append('left.transform')

        self.assertFalse(self._update(combat))

        self.assertEqual(['music', 'left.transform'], order)
        self.assertEqual('transform', combat.state)

    def test_begin_phase_runs_solver_and_reaches_proc_destination_in_one_update(self):
        order = []
        combat = _animation_combat_for_state('begin_phase')
        combat.state_machine = Mock()
        combat.state_machine.get_state.return_value = True
        combat.state_machine.do.side_effect = lambda: (
            order.append('solver.do') or
            (['generated-action'], [SimpleNamespace(nid='attack_proc')]))
        attacker = SimpleNamespace(nid='attacker')
        defender = SimpleNamespace(nid='defender')
        combat.get_actors = Mock(return_value=(
            attacker, None, defender, None, combat.current_battle_anim))
        combat.get_from_full_playback = Mock(return_value=[])
        combat.get_from_playback = Mock(
            side_effect=lambda nid: [object()] if nid == 'attack_proc' else [])
        combat.set_up_proc_animation = Mock(
            side_effect=lambda nid: (
                order.append(('proc', nid)), setattr(combat, 'state', nid)))

        self.assertFalse(self._update(combat))

        self.assertEqual(['solver.do', ('proc', 'attack_proc')], order)
        self.assertEqual(['generated-action'], combat.actions)
        self.assertEqual(
            ['attack_proc'], [brush.nid for brush in combat.full_playback])
        self.assertEqual('attack_proc', combat.state)

    def test_start_hit_and_spell_hit_apply_before_playback_and_solver_advance(self):
        for method_name in ('start_hit', 'spell_hit'):
            with self.subTest(method=method_name):
                order = []
                combat = _animation_combat_for_state('anim')
                combat.actions = ['first', 'second']
                combat.playback = [SimpleNamespace(nid='heal_hit')]
                combat.state_machine = Mock()
                combat.state_machine.setup_next_state.side_effect = \
                    lambda: order.append('solver.advance')
                combat._handle_playback = Mock(
                    side_effect=lambda *_args: order.append('playback'))

                with patch.object(
                        animation_combat_module.action, 'do',
                        side_effect=lambda act: order.append(f'action.{act}')):
                    getattr(combat, method_name)()

                self.assertEqual([
                    'action.first',
                    'action.second',
                    'solver.advance',
                    'playback',
                ], order)

    def test_combat_hit_groups_cleanup0_with_on_hit_effect_setup(self):
        order = []
        combat = _animation_combat_for_state('combat_hit')
        attacker, item = object(), object()
        defender, def_item = object(), object()
        combat.clean_up0 = Mock(
            side_effect=lambda: order.append('cleanup0'))
        combat.get_actors = Mock(return_value=(
            attacker, item, defender, def_item, combat.current_battle_anim))
        combat.current_battle_anim.get_effect.side_effect = \
            lambda *_args, **_kwargs: order.append('effect.get') or 'effect'
        combat.current_battle_anim.add_effect.side_effect = \
            lambda _effect: order.append('effect.add')

        with patch.object(
                animation_combat_module.item_system, 'on_hit_effect',
                side_effect=lambda *_args: order.append('effect.lookup') or 'fx'):
            self.assertFalse(self._update(combat))

        self.assertEqual([
            'cleanup0', 'effect.lookup', 'effect.get', 'effect.add',
        ], order)
        self.assertEqual('hp_change', combat.state)

    def test_hp_ready_resumes_and_sets_dying_wait_in_one_update(self):
        order = []
        combat = _animation_combat_for_state('hp_change')
        combat._delay_death = False
        combat.left = SimpleNamespace(get_hp=lambda: 0)
        combat.right = SimpleNamespace(get_hp=lambda: 10)
        combat.current_battle_anim.can_proceed.return_value = True
        combat.current_battle_anim.resume.side_effect = \
            lambda: order.append('resume')
        combat.left_battle_anim.start_dying_animation.side_effect = \
            lambda: order.append('left.dying')
        combat.current_battle_anim.wait_for_dying.side_effect = \
            lambda: order.append('wait_for_dying')

        self.assertFalse(self._update(combat))

        self.assertEqual([
            'resume', 'left.dying', 'wait_for_dying',
        ], order)
        self.assertEqual('anim', combat.state)

    def test_end_combat_and_exp_pause_keep_reference_cleanup_groups(self):
        order = []
        combat = _animation_combat_for_state('end_combat')
        combat.focus_exp = Mock(
            side_effect=lambda: order.append('focus_exp'))
        combat.move_camera = Mock(
            side_effect=lambda: order.append('move_camera'))

        self.assertFalse(self._update(combat))

        self.assertEqual(['focus_exp', 'move_camera'], order)
        self.assertEqual('exp_pause', combat.state)

        combat = _animation_combat_for_state('exp_pause')
        combat._skip = True
        combat.clean_up1 = Mock(
            side_effect=lambda: order.append('cleanup1'))

        self.assertFalse(self._update(combat))

        self.assertEqual(['focus_exp', 'move_camera', 'cleanup1'], order)
        self.assertEqual('exp_wait', combat.state)

    def test_fade_out_and_arena_out_finish_cleanup_and_end_skip_atomically(self):
        for state in ('fade_out', 'arena_out'):
            with self.subTest(state=state):
                order = []
                combat = _animation_combat_for_state(state)
                combat.viewbox_time = 250
                combat.bg_black_progress = 1
                combat.build_viewbox = Mock()
                combat.finish = Mock(
                    side_effect=lambda: order.append('finish'))
                combat.clean_up2 = Mock(
                    side_effect=lambda: order.append('cleanup2'))
                combat.end_skip = Mock(
                    side_effect=lambda: order.append('end_skip'))

                self.assertTrue(self._update(combat))

                self.assertEqual([
                    'finish', 'cleanup2', 'end_skip',
                ], order)

    def test_arena_back_and_forced_death_semantics_remain_intact(self):
        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state_machine = SimpleNamespace(total_rounds=3)

        combat.stop_arena()

        self.assertEqual(0, combat.state_machine.total_rounds)
        self.assertTrue(AnimationCombat.finalizes_turn)

        combat.arena_combat = True
        unit = SimpleNamespace(
            nid='arena_unit', position=(0, 0), is_dying=True)
        fake_game = SimpleNamespace(
            state=SimpleNamespace(change=Mock()),
            records=SimpleNamespace(get_killer=lambda *_args: None),
            level=None,
            get_unit=Mock(),
            events=SimpleNamespace(trigger=Mock()),
            death=SimpleNamespace(force_death=Mock()),
        )

        with (
                patch.object(simple_combat_module, 'game', fake_game),
                patch.object(simple_combat_module.skill_system, 'on_death'),
        ):
            combat.handle_death([unit])

        fake_game.state.change.assert_not_called()
        fake_game.death.force_death.assert_called_once_with(unit)


if __name__ == '__main__':
    unittest.main()
