"""The mark: a thin red cross 50 px across, so the centre of an in-game
marker can be laid on the exact crossing."""

from PyQt6.QtGui import QColor, QImage, QPainter

import overlay


def rendered(size=121):
    """The mark painted on a black image with its centre in the middle."""
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(QColor("black"))

    painter = QPainter(image)
    overlay.paint_crosshair(painter, size // 2, size // 2)
    painter.end()

    return image


def is_red(image, x, y):
    color = image.pixelColor(x, y)

    return color.red() > 200 and color.green() < 120 and color.blue() < 120


def test_the_mark_is_a_thin_red_cross_50_px_across():
    assert 2 * overlay.MARK_ARM == 50
    assert overlay.MARK_THICKNESS == 1
    assert overlay.MARK_COLOR == (255, 48, 48)
    assert overlay.MARK_REACH == 25


def test_the_painted_cross_spans_50_px_and_is_one_pixel_thin():
    image = rendered()
    centre = image.width() // 2

    reds_on_the_axis = [x for x in range(image.width()) if is_red(image, x, centre)]
    reds_across = [y for y in range(image.height()) if is_red(image, centre, y)]

    assert min(reds_on_the_axis) <= centre - 24
    assert max(reds_on_the_axis) >= centre + 23
    assert min(reds_on_the_axis) >= centre - 25
    assert max(reds_on_the_axis) <= centre + 25
    assert len(reds_across) == len(reds_on_the_axis)

    # Two pixels off the horizontal arm there is nothing but the faint edge.
    assert not is_red(image, centre + 15, centre + 3)
    assert not is_red(image, centre + 15, centre - 3)
