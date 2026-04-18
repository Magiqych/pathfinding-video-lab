from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from algorithms import ALGORITHMS, list_algorithms
from core.audio import AudioSynthesizer
from core.config import AppConfig, OutputConfig
from core.exporter import ExportConfig, OfflineExporter
from core.profiles import ExportMode, TimingConfig, get_export_profile, get_layout_profile, list_export_profiles, list_layout_profiles
from core.render_plan import build_render_plan
from core.rendering import GridRenderer
from core.timeline import TimelineBuilder
from core.video import VideoWriter
from scenarios import get_scenario, list_scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pathfinding Video Lab profile-driven export runner")
    parser.add_argument("--algorithm", choices=list_algorithms(), default="bfs")
    parser.add_argument("--scenario", choices=list_scenarios(), default="open_demo")
    parser.add_argument("--export-profile", choices=list_export_profiles(), default="shorts_vertical")
    parser.add_argument("--layout-profile", choices=list_layout_profiles(), default=None)
    parser.add_argument("--export-mode", choices=[mode.value for mode in ExportMode], default=None)
    parser.add_argument(
        "--write-frame",
        action="store_true",
        help="Write a single preview frame to the output/frames folder.",
    )
    parser.add_argument(
        "--write-audio",
        action="store_true",
        help="Write a short synthesized WAV preview for the event timeline.",
    )
    parser.add_argument("--export", action="store_true", help="Render frames, synthesize WAV audio, and export a final MP4.")
    parser.add_argument("--fps", type=int, default=None, help="Optional FPS override for the selected export profile.")
    parser.add_argument("--event-duration-seconds", type=float, default=None, help="Time allocated to each event on the shared timeline.")
    parser.add_argument("--initial-hold-seconds", type=float, default=None, help="How long to hold the initial state before the search starts.")
    parser.add_argument("--final-hold-seconds", type=float, default=None, help="How long to hold the final success state.")
    parser.add_argument("--failure-hold-seconds", type=float, default=None, help="How long to hold the no-path failure state.")
    parser.add_argument("--frame-width", type=int, default=None, help="Optional width override for the chosen export profile.")
    parser.add_argument("--frame-height", type=int, default=None, help="Optional height override for the chosen export profile.")
    parser.add_argument("--grid-cols", type=int, default=None, help="Optional grid column override independent from output resolution.")
    parser.add_argument("--grid-rows", type=int, default=None, help="Optional grid row override independent from output resolution.")
    parser.add_argument("--output-dir", default="output", help="Root output directory for frames, WAV files, and MP4 videos.")
    parser.add_argument("--temp-frames-dir", default=None, help="Optional custom temporary frame directory.")
    parser.add_argument("--keep-temp-frames", action="store_true", help="Keep the numbered PNG frames after a successful export.")
    parser.add_argument("--no-audio", action="store_true", help="Export a silent MP4 without generating a WAV track.")
    return parser


def _resolve_runtime_profiles(args: argparse.Namespace) -> tuple[object, object, TimingConfig, ExportMode]:
    export_profile = get_export_profile(args.export_profile)
    export_mode = ExportMode(args.export_mode) if args.export_mode else export_profile.export_mode
    export_profile = replace(
        export_profile,
        width=args.frame_width or export_profile.width,
        height=args.frame_height or export_profile.height,
        fps=args.fps or export_profile.fps,
        export_mode=export_mode,
    )
    layout_profile = get_layout_profile(args.layout_profile or export_profile.default_layout_profile)
    timing = TimingConfig(
        fps=export_profile.fps,
        event_duration_seconds=args.event_duration_seconds if args.event_duration_seconds is not None else 1.0 / export_profile.fps,
        initial_hold_seconds=args.initial_hold_seconds if args.initial_hold_seconds is not None else 2.0 / export_profile.fps,
        final_hold_seconds=args.final_hold_seconds if args.final_hold_seconds is not None else 8.0 / export_profile.fps,
        failure_hold_seconds=args.failure_hold_seconds if args.failure_hold_seconds is not None else 10.0 / export_profile.fps,
    )
    return export_profile, layout_profile, timing, export_mode


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = AppConfig()
    config.output = OutputConfig(root=Path(args.output_dir))
    config.output.ensure_directories()

    export_profile, layout_profile, timing, export_mode = _resolve_runtime_profiles(args)

    resolved_grid_cols = args.grid_cols or export_profile.default_grid_cols
    resolved_grid_rows = args.grid_rows or export_profile.default_grid_rows
    scenario = get_scenario(args.scenario, grid_cols=resolved_grid_cols, grid_rows=resolved_grid_rows)
    algorithm = ALGORITHMS[args.algorithm]
    events = algorithm(scenario.grid, scenario.start, scenario.goal)
    timeline = TimelineBuilder(timing=timing).build(events)

    run_name = f"{args.algorithm}_{args.scenario}_{scenario.grid.width}x{scenario.grid.height}_{export_profile.name}"
    render_plan = build_render_plan(
        width=export_profile.width,
        height=export_profile.height,
        layout_profile=layout_profile,
        title_text=f"{args.algorithm.upper()} • {args.scenario.replace('_', ' ').upper()}" if layout_profile.show_title else None,
        footer_text=layout_profile.name.replace("_", " ").upper() if layout_profile.show_footer else None,
    )

    renderer = GridRenderer(config.render)
    image = renderer.render_frame(
        scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        events=events,
        render_plan=render_plan,
    )

    if args.write_frame:
        frame_path = Path(config.output.frames_dir) / f"{run_name}_smoke.png"
        renderer.save_frame(image, frame_path)
        print(f"Preview frame written to: {frame_path}")

    if args.write_audio:
        audio_path = Path(config.output.videos_dir) / f"{run_name}_smoke.wav"
        AudioSynthesizer().render_timeline_to_wav(
            timeline.audio_cues,
            timeline.duration_seconds,
            audio_path,
        )
        print(f"Preview audio written to: {audio_path}")

    if args.export:
        export_result = OfflineExporter(
            render_config=config.render,
            export_config=ExportConfig(
                export_profile=export_profile,
                layout_profile=layout_profile,
                timing=timing,
                output_dir=Path(args.output_dir),
                temp_frames_dir=Path(args.temp_frames_dir) if args.temp_frames_dir else None,
                keep_temp_frames=args.keep_temp_frames or export_profile.keep_temp_frames,
                audio_enabled=export_profile.audio_enabled and not args.no_audio,
                overwrite=True,
                export_mode=export_mode,
            ),
        ).export(
            grid=scenario.grid,
            start=scenario.start,
            goal=scenario.goal,
            events=events,
            run_name=run_name,
        )
        print(f"Final MP4 written to: {export_result.video_path}")
        if export_result.wav_path is not None:
            print(f"Temporary WAV kept for debugging at: {export_result.wav_path}")
        if args.keep_temp_frames:
            print(f"Frame sequence kept in: {export_result.frame_dir}")

    writer = VideoWriter(fps=export_profile.fps)
    video_target = Path(config.output.videos_dir) / f"{run_name}.mp4"
    ffmpeg_command = writer.build_ffmpeg_command(
        str(Path(config.output.frames_dir) / run_name / "frame_%06d.png"),
        video_target,
        audio_path=None if args.no_audio else Path(config.output.videos_dir) / f"{run_name}.wav",
        crf=export_profile.crf,
        preset=export_profile.preset,
        video_codec=export_profile.video_codec,
        pixel_format=export_profile.pixel_format,
        audio_codec=export_profile.audio_codec,
        audio_bitrate=export_profile.audio_bitrate,
    )

    print(f"Algorithm: {args.algorithm}")
    print(f"Scenario: {args.scenario}")
    print(f"Export profile: {export_profile.name}")
    print(f"Layout profile: {layout_profile.name}")
    print(f"Canvas: {export_profile.width}x{export_profile.height}")
    print(f"Grid: {scenario.grid.width}x{scenario.grid.height}")
    print(f"Export mode: {export_mode.value}")
    print(f"Event count: {len(events)}")
    print(f"Timeline duration: {timeline.duration_seconds:.2f}s")
    print(f"Audio cues: {len(timeline.audio_cues)}")
    print(f"Audio enabled: {export_profile.audio_enabled and not args.no_audio}")
    print("FFmpeg command preview:")
    print(" ".join(ffmpeg_command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
