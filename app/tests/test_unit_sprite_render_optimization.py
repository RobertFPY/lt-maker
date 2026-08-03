import unittest
from types import SimpleNamespace

from app.engine.unit_sprite import SingleMapSprite


class _Frame:
    def __init__(self):
        self.copy_calls = 0

    def copy(self):
        self.copy_calls += 1
        return object()


class SingleMapSpriteRenderTests(unittest.TestCase):
    def test_frame_reference_avoids_copy_only_when_requested(self):
        frame = _Frame()
        sprite = SingleMapSprite()
        sprite.frames = [frame]
        sprite.counter = SimpleNamespace(count=0)

        self.assertIs(frame, sprite.get_frame(copy=False))
        self.assertEqual(0, frame.copy_calls)
        self.assertIsNot(frame, sprite.get_frame())
        self.assertEqual(1, frame.copy_calls)


if __name__ == '__main__':
    unittest.main()
