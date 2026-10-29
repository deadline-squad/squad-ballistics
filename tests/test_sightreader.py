import pytest

pytest.importorskip("PyQt6.QtGui")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QLinearGradient

import sightreader
from sightreader import GrayImage, LabelTemplates, decode_labels, read_scale
from sightimage import draw_sight


@pytest.fixture(scope="module")
def templates():
    return LabelTemplates()


def read(image, templates, centre=None):
    gray = GrayImage.from_qimage(image)
    cx, cy = centre or (gray.width // 2, gray.height // 2)

    return read_scale(gray, cx, cy, image.height() / sightreader.REFERENCE_HEIGHT, templates)


@pytest.mark.parametrize("mils", [800.0, 827.7, 1000.0, 1043.4, 1111.1, 1250.0, 1333.3, 1499.95, 1579.0])
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (2560, 1440), (3440, 1440), (3840, 2160)])
def test_reads_the_scale(templates, mils, size):
    reading = read(draw_sight(mils, *size), templates)

    assert reading is not None
    assert reading.mils == pytest.approx(mils, abs=0.05)
    assert reading.labels >= 2
    assert reading.margin > 0


def test_reads_a_grab_of_the_region_only(templates):
    """ScreenSight grabs the region left of the centre: the centre is then
    outside the image, the scale comes from the screen height."""
    screen = draw_sight(1043.4, 2560, 1440)
    left, top = 2560 // 2 - round(0.47 * 1440), 720 - round(0.16 * 1440)
    region = screen.copy(left, top, round(0.39 * 1440), round(0.32 * 1440))
    gray = GrayImage.from_qimage(region)

    reading = read_scale(gray, 1280 - left, 720 - top, 1440 / 1080, templates)

    assert reading.mils == pytest.approx(1043.4, abs=0.05)


@pytest.mark.parametrize("hud", [0.75, 0.9, 1.15, 1.3])
def test_reads_a_sight_at_another_hud_scale(templates, hud):
    assert read(draw_sight(1043.4, hud=hud), templates).mils == pytest.approx(1043.4, abs=0.05)


def test_reads_a_blurred_scale(templates):
    """Video compression or a lower render scale blurs the ticks and digits."""
    sharp = draw_sight(1187.6)
    blurred = sharp.scaled(1280, 720, transformMode=Qt.TransformationMode.SmoothTransformation) \
        .scaled(1920, 1080, transformMode=Qt.TransformationMode.SmoothTransformation)

    assert read(blurred, templates).mils == pytest.approx(1187.6, abs=0.2)


def test_reads_over_a_bright_or_dark_scene(templates):
    for scene in (20, 140):
        assert read(draw_sight(955.5, scene=scene), templates).mils == pytest.approx(955.5, abs=0.05)


def test_without_the_pointer_reads_at_the_centre_line(templates):
    assert read(draw_sight(1300.25, pointer=False), templates).mils == pytest.approx(1300.25, abs=0.1)


def test_no_sight_no_reading(templates):
    blank = QImage(1920, 1080, QImage.Format.Format_RGB32)
    blank.fill(QColor(90, 90, 90))
    assert read(blank, templates) is None

    gradient = QImage(1920, 1080, QImage.Format.Format_RGB32)
    painter = QPainter(gradient)
    fill = QLinearGradient(0, 0, 1920, 1080)
    fill.setColorAt(0, QColor(0, 0, 0))
    fill.setColorAt(1, QColor(255, 255, 255))
    painter.fillRect(gradient.rect(), fill)
    painter.end()
    assert read(gradient, templates) is None


def test_off_centre_sight_is_not_read(templates):
    """The scale is looked for left of the screen centre only."""
    shifted = draw_sight(1043.4)
    gray = GrayImage.from_qimage(shifted)

    assert read_scale(gray, 400, 540, 1.0, templates) is None


def test_digit_templates_match_themselves(templates):
    for digit, vector in enumerate(templates.digits):
        matches = [sum(a * b for a, b in zip(vector, other)) for other in templates.digits]
        assert max(range(10), key=matches.__getitem__) == digit


def test_scores_values_with_as_many_digits(templates):
    four = [templates.digits[1], templates.digits[0], templates.digits[4], templates.digits[0]]
    scores = templates.scores([four])

    assert max(scores, key=scores.get) == 1040
    assert all(len(str(value)) == 4 for value in scores)


def test_decode_prefers_the_consistent_sequence():
    """Labels 10 apart: one label alone may prefer a wrong value, together
    they read right."""
    values = range(800, 1600, 10)

    def scores(best, second=None, second_score=0.0):
        result = {value: 0.1 for value in values}
        result[best] = 0.8
        if second is not None:
            result[second] = second_score
        return result

    # The middle label looks more like 1340 than 1040
    decoded = decode_labels(
        [0, 1, 2],
        [scores(1030), scores(1340, 1040, 0.75), scores(1050)]
    )

    value, match, margin = decoded
    assert value == 1030
    assert match == pytest.approx((0.8 + 0.75 + 0.8) / 3)
    assert margin > 0


def test_decode_needs_every_label_among_the_values():
    assert decode_labels([0, 1], [{1590: 1.0}, {1590: 1.0}]) is None
