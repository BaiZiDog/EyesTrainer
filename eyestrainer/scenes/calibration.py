from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ..core import geometry
from ..core.timing import summarize_frames
from ..ui.widgets import Button, Slider
from .base import Scene

if TYPE_CHECKING:
    from ..app import App


class CalibrationScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self.buttons: dict[str, Button] = {}
        self.sliders: dict[str, Slider] = {}
        self.test_running = False
        self.test_elapsed = 0.0
        self.test_duration = 5.0
        self.samples: list[float] = []
        self.result: dict[str, float] | None = None
        self._layout()

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()
        self._layout()

    def on_exit(self) -> None:
        self.app.save_settings()

    def _layout(self) -> None:
        theme = self.app.theme
        self.buttons = {
            "back": Button(
                pygame.Rect(int(30 * theme.ui), int(30 * theme.ui), int(120 * theme.ui), int(42 * theme.ui)),
                "返回",
            ),
            "test": Button(
                pygame.Rect(int(60 * theme.ui), int(430 * theme.ui), int(260 * theme.ui), int(48 * theme.ui)),
                "重新自检" if self.result else "开始 5 秒性能自检",
                kind="primary",
            ),
        }
        cal = self.app.settings.calibration
        self.sliders = {
            "diagonal": Slider(
                pygame.Rect(
                    int(theme.width * 0.55),
                    int(260 * theme.ui),
                    int(360 * theme.ui),
                    int(8 * theme.ui),
                ),
                "屏幕对角线（英寸）",
                10.0,
                80.0,
                cal.screen_diagonal_in,
                step=0.5,
                formatter=lambda v: f"{v:.1f} in",
            ),
            "distance": Slider(
                pygame.Rect(
                    int(theme.width * 0.55),
                    int(360 * theme.ui),
                    int(360 * theme.ui),
                    int(8 * theme.ui),
                ),
                "观看距离（厘米）",
                20.0,
                200.0,
                cal.view_distance_cm,
                step=5.0,
                formatter=lambda v: f"{v:.0f} cm",
            ),
        }

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._go_back()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.buttons["back"].hit(event.pos):
                    self._go_back()
                    return
                if self.buttons["test"].hit(event.pos) and not self.test_running:
                    self.test_running = True
                    self.test_elapsed = 0.0
                    self.samples = []
                    self.result = None
                    self.app.audio.play("click")
                    return
            for key, slider in self.sliders.items():
                if slider.handle_event(event):
                    self._apply_slider(key, slider.value)

    def _apply_slider(self, key: str, value: float) -> None:
        cal = self.app.settings.calibration
        if key == "diagonal":
            cal.screen_diagonal_in = value
        elif key == "distance":
            cal.view_distance_cm = value

    def _go_back(self) -> None:
        self.app.save_settings()
        if len(self.app.scene_stack) > 1:
            self.app.pop_scene()
        else:
            from .menu import MenuScene

            self.app.switch_scene(MenuScene(self.app))

    def update(self, sim_dt: float, real_dt: float) -> None:
        if not self.test_running:
            return
        self.test_elapsed += max(0.0, real_dt)
        self.samples.append(max(0.0, real_dt))
        if self.test_elapsed >= self.test_duration:
            self.test_running = False
            self.result = summarize_frames(self.samples)
            self.buttons["test"].label = "重新自检"

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != getattr(self, "_display_gen", -1):
            self._display_gen = self.app.display_generation
            self._layout()
        surface.fill(theme.bg)
        theme.text(
            surface,
            "校准",
            (theme.width // 2, int(38 * theme.ui)),
            size=36,
            color=theme.text_color,
            bold=True,
            anchor="midtop",
        )
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)
        for slider in self.sliders.values():
            slider.draw(surface, theme)

        left = int(60 * theme.ui)
        top = int(150 * theme.ui)
        rates = []
        try:
            raw = pygame.display.get_desktop_refresh_rates()
            if isinstance(raw, dict):
                for item in raw.values():
                    if isinstance(item, (list, tuple)):
                        rates.extend(item)
                    else:
                        rates.append(item)
            else:
                rates = list(raw)
        except Exception:
            rates = []
        rate_text = ", ".join(str(int(v)) for v in rates) if rates else "未知"
        lines = [
            f"当前分辨率：{theme.width} × {theme.height}",
            f"当前刷新率：{self.app.refresh_rate} Hz",
            f"桌面刷新率列表：{rate_text}",
            f"垂直同步：{'开' if self.app.settings.display.vsync else '关'}",
            f"帧上限：{'跟随刷新率' if self.app.settings.display.fps_cap == 0 else self.app.settings.display.fps_cap}",
            "性能自检只测量主循环帧时，不代表显示器到眼睛的完整延迟。",
        ]
        for i, line in enumerate(lines):
            theme.text(
                surface,
                line,
                (left, top + i * int(28 * theme.ui)),
                size=16,
                color=theme.muted,
            )

        if self.test_running:
            progress = min(1.0, self.test_elapsed / self.test_duration)
            bar = pygame.Rect(left, int(500 * theme.ui), int(500 * theme.ui), int(10 * theme.ui))
            pygame.draw.rect(surface, theme.border, bar, border_radius=4)
            pygame.draw.rect(
                surface,
                theme.accent,
                pygame.Rect(bar.left, bar.top, int(bar.width * progress), bar.height),
                border_radius=4,
            )
            theme.text(
                surface,
                f"自检中… {self.test_elapsed:.1f}s",
                (left, bar.bottom + int(12 * theme.ui)),
                size=15,
                color=theme.text_color,
            )
        elif self.result:
            fps = self.result["fps"]
            p99 = self.result["p99_ms"]
            avg = self.result["avg_ms"]
            max_ms = self.result["max_ms"]
            good = fps >= self.app.refresh_rate * 0.9
            theme.text(
                surface,
                f"平均 {fps:.0f} FPS　平均帧时 {avg:.1f}ms　p99 {p99:.1f}ms　最大 {max_ms:.1f}ms",
                (left, int(500 * theme.ui)),
                size=17,
                color=theme.accent if good else theme.warning,
            )
            theme.text(
                surface,
                "帧时稳定，适合训练" if good else "帧时偏低：建议关闭垂直同步、降低分辨率或关闭后台程序",
                (left, int(532 * theme.ui)),
                size=14,
                color=theme.muted,
            )

        cal = self.app.settings.calibration
        ppd = geometry.px_per_degree(
            theme.width,
            theme.height,
            cal.screen_diagonal_in,
            cal.view_distance_cm,
        )
        theme.text(
            surface,
            "视觉角度换算",
            (int(theme.width * 0.55), int(150 * theme.ui)),
            size=20,
            color=theme.text_color,
            bold=True,
        )
        theme.text(
            surface,
            f"约 {ppd:.1f} 像素 / 度",
            (int(theme.width * 0.55), int(180 * theme.ui)),
            size=17,
            color=theme.accent,
        )

        preview = pygame.Rect(
            int(theme.width * 0.55),
            int(410 * theme.ui),
            int(360 * theme.ui),
            int(180 * theme.ui),
        )
        theme.panel_rect(surface, preview)
        cx, cy = preview.center
        radius = max(3, int(ppd / 2))
        pygame.draw.circle(surface, theme.target, (cx, cy), radius, width=2)
        pygame.draw.line(
            surface, theme.accent, (cx - radius - 20, cy), (cx - radius - 6, cy), 1
        )
        theme.text(
            surface,
            "1°",
            (cx + radius + int(12 * theme.ui), cy),
            size=13,
            color=theme.muted,
            anchor="midleft",
        )
        theme.text(
            surface,
            "图中圆环约对应 1° 视角",
            (preview.centerx, preview.bottom - int(18 * theme.ui)),
            size=12,
            color=theme.muted,
            anchor="midbottom",
        )
