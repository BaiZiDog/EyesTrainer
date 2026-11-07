from __future__ import annotations

import math
import random

import pygame

from ..core import geometry, metrics
from ..core.adaptive import DvaStaircase, level_from_value, value_from_level
from ..core.geometry import RectTuple
from ..core.input import InputFrame
from .base import ModuleConfig, RoundResult

# Gap direction indices: 0=right, 1=up, 2=left, 3=down.
_DIR_ANGLE = {0: 0.0, 1: -90.0, 2: 180.0, 3: 90.0}
_KEY_TO_DIR = {
    pygame.K_RIGHT: 0,
    pygame.K_d: 0,
    pygame.K_UP: 1,
    pygame.K_w: 1,
    pygame.K_LEFT: 2,
    pygame.K_a: 2,
    pygame.K_DOWN: 3,
    pygame.K_s: 3,
}
_DIR_NAMES = {0: "右", 1: "上", 2: "左", 3: "下"}


class DvaModule:
    module_id = "dva"

    MIN_DEG_S = 8.0
    MAX_DEG_S = 60.0
    INITIAL_DEG_S = 20.0
    GAP_HALF_DEG = 18.0
    FEEDBACK_S = 0.28
    POST_EXIT_S = 0.30

    def __init__(self) -> None:
        self.cfg: ModuleConfig | None = None
        self.mode = "staircase"
        self.arena: RectTuple = (0.0, 0.0, 1.0, 1.0)
        self.rng = random.Random(0)
        self.seed = 0
        self.duration_s = 90.0
        self.now_t = 0.0
        self.px_per_deg = 37.8
        self.radius = 32.0
        self.trials: list[dict] = []
        self.trial_idx = 0
        self.state = "prepare"
        self.phase_end = 0.0
        self.trial: dict | None = None
        self.start_x = 0.0
        self.move_dir = 1
        self.speed = 0.0
        self.level = 0.0
        self.staircase: DvaStaircase | None = None
        self.feedback_text = ""
        self.feedback_color = (255, 255, 255)
        self.feedback_events: list[str] = []

    # ------------------------------------------------------------------ lifecycle

    def begin_round(
        self, cfg: ModuleConfig, seed: int, arena: RectTuple
    ) -> None:
        self.cfg = cfg
        self.mode = cfg.mode
        self.arena = arena
        self.duration_s = cfg.duration_s
        self.rng = random.Random(seed)
        self.seed = int(seed)
        self.trials = []
        self.trial_idx = 0
        self.now_t = 0.0
        self.trial = None
        self.feedback_text = ""
        self.feedback_events = []
        self.px_per_deg = max(1.0, float(cfg.get("px_per_deg", 37.8)))
        self.radius = max(
            22.0,
            min(40.0, arena[3] * 0.034),
        )
        min_speed = self.px_per_deg * self.MIN_DEG_S
        max_speed = self.px_per_deg * self.MAX_DEG_S
        if cfg.adaptive and not cfg.warmup:
            self.staircase = DvaStaircase(
                min_speed=min_speed,
                max_speed=max_speed,
                initial_speed=self.px_per_deg * self.INITIAL_DEG_S,
            )
            self.speed = self.staircase.speed
        else:
            self.staircase = None
            level = 0 if cfg.warmup else max(0, min(100, int(cfg.fixed_level)))
            self.speed = value_from_level(level, min_speed, max_speed)
            if cfg.warmup:
                self.speed = self.px_per_deg * 12.0
        self.level = level_from_value(self.speed, min_speed, max_speed)
        self.state = "prepare"
        self.phase_end = self.rng.uniform(0.4, 0.8)

    def handle_input(self, inp: InputFrame, t: float) -> None:
        self.now_t = t
        if self.state != "moving" or self.trial is None:
            return
        if self.trial.get("responded"):
            return
        if t > self.trial["response_deadline"]:
            return
        direction = None
        for event in inp.events:
            if event.type == pygame.KEYDOWN and event.key in _KEY_TO_DIR:
                direction = _KEY_TO_DIR[event.key]
                break
        if direction is None:
            return
        self._finish_trial(t, direction)

    def update(self, dt: float, t: float) -> None:
        self.now_t = t
        if self.state == "prepare":
            if t >= self.phase_end:
                self._start_trial(t)
            return
        if self.state == "moving":
            if self.trial is None:
                return
            if t >= self.trial["response_deadline"]:
                self._finish_trial(t, None)
            return
        if self.state == "feedback" and t >= self.phase_end:
            self.state = "prepare"
            self.phase_end = t + self.rng.uniform(0.35, 0.75)

    def commit_frame(self, t: float) -> None:
        self.now_t = t

    def end_round(self, t: float) -> RoundResult:
        # Close an unfinished trial so metrics do not silently lose it.
        if self.state == "moving" and self.trial is not None:
            self._finish_trial(t, None, feedback=False)
        summary = metrics.summarize_dva(self.trials, self.duration_s)
        summary.update(
            {
                "final_speed_px_s": self.speed,
                "final_speed_deg_s": self.speed / self.px_per_deg,
                "px_per_deg": self.px_per_deg,
                "seed": self.seed,
            }
        )
        return RoundResult(
            module_id=self.module_id,
            mode=self.mode,
            duration_s=self.duration_s,
            seed=self.seed,
            summary=summary,
            trials=list(self.trials),
            is_warmup=bool(self.cfg and self.cfg.warmup),
        )

    # -------------------------------------------------------------------- trials

    def _start_trial(self, t: float) -> None:
        self.trial_idx += 1
        gap_dir = self.rng.randrange(4)
        self.move_dir = 1 if self.rng.random() < 0.5 else -1
        left, top, width, height = self.arena
        y = self.rng.uniform(top + self.radius, top + height - self.radius)
        start_x = left - self.radius if self.move_dir > 0 else left + width + self.radius
        travel = width + 2 * self.radius
        visible_end = t + travel / max(1.0, self.speed)
        self.start_x = start_x
        self.trial = {
            "trial_idx": self.trial_idx,
            "speed_px_s": self.speed,
            "speed_deg_s": self.speed / self.px_per_deg,
            "gap_dir": gap_dir,
            "response": None,
            "correct": 0,
            "timeout": 0,
            "rt_ms": None,
            "start_t": t,
            "visible_end_t": visible_end,
            "response_deadline": visible_end + self.POST_EXIT_S,
            "target_y": y,
            "radius": self.radius,
            "level": self.level,
            "reversal": 0,
            "responded": False,
        }
        self.state = "moving"

    def _finish_trial(self, t: float, response: int | None, feedback: bool = True) -> None:
        if self.trial is None or self.trial.get("responded"):
            return
        trial = self.trial
        trial["responded"] = True
        if response is None:
            trial["timeout"] = 1
            trial["correct"] = 0
            self.feedback_text = "超时"
            self.feedback_color = (255, 200, 87)
        else:
            trial["response"] = response
            correct = response == trial["gap_dir"]
            trial["correct"] = 1 if correct else 0
            trial["rt_ms"] = max(0.0, (t - trial["start_t"]) * 1000.0)
            self.feedback_text = "正确" if correct else f"错误，缺口朝{_DIR_NAMES[trial['gap_dir']]}"
            self.feedback_color = (
                (57, 255, 136) if correct else (255, 79, 109)
            )
        if self.staircase is not None:
            reversal = self.staircase.record(bool(trial["correct"]))
            trial["reversal"] = 1 if reversal else 0
            self.speed = self.staircase.speed
            trial_level = level_from_value(
                self.speed,
                self.px_per_deg * self.MIN_DEG_S,
                self.px_per_deg * self.MAX_DEG_S,
            )
        else:
            trial_level = level_from_value(
                self.speed,
                self.px_per_deg * self.MIN_DEG_S,
                self.px_per_deg * self.MAX_DEG_S,
            )
        self.level = trial_level
        self.trials.append(
            {k: v for k, v in trial.items() if k != "responded"}
        )
        self.feedback_events.append("hit" if trial["correct"] else "miss")
        self.trial = None
        if feedback:
            self.state = "feedback"
            self.phase_end = t + self.FEEDBACK_S
        else:
            self.state = "prepare"

    def take_feedback(self) -> list[str]:
        events = self.feedback_events
        self.feedback_events = []
        return events

    # ---------------------------------------------------------------------- draw

    def draw(self, surf: pygame.Surface, theme) -> None:
        left, top, width, height = self.arena
        cx = left + width / 2
        cy = top + height / 2
        pygame.draw.line(
            surf, theme.muted, (int(cx - 6 * theme.ui), int(cy)), (int(cx + 6 * theme.ui), int(cy)), 1
        )
        pygame.draw.line(
            surf, theme.muted, (int(cx), int(cy - 6 * theme.ui)), (int(cx), int(cy + 6 * theme.ui)), 1
        )
        if self.state == "moving" and self.trial is not None:
            elapsed = max(0.0, self.now_t - self.trial["start_t"])
            x = self.start_x + self.move_dir * self.speed * elapsed
            self._draw_landolt(
                surf,
                theme,
                (x, self.trial["target_y"]),
                self.radius,
                self.trial["gap_dir"],
            )
        elif self.state == "feedback" and self.feedback_text:
            theme.text(
                surf,
                self.feedback_text,
                (cx, cy + height * 0.28),
                size=22,
                color=self.feedback_color,
                bold=True,
                anchor="center",
            )
        theme.text(
            surf,
            "方向键 / WASD 判断缺口方向",
            (cx, top + height - 22 * theme.ui),
            size=14,
            color=theme.muted,
            anchor="midbottom",
        )

    def _draw_landolt(
        self,
        surf: pygame.Surface,
        theme,
        center: tuple[float, float],
        radius: float,
        gap_dir: int,
    ) -> None:
        gap_angle = _DIR_ANGLE[gap_dir]
        stroke = max(3.0, radius * 0.22)
        cx, cy = center
        inner = radius - stroke / 2
        outer = radius + stroke / 2
        width = max(2, int(stroke))
        for angle_deg in range(0, 360, 3):
            diff = abs((angle_deg - gap_angle + 180.0) % 360.0 - 180.0)
            if diff < self.GAP_HALF_DEG:
                continue
            angle = math.radians(angle_deg)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            pygame.draw.line(
                surf,
                theme.white,
                (int(cx + cos_a * inner), int(cy + sin_a * inner)),
                (int(cx + cos_a * outer), int(cy + sin_a * outer)),
                width,
            )
