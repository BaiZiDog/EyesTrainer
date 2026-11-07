from types import SimpleNamespace

import pygame

from eyestrainer.app import App


class _FakeNotifier:
    available = True

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str]] = []

    def notify(self, hwnd: int, title: str, message: str) -> bool:
        self.calls.append((hwnd, title, message))
        return True


def test_notify_system_only_when_minimized_or_unfocused(monkeypatch):
    notifier = _FakeNotifier()
    app = SimpleNamespace(notifier=notifier, window_minimized=False)
    monkeypatch.setattr(pygame.display, "get_active", lambda: True)
    monkeypatch.setattr(pygame.display, "get_wm_info", lambda: {"window": 123})

    assert App.notify_system(app, "title", "message") is False
    assert notifier.calls == []

    app.window_minimized = True
    assert App.notify_system(app, "title", "message") is True
    assert notifier.calls == [(123, "title", "message")]

    app.window_minimized = False
    monkeypatch.setattr(pygame.display, "get_active", lambda: False)
    assert App.notify_system(app, "title", "message") is True

    assert App.notify_system(app, "forced", "message", force=True) is True
    assert notifier.calls[-1] == (123, "forced", "message")
