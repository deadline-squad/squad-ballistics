"""A stand-in for the game on a real X server: windows with the properties a
window manager would give a game's window (`WM_CLASS`, `_NET_WM_NAME`) and
the root window's `_NET_CLIENT_LIST`, made over a connection of their own.
Shared by test_gamewindow.py and game_window_probe.py."""

import ctypes
import ctypes.util

XA_STRING = 31
XA_WINDOW = 33
PROP_MODE_REPLACE = 0


class XClient:
    """Creates, moves and destroys top-level windows on $DISPLAY and keeps
    the root's client list in step, as a window manager does."""

    def __init__(self):
        self.xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xlib = self.xlib

        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XDefaultScreen.argtypes = [ctypes.c_void_p]
        xlib.XRootWindow.restype = ctypes.c_ulong
        xlib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XInternAtom.restype = ctypes.c_ulong
        xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        xlib.XCreateSimpleWindow.restype = ctypes.c_ulong
        xlib.XCreateSimpleWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_ulong
        ]
        xlib.XChangeProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int,
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int
        ]
        xlib.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XMoveResizeWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ctypes.c_uint
        ]
        xlib.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

        self.display = xlib.XOpenDisplay(None)
        self.root = xlib.XRootWindow(self.display, xlib.XDefaultScreen(self.display))
        self.windows = []

    def atom(self, name):
        return self.xlib.XInternAtom(self.display, name.encode(), 0)

    def set_text(self, window, name, kind, text):
        data = text.encode()
        self.xlib.XChangeProperty(
            self.display, window, self.atom(name), kind, 8, PROP_MODE_REPLACE, data, len(data)
        )

    def publish_clients(self):
        """Write the root's `_NET_CLIENT_LIST` and make the server process it."""
        array = (ctypes.c_ulong * len(self.windows))(*self.windows)
        self.xlib.XChangeProperty(
            self.display, self.root, self.atom("_NET_CLIENT_LIST"), XA_WINDOW, 32,
            PROP_MODE_REPLACE, ctypes.cast(array, ctypes.c_char_p), len(self.windows)
        )
        self.xlib.XSync(self.display, 0)

    def create(self, x, y, width, height, wm_class="", title=""):
        """A mapped window at (x, y), listed as a client; its id."""
        window = self.xlib.XCreateSimpleWindow(self.display, self.root, x, y, width, height, 0, 0, 0)

        if wm_class:
            self.set_text(window, "WM_CLASS", XA_STRING, f"{wm_class}\0{wm_class}\0")

        if title:
            self.set_text(window, "_NET_WM_NAME", self.atom("UTF8_STRING"), title)

        self.xlib.XMapWindow(self.display, window)
        self.windows.append(window)
        self.publish_clients()

        return window

    def move_resize(self, window, x, y, width, height):
        self.xlib.XMoveResizeWindow(self.display, window, x, y, width, height)
        self.xlib.XSync(self.display, 0)

    def destroy(self, window):
        """Close the window the way a game exiting does; the client list is
        updated only afterwards (`forget`), as a window manager notices it
        later."""
        self.xlib.XDestroyWindow(self.display, window)
        self.xlib.XSync(self.display, 0)

    def forget(self, window):
        """Take `window` off the root's client list."""
        self.windows.remove(window)
        self.publish_clients()

    def close(self):
        self.xlib.XCloseDisplay(self.display)
