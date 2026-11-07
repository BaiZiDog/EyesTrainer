from __future__ import annotations

import time
from collections import deque


class FrameStats:
    def __init__(self, maxlen: int = 240) -> None:
        self._frames: deque[float] = deque(maxlen=maxlen)
        self.total_frames = 0
        self.long_frames = 0
        self.budget = 1.0 / 144.0

    def set_budget(self, budget: float) -> None:
        self.budget = max(1e-4, budget)

    def record(self, frame_dt: float) -> bool:
        self._frames.append(frame_dt)
        self.total_frames += 1
        is_long = frame_dt > self.budget * 2.0
        if is_long:
            self.long_frames += 1
        return is_long

    @property
    def avg_fps(self) -> float:
        if not self._frames:
            return 0.0
        mean_dt = sum(self._frames) / len(self._frames)
        return 1.0 / mean_dt if mean_dt > 0 else 0.0

    @property
    def avg_ms(self) -> float:
        if not self._frames:
            return 0.0
        return sum(self._frames) / len(self._frames) * 1000.0

    @property
    def p99_ms(self) -> float:
        if not self._frames:
            return 0.0
        data = sorted(self._frames)
        idx = min(len(data) - 1, int(len(data) * 0.99))
        return data[idx] * 1000.0

    @property
    def max_ms(self) -> float:
        if not self._frames:
            return 0.0
        return max(self._frames) * 1000.0

    def recent(self, count: int = 120) -> list[float]:
        return list(self._frames)[-count:]


class FramePacer:
    def __init__(self, fps_cap: int = 0, low_latency: bool = True) -> None:
        self.fps_cap = fps_cap
        self.low_latency = low_latency
        self._next_deadline = 0.0
        self.reset()

    def set_fps(self, fps_cap: int) -> None:
        self.fps_cap = fps_cap
        self.reset()

    def reset(self) -> None:
        self._next_deadline = time.perf_counter()

    def wait(self) -> None:
        if self.fps_cap <= 0:
            return
        interval = 1.0 / self.fps_cap
        now = time.perf_counter()
        if self._next_deadline <= 0.0 or now - self._next_deadline > 0.25:
            self._next_deadline = now
        self._next_deadline += interval
        remaining = self._next_deadline - time.perf_counter()
        if remaining <= 0:
            return
        if self.low_latency:
            if remaining > 0.002:
                time.sleep(remaining - 0.0015)
            while time.perf_counter() < self._next_deadline:
                pass
        else:
            if remaining > 0.001:
                time.sleep(remaining)


class RoundClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.running = False

    def start(self) -> None:
        self.t = 0.0
        self.running = True

    def stop(self) -> None:
        self.running = False

    def tick(self, real_dt: float) -> float:
        if self.running:
            self.t += max(0.0, real_dt)
        return self.t


def summarize_frames(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"fps": 0.0, "avg_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
    avg = sum(samples) / len(samples)
    ordered = sorted(samples)
    return {
        "fps": 1.0 / avg if avg > 0 else 0.0,
        "avg_ms": avg * 1000.0,
        "p99_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))] * 1000.0,
        "max_ms": ordered[-1] * 1000.0,
    }
