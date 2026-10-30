import os

import pytest

from PyQt6.QtGui import QColor, QFont, QImage, QPainter

from compassreader import DigitReader, read_compass, strip_ticks
from sightreader import GrayImage, LabelTemplates
from compassimage import bearing_text, draw_compass
from sightimage import draw_sight, font_family

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# What the strip must say of a number: within 2.5 degrees while it may lag
# behind a turn, within 1.5 when the camera is still (real mortar frames
# keep the ticks within 0.64 degree of the number).
MOVING = 2.5
STILL = 1.5


@pytest.fixture(scope="module")
def digits():
    return DigitReader(LabelTemplates())


def read(image, digits, tolerance=MOVING):
    gray = GrayImage.from_qimage(image)

    return read_compass(gray, gray.width / 2, image.height() / 1080, digits, tolerance)


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
    assert reading.labels >= 1


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


@pytest.mark.parametrize("scene", [15, 120, 175, 200, 220, 235])
def test_reads_over_a_dark_or_bright_scene(digits, scene):
    """A snow-white scene leaves the HUD's white 20 grey levels to stand
    out by."""
    reading = read(draw_compass(301.2, scene=scene), digits)

    assert reading is not None
    assert reading.text == "301.2"


@pytest.mark.parametrize("gaps", [(1,), (2.5,), (4,), (5,), (1, 5, 2, 4), "random"])
def test_reads_characters_packed_any_distance_apart(digits, gaps):
    """The game packs the digits 1 to 2 px apart, a "1" and the next
    digit up to 5 (a gap rule cut those frames' numbers)."""
    for bearing in (181.0, 111.9, 168.4):
        assert read(draw_compass(bearing, gaps=gaps, precise=False), digits).text == bearing_text(bearing, False)


@pytest.mark.parametrize("gaps", [(1,), (2.5,), (3,), "random"])
def test_reads_the_tenths_packed_any_distance_apart(digits, gaps):
    for bearing in (181.0, 111.9, 168.4):
        assert read(draw_compass(bearing, gaps=gaps), digits).text == bearing_text(bearing, True)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_reads_through_foliage_speckles(digits, seed):
    """Bright specks all over the strip, beside the number too."""
    reading = read(draw_compass(215.3, speckles=6, seed=seed, scene=110), digits)

    assert reading is not None
    assert reading.text == "215.3"


@pytest.mark.parametrize("hud", [0.8, 0.9, 1.1, 1.25])
@pytest.mark.parametrize("tolerance", [MOVING, STILL])
def test_reads_a_compass_at_another_hud_scale(digits, hud, tolerance):
    reading = read(draw_compass(215.3, hud=hud), digits, tolerance)

    assert reading is not None
    assert reading.text == "215.3"


def test_reads_a_compass_whose_ticks_are_faded(digits):
    """The labels alone are the strip."""
    reading = read(draw_compass(182.2, ticks=False), digits)

    assert reading.text == "182.2"
    assert reading.ticks == 0
    assert reading.labels >= 3


def test_a_number_the_strip_disagrees_with_is_no_reading(digits):
    """The strip's ticks must sit where the number puts them (within the
    lag of a turn): a misread number does not pass."""
    assert read(draw_compass(87.4, text="093.4"), digits) is None
    assert read(draw_compass(87.4, text="088.9"), digits) is not None


def test_the_strip_has_to_sit_where_the_camera_is_still(digits):
    lagging = draw_compass(215.3, lag=2.0)

    assert read(lagging, digits, MOVING).text == "215.3"
    assert read(lagging, digits, STILL) is None
    assert read(draw_compass(215.3), digits, STILL).text == "215.3"


def test_the_default_allows_a_strip_a_few_degrees_behind(digits):
    """Without a tolerance, a strip may lag by up to 2.5 degrees (a turn)."""
    gray = GrayImage.from_qimage(draw_compass(215.3, lag=2.0))
    behind = GrayImage.from_qimage(draw_compass(215.3, lag=3.5))

    assert read_compass(gray, gray.width / 2, 1.0, digits).text == "215.3"
    assert read_compass(behind, gray.width / 2, 1.0, digits) is None


def labelled(*texts):
    """A compass at 182.2 whose labels at 150, 165, 195 and 210 read
    `texts` (None keeps the mark's own, "" has none)."""
    marks = {150: "150", 165: "165", 195: "195", 210: "210"}
    shown = {mark: text if text is not None else own
             for (mark, own), text in zip(marks.items(), texts + (None,) * 4)}

    return draw_compass(182.2, 1920, 1080, labels=shown)


@pytest.mark.parametrize("texts, read_it", [
    (("", "165", "195", ""), True),             # two labels that agree
    (("", "165", "", ""), True),                # one, with the ticks to back it
    (("", "165", "105", ""), False),            # one agrees, one says another number
    (("120", "165", "105", ""), False),         # one agrees, two say others
    (("150", "165", "105", ""), True),          # two agree, one says another
    (("", "", "", ""), False),                  # none to read
])
def test_the_labels_that_agree_must_outnumber_those_that_do_not(digits, texts, read_it):
    assert (read(labelled(*texts), digits) is not None) == read_it


def test_a_label_a_few_degrees_off_its_mark_is_no_agreement(digits):
    """A label at its mark's place only counts within the tolerance: a still
    strip has 1.5 degrees to spare."""
    on_the_mark = GrayImage.from_qimage(draw_compass(182.2, 1920, 1080, ticks=False))
    behind = GrayImage.from_qimage(draw_compass(182.2, 1920, 1080, ticks=False, lag=2.0))

    assert read_compass(on_the_mark, 960.0, 1.0, digits, STILL).text == "182.2"
    assert read_compass(behind, 960.0, 1.0, digits, STILL) is None
    assert read_compass(behind, 960.0, 1.0, digits, MOVING).text == "182.2"


def test_a_turning_strip_is_not_looked_at(digits):
    """While the barrel turns the number is taken alone: the strip is
    behind by more than any tolerance."""
    lagging = draw_compass(215.3, lag=9.0)
    gray = GrayImage.from_qimage(lagging)

    assert read(lagging, digits, MOVING) is None

    reading = read_compass(gray, gray.width / 2, 1.0, digits, None)

    assert reading.text == "215.3"
    assert (reading.ticks, reading.labels) == (0, 0)


def accepted(digits, bearing, text, precise, tolerance, size=(1920, 1080)):
    return read(draw_compass(bearing, *size, precise=precise, text=text), digits, tolerance) is not None


def replaced(text, position, digit):
    return text[:position] + str(digit) + text[position + 1:]


def test_a_digit_misread_by_tens_or_hundreds_never_passes(digits):
    """Every digit of the number replaced with every other, strip at the
    true bearing: the ticks alone only pin it modulo 15 degrees (23% of
    the tens swaps passed), the labels say which 15."""
    swaps = tried = 0

    for bearing in (87.4, 182.2, 215.3, 268.9, 301.5, 7.7):
        text = bearing_text(bearing, True)

        for position in (0, 1):
            for digit in range(10):
                wrong = replaced(text, position, digit)

                if digit == int(text[position]) or float(wrong) > 360:
                    continue

                tried += 1
                swaps += accepted(digits, bearing, wrong, True, MOVING)

    assert tried > 60
    assert swaps == 0


@pytest.mark.parametrize("tolerance, caught_from", [(STILL, 2), (MOVING, 3)])
def test_a_units_digit_misread_by_a_few_degrees_is_caught(digits, tolerance, caught_from):
    """The ticks fix the units digit within the tolerance: a still strip
    catches a units digit that is 2 or more degrees off, a lagging one 3 or
    more; what remains is an error of 1 degree (STILL) or 2 (MOVING)."""
    for bearing in (87.0, 182.0, 215.0, 268.0, 301.0):
        text = bearing_text(bearing, False)

        for digit in range(10):
            wrong = replaced(text, 2, digit)

            if abs(digit - int(text[2])) >= caught_from:
                assert not accepted(digits, bearing + 0.5, wrong, False, tolerance), (bearing, wrong)


def test_the_tenths_digit_is_not_checked(digits):
    """What no check reaches: a tenths digit off by up to 0.9 degree. The
    lay asks for two readings that agree before it trusts one."""
    for digit in (0, 3, 9):
        assert accepted(digits, 182.2, replaced("182.2", 4, digit), True, STILL)


@pytest.mark.parametrize("text, degrees", [
    ("000.0", 0.0), ("360.0", 0.0), ("000", 0.5), ("360", 0.5), ("359", 359.5), ("359.9", 359.9),
])
def test_north_is_0_and_360(digits, text, degrees):
    """0 and 360 are the same bearing; whole degrees are read as the middle
    of their degree, always below 360."""
    reading = read(draw_compass(0.0 if degrees < 1 else degrees, text=text), digits)

    assert reading is not None
    assert reading.degrees == pytest.approx(degrees)
    assert reading.degrees < 360


@pytest.mark.parametrize("text", ["361.0", "360.1", "399", "999.9"])
def test_a_bearing_over_360_is_no_reading(digits, text):
    assert read(draw_compass(0.0, text=text), digits) is None


def noisy_number(text, ink):
    """A gray image of a bearing `text` drawn `ink` over a grey of 90."""
    image = QImage(200, 70, QImage.Format.Format_RGB32)
    image.fill(QColor(90, 90, 90))
    painter = QPainter(image)
    font = QFont(font_family())
    font.setPixelSize(17)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(ink, ink, ink))
    painter.drawText(image.rect().adjusted(0, 22, 0, 0), 0x84, text)
    painter.end()

    return GrayImage.from_qimage(image)


def test_the_number_must_stand_out_of_the_scene(digits):
    """Dull text is no number: it takes 12 grey levels above the scene."""
    assert digits.read(noisy_number("182", 240), 100.0, 1.0)[0] == "182"
    assert digits.read(noisy_number("182", 150), 100.0, 1.0)[0] == "182"
    assert digits.read(noisy_number("182", 95), 100.0, 1.0) is None


def test_every_digit_must_look_like_its_picture(digits):
    """A glyph that is no digit is no number, whatever digit it is closest
    to."""
    assert digits.read(noisy_number("182", 240), 100.0, 1.0)[0] == "182"
    assert digits.read(noisy_number("1W2", 240), 100.0, 1.0) is None
    assert digits.read(noisy_number("1M2", 240), 100.0, 1.0) is None


def tick_row(marks, degrees=100.0, width=2, extra=(), grey=250, scene=90, size=(840, 70)):
    """A gray image with bars at the 15-degree marks of `marks` as the
    strip puts them for a bearing `degrees`, bars at `extra` px, and a wide
    block of ink (a letter, the sight's frame) that makes the brightest
    percent of the row ink whatever the ticks."""
    image = QImage(size[0], size[1], QImage.Format.Format_Grayscale8)
    image.fill(QColor(scene, scene, scene))
    painter = QPainter(image)
    colour = QColor(grey, grey, grey)

    for mark in marks:
        x = size[0] / 2 + (mark - degrees + 0.5) * 6.33
        painter.fillRect(round(x - width / 2), size[1] - 43 - 5, width, 10, colour)

    for x in extra:
        painter.fillRect(x, size[1] - 43 - 5, 2, 10, colour)

    painter.fillRect(size[0] - 60, size[1] - 43 - 5, 30, 10, colour)
    painter.end()

    return GrayImage.from_qimage(image)


# The strip shows 63 degrees either side of the centre
ALL_MARKS = range(45, 151, 15)


def ticks(image, tolerance=MOVING, degrees=100.0):
    return strip_ticks(image, 420.0, 1.0, degrees, tolerance)


def test_ticks_that_sit_on_the_marks_count():
    assert ticks(tick_row(ALL_MARKS)) == len(ALL_MARKS)


def test_ticks_need_to_be_most_of_the_rows_narrow_ink():
    """Narrow ink off the marks (foliage) outvotes the ticks at half or
    more of it, whatever the ticks' number."""
    marks = list(ALL_MARKS)[:6]
    in_between = [round(420 + (m - 100 + 8) * 6.33) for m in ALL_MARKS]

    # 6 of 11 (0.55) pass, 6 of 13 (0.46) do not
    assert ticks(tick_row(marks, extra=in_between[:5])) == 6
    assert ticks(tick_row(marks, extra=in_between[:7])) is None


def test_fewer_than_three_agreeing_ticks_are_no_strip():
    """Two ticks on their marks and one off: 0.67 of the ink, but under
    the three ticks it takes."""
    assert ticks(tick_row([75, 90, 105])) == 3
    assert ticks(tick_row([75, 90], extra=[407])) is None


def test_a_row_without_ticks_has_none_to_disagree():
    """The compass may be drawn without its ticks: 0, not a contradiction
    (the labels then have to confirm the number)."""
    assert ticks(tick_row([])) == 0
    assert ticks(tick_row([75, 90])) == 0


def test_a_tick_is_narrow():
    assert ticks(tick_row(ALL_MARKS, width=4)) == len(ALL_MARKS)
    assert ticks(tick_row(ALL_MARKS, width=5)) == 0


def test_ticks_stand_out_of_a_bright_scene_by_a_few_levels():
    assert ticks(tick_row(ALL_MARKS, grey=255, scene=235)) == len(ALL_MARKS)
    assert ticks(tick_row(ALL_MARKS, grey=255, scene=250)) == 0


def test_ticks_off_by_more_than_the_tolerance_are_no_match():
    image = tick_row(ALL_MARKS)

    assert ticks(image, MOVING, degrees=102.0) is not None
    assert ticks(image, MOVING, degrees=103.5) is None
    assert ticks(image, STILL, degrees=101.0) is not None
    assert ticks(image, STILL, degrees=102.0) is None


@pytest.mark.parametrize("centre", [-5000.0, -1.0, 3000.0, 840.0])
def test_a_centre_outside_the_image_has_no_strip(centre):
    assert strip_ticks(tick_row(ALL_MARKS), centre, 1.0, 100.0) is None


def test_no_compass_no_reading(digits):
    blank = QImage(1920, 1080, QImage.Format.Format_RGB32)
    blank.fill(QColor(90, 90, 90))
    assert read(blank, digits) is None

    assert read(draw_sight(1043.4), digits) is None


def load_crop(name):
    image = QImage(os.path.join(DATA, f"compass_{name}.png"))
    assert not image.isNull()

    return GrayImage.from_qimage(image)


# Crops of the compass strip (bottom centre, 800x80, grey) of real 1080p
# frames of the game, from the videos of the mortar's guide (j), a Grad
# (i) and an AGS (a). What each frame reads, by eye: the number, and
# whether a number the old gap rule did not cut out or one it misread.
REAL_FRAMES = [
    ("j_058", "182.0", 182.0),     # the mortar's view, tenths
    ("i_010", "181", 181.5),       # a 5 px gap after the "1"
    ("i_021", "168", 168.5),       # foliage over the labels
    ("a_063", "119", 119.5),       # foliage within 4 px of the number
    ("j_100", "183", 183.5),       # the strip without its ticks
    ("j_040", "358", 358.5),       # the labels past north
]


@pytest.mark.parametrize("name, text, degrees", REAL_FRAMES)
def test_reads_real_frames(digits, name, text, degrees):
    reading = read_compass(load_crop(name), 400.0, 1.0, digits)

    assert reading is not None
    assert reading.text == text
    assert circular(reading.degrees, degrees) == pytest.approx(0, abs=1e-9)


def test_a_real_frame_whose_units_digit_was_misread_is_no_reading(digits):
    """j_037 shows 274 on a turning strip (2.7 degrees behind); the digit
    reader sees a 1 for the 4 (0.59 match). The old code let 271 pass; a
    strip that may lag by 2.5 degrees or less does not, nor does a still
    one."""
    crop = load_crop("j_037")

    assert read_compass(crop, 400.0, 1.0, digits) is None
    assert read_compass(crop, 400.0, 1.0, digits, MOVING) is None
    assert read_compass(crop, 400.0, 1.0, digits, STILL) is None


def test_a_real_frame_too_dim_to_read_is_no_reading(digits):
    """j_132, a fade: its 1 reads as a 7, 783 (the old code threw it away
    for being over 360 only)."""
    assert read_compass(load_crop("j_132"), 400.0, 1.0, digits) is None
