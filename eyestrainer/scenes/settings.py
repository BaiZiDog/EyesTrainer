from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pygame

from ..config import APP_VERSION
from ..ui.widgets import Button, Slider, draw_paragraph
from .base import Scene

if TYPE_CHECKING:
    from ..app import App


_TABS = [
    ("display", "显示"),
    ("input", "输入"),
    ("training", "训练"),
    ("audio", "声音"),
    ("eye", "护眼"),
    ("data", "数据"),
]
_CROSSHAIR_STYLES = ["cross_dot", "dot", "cross"]
_STYLE_LABELS = {"cross_dot": "点+十字", "dot": "圆点", "cross": "十字"}
_COLORS = ["#39FF88", "#4FA3FF", "#FFD166", "#FFFFFF", "#FF4F6D"]
_FPS_CAPS = [0, 60, 120, 144, 165, 240, 360]
_REMINDERS = [0, 15, 25, 40]


class SettingsScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self.tab = "display"
        self.buttons: dict[str, Button] = {}
        self.sliders: dict[str, Slider] = {}
        self.display_dirty = False
        self.status = ""
        self._confirm_clear_until = 0.0
        self._layout()

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()
        self._layout()

    def on_exit(self) -> None:
        self.app.settings.sanitize()
        self.app.save_settings()
        if self.display_dirty and self.app.running:
            self.app.apply_display_settings()
            self.display_dirty = False

    def _go_back(self) -> None:
        if len(self.app.scene_stack) > 1:
            self.app.pop_scene()
        else:
            from .menu import MenuScene

            self.app.switch_scene(MenuScene(self.app))

    def _toggle(
        self,
        key: str,
        label: str,
        value: bool,
        rect: pygame.Rect,
    ) -> None:
        self.buttons[key] = Button(
            rect,
            f"{label}：{'开' if value else '关'}",
            selected=value,
        )

    def _layout(self) -> None:
        theme = self.app.theme
        self.buttons = {}
        self.sliders = {}
        self.buttons["back"] = Button(
            pygame.Rect(int(30 * theme.ui), int(30 * theme.ui), int(120 * theme.ui), int(42 * theme.ui)),
            "返回",
        )
        tab_w = int(140 * theme.ui)
        tab_h = int(44 * theme.ui)
        x = int(60 * theme.ui)
        y = int(124 * theme.ui)
        for key, label in _TABS:
            self.buttons[f"tab:{key}"] = Button(
                pygame.Rect(x, y, tab_w, tab_h),
                label,
                selected=self.tab == key,
            )
            y += tab_h + int(8 * theme.ui)

        content_x = int(270 * theme.ui)
        content_w = theme.width - content_x - int(70 * theme.ui)
        row_h = int(46 * theme.ui)
        row_gap = int(16 * theme.ui)
        control_w = min(int(360 * theme.ui), content_w // 2)
        left = content_x
        right = content_x + content_w - control_w
        top = int(124 * theme.ui)
        full = pygame.Rect(left, top, control_w, row_h)

        if self.tab == "display":
            d = self.app.settings.display
            self._toggle("fullscreen", "全屏", d.fullscreen, full)
            self._toggle("vsync", "垂直同步", d.vsync, full.move(0, row_h + row_gap))
            self._toggle("low_latency", "低延迟忙等", d.low_latency, full.move(0, 2 * (row_h + row_gap)))
            self.buttons["fps_cap"] = Button(
                full.move(0, 3 * (row_h + row_gap)),
                f"帧上限：{self._fps_label(d.fps_cap)}",
            )
            self.buttons["calibration"] = Button(
                full.move(0, 4 * (row_h + row_gap)),
                "打开校准页",
            )
        elif self.tab == "input":
            i = self.app.settings.input
            self.sliders["sensitivity"] = Slider(
                pygame.Rect(left, top + int(34 * theme.ui), control_w, int(8 * theme.ui)),
                "灵敏度",
                0.1,
                5.0,
                i.sensitivity,
                step=0.05,
                formatter=lambda v: f"{v:.2f}",
            )
            self.buttons["style"] = Button(
                full.move(0, int(150 * theme.ui)),
                f"准星样式：{_STYLE_LABELS.get(i.crosshair.style, i.crosshair.style)}",
            )
            self.buttons["color"] = Button(
                full.move(0, int(150 * theme.ui) + row_h + row_gap),
                f"准星颜色：{i.crosshair.color}",
            )
            self.sliders["crosshair_size"] = Slider(
                pygame.Rect(left, top + int(340 * theme.ui), control_w, int(8 * theme.ui)),
                "准星大小",
                6,
                32,
                i.crosshair.size,
                step=1,
                formatter=lambda v: f"{v:.0f}",
            )
        elif self.tab == "training":
            t = self.app.settings.training
            self._toggle("warmup", "热身回合", t.warmup, full)
            self._toggle("adaptive", "默认自适应", t.adaptive, full.move(0, row_h + row_gap))
            self.sliders["rounds"] = Slider(
                pygame.Rect(left, top + int(174 * theme.ui), control_w, int(8 * theme.ui)),
                "每轮回合数",
                1,
                5,
                t.rounds,
                step=1,
                formatter=lambda v: f"{v:.0f}",
            )
            self.sliders["flick_round"] = Slider(
                pygame.Rect(right, top + int(34 * theme.ui), control_w, int(8 * theme.ui)),
                "甩枪回合时长（秒）",
                20,
                180,
                t.flick_round_s,
                step=5,
                formatter=lambda v: f"{v:.0f}s",
            )
            self.sliders["track_round"] = Slider(
                pygame.Rect(right, top + int(114 * theme.ui), control_w, int(8 * theme.ui)),
                "追踪回合时长（秒）",
                15,
                120,
                t.track_round_s,
                step=5,
                formatter=lambda v: f"{v:.0f}s",
            )
            self.sliders["rest"] = Slider(
                pygame.Rect(right, top + int(194 * theme.ui), control_w, int(8 * theme.ui)),
                "组间休息（秒）",
                0,
                60,
                t.rest_s,
                step=5,
                formatter=lambda v: f"{v:.0f}s",
            )
        elif self.tab == "audio":
            a = self.app.settings.audio
            self.sliders["volume"] = Slider(
                pygame.Rect(left, top + int(34 * theme.ui), control_w, int(8 * theme.ui)),
                "主音量",
                0.0,
                1.0,
                a.volume,
                step=0.05,
                formatter=lambda v: f"{v:.2f}",
            )
            self._toggle("hit", "命中音", a.hit, full.move(0, int(120 * theme.ui)))
            self._toggle("miss", "空点音", a.miss, full.move(0, int(120 * theme.ui) + row_h + row_gap))
            self._toggle("round_end", "回合结束音", a.round_end, full.move(0, int(120 * theme.ui) + 2 * (row_h + row_gap)))
        elif self.tab == "eye":
            e = self.app.settings.eye_care
            self.buttons["reminder"] = Button(
                full,
                "休息提醒：" + ("关闭" if e.reminder_min == 0 else f"每 {e.reminder_min} 分钟"),
            )
        elif self.tab == "data":
            is_training = any(
                type(scene).__name__ == "SessionScene"
                for scene in self.app.scene_stack
            )
            self.buttons["export"] = Button(full, "导出全部 CSV")
            self.buttons["open_data"] = Button(
                full.move(0, row_h + row_gap),
                "打开数据目录",
            )
            self.buttons["clear"] = Button(
                full.move(0, 2 * (row_h + row_gap)),
                "清空训练数据（点击两次确认）",
                enabled=not is_training,
            )

    @staticmethod
    def _fps_label(cap: int) -> str:
        return "跟随刷新率" if cap == 0 else str(cap)

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._go_back()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.buttons["back"].hit(pos):
                    self.app.audio.play("click")
                    self._go_back()
                    return
                for key, label in _TABS:
                    if self.buttons.get(f"tab:{key}") and self.buttons[f"tab:{key}"].hit(pos):
                        self.tab = key
                        self.app.audio.play("click")
                        self._layout()
                        return
                if self._handle_tab_click(pos):
                    return
            # Sliders are handled after buttons so a click on a slider does not
            # also trigger a page action.
            for key, slider in self.sliders.items():
                if slider.handle_event(event):
                    self._apply_slider(key, slider.value)

    def _handle_tab_click(self, pos: tuple[int, int]) -> bool:
        if self.tab == "display":
            d = self.app.settings.display
            if self.buttons["fullscreen"].hit(pos):
                d.fullscreen = not d.fullscreen
                self.display_dirty = True
                self._layout()
                return True
            if self.buttons["vsync"].hit(pos):
                d.vsync = not d.vsync
                self.display_dirty = True
                self._layout()
                return True
            if self.buttons["low_latency"].hit(pos):
                d.low_latency = not d.low_latency
                self.app.pacer.low_latency = d.low_latency
                self._layout()
                return True
            if self.buttons["fps_cap"].hit(pos):
                idx = (_FPS_CAPS.index(d.fps_cap) + 1) % len(_FPS_CAPS) if d.fps_cap in _FPS_CAPS else 0
                d.fps_cap = _FPS_CAPS[idx]
                self.display_dirty = True
                self._layout()
                return True
            if self.buttons["calibration"].hit(pos):
                from .calibration import CalibrationScene

                self.app.push_scene(CalibrationScene(self.app))
                return True
        elif self.tab == "input":
            i = self.app.settings.input
            if self.buttons["style"].hit(pos):
                idx = (_CROSSHAIR_STYLES.index(i.crosshair.style) + 1) % len(_CROSSHAIR_STYLES) if i.crosshair.style in _CROSSHAIR_STYLES else 0
                i.crosshair.style = _CROSSHAIR_STYLES[idx]
                self._layout()
                return True
            if self.buttons["color"].hit(pos):
                current = i.crosshair.color.upper()
                idx = (_COLORS.index(current) + 1) % len(_COLORS) if current in _COLORS else 0
                i.crosshair.color = _COLORS[idx]
                self._layout()
                return True
        elif self.tab == "training":
            t = self.app.settings.training
            if self.buttons["warmup"].hit(pos):
                t.warmup = not t.warmup
                self._layout()
                return True
            if self.buttons["adaptive"].hit(pos):
                t.adaptive = not t.adaptive
                self._layout()
                return True
        elif self.tab == "audio":
            a = self.app.settings.audio
            if self.buttons["hit"].hit(pos):
                a.hit = not a.hit
                self.app.audio.apply_config(a)
                self._layout()
                return True
            if self.buttons["miss"].hit(pos):
                a.miss = not a.miss
                self.app.audio.apply_config(a)
                self._layout()
                return True
            if self.buttons["round_end"].hit(pos):
                a.round_end = not a.round_end
                self.app.audio.apply_config(a)
                self._layout()
                return True
        elif self.tab == "eye":
            e = self.app.settings.eye_care
            if self.buttons["reminder"].hit(pos):
                idx = (_REMINDERS.index(e.reminder_min) + 1) % len(_REMINDERS) if e.reminder_min in _REMINDERS else 0
                e.reminder_min = _REMINDERS[idx]
                self._layout()
                return True
        elif self.tab == "data":
            if self.buttons["export"].hit(pos):
                paths = self.app.storage.export_csv(self.app.paths.export_dir)
                self.status = f"已导出到 {paths[0].parent}"
                self.app.audio.play("click")
                return True
            if self.buttons["open_data"].hit(pos):
                path = self.app.paths.data_dir
                try:
                    os.startfile(str(path))
                    self.status = f"已打开 {path}"
                except OSError as exc:
                    self.status = f"无法打开数据目录：{exc}"
                self.app.audio.play("click")
                return True
            if self.buttons["clear"].enabled and self.buttons["clear"].hit(pos):
                now = time.perf_counter()
                if now <= self._confirm_clear_until:
                    self.app.storage.clear_sessions()
                    self.status = "训练数据已清空"
                    self._confirm_clear_until = 0.0
                    self.app.audio.play("miss")
                else:
                    self._confirm_clear_until = now + 4.0
                    self.status = "再次点击确认清空所有训练数据"
                return True
        return False

    def _apply_slider(self, key: str, value: float) -> None:
        s = self.app.settings
        if key == "sensitivity":
            s.input.sensitivity = value
        elif key == "crosshair_size":
            s.input.crosshair.size = int(round(value))
        elif key == "rounds":
            s.training.rounds = int(round(value))
        elif key == "flick_round":
            s.training.flick_round_s = int(round(value))
        elif key == "track_round":
            s.training.track_round_s = int(round(value))
        elif key == "rest":
            s.training.rest_s = int(round(value))
        elif key == "volume":
            s.audio.volume = value
            self.app.audio.apply_config(s.audio)

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != getattr(self, "_display_gen", -1):
            self._display_gen = self.app.display_generation
            self._layout()
        surface.fill(theme.bg)
        theme.text(
            surface,
            "设置",
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

        content_x = int(270 * theme.ui)
        content_w = theme.width - content_x - int(70 * theme.ui)
        top = {
            "display": 470,
            "input": 560,
            "training": 430,
            "audio": 440,
            "eye": 220,
            "data": 340,
        }.get(self.tab, 300)
        top = int(top * theme.ui)
        if self.tab == "display":
            d = self.app.settings.display
            lines = [
                f"分辨率：{self.app.theme.width} × {self.app.theme.height}",
                f"刷新率：{self.app.refresh_rate} Hz",
                "显示设置修改后，返回时应用。",
            ]
            for i, line in enumerate(lines):
                theme.text(
                    surface,
                    line,
                    (content_x, top + i * int(28 * theme.ui)),
                    size=16,
                    color=theme.muted,
                )
        elif self.tab == "input":
            draw_paragraph(
                surface,
                theme,
                "训练时使用相对鼠标移动，隐藏系统光标并自绘准星。"
                "灵敏度只影响训练中的准星移动，不影响菜单。"
                "如果手感异常，请关闭 Windows 的“增强指针精确度”。",
                (content_x, top),
                content_w,
                size=15,
            )
        elif self.tab == "training":
            draw_paragraph(
                surface,
                theme,
                "这些是本机默认训练结构，模块选择页仍可临时切换自适应与固定难度。"
                "回合时长越长，长时注意力和疲劳因素越明显。",
                (content_x, top),
                content_w,
                size=15,
            )
        elif self.tab == "audio":
            theme.text(
                surface,
                "音效由程序合成，不加载外部音频文件。",
                (content_x, top),
                size=15,
                color=theme.muted,
            )
        elif self.tab == "eye":
            draw_paragraph(
                surface,
                theme,
                "累计训练达到提醒间隔后，会显示全屏休息层 20 秒，训练自动暂停。"
                "本工具不是医疗设备；如出现眼痛、头痛或眩晕，请停止使用并咨询专业人士。",
                (content_x, top),
                content_w,
                size=15,
            )
        elif self.tab == "data":
            total_minutes = self.app.storage.total_training_seconds() / 60.0
            lines = [
                f"档案：{self.app.settings.profile}",
                f"累计训练：{total_minutes:.0f} 分钟",
                f"数据目录：{self.app.paths.data_dir}",
                f"版本：{APP_VERSION}",
            ]
            for i, line in enumerate(lines):
                theme.text(
                    surface,
                    line,
                    (content_x, top + i * int(28 * theme.ui)),
                    size=15,
                    color=theme.muted,
                )
            if theme.width < 1300:
                theme.text(
                    surface,
                    "窗口较窄时路径可能超出屏幕",
                    (content_x, top + 4 * int(28 * theme.ui)),
                    size=13,
                    color=theme.warning,
                )
        if self.status:
            theme.text(
                surface,
                self.status,
                (theme.width // 2, theme.height - int(34 * theme.ui)),
                size=14,
                color=theme.accent,
                anchor="midbottom",
            )
