from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import metrics
from .motion import decode_blob

SCHEMA_VERSION = 3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id),
    app_version TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    config_json TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS rounds (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    mode        TEXT NOT NULL,
    round_idx   INTEGER NOT NULL,
    is_warmup   INTEGER NOT NULL DEFAULT 0,
    duration_s  REAL NOT NULL,
    seed        INTEGER NOT NULL,
    started_at  TEXT NOT NULL,
    summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flick_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    outcome      TEXT NOT NULL,
    spawn_t      REAL,
    click_t      REAL,
    age_ms       REAL,
    first_move_ms REAL,
    target_x     REAL, target_y REAL, target_r REAL,
    cross_x      REAL, cross_y REAL,
    click_err    REAL,
    path_px      REAL, ideal_px REAL,
    level        REAL,
    flags        TEXT,
    target_id    INTEGER,
    entry_ms     REAL,
    correction_ms REAL,
    overshoot_px REAL,
    overshoot_count INTEGER,
    direction_changes INTEGER,
    peak_speed   REAL,
    curvature    REAL
);

CREATE TABLE IF NOT EXISTS track_windows (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    window_idx   INTEGER NOT NULL,
    t_start      REAL NOT NULL,
    t_end        REAL NOT NULL,
    fired_ms     REAL NOT NULL,
    ontarget_ms  REAL NOT NULL,
    mean_err_px  REAL,
    max_err_px   REAL,
    speed        REAL NOT NULL,
    level        REAL NOT NULL,
    lag_ms       REAL,
    jitter       REAL,
    dir_changes  REAL,
    peak_speed   REAL,
    error_std    REAL
);

CREATE TABLE IF NOT EXISTS dva_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    speed_px_s   REAL NOT NULL,
    speed_deg_s  REAL NOT NULL,
    gap_dir      INTEGER NOT NULL,
    response     INTEGER,
    correct      INTEGER NOT NULL,
    timeout      INTEGER NOT NULL,
    rt_ms        REAL,
    start_t      REAL NOT NULL,
    visible_end_t REAL NOT NULL,
    target_y     REAL NOT NULL,
    radius       REAL NOT NULL,
    level        REAL,
    reversal     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS peripheral_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    target_present INTEGER NOT NULL,
    responded    INTEGER NOT NULL,
    correct      INTEGER NOT NULL,
    false_alarm  INTEGER NOT NULL,
    miss         INTEGER NOT NULL,
    rt_ms        REAL,
    eccentricity_deg REAL NOT NULL,
    exposure_ms  REAL NOT NULL,
    stimulus_count INTEGER NOT NULL,
    target_angle REAL,
    level        REAL
);

CREATE TABLE IF NOT EXISTS round_motion (
    round_id     INTEGER PRIMARY KEY REFERENCES rounds(id) ON DELETE CASCADE,
    sample_count INTEGER NOT NULL,
    format       TEXT NOT NULL,
    data         BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id);
CREATE INDEX IF NOT EXISTS idx_flick_round ON flick_trials(round_id);
CREATE INDEX IF NOT EXISTS idx_track_round ON track_windows(round_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, db_path: Path, app_version: str = "0.5.0") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.app_version = app_version
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_schema()
        self._ensure_default_profile()

    def _ensure_schema(self) -> None:
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version == 0:
            self.conn.executescript(SCHEMA_SQL)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()
            return
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {version} is newer than supported {SCHEMA_VERSION}"
            )
        if version < 2:
            self._migrate_v2()
        if version < 3:
            self._migrate_v3()
        if version < SCHEMA_VERSION:
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()

    def _migrate_v2(self) -> None:
        """Add trajectory columns/blob table and normalize legacy track modes."""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS round_motion ("
            " round_id INTEGER PRIMARY KEY REFERENCES rounds(id) ON DELETE CASCADE,"
            " sample_count INTEGER NOT NULL, format TEXT NOT NULL, data BLOB NOT NULL)"
        )
        flick_columns = {
            "target_id": "INTEGER",
            "entry_ms": "REAL",
            "correction_ms": "REAL",
            "overshoot_px": "REAL",
            "overshoot_count": "INTEGER",
            "direction_changes": "INTEGER",
            "peak_speed": "REAL",
            "curvature": "REAL",
        }
        track_columns = {
            "lag_ms": "REAL",
            "jitter": "REAL",
            "dir_changes": "REAL",
            "peak_speed": "REAL",
            "error_std": "REAL",
        }
        for column, decl in flick_columns.items():
            self._add_column("flick_trials", column, decl)
        for column, decl in track_columns.items():
            self._add_column("track_windows", column, decl)
        # Older builds allowed track sessions to inherit flick mode names. The
        # track module always ran waypoint motion for those values.
        self.conn.execute(
            "UPDATE rounds SET mode = 'waypoint'"
            " WHERE module = 'track' AND mode NOT IN ('waypoint', 'bounce')"
        )
        self.conn.commit()

    def _migrate_v3(self) -> None:
        """Add tables for the DVA and peripheral-vision modules."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dva_trials (
                id           INTEGER PRIMARY KEY,
                round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
                trial_idx    INTEGER NOT NULL,
                speed_px_s   REAL NOT NULL,
                speed_deg_s  REAL NOT NULL,
                gap_dir      INTEGER NOT NULL,
                response     INTEGER,
                correct      INTEGER NOT NULL,
                timeout      INTEGER NOT NULL,
                rt_ms        REAL,
                start_t      REAL NOT NULL,
                visible_end_t REAL NOT NULL,
                target_y     REAL NOT NULL,
                radius       REAL NOT NULL,
                level        REAL,
                reversal     INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS peripheral_trials (
                id           INTEGER PRIMARY KEY,
                round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
                trial_idx    INTEGER NOT NULL,
                target_present INTEGER NOT NULL,
                responded    INTEGER NOT NULL,
                correct      INTEGER NOT NULL,
                false_alarm  INTEGER NOT NULL,
                miss         INTEGER NOT NULL,
                rt_ms        REAL,
                eccentricity_deg REAL NOT NULL,
                exposure_ms  REAL NOT NULL,
                stimulus_count INTEGER NOT NULL,
                target_angle REAL,
                level        REAL
            );
            """
        )
        self.conn.commit()

    def _add_column(self, table: str, column: str, decl: str) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _ensure_default_profile(self) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles(name, created_at) VALUES (?, ?)",
            ("default", utc_now()),
        )
        self.conn.commit()

    def _profile_id(self, name: str = "default") -> int:
        row = self.conn.execute(
            "SELECT id FROM profiles WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            return int(row["id"])
        cur = self.conn.execute(
            "INSERT INTO profiles(name, created_at) VALUES (?, ?)", (name, utc_now())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------------------ sessions

    def start_session(self, config: dict[str, Any], profile: str = "default") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions(profile_id, app_version, started_at, config_json, status)"
            " VALUES (?, ?, ?, ?, 'running')",
            (
                self._profile_id(profile),
                self.app_version,
                utc_now(),
                json.dumps(config, ensure_ascii=False, default=str),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_session(
        self, session_id: int, status: str = "completed", ended_at: str | None = None
    ) -> None:
        self.conn.execute(
            "UPDATE sessions SET status = ?, ended_at = COALESCE(?, ended_at, ?)"
            " WHERE id = ?",
            (status, ended_at, utc_now(), session_id),
        )
        self.conn.commit()

    def mark_orphans_incomplete(self) -> int:
        cur = self.conn.execute(
            "UPDATE sessions SET status = 'incomplete', ended_at = COALESCE(ended_at, ?)"
            " WHERE status = 'running'",
            (utc_now(),),
        )
        self.conn.commit()
        return int(cur.rowcount)

    def session_row(self, session_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    # -------------------------------------------------------------------- rounds

    def save_round(
        self,
        session_id: int,
        module: str,
        mode: str,
        round_idx: int,
        is_warmup: bool,
        duration_s: float,
        seed: int,
        summary: dict[str, Any],
        trials: Iterable[dict[str, Any]] | None = None,
        windows: Iterable[dict[str, Any]] | None = None,
        started_at: str | None = None,
        motion_blob: bytes | None = None,
        motion_format: str = "",
        motion_count: int = 0,
    ) -> int:
        started_at = started_at or utc_now()
        trials = list(trials or [])
        windows = list(windows or [])
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO rounds(session_id, module, mode, round_idx, is_warmup,"
                " duration_s, seed, started_at, summary_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    module,
                    mode,
                    round_idx,
                    1 if is_warmup else 0,
                    float(duration_s),
                    int(seed),
                    started_at,
                    json.dumps(summary, ensure_ascii=False, default=str),
                ),
            )
            round_id = int(cur.lastrowid)
            for trial in trials:
                if module == "flick":
                    self._insert_trial(round_id, trial)
                elif module == "dva":
                    self._insert_dva_trial(round_id, trial)
                elif module == "peripheral":
                    self._insert_peripheral_trial(round_id, trial)
            for window in windows:
                self._insert_window(round_id, window)
            if motion_blob:
                self.conn.execute(
                    "INSERT OR REPLACE INTO round_motion(round_id, sample_count, format, data)"
                    " VALUES (?, ?, ?, ?)",
                    (round_id, int(motion_count), motion_format, sqlite3.Binary(motion_blob)),
                )
        return round_id

    def _insert_trial(self, round_id: int, t: dict[str, Any]) -> None:
        flags = t.get("flags") or ""
        if isinstance(flags, (list, tuple, set)):
            flags = ",".join(str(f) for f in flags)
        self.conn.execute(
            "INSERT INTO flick_trials(round_id, trial_idx, outcome, spawn_t, click_t,"
            " age_ms, first_move_ms, target_x, target_y, target_r, cross_x, cross_y,"
            " click_err, path_px, ideal_px, level, flags, target_id, entry_ms,"
            " correction_ms, overshoot_px, overshoot_count, direction_changes,"
            " peak_speed, curvature)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                round_id,
                int(t.get("trial_idx", 0)),
                str(t.get("outcome", "miss_click")),
                t.get("spawn_t"),
                t.get("click_t"),
                t.get("age_ms"),
                t.get("first_move_ms"),
                t.get("target_x"),
                t.get("target_y"),
                t.get("target_r"),
                t.get("cross_x"),
                t.get("cross_y"),
                t.get("click_err"),
                t.get("path_px"),
                t.get("ideal_px"),
                t.get("level"),
                flags,
                t.get("target_id"),
                t.get("entry_ms"),
                t.get("correction_ms"),
                t.get("overshoot_px"),
                t.get("overshoot_count"),
                t.get("direction_changes"),
                t.get("peak_speed"),
                t.get("curvature"),
            ),
        )

    def _insert_dva_trial(self, round_id: int, trial: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO dva_trials(round_id, trial_idx, speed_px_s, speed_deg_s,"
            " gap_dir, response, correct, timeout, rt_ms, start_t, visible_end_t,"
            " target_y, radius, level, reversal)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                round_id,
                int(trial.get("trial_idx", 0)),
                float(trial.get("speed_px_s", 0.0)),
                float(trial.get("speed_deg_s", 0.0)),
                int(trial.get("gap_dir", 0)),
                trial.get("response"),
                int(trial.get("correct", 0)),
                int(trial.get("timeout", 0)),
                trial.get("rt_ms"),
                float(trial.get("start_t", 0.0)),
                float(trial.get("visible_end_t", 0.0)),
                float(trial.get("target_y", 0.0)),
                float(trial.get("radius", 0.0)),
                trial.get("level"),
                int(trial.get("reversal", 0)),
            ),
        )

    def _insert_peripheral_trial(
        self, round_id: int, trial: dict[str, Any]
    ) -> None:
        self.conn.execute(
            "INSERT INTO peripheral_trials(round_id, trial_idx, target_present,"
            " responded, correct, false_alarm, miss, rt_ms, eccentricity_deg,"
            " exposure_ms, stimulus_count, target_angle, level)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                round_id,
                int(trial.get("trial_idx", 0)),
                int(trial.get("target_present", 0)),
                int(trial.get("responded", 0)),
                int(trial.get("correct", 0)),
                int(trial.get("false_alarm", 0)),
                int(trial.get("miss", 0)),
                trial.get("rt_ms"),
                float(trial.get("eccentricity_deg", 0.0)),
                float(trial.get("exposure_ms", 0.0)),
                int(trial.get("stimulus_count", 0)),
                trial.get("target_angle"),
                trial.get("level"),
            ),
        )

    def _insert_window(self, round_id: int, w: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO track_windows(round_id, window_idx, t_start, t_end, fired_ms,"
            " ontarget_ms, mean_err_px, max_err_px, speed, level, lag_ms, jitter,"
            " dir_changes, peak_speed, error_std)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                round_id,
                int(w.get("window_idx", 0)),
                float(w.get("t_start", 0.0)),
                float(w.get("t_end", 0.0)),
                float(w.get("fired_ms", 0.0)),
                float(w.get("ontarget_ms", 0.0)),
                w.get("mean_err_px"),
                w.get("max_err_px"),
                float(w.get("speed", 0.0)),
                float(w.get("level", 0.0)),
                w.get("lag_ms"),
                w.get("jitter"),
                w.get("dir_changes"),
                w.get("peak_speed"),
                w.get("error_std"),
            ),
        )

    def rounds_for_session(
        self, session_id: int, include_warmup: bool = True
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM rounds WHERE session_id = ?"
        params: list[Any] = [session_id]
        if not include_warmup:
            sql += " AND is_warmup = 0"
        sql += " ORDER BY round_idx, id"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def round_motion(self, round_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM round_motion WHERE round_id = ?", (round_id,)
        ).fetchone()
        return dict(row) if row else None

    def flick_trials_for_session(self, session_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT ft.* FROM flick_trials ft"
            " JOIN rounds r ON r.id = ft.round_id"
            " WHERE r.session_id = ? AND r.is_warmup = 0"
            " ORDER BY r.round_idx, ft.trial_idx, ft.id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def dva_trials_for_session(self, session_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT dt.* FROM dva_trials dt"
            " JOIN rounds r ON r.id = dt.round_id"
            " WHERE r.session_id = ? AND r.is_warmup = 0"
            " ORDER BY r.round_idx, dt.trial_idx, dt.id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def peripheral_trials_for_session(
        self, session_id: int
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT pt.* FROM peripheral_trials pt"
            " JOIN rounds r ON r.id = pt.round_id"
            " WHERE r.session_id = ? AND r.is_warmup = 0"
            " ORDER BY r.round_idx, pt.trial_idx, pt.id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def track_windows_for_session(self, session_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT tw.* FROM track_windows tw"
            " JOIN rounds r ON r.id = tw.round_id"
            " WHERE r.session_id = ? AND r.is_warmup = 0"
            " ORDER BY r.round_idx, tw.window_idx, tw.id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ history

    def recent_sessions(
        self, module: str | None = None, mode: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        where = ["r.is_warmup = 0"]
        params: list[Any] = []
        if module:
            where.append("r.module = ?")
            params.append(module)
        if mode:
            where.append("r.mode = ?")
            params.append(mode)
        params.append(int(limit))
        sql = (
            "SELECT s.id, s.started_at, s.status, s.config_json,"
            " MIN(r.module) AS module, MIN(r.mode) AS mode"
            " FROM sessions s JOIN rounds r ON r.session_id = s.id"
            " WHERE " + " AND ".join(where) +
            " GROUP BY s.id ORDER BY s.started_at DESC, s.id DESC LIMIT ?"
        )
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def session_metrics(self, session_id: int) -> dict[str, Any] | None:
        session = self.session_row(session_id)
        if session is None:
            return None
        rounds = self.rounds_for_session(session_id, include_warmup=False)
        if not rounds:
            return None
        module = str(rounds[0]["module"])
        mode = str(rounds[0]["mode"])
        duration = sum(float(r["duration_s"]) for r in rounds)
        if module == "flick":
            trials = self.flick_trials_for_session(session_id)
            summary = metrics.summarize_flick(trials, mode, duration)
        elif module == "track":
            windows = self.track_windows_for_session(session_id)
            summary = metrics.summarize_track(windows, duration)
        elif module == "dva":
            trials = self.dva_trials_for_session(session_id)
            summary = metrics.summarize_dva(trials, duration)
        elif module == "peripheral":
            trials = self.peripheral_trials_for_session(session_id)
            summary = metrics.summarize_peripheral(trials, duration)
        else:
            return None
        summary.update(
            {
                "session_id": session_id,
                "started_at": session["started_at"],
                "status": session["status"],
                "module": module,
                "mode": mode,
                "rounds": len(rounds),
            }
        )
        return summary

    def history(
        self, module: str | None = None, mode: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in self.recent_sessions(module, mode, limit):
            summary = self.session_metrics(int(row["id"]))
            if summary is not None:
                summary["config_json"] = row.get("config_json")
                results.append(summary)
        return results

    def previous_and_best(
        self, module: str, mode: str, current_session_id: int
    ) -> dict[str, Any | None]:
        history = [
            s
            for s in self.history(module, mode, limit=200)
            if int(s["session_id"]) != int(current_session_id)
        ]
        previous = history[0] if history else None
        primary = metrics.primary_metric(module, mode, {})
        key = primary["key"]
        higher = bool(primary["higher_is_better"])
        candidates = [s for s in history if s.get(key) is not None]
        best = None
        if candidates:
            best = (
                max(candidates, key=lambda s: float(s[key]))
                if higher
                else min(candidates, key=lambda s: float(s[key]))
            )
        return {"previous": previous, "best": best}

    def total_training_seconds(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(duration_s), 0) FROM rounds WHERE is_warmup = 0"
        ).fetchone()
        return float(row[0])

    # ------------------------------------------------------------------- export

    def export_csv(
        self,
        export_dir: Path,
        module: str | None = None,
        mode: str | None = None,
    ) -> list[Path]:
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths: list[Path] = []
        filters: list[str] = []
        params: list[Any] = []
        if module:
            filters.append("r.module = ?")
            params.append(module)
        if mode:
            filters.append("r.mode = ?")
            params.append(mode)
        where = (" WHERE " + " AND ".join(filters)) if filters else ""

        sessions_path = export_dir / f"eyestrainer_sessions_{stamp}.csv"
        self._write_query(
            sessions_path,
            "SELECT DISTINCT s.* FROM sessions s"
            " JOIN rounds r ON r.session_id = s.id" + where +
            " ORDER BY s.started_at",
            params,
        )
        paths.append(sessions_path)

        rounds_path = export_dir / f"eyestrainer_rounds_{stamp}.csv"
        self._write_query(
            rounds_path,
            "SELECT r.* FROM rounds r" + where + " ORDER BY r.started_at",
            params,
        )
        paths.append(rounds_path)

        trials_path = export_dir / f"eyestrainer_flick_trials_{stamp}.csv"
        self._write_query(
            trials_path,
            "SELECT ft.* FROM flick_trials ft JOIN rounds r ON r.id = ft.round_id"
            + where + " ORDER BY ft.id",
            params,
        )
        paths.append(trials_path)

        windows_path = export_dir / f"eyestrainer_track_windows_{stamp}.csv"
        self._write_query(
            windows_path,
            "SELECT tw.* FROM track_windows tw JOIN rounds r ON r.id = tw.round_id"
            + where + " ORDER BY tw.id",
            params,
        )
        paths.append(windows_path)

        dva_path = export_dir / f"eyestrainer_dva_trials_{stamp}.csv"
        self._write_query(
            dva_path,
            "SELECT dt.* FROM dva_trials dt JOIN rounds r ON r.id = dt.round_id"
            + where + " ORDER BY dt.id",
            params,
        )
        paths.append(dva_path)

        peripheral_path = export_dir / f"eyestrainer_peripheral_trials_{stamp}.csv"
        self._write_query(
            peripheral_path,
            "SELECT pt.* FROM peripheral_trials pt JOIN rounds r ON r.id = pt.round_id"
            + where + " ORDER BY pt.id",
            params,
        )
        paths.append(peripheral_path)

        motion_path = export_dir / f"eyestrainer_motion_samples_{stamp}.csv"
        self._write_motion_csv(motion_path, where, params)
        paths.append(motion_path)
        return paths

    def _write_motion_csv(
        self, path: Path, where: str, params: list[Any]
    ) -> None:
        sql = (
            "SELECT r.id AS round_id, r.session_id, r.module, r.mode, r.round_idx,"
            " rm.data FROM rounds r JOIN round_motion rm ON rm.round_id = r.id"
            + where + " ORDER BY r.id"
        )
        headers = [
            "round_id",
            "session_id",
            "module",
            "mode",
            "round_idx",
            "t_ms",
            "x",
            "y",
            "target_x",
            "target_y",
            "target_r",
            "err",
            "speed",
            "level",
            "target_id",
            "flags",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in self.conn.execute(sql, params):
                try:
                    _, samples = decode_blob(row["data"])
                except ValueError:
                    continue
                base = [
                    row["round_id"],
                    row["session_id"],
                    row["module"],
                    row["mode"],
                    row["round_idx"],
                ]
                for sample in samples:
                    writer.writerow(
                        base
                        + [
                            sample.t_ms,
                            sample.x,
                            sample.y,
                            sample.target_x,
                            sample.target_y,
                            sample.target_r,
                            sample.err,
                            sample.speed,
                            sample.level,
                            sample.target_id,
                            sample.flags,
                        ]
                    )

    def _write_query(self, path: Path, sql: str, params: list[Any]) -> None:
        cursor = self.conn.execute(sql, params)
        headers = [d[0] for d in cursor.description or []]
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in cursor:
                writer.writerow([row[h] for h in headers])

    # -------------------------------------------------------------------- admin

    def clear_sessions(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions")

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()
