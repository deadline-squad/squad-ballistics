"""Hold-key timer for weapons aimed by holding a key (AGS-17).

The AGS-17 emplacement is laid by time: W puts the barrel back to its top
elevation and holding S lowers it at a constant rate (see
`ballistics.Weapon.hold_time`). The timer adds up how long S has been held
since the last W and signals once when the hold time of the target is
reached, so the player can release S on the beep.

The beep comes `lead` seconds early: a player releases S a reaction time
after hearing it (150-300 ms, 40-120 m of range on the AGS-17 lob). The
lead is learnt from the player's own releases: each manual release after
the beep moves it by half of the overshoot (see `learn_lead`).

Keys are read system-wide by `keystate` (evdev or X11);
where they cannot be read `available` is False. Because the keys are
global, S pressed anywhere counts until the next W.

Auto-hold (opt-in): `toggle_auto_hold` makes the app hold S itself for the
time left to the target through a `keyinject.AutoHold`. For mortars it lays
the barrel from scratch: W to the top first (`reset_seconds`), then S for
the whole hold time.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import time

from PyQt6.QtCore import (
    QObject,
    QTimer,
    pyqtSignal
)

from keystate import KEY_S, KEY_W

BEEP_FREQUENCY = 1200
BEEP_MS = 120

# Players tried in order on Linux (PipeWire, PulseAudio, ALSA).
LINUX_PLAYERS = ("pw-play", "paplay", "aplay")

POLL_INTERVAL_MS = 10

# A longer gap between two polls means the UI was frozen: the key state in
# between is unknown, so at most this much of the gap is counted.
MAX_POLL_GAP = 0.05

# Beep this early before the hold time, at first (s): a typical reaction
# time to a sound plus starting the sound player. Each manual release
# after the beep corrects it by LEAD_LEARNING of its overshoot, within
# 0..MAX_LEAD; a release further than MAX_OVERSHOOT off the target was not
# a reaction to the beep and teaches nothing.
DEFAULT_LEAD = 0.2
MAX_LEAD = 0.6
LEAD_LEARNING = 0.5
MAX_OVERSHOOT = 0.6


class HoldTimer(QObject):
    """Counts how long S is held since the last W and signals the target.

    The keys are polled while the timer is `active` (a hold weapon is
    selected), with or without a target, so a W pressed while the target
    is out of range still resets the count. `advance` holds the logic and
    is driven by the poll timer; tests call it directly.
    """

    # Held time, target or key state changed (redraw the readouts).
    changed = pyqtSignal()

    # The held time has just reached the target, less the lead (beep now).
    reached = pyqtSignal()

    # The beep lead was learnt from a release (seconds; save it).
    lead_learned = pyqtSignal(float)

    def __init__(self, key_reader=None, parent=None, clock=time.perf_counter):
        super().__init__(parent)

        self.key_reader = key_reader

        # keyinject.AutoHold while auto-hold is enabled, else None.
        self.auto_hold = None

        self.clock = clock

        self.held = 0.0
        self.target = None
        self.lead = DEFAULT_LEAD

        # The beep sounded and S is still held by the player: its release
        # teaches the lead.
        self._awaiting_release = False

        self._reached = False
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
        return self.key_reader is not None

    @property
    def active(self):
        return self.poll_timer.isActive()

    @property
    def is_reached(self):
        return self.target is not None and self._reached

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
        """Start or stop watching the keys (no effect without a reader)."""
        if not active:
            self.stop_auto_hold()

        if not active or not self.available:
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
        continues from there, and does not beep again if already past it.
        """
        if seconds == self.target:
            return

        # The time left changed: a running auto-hold would miss the target.
        self.stop_auto_hold()

        self.target = seconds
        self._awaiting_release = False

        self._reached = seconds is None or self.held >= seconds - self.beep_lead

        self.changed.emit()

    def reset(self):
        """W pressed: the barrel is back at the top, start counting anew."""
        self.held = 0.0
        self._awaiting_release = False

        self._reached = self.target is None

        self.changed.emit()

    def advance(self, elapsed, s_down, w_down, own_w=False):
        """Account for `elapsed` seconds with the given key states.

        `own_w`: W is the app's own reset (mortar auto-lay), which restarts
        the count without cancelling the auto-hold it belongs to.
        """
        keys_changed = (s_down, w_down) != (self.s_down, self.w_down)
        released = self.s_down and not s_down

        self.s_down, self.w_down = s_down, w_down

        if released and self._awaiting_release:
            self._awaiting_release = False
            self.learn_lead()

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

        if not self._reached and self.target is not None \
                and self.held >= self.target - self.beep_lead:
            self._reached = True
            self._awaiting_release = not self.auto_holding
            self.reached.emit()

    @property
    def beep_lead(self):
        """How early the beep comes: the learnt lead, none while the app
        holds S itself (it releases on time)."""
        return 0.0 if self.auto_holding else self.lead

    def learn_lead(self):
        """S was released by the player after the beep: move the lead by
        part of the overshoot (positive: released late, beep earlier)."""
        if self.target is None:
            return

        overshoot = self.held - self.target

        if abs(overshoot) > MAX_OVERSHOOT:
            return

        lead = min(MAX_LEAD, max(0.0, self.lead + LEAD_LEARNING * overshoot))

        if lead != self.lead:
            self.lead = lead
            self.lead_learned.emit(lead)

    def poll(self):
        now = self.clock()

        elapsed = 0.0 if self._last_poll is None else now - self._last_poll

        self._last_poll = now

        resetting = self.auto_resetting

        self.advance(
            min(elapsed, MAX_POLL_GAP),
            # The reader may not see our own synthetic keys (evdev).
            self.key_reader(KEY_S) or self.auto_pressing,
            self.key_reader(KEY_W) or resetting,
            own_w=resetting
        )


def beep_wav(frequency=BEEP_FREQUENCY, duration_ms=BEEP_MS, rate=22050):
    """A mono 16-bit WAV of a sine tone with short fades (no clicks)."""
    import math

    count = rate * duration_ms // 1000
    fade = max(1, rate * 5 // 1000)

    samples = bytearray()

    for i in range(count):
        envelope = min(1.0, i / fade, (count - 1 - i) / fade)
        value = 0.5 * envelope * math.sin(2 * math.pi * frequency * i / rate)
        samples += struct.pack("<h", int(value * 32767))

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(samples), b"WAVE",
        b"fmt ", 16, 1, 1, rate, rate * 2, 2, 16,
        b"data", len(samples)
    )

    return header + bytes(samples)


_beep_file = None


def linux_beep_command():
    """Command that plays the beep on Linux, None without a player."""
    global _beep_file

    player = next(
        (path for path in map(shutil.which, LINUX_PLAYERS) if path), None
    )

    if player is None:
        return None

    if _beep_file is None or not os.path.exists(_beep_file):
        handle, path = tempfile.mkstemp(prefix="squad-ballistics-", suffix=".wav")

        with os.fdopen(handle, "wb") as f:
            f.write(beep_wav())

        _beep_file = path

    return [player, _beep_file]


def beep():
    """Short high beep that does not block the UI."""
    command = linux_beep_command()

    if command is not None:
        try:
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return
        except OSError:
            pass

    # Often muted on desktops: only the last resort.
    from PyQt6.QtWidgets import QApplication

    QApplication.beep()
