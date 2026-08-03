import ast
from pathlib import Path
import unittest

from app.engine import android_runtime


class _FakeVirtualControls:
    def __init__(self):
        self.active = False
        self.begin_calls = 0
        self.cancel_calls = 0
        self.result = None

    def begin_editor(self):
        self.active = True
        self.begin_calls += 1

    def cancel_editor(self):
        self.active = False
        self.cancel_calls += 1
        self.result = "cancel"

    def is_editor_active(self):
        return self.active

    def consume_editor_result(self):
        result = self.result
        self.result = None
        return result


class AndroidVirtualControlsSettingsTests(unittest.TestCase):
    def tearDown(self):
        android_runtime.register_android_virtual_controls(None)

    def test_runtime_bridge_returns_registered_controller(self):
        controls = _FakeVirtualControls()
        android_runtime.register_android_virtual_controls(controls)
        self.assertIs(controls, android_runtime.get_android_virtual_controls())

    def test_settings_declares_android_editor_route(self):
        engine_dir = Path(__file__).parents[1] / 'engine'
        settings_tree = ast.parse((engine_dir / 'settings.py').read_text(encoding='utf-8'))
        state_machine_tree = ast.parse((engine_dir / 'state_machine.py').read_text(encoding='utf-8'))

        settings_classes = {
            node.name: node for node in settings_tree.body if isinstance(node, ast.ClassDef)
        }
        self.assertIn('AndroidControlsEditorState', settings_classes)
        settings_methods = {
            node.name for node in settings_classes['SettingsMenuState'].body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn('_open_android_controls_editor', settings_methods)
        self.assertIn('draw_android_controls_prompt', settings_methods)

        self.assertIn("'android_controls_editor': settings.AndroidControlsEditorState",
                      ast.unparse(state_machine_tree))

        source = (engine_dir / 'settings.py').read_text(encoding='utf-8')
        self.assertIn('Press DOWN to configure', source)
        editor_class = settings_classes['AndroidControlsEditorState']
        self.assertIn(
            'transparent = True',
            ast.get_source_segment(source, editor_class),
        )
        editor_draw = next(
            node for node in editor_class.body
            if isinstance(node, ast.FunctionDef) and node.name == 'draw'
        )
        self.assertNotIn(
            'bg_black',
            ast.get_source_segment(source, editor_draw),
        )
        self.assertIn(
            'MapState.draw(self, surf)',
            ast.get_source_segment(source, editor_draw),
        )
