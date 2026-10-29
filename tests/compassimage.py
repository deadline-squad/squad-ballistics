"""Synthetic pictures of Squad's HUD compass (USQCompassMK2), for tests.

Drawn like the game's compass (measured on 1080p frames of it, see
compassreader): a white tick every 15 degrees 43 px above the bottom
(letters instead at N, NE, E...), labels every 15 degrees 22.5 px above
the bottom, hidden near the centre, where the bearing is in bold: "182.2"
on the mortar's view, "182" elsewhere.
"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen

from sightimage import font_family

SPACING = 6.33
TICKS_FROM_BOTTOM = 43
TICK = 10
TEXT_FROM_BOTTOM = 22.5
TEXT_PIXELS = 17
LABEL_PIXELS = 14
HALF_WIDTH = 400
HIDDEN_NEAR = 6
# The ink of the bearing's characters is this far apart (1080p px)
CHARACTER_GAP = 1.5

NAMES = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}


def bearing_text(bearing, precise):
    """The number the game shows: "%.1f" rounded, or whole degrees cut,
    in (0, 360]."""
    if precise:
        text = f"{bearing:.1f}"
        return "360.0" if text in ("0.0", "360.0") else f"{float(text):05.1f}"

    whole = math.floor(bearing) % 360

    return f"{whole if whole else 360:03d}"


def draw_compass(bearing, width=1920, height=1080, scene=70, precise=True, text=None):
    """A screen with the compass at `bearing` (degrees). `text` overrides
    the bearing's number."""
    k = height / 1080
    cx = width / 2
    tick_row = height - TICKS_FROM_BOTTOM * k
    text_row = height - TEXT_FROM_BOTTOM * k

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(scene, scene, scene))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(245, 245, 245), 2 * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
    label_font = QFont(font_family())
    label_font.setPixelSize(round(LABEL_PIXELS * k))
    letter_font = QFont(font_family())
    letter_font.setPixelSize(round(20 * k))

    first = math.ceil((bearing - HALF_WIDTH / SPACING) / 15) * 15

    for angle in range(first, math.floor(bearing + HALF_WIDTH / SPACING) + 1, 15):
        x = cx + (angle - bearing) * SPACING * k
        name = NAMES.get(angle % 360)

        if name is None:
            painter.setPen(pen)
            painter.drawLine(QPointF(x, tick_row - TICK / 2 * k), QPointF(x, tick_row + TICK / 2 * k))
        else:
            painter.setPen(QColor(245, 245, 245))
            painter.setFont(letter_font)
            painter.drawText(QRectF(x - 20 * k, tick_row - 12 * k, 40 * k, 24 * k),
                             Qt.AlignmentFlag.AlignCenter, name)

        if abs(angle - bearing) > HIDDEN_NEAR:
            painter.setPen(QColor(235, 235, 235))
            painter.setFont(label_font)
            painter.drawText(QRectF(x - 30 * k, text_row - 10 * k, 60 * k, 20 * k),
                             Qt.AlignmentFlag.AlignCenter, f"{angle % 360:03d}")

    number = QFont(font_family())
    number.setPixelSize(round(TEXT_PIXELS * k))
    number.setBold(True)
    painter.setFont(number)
    painter.setPen(QColor(250, 250, 250))
    _draw_packed(painter, number, text if text is not None else bearing_text(bearing, precise), cx, text_row, k)

    painter.end()

    return image


def _draw_packed(painter, font, text, centre_x, middle_y, k):
    """`text` centred at (centre_x, middle_y) with its characters' ink
    CHARACTER_GAP apart, as the game packs them, whatever the font's
    side bearings."""
    metrics = QFontMetricsF(font)
    inks = [metrics.tightBoundingRect(character) for character in text]
    gap = CHARACTER_GAP * k
    x = centre_x - (sum(ink.width() for ink in inks) + gap * (len(text) - 1)) / 2
    baseline = middle_y + metrics.tightBoundingRect("0").height() / 2

    for character, ink in zip(text, inks):
        painter.drawText(QPointF(x - ink.left(), baseline), character)
        x += ink.width() + gap
