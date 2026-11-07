from eyestrainer.core.input import InputFrame
from eyestrainer.modules.base import ModuleConfig
from eyestrainer.modules.track import TrackModule

ARENA = (0.0, 0.0, 800.0, 600.0)


def _cfg(adaptive=False, fixed_level=0):
    return ModuleConfig(
        module_id="track",
        mode="waypoint",
        duration_s=6.0,
        adaptive=adaptive,
        fixed_level=fixed_level,
        warmup=False,
        extra={},
    )


def test_tracking_time_on_target():
    module = TrackModule()
    module.begin_round(_cfg(fixed_level=0), 5, ARENA)
    module.speed = 0.0
    module.target_speed = 0.0
    for i in range(60):
        t = (i + 1) * 0.1
        module.handle_input(
            InputFrame((module.x, module.y), (0.0, 0.0), True, False, False),
            t,
        )
        module.update(0.1, t)
    result = module.end_round(6.0)
    assert len(result.windows) >= 2
    assert result.summary["fired_ms"] > 5000
    assert abs(result.summary["tot"] - 1.0) < 1e-9
    assert result.windows[0]["ontarget_ms"] == result.windows[0]["fired_ms"]
    assert result.windows[0]["lag_ms"] is not None
    assert result.windows[0]["jitter"] is not None
    assert result.motion_blob is not None
    assert result.motion_count > 0


def test_tracking_without_firing_has_no_coverage():
    module = TrackModule()
    module.begin_round(_cfg(fixed_level=0), 6, ARENA)
    module.speed = 0.0
    module.target_speed = 0.0
    for i in range(20):
        t = (i + 1) * 0.1
        module.handle_input(
            InputFrame((0.0, 0.0), (0.0, 0.0), False, False, False), t
        )
        module.update(0.1, t)
    result = module.end_round(2.0)
    assert result.summary["fired_ms"] == 0
    assert result.summary["tot"] is None


def test_track_adaptive_speed_changes_after_window():
    module = TrackModule()
    module.begin_round(_cfg(adaptive=True), 8, ARENA)
    start_speed = module.target_speed
    module.speed = 0.0
    module.target_speed = 0.0
    for i in range(50):
        t = (i + 1) * 0.1
        module.handle_input(
            InputFrame((module.x, module.y), (0.0, 0.0), True, False, False),
            t,
        )
        module.update(0.1, t)
    assert module.target_speed > start_speed
    assert module.target_speed <= module.HARD_SPEED


def test_track_end_round_is_deterministic():
    def run(seed):
        module = TrackModule()
        module.begin_round(_cfg(fixed_level=0), seed, ARENA)
        module.speed = 0.0
        module.target_speed = 0.0
        for i in range(20):
            t = (i + 1) * 0.1
            module.handle_input(
                InputFrame((module.x, module.y), (0.0, 0.0), True, False, False), t
            )
            module.update(0.1, t)
        result = module.end_round(2.0)
        return result.summary, result.windows

    a = run(123)
    b = run(123)
    assert a == b


def test_track_commit_frame():
    module = TrackModule()
    module.begin_round(_cfg(), 1, ARENA)
    module.commit_frame(2.5)
    assert module.now_t == 2.5
