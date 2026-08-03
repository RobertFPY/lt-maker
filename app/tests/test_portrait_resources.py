import unittest

from app.data.resources.portraits import PortraitPrefab


class PortraitResourceRestoreTests(unittest.TestCase):
    def test_restore_legacy_portrait_uses_compatible_defaults(self):
        portrait = PortraitPrefab.restore({
            'nid': 'legacy',
            'blinking_offset': [24, 24],
            'smiling_offset': [16, 40],
            'info_offset': 3,
        })

        self.assertEqual((8, 3), portrait.info_offset)
        self.assertEqual((128, 80), portrait.chibi_coord)
        self.assertEqual((160, 112), portrait.full_size)
        self.assertEqual((96, 80), portrait.face_size)
        self.assertEqual((32, 16), portrait.blink_size)
        self.assertEqual((32, 16), portrait.mouth_size)
        self.assertEqual(2, portrait.blink_frames)
        self.assertEqual(3, portrait.mouth_frames)

    def test_restore_current_portrait_preserves_explicit_coordinates(self):
        portrait = PortraitPrefab.restore({
            'nid': 'current',
            'blinking_offset': [24, 24],
            'smiling_offset': [16, 40],
            'info_offset': [6, 2],
            'chibi_coord': [120, 80],
            'full_size': [160, 112],
            'face_size': [96, 80],
            'blink_size': [32, 16],
            'mouth_size': [32, 16],
            'blink_frames': 2,
            'mouth_frames': 3,
        })

        self.assertEqual((6, 2), portrait.info_offset)
        self.assertEqual((120, 80), portrait.chibi_coord)
