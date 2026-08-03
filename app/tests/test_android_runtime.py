import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import android_runtime


class AndroidRuntimeTests(unittest.TestCase):
    def test_visible_height_converts_the_physical_ime_measurement_to_logical_canvas(self):
        with patch('app.engine.android_runtime.get_android_ime_inset_ratio',
                   return_value=0.5):
            self.assertEqual(80, android_runtime.get_android_visible_height(160))

    def test_native_debug_input_result_decodes_utf8_payload(self):
        encoded = base64.b64encode('lệnh;Đơn vị'.encode('utf-8')).decode('ascii')
        overlay = SimpleNamespace(pollResult=lambda: f'8\tsave\t{encoded}')

        with patch('app.engine.android_runtime._get_android_debug_input_overlay',
                   return_value=overlay):
            result = android_runtime.poll_android_debug_input()

        self.assertEqual('8', result.request_id)
        self.assertEqual('save', result.action)
        self.assertEqual('lệnh;Đơn vị', result.value)

    def test_native_debug_input_ignores_malformed_payload(self):
        overlay = SimpleNamespace(pollResult=lambda: 'not-a-result')

        with patch('app.engine.android_runtime._get_android_debug_input_overlay',
                   return_value=overlay):
            self.assertIsNone(android_runtime.poll_android_debug_input())


if __name__ == '__main__':
    unittest.main()
