"""keyinject.lay and hold_key edge cases found by mutation testing."""

import pytest

import keyinject
from keyinject import hold_key, lay
import test_keyinject
from test_keyinject import FakeInjector

clock = test_keyinject.clock


def kinds(log):
    return [(name, kind) for name, kind, _t in log]


def test_lay_without_a_reset_holds_only_the_key(clock):
    log = []
    injector = FakeInjector(clock, "S", log)

    lay(injector, 0.2, clock.event())

    assert kinds(log) == [("S", "press"), ("S", "release")]


@pytest.mark.parametrize("reset_injector, reset_seconds", [(None, 1.0), ("W", 0.0), ("W", -1.0)])
def test_lay_skips_the_reset_without_a_key_or_a_time(clock, reset_injector, reset_seconds):
    log = []
    injector = FakeInjector(clock, "S", log)
    reset = FakeInjector(clock, "W", log) if reset_injector else None
    resetting = clock.event()

    lay(injector, 0.2, clock.event(), reset, reset_seconds, resetting)

    assert kinds(log) == [("S", "press"), ("S", "release")]
    assert not resetting.is_set()


def test_lay_resets_with_w_then_settles_then_holds_s_and_flags_each_phase(clock):
    log = []
    injector, reset = FakeInjector(clock, "S", log), FakeInjector(clock, "W", log)
    resetting, pressing = clock.event(), clock.event()
    seen = []

    class Watching(FakeInjector):
        def press(self):
            seen.append((self.name, resetting.is_set(), pressing.is_set()))
            super().press()

    injector, reset = Watching(clock, "S", log), Watching(clock, "W", log)

    lay(injector, 0.3, clock.event(), reset, 0.5, resetting, pressing)

    assert kinds(log) == [("W", "press"), ("W", "release"), ("S", "press"), ("S", "release")]
    assert seen == [("W", True, False), ("S", False, True)]
    assert not resetting.is_set() and not pressing.is_set()

    w_release = log[1][2]
    s_press = log[2][2]
    assert s_press - w_release >= keyinject.RESET_SETTLE_SECONDS - 0.001
    assert log[1][2] - log[0][2] == pytest.approx(0.5, abs=0.001)
    assert log[3][2] - log[2][2] == pytest.approx(0.3, abs=0.001)


def test_cancelling_during_the_settle_pause_never_presses_the_key(clock):
    log = []
    injector, reset = FakeInjector(clock, "S", log), FakeInjector(clock, "W", log)
    cancel = clock.event()
    original_wait = cancel.wait

    def cancelling_wait(seconds):
        original_wait(seconds)
        cancel.set()
        return True

    cancel.wait = cancelling_wait

    lay(injector, 0.3, cancel, reset, 0.2, clock.event(), clock.event())

    assert kinds(log) == [("W", "press"), ("W", "release")]


def test_the_phase_flags_are_cleared_when_a_press_fails(clock):
    class Failing(FakeInjector):
        def press(self):
            raise OSError("no")

    resetting, pressing = clock.event(), clock.event()

    with pytest.raises(OSError):
        lay(Failing(clock, "S"), 0.2, clock.event(), None, 0.0, resetting, pressing)

    assert not pressing.is_set()

    with pytest.raises(OSError):
        lay(FakeInjector(clock, "S"), 0.2, clock.event(), Failing(clock, "W"), 0.2, resetting, pressing)

    assert not resetting.is_set()


def test_hold_key_does_not_sleep_for_a_hold_inside_the_spin_window(clock):
    injector = FakeInjector(clock)

    hold_key(injector, keyinject.PRECISE_SPIN_SECONDS / 2, clock.event())

    assert clock.waits == []
    assert [kind for _n, kind, _t in injector.events] == ["press", "release"]


def test_hold_key_with_no_time_presses_and_releases(clock):
    injector = FakeInjector(clock)

    hold_key(injector, 0.0, clock.event())

    assert [kind for _n, kind, _t in injector.events] == ["press", "release"]


def test_hold_key_releases_after_the_exception_of_a_failed_press(clock):
    class Half(FakeInjector):
        def press(self):
            super().press()
            raise OSError("half")

    injector = Half(clock)

    with pytest.raises(OSError):
        hold_key(injector, 1.0, clock.event())

    assert [kind for _n, kind, _t in injector.events] == ["press", "release"]
