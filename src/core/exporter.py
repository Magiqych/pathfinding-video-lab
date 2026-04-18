from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.audio import AudioSynthesizer
from core.config import OutputConfig, RenderConfig
from core.events import EventKind, SearchEvent
from core.grid import Grid, Point
from core.profiles import ExportMode, ExportProfile, LayoutProfile, TimingConfig, get_export_profile, get_layout_profile
from core.render_plan import build_render_plan
from core.rendering import GridRenderer
from core.timeline import Timeline, TimelineBuilder
from core.video import VideoWriter


@dataclass(slots=True)
class ExportConfig:
    """Profile-driven configuration for offline video export."""

    export_profile: ExportProfile
    layout_profile: LayoutProfile
    timing: TimingConfig
    output_dir: Path = Path("output")
    temp_frames_dir: Path | None = None
    keep_temp_frames: bool | None = None
    keep_temp_audio: bool = False
    audio_enabled: bool | None = None
    overwrite: bool = True
    export_mode: ExportMode | None = None

    def __post_init__(self) -> None:
        if self.keep_temp_frames is None:
            self.keep_temp_frames = self.export_profile.keep_temp_frames
        if self.audio_enabled is None:
            self.audio_enabled = self.export_profile.audio_enabled
        if self.export_mode is None:
            self.export_mode = self.export_profile.export_mode

    @classmethod
    def from_profile_names(
        cls,
        *,
        export_profile_name: str = "shorts_vertical",
        layout_profile_name: str | None = None,
        timing: TimingConfig | None = None,
        **kwargs: object,
    ) -> "ExportConfig":
        export_profile = get_export_profile(export_profile_name)
        layout_profile = get_layout_profile(layout_profile_name or export_profile.default_layout_profile)
        timing = timing or TimingConfig(fps=export_profile.fps)
        return cls(
            export_profile=export_profile,
            layout_profile=layout_profile,
            timing=timing,
            **kwargs,
        )


@dataclass(slots=True)
class ExportResult:
    run_name: str
    frame_dir: Path
    video_path: Path
    wav_path: Path | None
    frame_count: int
    duration_seconds: float
    export_mode: str


class OfflineExporter:
    """Render numbered PNG frames, generate a WAV track, and mux the final MP4."""

    def __init__(
        self,
        render_config: RenderConfig | None = None,
        export_config: ExportConfig | None = None,
    ) -> None:
        self.render_config = render_config or RenderConfig()
        self.export_config = export_config or ExportConfig.from_profile_names()
        self.output_config = OutputConfig(root=self.export_config.output_dir)
        self.output_config.ensure_directories()

    def export(
        self,
        *,
        grid: Grid,
        start: Point,
        goal: Point,
        events: Sequence[SearchEvent],
        run_name: str,
    ) -> ExportResult:
        if not events:
            raise ValueError("At least one event is required for export")

        timeline = TimelineBuilder(timing=self.export_config.timing).build(events)
        frame_dir = self._resolve_frame_dir(run_name)
        video_path = Path(self.output_config.videos_dir) / f"{run_name}.mp4"
        wav_path = Path(self.output_config.videos_dir) / f"{run_name}.wav" if self.export_config.audio_enabled else None

        retained_wav_path = wav_path

        try:
            if self.export_config.export_mode == ExportMode.FRAME_SEQUENCE:
                self._export_via_frame_sequence(
                    grid=grid,
                    start=start,
                    goal=goal,
                    timeline=timeline,
                    frame_dir=frame_dir,
                    video_path=video_path,
                    wav_path=wav_path,
                    run_name=run_name,
                )
            else:
                self._export_via_stream_mode(
                    grid=grid,
                    start=start,
                    goal=goal,
                    timeline=timeline,
                    frame_dir=frame_dir,
                    video_path=video_path,
                    wav_path=wav_path,
                    run_name=run_name,
                )
        except Exception:
            raise
        else:
            retained_wav_path = self._cleanup_temp_audio(wav_path)
            self._cleanup_temp_frames(frame_dir)

        return ExportResult(
            run_name=run_name,
            frame_dir=frame_dir,
            video_path=video_path,
            wav_path=retained_wav_path,
            frame_count=timeline.frame_count,
            duration_seconds=timeline.duration_seconds,
            export_mode=self.export_config.export_mode.value,
        )

    def _export_via_frame_sequence(
        self,
        *,
        grid: Grid,
        start: Point,
        goal: Point,
        timeline: Timeline,
        frame_dir: Path,
        video_path: Path,
        wav_path: Path | None,
        run_name: str,
    ) -> None:
        self.render_frame_sequence(
            grid=grid,
            start=start,
            goal=goal,
            timeline=timeline,
            frame_dir=frame_dir,
            run_name=run_name,
        )
        self._write_audio_track(timeline, wav_path)
        self._mux_video(frame_dir=frame_dir, video_path=video_path, wav_path=wav_path)

    def _export_via_stream_mode(
        self,
        *,
        grid: Grid,
        start: Point,
        goal: Point,
        timeline: Timeline,
        frame_dir: Path,
        video_path: Path,
        wav_path: Path | None,
        run_name: str,
    ) -> None:
        """Scaffolded stream mode for future long-form and 4K efficiency.

        The current implementation still stages PNG frames for reliability and debuggability,
        but the export mode is explicit so it can later be upgraded to direct ffmpeg piping.
        """

        self.render_frame_sequence(
            grid=grid,
            start=start,
            goal=goal,
            timeline=timeline,
            frame_dir=frame_dir,
            run_name=run_name,
        )
        self._write_audio_track(timeline, wav_path)
        self._mux_video(frame_dir=frame_dir, video_path=video_path, wav_path=wav_path)

    def render_frame_sequence(
        self,
        *,
        grid: Grid,
        start: Point,
        goal: Point,
        timeline: Timeline,
        frame_dir: Path,
        run_name: str = "preview_run",
    ) -> Path:
        frame_dir.mkdir(parents=True, exist_ok=True)
        renderer = GridRenderer(self.render_config)
        render_plan = build_render_plan(
            width=self.export_config.export_profile.width,
            height=self.export_config.export_profile.height,
            layout_profile=self.export_config.layout_profile,
            title_text=run_name.replace("_", " ").upper() if self.export_config.layout_profile.show_title else None,
            footer_text=self._footer_text(timeline),
        )
        applied_count = 0

        try:
            for frame_index in range(timeline.frame_count):
                while (
                    applied_count < len(timeline.timed_events)
                    and timeline.timed_events[applied_count].frame_index <= frame_index
                ):
                    applied_count += 1

                active_events = [item.event for item in timeline.timed_events[:applied_count]]
                image = renderer.render_frame(
                    grid,
                    start=start,
                    goal=goal,
                    events=active_events,
                    render_plan=render_plan,
                )
                renderer.save_frame(image, frame_dir / f"frame_{frame_index + 1:06d}.png")
        except Exception as exc:
            raise RuntimeError(f"Frame rendering failed at frame {frame_index + 1}") from exc

        return frame_dir

    def _write_audio_track(self, timeline: Timeline, wav_path: Path | None) -> None:
        if self.export_config.audio_enabled and wav_path is not None:
            AudioSynthesizer().render_timeline_to_wav(
                timeline.audio_cues,
                timeline.duration_seconds,
                wav_path,
            )

    def _cleanup_temp_audio(self, wav_path: Path | None) -> Path | None:
        if wav_path is None:
            return None
        if self.export_config.keep_temp_audio:
            return wav_path if wav_path.exists() else None
        if not wav_path.exists():
            return None

        try:
            wav_path.unlink()
        except OSError as exc:
            print(f"Warning: keeping temporary WAV for debugging because cleanup failed: {wav_path} ({exc})")
            return wav_path

        return None

    def _cleanup_temp_frames(self, frame_dir: Path) -> None:
        if self.export_config.keep_temp_frames:
            return
        if not frame_dir.exists():
            return

        try:
            shutil.rmtree(frame_dir)
        except OSError as exc:
            print(
                f"Warning: keeping temporary frame directory for debugging because cleanup failed: {frame_dir} ({exc})"
            )

    def _mux_video(self, *, frame_dir: Path, video_path: Path, wav_path: Path | None) -> None:
        profile = self.export_config.export_profile
        VideoWriter(fps=profile.fps).mux_png_sequence_to_mp4(
            frame_pattern=str(frame_dir / "frame_%06d.png"),
            output_path=video_path,
            audio_path=wav_path,
            overwrite=self.export_config.overwrite,
            crf=profile.crf,
            preset=profile.preset,
            video_codec=profile.video_codec,
            pixel_format=profile.pixel_format,
            audio_codec=profile.audio_codec,
            audio_bitrate=profile.audio_bitrate,
        )

    def _resolve_frame_dir(self, run_name: str) -> Path:
        if self.export_config.temp_frames_dir is not None:
            return self.export_config.temp_frames_dir
        return Path(self.output_config.frames_dir) / run_name

    def _footer_text(self, timeline: Timeline) -> str | None:
        if not self.export_config.layout_profile.show_footer:
            return None
        if any(item.event.kind == EventKind.NO_PATH for item in timeline.timed_events):
            return "NO PATH"
        return self.export_config.export_profile.name.replace("_", " ").upper()
