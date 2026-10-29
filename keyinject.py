"""Synthetic key presses for the auto-hold (the app holds S itself).

AGS-17: S is held for the time left to the target. Mortars (auto-lay): W is
held first until the barrel is at its top, then S for the whole hold time,
since the app cannot know where the barrel was left.

`system_key_injector(vk)` returns an injector with press()/release()/close()
for one key, or None where keys cannot be sent:

* Windows: SendInput with the scan code of the current layout, so games
  that read the keyboard directly see it (and it works on any layout).
* Linux, uinput: a virtual keyboard in /dev/uinput, seen by every program
  under X11 and Wayland. Needs write access to /dev/uinput (Steam's udev
  rules usually grant it to the logged-in user).
* Linux, XTest: a fake key event on $DISPLAY, for a game running on X11 or
  XWayland (Squad under Proton).

Synthetic input may be treated as a macro by EasyAntiCheat or by server
rules; the feature is off unless the user enables it.
"""

import ctypes
import ctypes.util
import fcntl
import os
import struct
import sys
import threading
import time

from keystate import EV_KEY, EVDEV_CODES

# The last milliseconds of a hold are waited for actively: sleeping is
# coarse on Windows.
PRECISE_SPIN_SECONDS = 0.003

# Pause between releasing W and pressing S, so the game sees two separate
# keys (at least a few frames at 30 fps).
RESET_SETTLE_SECONDS = 0.1

UINPUT_NAME = b"Squad Ballistics auto-hold"

_UI_SET_EVBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 100
_UI_SET_KEYBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 101
_UI_DEV_CREATE = (ord("U") << 8) | 1
_UI_DEV_DESTROY = (ord("U") << 8) | 2


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):
    # Only for the size of the union: SendInput checks sizeof(INPUT).
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyboardInput), ("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("union", _InputUnion)]


class WindowsInjector:
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0

    def __init__(self, vk):
        self.user32 = ctypes.windll.user32
        self.scan_code = self.user32.MapVirtualKeyW(vk, self.MAPVK_VK_TO_VSC)

    def _send(self, flags):
        event = _Input(
            self.INPUT_KEYBOARD,
            _InputUnion(ki=_KeyboardInput(
                0, self.scan_code, self.KEYEVENTF_SCANCODE | flags, 0, 0
            ))
        )
        self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))

    def press(self):
        self._send(0)

    def release(self):
        self._send(self.KEYEVENTF_KEYUP)

    def close(self):
        pass


class UinputInjector:
    """A virtual keyboard with one key."""

    def __init__(self, vk, path="/dev/uinput"):
        self.code = EVDEV_CODES[vk]
        self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)

        try:
            fcntl.ioctl(self.fd, _UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, _UI_SET_KEYBIT, self.code)

            # struct uinput_user_dev: name, input_id (BUS_VIRTUAL),
            # ff_effects_max, absmax/absmin/absfuzz/absflat[64].
            os.write(
                self.fd,
                UINPUT_NAME.ljust(80, b"\0")
                + struct.pack("HHHHI", 0x06, 0x5342, 0x0001, 1, 0)
                + bytes(4 * 64 * 4)
            )

            fcntl.ioctl(self.fd, _UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise

    def _key(self, value):
        # struct input_event: timeval, type, code, value; then SYN_REPORT.
        os.write(self.fd, struct.pack("llHHi", 0, 0, EV_KEY, self.code, value))
        os.write(self.fd, struct.pack("llHHi", 0, 0, 0, 0, 0))

    def press(self):
        self._key(1)

    def release(self):
        self._key(0)

    def close(self):
        if self.fd is None:
            return

        try:
            fcntl.ioctl(self.fd, _UI_DEV_DESTROY)
        except OSError:
            pass

        os.close(self.fd)

        self.fd = None


class XTestInjector:
    def __init__(self, vk):
        xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xtst = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")

        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xtst.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]

        self.display = xlib.XOpenDisplay(None)

        if not self.display:
            raise OSError("cannot open the X display")

        self.xlib = xlib
        self.xtst = xtst
        self.keycode = EVDEV_CODES[vk] + 8

    def _key(self, down):
        self.xtst.XTestFakeKeyEvent(self.display, self.keycode, int(down), 0)
        # XSync, not XFlush: return once the server has applied the event,
        # so the hold is timed from the real press.
        self.xlib.XSync(self.display, 0)

    def press(self):
        self._key(True)

    def release(self):
        self._key(False)

    def close(self):
        pass


def system_key_injector(vk):
    """The best injector for this system, None if keys cannot be sent."""
    if sys.platform == "win32":
        return WindowsInjector(vk)

    if not sys.platform.startswith("linux"):
        return None

    if os.access("/dev/uinput", os.W_OK):
        try:
            return UinputInjector(vk)
        except OSError:
            pass

    if os.environ.get("DISPLAY"):
        try:
            return XTestInjector(vk)
        except OSError:
            pass

    return None


def hold_key(injector, seconds, cancel):
    """Hold the key for exactly `seconds` (or until `cancel` is set).

    Runs in a worker thread; the key is always released.
    """
    injector.press()

    try:
        deadline = time.perf_counter() + seconds

        while not cancel.is_set():
            remaining = deadline - time.perf_counter()

            if remaining <= 0:
                return

            if remaining > PRECISE_SPIN_SECONDS \
                    and cancel.wait(remaining - PRECISE_SPIN_SECONDS):
                return
    finally:
        injector.release()


def lay(injector, seconds, cancel, reset_injector=None, reset_seconds=0.0,
        resetting=None, pressing=None):
    """Hold the reset key (W) `reset_seconds` first, if any, then the key.

    Runs in a worker thread; `cancel` stops it at any point with both keys
    released. `resetting` and `pressing` (threading.Event) are set while W,
    and then the key, are held: the hold timer counts the key from them and
    tells this W from one the player presses.
    """
    if reset_injector is not None and reset_seconds > 0:
        if resetting is not None:
            resetting.set()

        try:
            hold_key(reset_injector, reset_seconds, cancel)
        finally:
            if resetting is not None:
                resetting.clear()

        if cancel.wait(RESET_SETTLE_SECONDS):
            return

    if pressing is not None:
        pressing.set()

    try:
        hold_key(injector, seconds, cancel)
    finally:
        if pressing is not None:
            pressing.clear()


class AutoHold:
    """Holds the key in a worker thread; one hold at a time.

    `reset_injector` (optional) sends W, for holds that start by putting the
    barrel back to its top (`start(..., reset_seconds)`).
    """

    def __init__(self, injector, reset_injector=None):
        self.injector = injector
        self.reset_injector = reset_injector
        self.cancel = threading.Event()
        self.thread = None
        # Set while the app itself holds W (the reset before the hold), then
        # while it holds the key.
        self.resetting = threading.Event()
        self.pressing = threading.Event()

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, seconds, reset_seconds=0.0):
        """Hold the key `seconds`, after W for `reset_seconds` if > 0.

        Returns False if a hold is running, the time is not positive, or a
        reset is asked for without a W injector.
        """
        if self.active or seconds <= 0:
            return False

        if reset_seconds > 0 and self.reset_injector is None:
            return False

        self.cancel = threading.Event()
        self.thread = threading.Thread(
            target=lay,
            args=(self.injector, seconds, self.cancel, self.reset_injector, reset_seconds,
                  self.resetting, self.pressing),
            daemon=True
        )
        self.thread.start()

        return True

    def stop(self, wait=0.5):
        """Cancel the hold and wait for the release (the key never sticks)."""
        if self.thread is None:
            return

        self.cancel.set()
        self.thread.join(wait)
