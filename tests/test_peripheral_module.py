import pygame

from eyestrainer.core.input import InputFrame
from eyestrainer.modules.base import ModuleConfig
from eyestrainer.modules.peripheral import PeripheralModule

ARENA = (0.0, 0.0, 800.0, 600.0)


def _cfg(adaptive=False, fixed_level=50, warmup=False):
    return ModuleConfig(
        module_id="peripheral",
        mode="adaptive",
        duration_s=60.0,
        adaptive=adaptive,
        fixed_level=fixed_level,
        warmup=warmup,
        extra={"px_per_deg": 40.0},
    )


def _frame(events=()):
    return InputFrame((400.0, 300.0), (0.0, 0.0), False, False, False, tuple(events))


def _space():
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)


def _start_trial(module):
    module.phase_end = 0.0
    module.update(0.0, 0.01)
    assert module.state == "stimulus"
    assert module.trial is not None
    return module.trial


def test_peripheral_hit():
    module = PeripheralModule()
    module.begin_round(_cfg(), 1, ARENA)
    trial = _start_trial(module)
    trial["target_present"] = 1
    module.handle_input(_frame([_space()]), 0.02)
    record = module.trials[-1]
    assert record["correct"] == 1
    assert record["responded"] == 1
    assert record["false_alarm"] == 0
    assert record["rt_ms"] is not None
    result = module.end_round(1.0)
    assert result.summary["hit_rate_pct"] == 100.0


def test_peripheral_false_alarm_and_correct_rejection():
    module = PeripheralModule()
    module.begin_round(_cfg(), 2, ARENA)
    trial = _start_trial(module)
    trial["target_present"] = 0
    module.handle_input(_frame([_space()]), 0.02)
    assert module.trials[-1]["false_alarm"] == 1

    module.state = "prepare"
    module.phase_end = 0.0
    module.update(0.0, 1.0)
    trial = module.trial
    trial["target_present"] = 0
    module.update(0.0, trial["response_deadline"] + 0.01)
    assert module.trials[-1]["correct"] == 1
    assert module.trials[-1]["false_alarm"] == 0


def test_peripheral_miss_and_eccentricity():
    module = PeripheralModule()
    module.begin_round(_cfg(adaptive=False, fixed_level=100), 3, ARENA)
    assert module.eccentricity == module.HARD_DEG
    trial = _start_trial(module)
    trial["target_present"] = 1
    module.update(0.0, trial["response_deadline"] + 0.01)
    assert module.trials[-1]["miss"] == 1
    assert module.trials[-1]["eccentricity_deg"] >= 0
    result = module.end_round(2.0)
    assert result.summary["trials"] == 1
    assert result.summary["eccentricity_median_deg"] is not None
