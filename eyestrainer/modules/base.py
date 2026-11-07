from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import pygame

from ..core.geometry import RectTuple
from ..core.input import InputFrame


@dataclass
class ModuleConfig:
    module_id: str
    mode: str
    duration_s: float
    adaptive: bool
    fixed_level: int = 50
    warmup: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class RoundResult:
    module_id: str
    mode: str
    duration_s: float
    seed: int
    summary: dict[str, Any]
    trials: list[dict[str, Any]] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    is_warmup: bool = False
    motion_blob: bytes | None = None
    motion_format: str = ""
    motion_count: int = 0
    arena: tuple[float, float, float, float] | None = None


class TrainingModule(Protocol):
    module_id: str

    def begin_round(
        self, cfg: ModuleConfig, seed: int, arena: RectTuple
    ) -> None: ...

    def handle_input(self, inp: InputFrame, t: float) -> None: ...

    def update(self, dt: float, t: float) -> None: ...

    def draw(self, surf: pygame.Surface, theme: Any) -> None: ...

    def commit_frame(self, t: float) -> None: ...

    def end_round(self, t: float) -> RoundResult: ...
