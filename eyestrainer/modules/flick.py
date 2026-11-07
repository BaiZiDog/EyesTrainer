from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

from ..core import geometry, metrics
from ..core.adaptive import FlickAdaptive, level_from_value, value_from_level
from ..core.geometry import RectTuple
from ..core.input import InputFrame
from ..core.motion import FMT_FLICK, MotionRecorder, flick_trial_analysis
from ..core.stats import clamp
from .base import ModuleConfig, RoundResult


@dataclass
class Target:
    target_id: int
    x: float
    y: float
    r: float
    level: float
    spawn_t: float | None = None


class FlickModule:
    module_id = "flick"

    CHAIN_MIN_R = 24.0
    CHAIN_MAX_R = 80.0
    CHAIN_INITIAL_R = 48.0
    REACTION_MIN_R = 28.0
    REACTION_MAX_R = 90.0
    REACTION_INITIAL_R = 56.0

    def __init__(self) -> None:
        self.cfg: ModuleConfig | None = None
        self.mode = "chain"
        self.arena: RectTuple = (0.0, 0.0, 1.0, 1.0)
        self.rng = random.Random(0)
        self.seed = 0
        self.duration_s = 60.0
        self.now_t = 0.0
        self.crosshair: tuple[float, float] = (0.0, 0.0)
        self.prev_crosshair: tuple[float, float] = (0.0, 0.0)
        self.firing = False
        self.targets: list[Target] = []
        self.reaction_target: Target | None = None
        self.trials: list[dict] = []
        self.trial_idx = 0
        self.next_target_id = 1
        self.radius = self.CHAIN_INITIAL_R
        self.level = 0.0
        self.adaptive: FlickAdaptive | None = None
        self.path_accum = 0.0
        self.prev_kill_pos: tuple[float, float] = (0.0, 0.0)
        self.hitmarks: list[tuple[float, float, float]] = []
        self.miss_flash_until = -1.0
        self.feedback_events: list[str] = []
        self.next_spawn_t = 0.0
        self.transition_until = 0.0
        self.crosshair_at_onset: tuple[float, float] | None = None
        self.first_move_done = False
        self.first_move_ms: float | None = None
        self._warmup = False
        self.motion = MotionRecorder(FMT_FLICK)
        self._last_motion_t = 0.0

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
        self.next_target_id = 1
        self.targets = []
        self.reaction_target = None
        self.hitmarks = []
        self.feedback_events = []
        self.miss_flash_until = -1.0
        self.path_accum = 0.0
        self.prev_kill_pos = (arena[0] + arena[2] / 2, arena[1] + arena[3] / 2)
        self.crosshair = self.prev_kill_pos
        self.prev_crosshair = self.crosshair
        self.now_t = 0.0
        self._warmup = cfg.warmup
        self.motion = MotionRecorder(FMT_FLICK)
        self._last_motion_t = 0.0

        if self.mode == "reaction":
            easy, hard, initial = (
                self.REACTION_MAX_R,
                self.REACTION_MIN_R,
                self.REACTION_INITIAL_R,
            )
        else:
            easy, hard, initial = (
                self.CHAIN_MAX_R,
                self.CHAIN_MIN_R,
                self.CHAIN_INITIAL_R,
            )

        adaptive_on = bool(cfg.adaptive) and not cfg.warmup
        if adaptive_on:
            self.radius = initial
            self.adaptive = FlickAdaptive(
                easy_radius=easy,
                hard_radius=hard,
                initial_radius=initial,
                window=15 if self.mode == "chain" else 12,
            )
        else:
            self.adaptive = None
            level = 0 if cfg.warmup else clamp(float(cfg.fixed_level), 0.0, 100.0)
            self.radius = value_from_level(level, easy, hard)
        self.level = level_from_value(self.radius, easy, hard)

        if self.mode == "reaction":
            self.next_spawn_t = self.rng.uniform(0.8, 2.0)
            self.transition_until = 0.0
            self.crosshair_at_onset = None
            self.first_move_done = False
            self.first_move_ms = None
        else:
            count = int(cfg.get("target_count", 3))
            for _ in range(max(1, count)):
                self._spawn_chain_target()

    def commit_frame(self, t: float) -> None:
        self.now_t = t
        if self.mode == "reaction":
            target = self.reaction_target
            if target is not None and target.spawn_t is None:
                target.spawn_t = t
                self.crosshair_at_onset = self.crosshair
                self.first_move_done = False
                self.first_move_ms = None
        else:
            for target in self.targets:
                if target.spawn_t is None:
                    target.spawn_t = t

    def handle_input(self, inp: InputFrame, t: float) -> None:
        self.now_t = t
        self.crosshair = inp.crosshair
        self.firing = inp.lmb_down
        movement = geometry.distance(inp.crosshair, self.prev_crosshair)
        dt = t - self._last_motion_t
        speed = movement / dt if dt > 1e-3 else 0.0
        self.path_accum += movement
        self._record_motion(t, speed, inp.lmb_down)
        self.prev_crosshair = inp.crosshair
        self._last_motion_t = t

        if self.mode == "reaction":
            target = self.reaction_target
            if (
                target is not None
                and target.spawn_t is not None
                and not self.first_move_done
                and self.crosshair_at_onset is not None
            ):
                threshold = max(3.0, target.r * 0.1)
                if geometry.distance(self.crosshair, self.crosshair_at_onset) > threshold:
                    self.first_move_done = True
                    self.first_move_ms = max(0.0, (t - target.spawn_t) * 1000.0)

        if inp.lmb_pressed:
            if self.mode == "reaction":
                self._reaction_click(t)
            else:
                self._chain_click(t)

    def update(self, dt: float, t: float) -> None:
        self.now_t = t
        self.hitmarks = [h for h in self.hitmarks if h[2] > t]
        if self.mode != "reaction":
            return
        if self.reaction_target is None and t >= max(self.next_spawn_t, self.transition_until):
            self._spawn_reaction_target()
        target = self.reaction_target
        if (
            target is not None
            and target.spawn_t is not None
            and t - target.spawn_t >= 1.5
        ):
            self._record_timeout(t)
            self._schedule_next(t)
            self.miss_flash_until = t + 0.06
            self.feedback_events.append("miss")

    def end_round(self, t: float) -> RoundResult:
        summary = metrics.summarize_flick(self.trials, self.mode, self.duration_s)
        summary.update(
            {
                "final_radius": self.radius,
                "final_level": self.level,
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
            motion_blob=self.motion.to_blob(),
            motion_format="flick",
            motion_count=self.motion.count,
            arena=self.arena,
        )

    def take_feedback(self) -> list[str]:
        events = self.feedback_events
        self.feedback_events = []
        return events

    def _nearest_target(self) -> Target | None:
        candidates = (
            [self.reaction_target]
            if self.mode == "reaction" and self.reaction_target is not None
            else list(self.targets)
        )
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda target: geometry.distance(
                self.crosshair, (target.x, target.y)
            ),
        )

    def _record_motion(self, t: float, speed: float, lmb_down: bool) -> None:
        target = self._nearest_target()
        if target is None:
            self.motion.add(
                t * 1000.0,
                self.crosshair[0],
                self.crosshair[1],
                target=None,
                err=0.0,
                speed=speed,
                level=self.level,
                lmb_down=lmb_down,
            )
            return
        err = geometry.distance(
            self.crosshair, (target.x, target.y)
        )
        self.motion.add(
            t * 1000.0,
            self.crosshair[0],
            self.crosshair[1],
            target=(target.x, target.y, target.r),
            err=err,
            speed=speed,
            level=self.level,
            target_id=target.target_id,
            lmb_down=lmb_down,
            on_target=err <= target.r,
        )

    # -------------------------------------------------------------------- spawning

    def _spawn_chain_target(self) -> Target:
        min_dist = float(self.cfg.get("min_spawn_dist", 180.0)) if self.cfg else 180.0
        target = self._make_target(min_dist, avoid_targets=True)
        self.targets.append(target)
        return target

    def _spawn_reaction_target(self) -> Target:
        target = self._make_target(250.0, avoid_targets=False)
        self.reaction_target = target
        self.crosshair_at_onset = self.crosshair
        self.first_move_done = False
        self.first_move_ms = None
        return target

    def _make_target(self, min_crosshair_dist: float, avoid_targets: bool) -> Target:
        radius = self.radius
        point: tuple[float, float] | None = None
        for attempt in range(220):
            candidate = geometry.random_point_in_rect(self.rng, self.arena, radius)
            current_min = min_crosshair_dist if attempt < 180 else min(100.0, min_crosshair_dist)
            if geometry.distance(candidate, self.crosshair) < current_min:
                continue
            if avoid_targets:
                overlap = False
                for other in self.targets:
                    if geometry.distance(candidate, (other.x, other.y)) < radius + other.r + 40:
                        overlap = True
                        break
                if overlap:
                    continue
            point = candidate
            break
        if point is None:
            point = geometry.random_point_in_rect(self.rng, self.arena, radius)
        target = Target(
            target_id=self.next_target_id,
            x=point[0],
            y=point[1],
            r=radius,
            level=self.level,
        )
        self.next_target_id += 1
        return target

    # --------------------------------------------------------------------- clicks

    def _charge_adaptive(self, hit: bool) -> None:
        if self.adaptive is None or self.cfg is None:
            return
        if self.adaptive.record(hit):
            self.radius = self.adaptive.radius
            if self.mode == "reaction":
                easy, hard = self.REACTION_MAX_R, self.REACTION_MIN_R
            else:
                easy, hard = self.CHAIN_MAX_R, self.CHAIN_MIN_R
            self.level = level_from_value(self.radius, easy, hard)

    def _chain_click(self, t: float) -> None:
        clicked = None
        for target in self.targets:
            if geometry.point_in_circle(self.crosshair, (target.x, target.y), target.r):
                clicked = target
                break
        if clicked is None:
            self._record_trial(
                outcome="miss_click",
                spawn_t=None,
                click_t=t,
                age_ms=None,
                target=None,
                click_err=None,
                path_px=None,
                ideal_px=None,
                level=self.level,
            )
            self.miss_flash_until = t + 0.06
            self._charge_adaptive(False)
            self.feedback_events.append("miss")
            return

        if clicked.spawn_t is None:
            clicked.spawn_t = t
        age_ms = max(0.0, (t - clicked.spawn_t) * 1000.0)
        click_err = geometry.click_error(
            self.crosshair, (clicked.x, clicked.y), clicked.r
        )
        ideal = geometry.distance(self.prev_kill_pos, (clicked.x, clicked.y))
        path_px = self.path_accum
        self._record_trial(
            outcome="hit",
            spawn_t=clicked.spawn_t,
            click_t=t,
            age_ms=age_ms,
            target=clicked,
            click_err=click_err,
            path_px=path_px,
            ideal_px=ideal,
            level=clicked.level,
        )
        self.targets.remove(clicked)
        self._spawn_chain_target()
        self.hitmarks.append((self.crosshair[0], self.crosshair[1], t + 0.08))
        self.feedback_events.append("hit")
        self._charge_adaptive(True)
        self.prev_kill_pos = self.crosshair
        self.path_accum = 0.0

    def _reaction_click(self, t: float) -> None:
        target = self.reaction_target
        if (
            target is not None
            and target.spawn_t is not None
            and t - target.spawn_t >= 1.5
        ):
            self._record_timeout(t)
            self._schedule_next(t)
            self.miss_flash_until = t + 0.06
            self.feedback_events.append("miss")
            return
        if target is None or target.spawn_t is None:
            self._record_trial(
                outcome="anticipation",
                spawn_t=None,
                click_t=t,
                age_ms=None,
                target=None,
                click_err=None,
                path_px=None,
                ideal_px=None,
                level=self.level,
            )
            self._charge_adaptive(False)
            self.feedback_events.append("miss")
            return

        if geometry.point_in_circle(self.crosshair, (target.x, target.y), target.r):
            age_ms = max(0.0, (t - target.spawn_t) * 1000.0)
            flags: list[str] = []
            if age_ms < 100.0:
                flags.append("anticipation")
            first_move = self.first_move_ms if self.first_move_done else None
            self._record_trial(
                outcome="hit",
                spawn_t=target.spawn_t,
                click_t=t,
                age_ms=age_ms,
                target=target,
                click_err=geometry.click_error(
                    self.crosshair, (target.x, target.y), target.r
                ),
                path_px=None,
                ideal_px=None,
                level=target.level,
                first_move_ms=first_move,
                flags=flags,
            )
            self.hitmarks.append((self.crosshair[0], self.crosshair[1], t + 0.08))
            self.feedback_events.append("hit")
            self._charge_adaptive(True)
            self._schedule_next(t)
        else:
            self._record_trial(
                outcome="miss_click",
                spawn_t=target.spawn_t,
                click_t=t,
                age_ms=max(0.0, (t - target.spawn_t) * 1000.0),
                target=target,
                click_err=geometry.click_error(
                    self.crosshair, (target.x, target.y), target.r
                ),
                path_px=None,
                ideal_px=None,
                level=target.level,
                first_move_ms=self.first_move_ms if self.first_move_done else None,
            )
            self.feedback_events.append("miss")
            self._charge_adaptive(False)

    def _record_timeout(self, t: float) -> None:
        target = self.reaction_target
        if target is not None:
            self._record_trial(
                outcome="timeout",
                spawn_t=target.spawn_t,
                click_t=None,
                age_ms=1500.0,
                target=target,
                click_err=None,
                path_px=None,
                ideal_px=None,
                level=target.level,
                first_move_ms=self.first_move_ms if self.first_move_done else None,
            )
        self._charge_adaptive(False)

    def _schedule_next(self, t: float) -> None:
        self.reaction_target = None
        self.crosshair_at_onset = None
        self.first_move_done = False
        self.first_move_ms = None
        self.transition_until = t + 0.6
        self.next_spawn_t = self.transition_until + self.rng.uniform(0.8, 2.0)

    def _record_trial(
        self,
        outcome: str,
        spawn_t: float | None,
        click_t: float | None,
        age_ms: float | None,
        target: Target | None,
        click_err: float | None,
        path_px: float | None,
        ideal_px: float | None,
        level: float,
        first_move_ms: float | None = None,
        flags: list[str] | None = None,
    ) -> None:
        self.trial_idx += 1
        advanced: dict = {}
        if target is not None and spawn_t is not None:
            end_t = click_t if click_t is not None else self.now_t
            advanced = flick_trial_analysis(
                self.motion.samples,
                spawn_t * 1000.0,
                end_t * 1000.0,
                target.x,
                target.y,
                target.r,
                hit=outcome == "hit",
            )
        self.trials.append(
            {
                "trial_idx": self.trial_idx,
                "outcome": outcome,
                "spawn_t": spawn_t,
                "click_t": click_t,
                "age_ms": age_ms,
                "first_move_ms": first_move_ms,
                "target_x": target.x if target else None,
                "target_y": target.y if target else None,
                "target_r": target.r if target else None,
                "cross_x": self.crosshair[0],
                "cross_y": self.crosshair[1],
                "click_err": click_err,
                "path_px": path_px,
                "ideal_px": ideal_px,
                "level": level,
                "flags": list(flags or []),
                "target_id": target.target_id if target else None,
                "entry_ms": advanced.get("entry_ms"),
                "correction_ms": advanced.get("correction_ms"),
                "overshoot_px": advanced.get("overshoot_px"),
                "overshoot_count": advanced.get("overshoot_count"),
                "direction_changes": advanced.get("direction_changes"),
                "peak_speed": advanced.get("peak_speed"),
                "curvature": advanced.get("curvature"),
            }
        )

    # --------------------------------------------------------------------- draw

    def draw(self, surf: pygame.Surface, theme) -> None:
        if self.mode == "reaction":
            target = self.reaction_target
            if target is not None and target.spawn_t is not None:
                self._draw_target(surf, theme, target)
        else:
            for target in self.targets:
                self._draw_target(surf, theme, target)
        for x, y, until in self.hitmarks:
            if until > self.now_t:
                self._draw_hitmark(surf, theme, (x, y))
        if self.miss_flash_until > self.now_t:
            rect = pygame.Rect(
                int(self.arena[0]),
                int(self.arena[1]),
                int(self.arena[2]),
                int(self.arena[3]),
            )
            pygame.draw.rect(surf, theme.warning, rect, width=3)

    def _draw_target(self, surf: pygame.Surface, theme, target: Target) -> None:
        center = (int(target.x), int(target.y))
        radius = max(2, int(target.r))
        pygame.draw.circle(surf, theme.target, center, radius)
        pygame.draw.circle(surf, theme.target_edge, center, radius, width=2)

    def _draw_hitmark(
        self, surf: pygame.Surface, theme, center: tuple[float, float]
    ) -> None:
        cx, cy = int(center[0]), int(center[1])
        size = max(5, int(8 * theme.ui))
        gap = max(2, int(3 * theme.ui))
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            start = (cx + dx * gap, cy + dy * gap)
            end = (cx + dx * (gap + size), cy + dy * (gap + size))
            pygame.draw.line(surf, theme.white, start, end, max(1, int(2 * theme.ui)))
