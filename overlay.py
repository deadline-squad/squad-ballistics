"""The overlay: a transparent full-screen window over the game that draws
the aim mark, the range ladder and an info line, and lets every click
through.

It needs translucent windows. On X11 those are blended only by a
compositing manager; without one the window is opaque black, so the overlay
then stays hidden and says so (`compositing_active`). Compositing can also
stop while the overlay is up (KWin suspends it for a fullscreen game that
asks to block it), so `X11CompositorWatch` follows it: the overlay hides
when it stops and comes back when it starts again. It follows the screen
it is on: a resolution change or a monitor plugged in or out puts it back
over the configured monitor and emits `screen_changed`, so the mark and the
ladder can be recomputed for the new size.
"""

import ctypes
import ctypes.util
import math
import os
from typing import NamedTuple

from PyQt6.QtCore import (
    Qt,
    QObject,
    QPointF,
    QRectF,
    QSocketNotifier,
    QTimer,
    pyqtSignal
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

from PyQt6.QtWidgets import QMessageBox, QWidget

from config import MARK_COLORS
from i18n import tr


# Fonts of the overlay text, the first one installed is used.
OVERLAY_FONTS = ["Inter", "Noto Sans", "DejaVu Sans"]


def overlay_font(size):
    """The overlay's font (`OVERLAY_FONTS`) at `size` points."""
    font = QFont()
    font.setFamilies(OVERLAY_FONTS)
    font.setPointSize(size)

    return font


class MarkShape(NamedTuple):
    """What a mark style draws at size 100 %, in pixels; 0 leaves a part out.

    `no_bottom` drops the lower line (the T).
    """

    dot_radius: float = 0
    line_length: float = 0
    line_gap: float = 0
    line_thickness: float = 0
    circle_radius: float = 0
    no_bottom: bool = False


# The shapes of config.MARK_STYLES.
PRESETS = {
    "dot": MarkShape(dot_radius=4),
    "cross": MarkShape(line_length=10, line_gap=0, line_thickness=2),
    "t": MarkShape(line_length=12, line_gap=5, line_thickness=2, no_bottom=True),
    "circle": MarkShape(dot_radius=2, circle_radius=16),
    "cross_dot": MarkShape(dot_radius=3, line_length=14, line_gap=6, line_thickness=2),
}

# The outline around every part of the mark (px) and the circle's stroke.
OUTLINE_WIDTH = 1
CIRCLE_THICKNESS = 2


def mark_shape(cfg):
    """The shape of `cfg["mark_style"]` scaled by `cfg["mark_size"]` percent."""
    base = PRESETS[cfg["mark_style"]]
    factor = cfg["mark_size"] / 100

    return MarkShape(
        dot_radius=base.dot_radius * factor,
        line_length=base.line_length * factor,
        line_gap=base.line_gap * factor,
        line_thickness=base.line_thickness * factor,
        circle_radius=base.circle_radius * factor,
        no_bottom=base.no_bottom
    )


def mark_color(cfg):
    """The configured mark colour as a QColor."""
    return QColor(*MARK_COLORS[cfg["color"]])


def mark_reach(cfg):
    """How far the mark reaches from its centre (px)."""
    shape = mark_shape(cfg)

    return max(
        shape.circle_radius,
        shape.line_gap + shape.line_length,
        shape.dot_radius + 6
    )


def paint_crosshair(painter, cfg, x, y):
    """Draw the configured mark centred on (x, y).

    Shared by the overlay and the preview on the crosshair page.
    """
    shape = mark_shape(cfg)

    color = mark_color(cfg)

    outline = QColor("white")

    if shape.line_length:
        length = shape.line_length
        gap = shape.line_gap

        lines = [
            (x, y - gap, x, y - gap - length),
            (x - gap, y, x - gap - length, y),
            (x + gap, y, x + gap + length, y),
        ]

        if not shape.no_bottom:
            lines.append((x, y + gap, x, y + gap + length))

        for pen_color, width in (
            (outline, shape.line_thickness + OUTLINE_WIDTH * 2),
            (color, shape.line_thickness),
        ):
            painter.setPen(
                QPen(
                    pen_color,
                    width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.FlatCap
                )
            )

            for x1, y1, x2, y2 in lines:
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if shape.circle_radius:
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(outline, CIRCLE_THICKNESS + OUTLINE_WIDTH * 2))
        painter.drawEllipse(QPointF(x, y), shape.circle_radius, shape.circle_radius)

        painter.setPen(QPen(color, CIRCLE_THICKNESS))
        painter.drawEllipse(QPointF(x, y), shape.circle_radius, shape.circle_radius)

    if shape.dot_radius:
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(outline, OUTLINE_WIDTH))
        painter.drawEllipse(QPointF(x, y), shape.dot_radius, shape.dot_radius)


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


def load_xlib():
    """libX11 with the signatures this module calls, or None without it."""
    try:
        xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    except OSError:
        return None

    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultScreen.restype = ctypes.c_int
    xlib.XDefaultScreen.argtypes = [ctypes.c_void_p]
    xlib.XRootWindow.restype = ctypes.c_ulong
    xlib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    xlib.XGetSelectionOwner.restype = ctypes.c_ulong
    xlib.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xlib.XConnectionNumber.restype = ctypes.c_int
    xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
    xlib.XPending.restype = ctypes.c_int
    xlib.XPending.argtypes = [ctypes.c_void_p]
    xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    xlib.XFlush.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

    return xlib


def compositing_selection(xlib, display):
    """The atom `_NET_WM_CM_S<screen>` of `display`'s default screen, which
    a compositing manager owns while it runs (EWMH, "Compositing managers":
    https://specifications.freedesktop.org/wm-spec/latest/)."""
    screen = xlib.XDefaultScreen(display)

    return xlib.XInternAtom(display, f"_NET_WM_CM_S{screen}".encode(), 0)


def x11_compositing_manager_running():
    """Whether a compositing manager runs on $DISPLAY's default screen: it
    owns the selection `_NET_WM_CM_S<screen>` (see `compositing_selection`).

    True when that cannot be found out (no libX11, no display), so a failed
    check never hides the overlay.
    """
    xlib = load_xlib()

    if xlib is None:
        return True

    display = xlib.XOpenDisplay(None)

    if not display:
        return True

    try:
        return xlib.XGetSelectionOwner(display, compositing_selection(xlib, display)) != 0
    finally:
        xlib.XCloseDisplay(display)


# XFixes selection events (fixesproto, "Selection Tracking"): the owner of
# the selection changed, its window was destroyed, its client disconnected.
XFIXES_SELECTION_EVENTS = (1 << 0) | (1 << 1) | (1 << 2)

# Room for one Xlib XEvent (a union of 24 longs); the watch only drains them.
XEvent = ctypes.c_long * 24


class X11CompositorWatch(QObject):
    """Follows whether a compositing manager runs on $DISPLAY's default
    screen and emits `changed(active)` when it starts or stops.

    The X server reports every change of the `_NET_WM_CM_S<screen>`
    selection's owner (XFixes selection tracking,
    https://gitlab.freedesktop.org/xorg/proto/xorgproto/-/blob/master/fixesproto.txt)
    on a connection of the watch's own (PyQt cannot reach Qt's), whose
    socket a QSocketNotifier watches: nothing runs while nothing changes.
    Create it with `start`; `stop` closes the connection.
    """

    changed = pyqtSignal(bool)

    def __init__(self, xlib, display, parent=None):
        super().__init__(parent)

        self.xlib = xlib
        self.display = display
        self.root = xlib.XRootWindow(display, xlib.XDefaultScreen(display))
        self.selection = compositing_selection(xlib, display)
        self.active = xlib.XGetSelectionOwner(display, self.selection) != 0

        self.notifier = QSocketNotifier(
            xlib.XConnectionNumber(display),
            QSocketNotifier.Type.Read,
            self
        )
        self.notifier.activated.connect(self.check)

    @classmethod
    def start(cls, parent=None):
        """A running watch, or None when there is no X display or the
        server or the system lacks XFixes."""
        xlib = load_xlib()

        if xlib is None:
            return None

        try:
            xfixes = ctypes.CDLL(ctypes.util.find_library("Xfixes") or "libXfixes.so.3")
        except OSError:
            return None

        display = xlib.XOpenDisplay(None)

        if not display:
            return None

        xfixes.XFixesQueryExtension.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
        ]
        xfixes.XFixesQueryVersion.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
        ]
        xfixes.XFixesSelectSelectionInput.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
        ]

        event_base, error_base = ctypes.c_int(), ctypes.c_int()
        # The protocol asks a client to agree on a version before any request.
        major, minor = ctypes.c_int(5), ctypes.c_int(0)

        if not (
            xfixes.XFixesQueryExtension(display, ctypes.byref(event_base), ctypes.byref(error_base))
            and xfixes.XFixesQueryVersion(display, ctypes.byref(major), ctypes.byref(minor))
        ):
            xlib.XCloseDisplay(display)
            return None

        watch = cls(xlib, display, parent)

        xfixes.XFixesSelectSelectionInput(
            display, watch.root, watch.selection, XFIXES_SELECTION_EVENTS
        )
        xlib.XFlush(display)

        return watch

    def check(self):
        """Read the pending events and emit `changed` if the selection
        gained or lost its owner.

        The owner is asked after the events are drained: an event that
        arrives while the answer is awaited was sent before the answer, so
        the answer already counts it, and one sent later wakes the notifier.
        """
        if self.display is None:
            return

        event = XEvent()

        while self.xlib.XPending(self.display):
            self.xlib.XNextEvent(self.display, ctypes.byref(event))

        active = self.xlib.XGetSelectionOwner(self.display, self.selection) != 0

        if active != self.active:
            self.active = active
            self.changed.emit(active)

    def stop(self):
        """Stop watching and close the X connection."""
        if self.display is None:
            return

        self.notifier.setEnabled(False)
        self.xlib.XCloseDisplay(self.display)
        self.display = None


def compositing_active():
    """Whether a translucent window is blended over what is below it.

    Only X11 (Qt's "xcb" platform, also XWayland) can run without a
    compositing manager; Wayland always composites, and the offscreen
    platform of the tests has no screen to cover.
    """
    if QGuiApplication.platformName() != "xcb":
        return True

    return x11_compositing_manager_running()


def compositor_advice(environ=None):
    """The "no compositor" warning for the running desktop.

    KDE Plasma composites by default, but KWin lets a fullscreen window
    block compositing (Proton asks for it with `_NET_WM_BYPASS_COMPOSITOR`):
    the advice there is to stop that, not to turn compositing on.
    """
    environ = os.environ if environ is None else environ

    desktops = environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")

    return tr("no_compositor_kde" if "KDE" in desktops else "no_compositor")


class Overlay(QWidget):
    """The full-screen overlay window over the configured monitor.

    `config` is the app's settings dict, kept by reference: the mark's
    style, colour, size and alignment and the monitor are read from it on
    every paint.
    """

    # The overlay moved to another screen or its screen changed size.
    screen_changed = pyqtSignal()

    def __init__(self, config):
        super().__init__()

        self.config = config

        # The warning shown instead of the overlay without a compositor.
        self.compositor_warning = None

        # Whether the overlay was last asked to show (by `setVisible`): it
        # comes back when compositing does only then.
        self.wanted = False

        # Started on X11 only: Wayland always composites.
        self.compositor_watch = None

        if QGuiApplication.platformName() == "xcb":
            self.compositor_watch = X11CompositorWatch.start(self)

        if self.compositor_watch is not None:
            self.compositor_watch.changed.connect(self.compositing_changed)

        # Screen changes arrive as several signals at once (a monitor
        # unplugged also resizes the virtual desktop); they are handled
        # once, after Qt has updated its screen list.
        self.screen_timer = QTimer(self)
        self.screen_timer.setSingleShot(True)
        self.screen_timer.setInterval(0)
        self.screen_timer.timeout.connect(self.follow_screens)

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

        # False for weapons laid by elevation: no aim mark, only the info line.
        self.mark_visible = True

        # Range ticks under the centre: [(distance m, pixels below)].
        self.ladder = []

        app = QGuiApplication.instance()
        app.screenAdded.connect(self.watch_screen)
        app.screenAdded.connect(self.schedule_screen_check)
        app.screenRemoved.connect(self.schedule_screen_check)
        app.primaryScreenChanged.connect(self.schedule_screen_check)

        for screen in QGuiApplication.screens():
            self.watch_screen(screen)

        self.move_to_screen()

        self.show()

    def setVisible(self, visible):
        """Show or hide the overlay; it is not shown on X11 without a
        compositing manager, where it would be an opaque black screen, and a
        warning says why instead (again on every later try to show it).
        Shown, it follows the compositor, see `compositing_changed`."""
        self.wanted = visible

        if visible and not compositing_active():
            self.warn_no_compositor()
            return

        super().setVisible(visible)

    def compositing_changed(self, active):
        """Hide the overlay and warn when compositing stops while it is
        wanted; show it again, without the warning, when compositing is back.
        An overlay the user turned off stays off."""
        if not self.wanted:
            return

        if active:
            if self.compositor_warning is not None:
                self.compositor_warning.hide()

            super().setVisible(True)
        else:
            super().setVisible(False)
            self.warn_no_compositor()

    def warn_no_compositor(self):
        """Show the non-modal "no compositor" warning, once at a time.

        It does not take the keyboard focus: it may come up while the game
        has it. The advice depends on the desktop (`compositor_advice`).
        """
        if self.compositor_warning is None:
            self.compositor_warning = QMessageBox(
                QMessageBox.Icon.Warning,
                tr("no_compositor_title"),
                compositor_advice()
            )
            self.compositor_warning.setWindowModality(Qt.WindowModality.NonModal)
            self.compositor_warning.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.compositor_warning.show()
        self.compositor_warning.raise_()

    def closeEvent(self, event):
        """Close the compositor warning with the overlay: a window left
        open would keep the app running after the main window closed. The
        compositor is no longer watched."""
        if self.compositor_warning is not None:
            self.compositor_warning.close()

        if self.compositor_watch is not None:
            self.compositor_watch.stop()

        super().closeEvent(event)

    def watch_screen(self, screen):
        """Follow `screen`'s size and position (a resolution change)."""
        screen.geometryChanged.connect(self.schedule_screen_check)

    def schedule_screen_check(self, *args):
        """Re-place the overlay once the current screen changes settle."""
        self.screen_timer.start()

    def follow_screens(self):
        """Put the overlay back over the configured monitor and tell the
        owner, who recomputes the mark and the ladder for the new size."""
        self.move_to_screen()

        self.screen_changed.emit()

    def target_screen(self):
        """The screen of the configured monitor index; the primary screen
        when that monitor is not connected (it is used again once it is)."""
        screens = QGuiApplication.screens()

        index = int(self.config.get("monitor", 0))

        if 0 <= index < len(screens):
            return screens[index]

        return QGuiApplication.primaryScreen()

    def move_to_screen(self):
        """Cover the configured monitor (see `target_screen`)."""
        self.setGeometry(self.target_screen().geometry())

        self.update()

    @property
    def center_x(self):
        """x of the aim centre: the screen centre moved by the alignment."""
        return self.width() / 2 + self.config.get("center_offset_x", 0)

    @property
    def center_y(self):
        """y of the aim centre: the screen centre moved by the alignment."""
        return self.height() / 2 + self.config.get("center_offset_y", 0)

    # Distance from the screen edge inside which the mark is still drawn.
    EDGE_MARGIN = 20

    def screen_width(self):
        """Width of the covered screen in pixels, which the FOV spans."""
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
        return mark_reach(self.config)

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
        """Font of the range ladder's labels."""
        font = overlay_font(8)
        font.setBold(True)
        return font

    def info_font(self):
        """Font of the info line."""
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
        """Move the aim mark `value` pixels below the centre; None or NaN
        hides it.

        None is for weapons laid by elevation on their own sight (mortars,
        rocket artillery): a mark on the screen would point nowhere useful.
        NaN is an aim that could not be computed: a mark at the centre would
        point at the wrong range, so none is drawn. ±infinity keeps its
        direction and shows as the edge arrow.
        """
        if value is None or math.isnan(value):
            self.mark_visible = False
            self.offset = 0.0
            self.update()
            return

        self.mark_visible = True

        # Off-screen offsets only need to keep their direction.
        limit = self.height() * 2
        self.offset = max(-limit, min(limit, float(value)))
        self.update()

    def paintEvent(self, event):
        """Draw the ladder, the mark (or the edge arrow) and the info line."""
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        cfg = self.config

        color = mark_color(cfg)

        x = self.center_x
        y = self.center_y + self.offset

        if self.mark_visible:
            if self.ladder:
                self.draw_ladder(painter, color)

            if self.is_offscreen(self.offset):
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
        """The info line in the mark's colour over a dark shadow."""
        rect = self.info_rect()

        painter.setFont(self.info_font())

        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(rect.translated(1, 1), INFO_FLAGS, self.info_text)

        painter.setPen(color)
        painter.drawText(rect, INFO_FLAGS, self.info_text)

    def draw_edge_arrow(self, painter, color, x, top):
        """A triangle at the top (`top`) or bottom edge at `x`, pointing at
        an aim point off the screen."""
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
