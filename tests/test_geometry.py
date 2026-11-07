import math

from eyestrainer.core import geometry


def test_distance_and_hit():
    assert geometry.distance((0, 0), (3, 4)) == 5
    assert geometry.point_in_circle((0, 0), (0, 0), 1)
    assert geometry.point_in_circle((0.5, 0), (0, 0), 1)
    assert not geometry.point_in_circle((2, 0), (0, 0), 1)


def test_click_error_and_path_efficiency():
    assert geometry.click_error((0, 0), (0, 0), 10) == 0
    assert geometry.click_error((5, 0), (0, 0), 10) == 0.5
    assert geometry.click_error((0, 0), (0, 0), 0) is None
    assert geometry.path_efficiency(10, 10) == 1
    assert geometry.path_efficiency(10, 20) == 0.5
    assert geometry.path_efficiency(20, 10) == 1.0
    assert geometry.path_efficiency(10, 0) is None


def test_arena_and_clamp():
    rect = geometry.arena_rect((1920, 1080), 0.05, 24)
    assert rect == (96.0, 54.0, 1728.0, 972.0)
    assert geometry.rect_contains(rect, (100, 60))
    assert not geometry.rect_contains(rect, (0, 0))
    assert geometry.clamp_point((0, 0), rect) == (96.0, 54.0)


def test_px_per_degree():
    ppd = geometry.px_per_degree(1920, 1080, 24, 60)
    assert 20 < ppd < 100


def test_angles():
    assert abs(geometry.angle_diff(0, math.pi / 2) - math.pi / 2) < 1e-9
    turned = geometry.turn_towards(0, math.pi / 2, 0.1)
    assert abs(turned - 0.1) < 1e-9
