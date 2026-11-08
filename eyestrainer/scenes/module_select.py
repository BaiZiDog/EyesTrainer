from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..core import metrics
from ..ui.widgets import Button, Slider, draw_paragraph
from .base import Scene
from .options import SessionOptions

if TYPE_CHECKING:
    from ..app import App


_DESCRIPTIONS = {
    ("flick", "chain"): "3 个目标同屏，点掉即刷新。训练甩枪、目标切换与点击精度。",
    ("flick", "reaction"): "单目标随机延迟出现，限时点击。训练发现目标后的反应与首动速度。",
    ("track", "waypoint"): "目标沿平滑航点移动。按住左键，尽量让准星覆盖目标。",
    ("track", "bounce"): "目标在场地内横向弹跳。训练跟枪与方向预判。",
    ("dva", "staircase"): "带缺口圆环横向高速移动，用方向键判断缺口朝向。训练高速运动细节辨识。",
    ("peripheral", "adaptive"): "注视中央十字，周边闪现实心目标与空心干扰项，按空格报告实心目标。",
}
_MODE_LABELS = {
    "chain": "连击",
    "reaction": "反应",
    "waypoint": "航点",
    "bounce": "弹跳",
    "staircase": "阶梯",
    "adaptive": "自适应",
}
_MODULE_CARDS = [
    ("flick", "甩枪反应"),
    ("track", "动态追踪"),
    ("dva", "动态视敏"),
    ("peripheral", "周边视野"),
]
_MODULE_MODES = {
    "flick": ["chain", "reaction"],
    "track": ["waypoint", "bounce"],
    "dva": ["staircase"],
    "peripheral": ["adaptive"],
}
_DEFAULT_MODES = {
    "flick": "chain",
    "track": "waypoint",
    "dva": "staircase",
    "peripheral": "adaptive",
}


class ModuleSelectScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        latest = app.storage.history(limit=1)
        module_id = "flick"
        mode = "chain"
        if latest:
            module_id = latest[0].get("module", module_id)
            mode = latest[0].get("mode", mode)
        if module_id not in _MODULE_MODES:
            module_id, mode = "flick", "chain"
        if mode not in _MODULE_MODES[module_id]:
            mode = _DEFAULT_MODES[module_id]
        self.options = SessionOptions(
            module_id=module_id,
            mode=mode,
            adaptive=app.settings.training.adaptive,
            fixed_level=50,
        )
        self.buttons: dict[str, Button] = {}
        self.fixed_slider = Slider(
            pygame.Rect(0, 0, 1, 1),
            app.tr("固定难度"),
            0,
            100,
            50,
            step=1,
            formatter=lambda v: f"{v:.0f}",
        )
        self.sensitivity = Slider(
            pygame.Rect(0, 0, 1, 1),
            app.tr("鼠标灵敏度"),
            0.1,
            5.0,
            app.settings.input.sensitivity,
            step=0.05,
            formatter=lambda v: f"{v:.2f}",
        )
        self._stats_lines: list[str] = []

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()
        self.sensitivity.value = self.app.settings.input.sensitivity
        self._layout()
        self._refresh_stats()

    def _layout(self) -> None:
        theme = self.app.theme
        self.buttons = {}
        cx = theme.width // 2
        gap = int(24 * theme.ui)
        margin = int(30 * theme.ui)
        card_w = min(
            int(260 * theme.ui),
            (theme.width - 2 * margin - 3 * gap) // 4,
        )
        card_h = int(140 * theme.ui)
        y = int(theme.height * 0.18)
        total_w = 4 * card_w + 3 * gap
        x = cx - total_w // 2
        for module_id, label in _MODULE_CARDS:
            self.buttons[module_id] = Button(
                pygame.Rect(x, y, card_w, card_h),
                theme.tr(label),
                selected=self.options.module_id == module_id,
            )
            x += card_w + gap
        mode_y = y + card_h + int(32 * theme.ui)
        mode_w = int(180 * theme.ui)
        modes = _MODULE_MODES[self.options.module_id]
        if len(modes) == 1:
            mode_x = cx - mode_w // 2
        else:
            mode_x = cx - mode_w - gap // 2
        for i, mode in enumerate(modes):
            self.buttons[f"mode:{mode}"] = Button(
                pygame.Rect(mode_x + i * (mode_w + gap), mode_y, mode_w, int(48 * theme.ui)),
                theme.tr(_MODE_LABELS[mode]),
                selected=self.options.mode == mode,
            )
        self.buttons["adaptive"] = Button(
            pygame.Rect(cx - int(200 * theme.ui), mode_y + int(72 * theme.ui), int(400 * theme.ui), int(46 * theme.ui)),
            theme.tr(
                "自适应难度：开" if self.options.adaptive else "自适应难度：关"
            ),
            selected=self.options.adaptive,
        )
        slider_y = mode_y + int(146 * theme.ui)
        self._show_sensitivity = self.options.module_id in ("flick", "track")
        if self._show_sensitivity:
            self.sensitivity.rect = pygame.Rect(
                cx - int(400 * theme.ui),
                slider_y,
                int(360 * theme.ui),
                int(8 * theme.ui),
            )
            self.sensitivity.value = self.app.settings.input.sensitivity
            self.fixed_slider.rect = pygame.Rect(
                cx + int(40 * theme.ui),
                slider_y,
                int(360 * theme.ui),
                int(8 * theme.ui),
            )
        else:
            self.sensitivity.rect = pygame.Rect(0, 0, 1, 1)
            self.fixed_slider.rect = pygame.Rect(
                cx - int(200 * theme.ui),
                slider_y,
                int(400 * theme.ui),
                int(8 * theme.ui),
            )
        self.fixed_slider.value = self.options.fixed_level
        self.buttons["start"] = Button(
            pygame.Rect(cx - int(180 * theme.ui), theme.height - int(150 * theme.ui), int(360 * theme.ui), int(56 * theme.ui)),
            theme.tr("开始训练"),
            kind="primary",
        )
        self.buttons["back"] = Button(
            pygame.Rect(int(30 * theme.ui), theme.height - int(78 * theme.ui), int(150 * theme.ui), int(44 * theme.ui)),
            theme.tr("返回"),
        )
        self.fixed_slider.label = theme.tr("固定难度")
        self.sensitivity.label = theme.tr("鼠标灵敏度")
        self._compact = theme.height < 650

    def _refresh_stats(self) -> None:
        history = self.app.storage.history(
            self.options.module_id, self.options.mode, limit=50
        )
        self._stats_lines = []
        if not history:
            self._stats_lines.append(self.app.tr("还没有该模式的训练记录"))
            return
        primary = metrics.primary_metric(self.options.module_id, self.options.mode, {})
        key = primary["key"]
        values = [float(s[key]) for s in history if s.get(key) is not None]
        last = history[0]
        last_value = last.get(key)
        if last_value is not None:
            unit = primary["unit"]
            self._stats_lines.append(
                self.app.tr("上次：{value}", value=f"{float(last_value):.1f}{unit}")
            )
        if values:
            best = max(values) if primary["higher_is_better"] else min(values)
            unit = primary["unit"]
            self._stats_lines.append(
                self.app.tr("最佳：{value}", value=f"{best:.1f}{unit}")
            )
        self._stats_lines.append(
            self.app.tr("共 {count} 次记录", count=len(history))
        )

    def _set_module(self, module_id: str) -> None:
        self.options.module_id = module_id
        self.options.mode = _DEFAULT_MODES[module_id]
        self._layout()
        self._refresh_stats()

    def _set_mode(self, mode: str) -> None:
        if mode not in _MODULE_MODES.get(self.options.module_id, []):
            return
        self.options.mode = mode
        self._layout()
        self._refresh_stats()

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.app.save_settings()
                from .menu import MenuScene

                self.app.switch_scene(MenuScene(self.app))
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.buttons["flick"].hit(pos):
                    self._set_module("flick")
                    self.app.audio.play("click")
                elif self.buttons["track"].hit(pos):
                    self._set_module("track")
                    self.app.audio.play("click")
                elif self.buttons["dva"].hit(pos):
                    self._set_module("dva")
                    self.app.audio.play("click")
                elif self.buttons["peripheral"].hit(pos):
                    self._set_module("peripheral")
                    self.app.audio.play("click")
                elif any(
                    key.startswith("mode:") and self.buttons[key].hit(pos)
                    for key in self.buttons
                ):
                    mode = next(
                        key.split(":", 1)[1]
                        for key in self.buttons
                        if key.startswith("mode:") and self.buttons[key].hit(pos)
                    )
                    self._set_mode(mode)
                    self.app.audio.play("click")
                elif self.buttons["adaptive"].hit(pos):
                    self.options.adaptive = not self.options.adaptive
                    self.buttons["adaptive"].selected = self.options.adaptive
                    self.buttons["adaptive"].label = self.app.tr(
                        "自适应难度：开" if self.options.adaptive else "自适应难度：关"
                    )
                    self.app.audio.play("click")
                elif self.buttons["start"].hit(pos):
                    self.app.audio.play("click")
                    self.app.save_settings()
                    from .session import SessionScene

                    self.app.switch_scene(SessionScene(self.app, self.options))
                    return
                elif self.buttons["back"].hit(pos):
                    self.app.save_settings()
                    from .menu import MenuScene

                    self.app.switch_scene(MenuScene(self.app))
                    return
            if self._show_sensitivity and self.sensitivity.handle_event(event):
                self.app.settings.input.sensitivity = self.sensitivity.value
            if not self.options.adaptive:
                if self.fixed_slider.handle_event(event):
                    self.options.fixed_level = int(round(self.fixed_slider.value))

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != getattr(self, "_display_gen", -1):
            self._display_gen = self.app.display_generation
            self._layout()
        surface.fill(theme.bg)
        theme.text(
            surface,
            self.app.tr("选择训练"),
            (theme.width // 2, int(52 * theme.ui)),
            size=40,
            color=theme.text_color,
            bold=True,
            anchor="midtop",
        )
        theme.text(
            surface,
            self.app.tr("四个模块：甩枪 · 追踪 · 动态视敏 · 周边视野"),
            (theme.width // 2, int(102 * theme.ui)),
            size=17,
            color=theme.muted,
            anchor="midtop",
        )
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)

        desc = theme.tr(
            _DESCRIPTIONS.get((self.options.module_id, self.options.mode), "")
        )
        compact = getattr(self, "_compact", False)
        desc_width = int(720 * theme.ui)
        desc_y = int(theme.height * (0.68 if compact else 0.55))
        draw_paragraph(
            surface,
            theme,
            desc,
            (theme.width // 2 - desc_width // 2, desc_y),
            desc_width,
            size=15 if compact else 17,
            color=theme.muted,
        )
        if self._show_sensitivity:
            self.sensitivity.draw(surface, theme)
        if self.options.adaptive:
            if self._show_sensitivity:
                theme.text(
                    surface,
                    theme.tr("目标难度会在训练中自动调整"),
                    (theme.width // 2 + int(220 * theme.ui), self.fixed_slider.rect.top + int(6 * theme.ui)),
                    size=15,
                    color=theme.muted,
                    anchor="midtop",
                )
            else:
                theme.text(
                    surface,
                    theme.tr("本模块使用键盘，不涉及鼠标灵敏度"),
                    (theme.width // 2 - int(220 * theme.ui), self.fixed_slider.rect.top + int(6 * theme.ui)),
                    size=15,
                    color=theme.muted,
                    anchor="midtop",
                )
                theme.text(
                    surface,
                    theme.tr("目标难度会在训练中自动调整"),
                    (theme.width // 2 + int(220 * theme.ui), self.fixed_slider.rect.top + int(6 * theme.ui)),
                    size=15,
                    color=theme.muted,
                    anchor="midtop",
                )
        else:
            self.fixed_slider.draw(surface, theme)
            if not self._show_sensitivity:
                theme.text(
                    surface,
                    theme.tr("本模块使用键盘，不涉及鼠标灵敏度"),
                    (theme.width // 2 - int(220 * theme.ui), self.fixed_slider.rect.top + int(6 * theme.ui)),
                    size=15,
                    color=theme.muted,
                    anchor="midtop",
                )

        if not compact:
            panel = pygame.Rect(
                theme.width // 2 - int(220 * theme.ui),
                theme.height - int(272 * theme.ui),
                int(440 * theme.ui),
                int(100 * theme.ui),
            )
            theme.panel_rect(surface, panel)
            theme.text(
                surface,
                theme.tr("个人记录"),
                (panel.left + int(16 * theme.ui), panel.top + int(10 * theme.ui)),
                size=14,
                color=theme.muted,
            )
            for i, line in enumerate(self._stats_lines[:3]):
                theme.text(
                    surface,
                    line,
                    (panel.left + int(16 * theme.ui), panel.top + int(32 * theme.ui + i * 20 * theme.ui)),
                    size=16,
                    color=theme.text_color,
                )
        theme.text(
            surface,
            theme.tr("Esc 返回"),
            (theme.width // 2, theme.height - int(34 * theme.ui)),
            size=13,
            color=theme.muted,
            anchor="midbottom",
        )
