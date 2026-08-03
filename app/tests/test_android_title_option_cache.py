import ast
from pathlib import Path
import unittest


class AndroidTitleOptionCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).parents[1] / 'engine' / 'game_menus' / 'menu_options.py'
        ).read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.title_option = next(
            node for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'TitleOption'
        )
        cls.methods = {
            node.name: node for node in cls.title_option.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_android_cache_has_dedicated_render_path(self):
        self.assertIn('_draw_android_cached_text', self.methods)
        draw_text = ast.get_source_segment(self.source, self.methods['draw_text'])
        self.assertIn('is_android_render_optimization_enabled()', draw_text)

    def test_text_change_invalidates_android_render_cache(self):
        self.assertIn('_invalidate_android_text_cache', self.methods)
        set_text = ast.get_source_segment(self.source, self.methods['set_text'])
        self.assertIn('self._invalidate_android_text_cache()', set_text)

    def test_cache_is_bounded_by_animation_phase(self):
        cached_draw = ast.get_source_segment(
            self.source, self.methods['_draw_android_cached_text']
        )
        self.assertIn('_ANDROID_TITLE_OUTLINE_PHASES', cached_draw)
        self.assertIn('_android_outline_cache', cached_draw)

    def test_chapter_select_initializes_the_shared_cache(self):
        chapter_select = next(
            node for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'ChapterSelectOption'
        )
        init = next(
            node for node in chapter_select.body
            if isinstance(node, ast.FunctionDef) and node.name == '__init__'
        )
        init_source = ast.get_source_segment(self.source, init)

        self.assertIn('self._invalidate_android_text_cache()', init_source)


class AndroidSettingsCompositionTests(unittest.TestCase):
    def test_settings_stays_opaque_when_android_controls_are_available(self):
        source = (Path(__file__).parents[1] / 'engine' / 'settings.py').read_text(
            encoding='utf-8'
        )
        tree = ast.parse(source)
        settings_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'SettingsMenuState'
        )
        start = next(
            node for node in settings_class.body
            if isinstance(node, ast.FunctionDef) and node.name == 'start'
        )
        assignments = [
            node for node in ast.walk(start)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == 'self'
                and target.attr == 'transparent'
                for target in node.targets
            )
        ]

        self.assertEqual(1, len(assignments))
        self.assertIsInstance(assignments[0].value, ast.Constant)
        self.assertIs(assignments[0].value.value, False)


if __name__ == '__main__':
    unittest.main()
