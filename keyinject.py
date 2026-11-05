"""Synthetic key presses for the auto-hold (the app holds S itself).

AGS-17: S is held for the time left to the target. Mortars (auto-lay): W is
held first until the barrel is at its top, then S for the whole hold time,
since the app cannot know where the barrel was left.

`system_key_injector(code)` returns an injector with press()/release()/close()
for one key (a Linux input event code, see keystate), or None where keys
cannot be sent:

* uinput: a virtual keyboard in /dev/uinput, seen by every program under
  X11 and Wayland. Needs write access to /dev/uinput (Steam's udev rules
  usually grant it to the logged-in user).
* XTest: a fake key event on $DISPLAY, for a game running on X11 or
  XWayland (Squad under Proton).

Every injector remembers whether its key is down and sends the key-up in
`close()`. A key cannot be released after the process is killed (SIGKILL)
or crashes: a uinput key goes up with its device, but an XTest key stays
down on the X server until the key is pressed and released again.

An injector is used by one worker thread (`AutoHold`) and closed from the
GUI thread: `press`, `release` and `close` are serialized by a lock, and
after `close` the key calls do nothing.

Synthetic input may be treated as a macro by EasyAntiCheat or by server
rules; the feature is off unless the user enables it.
"""

import ctypes
import ctypes.util
import fcntl
import os
import struct
import threading
import time

from keystate import EV_KEY, UINPUT_NAME, X11_KEYCODE_OFFSET

# The last milliseconds of a hold are waited for actively: a sleep may wake
# up late.
PRECISE_SPIN_SECONDS = 0.003

# Pause between releasing W and pressing S, so the game sees two separate
# keys (at least a few frames at 30 fps).
RESET_SETTLE_SECONDS = 0.1

_UI_SET_EVBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 100
_UI_SET_KEYBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 101
_UI_DEV_CREATE = (ord("U") << 8) | 1
_UI_DEV_DESTROY = (ord("U") << 8) | 2


# The keys udev needs on a device before it tags it as a keyboard, which the
# compositor and the game's input stack then use: KEY_ESC .. KEY_S, codes
# 1-31, the first 32 bits of the key bitmap without KEY_RESERVED (systemd,
# src/udev/udev-builtin-input_id.c, test_key). The injector still sends only
# its own key; UINPUT_NAME keeps keystate from reading the device.
_KEYBOARD_PROBE_KEYS = range(1, 32)


class UinputInjector:
    """A virtual keyboard that sends one key (Linux input event `code`).

    Raises OSError when `path` cannot be opened or the device not created.
    """

    def __init__(self, code, path="/dev/uinput"):
        self.code = code
        self.lock = threading.Lock()
        self.down = False
        self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)

        try:
            fcntl.ioctl(self.fd, _UI_SET_EVBIT, EV_KEY)

            for key in (*_KEYBOARD_PROBE_KEYS, self.code):
                fcntl.ioctl(self.fd, _UI_SET_KEYBIT, key)

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

    def _send(self, value):
        # struct input_event: timeval, type, code, value; then SYN_REPORT.
        # The caller holds the lock.
        os.write(self.fd, struct.pack("llHHi", 0, 0, EV_KEY, self.code, value))
        os.write(self.fd, struct.pack("llHHi", 0, 0, 0, 0, 0))

        self.down = bool(value)

    def _key(self, value):
        with self.lock:
            if self.fd is None:
                return

            self._send(value)

    def press(self):
        """Key down; nothing once closed. Raises OSError if the write fails."""
        self._key(1)

    def release(self):
        """Key up; nothing once closed. Raises OSError if the write fails."""
        self._key(0)

    def close(self):
        """Release the key if it is down, then destroy the device (once;
        later calls do nothing). Waits for a press or release in progress."""
        with self.lock:
            if self.fd is None:
                return

            if self.down:
                try:
                    self._send(0)
                except OSError:
                    pass

            try:
                fcntl.ioctl(self.fd, _UI_DEV_DESTROY)
            except OSError:
                pass

            os.close(self.fd)

            self.fd = None


class XTestInjector:
    """Fake key events on $DISPLAY for one key (Linux input event `code`).

    Raises OSError when the X display cannot be opened. libX11 and libXtst
    must be installed (ctypes raises OSError otherwise).
    """

    def __init__(self, code):
        xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xtst = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")

        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]

        self.display = xlib.XOpenDisplay(None)

        if not self.display:
            raise OSError("cannot open the X display")

        self.xlib = xlib
        self.xtst = xtst
        self.keycode = code + X11_KEYCODE_OFFSET
        self.lock = threading.Lock()
        self.down = False

    def _send(self, down):
        # The caller holds the lock and the display is open: Xlib must never
        # be called with a closed (NULL) display, it crashes the process.
        self.xtst.XTestFakeKeyEvent(self.display, self.keycode, int(down), 0)
        # XSync, not XFlush: return once the server has applied the event,
        # so the hold is timed from the real press.
        self.xlib.XSync(self.display, 0)

        self.down = down

    def _key(self, down):
        with self.lock:
            if self.display is None:
                return

            self._send(down)

    def press(self):
        """Key down on the X server; nothing once closed."""
        self._key(True)

    def release(self):
        """Key up on the X server; nothing once closed."""
        self._key(False)

    def close(self):
        """Release the key if it is down, then close the connection to the
        X server (once; later calls do nothing). The X server does not
        release an XTest key when its client goes away, so this key-up is
        the only one. Waits for a press or release in progress."""
        with self.lock:
            if self.display is None:
                return

            if self.down:
                self._send(False)

            self.xlib.XCloseDisplay(self.display)

            self.display = None


def system_key_injector(code):
    """uinput, else XTest; None if keys cannot be sent."""
    if os.access("/dev/uinput", os.W_OK):
        try:
            return UinputInjector(code)
        except OSError:
            pass

    if os.environ.get("DISPLAY"):
        try:
            return XTestInjector(code)
        except OSError:
            pass

    return None


def hold_key(injector, seconds, cancel):
    """Hold the key for exactly `seconds` (or until `cancel` is set).

    Runs in a worker thread; the key is always released, also when the
    press itself fails halfway (the error is raised after the release).
    """
    try:
        injector.press()

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
        """Whether a hold (or its reset) is running in the worker thread."""
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

    def stop(self, wait=None):
        """Cancel the hold and wait for the worker to release the key and end.

        Cancelling wakes the worker at once; it is then only as slow as its
        last key call (an X server that does not answer holds it up). By
        default this waits until the worker is done, so the injectors can
        be closed right after: a worker still running would use them
        closed. `wait` (seconds) bounds the wait; then check `active`.
        """
        if self.thread is None:
            return

        self.cancel.set()
        self.thread.join(wait)
