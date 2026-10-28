"""Key injection: timing logic and real delivery (Xvfb + XTest, uinput)."""

import ctypes
import glob
import os
import shutil
import subprocess
import threading
import time

import pytest

import keyinject
import keystate
from keyinject import AutoHold, hold_key

VK_S = 0x53


class FakeInjector:
    def __init__(self):
        self.events = []
        self.closed = False

    def press(self):
        self.events.append(("press", time.perf_counter()))

    def release(self):
        self.events.append(("release", time.perf_counter()))

    def close(self):
        self.closed = True


def test_input_struct_matches_windows_x64():
    # SendInput rejects a wrong cbSize: sizeof(INPUT) is 40 on 64-bit.
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(keyinject._Input) == 40


def test_hold_key_holds_for_the_requested_time():
    injector = FakeInjector()

    hold_key(injector, 0.25, threading.Event())

    (kind1, start), (kind2, end) = injector.events
    assert (kind1, kind2) == ("press", "release")
    assert end - start == pytest.approx(0.25, abs=0.01)


def test_cancel_releases_at_once():
    injector = FakeInjector()
    auto = AutoHold(injector)

    assert auto.start(5.0)
    assert auto.active
    assert not auto.start(1.0)  # one hold at a time

    time.sleep(0.05)
    auto.stop()

    assert not auto.active
    assert [kind for kind, _ in injector.events] == ["press", "release"]
    assert injector.events[1][1] - injector.events[0][1] < 0.5


def test_nothing_to_hold():
    auto = AutoHold(FakeInjector())

    assert not auto.start(0)
    assert not auto.start(-1)
    auto.stop()  # no thread: no-op


def test_no_injector_on_other_systems(monkeypatch):
    monkeypatch.setattr(keyinject.sys, "platform", "darwin")

    assert keyinject.system_key_injector(VK_S) is None


@pytest.fixture
def xvfb(monkeypatch):
    if not (shutil.which("Xvfb") and (
        os.path.exists("/usr/lib/x86_64-linux-gnu/libXtst.so.6")
        or glob.glob("/usr/lib*/libXtst.so.6")
    )):
        pytest.skip("Xvfb and libXtst are not installed")

    server = subprocess.Popen(
        ["Xvfb", ":96", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        deadline = time.monotonic() + 10
        while not os.path.exists("/tmp/.X11-unix/X96"):
            if time.monotonic() > deadline or server.poll() is not None:
                pytest.skip("Xvfb did not start")
            time.sleep(0.05)

        monkeypatch.setenv("DISPLAY", ":96")
        yield
    finally:
        server.terminate()
        server.wait(5)


def test_xtest_injector_presses_s_on_the_display(xvfb):
    injector = keyinject.XTestInjector(VK_S)
    reader = keystate.x11_reader()

    assert not reader(VK_S)

    injector.press()
    assert reader(VK_S)

    injector.release()
    assert not reader(VK_S)


def test_uinput_injector_is_a_real_keyboard():
    if not os.access("/dev/uinput", os.W_OK):
        pytest.skip("/dev/uinput is not writable")

    injector = keyinject.UinputInjector(VK_S)

    try:
        path = None
        deadline = time.monotonic() + 5

        while path is None and time.monotonic() < deadline:
            for name_file in glob.glob("/sys/class/input/event*/device/name"):
                with open(name_file, "rb") as f:
                    if f.read().strip() == keyinject.UINPUT_NAME:
                        node = "/dev/input/" + name_file.split("/")[4]
                        if os.access(node, os.R_OK):
                            path = node
            time.sleep(0.05)

        if path is None:
            pytest.skip("the virtual keyboard did not appear in /dev/input")

        # The device only has KEY_S, so read it directly.
        import fcntl

        def s_down():
            state = bytearray(keystate.KEY_BYTES)
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            try:
                fcntl.ioctl(fd, keystate.EVIOCGKEY, state)
            finally:
                os.close(fd)
            return keystate._bit(state, keystate.EVDEV_CODES[VK_S])

        assert not s_down()
        injector.press()
        time.sleep(0.05)
        assert s_down()
        injector.release()
        time.sleep(0.05)
        assert not s_down()
    finally:
        injector.close()

    injector.close()  # idempotent
