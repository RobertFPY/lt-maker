"""P5-T02 regression tests for the canonical save-load transaction."""

from __future__ import annotations

import copy
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
from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import config as cf
from app.engine import save as save_module
from app.engine.game_state import game
from app.engine.objects.item import ItemObject
from app.engine.objects.skill import SkillObject


class CanonicalLoadRoutingTests(unittest.TestCase):
    def test_save_kind_does_not_guess_the_callers_destination(self):
        slot = SimpleNamespace(kind='start', idx=1)

        raw_context = save_module.LoadTransactionContext.for_slot(slot)
        restart_context = save_module.LoadTransactionContext.for_slot(
            slot, destination=save_module.LoadDestination.RESTART_LEVEL)

        self.assertEqual(save_module.LoadDestination.SAVED,
                         raw_context.destination)
        self.assertEqual(save_module.LoadDestination.RESTART_LEVEL,
                         restart_context.destination)

    def test_desktop_and_android_use_the_same_canonical_transaction(self):
        payload = {'state': (['free'], [])}
        slot = SimpleNamespace(save_loc='slot.p', idx=2, kind='battle')
        context = save_module.LoadTransactionContext.for_slot(
            slot, preserve_existing_states=False)
        desktop_game = Mock()

        with patch.object(save_module, '_read_save_data', return_value=payload), \
             patch.object(save_module, 'load_game_data') as transaction:
            save_module.load_game(desktop_game, slot, context=context)

        transaction.assert_called_once_with(desktop_game, payload, context=context)

        job = save_module.SaveLoadJob(slot, context=context)
        job._thread = Mock()
        job._save_data = payload
        job._read_finished.set()
        android_game = Mock()
        with patch.object(save_module, 'load_game_data') as transaction:
            self.assertTrue(job.advance(android_game))

        transaction.assert_called_once_with(android_game, payload, context=context)

    def test_android_worker_only_reads_and_unpickles(self):
        payload = {'state': (['free'], [])}
        slot = SimpleNamespace(save_loc='slot.p', idx=3, kind='battle')
        job = save_module.SaveLoadJob(slot)

        with patch.object(save_module, '_read_save_data', return_value=payload), \
             patch.object(save_module, 'load_game_data') as transaction:
            job._read_worker()

        self.assertIs(payload, job._save_data)
        self.assertTrue(job._read_finished.is_set())
        transaction.assert_not_called()

    def test_worker_read_failure_reaches_caller_before_authoritative_mutation(self):
        slot = SimpleNamespace(save_loc='broken.p', idx=3, kind='battle')
        job = save_module.SaveLoadJob(slot)
        read_error = OSError('unpickle failed')
        job._thread = Mock()
        job.error = read_error
        job._read_finished.set()
        game_state = Mock()

        with patch.object(save_module, 'load_game_data') as transaction:
            with self.assertRaisesRegex(
                    save_module.SaveLoadError, 'Unable to read') as raised:
                job.advance(game_state)

        self.assertIs(read_error, raised.exception.__cause__)
        transaction.assert_not_called()
        self.assertEqual([], game_state.mock_calls)

    def test_desktop_title_read_failure_does_not_clear_live_state_first(self):
        from app.engine import title_screen

        state = title_screen.TitleLoadState.__new__(title_screen.TitleLoadState)
        state.state = 'normal'
        state.fluid = Mock(
            update=Mock(return_value=False),
            get_directions=Mock(return_value=[]),
        )
        state.menu = Mock(current_index=0)
        slot = SimpleNamespace(save_loc='broken.p', idx=0, kind='battle')
        state.save_slots = [slot]
        fake_game = SimpleNamespace(memory={}, state=Mock())

        with patch.object(title_screen, 'game', fake_game), \
             patch.object(title_screen, 'is_android_runtime', return_value=False), \
             patch.object(title_screen, 'get_sound_thread', return_value=Mock()), \
             patch.object(title_screen.save, 'load_game',
                          side_effect=OSError('unpickle failed')) as load_game:
            with self.assertRaisesRegex(OSError, 'unpickle failed'):
                state.take_input('SELECT')

        context = load_game.call_args.kwargs['context']
        self.assertTrue(context.clear_existing_states)
        self.assertFalse(context.preserve_existing_states)
        fake_game.state.clear.assert_not_called()
        fake_game.state.process_temp_state.assert_not_called()

    def test_in_chapter_read_failure_does_not_clear_live_state_first(self):
        from app.engine import general_states

        slot = SimpleNamespace(save_loc='broken.p', idx=0, kind='battle')
        fake_game = SimpleNamespace(state=Mock())
        with patch.object(general_states, 'game', fake_game), \
             patch.object(general_states.save, 'load_game',
                          side_effect=OSError('unpickle failed')) as load_game, \
             patch.object(general_states.save, 'remove_suspend') as remove_suspend:
            with self.assertRaisesRegex(OSError, 'unpickle failed'):
                general_states.load_save_slot(slot)

        context = load_game.call_args.kwargs['context']
        self.assertTrue(context.clear_existing_states)
        self.assertFalse(context.preserve_existing_states)
        fake_game.state.clear.assert_not_called()
        fake_game.state.process_temp_state.assert_not_called()
        remove_suspend.assert_not_called()

    def test_android_title_routes_publish_one_explicit_destination(self):
        from app.engine import title_screen

        cases = (
            (None, 'Load Game', save_module.LoadDestination.SAVED, False),
            ('start_level', 'Load Game',
             save_module.LoadDestination.START_LEVEL, False),
            ('restart_level', 'Restart Level',
             save_module.LoadDestination.RESTART_LEVEL, True),
            ('overworld', 'Load Game',
             save_module.LoadDestination.OVERWORLD, False),
        )
        for next_action, transition_from, destination, keeps_prefix in cases:
            with self.subTest(next_action=next_action):
                state = title_screen.TitleLoadState.__new__(
                    title_screen.TitleLoadState)
                state.menu = object()
                old_states = [object(), object()]
                fake_game = SimpleNamespace(
                    memory={},
                    state=SimpleNamespace(state=old_states, change=Mock()),
                )
                slot = SimpleNamespace(save_loc='slot.p', idx=1, kind='start')
                job = Mock()
                with patch.object(title_screen, 'game', fake_game), \
                     patch.object(title_screen.save, 'SaveLoadJob',
                                  return_value=job) as job_class:
                    state._start_android_load(
                        slot,
                        transition_from=transition_from,
                        next_action=next_action,
                        remove_suspend=True,
                    )

                context = job_class.call_args.kwargs['context']
                self.assertEqual(destination, context.destination)
                self.assertFalse(context.preserve_existing_states)
                self.assertEqual(tuple(old_states) if keeps_prefix else (),
                                 context.state_prefix)

    def test_android_in_chapter_routes_publish_one_explicit_destination(self):
        from app.engine import general_states

        cases = {
            'battle': save_module.LoadDestination.SAVED,
            'start': save_module.LoadDestination.START_LEVEL,
            'overworld': save_module.LoadDestination.OVERWORLD,
        }
        for save_kind, destination in cases.items():
            with self.subTest(save_kind=save_kind):
                slot = SimpleNamespace(
                    save_loc='slot.p', idx=1, kind=save_kind)
                fake_game = SimpleNamespace(memory={}, state=Mock())
                job = Mock()
                with patch.object(general_states, 'game', fake_game), \
                     patch.object(general_states.save, 'SaveLoadJob',
                                  return_value=job) as job_class:
                    general_states.InChapterLoadState._start_android_load(slot)

                context = job_class.call_args.kwargs['context']
                self.assertEqual(destination, context.destination)
                self.assertFalse(context.preserve_existing_states)
                self.assertEqual((), context.state_prefix)


class ControllerPayloadScopeTests(unittest.TestCase):
    @staticmethod
    def _phase_game(current: int, previous: int):
        return SimpleNamespace(
            level=object(),
            phase=SimpleNamespace(current=current, previous=previous),
            initiative=None,
        )

    def test_ordinary_player_noninitiative_payload_is_byte_shape_unchanged(self):
        payload = {'state': (['free'], [])}
        player_idx = DB.teams.index('player')
        game_state = self._phase_game(player_idx, player_idx)

        with patch.object(DB.constants.get('initiative'), 'value', False):
            save_module.capture_controller_compatibility(
                game_state, payload, save_kind='battle')

        self.assertEqual({'state': (['free'], [])}, payload)

    def test_nonplayer_phase_writes_current_and_previous_team_nids(self):
        payload = {'state': (['ai'], [])}
        player_idx = DB.teams.index('player')
        enemy_idx = DB.teams.index('enemy')
        game_state = self._phase_game(enemy_idx, player_idx)

        with patch.object(DB.constants.get('initiative'), 'value', False):
            save_module.capture_controller_compatibility(
                game_state, payload, save_kind='enemy_turn_change')

        self.assertEqual({
            'phase': {'current': 'enemy', 'previous': 'player'},
        }, payload['controller_state'])

    def test_supported_initiative_suspend_couples_tracker_to_payload(self):
        payload = {'state': (['free'], [])}
        metadata = {}
        fake_state = SimpleNamespace(
            state_names=Mock(return_value=['free']), temp_state=[])
        fake_game = SimpleNamespace(
            level=object(),
            phase=SimpleNamespace(
                current=DB.teams.index('player'),
                previous=DB.teams.index('enemy')),
            initiative=SimpleNamespace(
                unit_line=['Eirika', '101'],
                initiative_line=[9, 4],
                current_idx=1,
            ),
            current_save_slot=0,
            state=fake_state,
            save=Mock(return_value=(payload, metadata)),
        )
        thread = Mock()
        original_thread = save_module.SAVE_THREAD
        try:
            with patch.object(DB.constants.get('initiative'), 'value', True), \
                 patch.object(save_module.threading, 'Thread',
                              return_value=thread) as thread_class:
                save_module.suspend_game(fake_game, 'battle', slot=1)
        finally:
            save_module.SAVE_THREAD = original_thread

        written_payload = thread_class.call_args.kwargs['args'][0]
        self.assertIs(payload, written_payload)
        self.assertEqual({
            'phase': {'current': 'player', 'previous': 'enemy'},
            'initiative': {
                'unit_line': ['Eirika', '101'],
                'initiative_line': [9, 4],
                'current_idx': 1,
            },
        }, written_payload['controller_state'])
        thread.start.assert_called_once_with()


class CanonicalLoadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DB.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        RESOURCES.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        from app.engine import fonts, sprites
        sprites.load_images()
        fonts.load_fonts(headless=True)

    def setUp(self):
        self._initiative_value = DB.constants.value('initiative')
        self._random_seed = cf.SETTINGS['random_seed']
        game.clear()

    def tearDown(self):
        DB.constants.get('initiative').set_value(self._initiative_value)
        cf.SETTINGS['random_seed'] = self._random_seed
        game.clear()

    def _start_chapter(self, *, initiative: bool) -> None:
        DB.constants.get('initiative').set_value(initiative)
        cf.SETTINGS['random_seed'] = 1701
        game.load_states(['free'])
        game.build_new()
        game.start_level('0')
        game.game_vars['_next_level_nid'] = '0'

    def test_initiative_current_progress_round_trips_exact_tracker(self):
        self._start_chapter(initiative=True)
        for _idx in range(3):
            game.initiative.next()
        current_unit = game.initiative.get_current_unit()
        game.phase.current = DB.teams.index(current_unit.team)
        game.phase.previous = DB.teams.index('player')
        game.initiative.draw_me = False  # Presentation toggle, not progress.
        payload, _metadata = game.save()
        save_module.capture_controller_compatibility(
            game, payload, save_kind='battle')
        expected = copy.deepcopy(payload['controller_state'])
        self.assertEqual({'unit_line', 'initiative_line', 'current_idx'},
                         set(expected['initiative']))
        expected_unit = current_unit.nid
        expected_team = current_unit.team

        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)
        game.clear()
        game.current_save_slot = 6
        install = game.install_state_machine
        publication_observations = []

        def observe_install(*args, **kwargs):
            publication_observations.append({
                'level': game.level is not None,
                'board': game.board is not None,
                'boundary': game.boundary is not None,
                'fog': game.board is not None and
                       hasattr(game.board, 'fog_of_war_grids'),
                'aura': game.board is not None and
                        hasattr(game.board, 'aura_grid'),
                'events': game.events is not None,
                'phase': game.phase is not None,
                'initiative': game.initiative is not None,
                'active_unit': game.initiative.get_current_unit().nid,
                'published_states_before_call': game.state.state_names(),
            })
            return install(*args, **kwargs)

        with patch.object(game, 'install_state_machine',
                          side_effect=observe_install) as publish:
            game.load(payload, load_context=context)

        self.assertEqual(1, publish.call_count)
        self.assertEqual([{
            'level': True,
            'board': True,
            'boundary': True,
            'fog': True,
            'aura': True,
            'events': True,
            'phase': True,
            'initiative': True,
            'active_unit': expected_unit,
            'published_states_before_call': [],
        }], publication_observations)
        self.assertEqual(expected['initiative']['unit_line'],
                         game.initiative.unit_line)
        self.assertEqual(expected['initiative']['initiative_line'],
                         game.initiative.initiative_line)
        self.assertEqual(expected['initiative']['current_idx'],
                         game.initiative.current_idx)
        self.assertEqual(expected_unit, game.initiative.get_current_unit().nid)
        self.assertEqual(expected_team, game.phase.get_current())
        self.assertEqual(expected['phase']['current'],
                         DB.teams[game.phase.current].nid)
        self.assertEqual(expected['phase']['previous'],
                         DB.teams[game.phase.previous].nid)
        self.assertTrue(game.initiative.draw_me)
        self.assertEqual(6, game.current_save_slot)

    def test_desktop_clear_policy_ends_old_state_inside_transaction(self):
        self._start_chapter(initiative=False)
        payload, _metadata = game.save()
        old_state = game.state.current_state()
        old_state.finish = Mock()
        context = save_module.LoadTransactionContext(
            save_kind='battle',
            clear_existing_states=True,
            preserve_existing_states=False,
        )

        game.load(payload, load_context=context)

        old_state.finish.assert_called_once_with()
        self.assertEqual(['free'], game.state.state_names())
        self.assertIsNot(old_state, game.state.current_state())

    def test_legacy_initiative_progress_fails_explicitly_before_saved_stack(self):
        self._start_chapter(initiative=True)
        game.initiative.next()
        payload, _metadata = game.save()
        self.assertNotIn('controller_state', payload)
        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)

        game.clear()
        with patch.object(game, 'install_state_machine',
                          wraps=game.install_state_machine) as publish:
            with self.assertRaisesRegex(
                    save_module.SaveCompatibilityError,
                    'initiative progress'):
                game.load(payload, load_context=context)

        publish.assert_not_called()
        self.assertNotIn('free', game.state.state_names())
        self.assertEqual(['title_start'], game.state.state_names())
        self.assertIsNone(game.level)

    def test_legacy_restart_rebuilds_chapter_start_initiative(self):
        self._start_chapter(initiative=True)
        payload, _metadata = game.save()
        self.assertNotIn('controller_state', payload)
        context = save_module.LoadTransactionContext(
            save_kind='start',
            destination=save_module.LoadDestination.RESTART_LEVEL,
            preserve_existing_states=False,
        )

        game.clear()
        game.load(payload, load_context=context)

        self.assertIsNotNone(game.initiative)
        self.assertEqual(-1, game.initiative.current_idx)
        self.assertEqual(len(game.initiative.unit_line),
                         len(game.initiative.initiative_line))
        self.assertEqual(['free'], game.state.state_names())

    def test_restart_preserves_counter_default_for_missing_next_level(self):
        self._start_chapter(initiative=False)
        payload, _metadata = game.save()
        payload['game_vars'].pop('_next_level_nid', None)
        context = save_module.LoadTransactionContext(
            save_kind='start',
            destination=save_module.LoadDestination.RESTART_LEVEL,
            preserve_existing_states=False,
        )

        game.clear()
        game.load(payload, load_context=context)

        self.assertEqual('0', game.level.nid)
        self.assertEqual(['free'], game.state.state_names())

    def test_legacy_enemy_turn_change_context_restores_enemy_phase(self):
        self._start_chapter(initiative=False)
        game.phase.current = DB.teams.index('enemy')
        game.phase.previous = DB.teams.index('player')
        payload, _metadata = game.save()
        self.assertNotIn('controller_state', payload)
        context = save_module.LoadTransactionContext.for_slot(
            SimpleNamespace(kind='enemy_turn_change', idx=2),
            preserve_existing_states=False,
        )

        game.clear()
        game.load(payload, load_context=context)

        self.assertEqual('enemy', game.phase.get_current())
        self.assertEqual('player', game.phase.get_previous())
        self.assertEqual(2, game.current_save_slot)

    def test_new_nonplayer_save_round_trips_exact_phase_pair(self):
        self._start_chapter(initiative=False)
        enemy_idx = DB.teams.index('enemy')
        game.phase.current = enemy_idx
        game.phase.previous = enemy_idx
        payload, _metadata = game.save()
        save_module.capture_controller_compatibility(
            game, payload, save_kind='battle')
        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)

        game.clear()
        game.load(payload, load_context=context)

        self.assertEqual('enemy', game.phase.get_current())
        self.assertEqual('enemy', game.phase.get_previous())

    def test_overworld_route_is_controller_irrelevant_and_installed_once(self):
        DB.constants.get('initiative').set_value(True)
        cf.SETTINGS['random_seed'] = 1701
        game.load_states(['title_start'])
        game.build_new()
        payload, _metadata = game.save()
        self.assertIsNone(payload['level'])
        self.assertNotIn('controller_state', payload)
        context = save_module.LoadTransactionContext(
            save_kind='overworld',
            destination=save_module.LoadDestination.OVERWORLD,
            preserve_existing_states=False,
        )

        game.clear()
        game.load(payload, load_context=context)

        self.assertIsNone(game.level)
        self.assertEqual(['title_start', 'overworld'], game.state.state_names())
        self.assertEqual(1, game.state.state_names().count('overworld'))
        self.assertIsNotNone(game.events)

    def test_internal_event_processor_state_survives_canonical_load(self):
        from app.events.event import Event
        from app.events.triggers import GenericTrigger

        self._start_chapter(initiative=False)
        event_prefab = DB.events.get_by_nid_or_name('1 TurnChange')[0]
        event = Event(event_prefab, GenericTrigger(), game)
        event.processor.fetch_next_command()
        event._android_tilemap_pending = True
        event._tilemap_change_job = object()
        game.events.append(event)
        expected_event_state = copy.deepcopy(event.save())
        self.assertNotIn('_android_tilemap_pending', expected_event_state)
        self.assertNotIn('_tilemap_change_job', expected_event_state)
        payload, _metadata = game.save()
        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)

        game.clear()
        game.load(payload, load_context=context)

        self.assertEqual(1, len(game.events.all_events))
        self.assertEqual(expected_event_state, game.events.all_events[0].save())
        self.assertIs(game.events.all_events[0], game.events.event_stack[0])
        self.assertFalse(hasattr(
            game.events.all_events[0], '_android_tilemap_pending'))
        self.assertFalse(hasattr(
            game.events.all_events[0], '_tilemap_change_job'))

    def test_malformed_initiative_payload_fails_atomically(self):
        self._start_chapter(initiative=True)
        payload, _metadata = game.save()
        save_module.capture_controller_compatibility(
            game, payload, save_kind='battle')
        payload['controller_state']['initiative']['unit_line'].append('missing')
        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)

        game.clear()
        with patch.object(game, 'install_state_machine',
                          wraps=game.install_state_machine) as publish:
            with self.assertRaisesRegex(
                    save_module.SaveCompatibilityError,
                    '(?i)initiative'):
                game.load(payload, load_context=context)

        publish.assert_not_called()
        self.assertEqual(['title_start'], game.state.state_names())
        self.assertIsNone(game.level)

    def test_late_restore_failure_clears_tracker_and_rolls_back_uid_globals(self):
        self._start_chapter(initiative=True)
        payload, _metadata = game.save()
        save_module.capture_controller_compatibility(
            game, payload, save_kind='battle')
        context = save_module.LoadTransactionContext(
            save_kind='battle', preserve_existing_states=False)
        prior_item_uid = ItemObject.next_uid
        prior_skill_uid = SkillObject.next_uid
        original_item_uid = 900_001
        original_skill_uid = 900_002
        ItemObject.next_uid = original_item_uid
        SkillObject.next_uid = original_skill_uid

        try:
            with patch.object(
                    game, 'install_state_machine',
                    side_effect=RuntimeError('late publication failure')):
                with self.assertRaisesRegex(
                        save_module.SaveLoadError,
                        'Unable to restore save transaction') as raised:
                    game.load(payload, load_context=context)

            self.assertIsInstance(raised.exception.__cause__, RuntimeError)
            self.assertEqual(original_item_uid, ItemObject.next_uid)
            self.assertEqual(original_skill_uid, SkillObject.next_uid)
            self.assertIsNone(game.initiative)
            self.assertIsNone(game.level)
            self.assertEqual(['title_start'], game.state.state_names())
        finally:
            ItemObject.next_uid = prior_item_uid
            SkillObject.next_uid = prior_skill_uid


if __name__ == '__main__':
    unittest.main()
