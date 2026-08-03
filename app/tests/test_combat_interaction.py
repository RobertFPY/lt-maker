import unittest
from types import SimpleNamespace

from app.engine.combat.interaction import _validated_num_targets


class CombatInteractionTests(unittest.TestCase):
    def test_invalid_num_targets_falls_back_to_single_target(self):
        item = SimpleNamespace(nid="TestItem")

        self.assertEqual(1, _validated_num_targets(None, item))
        self.assertEqual(1, _validated_num_targets("invalid", item))
        self.assertEqual(1, _validated_num_targets(0, item))

    def test_valid_num_targets_is_preserved(self):
        item = SimpleNamespace(nid="TestItem")

        self.assertEqual(3, _validated_num_targets(3, item))


if __name__ == "__main__":
    unittest.main()
