"""Hold-key timer for weapons aimed by holding a key (AGS-17).

The AGS-17 emplacement is laid by time: W puts the barrel back to its top
elevation and holding S lowers it at a constant rate (see
`ballistics.Weapon.hold_time`). The timer adds up how long S has been held
since the last W, which `crosshair` uses to calibrate the hold rate and
to time the auto-hold.

Keys are read system-wide by `keystate` (evdev or X11);
where they cannot be read `available` is False. Because the keys are
global, S pressed anywhere counts until the next W.

Auto-hold (opt-in): `toggle_auto_hold` makes the app hold S itself for the
time left to the target through a `keyinject.AutoHold`. For mortars it lays
the barrel from scratch: W to the top first (`reset_seconds`), then S for
the whole hold time.
"""

import time

from PyQt6.QtCore import (
    QObject,
    QTimer,
    pyqtSignal
)

from keystate import KEY_S, KEY_W

POLL_INTERVAL_MS = 10

# A longer gap between two polls means the UI was frozen. A key that changed
# across the gap changed at an unknown moment, so at most this much of such a
# gap is counted; S held down (and W up) on both sides counts the whole gap.
MAX_POLL_GAP = 0.05


class HoldTimer(QObject):
    """Counts how long S is held since the last W.

    The keys are polled while the timer is `active` (a hold weapon is
    selected), with or without a target, so a W pressed while the target
    is out of range still resets the count. `advance` holds the logic and
    is driven by the poll timer; tests call it directly.
    """

    # Held time, target or key state changed (redraw the readouts).
    changed = pyqtSignal()

    def __init__(self, key_reader=None, parent=None, clock=time.perf_counter):
        super().__init__(parent)

        self.key_reader = key_reader

        # keyinject.AutoHold while auto-hold is enabled, else None.
        self.auto_hold = None

        self.clock = clock

        self.held = 0.0
        self.target = None

        # `counting`: False while the keys are not counted (see `suspend`).
        # `measures_lay`: whether `held` is the S time of a lay from the
        # top; False from `suspend` to the next W.
        self.counting = True
        self.measures_lay = True

        self._w_was_down = False
        self._last_poll = None

        # Key state at the last poll, for the on-screen indicators.
        self.s_down = False
        self.w_down = False

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_INTERVAL_MS)
        self.poll_timer.timeout.connect(self.poll)

    @property
    def available(self):
        """Whether the keys can be read now: a reader exists and, for one
        that knows (keystate.EvdevReader), a keyboard is plugged in."""
        return self.key_reader is not None and getattr(self.key_reader, "available", True)

    @property
    def active(self):
        return self.poll_timer.isActive()

    @property
    def auto_holding(self):
        return self.auto_hold is not None and self.auto_hold.active

    @property
    def auto_resetting(self):
        """The app is holding W itself, before the hold (mortar auto-lay)."""
        return self.auto_holding and self.auto_hold.resetting.is_set()

    @property
    def auto_pressing(self):
        """The app is holding S itself."""
        return self.auto_holding and self.auto_hold.pressing.is_set()

    def toggle_auto_hold(self, reset_seconds=0.0):
        """Hold S for the time left to the target; again: release it.

        With `reset_seconds` > 0 the app first holds W that long, which puts
        the barrel back to its top, then S for the whole target time.
        Returns True when a hold was started.
        """
        if self.auto_hold is None:
            return False

        if self.auto_hold.active:
            self.stop_auto_hold()
            return False

        if self.target is None or not self.active:
            return False

        if reset_seconds > 0:
            started = self.auto_hold.start(self.target, reset_seconds)
        else:
            started = self.auto_hold.start(self.target - self.held)

        self.changed.emit()

        return started

    def stop_auto_hold(self):
        if self.auto_hold is not None:
            self.auto_hold.stop()

    def set_active(self, active):
        """Start or stop watching the keys (no effect without a reader).

        A reader whose keyboards are unplugged right now is still polled:
        polling is what finds them again when they come back.
        """
        if not active:
            self.stop_auto_hold()

        if not active or self.key_reader is None:
            self.poll_timer.stop()
            self._last_poll = None
            self.s_down = self.w_down = False
            return

        if not self.poll_timer.isActive():
            self._last_poll = self.clock()
            self.poll_timer.start()

    def set_target(self, seconds):
        """Track a new hold time; None means no target (keys still watched).

        The held time is kept: a new target while S is already partly held
        continues from there.
        """
        if seconds == self.target:
            return

        # The time left changed: a running auto-hold would miss the target.
        self.stop_auto_hold()

        self.target = seconds

        self.changed.emit()

    def reset(self):
        """W pressed: the barrel is back at the top, start counting anew."""
        self.held = 0.0
        self.measures_lay = True

        self.changed.emit()

    def suspend(self):
        """Stop counting the keys: the app is about to press W and S itself
        in taps (the lay on the mortar's sight), which do not lay from the
        top. Until the next W after `resume`, `held` is not a lay's hold
        time (`measures_lay` is False), so it cannot calibrate the rate."""
        self.counting = False
        self.measures_lay = False

    def resume(self):
        """Count the keys again (after `suspend`)."""
        self.counting = True

    def advance(self, elapsed, s_down, w_down, own_w=False):
        """Account for `elapsed` seconds with the given key states.

        `own_w`: W is the app's own reset (mortar auto-lay), which restarts
        the count without cancelling the auto-hold it belongs to. While
        suspended the key states are followed but nothing is counted.
        """
        keys_changed = (s_down, w_down) != (self.s_down, self.w_down)

        self.s_down, self.w_down = s_down, w_down

        if not self.counting:
            self._w_was_down = w_down

            if keys_changed:
                self.changed.emit()

            return

        if w_down and not self._w_was_down:
            if not own_w:
                self.stop_auto_hold()
            self.reset()
        elif keys_changed:
            self.changed.emit()

        self._w_was_down = w_down

        if not s_down or w_down:
            return

        self.held += elapsed

        self.changed.emit()

    def poll(self):
        now = self.clock()

        elapsed = 0.0 if self._last_poll is None else now - self._last_poll

        self._last_poll = now

        resetting = self.auto_resetting

        # Our own keys count from the AutoHold flags: evdev skips the app's
        # virtual keyboards (keystate), X11 sees them as any other key.
        s_down = self.key_reader(KEY_S) or self.auto_pressing
        w_down = self.key_reader(KEY_W) or resetting

        # S held through a UI freeze: the whole gap was held
        if not (s_down and self.s_down and not w_down and not self.w_down):
            elapsed = min(elapsed, MAX_POLL_GAP)

        self.advance(elapsed, s_down, w_down, own_w=resetting)
