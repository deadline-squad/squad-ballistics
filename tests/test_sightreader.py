import os

import pytest

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QLinearGradient

import sightreader
from sightreader import GrayImage, LabelTemplates, decode_labels, find_edge, find_pointer, find_ticks, read_scale
from sightimage import draw_sight

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


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


class AmbiguousTemplates:
    """Digit templates whose every label reads as well as the value 100
    above it: the hundreds digit cannot be told apart."""

    def __init__(self, templates):
        self.templates = templates
        self.values = templates.values

    def scores(self, readings):
        scores = self.templates.scores(readings)

        return {value: max(scores.get(value, -1.0), scores.get(value - 100, -1.0)) for value in scores}


def test_labels_that_read_as_well_as_another_sequence_are_no_reading(templates):
    """Two sequences of values match the labels alike (a margin of 0, under
    MIN_MARGIN): which one the scale shows is not known, so there is no
    reading rather than one 100 mils off."""
    image = draw_sight(1043.4)

    assert read(image, templates).mils == pytest.approx(1043.4, abs=0.05)
    assert read(image, AmbiguousTemplates(templates)) is None


@pytest.mark.parametrize("mils", [1043.4, 1100.5, 1250.2])
def test_a_speck_between_two_ticks_is_not_a_tick(templates, mils):
    """A short dark mark across the ticks 0.65 of a mil below the one above
    the pointer (dirt, a blade of grass): off the tick spacing by more than
    SPACING_TOLERANCE, it is left out; taken for the next tick it moved the
    reading 0.3 to 0.4 mil."""
    image = draw_sight(mils)
    gray = GrayImage.from_qimage(image)
    edge = find_edge(gray, 960, 540, 1.0)
    pointer = find_pointer(gray, edge, 540, 1.0)
    above = [tick for tick in find_ticks(gray, edge, 540, 1.0) if tick.y <= pointer][-1]

    painter = QPainter(image)
    painter.fillRect(QRectF(edge - 18, above.y + 0.65 * sightreader.MIL_SPACING - 1, 10, 2), QColor(30, 30, 30))
    painter.end()

    assert read(image, templates).mils == pytest.approx(mils, abs=0.05)


@pytest.mark.parametrize("hud", [1.5, 1.6])
def test_a_sight_past_the_hud_scales_tried_is_read_at_its_tick_spacing(templates, hud):
    """A sight 1.5 or 1.6 times the size expected (a display scaling of 150%
    the grab's pixel ratio did not show): none of HUD_SCALES reads it, the
    scale its ticks measure does."""
    assert read(draw_sight(1043.4, hud=hud), templates).mils == pytest.approx(1043.4, abs=0.05)


def load_sight(name):
    image = QImage(os.path.join(DATA, f"sight_{name}.png"))
    assert not image.isNull()

    return GrayImage.from_qimage(image)


# Grabs of the scale (the region ScreenSight grabs, 422x346 at 1080p, grey)
# of real 1080p frames of the game: the 81 mm mortar's sight in the videos
# of a mortar guide (j: "Squad Mortars Guide in 4 Minutes", 2026, at the
# second named) and of a mortar and Hell Cannon guide (z: 2022). The mils
# at the pointer as read by eye, to a fifth of a mil, off the ticks and
# labels around it; the 50s are labelled in a larger font.
REAL_SIGHTS = [
    ("j_117", 1333.8),     # the pointer between 1333 and 1334
    ("j_131", 1330.4),     # the pointer just above the 1330 label's tick
    ("j_137", 1555.5),     # a larger "1550" label below
    ("j_149", 1510.0),     # the pointer on the 1510 label's tick
    ("j_162", 1515.4),     # a darker scene behind the scale
    ("z_061", 1565.6),     # near the barrel's top: 1580, its warning sign
    ("z_065", 1557.8),     # another game version and scene
]


@pytest.mark.parametrize("name, mils", REAL_SIGHTS)
def test_reads_real_sights(templates, name, mils):
    """The digit templates are drawn with Roboto Condensed and the
    synthetic sights with the same font: these frames are drawn by the
    game. The screen's centre is outside the grab, as in ScreenSight."""
    gray = load_sight(name)
    left, top = 960 - round(0.47 * 1080), 540 - round(0.16 * 1080)

    reading = read_scale(gray, 960 - left, 540 - top, 1.0, templates)

    assert reading is not None
    assert reading.mils == pytest.approx(mils, abs=0.3)
    assert reading.labels >= 3
    assert reading.margin >= sightreader.MIN_MARGIN
