"""Synthetic pictures of the mortar sight's elevation scale, for tests.

Drawn like the game's sight (measured on 1080p frames of it, see
sightreader): ticks every mil ending EDGE_GAP left of the scale's edge line,
5- and 10-mil ticks longer, 10-mil ones labelled (larger every 50), a dark
triangle pointer on the centre line, the ticks slanting away from the centre
as on the wheel.
"""

from functools import cache

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPolygonF

from sightreader import LabelTemplates

# 1080p pixels
EDGE_FROM_CENTRE = 294
EDGE_GAP = 6
MIL = 8.2
TICK = {1: 32, 5: 56, 10: 60}
TICK_WIDTH = 2.5
LABEL_SIZE = (13, 19)
WHEEL_RADIUS = 800
POINTER = (30, 16)

SCALE_GREY = 190
SCENE_GREY = 70
INK_GREY = 60


@cache
def font_family():
    """The sight's font (Roboto Condensed), registered with Qt on the first
    call, or a generic family when it is not found."""
    LabelTemplates()

    for family in QFontDatabase.families():
        if "Roboto" in family:
            return family

    return "sans-serif"


def draw_sight(mils, width=1920, height=1080, scene=SCENE_GREY, pointer=True, hud=1.0):
    """A screen with the sight's scale at `mils` (the pointer's reading),
    drawn `hud` times its size at this screen height."""
    k = height / 1080 * hud
    cx, cy = width / 2, height / 2
    edge = cx - EDGE_FROM_CENTRE * k

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(scene, scene, scene))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # The scale's face, and the bright band right of the edge line
    face = QRectF(cx - 0.43 * height * hud, 0, 0.43 * height * hud - EDGE_FROM_CENTRE * k + 8 * k, height)
    painter.fillRect(face, QColor(SCALE_GREY, SCALE_GREY, SCALE_GREY))
    painter.fillRect(QRectF(edge, 0, 2 * k, height), QColor(20, 20, 20))

    small, large = (QFont(font_family()), QFont(font_family()))
    small.setPixelSize(round(LABEL_SIZE[0] * k))
    large.setPixelSize(round(LABEL_SIZE[1] * k))

    end = edge - EDGE_GAP * k
    reach = int(0.5 * height / (MIL * k))

    for mil in range(int(mils) - reach, int(mils) + reach + 1):
        y = cy - (mil - mils) * MIL * k
        length = TICK[10 if mil % 10 == 0 else 5 if mil % 5 == 0 else 1] * k
        slant = (y - cy) / (WHEEL_RADIUS * k)
        left = QPointF(end - length, y + slant * length)

        pen = painter.pen()
        pen.setColor(QColor(10, 10, 10))
        pen.setWidthF(TICK_WIDTH * k)
        painter.setPen(pen)
        painter.drawLine(QPointF(end, y), left)

        if mil % 10:
            continue

        font = large if mil % 50 == 0 else small
        painter.setFont(font)
        painter.setPen(QColor(INK_GREY, INK_GREY, INK_GREY))
        box = QRectF(left.x() - 4 * k - 80 * k, left.y() - 15 * k, 80 * k, 30 * k)
        painter.drawText(box, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(mil))

    if pointer:
        tip = QPointF(end, cy)
        length, half = POINTER[0] * k, POINTER[1] * k / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0))
        painter.drawPolygon(QPolygonF([tip, QPointF(end + length, cy - half),
                                       QPointF(end + length, cy + half)]))

    painter.end()

    return image
