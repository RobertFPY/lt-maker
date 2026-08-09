from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch


class TilemapWorkBudgetPolicyTests(unittest.TestCase):
    def test_desktop_disables_progressive_tilemap_preparation(self):
        from app.engine.runtime_capabilities import work_budget

        with patch.object(work_budget, 'is_android_runtime', return_value=False):
            budget = work_budget.tilemap_prepare_budget()

        self.assertFalse(budget.enabled)

    def test_android_uses_the_accepted_four_millisecond_off_world_budget(self):
        from app.engine.runtime_capabilities import work_budget

        with patch.object(work_budget, 'is_android_runtime', return_value=True):
            budget = work_budget.tilemap_prepare_budget()

        self.assertTrue(budget.enabled)
        self.assertEqual(4_000_000, budget.deadline_ns)

    def test_policy_module_has_no_gameplay_critical_imports(self):
        source = (Path(__file__).parents[1] / 'engine' / 'runtime_capabilities' /
                  'work_budget.py').read_text(encoding='utf-8')

        for forbidden in (
                'app.engine.game_state', 'app.events', 'app.engine.action',
                'app.engine.combat', 'app.engine.save', 'app.engine.state_machine',
                'app.engine.game_board', 'app.engine.objects.unit'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
