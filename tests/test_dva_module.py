import pygame

from eyestrainer.core.input import InputFrame
from eyestrainer.modules.base import ModuleConfig
from eyestrainer.modules.dva import DvaModule

ARENA = (0.0, 0.0, 800.0, 600.0)


def _cfg(adaptive=False, fixed_level=50, warmup=False):
    return ModuleConfig(
        module_id="dva",
        mode="staircase",
        duration_s=90.0,
        adaptive=adaptive,
        fixed_level=fixed_level,
        warmup=warmup,
        extra={"px_per_deg": 40.0},
    )


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _frame(events=()):
    return InputFrame((400.0, 300.0), (0.0, 0.0), False, False, False, tuple(events))


def _start_trial(module):
    module.phase_end = 0.0
    module.update(0.0, 0.01)
    assert module.state == "moving"
    assert module.trial is not None
    return module.trial


def test_dva_correct_response_and_metrics():
    module = DvaModule()
    module.begin_round(_cfg(), 11, ARENA)
    trial = _start_trial(module)
    trial["gap_dir"] = 0
    module.handle_input(_frame([_key(pygame.K_RIGHT)]), 0.02)
    record = module.trials[-1]
    assert record["correct"] == 1
    assert record["response"] == 0
    assert record["rt_ms"] is not None
    result = module.end_round(1.0)
    assert result.summary["trials"] == 1
    assert result.summary["threshold_deg_s"] is not None
    assert result.trials[0]["speed_deg_s"] > 0


def test_dva_wrong_response_and_timeout():
    module = DvaModule()
    module.begin_round(_cfg(), 12, ARENA)
    trial = _start_trial(module)
    trial["gap_dir"] = 1
    module.handle_input(_frame([_key(pygame.K_LEFT)]), 0.02)
    assert module.trials[-1]["correct"] == 0
    assert module.state == "feedback"

    module.state = "prepare"
    module.phase_end = 0.0
    module.update(0.0, 1.0)
    trial = module.trial
    assert trial is not None
    module.update(0.0, trial["response_deadline"] + 0.01)
    assert module.trials[-1]["timeout"] == 1


def test_dva_fixed_level_changes_speed():
    slow = DvaModule()
    slow.begin_round(_cfg(adaptive=False, fixed_level=0), 1, ARENA)
    fast = DvaModule()
    fast.begin_round(_cfg(adaptive=False, fixed_level=100), 1, ARENA)
    assert fast.speed > slow.speed


def test_dva_staircase_records_reversal():
    module = DvaModule()
    module.begin_round(_cfg(adaptive=True), 3, ARENA)
    module.trial_idx = 99
    for correct in [True, True, False]:
        module.phase_end = 0.0
        module.state = "prepare"
        module.update(0.0, module.now_t + 0.01)
        trial = module.trial
        assert trial is not None
        trial["gap_dir"] = 0
        key = pygame.K_RIGHT if correct else pygame.K_LEFT
        module.handle_input(_frame([_key(key)]), module.now_t + 0.02)
        module.now_t += 0.5
    reversals = [t for t in module.trials if t["reversal"]]
    assert reversals
