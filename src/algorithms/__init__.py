"""Algorithm registry for the pathfinding video lab."""

from algorithms.astar import run as run_astar
from algorithms.bfs import run as run_bfs
from algorithms.dfs import run as run_dfs
from algorithms.dijkstra import run as run_dijkstra
from algorithms.greedy_best_first import run as run_greedy_best_first

ALGORITHMS = {
    "astar": run_astar,
    "bfs": run_bfs,
    "dfs": run_dfs,
    "dijkstra": run_dijkstra,
    "greedy_best_first": run_greedy_best_first,
}


def list_algorithms() -> list[str]:
    return sorted(ALGORITHMS.keys())
