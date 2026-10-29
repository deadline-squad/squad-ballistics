import pytest

pytest.importorskip("PyQt6.QtGui")

from PyQt6.QtGui import QColor, QImage

from compassreader import DigitReader, read_compass
from sightreader import GrayImage, LabelTemplates
from compassimage import bearing_text, draw_compass
from sightimage import draw_sight


@pytest.fixture(scope="module")
def digits():
    return DigitReader(LabelTemplates())


def read(image, digits):
    gray = GrayImage.from_qimage(image)

    return read_compass(gray, gray.width / 2, image.height() / 1080, digits)


def circular(a, b):
    return (a - b + 180) % 360 - 180


@pytest.mark.parametrize("bearing", [0.04, 7.25, 89.96, 123.45, 182.2, 270.9, 359.7])
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)])
def test_reads_the_mortar_views_tenths(digits, bearing, size):
    reading = read(draw_compass(bearing, *size), digits)

    assert reading is not None
    assert reading.text == bearing_text(bearing, True)
    assert reading.resolution == 0.1
    assert circular(reading.degrees, bearing) == pytest.approx(0, abs=0.051)
    assert reading.ticks >= 3


@pytest.mark.parametrize("bearing", [3.7, 182.2, 359.9])
def test_whole_degrees_are_cut_and_read_as_the_middle(digits, bearing):
    reading = read(draw_compass(bearing, precise=False), digits)

    assert reading.resolution == 1.0
    assert reading.text == bearing_text(bearing, False)
    assert circular(reading.degrees, int(bearing) + 0.5) == pytest.approx(0, abs=1e-9)


def test_reads_a_grab_of_the_bottom_only(digits):
    """The overlay grabs a strip at the bottom centre: the centre is the
    grab's, the scale the screen's."""
    screen = draw_compass(211.37, 2560, 1440)
    strip = screen.copy(1280 - 600, 1440 - 100, 1200, 100)
    gray = GrayImage.from_qimage(strip)

    reading = read_compass(gray, 600.0, 1440 / 1080, digits)

    assert reading.text == "211.4"


@pytest.mark.parametrize("scene", [15, 120, 175])
def test_reads_over_a_dark_or_bright_scene(digits, scene):
    assert read(draw_compass(301.2, scene=scene), digits).text == "301.2"


def test_a_number_the_strip_disagrees_with_is_no_reading(digits):
    """The strip's ticks must sit where the number puts them (within the
    lag of a turn): a misread number does not pass."""
    assert read(draw_compass(87.4, text="093.4"), digits) is None
    assert read(draw_compass(87.4, text="088.9"), digits) is not None


def test_no_compass_no_reading(digits):
    blank = QImage(1920, 1080, QImage.Format.Format_RGB32)
    blank.fill(QColor(90, 90, 90))
    assert read(blank, digits) is None

    assert read(draw_sight(1043.4), digits) is None
