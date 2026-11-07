from eyestrainer.core.adaptive import (
    FlickAdaptive,
    TrackAdaptive,
    level_from_value,
    value_from_level,
)


def test_level_mapping():
    assert level_from_value(80, 80, 24) == 0
    assert level_from_value(24, 80, 24) == 100
    assert level_from_value(52, 80, 24) == 50
    assert value_from_level(0, 80, 24) == 80
    assert value_from_level(100, 80, 24) == 24
    assert value_from_level(50, 80, 24) == 52


def test_flick_adaptive_shrinks_after_window():
    ctl = FlickAdaptive(80, 24, 48, window=5)
    for _ in range(4):
        assert not ctl.record(True)
    assert ctl.radius == 48
    assert ctl.record(True)
    assert ctl.radius == 46


def test_flick_adaptive_grows_when_accuracy_low():
    ctl = FlickAdaptive(80, 24, 48, window=4)
    for _ in range(3):
        ctl.record(False)
    ctl.record(False)
    assert ctl.radius == 50


def test_flick_adaptive_clamps():
    ctl = FlickAdaptive(80, 24, 24, window=2)
    ctl.record(True)
    ctl.record(True)
    assert ctl.radius == 24
    ctl2 = FlickAdaptive(80, 24, 80, window=2)
    ctl2.record(False)
    ctl2.record(False)
    assert ctl2.radius == 80


def test_track_adaptive_hysteresis_and_clamps():
    ctl = TrackAdaptive(220, 1100, 420)
    assert not ctl.update(0.7, 1000)
    assert ctl.speed == 420
    assert ctl.update(0.9, 1000)
    assert ctl.speed > 420
    assert ctl.update(0.1, 1000)
    assert ctl.speed < 420
    assert not ctl.update(None, 0)
    tiny = TrackAdaptive(220, 1100, 1090)
    assert tiny.update(0.95, 1000)
    assert tiny.speed == 1100


def test_dva_staircase_two_down_one_up_and_reversal():
    from eyestrainer.core.adaptive import DvaStaircase

    ctl = DvaStaircase(min_speed=100, max_speed=1000, initial_speed=400)
    start = ctl.speed
    assert not ctl.record(True)
    assert not ctl.record(True)
    assert ctl.speed > start
    reversal = ctl.record(False)
    assert reversal
    assert ctl.reversals
    assert ctl.speed < start * 1.06
    assert ctl.threshold > 0


def test_peripheral_adaptive_changes_from_window():
    from eyestrainer.core.adaptive import PeripheralAdaptive

    ctl = PeripheralAdaptive(8, 25, 12, window=4)
    for _ in range(2):
        ctl.record(True, True)
    assert ctl.record(True, True) is False
    assert ctl.record(False, True) is True  # one false alarm + hits => hit 2/3, fa 1/1
    assert ctl.eccentricity == 11
    ctl2 = PeripheralAdaptive(8, 25, 20, window=4)
    for _ in range(3):
        ctl2.record(True, False)
    assert ctl2.record(True, False) is True
    assert ctl2.eccentricity == 19
