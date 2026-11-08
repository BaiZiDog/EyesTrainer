from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .core.i18n import DEFAULT_LANGUAGE, normalize_language

APP_NAME = "EyesTrainer"
APP_VERSION = "0.5.0"

_CROSSHAIR_STYLES = {"cross_dot", "dot", "cross"}
_VALID_COLORS = {"#39FF88", "#4FA3FF", "#FFD166", "#FFFFFF", "#FF4F6D"}


@dataclass
class DisplayConfig:
    fullscreen: bool = True
    fps_cap: int = 0  # 0 means "match the detected refresh rate"
    vsync: bool = False
    low_latency: bool = True
    ui_scale: str = "auto"


@dataclass
class CrosshairConfig:
    style: str = "cross_dot"
    color: str = "#39FF88"
    size: int = 12


@dataclass
class InputConfig:
    sensitivity: float = 1.0
    crosshair: CrosshairConfig = field(default_factory=CrosshairConfig)


@dataclass
class AudioConfig:
    volume: float = 0.3
    hit: bool = True
    miss: bool = True
    round_end: bool = True


@dataclass
class TrainingConfig:
    warmup: bool = True
    adaptive: bool = True
    flick_round_s: int = 60
    track_round_s: int = 30
    rounds: int = 3
    rest_s: int = 15


@dataclass
class EyeCareConfig:
    reminder_min: int = 25


@dataclass
class CalibrationConfig:
    screen_diagonal_in: float = 24.0
    view_distance_cm: float = 60.0


@dataclass
class UserSettings:
    version: int = 1
    profile: str = "default"
    language: str = DEFAULT_LANGUAGE
    display: DisplayConfig = field(default_factory=DisplayConfig)
    input: InputConfig = field(default_factory=InputConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    eye_care: EyeCareConfig = field(default_factory=EyeCareConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "UserSettings":
        settings = cls()
        if not isinstance(data, dict):
            return settings
        settings.profile = _as_str(data.get("profile"), settings.profile)
        settings.language = normalize_language(data.get("language"))
        settings.display = _load_section(DisplayConfig, data.get("display"))
        settings.input = _load_input(data.get("input"))
        settings.audio = _load_section(AudioConfig, data.get("audio"))
        settings.training = _load_section(TrainingConfig, data.get("training"))
        settings.eye_care = _load_section(EyeCareConfig, data.get("eye_care"))
        settings.calibration = _load_section(CalibrationConfig, data.get("calibration"))
        settings.sanitize()
        return settings

    def sanitize(self) -> None:
        self.language = normalize_language(self.language)

        d = self.display
        d.fullscreen = bool(d.fullscreen)
        d.vsync = bool(d.vsync)
        d.low_latency = bool(d.low_latency)
        if d.fps_cap not in (0, 60, 120, 144, 165, 240, 360):
            d.fps_cap = 0
        if d.ui_scale not in ("auto",):
            d.ui_scale = "auto"

        i = self.input
        i.sensitivity = _clamp(_as_float(i.sensitivity, 1.0), 0.1, 5.0)
        c = i.crosshair
        if c.style not in _CROSSHAIR_STYLES:
            c.style = "cross_dot"
        if c.color.upper() not in _VALID_COLORS:
            c.color = "#39FF88"
        else:
            c.color = c.color.upper()
        c.size = int(_clamp(_as_float(c.size, 12), 6, 32))

        a = self.audio
        a.volume = _clamp(_as_float(a.volume, 0.3), 0.0, 1.0)
        a.hit = bool(a.hit)
        a.miss = bool(a.miss)
        a.round_end = bool(a.round_end)

        t = self.training
        t.warmup = bool(t.warmup)
        t.adaptive = bool(t.adaptive)
        t.flick_round_s = int(_clamp(_as_float(t.flick_round_s, 60), 20, 180))
        t.track_round_s = int(_clamp(_as_float(t.track_round_s, 30), 15, 120))
        t.rounds = int(_clamp(_as_float(t.rounds, 3), 1, 5))
        t.rest_s = int(_clamp(_as_float(t.rest_s, 15), 0, 60))

        e = self.eye_care
        if e.reminder_min not in (0, 15, 25, 40):
            e.reminder_min = 25

        cal = self.calibration
        cal.screen_diagonal_in = _clamp(
            _as_float(cal.screen_diagonal_in, 24.0), 10.0, 80.0
        )
        cal.view_distance_cm = _clamp(
            _as_float(cal.view_distance_cm, 60.0), 20.0, 200.0
        )

    def snapshot(self) -> dict[str, Any]:
        return self.to_dict()


def _is_packaged() -> bool:
    if getattr(sys, "frozen", False):
        return True
    if "__compiled__" in globals():
        return True
    executable = Path(sys.executable).name.lower()
    if executable.startswith("python") or executable.startswith("py"):
        return False
    return True


@dataclass
class AppPaths:
    data_dir: Path
    db_path: Path
    settings_path: Path
    export_dir: Path
    log_dir: Path

    @classmethod
    def default(cls) -> "AppPaths":
        env = os.environ.get("EYESTRAINER_DATA_DIR")
        if env:
            data_dir = Path(env).expanduser().resolve()
        elif _is_packaged():
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
            data_dir = base / APP_NAME
        else:
            data_dir = Path(__file__).resolve().parent.parent / "data"
        return cls(
            data_dir=data_dir,
            db_path=data_dir / "eyestrainer.db",
            settings_path=data_dir / "settings.json",
            export_dir=data_dir / "exports",
            log_dir=data_dir / "logs",
        )

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


class SettingsStore:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> UserSettings:
        self.paths.ensure()
        path = self.paths.settings_path
        if not path.exists():
            return UserSettings()
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return UserSettings.from_dict(data)
        except (OSError, ValueError, TypeError):
            try:
                bad = path.with_suffix(".json.bad")
                if bad.exists():
                    bad.unlink()
                path.replace(bad)
            except OSError:
                pass
            return UserSettings()

    def save(self, settings: UserSettings) -> None:
        self.paths.ensure()
        settings.sanitize()
        path = self.paths.settings_path
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)


def _load_section(cls: type, data: Any):
    obj = cls()
    if not isinstance(data, dict):
        return obj
    for f in fields(cls):
        if f.name not in data:
            continue
        current = getattr(obj, f.name)
        value = data[f.name]
        if isinstance(current, bool):
            setattr(obj, f.name, bool(value))
        elif isinstance(current, int):
            try:
                setattr(obj, f.name, int(value))
            except (TypeError, ValueError):
                pass
        elif isinstance(current, float):
            try:
                setattr(obj, f.name, float(value))
            except (TypeError, ValueError):
                pass
        elif isinstance(current, str):
            setattr(obj, f.name, str(value))
    return obj


def _load_input(data: Any) -> InputConfig:
    if not isinstance(data, dict):
        return InputConfig()
    cross = data.get("crosshair")
    cross_cfg = CrosshairConfig()
    if isinstance(cross, dict):
        for f in fields(CrosshairConfig):
            if f.name in cross:
                setattr(cross_cfg, f.name, cross[f.name])
    return InputConfig(
        sensitivity=_as_float(data.get("sensitivity"), 1.0),
        crosshair=cross_cfg,
    )


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:40]
    return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
