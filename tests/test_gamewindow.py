"""The game's window on the X server (gamewindow.py): the lookup against a
fake X layer, the watch, and the real thing against an Xvfb server with
stand-in windows (xclient.py). How the overlay follows the window is in
test_overlay.py."""

import json
import os
import subprocess
import sys

import pytest

import gamewindow
from conftest import ROOT
from gamewindow import GameWindowWatch, X11Windows, find_game_rect, is_game_window

PROBE = os.path.join(ROOT, "tests", "game_window_probe.py")

PROTON = ("steam_app_393380", "steam_app_393380")


class FakeWindows:
    """The questions gamewindow asks of the X server, answered from a dict
    of windows: id -> (WM_CLASS names, title, rect or None when gone)."""

    def __init__(self):
        self.windows = {}
        self.closed = False

    def add(self, window, wm_class=(), title="", rect=(0, 0, 1920, 1080)):
        self.windows[window] = (wm_class, title, rect)

    def client_list(self):
        return list(self.windows)

    def wm_class(self, window):
        return self.windows[window][0]

    def title(self, window):
        return self.windows[window][1]

    def geometry(self, window):
        return self.windows[window][2]

    def close(self):
        self.closed = True


# ---------- which window is the game's ----------

@pytest.mark.parametrize("wm_class, title, game", [
    (PROTON, "", True),
    (("steam_app_393380",), "anything", True),
    (("other", "steam_app_393380"), "", True),
    ((), "SquadGame", True),
    (("firefox", "Navigator"), "SquadGame  ", True),
    ((), "", False),
    (("firefox", "Navigator"), "SquadGame wiki - Mozilla Firefox", False),
    (("steam_app_440", "steam_app_440"), "Team Fortress 2", False),
    (("steam_app_3933800",), "", False),
])
def test_which_windows_are_the_games(wm_class, title, game):
    assert is_game_window(wm_class, title) is game


# ---------- the lookup ----------

def test_without_the_game_no_window_is_found():
    windows = FakeWindows()
    windows.add(1, ("konsole", "konsole"), "Terminal")
    windows.add(2, ("firefox", "Navigator"), "Mozilla Firefox")

    assert find_game_rect(windows) is None


def test_without_any_window_none_is_found():
    assert find_game_rect(FakeWindows()) is None


def test_the_game_window_is_found_with_its_geometry():
    windows = FakeWindows()
    windows.add(1, ("konsole", "konsole"), "Terminal")
    windows.add(2, PROTON, "SquadGame", (320, 180, 1280, 720))

    assert find_game_rect(windows) == (320, 180, 1280, 720)


def test_a_window_fullscreen_on_a_second_monitor_gives_its_place_in_root_coordinates():
    windows = FakeWindows()
    windows.add(2, PROTON, "SquadGame", (1920, 0, 2560, 1440))

    assert find_game_rect(windows) == (1920, 0, 2560, 1440)


def test_the_largest_window_of_the_game_is_the_picture():
    windows = FakeWindows()
    windows.add(1, PROTON, "", (800, 400, 320, 200))
    windows.add(2, PROTON, "SquadGame", (0, 0, 1920, 1080))
    windows.add(3, PROTON, "", (0, 0, 64, 64))

    assert find_game_rect(windows) == (0, 0, 1920, 1080)


def test_a_window_that_closed_between_the_list_and_the_question_is_not_found():
    windows = FakeWindows()
    windows.add(2, PROTON, "SquadGame", None)

    assert find_game_rect(windows) is None


@pytest.mark.parametrize("rect", [(0, 0, 0, 1080), (0, 0, 1920, 0)])
def test_a_window_without_an_area_is_not_found(rect):
    windows = FakeWindows()
    windows.add(2, PROTON, "SquadGame", rect)

    assert find_game_rect(windows) is None


# ---------- the watch ----------

def make_watch(qapp, windows):
    watch = GameWindowWatch(windows)
    seen = []
    watch.changed.connect(seen.append)

    return watch, seen


def test_the_watch_tells_when_the_window_appears_moves_resizes_and_closes(qapp):
    windows = FakeWindows()
    watch, seen = make_watch(qapp, windows)

    watch.poll()
    assert seen == []

    windows.add(2, PROTON, "SquadGame", (0, 0, 1280, 720))
    watch.poll()
    watch.poll()
    assert seen == [(0, 0, 1280, 720)]

    windows.add(2, PROTON, "SquadGame", (100, 60, 1280, 720))
    watch.poll()
    windows.add(2, PROTON, "SquadGame", (100, 60, 1920, 1080))
    watch.poll()
    assert seen[1:] == [(100, 60, 1280, 720), (100, 60, 1920, 1080)]

    del windows.windows[2]
    watch.poll()
    watch.poll()
    assert seen[3:] == [None]

    watch.stop()


def test_the_watch_polls_on_a_timer_and_stop_ends_it_and_the_connection(qapp):
    windows = FakeWindows()
    watch, _seen = make_watch(qapp, windows)

    assert watch.timer.isActive()
    assert watch.timer.interval() == gamewindow.POLL_MS

    watch.stop()

    assert not watch.timer.isActive()
    assert windows.closed


# ---------- a real X server ----------

@pytest.fixture
def x_session(xvfb_display, monkeypatch):
    """The X layer and a client making the game's window, on one Xvfb."""
    from xclient import XClient

    monkeypatch.setenv("DISPLAY", xvfb_display)
    windows = X11Windows.open()
    client = XClient()

    yield windows, client

    client.close()
    windows.close()


def test_the_real_layer_finds_the_game_window_by_its_class(x_session):
    windows, client = x_session
    client.create(10, 20, 300, 200, wm_class="konsole", title="Terminal")
    game = client.create(100, 50, 960, 540, wm_class="steam_app_393380")

    assert game in windows.client_list()
    assert windows.wm_class(game) == PROTON
    assert find_game_rect(windows) == (100, 50, 960, 540)


def test_the_real_layer_finds_the_game_window_by_its_title(x_session):
    windows, client = x_session
    game = client.create(0, 0, 640, 360, title="SquadGame")

    assert windows.title(game) == "SquadGame"
    assert find_game_rect(windows) == (0, 0, 640, 360)


def test_the_real_layer_sees_no_game_among_other_windows(x_session):
    windows, client = x_session
    client.create(10, 20, 300, 200, wm_class="konsole", title="Terminal")

    assert find_game_rect(windows) is None


def test_the_real_layer_follows_a_moved_and_resized_window(x_session):
    windows, client = x_session
    game = client.create(100, 50, 960, 540, wm_class="steam_app_393380")

    client.move_resize(game, 300, 100, 640, 360)

    assert find_game_rect(windows) == (300, 100, 640, 360)


def test_a_window_destroyed_before_the_list_changed_is_not_found_and_does_not_end_the_process(x_session):
    windows, client = x_session
    game = client.create(100, 50, 960, 540, wm_class="steam_app_393380")

    client.destroy(game)

    assert game in windows.client_list()
    assert find_game_rect(windows) is None
    assert windows.wm_class(game) == ()
    assert windows.title(game) == ""

    client.forget(game)
    assert find_game_rect(windows) is None


def test_the_overlay_follows_the_window_on_a_real_server(xvfb_display):
    env = dict(os.environ, DISPLAY=xvfb_display, QT_QPA_PLATFORM="xcb")
    result = subprocess.run(
        [sys.executable, PROBE], env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout.strip().splitlines()[-1])

    assert seen["watching"]
    assert seen["start"] == [0, 0, 1280, 720]
    assert seen["found"] == [100, 50, 960, 540]
    assert seen["moved"] == [200, 80, 640, 360]
    assert seen["destroyed_before_the_list_changed"] == [0, 0, 1280, 720]
    assert seen["closed"] == [0, 0, 1280, 720]
    assert seen["monitor"] == 0
    assert seen["changes"] == [
        [100, 50, 960, 540], [200, 80, 640, 360], [0, 0, 1280, 720]
    ]
