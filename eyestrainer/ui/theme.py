from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from ..core.font import FontBook
from ..core.geometry import RectTuple

Color = tuple[int, int, int]


def parse_color(value: str, fallback: Color = (57, 255, 136)) -> Color:
    raw = value.lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return fallback


@dataclass
class Theme:
    width: int
    height: int
    fonts: FontBook
    ui: float = 1.0
    bg: Color = (11, 14, 20)
    panel: Color = (18, 23, 34)
    panel_alt: Color = (22, 28, 41)
    border: Color = (30, 39, 53)
    text_color: Color = (230, 237, 243)
    muted: Color = (139, 152, 169)
    accent: Color = (57, 255, 136)
    target: Color = (255, 79, 109)
    target_edge: Color = (150, 38, 58)
    warning: Color = (255, 200, 87)
    white: Color = (255, 255, 255)
    overlay: Color = (5, 7, 11)
    _arena_cache: dict[tuple[int, int], pygame.Surface] = field(
        default_factory=dict, init=False, repr=False
    )

    def font(self, size: float, bold: bool = False) -> pygame.font.Font:
        return self.fonts.get(int(round(size * self.ui)), bold)

    def text(
        self,
        surface: pygame.Surface,
        text: str,
        pos: tuple[float, float],
        size: float = 20,
        color: Color | None = None,
        bold: bool = False,
        anchor: str = "topleft",
    ) -> pygame.Rect:
        font = self.font(size, bold=bold)
        rendered = font.render(str(text), True, color or self.text_color)
        rect = rendered.get_rect()
        setattr(rect, anchor, (int(pos[0]), int(pos[1])))
        surface.blit(rendered, rect)
        return rect

    def panel_rect(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        radius: int | None = None,
        color: Color | None = None,
        border: bool = True,
    ) -> None:
        radius = int(10 * self.ui) if radius is None else radius
        pygame.draw.rect(surface, color or self.panel, rect, border_radius=radius)
        if border:
            pygame.draw.rect(
                surface, self.border, rect, width=max(1, int(self.ui)), border_radius=radius
            )

    def draw_arena(self, surface: pygame.Surface, arena: RectTuple) -> None:
        x, y, w, h = (int(v) for v in arena)
        key = (w, h)
        cached = self._arena_cache.get(key)
        if cached is None:
            cached = pygame.Surface((w, h))
            cached.fill(self.bg)
            step = max(48, int(90 * self.ui))
            grid_color = tuple(
                int(self.bg[i] * 0.65 + self.border[i] * 0.35) for i in range(3)
            )
            for gx in range(0, w, step):
                pygame.draw.line(cached, grid_color, (gx, 0), (gx, h), 1)
            for gy in range(0, h, step):
                pygame.draw.line(cached, grid_color, (0, gy), (w, gy), 1)
            pygame.draw.rect(
                cached,
                self.border,
                pygame.Rect(0, 0, w, h),
                width=max(1, int(2 * self.ui)),
            )
            self._arena_cache[key] = cached
        surface.blit(cached, (x, y))


def make_theme(width: int, height: int, fonts: FontBook) -> Theme:
    ui = max(0.75, min(1.5, height / 1080.0))
    return Theme(width=width, height=height, fonts=fonts, ui=ui)
