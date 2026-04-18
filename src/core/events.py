from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.grid import Point


class EventKind(str, Enum):
    START = "start"
    FRONTIER = "frontier"
    VISITED = "visited"
    EXPAND = "expand"
    PATH = "path"
    GOAL = "goal"
    NO_PATH = "no_path"
    FINISH = "finish"


@dataclass(slots=True)
class SearchEvent:
    """A render-friendly event emitted by an algorithm run."""

    step: int
    kind: EventKind
    point: Point | None = None
    details: dict[str, Any] = field(default_factory=dict)
