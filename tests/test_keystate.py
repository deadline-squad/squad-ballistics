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
from keystate import EVIOCGBIT_KEY, EVIOCGKEY, KEY_MAX, KEY_S, KEY_W

KEY_F8 = KEYS["F8"]


def test_ioctl_numbers_match_linux_input_h():
    # _IOR('E', 0x18, char[96]) and _IOR('E', 0x20 + EV_KEY, char[96])
    assert EVIOCGKEY == 0x80604518
    assert EVIOCGBIT_KEY == 0x80604521


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
