"""Synthetic pictures of Squad's HUD compass, for tests.

Drawn like the game's compass (measured on 1080p frames of it, see
compassreader): a tick per degree, 6.345 px apart, white, 8 px tall,
14 px every 5 degrees and 18 px every 15, centred 46.5 px above the bottom;
the bearing box (32 x 20, dark) at the centre with the bearing's whole
degrees; labels every 15 degrees below.
"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen

from sightimage import font_family

SPACING = 6.345
ROW_FROM_BOTTOM = 46.5
TICK = {1: 8, 5: 14, 15: 18}
TICK_WIDTH = 2
BOX = (32, 20)
DIGIT_PIXELS = 17
LABEL_FROM_BOTTOM = 22
HALF_WIDTH = 400

NAMES = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}


def draw_compass(bearing, width=1920, height=1080, scene=70, hud=1.0, box_text=None):
    """A screen with the compass at `bearing` (degrees), drawn `hud` times
    its size at this screen height. `box_text` overrides the box's digits."""
    k = height / 1080 * hud
    cx = width / 2
    row = height - ROW_FROM_BOTTOM * k

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(scene, scene, scene))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(250, 250, 250), TICK_WIDTH * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
    label_font = QFont(font_family())
    label_font.setPixelSize(round(14 * k))

    reach = math.ceil(HALF_WIDTH / SPACING)

    for offset in range(-reach, reach + 1):
        angle = math.floor(bearing) + offset
        x = cx + (angle - bearing) * SPACING * k

        if abs(x - cx) > HALF_WIDTH * k:
            continue

        length = TICK[15 if angle % 15 == 0 else 5 if angle % 5 == 0 else 1] * k
        painter.setPen(pen)
        painter.drawLine(QPointF(x, row - length / 2), QPointF(x, row + length / 2))

        if angle % 15 == 0:
            text = NAMES.get(angle % 360, f"{angle % 360:03d}")
            painter.setFont(label_font)
            painter.drawText(QRectF(x - 30 * k, height - (LABEL_FROM_BOTTOM + 10) * k, 60 * k, 20 * k),
                             Qt.AlignmentFlag.AlignCenter, text)

    box = QRectF(cx - BOX[0] / 2 * k, row - BOX[1] / 2 * k, BOX[0] * k, BOX[1] * k)
    painter.fillRect(box, QColor(10, 10, 10))

    digits = QFont(font_family())
    digits.setPixelSize(round(DIGIT_PIXELS * k))
    digits.setBold(True)
    painter.setFont(digits)
    painter.setPen(QColor(250, 250, 250))
    text = box_text if box_text is not None else f"{math.floor(bearing) % 360:03d}"
    painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    painter.end()

    return image
