from __future__ import annotations

import argparse
import ctypes
import logging
import math
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from .config import AppPaths, SettingsStore, UserSettings
from .core.audio import Audio
from .core.font import FontBook
from .core.input import AimInput
from .core.notify import WindowsNotifier
from .core.storage import Storage
from .core.timing import FramePacer, FrameStats
from .ui.hud import draw_debug, draw_dim
from .ui.theme import make_theme

if TYPE_CHECKING:
    from .scenes.base import Scene


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _detect_refresh_rate() -> int:
    try:
        current = getattr(pygame.display, "get_current_refresh_rate", None)
        if current is not None:
            rate = int(current())
            if rate > 0:
                return rate
    except Exception:
        pass
    try:
        rates = pygame.display.get_desktop_refresh_rates()
        if isinstance(rates, dict):
            values = []
            for item in rates.values():
                if isinstance(item, (list, tuple)):
                    values.extend(item)
                else:
                    values.append(item)
        else:
            values = list(rates)
        parsed = [int(v) for v in values if v and float(v) > 0]
        if parsed:
            return max(parsed)
    except Exception:
        pass
    return 60


class EyeCareTracker:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.accumulated = 0.0
        self.overlay_remaining = 0.0

    @property
    def active(self) -> bool:
        return self.overlay_remaining > 0

    def add_active(self, real_dt: float) -> None:
        if self.active:
            return
        minutes = self.app.settings.eye_care.reminder_min
        if minutes <= 0:
            self.accumulated = 0.0
            return
        self.accumulated += max(0.0, real_dt)
        if self.accumulated >= minutes * 60:
            self.accumulated = 0.0
            self.overlay_remaining = 20.0
            self.app.notify_system(
                "EyesTrainer · 休息提醒",
                "已训练较长时间，请看向 6 米外至少 20 秒。",
                force=True,
            )
            hook = getattr(self.app.current, "on_eye_rest_start", None)
            if callable(hook):
                hook()

    def update(self, real_dt: float) -> None:
        if not self.active:
            return
        self.overlay_remaining = max(0.0, self.overlay_remaining - real_dt)
        if self.overlay_remaining <= 0:
            hook = getattr(self.app.current, "on_eye_rest_end", None)
            if callable(hook):
                hook()


class App:
    def __init__(self, windowed_override: bool = False) -> None:
        _enable_dpi_awareness()
        pygame.init()
        self.paths = AppPaths.default()
        self.paths.ensure()
        self._setup_logging()
        self.settings_store = SettingsStore(self.paths)
        self.settings = self.settings_store.load()
        if windowed_override:
            self.settings.display.fullscreen = False
        self.running = True
        self.debug = False
        self.display_generation = 0
        self.refresh_rate = 60
        self.frame_budget = 1.0 / 60.0
        self.screen = pygame.Surface((1280, 720))
        self._apply_display(initial=True)
        self.notifier = WindowsNotifier()
        self.window_minimized = False
        try:
            self.notifier.set_window(
                int(pygame.display.get_wm_info().get("window", 0))
            )
        except pygame.error:
            pass

        self.fonts = FontBook()
        self.theme = make_theme(self.screen.get_width(), self.screen.get_height(), self.fonts)
        self.storage = Storage(self.paths.db_path)
        orphans = self.storage.mark_orphans_incomplete()
        if orphans:
            logging.info("Marked %s orphan session(s) incomplete", orphans)
        self.audio = Audio(self.settings.audio)
        self.input = AimInput()
        self.frame_stats = FrameStats()
        self.frame_stats.set_budget(self.frame_budget)
        self.pacer = FramePacer(self._effective_fps_cap(), self.settings.display.low_latency)
        self.eye_care = EyeCareTracker(self)

        from .scenes.menu import MenuScene

        self.scene_stack: list[Scene] = [MenuScene(self)]
        self.scene_stack[0].on_enter()
        logging.info(
            "Started EyesTrainer display=%sx%s fullscreen=%s refresh=%s data_dir=%s",
            self.screen.get_width(),
            self.screen.get_height(),
            self.settings.display.fullscreen,
            self.refresh_rate,
            self.paths.data_dir,
        )

    @property
    def current(self) -> "Scene":
        return self.scene_stack[-1]

    def _setup_logging(self) -> None:
        log_path = self.paths.log_dir / "eyestrainer.log"
        handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.handlers.clear()
        root.addHandler(handler)

    def _apply_display(self, initial: bool = False) -> None:
        display = self.settings.display
        try:
            desktop = pygame.display.get_desktop_sizes()[0]
            desktop_w, desktop_h = int(desktop[0]), int(desktop[1])
        except (pygame.error, IndexError):
            desktop_w, desktop_h = 1280, 720
        if display.fullscreen:
            size = (desktop_w, desktop_h)
            flags = pygame.FULLSCREEN
        else:
            width = min(1600, max(960, desktop_w - 80))
            height = int(width * 9 / 16)
            if height > desktop_h - 80:
                height = max(640, desktop_h - 80)
                width = int(height * 16 / 9)
            size = (width, height)
            flags = 0
        vsync = 1 if display.vsync else 0
        try:
            self.screen = pygame.display.set_mode(size, flags, vsync=vsync)
        except (pygame.error, TypeError):
            try:
                self.screen = pygame.display.set_mode(size, flags)
            except pygame.error:
                self.settings.display.fullscreen = False
                self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("EyesTrainer")
        self.refresh_rate = _detect_refresh_rate()
        self.frame_budget = 1.0 / max(1, self.refresh_rate)
        if not initial:
            self.theme = make_theme(
                self.screen.get_width(), self.screen.get_height(), self.fonts
            )
            self.frame_stats.set_budget(self.frame_budget)
            self.pacer.set_fps(self._effective_fps_cap())
            self.pacer.low_latency = self.settings.display.low_latency
            self.display_generation += 1

    def _effective_fps_cap(self) -> int:
        cap = self.settings.display.fps_cap
        return self.refresh_rate if cap == 0 else cap

    def apply_display_settings(self) -> None:
        self.input.exit_gameplay()
        self._apply_display(initial=False)
        try:
            self.notifier.set_window(
                int(pygame.display.get_wm_info().get("window", 0))
            )
        except pygame.error:
            pass
        self.settings_store.save(self.settings)
        logging.info(
            "Display reconfigured: %sx%s refresh=%s",
            self.screen.get_width(),
            self.screen.get_height(),
            self.refresh_rate,
        )

    def save_settings(self) -> None:
        self.settings_store.save(self.settings)
        self.audio.apply_config(self.settings.audio)

    def notify_system(self, title: str, message: str, force: bool = False) -> bool:
        """Show a Win32 tray notification; default only when minimized/unfocused."""
        notifier = getattr(self, "notifier", None)
        if notifier is None or not notifier.available:
            return False
        if not force and not (
            self.window_minimized or not pygame.display.get_active()
        ):
            return False
        try:
            hwnd = int(pygame.display.get_wm_info().get("window", 0))
        except pygame.error:
            return False
        return notifier.notify(hwnd, title, message)

    def switch_scene(self, scene: "Scene") -> None:
        while self.scene_stack:
            self.scene_stack.pop().on_exit()
        scene.on_enter()
        self.scene_stack = [scene]

    def push_scene(self, scene: "Scene") -> None:
        scene.on_enter()
        self.scene_stack.append(scene)

    def pop_scene(self) -> None:
        if len(self.scene_stack) <= 1:
            return
        popped = self.scene_stack.pop()
        popped.on_exit()
        self.current.on_enter()

    def run(self) -> None:
        last = time.perf_counter()
        try:
            while self.running:
                now = time.perf_counter()
                real_dt = max(0.0, now - last)
                last = now
                sim_dt = min(real_dt, 0.05)

                events = pygame.event.get()
                self.input.begin_frame()
                self.input.process_events(events)

                for event in events:
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                        self.debug = not self.debug
                    elif event.type == getattr(pygame, "WINDOWMINIMIZED", -1):
                        self.window_minimized = True
                    elif event.type in (
                        getattr(pygame, "WINDOWRESTORED", -1),
                        getattr(pygame, "WINDOWSHOWN", -1),
                    ):
                        self.window_minimized = False

                if not self.eye_care.active:
                    self.current.handle_events(events)
                    self.current.update(sim_dt, real_dt)

                self.eye_care.update(real_dt)
                scene = self.current
                self.screen.fill(self.theme.bg)
                scene.draw(self.screen)
                scene.commit_frame()
                if self.debug:
                    draw_debug(
                        self.screen,
                        self.theme,
                        self.frame_stats.avg_fps,
                        self.frame_stats.avg_ms,
                        self.frame_stats.p99_ms,
                        self.frame_stats.long_frames,
                    )
                if self.eye_care.active:
                    self._draw_eye_care()
                pygame.display.flip()
                self.frame_stats.record(real_dt)
                self.pacer.wait()
        except Exception:
            logging.exception("Unhandled exception in main loop")
            raise
        finally:
            self.shutdown()

    def _draw_eye_care(self) -> None:
        draw_dim(self.screen, self.theme, 225)
        theme = self.theme
        width = min(int(620 * theme.ui), self.screen.get_width() - 80)
        height = int(280 * theme.ui)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
        theme.panel_rect(self.screen, rect, radius=int(16 * theme.ui))
        theme.text(
            self.screen,
            "休息一下",
            (rect.centerx, rect.top + int(46 * theme.ui)),
            size=38,
            color=theme.accent,
            bold=True,
            anchor="center",
        )
        theme.text(
            self.screen,
            "看远处 20 英尺（约 6 米）外至少 20 秒",
            (rect.centerx, rect.top + int(104 * theme.ui)),
            size=20,
            color=theme.text_color,
            anchor="center",
        )
        theme.text(
            self.screen,
            "顺便眨眼、放松肩颈",
            (rect.centerx, rect.top + int(142 * theme.ui)),
            size=18,
            color=theme.muted,
            anchor="center",
        )
        remaining = int(math.ceil(self.eye_care.overlay_remaining))
        theme.text(
            self.screen,
            f"{remaining}s",
            (rect.centerx, rect.bottom - int(52 * theme.ui)),
            size=34,
            color=theme.warning,
            bold=True,
            anchor="center",
        )

    def shutdown(self) -> None:
        try:
            for scene in reversed(self.scene_stack):
                scene.on_exit()
            self.scene_stack.clear()
            self.save_settings()
            self.storage.close()
        finally:
            self.notifier.remove()
            pygame.quit()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="EyesTrainer")
    parser.add_argument("--windowed", action="store_true", help="run in a window")
    parser.add_argument("--data-dir", default=None, help="override data directory")
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ["EYESTRAINER_DATA_DIR"] = args.data_dir
    app = App(windowed_override=args.windowed)
    app.run()


if __name__ == "__main__":
    main()
