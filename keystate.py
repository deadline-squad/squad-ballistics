"""Physical key state, read system-wide (the game has the focus, not us).

Keys are named by their Linux input event codes (KEY_* of
linux/input-event-codes.h); an X11 keycode is the code + 8.
`system_key_reader()` returns `reader(code) -> bool`, or None when keys
cannot be read:

* evdev: the keyboards in /dev/input are queried with EVIOCGKEY.
  Works under X11 and Wayland alike, but the user must be allowed to read
  the devices (member of the `input` group).
* X11: XQueryKeymap on $DISPLAY. Works on an X11 session, and on
  Wayland while an XWayland window has the focus — Squad under Proton is
  one.

Only plain ctypes/fcntl are used, nothing to install.
"""

import ctypes
import ctypes.util
import fcntl
import glob
import os

# Linux input event codes (linux/input-event-codes.h)
KEY_W = 17
KEY_S = 31

# X11 keycodes are the input event codes + 8
X11_KEYCODE_OFFSET = 8

EV_KEY = 0x01
KEY_MAX = 0x2FF
KEY_BYTES = KEY_MAX // 8 + 1

_IOC_READ = 2


def _ioc_read(nr, size):
    """_IOR('E', nr, size) of linux/input.h."""
    return (_IOC_READ << 30) | (size << 16) | (ord("E") << 8) | nr


EVIOCGKEY = _ioc_read(0x18, KEY_BYTES)
EVIOCGBIT_KEY = _ioc_read(0x20 + EV_KEY, KEY_BYTES)


def _bit(buffer, code):
    return bool(buffer[code // 8] & (1 << (code % 8)))


def evdev_reader(paths=None):
    """Reader over every readable keyboard in /dev/input, None if none.

    A device counts as a keyboard when it reports KEY_S and KEY_W. A key is
    down when it is down on any of them.
    """
    if paths is None:
        paths = sorted(glob.glob("/dev/input/event*"))

    keyboards = []

    for path in paths:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        except OSError:
            continue

        try:
            capabilities = bytearray(KEY_BYTES)
            fcntl.ioctl(fd, EVIOCGBIT_KEY, capabilities)
        except OSError:
            os.close(fd)
            continue

        if _bit(capabilities, KEY_S) and _bit(capabilities, KEY_W):
            keyboards.append(fd)
        else:
            os.close(fd)

    if not keyboards:
        return None

    state = bytearray(KEY_BYTES)

    def reader(code):
        for fd in keyboards:
            try:
                fcntl.ioctl(fd, EVIOCGKEY, state)
            except OSError:
                # Unplugged keyboard: its fd stays dead, the others work.
                continue

            if _bit(state, code):
                return True

        return False

    return reader


def x11_reader():
    """Reader over XQueryKeymap of $DISPLAY, None without X11."""
    if not os.environ.get("DISPLAY"):
        return None

    name = ctypes.util.find_library("X11") or "libX11.so.6"

    try:
        xlib = ctypes.CDLL(name)
    except OSError:
        return None

    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char * 32]

    display = xlib.XOpenDisplay(None)

    if not display:
        return None

    keymap = (ctypes.c_char * 32)()

    def reader(code):
        xlib.XQueryKeymap(display, keymap)

        return _bit(keymap.raw, code + X11_KEYCODE_OFFSET)

    return reader


def system_key_reader():
    """evdev, else X11; None if keys cannot be read."""
    return evdev_reader() or x11_reader()
