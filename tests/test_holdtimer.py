import pytest

pytest.importorskip("PyQt6.QtCore")

from holdtimer import VK_S, VK_W, HoldTimer


def make_timer(keys=None):
    keys = set() if keys is None else keys

    timer = HoldTimer(lambda vk: vk in keys)

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


def test_poll_reads_the_keys():
    timer, keys, _reached = make_timer()

    timer.set_target(10.0)

    keys.add(VK_S)
    timer.poll()
    timer.poll()
    assert timer.held >= 0.0

    keys.add(VK_W)
    timer.poll()
    assert timer.held == 0.0


def test_without_key_reader_nothing_polls():
    timer = HoldTimer(None)

    assert not timer.available

    timer.set_target(1.0)

    assert not timer.poll_timer.isActive()

    timer.set_target(None)
    assert not timer.is_reached
