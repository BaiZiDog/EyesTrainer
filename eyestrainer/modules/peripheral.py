from __future__ import annotations

import math
import random

import pygame

from ..core import geometry, metrics
from ..core.adaptive import PeripheralAdaptive, level_from_value, value_from_level
from ..core.geometry import RectTuple
from ..core.input import InputFrame
from .base import ModuleConfig, RoundResult


class PeripheralModule:
    module_id = "peripheral"

    EASY_DEG = 8.0
    HARD_DEG = 25.0
    INITIAL_DEG = 12.0
    EXPOSURE_MS = 150.0
    RESPONSE_WINDOW_S = 0.90
    FEEDBACK_S = 0.30
    TARGET_PROBABILITY = 0.60
    STIMULUS_COUNT = 3

    def __init__(self) -> None:
        self.cfg: ModuleConfig | None = None
        self.mode = "adaptive"
        self.arena: RectTuple = (0.0, 0.0, 1.0, 1.0)
        self.rng = random.Random(0)
        self.seed = 0
        self.duration_s = 60.0
        self.now_t = 0.0
        self.px_per_deg = 37.8
        self.stimulus_radius = 14.0
        self.trials: list[dict] = []
        self.trial_idx = 0
        self.state = "prepare"
        self.phase_end = 0.0
        self.trial: dict | None = None
        self.eccentricity = self.INITIAL_DEG
        self.adaptive: PeripheralAdaptive | None = None
        self.level = 0.0
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
        self.stimulus_radius = max(9.0, min(18.0, arena[3] * 0.016))
        if cfg.adaptive and not cfg.warmup:
            self.adaptive = PeripheralAdaptive(
                easy_deg=self.EASY_DEG,
                hard_deg=self.HARD_DEG,
                initial_deg=self.INITIAL_DEG,
                window=8,
            )
            self.eccentricity = self.adaptive.eccentricity
        else:
            self.adaptive = None
            level = 0 if cfg.warmup else max(0, min(100, int(cfg.fixed_level)))
            self.eccentricity = value_from_level(
                level, self.EASY_DEG, self.HARD_DEG
            )
        self.level = level_from_value(
            self.eccentricity, self.EASY_DEG, self.HARD_DEG
        )
        self.state = "prepare"
        self.phase_end = self.rng.uniform(0.4, 0.9)

    def handle_input(self, inp: InputFrame, t: float) -> None:
        self.now_t = t
        if self.state != "stimulus" or self.trial is None:
            return
        if self.trial.get("responded"):
            return
        if t > self.trial["response_deadline"]:
            return
        pressed = any(
            event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
            for event in inp.events
        )
        if pressed:
            self._finish_trial(t, responded=True)

    def update(self, dt: float, t: float) -> None:
        self.now_t = t
        if self.state == "prepare":
            if t >= self.phase_end:
                self._start_trial(t)
            return
        if self.state == "stimulus":
            if (
                self.trial is not None
                and not self.trial.get("responded")
                and t >= self.trial["response_deadline"]
            ):
                self._finish_trial(t, responded=False)
            return
        if self.state == "feedback" and t >= self.phase_end:
            self.state = "prepare"
            self.phase_end = t + self.rng.uniform(0.4, 0.9)

    def commit_frame(self, t: float) -> None:
        self.now_t = t

    def end_round(self, t: float) -> RoundResult:
        if self.state == "stimulus" and self.trial is not None:
            if not self.trial.get("responded"):
                self._finish_trial(t, responded=False, feedback=False)
        summary = metrics.summarize_peripheral(self.trials, self.duration_s)
        summary.update(
            {
                "final_eccentricity_deg": self.eccentricity,
                "final_level": self.level,
                "px_per_deg": self.px_per_deg,
                "exposure_ms": self.EXPOSURE_MS,
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
        target_present = self.rng.random() < self.TARGET_PROBABILITY
        center_x, center_y, positions = self._make_positions()
        target_index = self.rng.randrange(len(positions)) if target_present else -1
        stimuli = []
        for i, (x, y, angle, actual_deg) in enumerate(positions):
            stimuli.append(
                {
                    "x": x,
                    "y": y,
                    "angle": angle,
                    "actual_deg": actual_deg,
                    "is_target": i == target_index,
                }
            )
        actual_deg = (
            sum(item["actual_deg"] for item in stimuli) / len(stimuli)
        )
        target = next((s for s in stimuli if s["is_target"]), None)
        self.trial = {
            "trial_idx": self.trial_idx,
            "target_present": 1 if target_present else 0,
            "responded": False,
            "onset_t": t,
            "flash_end_t": t + self.EXPOSURE_MS / 1000.0,
            "response_deadline": t + self.RESPONSE_WINDOW_S,
            "stimuli": stimuli,
            "eccentricity_deg": actual_deg,
            "exposure_ms": self.EXPOSURE_MS,
            "stimulus_count": len(stimuli),
            "target_angle": target["angle"] if target else None,
            "level": self.level,
            "rt_ms": None,
        }
        self.state = "stimulus"

    def _make_positions(
        self,
    ) -> tuple[float, float, list[tuple[float, float, float, float]]]:
        left, top, width, height = self.arena
        cx = left + width / 2
        cy = top + height / 2
        side = 0.0 if self.rng.random() < 0.5 else 180.0
        offsets = [-30.0, -10.0, 10.0, 30.0]
        self.rng.shuffle(offsets)
        chosen = sorted(offsets[: self.STIMULUS_COUNT])
        requested_px = self.eccentricity * self.px_per_deg
        positions: list[tuple[float, float, float, float]] = []
        for offset in chosen:
            angle = math.radians(side + offset + self.rng.uniform(-3.0, 3.0))
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            max_r = requested_px
            margin = self.stimulus_radius + 8.0
            if abs(cos_a) > 1e-6:
                limit_x = (
                    (left + width - margin - cx) / cos_a
                    if cos_a > 0
                    else (left + margin - cx) / cos_a
                )
                max_r = min(max_r, abs(limit_x))
            if abs(sin_a) > 1e-6:
                limit_y = (
                    (top + height - margin - cy) / sin_a
                    if sin_a > 0
                    else (top + margin - cy) / sin_a
                )
                max_r = min(max_r, abs(limit_y))
            max_r = max(0.0, max_r)
            x = cx + cos_a * max_r
            y = cy + sin_a * max_r
            actual_deg = max_r / self.px_per_deg
            positions.append((x, y, math.degrees(angle), actual_deg))
        return cx, cy, positions

    def _finish_trial(
        self, t: float, responded: bool, feedback: bool = True
    ) -> None:
        if self.trial is None or self.trial.get("responded"):
            return
        trial = self.trial
        trial["responded"] = True
        target_present = bool(trial["target_present"])
        if responded:
            trial["rt_ms"] = max(
                0.0, (t - trial["onset_t"]) * 1000.0
            )
            if target_present:
                self.feedback_text = "命中"
                self.feedback_color = (57, 255, 136)
            else:
                self.feedback_text = "误报"
                self.feedback_color = (255, 79, 109)
        else:
            if target_present:
                self.feedback_text = "漏检"
                self.feedback_color = (255, 200, 87)
            else:
                self.feedback_text = "抑制正确"
                self.feedback_color = (139, 152, 169)
        correct = (target_present and responded) or (
            not target_present and not responded
        )
        false_alarm = responded and not target_present
        miss = target_present and not responded
        record = {
            "trial_idx": trial["trial_idx"],
            "target_present": 1 if target_present else 0,
            "responded": 1 if responded else 0,
            "correct": 1 if correct else 0,
            "false_alarm": 1 if false_alarm else 0,
            "miss": 1 if miss else 0,
            "rt_ms": trial["rt_ms"],
            "eccentricity_deg": trial["eccentricity_deg"],
            "exposure_ms": trial["exposure_ms"],
            "stimulus_count": trial["stimulus_count"],
            "target_angle": trial["target_angle"],
            "level": trial["level"],
        }
        self.trials.append(record)
        if target_present and responded:
            self.feedback_events.append("hit")
        elif false_alarm or miss:
            self.feedback_events.append("miss")
        if self.adaptive is not None:
            if self.adaptive.record(target_present, responded):
                self.eccentricity = self.adaptive.eccentricity
                self.level = level_from_value(
                    self.eccentricity, self.EASY_DEG, self.HARD_DEG
                )
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
        size = max(8, int(14 * theme.ui))
        color = theme.accent
        pygame.draw.line(surf, color, (int(cx - size), int(cy)), (int(cx - 3), int(cy)), 2)
        pygame.draw.line(surf, color, (int(cx + 3), int(cy)), (int(cx + size), int(cy)), 2)
        pygame.draw.line(surf, color, (int(cx), int(cy - size)), (int(cx), int(cy - 3)), 2)
        pygame.draw.line(surf, color, (int(cx), int(cy + 3)), (int(cx), int(cy + size)), 2)
        pygame.draw.circle(surf, color, (int(cx), int(cy)), 1)

        if (
            self.state == "stimulus"
            and self.trial is not None
            and self.now_t <= self.trial["flash_end_t"]
        ):
            for stimulus in self.trial["stimuli"]:
                center = (int(stimulus["x"]), int(stimulus["y"]))
                radius = max(4, int(self.stimulus_radius))
                if stimulus["is_target"]:
                    pygame.draw.circle(surf, theme.accent, center, radius)
                else:
                    pygame.draw.circle(
                        surf,
                        theme.white,
                        center,
                        radius,
                        width=max(2, int(2 * theme.ui)),
                    )
        if self.state == "feedback" and self.feedback_text:
            theme.text(
                surf,
                self.feedback_text,
                (cx, cy + height * 0.20),
                size=20,
                color=self.feedback_color,
                bold=True,
                anchor="center",
            )
        theme.text(
            surf,
            "注视中央十字 · 空格：报告实心目标",
            (cx, top + height - 22 * theme.ui),
            size=14,
            color=theme.muted,
            anchor="midbottom",
        )
