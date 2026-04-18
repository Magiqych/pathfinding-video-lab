from __future__ import annotations

import wave
from pathlib import Path

from PIL import Image

from algorithms import ALGORITHMS
from app import main
from core import theme
from core.audio import AudioSynthesizer
from core.config import OutputConfig, RenderConfig
from core.events import EventKind, SearchEvent
from core.exporter import ExportConfig, OfflineExporter
from core.grid import Grid
from core.profiles import ExportMode, TimingConfig, get_export_profile, get_layout_profile, list_export_profiles, list_layout_profiles
from core.render_plan import build_render_plan, resolve_layout
from core.rendering import GridRenderer
from core.timeline import TimelineBuilder
from core.video import VideoWriter
from scenarios import get_scenario


def _count_branch_points(grid: Grid) -> int:
    total = 0
    for y in range(grid.height):
        for x in range(grid.width):
            point = (x, y)
            if grid.is_walkable(point) and len(grid.neighbors(point)) >= 3:
                total += 1
    return total


def _count_dead_ends(grid: Grid) -> int:
    total = 0
    for y in range(grid.height):
        for x in range(grid.width):
            point = (x, y)
            if grid.is_walkable(point) and len(grid.neighbors(point)) == 1:
                total += 1
    return total


def test_imports_and_cli_smoke() -> None:
    assert "bfs" in ALGORITHMS
    assert main(["--algorithm", "bfs", "--scenario", "open_demo"]) == 0


def test_export_profiles_resolve_correctly() -> None:
    assert "shorts_vertical" in list_export_profiles()
    assert "hd_landscape" in list_export_profiles()
    assert get_export_profile("shorts_vertical").width == 1080
    assert get_export_profile("shorts_vertical").default_grid_cols == 12
    assert get_export_profile("hd_landscape").height == 1080
    assert get_export_profile("uhd_4k_landscape").width == 3840
    assert get_export_profile("uhd_4k_landscape").export_mode == ExportMode.STREAM_TO_FFMPEG


def test_layout_profiles_resolve_correctly() -> None:
    assert "shorts_vertical" in list_layout_profiles()
    assert "standard_landscape" in list_layout_profiles()

    standard_layout = get_layout_profile("standard_landscape")
    standard_resolved = resolve_layout(standard_layout, 1920, 1080)
    assert standard_resolved.grid_box[2] > standard_resolved.grid_box[0]
    assert standard_resolved.grid_box[3] > standard_resolved.grid_box[1]
    assert standard_resolved.title_box is not None
    assert standard_resolved.footer_box is not None

    shorts_layout = get_layout_profile("shorts_vertical")
    shorts_resolved = resolve_layout(shorts_layout, 1080, 1920)
    shorts_grid_width = shorts_resolved.grid_box[2] - shorts_resolved.grid_box[0]
    shorts_grid_height = shorts_resolved.grid_box[3] - shorts_resolved.grid_box[1]

    assert shorts_resolved.title_box is None
    assert shorts_resolved.footer_box is None
    assert shorts_grid_width / 1080 > 0.90
    assert shorts_grid_height / 1920 > 0.90


def test_output_directories_can_be_created(tmp_path: Path) -> None:
    config = OutputConfig(root=tmp_path / "output")
    config.ensure_directories()

    assert config.frames_dir is not None
    assert config.videos_dir is not None
    assert config.frames_dir.exists()
    assert config.videos_dir.exists()


def test_final_path_theme_is_bright_and_distinct() -> None:
    assert theme.PATH == (255, 213, 74)
    assert theme.PATH != theme.VISITED
    assert theme.PATH != theme.FRONTIER
    assert theme.PATH != theme.WALL
    assert theme.PATH != theme.OPEN_CELL
    assert theme.PATH_BORDER != theme.PATH


def test_renderer_draws_final_path_with_highlight_border() -> None:
    grid, start, goal = Grid.from_ascii(["S.G"])
    renderer = GridRenderer(RenderConfig(cell_size=40, margin=4))
    render_plan = build_render_plan(
        width=360,
        height=360,
        layout_profile=get_layout_profile("shorts_vertical"),
    )
    image = renderer.render_frame(
        grid,
        start=start,
        goal=goal,
        events=[SearchEvent(step=1, kind=EventKind.PATH, point=(1, 0))],
        render_plan=render_plan,
    )

    origin_x, origin_y, cell_size, _ = renderer._grid_metrics(grid, render_plan)
    center_pixel = image.getpixel((origin_x + cell_size + cell_size // 2, origin_y + cell_size // 2))
    border_pixel = image.getpixel((origin_x + cell_size + max(1, cell_size // 7), origin_y + max(1, cell_size // 7)))

    assert center_pixel == theme.PATH
    assert border_pixel == theme.PATH_BORDER


def test_bfs_emits_non_empty_event_stream() -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)

    assert events
    assert events[0].kind == EventKind.START
    assert events[-1].kind == EventKind.FINISH


def test_renderer_is_not_tied_to_a_single_resolution() -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    renderer = GridRenderer(RenderConfig(cell_size=20, margin=4))

    vertical_plan = build_render_plan(
        width=1080,
        height=1920,
        layout_profile=get_layout_profile("shorts_vertical"),
        title_text="BFS",
    )
    landscape_plan = build_render_plan(
        width=1920,
        height=1080,
        layout_profile=get_layout_profile("standard_landscape"),
        title_text="BFS",
    )

    vertical_image = renderer.render_frame(
        scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        events=events,
        render_plan=vertical_plan,
    )
    landscape_image = renderer.render_frame(
        scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        events=events,
        render_plan=landscape_plan,
    )

    assert vertical_image.size == (1080, 1920)
    assert landscape_image.size == (1920, 1080)


def test_different_grid_sizes_render_with_same_export_profile() -> None:
    renderer = GridRenderer(RenderConfig(cell_size=20, margin=4))
    render_plan = build_render_plan(
        width=1080,
        height=1920,
        layout_profile=get_layout_profile("shorts_vertical"),
        title_text="BFS",
    )

    _, _, small_cell_size, _ = renderer.compute_cell_metrics(
        grid_cols=12,
        grid_rows=20,
        grid_box=render_plan.grid_box,
    )
    _, _, large_cell_size, _ = renderer.compute_cell_metrics(
        grid_cols=16,
        grid_rows=24,
        grid_box=render_plan.grid_box,
    )

    assert small_cell_size > large_cell_size
    assert small_cell_size >= 4
    assert large_cell_size >= 4


def test_video_writer_interface_is_callable(tmp_path: Path) -> None:
    writer = VideoWriter(fps=30)
    output_path = writer.prepare_output_path(tmp_path / "preview.mp4")
    command = writer.build_ffmpeg_command(
        "frame_%06d.png",
        output_path,
        audio_path=tmp_path / "preview.wav",
        video_codec="libx264",
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_bitrate="192k",
    )

    assert output_path.parent.exists()
    assert command[0] == "ffmpeg"
    assert "libx264" in command
    assert "aac" in command
    assert callable(writer.write_video)


def test_bfs_reconstructs_the_shortest_path_correctly() -> None:
    grid, start, goal = Grid.from_ascii(
        [
            "S..",
            "##.",
            "..G",
        ]
    )

    events = ALGORITHMS["bfs"](grid, start, goal)
    path_points = [event.point for event in events if event.kind == EventKind.PATH]

    assert path_points == [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]


def test_bfs_returns_no_path_when_blocked() -> None:
    grid, start, goal = Grid.from_ascii(
        [
            "S#G",
            "###",
            "...",
        ]
    )

    events = ALGORITHMS["bfs"](grid, start, goal)
    finish_event = events[-1]

    assert finish_event.kind == EventKind.FINISH
    assert finish_event.details["status"] == "no_path"
    assert any(event.kind == EventKind.NO_PATH for event in events)
    assert not any(event.kind == EventKind.PATH for event in events)


def test_maze_and_no_path_scenarios_have_blocked_cells_and_large_dimensions() -> None:
    maze = get_scenario("maze_demo")
    no_path = get_scenario("no_path_demo")
    branchy = get_scenario("branchy_demo")

    assert maze.grid.width == 12 and maze.grid.height == 20
    assert no_path.grid.width == 12 and no_path.grid.height == 20
    assert branchy.grid.width == 12 and branchy.grid.height == 20
    assert len(maze.grid.walls) > 0
    assert len(no_path.grid.walls) > 0
    assert len(branchy.grid.walls) > 0


def test_scenario_grid_compatibility_is_validated() -> None:
    scalable = get_scenario("open_demo", grid_cols=16, grid_rows=24)
    assert scalable.grid.width == 16
    assert scalable.grid.height == 24
    assert scalable.scalable is True

    try:
        get_scenario("maze_demo", grid_cols=16, grid_rows=24)
    except ValueError as exc:
        assert "fixed-size" in str(exc)
    else:
        raise AssertionError("Expected maze_demo to reject unsupported grid dimensions")


def test_branching_scenarios_are_not_single_corridors() -> None:
    maze = get_scenario("maze_demo")
    branchy = get_scenario("branchy_demo")

    assert _count_branch_points(maze.grid) >= 4
    assert _count_dead_ends(maze.grid) >= 4
    assert _count_branch_points(branchy.grid) >= 5
    assert _count_dead_ends(branchy.grid) >= 5

    maze_events = ALGORITHMS["bfs"](maze.grid, maze.start, maze.goal)
    branchy_events = ALGORITHMS["bfs"](branchy.grid, branchy.start, branchy.goal)

    assert any(event.kind == EventKind.PATH for event in maze_events)
    assert any(event.kind == EventKind.PATH for event in branchy_events)


def test_no_path_demo_is_truly_unreachable() -> None:
    scenario = get_scenario("no_path_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)

    assert any(event.kind == EventKind.NO_PATH for event in events)
    assert events[-1].kind == EventKind.FINISH
    assert events[-1].details["status"] == "no_path"


def test_bfs_rejects_invalid_start_or_goal() -> None:
    grid = Grid(width=3, height=3)

    try:
        ALGORITHMS["bfs"](grid, (-1, 0), (2, 2))
    except ValueError as exc:
        assert "start" in str(exc)
    else:
        raise AssertionError("Expected BFS to reject an out-of-bounds start")


def test_timing_config_can_be_expressed_in_seconds() -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig(
        fps=24,
        event_duration_seconds=0.05,
        initial_hold_seconds=0.10,
        final_hold_seconds=0.20,
        failure_hold_seconds=0.30,
    )
    timeline = TimelineBuilder(timing=timing).build(events)

    assert timeline.fps == 24
    assert timeline.duration_seconds > 0.0
    assert timeline.frame_count >= 2


def test_cli_can_select_different_export_profiles() -> None:
    assert main(["--algorithm", "bfs", "--scenario", "maze_demo", "--export-profile", "shorts_vertical"]) == 0
    assert main(["--algorithm", "bfs", "--scenario", "maze_demo", "--export-profile", "hd_landscape", "--layout-profile", "standard_landscape"]) == 0


def test_cli_grid_size_overrides_are_respected() -> None:
    assert main([
        "--algorithm",
        "bfs",
        "--scenario",
        "open_demo",
        "--export-profile",
        "shorts_vertical",
        "--grid-cols",
        "16",
        "--grid-rows",
        "24",
    ]) == 0


def test_exporter_renders_numbered_frame_sequence(tmp_path: Path) -> None:
    scenario = get_scenario("no_path_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig(
        fps=30,
        event_duration_seconds=1.0 / 30.0,
        initial_hold_seconds=2.0 / 30.0,
        final_hold_seconds=8.0 / 30.0,
        failure_hold_seconds=10.0 / 30.0,
    )
    timeline = TimelineBuilder(timing=timing).build(events)

    exporter = OfflineExporter(
        render_config=RenderConfig(cell_size=20, margin=6),
        export_config=ExportConfig(
            export_profile=get_export_profile("shorts_vertical"),
            layout_profile=get_layout_profile("shorts_vertical"),
            timing=timing,
            output_dir=tmp_path / "output",
            temp_frames_dir=tmp_path / "output" / "frames" / "demo_run",
            keep_temp_frames=True,
            audio_enabled=False,
        ),
    )
    frame_dir = exporter.render_frame_sequence(
        grid=scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        timeline=timeline,
        frame_dir=tmp_path / "output" / "frames" / "demo_run",
        run_name="demo_run",
    )

    frame_files = sorted(frame_dir.glob("frame_*.png"))
    assert len(frame_files) == timeline.frame_count
    assert frame_files[0].name == "frame_000001.png"
    assert frame_files[-1].name == f"frame_{timeline.frame_count:06d}.png"

    with Image.open(frame_files[0]) as first_frame:
        assert first_frame.size == (1080, 1920)


def test_wav_is_deleted_after_successful_export(tmp_path: Path) -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig()
    expected_wav_path = tmp_path / "output" / "videos" / "cleanup_success.wav"

    exporter = OfflineExporter(
        export_config=ExportConfig(
            export_profile=get_export_profile("shorts_vertical"),
            layout_profile=get_layout_profile("shorts_vertical"),
            timing=timing,
            output_dir=tmp_path / "output",
            keep_temp_frames=True,
            audio_enabled=True,
        ),
    )
    result = exporter.export(
        grid=scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        events=events,
        run_name="cleanup_success",
    )

    assert result.video_path.exists()
    assert result.wav_path is None
    assert not expected_wav_path.exists()


def test_frame_dir_is_deleted_after_successful_export(tmp_path: Path) -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig()
    expected_frame_dir = tmp_path / "output" / "frames" / "cleanup_frames_success"

    exporter = OfflineExporter(
        export_config=ExportConfig(
            export_profile=get_export_profile("shorts_vertical"),
            layout_profile=get_layout_profile("shorts_vertical"),
            timing=timing,
            output_dir=tmp_path / "output",
            keep_temp_frames=False,
            audio_enabled=False,
        ),
    )
    result = exporter.export(
        grid=scenario.grid,
        start=scenario.start,
        goal=scenario.goal,
        events=events,
        run_name="cleanup_frames_success",
    )

    assert result.video_path.exists()
    assert not expected_frame_dir.exists()


def test_wav_is_preserved_when_mux_fails(tmp_path: Path) -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig()

    exporter = OfflineExporter(
        export_config=ExportConfig(
            export_profile=get_export_profile("shorts_vertical"),
            layout_profile=get_layout_profile("shorts_vertical"),
            timing=timing,
            output_dir=tmp_path / "output",
            keep_temp_frames=True,
            audio_enabled=True,
        ),
    )

    original_mux = exporter._mux_video

    def failing_mux(*, frame_dir: Path, video_path: Path, wav_path: Path | None) -> None:
        raise RuntimeError("forced mux failure")

    exporter._mux_video = failing_mux  # type: ignore[method-assign]
    try:
        try:
            exporter.export(
                grid=scenario.grid,
                start=scenario.start,
                goal=scenario.goal,
                events=events,
                run_name="cleanup_failure",
            )
        except RuntimeError as exc:
            assert "forced mux failure" in str(exc)
        else:
            raise AssertionError("Expected forced mux failure during export")

        wav_path = tmp_path / "output" / "videos" / "cleanup_failure.wav"
        assert wav_path.exists()
    finally:
        exporter._mux_video = original_mux  # type: ignore[method-assign]


def test_frame_dir_is_preserved_when_mux_fails(tmp_path: Path) -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timing = TimingConfig()
    expected_frame_dir = tmp_path / "output" / "frames" / "cleanup_frames_failure"

    exporter = OfflineExporter(
        export_config=ExportConfig(
            export_profile=get_export_profile("shorts_vertical"),
            layout_profile=get_layout_profile("shorts_vertical"),
            timing=timing,
            output_dir=tmp_path / "output",
            keep_temp_frames=False,
            audio_enabled=False,
        ),
    )

    original_mux = exporter._mux_video

    def failing_mux(*, frame_dir: Path, video_path: Path, wav_path: Path | None) -> None:
        raise RuntimeError("forced mux failure")

    exporter._mux_video = failing_mux  # type: ignore[method-assign]
    try:
        try:
            exporter.export(
                grid=scenario.grid,
                start=scenario.start,
                goal=scenario.goal,
                events=events,
                run_name="cleanup_frames_failure",
            )
        except RuntimeError as exc:
            assert "forced mux failure" in str(exc)
        else:
            raise AssertionError("Expected forced mux failure during export")

        assert expected_frame_dir.exists()
    finally:
        exporter._mux_video = original_mux  # type: ignore[method-assign]


def test_audio_timeline_generates_short_wav(tmp_path: Path) -> None:
    scenario = get_scenario("open_demo")
    events = ALGORITHMS["bfs"](scenario.grid, scenario.start, scenario.goal)
    timeline = TimelineBuilder(timing=TimingConfig()).build(events)

    output_path = tmp_path / "smoke_audio.wav"
    AudioSynthesizer(sample_rate=22_050).render_timeline_to_wav(
        timeline.audio_cues,
        timeline.duration_seconds,
        output_path,
    )

    assert output_path.exists()
    with wave.open(str(output_path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 22_050
        assert wav_file.getnframes() > 0
