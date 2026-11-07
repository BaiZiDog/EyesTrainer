from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from .stats import median, median_iqr, percentile, safe_div, weighted_mean

VALID_RT_MIN_MS = 100.0
VALID_RT_MAX_MS = 1500.0


def _flags(trial: dict[str, Any]) -> set[str]:
    raw = trial.get("flags") or ""
    if isinstance(raw, str):
        return {part.strip() for part in raw.split(",") if part.strip()}
    return set(raw)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def valid_reaction_rts(trials: Sequence[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for trial in trials:
        if trial.get("outcome") != "hit":
            continue
        if "anticipation" in _flags(trial):
            continue
        rt = _number(trial.get("age_ms"))
        if rt is None:
            continue
        if VALID_RT_MIN_MS <= rt <= VALID_RT_MAX_MS:
            values.append(rt)
    return values


def first_move_values(trials: Sequence[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for trial in trials:
        if trial.get("outcome") != "hit":
            continue
        value = _number(trial.get("first_move_ms"))
        if value is not None:
            values.append(value)
    return values


def inter_kill_intervals(trials: Sequence[dict[str, Any]]) -> list[float]:
    kill_times = sorted(
        float(t["click_t"])
        for t in trials
        if t.get("outcome") == "hit" and t.get("click_t") is not None
    )
    return [
        (kill_times[i] - kill_times[i - 1]) * 1000.0
        for i in range(1, len(kill_times))
    ]


def click_errors(trials: Sequence[dict[str, Any]]) -> list[float]:
    return [
        float(t["click_err"])
        for t in trials
        if t.get("outcome") == "hit" and t.get("click_err") is not None
    ]


def path_efficiencies(trials: Sequence[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for t in trials:
        if t.get("outcome") != "hit":
            continue
        ideal = _number(t.get("ideal_px"))
        actual = _number(t.get("path_px"))
        if ideal is None or actual is None or actual <= 0:
            continue
        values.append(max(0.0, min(1.0, ideal / actual)))
    return values


def summarize_flick(
    trials: Sequence[dict[str, Any]], mode: str, duration_s: float
) -> dict[str, Any]:
    hits = sum(1 for t in trials if t.get("outcome") == "hit")
    miss_clicks = sum(1 for t in trials if t.get("outcome") == "miss_click")
    timeouts = sum(1 for t in trials if t.get("outcome") == "timeout")
    anticipation = sum(1 for t in trials if t.get("outcome") == "anticipation")
    hit_anticipation = sum(
        1
        for t in trials
        if t.get("outcome") == "hit" and "anticipation" in _flags(t)
    )
    shots = hits + miss_clicks + anticipation
    accuracy = safe_div(hits, hits + miss_clicks + anticipation + timeouts)
    rt_med, rt_p25, rt_p75 = median_iqr(valid_reaction_rts(trials))
    fm_med, fm_p25, fm_p75 = median_iqr(first_move_values(trials))
    ikis = inter_kill_intervals(trials)
    iki_med, iki_p25, iki_p75 = median_iqr(ikis)
    levels = [
        float(t["level"]) for t in trials if t.get("level") is not None
    ]
    advanced = [t for t in trials if t.get("outcome") == "hit"]
    entry_values = [
        float(t["entry_ms"])
        for t in advanced
        if t.get("entry_ms") is not None
    ]
    correction_values = [
        float(t["correction_ms"])
        for t in advanced
        if t.get("correction_ms") is not None
    ]
    overshoot_values = [
        float(t["overshoot_px"])
        for t in advanced
        if t.get("overshoot_px") is not None
    ]
    overshoot_counts = [
        float(t["overshoot_count"])
        for t in advanced
        if t.get("overshoot_count") is not None
    ]
    direction_values = [
        float(t["direction_changes"])
        for t in advanced
        if t.get("direction_changes") is not None
    ]
    peak_speeds = [
        float(t["peak_speed"])
        for t in advanced
        if t.get("peak_speed") is not None
    ]
    curvatures = [
        float(t["curvature"])
        for t in advanced
        if t.get("curvature") is not None
    ]
    duration_min = duration_s / 60.0 if duration_s > 0 else 0.0
    return {
        "mode": mode,
        "duration_s": round(duration_s, 2),
        "trials": len(trials),
        "shots": shots,
        "hits": hits,
        "kill_count": hits,
        "miss_clicks": miss_clicks,
        "timeouts": timeouts,
        "anticipation": anticipation,
        "hit_anticipation": hit_anticipation,
        "accuracy": accuracy,
        "kills_per_minute": safe_div(hits, duration_min),
        "rt_median": rt_med,
        "rt_p25": rt_p25,
        "rt_p75": rt_p75,
        "rt_n": len(valid_reaction_rts(trials)),
        "first_move_median": fm_med,
        "first_move_p25": fm_p25,
        "first_move_p75": fm_p75,
        "first_move_n": len(first_move_values(trials)),
        "iki_median": iki_med,
        "iki_p25": iki_p25,
        "iki_p75": iki_p75,
        "iki_n": len(ikis),
        "click_err_median": median(click_errors(trials)),
        "click_err_n": len(click_errors(trials)),
        "path_eff_median": median(path_efficiencies(trials)),
        "path_eff_n": len(path_efficiencies(trials)),
        "level_min": min(levels) if levels else None,
        "level_max": max(levels) if levels else None,
        "level_final": levels[-1] if levels else None,
        "entry_median": median(entry_values),
        "entry_n": len(entry_values),
        "correction_median": median(correction_values),
        "correction_n": len(correction_values),
        "overshoot_median": median(overshoot_values),
        "overshoot_count_median": median(overshoot_counts),
        "direction_changes_median": median(direction_values),
        "peak_speed_median": median(peak_speeds),
        "curvature_median": median(curvatures),
    }


def summarize_track(
    windows: Sequence[dict[str, Any]],
    duration_s: float,
    target_radius: float = 40.0,
) -> dict[str, Any]:
    fired_ms = sum(float(w.get("fired_ms") or 0.0) for w in windows)
    ontarget_ms = sum(float(w.get("ontarget_ms") or 0.0) for w in windows)
    tot = safe_div(ontarget_ms, fired_ms)
    err_values = [
        (float(w["mean_err_px"]), float(w.get("fired_ms") or 0.0))
        for w in windows
        if w.get("mean_err_px") is not None
    ]
    err_mean = weighted_mean(err_values)
    speeds = [float(w["speed"]) for w in windows if w.get("speed") is not None]
    levels = [float(w["level"]) for w in windows if w.get("level") is not None]
    lag_values = [
        float(w["lag_ms"])
        for w in windows
        if w.get("lag_ms") is not None and float(w.get("fired_ms") or 0.0) > 0
    ]
    jitter_values = [
        float(w["jitter"])
        for w in windows
        if w.get("jitter") is not None and float(w.get("fired_ms") or 0.0) > 0
    ]
    direction_values = [
        float(w["dir_changes"])
        for w in windows
        if w.get("dir_changes") is not None and float(w.get("fired_ms") or 0.0) > 0
    ]
    peak_values = [
        float(w["peak_speed"])
        for w in windows
        if w.get("peak_speed") is not None
    ]
    error_std_values = [
        float(w["error_std"])
        for w in windows
        if w.get("error_std") is not None and float(w.get("fired_ms") or 0.0) > 0
    ]
    total_ms = duration_s * 1000.0
    return {
        "duration_s": round(duration_s, 2),
        "windows": len(windows),
        "fired_ms": fired_ms,
        "ontarget_ms": ontarget_ms,
        "tot": tot,
        "tot_pct": tot * 100.0 if tot is not None else None,
        "mean_err_px": err_mean,
        "mean_err_norm": (err_mean / target_radius) if err_mean is not None else None,
        "trigger_coverage": safe_div(fired_ms, total_ms),
        "speed_median": median(speeds),
        "speed_min": min(speeds) if speeds else None,
        "speed_max": max(speeds) if speeds else None,
        "level_median": median(levels),
        "level_min": min(levels) if levels else None,
        "level_max": max(levels) if levels else None,
        "level_final": levels[-1] if levels else None,
        "lag_median": median(lag_values),
        "lag_n": len(lag_values),
        "jitter_median": median(jitter_values),
        "dir_changes_median": median(direction_values),
        "peak_speed_max": max(peak_values) if peak_values else None,
        "error_std_median": median(error_std_values),
    }


def summarize_dva(
    trials: Sequence[dict[str, Any]], duration_s: float
) -> dict[str, Any]:
    total = len(trials)
    correct = sum(1 for t in trials if t.get("correct"))
    timeouts = sum(1 for t in trials if t.get("timeout"))
    incorrect = max(0, total - correct - timeouts)
    responses = correct + incorrect
    accuracy = safe_div(correct, total)
    rt_values = [
        float(t["rt_ms"])
        for t in trials
        if t.get("correct") and t.get("rt_ms") is not None
    ]
    rt_med, rt_p25, rt_p75 = median_iqr(rt_values)
    reversal_trials = [t for t in trials if t.get("reversal")]
    if reversal_trials:
        threshold_deg = median(
            [float(t["speed_deg_s"]) for t in reversal_trials[-6:]]
        )
        threshold_px = median(
            [float(t["speed_px_s"]) for t in reversal_trials[-6:]]
        )
    else:
        recent = trials[-5:]
        threshold_deg = median(
            [float(t["speed_deg_s"]) for t in recent]
        )
        threshold_px = median(
            [float(t["speed_px_s"]) for t in recent]
        )
    speed_degs = [float(t["speed_deg_s"]) for t in trials]
    speed_pxs = [float(t["speed_px_s"]) for t in trials]
    levels = [float(t["level"]) for t in trials if t.get("level") is not None]
    return {
        "duration_s": round(duration_s, 2),
        "trials": total,
        "correct": correct,
        "incorrect": incorrect,
        "timeouts": timeouts,
        "responses": responses,
        "accuracy": accuracy,
        "response_rate": safe_div(responses, total),
        "rt_median": rt_med,
        "rt_p25": rt_p25,
        "rt_p75": rt_p75,
        "rt_n": len(rt_values),
        "threshold_px_s": threshold_px,
        "threshold_deg_s": threshold_deg,
        "reversals": len(reversal_trials),
        "speed_median_deg_s": median(speed_degs),
        "speed_max_deg_s": max(speed_degs) if speed_degs else None,
        "speed_median_px_s": median(speed_pxs),
        "final_speed_px_s": speed_pxs[-1] if speed_pxs else None,
        "final_speed_deg_s": speed_degs[-1] if speed_degs else None,
        "level_final": levels[-1] if levels else None,
        "level_min": min(levels) if levels else None,
        "level_max": max(levels) if levels else None,
    }


def summarize_peripheral(
    trials: Sequence[dict[str, Any]], duration_s: float
) -> dict[str, Any]:
    total = len(trials)
    target_trials = sum(1 for t in trials if t.get("target_present"))
    hits = sum(
        1 for t in trials if t.get("target_present") and t.get("responded")
    )
    misses = target_trials - hits
    catch_trials = total - target_trials
    false_alarms = sum(
        1 for t in trials if not t.get("target_present") and t.get("responded")
    )
    correct_rejections = catch_trials - false_alarms
    correct = hits + correct_rejections
    hit_rate = safe_div(hits, target_trials)
    false_alarm_rate = safe_div(false_alarms, catch_trials)
    accuracy = safe_div(correct, total)
    rt_values = [
        float(t["rt_ms"])
        for t in trials
        if t.get("target_present") and t.get("responded") and t.get("rt_ms") is not None
    ]
    rt_med, rt_p25, rt_p75 = median_iqr(rt_values)
    eccs = [
        float(t["eccentricity_deg"])
        for t in trials
        if t.get("eccentricity_deg") is not None
    ]
    exposures = [
        float(t["exposure_ms"])
        for t in trials
        if t.get("exposure_ms") is not None
    ]
    stimulus_counts = [
        float(t["stimulus_count"])
        for t in trials
        if t.get("stimulus_count") is not None
    ]
    levels = [float(t["level"]) for t in trials if t.get("level") is not None]
    return {
        "duration_s": round(duration_s, 2),
        "trials": total,
        "target_trials": target_trials,
        "hits": hits,
        "misses": misses,
        "catch_trials": catch_trials,
        "false_alarms": false_alarms,
        "correct_rejections": correct_rejections,
        "correct": correct,
        "accuracy": accuracy,
        "hit_rate": hit_rate,
        "hit_rate_pct": hit_rate * 100.0 if hit_rate is not None else None,
        "false_alarm_rate": false_alarm_rate,
        "false_alarm_rate_pct": (
            false_alarm_rate * 100.0 if false_alarm_rate is not None else None
        ),
        "rt_median": rt_med,
        "rt_p25": rt_p25,
        "rt_p75": rt_p75,
        "rt_n": len(rt_values),
        "eccentricity_median_deg": median(eccs),
        "eccentricity_max_deg": max(eccs) if eccs else None,
        "exposure_ms_median": median(exposures),
        "stimulus_count_median": median(stimulus_counts),
        "level_final": levels[-1] if levels else None,
        "level_min": min(levels) if levels else None,
        "level_max": max(levels) if levels else None,
    }


def summarize_session(
    module: str,
    mode: str,
    rounds: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate non-warmup round results by pooling raw trials/windows."""
    main = [r for r in rounds if not r.get("is_warmup")]
    duration = sum(float(r.get("duration_s") or 0.0) for r in main)
    if module == "flick":
        trials: list[dict[str, Any]] = []
        for r in main:
            trials.extend(r.get("trials") or [])
        summary = summarize_flick(trials, mode, duration)
        summary["rounds"] = len(main)
        return summary
    if module == "dva":
        trials: list[dict[str, Any]] = []
        for r in main:
            trials.extend(r.get("trials") or [])
        summary = summarize_dva(trials, duration)
        summary["rounds"] = len(main)
        return summary
    if module == "peripheral":
        trials = []
        for r in main:
            trials.extend(r.get("trials") or [])
        summary = summarize_peripheral(trials, duration)
        summary["rounds"] = len(main)
        return summary
    windows: list[dict[str, Any]] = []
    for r in main:
        windows.extend(r.get("windows") or [])
    summary = summarize_track(windows, duration)
    summary["rounds"] = len(main)
    return summary


def histogram(values: Iterable[float], bins: int = 20) -> list[tuple[float, float, int]]:
    data = sorted(float(v) for v in values)
    if not data:
        return []
    lo, hi = data[0], data[-1]
    if hi - lo < 1e-9:
        return [(lo, hi + 1e-9, len(data))]
    width = (hi - lo) / bins
    counts = [0] * bins
    for value in data:
        idx = int((value - lo) / width)
        idx = min(max(idx, 0), bins - 1)
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, counts[i]) for i in range(bins)]


def primary_metric(module: str, mode: str, summary: dict[str, Any]) -> dict[str, Any]:
    if module == "flick" and mode == "chain":
        return {
            "key": "kills_per_minute",
            "label": "每分钟击杀",
            "value": summary.get("kills_per_minute"),
            "higher_is_better": True,
            "unit": "",
        }
    if module == "flick":
        return {
            "key": "rt_median",
            "label": "命中反应时",
            "value": summary.get("rt_median"),
            "higher_is_better": False,
            "unit": "ms",
        }
    if module == "dva":
        return {
            "key": "threshold_deg_s",
            "label": "可辨速度阈值",
            "value": summary.get("threshold_deg_s"),
            "higher_is_better": True,
            "unit": " °/s",
        }
    if module == "peripheral":
        return {
            "key": "hit_rate_pct",
            "label": "周边检出率",
            "value": summary.get("hit_rate_pct"),
            "higher_is_better": True,
            "unit": "%",
        }
    return {
        "key": "tot_pct",
        "label": "覆盖率 TO/T",
        "value": summary.get("tot_pct"),
        "higher_is_better": True,
        "unit": "%",
    }


def metric_series(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile_value(values: Sequence[float], p: float) -> float | None:
    return percentile(values, p)
