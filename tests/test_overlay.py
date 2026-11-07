"""The overlay window: its flags, the screen it covers and how it follows
screen changes, and the compositor check (with real X servers in
test_overlay_x11.py)."""

import copy
import os

import pytest

from PyQt6.QtCore import QObject, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

import config
import overlay
from ballistics import load_weapons, mark_offset, range_ladder
from conftest import ROOT
from i18n import tr
from overlay import Overlay


class FakeScreen(QObject):
    """A monitor: its geometry can change like a QScreen's."""

    geometryChanged = pyqtSignal(QRect)

    def __init__(self, x, y, width, height, name="fake"):
        super().__init__()
        self._geometry = QRect(x, y, width, height)
        self._name = name

    def geometry(self):
        return self._geometry

    def availableGeometry(self):
        return self._geometry

    def name(self):
        return self._name

    def resize(self, width, height):
        self._geometry = QRect(self._geometry.x(), self._geometry.y(), width, height)
        self.geometryChanged.emit(self._geometry)


@pytest.fixture
def real_screen(qapp):
    """Qt's own screen, the argument of the application's screen signals."""
    return QGuiApplication.primaryScreen()


@pytest.fixture
def screens(monkeypatch, real_screen):
    """The list QGuiApplication.screens() returns, primary first."""
    fakes = [FakeScreen(0, 0, 1920, 1080, "DP-1")]

    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: list(fakes)))
    monkeypatch.setattr(QGuiApplication, "primaryScreen", staticmethod(lambda: fakes[0]))

    return fakes


def settle():
    """Let the overlay's zero-timer handle the screen signals."""
    for _ in range(3):
        QApplication.processEvents()


def make_overlay(**settings):
    cfg = copy.deepcopy(config.DEFAULT_CONFIG)
    cfg.update(settings)
    widget = Overlay(cfg)
    return widget


def test_the_overlay_is_a_click_through_frameless_window_on_top():
    widget = make_overlay()

    flags = widget.windowFlags()
    for flag in (
        Qt.WindowType.WindowTransparentForInput,
        Qt.WindowType.WindowStaysOnTopHint,
        Qt.WindowType.FramelessWindowHint,
        Qt.WindowType.Tool,
    ):
        assert flags & flag, flag

    for attribute in (
        Qt.WidgetAttribute.WA_TranslucentBackground,
        Qt.WidgetAttribute.WA_TransparentForMouseEvents,
        Qt.WidgetAttribute.WA_ShowWithoutActivating,
    ):
        assert widget.testAttribute(attribute), attribute

    widget.close()


def test_the_overlay_covers_the_configured_monitor(screens):
    screens.append(FakeScreen(1920, 0, 2560, 1440, "DP-2"))

    first = make_overlay(monitor=0)
    second = make_overlay(monitor=1)

    assert first.geometry() == QRect(0, 0, 1920, 1080)
    assert second.geometry() == QRect(1920, 0, 2560, 1440)
    assert second.screen_width() == 2560

    first.close()
    second.close()


def test_a_monitor_that_is_gone_falls_back_to_the_primary_and_comes_back(screens, real_screen):
    widget = make_overlay(monitor=1)
    assert widget.geometry() == QRect(0, 0, 1920, 1080)

    moved = []
    widget.screen_changed.connect(lambda: moved.append(widget.geometry()))

    # The second monitor is plugged in again.
    screens.append(FakeScreen(1920, 0, 2560, 1440, "DP-2"))
    QGuiApplication.instance().screenAdded.emit(real_screen)
    settle()

    assert widget.geometry() == QRect(1920, 0, 2560, 1440)
    assert moved == [QRect(1920, 0, 2560, 1440)]

    # ... and unplugged.
    screens.pop()
    QGuiApplication.instance().screenRemoved.emit(real_screen)
    settle()

    assert widget.geometry() == QRect(0, 0, 1920, 1080)
    widget.close()


def test_a_resolution_change_resizes_the_overlay(screens):
    widget = make_overlay()
    assert widget.geometry() == QRect(0, 0, 1920, 1080)

    screens[0].resize(2560, 1440)
    settle()

    assert widget.geometry() == QRect(0, 0, 2560, 1440)
    assert widget.center_x == 1280
    widget.close()


def test_a_burst_of_screen_signals_moves_the_overlay_once(screens, real_screen):
    widget = make_overlay()
    moves = []
    widget.screen_changed.connect(lambda: moves.append(1))

    app = QGuiApplication.instance()
    app.screenAdded.emit(real_screen)
    screens[0].resize(1920, 1080)
    app.primaryScreenChanged.emit(real_screen)
    settle()

    assert moves == [1]
    widget.close()


@pytest.fixture
def window(qapp, tmp_path, monkeypatch, screens):
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    yield win
    win.close()


def test_the_mark_and_the_ladder_follow_a_resolution_change(window, screens):
    """After the switch the mark and the ladder are where they would be had
    the app started on the new resolution."""
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("700")
    window.calculate()
    weapon = window.current_weapon()
    full_hd = (window.overlay.offset, list(window.overlay.ladder))

    screens[0].resize(3840, 2160)
    settle()

    assert window.overlay.width() == 3840
    expected = mark_offset(
        weapon, window.last_solution.sight_angle, window.config["fov"], 3840,
        window.config["offset_scale"] / 100
    )
    assert window.overlay.offset == pytest.approx(expected)
    assert window.overlay.offset == pytest.approx(full_hd[0] * 2)

    first, spacing, reach = window.overlay.ladder_bounds()
    assert window.overlay.ladder == range_ladder(
        weapon, window.config["fov"], 3840, first, spacing, reach,
        window.config["offset_scale"] / 100
    )
    assert window.overlay.ladder != full_hd[1]


def test_closing_the_window_closes_the_overlay(window):
    assert window.overlay.isVisible()

    window.close()

    assert not window.overlay.isVisible()


def test_without_a_compositor_the_overlay_stays_hidden_and_says_why(monkeypatch):
    monkeypatch.setattr(overlay, "compositing_active", lambda: False)

    widget = make_overlay()

    assert not widget.isVisible()
    warning = widget.compositor_warning
    assert warning.isVisible()
    assert "compositing" in warning.text()
    assert not warning.isModal()

    # Trying again (the overlay hotkey) shows the same warning, not a second one.
    warning.hide()
    widget.show()
    assert not widget.isVisible()
    assert widget.compositor_warning is warning and warning.isVisible()

    # A compositor was started: the overlay shows; closing it closes the warning.
    monkeypatch.setattr(overlay, "compositing_active", lambda: True)
    widget.show()
    assert widget.isVisible()
    widget.close()
    assert not warning.isVisible()


def test_compositing_that_stops_while_shown_hides_the_overlay_until_it_is_back(monkeypatch):
    """KWin suspends compositing for a fullscreen game that asks for it:
    the overlay must not stay up as a black screen."""
    widget = make_overlay()
    assert widget.isVisible() and widget.compositor_warning is None

    widget.compositing_changed(False)

    assert not widget.isVisible()
    warning = widget.compositor_warning
    assert warning.isVisible() and not warning.isModal()
    assert warning.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    widget.compositing_changed(True)

    assert widget.isVisible()
    assert not warning.isVisible()

    # Turned off by the user: compositing coming back does not show it.
    widget.hide()
    widget.compositing_changed(False)
    widget.compositing_changed(True)
    assert not widget.isVisible()
    assert not warning.isVisible()
    widget.close()


def test_kde_gets_advice_about_blocked_compositing():
    kde = overlay.compositor_advice({"XDG_CURRENT_DESKTOP": "KDE"})
    assert "Allow applications to block compositing" in kde
    assert "Display & Monitor" in kde and "Window Rules" in kde

    for desktop in ("XFCE", "GNOME", "i3", ""):
        other = overlay.compositor_advice({"XDG_CURRENT_DESKTOP": desktop})
        assert "picom" in other and "block compositing" not in other, desktop

    assert overlay.compositor_advice({"XDG_CURRENT_DESKTOP": "ubuntu:KDE"}) == kde


def test_no_compositor_watch_without_x(monkeypatch):
    """The tests' offscreen platform has no X display to watch."""
    widget = make_overlay()

    assert widget.compositor_watch is None
    widget.close()


def test_hiding_never_asks_for_a_compositor(monkeypatch):
    widget = make_overlay()
    monkeypatch.setattr(overlay, "compositing_active", lambda: pytest.fail("checked on hide"))

    widget.hide()

    assert not widget.isVisible()
    assert widget.compositor_warning is None
    widget.close()


def test_only_x11_needs_a_compositing_manager(monkeypatch):
    monkeypatch.setattr(overlay, "x11_compositing_manager_running", lambda: False)

    monkeypatch.setattr(QGuiApplication, "platformName", staticmethod(lambda: "wayland"))
    assert overlay.compositing_active()

    monkeypatch.setattr(QGuiApplication, "platformName", staticmethod(lambda: "xcb"))
    assert not overlay.compositing_active()


def test_no_x_display_counts_as_a_compositor(monkeypatch):
    """A check that cannot run never hides the overlay."""
    monkeypatch.setenv("DISPLAY", ":12345")

    assert overlay.x11_compositing_manager_running()


def painted_pixels(widget):
    image = widget.grab().toImage()
    return sum(
        1
        for y in range(0, image.height(), 2)
        for x in range(0, image.width(), 2)
        if image.pixelColor(x, y).alpha() > 0
    )


def test_an_aim_that_could_not_be_computed_draws_no_mark(screens):
    widget = make_overlay(range_ladder=False)
    widget.setGeometry(0, 0, 400, 300)

    widget.set_offset(40)
    assert widget.mark_visible and painted_pixels(widget) > 0

    widget.set_offset(float("nan"))
    assert not widget.mark_visible
    assert widget.offset == 0.0
    assert painted_pixels(widget) == 0

    widget.close()


@pytest.mark.parametrize("value, top", [(float("inf"), False), (float("-inf"), True)])
def test_an_infinite_aim_points_off_the_screen(screens, value, top):
    widget = make_overlay()
    widget.setGeometry(0, 0, 400, 300)

    widget.set_offset(value)

    assert widget.mark_visible
    assert widget.is_offscreen(widget.offset)
    # Held two screen heights out: far enough for the arrow, and a finite
    # number for the info line's position.
    assert widget.offset == (-600 if top else 600)
    widget.close()


# ---------- the overlay follows the game's window ----------

def test_the_overlay_covers_a_game_window_and_leaves_the_monitor_setting_alone(screens):
    widget = make_overlay(monitor=0)
    moved = []
    widget.screen_changed.connect(lambda: moved.append(widget.geometry()))

    widget.follow_game_window((320, 180, 1280, 720))

    assert widget.geometry() == QRect(320, 180, 1280, 720)
    assert widget.screen_width() == 1280
    assert widget.center_x == 640
    assert widget.config["monitor"] == 0
    assert moved == [QRect(320, 180, 1280, 720)]
    widget.close()


def test_a_game_window_that_fills_its_screen_gives_that_screens_width(screens):
    screens.append(FakeScreen(1920, 0, 2560, 1440, "DP-2"))
    widget = make_overlay(monitor=0)

    widget.follow_game_window((1920, 0, 2560, 1440))

    assert widget.geometry() == screens[1].geometry()
    assert widget.screen_width() == 2560
    widget.close()


def test_a_game_window_on_the_second_monitor_is_covered_whatever_monitor_is_configured(screens):
    screens.append(FakeScreen(1920, 0, 2560, 1440, "DP-2"))
    widget = make_overlay(monitor=0)

    widget.follow_game_window((2240, 360, 1920, 1080))

    assert widget.geometry() == QRect(2240, 360, 1920, 1080)
    assert widget.config["monitor"] == 0
    widget.close()


def test_a_closed_game_window_puts_the_overlay_back_over_the_configured_monitor(screens):
    screens.append(FakeScreen(1920, 0, 2560, 1440, "DP-2"))
    widget = make_overlay(monitor=1)
    moved = []
    widget.screen_changed.connect(lambda: moved.append(widget.geometry()))

    widget.follow_game_window((100, 100, 1280, 720))
    widget.follow_game_window(None)

    assert widget.geometry() == QRect(1920, 0, 2560, 1440)
    assert moved == [QRect(100, 100, 1280, 720), QRect(1920, 0, 2560, 1440)]
    widget.close()


def test_a_moved_and_resized_game_window_is_followed(screens):
    widget = make_overlay()

    widget.follow_game_window((0, 0, 1280, 720))
    widget.follow_game_window((200, 100, 1280, 720))
    assert widget.geometry() == QRect(200, 100, 1280, 720)

    widget.follow_game_window((200, 100, 1920, 1080))
    assert widget.geometry() == QRect(200, 100, 1920, 1080)
    assert widget.screen_width() == 1920
    widget.close()


def test_a_screen_change_leaves_the_overlay_on_the_game_window(screens):
    widget = make_overlay()
    widget.follow_game_window((200, 100, 1280, 720))

    screens[0].resize(2560, 1440)
    settle()

    assert widget.geometry() == QRect(200, 100, 1280, 720)
    widget.close()


def test_the_origin_on_the_screen_is_the_overlays_corner_from_the_screens(screens):
    widget = make_overlay()

    widget.follow_game_window((320, 180, 1280, 720))

    assert widget.origin_on_screen() == (320 - widget.screen().geometry().x(), 180 - widget.screen().geometry().y())
    widget.close()


def test_a_game_window_narrower_than_the_screen_lays_the_mark_for_its_width(window, screens):
    """The overlay at 2560 against a 1920-wide game sent a 1000 m shot to
    1282 m: the mark must be laid for the width of the game's picture."""
    screens[0].resize(2560, 1440)
    settle()
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("1000")
    window.calculate()
    weapon = window.current_weapon()
    sight_angle = window.last_solution.sight_angle
    fov = window.active_fov()
    scale = window.config["offset_scale"] / 100
    assert window.overlay.offset == pytest.approx(mark_offset(weapon, sight_angle, fov, 2560, scale))

    window.overlay.follow_game_window((320, 180, 1920, 1080))

    assert window.overlay.offset == pytest.approx(mark_offset(weapon, sight_angle, fov, 1920, scale))
    assert window.overlay.offset != pytest.approx(mark_offset(weapon, sight_angle, fov, 2560, scale))
    first, spacing, reach = window.overlay.ladder_bounds()
    assert window.overlay.ladder == range_ladder(weapon, fov, 1920, first, spacing, reach, scale)

    window.overlay.follow_game_window(None)

    assert window.overlay.offset == pytest.approx(mark_offset(weapon, sight_angle, fov, 2560, scale))


def test_a_game_window_that_is_not_16_9_is_warned_about_and_a_16_9_one_is_not(window):
    window.overlay.follow_game_window((0, 0, 1280, 1024))

    assert window.screen_ratio_text == tr("screen_not_16_9", size="1280x1024")
    assert not window.screen_ratio_label.isHidden()

    window.overlay.follow_game_window((0, 0, 1280, 720))

    assert window.screen_ratio_text == ""
    assert window.screen_ratio_label.isHidden()


def test_a_game_window_that_is_16_9_raises_no_screen_warning(window):
    window.overlay.follow_game_window((100, 100, 1600, 900))

    assert window.screen_ratio_label.isHidden()
