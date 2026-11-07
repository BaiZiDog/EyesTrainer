from __future__ import annotations

from dataclasses import dataclass, field

from .stats import clamp


def level_from_value(
    value: float, easy_value: float, hard_value: float
) -> float:
    """Map a difficulty parameter to 0..100 (0 = easy, 100 = hard)."""
    if hard_value == easy_value:
        return 0.0
    return clamp((value - easy_value) / (hard_value - easy_value) * 100.0, 0.0, 100.0)


def value_from_level(
    level: float, easy_value: float, hard_value: float
) -> float:
    level = clamp(level, 0.0, 100.0)
    return easy_value + (hard_value - easy_value) * (level / 100.0)


@dataclass
class FlickAdaptive:
    """Batch controller: evaluate the last `window` shots, then adjust radius."""

    easy_radius: float
    hard_radius: float
    initial_radius: float
    window: int
    shrink_rate: float = 0.90
    grow_rate: float = 0.75
    step: float = 2.0
    radius: float = field(init=False)
    _outcomes: list[bool] = field(default_factory=list, init=False)
    changes: int = 0

    def __post_init__(self) -> None:
        self.radius = float(self.initial_radius)

    def record(self, hit: bool) -> bool:
        self._outcomes.append(bool(hit))
        if len(self._outcomes) < self.window:
            return False
        rate = sum(self._outcomes) / len(self._outcomes)
        self._outcomes.clear()
        changed = False
        if rate >= self.shrink_rate:
            new_radius = max(self.hard_radius, self.radius - self.step)
            if new_radius != self.radius:
                self.radius = new_radius
                changed = True
        elif rate <= self.grow_rate:
            new_radius = min(self.easy_radius, self.radius + self.step)
            if new_radius != self.radius:
                self.radius = new_radius
                changed = True
        if changed:
            self.changes += 1
        return changed

    @property
    def level(self) -> float:
        return level_from_value(self.radius, self.easy_radius, self.hard_radius)


@dataclass
class TrackAdaptive:
    """Hysteresis controller evaluated at the end of each tracking window."""

    easy_speed: float
    hard_speed: float
    initial_speed: float
    up_factor: float = 1.05
    down_factor: float = 0.95
    upper_tot: float = 0.80
    lower_tot: float = 0.55
    speed: float = field(init=False)
    changes: int = 0

    def __post_init__(self) -> None:
        self.speed = float(self.initial_speed)

    def update(self, tot: float | None, fired_ms: float) -> bool:
        if tot is None or fired_ms <= 0:
            return False
        old = self.speed
        if tot > self.upper_tot:
            self.speed = min(self.hard_speed, self.speed * self.up_factor)
        elif tot < self.lower_tot:
            self.speed = max(self.easy_speed, self.speed * self.down_factor)
        if abs(self.speed - old) > 1e-9:
            self.changes += 1
            return True
        return False

    @property
    def level(self) -> float:
        return level_from_value(self.speed, self.easy_speed, self.hard_speed)


@dataclass
class DvaStaircase:
    """2-down-1-up staircase for dynamic visual acuity speed thresholds."""

    min_speed: float
    max_speed: float
    initial_speed: float
    up_streak_required: int = 2
    step_factor: float = 1.06
    speed: float = field(init=False)
    _streak: int = field(default=0, init=False)
    _last_direction: int = field(default=0, init=False)
    reversals: list[float] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.speed = float(self.initial_speed)

    def record(self, correct: bool) -> bool:
        """Update difficulty; return True if this trial was a reversal."""
        reversal = False
        if correct:
            self._streak += 1
            if self._streak >= self.up_streak_required:
                self._streak = 0
                if self._last_direction == -1:
                    reversal = True
                    self.reversals.append(self.speed)
                self._last_direction = 1
                self.speed = min(self.max_speed, self.speed * self.step_factor)
        else:
            self._streak = 0
            if self._last_direction == 1:
                reversal = True
                self.reversals.append(self.speed)
            self._last_direction = -1
            self.speed = max(self.min_speed, self.speed / self.step_factor)
        return reversal

    @property
    def threshold(self) -> float:
        values = self.reversals[-6:]
        if values:
            return sum(values) / len(values)
        return self.speed

    @property
    def level(self) -> float:
        return level_from_value(self.speed, self.min_speed, self.max_speed)


@dataclass
class PeripheralAdaptive:
    """Adjust eccentricity from hit rate and false-alarm rate in batches."""

    easy_deg: float
    hard_deg: float
    initial_deg: float
    window: int = 10
    eccentricity: float = field(init=False)
    _outcomes: list[tuple[bool, bool]] = field(default_factory=list, init=False)
    changes: int = 0

    def __post_init__(self) -> None:
        self.eccentricity = float(self.initial_deg)

    def record(self, target_present: bool, responded: bool) -> bool:
        self._outcomes.append((bool(target_present), bool(responded)))
        if len(self._outcomes) < self.window:
            return False
        target_trials = [r for present, r in self._outcomes if present]
        catch_trials = [r for present, r in self._outcomes if not present]
        hit_rate = (
            sum(target_trials) / len(target_trials) if target_trials else None
        )
        false_alarm_rate = (
            sum(catch_trials) / len(catch_trials) if catch_trials else None
        )
        self._outcomes.clear()
        old = self.eccentricity
        if (
            hit_rate is not None
            and false_alarm_rate is not None
            and hit_rate >= 0.85
            and false_alarm_rate <= 0.10
        ):
            self.eccentricity = min(self.hard_deg, self.eccentricity + 1.0)
        elif (
            (hit_rate is not None and hit_rate < 0.60)
            or (false_alarm_rate is not None and false_alarm_rate > 0.25)
        ):
            self.eccentricity = max(self.easy_deg, self.eccentricity - 1.0)
        if abs(self.eccentricity - old) > 1e-9:
            self.changes += 1
            return True
        return False

    @property
    def level(self) -> float:
        return level_from_value(self.eccentricity, self.easy_deg, self.hard_deg)
