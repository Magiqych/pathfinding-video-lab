from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExportMode(str, Enum):
    FRAME_SEQUENCE = "frame_sequence"
    STREAM_TO_FFMPEG = "stream_to_ffmpeg"


@dataclass(frozen=True, slots=True)
class TimingConfig:
    """Time-oriented timing settings that can be converted to frames via FPS."""

    fps: int = 30
    event_duration_seconds: float = 1.0 / 30.0
    initial_hold_seconds: float = 2.0 / 30.0
    final_hold_seconds: float = 8.0 / 30.0
    failure_hold_seconds: float = 10.0 / 30.0


@dataclass(frozen=True, slots=True)
class LayoutProfile:
    """Logical layout settings independent from the final output resolution."""

    name: str
    title_height_ratio: float
    footer_height_ratio: float
    outer_padding_ratio: float
    hud_width_ratio: float = 0.0
    show_title: bool = True
    show_footer: bool = True
    show_hud: bool = False
    show_debug_panel: bool = False


@dataclass(frozen=True, slots=True)
class ExportProfile:
    """Reusable output-profile defaults for different delivery targets."""

    name: str
    width: int
    height: int
    fps: int
    default_grid_cols: int = 12
    default_grid_rows: int = 20
    video_codec: str = "libx264"
    pixel_format: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    preset: str = "medium"
    crf: int = 18
    audio_enabled: bool = True
    keep_temp_frames: bool = False
    export_mode: ExportMode = ExportMode.FRAME_SEQUENCE
    default_layout_profile: str = "shorts_vertical"


EXPORT_PROFILES: dict[str, ExportProfile] = {
    "shorts_vertical": ExportProfile(
        name="shorts_vertical",
        width=1080,
        height=1920,
        fps=30,
        default_layout_profile="shorts_vertical",
        export_mode=ExportMode.FRAME_SEQUENCE,
    ),
    "hd_landscape": ExportProfile(
        name="hd_landscape",
        width=1920,
        height=1080,
        fps=30,
        default_layout_profile="standard_landscape",
        export_mode=ExportMode.FRAME_SEQUENCE,
    ),
    "uhd_4k_landscape": ExportProfile(
        name="uhd_4k_landscape",
        width=3840,
        height=2160,
        fps=30,
        preset="slow",
        default_layout_profile="4k_landscape",
        export_mode=ExportMode.STREAM_TO_FFMPEG,
    ),
}


LAYOUT_PROFILES: dict[str, LayoutProfile] = {
    "shorts_vertical": LayoutProfile(
        name="shorts_vertical",
        title_height_ratio=0.0,
        footer_height_ratio=0.0,
        outer_padding_ratio=0.02,
        show_title=False,
        show_footer=False,
        show_hud=False,
    ),
    "standard_landscape": LayoutProfile(
        name="standard_landscape",
        title_height_ratio=0.10,
        footer_height_ratio=0.08,
        outer_padding_ratio=0.04,
        hud_width_ratio=0.0,
        show_title=True,
        show_footer=True,
        show_hud=False,
    ),
    "4k_landscape": LayoutProfile(
        name="4k_landscape",
        title_height_ratio=0.10,
        footer_height_ratio=0.08,
        outer_padding_ratio=0.035,
        hud_width_ratio=0.18,
        show_title=True,
        show_footer=True,
        show_hud=True,
        show_debug_panel=True,
    ),
}


def list_export_profiles() -> list[str]:
    return sorted(EXPORT_PROFILES.keys())


def list_layout_profiles() -> list[str]:
    return sorted(LAYOUT_PROFILES.keys())


def get_export_profile(name: str) -> ExportProfile:
    try:
        return EXPORT_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown export profile: {name}") from exc


def get_layout_profile(name: str) -> LayoutProfile:
    try:
        return LAYOUT_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown layout profile: {name}") from exc
