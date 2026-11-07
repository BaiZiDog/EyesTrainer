from __future__ import annotations

from dataclasses import dataclass

import pygame

from .geometry import RectTuple, clamp_point


@dataclass(frozen=True)
class InputFrame:
    crosshair: tuple[float, float]
    delta: tuple[float, float]
    lmb_down: bool
    lmb_pressed: bool
    lmb_released: bool
    events: tuple[pygame.event.Event, ...] = ()


class AimInput:
    """Owns the switch between OS cursor (menus) and relative aim (rounds)."""

    def __init__(self) -> None:
        self.relative = False
        self.crosshair: list[float] = [0.0, 0.0]
        self.delta: tuple[float, float] = (0.0, 0.0)
        self.lmb_down = False
        self.lmb_pressed = False
        self.lmb_released = False
        self._arena: RectTuple = (0.0, 0.0, 1.0, 1.0)
        self._warp_center: tuple[int, int] = (0, 0)
        self._use_warp_fallback = not hasattr(pygame.mouse, "set_relative_mode")

    def enter_gameplay(
        self, arena: RectTuple, reset_crosshair: bool = True
    ) -> None:
        self._arena = arena
        if reset_crosshair:
            self.crosshair = [arena[0] + arena[2] / 2, arena[1] + arena[3] / 2]
        else:
            self.crosshair[0], self.crosshair[1] = clamp_point(
                (self.crosshair[0], self.crosshair[1]), arena
            )
        self._warp_center = (int(self.crosshair[0]), int(self.crosshair[1]))
        self.lmb_down = False
        self.lmb_pressed = False
        self.lmb_released = False
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
        if self._use_warp_fallback:
            pygame.mouse.set_pos(self._warp_center)
        else:
            try:
                pygame.mouse.set_relative_mode(True)
            except (AttributeError, pygame.error):
                self._use_warp_fallback = True
                pygame.mouse.set_pos(self._warp_center)
        pygame.mouse.get_rel()
        self.relative = True
        self.delta = (0.0, 0.0)

    def exit_gameplay(self) -> None:
        if not self.relative:
            return
        if not self._use_warp_fallback:
            try:
                pygame.mouse.set_relative_mode(False)
            except (AttributeError, pygame.error):
                pass
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        try:
            pygame.mouse.set_pos((int(self.crosshair[0]), int(self.crosshair[1])))
        except pygame.error:
            pass
        self.relative = False
        self.lmb_down = False
        self.lmb_pressed = False
        self.lmb_released = False
        self.delta = (0.0, 0.0)
        pygame.mouse.get_rel()

    def begin_frame(self) -> None:
        self.lmb_pressed = False
        self.lmb_released = False
        if not self.relative:
            self.delta = (0.0, 0.0)
            return
        if self._use_warp_fallback:
            pos = pygame.mouse.get_pos()
            dx = pos[0] - self._warp_center[0]
            dy = pos[1] - self._warp_center[1]
            if dx or dy:
                pygame.mouse.set_pos(self._warp_center)
        else:
            dx, dy = pygame.mouse.get_rel()
        self.delta = (float(dx), float(dy))

    def process_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self.lmb_down:
                    self.lmb_pressed = True
                self.lmb_down = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.lmb_down = False
                self.lmb_released = True

    def update_motion(self, sensitivity: float) -> None:
        if not self.relative:
            return
        x = self.crosshair[0] + self.delta[0] * sensitivity
        y = self.crosshair[1] + self.delta[1] * sensitivity
        self.crosshair[0], self.crosshair[1] = clamp_point((x, y), self._arena)

    def frame(self) -> InputFrame:
        return InputFrame(
            crosshair=(self.crosshair[0], self.crosshair[1]),
            delta=self.delta,
            lmb_down=self.lmb_down,
            lmb_pressed=self.lmb_pressed,
            lmb_released=self.lmb_released,
        )
