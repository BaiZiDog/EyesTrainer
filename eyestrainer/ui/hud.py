from __future__ import annotations

import pygame

from ..core.geometry import RectTuple
from .theme import Color, Theme


def draw_crosshair(
    surface: pygame.Surface,
    theme: Theme,
    pos: tuple[float, float],
    style: str,
    color: Color,
    size: float,
) -> None:
    cx, cy = int(pos[0]), int(pos[1])
    s = max(4, int(size * theme.ui))
    gap = max(2, int(s * 0.35))
    width = max(1, int(1.5 * theme.ui))
    if style in ("cross", "cross_dot"):
        pygame.draw.line(surface, color, (cx - gap - s, cy), (cx - gap, cy), width)
        pygame.draw.line(surface, color, (cx + gap, cy), (cx + gap + s, cy), width)
        pygame.draw.line(surface, color, (cx, cy - gap - s), (cx, cy - gap), width)
        pygame.draw.line(surface, color, (cx, cy + gap), (cx, cy + gap + s), width)
    if style == "dot":
        pygame.draw.circle(surface, color, (cx, cy), max(2, int(s * 0.2)))
    elif style == "cross_dot":
        pygame.draw.circle(surface, color, (cx, cy), max(1, int(1.5 * theme.ui)))


def draw_hud(
    surface: pygame.Surface,
    theme: Theme,
    time_left: float,
    level: float | None,
    *,
    show_level: bool = True,
) -> None:
    left = max(0.0, time_left)
    minutes = int(left // 60)
    seconds = int(left % 60)
    text = f"{minutes}:{seconds:02d}" if minutes else f"{left:.1f}s"
    theme.text(
        surface,
        text,
        (theme.width / 2, 18 * theme.ui),
        size=30,
        color=theme.text_color,
        bold=True,
        anchor="midtop",
    )
    if show_level and level is not None:
        theme.text(
            surface,
            f"等级 {level:.0f}",
            (theme.width - 28 * theme.ui, 20 * theme.ui),
            size=18,
            color=theme.muted,
            anchor="topright",
        )


def draw_countdown(
    surface: pygame.Surface,
    theme: Theme,
    number: int,
    arena: RectTuple,
) -> None:
    overlay = pygame.Surface((int(arena[2]), int(arena[3])), pygame.SRCALPHA)
    overlay.fill((*theme.overlay, 190))
    surface.blit(overlay, (int(arena[0]), int(arena[1])))
    theme.text(
        surface,
        str(max(1, number)),
        (arena[0] + arena[2] / 2, arena[1] + arena[3] / 2),
        size=96,
        color=theme.accent,
        bold=True,
        anchor="center",
    )


def draw_dim(
    surface: pygame.Surface, theme: Theme, alpha: int = 190
) -> None:
    overlay = pygame.Surface((theme.width, theme.height), pygame.SRCALPHA)
    overlay.fill((*theme.overlay, alpha))
    surface.blit(overlay, (0, 0))


def draw_debug(
    surface: pygame.Surface,
    theme: Theme,
    fps: float,
    avg_ms: float,
    p99_ms: float,
    long_frames: int,
) -> None:
    lines = [
        f"FPS {fps:.0f}",
        f"frame {avg_ms:.1f}ms  p99 {p99_ms:.1f}ms",
        f"long {long_frames}",
    ]
    x = int(16 * theme.ui)
    y = theme.height - int(80 * theme.ui)
    for i, line in enumerate(lines):
        theme.text(
            surface,
            line,
            (x, y + i * int(20 * theme.ui)),
            size=14,
            color=theme.muted,
        )
