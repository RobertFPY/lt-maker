from __future__ import annotations

class McostGrid():
    default_value = 1

    def __init__(self) -> None:
        self.grid: list[list[int]] = []
        self.terrain_types: list[str] = []
        self.unit_types: list[str] = []

    @property
    def row_headers(self) -> list[str]:
        return self.terrain_types

    @property
    def column_headers(self) -> list[str]:
        return self.unit_types

    def set(self, coord: tuple[int, int], val: int) -> None:
        x, y = coord
        self.grid[y][x] = val

    def get(self, coord: tuple[int, int]) -> int:
        x, y = coord
        return self.grid[y][x]

    def get_mcost(self, unit_type: str, terrain_type: str) -> int:
        cidx = self.unit_types.index(unit_type)
        ridx = self.terrain_types.index(terrain_type)
        return self.get((cidx, ridx))

    def width(self) -> int:
        return len(self.unit_types)

    def height(self) -> int:
        return len(self.terrain_types)

    def add_row(self, name: str) -> None:
        self.terrain_types.append(name)
        self.grid.append([self.default_value] * self.width())

    def add_column(self, name: str) -> None:
        self.unit_types.append(name)
        for row in self.grid:
            row.append(self.default_value)

    def insert_column(self, name: str, idx: int) -> None:
        self.unit_types.insert(idx, name)
        for row in self.grid:
            row.insert(idx, self.default_value)

    def insert_row(self, name: str, idx: int) -> None:
        self.terrain_types.insert(idx, name)
        self.grid.insert(idx, [self.default_value] * self.width())

    def delete_column(self, idx: int) -> None:
        self.unit_types.pop(idx)
        for row in self.grid:
            row.pop(idx)

    def delete_row(self, idx: int) -> None:
        self.terrain_types.pop(idx)
        self.grid.pop(idx)

    def get_row(self, idx: int) -> list[int]:
        return self.grid[idx]

    def get_column(self, idx: int) -> list[int]:
        return [row[idx] for row in self.grid]

    def set_row(self, idx: int, data: list[int]) -> None:
        self.grid[idx] = data

    def set_column(self, idx: int, data: list[int]) -> None:
        for row, val in enumerate(data):
            self.grid[row][idx] = val

    def get_terrain_types(self) -> list[str]:
        return self.terrain_types

    def get_unit_types(self) -> list[str]:
        return self.unit_types

    def save(self) -> tuple[list[list[int]], list[str], list[str]]:
        return ([x[:] for x in self.grid], self.terrain_types[:], self.unit_types[:])

    def restore(self, data: tuple[list[list[int]], list[str], list[str]]) -> McostGrid:
        self.grid = data[0]
        self.terrain_types = data[1]
        self.unit_types = data[2]
        return self
