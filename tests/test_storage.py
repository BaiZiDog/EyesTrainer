import csv

from eyestrainer.core.motion import FMT_FLICK, MotionRecorder
from eyestrainer.core.storage import Storage


def _trial(idx, outcome="hit", age=300.0, click_t=1.0, err=0.2):
    return {
        "trial_idx": idx,
        "outcome": outcome,
        "spawn_t": max(0.0, click_t - age / 1000.0),
        "click_t": click_t,
        "age_ms": age,
        "first_move_ms": 180.0 if outcome == "hit" else None,
        "target_x": 100.0,
        "target_y": 100.0,
        "target_r": 40.0,
        "cross_x": 100.0,
        "cross_y": 100.0,
        "click_err": err if outcome == "hit" else None,
        "path_px": None,
        "ideal_px": None,
        "level": 50.0,
        "flags": [],
    }


def _summary(age=300.0):
    return {
        "rt_median": age,
        "accuracy": 1.0,
        "hits": 1,
        "shots": 1,
        "mode": "reaction",
        "duration_s": 30.0,
    }


def _add_session(storage: Storage, age: float, click_base: float = 1.0):
    sid = storage.start_session({"test": True})
    storage.save_round(
        session_id=sid,
        module="flick",
        mode="reaction",
        round_idx=1,
        is_warmup=False,
        duration_s=30.0,
        seed=42,
        summary=_summary(age),
        trials=[_trial(1, age=age, click_t=click_base)],
        started_at="2026-01-01T00:00:00+00:00",
    )
    storage.finish_session(sid, "completed")
    return sid


def test_storage_roundtrip_and_history(tmp_path):
    storage = Storage(tmp_path / "test.db")
    sid = _add_session(storage, age=300.0)
    summary = storage.session_metrics(sid)
    assert summary is not None
    assert summary["module"] == "flick"
    assert summary["mode"] == "reaction"
    assert summary["rt_median"] == 300.0
    assert summary["rounds"] == 1
    assert len(storage.history("flick", "reaction")) == 1
    assert storage.total_training_seconds() == 30.0
    storage.close()


def test_previous_and_best(tmp_path):
    storage = Storage(tmp_path / "test.db")
    _add_session(storage, age=300.0, click_base=1.0)
    _add_session(storage, age=250.0, click_base=2.0)
    current = _add_session(storage, age=400.0, click_base=3.0)
    comparison = storage.previous_and_best("flick", "reaction", current)
    assert comparison["previous"] is not None
    assert comparison["previous"]["rt_median"] == 250.0
    assert comparison["best"] is not None
    assert comparison["best"]["rt_median"] == 250.0
    storage.close()


def test_warmup_excluded_from_metrics(tmp_path):
    storage = Storage(tmp_path / "test.db")
    sid = storage.start_session({})
    storage.save_round(
        session_id=sid,
        module="flick",
        mode="chain",
        round_idx=0,
        is_warmup=True,
        duration_s=15.0,
        seed=1,
        summary={},
        trials=[_trial(1)],
    )
    assert storage.session_metrics(sid) is None
    assert storage.history("flick", "chain") == []
    assert storage.total_training_seconds() == 0.0
    storage.close()


def test_export_csv(tmp_path):
    storage = Storage(tmp_path / "test.db")
    _add_session(storage, age=300.0)
    paths = storage.export_csv(tmp_path / "exports", "flick", "reaction")
    assert paths
    for path in paths:
        assert path.exists()
    with paths[2].open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][0] == "id"
    assert len(rows) >= 2
    storage.close()


def test_mark_orphans_and_clear(tmp_path):
    storage = Storage(tmp_path / "test.db")
    sid = storage.start_session({})
    assert storage.session_row(sid)["status"] == "running"
    assert storage.mark_orphans_incomplete() == 1
    assert storage.session_row(sid)["status"] == "incomplete"
    _add_session(storage, age=300.0)
    storage.clear_sessions()
    assert storage.history() == []
    storage.close()


def test_save_round_motion_blob(tmp_path):
    storage = Storage(tmp_path / "test.db")
    sid = storage.start_session({})
    rec = MotionRecorder(FMT_FLICK)
    rec.add(0.0, 100.0, 100.0, target=(200.0, 100.0, 40.0), err=100.0, speed=0.0, level=10.0)
    rec.add(16.0, 120.0, 100.0, target=(200.0, 100.0, 40.0), err=80.0, speed=1250.0, level=10.0)
    blob = rec.to_blob()
    round_id = storage.save_round(
        session_id=sid,
        module="flick",
        mode="chain",
        round_idx=1,
        is_warmup=False,
        duration_s=60.0,
        seed=1,
        summary={},
        trials=[],
        motion_blob=blob,
        motion_format="flick",
        motion_count=rec.count,
    )
    row = storage.round_motion(round_id)
    assert row is not None
    assert row["sample_count"] == 2
    assert row["format"] == "flick"
    assert isinstance(row["data"], bytes)
    paths = storage.export_csv(tmp_path / "exports")
    motion_path = paths[-1]
    assert motion_path.exists()
    with motion_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][5] == "t_ms"
    assert len(rows) == 3
    storage.close()


def test_v1_migration_adds_motion_and_normalizes_track_mode(tmp_path):
    import sqlite3

    db = tmp_path / "v1.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL, app_version TEXT NOT NULL,
            started_at TEXT NOT NULL, ended_at TEXT, config_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running');
        CREATE TABLE rounds (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, module TEXT NOT NULL,
            mode TEXT NOT NULL, round_idx INTEGER NOT NULL, is_warmup INTEGER NOT NULL DEFAULT 0,
            duration_s REAL NOT NULL, seed INTEGER NOT NULL, started_at TEXT NOT NULL, summary_json TEXT NOT NULL);
        CREATE TABLE flick_trials (id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, trial_idx INTEGER NOT NULL,
            outcome TEXT NOT NULL, spawn_t REAL, click_t REAL, age_ms REAL, first_move_ms REAL,
            target_x REAL, target_y REAL, target_r REAL, cross_x REAL, cross_y REAL, click_err REAL,
            path_px REAL, ideal_px REAL, level REAL, flags TEXT);
        CREATE TABLE track_windows (id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, window_idx INTEGER NOT NULL,
            t_start REAL NOT NULL, t_end REAL NOT NULL, fired_ms REAL NOT NULL, ontarget_ms REAL NOT NULL,
            mean_err_px REAL, max_err_px REAL, speed REAL NOT NULL, level REAL NOT NULL);
        INSERT INTO profiles(name, created_at) VALUES ('default', '2026-01-01');
        INSERT INTO sessions(profile_id, app_version, started_at, config_json, status)
            VALUES (1, '0.1.0', '2026-01-01', '{}', 'completed');
        INSERT INTO rounds(session_id, module, mode, round_idx, is_warmup, duration_s, seed, started_at, summary_json)
            VALUES (1, 'track', 'chain', 1, 0, 30, 1, '2026-01-01', '{}');
        PRAGMA user_version = 1;
        """
    )
    con.commit()
    con.close()
    storage = Storage(db)
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    assert con.execute("SELECT mode FROM rounds").fetchone()[0] == "waypoint"
    flick_columns = {r[1] for r in con.execute("PRAGMA table_info(flick_trials)")}
    assert {"entry_ms", "overshoot_px", "peak_speed", "target_id"} <= flick_columns
    track_columns = {r[1] for r in con.execute("PRAGMA table_info(track_windows)")}
    assert {"lag_ms", "jitter", "dir_changes"} <= track_columns
    for table in ("round_motion", "dva_trials", "peripheral_trials"):
        assert con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None
    con.close()
    storage.close()


def test_save_dva_and_peripheral_rounds(tmp_path):
    storage = Storage(tmp_path / "test.db")

    sid = storage.start_session({})
    storage.save_round(
        session_id=sid,
        module="dva",
        mode="staircase",
        round_idx=1,
        is_warmup=False,
        duration_s=90.0,
        seed=1,
        summary={},
        trials=[
            {
                "trial_idx": 1,
                "speed_px_s": 600.0,
                "speed_deg_s": 15.0,
                "gap_dir": 0,
                "response": 0,
                "correct": 1,
                "timeout": 0,
                "rt_ms": 420.0,
                "start_t": 1.0,
                "visible_end_t": 2.0,
                "target_y": 400.0,
                "radius": 32.0,
                "level": 30.0,
                "reversal": 1,
            }
        ],
    )
    storage.finish_session(sid, "completed")
    dva = storage.session_metrics(sid)
    assert dva is not None
    assert dva["trials"] == 1
    assert dva["threshold_deg_s"] == 15.0

    sid2 = storage.start_session({})
    storage.save_round(
        session_id=sid2,
        module="peripheral",
        mode="adaptive",
        round_idx=1,
        is_warmup=False,
        duration_s=60.0,
        seed=2,
        summary={},
        trials=[
            {
                "trial_idx": 1,
                "target_present": 1,
                "responded": 1,
                "correct": 1,
                "false_alarm": 0,
                "miss": 0,
                "rt_ms": 350.0,
                "eccentricity_deg": 12.0,
                "exposure_ms": 150.0,
                "stimulus_count": 3,
                "target_angle": 10.0,
                "level": 20.0,
            }
        ],
    )
    storage.finish_session(sid2, "completed")
    per = storage.session_metrics(sid2)
    assert per is not None
    assert per["trials"] == 1
    assert per["hit_rate_pct"] == 100.0
    storage.close()
