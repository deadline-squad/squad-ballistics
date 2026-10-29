"""Mortar laying on the elevation and bearing it shows on the screen.

While the player is on the mortar, the app reads the elevation off its
scale (`sightreader`) and the bearing off the HUD compass
(`compassreader`), and holds the keys itself until the screen shows the
target, so neither the rates nor where the barrel was left matter. Each
axis is laid the same way (a `SightLayer` with its `Axis`: W/S for the
elevation in mils, D/A for the bearing in degrees, which wraps at 360):

1. two readings that agree confirm the sight is seen;
2. the key towards the target is held (W raises the barrel, S lowers it)
   while the sight is read; the rate is measured from the readings and the
   key is released when the target is about to be reached. A hold ends
   without the target when the reading stops moving (the barrel's end) or
   takes far longer than the error needs;
3. after the barrel stops, the rest is covered by taps timed with the
   measured rate, until the sight is within TOLERANCE of the target.

The compass strip lags behind a turn, so the bearing is read from the
number alone while the barrel moves; the strip confirms it only when the
barrel is still (the confirm and settle phases).

Everything runs on the GUI thread (screen grabs are GUI-thread only) from
Qt timers; a reading takes a few tens of milliseconds. Whatever goes wrong
inside a timer callback releases the key before the error is raised.
"""

import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from compassreader import SEARCH_TOP, STILL_TOLERANCE, STRIP_HALF_WIDTH, TICK_TOLERANCE, read_compass
from sightreader import REFERENCE_HEIGHT, GrayImage, read_scale

# Done when the sight is this close to the target (mils).
TOLERANCE = 0.5

# Rate of the sight while W or S is held (mil/s), until measured: measured
# on a 81 mm mortar sight video (about 46 mil/s). The game moves the barrel
# a fixed step for every frame the key is down (0.075 degree, 1.33 mil,
# times the view's sensitivity), so the rate depends on the frame rate.
DEFAULT_RATE = 46.0

# Readings while holding, and the wait for the barrel to stop after a
# release before reading it (ms): a few frames of the game and the screen.
READ_INTERVAL_MS = 30
SETTLE_MS = 150

# The rate of a hold is measured over its last RATE_WINDOW readings (the
# first, from before the barrel moved, is left out): 8 readings of a
# barrel that moves a step per 60 fps frame give it within 2%.
RATE_WINDOW = 8

# A hold whose reading has not moved for STALL_TICKS readings in a row is
# at the barrel's end (or its key does not reach the game); a hold ends
# after HOLD_FACTOR times what the error needs at the rate, plus HOLD_SLACK
# seconds.
STALL_TICKS = 10
HOLD_FACTOR = 2.0
HOLD_SLACK = 1.0

# Release this long before the target is predicted, at first: the time
# from a frame on the screen to the game seeing the key up (s). Each hold's
# overshoot corrects it, up to MAX_LEAD.
RELEASE_LEAD = 0.03
MAX_LEAD = 0.3

# Taps: shortest and longest (s; further than the longest tap covers, the
# key is held); a tap that moved the sight less than MIN_MOVE mils is
# retried twice as long. A lay gives up after MAX_MOVES holds and taps.
MIN_TAP = 0.015
MAX_TAP = 0.25
MIN_MOVE = 0.2
MAX_MOVES = 12

# Readings in a row that may fail (the scale hidden by smoke, a flash)
# before the lay gives up.
MAX_MISSES = 5

# Two readings this close (mils) confirm the first one; a reading this
# far from the one expected is a misread and is skipped.
CONFIRM = 1.0
MAX_JUMP = 15.0

# Where the scale is grabbed, in screen heights from the centre: left,
# right (left of the centre), and above/below the centre line.
GRAB_LEFT = 0.47
GRAB_RIGHT = 0.08
GRAB_HALF_HEIGHT = 0.16

# Margin around the compass strip in its grab (px at 1080p).
COMPASS_MARGIN = 20


@dataclass(frozen=True)
class Axis:
    """What a SightLayer lays: how to get the value from a reading, and
    the axis' own limits (in its unit: mils or degrees).

    `value`: the axis' value of a reading; `default_rate`: units per second
    while a key is held, until measured; `tolerance`, `confirm`,
    `max_jump`, `min_move`: as TOLERANCE, CONFIRM, MAX_JUMP and MIN_MOVE
    for the elevation; `max_rate`: the fastest the game can move it (units
    per second), which bounds a reading's jump until the rate is measured;
    `period`: values wrap at it (bearings at 360), None for none.
    """

    value: Callable[[object], float]
    default_rate: float
    tolerance: float
    confirm: float
    max_jump: float
    min_move: float
    max_rate: float
    period: float | None = None

    def difference(self, a, b):
        """a - b, the short way round on a wrapping axis."""
        if self.period is None:
            return a - b

        half = self.period / 2

        return (a - b + half) % self.period - half


# The mortar's barrel turns a fixed step for every game frame W or S is
# down, up to 25 degrees/s (USQTurretMovementComponent MaxPitch of the
# mortar, decompiled from the game server): 6400 mils / 360 degrees * 25.
ELEVATION = Axis(
    value=lambda reading: reading.mils,
    default_rate=DEFAULT_RATE,
    tolerance=TOLERANCE,
    confirm=CONFIRM,
    max_jump=MAX_JUMP,
    min_move=MIN_MOVE,
    max_rate=444.0,
)

# The mortar turns a fixed step for every game frame A or D is down
# (USQTurretMovementComponent of the mortar, decompiled from the game
# server: 0.25 degree times the view's sensitivity, up to MaxYaw 50
# degrees/s), so its rate grows with the frame rate: 15 degrees/s at 60
# fps. The lay measures the rate and the step and stops within half of the
# step.
BEARING = Axis(
    value=lambda reading: reading.degrees,
    default_rate=15.0,
    tolerance=0.1,
    confirm=0.3,
    max_jump=10.0,
    min_move=0.05,
    max_rate=50.0,
    period=360.0,
)


@dataclass(frozen=True)
class Sight:
    """A grab of the scale: the image and the screen centre in it."""

    image: GrayImage
    centre_x: int
    centre_y: int
    scale: float


class ScreenSight:
    """Grabs the scale region of the overlay's screen around its centre."""

    def __init__(self, overlay):
        self.overlay = overlay

    def region(self):
        """(left, top, right, bottom) of the grab in the screen's logical
        pixels, or None."""
        overlay = self.overlay
        height = overlay.height()
        centre_x, centre_y = overlay.center_x, overlay.center_y
        left = max(0, round(centre_x - GRAB_LEFT * height))
        right = round(centre_x - GRAB_RIGHT * height)
        top = max(0, round(centre_y - GRAB_HALF_HEIGHT * height))
        bottom = min(height, round(centre_y + GRAB_HALF_HEIGHT * height))

        if right <= left or bottom <= top:
            return None

        return left, top, right, bottom

    def grab_image(self):
        """The region as a QImage, or None if the screen can't be grabbed
        (a Wayland session without XWayland)."""
        screen = self.overlay.screen() or QGuiApplication.primaryScreen()
        region = self.region()

        if screen is None or region is None:
            return None

        left, top, right, bottom = region
        image = screen.grabWindow(0, left, top, right - left, bottom - top).toImage()

        if image.isNull() or image.width() == 0:
            return None

        return image

    def grab(self):
        """The region as a Sight, or None."""
        image = self.grab_image()

        if image is None:
            return None

        left, top, right, _ = self.region()

        # Device pixels per logical pixel (display scaling)
        ratio = image.width() / (right - left)

        return Sight(
            GrayImage.from_qimage(image),
            round((self.overlay.center_x - left) * ratio),
            round((self.overlay.center_y - top) * ratio),
            self.overlay.height() * ratio / REFERENCE_HEIGHT
        )

    def compass_region(self):
        """(left, top, right, bottom) of the compass grab in the screen's
        logical pixels: the strip at the bottom centre, or None."""
        overlay = self.overlay
        height = overlay.height()
        scale = height / REFERENCE_HEIGHT
        half = (STRIP_HALF_WIDTH + COMPASS_MARGIN) * scale
        # The compass is at the screen's centre, wherever the crosshair is
        centre = overlay.width() / 2
        left = max(0, round(centre - half))
        right = min(overlay.width(), round(centre + half))
        top = max(0, round(height - SEARCH_TOP * scale))

        if right <= left or height <= top:
            return None

        return left, top, right, height

    def grab_compass(self):
        """The compass region as a Sight (`centre_x` continuous, the screen
        centre's), or None."""
        screen = self.overlay.screen() or QGuiApplication.primaryScreen()
        region = self.compass_region()

        if screen is None or region is None:
            return None

        left, top, right, bottom = region
        image = screen.grabWindow(0, left, top, right - left, bottom - top).toImage()

        if image.isNull() or image.width() == 0:
            return None

        ratio = image.width() / (right - left)

        return Sight(
            GrayImage.from_qimage(image),
            (self.overlay.width() / 2 - left) * ratio,
            0,
            self.overlay.height() * ratio / REFERENCE_HEIGHT
        )


class CompassReader:
    """Reads a compass grab (a Sight) for a SightLayer on the BEARING axis
    (`compassreader.read_compass` with the digit pictures `digits`)."""

    def __init__(self, digits):
        self.digits = digits

    def __call__(self, sight, moving=None):
        """The compass reading (compassreader.CompassReading) on `sight`,
        or None. `moving` tells whether the barrel is turning: the strip
        lags behind a turn, so then (True) the number is taken alone; when
        it is still (False) the strip must confirm the number closely;
        None (not known) allows for a lagging strip."""
        if sight is None:
            return None

        if moving is None:
            tolerance = TICK_TOLERANCE
        else:
            tolerance = None if moving else STILL_TOLERANCE

        return read_compass(sight.image, sight.centre_x, sight.scale, self.digits, tolerance)


def read_sight(sight, templates):
    """The elevation on a grab (sightreader.Reading), or None."""
    if sight is None:
        return None

    return read_scale(sight.image, sight.centre_x, sight.centre_y, sight.scale, templates)


class SightLayer(QObject):
    """Lays one axis until the screen shows the target (closed loop).

    `grab()` returns a Sight or None, `target()` the value to lay to (None
    stops the lay); `raise_key` and `lower_key` are key injectors that move
    the value up and down (W and S for the elevation, D and A for the
    bearing). `axis` says what is laid (ELEVATION by default); `reader`
    turns a grab into a reading, `reader(sight, moving)` with `moving` true
    while the barrel turns (default: the elevation scale with `templates`).
    `clock` gives the time in seconds.
    """

    # Every reading while laying (sightreader.Reading).
    read = pyqtSignal(object)

    # The lay ended: the last reading (None if the sight was lost) and
    # whether it is on the target.
    finished = pyqtSignal(object, bool)

    def __init__(self, grab, templates, target, raise_key, lower_key, parent=None,
                 clock=time.perf_counter, axis=ELEVATION, reader=None):
        super().__init__(parent)

        self.grab = grab
        self.templates = templates
        self.target = target
        self.raise_key = raise_key
        self.lower_key = lower_key
        self.clock = clock
        self.axis = axis
        self.reader = reader or (lambda sight, moving: read_sight(sight, self.templates))

        # Rate (units/s), the shortest tap that moves the barrel (s) and its
        # move (the game's frame step), measured and kept between lays.
        self.rate = axis.default_rate
        self.rate_measured = False
        self.short_tap = MIN_TAP
        self.step_size = 0.0
        self.lead = RELEASE_LEAD

        self.key = None
        self.phase = None
        self.last = None
        self.last_time = 0.0
        self.stopped = False
        self.failure = None
        self.samples = []
        self.moves = 0
        self.tap = 0.0
        self.misses = 0
        self.settle_until = 0.0
        self.hold_started = 0.0
        self.hold_error = 0.0
        self.hold_rate = 0.0
        self.still_ticks = 0

        # The last move: (time pressed, value then, direction, time released)
        self.move = None

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(READ_INTERVAL_MS)
        self.timer.timeout.connect(self.step)

        self.release_timer = QTimer(self)
        self.release_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.release_timer.setSingleShot(True)
        self.release_timer.timeout.connect(self.end_move)

    @property
    def active(self):
        """Whether a lay is under way."""
        return self.phase is not None

    def reading(self, moving=False):
        """A reading now, as (time, reading or None); `moving`: the barrel
        is turning (see the reader)."""
        now = self.clock()

        return now, self.reader(self.grab(), moving)

    def value(self, reading):
        """The axis' value of a reading."""
        return self.axis.value(reading)

    def difference(self, a, b):
        """a - b on the layer's axis (the short way round on a bearing)."""
        return self.axis.difference(a, b)

    @contextmanager
    def failsafe(self):
        """Whatever is raised inside releases the key and ends the lay
        before it goes on; the lay is over, so nothing raises it again."""
        try:
            yield
        except BaseException:
            if self.active:
                self.finish(False, "error")

            raise

    def start(self):
        """Begin a lay; False if the sight is not seen or there is no
        target (the caller can fall back to the timed lay)."""
        if self.active or self.target() is None:
            return False

        now, first = self.reading()

        if first is None:
            return False

        self.last = first
        self.last_time = now
        self.stopped = False
        self.failure = None
        self.moves = 0
        self.tap = 0.0
        self.misses = 0
        self.move = None
        self.phase = "confirm"
        self.timer.start()

        return True

    def stop(self):
        """Release the key and end the lay (the last reading is kept);
        `stopped` tells the end apart from one the lay came to itself."""
        if not self.active:
            return

        self.stopped = True
        self.finish(False, "stopped")

    def finish(self, on_target, failure=None):
        """End the lay: stop the timers, release the key, tell `finished`.

        `failure` says why the lay is not on the target: "stopped" (by the
        player), "target" (gone), "lost" (the sight was not read),
        "moves" (MAX_MOVES holds and taps were not enough), "stalled" (the
        barrel stopped under a held key, at its end), "timeout" (a hold took
        far longer than the error needs), "error" (something raised); None
        on the target. The caller can show it from `failure`.
        """
        self.timer.stop()
        self.release_timer.stop()

        try:
            self.release()
        finally:
            self.phase = None
            self.failure = None if on_target else failure
            self.finished.emit(self.last, on_target)

    def press(self, key):
        """Press `key`: a move towards the key's direction, from now."""
        self.key = key
        self.move = (self.clock(), self.value(self.last), 1 if key is self.raise_key else -1, None)
        key.press()

    def release(self):
        """Release the key, if one is down."""
        key, self.key = self.key, None

        if key is None:
            return

        try:
            key.release()
        finally:
            if self.move is not None:
                pressed, value, direction, _ = self.move
                self.move = (pressed, value, direction, self.clock())

    def held_since(self, since, now):
        """Seconds between `since` and `now` that a key was down."""
        if self.move is None:
            return 0.0

        pressed, _, _, released = self.move

        return max(0.0, min(now, now if released is None else released) - max(since, pressed))

    def expected(self, now):
        """Where the sight should be, and how far off a reading may be: the
        last reading, moved on at the rate for the time a key was held since
        then. The rate may be off by half once it is measured; until then
        the barrel may be as fast as the game allows."""
        value = self.value(self.last)
        held = self.held_since(self.last_time, now)

        if not held:
            return value, self.axis.max_jump

        direction = self.move[2]
        slack = 0.5 * self.rate if self.rate_measured else self.axis.max_rate

        return value + direction * self.rate * held, self.axis.max_jump + slack * held

    def step(self):
        """Timer tick: read the sight and act on the phase."""
        with self.failsafe():
            self.read_and_act()

    def read_and_act(self):
        """The body of a tick."""
        target = self.target()

        if target is None:
            self.finish(False, "target")
            return

        # The barrel is not read until it has stopped
        if self.phase == "settle" and self.clock() < self.settle_until:
            return

        now, reading = self.reading(moving=self.phase == "hold")

        if reading is not None and self.phase != "confirm":
            expected, allowed = self.expected(now)

            if abs(self.difference(self.value(reading), expected)) > allowed:
                reading = None

        if reading is None:
            self.misses += 1

            if self.misses > MAX_MISSES:
                self.finish(False, "lost")

            return

        self.misses = 0
        self.read.emit(reading)

        if self.phase == "confirm":
            confirmed = abs(self.difference(self.value(reading), self.value(self.last))) \
                <= self.axis.confirm
            self.last = reading
            self.last_time = now

            if confirmed:
                self.aim(target, now)
        elif self.phase == "hold":
            self.hold(reading, target, now)
        elif self.phase == "settle":
            self.settled(reading, target)
            self.last_time = now
            self.aim(target, now)

    def settled(self, reading, target):
        """The barrel stopped after a move: learn the release lead from a
        hold's overshoot, the rate and the frame step from a tap."""
        moved = abs(self.difference(self.value(reading), self.value(self.last)))
        self.last = reading

        if not self.tap:
            _, _, direction, _ = self.move
            overshoot = direction * self.difference(self.value(reading), target)
            self.lead = min(MAX_LEAD, max(0.0, self.lead + overshoot / self.rate))
            return

        shortest = self.tap <= self.short_tap

        if moved < self.axis.min_move:
            # Too short for a game frame: longer next time
            self.short_tap = min(MAX_TAP, 2 * max(self.tap, self.short_tap))
            return

        if shortest:
            self.step_size = moved

        if not self.rate_measured:
            self.rate = moved / self.tap

    def aim(self, target, now):
        """The barrel is still: done, hold or tap towards the target.

        Done within the axis' tolerance, or within half the move of the
        shortest tap (the game's frame step) or of the reading's resolution
        when that is larger.
        """
        error = self.difference(target, self.value(self.last))

        # A reading shown in whole degrees cannot tell more than half of one
        if abs(error) <= max(self.axis.tolerance, self.step_size / 2, self.last.resolution / 2):
            self.finish(True)
            return

        if self.moves >= MAX_MOVES:
            self.finish(False, "moves")
            return

        self.moves += 1
        key = self.raise_key if error > 0 else self.lower_key

        if abs(error) / self.rate > MAX_TAP:
            self.samples = [(now, self.value(self.last))]
            self.tap = 0.0
            self.hold_started = now
            self.hold_error = abs(error)
            self.hold_rate = 0.0
            self.still_ticks = 0
            self.phase = "hold"
            self.press(key)
            return

        seconds = min(MAX_TAP, max(self.short_tap, abs(error) / self.rate))
        self.tap = seconds
        self.phase = "move"
        self.timer.stop()
        self.press(key)
        self.release_timer.start(round(seconds * 1000))

    def hold(self, reading, target, now):
        """Holding: end the hold when the barrel is not moving or it takes
        too long, else measure the rate and release just before the
        target."""
        moved = abs(self.difference(self.value(reading), self.value(self.last)))
        self.still_ticks = self.still_ticks + 1 if moved < self.axis.min_move else 0
        self.last = reading
        self.last_time = now
        self.samples.append((now, self.value(reading)))

        # At the fastest rate this hold has measured: a stopping barrel does
        # not make the time allowed longer
        too_long = now - self.hold_started > HOLD_FACTOR * self.hold_error / (self.hold_rate or self.rate) + HOLD_SLACK

        if self.still_ticks >= STALL_TICKS or too_long:
            # Whatever rate was seen is of a barrel that was stopping
            self.rate = self.axis.default_rate
            self.rate_measured = False
            self.finish(False, "stalled" if self.still_ticks >= STALL_TICKS else "timeout")
            return

        self.measure_rate()

        _, _, direction, _ = self.move
        left = direction * self.difference(target, self.value(self.last))
        seconds = left / self.rate - self.lead

        # Released at the next tick at the latest: a timer for the exact time
        if seconds <= READ_INTERVAL_MS / 1000:
            self.timer.stop()
            self.phase = "move"
            self.release_timer.start(max(0, round(seconds * 1000)))

    def measure_rate(self):
        """The rate of the hold: the slope of a line through its last
        RATE_WINDOW readings, without the first (taken before the barrel
        started, it would make the rate 10 to 13% low). A line, not the two
        ends, because the barrel moves a step per game frame."""
        recent = self.samples[1:][-RATE_WINDOW:]

        if len(recent) < 3:
            return

        first = recent[0][1]
        points = [(t, self.difference(v, first)) for t, v in recent]
        mean_t = sum(t for t, _ in points) / len(points)
        mean_v = sum(v for _, v in points) / len(points)
        spread = sum((t - mean_t) ** 2 for t, _ in points)

        if not spread or abs(points[-1][1] - points[0][1]) <= 1:
            return

        self.rate = abs(sum((t - mean_t) * (v - mean_v) for t, v in points) / spread)
        self.hold_rate = max(self.hold_rate, self.rate)
        self.rate_measured = True

    def end_move(self):
        """Release the key, then read once the barrel has stopped."""
        with self.failsafe():
            self.release()
            self.phase = "settle"
            self.settle_until = self.clock() + SETTLE_MS / 1000
            self.timer.start()
