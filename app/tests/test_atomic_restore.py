"""P2-T02 regression tests for authoritative save-restore transactions."""

from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

if not pygame.display.get_init():
    pygame.display.init()
if pygame.display.get_surface() is None:
    pygame.display.set_mode((1, 1))

# Match engine startup import order and avoid the battle-animation import cycle.
from app.engine import battle_animation  # noqa: F401
from app.engine import general_states, title_screen
from app.engine import save as save_module
from app.engine.game_state import GameState


class _AtomicRestoreGame:
    def __init__(self, *, fail: bool = False):
        self.world = 'old-valid'
        self.current_save_slot = None
        self.fail = fail
        self.restore_phases = []
        self.state_installed = False

    def build_new(self):
        self.world = 'new-default'

    def load_iter(self, payload, *, replace_state_machine):
        if not replace_state_machine:
            self.state_installed = True
        self.world = 'registries'
        self.restore_phases.append('registries')
        yield 'registries'
        self.world = 'board'
        self.restore_phases.append('board')
        yield 'board'
        if self.fail:
            self.world = 'partial-failure'
            raise RuntimeError('restore failed')
        self.world = 'complete'
        self.restore_phases.append('complete')
        yield 'events'

    def clear(self):
        self.world = 'cleared'
        self.current_save_slot = None


class AtomicSaveLoadJobTests(unittest.TestCase):
    def _ready_job(self, payload, *, slot=3):
        job = save_module.SaveLoadJob(
            SimpleNamespace(save_loc='slot.p', idx=slot))
        job._thread = Mock()
        job._save_data = payload
        job._read_finished.set()
        return job

    def test_restore_waits_without_mutation_then_completes_in_one_update(self):
        payload = {'state': (['free'], ['alert'])}
        job = save_module.SaveLoadJob(
            SimpleNamespace(save_loc='slot.p', idx=7))
        job._thread = Mock()
        game = _AtomicRestoreGame()

        self.assertFalse(job.advance(game, budget_ms=0.0))
        self.assertEqual('old-valid', game.world)
        self.assertFalse(game.state_installed)

        job._save_data = payload
        job._read_finished.set()
        with patch.object(save_module, 'set_next_uids'):
            self.assertTrue(job.advance(game, budget_ms=0.0))

        self.assertEqual(['registries', 'board', 'complete'], game.restore_phases)
        self.assertEqual('complete', game.world)
        self.assertFalse(game.state_installed)
        self.assertEqual(7, game.current_save_slot)
        self.assertEqual((['free'], ['alert']), job.take_state_data())
        self.assertIsNone(job.take_state_data())

    def test_failed_restore_aborts_to_a_clean_deterministic_game(self):
        payload = {'state': (['free'], [])}
        job = self._ready_job(payload)
        game = _AtomicRestoreGame(fail=True)

        with patch.object(save_module, 'set_next_uids'):
            with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                job.advance(game, budget_ms=0.0)
        self.assertEqual('partial-failure', game.world)

        job.abort(game)

        self.assertEqual('new-default', game.world)
        self.assertIsNone(game.current_save_slot)
        self.assertIsNone(job.take_state_data())
        self.assertFalse(job.completed)

    def test_state_payload_cannot_be_taken_before_hydration_completes(self):
        job = save_module.SaveLoadJob(
            SimpleNamespace(save_loc='slot.p', idx=1))
        job._state_data = (['free'], [])

        with self.assertRaisesRegex(
                save_module.SaveLoadError, 'before hydration completed'):
            job.take_state_data()

        self.assertEqual((['free'], []), job._state_data)

    def test_chapter_snapshot_records_destination_without_publishing_it(self):
        game = GameState()
        source_snapshot = {
            'state': (['title_load_job'], []),
            'world_marker': {'complete': True},
        }
        game.save = Mock(return_value=(source_snapshot, {}))
        destination = (
            ['free', 'start_level_asset_loading'], ['alert'])

        game._capture_chapter_start_snapshot(destination)

        self.assertEqual(destination, game.chapter_start_snapshot['state'])
        self.assertEqual({'complete': True},
                         game.chapter_start_snapshot['world_marker'])
        self.assertEqual((['title_load_job'], []), source_snapshot['state'])
        self.assertEqual([], game.state.state_names())


class _CompletedRestoreJob:
    def __init__(self, state_data):
        self.completed = True
        self.phase = 'complete'
        self.is_reading = False
        self.remaining_state_data = state_data
        self.advance_calls = 0

    def advance(self, game, budget_ms=8.0):
        self.advance_calls += 1
        return True

    def take_state_data(self):
        state_data = self.remaining_state_data
        self.remaining_state_data = None
        return state_data

    def abort(self, game):
        game.clear()
        game.build_new()


class _TransitionObserver:
    def __init__(self):
        self.committed_stacks = []

    def state_transition_committed(self, machine):
        self.committed_stacks.append(machine.state_names())


class AtomicDestinationStateTests(unittest.TestCase):
    def test_game_state_has_no_legacy_singleton_staged_payload(self):
        self.assertFalse(hasattr(GameState(), '_staged_state_data'))

    def _title_fixture(self, next_action, *, transition_from='Load Game',
                       state_data=(['free'], [])):
        game = GameState()
        base_states = (['title_start', 'title_main', 'title_restart']
                       if transition_from == 'Restart Level'
                       else ['title_start', 'title_main', 'title_load'])
        game.state.load_states(base_states)
        state = title_screen.TitleLoadJobState('title_load_job')
        state.started = True
        state.processed = True
        game.state.state.append(state)
        job = _CompletedRestoreJob(state_data)
        state.job = job
        state.context = {
            'next_action': next_action,
            'transition_from': transition_from,
            'title_menu': object(),
            'remove_suspend': False,
        }
        state.error = None
        state.finished = False
        game.game_vars['_next_level_nid'] = 'chapter'
        game.start_level = Mock()
        return game, state, job

    def _run_title(self, game, state):
        with patch.object(title_screen, 'game', game), \
             patch.object(title_screen.save, 'remove_suspend'):
            self.assertEqual('repeat', state.update())

    def test_title_normal_installs_saved_stack_only_at_complete_world_boundary(self):
        game, state, job = self._title_fixture(
            None, state_data=(['free'], ['alert']))

        self._run_title(game, state)

        self.assertEqual(['free', 'alert', 'title_wait'], game.state.state_names())
        self.assertEqual([], game.state.temp_state)
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def test_title_start_uses_reference_stack_without_loader_or_stale_payload(self):
        game, state, job = self._title_fixture('start_level')

        self._run_title(game, state)

        self.assertEqual(
            ['free', 'start_level_asset_loading', 'title_wait'],
            game.state.state_names())
        game.start_level.assert_called_once_with(
            'chapter', chapter_start_state=(
                ['free', 'start_level_asset_loading'], []))
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def test_title_restart_preserves_title_prefix_without_loader_or_stale_payload(self):
        game, state, job = self._title_fixture(
            'restart_level', transition_from='Restart Level')

        self._run_title(game, state)

        self.assertEqual(
            ['title_start', 'title_main', 'title_restart', 'free', 'title_wait'],
            game.state.state_names())
        game.start_level.assert_called_once_with(
            'chapter', chapter_start_state=(
                ['title_start', 'title_main', 'title_restart', 'free'], []))
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def test_title_restart_observer_sees_only_the_final_destination(self):
        game, state, _job = self._title_fixture(
            'restart_level', transition_from='Restart Level')
        observer = _TransitionObserver()
        game.state.set_trace_recorder(observer)

        self._run_title(game, state)

        self.assertEqual([[
            'title_start', 'title_main', 'title_restart', 'free', 'title_wait',
        ]], observer.committed_stacks)

    def test_title_overworld_installs_exactly_one_destination(self):
        game, state, job = self._title_fixture('overworld')

        self._run_title(game, state)

        self.assertEqual(['free', 'overworld', 'title_wait'],
                         game.state.state_names())
        self.assertEqual(1, game.state.state_names().count('overworld'))
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def _in_chapter_fixture(self, kind, *, state_data=(['free'], ['alert'])):
        game = GameState()
        game.state.load_states(['in_chapter_load_job'])
        state = game.state.state[-1]
        state.started = True
        state.processed = True
        job = _CompletedRestoreJob(state_data)
        state.job = job
        state.save_slot = SimpleNamespace(kind=kind)
        state.error = None
        state.finished = False
        game.game_vars['_next_level_nid'] = 'chapter'
        game.start_level = Mock()
        return game, state, job

    def _run_in_chapter(self, game, state):
        with patch.object(general_states, 'game', game), \
             patch.object(general_states.save, 'remove_suspend'):
            self.assertEqual('repeat', state.update())

    def test_in_chapter_normal_restores_saved_stack_and_pending_transitions(self):
        game, state, job = self._in_chapter_fixture('battle')

        self._run_in_chapter(game, state)

        self.assertEqual(['free'], game.state.state_names())
        self.assertEqual(['alert'], game.state.temp_state)
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def test_in_chapter_start_has_saved_stack_and_one_loading_destination(self):
        game, state, job = self._in_chapter_fixture('start')

        self._run_in_chapter(game, state)

        self.assertEqual(['free', 'start_level_asset_loading'],
                         game.state.state_names())
        self.assertEqual(['alert'], game.state.temp_state)
        game.start_level.assert_called_once_with(
            'chapter', chapter_start_state=(
                ['free', 'start_level_asset_loading'], ['alert']))
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)

    def test_in_chapter_overworld_has_saved_stack_and_one_destination(self):
        game, state, job = self._in_chapter_fixture('overworld')

        self._run_in_chapter(game, state)

        self.assertEqual(['free', 'overworld'], game.state.state_names())
        self.assertEqual(['alert'], game.state.temp_state)
        self.assertEqual(1, game.state.state_names().count('overworld'))
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.remaining_state_data)


class AtomicRestoreFailureTests(unittest.TestCase):
    def test_title_restore_failure_resets_before_update_returns(self):
        game = GameState()
        game.state.load_states(['title_start', 'title_load_job'])
        state = game.state.state[-1]
        state.started = True
        state.processed = True
        state.context = {
            'next_action': None,
            'transition_from': 'Load Game',
            'title_menu': object(),
            'remove_suspend': False,
        }
        state.error = None
        state.finished = False

        job = save_module.SaveLoadJob(
            SimpleNamespace(save_loc='slot.p', idx=2))
        job._thread = Mock()
        job._save_data = {'state': (['free'], [])}
        job._read_finished.set()
        state.job = job

        game.board = 'old-valid-board'
        game.overworld_controller = 'old-valid-overworld'
        game.build_new = Mock()

        def fail_during_restore(_payload, *, replace_state_machine):
            self.assertTrue(replace_state_machine)
            game.board = 'partial-board'
            game.overworld_controller = 'partial-overworld'
            game._current_level = 'partial-level'
            yield 'board'
            raise RuntimeError('restore exploded')

        game.load_iter = fail_during_restore

        with patch.object(title_screen, 'game', game), \
             patch.object(save_module, 'set_next_uids'), \
             patch.object(title_screen.logging, 'error'):
            self.assertEqual('repeat', state.update())

        self.assertEqual(['title_start'], game.state.state_names())
        self.assertEqual([], game.state.temp_state)
        self.assertIsNone(game.board)
        self.assertIsNone(game.overworld_controller)
        self.assertIsNone(game._current_level)
        self.assertFalse(hasattr(game, '_staged_state_data'))
        self.assertIsNone(job.take_state_data())
        self.assertEqual(2, game.build_new.call_count)
        self.assertTrue(state.finished)


if __name__ == '__main__':
    unittest.main()
