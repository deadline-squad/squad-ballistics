"""Key readers against real devices: a uinput keyboard and an Xvfb server.

Both integration tests skip where the system does not allow them (no
writable /dev/uinput, no Xvfb/xdotool).
"""

import ctypes
import glob
import os
import shutil
import struct
import subprocess
import time

import pytest

import keystate
from hotkeys import KEYS
from keystate import EVIOCGBIT_KEY, EVIOCGKEY, EVIOCGNAME, KEY_MAX, KEY_S, KEY_W

KEY_F8 = KEYS["F8"]


def test_ioctl_numbers_match_linux_input_h():
    # _IOR('E', 0x18, char[96]), _IOR('E', 0x20 + EV_KEY, char[96]) and
    # EVIOCGNAME(256) = _IOC(_IOC_READ, 'E', 0x06, 256)
    assert EVIOCGKEY == 0x80604518
    assert EVIOCGBIT_KEY == 0x80604521
    assert EVIOCGNAME == 0x81004506


def test_key_codes_match_linux_input_event_codes_h():
    assert (KEY_S, KEY_W, KEY_F8) == (31, 17, 66)
    assert (keystate.KEY_A, keystate.KEY_D) == (30, 32)
    assert (KEYS["F1"], KEYS["F10"], KEYS["F11"], KEYS["F12"]) == (59, 68, 87, 88)
    assert len(set(KEYS.values())) == len(KEYS)
    assert all(0 < code <= KEY_MAX for code in KEYS.values())


def test_no_devices_means_no_reader(tmp_path):
    plain = tmp_path / "event0"
    plain.write_bytes(b"")

    assert keystate.evdev_reader([str(plain), str(tmp_path / "missing")]) is None


def test_x11_reader_needs_a_display(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)

    assert keystate.x11_reader() is None


# ---------- evdev through a virtual uinput keyboard ----------

UI_SET_EVBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 100
UI_SET_KEYBIT = (1 << 30) | (4 << 16) | (ord("U") << 8) | 101
UI_DEV_CREATE = (ord("U") << 8) | 1
UI_DEV_DESTROY = (ord("U") << 8) | 2

DEVICE_NAME = b"squad-ballistics-test-keyboard"


def _emit(fd, event_type, code, value):
    os.write(fd, struct.pack("llHHi", 0, 0, event_type, code, value))


def _key(fd, code, down):
    _emit(fd, keystate.EV_KEY, code, 1 if down else 0)
    _emit(fd, 0, 0, 0)  # EV_SYN / SYN_REPORT


@pytest.fixture
def uinput_keyboard():
    if not os.access("/dev/uinput", os.W_OK):
        pytest.skip("/dev/uinput is not writable")

    fcntl = pytest.importorskip("fcntl")
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)

    try:
        fcntl.ioctl(fd, UI_SET_EVBIT, keystate.EV_KEY)

        for code in (KEY_S, KEY_W, *KEYS.values()):
            fcntl.ioctl(fd, UI_SET_KEYBIT, code)

        setup = DEVICE_NAME.ljust(80, b"\0") + struct.pack(
            "HHHHI", 0x06, 0x1234, 0x5678, 1, 0
        ) + bytes(4 * 64 * 4)
        os.write(fd, setup)

        fcntl.ioctl(fd, UI_DEV_CREATE)

        path = None
        deadline = time.monotonic() + 5

        while path is None and time.monotonic() < deadline:
            for name_file in glob.glob("/sys/class/input/event*/device/name"):
                with open(name_file, "rb") as f:
                    if f.read().strip() == DEVICE_NAME:
                        node = "/dev/input/" + name_file.split("/")[4]
                        if os.access(node, os.R_OK):
                            path = node
            time.sleep(0.05)

        if path is None:
            pytest.skip("the virtual keyboard did not appear in /dev/input")

        yield fd, path
    finally:
        try:
            fcntl.ioctl(fd, UI_DEV_DESTROY)
        finally:
            os.close(fd)


def test_evdev_reader_sees_a_real_keyboard(uinput_keyboard):
    fd, path = uinput_keyboard

    reader = keystate.evdev_reader([path])

    assert reader is not None
    assert not reader(KEY_S)

    _key(fd, KEY_S, True)
    time.sleep(0.05)
    assert reader(KEY_S)
    assert not reader(KEY_W)

    _key(fd, KEY_F8, True)
    time.sleep(0.05)
    assert reader(KEY_F8)

    _key(fd, KEY_S, False)
    _key(fd, KEY_F8, False)
    time.sleep(0.05)
    assert not reader(KEY_S)
    assert not reader(KEY_F8)
    assert not reader(0x41)  # a key without a Linux mapping


# ---------- X11 through Xvfb ----------

@pytest.fixture
def xvfb(monkeypatch):
    if not (shutil.which("Xvfb") and shutil.which("xdotool")):
        pytest.skip("Xvfb and xdotool are not installed")

    display = ":97"
    server = subprocess.Popen(
        ["Xvfb", display, "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        deadline = time.monotonic() + 10
        while not os.path.exists("/tmp/.X11-unix/X97"):
            if time.monotonic() > deadline or server.poll() is not None:
                pytest.skip("Xvfb did not start")
            time.sleep(0.05)

        monkeypatch.setenv("DISPLAY", display)
        yield display
    finally:
        server.terminate()
        server.wait(5)


def xdotool(*args):
    subprocess.run(["xdotool", *args], check=True)


def test_x11_reader_sees_keys_on_the_display(xvfb):
    reader = keystate.x11_reader()

    assert reader is not None
    assert not reader(KEY_S)

    xdotool("keydown", "s")
    assert reader(KEY_S)
    assert not reader(KEY_W)

    xdotool("keydown", "F8")
    assert reader(KEY_F8)

    xdotool("keyup", "s", "keyup", "F8")
    assert not reader(KEY_S)
    assert not reader(KEY_F8)


def test_prefers_evdev_then_x11(monkeypatch):
    monkeypatch.setattr(keystate, "evdev_reader", lambda: "evdev")
    monkeypatch.setattr(keystate, "x11_reader", lambda: "x11")
    assert keystate.system_key_reader() == "evdev"

    monkeypatch.setattr(keystate, "evdev_reader", lambda: None)
    assert keystate.system_key_reader() == "x11"

    monkeypatch.setattr(keystate, "x11_reader", lambda: None)
    assert keystate.system_key_reader() is None


def test_ctypes_char_buffer_bit_order():
    buffer = (ctypes.c_char * 32)()
    buffer[39 // 8] = bytes([1 << (39 % 8)])

    assert keystate._bit(buffer.raw, 39)
    assert not keystate._bit(buffer.raw, 38)


# ---------- evdev hotplug (#3 item 24), on fake devices ----------

class FakeStat:
    """The one field of os.stat_result keystate reads."""

    def __init__(self, rdev):
        self.st_rdev = rdev


class FakeInput:
    """/dev/input stand-in: os.open, os.close, os.stat, os.fstat and
    fcntl.ioctl of keystate over devices that can be plugged in and out.
    Other paths and fds go to the real functions."""

    def __init__(self, monkeypatch):
        # path -> {"keys": capabilities, "down": set, "gone": bool,
        #          "name": bytes, "rdev": device number}
        self.devices = {}
        self.fds = {}      # fd -> (path, device)
        self.opened = 0
        self.opened_paths = []
        self.next_fd = 100
        self.next_rdev = 0x0D40
        self.now = 0.0

        real_stat, real_fstat = os.stat, os.fstat

        def stat(path, *args, **kwargs):
            if path in self.devices:
                return FakeStat(self.devices[path]["rdev"])
            if isinstance(path, str) and path.startswith("/dev/input/"):
                raise FileNotFoundError(path)
            return real_stat(path, *args, **kwargs)

        def fstat(fd):
            if fd in self.fds:
                return FakeStat(self.fds[fd][1]["rdev"])
            return real_fstat(fd)

        monkeypatch.setattr(keystate.os, "open", self.open)
        monkeypatch.setattr(keystate.os, "close", self.close)
        monkeypatch.setattr(keystate.os, "stat", stat)
        monkeypatch.setattr(keystate.os, "fstat", fstat)
        monkeypatch.setattr(keystate.fcntl, "ioctl", self.ioctl)

    def plug(self, path, keyboard=True, name=b"AT Translated Set 2 keyboard"):
        """A new device on `path` (a new device number, like the kernel
        gives a reconnected device)."""
        keys = {KEY_S, KEY_W, KEY_F8} if keyboard else {KEY_F8}
        self.next_rdev += 1
        self.devices[path] = {"keys": keys, "down": set(), "gone": False,
                              "name": name, "rdev": self.next_rdev}

    def unplug(self, path):
        # The node goes away; an fd still open on it answers ENODEV
        self.devices.pop(path)["gone"] = True

    def paths(self):
        return sorted(self.devices)

    def clock(self):
        return self.now

    def open(self, path, flags):
        if path not in self.devices:
            raise FileNotFoundError(path)

        self.opened += 1
        self.opened_paths.append(path)
        self.next_fd += 1
        self.fds[self.next_fd] = (path, self.devices[path])
        return self.next_fd

    def close(self, fd):
        self.fds.pop(fd)

    def ioctl(self, fd, request, buffer):
        _path, device = self.fds[fd]

        if device["gone"]:
            raise OSError(19, "No such device")

        if request == EVIOCGNAME:
            buffer[:len(device["name"]) + 1] = device["name"] + b"\0"
            return

        bits = device["keys"] if request == EVIOCGBIT_KEY else device["down"]

        for code in bits:
            buffer[code // 8] |= 1 << (code % 8)


@pytest.fixture
def fake_input(monkeypatch):
    return FakeInput(monkeypatch)


def make_reader(fake_input):
    return keystate.EvdevReader(fake_input.paths, fake_input.clock)


def test_a_keyboard_plugged_in_later_is_read(fake_input):
    fake_input.plug("/dev/input/event0", keyboard=False)
    reader = make_reader(fake_input)
    assert not reader.available

    fake_input.plug("/dev/input/event5")
    fake_input.devices["/dev/input/event5"]["down"].add(KEY_S)

    # Not before the next scan, then without a restart
    fake_input.now += keystate.RESCAN_SECONDS / 2
    assert not reader(KEY_S)

    fake_input.now += keystate.RESCAN_SECONDS
    assert reader(KEY_S)
    assert reader.available


def test_an_unplugged_keyboard_is_dropped_and_its_return_is_read(fake_input):
    fake_input.plug("/dev/input/event3")
    reader = make_reader(fake_input)
    assert reader.available

    fake_input.unplug("/dev/input/event3")
    assert not reader(KEY_S)
    assert not reader.available, "available says the keyboard is gone"
    assert fake_input.fds == {}, "the dead fd is closed"

    # Reconnected (a new node): found soon, well before the periodic scan
    fake_input.plug("/dev/input/event7")
    fake_input.devices["/dev/input/event7"]["down"].add(KEY_W)
    fake_input.now += keystate.FAILURE_RESCAN_SECONDS
    assert reader(KEY_W)
    assert reader.available


def test_keys_are_read_on_any_of_several_keyboards(fake_input):
    fake_input.plug("/dev/input/event1")
    fake_input.plug("/dev/input/event2")
    reader = make_reader(fake_input)

    fake_input.devices["/dev/input/event2"]["down"].add(KEY_F8)

    assert reader(KEY_F8)
    assert not reader(KEY_S)

    # One of them unplugged: the other still works
    fake_input.unplug("/dev/input/event1")
    assert reader(KEY_F8)
    assert reader.available


def test_scans_do_not_reopen_known_devices(fake_input):
    fake_input.plug("/dev/input/event1")
    reader = make_reader(fake_input)
    opened = fake_input.opened

    for _ in range(5):
        fake_input.now += keystate.RESCAN_SECONDS
        reader(KEY_S)

    assert fake_input.opened == opened
    assert len(fake_input.fds) == 1


def test_evdev_reader_needs_a_keyboard_at_the_start(fake_input):
    fake_input.plug("/dev/input/event0", keyboard=False)
    assert keystate.evdev_reader(["/dev/input/event0"]) is None

    fake_input.plug("/dev/input/event1")
    reader = keystate.evdev_reader(["/dev/input/event0", "/dev/input/event1"])
    assert isinstance(reader, keystate.EvdevReader) and reader.available


def test_devices_that_are_not_keyboards_are_not_reopened_at_every_scan(fake_input):
    """A mouse or a power button is opened once, not every RESCAN_SECONDS
    (#5, review 1.6.0 slice 5 claim 7)."""
    fake_input.plug("/dev/input/event0", keyboard=False)
    fake_input.plug("/dev/input/event1")
    reader = make_reader(fake_input)

    for _ in range(5):
        fake_input.now += keystate.RESCAN_SECONDS
        reader(KEY_S)

    assert fake_input.opened_paths.count("/dev/input/event0") == 1
    assert list(fake_input.fds.values())[0][0] == "/dev/input/event1"


def test_a_new_device_on_a_rejected_path_is_looked_at(fake_input):
    """The node of a device that was not a keyboard is reused by a keyboard
    plugged in later: a new device number, so it is opened again."""
    fake_input.plug("/dev/input/event4", keyboard=False)
    reader = make_reader(fake_input)
    assert not reader.available

    fake_input.devices.pop("/dev/input/event4")
    fake_input.plug("/dev/input/event4")
    fake_input.devices["/dev/input/event4"]["down"].add(KEY_S)
    fake_input.now += keystate.RESCAN_SECONDS

    assert reader(KEY_S)
    assert reader.available


def test_a_rejected_path_that_vanished_is_forgotten(fake_input):
    fake_input.plug("/dev/input/event4", keyboard=False)
    reader = make_reader(fake_input)
    assert "/dev/input/event4" in reader.rejected

    fake_input.devices.pop("/dev/input/event4")
    fake_input.now += keystate.RESCAN_SECONDS
    reader(KEY_S)

    assert reader.rejected == {}


def test_the_apps_own_virtual_keyboards_are_not_read(fake_input):
    """keyinject's uinput devices report KEY_ESC..KEY_S, so they look like
    keyboards; their keys are the app's own auto-hold, not the player's
    (#5, review 1.6.0 slice 5 claim 8)."""
    fake_input.plug("/dev/input/event9", name=keystate.UINPUT_NAME)
    fake_input.devices["/dev/input/event9"]["down"].add(KEY_S)
    fake_input.plug("/dev/input/event1")

    reader = make_reader(fake_input)

    assert not reader(KEY_S)
    assert list(reader.keyboards) == ["/dev/input/event1"]

    # Not looked at again either.
    fake_input.now += keystate.RESCAN_SECONDS
    reader(KEY_S)
    assert fake_input.opened_paths.count("/dev/input/event9") == 1


def test_a_keyboard_whose_node_vanished_is_no_longer_read(fake_input):
    """The device list is the truth: a node gone from it is dropped at the
    next scan even if its old fd still answers (#5, review 1.6.0 slice 5
    claim 10: the drop of vanished paths was not tested)."""
    fake_input.plug("/dev/input/event3")
    fake_input.devices["/dev/input/event3"]["down"].add(KEY_S)
    reader = make_reader(fake_input)
    assert reader(KEY_S)

    # The node is removed from /dev/input; the open fd still answers.
    device = fake_input.devices.pop("/dev/input/event3")
    fake_input.now += keystate.RESCAN_SECONDS

    assert not reader(KEY_S)
    assert not reader.available
    assert fake_input.fds == {}
    assert not device["gone"]
