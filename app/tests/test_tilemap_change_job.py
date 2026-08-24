from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch


class TilemapChangeJobTests(unittest.TestCase):
    def _job(self, *, board_builder, commit):
        from app.engine.jobs.tilemap_change_job import TilemapChangeJob
        from app.engine.runtime_capabilities.work_budget import OffWorldWorkBudget

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
            work_budget=OffWorldWorkBudget(True, 4_000_000),
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
        from app.engine.runtime_capabilities.work_budget import OffWorldWorkBudget

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
            work_budget=OffWorldWorkBudget(True, 4_000_000),
        )

        job.run_one_operation()  # CAPTURE_STATE -> CREATE_TILEMAP
        job.run_one_operation()  # first tilemap batch
        self.assertEqual(job.CREATE_TILEMAP, job.state)
        self.assertIsNone(job.pending_tilemap)

        job.run_one_operation()  # iterator completes
        self.assertEqual(job.CREATE_TEMP_BOARD, job.state)
        self.assertIs(job.pending_tilemap, tilemap)

    def test_multiple_pending_build_operations_leave_live_world_unchanged(self):
        def build_board(tilemap):
            yield 'terrain'
            yield 'collections'
            return SimpleNamespace(width=tilemap.width, height=tilemap.height)

        job, game, old_tilemap = self._job(
            board_builder=build_board, commit=lambda *_args: None)
        old_board = object()
        old_unit_position = (1, 1)
        old_region_position = (2, 2)
        game.board = old_board
        game.units = [SimpleNamespace(position=old_unit_position)]
        game.level.regions = [SimpleNamespace(position=old_region_position)]

        for _ in range(5):
            job.run_one_operation()
            self.assertIs(old_tilemap, game.level.tilemap)
            self.assertIs(old_board, game.board)
            self.assertEqual(old_unit_position, game.units[0].position)
            self.assertEqual(old_region_position, game.level.regions[0].position)

        self.assertEqual(job.BUILD_BOARD, job.state)

    def test_skip_drains_only_pending_off_world_preparation(self):
        def build_board(tilemap):
            yield 'terrain'
            yield 'collections'
            return SimpleNamespace(width=tilemap.width, height=tilemap.height)

        commits = []
        job, game, old_tilemap = self._job(
            board_builder=build_board,
            commit=lambda tilemap, board, boundary: commits.append((tilemap, board, boundary)),
        )

        self.assertTrue(job.update(should_skip=True))
        self.assertTrue(job.succeeded)
        self.assertIs(old_tilemap, game.level.tilemap)
        self.assertEqual(1, len(commits))

    def test_commit_callback_must_not_be_a_generator(self):

        def build_board(tilemap):
            return_value = SimpleNamespace(width=tilemap.width, height=tilemap.height)
            if False:
                yield 'unused'
            return return_value

        def commit(*_args):
            yield 'DETACH_UNITS'

        job, _game, _old_tilemap = self._job(
            board_builder=build_board, commit=commit)

        job.step(2**63 - 1)

        self.assertTrue(job.failed)
        self.assertIsInstance(job.error, TypeError)
        self.assertIn('synchronous', str(job.error))

    def test_synchronous_commit_failure_marks_job_failed(self):
        def build_board(tilemap):
            if False:
                yield 'unused'
            return SimpleNamespace(width=tilemap.width, height=tilemap.height)

        def commit(*_args):
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
            state='blocked',
            _defer_render=True,
        )

        self.assertTrue(state.should_defer_render())

    def test_android_change_tilemap_blocks_event_until_its_job_finishes(self):
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

        with patch.object(event_functions, 'tilemap_prepare_budget',
                           return_value=SimpleNamespace(enabled=True, deadline_ns=4_000_000)), \
                patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=prefab), \
                patch('app.engine.jobs.tilemap_change_job.TilemapChangeJob',
                      return_value=job) as job_type:
            event_functions.change_tilemap(event, 'new')

        self.assertEqual('blocked', event.state)
        self.assertTrue(event._defer_render)
        self.assertTrue(event._android_tilemap_pending)
        self.assertEqual(4_000_000, job_type.call_args.kwargs['work_budget'].deadline_ns)
        self.assertTrue(event.should_remain_blocked[0]())
        self.assertTrue(event.should_update['tilemap_change'](False))
        self.assertFalse(event._defer_render)
        self.assertFalse(event._android_tilemap_pending)
        self.assertFalse(event.should_remain_blocked[0]())

    def test_android_failed_tilemap_job_releases_barrier_after_rollback(self):
        from app.events import event_functions

        class FakeJob:
            is_finished = False
            failed = True
            error = RuntimeError('pending build failed')

            def update(self, _should_skip):
                self.is_finished = True
                return True

        errors = []
        job = FakeJob()
        game = SimpleNamespace(
            level=SimpleNamespace(tilemap=SimpleNamespace(nid='old'), regions=[]),
            units=[], level_vars={}, skill_registry={}, terrain_status_registry={},
            action_log=SimpleNamespace(actions=[], action_index=-1, _first_free_action=-1),
            board=SimpleNamespace(bounds=(0, 0, 1, 1), previously_visited_tiles=set()),
            cursor=object(), movement=object(), map_view=object(),
        )
        event = SimpleNamespace(
            game=game, should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: errors.append(_args)),
        )

        with patch.object(event_functions, 'tilemap_prepare_budget',
                           return_value=SimpleNamespace(enabled=True, deadline_ns=4_000_000)), \
                patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=object()), \
                patch('app.engine.jobs.tilemap_change_job.TilemapChangeJob', return_value=job):
            event_functions.change_tilemap(event, 'new')

        self.assertTrue(event._android_tilemap_pending)
        self.assertTrue(event.should_update['tilemap_change'](False))
        self.assertFalse(event._android_tilemap_pending)
        self.assertFalse(event._defer_render)
        self.assertEqual(1, len(errors))

    def test_android_pending_barrier_runs_only_tilemap_work_and_suspends_movement(self):
        from app.events.event import Event

        updates = []
        unit = SimpleNamespace(position=(1, 1))

        def advance_movement():
            updates.append('movement')
            unit.position = (2, 1)

        movement = SimpleNamespace(update=advance_movement)
        event = SimpleNamespace(
            should_update={
                'tilemap_change': lambda _skip: updates.append('tilemap') or False,
                'other': lambda _skip: updates.append('other') or False,
            },
            do_skip=False,
            game=SimpleNamespace(movement=movement, units=[unit]),
            _android_tilemap_pending=True,
            _update_state=lambda: updates.append('state'),
            _update_text_boxes=lambda: updates.append('text'),
        )

        Event.update(event)

        self.assertEqual(['tilemap', 'state', 'text'], updates)
        self.assertEqual((1, 1), unit.position)
        self.assertIn('tilemap_change', event.should_update)
        self.assertIn('other', event.should_update)

    def test_android_pending_barrier_ignores_gameplay_input_listeners(self):
        from app.events.event import Event

        received = []
        event = SimpleNamespace(
            _android_tilemap_pending=True,
            state='processing',
            functions_listening_for_input={'mutating_listener': received.append},
        )

        Event.take_input(event, 'SELECT')

        self.assertEqual([], received)

    def test_android_pending_barrier_resumes_lifecycle_once_on_next_outer_update(self):
        from app.events.event import Event

        updates = []
        event = SimpleNamespace(
            should_update={
                'tilemap_change': lambda _skip: setattr(
                    event, '_android_tilemap_pending', False) or updates.append('tilemap') or True,
                'other': lambda _skip: updates.append('other') or True,
            },
            do_skip=False,
            game=SimpleNamespace(movement=SimpleNamespace(
                update=lambda: updates.append('movement'))),
            _android_tilemap_pending=True,
            _update_state=lambda: updates.append('state'),
            _update_text_boxes=lambda: updates.append('text'),
        )

        Event.update(event)
        self.assertEqual(['tilemap', 'state', 'text'], updates)
        self.assertNotIn('tilemap_change', event.should_update)
        self.assertIn('other', event.should_update)

        Event.update(event)
        self.assertEqual(
            ['tilemap', 'state', 'text', 'other', 'movement', 'state', 'text'], updates)
        self.assertEqual({}, event.should_update)

    def test_android_pending_blocker_prevents_processor_progress(self):
        from app.events.event import Event

        calls = []
        event = SimpleNamespace(
            state='blocked', prev_state=None,
            should_remain_blocked=[lambda: True],
            logger=SimpleNamespace(debug=lambda *_args: None),
            process=lambda: calls.append('process'),
        )

        Event._update_state(event)

        self.assertEqual([], calls)
        self.assertEqual('blocked', event.state)

    def test_desktop_change_tilemap_commits_atomically_without_a_job(self):
        from app.events import event_functions

        order = []

        class Tilemap:
            def __init__(self, nid):
                self.nid = nid
                self.width = 3
                self.height = 3

            def check_bounds(self, _position):
                return True

        class Level:
            def __init__(self):
                self._tilemap = Tilemap('old')
                self.regions = [region]

            @property
            def tilemap(self):
                return self._tilemap

            @tilemap.setter
            def tilemap(self, value):
                order.append('publish_tilemap')
                self._tilemap = value

        class ActionLog:
            actions = []
            action_index = -1
            _first_free_action = -1

            def set_first_free_action(self):
                order.append('action_log')

        class Cursor:
            def set_pos(self, position):
                order.append(('cursor', position))

        class Game:
            def __init__(self):
                self.level = Level()
                self.units = [unit]
                self.level_vars = {}
                self.skill_registry = {}
                self.terrain_status_registry = {}
                self.action_log = ActionLog()
                self.board = SimpleNamespace(
                    bounds=(0, 0, 2, 2), previously_visited_tiles=set())
                self.boundary = object()
                self.cursor = Cursor()
                self.movement = object()
                self.map_view = object()

            @property
            def tilemap(self):
                return self.level.tilemap

            def is_displaying_overworld(self):
                return False

            def get_unit(self, nid):
                return unit if nid == unit.nid else None

            def get_region(self, nid):
                return region if nid == region.nid else None

            def on_alter_game_state(self):
                order.append('invalidate')

        unit = SimpleNamespace(nid='unit', position=(1, 1), previous_position=None,
                               _skills=[], _visible_skills_cache=[])
        region = SimpleNamespace(nid='region', position=(2, 2))
        game = Game()
        event = SimpleNamespace(
            game=game, should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: None),
        )
        pending_tilemap = Tilemap('new')
        pending_board = SimpleNamespace(width=3, height=3)
        pending_boundary = object()

        def build_board(_tilemap, **_kwargs):
            if False:
                yield 'unused'
            return pending_board

        class Leave:
            def __init__(self, actor):
                self.actor = actor

            def execute(self):
                order.append('leave')
                self.actor.position = None

        class Remove:
            def __init__(self, target):
                self.target = target

            def execute(self):
                order.append('remove_region')
                self.target.position = None

        class Arrive:
            def __init__(self, actor, position):
                self.actor = actor
                self.position = position

            def execute(self):
                order.append('arrive')
                self.actor.position = self.position

        class Add:
            def __init__(self, target):
                self.target = target

            def execute(self):
                order.append('add_region')

        with patch.object(event_functions, 'tilemap_prepare_budget',
                           return_value=SimpleNamespace(enabled=False, deadline_ns=0)), \
                patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=object()), \
                patch.object(event_functions.TileMapObject, 'from_prefab', return_value=pending_tilemap), \
                patch('app.engine.game_board.GameBoard.build_iter', side_effect=build_board), \
                patch('app.engine.boundary.BoundaryInterface', return_value=pending_boundary), \
                patch.object(event_functions.action, 'LeaveMap', Leave), \
                patch.object(event_functions.action, 'RemoveRegion', Remove), \
                patch.object(event_functions.action, 'ArriveOnMap', Arrive), \
                patch.object(event_functions.action, 'AddRegion', Add), \
                patch('app.engine.jobs.tilemap_change_job.TilemapChangeJob',
                      side_effect=AssertionError('desktop must not create a tilemap job')):
            event_functions.change_tilemap(event, 'new', flags={'reload'})

        self.assertEqual(
            [('cursor', (0, 0)), 'leave', 'remove_region', 'publish_tilemap',
             'arrive', 'add_region', 'action_log', 'invalidate'], order)
        self.assertIs(pending_tilemap, game.level.tilemap)
        self.assertIs(pending_board, game.board)
        self.assertIs(pending_boundary, game.boundary)
        self.assertEqual((1, 1), unit.position)
        self.assertEqual((2, 2), region.position)
        self.assertEqual('processing', event.state)
        self.assertEqual({}, event.should_update)
        self.assertEqual([], event.should_remain_blocked)

    def test_desktop_pending_build_failure_leaves_live_world_untouched(self):
        from app.events import event_functions

        old_tilemap = SimpleNamespace(nid='old')
        event = SimpleNamespace(
            game=SimpleNamespace(
                level=SimpleNamespace(tilemap=old_tilemap, regions=[]), units=[],
                level_vars={}, skill_registry={}, terrain_status_registry={},
                action_log=SimpleNamespace(actions=[], action_index=-1, _first_free_action=-1),
                board=SimpleNamespace(bounds=(0, 0, 1, 1), previously_visited_tiles=set()),
                boundary=object(), cursor=object(), movement=object(), map_view=object()),
            should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: None),
        )
        event.game.is_displaying_overworld = lambda: False

        with patch.object(event_functions, 'tilemap_prepare_budget',
                           return_value=SimpleNamespace(enabled=False, deadline_ns=0)), \
                patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=object()), \
                patch.object(event_functions.TileMapObject, 'from_prefab',
                             side_effect=RuntimeError('pending build failed')):
            with self.assertRaisesRegex(RuntimeError, 'pending build failed'):
                event_functions.change_tilemap(event, 'new')

        self.assertIs(old_tilemap, event.game.level.tilemap)
        self.assertEqual([], event.game.units)
        self.assertEqual({}, event.game.level_vars)
        self.assertEqual({}, event.should_update)
        self.assertEqual([], event.should_remain_blocked)

    def test_desktop_commit_failure_rolls_back_before_propagating_error(self):
        from app.events import event_functions

        class Tilemap:
            def __init__(self, nid):
                self.nid = nid
                self.width = 3
                self.height = 3

            def check_bounds(self, _position):
                return True

        class Regions(list):
            def restore(self, values):
                self[:] = values

        class Board:
            def __init__(self):
                self.bounds = (0, 0, 2, 2)
                self.previously_visited_tiles = {(0, 0)}

            def set_bounds(self, *bounds):
                self.bounds = bounds

            def set_previously_visited_tiles(self, fog_state):
                self.previously_visited_tiles = fog_state

            def set_unit(self, _position, _unit):
                pass

        class Boundary:
            def register_unit_auras(self, _unit):
                pass

            def arrive(self, _unit):
                pass

        old_tilemap = Tilemap('old')
        pending_tilemap = Tilemap('new')
        unit = SimpleNamespace(nid='unit', position=(1, 1), previous_position=None,
                               _skills=[], _visible_skills_cache=[], all_skills=[])
        region = SimpleNamespace(nid='region', position=(2, 2), region_type=None)
        old_regions = Regions([region])
        old_board = Board()
        old_boundary = Boundary()
        action_log = SimpleNamespace(actions=['existing'], action_index=0, _first_free_action=0,
                                     set_first_free_action=lambda: None)
        cursor = SimpleNamespace(set_pos=lambda _position: None)
        region_lookup = SimpleNamespace(cache_clear=lambda: None)
        game = SimpleNamespace(
            level=SimpleNamespace(tilemap=old_tilemap, regions=old_regions), units=[unit],
            level_vars={}, skill_registry={}, terrain_status_registry={}, action_log=action_log,
            board=old_board, boundary=old_boundary, cursor=cursor, movement=object(), map_view=object(),
            get_unit=lambda nid: unit if nid == unit.nid else None,
            get_region=lambda nid: region if nid == region.nid else None,
            get_region_under_pos=region_lookup,
            is_displaying_overworld=lambda: False,
            on_alter_game_state=lambda: None,
        )
        game.tilemap = old_tilemap
        event = SimpleNamespace(
            game=game, should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: None),
        )
        pending_board = SimpleNamespace(width=3, height=3)
        pending_boundary = Boundary()
        restored_board = Board()
        restored_boundary = Boundary()

        def build_board(_tilemap, **_kwargs):
            if False:
                yield 'unused'
            return pending_board

        class Leave:
            def __init__(self, actor):
                self.actor = actor

            def execute(self):
                self.actor.position = None

        class Remove:
            def __init__(self, target):
                self.target = target

            def execute(self):
                self.target.position = None

        class Arrive:
            def __init__(self, _actor, _position):
                pass

            def execute(self):
                raise RuntimeError('restore unit failed')

        class UpdateFog:
            def __init__(self, _unit):
                pass

            def execute(self):
                pass

        with patch.object(event_functions, 'tilemap_prepare_budget',
                           return_value=SimpleNamespace(enabled=False, deadline_ns=0)), \
                patch.object(event_functions.RESOURCES.tilemaps, 'get', return_value=object()), \
                patch.object(event_functions.TileMapObject, 'from_prefab', return_value=pending_tilemap), \
                patch('app.engine.game_board.GameBoard', return_value=restored_board) as board_type, \
                patch('app.engine.boundary.BoundaryInterface',
                      side_effect=[pending_boundary, restored_boundary]), \
                patch.object(event_functions.action, 'LeaveMap', Leave), \
                patch.object(event_functions.action, 'RemoveRegion', Remove), \
                patch.object(event_functions.action, 'ArriveOnMap', Arrive), \
                patch.object(event_functions.action, 'UpdateFogOfWar', UpdateFog):
            board_type.build_iter.side_effect = build_board
            with self.assertRaisesRegex(RuntimeError, 'restore unit failed'):
                event_functions.change_tilemap(event, 'new', flags={'reload'})

        self.assertIs(old_tilemap, game.level.tilemap)
        self.assertIs(restored_board, game.board)
        self.assertIs(restored_boundary, game.boundary)
        self.assertEqual((1, 1), unit.position)
        self.assertEqual((2, 2), region.position)
        self.assertEqual(['existing'], action_log.actions)
        self.assertEqual({}, event.should_update)
        self.assertEqual([], event.should_remain_blocked)
