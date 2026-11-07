import math

from eyestrainer.core.motion import (
    FLAG_LMB,
    FMT_FLICK,
    FMT_TRACK,
    MotionRecorder,
    decode_blob,
    flick_trial_analysis,
    track_window_analysis,
)


def _sample(t, x, y, target, err, speed=0.0, lmb=False, on_target=False):
    return {
        "t": t,
        "x": x,
        "y": y,
        "target": target,
        "err": err,
        "speed": speed,
        "lmb": lmb,
        "on_target": on_target,
    }


def _recorder(data, fmt=FMT_FLICK):
    rec = MotionRecorder(fmt)
    for item in data:
        rec.add(
            item["t"],
            item["x"],
            item["y"],
            target=item["target"],
            err=item["err"],
            speed=item["speed"],
            level=10.0,
            target_id=1 if item["target"] else -1,
            lmb_down=item["lmb"],
            on_target=item["on_target"],
        )
    return rec


def test_encode_decode_roundtrip():
    rec = _recorder(
        [
            _sample(0, 0, 0, (100, 0, 10), 100),
            _sample(50, 20, 0, (100, 0, 10), 80, 400),
            _sample(100, 40, 0, None, 0),
        ]
    )
    blob = rec.to_blob()
    assert blob is not None
    fmt, samples = decode_blob(blob)
    assert fmt == FMT_FLICK
    assert len(samples) == 3
    assert samples[1].x == 20
    assert samples[1].target_x == 100
    assert samples[2].has_target is False
    assert samples[0].lmb_down is False


def test_flick_entry_and_correction():
    data = []
    for i in range(11):
        t = i * 50
        x = min(100, i * 10)
        dist = abs(100 - x)
        data.append(
            _sample(t, x, 0, (100, 0, 10), dist, 200, on_target=dist <= 10)
        )
    # Final click at t=500 inside the target.
    recorder = _recorder(data)
    result = flick_trial_analysis(
        recorder.samples, 0, 500, 100, 0, 10, hit=True
    )
    assert result["entry_ms"] == 450
    assert result["correction_ms"] == 50
    assert result["overshoot_px"] == 0
    assert result["overshoot_count"] == 0
    assert result["peak_speed"] is not None
    assert result["curvature"] is not None


def test_flick_overshoot_and_direction_change():
    xs = [0, 30, 60, 90, 120, 110, 100]
    data = []
    for i, x in enumerate(xs):
        t = i * 50
        dist = abs(100 - x)
        data.append(
            _sample(t, x, 0, (100, 0, 10), dist, 600, on_target=dist <= 10)
        )
    recorder = _recorder(data)
    result = flick_trial_analysis(
        recorder.samples, 0, 300, 100, 0, 10, hit=True
    )
    assert result["overshoot_px"] == 10
    assert result["overshoot_count"] == 1
    assert result["direction_changes"] >= 1


def test_track_lag_detection():
    dt = 10.0
    data = []
    for i in range(60):
        t = i * dt
        target_x = 100 + t * 0.1
        cross_x = 100 + max(0.0, t - 20.0) * 0.1
        dist = abs(cross_x - target_x)
        data.append(
            _sample(
                t,
                cross_x,
                0,
                (target_x, 0, 40),
                dist,
                10,
                lmb=True,
                on_target=dist <= 40,
            )
        )
    recorder = _recorder(data, FMT_TRACK)
    result = track_window_analysis(recorder.samples, 0, 600)
    assert result["lag_ms"] is not None
    assert abs(result["lag_ms"] - 20.0) < 11.0
    assert result["jitter"] is not None
    assert result["dir_changes"] == 0.0


def test_track_analysis_without_firing_is_empty():
    rec = _recorder(
        [_sample(0, 0, 0, (10, 0, 10), 10), _sample(16, 0, 0, (10, 0, 10), 10)],
        FMT_TRACK,
    )
    assert track_window_analysis(rec.samples, 0, 32) == {}


def test_flags_values():
    rec = _recorder(
        [_sample(0, 0, 0, (10, 0, 10), 10, lmb=True, on_target=True)]
    )
    sample = rec.samples[0]
    assert sample.flags & FLAG_LMB
    assert sample.on_target
    assert sample.has_target
