import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app.engine.android_runtime import (
    is_android_render_optimization_enabled,
    is_android_runtime,
)


class AndroidRenderOptimizationTests(unittest.TestCase):
    def test_desktop_never_enables_android_render_path(self):
        with patch.dict(os.environ, {'LT_ANDROID_RENDER_OPT': '1'}, clear=False):
            os.environ.pop('LT_ANDROID_RUNTIME', None)
            self.assertFalse(is_android_runtime())
            self.assertFalse(is_android_render_optimization_enabled())

    def test_android_requires_both_runtime_and_render_flags(self):
        with patch.dict(os.environ, {
            'LT_ANDROID_RUNTIME': '1',
            'LT_ANDROID_RENDER_OPT': '1',
        }, clear=False):
            self.assertTrue(is_android_runtime())
            self.assertTrue(is_android_render_optimization_enabled())

    def test_android_template_sets_explicit_runtime_flags(self):
        repository = Path(__file__).resolve().parents[2]
        template = repository / 'utilities' / 'build_tools' / 'android_runtime' / 'app_template' / 'main.py'
        source = template.read_text(encoding='utf-8')

        self.assertIn('os.environ.setdefault("LT_ANDROID_RUNTIME", "1")', source)
        self.assertIn('os.environ.setdefault("LT_ANDROID_RENDER_OPT", "1")', source)


if __name__ == '__main__':
    unittest.main()
