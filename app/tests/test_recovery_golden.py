import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from app.engine import config as cf
from app.engine import engine


PC_REFERENCE_REVISION = '9314f54b49f4552b5a3d023b4da0012ce7dfbc89'
FIXTURE_ROOT = (Path(__file__).resolve().parent / 'fixtures' /
                'recovery_traces' / 'v1')
MANIFEST_PATH = FIXTURE_ROOT / 'manifest.json'
EVIDENCE_PATH = Path(__file__).resolve().parents[2] / 'recovery' / 'p1_t03_evidence.md'

EXPECTED_GOLDENS = {
    '01_new_game_first_playable_map': 'testing_proj_chapter_0_seed_1701_v1',
    '02_existing_save_load': 'testing_proj_chapter_0_seed_1701_in_memory_save_v1',
    '04_restart_current_chapter': 'testing_proj_chapter_0_restart_slot_seed_1701_v1',
    '05_standard_map_combat': 'testing_proj_chapter_0_eirika_map_combat_seed_1701_v1',
    '06_simple_combat': 'testing_proj_chapter_0_eirika_simple_combat_seed_1701_v1',
    '07_animation_combat': 'default_proj_chapter_0_eirika_animation_combat_seed_1701_v1',
    '08_base_combat': 'default_proj_chapter_0_eirika_vulnerary_base_combat_seed_1701_v1',
    '09_skill_proc_hooks': 'default_proj_chapter_0_eirika_luna_seed_0_v1',
    '10_item_durability_and_broken': 'default_proj_chapter_0_eirika_angelic_robe_one_use_seed_1701_v1',
    '11_promotion_class_change': 'default_proj_chapter_0_eirika_lunar_brace_single_route_seed_1701_v1',
    '12_aura_lifecycle': 'default_proj_chapter_0_eirika_inspiration_aura_save_load_seed_1701_v1',
    '13_fog_move_cancel_wait': 'default_proj_chapter_0_eirika_fog_move_cancel_wait_seed_1701_v1',
    '14_tilemap_change': 'testing_proj_chapter_0_prologue_to_magvel_tilemap_v1',
    '15_phase_transition': 'testing_proj_chapter_0_player_to_enemy_phase_seed_1701_v1',
    '16_fast_forward_equivalence': 'testing_proj_chapter_0_simple_combat_fast_forward_v1',
    '17_observer_idle_hybrid': 'testing_proj_chapter_0_observer_idle_seed_1701_v1',
    '18_game_over_restart': 'default_proj_chapter_0_death_eirika_restart_slot_seed_1701_v1',
}


class RecoveryGoldenFixtureTests(unittest.TestCase):
    def _manifest(self):
        with MANIFEST_PATH.open(encoding='utf-8') as manifest_file:
            return json.load(manifest_file)

    def test_manifest_locks_the_complete_trace_v1_fixture_set(self):
        manifest = self._manifest()
        self.assertEqual(1, manifest['schema_version'])
        self.assertEqual(PC_REFERENCE_REVISION, manifest['reference_revision'])

        scenarios = {record['scenario_id']: record for record in manifest['scenarios']}
        self.assertEqual(set(EXPECTED_GOLDENS) | {'03_event_save_load'}, set(scenarios))
        s3 = scenarios['03_event_save_load']
        self.assertEqual('N/A — REFERENCE-UNSUPPORTED', s3['status'])
        self.assertNotIn('fixture_path', s3)
        self.assertFalse(list(FIXTURE_ROOT.glob('03_*.jsonl')))

    def test_each_golden_has_a_locked_trace_v1_header_and_hash(self):
        manifest = self._manifest()
        evidence = EVIDENCE_PATH.read_text(encoding='utf-8')
        for record in manifest['scenarios']:
            if record['scenario_id'] == '03_event_save_load':
                continue
            with self.subTest(scenario_id=record['scenario_id']):
                self.assertEqual(1, record['schema_version'])
                self.assertEqual(PC_REFERENCE_REVISION, record['reference_revision'])
                self.assertEqual(EXPECTED_GOLDENS[record['scenario_id']],
                                 record['input_fixture_id'])
                fixture_path = Path(record['fixture_path'])
                self.assertEqual(FIXTURE_ROOT.resolve(), fixture_path.resolve().parent)
                self.assertTrue(fixture_path.is_file())
                digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest().upper()
                self.assertEqual(record['sha256'], digest)
                self.assertIn('`%s`' % digest, evidence)
                self.assertIn(record['fixture_path'], evidence)

                records = [json.loads(line) for line in
                           fixture_path.read_text(encoding='utf-8').splitlines()]
                headers = [entry for entry in records if entry['kind'] == 'trace_header']
                self.assertEqual(1, len(headers))
                header = headers[0]
                self.assertEqual(1, header['schema_version'])
                self.assertEqual('logical-trace-v1', header['serializer'])
                self.assertEqual(PC_REFERENCE_REVISION, header['reference_revision'])
                self.assertEqual(record['scenario_id'], header['scenario_id'])
                self.assertEqual(record['input_fixture_id'], header['input_fixture_id'])
                self.assertEqual(record['checkpoint_ids'], [
                    entry['checkpoint_id'] for entry in records
                    if entry['kind'] == 'checkpoint'
                ])


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
