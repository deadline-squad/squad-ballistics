import os
import threading

import pytest

pytest.importorskip("PyQt6.QtCore")

from holdtimer import DEFAULT_LEAD, MAX_LEAD, MAX_POLL_GAP, HoldTimer
from keystate import KEY_S, KEY_W


def make_timer(keys=None, lead=0.0):
    """A timer on fake keys; the beep lead is 0 unless a test is about it."""
    keys = set() if keys is None else keys

    timer = HoldTimer(lambda code: code in keys)
    timer.set_active(True)
    timer.lead = lead

    reached = []
    timer.reached.connect(lambda: reached.append(timer.held))

    return timer, keys, reached


def test_beeps_once_when_the_hold_time_is_reached():
    timer, _keys, reached = make_timer()

    timer.set_target(1.0)

    assert timer.poll_timer.isActive()

    timer.advance(0.6, s_down=True, w_down=False)
    assert reached == []

    timer.advance(0.5, s_down=True, w_down=False)
    assert reached == [pytest.approx(1.1)]
    assert timer.is_reached

    timer.advance(0.5, s_down=True, w_down=False)
    assert len(reached) == 1


def test_released_key_does_not_count_and_w_resets():
    timer, _keys, reached = make_timer()

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
    assert len(reached) == 1

    # A new W after the beep arms it again.
    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(0.01, s_down=False, w_down=False)
    timer.advance(1.0, s_down=True, w_down=False)
    assert len(reached) == 2


def test_new_target_continues_from_the_held_time():
    timer, _keys, reached = make_timer()

    timer.set_target(2.0)
    timer.advance(1.5, s_down=True, w_down=False)

    # Already past the new target: no late beep.
    timer.set_target(1.0)
    assert timer.is_reached
    timer.advance(0.1, s_down=True, w_down=False)
    assert reached == []

    timer.set_target(3.0)
    assert not timer.is_reached
    timer.advance(1.5, s_down=True, w_down=False)
    assert len(reached) == 1


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_polled_timer():
    keys = set()
    clock = FakeClock()
    timer = HoldTimer(lambda code: code in keys, clock=clock)
    timer.lead = 0.0
    reached = []
    timer.reached.connect(lambda: reached.append(timer.held))
    timer.set_active(True)
    return timer, keys, clock, reached


def test_poll_measures_the_time_between_polls():
    timer, keys, clock, _reached = make_polled_timer()

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
    timer, keys, clock, _reached = make_polled_timer()

    timer.set_target(1.0)

    # The UI froze for 2 s; S is down only at the next poll.
    clock.now += 2.0
    keys.add(KEY_S)
    timer.poll()

    assert timer.held <= MAX_POLL_GAP


def test_w_is_watched_without_a_target():
    """Target out of range, W pressed, new target: the count starts anew."""
    timer, keys, clock, reached = make_polled_timer()

    timer.set_target(2.0)
    keys.add(KEY_S)
    for _ in range(250):
        clock.now += 0.01
        timer.poll()
    keys.discard(KEY_S)
    assert len(reached) == 1

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
    assert not timer.is_reached

    keys.add(KEY_S)
    for _ in range(160):
        clock.now += 0.01
        timer.poll()
    assert len(reached) == 2
    assert reached[1] == pytest.approx(1.5, abs=0.011)


def test_set_active_starts_and_stops_polling():
    timer, _keys, _clock, _reached = make_polled_timer()

    assert timer.active

    timer.set_active(False)
    assert not timer.active


def test_without_key_reader_nothing_polls():
    timer = HoldTimer(None)

    assert not timer.available

    timer.set_active(True)
    timer.set_target(1.0)

    assert not timer.active

    timer.set_target(None)
    assert not timer.is_reached


def test_beep_wav_is_a_valid_tone():
    import io
    import wave

    from holdtimer import BEEP_MS, beep_wav

    with wave.open(io.BytesIO(beep_wav())) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        frames = w.readframes(w.getnframes())
        assert w.getnframes() == w.getframerate() * BEEP_MS // 1000

    samples = [int.from_bytes(frames[i:i + 2], "little", signed=True)
               for i in range(0, len(frames), 2)]
    assert max(samples) > 10000
    assert samples[0] == 0  # faded in: no click


def test_linux_beep_uses_the_first_player_found(monkeypatch, tmp_path):
    import holdtimer

    players = {"paplay": "/usr/bin/paplay", "aplay": "/usr/bin/aplay"}
    monkeypatch.setattr(holdtimer.shutil, "which", players.get)
    monkeypatch.setattr(holdtimer, "_beep_file", None)
    monkeypatch.setattr(holdtimer.tempfile, "tempdir", str(tmp_path))

    command = holdtimer.linux_beep_command()

    assert command[0] == "/usr/bin/paplay"
    assert os.path.getsize(command[1]) > 44

    monkeypatch.setattr(holdtimer.shutil, "which", lambda name: None)
    assert holdtimer.linux_beep_command() is None


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
    timer, keys, clock, reached = make_polled_timer()
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
    assert len(reached) == 1

    # Pressing the hotkey again releases.
    timer.auto_hold.active = True
    assert not timer.toggle_auto_hold()
    assert not timer.auto_hold.active


@pytest.mark.parametrize("cancel", ["w", "new_target", "no_target", "inactive"])
def test_auto_hold_is_cancelled(cancel):
    timer, keys, clock, _reached = make_polled_timer()
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
    timer, keys, clock, reached = make_polled_timer()
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
    assert len(reached) == 1


def test_player_w_still_cancels_a_mortar_auto_lay():
    timer, keys, clock, _reached = make_polled_timer()
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
    timer, _keys, _clock, _reached = make_polled_timer()

    assert not timer.toggle_auto_hold()  # disabled: no AutoHold

    timer.auto_hold = FakeAutoHold()
    assert not timer.toggle_auto_hold()  # no target
    assert timer.auto_hold.started == []


def test_key_state_is_reported():
    timer, keys, clock, _reached = make_polled_timer()
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


def test_the_beep_comes_early_by_the_lead():
    timer, _keys, reached = make_timer(lead=DEFAULT_LEAD)
    timer.set_target(2.0)

    timer.advance(1.75, s_down=True, w_down=False)
    assert reached == []

    timer.advance(0.05, s_down=True, w_down=False)
    assert reached == [pytest.approx(1.8)]


def test_the_lead_is_learnt_from_the_players_release():
    """Released 0.1 s late after the beep: the next beep comes 0.05 s
    earlier; released early: later. Each change is reported to be saved."""
    timer, _keys, reached = make_timer(lead=0.2)
    learned = []
    timer.lead_learned.connect(learned.append)
    timer.set_target(2.0)

    timer.advance(1.8, s_down=True, w_down=False)
    assert len(reached) == 1
    timer.advance(0.3, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)

    assert timer.lead == pytest.approx(0.25)
    assert learned == [pytest.approx(0.25)]

    # Next lay: released 0.06 s early
    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(0.01, s_down=False, w_down=False)
    timer.advance(1.75, s_down=True, w_down=False)
    assert len(reached) == 2
    timer.advance(0.19, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)

    assert timer.lead == pytest.approx(0.22)


def test_only_the_first_release_after_the_beep_teaches():
    timer, _keys, _reached = make_timer(lead=0.2)
    timer.set_target(2.0)

    timer.advance(1.9, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)
    lead = timer.lead

    # Topping up with S afterwards is not a reaction to the beep
    timer.advance(0.3, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)
    assert timer.lead == lead


def test_no_learning_from_releases_before_the_beep_or_far_off():
    timer, _keys, _reached = make_timer(lead=0.2)
    timer.set_target(2.0)

    # Released before the beep
    timer.advance(1.0, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)
    assert timer.lead == 0.2

    # Held on for a second after the beep: not a reaction
    timer.advance(1.0, s_down=True, w_down=False)
    timer.advance(1.0, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)
    assert timer.lead == 0.2


def test_the_lead_stays_within_its_limits():
    timer, _keys, _reached = make_timer(lead=MAX_LEAD - 0.01)
    timer.set_target(2.0)

    # Released 0.4 s late: half of it would pass the limit
    timer.advance(2.0 - timer.lead, s_down=True, w_down=False)
    timer.advance(timer.lead + 0.4, s_down=True, w_down=False)
    timer.advance(0.01, s_down=False, w_down=False)

    assert timer.lead == MAX_LEAD

