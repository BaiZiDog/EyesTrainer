from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..ui.widgets import Button
from .base import Scene

if TYPE_CHECKING:
    from ..app import App


class MenuScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self.buttons: dict[str, Button] = {}

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()
        self._layout()
        self._total_minutes = self.app.storage.total_training_seconds() / 60.0

    def _layout(self) -> None:
        theme = self.app.theme
        width = int(360 * theme.ui)
        height = int(52 * theme.ui)
        gap = int(12 * theme.ui)
        x = int(theme.width * 0.56) - width // 2
        y = int(theme.height * 0.38)
        items = [
            ("start", "开始训练", "primary"),
            ("history", "历史记录", "secondary"),
            ("settings", "设置", "secondary"),
            ("calibration", "校准", "secondary"),
            ("quit", "退出", "secondary"),
        ]
        self.buttons = {}
        for key, label, kind in items:
            self.buttons[key] = Button(
                pygame.Rect(x, y, width, height), label, kind=kind
            )
            y += height + gap

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.app.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.buttons.get("start") and self.buttons["start"].hit(pos):
                    self.app.audio.play("click")
                    from .module_select import ModuleSelectScene

                    self.app.switch_scene(ModuleSelectScene(self.app))
                elif self.buttons.get("history") and self.buttons["history"].hit(pos):
                    self.app.audio.play("click")
                    from .history import HistoryScene

                    self.app.switch_scene(HistoryScene(self.app))
                elif self.buttons.get("settings") and self.buttons["settings"].hit(pos):
                    self.app.audio.play("click")
                    from .settings import SettingsScene

                    self.app.switch_scene(SettingsScene(self.app))
                elif (
                    self.buttons.get("calibration")
                    and self.buttons["calibration"].hit(pos)
                ):
                    self.app.audio.play("click")
                    from .calibration import CalibrationScene

                    self.app.switch_scene(CalibrationScene(self.app))
                elif self.buttons.get("quit") and self.buttons["quit"].hit(pos):
                    self.app.running = False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != getattr(self, "_display_gen", -1):
            self._display_gen = self.app.display_generation
            self._layout()
        surface.fill(theme.bg)

        # Decorative arena grid on the right; no motion, purely visual.
        arena = pygame.Rect(
            int(theme.width * 0.66),
            int(theme.height * 0.20),
            int(theme.width * 0.28),
            int(theme.height * 0.28),
        )
        theme.panel_rect(surface, arena, radius=int(14 * theme.ui), color=theme.bg)
        step = max(24, int(48 * theme.ui))
        for gx in range(arena.left, arena.right, step):
            pygame.draw.line(
                surface, theme.border, (gx, arena.top), (gx, arena.bottom), 1
            )
        for gy in range(arena.top, arena.bottom, step):
            pygame.draw.line(
                surface, theme.border, (arena.left, gy), (arena.right, gy), 1
            )
        pygame.draw.circle(
            surface,
            theme.target,
            (arena.centerx, arena.centery),
            int(30 * theme.ui),
        )
        cx, cy = arena.centerx, arena.centery
        gap = int(10 * theme.ui)
        length = int(18 * theme.ui)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(
                surface,
                theme.accent,
                (cx + dx * gap, cy + dy * gap),
                (cx + dx * (gap + length), cy + dy * (gap + length)),
                max(1, int(2 * theme.ui)),
            )
        pygame.draw.circle(surface, theme.accent, (cx, cy), max(1, int(2 * theme.ui)))

        theme.text(
            surface,
            "EyesTrainer",
            (int(theme.width * 0.10), int(theme.height * 0.28)),
            size=58,
            color=theme.text_color,
            bold=True,
        )
        theme.text(
            surface,
            "FPS 视觉与反应训练",
            (int(theme.width * 0.10), int(theme.height * 0.28 + 74 * theme.ui)),
            size=24,
            color=theme.accent,
        )
        theme.text(
            surface,
            "数据优先 · 相对鼠标瞄准 · 本地离线",
            (int(theme.width * 0.10), int(theme.height * 0.28 + 112 * theme.ui)),
            size=17,
            color=theme.muted,
        )

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)

        total_minutes = getattr(self, "_total_minutes", 0.0)
        theme.text(
            surface,
            f"档案 {self.app.settings.profile}   ·   累计训练 {total_minutes:.0f} 分钟",
            (int(theme.width * 0.10), theme.height - int(58 * theme.ui)),
            size=15,
            color=theme.muted,
        )
        theme.text(
            surface,
            "v0.5.0   ·   F3 帧率信息",
            (int(theme.width * 0.10), theme.height - int(34 * theme.ui)),
            size=13,
            color=theme.muted,
        )
