from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from ..app import App


class Scene:
    def __init__(self, app: "App") -> None:
        self.app = app

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        pass

    def update(self, sim_dt: float, real_dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass

    def commit_frame(self) -> None:
        pass
