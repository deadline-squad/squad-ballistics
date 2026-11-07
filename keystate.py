"""Physical key and mouse button state, read system-wide (the game has the
focus, not us).

Keys are named by their Linux input event codes (KEY_* and BTN_* of
linux/input-event-codes.h); an X11 keycode is the code + 8. The mouse side
buttons are BTN_SIDE (X11 button 8, "Mouse4") and BTN_EXTRA (9, "Mouse5").
`system_key_reader()` returns `reader(code) -> bool`, or None when keys
cannot be read:

* evdev: the keyboards and the mice with side buttons in /dev/input are
  queried with EVIOCGKEY. Works under X11 and Wayland alike, but the user
  must be allowed to read the devices (member of the `input` group, which
  lets every program of the user read every keystroke). Devices plugged in
  or reconnected later are found (see EvdevReader). The app's own virtual
  keyboards (keyinject's uinput devices, named UINPUT_NAME) are not read:
  their keys are the app's, not the player's.
* X11: XQueryKeymap on $DISPLAY for keys, XInput2's XIQueryPointer for the
  mouse side buttons (the core pointer mask knows buttons 1-5 only). Works
  on an X11 session, and on Wayland while an XWayland window has the
  focus — Squad under Proton is one.

Nothing is grabbed or swallowed: the game still gets every key and button.

Only plain ctypes/fcntl are used, nothing to install.
"""

import ctypes
import ctypes.util
import fcntl
import glob
import os
import time

# Linux input event codes (linux/input-event-codes.h)
KEY_W = 17
KEY_A = 30
KEY_S = 31
KEY_D = 32
# The game's default Focus key (IA_Focus in Content/Input/IMC_Turret, IMC_GroundVehicle).
KEY_LEFTSHIFT = 42
BTN_SIDE = 0x113
BTN_EXTRA = 0x114

# The X11 button number of the mouse buttons the X11 reader can tell (XInput2).
X11_BUTTONS = {BTN_SIDE: 8, BTN_EXTRA: 9}

# X11 keycodes are the input event codes + 8
X11_KEYCODE_OFFSET = 8

EV_KEY = 0x01
KEY_MAX = 0x2FF
KEY_BYTES = KEY_MAX // 8 + 1

# Name of the virtual keyboards keyinject creates in /dev/uinput. EvdevReader
# skips devices with this name: what they send is the app's own auto-hold.
UINPUT_NAME = b"Squad Ballistics auto-hold"

# Bytes asked for the device name (uinput names are at most 80).
NAME_BYTES = 256

_IOC_READ = 2


def _ioc_read(nr, size):
    """_IOR('E', nr, size) of linux/input.h."""
    return (_IOC_READ << 30) | (size << 16) | (ord("E") << 8) | nr


EVIOCGKEY = _ioc_read(0x18, KEY_BYTES)
EVIOCGBIT_KEY = _ioc_read(0x20 + EV_KEY, KEY_BYTES)
EVIOCGNAME = _ioc_read(0x06, NAME_BYTES)


def _bit(buffer, code):
    """Whether bit `code` is set in the key bitmap `buffer` (bytes, LSB first)."""
    return bool(buffer[code // 8] & (1 << (code % 8)))


# Keyboards are looked for again this often (seconds), so one plugged in
# after the start (a KVM switch, a dock, a Bluetooth reconnect) is read too.
RESCAN_SECONDS = 3.0

# After a keyboard stops answering (ENODEV: unplugged) the devices are looked
# for again at the next read, but not more often than this (seconds): a
# device that keeps failing must not turn every poll into a scan.
FAILURE_RESCAN_SECONDS = 0.5


def _open_device(path):
    """A read-only fd on the event device at `path`, None if it cannot be
    opened (gone, or no permission: both may change, so they are tried again
    at every scan)."""
    try:
        return os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None


def _device_name(fd):
    """The device's name (EVIOCGNAME) as bytes, b"" if it has none."""
    name = bytearray(NAME_BYTES)

    try:
        fcntl.ioctl(fd, EVIOCGNAME, name)
    except OSError:
        return b""

    return bytes(name).split(b"\0", 1)[0]


def _is_player_input(fd):
    """Whether the device on `fd` is one to read: a keyboard (it reports
    KEY_S and KEY_W) or a mouse with side buttons (BTN_SIDE or BTN_EXTRA),
    and not one of the app's own uinput keyboards (which report KEY_S and
    KEY_W too, see keyinject)."""
    try:
        capabilities = bytearray(KEY_BYTES)
        fcntl.ioctl(fd, EVIOCGBIT_KEY, capabilities)
    except OSError:
        return False

    keyboard = _bit(capabilities, KEY_S) and _bit(capabilities, KEY_W)
    side_buttons = _bit(capabilities, BTN_SIDE) or _bit(capabilities, BTN_EXTRA)

    if not (keyboard or side_buttons):
        return False

    return _device_name(fd) != UINPUT_NAME


def _input_devices():
    """The event devices in /dev/input."""
    return sorted(glob.glob("/dev/input/event*"))


class EvdevReader:
    """Reads keys and mouse buttons off every keyboard and mouse in
    /dev/input: `reader(code) -> bool`.

    A key is down when it is down on any such device. The device list is not
    fixed at the start: it is scanned again every RESCAN_SECONDS, and soon
    after a device fails (unplugged: its fd answers ENODEV for good), so a
    keyboard or mouse plugged in or reconnected later is read without a
    restart. Reads happen on the caller's thread (the Qt pollers); nothing
    runs in the background.

    A device that opens but is not one to read (a mouse without side
    buttons, a power button, the app's own uinput keyboards) is remembered by its path and
    device number (st_rdev) and not opened again at the next scans; a new
    device on the same path has another number and is looked at again.

    `list_paths()` gives the device paths to look at; `clock()` the time in
    seconds (tests pass fakes).
    """

    def __init__(self, list_paths=_input_devices, clock=time.monotonic):
        self.list_paths = list_paths
        self.clock = clock
        self.devices = {}
        # path -> st_rdev of the devices that are not keyboards to read
        self.rejected = {}
        self.state = bytearray(KEY_BYTES)
        self.next_scan = 0.0

        self.scan()

    @property
    def available(self):
        """Whether a device can be read now (False while every keyboard
        and mouse is unplugged; True again once one is back)."""
        return bool(self.devices)

    def scan(self, interval=RESCAN_SECONDS):
        """Open the devices that appeared, close the ones that are gone;
        the next scan is due `interval` seconds from now."""
        self.next_scan = self.clock() + interval

        present = set(self.list_paths())

        for path in [p for p in self.devices if p not in present]:
            self.drop(path)

        for path in [p for p in self.rejected if p not in present]:
            del self.rejected[path]

        for path in sorted(present - set(self.devices)):
            self.probe(path)

    def probe(self, path):
        """Open the device at `path` and keep it if it is one to read;
        a device already rejected under the same device number is skipped."""
        try:
            device = os.stat(path).st_rdev
        except OSError:
            return

        if self.rejected.get(path) == device:
            return

        fd = _open_device(path)

        if fd is None:
            return

        if _is_player_input(fd):
            self.devices[path] = fd
            self.rejected.pop(path, None)
            return

        # The number of the device that was looked at, not of whatever the
        # path may have been replaced with since the stat above.
        try:
            self.rejected[path] = os.fstat(fd).st_rdev
        except OSError:
            pass

        os.close(fd)

    def drop(self, path):
        """Forget the device at `path` and close its fd."""
        fd = self.devices.pop(path)

        try:
            os.close(fd)
        except OSError:
            pass

    def __call__(self, code):
        """Whether key or button `code` is down on any device."""
        if self.clock() >= self.next_scan:
            self.scan()

        failed = False

        for path, fd in list(self.devices.items()):
            try:
                fcntl.ioctl(fd, EVIOCGKEY, self.state)
            except OSError:
                # Unplugged: the fd stays dead even if the device comes
                # back (it gets a new node), so it is closed and the devices
                # are looked for again.
                self.drop(path)
                failed = True
                continue

            if _bit(self.state, code):
                return True

        if failed:
            self.next_scan = min(self.next_scan, self.clock() + FAILURE_RESCAN_SECONDS)

        return False


def evdev_reader(paths=None):
    """EvdevReader over the keyboards and mice in /dev/input (or over
    `paths`), None if none can be read at the start (then X11 is tried
    instead)."""
    if paths is None:
        reader = EvdevReader()
    else:
        paths = list(paths)
        reader = EvdevReader(lambda: paths)

    return reader if reader.available else None


# XInput2 (https://www.x.org/releases/current/doc/inputproto/XI2proto.txt):
# the master pointer whose buttons are asked, and the protocol version
# agreed with the server before any XI2 request.
XI_VIRTUAL_CORE_POINTER = 2
XI_MAJOR, XI_MINOR = 2, 0


class XIButtonState(ctypes.Structure):
    """XIButtonState of XInput2.h: a bitmap of the buttons held, bit n =
    button n."""

    _fields_ = [("mask_len", ctypes.c_int), ("mask", ctypes.POINTER(ctypes.c_ubyte))]


class XIModifierState(ctypes.Structure):
    """XIModifierState (also XIGroupState) of XInput2.h."""

    _fields_ = [
        ("base", ctypes.c_int),
        ("latched", ctypes.c_int),
        ("locked", ctypes.c_int),
        ("effective", ctypes.c_int),
    ]


def x11_button_reader(xlib, display):
    """`reader(button) -> bool` over XIQueryPointer of the virtual core
    pointer: whether X11 button number `button` is down. None when libXi or
    XInput2 is missing (the keys of the X11 reader still work)."""
    try:
        xinput = ctypes.CDLL(ctypes.util.find_library("Xi") or "libXi.so.6")
    except OSError:
        return None

    xinput.XIQueryVersion.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
    ]
    xinput.XIQueryPointer.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(XIButtonState), ctypes.POINTER(XIModifierState),
        ctypes.POINTER(XIModifierState)
    ]
    xinput.XIQueryPointer.restype = ctypes.c_int
    xlib.XRootWindow.restype = ctypes.c_ulong
    xlib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    xlib.XDefaultScreen.argtypes = [ctypes.c_void_p]
    xlib.XFree.argtypes = [ctypes.c_void_p]

    major, minor = ctypes.c_int(XI_MAJOR), ctypes.c_int(XI_MINOR)

    if xinput.XIQueryVersion(display, ctypes.byref(major), ctypes.byref(minor)) != 0:
        return None

    root = xlib.XRootWindow(display, xlib.XDefaultScreen(display))

    def reader(button):
        """Whether X11 button `button` is down on the master pointer."""
        root_return, child_return = ctypes.c_ulong(), ctypes.c_ulong()
        positions = [ctypes.c_double() for _ in range(4)]
        buttons = XIButtonState()
        modifiers, group = XIModifierState(), XIModifierState()

        queried = xinput.XIQueryPointer(
            display, XI_VIRTUAL_CORE_POINTER, root,
            ctypes.byref(root_return), ctypes.byref(child_return),
            *(ctypes.byref(p) for p in positions),
            ctypes.byref(buttons), ctypes.byref(modifiers), ctypes.byref(group)
        )

        if not queried:
            return False

        try:
            return button // 8 < buttons.mask_len and bool(buttons.mask[button // 8] & (1 << (button % 8)))
        finally:
            xlib.XFree(buttons.mask)

    return reader


def x11_reader():
    """Reader over XQueryKeymap (keys) and XInput2 (the mouse side buttons
    of X11_BUTTONS) of $DISPLAY, None without X11. Without XInput2 the mouse
    buttons read as up."""
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
    buttons = x11_button_reader(xlib, display)

    def reader(code):
        """Whether key or mouse button `code` is down on the X server (any
        client's keys, XTest ones included)."""
        if code in X11_BUTTONS:
            return buttons is not None and buttons(X11_BUTTONS[code])

        xlib.XQueryKeymap(display, keymap)

        return _bit(keymap.raw, code + X11_KEYCODE_OFFSET)

    return reader


def system_key_reader():
    """evdev, else X11; None if keys cannot be read."""
    return evdev_reader() or x11_reader()
