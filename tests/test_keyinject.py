"""Key injection: timing logic and real delivery (Xvfb + XTest, uinput)."""

import glob
import os
import time

import pytest

import keyinject
import keystate
from keyinject import AutoHold, hold_key
from keystate import KEY_S


class VirtualClock:
    """`time.perf_counter` and `threading.Event` for keyinject that only
    move when the code under test waits or reads the clock, so the timing
    is exact under any CPU load. Every read advances 50 µs, like a busy
    wait would."""

    TICK = 0.00005

    def __init__(self):
        self.now = 1000.0
        self.waits = []

    def perf_counter(self):
        self.now += self.TICK
        return self.now

    def event(self):
        clock = self

        class Event:
            def __init__(self):
                self.flag = False

            def is_set(self):
                return self.flag

            def set(self):
                self.flag = True

            def clear(self):
                self.flag = False

            def wait(self, seconds):
                clock.waits.append(seconds)
                clock.now += seconds
                return self.flag

        return Event()


@pytest.fixture
def clock(monkeypatch):
    virtual = VirtualClock()
    monkeypatch.setattr(keyinject, "time", virtual)
    return virtual


class FakeInjector:
    def __init__(self, clock=None, name="S", log=None):
        self.clock = clock or time
        self.name = name
        self.events = [] if log is None else log
        self.closed = False

    def press(self):
        self.events.append((self.name, "press", self.clock.perf_counter()))

    def release(self):
        self.events.append((self.name, "release", self.clock.perf_counter()))

    def close(self):
        self.closed = True


def test_hold_key_holds_for_the_requested_time(clock):
    injector = FakeInjector(clock)

    hold_key(injector, 0.25, clock.event())

    (_k1, kind1, start), (_k2, kind2, end) = injector.events
    assert (kind1, kind2) == ("press", "release")
    assert end - start == pytest.approx(0.25, abs=0.0002)
    # Slept to just before the end, then waited actively.
    assert clock.waits == [pytest.approx(0.25 - keyinject.PRECISE_SPIN_SECONDS, abs=0.0002)]


def test_hold_key_stops_at_once_when_cancelled(clock):
    injector = FakeInjector(clock)
    cancel = clock.event()
    cancel.set()

    hold_key(injector, 5.0, cancel)

    assert [kind for _key, kind, _t in injector.events] == ["press", "release"]
    assert clock.waits == []


def wait_until(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.005)
    return condition()


def test_cancel_releases_at_once():
    injector = FakeInjector()
    auto = AutoHold(injector)

    assert auto.start(5.0)
    assert auto.active
    assert not auto.start(1.0)  # one hold at a time

    assert wait_until(auto.pressing.is_set)
    auto.stop(wait=5)

    assert not auto.active
    assert [kind for _key, kind, _t in injector.events] == ["press", "release"]
    assert injector.events[1][2] - injector.events[0][2] < 4


def test_auto_lay_holds_w_then_s(clock):
    log = []
    states = []
    resetting, pressing = clock.event(), clock.event()

    class Recording(FakeInjector):
        def press(self):
            states.append((self.name, resetting.is_set(), pressing.is_set()))
            super().press()

    keyinject.lay(
        Recording(clock, "S", log), 0.2, clock.event(),
        Recording(clock, "W", log), 0.3, resetting, pressing
    )

    assert [(key, kind) for key, kind, _ in log] == [
        ("W", "press"), ("W", "release"), ("S", "press"), ("S", "release")]
    # W is held while `resetting` is set, S while `pressing` is.
    assert states == [("W", True, False), ("S", False, True)]
    w_held = log[1][2] - log[0][2]
    gap = log[2][2] - log[1][2]
    s_held = log[3][2] - log[2][2]
    assert w_held == pytest.approx(0.3, abs=0.0002)
    assert gap == pytest.approx(keyinject.RESET_SETTLE_SECONDS, abs=0.0002)
    assert s_held == pytest.approx(0.2, abs=0.0002)
    assert not resetting.is_set() and not pressing.is_set()


def test_cancel_during_the_reset_never_presses_s():
    log = []
    auto = AutoHold(FakeInjector(name="S", log=log), FakeInjector(name="W", log=log))

    assert auto.start(1.0, reset_seconds=5.0)
    assert wait_until(auto.resetting.is_set)
    auto.stop(wait=5)

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
def xvfb(monkeypatch, xvfb_display):
    if not (
        os.path.exists("/usr/lib/x86_64-linux-gnu/libXtst.so.6")
        or glob.glob("/usr/lib*/libXtst.so.6")
    ):
        pytest.skip("libXtst is not installed")

    monkeypatch.setenv("DISPLAY", xvfb_display)


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

    # No client is left behind: far more cycles than the server's client
    # limit. A busy server may free a closed client's slot a little late,
    # so a refused connection is retried; a leak would refuse it for good.
    def connect():
        for _ in range(100):
            try:
                return keyinject.XTestInjector(KEY_S)
            except OSError:
                time.sleep(0.05)
        pytest.fail("the X server kept refusing connections")

    for _ in range(300):
        connect().close()

    assert keyinject.XTestInjector(KEY_S).display
