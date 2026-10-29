import time

import pytest

pytest.importorskip("PyQt6.QtGui")

from PyQt6.QtCore import QEventLoop, QTimer

import sightlay
from sightlay import Sight, SightLayer
from sightreader import GrayImage, LabelTemplates
from sightimage import draw_sight

WIDTH, HEIGHT = 1280, 720
FRAME = 1 / 60


class Barrel:
    """The game's barrel: moves at `rate` mil/s while W (up) or S (down) is
    down at a frame (60 fps), so a tap shorter than a frame may do nothing."""

    def __init__(self, mils, rate):
        self.mils = mils
        self.rate = rate
        self.direction = 0
        self.frame = time.perf_counter()
        self.presses = []

    def update(self):
        now = time.perf_counter()

        while self.frame + FRAME <= now:
            self.frame += FRAME
            self.mils += self.direction * self.rate * FRAME
            self.mils = min(1580.0, max(800.0, self.mils))

    def key(self, direction):
        barrel = self

        class Key:
            def press(self):
                barrel.update()
                barrel.direction = direction
                barrel.presses.append(direction)

            def release(self):
                barrel.update()
                barrel.direction = 0

        return Key()


@pytest.fixture(scope="module")
def templates():
    return LabelTemplates()


def make_layer(barrel, templates, target, visible=lambda: True):
    def grab():
        barrel.update()

        if not visible():
            return Sight(GrayImage.from_qimage(draw_sight(1000, WIDTH, HEIGHT).copy(0, 0, 10, 10)),
                         WIDTH // 2, HEIGHT // 2, HEIGHT / 1080)

        image = draw_sight(barrel.mils, WIDTH, HEIGHT)

        return Sight(GrayImage.from_qimage(image), WIDTH // 2, HEIGHT // 2, HEIGHT / 1080)

    return SightLayer(grab, templates, target, barrel.key(1), barrel.key(-1))


def run(layer, timeout=15.0):
    """Start the lay and wait for its end; returns (reading, on_target)."""
    result = []
    loop = QEventLoop()
    layer.finished.connect(lambda reading, ok: (result.append((reading, ok)), loop.quit()))
    QTimer.singleShot(round(timeout * 1000), loop.quit)

    assert layer.start()
    loop.exec()

    assert result, "the lay did not end"
    return result[0]


@pytest.mark.parametrize("start, target, rate", [
    (900.0, 1043.4, 200.0),     # up a long way: hold W
    (1450.0, 1203.7, 250.0),    # down: hold S
    (1100.0, 1103.2, 46.0),     # close: taps only, at the rate seen in the game
])
def test_lays_to_the_target(templates, start, target, rate):
    barrel = Barrel(start, rate)
    layer = make_layer(barrel, templates, lambda: target)

    reading, on_target = run(layer)
    barrel.update()

    assert on_target
    assert reading.mils == pytest.approx(target, abs=sightlay.TOLERANCE)
    assert barrel.mils == pytest.approx(target, abs=sightlay.TOLERANCE + 0.1)
    assert barrel.direction == 0
    # The rate was measured on the way (holds only)
    if abs(target - start) / rate > 3 * sightlay.MAX_TAP:
        assert layer.rate == pytest.approx(rate, rel=0.15)


def test_already_on_target_presses_nothing(templates):
    barrel = Barrel(1222.2, 100.0)
    layer = make_layer(barrel, templates, lambda: 1222.4)

    _, on_target = run(layer)

    assert on_target
    assert barrel.presses == []


def test_no_sight_no_lay(templates):
    barrel = Barrel(1000.0, 100.0)

    assert not make_layer(barrel, templates, lambda: 1100.0, visible=lambda: False).start()
    assert not make_layer(barrel, templates, lambda: None).start()
    assert barrel.presses == []


def test_lost_sight_releases_the_key(templates, monkeypatch):
    barrel = Barrel(900.0, 60.0)
    seen = {"left": 3}

    def visible():
        seen["left"] -= 1
        return seen["left"] >= 0

    layer = make_layer(barrel, templates, lambda: 1400.0, visible)

    reading, on_target = run(layer)

    assert not on_target
    assert barrel.direction == 0
    assert not layer.active


def test_stop_releases_the_key(templates):
    barrel = Barrel(900.0, 30.0)
    layer = make_layer(barrel, templates, lambda: 1500.0)
    ended = []
    layer.finished.connect(lambda reading, ok: ended.append(ok))

    assert layer.start()
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()

    assert barrel.direction == 1
    layer.stop()
    assert barrel.direction == 0
    assert ended == [False]
    assert not layer.active


def test_target_gone_ends_the_lay(templates):
    barrel = Barrel(900.0, 30.0)
    target = {"mils": 1500.0}
    layer = make_layer(barrel, templates, lambda: target["mils"])
    QTimer.singleShot(250, lambda: target.update(mils=None))

    _, on_target = run(layer)

    assert not on_target
    assert barrel.direction == 0
