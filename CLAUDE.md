# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/DESIGN.md` is the product and measurement specification. Read it before changing training rules, timing, metrics, difficulty adaptation, or the database schema. When code and design disagree, treat the design as intent and update both in the same change.

## Commands

Windows, Git Bash:

```bash
# setup (Python 3.11+; project currently runs on 3.13)
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# run the app
.venv/Scripts/python.exe main.py
# or: .venv/Scripts/python.exe -m eyestrainer

# all tests
.venv/Scripts/python.exe -m pytest -q

# one test file / one test
.venv/Scripts/python.exe -m pytest tests/test_stats.py -q
.venv/Scripts/python.exe -m pytest tests/test_stats.py::test_median -q

# headless scene smoke test
SDL_VIDEODRIVER=dummy .venv/Scripts/python.exe -m pytest tests/test_scene_smoke.py -q

# override data directory (tests, portable mode)
EYESTRAINER_DATA_DIR=/tmp/eyestrainer-data .venv/Scripts/python.exe main.py

# syntax check without a configured linter
.venv/Scripts/python.exe -m compileall -q eyestrainer

# build the onefile EXE and the Inno Setup installer (requires Nuitka/Zig and Inno Setup 6)
build_exe.bat
build_installer.bat
```

Packaged builds use `%APPDATA%/EyesTrainer/` for settings, logs, and SQLite data; the installer creates that directory with `uninsneveruninstall`. Build artifacts stay in `dist/` (gitignored) and are attached to GitHub releases.

No linter is configured. Runtime dependency is `pygame-ce`; development dependency is `pytest`.

## Architecture

```
main.py
└── eyestrainer.app.App
    ├── Window / FramePacer / FrameStats
    ├── InputState (system cursor in menus, relative mouse + virtual crosshair in rounds)
    ├── SceneManager
    │   ├── MenuScene / ModuleSelectScene
    │   ├── SessionScene（回合运行器）── TrainingModule
    │   │                              ├── FlickModule / TrackModule
    │   │                              └── DvaModule / PeripheralModule
    │   ├── ResultsScene / HistoryScene / SettingsScene / CalibrationScene
    ├── Storage (SQLite)
    └── Audio
```

- **`SessionScene`** owns the round lifecycle: countdown, warm-up, round timer, rest, pause, focus-loss handling, and persistence. It feeds the active module a round-relative time `t` that only advances during active play.
- **`TrainingModule`** (`eyestrainer/modules/base.py`) owns only stimuli, hit judgement, adaptive difficulty, and trial/window collection. It does not read the keyboard directly, write the database, or call `time.perf_counter()`.
- **`core/timing.py`** implements the low-latency frame pacer and the round clock. Stimulus onset is stamped in `TrainingModule.commit_frame()` with the round-relative time immediately before `display.flip()`.
- **`core/input.py`** switches between system cursor (menus) and SDL relative mouse + virtual crosshair (active rounds). `Esc` and focus loss release the mouse and pause.
- **`core/storage.py`** is the only SQLite gateway. Schema and metric definitions are in `docs/DESIGN.md` §11–12. Schema is version 3; `_migrate_v2()` adds trajectory columns/table and normalizes legacy track modes, `_migrate_v3()` adds DVA/peripheral trial tables.
- **`core/notify.py`** wraps the Win32 tray notification API so eye-care and session-completion notices remain visible when the window is minimized or unfocused. Notifications are additive to the in-window rest overlay; the app remains offline-only.
- **`core/motion.py`** encodes per-round mouse/target trajectories into zlib-compressed binary blobs and computes advanced flick/track metrics (entry time, correction time, overshoot, tracking lag, jitter). DVA and peripheral rounds do not produce motion blobs.
- **`core/stats.py`** holds median/IQR and rolling-window helpers. **`core/adaptive.py`** holds the hysteresis-based flick and track controllers. **`core/metrics.py`** defines the trial/window aggregations shared by results, history, and storage.
- **`modules/flick.py`** implements chain and reaction modes. **`modules/track.py`** implements bounce and waypoint motion plus time-on-target windows. **`modules/dva.py`** implements the Landolt-C speed staircase. **`modules/peripheral.py`** implements peripheral target/distractor detection at an adaptive eccentricity.
- DVA and peripheral-vision modules are keyboard-driven (`Arrow/WASD` and `Space`) and read keydown events from `InputFrame.events`. They intentionally have no mouse crosshair and no motion blob.
- **`ui/`** is hand-rolled: theme, widgets, charts, HUD. No UI framework.

## Invariants

1. Modules receive round-relative time; they never read wall-clock time. Pauses, rest, and countdowns must not enter reaction times. Tests inject a fake clock.
2. Every stimulus is timestamped in `commit_frame()` before the frame is flipped. Reaction-time resolution is one display frame; do not print precision finer than that.
3. Menus use the OS cursor. Only active rounds grab/hide the mouse and use a virtual crosshair. Pause, focus loss, and results release the mouse and restore the cursor at the crosshair position.
4. Each round stores its RNG seed and each session stores a full config snapshot. Same seed + same config must reproduce target spawns and trajectories.
5. Primary metrics use median and IQR; never substitute means for skewed timing data. Session summaries pool raw trials/windows, not averages of round averages. Do not add an opaque composite score.
6. Adaptive difficulty changes exactly one parameter per module, uses hysteresis, and only affects newly spawned targets or new tracking windows. Record the level with every trial/window.
7. Track statistics accrue only while LMB is held. Track data is stored as 1-second windows plus a compressed per-round motion blob; advanced metrics live on those rows.
8. Trajectories are sampled every active frame for mouse modules (flick/track) and stored once per round in `round_motion`; per-trial and per-window advanced metrics are derived at record time and exported to CSV. Treat the binary blob format as a versioned format (`core/motion.py`).
9. Keyboard modules receive events through `InputFrame.events`; they must not assume the mouse crosshair exists. SessionScene hides the crosshair for `dva` and `peripheral`.
10. SQLite schema changes require a `PRAGMA user_version` migration and a matching update to `docs/DESIGN.md` §12.
11. Data lives in `%APPDATA%/EyesTrainer/` when packaged and `./data/` in development; `EYESTRAINER_DATA_DIR` overrides both. The app is offline-only.
12. v1 is 2D screen-space by design. Do not introduce 3D, weapon models, or game simulation without an explicit scope decision.
13. History defaults to the most recent session with real rounds; module select also defaults to the last used module/mode. Sensitivity is a global user setting, editable in Settings and on module select for mouse modules only.

## Adding a training module

Implement the `TrainingModule` protocol in `eyestrainer/modules/`, register it in the module-select scene, add its storage writer/table (or reuse a generic one), add results and history metric mappings, and update `docs/DESIGN.md` with its rules, metrics, and schema. Keep judgement and adaptive logic pure enough to test with a seeded RNG and injected time.
