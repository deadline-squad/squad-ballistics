import sys

from PyQt6.QtCore import QObject

import hotkeys


class Window(QObject):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def act(self):
        self.calls += 1
        raise RuntimeError("the action failed")


def test_a_mouse_button_that_bounces_fires_once(qapp):
    """A worn switch reports up and down again within milliseconds: one
    click must not flip a toggle twice. A key is not debounced."""
    window = Window()
    window.act = lambda: window.__setattr__("calls", window.calls + 1)
    pressed = {"Mouse4": False, "F8": False}
    now = [0.0]

    hotkeys._start_polling(
        window,
        [("Mouse4", "act"), ("F8", "act")],
        lambda code: pressed["Mouse4"] if code == hotkeys.KEYS["Mouse4"] else pressed["F8"],
        clock=lambda: now[0],
    )
    timer = window._hotkey_poller

    def click(key, gap):
        pressed[key] = True
        timer.timeout.emit()
        pressed[key] = False
        timer.timeout.emit()
        now[0] += gap

    click("Mouse4", 0.03)
    click("Mouse4", 0.03)
    assert window.calls == 1

    now[0] += hotkeys.MOUSE_DEBOUNCE_SECONDS
    click("Mouse4", 0.03)
    assert window.calls == 2

    click("F8", 0.03)
    click("F8", 0.03)
    assert window.calls == 4
    timer.stop()


def test_a_mouse_button_has_no_window_shortcut(qapp):
    window = Window()
    window.config = {"hotkeys": {"toggle_view": "Mouse4", "reset_offset": "F9"}}
    window.act = lambda: None
    window.reset_offset = window.toggle_view = window.act

    hotkeys.setup_hotkeys(window)

    assert len(window._shortcuts) == 1
    hotkeys.teardown_hotkeys(window)


def test_a_failing_action_fires_once_per_key_press(qapp, monkeypatch):
    """The key stays down for many polls: an action that raises must not
    run again on each of them (each failure opens a crash dialog)."""
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *info: errors.append(info))
    window = Window()
    down = [True]

    hotkeys._start_polling(window, [("F8", "act")], lambda code: down[0])
    timer = window._hotkey_poller

    for _ in range(5):
        timer.timeout.emit()

    assert window.calls == 1
    assert len(errors) == 1

    down[0] = False
    timer.timeout.emit()
    down[0] = True
    timer.timeout.emit()

    assert window.calls == 2
    timer.stop()
