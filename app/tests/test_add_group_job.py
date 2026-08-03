from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch


class AddGroupJobTests(unittest.TestCase):
    def test_advances_group_members_one_step_at_a_time(self):
        from app.engine.jobs.add_group_job import AddGroupJob

        placed = []
        job = AddGroupJob(['A', 'B'], placed.append)

        job.run_one_operation()
        self.assertEqual(['A'], placed)
        self.assertFalse(job.is_finished)

        job.run_one_operation()
        self.assertEqual(['A', 'B'], placed)
        self.assertTrue(job.is_finished)

    def test_failure_stops_remaining_members(self):
        from app.engine.jobs.add_group_job import AddGroupJob

        def place(unit_nid):
            if unit_nid == 'B':
                raise RuntimeError('placement failed')

        job = AddGroupJob(['A', 'B', 'C'], place)
        job.step(2**63 - 1)

        self.assertTrue(job.failed)
        self.assertIsInstance(job.error, RuntimeError)
        self.assertEqual(2, job.index)

    def test_event_blocks_until_add_group_job_finishes(self):
        from app.events import event_functions

        class FakeJob:
            is_finished = False
            failed = False
            error = None

            def update(self, _should_skip):
                self.is_finished = True
                return True

        job = FakeJob()
        group = SimpleNamespace(units=['unit'])
        event = SimpleNamespace(
            game=SimpleNamespace(level=SimpleNamespace(unit_groups={'group': group})),
            should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: None),
        )

        with patch('app.engine.jobs.add_group_job.AddGroupJob', return_value=job):
            event_functions.add_group(event, 'group')

        self.assertEqual('blocked', event.state)
        self.assertTrue(event.should_remain_blocked[0]())
        self.assertTrue(event.should_update['add_group'](False))
        self.assertFalse(event.should_remain_blocked[0]())
