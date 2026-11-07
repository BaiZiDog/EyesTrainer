from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import json

import pygame

from ..ui.charts import draw_line_chart
from ..ui.widgets import Button
from .base import Scene

if TYPE_CHECKING:
    from ..app import App


_MODULE_LABELS = {
    "flick": "甩枪反应",
    "track": "动态追踪",
    "dva": "动态视敏",
    "peripheral": "周边视野",
}
_MODE_LABELS = {
    "chain": "连击",
    "reaction": "反应",
    "waypoint": "航点",
    "bounce": "弹跳",
    "staircase": "阶梯",
    "adaptive": "自适应",
}
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
_METRICS = {
    ("flick", "chain"): [
        ("accuracy", "命中率", 100.0, "%", True),
        ("kills_per_minute", "每分钟击杀", 1.0, "", True),
        ("iki_median", "击杀间隔", 1.0, " ms", False),
        ("entry_median", "首次入靶", 1.0, " ms", False),
        ("overshoot_median", "过冲", 1.0, " px", False),
    ],
    ("flick", "reaction"): [
        ("rt_median", "命中反应时", 1.0, " ms", False),
        ("first_move_median", "首动反应时", 1.0, " ms", False),
        ("accuracy", "命中率", 100.0, "%", True),
        ("entry_median", "首次入靶", 1.0, " ms", False),
        ("correction_median", "入靶→点击", 1.0, " ms", False),
    ],
    ("track", "waypoint"): [
        ("tot_pct", "覆盖率", 1.0, "%", True),
        ("mean_err_px", "平均偏离", 1.0, " px", False),
        ("trigger_coverage", "触发覆盖率", 100.0, "%", True),
        ("lag_median", "跟踪滞后", 1.0, " ms", False),
        ("dir_changes_median", "方向修正/秒", 1.0, "/s", False),
    ],
    ("track", "bounce"): [
        ("tot_pct", "覆盖率", 1.0, "%", True),
        ("mean_err_px", "平均偏离", 1.0, " px", False),
        ("trigger_coverage", "触发覆盖率", 100.0, "%", True),
        ("lag_median", "跟踪滞后", 1.0, " ms", False),
        ("dir_changes_median", "方向修正/秒", 1.0, "/s", False),
    ],
    ("dva", "staircase"): [
        ("threshold_deg_s", "可辨速度阈值", 1.0, " °/s", True),
        ("accuracy", "正确率", 100.0, "%", True),
        ("rt_median", "反应时", 1.0, " ms", False),
        ("reversals", "阶梯反转", 1.0, "", True),
    ],
    ("peripheral", "adaptive"): [
        ("hit_rate_pct", "周边检出率", 1.0, "%", True),
        ("false_alarm_rate_pct", "误报率", 1.0, "%", False),
        ("rt_median", "周边反应时", 1.0, " ms", False),
    ],
}


def _fmt(value, unit: str = "", digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(number) >= 100:
        digits = 0
    return f"{number:.{digits}f}{unit}"


def _config_mismatch(summary: dict, app) -> bool:
    raw = summary.get("config_json")
    if not raw:
        return False
    try:
        snap = json.loads(raw)
    except (TypeError, ValueError):
        return False
    settings = snap.get("settings") or {}
    inp = settings.get("input") or {}
    display = snap.get("display") or {}
    sensitivity = inp.get("sensitivity")
    if sensitivity is not None and abs(float(sensitivity) - app.settings.input.sensitivity) > 0.02:
        return True
    if display:
        if int(display.get("width", app.theme.width)) != app.theme.width:
            return True
        if int(display.get("height", app.theme.height)) != app.theme.height:
            return True
        if int(display.get("refresh_rate", app.refresh_rate)) != app.refresh_rate:
            return True
    return False


def _local_date(raw: str) -> str:
    try:
        dt = datetime.fromisoformat(raw)
        return dt.astimezone().strftime("%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(raw)[:16]


class HistoryScene(Scene):
    def __init__(
        self,
        app: "App",
        initial_module: str | None = None,
        initial_mode: str | None = None,
    ) -> None:
        super().__init__(app)
        latest = app.storage.history(limit=1)
        if initial_module is None:
            if latest:
                initial_module = latest[0]["module"]
                initial_mode = latest[0]["mode"]
            else:
                initial_module, initial_mode = "flick", "chain"
        if initial_module not in _MODULE_MODES:
            initial_module, initial_mode = "flick", "chain"
        if initial_mode not in _MODULE_MODES[initial_module]:
            initial_mode = _DEFAULT_MODES[initial_module]
        self.module_id = initial_module
        self.mode = initial_mode
        self.latest = latest
        self.metric_index = 0
        self.history: list[dict] = []
        self.buttons: dict[str, Button] = {}
        self.status = ""
        self._layout()
        self._refresh()

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()
        self._layout()
        self._refresh()

    def _refresh(self) -> None:
        self.latest = self.app.storage.history(limit=1)
        self.history = self.app.storage.history(
            self.module_id, self.mode, limit=30
        )
        options = _METRICS.get((self.module_id, self.mode), [])
        self.metric_index = min(self.metric_index, max(0, len(options) - 1))

    def _set_module(self, module: str) -> None:
        if module not in _MODULE_MODES:
            return
        self.module_id = module
        self.mode = _DEFAULT_MODES[module]
        self.metric_index = 0
        self._layout()
        self._refresh()

    def _set_mode(self, mode: str) -> None:
        if mode not in _MODULE_MODES.get(self.module_id, []):
            return
        self.mode = mode
        self.metric_index = 0
        self._layout()
        self._refresh()

    def _layout(self) -> None:
        theme = self.app.theme
        cx = theme.width // 2
        self.buttons = {}
        module_w = int(180 * theme.ui)
        module_gap = int(12 * theme.ui)
        for i, (module_id, label) in enumerate(_MODULE_LABELS.items()):
            self.buttons[module_id] = Button(
                pygame.Rect(
                    int(60 * theme.ui) + i * (module_w + module_gap),
                    int(130 * theme.ui),
                    module_w,
                    int(44 * theme.ui),
                ),
                label,
                selected=self.module_id == module_id,
            )
        self.buttons["back"] = Button(
            pygame.Rect(int(30 * theme.ui), int(30 * theme.ui), int(120 * theme.ui), int(42 * theme.ui)),
            "返回",
        )
        self.buttons["export"] = Button(
            pygame.Rect(theme.width - int(210 * theme.ui), int(30 * theme.ui), int(180 * theme.ui), int(42 * theme.ui)),
            "导出 CSV",
        )
        modes = _MODULE_MODES[self.module_id]
        mode_w = int(150 * theme.ui)
        if len(modes) == 1:
            mode_x = cx - mode_w // 2
        else:
            mode_x = cx - mode_w - int(8 * theme.ui)
        for i, mode in enumerate(modes):
            self.buttons[f"mode:{mode}"] = Button(
                pygame.Rect(
                    mode_x + i * (mode_w + int(16 * theme.ui)),
                    int(182 * theme.ui),
                    mode_w,
                    int(44 * theme.ui),
                ),
                _MODE_LABELS[mode],
                selected=self.mode == mode,
            )
        options = _METRICS.get((self.module_id, self.mode), [])
        metric_w = int(150 * theme.ui)
        for i, (key, label, scale, unit, higher) in enumerate(options):
            self.buttons[f"metric:{key}"] = Button(
                pygame.Rect(
                    int(60 * theme.ui) + i * (metric_w + int(10 * theme.ui)),
                    int(240 * theme.ui),
                    metric_w,
                    int(36 * theme.ui),
                ),
                label,
                selected=self.metric_index == i,
            )

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                from .menu import MenuScene

                self.app.switch_scene(MenuScene(self.app))
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                module_clicked = next(
                    (
                        module_id
                        for module_id in _MODULE_MODES
                        if self.buttons[module_id].hit(pos)
                    ),
                    None,
                )
                if module_clicked:
                    self._set_module(module_clicked)
                    self.app.audio.play("click")
                    return
                mode_clicked = next(
                    (
                        key.split(":", 1)[1]
                        for key in self.buttons
                        if key.startswith("mode:") and self.buttons[key].hit(pos)
                    ),
                    None,
                )
                if mode_clicked:
                    self._set_mode(mode_clicked)
                    self.app.audio.play("click")
                    return
                options = _METRICS.get((self.module_id, self.mode), [])
                for i, (key, label, scale, unit, higher) in enumerate(options):
                    button = self.buttons.get(f"metric:{key}")
                    if button and button.hit(pos):
                        self.metric_index = i
                        self._layout()
                        self.app.audio.play("click")
                        return
                if self.buttons["export"].hit(pos):
                    paths = self.app.storage.export_csv(
                        self.app.paths.export_dir, self.module_id, self.mode
                    )
                    self.status = f"已导出到 {paths[0].parent}"
                    self.app.audio.play("click")
                    return
                if self.buttons["back"].hit(pos):
                    from .menu import MenuScene

                    self.app.switch_scene(MenuScene(self.app))
                    return

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != getattr(self, "_display_gen", -1):
            self._display_gen = self.app.display_generation
            self._layout()
        surface.fill(theme.bg)
        theme.text(
            surface,
            "历史记录",
            (theme.width // 2, int(38 * theme.ui)),
            size=36,
            color=theme.text_color,
            bold=True,
            anchor="midtop",
        )
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)

        options = _METRICS.get((self.module_id, self.mode), [])
        if not self.history or not options:
            theme.text(
                surface,
                "当前筛选暂无训练记录",
                (theme.width // 2, theme.height // 2 - int(22 * theme.ui)),
                size=22,
                color=theme.muted,
                anchor="center",
            )
            if self.latest:
                latest = self.latest[0]
                theme.text(
                    surface,
                    f"最近一次训练：{_MODULE_LABELS.get(latest['module'], latest['module'])} · "
                    f"{_MODE_LABELS.get(latest['mode'], latest['mode'])}",
                    (theme.width // 2, theme.height // 2 + int(18 * theme.ui)),
                    size=15,
                    color=theme.warning,
                    anchor="center",
                )
            return
        key, label, scale, unit, higher = options[self.metric_index]
        values: list[float] = []
        labels: list[str] = []
        for summary in reversed(self.history):
            value = summary.get(key)
            if value is None:
                continue
            try:
                values.append(float(value) * scale)
            except (TypeError, ValueError):
                continue
            labels.append(_local_date(summary.get("started_at", "")))
        chart_rect = pygame.Rect(
            int(60 * theme.ui),
            int(300 * theme.ui),
            theme.width - int(120 * theme.ui),
            int(330 * theme.ui),
        )
        best = (max(values) if higher else min(values)) if values else None
        draw_line_chart(
            surface,
            theme,
            chart_rect,
            values,
            title=f"{label} 趋势（最近 {len(values)} 次）",
            unit=unit,
            x_labels=labels,
            reference=best,
            reference_label="最佳",
        )
        if not values:
            theme.text(
                surface,
                "旧记录未采集该指标，完成一次新训练后即可看到趋势",
                (chart_rect.centerx, chart_rect.centery + int(22 * theme.ui)),
                size=15,
                color=theme.warning,
                anchor="center",
            )

        list_y = chart_rect.bottom + int(26 * theme.ui)
        theme.text(
            surface,
            "最近记录",
            (int(60 * theme.ui), list_y),
            size=17,
            color=theme.text_color,
            bold=True,
        )
        list_y += int(30 * theme.ui)
        for summary in self.history[:5]:
            value = summary.get(key)
            value_text = (
                _fmt(float(value) * scale, unit, 1) if value is not None else "—"
            )
            status = {
                "completed": "完成",
                "incomplete": "未完成",
                "running": "进行中",
            }.get(summary.get("status", ""), summary.get("status", ""))
            mismatch = "  设置不同" if _config_mismatch(summary, self.app) else ""
            line = (
                f"{_local_date(summary.get('started_at', ''))}   "
                f"{_MODE_LABELS.get(summary.get('mode', ''), summary.get('mode', ''))}   "
                f"{label} {value_text}   "
                f"状态 {status}{mismatch}"
            )
            theme.text(
                surface,
                line,
                (int(60 * theme.ui), list_y),
                size=15,
                color=theme.muted,
            )
            list_y += int(24 * theme.ui)
        if self.status:
            theme.text(
                surface,
                self.status,
                (theme.width // 2, theme.height - int(34 * theme.ui)),
                size=14,
                color=theme.accent,
                anchor="midbottom",
            )
