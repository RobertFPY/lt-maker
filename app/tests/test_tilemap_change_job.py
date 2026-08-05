from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch


class TilemapChangeJobTests(unittest.TestCase):
    def _job(self, *, board_builder, commit):
        from app.engine.jobs.tilemap_change_job import TilemapChangeJob

        old_tilemap = SimpleNamespace(nid='old', width=2, height=2)
        game = SimpleNamespace(level=SimpleNamespace(tilemap=old_tilemap))
        prefab = SimpleNamespace(nid='new', width=3, height=4)
        return TilemapChangeJob(
            game,
            prefab,
            tilemap_builder=lambda value: value,
            board_builder=board_builder,
            boundary_builder=lambda width, height: (width, height),
            commit=commit,
        ), game, old_tilemap

    def test_builds_offscreen_and_commits_only_after_validation(self):
        commits = []

        def build_board(tilemap):
            yield 'terrain'
            return SimpleNamespace(width=tilemap.width, height=tilemap.height)

        def commit(tilemap, board, boundary):
            commits.append((tilemap, board, boundary))

        job, game, old_tilemap = self._job(
            board_builder=build_board, commit=commit)

        job.step(2**63 - 1)

        self.assertTrue(job.succeeded)
        self.assertEqual('COMPLETE', job.state)
        self.assertIs(game.level.tilemap, old_tilemap)
        self.assertEqual(1, len(commits))
        self.assertEqual('new', commits[0][0].nid)
        self.assertEqual((3, 4), commits[0][2])

    def test_builder_failure_does_not_commit_or_change_the_live_tilemap(self):
        commits = []

        def build_board(_tilemap):
            yield 'terrain'
            raise RuntimeError('board build failed')

        job, game, old_tilemap = self._job(
            board_builder=build_board,
            commit=lambda *_args: commits.append(True),
        )

        job.step(2**63 - 1)

        self.assertTrue(job.failed)
        self.assertIsInstance(job.error, RuntimeError)
        self.assertIs(game.level.tilemap, old_tilemap)
        self.assertEqual([], commits)

    def test_tilemap_builder_iterator_is_advanced_before_board_creation(self):
        from app.engine.jobs.tilemap_change_job import TilemapChangeJob

        tilemap = SimpleNamespace(nid='new', width=3, height=4)

        def build_tilemap(_prefab):
            yield 'sprites'
            return tilemap

        def build_board(_tilemap):
            if False:
                yield 'unused'
            return SimpleNamespace(width=3, height=4)

        job = TilemapChangeJob(
            SimpleNamespace(level=SimpleNamespace(tilemap=SimpleNamespace(nid='old'))),
            SimpleNamespace(nid='new'),
            tilemap_builder=build_tilemap,
            board_builder=build_board,
            boundary_builder=lambda width, height: (width, height),
            commit=lambda *_args: None,
        )

        job.run_one_operation()  # CAPTURE_STATE -> CREATE_TILEMAP
        job.run_one_operation()  # first tilemap batch
        self.assertEqual(job.CREATE_TILEMAP, job.state)
        self.assertIsNone(job.pending_tilemap)

        job.run_one_operation()  # iterator completes
        self.assertEqual(job.CREATE_TEMP_BOARD, job.state)
        self.assertIs(job.pending_tilemap, tilemap)

    def test_commit_generator_is_advanced_in_separate_job_steps(self):
        commits = []

        def build_board(tilemap):
            return_value = SimpleNamespace(width=tilemap.width, height=tilemap.height)
            if False:
                yield 'unused'
            return return_value

        def commit(*_args):
            yield 'DETACH_UNITS'
            commits.append('complete')

        job, _game, _old_tilemap = self._job(
            board_builder=build_board, commit=commit)

        for _ in range(6):
            job.run_one_operation()
        self.assertEqual('COMMIT', job.state)

        job.run_one_operation()
        self.assertEqual([], commits)
        self.assertEqual('DETACH_UNITS', job.last_commit_phase)

        job.run_one_operation()
        self.assertTrue(job.succeeded)
        self.assertEqual(['complete'], commits)

    def test_commit_generator_failure_marks_job_failed(self):
        def build_board(tilemap):
            if False:
                yield 'unused'
            return SimpleNamespace(width=tilemap.width, height=tilemap.height)

        def commit(*_args):
            yield 'DETACH_UNITS'
            raise RuntimeError('restore failed')

        job, _game, _old_tilemap = self._job(
            board_builder=build_board, commit=commit)

        job.step(2**63 - 1)

        self.assertTrue(job.failed)
        self.assertIsInstance(job.error, RuntimeError)

    def test_event_state_retains_last_frame_while_tilemap_job_is_running(self):
        from app.events.event_state import EventState

        state = EventState('event')
        state.event = SimpleNamespace(
            state='blocked', _android_process_yielded=False,
            _defer_render=True,
        )

        self.assertTrue(state.should_defer_render())

    def test_change_tilemap_blocks_event_until_its_job_finishes(self):
        from app.events import event_functions

        class FakeJob:
            is_finished = False
            failed = False
            error = None

            def update(self, _should_skip):
                self.is_finished = True
                return True

        job = FakeJob()
        game = SimpleNamespace(
            level=SimpleNamespace(
                tilemap=SimpleNamespace(nid='old'), regions=[]),
            units=[], level_vars={}, skill_registry={}, terrain_status_registry={},
            action_log=SimpleNamespace(
                actions=[], action_index=-1, _first_free_action=-1),
            board=SimpleNamespace(bounds=(0, 0, 1, 1), previously_visited_tiles=set()),
            cursor=object(), movement=object(), map_view=object(),
        )
        event = SimpleNamespace(
            game=game, should_update={}, should_remain_blocked=[],
            state='processing', logger=SimpleNamespace(error=lambda *_args: None),
        )
        prefab = SimpleNamespace(nid='new')

        with patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=prefab), \
                patch('app.engine.jobs.tilemap_change_job.TilemapChangeJob', return_value=job):
            event_functions.change_tilemap(event, 'new')

        self.assertEqual('blocked', event.state)
        self.assertTrue(event._defer_render)
        self.assertTrue(event.should_remain_blocked[0]())
        self.assertTrue(event.should_update['tilemap_change'](False))
        self.assertFalse(event._defer_render)
        self.assertFalse(event.should_remain_blocked[0]())
