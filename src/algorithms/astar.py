from __future__ import annotations

from core.events import EventKind, SearchEvent
from core.grid import Grid, Point


def run(grid: Grid, start: Point, goal: Point) -> list[SearchEvent]:
    """Placeholder A* implementation for smoke testing the pipeline."""

    del grid
    return [
        SearchEvent(step=0, kind=EventKind.START, point=start, details={"algorithm": "astar"}),
        SearchEvent(step=1, kind=EventKind.FRONTIER, point=start, details={"heuristic": "manhattan"}),
        SearchEvent(step=2, kind=EventKind.GOAL, point=goal, details={"note": "goal registered"}),
        SearchEvent(step=3, kind=EventKind.FINISH, point=goal, details={"status": "not implemented yet"}),
    ]
