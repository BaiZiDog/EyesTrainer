from __future__ import annotations

import math
import random

import pygame

from ..core import geometry, metrics
from ..core.adaptive import TrackAdaptive, level_from_value, value_from_level
from ..core.geometry import RectTuple
from ..core.input import InputFrame
from ..core.motion import FMT_TRACK, MotionRecorder, track_window_analysis
from ..core.stats import clamp
from .base import ModuleConfig, RoundResult


class TrackModule:
    module_id = "track"

    EASY_SPEED = 220.0
    HARD_SPEED = 1100.0
    INITIAL_SPEED = 420.0
    TARGET_RADIUS = 40.0
    WINDOW_S = 5.0
    TURN_RATE_DEG = 300.0

    def __init__(self) -> None:
        self.cfg: ModuleConfig | None = None
        self.mode = "waypoint"
        self.arena: RectTuple = (0.0, 0.0, 1.0, 1.0)
        self.rng = random.Random(0)
        self.seed = 0
        self.duration_s = 30.0
        self.radius = self.TARGET_RADIUS
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.speed = self.INITIAL_SPEED
        self.target_speed = self.INITIAL_SPEED
        self.adaptive: TrackAdaptive | None = None
        self.level = 0.0
        self.crosshair: tuple[float, float] = (0.0, 0.0)
        self.firing = False
        self.now_t = 0.0
        self.waypoint: tuple[float, float] | None = None
        self.next_waypoint_t = 0.0
        self.windows: list[dict] = []
        self.window_idx = 0
        self.window_start = 0.0
        self.next_window_end = self.WINDOW_S
        self.fired_ms = 0.0
        self.ontarget_ms = 0.0
        self.err_weighted = 0.0
        self.max_err = 0.0
        self._last_on_target = False
        self.initial_x = 0.0
        self.initial_y = 0.0
        self.initial_heading = 0.0
        self.motion = MotionRecorder(FMT_TRACK)
        self._last_motion_t = 0.0
        self._prev_crosshair: tuple[float, float] = (0.0, 0.0)

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
        self.radius = float(cfg.get("target_radius", self.TARGET_RADIUS))
        self.windows = []
        self.window_idx = 0
        self.window_start = 0.0
        self.next_window_end = self.WINDOW_S
        self.fired_ms = 0.0
        self.ontarget_ms = 0.0
        self.err_weighted = 0.0
        self.max_err = 0.0
        self._last_on_target = False
        self.now_t = 0.0
        self.firing = False
        self.waypoint = None

        adaptive_on = bool(cfg.adaptive) and not cfg.warmup
        if adaptive_on:
            self.adaptive = TrackAdaptive(
                easy_speed=self.EASY_SPEED,
                hard_speed=self.HARD_SPEED,
                initial_speed=float(cfg.get("initial_speed", self.INITIAL_SPEED)),
            )
            self.target_speed = self.adaptive.speed
        else:
            self.adaptive = None
            level = 0 if cfg.warmup else clamp(float(cfg.fixed_level), 0.0, 100.0)
            self.target_speed = value_from_level(
                level, self.EASY_SPEED, self.HARD_SPEED
            )
        self.speed = self.target_speed
        self.level = level_from_value(
            self.target_speed, self.EASY_SPEED, self.HARD_SPEED
        )

        left, top, width, height = arena
        self.x = left + width * self.rng.uniform(0.35, 0.65)
        self.y = top + height * self.rng.uniform(0.35, 0.65)
        self.x = clamp(self.x, left + self.radius, left + width - self.radius)
        self.y = clamp(self.y, top + self.radius, top + height - self.radius)
        self.initial_x, self.initial_y = self.x, self.y
        if self.mode == "bounce":
            angle = self.rng.uniform(-math.radians(20), math.radians(20))
            if self.rng.random() < 0.5:
                angle += math.pi
            self.heading = angle
        else:
            self.heading = self.rng.uniform(0, 2 * math.pi)
            self._choose_waypoint(0.0)
        self.initial_heading = self.heading
        self.crosshair = (left + width / 2, top + height / 2)
        self._prev_crosshair = self.crosshair
        self._last_motion_t = 0.0
        self.motion = MotionRecorder(FMT_TRACK)

    def handle_input(self, inp: InputFrame, t: float) -> None:
        self.now_t = t
        self.crosshair = inp.crosshair
        self.firing = inp.lmb_down

    def commit_frame(self, t: float) -> None:
        self.now_t = t

    def update(self, dt: float, t: float) -> None:
        self.now_t = t
        self._move_target(dt, t)
        self._ramp_speed(dt)

        if self.firing:
            dt_ms = max(0.0, dt * 1000.0)
            dist = geometry.distance((self.x, self.y), self.crosshair)
            self.fired_ms += dt_ms
            if dist <= self.radius:
                self.ontarget_ms += dt_ms
            self.err_weighted += dist * dt_ms
            self.max_err = max(self.max_err, dist)
            self._last_on_target = dist <= self.radius

        dt_motion = t - self._last_motion_t
        movement = geometry.distance(self.crosshair, self._prev_crosshair)
        mouse_speed = movement / dt_motion if dt_motion > 1e-3 else 0.0
        err = geometry.distance((self.x, self.y), self.crosshair)
        self.motion.add(
            t * 1000.0,
            self.crosshair[0],
            self.crosshair[1],
            target=(self.x, self.y, self.radius),
            err=err,
            speed=mouse_speed,
            level=self.level,
            target_id=0,
            lmb_down=self.firing,
            on_target=err <= self.radius,
        )
        self._prev_crosshair = self.crosshair
        self._last_motion_t = t

        while t >= self.next_window_end:
            self._finalize_window(self.next_window_end)

        if self.mode == "waypoint" and t >= self.next_waypoint_t:
            self._choose_waypoint(t)

    def end_round(self, t: float) -> RoundResult:
        self._finalize_window(max(t, self.window_start))
        summary = metrics.summarize_track(
            self.windows, self.duration_s, self.radius
        )
        summary.update(
            {
                "final_speed": self.target_speed,
                "final_level": self.level,
                "radius": self.radius,
                "seed": self.seed,
            }
        )
        return RoundResult(
            module_id=self.module_id,
            mode=self.mode,
            duration_s=self.duration_s,
            seed=self.seed,
            summary=summary,
            windows=list(self.windows),
            is_warmup=bool(self.cfg and self.cfg.warmup),
            motion_blob=self.motion.to_blob(),
            motion_format="track",
            motion_count=self.motion.count,
            arena=self.arena,
        )

    # -------------------------------------------------------------------- motion

    def _move_target(self, dt: float, t: float) -> None:
        left, top, width, height = self.arena
        min_x = left + self.radius
        max_x = left + width - self.radius
        min_y = top + self.radius
        max_y = top + height - self.radius
        if self.mode == "bounce":
            self.x += math.cos(self.heading) * self.speed * dt
            self.y += math.sin(self.heading) * self.speed * dt
            hit_x = False
            hit_y = False
            if self.x < min_x:
                self.x = min_x + (min_x - self.x)
                hit_x = True
            elif self.x > max_x:
                self.x = max_x - (self.x - max_x)
                hit_x = True
            if self.y < min_y:
                self.y = min_y + (min_y - self.y)
                hit_y = True
            elif self.y > max_y:
                self.y = max_y - (self.y - max_y)
                hit_y = True
            vx = math.cos(self.heading)
            vy = math.sin(self.heading)
            if hit_x:
                vx = -vx
            if hit_y:
                vy = -vy
            self.heading = math.atan2(vy, vx)
            self.x = clamp(self.x, min_x, max_x)
            self.y = clamp(self.y, min_y, max_y)
        else:
            if self.waypoint is None:
                self._choose_waypoint(t)
            assert self.waypoint is not None
            desired = math.atan2(self.waypoint[1] - self.y, self.waypoint[0] - self.x)
            max_turn = math.radians(self.TURN_RATE_DEG) * dt
            self.heading = geometry.turn_towards(self.heading, desired, max_turn)
            self.x += math.cos(self.heading) * self.speed * dt
            self.y += math.sin(self.heading) * self.speed * dt
            clamped_x = clamp(self.x, min_x, max_x)
            clamped_y = clamp(self.y, min_y, max_y)
            if (clamped_x, clamped_y) != (self.x, self.y):
                self.x, self.y = clamped_x, clamped_y
                self._choose_waypoint(t)
            if geometry.distance((self.x, self.y), self.waypoint) < 12.0:
                self._choose_waypoint(t)

    def _choose_waypoint(self, t: float) -> None:
        left, top, width, height = self.arena
        inset = max(60.0, self.radius + 20.0)
        self.waypoint = (
            self.rng.uniform(left + inset, left + width - inset),
            self.rng.uniform(top + inset, top + height - inset),
        )
        self.next_waypoint_t = t + self.rng.uniform(0.8, 1.6)

    def _ramp_speed(self, dt: float) -> None:
        if abs(self.speed - self.target_speed) < 0.5:
            self.speed = self.target_speed
            return
        max_delta = (self.HARD_SPEED - self.EASY_SPEED) / 0.4 * dt
        if self.target_speed > self.speed:
            self.speed = min(self.target_speed, self.speed + max_delta)
        else:
            self.speed = max(self.target_speed, self.speed - max_delta)

    # ------------------------------------------------------------------- windows

    def _finalize_window(self, end_t: float) -> None:
        end_t = max(end_t, self.window_start)
        if self.windows and end_t - self.window_start < 1e-6:
            return
        fired = self.fired_ms
        ontarget = self.ontarget_ms
        mean_err = self.err_weighted / fired if fired > 0 else None
        advanced = track_window_analysis(
            self.motion.samples,
            self.window_start * 1000.0,
            end_t * 1000.0,
        )
        row = {
            "window_idx": self.window_idx,
            "t_start": self.window_start,
            "t_end": end_t,
            "fired_ms": fired,
            "ontarget_ms": ontarget,
            "mean_err_px": mean_err,
            "max_err_px": self.max_err if fired > 0 else None,
            "speed": self.target_speed,
            "level": self.level,
            "lag_ms": advanced.get("lag_ms"),
            "jitter": advanced.get("jitter"),
            "dir_changes": advanced.get("dir_changes"),
            "peak_speed": advanced.get("peak_speed"),
            "error_std": advanced.get("error_std"),
        }
        self.windows.append(row)
        self.window_idx += 1
        self.window_start = end_t
        self.next_window_end = end_t + self.WINDOW_S
        self.fired_ms = 0.0
        self.ontarget_ms = 0.0
        self.err_weighted = 0.0
        self.max_err = 0.0

        if self.adaptive is not None and fired > 0:
            tot = ontarget / fired
            if self.adaptive.update(tot, fired):
                self.target_speed = self.adaptive.speed
                self.level = level_from_value(
                    self.target_speed, self.EASY_SPEED, self.HARD_SPEED
                )

    # ---------------------------------------------------------------------- draw

    def draw(self, surf: pygame.Surface, theme) -> None:
        center = (int(self.x), int(self.y))
        radius = max(2, int(self.radius))
        pygame.draw.circle(surf, theme.target, center, radius)
        pygame.draw.circle(surf, theme.target_edge, center, radius, width=2)
        if self.firing and self._last_on_target:
            pygame.draw.circle(
                surf,
                theme.accent,
                center,
                radius + max(2, int(4 * theme.ui)),
                width=max(1, int(2 * theme.ui)),
            )
