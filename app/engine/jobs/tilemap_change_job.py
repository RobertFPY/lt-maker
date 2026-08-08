from __future__ import annotations

import time
from typing import Callable, Generator, Optional, TYPE_CHECKING, Union

from app.engine.boundary import BoundaryInterface
from app.engine.game_board import GameBoard
from app.engine.objects.tilemap import TileMapObject
from app.engine.performance import RUNTIME_PROFILER

if TYPE_CHECKING:
    from app.engine.game_state import GameState


BoardBuilder = Callable[[TileMapObject], Generator[str, None, GameBoard]]
BoundaryBuilder = Callable[[int, int], BoundaryInterface]
TilemapBuilder = Callable[[object], Union[TileMapObject, Generator[str, None, TileMapObject]]]
Commit = Callable[[TileMapObject, GameBoard, BoundaryInterface], None]


class TilemapChangeJob:
    """Build a replacement tilemap and board without touching live state.

    The caller owns the final commit because event commands also need to
    preserve their unit/region bookkeeping.  Until that callback runs, this
    job only owns pending objects and a failure leaves the live map alone.
    """

    FRAME_BUDGET_NS = 4_000_000
    CAPTURE_STATE = 'CAPTURE_STATE'
    CREATE_TILEMAP = 'CREATE_TILEMAP'
    CREATE_TEMP_BOARD = 'CREATE_TEMP_BOARD'
    BUILD_BOARD = 'BUILD_BOARD'
    CREATE_TEMP_BOUNDARY = 'CREATE_TEMP_BOUNDARY'
    VALIDATE = 'VALIDATE'
    COMMIT = 'COMMIT'
    COMPLETE = 'COMPLETE'
    FAILED = 'FAILED'

    def __init__(
        self,
        game: GameState,
        tilemap_prefab: object,
        *,
        tilemap_builder: TilemapBuilder = TileMapObject.from_prefab_iter,
        board_builder: BoardBuilder = GameBoard.build_iter,
        boundary_builder: BoundaryBuilder = BoundaryInterface,
        commit: Commit,
    ) -> None:
        self.game = game
        self.tilemap_prefab = tilemap_prefab
        self.tilemap_builder = tilemap_builder
        self.board_builder = board_builder
        self.boundary_builder = boundary_builder
        self.commit = commit
        self.state = self.CAPTURE_STATE
        self.error: Optional[Exception] = None
        self.pending_tilemap: Optional[TileMapObject] = None
        self.pending_board: Optional[GameBoard] = None
        self.pending_boundary: Optional[BoundaryInterface] = None
        self.last_board_phase: Optional[str] = None
        self._tilemap_iter: Optional[Generator[str, None, TileMapObject]] = None
        self._board_iter: Optional[Generator[str, None, GameBoard]] = None

    @property
    def is_finished(self) -> bool:
        return self.state in (self.COMPLETE, self.FAILED)

    @property
    def succeeded(self) -> bool:
        return self.state == self.COMPLETE

    @property
    def failed(self) -> bool:
        return self.state == self.FAILED

    def update(self, should_skip: bool) -> bool:
        deadline_ns = (2**63 - 1 if should_skip
                       else time.perf_counter_ns() + self.FRAME_BUDGET_NS)
        return self.step(deadline_ns)

    def step(self, deadline_ns: int) -> bool:
        while not self.is_finished and time.perf_counter_ns() < deadline_ns:
            try:
                with RUNTIME_PROFILER.section('tilemap_change.%s' % self.state):
                    self.run_one_operation()
            except Exception as error:
                self.error = error
                self.state = self.FAILED
        return self.is_finished

    def run_one_operation(self) -> None:
        if self.state == self.CAPTURE_STATE:
            self.state = self.CREATE_TILEMAP
        elif self.state == self.CREATE_TILEMAP:
            if self._tilemap_iter is None:
                tilemap_or_iter = self.tilemap_builder(self.tilemap_prefab)
                if not hasattr(tilemap_or_iter, '__next__'):
                    self.pending_tilemap = tilemap_or_iter
                    self.state = self.CREATE_TEMP_BOARD
                    return
                self._tilemap_iter = tilemap_or_iter
            try:
                next(self._tilemap_iter)
            except StopIteration as result:
                self.pending_tilemap = result.value
                self.state = self.CREATE_TEMP_BOARD
        elif self.state == self.CREATE_TEMP_BOARD:
            assert self.pending_tilemap is not None
            self._board_iter = self.board_builder(self.pending_tilemap)
            self.state = self.BUILD_BOARD
        elif self.state == self.BUILD_BOARD:
            assert self._board_iter is not None
            try:
                self.last_board_phase = next(self._board_iter)
            except StopIteration as result:
                self.pending_board = result.value
                self.state = self.CREATE_TEMP_BOUNDARY
        elif self.state == self.CREATE_TEMP_BOUNDARY:
            assert self.pending_tilemap is not None
            self.pending_boundary = self.boundary_builder(
                self.pending_tilemap.width, self.pending_tilemap.height)
            self.state = self.VALIDATE
        elif self.state == self.VALIDATE:
            self._validate()
            self.state = self.COMMIT
        elif self.state == self.COMMIT:
            assert self.pending_tilemap is not None
            assert self.pending_board is not None
            assert self.pending_boundary is not None
            result = self.commit(
                self.pending_tilemap, self.pending_board, self.pending_boundary)
            if result is not None:
                raise TypeError('Tilemap change commit must be synchronous and return None')
            self.state = self.COMPLETE

    def _validate(self) -> None:
        if not self.pending_tilemap or not self.pending_board or not self.pending_boundary:
            raise ValueError('Tilemap change did not build all pending state')
        if (self.pending_board.width, self.pending_board.height) != (
                self.pending_tilemap.width, self.pending_tilemap.height):
            raise ValueError('Pending board dimensions do not match tilemap')
