"""The lay of the mortar's elevation and bearing (sightlay).

The layer is driven on a virtual clock: `World` is the clock the layer is
given, `Barrel` and `Turret` move with it, and `drive` runs the layer's
timers (it never runs Qt's event loop), so the tests take no real time to
wait and do not depend on how busy the machine is. Two smoke tests at the
end run the layer on real timers.
"""

import time

import pytest

from PyQt6.QtCore import QEventLoop, QTimer

import sightlay
from compassreader import CompassReading, DigitReader
from compassimage import draw_compass
from sightimage import draw_sight
from sightlay import Sight, SightLayer
from sightreader import GrayImage, LabelTemplates, Reading

WIDTH, HEIGHT = 1280, 720
FRAME = 1 / 60

# Reading and grabbing the screen take this long (s) in the game
READ_TIME = 0.02


class World:
    """The virtual clock (seconds) a layer, a barrel and a driver share."""

    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now


class Barrel:
    """The game's barrel on the world's clock: at every game frame (60 fps)
    it moves `rate` per second if a key is down, between `low` and `high`
    (or round a circle of `wrap`); the game sees a key `latency` seconds
    after it was pressed or released."""

    def __init__(self, world, value, rate, low=800.0, high=1580.0, wrap=None, latency=0.0):
        self.world = world
        self.value = value
        self.rate = rate
        self.low, self.high, self.wrap = low, high, wrap
        self.latency = latency
        self.direction = 0
        self.frame = world.now
        self.events = []
        self.presses = []
        self.releases = []
        self.keys_down = 0

    def frame_moved(self):
        """Hook: the barrel moved a frame (the turret's strip follows)."""

    def update(self):
        """Move the barrel up to the world's time."""
        while self.frame + FRAME <= self.world.now:
            self.frame += FRAME

            while self.events and self.events[0][0] <= self.frame:
                self.direction = self.events.pop(0)[1]

            self.value += self.direction * self.rate * FRAME
            self.value = self.value % self.wrap if self.wrap else min(self.high, max(self.low, self.value))
            self.frame_moved()

    def key(self, direction):
        barrel = self

        class Key:
            def press(self):
                barrel.update()
                barrel.keys_down += 1
                barrel.events.append((barrel.world.now + barrel.latency, direction))
                barrel.presses.append((barrel.world.now, direction))

            def release(self):
                barrel.update()
                barrel.keys_down -= 1
                barrel.events.append((barrel.world.now + barrel.latency, 0))
                barrel.releases.append(barrel.world.now)

        return Key()


class Turret(Barrel):
    """The mortar's traverse: D turns right (bearing up), A left, `rate`
    degrees/s at every frame, round 360. The compass's strip follows the
    bearing with a lag (its yaw is smoothed): `strip` trails by `rate` *
    `lag` degrees in a steady turn."""

    def __init__(self, world, value, rate, lag=0.0, **kwargs):
        super().__init__(world, value, rate, wrap=360.0, **kwargs)
        self.strip = value
        self.smoothing = lag

    def frame_moved(self):
        if not self.smoothing:
            self.strip = self.value
            return

        share = FRAME / (self.smoothing + FRAME)
        self.strip = (self.strip + share * bearing_error(self.value, self.strip)) % 360.0

    @property
    def lag(self):
        return bearing_error(self.value, self.strip)


def bearing_error(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def drive(world, layer, limit=60.0):
    """Run the layer's timers on the world's clock until the lay ends or
    `limit` seconds pass: the tick timer every READ_INTERVAL_MS while it is
    active, the release timer once its interval has gone by."""
    end = world.now + limit
    tick_at = release_at = None

    while layer.active and world.now < end:
        if layer.release_timer.isActive():
            release_at = release_at if release_at is not None else world.now + layer.release_timer.interval() / 1000
        else:
            release_at = None

        if layer.timer.isActive():
            tick_at = tick_at if tick_at is not None else world.now + layer.timer.interval() / 1000
        else:
            tick_at = None

        due = [t for t in (release_at, tick_at) if t is not None]
        assert due, "the lay is active but no timer is running"
        world.now = max(world.now, min(due))

        if release_at is not None and release_at <= world.now and (tick_at is None or release_at <= tick_at):
            layer.release_timer.stop()
            release_at = None
            layer.end_move()
        else:
            tick_at = max(tick_at + layer.timer.interval() / 1000, world.now)
            layer.step()

    assert not layer.active, "the lay did not end"


@pytest.fixture(scope="module")
def templates():
    return LabelTemplates()


@pytest.fixture
def world():
    return World()


class Run:
    """A layer on a virtual world and everything it said."""

    def __init__(self, world, layer):
        self.world = world
        self.layer = layer
        self.readings = []
        self.ends = []
        layer.read.connect(self.readings.append)
        layer.finished.connect(lambda reading, ok: self.ends.append((reading, ok)))

    def lay(self, limit=60.0):
        assert self.layer.start()
        drive(self.world, self.layer, limit)
        assert len(self.ends) == 1

        return self.ends[0]


def sight_layer(world, barrel, templates, target, reader=None, grab=None, **kwargs):
    """A layer on the elevation scale, drawn at the barrel's mils
    (rendered and read by default), or read by `reader`."""
    def render():
        world.now += READ_TIME
        barrel.update()
        image = draw_sight(barrel.value, WIDTH, HEIGHT)

        return Sight(GrayImage.from_qimage(image), WIDTH // 2, HEIGHT // 2, HEIGHT / 1080)

    return SightLayer(grab or render, templates, target, barrel.key(1), barrel.key(-1),
                      clock=world.clock, reader=reader, **kwargs)


def fake_sight_layer(world, barrel, target, readings=None, read_time=READ_TIME, **kwargs):
    """A layer that reads the barrel's mils itself (no pictures): `readings`
    maps the layer's n-th read to what is read (None: not seen); a read
    takes `read_time` seconds."""
    reads = []

    def grab():
        world.now += read_time
        barrel.update()

        return object()

    def reader(sight, moving):
        reads.append(moving)
        reading = Reading(barrel.value, 1, 1.0, 1.0)

        if readings and len(reads) in readings:
            return readings[len(reads)](reading)

        return reading

    layer = SightLayer(grab, None, target, barrel.key(1), barrel.key(-1),
                       clock=world.clock, reader=reader, **kwargs)
    layer.reads = reads

    return layer


@pytest.mark.parametrize("start, target, rate", [
    (900.0, 1043.4, 200.0),     # up a long way: hold W
    (1450.0, 1203.7, 250.0),    # down: hold S
    (1100.0, 1103.2, 46.0),     # close: taps only, at the rate seen in the game
])
def test_lays_to_the_target(world, templates, start, target, rate):
    barrel = Barrel(world, start, rate)
    layer = sight_layer(world, barrel, templates, lambda: target)

    reading, on_target = Run(world, layer).lay()
    barrel.update()

    assert on_target
    assert reading.mils == pytest.approx(target, abs=sightlay.TOLERANCE)
    assert barrel.value == pytest.approx(target, abs=sightlay.TOLERANCE + 0.1)
    assert barrel.keys_down == 0
    assert layer.failure is None
    # The rate was measured on the way (holds only)
    if abs(target - start) / rate > 3 * sightlay.MAX_TAP:
        assert layer.rate == pytest.approx(rate, rel=0.15)


@pytest.mark.parametrize("rate, read_time", [(220.0, 0.04), (300.0, 0.06), (440.0, 0.06)])
def test_lays_with_a_barrel_faster_than_the_default_rate(world, rate, read_time):
    """The game moves the barrel up to 444 mil/s (25 degrees/s); at 80 fps
    and a sensitivity of 2 it is 12 degrees/s, 220 mil/s. Readings of such a
    barrel are no misreads, even before its rate is known: a gate on 46
    mil/s threw them all away and the lay ended with the rate still
    unmeasured. (A reading takes 20 to 60 ms on a busy machine.)"""
    barrel = Barrel(world, 900.0, rate)
    layer = fake_sight_layer(world, barrel, lambda: 1400.0, read_time=read_time)

    reading, on_target = Run(world, layer).lay()

    # Within half the game's frame step, as measured
    assert on_target
    assert reading.mils == pytest.approx(1400.0, abs=rate * FRAME / 2 + 0.6)
    assert layer.rate == pytest.approx(rate, rel=0.05)


def test_the_rate_is_measured_over_the_last_readings_not_from_before_the_barrel_moved(world):
    """The game sees the key 50 ms after the press: a rate taken from the
    press (the sample before the barrel moved) is 10% low in a hold of half
    a second."""
    barrel = Barrel(world, 900.0, 200.0, latency=0.05)
    layer = fake_sight_layer(world, barrel, lambda: 1010.0)

    _, on_target = Run(world, layer).lay()

    assert on_target
    assert layer.rate_measured
    assert layer.rate == pytest.approx(200.0, rel=0.04)


def test_the_rate_leaves_out_the_reading_from_before_the_barrel_moved(world):
    """The first reading of a hold is the press's: the barrel moved on the
    key's way to the game. The line through the rest has the rate (200
    mil/s here); with the first it is 7% low."""
    barrel = Barrel(world, 1000.0, 200.0)
    layer = fake_sight_layer(world, barrel, lambda: 1500.0)
    layer.samples = [(0.00, 1000.0), (0.05, 1000.0), (0.10, 1010.0), (0.15, 1020.0), (0.20, 1030.0)]

    layer.measure_rate()

    assert layer.rate == pytest.approx(200.0)
    assert layer.rate_measured


@pytest.mark.parametrize("start, target, low, high", [
    (1500.0, 1700.0, 800.0, 1580.0),    # up past the barrel's end
    (900.0, 700.0, 800.0, 1580.0),      # down past the other end
    (1570.0, 1590.0, 800.0, 1580.0),    # a few mils past it
])
def test_a_target_past_the_barrels_end_ends_the_hold(world, start, target, low, high):
    """A held key moves nothing at the end: the lay used to hold it for
    ever, every reading looking like the last."""
    barrel = Barrel(world, start, 200.0, low=low, high=high)
    layer = fake_sight_layer(world, barrel, lambda: target)

    reading, on_target = Run(world, layer).lay(limit=30.0)

    assert not on_target
    assert layer.failure == "stalled"
    assert barrel.keys_down == 0
    assert barrel.value == pytest.approx(high if target > start else low)
    assert world.now < 5.0
    # What was seen of the stopping barrel is not the rate of the next lay
    assert layer.rate == sightlay.ELEVATION.default_rate
    assert not layer.rate_measured


def test_a_hold_that_never_arrives_is_cut(world):
    """A reading that keeps moving (jitter at the end of the barrel) is no
    stall: the hold is cut at twice what the error takes at the rate, plus a
    second."""
    barrel = Barrel(world, 1500.0, 200.0)
    flicker = {n: (lambda reading, n=n: Reading(reading.mils + (0.5 if n % 2 else -0.5), 1, 1.0, 1.0))
               for n in range(1, 400)}
    layer = fake_sight_layer(world, barrel, lambda: 1700.0, readings=flicker)

    _, on_target = Run(world, layer).lay(limit=30.0)

    assert not on_target
    assert layer.failure == "timeout"
    assert barrel.keys_down == 0
    assert 2.5 < world.now < 4.5


class FailingGrab:
    """A grab that raises on its n-th call."""

    def __init__(self, world, barrel, fails_at, error=RuntimeError("screen gone")):
        self.world, self.barrel, self.fails_at, self.error = world, barrel, fails_at, error
        self.calls = 0

    def __call__(self):
        self.calls += 1
        self.world.now += READ_TIME
        self.barrel.update()

        if self.calls == self.fails_at:
            raise self.error

        return object()


@pytest.mark.parametrize("fails_at", [4, 9])
def test_an_error_while_holding_releases_the_key(world, fails_at):
    """The grab raises in a timer callback: the key is let go and the lay
    ended before the error goes on (it did stay down with the layer
    active)."""
    barrel = Barrel(world, 900.0, 200.0)
    layer = fake_sight_layer(world, barrel, lambda: 1500.0)
    layer.grab = FailingGrab(world, barrel, fails_at)
    run = Run(world, layer)

    assert layer.start()

    with pytest.raises(RuntimeError, match="screen gone"):
        drive(world, layer)

    assert barrel.keys_down == 0
    assert not layer.active
    assert layer.failure == "error"
    assert run.ends == [(layer.last, False)]
    assert not layer.timer.isActive()
    assert not layer.release_timer.isActive()


def test_an_error_in_the_reader_releases_the_key(world):
    barrel = Barrel(world, 900.0, 200.0)

    def reader(sight, moving):
        if world.now > 0.4:
            raise ValueError("misread")

        return Reading(barrel.value, 1, 1.0, 1.0)

    layer = fake_sight_layer(world, barrel, lambda: 1500.0)
    layer.reader = reader

    assert layer.start()

    with pytest.raises(ValueError):
        drive(world, layer)

    assert barrel.keys_down == 0
    assert not layer.active


def test_an_error_when_the_key_is_released_ends_the_lay(world):
    """The key injector fails on the release that ends a tap."""
    barrel = Barrel(world, 1100.0, 46.0)
    layer = fake_sight_layer(world, barrel, lambda: 1103.2)
    key = layer.raise_key

    class Broken:
        def press(self):
            key.press()

        def release(self):
            key.release()
            raise OSError("uinput closed")

    layer.raise_key = Broken()
    run = Run(world, layer)

    assert layer.start()

    with pytest.raises(OSError):
        drive(world, layer)

    assert not layer.active
    assert layer.failure == "error"
    assert len(run.ends) == 1


def test_already_on_target_presses_nothing(world, templates):
    barrel = Barrel(world, 1222.2, 100.0)
    layer = sight_layer(world, barrel, templates, lambda: 1222.4)

    _, on_target = Run(world, layer).lay()

    assert on_target
    assert barrel.presses == []


def test_no_sight_no_lay(world, templates):
    barrel = Barrel(world, 1000.0, 100.0)
    nothing = Sight(GrayImage.from_qimage(draw_sight(1000, WIDTH, HEIGHT).copy(0, 0, 10, 10)),
                    WIDTH // 2, HEIGHT // 2, HEIGHT / 1080)

    assert not sight_layer(world, barrel, templates, lambda: 1100.0, grab=lambda: nothing).start()
    assert not sight_layer(world, barrel, templates, lambda: None).start()
    assert barrel.presses == []


def test_lost_sight_releases_the_key(world):
    """The scale is hidden for more than MAX_MISSES readings in a hold."""
    barrel = Barrel(world, 900.0, 60.0)
    hidden = {n: (lambda reading: None) for n in range(4, 40)}
    layer = fake_sight_layer(world, barrel, lambda: 1400.0, readings=hidden)

    _, on_target = Run(world, layer).lay()

    assert not on_target
    assert layer.failure == "lost"
    assert barrel.keys_down == 0
    assert not layer.active


@pytest.mark.parametrize("hidden_reads, lost", [(5, False), (6, True)])
def test_the_sight_may_be_missed_five_readings_in_a_row(world, hidden_reads, lost):
    """Smoke over the scale for 5 readings is carried through, 6 end the
    lay (a literal: MAX_MISSES is 5)."""
    barrel = Barrel(world, 900.0, 100.0)
    hidden = {n: (lambda reading: None) for n in range(5, 5 + hidden_reads)}
    layer = fake_sight_layer(world, barrel, lambda: 1000.0, readings=hidden)

    _, on_target = Run(world, layer).lay()

    assert (layer.failure == "lost") == lost
    assert on_target == (not lost)


def test_a_misread_is_skipped_not_followed(world):
    """One reading 300 mils off, in the middle of a hold, is no move of the
    barrel: it is not acted on or shown, and the hold goes on."""
    barrel = Barrel(world, 900.0, 200.0)
    jump = {8: lambda reading: Reading(reading.mils + 300.0, 1, 1.0, 1.0)}
    layer = fake_sight_layer(world, barrel, lambda: 1200.0, readings=jump)
    run = Run(world, layer)

    reading, on_target = run.lay()

    assert on_target
    assert reading.mils == pytest.approx(1200.0, abs=1.0)
    assert max(shown.mils for shown in run.readings) < 1210.0


def test_the_readers_are_told_whether_the_barrel_moves(world):
    """The strip of a compass lags in a turn: the reader looks at it only
    while the barrel is still."""
    barrel = Barrel(world, 900.0, 200.0)
    layer = fake_sight_layer(world, barrel, lambda: 1200.0)
    phases = []
    reader = layer.reader

    def watching(sight, moving):
        phases.append((layer.phase, moving))

        return reader(sight, moving)

    layer.reader = watching

    Run(world, layer).lay()

    assert {phase: moving for phase, moving in phases if phase != "move"} == {
        None: False, "confirm": False, "hold": True, "settle": False,
    }
    assert ("hold", True) in phases


def test_a_barrel_that_does_not_move_ends_the_lay_after_the_moves(world):
    """Nothing moves: taps that do nothing are tried 12 times (MAX_MOVES) and
    the lay ends."""
    barrel = Barrel(world, 1100.0, 0.0)
    layer = fake_sight_layer(world, barrel, lambda: 1103.0)

    _, on_target = Run(world, layer).lay()

    assert not on_target
    assert layer.failure == "moves"
    assert len(barrel.presses) == 12


class TapBarrel(Barrel):
    """A barrel that needs a key down for `shortest` seconds to move at
    all (a game frame, or the key reaching it)."""

    def __init__(self, world, value, rate, shortest):
        super().__init__(world, value, rate)
        self.shortest = shortest

    def key(self, direction):
        barrel = self
        pressed = []

        class Key:
            def press(self):
                pressed.append(barrel.world.now)
                barrel.keys_down += 1
                barrel.presses.append((barrel.world.now, direction))

            def release(self):
                held = barrel.world.now - pressed.pop()
                barrel.keys_down -= 1
                barrel.releases.append(barrel.world.now)

                if held >= barrel.shortest:
                    barrel.value += direction * barrel.rate * held

        return Key()


def test_a_tap_that_moved_nothing_is_retried_twice_as_long(world):
    barrel = TapBarrel(world, 1100.0, 46.0, shortest=0.07)
    layer = fake_sight_layer(world, barrel, lambda: 1102.5)

    _, on_target = Run(world, layer).lay()

    held = [release - press for (press, _), release in zip(barrel.presses, barrel.releases)]

    assert on_target
    # The first tap (1.1 mils at 46 mil/s, 0.054 s) was too short for the barrel
    assert held[0] == pytest.approx(0.054, abs=0.002)
    assert held[1] >= 2 * held[0] - 0.002
    assert layer.short_tap >= 2 * held[0] - 0.002


def test_a_lay_cannot_start_over_a_lay(world):
    barrel = Barrel(world, 900.0, 200.0)
    layer = fake_sight_layer(world, barrel, lambda: 1500.0)

    assert layer.start()
    drive_ticks(world, layer, 6)

    state = (layer.phase, layer.moves, list(barrel.presses))

    assert layer.active
    assert not layer.start()
    assert (layer.phase, layer.moves, barrel.presses) == state


def drive_ticks(world, layer, ticks):
    """Up to `ticks` readings of the layer's timer (it stops for a tap)."""
    for _ in range(ticks):
        if not layer.timer.isActive():
            break

        world.now += layer.timer.interval() / 1000
        layer.step()


def test_stopping_cancels_a_tap_in_progress(world):
    """A tap has its release timer running: stopping the lay must not leave
    it to release (and settle) a lay that is over."""
    barrel = Barrel(world, 1100.0, 46.0)
    layer = fake_sight_layer(world, barrel, lambda: 1105.0)
    run = Run(world, layer)

    assert layer.start()
    drive_ticks(world, layer, 3)

    assert layer.phase == "move"
    assert layer.release_timer.isActive()

    layer.stop()

    assert not layer.release_timer.isActive()
    assert not layer.timer.isActive()
    assert barrel.keys_down == 0
    assert layer.stopped
    assert layer.failure == "stopped"
    assert run.ends == [(layer.last, False)]


def test_a_new_lay_is_not_cut_short_by_the_last_ones_settle_time(world):
    """The player stops a lay and starts another within 150 ms: the second
    lay waits its own settle time, a leftover timer of the first does not
    end it."""
    barrel = Barrel(world, 1100.0, 46.0)
    layer = fake_sight_layer(world, barrel, lambda: 1108.0)

    assert layer.start()
    drive_ticks(world, layer, 3)
    layer.release_timer.stop()
    layer.end_move()
    assert layer.phase == "settle"

    layer.stop()
    assert layer.start()
    drive_ticks(world, layer, 3)
    assert layer.phase == "move"
    layer.release_timer.stop()
    layer.end_move()

    reads_before = len(layer.reads)

    # Real time passes (the first lay's settle time, SETTLE_MS) while the
    # virtual clock stands still: nothing may be read
    loop = QEventLoop()
    QTimer.singleShot(sightlay.SETTLE_MS + 100, loop.quit)
    loop.exec()

    assert len(layer.reads) == reads_before
    assert layer.phase == "settle"

    layer.stop()


class FakeOverlay:
    """What ScreenSight asks of the overlay."""

    def __init__(self, width, height, center_x):
        self.size = (width, height)
        self.center_x = center_x
        self.center_y = height // 2

    def width(self):
        return self.size[0]

    def height(self):
        return self.size[1]


@pytest.mark.parametrize("offset", [0, 120, -80])
def test_the_compass_grab_is_centred_on_the_screen_not_the_crosshair(offset):
    """The crosshair may be moved off the centre (center_offset_x); the
    compass is at the screen's centre."""
    overlay = FakeOverlay(1920, 1080, 960 + offset)
    left, top, right, bottom = sightlay.ScreenSight(overlay).compass_region()

    assert (left + right) / 2 == pytest.approx(960, abs=1)
    assert bottom == 1080
    assert top < 1080 - 60


class ImageScreen:
    """A screen that shows `image`: `grabWindow` as QScreen grabs it."""

    def __init__(self, image):
        self.image = image

    def grabWindow(self, _window, x, y, width, height):
        from PyQt6.QtGui import QPixmap

        return QPixmap.fromImage(self.image.copy(x, y, width, height))


class AlignedOverlay:
    """An overlay whose crosshair the player aligned `dx`, `dy` pixels off
    the screen centre ("Align with the sight"), on `screen`."""

    def __init__(self, screen, dx, dy):
        self.shown = screen
        self.center_x = screen.image.width() / 2 + dx
        self.center_y = screen.image.height() / 2 + dy

    def width(self):
        return self.shown.image.width()

    def height(self):
        return self.shown.image.height()

    def screen(self):
        return self.shown


@pytest.mark.parametrize("dx, dy", [(0, 0), (0, 40), (0, 60), (0, 100), (0, -100), (100, 0)])
def test_the_mortar_scale_is_grabbed_at_the_screen_centre_not_the_crosshair(qapp, dx, dy):
    """The game draws the sight at the screen centre; an aligned crosshair
    must not move the grab, or the scale reads 5-12 mil wrong at 40-100 px."""
    screen = ImageScreen(draw_sight(1043.4, 1920, 1080))
    sight = sightlay.ScreenSight(AlignedOverlay(screen, dx, dy))

    left, top, _right, _bottom = sight.region()
    grab = sight.grab()

    assert sight.region() == sightlay.ScreenSight(AlignedOverlay(screen, 0, 0)).region()
    assert (grab.centre_x, grab.centre_y) == (960 - left, 540 - top)

    reading = sightlay.read_sight(grab, LabelTemplates())

    assert reading is not None
    assert reading.mils == pytest.approx(1043.4, abs=sightlay.TOLERANCE)


def bearing_layer(world, turret, templates, target):
    """A layer on the compass: the strip drawn behind the bearing by the
    turret's lag, rendered at 1080p and read as the app reads it."""
    def grab():
        world.now += READ_TIME
        turret.update()
        image = draw_compass(turret.value, 1920, 1080, lag=turret.lag)

        return Sight(GrayImage.from_qimage(image.copy(0, 1080 - 80, 1920, 80)), 960.0, 0, 1.0)

    return SightLayer(grab, templates, target, turret.key(1), turret.key(-1),
                      clock=world.clock, axis=sightlay.BEARING,
                      reader=sightlay.CompassReader(DigitReader(templates)))


@pytest.mark.parametrize("start, target, rate, lag", [
    (100.0, 37.4, 50.0, 0.0),       # left a long way: hold A
    (350.0, 10.3, 50.0, 0.0),       # right over north: the short way round
    (12.6, 13.4, 50.0, 0.0),        # close: taps
    (100.0, 37.4, 15.0, 0.1),       # a strip 1.5 degrees behind at 15 degrees/s
    (100.0, 37.4, 36.0, 0.1),       # 3.6 degrees behind: past what a still strip may be off
    (200.0, 290.0, 36.0, 0.1),      # right a long way, lagging
])
def test_lays_the_bearing(world, templates, start, target, rate, lag):
    turret = Turret(world, start, rate, lag=lag)
    layer = bearing_layer(world, turret, templates, lambda: target)

    reading, on_target = Run(world, layer).lay()
    turret.update()

    # Within half the game's frame step (rate / 60), as measured
    allowed = max(sightlay.BEARING.tolerance, layer.step_size / 2) + 0.05
    assert on_target, layer.failure
    assert abs(bearing_error(reading.degrees, target)) <= allowed
    assert abs(bearing_error(turret.value, target)) <= allowed + 0.05
    assert turret.direction == 0
    # Never the long way round
    assert turret.presses[0][1] == (1 if bearing_error(target, start) > 0 else -1)


def test_a_lagging_strip_does_not_end_a_turning_lay(world, templates):
    """At 36 degrees/s with 0.1 s of lag the strip is 3.6 degrees behind
    the number: the lay used to be dropped after 0.3 s, the strip
    contradicting every reading, and left the mortar at 91 degrees for a
    target at 37.4."""
    turret = Turret(world, 100.0, 36.0, lag=0.1)
    layer = bearing_layer(world, turret, templates, lambda: 37.4)

    _, on_target = Run(world, layer).lay()

    assert on_target
    assert layer.failure is None


def test_the_compass_reader_looks_at_the_strip_when_the_barrel_is_still(templates):
    reader = sightlay.CompassReader(DigitReader(templates))
    lagging = draw_compass(215.3, 1920, 1080, lag=2.0)
    strip = Sight(GrayImage.from_qimage(lagging.copy(0, 1000, 1920, 80)), 960.0, 0, 1.0)

    assert reader(strip) .text == "215.3"           # not known: a lagging strip allowed
    assert reader(strip, moving=True).text == "215.3"
    assert reader(strip, moving=False) is None      # still: the strip must agree
    assert reader(None) is None


def bearing_reading(degrees, resolution):
    return CompassReading(degrees, resolution, "", 0, 0)


@pytest.mark.parametrize("target, presses", [
    (182.9, False),     # 0.4 from the middle of 182: inside half a degree
    (183.2, True),      # 0.7 from it
    (182.1, False),
    (181.7, True),
])
def test_a_whole_degree_reading_is_done_within_half_a_degree(world, target, presses):
    """A compass shown in whole degrees cannot tell more: the lay is done
    within half of its resolution, however fine the target."""
    turret = Turret(world, 182.5, 36.0)
    layer = SightLayer(lambda: object(), None, lambda: target, turret.key(1), turret.key(-1),
                       clock=world.clock, axis=sightlay.BEARING,
                       reader=lambda sight, moving: bearing_reading(turret.value, 1.0))

    assert layer.start()
    drive_ticks(world, layer, 2)

    assert bool(turret.presses) == presses


def test_the_axes_know_how_fast_the_game_can_turn_them():
    """Mils per second (25 degrees/s of 6400/360 mils) and degrees/s, from
    the game's MaxPitch and MaxYaw of the mortar."""
    assert sightlay.ELEVATION.max_rate == pytest.approx(444.4, abs=0.5)
    assert sightlay.BEARING.max_rate == 50.0


def test_axis_difference_wraps_only_bearings():
    assert sightlay.BEARING.difference(10.0, 350.0) == pytest.approx(20.0)
    assert sightlay.BEARING.difference(350.0, 10.0) == pytest.approx(-20.0)
    assert sightlay.ELEVATION.difference(1010.0, 990.0) == 20.0
    assert sightlay.ELEVATION.difference(10.0, 350.0) == -340.0


class WallBarrel:
    """The barrel on the wall clock: for the smoke tests with real timers."""

    def __init__(self, value, rate):
        self.value = value
        self.rate = rate
        self.direction = 0
        self.frame = time.perf_counter()

    def update(self):
        now = time.perf_counter()

        while self.frame + FRAME <= now:
            self.frame += FRAME
            self.value = min(1580.0, max(800.0, self.value + self.direction * self.rate * FRAME))

    def key(self, direction):
        barrel = self

        class Key:
            def press(self):
                barrel.update()
                barrel.direction = direction

            def release(self):
                barrel.update()
                barrel.direction = 0

        return Key()


def real_time_layer(barrel, templates, target):
    def grab():
        barrel.update()

        return Sight(GrayImage.from_qimage(draw_sight(barrel.value, WIDTH, HEIGHT)),
                     WIDTH // 2, HEIGHT // 2, HEIGHT / 1080)

    return SightLayer(grab, templates, target, barrel.key(1), barrel.key(-1))


def test_smoke_a_lay_on_real_timers_ends_with_the_key_up(templates):
    """The layer on Qt's timers and the wall clock. How close it gets
    depends on how busy the machine is, so the bounds are wide: it ends,
    on a target it says it reached, and lets the key go."""
    barrel = WallBarrel(1100.0, 46.0)
    layer = real_time_layer(barrel, templates, lambda: 1112.0)
    ended = []
    loop = QEventLoop()
    layer.finished.connect(lambda reading, ok: (ended.append(ok), loop.quit()))
    QTimer.singleShot(90_000, loop.quit)

    assert layer.start()
    loop.exec()
    layer.stop()
    barrel.update()

    assert ended
    assert barrel.direction == 0
    assert not layer.active

    if ended[0]:
        assert barrel.value == pytest.approx(1112.0, abs=3.0)


def test_smoke_stopping_a_real_lay_releases_the_key(templates):
    barrel = WallBarrel(900.0, 30.0)
    layer = real_time_layer(barrel, templates, lambda: 1500.0)
    ended = []
    layer.finished.connect(lambda reading, ok: ended.append(ok))

    assert layer.start()
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()

    assert barrel.direction == 1
    layer.stop()
    assert barrel.direction == 0
    assert ended == [False]
    assert not layer.active
    assert layer.stopped
