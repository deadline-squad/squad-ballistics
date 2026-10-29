import math

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QRectF
)

from PyQt6.QtGui import (
    QColor,
    QPainter,
    QBrush,
    QPen,
    QPolygonF,
    QFont,
    QFontMetricsF,
    QGuiApplication
)

from PyQt6.QtWidgets import QWidget


# Fonts of the overlay text, the first one installed is used.
OVERLAY_FONTS = ["Inter", "Noto Sans", "DejaVu Sans"]


def overlay_font(size):
    font = QFont()
    font.setFamilies(OVERLAY_FONTS)
    font.setPointSize(size)

    return font


def paint_crosshair(painter, cfg, x, y):
    """Draw the configured crosshair centred on (x, y).

    Shared by the overlay and the preview on the crosshair page.
    """
    r, g, b = cfg["color"]

    color = QColor(r, g, b, cfg["opacity"])

    outline = QColor(
        "black" if cfg.get("outline_color") == "black" else "white"
    )
    outline.setAlpha(cfg["opacity"])

    outline_width = cfg["outline_thickness"]

    dot_size = cfg["dot_size"]

    if cfg["glow_enabled"]:
        painter.setPen(Qt.PenStyle.NoPen)

        for spread, alpha in ((dot_size + 9, 25), (dot_size + 5, 55)):
            painter.setBrush(QBrush(QColor(r, g, b, min(alpha, cfg["opacity"]))))
            painter.drawEllipse(QPointF(x, y), spread, spread)

    if cfg["lines_enabled"]:
        length = cfg["line_length"]
        gap = cfg["line_gap"]

        lines = [
            (x, y - gap, x, y - gap - length),
            (x - gap, y, x - gap - length, y),
            (x + gap, y, x + gap + length, y),
        ]

        if not cfg["t_style"]:
            lines.append((x, y + gap, x, y + gap + length))

        passes = []

        if cfg["outline_enabled"]:
            passes.append(
                QPen(
                    outline,
                    cfg["line_thickness"] + outline_width * 2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.FlatCap
                )
            )

        passes.append(
            QPen(
                color,
                cfg["line_thickness"],
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap
            )
        )

        for pen in passes:
            painter.setPen(pen)

            for x1, y1, x2, y2 in lines:
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if cfg["circle_enabled"]:
        painter.setBrush(Qt.BrushStyle.NoBrush)

        radius = cfg["circle_radius"]

        if cfg["outline_enabled"]:
            painter.setPen(QPen(outline, 2 + outline_width * 2))
            painter.drawEllipse(QPointF(x, y), radius, radius)

        painter.setPen(QPen(color, 2))
        painter.drawEllipse(QPointF(x, y), radius, radius)

    if cfg["dot_enabled"]:
        painter.setBrush(QBrush(color))

        if cfg["outline_enabled"]:
            painter.setPen(QPen(outline, outline_width))
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawEllipse(QPointF(x, y), dot_size, dot_size)


# The info label: gap right of the crosshair, height of one line, the
# narrowest it wraps to and its distance from the screen's right edge (px).
INFO_GAP = 10
INFO_LINE_HEIGHT = 20
INFO_MIN_WIDTH = 200
INFO_EDGE = 8

# The range ladder: its ticks end this far left of the mark's centre line,
# are this long, at least LADDER_SPACING screen heights apart, and start
# LADDER_CLEAR px below the crosshair's reach (px).
LADDER_GAP = 6
LADDER_TICK = 10
LADDER_SPACING = 0.017
LADDER_CLEAR = 6

INFO_FLAGS = (
    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
).value | Qt.TextFlag.TextWordWrap.value


class Overlay(QWidget):
    def __init__(self, config):
        super().__init__()

        self.config = config

        self.info_text = ""

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating
        )

        self.offset = 0.0

        self.target_offset = 0.0

        # False for weapons laid by elevation: no aim mark, only the info line.
        self.mark_visible = True

        # Range ticks under the centre: [(distance m, pixels below)].
        self.ladder = []

        # The animation timer only runs while the aim point is moving.
        self.animation_timer = QTimer(self)

        self.animation_timer.timeout.connect(
            self.animate_offset
        )

        self.move_to_screen()

        self.show()

    def move_to_screen(self):
        screens = QGuiApplication.screens()

        index = int(self.config.get("monitor", 0))

        if 0 <= index < len(screens):
            screen = screens[index]
        else:
            screen = QGuiApplication.primaryScreen()

        self.setGeometry(screen.geometry())

        self.update()

    @property
    def center_x(self):
        return self.width() / 2 + self.config.get("center_offset_x", 0)

    @property
    def center_y(self):
        return self.height() / 2 + self.config.get("center_offset_y", 0)

    # Distance from the screen edge inside which the mark is still drawn.
    EDGE_MARGIN = 20

    def screen_width(self):
        return self.width()

    def is_offscreen(self, offset):
        """Whether the aim mark for `offset` falls outside the screen."""
        y = self.center_y + offset

        return not self.EDGE_MARGIN <= y <= self.height() - self.EDGE_MARGIN

    def set_info(self, text):
        """Show `text` next to the mark ("" hides it).

        Only where the label was and is now is repainted, and nothing when
        the text is the same: this runs on every hold-timer poll.
        """
        if text == self.info_text:
            return

        old = self.info_rect()

        self.info_text = text

        area = old.united(self.info_rect())

        # The shadow is drawn 1 px lower right; antialiasing spills over.
        self.update(area.toAlignedRect().adjusted(-2, -2, 3, 3))

    def crosshair_reach(self):
        """How far the crosshair reaches from its centre (px)."""
        cfg = self.config

        return max(
            cfg["circle_radius"] if cfg["circle_enabled"] else 0,
            cfg["line_gap"] + cfg["line_length"] if cfg["lines_enabled"] else 0,
            cfg["dot_size"] + 6
        )

    def ladder_bounds(self):
        """(first, spacing, reach) of the range ladder in px, as
        ballistics.range_ladder takes them: clear of the crosshair, ticks
        apart by a share of the screen height, down to the screen edge."""
        first = self.crosshair_reach() + LADDER_CLEAR
        spacing = max(14.0, LADDER_SPACING * self.height())
        reach = self.height() - self.EDGE_MARGIN - self.center_y

        return first, spacing, reach

    def set_ladder(self, ticks):
        """Show the range ladder: [(distance m, pixels below the centre)];
        an empty list hides it."""
        ticks = list(ticks)

        if ticks == self.ladder:
            return

        self.ladder = ticks
        self.update()

    def ladder_font(self):
        font = overlay_font(8)
        font.setBold(True)
        return font

    def info_font(self):
        font = overlay_font(10)
        font.setBold(True)
        return font

    def info_anchor(self):
        """(x, y) the info label is placed by: the mark, or next to the edge
        arrow when the mark is off-screen."""
        x = self.center_x
        y = self.center_y + self.offset

        if self.mark_visible and self.is_offscreen(self.offset):
            y = 50 if y < self.EDGE_MARGIN else self.height() - 50

        return x, y

    def info_rect(self):
        """Where the info label is drawn: right of the crosshair, as wide as
        its text, wrapped onto more lines when it would leave the screen.
        Centred on the anchor's height."""
        x, y = self.info_anchor()

        left = x + self.crosshair_reach() + INFO_GAP
        room = max(INFO_MIN_WIDTH, self.width() - INFO_EDGE - left)
        metrics = QFontMetricsF(self.info_font(), self)

        # +2: rounding must not wrap a line that fits
        width = metrics.horizontalAdvance(self.info_text) + 2

        if width <= room:
            return QRectF(left, y - INFO_LINE_HEIGHT / 2, width, INFO_LINE_HEIGHT)

        height = max(
            INFO_LINE_HEIGHT,
            metrics.boundingRect(QRectF(0, 0, room, 10000), INFO_FLAGS, self.info_text).height()
        )

        return QRectF(left, y - height / 2, room, height)

    def set_offset(self, value):
        """Move the aim mark `value` pixels below the centre; None hides it.

        None is for weapons laid by elevation on their own sight (mortars,
        rocket artillery): a mark on the screen would point nowhere useful.
        """
        if value is None:
            self.mark_visible = False
            self.offset = self.target_offset = 0.0
            self.animation_timer.stop()
            self.update()
            return

        self.mark_visible = True
        value = float(value)

        if math.isnan(value):
            value = 0.0

        # Off-screen offsets only need to keep their direction.
        limit = self.height() * 2
        self.target_offset = max(-limit, min(limit, value))

        if not self.config.get("animated", True):
            self.offset = self.target_offset
            self.animation_timer.stop()
            self.update()
            return

        fps = max(10, min(240, int(self.config.get("fps", 60))))

        self.animation_timer.start(int(1000 / fps))

    def reset_offset(self):
        self.set_offset(0)

    def animate_offset(self):
        self.offset += (
            self.target_offset - self.offset
        ) * 0.12

        if abs(
            self.target_offset - self.offset
        ) < 0.01:

            self.offset = self.target_offset

            self.animation_timer.stop()

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        cfg = self.config

        r, g, b = cfg["color"]

        color = QColor(r, g, b, cfg["opacity"])

        x = self.center_x
        y = self.center_y + self.offset

        if self.mark_visible and self.ladder:
            self.draw_ladder(painter, color)

        if not self.mark_visible:
            pass
        elif self.is_offscreen(self.offset):
            # The aim point is off-screen (very high angle shot):
            # show an arrow on the edge pointing towards it; the label
            # stays next to it (see info_anchor).
            self.draw_edge_arrow(painter, color, x, y < self.EDGE_MARGIN)
        else:
            paint_crosshair(painter, cfg, x, y)

        if cfg.get("info_enabled", True) and self.info_text:
            self.draw_info(painter, color)

        painter.end()

    def draw_ladder(self, painter, color):
        """Range ticks left of the centre line, labelled with the range:
        the target at that range goes on its tick. Dimmer than the mark,
        with a dark shadow to read over bright ground."""
        x = self.center_x
        right = x - LADDER_GAP
        left = right - LADDER_TICK

        tick_color = QColor(color)
        tick_color.setAlpha(round(color.alpha() * 0.8))
        shadow = QColor(0, 0, 0, round(color.alpha() * 0.7))

        painter.setFont(self.ladder_font())
        metrics = QFontMetricsF(painter.font())
        height = metrics.height()

        for distance, offset in self.ladder:
            y = self.center_y + offset
            label = QRectF(left - 4 - 60, y - height / 2, 60, height)
            flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

            for pen_color, shift in ((shadow, 1), (tick_color, 0)):
                painter.setPen(QPen(pen_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                painter.drawLine(QPointF(left + shift, y + shift), QPointF(right + shift, y + shift))
                painter.drawText(label.translated(shift, shift), flags, str(distance))

    def draw_info(self, painter, color):
        rect = self.info_rect()

        painter.setFont(self.info_font())

        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(rect.translated(1, 1), INFO_FLAGS, self.info_text)

        painter.setPen(color)
        painter.drawText(rect, INFO_FLAGS, self.info_text)

    def draw_edge_arrow(self, painter, color, x, top):
        size = 14

        if top:
            tip = 8
            base = tip + size
        else:
            tip = self.height() - 8
            base = tip - size

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(color))

        painter.drawPolygon(
            QPolygonF([
                QPointF(x, tip),
                QPointF(x - size, base),
                QPointF(x + size, base)
            ])
        )
