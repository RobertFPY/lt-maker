import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine.combat import map_combat as map_combat_module
from app.engine.combat import simple_combat as simple_combat_module
from app.engine.combat.map_combat import MapCombat
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


class _ObservedSimpleCombat(SimpleCombat):
    order = None

    def _full_setup(self, attacker, main_item, items, positions,
                    main_target_positions, splash_positions):
        self.main_item = main_item
        self.items = items
        self.defenders = []
        self.splashes = []
        self.target_positions = positions
        self.defender = None
        self.def_item = None

    def start_combat(self):
        self.order.append('hooks.start')

    def start_event(self, full_animation=False):
        self.order.append('event.CombatStart')


def _map_combat_for_state(state):
    combat = MapCombat.__new__(MapCombat)
    combat.state = state
    combat.last_update = 0
    combat._skip = False
    combat.health_bars = {}
    combat.animations = []
    combat.first_phase = False
    combat.cast_pose = False
    combat.actions = []
    combat.playback = []
    combat.full_playback = []
    combat.attacker = SimpleNamespace(
        position=None, strike_partner=None, sprite=Mock(), skills=[])
    combat.defender = None
    combat.main_item = object()
    combat.def_item = None
    combat.attack_partner_weapon = None
    combat.defense_partner_weapon = None
    combat.target_positions = [None]
    return combat


class SimpleCombatTransactionTests(unittest.TestCase):
    def test_constructor_completes_hooks_event_solver_and_actions_in_order(self):
        order = []
        solver = _OrderedSolver(order)
        _ObservedSimpleCombat.order = order

        with patch.object(
                simple_combat_module, 'CombatPhaseSolver',
                return_value=solver), patch.object(
                    simple_combat_module.action, 'execute',
                    side_effect=lambda act: order.append(f'apply.{act}')):
            combat = _ObservedSimpleCombat(
                object(), object(), [object()], [(0, 0)], [(1, 0)],
                [[]], None)

        self.assertEqual([
            'hooks.start',
            'event.CombatStart',
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
        self.assertEqual('combat', combat.state)

    def test_cleanup_updates_keep_reference_order(self):
        order = []
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.state = 'combat'
        combat.state_machine = Mock()
        combat.state_machine.get_state.return_value = False
        combat.clean_up0 = Mock(side_effect=lambda: order.append('cleanup0'))
        combat.clean_up1 = Mock(side_effect=lambda: order.append('cleanup1'))
        combat.clean_up2 = Mock(side_effect=lambda: order.append('cleanup2'))

        self.assertFalse(combat.update())
        self.assertEqual('post_combat', combat.state)
        self.assertFalse(combat.update())
        self.assertEqual('exp_pause', combat.state)
        self.assertTrue(combat.update())
        self.assertEqual(['cleanup0', 'cleanup1', 'cleanup2'], order)


class MapCombatTransactionTests(unittest.TestCase):
    @patch.object(map_combat_module.engine, 'get_time', return_value=100)
    def test_terminal_detection_runs_cleanup0_in_same_update(self, _get_time):
        combat = _map_combat_for_state('begin_phase')
        combat.state_machine = Mock()
        combat.state_machine.get_state.return_value = False
        combat.clean_up0 = Mock()

        self.assertFalse(combat.update())

        combat.clean_up0.assert_called_once_with()
        self.assertEqual('exp_wait', combat.state)

    @patch.object(map_combat_module.item_system, 'no_map_hp_display',
                  return_value=True)
    @patch.object(map_combat_module.engine, 'get_time', return_value=100)
    def test_solver_result_enters_reference_visual_wait_without_staging_state(
            self, _get_time, _no_hp_display):
        combat = _map_combat_for_state('begin_phase')
        combat._skip = True
        combat.state_machine = Mock()
        combat.state_machine.get_state.return_value = True
        combat.state_machine.do.return_value = (
            ['generated-action'], [SimpleNamespace(nid='phase')])

        self.assertFalse(combat.update())

        combat.state_machine.do.assert_called_once_with()
        self.assertEqual(['generated-action'], combat.actions)
        self.assertEqual(['phase'], [brush.nid for brush in combat.full_playback])
        self.assertEqual('proc_animations', combat.state)

    @patch.object(map_combat_module.engine, 'get_time', return_value=100)
    def test_playback_and_action_commit_share_one_update(self, _get_time):
        order = []
        combat = _map_combat_for_state('anim')
        combat._skip = True
        combat._handle_playback = Mock(
            side_effect=lambda: order.append('playback'))
        combat._apply_actions = Mock(
            side_effect=lambda: order.append('actions'))

        self.assertFalse(combat.update())

        self.assertEqual(['playback', 'actions'], order)
        self.assertEqual('hp_bar_wait', combat.state)

    @patch.object(map_combat_module.engine, 'get_time', return_value=100)
    def test_visual_wait_does_not_advance_early(self, _get_time):
        combat = _map_combat_for_state('start_anim')

        self.assertFalse(combat.update())

        self.assertEqual('start_anim', combat.state)


if __name__ == '__main__':
    unittest.main()
