from __future__ import annotations

from dataclasses import dataclass

from core.profiles import LayoutProfile

Bounds = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    canvas_size: tuple[int, int]
    grid_box: Bounds
    title_box: Bounds | None = None
    footer_box: Bounds | None = None
    hud_box: Bounds | None = None


@dataclass(frozen=True, slots=True)
class RenderPlan:
    width: int
    height: int
    layout_name: str
    grid_box: Bounds
    title_box: Bounds | None = None
    footer_box: Bounds | None = None
    hud_box: Bounds | None = None
    title_text: str | None = None
    footer_text: str | None = None
    show_hud: bool = False


def resolve_layout(profile: LayoutProfile, width: int, height: int) -> ResolvedLayout:
    padding = int(min(width, height) * profile.outer_padding_ratio)
    title_height = int(height * profile.title_height_ratio) if profile.show_title else 0
    footer_height = int(height * profile.footer_height_ratio) if profile.show_footer else 0
    hud_width = int(width * profile.hud_width_ratio) if profile.show_hud else 0

    title_box = (padding, padding, width - padding, padding + title_height) if title_height > 0 else None
    footer_box = (
        padding,
        height - padding - footer_height,
        width - padding,
        height - padding,
    ) if footer_height > 0 else None
    hud_box = (
        width - padding - hud_width,
        padding + title_height,
        width - padding,
        height - padding - footer_height,
    ) if hud_width > 0 else None

    grid_left = padding
    grid_top = padding + title_height
    grid_right = width - padding - hud_width
    grid_bottom = height - padding - footer_height

    return ResolvedLayout(
        canvas_size=(width, height),
        grid_box=(grid_left, grid_top, grid_right, grid_bottom),
        title_box=title_box,
        footer_box=footer_box,
        hud_box=hud_box,
    )


def build_render_plan(
    *,
    width: int,
    height: int,
    layout_profile: LayoutProfile,
    title_text: str | None = None,
    footer_text: str | None = None,
) -> RenderPlan:
    resolved = resolve_layout(layout_profile, width, height)
    return RenderPlan(
        width=width,
        height=height,
        layout_name=layout_profile.name,
        grid_box=resolved.grid_box,
        title_box=resolved.title_box,
        footer_box=resolved.footer_box,
        hud_box=resolved.hud_box,
        title_text=title_text,
        footer_text=footer_text,
        show_hud=layout_profile.show_hud,
    )
