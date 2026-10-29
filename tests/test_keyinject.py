"""Key injection: timing logic and real delivery (Xvfb + XTest, uinput)."""

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
from keystate import KEY_S


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


class NamedInjector(FakeInjector):
    def __init__(self, name, log):
        super().__init__()
        self.name = name
        self.events = log

    def press(self):
        self.events.append((self.name, "press", time.perf_counter()))

    def release(self):
        self.events.append((self.name, "release", time.perf_counter()))


def test_auto_lay_holds_w_then_s():
    log = []
    auto = AutoHold(NamedInjector("S", log), NamedInjector("W", log))

    assert auto.start(0.2, reset_seconds=0.3)
    time.sleep(0.1)
    assert auto.resetting.is_set() and not auto.pressing.is_set()
    auto.thread.join(2)

    assert [(key, kind) for key, kind, _ in log] == [
        ("W", "press"), ("W", "release"), ("S", "press"), ("S", "release")]
    w_held = log[1][2] - log[0][2]
    gap = log[2][2] - log[1][2]
    s_held = log[3][2] - log[2][2]
    assert w_held == pytest.approx(0.3, abs=0.01)
    assert gap == pytest.approx(keyinject.RESET_SETTLE_SECONDS, abs=0.02)
    assert s_held == pytest.approx(0.2, abs=0.01)
    assert not auto.resetting.is_set() and not auto.pressing.is_set()


def test_cancel_during_the_reset_never_presses_s():
    log = []
    auto = AutoHold(NamedInjector("S", log), NamedInjector("W", log))

    assert auto.start(1.0, reset_seconds=5.0)
    time.sleep(0.05)
    auto.stop()

    assert [(key, kind) for key, kind, _ in log] == [("W", "press"), ("W", "release")]
    assert not auto.resetting.is_set()


def test_reset_needs_a_w_injector():
    assert not AutoHold(FakeInjector()).start(1.0, reset_seconds=5.0)


def test_nothing_to_hold():
    auto = AutoHold(FakeInjector())

    assert not auto.start(0)
    assert not auto.start(-1)
    auto.stop()  # no thread: no-op


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
    injector = keyinject.XTestInjector(KEY_S)
    reader = keystate.x11_reader()

    assert not reader(KEY_S)

    injector.press()
    assert reader(KEY_S)

    injector.release()
    assert not reader(KEY_S)


def test_uinput_injector_is_a_real_keyboard():
    if not os.access("/dev/uinput", os.W_OK):
        pytest.skip("/dev/uinput is not writable")

    injector = keyinject.UinputInjector(KEY_S)

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
            return keystate._bit(state, KEY_S)

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


def test_uinput_device_advertises_the_keys_udev_needs_for_a_keyboard(monkeypatch, tmp_path):
    """udev tags a device as a keyboard only with KEY_ESC..KEY_D set;
    without the tag the compositor may ignore the injected keys."""
    calls = []
    opened = []

    monkeypatch.setattr(keyinject.fcntl, "ioctl", lambda fd, request, arg=0: calls.append((request, arg)))
    monkeypatch.setattr(keyinject.os, "write", lambda fd, data: len(data))
    monkeypatch.setattr(keyinject.os, "close", lambda fd: opened.append(fd))

    device = tmp_path / "uinput"
    device.touch()
    injector = keyinject.UinputInjector(keystate.KEY_D, str(device))
    keys = {arg for request, arg in calls if request == keyinject._UI_SET_KEYBIT}

    assert set(range(1, 32)) <= keys
    assert keystate.KEY_D in keys
    injector.close()


def test_xtest_injector_closes_its_connection_once(xvfb):
    injector = keyinject.XTestInjector(KEY_S)

    injector.close()
    assert injector.display is None
    injector.close()

    # No client is left behind: far more cycles than the server's client limit
    for _ in range(300):
        keyinject.XTestInjector(KEY_S).close()

    assert keyinject.XTestInjector(KEY_S).display
