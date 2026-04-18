from __future__ import annotations

from dataclasses import dataclass

from core.grid import Grid, Point

DEFAULT_GRID_COLS = 12
DEFAULT_GRID_ROWS = 20
MIN_GRID_COLS = 8
MIN_GRID_ROWS = 10


@dataclass(slots=True)
class ScenarioDefinition:
    name: str
    description: str
    grid: Grid
    start: Point
    goal: Point
    preferred_grid_cols: int
    preferred_grid_rows: int
    scalable: bool = False


def _validate_grid_size(name: str, grid_cols: int, grid_rows: int) -> None:
    if grid_cols < MIN_GRID_COLS or grid_rows < MIN_GRID_ROWS:
        raise ValueError(
            f"Scenario '{name}' requires at least {MIN_GRID_COLS} columns and {MIN_GRID_ROWS} rows."
        )


def _build_open_demo(grid_cols: int = DEFAULT_GRID_COLS, grid_rows: int = DEFAULT_GRID_ROWS) -> ScenarioDefinition:
    _validate_grid_size("open_demo", grid_cols, grid_rows)
    grid = Grid(width=grid_cols, height=grid_rows)
    start = (0, 0)
    goal = (grid_cols - 2, grid_rows - 2)

    for x in range(2, grid_cols - 1, 3):
        gap_center = 2 if (x // 3) % 2 == 0 else grid_rows - 3
        openings = {max(1, gap_center - 1), gap_center, min(grid_rows - 2, gap_center + 1)}
        for y in range(grid_rows - 1):
            if y not in openings:
                grid.walls.add((x, y))

    grid.walls.discard(start)
    grid.walls.discard(goal)
    return ScenarioDefinition(
        name="open_demo",
        description="A scalable reachable demo with a few barriers and clear pathfinding progression.",
        grid=grid,
        start=start,
        goal=goal,
        preferred_grid_cols=grid_cols,
        preferred_grid_rows=grid_rows,
        scalable=True,
    )


def _build_no_path_demo(grid_cols: int = DEFAULT_GRID_COLS, grid_rows: int = DEFAULT_GRID_ROWS) -> ScenarioDefinition:
    _validate_grid_size("no_path_demo", grid_cols, grid_rows)
    grid = Grid(width=grid_cols, height=grid_rows)
    start = (1, 1)
    goal = (grid_cols - 2, grid_rows - 2)
    barrier_row = grid_rows // 2

    for x in range(grid_cols):
        if (x, barrier_row) != start and (x, barrier_row) != goal:
            grid.walls.add((x, barrier_row))

    for x in range(2, grid_cols - 2, 3):
        top_gap = 1 if (x // 3) % 2 == 0 else max(1, barrier_row - 2)
        bottom_gap = min(grid_rows - 2, barrier_row + 2) if (x // 3) % 2 == 0 else grid_rows - 3
        for y in range(barrier_row):
            if abs(y - top_gap) > 1:
                grid.walls.add((x, y))
        for y in range(barrier_row + 1, grid_rows):
            if abs(y - bottom_gap) > 1:
                grid.walls.add((x, y))

    for point in (start, goal):
        grid.walls.discard(point)

    for dx, dy in [(-1, 0), (1, 0), (0, -1)]:
        candidate = (goal[0] + dx, goal[1] + dy)
        if grid.in_bounds(candidate) and candidate != start:
            grid.walls.add(candidate)

    return ScenarioDefinition(
        name="no_path_demo",
        description="A scalable blocked-goal demo that ends in a clear no-path state.",
        grid=grid,
        start=start,
        goal=goal,
        preferred_grid_cols=grid_cols,
        preferred_grid_rows=grid_rows,
        scalable=True,
    )


_wall_grid, _wall_start, _wall_goal = Grid.from_ascii(
    [
        "S...########",
        "###.########",
        "#...########",
        "#.##########",
        "#....#######",
        "####.#######",
        "##...#######",
        "##.#########",
        "##....######",
        "#####.######",
        "###...######",
        "###.########",
        "###....#####",
        "######.#####",
        "####...#####",
        "####.#######",
        "####....####",
        "#######.####",
        "#######...G#",
        "############",
    ]
)

_maze_grid, _maze_start, _maze_goal = Grid.from_ascii(
    [
        "S...#...####",
        ".#.#.#.#####",
        ".#...#...###",
        ".###...#.###",
        ".#...###.###",
        ".#.##....###",
        ".#....##.###",
        ".###.#...###",
        ".#...#.#.###",
        ".#.###.#.###",
        ".#.#...#.###",
        ".#.#.###.###",
        ".#...#...###",
        ".###.#.#.###",
        ".#...#.#.###",
        ".#.###.#.###",
        ".#.....#.###",
        ".#####.#.###",
        ".#.....G.###",
        "############",
    ]
)

_branchy_grid, _branchy_start, _branchy_goal = Grid.from_ascii(
    [
        "S..#########",
        ".###########",
        "....########",
        ".###########",
        ".....#######",
        ".###########",
        "....########",
        ".###########",
        ".....#######",
        ".###########",
        "....########",
        ".##..#######",
        "....########",
        ".###########",
        ".....#######",
        ".###########",
        "....########",
        ".###########",
        ".....G######",
        "############",
    ]
)

SCENARIOS: dict[str, ScenarioDefinition] = {
    "open_demo": _build_open_demo(),
    "wall_demo": ScenarioDefinition(
        name="wall_demo",
        description="A fixed-size wall demo kept for comparison and smoke checks.",
        grid=_wall_grid,
        start=_wall_start,
        goal=_wall_goal,
        preferred_grid_cols=_wall_grid.width,
        preferred_grid_rows=_wall_grid.height,
        scalable=False,
    ),
    "maze_demo": ScenarioDefinition(
        name="maze_demo",
        description="A 12 by 20 branch-heavy maze with forks, dead ends, and rejoining paths.",
        grid=_maze_grid,
        start=_maze_start,
        goal=_maze_goal,
        preferred_grid_cols=_maze_grid.width,
        preferred_grid_rows=_maze_grid.height,
        scalable=False,
    ),
    "branchy_demo": ScenarioDefinition(
        name="branchy_demo",
        description="A fixed-size branch-rich BFS showcase with misleading paths and visible frontier spread.",
        grid=_branchy_grid,
        start=_branchy_start,
        goal=_branchy_goal,
        preferred_grid_cols=_branchy_grid.width,
        preferred_grid_rows=_branchy_grid.height,
        scalable=False,
    ),
    "no_path_demo": _build_no_path_demo(),
}

SCALABLE_SCENARIOS = {
    "open_demo": _build_open_demo,
    "no_path_demo": _build_no_path_demo,
}


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS.keys())


def get_scenario(
    name: str,
    *,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> ScenarioDefinition:
    try:
        scenario = SCENARIOS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario: {name}") from exc

    resolved_cols = grid_cols if grid_cols is not None else scenario.preferred_grid_cols
    resolved_rows = grid_rows if grid_rows is not None else scenario.preferred_grid_rows

    if name in SCALABLE_SCENARIOS:
        return SCALABLE_SCENARIOS[name](resolved_cols, resolved_rows)

    if (resolved_cols, resolved_rows) != (scenario.preferred_grid_cols, scenario.preferred_grid_rows):
        raise ValueError(
            f"Scenario '{name}' is currently fixed-size and supports only "
            f"{scenario.preferred_grid_cols}x{scenario.preferred_grid_rows}."
        )

    return scenario
