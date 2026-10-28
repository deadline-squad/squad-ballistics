"""Hold-key timer for weapons aimed by holding a key (AGS-17).

The AGS-17 emplacement is laid by time: W puts the barrel back to its top
elevation and holding S lowers it at a constant rate (see
`ballistics.Weapon.hold_time`). The timer adds up how long S has been held
since the last W and signals once when the hold time of the target is
reached, so the player can release S on the beep.

Keys are read with GetAsyncKeyState, which sees them while the game has the
focus; it does not work on other systems (`available` is then False), and
not for a game started as administrator unless this app is too.
"""

import sys
import time

from PyQt6.QtCore import (
    QObject,
    QTimer,
    pyqtSignal
)

VK_S = 0x53
VK_W = 0x57

POLL_INTERVAL_MS = 10


def windows_key_reader():
    """`reader(vk) -> bool` for the physical key state, None off Windows."""
    if sys.platform != "win32":
        return None

    import ctypes

    user32 = ctypes.windll.user32

    return lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)


class HoldTimer(QObject):
    """Counts how long S is held and signals when the target time is reached.

    Polling only runs while a target is set. `advance` holds the logic and
    is driven by the poll timer; tests call it directly.
    """

    # Held time or target changed (redraw the readouts).
    changed = pyqtSignal()

    # The held time has just reached the target (beep now).
    reached = pyqtSignal()

    def __init__(self, key_reader=None, parent=None):
        super().__init__(parent)

        self.key_reader = key_reader

        self.held = 0.0
        self.target = None

        self._reached = False
        self._w_was_down = False
        self._last_poll = None

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_INTERVAL_MS)
        self.poll_timer.timeout.connect(self.poll)

    @property
    def available(self):
        return self.key_reader is not None

    @property
    def is_reached(self):
        return self.target is not None and self._reached

    def set_target(self, seconds):
        """Track a new hold time; None stops the timer.

        The held time is kept: a new target while S is already partly held
        continues from there, and does not beep again if already past it.
        """
        if seconds == self.target:
            return

        self.target = seconds

        self._reached = seconds is None or self.held >= seconds

        if seconds is None or not self.available:
            self.poll_timer.stop()
            self._last_poll = None
        elif not self.poll_timer.isActive():
            self._last_poll = time.monotonic()
            self.poll_timer.start()

        self.changed.emit()

    def reset(self):
        """W pressed: the barrel is back at the top, start counting anew."""
        self.held = 0.0

        self._reached = self.target is None

        self.changed.emit()

    def advance(self, elapsed, s_down, w_down):
        """Account for `elapsed` seconds with the given key states."""
        if w_down and not self._w_was_down:
            self.reset()

        self._w_was_down = w_down

        if not s_down or w_down:
            return

        self.held += elapsed

        self.changed.emit()

        if not self._reached and self.target is not None \
                and self.held >= self.target:
            self._reached = True
            self.reached.emit()

    def poll(self):
        now = time.monotonic()

        elapsed = 0.0 if self._last_poll is None else now - self._last_poll

        self._last_poll = now

        self.advance(
            elapsed,
            self.key_reader(VK_S),
            self.key_reader(VK_W)
        )


def beep():
    """Short high beep that does not block the UI."""
    if sys.platform == "win32":
        import threading
        import winsound

        threading.Thread(
            target=winsound.Beep,
            args=(1200, 120),
            daemon=True
        ).start()
        return

    from PyQt6.QtWidgets import QApplication

    QApplication.beep()
