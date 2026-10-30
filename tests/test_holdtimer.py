import threading

import pytest

from holdtimer import MAX_POLL_GAP, HoldTimer
from keystate import KEY_S, KEY_W


def make_timer():
    """A timer on fake keys."""
    keys = set()

    timer = HoldTimer(lambda code: code in keys)
    timer.set_active(True)

    return timer, keys


def test_counts_the_time_s_is_held():
    timer, _keys = make_timer()

    timer.set_target(1.0)

    assert timer.poll_timer.isActive()

    timer.advance(0.6, s_down=True, w_down=False)
    timer.advance(0.5, s_down=True, w_down=False)

    assert timer.held == pytest.approx(1.1)


def test_released_key_does_not_count_and_w_resets():
    timer, _keys = make_timer()

    timer.set_target(1.0)

    timer.advance(0.4, s_down=True, w_down=False)
    timer.advance(5.0, s_down=False, w_down=False)
    assert timer.held == pytest.approx(0.4)

    timer.advance(0.01, s_down=False, w_down=True)
    assert timer.held == 0.0

    # Holding W keeps the barrel up: nothing counts until it is released.
    timer.advance(0.5, s_down=True, w_down=True)
    assert timer.held == 0.0

    timer.advance(1.2, s_down=True, w_down=False)
    assert timer.held == pytest.approx(1.2)

    # A new W starts the count anew.
    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(0.01, s_down=False, w_down=False)
    timer.advance(1.0, s_down=True, w_down=False)
    assert timer.held == pytest.approx(1.0)


def test_new_target_continues_from_the_held_time():
    timer, _keys = make_timer()

    timer.set_target(2.0)
    timer.advance(1.5, s_down=True, w_down=False)

    timer.set_target(1.0)
    assert timer.held == pytest.approx(1.5)

    timer.set_target(3.0)
    timer.advance(0.5, s_down=True, w_down=False)
    assert timer.held == pytest.approx(2.0)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_polled_timer():
    keys = set()
    clock = FakeClock()
    timer = HoldTimer(lambda code: code in keys, clock=clock)
    timer.set_active(True)
    return timer, keys, clock


def test_poll_measures_the_time_between_polls():
    timer, keys, clock = make_polled_timer()

    timer.set_target(10.0)

    keys.add(KEY_S)
    for _ in range(5):
        clock.now += 0.01
        timer.poll()

    assert timer.held == pytest.approx(0.05)

    keys.add(KEY_W)
    clock.now += 0.01
    timer.poll()
    assert timer.held == 0.0


def test_ui_freeze_is_not_counted_as_holding():
    timer, keys, clock = make_polled_timer()

    timer.set_target(1.0)

    # The UI froze for 2 s; S is down only at the next poll.
    clock.now += 2.0
    keys.add(KEY_S)
    timer.poll()

    assert timer.held <= MAX_POLL_GAP


def test_w_is_watched_without_a_target():
    """Target out of range, W pressed, new target: the count starts anew."""
    timer, keys, clock = make_polled_timer()

    timer.set_target(2.0)
    keys.add(KEY_S)
    for _ in range(250):
        clock.now += 0.01
        timer.poll()
    keys.discard(KEY_S)
    assert timer.held == pytest.approx(2.5, abs=0.011)

    timer.set_target(None)
    assert timer.active

    keys.add(KEY_W)
    clock.now += 0.01
    timer.poll()
    keys.discard(KEY_W)
    clock.now += 0.01
    timer.poll()

    timer.set_target(1.5)
    assert timer.held == 0.0

    keys.add(KEY_S)
    for _ in range(160):
        clock.now += 0.01
        timer.poll()
    assert timer.held == pytest.approx(1.6, abs=0.011)


def test_set_active_starts_and_stops_polling():
    timer, _keys, _clock = make_polled_timer()

    assert timer.active

    timer.set_active(False)
    assert not timer.active


def test_without_key_reader_nothing_polls():
    timer = HoldTimer(None)

    assert not timer.available

    timer.set_active(True)
    timer.set_target(1.0)

    assert not timer.active


class FakeAutoHold:
    """keyinject.AutoHold without threads: the test drives `resetting`/`pressing`."""

    def __init__(self):
        self.started = []
        self.stopped = 0
        self.active = False
        self.resetting = threading.Event()
        self.pressing = threading.Event()

    def start(self, seconds, reset_seconds=0.0):
        self.started.append(seconds if not reset_seconds else (seconds, reset_seconds))
        self.active = True
        if reset_seconds:
            self.resetting.set()
        else:
            self.pressing.set()
        return True

    def stop(self):
        self.stopped += 1
        self.active = False
        self.resetting.clear()
        self.pressing.clear()


def test_auto_hold_holds_the_time_left_and_counts_it():
    timer, keys, clock = make_polled_timer()
    timer.auto_hold = FakeAutoHold()

    timer.set_target(1.0)
    keys.add(KEY_S)
    for _ in range(30):
        clock.now += 0.01
        timer.poll()
    keys.discard(KEY_S)

    assert timer.toggle_auto_hold()
    assert timer.auto_hold.started == [pytest.approx(0.7)]

    # Our own S is counted even when the reader does not see it.
    for _ in range(71):
        clock.now += 0.01
        timer.poll()
    assert timer.held == pytest.approx(1.0, abs=0.011)

    # Pressing the hotkey again releases.
    timer.auto_hold.active = True
    assert not timer.toggle_auto_hold()
    assert not timer.auto_hold.active


@pytest.mark.parametrize("cancel", ["w", "new_target", "no_target", "inactive"])
def test_auto_hold_is_cancelled(cancel):
    timer, keys, clock = make_polled_timer()
    timer.auto_hold = FakeAutoHold()
    timer.set_target(2.0)
    timer.toggle_auto_hold()

    if cancel == "w":
        timer.advance(0.01, False, True)
    elif cancel == "new_target":
        timer.set_target(1.0)
    elif cancel == "no_target":
        timer.set_target(None)
    else:
        timer.set_active(False)

    assert not timer.auto_hold.active


def test_mortar_auto_lay_resets_with_its_own_w_then_holds_the_whole_time():
    timer, keys, clock = make_polled_timer()
    timer.auto_hold = FakeAutoHold()
    timer.set_target(1.0)

    # S partly held by hand: the auto-lay still holds the whole time after W
    keys.add(KEY_S)
    for _ in range(30):
        clock.now += 0.01
        timer.poll()
    keys.discard(KEY_S)

    assert timer.toggle_auto_hold(reset_seconds=5.2)
    assert timer.auto_hold.started == [(1.0, 5.2)]

    # Our own W (unseen by the reader) restarts the count without cancelling
    for _ in range(50):
        clock.now += 0.01
        timer.poll()
    assert timer.auto_hold.active
    assert timer.held == 0
    assert timer.w_down and not timer.s_down

    # W released, S not yet pressed (settle pause): nothing counted
    timer.auto_hold.resetting.clear()
    for _ in range(10):
        clock.now += 0.01
        timer.poll()
    assert timer.held == 0

    timer.auto_hold.pressing.set()
    for _ in range(101):
        clock.now += 0.01
        timer.poll()
    assert timer.held == pytest.approx(1.01)


def test_player_w_still_cancels_a_mortar_auto_lay():
    timer, keys, clock = make_polled_timer()
    timer.auto_hold = FakeAutoHold()
    timer.set_target(1.0)
    timer.toggle_auto_hold(reset_seconds=5.2)
    timer.auto_hold.resetting.clear()
    timer.auto_hold.pressing.set()

    keys.add(KEY_W)
    clock.now += 0.01
    timer.poll()

    assert not timer.auto_hold.active


def test_auto_hold_needs_a_target_and_the_setting():
    timer, _keys, _clock = make_polled_timer()

    assert not timer.toggle_auto_hold()  # disabled: no AutoHold

    timer.auto_hold = FakeAutoHold()
    assert not timer.toggle_auto_hold()  # no target
    assert timer.auto_hold.started == []


def test_key_state_is_reported():
    timer, keys, clock = make_polled_timer()
    changes = []
    timer.changed.connect(lambda: changes.append((timer.s_down, timer.w_down)))

    keys.add(KEY_W)
    clock.now += 0.01
    timer.poll()
    assert (timer.s_down, timer.w_down) == (False, True)

    keys.clear()
    clock.now += 0.01
    timer.poll()
    assert (timer.s_down, timer.w_down) == (False, False)
    assert changes


def test_s_held_through_a_ui_freeze_counts_the_whole_freeze():
    """#3 item 25: S down before and after a 300 ms hitch was held all along."""
    timer, keys, clock = make_polled_timer()

    timer.set_target(5.0)
    keys.add(KEY_S)
    clock.now += 0.01
    timer.poll()
    held = timer.held

    clock.now += 0.3
    timer.poll()

    assert timer.held == pytest.approx(held + 0.3)


def test_a_key_that_changed_across_a_freeze_counts_at_most_the_cap():
    timer, keys, clock = make_polled_timer()

    timer.set_target(5.0)
    keys.add(KEY_S)
    clock.now += 0.01
    timer.poll()
    held = timer.held

    # S released at an unknown moment of the freeze
    keys.discard(KEY_S)
    clock.now += 0.3
    timer.poll()
    assert timer.held == pytest.approx(held)

    # W down through a freeze resets, it does not count S
    keys.update({KEY_S, KEY_W})
    clock.now += 0.3
    timer.poll()
    assert timer.held == 0.0


def test_suspended_keys_are_not_counted_until_w_after_resume():
    """#3 item 17: the taps of a lay on the sight neither count nor reset,
    and the count then says it is no lay from the top."""
    timer, _keys = make_timer()

    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(2.0, s_down=True, w_down=False)
    assert timer.measures_lay

    timer.suspend()
    timer.advance(0.05, s_down=False, w_down=True)
    timer.advance(0.5, s_down=True, w_down=False)
    assert timer.held == pytest.approx(2.0)
    assert not timer.measures_lay

    timer.resume()
    timer.advance(0.5, s_down=True, w_down=False)
    assert not timer.measures_lay

    timer.advance(0.01, s_down=False, w_down=True)
    assert timer.measures_lay and timer.held == 0.0


def test_a_w_held_through_resume_is_not_a_new_press():
    timer, _keys = make_timer()

    timer.advance(1.0, s_down=True, w_down=False)
    timer.suspend()
    timer.advance(0.05, s_down=False, w_down=True)
    timer.resume()
    timer.advance(0.05, s_down=False, w_down=True)

    assert not timer.measures_lay


class SwitchingReader:
    """A key reader whose keyboard can be unplugged (EvdevReader-like)."""

    def __init__(self):
        self.available = True

    def __call__(self, code):
        return False


def test_available_follows_the_readers_keyboards_and_polling_goes_on():
    reader = SwitchingReader()
    timer = HoldTimer(reader)

    assert timer.available

    reader.available = False
    assert not timer.available

    # Polling is what finds the keyboard again: it starts all the same
    timer.set_active(True)
    assert timer.active

    reader.available = True
    assert timer.available
