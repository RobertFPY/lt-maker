import unittest
from unittest.mock import patch

from app.engine.combat.solver import CombatPhaseSolver


class CombatSolverMissingItemTests(unittest.TestCase):
    def test_scripted_phase_without_item_is_noop(self):
        solver = CombatPhaseSolver.__new__(CombatPhaseSolver)
        solver.main_item = object()
        solver.def_item = None
        solver.items = [solver.main_item]
        solver.current_command = "miss2"

        with patch("app.engine.combat.solver.combat_calcs.compute_hit") as compute_hit:
            solver.process(
                [],
                [],
                attacker=type("Unit", (), {"nid": "Defender"})(),
                defender=object(),
                def_pos=(0, 0),
                item=None,
                def_item=solver.main_item,
                mode="defense",
                attack_info=(0, 0),
            )

        compute_hit.assert_not_called()
