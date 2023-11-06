from __future__ import annotations

from typing import Generic, Tuple, TypeVar

from app.utilities.typing import Pos

T = TypeVar('T')

class Grid(Generic[T]):
    __slots__ = ['width', 'height', '_cells']

    def __init__(self, size: Tuple[int, int]):
        self.width, self.height = size
        self._cells = [None for _ in range(self.width * self.height)]

    def get(self, pos: Pos) -> T:
        return self._cells[pos[0] * self.height + pos[1]]
        
    def insert(self, pos: Pos, obj: T):
        self._cells[pos[0] * self.height + pos[1]] = obj

    def cells(self):
        return self._cells

    def apply_bounds(self, bounds: Tuple[int, int, int, int]) -> BoundedGrid:
        new_grid = BoundedGrid((self.width, self.height), bounds)
        new_grid._cells = self._cells

class BoundedGrid(Grid[T]):
    __slots__ = ['width', 'height', '_cells', 'bounds']

    def __init__(self, size: Tuple[int, int], bounds: Tuple[int, int, int, int]):
        self.width, self.height = size
        self._cells = [None for _ in range(self.width * self.height)]
        self.bounds = bounds

    def check_bounds(self, pos: Pos) -> bool:
        """
        Leftmost, Topmost, Rightmost, Bottommost valid position
        """
        return self.bounds[0] <= pos[0] <= self.bounds[2] and self.bounds[1] <= pos[1] <= self.bounds[3]
