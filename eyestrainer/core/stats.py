from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def median(values: Iterable[float]) -> float | None:
    data = [float(v) for v in values]
    if not data:
        return None
    data.sort()
    n = len(data)
    mid = n // 2
    if n % 2:
        return data[mid]
    return (data[mid - 1] + data[mid]) / 2.0


def percentile(values: Sequence[float] | Iterable[float], p: float) -> float | None:
    """Linear-interpolated percentile. p is in [0, 100]."""
    data = sorted(float(v) for v in values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    p = clamp(p, 0.0, 100.0)
    rank = (len(data) - 1) * (p / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return data[lower]
    weight = rank - lower
    return data[lower] * (1.0 - weight) + data[upper] * weight


def median_iqr(values: Iterable[float]) -> tuple[float | None, float | None, float | None]:
    data = [float(v) for v in values]
    if not data:
        return None, None, None
    return median(data), percentile(data, 25), percentile(data, 75)


def weighted_mean(pairs: Iterable[tuple[float, float]]) -> float | None:
    total_weight = 0.0
    total = 0.0
    for value, weight in pairs:
        if weight <= 0:
            continue
        total += value * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return total / total_weight


def round_or_none(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(value, digits)
