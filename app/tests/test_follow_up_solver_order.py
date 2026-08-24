import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import combat_calcs
from app.engine.combat.solver import (
    AttackerPartnerState, AttackerState, CombatPhaseSolver,
    DefenderPartnerState, DefenderState, InitState,
)
from app.data.database.database import DB


class FollowUpSolverOrderTests(unittest.TestCase):
    def test_terminal_strike_stops_every_scheduler_state_before_next_phase(self):
        solver = SimpleNamespace(force_end_combat=True)
        for state in (InitState(), AttackerState(), AttackerPartnerState(),
                      DefenderState(), DefenderPartnerState()):
            self.assertEqual('done', state.get_next_state(solver))

    def test_attacker_runs_early_phase_before_counterattack(self):
        solver = SimpleNamespace(
            attacker=SimpleNamespace(strike_partner=None),
            defender=SimpleNamespace(strike_partner=None),
            main_item=object(),
            def_item=object(),
            num_attacks=1,
            num_defends=0,
            num_subattacks=1,
            num_subdefends=0,
            attacker_partner_pending=0,
            get_script=lambda: '--',
            attacker_alive=lambda: True,
            defender_alive=lambda: True,
            item_has_uses=lambda: True,
            allow_counterattack=lambda: True,
            attacker_has_desperation=lambda: False,
            get_attack_info=lambda: (1, 0),
            get_defense_info=lambda: (0, 0),
            get_attack_phase_plan=lambda *args: combat_calcs.compute_attack_phase_plan(*args),
        )

        with patch('app.engine.combat.solver.combat_calcs.compute_attack_phase_plan', side_effect=(
                combat_calcs.AttackPhasePlan(2, 1),
                combat_calcs.AttackPhasePlan(1, 0))):
            next_state = AttackerState().get_next_state(solver)

        self.assertEqual('attacker', next_state)

    def test_early_group_does_not_skip_limited_strike_partner(self):
        solver = SimpleNamespace(
            attacker=SimpleNamespace(strike_partner=object()),
            defender=SimpleNamespace(strike_partner=None),
            main_item=object(),
            def_item=object(),
            num_attacks=3,
            num_defends=0,
            num_subattacks=1,
            num_subdefends=0,
            attacker_partner_pending=1,
            get_script=lambda: '--',
            attacker_alive=lambda: True,
            defender_alive=lambda: True,
            attacker_partner_alive=lambda: True,
            attacker_partner_item_has_uses=lambda: True,
            item_has_uses=lambda: True,
            allow_counterattack=lambda: True,
            attacker_has_desperation=lambda: False,
            get_attack_info=lambda: (3, 0),
            get_defense_info=lambda: (0, 0),
            get_attack_phase_plan=lambda *args: combat_calcs.compute_attack_phase_plan(*args),
        )

        with patch.object(DB.constants, 'value', return_value=True), \
                patch('app.engine.combat.solver.combat_calcs.compute_attack_phase_plan', side_effect=(
                    combat_calcs.AttackPhasePlan(3, 2),
                    combat_calcs.AttackPhasePlan(1, 0))):
            next_state = AttackerState().get_next_state(solver)

        self.assertEqual('attacker_partner', next_state)

    def test_each_completed_phase_queues_partner_when_limit_is_disabled(self):
        solver = CombatPhaseSolver.__new__(CombatPhaseSolver)
        solver.attacker = SimpleNamespace(strike_partner=object())
        solver.attacker_partner_pending = 0
        solver.num_attacks = 1
        solver.attacker_partner_alive = lambda: True
        solver.attacker_partner_item_has_uses = lambda: True

        with patch.object(DB.constants, 'value', return_value=False):
            solver.queue_attacker_partner()
            solver.num_attacks = 2
            solver.queue_attacker_partner()

        self.assertEqual(2, solver.attacker_partner_pending)

    def test_limited_strike_partner_only_queues_after_first_phase(self):
        solver = CombatPhaseSolver.__new__(CombatPhaseSolver)
        solver.attacker = SimpleNamespace(strike_partner=object())
        solver.attacker_partner_pending = 0
        solver.num_attacks = 1
        solver.attacker_partner_alive = lambda: True
        solver.attacker_partner_item_has_uses = lambda: True

        with patch.object(DB.constants, 'value', return_value=True):
            solver.queue_attacker_partner()
            solver.num_attacks = 2
            solver.queue_attacker_partner()

        self.assertEqual(1, solver.attacker_partner_pending)

    def test_solver_reuses_proc_grants_for_later_phase_plan_queries(self):
        """A proc follow-up must not consume fresh RNG on every scheduler pass."""
        solver = CombatPhaseSolver.__new__(CombatPhaseSolver)
        solver._phase_plan_proc_grants = {}
        attacker = object()
        defender = object()
        item = object()
        defender_item = object()

        with patch('app.engine.combat.solver.combat_calcs.compute_attack_phase_plan',
                   side_effect=(
                       combat_calcs.AttackPhasePlan(4, 1, 2),
                       combat_calcs.AttackPhasePlan(4, 1, 2),
                   )) as resolve:
            first = solver.get_attack_phase_plan(
                attacker, defender, item, defender_item, 'attack', (0, 0))
            second = solver.get_attack_phase_plan(
                attacker, defender, item, defender_item, 'attack', (1, 0))

        self.assertEqual(4, first.total_phases)
        self.assertEqual(4, second.total_phases)
        self.assertEqual(
            ((id(attacker), 'attack'),),
            tuple(solver._phase_plan_proc_grants.keys()),
        )
        self.assertEqual(2, resolve.call_count)
        self.assertNotIn('proc_grants', resolve.call_args_list[0].kwargs)
        self.assertEqual(2, resolve.call_args_list[1].kwargs['proc_grants'])


if __name__ == '__main__':
    unittest.main()
