"""Synthetic pictures of Squad's HUD compass (USQCompassMK2), for tests.

Drawn like the game's compass, with the sizes measured on 1080p frames of
it (Oct 2026, 270 frames of the mortar's guide video, a Grad video and an
AGS video, see compassreader): a white tick every 15 degrees 43 px above
the bottom (letters instead at N, NE, E...), labels every 15 degrees 22.5
px above the bottom, hidden within 6 degrees of the centre, where the
bearing is in bold on a dark backing box with a dark outline: "182.2" on
the mortar's view, "182" elsewhere. The strip (ticks and labels) sits 0.5
degree after where the number puts it. The pictures are harsher than the
game's, on purpose: foliage-like speckles, characters packed 1 to 5 px
apart, scenes as bright as snow.
"""

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen

from sightimage import font_family

# Measured on real frames (1080p px, degrees)
SPACING = 6.33
TICKS_FROM_BOTTOM = 43
TICK = 10
TEXT_FROM_BOTTOM = 22.5
TEXT_PIXELS = 17
LABEL_PIXELS = 14
HALF_WIDTH = 400
HIDDEN_NEAR = 6
STRIP_OFFSET = 0.5
BACKING_PADDING = 3
BACKING_HEIGHT = 20

NAMES = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}


def bearing_text(bearing, precise):
    """The number the game shows: "%.1f" rounded, or whole degrees cut,
    in (0, 360]."""
    if precise:
        text = f"{bearing:.1f}"
        return "360.0" if text in ("0.0", "360.0") else f"{float(text):05.1f}"

    whole = math.floor(bearing) % 360

    return f"{whole if whole else 360:03d}"


def draw_compass(bearing, width=1920, height=1080, scene=70, precise=True, text=None,
                 lag=0.0, hud=1.0, gaps=(1.5,), ticks=True, speckles=0.0, seed=1,
                 backing=True, shadow=True, tick_pen=2.0, labels=None):
    """A screen with the compass at `bearing` (degrees).

    `text` overrides the bearing's number; `lag`: the strip is drawn this
    many degrees behind the number, as in a turn; `hud`: the HUD's scale;
    `gaps`: the px between the ink of the number's characters, in turn
    (1.5 on the game's, up to 5 after a "1"), or "random" for 1 to 4 each;
    `ticks`: False draws the strip without its ticks; `speckles`: bright
    specks (foliage) per 1000 px of the strip's band; `backing`, `shadow`:
    the number's dark box and outline; `tick_pen`: the ticks' width;
    `labels`: the text of the label under the mark at an angle (0-345) in
    place of its own, "" for none.
    """
    k = height / 1080 * hud
    cx = width / 2
    tick_row = height - TICKS_FROM_BOTTOM * k
    text_row = height - TEXT_FROM_BOTTOM * k
    strip = bearing - lag
    chance = random.Random(seed)

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(scene, scene, scene))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    for _ in range(round(speckles * width * 70 * k / 1000)):
        x, y = chance.uniform(0, width), chance.uniform(height - 70 * k, height)
        grey = chance.randint(150, 235)
        painter.fillRect(QRectF(x, y, 2 * k, 2 * k), QColor(grey, grey, grey))

    pen = QPen(QColor(255, 255, 255), tick_pen * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
    label_font = QFont(font_family())
    label_font.setPixelSize(round(LABEL_PIXELS * k))
    letter_font = QFont(font_family())
    letter_font.setPixelSize(round(20 * k))

    first = math.ceil((strip - HALF_WIDTH / SPACING / hud) / 15) * 15

    for angle in range(first, math.floor(strip + HALF_WIDTH / SPACING / hud) + 1, 15):
        x = cx + (angle - strip + STRIP_OFFSET) * SPACING * k
        name = NAMES.get(angle % 360)

        if ticks and name is None:
            painter.setPen(pen)
            painter.drawLine(QPointF(x, tick_row - TICK / 2 * k), QPointF(x, tick_row + TICK / 2 * k))
        elif ticks:
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(letter_font)
            painter.drawText(QRectF(x - 20 * k, tick_row - 12 * k, 40 * k, 24 * k),
                             Qt.AlignmentFlag.AlignCenter, name)

        label = (labels or {}).get(angle % 360, f"{angle % 360:03d}")

        if abs(angle - strip) > HIDDEN_NEAR and label:
            painter.setFont(label_font)

            for colour, offset in ((QColor(0, 0, 0), k), (QColor(252, 252, 252), 0)):
                painter.setPen(colour)
                painter.drawText(QRectF(x - 30 * k + offset, text_row - 10 * k + offset, 60 * k, 20 * k),
                                 Qt.AlignmentFlag.AlignCenter, label)

    number = QFont(font_family())
    number.setPixelSize(round(TEXT_PIXELS * k))
    number.setBold(True)
    painter.setFont(number)
    _draw_packed(painter, number, text if text is not None else bearing_text(bearing, precise),
                 cx, text_row, k, gaps, chance, backing, shadow)

    painter.end()

    return image


def _draw_packed(painter, font, text, centre_x, middle_y, k, gaps, chance, backing, shadow):
    """`text` centred at (centre_x, middle_y) with its characters' ink
    `gaps` apart, as the game packs them, whatever the font's side
    bearings."""
    metrics = QFontMetricsF(font)
    inks = [metrics.tightBoundingRect(character) for character in text]
    spaces = [chance.uniform(1, 4) if gaps == "random" else gaps[i % len(gaps)]
              for i in range(len(text) - 1)]
    width = sum(ink.width() for ink in inks) + k * sum(spaces)
    baseline = middle_y + metrics.tightBoundingRect("0").height() / 2

    if backing:
        padding = BACKING_PADDING * k
        painter.fillRect(QRectF(centre_x - width / 2 - padding, middle_y - BACKING_HEIGHT / 2 * k,
                                width + 2 * padding, BACKING_HEIGHT * k), QColor(0, 0, 0, 110))

    for colour, offset in ((QColor(0, 0, 0), k), (QColor(255, 255, 255), 0)):
        if offset and not shadow:
            continue

        painter.setPen(colour)
        x = centre_x - width / 2

        for i, (character, ink) in enumerate(zip(text, inks)):
            painter.drawText(QPointF(x - ink.left() + offset, baseline + offset), character)
            x += ink.width() + (spaces[i] * k if i < len(spaces) else 0)
