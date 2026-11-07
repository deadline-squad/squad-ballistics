"""The game's own window on the X server, so the overlay can sit on it.

The mark is laid on the picture the game draws, and that picture is the
game's window, not the monitor: a game in a window, or at a lower mode that a
compositor scales to the screen, would get a mark for the wrong width. The
window is found the way a window manager lists its clients: the root
window's `_NET_CLIENT_LIST` (EWMH, "Root Window Properties",
https://specifications.freedesktop.org/wm-spec/latest/), and a client is the
game when

* its `WM_CLASS` holds `steam_app_393380`, the name Steam's Proton gives the
  windows of a Steam game (`steam_app_<app id>`), or
* its title is exactly `SquadGame`, Unreal Engine's name for the project.

Neither was checked against a live Proton window of the game; the class
follows what Steam window rules for Proton games use, the title the
engine's default.

`X11Windows` is the thin layer over libX11 (plain ctypes, nothing to
install), `find_game_rect` the lookup on top of it, and `GameWindowWatch`
polls it on a timer. The poll costs a few round trips to the X server on a
local socket and runs on the UI thread without waiting for anything else.
"""

import contextlib
import ctypes
import ctypes.util

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# The WM_CLASS name Steam's Proton gives the windows of Squad (Steam app 393380).
GAME_WM_CLASS = "steam_app_393380"

# The title the game's window carries.
GAME_TITLE = "SquadGame"

# How often the window is looked for again (ms): a window dragged or resized
# is followed within this time.
POLL_MS = 500

# Predefined atoms of the X protocol (X11/Xatom.h).
XA_CARDINAL = 6
XA_STRING = 31
XA_WINDOW = 33

# The longest property read (32-bit units): a client list of 4 MB.
PROPERTY_LENGTH = 1 << 20


@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
def ignore_x_error(display, event):
    """Xlib's default error handler ends the process; a window that closes
    between the list and the question about it is expected here and
    answered with a failed call instead (see `X11Windows.errors_ignored`)."""
    return 0


def is_game_window(wm_class, title):
    """Whether a client with the `WM_CLASS` names `wm_class` and the title
    `title` is the game's window."""
    return GAME_WM_CLASS in wm_class or title.strip() == GAME_TITLE


def find_game_rect(windows):
    """(x, y, width, height) of the game's window in root coordinates, or
    None when it is not running. `windows` is an `X11Windows` or anything
    with its methods.

    Windows of the game other than the picture (a launcher, a splash) can
    share its class, so the largest one is taken.
    """
    rects = []

    for window in windows.client_list():
        if not is_game_window(windows.wm_class(window), windows.title(window)):
            continue

        rect = windows.geometry(window)

        if rect is not None and rect[2] > 0 and rect[3] > 0:
            rects.append(rect)

    return max(rects, key=lambda rect: rect[2] * rect[3], default=None)


class X11Windows:
    """The questions about windows that `find_game_rect` asks, answered by
    an X server over its own connection. Create it with `open`; `close`
    ends the connection."""

    def __init__(self, xlib, display):
        self.xlib = xlib
        self.display = display
        self.root = xlib.XRootWindow(display, xlib.XDefaultScreen(display))
        self.client_list_atom = self.atom("_NET_CLIENT_LIST")
        self.wm_class_atom = self.atom("WM_CLASS")
        self.wm_name_atom = self.atom("WM_NAME")
        self.net_wm_name_atom = self.atom("_NET_WM_NAME")
        self.utf8_atom = self.atom("UTF8_STRING")

    @classmethod
    def open(cls):
        """A connection to $DISPLAY, or None without libX11 or a display."""
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
        xlib.XGetWindowProperty.restype = ctypes.c_int
        xlib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
            ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)
        ]
        xlib.XGetGeometry.restype = ctypes.c_int
        xlib.XGetGeometry.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)
        ]
        xlib.XTranslateCoordinates.restype = ctypes.c_int
        xlib.XTranslateCoordinates.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong)
        ]
        xlib.XSetErrorHandler.restype = ctypes.c_void_p
        xlib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        xlib.XFree.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

        display = xlib.XOpenDisplay(None)

        if not display:
            return None

        return cls(xlib, display)

    @contextlib.contextmanager
    def errors_ignored(self):
        """Run the block with `ignore_x_error` as Xlib's error handler, which
        is one for the whole process: the one in place (another library's)
        is put back afterwards."""
        previous = self.xlib.XSetErrorHandler(ctypes.cast(ignore_x_error, ctypes.c_void_p))

        try:
            yield
        finally:
            self.xlib.XSetErrorHandler(previous)

    def atom(self, name):
        """The atom of `name`."""
        return self.xlib.XInternAtom(self.display, name.encode(), 0)

    def property(self, window, name_atom, type_atom):
        """(format, items) of a property of `window`, or None when the
        window or the property is gone or has another type. Items of
        format 8 are bytes, of format 32 unsigned numbers."""
        actual_type = ctypes.c_ulong()
        item_format = ctypes.c_int()
        count = ctypes.c_ulong()
        after = ctypes.c_ulong()
        data = ctypes.c_void_p()

        with self.errors_ignored():
            status = self.xlib.XGetWindowProperty(
                self.display, window, name_atom, 0, PROPERTY_LENGTH, 0, type_atom,
                ctypes.byref(actual_type), ctypes.byref(item_format), ctypes.byref(count),
                ctypes.byref(after), ctypes.byref(data)
            )

        if not data.value:
            return None

        try:
            if status != 0 or actual_type.value != type_atom or count.value == 0:
                return None

            if item_format.value == 8:
                return 8, ctypes.string_at(data.value, count.value)

            # Format 32 is an array of C longs, whatever their size.
            return 32, list(ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[:count.value])
        finally:
            self.xlib.XFree(data)

    def client_list(self):
        """The windows the window manager manages, oldest first."""
        found = self.property(self.root, self.client_list_atom, XA_WINDOW)

        return found[1] if found else []

    def wm_class(self, window):
        """The `WM_CLASS` names (instance, class) of `window`, empty when it
        has none."""
        found = self.property(window, self.wm_class_atom, XA_STRING)

        if not found:
            return ()

        return tuple(name.decode("latin-1") for name in found[1].split(b"\0") if name)

    def title(self, window):
        """The title of `window` ("" when it has none): `_NET_WM_NAME`, else
        the older `WM_NAME`."""
        found = (
            self.property(window, self.net_wm_name_atom, self.utf8_atom)
            or self.property(window, self.wm_name_atom, XA_STRING)
        )

        return found[1].decode("utf-8", errors="replace") if found else ""

    def geometry(self, window):
        """(x, y, width, height) of the window's inside in root coordinates,
        or None when the window is gone. Its frame and title bar, if the
        window manager adds any, are not part of it."""
        root = ctypes.c_ulong()
        x, y = ctypes.c_int(), ctypes.c_int()
        width, height = ctypes.c_uint(), ctypes.c_uint()
        border, depth = ctypes.c_uint(), ctypes.c_uint()

        left, top = ctypes.c_int(), ctypes.c_int()
        child = ctypes.c_ulong()

        with self.errors_ignored():
            if not self.xlib.XGetGeometry(
                self.display, window, ctypes.byref(root), ctypes.byref(x), ctypes.byref(y),
                ctypes.byref(width), ctypes.byref(height), ctypes.byref(border),
                ctypes.byref(depth)
            ):
                return None

            if not self.xlib.XTranslateCoordinates(
                self.display, window, self.root, 0, 0,
                ctypes.byref(left), ctypes.byref(top), ctypes.byref(child)
            ):
                return None

        return left.value, top.value, width.value, height.value

    def close(self):
        """End the connection."""
        if self.display is None:
            return

        self.xlib.XCloseDisplay(self.display)
        self.display = None


class GameWindowWatch(QObject):
    """Looks for the game's window every `POLL_MS` and emits
    `changed(rect)` when it appears, moves, is resized or closes: `rect` is
    (x, y, width, height) in root coordinates, or None once there is no
    window."""

    changed = pyqtSignal(object)

    def __init__(self, windows, parent=None):
        super().__init__(parent)

        self.windows = windows
        self.rect = None

        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    @classmethod
    def start(cls, parent=None):
        """A running watch, or None when there is no X display."""
        windows = X11Windows.open()

        return None if windows is None else cls(windows, parent)

    def poll(self):
        """Look for the window now; emit `changed` if what was found differs
        from the last time."""
        rect = find_game_rect(self.windows)

        if rect == self.rect:
            return

        self.rect = rect
        self.changed.emit(rect)

    def stop(self):
        """Stop looking and close the X connection."""
        self.timer.stop()
        self.windows.close()
