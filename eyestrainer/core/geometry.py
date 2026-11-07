from __future__ import annotations

import math
import random
from typing import TypeAlias

Point: TypeAlias = tuple[float, float]
RectTuple: TypeAlias = tuple[float, float, float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_in_circle(point: Point, center: Point, radius: float) -> bool:
    return distance(point, center) <= radius


def click_error(point: Point, center: Point, radius: float) -> float | None:
    if radius <= 0:
        return None
    return distance(point, center) / radius


def path_efficiency(ideal: float, actual: float) -> float | None:
    if actual <= 0:
        return None
    return max(0.0, min(1.0, ideal / actual))


def clamp_point(point: Point, rect: RectTuple) -> Point:
    x, y, w, h = rect
    return (
        max(x, min(x + w, point[0])),
        max(y, min(y + h, point[1])),
    )


def arena_rect(
    size: tuple[int, int], margin_frac: float = 0.05, min_margin: float = 24.0
) -> RectTuple:
    width, height = size
    margin_x = max(min_margin, width * margin_frac)
    margin_y = max(min_margin, height * margin_frac)
    return (margin_x, margin_y, width - 2 * margin_x, height - 2 * margin_y)


def rect_contains(rect: RectTuple, point: Point) -> bool:
    x, y, w, h = rect
    return x <= point[0] <= x + w and y <= point[1] <= y + h


def random_point_in_rect(
    rng: random.Random, rect: RectTuple, radius: float
) -> Point:
    x, y, w, h = rect
    left = x + radius
    right = x + w - radius
    top = y + radius
    bottom = y + h - radius
    if right < left:
        left = right = x + w / 2
    if bottom < top:
        top = bottom = y + h / 2
    return (rng.uniform(left, right), rng.uniform(top, bottom))


def px_per_degree(
    screen_w: int, screen_h: int, diagonal_in: float, distance_cm: float
) -> float:
    """Approximate pixels per visual degree for a flat screen."""
    diag_px = math.hypot(screen_w, screen_h)
    diag_cm = max(diagonal_in, 1.0) * 2.54
    px_per_cm = diag_px / diag_cm
    return px_per_cm * max(distance_cm, 1.0) * math.tan(math.radians(1.0))


def angle_diff(a: float, b: float) -> float:
    """Shortest signed angular difference b - a, in radians."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


def turn_towards(current: float, target: float, max_delta: float) -> float:
    diff = angle_diff(current, target)
    if abs(diff) <= max_delta:
        return target
    return current + math.copysign(max_delta, diff)
