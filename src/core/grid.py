from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

Point = tuple[int, int]


@dataclass(slots=True)
class Grid:
    """A simple 2D grid with orthogonal movement."""

    width: int
    height: int
    walls: set[Point] = field(default_factory=set)

    def in_bounds(self, point: Point) -> bool:
        x, y = point
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, point: Point) -> bool:
        return self.in_bounds(point) and point not in self.walls

    def neighbors(self, point: Point) -> list[Point]:
        x, y = point
        candidates = [
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        ]
        return [candidate for candidate in candidates if self.is_walkable(candidate)]

    def add_walls(self, points: Iterable[Point]) -> None:
        for point in points:
            if self.in_bounds(point):
                self.walls.add(point)

    @classmethod
    def from_ascii(cls, rows: list[str]) -> tuple["Grid", Point, Point]:
        """Build a grid from ASCII rows using # for walls, S for start, and G for goal."""

        if not rows:
            raise ValueError("rows must not be empty")

        width = len(rows[0])
        height = len(rows)
        grid = cls(width=width, height=height)
        start: Point | None = None
        goal: Point | None = None

        for y, row in enumerate(rows):
            if len(row) != width:
                raise ValueError("all rows must have the same width")
            for x, cell in enumerate(row):
                point = (x, y)
                if cell == "#":
                    grid.walls.add(point)
                elif cell == "S":
                    start = point
                elif cell == "G":
                    goal = point

        if start is None or goal is None:
            raise ValueError("rows must include both S and G")

        return grid, start, goal
