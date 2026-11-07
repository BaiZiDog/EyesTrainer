from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..core import metrics
from ..core.metrics import summarize_session
from ..core.motion import decode_blob, downsample, slice_samples
from ..modules.base import RoundResult
from ..ui.charts import draw_histogram, draw_line_chart
from ..ui.widgets import Button, draw_card
from .base import Scene
from .options import SessionOptions

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


def _fmt(value, unit: str = "", digits: int = 1, scale: float = 1.0) -> str:
    if value is None:
        return "—"
    try:
        number = float(value) * scale
    except (TypeError, ValueError):
        return "—"
    return f"{number:.{digits}f}{unit}"


class ResultsScene(Scene):
    def __init__(
        self,
        app: "App",
        module_id: str,
        mode: str,
        options: SessionOptions,
        rounds: list[RoundResult],
        plan,
        session_id: int | None,
    ) -> None:
        super().__init__(app)
        self.module_id = module_id
        self.mode = mode
        self.options = options
        self.rounds = rounds
        self.plan = plan
        self.session_id = session_id
        round_dicts = [
            {
                "is_warmup": r.is_warmup,
                "duration_s": r.duration_s,
                "trials": r.trials,
                "windows": r.windows,
            }
            for r in rounds
        ]
        self.summary = summarize_session(module_id, mode, round_dicts)
        self.main_trials = [
            t for r in rounds if not r.is_warmup for t in r.trials
        ]
        self.main_windows = [
            w for r in rounds if not r.is_warmup for w in r.windows
        ]
        self.warmup_rounds = sum(1 for r in rounds if r.is_warmup)
        self.buttons: dict[str, Button] = {}
        self._trajectory = self._prepare_trajectory()
        self.show_trajectory = self._trajectory is not None
        self.previous = None
        self.best = None
        if session_id is not None:
            comparison = app.storage.previous_and_best(
                module_id, mode, session_id
            )
            self.previous = comparison.get("previous")
            self.best = comparison.get("best")
        self._layout()

    def on_enter(self) -> None:
        self.app.input.exit_gameplay()

    def _layout(self) -> None:
        theme = self.app.theme
        width = int(200 * theme.ui)
        height = int(46 * theme.ui)
        gap = int(12 * theme.ui)
        items = [
            ("again", "再来一次"),
            ("modules", "模块选择"),
            ("history", "历史记录"),
            ("chart_mode", "分布图" if self.show_trajectory else "轨迹分析"),
            ("menu", "主菜单"),
        ]
        if self._trajectory is None:
            items = [item for item in items if item[0] != "chart_mode"]
        total = len(items) * width + (len(items) - 1) * gap
        x = theme.width // 2 - total // 2
        y = theme.height - int(74 * theme.ui)
        self.buttons = {}
        for key, label in items:
            self.buttons[key] = Button(
                pygame.Rect(x, y, width, height),
                label,
                kind="primary" if key == "again" else "secondary",
            )
            x += width + gap

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                from .module_select import ModuleSelectScene

                self.app.switch_scene(ModuleSelectScene(self.app))
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.buttons["again"].hit(pos):
                    self.app.audio.play("click")
                    from .session import SessionScene

                    self.app.switch_scene(
                        SessionScene(self.app, self.options)
                    )
                    return
                if self.buttons["modules"].hit(pos):
                    self.app.audio.play("click")
                    from .module_select import ModuleSelectScene

                    self.app.switch_scene(ModuleSelectScene(self.app))
                    return
                if self.buttons.get("chart_mode") and self.buttons["chart_mode"].hit(pos):
                    if self._trajectory is not None:
                        self.show_trajectory = not self.show_trajectory
                        self.buttons["chart_mode"].label = (
                            "分布图" if self.show_trajectory else "轨迹分析"
                        )
                        self.app.audio.play("click")
                    return
                if self.buttons["history"].hit(pos):
                    self.app.audio.play("click")
                    from .history import HistoryScene

                    self.app.switch_scene(
                        HistoryScene(
                            self.app,
                            initial_module=self.module_id,
                            initial_mode=self.mode,
                        )
                    )
                    return
                if self.buttons["menu"].hit(pos):
                    self.app.audio.play("click")
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
            f"{_MODULE_LABELS.get(self.module_id, self.module_id)} · {_MODE_LABELS.get(self.mode, self.mode)}",
            (theme.width // 2, int(36 * theme.ui)),
            size=36,
            color=theme.text_color,
            bold=True,
            anchor="midtop",
        )
        theme.text(
            surface,
            "训练完成" if self._main_rounds_done() else "训练已结束（未完成全部回合）",
            (theme.width // 2, int(82 * theme.ui)),
            size=17,
            color=theme.accent if self._main_rounds_done() else theme.warning,
            anchor="midtop",
        )

        cards = self._cards()
        gap = int(16 * theme.ui)
        margin = int(60 * theme.ui)
        available = theme.width - 2 * margin
        card_w = int((available - gap * (len(cards) - 1)) / max(1, len(cards)))
        card_h = int(104 * theme.ui)
        y = int(132 * theme.ui)
        x = margin
        for label, value, sub in cards:
            rect = pygame.Rect(x, y, card_w, card_h)
            draw_card(surface, theme, rect, label, value, sub)
            x += card_w + gap

        chart_rect = pygame.Rect(
            margin,
            y + card_h + int(24 * theme.ui),
            int(available * 0.62),
            int(330 * theme.ui),
        )
        self._draw_chart(surface, chart_rect)
        side_rect = pygame.Rect(
            chart_rect.right + int(20 * theme.ui),
            chart_rect.top,
            theme.width - margin - chart_rect.right - int(20 * theme.ui),
            chart_rect.height,
        )
        self._draw_side_panel(surface, side_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)

    def _main_rounds_done(self) -> bool:
        total = sum(1 for p in self.plan if not p.is_warmup)
        done = sum(1 for r in self.rounds if not r.is_warmup)
        return done >= total

    def _cards(self) -> list[tuple[str, str, str]]:
        s = self.summary
        if self.module_id == "flick" and self.mode == "chain":
            return [
                ("命中率", _fmt(s.get("accuracy"), "%", 1, 100.0), f"n={s.get('shots', 0)} 次射击"),
                ("每分钟击杀", _fmt(s.get("kills_per_minute"), "", 1), f"{s.get('kill_count', 0)} 次击杀"),
                ("击杀间隔", _fmt(s.get("iki_median"), " ms", 0), f"P25–P75 {_fmt(s.get('iki_p25'), '', 0)}–{_fmt(s.get('iki_p75'), '', 0)}"),
                ("路径效率", _fmt(s.get("path_eff_median"), "%", 1, 100.0), "理想直线 / 实际移动"),
            ]
        if self.module_id == "flick":
            return [
                ("命中反应时", _fmt(s.get("rt_median"), " ms", 0), f"P25–P75 {_fmt(s.get('rt_p25'), '', 0)}–{_fmt(s.get('rt_p75'), '', 0)}"),
                ("首动反应时", _fmt(s.get("first_move_median"), " ms", 0), f"n={s.get('first_move_n', 0)}"),
                ("命中率", _fmt(s.get("accuracy"), "%", 1, 100.0), f"命中 {s.get('hits', 0)} / 超时 {s.get('timeouts', 0)}"),
                ("预判 / 空点", f"{s.get('anticipation', 0)} / {s.get('miss_clicks', 0)}", "预判点击计为失误"),
            ]
        if self.module_id == "dva":
            return [
                ("可辨速度阈值", _fmt(s.get("threshold_deg_s"), " °/s", 1), f"{_fmt(s.get('threshold_px_s'), ' px/s', 0)}"),
                ("正确率", _fmt(s.get("accuracy"), "%", 1, 100.0), f"{s.get('correct', 0)}/{s.get('trials', 0)} · 超时 {s.get('timeouts', 0)}"),
                ("反应时中位", _fmt(s.get("rt_median"), " ms", 0), f"n={s.get('rt_n', 0)}"),
                ("阶梯反转", f"{s.get('reversals', 0)}", f"最终 {_fmt(s.get('final_speed_deg_s'), ' °/s', 1)}"),
            ]
        if self.module_id == "peripheral":
            return [
                ("周边检出率", _fmt(s.get("hit_rate_pct"), "%", 1), f"命中 {s.get('hits', 0)}/{s.get('target_trials', 0)}"),
                ("误报率", _fmt(s.get("false_alarm_rate_pct"), "%", 1), f"误报 {s.get('false_alarms', 0)}/{s.get('catch_trials', 0)}"),
                ("周边反应时", _fmt(s.get("rt_median"), " ms", 0), f"n={s.get('rt_n', 0)}"),
                ("偏心角", _fmt(s.get("eccentricity_median_deg"), "°", 1), f"最大 {_fmt(s.get('eccentricity_max_deg'), '°', 1)}"),
            ]
        return [
            ("覆盖率 TO/T", _fmt(s.get("tot_pct"), "%", 1), f"开火 {float(s.get('fired_ms') or 0) / 1000:.1f}s"),
            ("平均偏离", _fmt(s.get("mean_err_px"), " px", 1), f"归一化 {_fmt(s.get('mean_err_norm'), '', 2)} r"),
            ("触发覆盖率", _fmt(s.get("trigger_coverage"), "%", 1, 100.0), "低于 70% 参考性下降"),
            ("目标速度", _fmt(s.get("speed_median"), " px/s", 0), f"范围 {_fmt(s.get('speed_min'), '', 0)}–{_fmt(s.get('speed_max'), '', 0)}"),
        ]

    def _prepare_trajectory(self) -> dict | None:
        if self.module_id == "flick":
            candidates = []
            for result in self.rounds:
                if result.is_warmup or not result.motion_blob or not result.arena:
                    continue
                try:
                    _, samples = decode_blob(result.motion_blob)
                except (ValueError, OSError):
                    continue
                for trial in result.trials:
                    if (
                        trial.get("outcome") == "hit"
                        and trial.get("target_x") is not None
                        and trial.get("spawn_t") is not None
                        and trial.get("click_t") is not None
                    ):
                        candidates.append((result, trial, samples))
            if not candidates:
                return None
            target_score = self.summary.get("correction_median")
            if target_score is None:
                target_score = self.summary.get("entry_median")
            if target_score is None:
                chosen = candidates[0]
            else:
                chosen = min(
                    candidates,
                    key=lambda item: abs(
                        float(
                            item[1].get("correction_ms")
                            or item[1].get("entry_ms")
                            or 0.0
                        )
                        - float(target_score)
                    ),
                )
            result, trial, samples = chosen
            window = slice_samples(
                samples,
                float(trial["spawn_t"]) * 1000.0,
                float(trial["click_t"]) * 1000.0,
            )
            if len(window) < 2:
                return None
            return {
                "kind": "flick",
                "samples": downsample(window, 700),
                "target": (
                    trial["target_x"],
                    trial["target_y"],
                    trial["target_r"],
                ),
                "click": (trial["cross_x"], trial["cross_y"]),
                "arena": result.arena,
                "label": f"轨迹示例 · 目标 #{trial.get('target_id', '-')}",
            }
        for result in reversed(self.rounds):
            if result.is_warmup or not result.motion_blob or not result.arena:
                continue
            try:
                _, samples = decode_blob(result.motion_blob)
            except (ValueError, OSError):
                continue
            end_ms = samples[-1].t_ms
            window = [
                s for s in samples if s.t_ms >= max(0.0, end_ms - 6000.0)
            ]
            if len(window) < 2:
                continue
            return {
                "kind": "track",
                "samples": downsample(window, 700),
                "arena": result.arena,
                "label": "追踪轨迹 · 最近 6 秒",
            }
        return None

    def _draw_chart(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        if self.show_trajectory and self._trajectory is not None:
            self._draw_trajectory(surface, rect)
            return
        if self.module_id == "flick" and self.mode == "reaction":
            draw_histogram(
                surface,
                self.app.theme,
                rect,
                metrics.valid_reaction_rts(self.main_trials),
                title="命中反应时分布",
                unit=" ms",
            )
        elif self.module_id == "flick":
            draw_histogram(
                surface,
                self.app.theme,
                rect,
                metrics.inter_kill_intervals(self.main_trials),
                title="击杀间隔分布",
                unit=" ms",
            )
        elif self.module_id == "dva":
            values = [
                float(t["speed_deg_s"])
                for t in self.main_trials
                if t.get("speed_deg_s") is not None
            ]
            draw_line_chart(
                surface,
                self.app.theme,
                rect,
                values,
                title="速度阶梯（deg/s）",
                unit=" °/s",
                x_labels=[str(t.get("trial_idx", i + 1)) for i, t in enumerate(self.main_trials)],
                reference=self.summary.get("threshold_deg_s"),
                reference_label="阈值",
            )
        elif self.module_id == "peripheral":
            values = [
                float(t["eccentricity_deg"])
                for t in self.main_trials
                if t.get("eccentricity_deg") is not None
            ]
            draw_line_chart(
                surface,
                self.app.theme,
                rect,
                values,
                title="偏心角阶梯（度）",
                unit="°",
                x_labels=[str(t.get("trial_idx", i + 1)) for i, t in enumerate(self.main_trials)],
                reference=self.summary.get("eccentricity_median_deg"),
                reference_label="中位",
            )
        else:
            values: list[float] = []
            labels: list[str] = []
            for result in self.rounds:
                if result.is_warmup or not result.windows:
                    continue
                fired = sum(float(w.get("fired_ms") or 0.0) for w in result.windows)
                ontarget = sum(float(w.get("ontarget_ms") or 0.0) for w in result.windows)
                if fired > 0:
                    values.append(ontarget / fired * 100.0)
                    labels.append(f"R{result.summary.get('round_idx', len(labels) + 1)}")
            draw_line_chart(
                surface,
                self.app.theme,
                rect,
                values,
                title="各回合覆盖率",
                unit="%",
                x_labels=labels,
            )

    def _draw_trajectory(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        theme = self.app.theme
        theme.panel_rect(surface, rect)
        data = self._trajectory
        if data is None:
            return
        theme.text(
            surface,
            data["label"],
            (rect.left + int(16 * theme.ui), rect.top + int(12 * theme.ui)),
            size=17,
            color=theme.text_color,
            bold=True,
        )
        inner = pygame.Rect(
            rect.left + int(28 * theme.ui),
            rect.top + int(46 * theme.ui),
            rect.width - int(56 * theme.ui),
            rect.height - int(92 * theme.ui),
        )
        ax, ay, aw, ah = data["arena"]
        scale = min(inner.width / max(aw, 1), inner.height / max(ah, 1))
        ox = inner.centerx - aw * scale / 2
        oy = inner.centery - ah * scale / 2

        def point(x: float, y: float) -> tuple[int, int]:
            return (
                int(ox + (x - ax) * scale),
                int(oy + (y - ay) * scale),
            )

        pygame.draw.rect(
            surface,
            theme.border,
            pygame.Rect(int(ox), int(oy), int(aw * scale), int(ah * scale)),
            width=max(1, int(theme.ui)),
        )
        samples = data["samples"]
        if data["kind"] == "flick":
            target = data["target"]
            pygame.draw.circle(
                surface,
                theme.target,
                point(target[0], target[1]),
                max(2, int(target[2] * scale)),
                width=max(1, int(2 * theme.ui)),
            )
            path = [point(s.x, s.y) for s in samples]
            if len(path) > 1:
                pygame.draw.lines(
                    surface, theme.accent, False, path, max(2, int(2 * theme.ui))
                )
            pygame.draw.circle(
                surface, theme.white, path[0], max(3, int(4 * theme.ui))
            )
            pygame.draw.circle(
                surface, theme.warning, path[-1], max(3, int(4 * theme.ui))
            )
        else:
            target_path = [point(s.target_x, s.target_y) for s in samples]
            cross_path = [point(s.x, s.y) for s in samples]
            if len(target_path) > 1:
                pygame.draw.lines(
                    surface,
                    theme.target,
                    False,
                    target_path,
                    max(3, int(3 * theme.ui)),
                )
                pygame.draw.lines(
                    surface,
                    theme.accent,
                    False,
                    cross_path,
                    max(1, int(1.5 * theme.ui)),
                )
            last = samples[-1]
            pygame.draw.circle(
                surface,
                theme.target,
                point(last.target_x, last.target_y),
                max(2, int(last.target_r * scale)),
                width=max(1, int(2 * theme.ui)),
            )
        legend = (
            "白=起点  绿=准星轨迹  红=目标  黄=点击"
            if data["kind"] == "flick"
            else "红=目标轨迹  绿=准星轨迹"
        )
        theme.text(
            surface,
            legend,
            (rect.left + int(16 * theme.ui), rect.bottom - int(28 * theme.ui)),
            size=13,
            color=theme.muted,
        )

    def _draw_side_panel(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        theme = self.app.theme
        theme.panel_rect(surface, rect)
        x = rect.left + int(18 * theme.ui)
        y = rect.top + int(14 * theme.ui)
        theme.text(surface, "本次 vs 历史", (x, y), size=17, color=theme.text_color, bold=True)
        y += int(34 * theme.ui)
        primary = metrics.primary_metric(
            self.module_id, self.mode, self.summary
        )
        key = primary["key"]
        label = primary["label"]
        unit = primary["unit"]
        current = self.summary.get(key)
        theme.text(surface, label, (x, y), size=14, color=theme.muted)
        y += int(22 * theme.ui)
        theme.text(
            surface,
            _fmt(current, unit, 1),
            (x, y),
            size=26,
            color=theme.text_color,
            bold=True,
        )
        y += int(38 * theme.ui)
        prev_value = self.previous.get(key) if self.previous else None
        best_value = self.best.get(key) if self.best else None
        theme.text(
            surface,
            f"上次：{_fmt(prev_value, unit, 1)}",
            (x, y),
            size=15,
            color=theme.muted,
        )
        y += int(24 * theme.ui)
        theme.text(
            surface,
            f"最佳：{_fmt(best_value, unit, 1)}",
            (x, y),
            size=15,
            color=theme.muted,
        )
        y += int(34 * theme.ui)
        level_min = self.summary.get("level_min")
        level_max = self.summary.get("level_max")
        theme.text(
            surface,
            f"等级范围：{_fmt(level_min, '', 0)} – {_fmt(level_max, '', 0)}",
            (x, y),
            size=14,
            color=theme.muted,
        )
        y += int(26 * theme.ui)
        long_frames = sum(
            int(r.summary.get("long_frames", 0)) for r in self.rounds
        )
        pauses = sum(int(r.summary.get("pauses", 0)) for r in self.rounds)
        theme.text(
            surface,
            f"长帧：{long_frames}　暂停：{pauses}　热身：{self.warmup_rounds} 回合",
            (x, y),
            size=14,
            color=theme.warning if long_frames > 20 else theme.muted,
        )
        y += int(26 * theme.ui)
        if self.module_id == "flick" and self.mode == "reaction":
            extra = f"超时 {self.summary.get('timeouts', 0)} · 预判 {self.summary.get('anticipation', 0)}"
        elif self.module_id == "track":
            extra = f"窗口 {self.summary.get('windows', 0)} · 开火占比 {_fmt(self.summary.get('trigger_coverage'), '%', 0, 100.0)}"
        elif self.module_id == "dva":
            extra = f"响应 {self.summary.get('responses', 0)}/{self.summary.get('trials', 0)} · 超时 {self.summary.get('timeouts', 0)}"
        elif self.module_id == "peripheral":
            extra = f"试次 {self.summary.get('trials', 0)} · 目标 {self.summary.get('target_trials', 0)} · 抑制 {self.summary.get('catch_trials', 0)}"
        else:
            extra = f"点击误差中位 {_fmt(self.summary.get('click_err_median'), ' r', 2)}"
        theme.text(
            surface,
            extra,
            (x, y),
            size=13,
            color=theme.muted,
        )
        y += int(24 * theme.ui)
        pygame.draw.line(
            surface,
            theme.border,
            (x, y),
            (rect.right - int(18 * theme.ui), y),
            width=1,
        )
        y += int(10 * theme.ui)
        if self.module_id == "flick":
            advanced = [
                f"首次入靶 {_fmt(self.summary.get('entry_median'), ' ms', 0)} · "
                f"入靶→点击 {_fmt(self.summary.get('correction_median'), ' ms', 0)}",
                f"过冲 {_fmt(self.summary.get('overshoot_median'), ' px', 1)} · "
                f"方向变化 {_fmt(self.summary.get('direction_changes_median'), '', 1)}",
                f"峰值速度 {_fmt(self.summary.get('peak_speed_median'), ' px/s', 0)}",
                f"轨迹曲率 {_fmt(self.summary.get('curvature_median'), '', 2)}",
            ]
        elif self.module_id == "track":
            advanced = [
                f"跟踪滞后 {_fmt(self.summary.get('lag_median'), ' ms', 0)} · "
                f"方向修正 {_fmt(self.summary.get('dir_changes_median'), '/s', 1)}",
                f"速度波动 {_fmt(self.summary.get('jitter_median'), ' px/s', 0)}",
                f"峰值速度 {_fmt(self.summary.get('peak_speed_max'), ' px/s', 0)}",
                f"误差波动 {_fmt(self.summary.get('error_std_median'), ' px', 1)}",
            ]
        elif self.module_id == "dva":
            advanced = [
                f"阈值 {_fmt(self.summary.get('threshold_deg_s'), ' °/s', 1)} · "
                f"{_fmt(self.summary.get('threshold_px_s'), ' px/s', 0)}",
                f"反转 {self.summary.get('reversals', 0)} · "
                f"响应率 {_fmt(self.summary.get('response_rate'), '%', 1, 100.0)}",
                f"平均速度 {_fmt(self.summary.get('speed_median_deg_s'), ' °/s', 1)}",
                f"最终速度 {_fmt(self.summary.get('final_speed_deg_s'), ' °/s', 1)} · "
                f"等级 {_fmt(self.summary.get('level_final'), '', 0)}",
            ]
        else:
            advanced = [
                f"漏检 {self.summary.get('misses', 0)} · 误报 {self.summary.get('false_alarms', 0)}",
                f"正确抑制 {self.summary.get('correct_rejections', 0)}/{self.summary.get('catch_trials', 0)}",
                f"曝光 {_fmt(self.summary.get('exposure_ms_median'), ' ms', 0)} · "
                f"刺激 {_fmt(self.summary.get('stimulus_count_median'), '', 0)}",
                f"偏心角 {_fmt(self.summary.get('eccentricity_median_deg'), '°', 1)} · "
                f"等级 {_fmt(self.summary.get('level_final'), '', 0)}",
            ]
        for line in advanced:
            theme.text(
                surface,
                line,
                (x, y),
                size=13,
                color=theme.muted,
            )
            y += int(20 * theme.ui)
