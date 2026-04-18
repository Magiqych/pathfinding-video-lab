from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class RenderConfig:
    """Logical rendering hints that scale with the chosen canvas size."""

    cell_size: int = 32
    margin: int = 16
    min_line_width: int = 1
    grid_line_scale: float = 0.06
    label_padding_scale: float = 0.30


@dataclass(slots=True)
class OutputConfig:
    """Filesystem locations for generated artifacts."""

    root: Path = Path("output")
    frames_dir: Path | None = None
    videos_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.frames_dir is None:
            self.frames_dir = self.root / "frames"
        if self.videos_dir is None:
            self.videos_dir = self.root / "videos"

    def ensure_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        assert self.frames_dir is not None
        assert self.videos_dir is not None
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AppConfig:
    """Top-level application configuration container."""

    render: RenderConfig = field(default_factory=RenderConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
