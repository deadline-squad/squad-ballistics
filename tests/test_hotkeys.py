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
