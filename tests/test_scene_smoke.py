import pygame

from eyestrainer.app import App
from eyestrainer.core.font import FontBook
from eyestrainer.modules.base import ModuleConfig
from eyestrainer.modules.flick import FlickModule
from eyestrainer.modules.track import TrackModule
from eyestrainer.ui.theme import make_theme


def test_app_starts_and_draws_menu(tmp_path, monkeypatch):
    monkeypatch.setenv("EYESTRAINER_DATA_DIR", str(tmp_path / "data"))
    app = App(windowed_override=True)
    try:
        surface = pygame.Surface((app.theme.width, app.theme.height))
        app.current.draw(surface)
        assert app.current.__class__.__name__ == "MenuScene"
        assert app.storage is not None
    finally:
        app.storage.close()


def test_modules_draw_without_display_dependency():
    surface = pygame.Surface((800, 600))
    theme = make_theme(800, 600, FontBook())
    arena = (40.0, 30.0, 720.0, 540.0)
    flick = FlickModule()
    flick.begin_round(
        ModuleConfig("flick", "chain", 60, False, 50, False, {}), 1, arena
    )
    flick.commit_frame(0.0)
    flick.draw(surface, theme)
    assert len(flick.targets) == 3

    track = TrackModule()
    track.begin_round(
        ModuleConfig("track", "waypoint", 30, False, 50, False, {}), 2, arena
    )
    track.draw(surface, theme)


def test_module_select_clears_stale_mode_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("EYESTRAINER_DATA_DIR", str(tmp_path / "data"))
    app = App(windowed_override=True)
    try:
        from eyestrainer.scenes.module_select import ModuleSelectScene

        scene = ModuleSelectScene(app)
        scene.on_enter()
        pos = scene.buttons["track"].rect.center
        scene.handle_events(
            [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)]
        )
        assert scene.options.module_id == "track"
        assert scene.options.mode == "waypoint"
        assert "mode:chain" not in scene.buttons
        assert "mode:reaction" not in scene.buttons
        assert "mode:waypoint" in scene.buttons
        assert "mode:bounce" in scene.buttons
        for module_id, mode in (("dva", "staircase"), ("peripheral", "adaptive")):
            pos = scene.buttons[module_id].rect.center
            scene.handle_events(
                [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)]
            )
            assert scene.options.module_id == module_id
            assert scene.options.mode == mode
            assert f"mode:{mode}" in scene.buttons
            assert "mode:chain" not in scene.buttons
    finally:
        app.storage.close()


def test_new_module_sessions_and_plans(tmp_path, monkeypatch):
    monkeypatch.setenv("EYESTRAINER_DATA_DIR", str(tmp_path / "data"))
    app = App(windowed_override=True)
    try:
        from eyestrainer.scenes.options import SessionOptions
        from eyestrainer.scenes.session import SessionScene
        from eyestrainer.modules.dva import DvaModule
        from eyestrainer.modules.peripheral import PeripheralModule

        app.settings.training.warmup = False
        dva = SessionScene(app, SessionOptions("dva", "staircase", True, 50))
        dva.on_enter()
        assert isinstance(dva.module, DvaModule)
        assert dva.plan[0].duration_s == 90.0
        surface = pygame.Surface((app.theme.width, app.theme.height))
        dva.draw(surface)
        app.storage.finish_session(dva.session_id, "incomplete")
        dva.session_finished = True
        dva.on_exit()

        per = SessionScene(app, SessionOptions("peripheral", "adaptive", True, 50))
        per.on_enter()
        assert isinstance(per.module, PeripheralModule)
        assert per.plan[0].duration_s == 60.0
        per.draw(surface)
        app.storage.finish_session(per.session_id, "incomplete")
        per.session_finished = True
        per.on_exit()
    finally:
        app.storage.close()
