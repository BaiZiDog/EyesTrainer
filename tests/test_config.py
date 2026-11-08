import json
import sys

from eyestrainer.config import (
    AppPaths,
    DisplayConfig,
    UserSettings,
    SettingsStore,
)


def test_defaults_and_sanitize():
    s = UserSettings.from_dict(
        {
            "display": {"fps_cap": 999, "fullscreen": 0},
            "input": {
                "sensitivity": 99,
                "crosshair": {"style": "bad", "color": "#abcdef", "size": 1000},
            },
            "audio": {"volume": -1},
            "training": {"rounds": 99, "flick_round_s": 1, "rest_s": -5},
            "eye_care": {"reminder_min": 7},
            "calibration": {"screen_diagonal_in": 999, "view_distance_cm": 0},
        }
    )
    assert s.display.fps_cap == 0
    assert s.display.fullscreen is False
    assert s.input.sensitivity == 5.0
    assert s.input.crosshair.style == "cross_dot"
    assert s.input.crosshair.color == "#39FF88"
    assert s.input.crosshair.size == 32
    assert s.audio.volume == 0.0
    assert s.training.rounds == 5
    assert s.training.flick_round_s == 20
    assert s.training.rest_s == 0
    assert s.eye_care.reminder_min == 25
    assert s.calibration.screen_diagonal_in == 80
    assert s.calibration.view_distance_cm == 20
    assert s.language == "zh"


def test_language_roundtrip_and_sanitize():
    s = UserSettings.from_dict({"language": "en"})
    assert s.language == "en"
    s.language = "fr"
    s.sanitize()
    assert s.language == "zh"
    assert UserSettings.from_dict({"language": "EN"}).language == "en"


def test_settings_store_roundtrip(tmp_path):
    paths = AppPaths(
        data_dir=tmp_path,
        db_path=tmp_path / "db.sqlite",
        settings_path=tmp_path / "settings.json",
        export_dir=tmp_path / "exports",
        log_dir=tmp_path / "logs",
    )
    store = SettingsStore(paths)
    s = store.load()
    s.input.sensitivity = 2.5
    s.training.rounds = 4
    s.language = "en"
    store.save(s)
    loaded = store.load()
    assert loaded.input.sensitivity == 2.5
    assert loaded.training.rounds == 4
    assert loaded.language == "en"
    data = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    assert data["input"]["sensitivity"] == 2.5


def test_corrupt_settings_backs_up(tmp_path):
    paths = AppPaths(
        data_dir=tmp_path,
        db_path=tmp_path / "db.sqlite",
        settings_path=tmp_path / "settings.json",
        export_dir=tmp_path / "exports",
        log_dir=tmp_path / "logs",
    )
    paths.ensure()
    paths.settings_path.write_text("{not json", encoding="utf-8")
    store = SettingsStore(paths)
    loaded = store.load()
    assert loaded.input.sensitivity == 1.0
    assert paths.settings_path.with_suffix(".json.bad").exists()


def test_app_paths_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("EYESTRAINER_DATA_DIR", str(tmp_path / "portable"))
    paths = AppPaths.default()
    assert paths.data_dir == (tmp_path / "portable").resolve()
    assert paths.db_path.name == "eyestrainer.db"


def test_app_paths_packaged_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.delenv("EYESTRAINER_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "EyesTrainer.exe"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    paths = AppPaths.default()
    assert paths.data_dir == (tmp_path / "appdata" / "EyesTrainer").resolve()
