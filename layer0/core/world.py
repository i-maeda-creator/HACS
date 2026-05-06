from __future__ import annotations
from enum import IntEnum


class Cell(IntEnum):
    EMPTY = 0
    WALL = 1
    CHARGE = 2
    DANGER = 3


class World:
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.grid: list[list[Cell]] = [
            [Cell.EMPTY] * width for _ in range(height)
        ]

    def set_cell(self, x: int, y: int, cell: Cell) -> None:
        self.grid[y][x] = cell

    def get_cell(self, x: int, y: int) -> Cell:
        return self.grid[y][x]

    def is_passable(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.grid[y][x] != Cell.WALL

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def charger_positions(self) -> list:
        return [(x, y)
                for y in range(self.height)
                for x in range(self.width)
                if self.grid[y][x] == Cell.CHARGE]

    def nearest_charger(self, x: int, y: int):
        best, best_d = None, float("inf")
        for cx, cy in self.charger_positions():
            d = abs(cx - x) + abs(cy - y)
            if d < best_d:
                best, best_d = (cx, cy), d
        return best

    @classmethod
    def default_layout(cls) -> "World":
        w = cls(20, 20)
        for x in range(20):
            w.set_cell(x, 0, Cell.WALL)
            w.set_cell(x, 19, Cell.WALL)
        for y in range(20):
            w.set_cell(0, y, Cell.WALL)
            w.set_cell(19, y, Cell.WALL)
        w.set_cell(1, 1, Cell.CHARGE)
        w.set_cell(18, 18, Cell.CHARGE)
        w.set_cell(18, 1, Cell.CHARGE)
        return w
