import unittest
from contextlib import ExitStack
from unittest.mock import patch

from app.engine import combat_calcs, item_system, skill_system


class FollowUpPhaseResolutionTests(unittest.TestCase):
    def _resolve(self, *, can_double=True, hard_no_double=False,
                 self_prevent=False, foe_prevent=False,
                 foe_natural_prevent=False,
                 neutralize_prevention=False, neutralize_grants=False,
                 normal_grants=1, early_grants=1, natural=1):
        unit = object()
        target = object()
        item = object()
        def_item = object()

        with ExitStack() as stack:
            stack.enter_context(patch.object(item_system, 'can_double', return_value=can_double))
            stack.enter_context(patch.object(skill_system, 'no_double', return_value=hard_no_double))
            stack.enter_context(patch.object(skill_system, 'prevent_self_follow_up', return_value=self_prevent, create=True))
            stack.enter_context(patch.object(skill_system, 'prevent_foe_follow_up', return_value=foe_prevent, create=True))
            stack.enter_context(patch.object(skill_system, 'prevent_foe_natural_follow_up', return_value=foe_natural_prevent, create=True))
            stack.enter_context(patch.object(skill_system, 'neutralize_follow_up_prevention', return_value=neutralize_prevention, create=True))
            stack.enter_context(patch.object(skill_system, 'neutralize_foe_follow_up_grants', return_value=neutralize_grants, create=True))
            stack.enter_context(patch.object(skill_system, 'no_dynamic_attacks', return_value=False))
            stack.enter_context(patch.object(skill_system, 'negate_no_dynamic_attacks', return_value=False))
            stack.enter_context(patch.object(item_system, 'dynamic_attacks', return_value=0))
            stack.enter_context(patch.object(skill_system, 'dynamic_attacks', return_value=normal_grants))
            stack.enter_context(patch.object(skill_system, 'dynamic_early_attacks', return_value=early_grants, create=True))
            stack.enter_context(patch.object(skill_system, 'dynamic_follow_up_proc_count', return_value=0, create=True))
            stack.enter_context(patch('app.engine.combat_calcs.outspeed', return_value=natural))
            stack.enter_context(patch('app.engine.combat_calcs.resolve_weapon', return_value=def_item))
            return combat_calcs.compute_attack_phase_plan(
                unit, target, item, def_item, 'attack', (0, 0))

    def test_adds_natural_normal_and_early_follow_up_phases(self):
        plan = self._resolve()

        self.assertEqual(4, plan.total_phases)
        self.assertEqual(1, plan.early_phases)

    def test_prevention_blocks_every_follow_up_source(self):
        plan = self._resolve(self_prevent=True, normal_grants=2, early_grants=2)

        self.assertEqual(1, plan.total_phases)
        self.assertEqual(0, plan.early_phases)

    def test_prevention_neutralization_restores_every_follow_up_source(self):
        plan = self._resolve(foe_prevent=True, neutralize_prevention=True,
                             normal_grants=2, early_grants=2)

        self.assertEqual(6, plan.total_phases)
        self.assertEqual(2, plan.early_phases)

    def test_foe_grant_neutralization_preserves_natural_follow_up(self):
        plan = self._resolve(neutralize_grants=True, normal_grants=2,
                             early_grants=2, natural=1)

        self.assertEqual(2, plan.total_phases)
        self.assertEqual(0, plan.early_phases)

    def test_foe_natural_follow_up_prevention_keeps_granted_phases(self):
        plan = self._resolve(foe_natural_prevent=True, normal_grants=2,
                             early_grants=2, natural=1)

        self.assertEqual(5, plan.total_phases)
        self.assertEqual(2, plan.early_phases)

    def test_prevention_neutralization_restores_foe_natural_follow_up(self):
        plan = self._resolve(foe_natural_prevent=True,
                             neutralize_prevention=True, normal_grants=2,
                             early_grants=2, natural=1)

        self.assertEqual(6, plan.total_phases)
        self.assertEqual(2, plan.early_phases)

    def test_hard_no_double_clamps_all_granted_follow_up_phases(self):
        plan = self._resolve(hard_no_double=True, normal_grants=2,
                             early_grants=2, neutralize_prevention=True)

        self.assertEqual(1, plan.total_phases)
        self.assertEqual(0, plan.early_phases)

    def test_item_that_cannot_double_clamps_all_follow_up_phases(self):
        plan = self._resolve(can_double=False, normal_grants=2,
                             early_grants=2, neutralize_prevention=True)

        self.assertEqual(1, plan.total_phases)
        self.assertEqual(0, plan.early_phases)


if __name__ == '__main__':
    unittest.main()
