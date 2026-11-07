from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from .theme import Theme


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    kind: str = "secondary"
    selected: bool = False
    enabled: bool = True

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)

    def draw(
        self, surface: pygame.Surface, theme: Theme, mouse_pos: tuple[int, int] | None = None
    ) -> None:
        hovered = self.enabled and mouse_pos is not None and self.rect.collidepoint(mouse_pos)
        if not self.enabled:
            bg = theme.panel
            fg = theme.muted
        elif self.selected:
            bg = theme.accent
            fg = theme.bg
        elif self.kind == "primary":
            bg = theme.accent if hovered else (42, 190, 106)
            fg = theme.bg
        elif hovered:
            bg = theme.panel_alt
            fg = theme.text_color
        else:
            bg = theme.panel
            fg = theme.text_color
        pygame.draw.rect(
            surface, bg, self.rect, border_radius=max(6, int(9 * theme.ui))
        )
        if not self.selected:
            pygame.draw.rect(
                surface,
                theme.border,
                self.rect,
                width=max(1, int(theme.ui)),
                border_radius=max(6, int(9 * theme.ui)),
            )
        theme.text(
            surface,
            self.label,
            self.rect.center,
            size=20,
            color=fg,
            bold=self.kind == "primary" or self.selected,
            anchor="center",
        )


class Slider:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        *,
        step: float = 0.0,
        formatter: Callable[[float], str] | None = None,
    ) -> None:
        self.rect = rect
        self.label = label
        self.minimum = minimum
        self.maximum = maximum
        self.value = value
        self.step = step
        self.formatter = formatter or (lambda v: f"{v:.1f}")
        self.dragging = False

    def _to_x(self, value: float) -> int:
        span = self.maximum - self.minimum
        ratio = 0.0 if span <= 0 else (value - self.minimum) / span
        return int(self.rect.left + ratio * self.rect.width)

    def _set_from_x(self, x: int) -> bool:
        ratio = (x - self.rect.left) / max(1, self.rect.width)
        value = self.minimum + max(0.0, min(1.0, ratio)) * (
            self.maximum - self.minimum
        )
        if self.step > 0:
            value = round(value / self.step) * self.step
        value = max(self.minimum, min(self.maximum, value))
        changed = abs(value - self.value) > 1e-9
        self.value = value
        return changed

    def handle_event(self, event: pygame.event.Event) -> bool:
        hit_rect = self.rect.inflate(0, int(self.rect.height * 1.5))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hit_rect.collidepoint(event.pos):
                self.dragging = True
                return self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            return self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        return False

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        theme.text(
            surface,
            self.label,
            (self.rect.left, self.rect.top - int(26 * theme.ui)),
            size=16,
            color=theme.muted,
        )
        theme.text(
            surface,
            self.formatter(self.value),
            (self.rect.right, self.rect.top - int(26 * theme.ui)),
            size=16,
            color=theme.text_color,
            anchor="topright",
        )
        pygame.draw.rect(
            surface,
            theme.border,
            self.rect,
            border_radius=max(2, int(4 * theme.ui)),
        )
        fill_x = self._to_x(self.value)
        if fill_x > self.rect.left:
            fill_rect = pygame.Rect(
                self.rect.left,
                self.rect.top,
                fill_x - self.rect.left,
                self.rect.height,
            )
            pygame.draw.rect(
                surface,
                theme.accent,
                fill_rect,
                border_radius=max(2, int(4 * theme.ui)),
            )
        knob_radius = max(5, int(8 * theme.ui))
        pygame.draw.circle(
            surface, theme.text_color, (fill_x, self.rect.centery), knob_radius
        )


def wrap_text(
    font: pygame.font.Font, text: str, max_width: int
) -> list[str]:
    words = text.split(" ")
    if len(words) == 1:
        return _wrap_cjk(font, text, max_width)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap_cjk(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_paragraph(
    surface: pygame.Surface,
    theme: Theme,
    text: str,
    pos: tuple[int, int],
    max_width: int,
    size: float = 18,
    color: tuple[int, int, int] | None = None,
    line_gap: int | None = None,
) -> int:
    font = theme.font(size)
    lines = wrap_text(font, text, max_width)
    line_gap = line_gap if line_gap is not None else int(8 * theme.ui)
    x, y = pos
    for line in lines:
        surface.blit(font.render(line, True, color or theme.muted), (x, y))
        y += font.get_height() + line_gap
    return y


def draw_card(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    label: str,
    value: str,
    sub: str = "",
) -> None:
    theme.panel_rect(surface, rect)
    theme.text(
        surface,
        label,
        (rect.left + int(16 * theme.ui), rect.top + int(12 * theme.ui)),
        size=15,
        color=theme.muted,
    )
    theme.text(
        surface,
        value,
        (rect.left + int(16 * theme.ui), rect.top + int(34 * theme.ui)),
        size=30,
        color=theme.text_color,
        bold=True,
    )
    if sub:
        theme.text(
            surface,
            sub,
            (rect.left + int(16 * theme.ui), rect.bottom - int(24 * theme.ui)),
            size=14,
            color=theme.muted,
        )
