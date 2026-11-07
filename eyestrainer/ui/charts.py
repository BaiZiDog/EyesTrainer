from __future__ import annotations

from collections.abc import Sequence

import pygame

from ..core.metrics import histogram
from ..core.stats import median
from .theme import Theme


def _fmt(value: float, unit: str = "") -> str:
    if abs(value) >= 100:
        text = f"{value:.0f}"
    elif abs(value) >= 10:
        text = f"{value:.1f}"
    else:
        text = f"{value:.2f}"
    return text + unit


def draw_line_chart(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    values: Sequence[float],
    *,
    title: str = "",
    unit: str = "",
    x_labels: Sequence[str] | None = None,
    reference: float | None = None,
    reference_label: str = "最佳",
) -> None:
    theme.panel_rect(surface, rect)
    inner = rect.inflate(-int(110 * theme.ui), -int(96 * theme.ui))
    if title:
        theme.text(
            surface,
            title,
            (rect.left + int(16 * theme.ui), rect.top + int(12 * theme.ui)),
            size=17,
            color=theme.text_color,
            bold=True,
        )
    if not values:
        theme.text(surface, "暂无数据", inner.center, size=16, color=theme.muted, anchor="center")
        return
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-9:
        pad = max(1.0, abs(hi) * 0.05)
        lo -= pad
        hi += pad
    else:
        pad = (hi - lo) * 0.08
        lo -= pad
        hi += pad
    grid_color = theme.border
    for i in range(5):
        y = int(inner.bottom - (inner.height * i / 4))
        pygame.draw.line(
            surface, grid_color, (inner.left, y), (inner.right, y), 1
        )
        theme.text(
            surface,
            _fmt(lo + (hi - lo) * i / 4, unit),
            (inner.left - int(8 * theme.ui), y),
            size=12,
            color=theme.muted,
            anchor="midright",
        )
    n = len(values)
    points: list[tuple[int, int]] = []
    for i, value in enumerate(values):
        x = inner.left if n == 1 else int(inner.left + inner.width * i / (n - 1))
        y = int(inner.bottom - (value - lo) / (hi - lo) * inner.height)
        points.append((x, y))
    if reference is not None:
        ref_y = int(inner.bottom - (reference - lo) / (hi - lo) * inner.height)
        pygame.draw.line(
            surface,
            theme.warning,
            (inner.left, ref_y),
            (inner.right, ref_y),
            max(1, int(theme.ui)),
        )
        theme.text(
            surface,
            reference_label,
            (inner.left + int(6 * theme.ui), ref_y - int(4 * theme.ui)),
            size=12,
            color=theme.warning,
            anchor="bottomleft",
        )
    if len(points) > 1:
        pygame.draw.lines(surface, theme.accent, False, points, max(2, int(2 * theme.ui)))
    for x, y in points:
        pygame.draw.circle(surface, theme.accent, (x, y), max(3, int(4 * theme.ui)))
    if x_labels:
        available = min(len(x_labels), n)
        step = max(1, available // 6)
        for i in range(0, available, step):
            x = points[i][0]
            theme.text(
                surface,
                x_labels[i],
                (x, inner.bottom + int(8 * theme.ui)),
                size=12,
                color=theme.muted,
                anchor="midtop",
            )


def draw_histogram(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    values: Sequence[float],
    *,
    title: str = "",
    unit: str = "",
    bins: int = 20,
) -> None:
    theme.panel_rect(surface, rect)
    inner = rect.inflate(-int(56 * theme.ui), -int(72 * theme.ui))
    if title:
        theme.text(
            surface,
            title,
            (rect.left + int(16 * theme.ui), rect.top + int(12 * theme.ui)),
            size=17,
            color=theme.text_color,
            bold=True,
        )
    bins_data = histogram(values, bins)
    if not bins_data:
        theme.text(surface, "暂无数据", inner.center, size=16, color=theme.muted, anchor="center")
        return
    max_count = max(count for _, _, count in bins_data) or 1
    bar_gap = max(1, int(2 * theme.ui))
    bar_width = max(2, inner.width // len(bins_data) - bar_gap)
    for i, (lo, hi, count) in enumerate(bins_data):
        height = int(inner.height * count / max_count)
        bar = pygame.Rect(
            inner.left + i * (inner.width / len(bins_data)),
            inner.bottom - height,
            bar_width,
            height,
        )
        pygame.draw.rect(surface, theme.accent, bar, border_radius=2)
    med = median(values)
    if med is not None:
        lo, hi, _ = bins_data[0][0], bins_data[-1][1], 0
        if hi - lo < 1e-9:
            x = inner.centerx
        else:
            x = int(inner.left + (med - lo) / (hi - lo) * inner.width)
        pygame.draw.line(
            surface,
            theme.warning,
            (x, inner.top),
            (x, inner.bottom),
            max(1, int(2 * theme.ui)),
        )
        theme.text(
            surface,
            f"中位数 {_fmt(med, unit)}",
            (inner.right, rect.top + int(12 * theme.ui)),
            size=12,
            color=theme.warning,
            anchor="topright",
        )
    theme.text(
        surface,
        _fmt(bins_data[0][0], unit),
        (inner.left, inner.bottom + int(10 * theme.ui)),
        size=12,
        color=theme.muted,
        anchor="midtop",
    )
    theme.text(
        surface,
        _fmt(bins_data[-1][1], unit),
        (inner.right, inner.bottom + int(10 * theme.ui)),
        size=12,
        color=theme.muted,
        anchor="midtop",
    )
