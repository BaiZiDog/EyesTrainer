from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionOptions:
    module_id: str = "flick"
    mode: str = "chain"
    adaptive: bool = True
    fixed_level: int = 50
