from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import pygame

from ..config import APP_VERSION
from ..core import geometry
from ..core.input import InputFrame
from ..core.storage import utc_now
from ..modules.base import ModuleConfig, RoundResult
from ..modules.dva import DvaModule
from ..modules.flick import FlickModule
from ..modules.peripheral import PeripheralModule
from ..modules.track import TrackModule
from ..ui.hud import draw_countdown, draw_crosshair, draw_dim, draw_hud
from ..ui.theme import parse_color
from ..ui.widgets import Button
from .base import Scene
from .options import SessionOptions

if TYPE_CHECKING:
    from ..app import App


DVA_ROUND_S = 90.0
PERIPHERAL_ROUND_S = 60.0


@dataclass
class RoundPlan:
    round_idx: int
    is_warmup: bool
    duration_s: float
    adaptive: bool
    fixed_level: int
    mode: str


class SessionScene(Scene):
    def __init__(self, app: "App", options: SessionOptions) -> None:
        super().__init__(app)
        self.options = options
        self.module_id = options.module_id
        self.mode = options.mode
        self.plan = self._build_plan()
        self.plan_index = 0
        self.module = None
        self.session_id: int | None = None
        self.results: list[RoundResult] = []
        self.completed_main_rounds = 0
        self.started = False
        self.session_finished = False
        self.phase = "idle"
        self.phase_timer = 0.0
        self.round_t = 0.0
        self.paused_phase: str | None = None
        self.pause_due_to_eye_rest = False
        self._restart_on_resume = False
        self._last_countdown_second = 0
        self._pause_count = 0
        self._long_frames_start = 0
        self._round_started_at = utc_now()
        self.arena = geometry.arena_rect((app.theme.width, app.theme.height))
        self.buttons: dict[str, Button] = {}
        self.rest_skip = Button(
            pygame.Rect(0, 0, 1, 1), app.tr("跳过休息")
        )
        self._display_gen = app.display_generation
        self._frame_events: tuple[pygame.event.Event, ...] = ()
        self._layout_overlays()

    # ------------------------------------------------------------------ lifecycle

    def _build_plan(self) -> list[RoundPlan]:
        t = self.app.settings.training
        mode = self.mode
        plan: list[RoundPlan] = []
        if t.warmup:
            plan.append(
                RoundPlan(
                    round_idx=0,
                    is_warmup=True,
                    duration_s=15.0,
                    adaptive=False,
                    fixed_level=0,
                    mode=mode,
                )
            )
        if self.module_id == "flick":
            duration = float(t.flick_round_s)
        elif self.module_id == "track":
            duration = float(t.track_round_s)
        elif self.module_id == "dva":
            duration = DVA_ROUND_S
        else:
            duration = PERIPHERAL_ROUND_S
        for i in range(t.rounds):
            plan.append(
                RoundPlan(
                    round_idx=i + 1,
                    is_warmup=False,
                    duration_s=duration,
                    adaptive=self.options.adaptive,
                    fixed_level=self.options.fixed_level,
                    mode=mode,
                )
            )
        return plan

    def on_enter(self) -> None:
        if not self.started:
            self.started = True
            self.session_id = self.app.storage.start_session(
                self._snapshot(), profile=self.app.settings.profile
            )
            self._begin_round(0)
            return
        self.app.input.exit_gameplay()
        if self.app.display_generation != self._display_gen:
            self._display_gen = self.app.display_generation
            self._restart_on_resume = True
            self.arena = geometry.arena_rect(
                (self.app.theme.width, self.app.theme.height)
            )
        self._layout_overlays()

    def on_exit(self) -> None:
        self.app.input.exit_gameplay()
        if self.session_id is not None and not self.session_finished:
            self.app.storage.finish_session(self.session_id, "incomplete")
            self.session_finished = True

    def on_eye_rest_start(self) -> None:
        if self.phase in ("playing", "countdown"):
            self._pause()
            self.pause_due_to_eye_rest = True

    def on_eye_rest_end(self) -> None:
        if self.pause_due_to_eye_rest and self.phase == "paused":
            self.pause_due_to_eye_rest = False
            self._resume()

    # ------------------------------------------------------------------ snapshot

    def _snapshot(self) -> dict:
        return {
            "app_version": APP_VERSION,
            "module": self.module_id,
            "mode": self.mode,
            "options": asdict(self.options),
            "settings": self.app.settings.snapshot(),
            "plan": [asdict(p) for p in self.plan],
            "display": {
                "width": self.app.theme.width,
                "height": self.app.theme.height,
                "refresh_rate": self.app.refresh_rate,
                "fullscreen": self.app.settings.display.fullscreen,
            },
            "arena": list(self.arena),
        }

    # -------------------------------------------------------------------- rounds

    def _begin_round(self, index: int) -> None:
        self.plan_index = index
        plan = self.plan[index]
        self.arena = geometry.arena_rect(
            (self.app.theme.width, self.app.theme.height)
        )
        seed = random.SystemRandom().getrandbits(63)
        px_per_deg = geometry.px_per_degree(
            self.app.theme.width,
            self.app.theme.height,
            self.app.settings.calibration.screen_diagonal_in,
            self.app.settings.calibration.view_distance_cm,
        )
        cfg = ModuleConfig(
            module_id=self.module_id,
            mode=plan.mode,
            duration_s=plan.duration_s,
            adaptive=plan.adaptive,
            fixed_level=plan.fixed_level,
            warmup=plan.is_warmup,
            extra={
                "seed": seed,
                "target_count": 3,
                "px_per_deg": px_per_deg,
            },
        )
        module_classes = {
            "flick": FlickModule,
            "track": TrackModule,
            "dva": DvaModule,
            "peripheral": PeripheralModule,
        }
        self.module = module_classes[self.module_id]()
        self.module.begin_round(cfg, seed, self.arena)
        self.round_t = 0.0
        self.phase = "countdown"
        self.phase_timer = 3.0
        self.paused_phase = None
        self.pause_due_to_eye_rest = False
        self._restart_on_resume = False
        self._pause_count = 0
        self._last_countdown_second = 4
        self._long_frames_start = self.app.frame_stats.long_frames
        self._round_started_at = utc_now()
        self.app.input.enter_gameplay(self.arena)
        self._layout_overlays()
        self.app.audio.play("countdown")

    def _start_playing(self) -> None:
        self.phase = "playing"
        self.phase_timer = 0.0

    def _end_round(self) -> None:
        if self.module is None:
            return
        plan = self.plan[self.plan_index]
        result = self.module.end_round(self.round_t)
        result.is_warmup = plan.is_warmup
        long_frames = max(
            0, self.app.frame_stats.long_frames - self._long_frames_start
        )
        result.summary["long_frames"] = long_frames
        result.summary["pauses"] = self._pause_count
        result.summary["round_idx"] = plan.round_idx
        if self.session_id is not None:
            self.app.storage.save_round(
                session_id=self.session_id,
                module=self.module_id,
                mode=plan.mode,
                round_idx=plan.round_idx,
                is_warmup=plan.is_warmup,
                duration_s=plan.duration_s,
                seed=result.seed,
                summary=result.summary,
                trials=result.trials,
                windows=result.windows,
                started_at=self._round_started_at,
                motion_blob=result.motion_blob,
                motion_format=result.motion_format,
                motion_count=result.motion_count,
            )
        self.results.append(result)
        if not plan.is_warmup:
            self.completed_main_rounds += 1
        self.app.input.exit_gameplay()
        self.app.audio.play("round_end")
        self._pause_count = 0

        if self.plan_index + 1 >= len(self.plan):
            self._finish_session("completed" if self._all_main_done() else "incomplete")
            return
        self.phase = "rest"
        self.phase_timer = float(self.app.settings.training.rest_s)
        if self.phase_timer <= 0:
            self._begin_round(self.plan_index + 1)

    def _all_main_done(self) -> bool:
        total_main = sum(1 for p in self.plan if not p.is_warmup)
        return self.completed_main_rounds >= total_main

    def _finish_session(self, status: str) -> None:
        if self.session_finished:
            return
        if self.session_id is not None:
            self.app.storage.finish_session(self.session_id, status)
        self.session_finished = True
        self.phase = "finished"
        self.app.input.exit_gameplay()
        self.app.notify_system(
            self.app.tr("EyesTrainer · 训练完成"),
            self.app.tr("本次训练已结束，结果已保存。建议休息 1–2 分钟。"),
        )
        from .results import ResultsScene

        self.app.switch_scene(
            ResultsScene(
                self.app,
                self.module_id,
                self.mode,
                self.options,
                list(self.results),
                self.plan,
                self.session_id,
            )
        )

    def _end_session_from_pause(self) -> None:
        if self.session_finished:
            return
        self._finish_session(
            "completed" if self._all_main_done() else "incomplete"
        )

    def _return_to_menu(self) -> None:
        if not self.session_finished and self.session_id is not None:
            self.app.storage.finish_session(self.session_id, "incomplete")
            self.session_finished = True
        self.app.input.exit_gameplay()
        from .menu import MenuScene

        self.app.switch_scene(MenuScene(self.app))

    # --------------------------------------------------------------------- pause

    def _pause(self) -> None:
        if self.phase not in ("playing", "countdown"):
            return
        self.paused_phase = self.phase
        self.phase = "paused"
        self._pause_count += 1
        self.app.input.exit_gameplay()
        self._layout_overlays()

    def _resume(self) -> None:
        if self.phase != "paused":
            return
        if self._restart_on_resume:
            self._restart_on_resume = False
            self._begin_round(self.plan_index)
            return
        self.phase = "countdown"
        self.phase_timer = 3.0
        self._last_countdown_second = 4
        self.app.input.enter_gameplay(self.arena, reset_crosshair=False)
        self._layout_overlays()
        self.app.audio.play("countdown")

    def _restart_round(self) -> None:
        if self.session_finished:
            return
        self._begin_round(self.plan_index)

    # -------------------------------------------------------------------- events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        self._frame_events = tuple(events)
        for event in events:
            if event.type in (
                pygame.WINDOWFOCUSLOST,
                pygame.ACTIVEEVENT,
            ):
                if getattr(event, "gain", 1) == 0 or event.type == pygame.WINDOWFOCUSLOST:
                    if self.phase in ("playing", "countdown"):
                        self._pause()
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.phase in ("playing", "countdown"):
                        self._pause()
                    elif self.phase == "paused":
                        self._resume()
                    elif self.phase == "rest":
                        self._begin_round(self.plan_index + 1)
                    return
                if self.phase == "rest" and event.key in (
                    pygame.K_RETURN,
                    pygame.K_SPACE,
                ):
                    self._begin_round(self.plan_index + 1)
                    return
                if self.phase == "paused":
                    if event.key == pygame.K_r:
                        self._restart_round()
                        return
                    if event.key == pygame.K_m:
                        self._return_to_menu()
                        return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.phase == "paused":
                    if self._handle_pause_click(event.pos):
                        return
                elif self.phase == "rest":
                    if self.rest_skip.hit(event.pos):
                        self.app.audio.play("click")
                        self._begin_round(self.plan_index + 1)
                        return

    def _handle_pause_click(self, pos: tuple[int, int]) -> bool:
        actions = {
            "resume": self._resume,
            "restart": self._restart_round,
            "end": self._end_session_from_pause,
            "settings": self._open_settings,
            "menu": self._return_to_menu,
        }
        for key, action in actions.items():
            button = self.buttons.get(key)
            if button is not None and button.hit(pos):
                self.app.audio.play("click")
                action()
                return True
        return False

    def _open_settings(self) -> None:
        from .settings import SettingsScene

        self.app.push_scene(SettingsScene(self.app))

    # -------------------------------------------------------------------- update

    def update(self, sim_dt: float, real_dt: float) -> None:
        if self.phase == "countdown":
            self.phase_timer -= real_dt
            second = max(1, int(math.ceil(self.phase_timer)))
            if second != self._last_countdown_second:
                self._last_countdown_second = second
                self.app.audio.play("countdown")
            if self.phase_timer <= 0:
                self._start_playing()
            return
        if self.phase == "playing":
            self.round_t += max(0.0, real_dt)
            self.app.input.update_motion(self.app.settings.input.sensitivity)
            base = self.app.input.frame()
            inp = InputFrame(
                base.crosshair,
                base.delta,
                base.lmb_down,
                base.lmb_pressed,
                base.lmb_released,
                self._frame_events,
            )
            if self.module is not None:
                self.module.handle_input(inp, self.round_t)
                self.module.update(sim_dt, self.round_t)
                if hasattr(self.module, "take_feedback"):
                    for name in self.module.take_feedback():
                        self.app.audio.play(name)
            self.app.eye_care.add_active(real_dt)
            if (
                self.phase == "playing"
                and self.module is not None
                and self.round_t >= self.plan[self.plan_index].duration_s
            ):
                self._end_round()
            return
        if self.phase == "rest":
            self.phase_timer -= max(0.0, real_dt)
            if self.phase_timer <= 0:
                self._begin_round(self.plan_index + 1)

    # ---------------------------------------------------------------------- draw

    def commit_frame(self) -> None:
        if self.phase == "playing" and self.module is not None:
            self.module.commit_frame(self.round_t)

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        if self.app.display_generation != self._display_gen:
            self._display_gen = self.app.display_generation
            self._layout_overlays()
        theme.draw_arena(surface, self.arena)
        plan = self.plan[self.plan_index] if self.plan_index < len(self.plan) else None
        if plan is None:
            return
        if self.phase == "playing" and self.module is not None:
            self.module.draw(surface, theme)
        if self.phase == "playing" and self.module is not None:
            if self.module_id in ("flick", "track"):
                cross = self.app.settings.input.crosshair
                draw_crosshair(
                    surface,
                    theme,
                    self.app.input.crosshair,
                    cross.style,
                    parse_color(cross.color),
                    cross.size,
                )
            draw_hud(
                surface,
                theme,
                plan.duration_s - self.round_t,
                getattr(self.module, "level", None),
            )
        elif self.phase == "countdown":
            draw_countdown(
                surface,
                theme,
                max(1, int(math.ceil(self.phase_timer))),
                self.arena,
            )
        elif self.phase == "rest":
            draw_dim(surface, theme, 205)
            self._draw_rest(surface)
        elif self.phase == "paused":
            draw_dim(surface, theme, 190)
            self._draw_pause(surface)

    def _layout_overlays(self) -> None:
        theme = self.app.theme
        cx = theme.width // 2
        width = int(420 * theme.ui)
        height = int(58 * theme.ui)
        gap = int(12 * theme.ui)
        y = int(theme.height * 0.52)
        items = [
            ("resume", self.app.tr("继续"), "primary"),
            ("restart", self.app.tr("重新开始本回合"), "secondary"),
            ("end", self.app.tr("结束本次训练"), "secondary"),
            ("settings", self.app.tr("设置"), "secondary"),
            ("menu", self.app.tr("返回主菜单"), "secondary"),
        ]
        self.buttons = {}
        for key, label, kind in items:
            self.buttons[key] = Button(
                pygame.Rect(cx - width // 2, y, width, height), label, kind=kind
            )
            y += height + gap
        self.rest_skip = Button(
            pygame.Rect(cx - int(160 * theme.ui), int(theme.height * 0.68), int(320 * theme.ui), int(52 * theme.ui)),
            self.app.tr("跳过休息（Enter）"),
        )

    def _draw_rest(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        theme.text(
            surface,
            self.app.tr("休息"),
            (theme.width // 2, int(theme.height * 0.34)),
            size=52,
            color=theme.accent,
            bold=True,
            anchor="center",
        )
        theme.text(
            surface,
            self.app.tr(
                "下一回合 {seconds} 秒后开始",
                seconds=max(0, math.ceil(self.phase_timer)),
            ),
            (theme.width // 2, int(theme.height * 0.43)),
            size=22,
            color=theme.text_color,
            anchor="center",
        )
        theme.text(
            surface,
            self.app.tr("放松手腕，眨眨眼，看向远处"),
            (theme.width // 2, int(theme.height * 0.48)),
            size=17,
            color=theme.muted,
            anchor="center",
        )
        next_plan = (
            self.plan[self.plan_index + 1]
            if self.plan_index + 1 < len(self.plan)
            else None
        )
        if next_plan is not None:
            theme.text(
                surface,
                self.app.tr(
                    "下一回合：热身"
                    if next_plan.is_warmup
                    else "下一回合：第 {round} 回合",
                    round=next_plan.round_idx,
                ),
                (theme.width // 2, int(theme.height * 0.54)),
                size=16,
                color=theme.muted,
                anchor="center",
            )
        self.rest_skip.draw(surface, theme, pygame.mouse.get_pos())

    def _draw_pause(self, surface: pygame.Surface) -> None:
        theme = self.app.theme
        theme.text(
            surface,
            self.app.tr("已暂停"),
            (theme.width // 2, int(theme.height * 0.34)),
            size=44,
            color=theme.text_color,
            bold=True,
            anchor="center",
        )
        plan = self.plan[self.plan_index]
        theme.text(
            surface,
            self.app.tr(
                "热身 · 剩余 {seconds}s"
                if plan.is_warmup
                else "第 {round} 回合 · 剩余 {seconds}s",
                round=plan.round_idx,
                seconds=f"{max(0, plan.duration_s - self.round_t):.0f}",
            ),
            (theme.width // 2, int(theme.height * 0.40)),
            size=17,
            color=theme.muted,
            anchor="center",
        )
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons.values():
            button.draw(surface, theme, mouse_pos)
        theme.text(
            surface,
            self.app.tr("Esc 继续 · R 重开本回合 · M 返回主菜单"),
            (theme.width // 2, theme.height - int(28 * theme.ui)),
            size=13,
            color=theme.muted,
            anchor="midbottom",
        )
