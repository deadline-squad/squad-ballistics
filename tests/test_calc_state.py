"""Calculator and lay state through the real main window (#3 items 11, 12,
14, 15, 17, the monitor choice of item 2, and the weapon search)."""

import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

import config
from ballistics import load_weapons, solve
from conftest import ROOT
from i18n import STRINGS, tr
from maplink import MapTarget
from widgets import format_angle

from test_ui import AGS17, MORTAR, compass_at, sight_at


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    yield win
    win.close()


class Injector:
    """A key injector that sends nothing (keyinject's interface)."""

    def __init__(self, code):
        self.code = code

    def press(self):
        pass

    def release(self):
        pass

    def close(self):
        pass


def enable_auto_hold(window, monkeypatch, key_reader=lambda code: False):
    import crosshair

    monkeypatch.setattr(crosshair, "system_key_injector", Injector)
    window.controls["auto_hold"].toggled.emit(True)
    window.hold_timer.key_reader = key_reader
    window.hold_timer.set_active(key_reader is not None)


# ---------- item 11: no stale result ----------

def test_clearing_the_distance_without_auto_calc_clears_the_overlay(window):
    window.config["auto_calc"] = False
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.calculate()
    assert window.overlay.info_text.startswith("400 m")

    # Cleared by hand: nothing is solved without auto-calc, but the old
    # shot must not stay on the overlay
    window.distance_entry.setFocus()
    window.distance_entry.selectAll()
    QApplication.sendEvent(
        window.distance_entry,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)
    )
    assert window.distance_entry.text() == ""
    assert window.overlay.info_text == ""
    assert window.last_solution is None
    assert window.status_text() == tr("ready")


def test_switching_the_weapon_without_a_distance_leaves_nothing_behind(window):
    window.config["auto_calc"] = False
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.calculate()
    assert window.overlay.info_text

    # Emptied without an edit signal (as a reset does), then another weapon
    window.distance_entry.setText("")
    window.select_weapon("SPG-9 · FRAG")

    assert window.overlay.info_text == ""
    assert window.last_solution is None
    assert window.status_text() == tr("ready")
    assert window.current_steps == []


# ---------- item 12: a new map target during the lay ----------

def test_a_map_target_during_the_elevation_lay_turns_the_mortar_first(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])

    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    turning, layer = window.bearing_layer, window.sight_layer

    window.auto_hold()
    turning.finish(True)
    assert layer.active and not turning.active

    # Another target with another bearing while the elevation is laid
    window.on_map_targets([MapTarget(900, 4.0, 123.4), MapTarget(700, 2.0, 200.0)])

    assert window.bearing_target() == pytest.approx(200.0)
    assert turning.active, "the new bearing is laid first"
    assert not layer.active
    assert not window.sight_timer.isActive()
    # A restart is not a failure: no cross, no reason
    assert "✗" not in window.overlay.info_text
    assert window.lay_info == ""

    window.auto_hold()
    assert not window.laying()


def test_a_map_target_without_a_lay_starts_nothing(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"

    window.on_map_targets([MapTarget(900, 4.0, 123.4)])

    assert not window.laying()


def test_the_sight_watch_waits_while_the_bearing_is_laid(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])
    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    window.auto_hold()
    assert window.bearing_layer.active and not window.sight_timer.isActive()

    # Anything that refreshes the watch (the weapon, a setting) meanwhile
    window.update_hold_watch()
    window.controls["sight_reader"].toggled.emit(True)

    assert not window.sight_timer.isActive()

    window.auto_hold()
    assert window.sight_timer.isActive()


# ---------- item 14: the overlay says why F7 did nothing ----------

def key_text(window, key):
    return tr(key, key=window.config["hotkeys"]["auto_hold"])


def test_the_auto_lay_key_says_why_it_cannot_run(window, monkeypatch):
    enable_auto_hold(window, monkeypatch, key_reader=None)
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)

    # A weapon that is not laid by a key
    window.select_weapon("SPG-9 · HEAT")
    window.auto_hold()
    assert key_text(window, "lay_key_weapon") in window.overlay.info_text

    # The keyboard cannot be read: the timed lay cannot count
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    window.auto_hold()
    assert key_text(window, "lay_key_no_reader") in window.overlay.info_text

    # Read, but no target
    window.hold_timer.key_reader = lambda code: False
    window.hold_timer.set_active(True)
    window.distance_entry.setText("")
    window.calculate(show_errors=False)
    window.auto_hold()
    assert key_text(window, "lay_key_no_target") in window.overlay.info_text

    # Nothing left: S already held for the whole time
    window.distance_entry.setText("1000")
    window.calculate()
    window.hold_timer.held = window.hold_timer.target + 1
    window.auto_hold()
    assert key_text(window, "lay_key_held") in window.overlay.info_text

    # A mortar's timed lay needs W to raise the barrel first
    window.select_weapon(MORTAR)
    assert window.lay_info == "", "another weapon clears the reason"
    window.distance_entry.setText("1000")
    window.calculate()
    window.hold_timer.auto_hold.reset_injector = None
    window.auto_hold()
    assert key_text(window, "lay_key_no_w") in window.overlay.info_text


def test_the_auto_lay_key_says_when_keys_cannot_be_sent(window):
    window.config["auto_hold"] = True
    window.select_weapon(AGS17)
    window.distance_entry.setText("1000")
    window.calculate()

    assert window.hold_timer.auto_hold is None
    window.auto_hold()
    assert key_text(window, "lay_key_no_keys") in window.overlay.info_text


def test_a_lay_that_starts_shows_no_reason(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    started = []
    monkeypatch.setattr(window.hold_timer.auto_hold, "start",
                        lambda seconds, reset_seconds=0.0: started.append(seconds) or True)
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    window.set_lay_info("old")
    window.auto_hold()

    assert started and window.lay_info == ""


@pytest.mark.parametrize("failure", ["target", "lost", "moves", "stalled", "timeout", "error"])
def test_a_lay_that_stops_short_says_why(window, monkeypatch, failure):
    enable_auto_hold(window, monkeypatch)
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    window.auto_hold()
    layer = window.sight_layer
    assert layer.active

    layer.finish(False, failure)

    from sightlay import MAX_MOVES

    reason = tr("lay_failed", what=tr("lay_elevation"), why=tr(f"lay_why_{failure}", moves=MAX_MOVES))
    assert f"lay_why_{failure}" in STRINGS
    assert reason in window.overlay.info_text
    assert "✗" in window.overlay.info_text

    # The next press of the key starts afresh
    window.auto_hold()
    assert reason not in window.overlay.info_text
    window.auto_hold()


def test_a_bearing_that_stops_short_says_why_and_the_elevation_follows(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])
    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    window.auto_hold()
    window.bearing_layer.finish(False, "stalled")

    reason = tr("lay_failed", what=tr("lay_bearing"), why=tr("lay_why_stalled"))
    assert reason in window.overlay.info_text
    assert window.sight_layer.active

    # The elevation on its target keeps the bearing's reason
    window.sight_layer.finish(True)
    assert reason in window.overlay.info_text


def test_a_bearing_lay_that_ends_on_an_error_does_not_lay_the_elevation(window, monkeypatch):
    """The bearing's lay raised (the keys or the screen failed): the
    elevation's lay is not started on the same keys and screen, the reason
    is shown."""
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])
    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    window.auto_hold()
    assert window.bearing_layer.active
    window.bearing_layer.finish(False, "error")

    assert not window.sight_layer.active
    assert not window.laying()
    assert tr("lay_failed", what=tr("lay_bearing"), why=tr("lay_why_error")) in window.overlay.info_text


def test_no_cross_after_the_player_stops_the_lay(window, monkeypatch):
    enable_auto_hold(window, monkeypatch)
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])
    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    # Stopped while turning
    window.auto_hold()
    window.auto_hold()
    assert "✗" not in window.overlay.info_text
    assert window.lay_info == ""

    # Stopped while laying the elevation
    window.auto_hold()
    window.bearing_layer.finish(True)
    assert window.sight_layer.active
    window.auto_hold()
    assert not window.sight_layer.active
    assert "✗" not in window.overlay.info_text
    assert window.lay_info == ""


# ---------- item 15: units ----------

def test_the_overlay_direct_fire_angle_follows_the_unit_mode(window):
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.set_unit_mode("mil")
    window.calculate()

    direct = window.direct_solution
    assert direct is not None
    assert tr("direct_short", angle=format_angle(direct.sight_angle, "mil")) in window.overlay.info_text
    assert "°" not in window.overlay.info_text.split("  ·  ")[1]


def test_the_elevation_limits_are_in_the_weapons_unit(window):
    window.select_weapon(MORTAR)
    weapon = window.current_weapon()
    low, high = weapon.elevation_limits
    window.config["arc"] = "low"
    window.config["unit_mode"] = "auto"

    # Find a distance the low arc cannot reach within the limits
    for distance in range(100, 1300, 25):
        solution = solve(weapon, distance, 0.0, "low")
        if not solution.reachable and solution.reason_code == "elevation_limit":
            break
    else:
        pytest.skip("no limited low-arc distance for the mortar")

    window.distance_entry.setText(str(distance))
    window.calculate()

    assert weapon.unit == "mil"
    text = window.sub_label.text()
    assert format_angle(low, "mil") in text and format_angle(high, "mil") in text
    assert "°" not in text


# ---------- item 17: calibration after a lay on the sight ----------

def test_a_lay_on_the_sight_cannot_calibrate_the_rate(window, monkeypatch):
    keys = set()
    enable_auto_hold(window, monkeypatch, key_reader=lambda code: code in keys)
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    timer = window.hold_timer
    top = window.current_weapon().hold_elevation[1]

    # A lay from the top by hand: W, then 3 s of S
    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(3.0, s_down=True, w_down=False)
    assert timer.measures_lay

    # The lay on the sight taps W and S itself (the X11 reader sees them)
    window.auto_hold()
    assert window.sight_layer.active
    timer.advance(0.05, s_down=False, w_down=True)
    timer.advance(0.05, s_down=False, w_down=False)
    timer.advance(2.0, s_down=True, w_down=False)
    window.sight_layer.finish(True)

    assert timer.held == pytest.approx(3.0), "the taps are not counted"

    # Mils that would fit 8.5 deg/s on the 2 s of the last tap
    window.lay_entry.setText(f"{(top - 2.0 * 8.5) * 6400 / 360:.4f}")
    assert not window.calibrate_lay()
    assert window.lay_status.text() == tr("lay_after_sight")
    assert MORTAR not in window.config["lay_rates"]

    # W again: a lay from the top calibrates as before
    timer.advance(0.01, s_down=False, w_down=True)
    timer.advance(3.0, s_down=True, w_down=False)
    window.lay_entry.setText(f"{(top - 3.0 * 8.5) * 6400 / 360:.4f}")
    assert window.calibrate_lay()
    assert window.config["lay_rates"][MORTAR] == pytest.approx(8.5, abs=1e-4)


# ---------- the monitor choice (item 2) ----------

class FakeScreen:
    def __init__(self, name, width, height):
        self._name = name
        self.rect = QRect(0, 0, width, height)

    def name(self):
        return self._name

    def geometry(self):
        return self.rect


def test_the_monitor_choice_shows_the_monitor_in_use(window, monkeypatch):
    import crosshair

    left, right = FakeScreen("DP-1", 1920, 1080), FakeScreen("HDMI-1", 2560, 1440)

    class FakeGui:
        @staticmethod
        def screens():
            return [left, right]

        @staticmethod
        def primaryScreen():
            return right

    monkeypatch.setattr(crosshair, "QGuiApplication", FakeGui)

    # A saved monitor that is gone: the overlay is on the primary one
    window.config["monitor"] = 5
    window.rebuild()

    box = window.monitor_box
    assert [box.itemText(i) for i in range(box.count())] == [
        "1: DP-1 (1920×1080)", "2: HDMI-1 (2560×1440)"
    ]
    assert box.currentData() == 1
    assert window.config["monitor"] == 5, "the saved choice is kept"
    assert not window.overlay_card.isHidden()

    # A saved monitor that exists is shown as it is
    window.config["monitor"] = 0
    window.update_monitor_choice()
    assert box.currentData() == 0

    # Down to one monitor: the list follows, the choice is hidden
    FakeGui.screens = staticmethod(lambda: [right])
    window.update_monitor_choice()
    assert box.count() == 1 and box.currentData() == 0
    assert window.overlay_card.isHidden()


def test_the_monitor_list_is_refreshed_without_saving(window):
    saved = []
    window.schedule_save = lambda: saved.append(True)

    window.update_monitor_choice()

    assert saved == []
    assert window.monitor_box.currentData() == 0


# ---------- weapon search (A8) ----------

def search(window, text):
    popup = window.picker.popup
    popup.search.setText(text)
    names = []
    headers = []

    for row in range(popup.list.count()):
        item = popup.list.item(row)
        name = item.data(0x0100)
        if name:
            names.append(name)
        else:
            headers.append(item.text())

    return names, headers, popup.list.currentItem()


@pytest.mark.parametrize("query", ["M1117", "m1117", "AAVP", "aavp-7a1"])
def test_the_vehicle_finds_its_weapon(window, query):
    names, headers, current = search(window, query)

    assert "MK19" in names
    assert tr("found_in_notes").upper() in headers
    # Enter picks it: it is the first (and only) weapon listed
    assert current.data(0x0100) == names[0]


def test_name_matches_come_before_note_matches(window):
    names, headers, current = search(window, "AGS-17")

    by_name = [n for n in names if "ags-17" in n.lower()]
    assert names[:len(by_name)] == by_name
    assert current.data(0x0100) == by_name[0]
    # The MK19's note mentions the AGS-17: listed after, under its header
    assert "MK19" in names[len(by_name):]
    assert headers[-1] == tr("found_in_notes").upper()


def test_notes_match_only_at_a_word_start(window):
    names, _headers, _current = search(window, "ehicle")

    assert names == []


def test_weapon_names_are_unchanged_by_the_search(window):
    from ballistics import load_weapons

    on_file = list(load_weapons(os.path.join(ROOT, "weapons.json")))
    picker_names = [n for _category, names in window.picker.popup.groups for n in names]

    assert sorted(picker_names) == sorted(on_file)


# ---------- inputs and accessibility (#3 items 5, 10) ----------

def test_select_all_then_minus_five_gives_minus_five(window):
    """#3 item 5: over a selection "-" replaces it, it does not flip it."""
    from test_ui import type_text

    entry = window.height_entry
    entry.setText("12.5")
    entry.setFocus()
    entry.selectAll()

    type_text(entry, "-5")

    assert entry.text() == "-5"
    assert entry.value() == -5

    # Without a selection "-" still flips the sign
    entry.setCursorPosition(len(entry.text()))
    type_text(entry, "-")
    assert entry.text() == "5"


def test_icon_only_buttons_have_accessible_names(window):
    assert [b.accessibleName() for b in window.nav_buttons] == [
        tr("nav_calc"), tr("nav_crosshair"), tr("nav_settings"), tr("nav_web")
    ]
    assert [b.accessibleName() for b in window.color_swatches.buttons.values()] == [
        name.capitalize() for name in config.MARK_COLORS
    ]


def test_the_sidebar_icons_are_files_tinted_with_the_text_colour(window):
    import theme
    from utils import resource_path

    for button in window.nav_buttons:
        image = button.icon().pixmap(20, 20).toImage()
        opaque = {
            image.pixelColor(x, y).name()
            for x in range(image.width()) for y in range(image.height())
            if image.pixelColor(x, y).alpha() == 255
        }
        assert opaque == {theme.TEXT.lower()}

    for name in ("bullseye", "crosshairs", "sliders-h", "map"):
        with open(resource_path(f"assets/icons/{name}.svg"), encoding="utf-8") as f:
            svg = f.read()
        assert f'fill="{theme.TEXT}"' in svg
        assert "Font Awesome Free 5.15.4" in svg and "CC BY 4.0" in svg


def toggle_pixels(toggle):
    toggle.resize(toggle.sizeHint())
    return toggle.grab().toImage()


def test_the_toggle_shows_its_edge_off_and_its_focus(window):
    import theme
    from widgets import Toggle

    toggle = Toggle("Switch")

    # Off: the track's edge is the muted colour, 3:1 or more on the card
    image = toggle_pixels(toggle)
    edge = image.pixelColor(3 + 17, 4).name()
    assert theme.contrast(edge, theme.SURFACE) >= 3.0

    # Focused: a ring in the accent colour just outside the track
    toggle.show()
    toggle.activateWindow()
    QApplication.processEvents()
    toggle.setFocus()
    QApplication.processEvents()
    assert toggle.hasFocus()
    ring = toggle_pixels(toggle).pixelColor(1, 13)
    assert ring.name() == theme.ACCENT and ring.alpha() > 200

    toggle.clearFocus()
    QApplication.processEvents()
    assert toggle_pixels(toggle).pixelColor(1, 13).name() != theme.ACCENT
    toggle.close()


def test_the_main_window_module_does_not_import_qtawesome():
    """#1: qtawesome and its qtpy shims cost ~0.17 s of the start for four
    icons; the icons are files now."""
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import crosshair; "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('qtawesome', 'qtpy')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, ROOT],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


# ---------- item 16: a hotkey change does not rebuild the pages ----------

def test_a_hotkey_change_keeps_the_pages_and_names_the_new_key(window):
    settings = window.pages.widget(2)
    status = window.auto_hold_status
    status.setText("kept")
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.calculate()

    window.set_hotkey("toggle_overlay", "F11")

    assert window.pages.widget(2) is settings, "no rebuild"
    assert window.auto_hold_status is status and status.text() == "kept"
    assert "F11" in window.hotkey_hint.text()
    assert window.current_steps[0].startswith(tr("how_overlay_on", hotkey="F11"))

    # The key moves from another action: that one's choice shows None
    window.set_hotkey("auto_hold", "F11")
    assert window.hotkey_boxes["toggle_overlay"].currentData() == ""
    assert window.hotkey_boxes["auto_hold"].currentData() == "F11"
    assert window.controls["auto_hold"].text() == tr("s_auto_hold", key="F11")
    assert window.config["hotkeys"]["toggle_overlay"] == ""

    window.set_hotkey("auto_hold", "")
    assert window.controls["auto_hold"].text() == tr("s_auto_hold", key=tr("hk_none"))
