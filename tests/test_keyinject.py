"""Key injection: timing logic and real delivery (Xvfb + XTest, uinput)."""

import glob
import os
import signal
import struct
import subprocess
import sys
import threading
import time

import pytest

import keyinject
import keystate
from keyinject import AutoHold, hold_key
from conftest import ROOT
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


def test_hold_key_releases_when_the_press_fails(clock):
    """A press that fails halfway (uinput: the key-down written, the
    SYN_REPORT not) still gets its release, and the error is raised
    (#5, review 1.6.0 slice 5 claim 9)."""
    class FailingPress(FakeInjector):
        def press(self):
            super().press()
            raise OSError("write failed")

    injector = FailingPress(clock)

    with pytest.raises(OSError):
        hold_key(injector, 1.0, clock.event())

    assert [kind for _key, kind, _t in injector.events] == ["press", "release"]


def test_stop_waits_until_the_worker_is_done():
    """stop() returns only once the worker has released the key, however
    long its key call takes (a stalled X server): the injector is closed
    right after it (#5, review 1.6.0 slice 5 claim 2)."""
    unblock = threading.Event()
    log = []

    class SlowPress(FakeInjector):
        def press(self):
            super().press()
            unblock.wait(10)

    auto = AutoHold(SlowPress(log=log))
    assert auto.start(5.0)
    assert wait_until(lambda: log)

    stopped = threading.Event()
    stopper = threading.Thread(target=lambda: (auto.stop(), stopped.set()))
    stopper.start()

    # Longer than the 0.5 s the stop used to give up after.
    assert not stopped.wait(1.0), "stop() returned while the worker was in press()"

    unblock.set()
    assert stopped.wait(5)
    stopper.join()

    assert not auto.active
    assert [kind for _key, kind, _t in log] == ["press", "release"]


def test_uinput_close_releases_a_held_key(monkeypatch, tmp_path):
    """close() sends the key-up before destroying the device, and the key
    calls do nothing afterwards (#5, review 1.6.0 slice 5 claims 2 and 3)."""
    writes = []
    calls = []

    monkeypatch.setattr(keyinject.fcntl, "ioctl", lambda fd, request, arg=0: calls.append(request))
    monkeypatch.setattr(keyinject.os, "write", lambda fd, data: writes.append(data) or len(data))
    monkeypatch.setattr(keyinject.os, "close", lambda fd: calls.append("close"))

    device = tmp_path / "uinput"
    device.touch()
    injector = keyinject.UinputInjector(KEY_S, str(device))
    writes.clear()

    injector.press()
    injector.close()

    events = [struct.unpack("llHHi", data)[3:] for data in writes]
    key_events = [value for code, value in events if code == KEY_S]
    assert key_events == [1, 0]
    assert calls[-2:] == [keyinject._UI_DEV_DESTROY, "close"]

    writes.clear()
    injector.press()
    injector.release()
    injector.close()
    assert writes == []


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

        # Read this device alone: keystate's readers skip the app's own
        # virtual keyboards (UINPUT_NAME).
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
    """udev tags a device as a keyboard only with KEY_ESC..KEY_S (codes
    1-31) set; without the tag the compositor may ignore the injected
    keys."""
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


def test_xtest_close_releases_a_held_key(xvfb):
    """The X server keeps an XTest key down after its client goes away, so
    close() sends the key-up (#5, review 1.6.0 slice 5 claim 3). The
    reader stays connected, like the window manager and the game: Xvfb
    left without clients resets and would release the key itself."""
    reader = keystate.x11_reader()
    injector = keyinject.XTestInjector(KEY_S)

    injector.press()
    assert reader(KEY_S)

    injector.close()
    assert not reader(KEY_S)


# Runs in a child process: a key call on a closed display used to crash
# the process (XTestFakeKeyEvent on NULL).
CLOSED_DISPLAY_CHILD = r"""
import sys
sys.path.insert(0, sys.argv[1])
import keyinject
from keystate import KEY_S

injector = keyinject.XTestInjector(KEY_S)
injector.close()
injector.press()
injector.release()
injector.close()
print("ok", flush=True)
"""


def test_xtest_key_calls_after_close_do_nothing(xvfb):
    child = subprocess.run(
        [sys.executable, "-c", CLOSED_DISPLAY_CHILD, ROOT],
        env=dict(os.environ), capture_output=True, text=True, timeout=30
    )

    assert child.returncode == 0, child.stderr[-2000:]
    assert child.stdout.strip() == "ok"


def own_xvfb_pid():
    """The pid of the Xvfb this test process started (xvfb_display)."""
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue

        try:
            with open(f"/proc/{entry}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            with open(f"/proc/{entry}/comm") as f:
                comm = f.read().strip()
        except OSError:
            continue

        if comm == "Xvfb" and int(fields[1]) == os.getpid():
            return int(entry)

    pytest.fail("the test's Xvfb was not found")


# What MainWindow.drop_auto_hold does, while the X server does not answer:
# stop the hold, then close the injector the worker was using.
STALLED_SERVER_CHILD = r"""
import os, signal, sys, threading, time
sys.path.insert(0, sys.argv[1])
import keyinject
from keystate import KEY_S

xvfb_pid = int(sys.argv[2])
injector = keyinject.XTestInjector(KEY_S)
auto = keyinject.AutoHold(injector)

os.kill(xvfb_pid, signal.SIGSTOP)
threading.Timer(1.5, os.kill, (xvfb_pid, signal.SIGCONT)).start()
auto.start(5.0)
time.sleep(0.1)

auto.stop()
print("stopped, worker alive:", auto.active, flush=True)
injector.close()
os._exit(3 if auto.active else 0)
"""


def test_closing_after_a_stop_on_a_stalled_x_server(xvfb):
    """The worker is inside press() while the X server is stopped; stop()
    must wait for it, so close() never runs under the worker: no crash, S
    not left down (#5, review 1.6.0 slice 5 claim 2)."""
    reader = keystate.x11_reader()
    xvfb_pid = own_xvfb_pid()

    try:
        child = subprocess.run(
            [sys.executable, "-c", STALLED_SERVER_CHILD, ROOT, str(xvfb_pid)],
            env=dict(os.environ), capture_output=True, text=True, timeout=30
        )
    finally:
        os.kill(xvfb_pid, signal.SIGCONT)

    assert child.returncode == 0, (child.returncode, child.stdout, child.stderr[-2000:])
    assert not reader(KEY_S), "S left held"
