from __future__ import annotations

from collections import deque

from core.events import EventKind, SearchEvent
from core.grid import Grid, Point

NEIGHBOR_ORDER: tuple[Point, ...] = (
    (0, -1),  # up
    (1, 0),   # right
    (0, 1),   # down
    (-1, 0),  # left
)


def run(grid: Grid, start: Point, goal: Point) -> list[SearchEvent]:
    """Run breadth-first search and emit visualization-friendly events.

    Neighbor visitation order is fixed as: up, right, down, left.
    This keeps the resulting search and reconstructed path deterministic.
    """

    events: list[SearchEvent] = []
    step = 0

    def emit(kind: EventKind, point: Point | None = None, **details: object) -> None:
        nonlocal step
        events.append(SearchEvent(step=step, kind=kind, point=point, details=dict(details)))
        step += 1

    if not grid.in_bounds(start):
        raise ValueError("start is outside the grid bounds")
    if not grid.in_bounds(goal):
        raise ValueError("goal is outside the grid bounds")
    if not grid.is_walkable(start):
        raise ValueError("start is blocked and cannot be searched")
    if not grid.is_walkable(goal):
        raise ValueError("goal is blocked and cannot be searched")

    emit(EventKind.START, start, algorithm="bfs", neighbor_order="up,right,down,left")

    if start == goal:
        emit(EventKind.GOAL, goal, found=True, distance=0)
        emit(EventKind.PATH, start, path_index=0, path_length=0)
        emit(EventKind.FINISH, goal, status="success", found=True, path_length=0, visited_count=1)
        return events

    frontier: deque[Point] = deque([start])
    parents: dict[Point, Point | None] = {start: None}
    distances: dict[Point, int] = {start: 0}

    emit(EventKind.FRONTIER, start, queue_size=1, distance=0)

    while frontier:
        current = frontier.popleft()
        emit(EventKind.EXPAND, current, queue_size=len(frontier), distance=distances[current])
        emit(EventKind.VISITED, current, distance=distances[current])

        for neighbor in _ordered_neighbors(grid, current):
            if neighbor in parents:
                continue

            parents[neighbor] = current
            distances[neighbor] = distances[current] + 1
            frontier.append(neighbor)
            emit(
                EventKind.FRONTIER,
                neighbor,
                parent=current,
                queue_size=len(frontier),
                distance=distances[neighbor],
            )

            if neighbor == goal:
                emit(EventKind.GOAL, goal, found=True, distance=distances[goal])
                path = _reconstruct_path(parents, goal)
                for index, point in enumerate(path):
                    emit(EventKind.PATH, point, path_index=index, path_length=len(path) - 1)
                emit(
                    EventKind.FINISH,
                    goal,
                    status="success",
                    found=True,
                    path_length=len(path) - 1,
                    visited_count=len(parents),
                )
                return events

    emit(EventKind.NO_PATH, goal, found=False, reason="frontier_exhausted")
    emit(EventKind.FINISH, goal, status="no_path", found=False, visited_count=len(parents))
    return events


def _ordered_neighbors(grid: Grid, point: Point) -> list[Point]:
    x, y = point
    ordered: list[Point] = []
    for dx, dy in NEIGHBOR_ORDER:
        candidate = (x + dx, y + dy)
        if grid.is_walkable(candidate):
            ordered.append(candidate)
    return ordered


def _reconstruct_path(parents: dict[Point, Point | None], goal: Point) -> list[Point]:
    path: list[Point] = []
    current: Point | None = goal
    while current is not None:
        path.append(current)
        current = parents[current]
    path.reverse()
    return path
