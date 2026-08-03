import unittest
from unittest.mock import Mock, patch

import pygame

from app.engine import config as cf
from app.engine import driver, engine
from app.engine import input_manager as input_manager_module
from app.engine.fluid_scroll import FluidScroll
from app.engine.input_manager import InputManager
from app.engine.sound import DefaultSoundController, GlobalMusicState


class _FakeInput:
    def __init__(self, pressed: bool):
        self.pressed = pressed

    def is_pressed(self, button):
        return button == 'FAST_FORWARD' and self.pressed


class _FakeState:
    def __init__(self, blocks_fast_forward=False):
        self.blocks_fast_forward = blocks_fast_forward
        self.started = True


class _FakeStateMachine:
    def __init__(self, block_after_updates=None):
        self.calls = []
        self.draw_flags = []
        self.state = _FakeState()
        self.block_after_updates = block_after_updates

    def current_state(self):
        return self.state

    def update(self, event, surf, draw=True):
        self.calls.append(event)
        self.draw_flags.append(draw)
        if self.block_after_updates == len(self.calls):
            self.state.blocks_fast_forward = True
        return surf, False


class _PresentationBarrierStateMachine(_FakeStateMachine):
    """Reports that it composed an otherwise deferred visual cue."""
    def __init__(self):
        super().__init__()
        self._barrier = False

    def update(self, event, surf, draw=True):
        result = super().update(event, surf, draw)
        if len(self.calls) == 1:
            self._barrier = True
        return result

    def consume_presentation_barrier(self):
        barrier, self._barrier = self._barrier, False
        return barrier


class _InputReadingStateMachine:
    """State-machine double that reads the global input snapshot per update."""
    def __init__(self, input_manager, repeat_once=False):
        self.input_manager = input_manager
        self.repeat_once = repeat_once
        self.calls = []
        self.state = _FakeState()

    def current_state(self):
        return self.state

    def update(self, event, surf, draw=True):
        self.calls.append({
            'event': event,
            'edges': {
                direction: self.input_manager.just_pressed(direction)
                for direction in ('UP', 'DOWN', 'LEFT', 'RIGHT')
            },
            'held_right': self.input_manager.is_pressed('RIGHT'),
            'raw_events': self.input_manager.get_input_events(),
            'engine_events': list(engine.events),
        })
        return surf, self.repeat_once and len(self.calls) == 1


class _FakeGame:
    def __init__(self, block_after_updates=None):
        self.state = _FakeStateMachine(block_after_updates)


class _FakeMusicChannel:
    def __init__(self):
        self.current_time = None

    def update(self, _event_list, current_time):
        self.current_time = current_time
        return False

    def is_playing(self):
        return True


class _FakeDialog:
    def __init__(self):
        self.update_calls = 0
        self.draw_calls = 0
        self.solo_flag = False

    def is_complete(self):
        return False

    def update(self):
        self.update_calls += 1

    def draw(self, _surf):
        self.draw_calls += 1


class _EventDialogStateMachine:
    def __init__(self, event):
        self.event = event
        self.state = _FakeState()
        self.draw_flags = []

    def current_state(self):
        return self.state

    def update(self, _event, surf, draw=True):
        self.draw_flags.append(draw)
        self.event.update()
        if draw:
            self.event._draw_text_boxes(surf)
        return surf, False


class FastForwardConfigTests(unittest.TestCase):
    def test_defaults_and_allowed_speeds(self):
        defaults = cf.base_config()

        self.assertEqual(300, defaults['fast_forward_speed'])
        self.assertEqual('K_SPACE', defaults['key_FAST_FORWARD'])
        self.assertEqual((200, 300, 400, 500, 600, 700, 800), cf.FAST_FORWARD_SPEEDS)

    def test_invalid_speed_uses_default(self):
        for speed in (100, 250, 850, -300):
            with self.subTest(speed=speed):
                self.assertEqual(300, cf.normalize_fast_forward_speed(speed))

    def test_driver_uses_configured_number_of_updates(self):
        original_speed = cf.SETTINGS['fast_forward_speed']
        try:
            for speed in cf.FAST_FORWARD_SPEEDS:
                with self.subTest(speed=speed):
                    cf.SETTINGS['fast_forward_speed'] = speed
                    self.assertEqual(speed // 100, driver.get_fast_forward_steps(_FakeInput(True)))
            self.assertEqual(1, driver.get_fast_forward_steps(_FakeInput(False)))
        finally:
            cf.SETTINGS['fast_forward_speed'] = original_speed


class FastForwardInputTests(unittest.TestCase):
    def setUp(self):
        self.original_key = cf.SETTINGS['key_FAST_FORWARD']

    def tearDown(self):
        cf.SETTINGS['key_FAST_FORWARD'] = self.original_key

    @patch('app.engine.engine.joystick_avail', return_value=False)
    def test_fast_forward_is_held_but_not_sent_to_game_state(self, _joystick_avail):
        cf.SETTINGS['key_FAST_FORWARD'] = pygame.K_SPACE
        input_manager = InputManager()
        self.assertEqual([], input_manager.joystick_control['FAST_FORWARD'])

        key_down = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        self.assertIsNone(input_manager.process_input([key_down]))
        self.assertTrue(input_manager.is_pressed('FAST_FORWARD'))

        key_up = pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE)
        self.assertIsNone(input_manager.process_input([key_up]))
        self.assertFalse(input_manager.is_pressed('FAST_FORWARD'))

    def test_quit_sentinel_is_not_sent_to_input_manager(self):
        input_manager = Mock()

        with patch.object(engine, 'get_events', return_value=engine.QUIT):
            raw_events, event = driver.poll_events(input_manager)

        self.assertEqual(engine.QUIT, raw_events)
        self.assertIsNone(event)
        input_manager.process_input.assert_not_called()

    @patch('app.engine.engine.joystick_avail', return_value=False)
    def test_gameplay_binding_wins_if_config_is_manually_duplicated(self, _joystick_avail):
        cf.SETTINGS['key_FAST_FORWARD'] = cf.SETTINGS['key_SELECT']
        input_manager = InputManager()

        self.assertEqual('SELECT', input_manager.map_keys[cf.SETTINGS['key_SELECT']])

    @patch('app.engine.engine.joystick_avail', return_value=False)
    def test_consuming_transient_input_keeps_held_buttons(self, _joystick_avail):
        input_manager = InputManager()
        right_key = input_manager.key_map['RIGHT']
        raw_events = [pygame.event.Event(pygame.KEYDOWN, key=right_key)]

        input_manager.process_input(raw_events)
        self.assertTrue(input_manager.just_pressed('RIGHT'))
        self.assertTrue(input_manager.is_pressed('RIGHT'))
        self.assertEqual(raw_events, input_manager.get_input_events())

        input_manager.consume_transient_input()

        self.assertFalse(input_manager.just_pressed('RIGHT'))
        self.assertTrue(input_manager.is_pressed('RIGHT'))
        self.assertEqual([], input_manager.get_input_events())

    @patch('app.engine.engine.joystick_avail', return_value=False)
    def test_all_directional_edges_are_seen_once_at_every_fast_forward_speed(self, _joystick_avail):
        for direction in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            for steps in (1, 2, 3, 5, 8, 20):
                with self.subTest(direction=direction, steps=steps):
                    input_manager = InputManager()
                    input_manager.process_input([
                        pygame.event.Event(pygame.KEYDOWN, key=input_manager.key_map[direction])
                    ])
                    game = _FakeGame()
                    game.state = _InputReadingStateMachine(input_manager)

                    with patch.object(input_manager_module, 'INPUT', input_manager):
                        _, updates_run = driver.update_game_state_for_frame(
                            game, direction, object(), steps, 16)

                    self.assertEqual(steps, updates_run)
                    self.assertTrue(game.state.calls[0]['edges'][direction])
                    self.assertEqual(
                        [False] * (steps - 1),
                        [call['edges'][direction] for call in game.state.calls[1:]])
                    self.assertTrue(all(call['held_right'] for call in game.state.calls)
                                    if direction == 'RIGHT' else True)

    @patch('app.engine.engine.joystick_avail', return_value=False)
    def test_repeat_chain_cannot_replay_an_input_edge(self, _joystick_avail):
        input_manager = InputManager()
        raw_events = [
            pygame.event.Event(pygame.KEYDOWN, key=input_manager.key_map['RIGHT'])
        ]
        input_manager.process_input(raw_events)
        game = _FakeGame()
        game.state = _InputReadingStateMachine(input_manager, repeat_once=True)
        original_engine_events = engine.events

        try:
            engine.events = raw_events
            with patch.object(input_manager_module, 'INPUT', input_manager):
                driver.update_game_state_for_frame(game, 'RIGHT', object(), 1, 16)
        finally:
            engine.events = original_engine_events

        self.assertEqual(['RIGHT', []], [call['event'] for call in game.state.calls])
        self.assertTrue(game.state.calls[0]['edges']['RIGHT'])
        self.assertFalse(game.state.calls[1]['edges']['RIGHT'])
        self.assertEqual(1, len(game.state.calls[0]['raw_events']))
        self.assertEqual([], game.state.calls[1]['raw_events'])
        self.assertEqual(raw_events, game.state.calls[0]['engine_events'])
        self.assertEqual([], game.state.calls[1]['engine_events'])

    @patch('app.engine.engine.joystick_avail', return_value=False)
    @patch('app.engine.fluid_scroll.engine.get_true_time')
    def test_fluid_scroll_uses_true_time_after_transient_input_is_consumed(
            self, get_true_time, _joystick_avail):
        input_manager = InputManager()
        input_manager.process_input([
            pygame.event.Event(pygame.KEYDOWN, key=input_manager.key_map['RIGHT'])
        ])
        scroll = FluidScroll()

        with patch.object(input_manager_module, 'INPUT', input_manager):
            get_true_time.return_value = 1000
            self.assertTrue(scroll.update())
            self.assertEqual(['RIGHT'], scroll.get_directions())

            input_manager.consume_transient_input()
            for _ in range(20):
                engine.advance_time(16)
                self.assertFalse(scroll.update())
                self.assertEqual([], scroll.get_directions())

            get_true_time.return_value = 1202
            self.assertFalse(scroll.update())
            self.assertEqual(['RIGHT'], scroll.get_directions())

class FastForwardTimingTests(unittest.TestCase):
    def setUp(self):
        self.original_constants = engine.constants.copy()
        engine.constants.update({
            'current_time': 0,
            'last_time': 0,
            'delta_t': 0,
            'true_time': None,
        })

    def tearDown(self):
        engine.constants.clear()
        engine.constants.update(self.original_constants)

    @patch('app.engine.engine.pygame.time.get_ticks', side_effect=(1000, 1016))
    def test_virtual_time_can_advance_without_advancing_true_time(self, _get_ticks):
        engine.update_time()
        engine.update_time()
        self.assertEqual(1016, engine.get_time())
        self.assertEqual(16, engine.get_delta())

        engine.advance_time(16)
        self.assertEqual(1032, engine.get_time())
        self.assertEqual(1016, engine.constants['true_time'])

    def test_extra_updates_receive_no_input(self):
        game = _FakeGame()
        surf = object()

        _, updates_run = driver.update_game_state_for_frame(
            game, 'SELECT', surf, 5, 16)

        self.assertEqual(5, updates_run)
        self.assertEqual('SELECT', game.state.calls[0])
        self.assertEqual([[], [], [], []], game.state.calls[1:])
        self.assertEqual([False, False, False, False, True], game.state.draw_flags)
        self.assertEqual(1, game._last_fast_forward_draws)
        self.assertEqual(64, engine.get_time())

    def test_fast_forward_updates_many_times_but_draws_once_on_all_platforms(self):
        game = _FakeGame()

        _, updates_run = driver.update_game_state_for_frame(
            game, 'SELECT', object(), 5, 16)

        self.assertEqual(5, updates_run)
        self.assertEqual([False, False, False, False, True], game.state.draw_flags)
        self.assertEqual(1, game._last_fast_forward_draws)
        self.assertEqual(64, engine.get_time())

    def test_fast_forward_uses_host_delta_until_the_hitch_cap(self):
        self.assertEqual(16, driver.get_fast_forward_step_ms(16))
        self.assertEqual(26, driver.get_fast_forward_step_ms(26))
        self.assertEqual(34, driver.get_fast_forward_step_ms(34))
        self.assertEqual(34, driver.get_fast_forward_step_ms(100))
        self.assertEqual(16, driver.get_fast_forward_step_ms(0))

    def test_fast_forward_matches_host_delta_without_multiplying_a_hitch(self):
        game = _FakeGame()
        engine.advance_time(26)
        _, updates_run = driver.update_game_state_for_frame(
            game, None, object(), 8,
            driver.get_fast_forward_step_ms(engine.get_delta()))

        self.assertEqual(8, updates_run)
        self.assertEqual(26 * 8, engine.get_time())

        engine.constants.update({'current_time': 0, 'last_time': 0, 'delta_t': 0})
        engine.advance_time(100)
        _, updates_run = driver.update_game_state_for_frame(
            game, None, object(), 8,
            driver.get_fast_forward_step_ms(engine.get_delta()))

        self.assertEqual(8, updates_run)
        self.assertEqual(100 + 7 * driver.MAX_FAST_FORWARD_STEP_MS,
                         engine.get_time())

    def test_fast_forward_dialog_updates_each_substep_but_draws_once(self):
        from types import SimpleNamespace
        from app.events.event import Event

        dialog = _FakeDialog()
        event = Event.__new__(Event)
        event.should_update = {}
        event.game = SimpleNamespace(movement=None)
        event.text_boxes = [dialog]
        event.do_skip = False
        event._update_state = Mock()
        game = _FakeGame()
        game.state = _EventDialogStateMachine(event)

        _, updates_run = driver.update_game_state_for_frame(
            game, None, object(), 8, 16)

        self.assertEqual(8, updates_run)
        self.assertEqual(8, dialog.update_calls)
        self.assertEqual(1, dialog.draw_calls)
        self.assertEqual([False] * 7 + [True], game.state.draw_flags)

    def test_help_typewriter_updates_each_fast_forward_substep(self):
        from app.engine.help_menu import HelpDialog

        dialog = _FakeDialog()
        dialog.plain_text = 'help'
        help_box = HelpDialog.__new__(HelpDialog)
        help_box.dlg = dialog
        help_box.last_time = 0

        for _ in range(8):
            HelpDialog.update(help_box)

        self.assertEqual(8, dialog.update_calls)

    def test_event_portrait_motion_uses_virtual_time_not_render_count(self):
        from app.events.event_portrait import EventPortrait

        portrait = EventPortrait.__new__(EventPortrait)
        portrait.talk_on = False
        portrait.talk_state = 0
        portrait.reverse = False
        portrait.blink_counter = Mock()
        portrait.saturation_direction = 0
        portrait.transition = False
        portrait.bops_remaining = 0
        portrait.moving = True
        portrait.orig_position = (0, 0)
        portrait.next_position = (80, 0)
        portrait.position = (0, 0)
        portrait.move_start_time = 0
        portrait.travel_time = 100

        with patch.object(engine, 'get_time', return_value=50), \
                patch.object(engine, 'get_delta', return_value=16):
            portrait.update()

        self.assertEqual((40, 0), portrait.position)
        self.assertTrue(portrait.moving)

    def test_presentation_barrier_stops_remaining_fast_forward_substeps(self):
        game = _FakeGame()
        game.state = _PresentationBarrierStateMachine()

        _, updates_run = driver.update_game_state_for_frame(
            game, None, object(), 8, 16)

        self.assertEqual(1, updates_run)
        self.assertEqual(1, game._last_fast_forward_draws)

    def test_event_draw_does_not_advance_dialogue(self):
        from types import SimpleNamespace
        from app.events.event import Event

        dialog = _FakeDialog()
        event = Event.__new__(Event)
        event.animations = []
        event.background = None
        event.portraits = {}
        event.overlay_ui = Mock()
        event.foreground_overlay_ui = Mock()
        event.overlay_ui.to_surf.return_value = object()
        event.foreground_overlay_ui.to_surf.return_value = object()
        event.other_boxes = []
        event._last_visible_text_boxes = [dialog]
        event.transition_state = None
        event.game = SimpleNamespace(camera=Mock())

        Event.draw(event, Mock())

        self.assertEqual(0, dialog.update_calls)
        self.assertEqual(1, dialog.draw_calls)

    def test_blocking_transition_defers_at_most_one_frame(self):
        game = _FakeGame(block_after_updates=1)

        _, updates_run = driver.update_game_state_for_frame(
            game, 'SELECT', object(), 5, 16)
        self.assertEqual(1, updates_run)
        self.assertEqual([False], game.state.draw_flags)
        self.assertEqual(0, game._last_fast_forward_draws)

        # The blocking state is now current, so the next host frame runs one
        # normal update and draws it instead of leaving the surface frozen.
        _, updates_run = driver.update_game_state_for_frame(
            game, None, object(), 5, 16)
        self.assertEqual(1, updates_run)
        self.assertEqual([False, True], game.state.draw_flags)
        self.assertEqual(1, game._last_fast_forward_draws)

    def test_choice_state_stops_remaining_extra_updates(self):
        game = _FakeGame(block_after_updates=1)

        _, updates_run = driver.update_game_state_for_frame(game, None, object(), 5, 16)

        self.assertEqual(1, updates_run)
        self.assertEqual(1, len(game.state.calls))
        self.assertEqual(0, engine.get_time())

    @patch('app.engine.engine.get_true_time', return_value=1234)
    def test_music_controller_uses_true_time(self, _get_true_time):
        channel = _FakeMusicChannel()
        controller = DefaultSoundController.__new__(DefaultSoundController)
        controller.channel_stack = [channel]
        controller._state = GlobalMusicState.STOPPED

        controller.update([])

        self.assertEqual(1234, channel.current_time)


if __name__ == '__main__':
    unittest.main()
