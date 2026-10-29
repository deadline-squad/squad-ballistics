import math
from dataclasses import dataclass

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


@dataclass(frozen=True)
class HoldPanel:
    """What the AGS-17 timer panel shows (see Overlay.set_hold_panel).

    target_text  -- first line, e.g. "TARGET 1000 m · S 1.25 s"
    barrel_text  -- big line: where the barrel shoots now, e.g. "~820 m"
    held/target  -- seconds S held since W and the hold time (None: none)
    """

    target_text: str
    barrel_text: str
    held: float
    target: float = None
    reached: bool = False
    s_down: bool = False
    w_down: bool = False
    auto_text: str = ""


PANEL_WIDTH = 230
PANEL_HEIGHT = 112
PANEL_MARGIN = 24

# The info label: gap right of the crosshair, height of one line, the
# narrowest it wraps to and its distance from the screen's right edge (px).
INFO_GAP = 10
INFO_LINE_HEIGHT = 20
INFO_MIN_WIDTH = 200
INFO_EDGE = 8

INFO_FLAGS = (
    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
).value | Qt.TextFlag.TextWordWrap.value


class Overlay(QWidget):
    def __init__(self, config):
        super().__init__()

        self.config = config

        self.info_text = ""

        self.hold_panel = None

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
        cfg = self.config

        reach = max(
            cfg["circle_radius"] if cfg["circle_enabled"] else 0,
            cfg["line_gap"] + cfg["line_length"] if cfg["lines_enabled"] else 0,
            cfg["dot_size"] + 6
        )

        left = x + reach + INFO_GAP
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

    def hold_panel_rect(self):
        corner = self.config.get("hold_panel_corner", "top_right")

        x = PANEL_MARGIN if corner.endswith("left") \
            else self.width() - PANEL_WIDTH - PANEL_MARGIN
        y = PANEL_MARGIN if corner.startswith("top") \
            else self.height() - PANEL_HEIGHT - PANEL_MARGIN

        return QRectF(x, y, PANEL_WIDTH, PANEL_HEIGHT)

    def set_hold_panel(self, panel):
        """Show the timer panel (a HoldPanel) or hide it (None).

        Only the panel area is repainted: this runs on every key poll.
        """
        if panel == self.hold_panel:
            return

        self.hold_panel = panel

        self.update(self.hold_panel_rect().toAlignedRect().adjusted(-2, -2, 2, 2))

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

        if self.hold_panel is not None:
            self.draw_hold_panel(painter, self.hold_panel)

        painter.end()

    def draw_hold_panel(self, painter, panel):
        rect = self.hold_panel_rect()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(rect, 8, 8)

        left = rect.x() + 12
        width = rect.width() - 24

        def text(y, height, size, bold, color, value, align=Qt.AlignmentFlag.AlignLeft):
            font = overlay_font(size)
            font.setBold(bold)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(
                QRectF(left, rect.y() + y, width, height),
                align | Qt.AlignmentFlag.AlignVCenter,
                value
            )

        text(6, 18, 9, True, "#ffa040", panel.target_text)
        text(24, 34, 20, True, "#40e0ff" if panel.target is not None else "#9a9a9a", panel.barrel_text)

        held = f"{min(panel.held, 99.99):.2f}"
        timing = held if panel.target is None else f"{held} / {panel.target:.2f}"
        text(58, 18, 11, True, "#ffffff", timing)

        if panel.auto_text:
            text(58, 18, 9, True, "#ff5050", panel.auto_text, Qt.AlignmentFlag.AlignRight)

        # Progress to the hold time: green once it is time to release.
        bar = QRectF(left, rect.y() + 80, width, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 50))
        painter.drawRoundedRect(bar, 3, 3)

        if panel.target:
            share = max(0.0, min(1.0, panel.held / panel.target))
            painter.setBrush(QColor("#40d060" if panel.reached else "#40e0ff"))
            painter.drawRoundedRect(
                QRectF(bar.x(), bar.y(), bar.width() * share, bar.height()), 3, 3
            )

        keys = "   ".join(
            f"{name} {'●' if down else '○'}"
            for name, down in (("S", panel.s_down), ("W", panel.w_down))
        )
        text(90, 16, 9, False, "#80ff80" if panel.s_down or panel.w_down else "#9a9a9a", keys)

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
