"""The mark's default shape: a thin red cross 50 px across, so the centre of
an in-game marker can be laid on the exact crossing."""

from PyQt6.QtGui import QColor, QImage, QPainter

import config
import overlay


def rendered(cfg, size=121):
    """The mark painted on a black image with its centre in the middle."""
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(QColor("black"))

    painter = QPainter(image)
    overlay.paint_crosshair(painter, cfg, size // 2, size // 2)
    painter.end()

    return image


def is_red(image, x, y):
    color = image.pixelColor(x, y)

    return color.red() > 200 and color.green() < 120 and color.blue() < 120


def test_the_default_mark_is_a_thin_red_cross():
    assert config.DEFAULT_CONFIG["mark_style"] == "cross_thin"
    assert config.DEFAULT_CONFIG["color"] == "red"
    assert config.DEFAULT_CONFIG["mark_size"] == 100


def test_the_thin_cross_is_50_px_across_at_100_percent():
    shape = overlay.mark_shape(config.DEFAULT_CONFIG)

    assert shape.line_gap == 0
    assert 2 * shape.line_length == 50
    assert shape.line_thickness == 1


def test_the_painted_cross_spans_50_px_and_is_one_pixel_thin():
    image = rendered(config.DEFAULT_CONFIG)
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


def test_the_size_setting_scales_the_cross():
    cfg = dict(config.DEFAULT_CONFIG, mark_size=200)

    assert overlay.mark_reach(cfg) == 50
