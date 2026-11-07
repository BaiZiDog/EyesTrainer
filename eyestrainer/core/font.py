from __future__ import annotations

from pathlib import Path

import pygame

_CANDIDATES_REGULAR = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]
_CANDIDATES_BOLD = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyhbd.ttf",
]
_SYS_NAMES = ["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "SimHei"]


def _first_existing(paths: list[str]) -> str | None:
    for raw in paths:
        if Path(raw).exists():
            return raw
    return None


class FontBook:
    def __init__(self) -> None:
        pygame.font.init()
        self._regular = _first_existing(_CANDIDATES_REGULAR)
        self._bold = _first_existing(_CANDIDATES_BOLD)
        self._cache: dict[tuple[int, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        size = max(8, int(size))
        key = (size, bold)
        if key in self._cache:
            return self._cache[key]
        path = self._bold if bold and self._bold else self._regular
        font: pygame.font.Font | None = None
        if path:
            try:
                font = pygame.font.Font(path, size)
            except (OSError, pygame.error):
                font = None
        if font is None:
            font = pygame.font.SysFont(_SYS_NAMES, size, bold=bold)
        self._cache[key] = font
        return font
