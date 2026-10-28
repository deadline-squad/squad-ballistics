"""Physical key state, read system-wide (the game has the focus, not us).

Keys are named by their Windows virtual-key codes (VK_*), which the rest of
the app already uses. `system_key_reader()` returns `reader(vk) -> bool`
for the current system, or None when keys cannot be read:

* Windows: GetAsyncKeyState. A game run as administrator is only visible
  to an app run as administrator too.
* Linux, evdev: the keyboards in /dev/input are queried with EVIOCGKEY.
  Works under X11 and Wayland alike, but the user must be allowed to read
  the devices (member of the `input` group).
* Linux, X11: XQueryKeymap on $DISPLAY. Works on an X11 session, and on
  Wayland while an XWayland window has the focus — Squad under Proton is
  one.

Only plain ctypes/fcntl are used, nothing to install.
"""

import ctypes
import ctypes.util
import fcntl
import glob
import os
import sys

# Windows virtual-key code -> Linux input event code (linux/input-event-codes.h).
# X11 keycodes on Linux are the evdev codes + 8.
EVDEV_CODES = {
    0x53: 31,   # S
    0x57: 17,   # W
    **{0x70 + i: 59 + i for i in range(10)},  # F1..F10
    0x7A: 87,   # F11
    0x7B: 88,   # F12
    0x2D: 110,  # Insert
    0x24: 102,  # Home
    0x23: 107,  # End
    0x21: 104,  # Page Up
    0x22: 109,  # Page Down
    0x13: 119,  # Pause
    0x91: 70,   # Scroll Lock
}

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


def windows_reader():
    user32 = ctypes.windll.user32

    return lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)


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

        if _bit(capabilities, EVDEV_CODES[0x53]) \
                and _bit(capabilities, EVDEV_CODES[0x57]):
            keyboards.append(fd)
        else:
            os.close(fd)

    if not keyboards:
        return None

    state = bytearray(KEY_BYTES)

    def reader(vk):
        code = EVDEV_CODES.get(vk)

        if code is None:
            return False

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

    def reader(vk):
        code = EVDEV_CODES.get(vk)

        if code is None:
            return False

        xlib.XQueryKeymap(display, keymap)

        return _bit(keymap.raw, code + 8)

    return reader


def system_key_reader():
    """The best reader for this system, None if keys cannot be read."""
    if sys.platform == "win32":
        return windows_reader()

    if sys.platform.startswith("linux"):
        return evdev_reader() or x11_reader()

    return None
