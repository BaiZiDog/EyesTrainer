from __future__ import annotations

import math
import statistics
import struct
import zlib
from dataclasses import dataclass
from typing import Iterable, Sequence

MAGIC = b"ETM1"
VERSION = 1
FMT_FLICK = 1
FMT_TRACK = 2
MAX_SAMPLES = 120_000

FLAG_LMB = 1
FLAG_ON_TARGET = 2
FLAG_HAS_TARGET = 4

_HEADER = struct.Struct("<4sHHI")
_SAMPLE = struct.Struct("<9fih")


@dataclass(frozen=True, slots=True)
class MotionSample:
    t_ms: float
    x: float
    y: float
    target_x: float
    target_y: float
    target_r: float
    err: float
    speed: float
    level: float
    target_id: int
    flags: int

    @property
    def lmb_down(self) -> bool:
        return bool(self.flags & FLAG_LMB)

    @property
    def on_target(self) -> bool:
        return bool(self.flags & FLAG_ON_TARGET)

    @property
    def has_target(self) -> bool:
        return bool(self.flags & FLAG_HAS_TARGET)


class MotionRecorder:
    def __init__(self, fmt: int) -> None:
        self.fmt = fmt
        self._samples: list[MotionSample] = []

    @property
    def samples(self) -> list[MotionSample]:
        return self._samples

    @property
    def count(self) -> int:
        return len(self._samples)

    def add(
        self,
        t_ms: float,
        x: float,
        y: float,
        *,
        target: tuple[float, float, float] | None,
        err: float,
        speed: float,
        level: float,
        target_id: int = -1,
        lmb_down: bool = False,
        on_target: bool = False,
    ) -> None:
        if len(self._samples) >= MAX_SAMPLES:
            return
        flags = 0
        if lmb_down:
            flags |= FLAG_LMB
        if on_target:
            flags |= FLAG_ON_TARGET
        if target is not None:
            flags |= FLAG_HAS_TARGET
            tx, ty, tr = target
        else:
            tx = ty = tr = 0.0
            target_id = -1
        self._samples.append(
            MotionSample(
                t_ms=float(t_ms),
                x=float(x),
                y=float(y),
                target_x=float(tx),
                target_y=float(ty),
                target_r=float(tr),
                err=float(err),
                speed=float(speed),
                level=float(level),
                target_id=int(target_id),
                flags=flags,
            )
        )

    def to_blob(self) -> bytes | None:
        return encode_samples(self._samples, self.fmt)


def encode_samples(samples: Sequence[MotionSample], fmt: int) -> bytes | None:
    if not samples:
        return None
    buf = bytearray(_HEADER.pack(MAGIC, VERSION, fmt, len(samples)))
    pack = _SAMPLE.pack
    for s in samples:
        buf += pack(
            s.t_ms,
            s.x,
            s.y,
            s.target_x,
            s.target_y,
            s.target_r,
            s.err,
            s.speed,
            s.level,
            s.target_id,
            s.flags,
        )
    return zlib.compress(bytes(buf), 6)


def decode_blob(blob: bytes) -> tuple[int, list[MotionSample]]:
    try:
        raw = zlib.decompress(blob)
    except zlib.error as exc:
        raise ValueError("invalid motion blob") from exc
    if len(raw) < _HEADER.size:
        raise ValueError("motion blob is too short")
    magic, version, fmt, count = _HEADER.unpack_from(raw, 0)
    if magic != MAGIC or version != VERSION:
        raise ValueError("unsupported motion blob")
    expected = _HEADER.size + count * _SAMPLE.size
    if len(raw) < expected:
        raise ValueError("motion blob is truncated")
    samples: list[MotionSample] = []
    offset = _HEADER.size
    unpack = _SAMPLE.unpack_from
    for _ in range(count):
        values = unpack(raw, offset)
        offset += _SAMPLE.size
        samples.append(MotionSample(*values))
    return fmt, samples


def slice_samples(
    samples: Iterable[MotionSample], start_ms: float, end_ms: float
) -> list[MotionSample]:
    return [s for s in samples if start_ms - 8.0 <= s.t_ms <= end_ms + 8.0]


def downsample(samples: Sequence[MotionSample], max_points: int = 600) -> list[MotionSample]:
    if len(samples) <= max_points:
        return list(samples)
    step = max(1, len(samples) // max_points)
    result = list(samples[::step])
    if result and result[-1] is not samples[-1]:
        result.append(samples[-1])
    return result


def _velocities(samples: Sequence[MotionSample]) -> list[tuple[float, float, float, float]]:
    """Return (t_ms, vx, vy, speed) for consecutive samples."""
    result: list[tuple[float, float, float, float]] = []
    prev = samples[0]
    for sample in samples[1:]:
        dt = (sample.t_ms - prev.t_ms) / 1000.0
        if dt <= 1e-5:
            prev = sample
            continue
        vx = (sample.x - prev.x) / dt
        vy = (sample.y - prev.y) / dt
        result.append((sample.t_ms, vx, vy, math.hypot(vx, vy)))
        prev = sample
    return result


def _direction_changes(
    velocities: Sequence[tuple[float, float, float, float]],
    min_speed: float = 80.0,
    angle_deg: float = 40.0,
) -> int:
    count = 0
    threshold = math.cos(math.radians(angle_deg))
    prev: tuple[float, float, float, float] | None = None
    for item in velocities:
        if item[3] < min_speed:
            continue
        if prev is not None and prev[3] >= min_speed:
            denom = prev[3] * item[3]
            if denom > 0:
                dot = (prev[1] * item[1] + prev[2] * item[2]) / denom
                if dot < threshold:
                    count += 1
        prev = item
    return count


def flick_trial_analysis(
    samples: Sequence[MotionSample],
    spawn_ms: float,
    end_ms: float,
    target_x: float,
    target_y: float,
    target_r: float,
    *,
    hit: bool,
) -> dict[str, float | int | None]:
    window = slice_samples(samples, spawn_ms, end_ms)
    if len(window) < 2:
        return {}
    distances = [
        math.hypot(s.x - target_x, s.y - target_y) for s in window
    ]
    entry_index = next(
        (i for i, dist in enumerate(distances) if dist <= target_r), None
    )
    entry_ms = (
        window[entry_index].t_ms - spawn_ms if entry_index is not None else None
    )
    correction_ms = None
    if hit and entry_index is not None:
        correction_ms = max(0.0, end_ms - window[entry_index].t_ms)
    overshoot_px: float | None = None
    overshoot_count = 0
    if entry_index is not None:
        overshoot_px = max(
            0.0,
            max((dist - target_r for dist in distances[entry_index:]), default=0.0),
        )
        inside = True
        for dist in distances[entry_index:]:
            now_inside = dist <= target_r
            if inside and not now_inside:
                overshoot_count += 1
            inside = now_inside
    velocities = _velocities(window)
    direction_changes = _direction_changes(velocities)
    speeds = [v[3] for v in velocities]
    peak_speed = max(speeds) if speeds else None
    mean_speed = sum(speeds) / len(speeds) if speeds else None
    time_to_peak = None
    if velocities:
        peak_index = max(range(len(velocities)), key=lambda i: velocities[i][3])
        time_to_peak = velocities[peak_index][0] - spawn_ms
    path = sum(
        math.hypot(
            window[i].x - window[i - 1].x,
            window[i].y - window[i - 1].y,
        )
        for i in range(1, len(window))
    )
    straight = math.hypot(
        window[-1].x - window[0].x, window[-1].y - window[0].y
    )
    curvature = path / straight if straight > 1.0 else None
    pre_click_speeds = [
        v[3] for v in velocities if v[0] >= end_ms - 80.0
    ]
    pre_click_speed = (
        sum(pre_click_speeds) / len(pre_click_speeds)
        if pre_click_speeds
        else None
    )
    first_move_ms = None
    threshold = max(3.0, target_r * 0.1)
    for sample in window:
        if math.hypot(sample.x - window[0].x, sample.y - window[0].y) > threshold:
            first_move_ms = sample.t_ms - spawn_ms
            break
    return {
        "entry_ms": entry_ms,
        "correction_ms": correction_ms,
        "overshoot_px": overshoot_px,
        "overshoot_count": overshoot_count if entry_index is not None else None,
        "direction_changes": direction_changes,
        "peak_speed": peak_speed,
        "mean_speed": mean_speed,
        "time_to_peak_ms": time_to_peak,
        "curvature": curvature,
        "pre_click_speed": pre_click_speed,
        "first_move_ms": first_move_ms,
    }


def track_window_analysis(
    samples: Sequence[MotionSample], start_ms: float, end_ms: float
) -> dict[str, float | None]:
    window = slice_samples(samples, start_ms, end_ms)
    firing = [s for s in window if s.lmb_down]
    if len(firing) < 3:
        return {}
    intervals = [
        firing[i].t_ms - firing[i - 1].t_ms
        for i in range(1, len(firing))
        if firing[i].t_ms > firing[i - 1].t_ms
    ]
    dt_ms = statistics.median(intervals) if intervals else 16.7
    lag_samples = 0
    best_distance: float | None = None
    max_lag = min(30, len(firing) // 2)
    for k in range(0, max_lag + 1):
        distances = [
            math.hypot(firing[i].x - firing[i - k].target_x,
                       firing[i].y - firing[i - k].target_y)
            for i in range(k, len(firing))
            if firing[i].has_target and firing[i - k].has_target
        ]
        if not distances:
            continue
        mean_distance = sum(distances) / len(distances)
        if best_distance is None or mean_distance < best_distance:
            best_distance = mean_distance
            lag_samples = k
    velocities = _velocities(firing)
    speeds = [v[3] for v in velocities]
    speed_std = statistics.pstdev(speeds) if len(speeds) > 1 else None
    mean_speed = sum(speeds) / len(speeds) if speeds else None
    peak_speed = max(speeds) if speeds else None
    dir_changes = _direction_changes(velocities)
    firing_seconds = (firing[-1].t_ms - firing[0].t_ms) / 1000.0
    dir_changes_per_s = (
        dir_changes / firing_seconds if firing_seconds > 0.2 else None
    )
    errors = [s.err for s in firing]
    error_std = statistics.pstdev(errors) if len(errors) > 1 else None
    return {
        "lag_ms": lag_samples * dt_ms if lag_samples else 0.0,
        "jitter": speed_std,
        "dir_changes": dir_changes_per_s,
        "peak_speed": peak_speed,
        "mean_speed": mean_speed,
        "error_std": error_std,
    }
