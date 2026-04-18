from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.config import RenderConfig
from core.events import EventKind, SearchEvent
from core.grid import Grid, Point
from core import theme
from core.profiles import get_layout_profile
from core.render_plan import RenderPlan, build_render_plan


class GridRenderer:
    """Render a logical pathfinding scene into any output resolution via a render plan."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()

    def render_frame(
        self,
        grid: Grid,
        *,
        start: Point | None = None,
        goal: Point | None = None,
        events: Iterable[SearchEvent] | None = None,
        render_plan: RenderPlan | None = None,
    ) -> Image.Image:
        if render_plan is None:
            preview_width = max(640, grid.width * self.config.cell_size + self.config.margin * 2)
            preview_height = max(640, grid.height * self.config.cell_size + self.config.margin * 2)
            render_plan = build_render_plan(
                width=preview_width,
                height=preview_height,
                layout_profile=get_layout_profile("shorts_vertical"),
            )

        image = Image.new("RGB", (render_plan.width, render_plan.height), theme.BACKGROUND)
        draw = ImageDraw.Draw(image)
        event_list = list(events or [])
        overlays = self._collect_event_overlays(event_list)
        path_points = {
            event.point
            for event in event_list
            if event.kind == EventKind.PATH and event.point is not None
        }
        no_path = any(
            event.kind == EventKind.NO_PATH
            or (event.kind == EventKind.FINISH and event.details.get("status") == "no_path")
            for event in event_list
        )

        self._draw_panel_backgrounds(draw, render_plan)
        origin_x, origin_y, cell_size, line_width = self._grid_metrics(grid, render_plan)

        for y in range(grid.height):
            for x in range(grid.width):
                point = (x, y)
                fill = theme.WALL if point in grid.walls else theme.OPEN_CELL
                if point in overlays:
                    fill = overlays[point]
                if start == point:
                    fill = theme.START
                if goal == point:
                    fill = theme.NO_PATH if no_path else theme.GOAL
                bounds = self._cell_bounds(point, origin_x=origin_x, origin_y=origin_y, cell_size=cell_size)
                draw.rectangle(
                    bounds,
                    fill=fill,
                    outline=theme.GRID_LINE,
                    width=line_width,
                )
                if point in path_points and start != point and goal != point and point not in grid.walls:
                    self._draw_path_highlight(draw, bounds, cell_size)

        if render_plan.title_box and render_plan.title_text:
            self._draw_text_in_box(draw, render_plan.title_box, render_plan.title_text)
        if render_plan.footer_box and render_plan.footer_text:
            self._draw_text_in_box(draw, render_plan.footer_box, render_plan.footer_text)
        if render_plan.show_hud and render_plan.hud_box:
            self._draw_text_in_box(draw, render_plan.hud_box, "HUD READY", center=True)
        if no_path:
            badge_box = render_plan.footer_box or render_plan.title_box
            if badge_box is not None:
                self._draw_text_in_box(draw, badge_box, "NO PATH", accent=True, center=True)

        return image

    def render_array(
        self,
        grid: Grid,
        *,
        start: Point | None = None,
        goal: Point | None = None,
        events: Iterable[SearchEvent] | None = None,
        render_plan: RenderPlan | None = None,
    ) -> np.ndarray:
        image = self.render_frame(grid, start=start, goal=goal, events=events, render_plan=render_plan)
        return np.asarray(image)

    def save_frame(self, image: Image.Image, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    def compute_cell_metrics(
        self,
        *,
        grid_cols: int,
        grid_rows: int,
        grid_box: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        left, top, right, bottom = grid_box
        viewport_width = max(1, right - left)
        viewport_height = max(1, bottom - top)
        cell_size = max(4, min(viewport_width // grid_cols, viewport_height // grid_rows))
        line_width = max(self.config.min_line_width, int(round(cell_size * self.config.grid_line_scale)))
        return viewport_width, viewport_height, cell_size, line_width

    def _grid_metrics(self, grid: Grid, render_plan: RenderPlan) -> tuple[int, int, int, int]:
        left, top, right, bottom = render_plan.grid_box
        viewport_width, viewport_height, cell_size, line_width = self.compute_cell_metrics(
            grid_cols=grid.width,
            grid_rows=grid.height,
            grid_box=render_plan.grid_box,
        )
        grid_width = grid.width * cell_size
        grid_height = grid.height * cell_size
        origin_x = left + (viewport_width - grid_width) // 2
        origin_y = top + (viewport_height - grid_height) // 2
        return origin_x, origin_y, cell_size, line_width

    @staticmethod
    def _cell_bounds(
        point: Point,
        *,
        origin_x: int,
        origin_y: int,
        cell_size: int,
    ) -> tuple[int, int, int, int]:
        x, y = point
        left = origin_x + x * cell_size
        top = origin_y + y * cell_size
        right = left + cell_size
        bottom = top + cell_size
        return left, top, right, bottom

    def _draw_panel_backgrounds(self, draw: ImageDraw.ImageDraw, render_plan: RenderPlan) -> None:
        stroke = max(1, int(min(render_plan.width, render_plan.height) * 0.0015))
        radius = max(6, stroke * 4)
        for box in (render_plan.title_box, render_plan.footer_box, render_plan.hud_box):
            if box is None:
                continue
            draw.rounded_rectangle(box, outline=theme.GRID_LINE, width=stroke, radius=radius)

    def _draw_path_highlight(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: tuple[int, int, int, int],
        cell_size: int,
    ) -> None:
        left, top, right, bottom = bounds
        inset = max(1, cell_size // 7)
        stroke = max(1, cell_size // 10)
        inner = (left + inset, top + inset, right - inset, bottom - inset)
        if inner[2] <= inner[0] or inner[3] <= inner[1]:
            return
        draw.rectangle(inner, fill=theme.PATH, outline=theme.PATH_BORDER, width=stroke)

    def _draw_text_in_box(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        *,
        accent: bool = False,
        center: bool = False,
    ) -> None:
        left, top, right, bottom = box
        fill = theme.NO_PATH if accent else theme.LABEL_BG
        stroke = max(1, int(min(right - left, bottom - top) * 0.04))
        radius = max(6, stroke * 3)
        draw.rounded_rectangle(box, fill=fill, outline=theme.GRID_LINE, width=stroke, radius=radius)
        font = self._font_for_box(box)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = left + int((bottom - top) * self.config.label_padding_scale)
        text_y = top + max(4, (bottom - top - text_height) // 2)
        if center:
            text_x = left + max(6, (right - left - text_width) // 2)
        draw.text((text_x, text_y), text, fill=theme.LABEL_TEXT, font=font)

    @staticmethod
    def _font_for_box(box: tuple[int, int, int, int]) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        _, top, _, bottom = box
        target_size = max(12, int((bottom - top) * 0.45))
        for candidate in ("arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(candidate, size=target_size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _collect_event_overlays(events: Iterable[SearchEvent]) -> dict[Point, tuple[int, int, int]]:
        overlays: dict[Point, tuple[int, int, int]] = {}
        for event in events:
            if event.point is None:
                continue
            if event.kind == EventKind.FRONTIER:
                overlays[event.point] = theme.FRONTIER
            elif event.kind == EventKind.EXPAND:
                overlays[event.point] = theme.EXPAND
            elif event.kind == EventKind.VISITED:
                overlays[event.point] = theme.VISITED
            elif event.kind == EventKind.PATH:
                overlays[event.point] = theme.PATH
            elif event.kind == EventKind.NO_PATH:
                overlays[event.point] = theme.NO_PATH
        return overlays
