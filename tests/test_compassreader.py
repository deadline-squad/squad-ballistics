import pytest

pytest.importorskip("PyQt6.QtGui")

from PyQt6.QtGui import QColor, QImage

from compassreader import DigitReader, read_compass
from sightreader import GrayImage, LabelTemplates
from compassimage import draw_compass
from sightimage import draw_sight


@pytest.fixture(scope="module")
def digits():
    return DigitReader(LabelTemplates())


def read(image, digits=None, near=None):
    gray = GrayImage.from_qimage(image)

    return read_compass(gray, gray.width / 2, image.height() / 1080, digits, near)


def circular(a, b):
    return (a - b + 180) % 360 - 180


@pytest.mark.parametrize("bearing", [0.0, 0.5, 7.25, 123.45, 179.99, 270.9, 359.7])
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)])
def test_reads_the_bearing(digits, bearing, size):
    reading = read(draw_compass(bearing, *size), digits)

    assert reading is not None
    assert circular(reading.degrees, bearing) == pytest.approx(0, abs=0.05)
    assert reading.digits == int(bearing)
    assert reading.ticks >= 80


def test_reads_a_grab_of_the_bottom_only(digits):
    """The overlay grabs a strip at the bottom centre: the centre is the
    grab's, the scale the screen's."""
    screen = draw_compass(211.37, 2560, 1440)
    strip = screen.copy(1280 - 600, 1440 - 170, 1200, 170)
    gray = GrayImage.from_qimage(strip)

    reading = read_compass(gray, 600.0, 1440 / 1080, digits)

    assert reading.degrees == pytest.approx(211.37, abs=0.05)


@pytest.mark.parametrize("hud", [0.8, 1.25])
def test_reads_another_hud_scale(digits, hud):
    assert read(draw_compass(48.6, hud=hud), digits).degrees == pytest.approx(48.6, abs=0.05)


@pytest.mark.parametrize("scene", [15, 140])
def test_reads_over_a_dark_or_bright_scene(digits, scene):
    assert read(draw_compass(301.2, scene=scene), digits).degrees == pytest.approx(301.2, abs=0.05)


def test_near_stands_in_for_the_digits():
    image = draw_compass(87.4)

    assert read(image, near=86.0).degrees == pytest.approx(87.4, abs=0.05)
    # Over the 360 wrap
    assert read(draw_compass(359.6), near=1.0).degrees == pytest.approx(359.6, abs=0.05)
    # Without either the turn of 15 degrees is unknown
    assert read(image) is None


def test_digits_that_disagree_with_the_ticks_give_no_reading(digits):
    assert read(draw_compass(87.4, box_text="093"), digits) is None


def test_no_compass_no_reading(digits):
    blank = QImage(1920, 1080, QImage.Format.Format_RGB32)
    blank.fill(QColor(90, 90, 90))
    assert read(blank, digits, near=10.0) is None

    # The mortar sight's scale has evenly spaced ticks too, but no compass
    assert read(draw_sight(1043.4), digits, near=10.0) is None
