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
   key is released when the target is about to be reached;
3. after the barrel stops, the rest is covered by taps timed with the
   measured rate, until the sight is within TOLERANCE of the target.

Everything runs on the GUI thread (screen grabs are GUI-thread only) from
Qt timers; a reading takes a few tens of milliseconds.
"""

import time
from dataclasses import dataclass

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from compassreader import SEARCH_TOP, STRIP_HALF_WIDTH, read_compass
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

    `period`: values wrap at it (bearings at 360), None for none;
    `default_rate`: units per second while a key is held, until measured;
    `tolerance`, `confirm`, `max_jump`, `min_move`: as TOLERANCE, CONFIRM,
    MAX_JUMP and MIN_MOVE for the elevation.
    """

    value: object
    default_rate: float
    tolerance: float
    confirm: float
    max_jump: float
    min_move: float
    period: float | None = None

    def difference(self, a, b):
        """a - b, the short way round on a wrapping axis."""
        if self.period is None:
            return a - b

        half = self.period / 2

        return (a - b + half) % self.period - half


ELEVATION = Axis(
    value=lambda reading: reading.mils,
    default_rate=DEFAULT_RATE,
    tolerance=TOLERANCE,
    confirm=CONFIRM,
    max_jump=MAX_JUMP,
    min_move=MIN_MOVE,
)

# The mortar turns a fixed step for every game frame A or D is down
# (USQTurretMovementComponent of the mortar, decompiled from the game
# server: 0.25 degree times the view's sensitivity, up to 50 degrees/s), so
# its rate grows with the frame rate: 15 degrees/s at 60 fps. The lay
# measures the rate and the step and stops within half of the step.
BEARING = Axis(
    value=lambda reading: reading.degrees,
    default_rate=15.0,
    tolerance=0.1,
    confirm=0.3,
    max_jump=10.0,
    min_move=0.05,
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
        left = max(0, round(overlay.center_x - half))
        right = min(overlay.width(), round(overlay.center_x + half))
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

    def __call__(self, sight):
        if sight is None:
            return None

        return read_compass(sight.image, sight.centre_x, sight.scale, self.digits)


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
    turns a grab into a reading (default: the elevation scale with
    `templates`).
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
        self.reader = reader or (lambda sight: read_sight(sight, self.templates))

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
        self.stopped = False
        self.samples = []
        self.moves = 0
        self.tap = 0.0
        self.misses = 0

        # The last move: (time pressed, mils then, direction, time released)
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
        return self.phase is not None

    def reading(self):
        """A reading now, as (time, sightreader.Reading or None)."""
        now = self.clock()

        return now, self.reader(self.grab())

    def value(self, reading):
        return self.axis.value(reading)

    def difference(self, a, b):
        return self.axis.difference(a, b)

    def start(self):
        """Begin a lay; False if the sight is not seen or there is no
        target (the caller can fall back to the timed lay)."""
        if self.active or self.target() is None:
            return False

        _, first = self.reading()

        if first is None:
            return False

        self.last = first
        self.stopped = False
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
        self.finish(False)

    def finish(self, on_target):
        self.timer.stop()
        self.release_timer.stop()
        self.release()
        self.phase = None
        self.finished.emit(self.last, on_target)

    def press(self, key, now):
        self.key = key
        self.move = (now, self.value(self.last), 1 if key is self.raise_key else -1, None)
        key.press()

    def release(self):
        if self.key is None:
            return

        self.key.release()
        self.key = None

        if self.move is not None:
            pressed, mils, direction, _ = self.move
            self.move = (pressed, mils, direction, self.clock())

    def expected(self, now):
        """Where the sight should be, and how far off a reading may be:
        the last reading, moved on at the rate for the time a key was held
        (the rate may be off by half while it is not measured)."""
        max_jump = self.axis.max_jump

        if self.move is None:
            return self.value(self.last), max_jump

        pressed, value, direction, released = self.move
        held = (released or now) - pressed

        return value + direction * self.rate * held, max_jump + 0.5 * self.rate * held

    def step(self):
        """Timer tick: read the sight and act on the phase."""
        target = self.target()

        if target is None:
            self.finish(False)
            return

        now, reading = self.reading()

        if reading is not None and self.phase != "confirm":
            expected, allowed = self.expected(now)

            if abs(self.difference(self.value(reading), expected)) > allowed:
                reading = None

        if reading is None:
            self.misses += 1

            if self.misses > MAX_MISSES:
                self.finish(False)

            return

        self.misses = 0
        self.read.emit(reading)

        if self.phase == "confirm":
            confirmed = abs(self.difference(self.value(reading), self.value(self.last))) \
                <= self.axis.confirm
            self.last = reading

            if confirmed:
                self.aim(target, now)
        elif self.phase == "hold":
            self.last = reading
            self.samples.append((now, self.value(reading)))
            self.hold(target, now)
        elif self.phase == "settle":
            self.settled(reading, target)
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
        resolution = getattr(self.last, "resolution", 0.0)

        if abs(error) <= max(self.axis.tolerance, self.step_size / 2, resolution / 2):
            self.finish(True)
            return

        if self.moves >= MAX_MOVES:
            self.finish(False)
            return

        self.moves += 1
        key = self.raise_key if error > 0 else self.lower_key

        if abs(error) / self.rate > MAX_TAP:
            self.samples = [(now, self.value(self.last))]
            self.tap = 0.0
            self.phase = "hold"
            self.press(key, now)
            return

        seconds = min(MAX_TAP, max(self.short_tap, abs(error) / self.rate))
        self.tap = seconds
        self.phase = "move"
        self.timer.stop()
        self.press(key, now)
        self.release_timer.start(round(seconds * 1000))

    def hold(self, target, now):
        """Holding: measure the rate, release just before the target."""
        if len(self.samples) >= 3:
            (t0, m0), (t1, m1) = self.samples[0], self.samples[-1]
            moved = abs(self.difference(m1, m0))

            if t1 > t0 and moved > 1:
                self.rate = moved / (t1 - t0)
                self.rate_measured = True

        _, _, direction, _ = self.move
        left = direction * self.difference(target, self.value(self.last))
        seconds = left / self.rate - self.lead

        # Released at the next tick at the latest: a timer for the exact time
        if seconds <= READ_INTERVAL_MS / 1000:
            self.timer.stop()
            self.phase = "move"
            self.release_timer.start(max(0, round(seconds * 1000)))

    def end_move(self):
        """Release the key, then read once the barrel has stopped."""
        self.release()
        self.phase = "settle"
        QTimer.singleShot(SETTLE_MS, Qt.TimerType.PreciseTimer, self.resume)

    def resume(self):
        if self.phase == "settle":
            self.timer.start()
