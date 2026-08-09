import json
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine import android_debugger, driver, engine
from app.engine.android_runtime import (
    get_android_touch_passthrough_buttons,
    is_android_touch_consumer_active,
)
from app.engine.runtime_debugger_service import (
    PendingCommand,
    RuntimeDebuggerService,
)


class RuntimeDebuggerServiceParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RuntimeDebuggerService()
        self.service._server = object()
        self.service._controller = MagicMock()
        self.service._last_snapshot_time = time.monotonic()

    def tearDown(self) -> None:
        self.service._server = None

    def test_http_command_waits_for_game_thread_update(self) -> None:
        self.service._controller.dispatch.return_value = {
            'ok': True, 'message': 'Money set to 7.'}
        server = HTTPServer(('127.0.0.1', 0), self.service._make_handler())
        self.service._server = server
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        response_holder = {}

        def request() -> None:
            connection = HTTPConnection('127.0.0.1', server.server_address[1], timeout=3)
            try:
                connection.request(
                    'POST', f'/api/command?token={self.service._token}',
                    body=json.dumps({'op': 'set_money', 'args': {'value': 7}}),
                    headers={'Content-Type': 'application/json'},
                )
                response = connection.getresponse()
                response_holder['status'] = response.status
                response_holder['body'] = json.loads(response.read().decode('utf-8'))
            finally:
                connection.close()

        request_thread = threading.Thread(target=request, daemon=True)
        request_thread.start()
        deadline = time.monotonic() + 1
        while self.service._commands.empty() and time.monotonic() < deadline:
            time.sleep(0.005)

        self.assertFalse(self.service._controller.dispatch.called)
        self.service.update()
        request_thread.join(timeout=2)
        self.assertFalse(request_thread.is_alive())
        self.assertEqual(200, response_holder['status'])
        self.assertEqual({'ok': True, 'message': 'Money set to 7.'},
                         response_holder['body'])
        self.service._controller.dispatch.assert_called_once_with(
            'set_money', {'value': 7})
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    def test_update_completes_one_command_once_even_when_dispatch_fails(self) -> None:
        self.service._controller.dispatch.side_effect = ValueError('invalid command')
        pending = PendingCommand('set_weather', {'weather_nid': 'missing'})
        self.service._commands.put(pending)

        self.service.update()
        self.service.update()

        self.service._controller.dispatch.assert_called_once_with(
            'set_weather', {'weather_nid': 'missing'})
        self.assertTrue(pending.complete.is_set())
        self.assertEqual(
            {'ok': False, 'message': 'invalid command'}, pending.result)

    def test_http_timeout_keeps_one_queued_command_for_one_later_dispatch(self) -> None:
        pending = MagicMock()
        pending.op = 'set_money'
        pending.args = {'value': 7}
        pending.result = {}
        pending.complete.wait.return_value = False
        self.service._controller.dispatch.return_value = {
            'ok': True, 'message': 'Money set to 7.'}
        with patch('app.engine.runtime_debugger_service.PendingCommand',
                   return_value=pending):
            server = HTTPServer(('127.0.0.1', 0), self.service._make_handler())
            self.service._server = server
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            connection = HTTPConnection('127.0.0.1', server.server_address[1], timeout=3)
            try:
                connection.request(
                    'POST', f'/api/command?token={self.service._token}',
                    body=json.dumps({'op': 'set_money', 'args': {'value': 7}}),
                    headers={'Content-Type': 'application/json'},
                )
                self.assertEqual(504, connection.getresponse().status)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

        self.service.update()
        self.service.update()
        self.service._controller.dispatch.assert_called_once_with(
            'set_money', {'value': 7})
        pending.complete.set.assert_called_once_with()

    def test_snapshot_polling_does_not_dispatch_gameplay_commands(self) -> None:
        self.service._last_snapshot_time = 0
        self.service._controller.build_snapshot.return_value = {'runtime_active': True}

        self.service.update()

        self.service._controller.dispatch.assert_not_called()
        self.service._controller.build_snapshot.assert_called_once()


class RuntimeDebuggerFrontendParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = android_debugger.AndroidDebuggerState()
        self.state.controller = MagicMock()
        self.state.controller.dispatch.return_value = {'ok': True, 'message': 'Done.'}
        self.state._refresh = MagicMock()
        self.state._sync_selection_from_snapshot = MagicMock()

    def test_android_and_desktop_route_same_unit_world_event_operations(self) -> None:
        cases = (
            ('set_field', {'nid': 'Eirika', 'key': 'hp', 'value': 12}),
            ('set_weather', {'weather_nid': 'rain'}),
            ('event_command', {'script': 'wait;1', 'nid': 'Eirika'}),
        )
        fake_game = SimpleNamespace(state=SimpleNamespace(temp_state=[]))
        for op, args in cases:
            self.state.controller.reset_mock()
            with patch.object(android_debugger.game, 'state', fake_game.state):
                self.assertTrue(self.state._run(op, args))
            android_call = self.state.controller.dispatch.call_args

            service = RuntimeDebuggerService()
            service._server = object()
            service._controller = self.state.controller
            service._last_snapshot_time = time.monotonic()
            service._commands.put(PendingCommand(op, args))
            service.update()

            self.assertEqual(android_call, self.state.controller.dispatch.call_args)
            service._server = None

    def test_android_debugger_is_a_fast_forward_blocking_state(self) -> None:
        self.assertTrue(android_debugger.AndroidDebuggerState.blocks_fast_forward)

    def test_touch_consumer_is_installed_and_released_with_debugger_lifecycle(self) -> None:
        self.state.fluid = MagicMock()
        self.state.begin()
        self.assertTrue(is_android_touch_consumer_active())
        self.assertEqual(
            frozenset(('UP', 'DOWN', 'LEFT', 'RIGHT')),
            get_android_touch_passthrough_buttons(),
        )

        self.state.end()
        self.assertFalse(is_android_touch_consumer_active())
        self.assertEqual(frozenset(), get_android_touch_passthrough_buttons())

    def test_native_editor_result_cannot_submit_twice(self) -> None:
        apply = MagicMock()
        result = SimpleNamespace(request_id='1', action='save', value='Eirika')
        with patch.object(android_debugger, 'show_android_debug_input', return_value=True), \
                patch.object(android_debugger, 'poll_android_debug_input', return_value=result), \
                patch.object(android_debugger, 'dismiss_android_debug_input') as dismiss:
            self.state._begin_text('Find unit', '', apply)
            self.state._consume_native_text_result()
            self.state._consume_native_text_result()

        apply.assert_called_once_with('Eirika')
        dismiss.assert_called_once_with('1')


class RuntimeDebuggerHotkeyParityTests(unittest.TestCase):
    def test_desktop_hotkeys_map_to_shared_operations(self) -> None:
        runtime_debugger = MagicMock()
        events = [
            SimpleNamespace(type=engine.KEYDOWN, key=engine.key_map[key], mod=engine.KMOD_CTRL)
            for key in ('1', '2', '3', '4', '5', '0')
        ]
        expected = [
            'max_selected', 'max_players', 'max_enemies',
            'enemy_hp', 'enemy_ai', 'complete_chapter',
        ]
        with patch.dict(driver.cf.SETTINGS, {'debug': True}, clear=False):
            self.assertTrue(driver.check_runtime_debugger(runtime_debugger, events))

        self.assertEqual(
            [((operation,), {}) for operation in expected],
            runtime_debugger.handle_hotkey.call_args_list,
        )


if __name__ == '__main__':
    unittest.main()
