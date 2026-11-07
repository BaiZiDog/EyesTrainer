from eyestrainer.core import metrics


def _trial(
    outcome,
    *,
    click_t=None,
    age_ms=None,
    spawn_t=0.0,
    first_move_ms=None,
    click_err=None,
    path_px=None,
    ideal_px=None,
    level=50.0,
    flags=None,
):
    return {
        "outcome": outcome,
        "spawn_t": spawn_t,
        "click_t": click_t,
        "age_ms": age_ms,
        "first_move_ms": first_move_ms,
        "target_x": 100.0,
        "target_y": 100.0,
        "target_r": 40.0,
        "cross_x": 100.0,
        "cross_y": 100.0,
        "click_err": click_err,
        "path_px": path_px,
        "ideal_px": ideal_px,
        "level": level,
        "flags": flags or [],
    }


def test_reaction_summary_filters_and_counts():
    trials = [
        _trial("hit", click_t=1.0, age_ms=300, first_move_ms=180),
        _trial("hit", click_t=2.0, age_ms=250, first_move_ms=170),
        _trial("hit", click_t=2.4, age_ms=50, flags=["anticipation"]),
        _trial("miss_click", click_t=2.8, age_ms=400),
        _trial("timeout", age_ms=1500),
        _trial("anticipation", click_t=3.2),
    ]
    s = metrics.summarize_flick(trials, "reaction", 30.0)
    assert s["hits"] == 3
    assert s["miss_clicks"] == 1
    assert s["timeouts"] == 1
    assert s["anticipation"] == 1
    assert s["shots"] == 5
    assert s["accuracy"] == 0.5
    assert s["rt_median"] == 275
    assert s["rt_n"] == 2
    assert s["first_move_median"] == 175
    assert s["hit_anticipation"] == 1


def test_chain_summary_intervals_and_accuracy():
    trials = [
        _trial("hit", click_t=1.0, age_ms=900, click_err=0.2, path_px=100, ideal_px=80),
        _trial("miss_click", click_t=1.5),
        _trial("hit", click_t=1.8, age_ms=700, click_err=0.4, path_px=120, ideal_px=60),
        _trial("hit", click_t=3.0, age_ms=1100, click_err=0.6, path_px=200, ideal_px=100),
    ]
    s = metrics.summarize_flick(trials, "chain", 60.0)
    assert s["hits"] == 3
    assert s["miss_clicks"] == 1
    assert s["accuracy"] == 0.75
    assert s["iki_n"] == 2
    assert s["iki_median"] == 1000
    assert abs(s["click_err_median"] - 0.4) < 1e-9
    assert abs(s["path_eff_median"] - 0.5) < 1e-9
    assert s["kills_per_minute"] == 3.0


def test_track_summary():
    windows = [
        {"fired_ms": 1000, "ontarget_ms": 700, "mean_err_px": 10, "speed": 400, "level": 20},
        {"fired_ms": 1000, "ontarget_ms": 900, "mean_err_px": 20, "speed": 500, "level": 40},
    ]
    s = metrics.summarize_track(windows, 10.0, target_radius=40)
    assert s["fired_ms"] == 2000
    assert s["ontarget_ms"] == 1600
    assert abs(s["tot"] - 0.8) < 1e-9
    assert s["tot_pct"] == 80
    assert s["mean_err_px"] == 15
    assert s["mean_err_norm"] == 0.375
    assert s["trigger_coverage"] == 0.2
    assert s["speed_median"] == 450


def test_session_summary_excludes_warmup():
    warm = {
        "is_warmup": True,
        "duration_s": 15,
        "trials": [_trial("hit", click_t=1.0, age_ms=300)],
        "windows": [],
    }
    main = {
        "is_warmup": False,
        "duration_s": 60,
        "trials": [
            _trial("hit", click_t=1.0, age_ms=300),
            _trial("miss_click", click_t=1.5),
        ],
        "windows": [],
    }
    s = metrics.summarize_session("flick", "reaction", [warm, main])
    assert s["rounds"] == 1
    assert s["hits"] == 1
    assert s["accuracy"] == 0.5


def test_histogram():
    assert metrics.histogram([]) == []
    bins = metrics.histogram([1, 2, 3], bins=2)
    assert len(bins) == 2
    assert sum(count for _, _, count in bins) == 3
    same = metrics.histogram([5, 5, 5])
    assert same[0][2] == 3


def test_advanced_flick_metrics():
    trials = [
        {**_trial("hit", click_t=1.0, age_ms=300), "entry_ms": 200.0, "correction_ms": 100.0,
         "overshoot_px": 5.0, "overshoot_count": 1, "direction_changes": 2,
         "peak_speed": 900.0, "curvature": 1.2},
        {**_trial("hit", click_t=2.0, age_ms=300), "entry_ms": 260.0, "correction_ms": 40.0,
         "overshoot_px": 15.0, "overshoot_count": 2, "direction_changes": 4,
         "peak_speed": 1100.0, "curvature": 1.4},
    ]
    s = metrics.summarize_flick(trials, "chain", 60.0)
    assert s["entry_median"] == 230.0
    assert s["correction_median"] == 70.0
    assert s["overshoot_median"] == 10.0
    assert s["direction_changes_median"] == 3.0
    assert s["peak_speed_median"] == 1000.0


def test_advanced_track_metrics():
    windows = [
        {"fired_ms": 1000, "ontarget_ms": 700, "mean_err_px": 10, "speed": 400, "level": 20,
         "lag_ms": 30, "jitter": 100, "dir_changes": 1.5, "peak_speed": 800, "error_std": 5},
        {"fired_ms": 1000, "ontarget_ms": 900, "mean_err_px": 20, "speed": 500, "level": 40,
         "lag_ms": 10, "jitter": 140, "dir_changes": 2.5, "peak_speed": 900, "error_std": 7},
    ]
    s = metrics.summarize_track(windows, 10.0)
    assert s["lag_median"] == 20.0
    assert s["jitter_median"] == 120.0
    assert s["dir_changes_median"] == 2.0
    assert s["peak_speed_max"] == 900.0
    assert s["error_std_median"] == 6.0


def test_dva_summary_threshold_and_accuracy():
    trials = [
        {"trial_idx": 1, "speed_px_s": 500, "speed_deg_s": 12.5, "correct": 1, "timeout": 0,
         "rt_ms": 420, "level": 20, "reversal": 0},
        {"trial_idx": 2, "speed_px_s": 600, "speed_deg_s": 15.0, "correct": 1, "timeout": 0,
         "rt_ms": 380, "level": 25, "reversal": 1},
        {"trial_idx": 3, "speed_px_s": 550, "speed_deg_s": 13.75, "correct": 0, "timeout": 0,
         "rt_ms": 400, "level": 22, "reversal": 1},
        {"trial_idx": 4, "speed_px_s": 520, "speed_deg_s": 13.0, "correct": 0, "timeout": 1,
         "rt_ms": None, "level": 21, "reversal": 0},
    ]
    s = metrics.summarize_dva(trials, 90.0)
    assert s["trials"] == 4
    assert s["correct"] == 2
    assert s["timeouts"] == 1
    assert s["accuracy"] == 0.5
    assert s["reversals"] == 2
    assert s["threshold_deg_s"] == 14.375
    assert s["threshold_px_s"] == 575.0
    assert s["rt_median"] == 400.0


def test_peripheral_summary_rates():
    trials = [
        {"target_present": 1, "responded": 1, "correct": 1, "false_alarm": 0, "miss": 0,
         "rt_ms": 350, "eccentricity_deg": 12, "exposure_ms": 150, "stimulus_count": 3, "level": 30},
        {"target_present": 1, "responded": 0, "correct": 0, "false_alarm": 0, "miss": 1,
         "rt_ms": None, "eccentricity_deg": 12, "exposure_ms": 150, "stimulus_count": 3, "level": 30},
        {"target_present": 0, "responded": 1, "correct": 0, "false_alarm": 1, "miss": 0,
         "rt_ms": 500, "eccentricity_deg": 12, "exposure_ms": 150, "stimulus_count": 3, "level": 30},
        {"target_present": 0, "responded": 0, "correct": 1, "false_alarm": 0, "miss": 0,
         "rt_ms": None, "eccentricity_deg": 12, "exposure_ms": 150, "stimulus_count": 3, "level": 30},
    ]
    s = metrics.summarize_peripheral(trials, 60.0)
    assert s["trials"] == 4
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["false_alarms"] == 1
    assert s["correct_rejections"] == 1
    assert s["hit_rate_pct"] == 50.0
    assert s["false_alarm_rate_pct"] == 50.0
    assert s["rt_median"] == 350.0
    assert s["eccentricity_median_deg"] == 12.0
