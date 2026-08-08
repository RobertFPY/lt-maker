import unittest
from unittest.mock import Mock

from app.engine import config as cf
from app.engine import engine


class RecoveryGoldenScenarioTests(unittest.TestCase):
    def test_virtual_frame_driver_advances_only_outer_frames_and_restores_clock(self):
        from app.tests.recovery_trace_runner import VirtualFrameDriver

        original = dict(engine.constants)
        state = Mock()
        state.update.side_effect = [(None, True), (None, False)]
        game = Mock(state=state)
        try:
            with VirtualFrameDriver() as frames:
                frames.step(game, object())
                self.assertEqual(2, state.update.call_count)
                self.assertEqual(16, engine.constants['current_time'])
                self.assertEqual(0, engine.constants['last_time'])
                self.assertEqual(16, engine.constants['delta_t'])
        finally:
            engine.constants.update(original)
        self.assertEqual(original, engine.constants)

    def test_raw_input_frame_driver_routes_edges_through_input_manager(self):
        from app.engine import engine
        from app.tests.recovery_trace_runner import RawInputFrameDriver

        input_manager = Mock()
        input_manager.keys_pressed = {'SELECT': False}
        input_manager.joys_pressed = {'SELECT': False}
        input_manager.key_down_events = []
        input_manager.key_up_events = []
        input_manager.input_events = []
        input_manager.transient_input_consumed = False
        input_manager.key_map = {'SELECT': engine.key_map['enter']}
        input_manager.process_input.side_effect = ['SELECT', None]
        state = Mock()
        state.update.side_effect = [(None, False), (None, False)]
        game = Mock(state=state)

        with RawInputFrameDriver(input_manager) as frames:
            frames.press(game, object(), 'SELECT')

        self.assertEqual(['SELECT', None], [call.args[0] for call in state.update.call_args_list])
        raw_down = input_manager.process_input.call_args_list[0].args[0][0]
        raw_up = input_manager.process_input.call_args_list[1].args[0][0]
        self.assertEqual((engine.KEYDOWN, engine.KEYUP), (raw_down.type, raw_up.type))

    def test_scenario_registry_includes_the_pc_restart_slot_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_4', SCENARIOS['04_restart_current_chapter'].__name__)

    def test_scenario_registry_includes_the_simple_combat_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_6', SCENARIOS['06_simple_combat'].__name__)

    def test_scenario_registry_includes_the_animation_combat_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_7', SCENARIOS['07_animation_combat'].__name__)

    def test_scenario_registry_includes_the_base_combat_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_8', SCENARIOS['08_base_combat'].__name__)

    def test_scenario_registry_includes_the_skill_proc_hook_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS, SCENARIO_9_SEED

        self.assertEqual('capture_scenario_9', SCENARIOS['09_skill_proc_hooks'].__name__)
        self.assertEqual(0, SCENARIO_9_SEED)

    def test_scenario_registry_includes_the_one_use_item_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_10',
                         SCENARIOS['10_item_durability_and_broken'].__name__)

    def test_scenario_registry_includes_the_single_route_promotion_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_11',
                         SCENARIOS['11_promotion_class_change'].__name__)

    def test_scenario_registry_includes_the_aura_lifecycle_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_12', SCENARIOS['12_aura_lifecycle'].__name__)

    def test_scenario_registry_includes_the_fog_move_cancel_wait_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_13', SCENARIOS['13_fog_move_cancel_wait'].__name__)

    def test_scenario_registry_includes_the_tilemap_change_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_14', SCENARIOS['14_tilemap_change'].__name__)

    def test_scenario_registry_includes_the_phase_transition_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_15', SCENARIOS['15_phase_transition'].__name__)

    def test_scenario_registry_includes_the_fast_forward_equivalence_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_16', SCENARIOS['16_fast_forward_equivalence'].__name__)

    def test_scenario_registry_includes_the_observer_idle_hybrid_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_17',
                         SCENARIOS['17_observer_idle_hybrid'].__name__)

    def test_scenario_registry_includes_the_game_over_restart_contract(self):
        from app.tests.recovery_trace_runner import SCENARIOS

        self.assertEqual('capture_scenario_18',
                         SCENARIOS['18_game_over_restart'].__name__)

    def test_new_game_seed_uses_config_and_restores_it_after_failure(self):
        from app.tests.recovery_trace_runner import run_new_game_with_seed

        original_seed = cf.SETTINGS['random_seed']
        game = Mock()
        observed = []

        def capture():
            observed.append(cf.SETTINGS['random_seed'])
            raise RuntimeError('capture failure')

        try:
            with self.assertRaisesRegex(RuntimeError, 'capture failure'):
                run_new_game_with_seed(game, 1701, capture)
            game.build_new.assert_called_once_with()
            self.assertEqual([1701], observed)
            self.assertEqual(original_seed, cf.SETTINGS['random_seed'])
        finally:
            cf.SETTINGS['random_seed'] = original_seed


if __name__ == '__main__':
    unittest.main()
