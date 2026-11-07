from eyestrainer.core.input import InputFrame
from eyestrainer.modules.base import ModuleConfig
from eyestrainer.modules.flick import FlickModule

ARENA = (0.0, 0.0, 800.0, 600.0)


def _cfg(mode="chain", adaptive=False, fixed_level=50):
    return ModuleConfig(
        module_id="flick",
        mode=mode,
        duration_s=60.0,
        adaptive=adaptive,
        fixed_level=fixed_level,
        warmup=False,
        extra={},
    )


def _click_at(x, y, t, module, pressed=True):
    module.handle_input(
        InputFrame((x, y), (0.0, 0.0), True, pressed, False), t
    )


def test_chain_hit_spawns_replacement():
    module = FlickModule()
    module.begin_round(_cfg(), 123, ARENA)
    module.commit_frame(0.0)
    assert len(module.targets) == 3
    target = module.targets[0]
    _click_at(target.x, target.y, 0.1, module)
    assert module.trials[-1]["outcome"] == "hit"
    assert module.trials[-1]["age_ms"] == 100
    assert len(module.targets) == 3
    result = module.end_round(10.0)
    assert result.summary["hits"] == 1
    assert result.summary["accuracy"] == 1


def test_chain_miss_is_recorded():
    module = FlickModule()
    module.begin_round(_cfg(), 321, ARENA)
    module.commit_frame(0.0)
    # Pick a point in the arena that is not inside any target.
    point = None
    for x in range(10, 790, 10):
        for y in range(10, 590, 10):
            if not any(
                (t.x - x) ** 2 + (t.y - y) ** 2 <= t.r**2 for t in module.targets
            ):
                point = (float(x), float(y))
                break
        if point:
            break
    assert point is not None
    _click_at(point[0], point[1], 0.1, module)
    assert module.trials[-1]["outcome"] == "miss_click"
    assert module.trials[-1]["target_x"] is None
    assert len(module.targets) == 3


def test_fixed_level_controls_radius():
    module = FlickModule()
    module.begin_round(_cfg(fixed_level=100), 1, ARENA)
    assert module.radius == module.CHAIN_MIN_R
    module2 = FlickModule()
    module2.begin_round(_cfg(fixed_level=0), 1, ARENA)
    assert module2.radius == module2.CHAIN_MAX_R


def test_reaction_hit_reaction_time():
    module = FlickModule()
    module.begin_round(_cfg(mode="reaction"), 99, ARENA)
    module.next_spawn_t = 0.0
    module.update(0.016, 0.0)
    module.commit_frame(0.0)
    target = module.reaction_target
    assert target is not None
    _click_at(target.x, target.y, 0.3, module)
    assert module.trials[-1]["outcome"] == "hit"
    assert abs(module.trials[-1]["age_ms"] - 300.0) < 1e-6
    assert module.reaction_target is None


def test_reaction_timeout():
    module = FlickModule()
    module.begin_round(_cfg(mode="reaction"), 7, ARENA)
    module.next_spawn_t = 0.0
    module.update(0.016, 0.0)
    module.commit_frame(0.0)
    module.update(0.016, 1.6)
    assert module.trials[-1]["outcome"] == "timeout"
    assert module.reaction_target is None
    assert module.trials[-1]["age_ms"] == 1500.0


def test_anticipation_click_without_target():
    module = FlickModule()
    module.begin_round(_cfg(mode="reaction"), 7, ARENA)
    module.next_spawn_t = 10.0
    _click_at(400.0, 300.0, 0.2, module)
    assert module.trials[-1]["outcome"] == "anticipation"
    assert module.trials[-1]["target_x"] is None
    result = module.end_round(0.5)
    assert result.summary["anticipation"] == 1


def test_reaction_late_click_is_timeout_not_hit():
    module = FlickModule()
    module.begin_round(_cfg(mode="reaction"), 7, ARENA)
    module.next_spawn_t = 0.0
    module.update(0.016, 0.0)
    module.commit_frame(0.0)
    target = module.reaction_target
    assert target is not None
    _click_at(target.x, target.y, 1.6, module)
    assert module.trials[-1]["outcome"] == "timeout"
    assert module.reaction_target is None


def test_chain_hit_records_trajectory_metrics():
    module = FlickModule()
    module.begin_round(_cfg(), 123, ARENA)
    module.commit_frame(0.0)
    target = module.targets[0]
    start = (400.0, 300.0)
    for i in range(1, 11):
        x = start[0] + (target.x - start[0]) * i / 10
        y = start[1] + (target.y - start[1]) * i / 10
        module.handle_input(
            InputFrame((x, y), (0.0, 0.0), False, False, False), i * 0.016
        )
    module.handle_input(
        InputFrame((target.x, target.y), (0.0, 0.0), True, True, False),
        0.176,
    )
    trial = module.trials[-1]
    assert trial["outcome"] == "hit"
    assert trial["entry_ms"] is not None
    assert trial["peak_speed"] is not None
    result = module.end_round(0.2)
    assert result.motion_blob is not None
    assert result.motion_count > 0
    assert result.arena == ARENA
