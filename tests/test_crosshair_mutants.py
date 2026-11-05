"""Behaviour of crosshair.py found by mutation testing (mutmut) that the other
test files did not pin: the texts and values the Calculator page puts on its
labels, the trim, the lay (auto-hold, sight and compass), the settings and the
window rebuild. Every test drives the real main window."""

import math
import os
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import config
from ballistics import TRIM_LIMIT, load_weapons, solve, trim_for_landing
from conftest import ROOT
from i18n import tr
from keystate import KEY_A, KEY_D
from maplink import MapTarget
from sightlay import BEARING, MAX_MOVES

M203 = "M203 / M320 / GP-25 / HK79 / SL40"
AGS = "AGS-17 · emplacement · optic (RMB ×2.5)"
MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    win.overlay.setGeometry(0, 0, 1920, 1080)
    yield win

    # Tests put stand-ins for the lay objects here; close() would call them.
    win.bearing_layer = None
    win.sight_layer = None
    win.close()


def fire_at(window, name, distance, height=""):
    window.select_weapon(name)
    window.distance_entry.setText(str(distance))
    window.height_entry.setText(height)
    window.calculate()


# ---------- the trim ----------

def test_set_trim_stores_the_limited_rounded_trim_and_drops_a_zero_one(window):
    window.select_weapon(M203)

    window.set_trim(0.12345)
    assert window.config["mark_trim"] == {M203: 0.123}

    window.set_trim(9.0)
    assert window.config["mark_trim"] == {M203: TRIM_LIMIT}

    window.set_trim(-0.0004)
    assert window.config["mark_trim"] == {}

    window.set_trim(0.0)
    assert window.config["mark_trim"] == {}


def test_typing_a_trim_stores_it_and_clears_the_status(window):
    window.select_weapon(M203)
    window.trim_status.setText("old status")
    window.trim_entry.setText("0.5")

    window.on_trim_edited()

    assert window.config["mark_trim"] == {M203: 0.5}
    assert window.trim_status.text() == ""
    assert window.trim_entry.text() == "0.5"


def test_an_empty_trim_entry_is_a_zero_trim(window):
    window.select_weapon(M203)
    window.set_trim(0.5)
    window.trim_entry.setText("")

    window.on_trim_edited()

    assert window.config["mark_trim"] == {}


def test_a_trim_over_the_limit_is_shown_as_the_limit_and_one_at_the_limit_is_left_as_typed(window):
    window.select_weapon(M203)

    window.trim_entry.setText("7")
    window.on_trim_edited()
    assert window.config["mark_trim"] == {M203: TRIM_LIMIT}
    assert window.trim_entry.text() == "5"

    window.trim_entry.setText("5.00")
    window.on_trim_edited()
    assert window.trim_entry.text() == "5.00"


def test_resetting_the_trim_removes_it_and_shows_zero(window):
    window.select_weapon(M203)
    window.set_trim(0.5)
    window.show_trim()

    window.reset_trim()

    assert window.config["mark_trim"] == {}
    assert window.trim_entry.text() == "0"


def test_apply_without_a_height_difference_lands_on_the_flat_ground(window):
    fire_at(window, M203, 300)
    window.landed_entry.setText("260")

    window.apply_landing()

    assert window.config["mark_trim"] == {M203: round(trim_for_landing(window.current_weapon(), 300, 0.0, 260), 3)}


def test_apply_uses_the_chosen_arc_and_the_trim_already_set(window):
    window.select_weapon(M203)
    weapon = window.current_weapon()
    window.config["arc"] = "high"
    window.set_trim(0.3)
    window.distance_entry.setText("300")
    window.landed_entry.setText("280")

    window.apply_landing()

    expected = round(trim_for_landing(weapon, 300, 0.0, 280, 0.3, "high"), 3)
    assert window.config["mark_trim"] == {M203: expected}


def test_a_trim_that_reaches_the_limit_is_reported_as_the_limit(window):
    fire_at(window, M203, 300)
    window.landed_entry.setText("100")

    window.apply_landing()

    assert window.config["mark_trim"] == {M203: TRIM_LIMIT}
    assert window.trim_status.text() == tr("trim_set_limit", trim="+5")


def test_a_trim_just_under_the_limit_is_not_reported_as_the_limit(window):
    fire_at(window, M203, 300)
    window.landed_entry.setText("260")

    window.apply_landing()

    assert window.trim_status.text() == tr("trim_set", trim=f"{window.config['mark_trim'][M203]:+g}")


def test_the_lob_of_a_hold_weapon_is_not_applied_where_it_can_reach(window):
    window.select_weapon(AGS)
    window.config["arc"] = "high"
    window.distance_entry.setText("300")
    window.landed_entry.setText("250")

    window.apply_landing()

    assert window.trim_status.text() == tr("trim_lob_refused")
    assert window.config["mark_trim"] == {}


def test_the_direct_fire_of_a_hold_weapon_is_applied_where_the_lob_cannot_reach(window):
    window.select_weapon(AGS)
    weapon = window.current_weapon()
    window.config["arc"] = "high"
    assert not solve(weapon, 100, 0.0, "high").reachable
    window.distance_entry.setText("100")
    window.landed_entry.setText("90")

    window.apply_landing()

    expected = round(trim_for_landing(weapon, 100, 0.0, 90, 0.0, "low"), 3)
    assert window.config["mark_trim"] == {AGS: expected}


def test_a_landing_that_overflows_says_bad_number(window, monkeypatch):
    import crosshair

    def overflow(*_):
        raise OverflowError

    monkeypatch.setattr(crosshair, "trim_for_landing", overflow)
    fire_at(window, M203, 300)
    window.landed_entry.setText("260")

    window.apply_landing()

    assert window.trim_status.text() == tr("bad_number")
    assert window.config["mark_trim"] == {}


# ---------- a target that cannot be hit ----------

MK19 = "MK19"


def explain(window, name, distance, arc, ready_arc=None):
    """Fire at a reachable target first on `ready_arc` (so there is an old
    result to clear), then at the unreachable `distance` on `arc`; return the
    weapon and its solution."""
    window.select_weapon(name)
    window.config["arc"] = ready_arc or arc
    window.distance_entry.setText("300")
    window.calculate()
    assert window.last_solution.reachable

    window.config["arc"] = arc
    window.distance_entry.setText(str(distance))
    window.calculate()
    weapon = window.current_weapon()
    solution = solve(weapon, float(distance), 0.0, arc)
    assert not solution.reachable

    return weapon, solution


def test_a_target_out_of_range_says_the_maximum_range(window):
    weapon, solution = explain(window, M203, 800, "low")

    assert solution.reason_code == "out_of_range"
    assert window.big_label.text() == tr("unreachable")
    assert window.big_label.property("state") == "error"
    assert window.sub_label.text() == tr("how_unreachable_range", max=f"{weapon.max_range():.0f}")


def test_a_target_too_close_says_the_minimum_distance(window):
    weapon, solution = explain(window, MORTAR, 5, "high")

    assert solution.reason_code == "too_close"
    assert window.sub_label.text() == tr("how_unreachable_close", min=f"{weapon.min_distance:g}")


def test_a_lob_the_hold_cannot_lay_says_the_angle_and_the_hold_limits(window):
    """`calculate` fires such a target directly while the low arc reaches it, so
    the explanation is asked for from the solution itself."""
    window.select_weapon(AGS)
    weapon = window.current_weapon()
    solution = solve(weapon, 1933.0, 0.0, "high")
    unit = window.primary_unit(weapon)
    lowest, top = weapon.hold_elevation

    from widgets import format_angle

    assert solution.reason_code == "hold_limit"

    window.show_unreachable(weapon, solution)

    assert window.sub_label.text() == tr(
        "how_unreachable_hold",
        angle=format_angle(solution.angle, unit),
        low=format_angle(lowest, unit),
        high=format_angle(top, unit),
    )


def test_a_target_beyond_the_elevation_limits_says_the_angle_and_the_limits(window):
    weapon, solution = explain(window, MK19, 5, "high", "low")
    unit = window.primary_unit(weapon)
    low, high = weapon.elevation_limits

    from widgets import format_angle

    assert solution.reason_code == "elevation_limit"
    assert window.sub_label.text() == tr(
        "how_unreachable_limit",
        angle=format_angle(solution.angle, unit),
        low=format_angle(low, unit),
        high=format_angle(high, unit),
    )


def test_a_target_in_the_mil_unit_is_explained_in_mils(window):
    window.config["unit_mode"] = "mil"
    weapon, solution = explain(window, MK19, 5, "high", "low")
    low, high = weapon.elevation_limits

    from widgets import format_angle

    assert window.sub_label.text() == tr(
        "how_unreachable_limit",
        angle=format_angle(solution.angle, "mil"),
        low=format_angle(low, "mil"),
        high=format_angle(high, "mil"),
    )


def test_an_unreachable_target_clears_the_overlay_and_the_hold_target(window):
    fire_at(window, AGS, 300)
    assert window.overlay.offset != 0.0
    assert window.overlay.info_text
    assert window.hold_timer.target is not None

    window.distance_entry.setText("3000")
    window.calculate()

    assert window.overlay.offset == 0.0
    assert window.overlay.info_text == ""
    assert window.hold_timer.target is None
    assert all(tile.value.text() == "—" for tile in window.stats.values())


# ---------- calibrating the hold rate of the mortar auto-lay ----------

MILS_PER_DEGREE = 6400 / 360


def mortar_ready_to_calibrate(window, held):
    window.select_weapon(MORTAR)
    window.hold_timer.held = held

    return window.current_weapon().hold_elevation[1]


def mils_for(top, rate, held):
    """The mils the sight shows after `held` seconds of S at `rate` deg/s."""
    return (top - rate * held) * MILS_PER_DEGREE


def test_only_a_weapon_laid_by_elevation_with_a_hold_is_calibrated(window):
    window.select_weapon(AGS)
    window.hold_timer.held = 3.0
    window.lay_entry.setText("1500")

    assert window.calibrate_lay() is False
    assert window.config["lay_rates"] == {}
    assert window.lay_status.text() == ""


def test_without_a_weapon_nothing_is_calibrated_and_no_hold_time_is_needed(window):
    window.picker.current = None
    window.lay_entry.setText("1500")

    assert window.current_weapon() is None
    assert window.calibrate_lay() is False
    assert window.lay_reset_time(None) == 0.0


def test_a_hold_of_exactly_the_minimum_calibrates(window):
    top = mortar_ready_to_calibrate(window, 0.5)
    window.lay_entry.setText(f"{mils_for(top, 9.0, 0.5):.4f}")

    assert window.calibrate_lay() is True


def test_a_rate_off_by_exactly_the_tolerance_is_accepted(window, monkeypatch):
    import crosshair

    monkeypatch.setattr(crosshair, "MILS_PER_DEGREE", 1.0)
    monkeypatch.setattr(crosshair, "LAY_RATE_TOLERANCE", 0.5)
    top = mortar_ready_to_calibrate(window, 2.0)
    window.lay_entry.setText(f"{top - 13.5 * 2.0}")

    assert window.calibrate_lay() is True
    assert window.config["lay_rates"][MORTAR] == 13.5


def test_a_rate_out_of_range_is_refused_with_both_rates_in_the_status(window):
    top = mortar_ready_to_calibrate(window, 3.0)
    typed = f"{mils_for(top, 15.0, 3.0):.1f}"
    window.lay_entry.setText(typed)
    rate = (top - float(typed) / MILS_PER_DEGREE) / 3.0

    assert window.calibrate_lay() is False
    assert window.lay_status.text() == tr("lay_out_of_range", rate=f"{rate:.2f}", base="9")
    assert window.config["lay_rates"] == {}


def test_a_calibrated_rate_is_kept_to_four_decimals_and_reported(window):
    top = mortar_ready_to_calibrate(window, 3.0)
    typed = f"{mils_for(top, 8.123456789, 3.0):.4f}"
    window.lay_entry.setText(typed)
    rate = (top - float(typed) / MILS_PER_DEGREE) / 3.0

    assert window.calibrate_lay() is True
    assert window.config["lay_rates"] == {MORTAR: round(rate, 4)}
    assert window.lay_entry.text() == ""
    assert window.lay_status.text() == tr("lay_done", rate=f"{rate:.2f}", base="9")


def test_resetting_a_rate_that_was_never_calibrated_changes_nothing(window):
    window.select_weapon(MORTAR)
    window.lay_status.setText("kept")

    window.reset_lay_rate()

    assert window.lay_status.text() == "kept"
    assert window.config["lay_rates"] == {}


def test_resetting_a_calibrated_rate_says_the_file_rate(window):
    top = mortar_ready_to_calibrate(window, 3.0)
    window.lay_entry.setText(f"{mils_for(top, 8.5, 3.0):.4f}")
    assert window.calibrate_lay()

    window.reset_lay_rate()

    assert window.config["lay_rates"] == {}
    assert window.lay_status.text() == tr("lay_reset_done", base="9")


def test_the_mortar_needs_a_reset_to_the_top_and_the_ags_does_not(window):
    window.select_weapon(MORTAR)
    mortar = window.current_weapon()
    window.select_weapon(AGS)

    assert window.lay_reset_time(mortar) == mortar.max_hold_time() + 0.3
    assert window.lay_reset_time(window.current_weapon()) == 0.0


# ---------- the sight and the compass on the overlay ----------

def lay_a_mortar_shot(window, distance="1000"):
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText(distance)
    window.calculate()


def test_a_sight_reading_without_a_target_is_shown_with_its_mark(window):
    window.select_weapon(MORTAR)
    reading = SimpleNamespace(mils=1043.44)

    window.show_sight_reading(reading)
    assert window.sight_info == tr("sight_reading", mils="1043.4")

    window.show_sight_reading(reading, "  ✓")
    assert window.sight_info == tr("sight_reading", mils="1043.4") + "  ✓"

    window.show_sight_reading(None)
    assert window.sight_info == ""


def test_a_sight_reading_with_a_target_says_the_mils_left(window):
    lay_a_mortar_shot(window)
    target = window.sight_target()

    window.show_sight_reading(SimpleNamespace(mils=1043.44), "  ✗")

    assert window.sight_info == tr("sight_reading_left", mils="1043.4", left=f"{target - 1043.44:+.1f}") + "  ✗"


def test_the_sight_target_is_the_laid_angle_of_a_hold_weapon_in_mils(window):
    window.select_weapon(M203)
    assert window.sight_target() is None

    window.select_weapon(MORTAR)
    assert window.sight_target() is None

    lay_a_mortar_shot(window)
    assert window.sight_target() == window.last_solution.angle * MILS_PER_DEGREE

    window.config["arc"] = "low"
    window.calculate()
    assert not math.isfinite(window.last_solution.hold_time)
    assert window.sight_target() is None


def test_a_compass_reading_without_a_map_target_is_shown_with_its_mark(window):
    reading = SimpleNamespace(degrees=123.46)

    window.show_bearing_reading(reading)
    assert window.bearing_info == tr("compass_reading", deg="123.5")

    window.show_bearing_reading(reading, "  ✓")
    assert window.bearing_info == tr("compass_reading", deg="123.5") + "  ✓"

    window.show_bearing_reading(None)
    assert window.bearing_info == ""


def test_a_compass_reading_with_a_map_target_says_the_degrees_left(window):
    lay_a_mortar_shot(window)
    window.map_target = MapTarget(900, 4.0, 123.4)

    window.show_bearing_reading(SimpleNamespace(degrees=100.0))

    assert window.bearing_info == tr(
        "compass_reading_left", deg="100.0", left=f"{BEARING.difference(123.4, 100.0):+.1f}"
    )


def test_the_bearing_target_is_the_map_bearing_of_a_laid_mortar_modulo_360(window):
    window.map_target = MapTarget(900, 4.0, 123.4)
    assert window.bearing_target() is None

    lay_a_mortar_shot(window)
    assert window.bearing_target() == 123.4

    window.map_target = MapTarget(900, 4.0, 400.0)
    assert window.bearing_target() == 40.0

    window.map_target = MapTarget(900, 4.0, None)
    assert window.bearing_target() is None

    window.map_target = None
    assert window.bearing_target() is None


def test_a_sight_watch_tick_without_a_bearing_target_clears_the_compass_line(window, monkeypatch):
    lay_a_mortar_shot(window)
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)
    window.set_bearing_info("old compass line")

    window.watch_sight()

    assert window.bearing_info == ""


def test_the_lay_mark_is_a_tick_on_target_a_cross_when_it_stopped_short_and_nothing_when_stopped(window):
    from crosshair import MainWindow

    assert MainWindow.lay_mark(None, True) == "  ✓"
    assert MainWindow.lay_mark(None, False) == "  ✗"
    assert MainWindow.lay_mark(SimpleNamespace(stopped=False), False) == "  ✗"
    assert MainWindow.lay_mark(SimpleNamespace(stopped=True), False) == ""


@pytest.mark.parametrize("failure, why", [
    ("stalled", tr("lay_why_stalled")),
    ("moves", tr("lay_why_moves", moves=MAX_MOVES)),
])
def test_a_lay_that_stopped_short_says_what_and_why(failure, why):
    from crosshair import MainWindow

    text = MainWindow.lay_failure_text(SimpleNamespace(failure=failure), "lay_bearing")

    assert text == tr("lay_failed", what=tr("lay_bearing"), why=why)


def test_a_lay_that_is_on_target_or_was_stopped_has_no_failure_text():
    from crosshair import MainWindow

    assert MainWindow.lay_failure_text(SimpleNamespace(failure=None), "lay_bearing") == ""
    assert MainWindow.lay_failure_text(SimpleNamespace(failure="stopped"), "lay_bearing") == ""


def test_a_finished_bearing_lay_shows_the_compass_and_why_it_stopped(window, monkeypatch):
    lay_a_mortar_shot(window)
    window.bearing_layer = SimpleNamespace(stopped=False, failure="stalled")
    started = []
    monkeypatch.setattr(window, "start_sight_lay", lambda: started.append(True) or False)
    watched = []
    monkeypatch.setattr(window, "update_sight_watch", lambda: watched.append(True))

    window.on_bearing_lay_finished(SimpleNamespace(degrees=12.34), False)

    assert window.bearing_info == tr("compass_reading", deg="12.3") + "  ✗"
    assert window.lay_info == tr("lay_failed", what=tr("lay_bearing"), why=tr("lay_why_stalled"))
    assert started == [True] and watched == [True]


def test_a_finished_bearing_lay_on_target_goes_on_to_the_elevation(window, monkeypatch):
    lay_a_mortar_shot(window)
    window.bearing_layer = SimpleNamespace(stopped=False, failure=None)
    monkeypatch.setattr(window, "start_sight_lay", lambda: True)
    watched = []
    monkeypatch.setattr(window, "update_sight_watch", lambda: watched.append(True))

    window.on_bearing_lay_finished(SimpleNamespace(degrees=12.34), True)

    assert window.bearing_info == tr("compass_reading", deg="12.3") + "  ✓"
    assert window.lay_info == ""
    assert watched == []


@pytest.mark.parametrize("layer", [
    SimpleNamespace(stopped=True, failure=None),
    SimpleNamespace(stopped=False, failure="error"),
])
def test_a_stopped_bearing_lay_does_not_go_on_to_the_elevation(window, monkeypatch, layer):
    window.bearing_layer = layer
    started = []
    monkeypatch.setattr(window, "start_sight_lay", lambda: started.append(True) or True)
    watched = []
    monkeypatch.setattr(window, "update_sight_watch", lambda: watched.append(True))

    window.on_bearing_lay_finished(None, False)

    assert started == [] and watched == [True]


def test_a_bearing_lay_that_finishes_without_a_layer_still_shows_the_compass(window):
    window.select_weapon(MORTAR)
    window.bearing_layer = None

    window.on_bearing_lay_finished(SimpleNamespace(degrees=5.0), True)

    assert window.bearing_info == tr("compass_reading", deg="5.0") + "  ✓"


def test_a_finished_sight_lay_shows_the_mils_beeps_on_target_and_keeps_watching(window, monkeypatch):
    import crosshair

    beeps = []
    monkeypatch.setattr(crosshair, "beep", lambda: beeps.append(True))
    watched = []
    monkeypatch.setattr(window, "update_sight_watch", lambda: watched.append(True))
    window.select_weapon(MORTAR)
    watched.clear()
    window.sight_layer = SimpleNamespace(stopped=False, failure="timeout")

    window.on_sight_lay_finished(SimpleNamespace(mils=1000.0), True)

    assert window.sight_info == tr("sight_reading", mils="1000.0") + "  ✓"
    assert window.lay_info == tr("lay_failed", what=tr("lay_elevation"), why=tr("lay_why_timeout"))
    assert beeps == [True] and watched == [True]

    window.on_sight_lay_finished(SimpleNamespace(mils=1000.0), False)
    assert window.sight_info == tr("sight_reading", mils="1000.0") + "  ✗"
    assert beeps == [True]


def test_a_finished_sight_lay_without_a_layer_leaves_the_lay_info(window, monkeypatch):
    window.sight_layer = None
    window.set_lay_info("bearing failed")

    window.on_sight_lay_finished(SimpleNamespace(mils=1000.0), False)

    assert window.lay_info == "bearing failed"


def test_a_lay_is_running_when_either_layer_is_active(window):
    window.bearing_layer = None
    window.sight_layer = None
    assert window.laying() is False

    window.bearing_layer = SimpleNamespace(active=True)
    assert window.laying() is True

    window.bearing_layer = SimpleNamespace(active=False)
    window.sight_layer = SimpleNamespace(active=True)
    assert window.laying() is True

    window.sight_layer = SimpleNamespace(active=False)
    assert window.laying() is False


def test_the_compass_reader_is_the_layers_or_one_of_its_own_made_once(window):
    from sightlay import CompassReader

    window.bearing_layer = SimpleNamespace(reader="the layer's")
    assert window.compass_reader() == "the layer's"

    window.bearing_layer = None
    window.own_compass_reader = None
    own = window.compass_reader()

    assert isinstance(own, CompassReader)
    assert own.digits.templates is window.templates()
    assert window.compass_reader() is own


def test_the_sight_grab_is_saved_in_the_config_folder_and_a_failure_gives_no_path(window, monkeypatch, tmp_path):
    from PyQt6.QtGui import QImage

    import crosshair

    monkeypatch.setattr(crosshair, "config_dir", lambda: str(tmp_path / "settings"))
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    monkeypatch.setattr(window.screen_sight, "grab_image", lambda: image)

    path = window.save_sight_grab()
    assert path == str(tmp_path / "settings" / "sight-grab.png")
    assert os.path.isfile(path)
    assert window.save_sight_grab() == path

    monkeypatch.setattr(window.screen_sight, "grab_image", lambda: QImage())
    assert window.save_sight_grab() == ""

    monkeypatch.setattr(window.screen_sight, "grab_image", lambda: None)
    assert window.save_sight_grab() == ""


# ---------- the auto-lay hotkey ----------

class KeyRecorder:
    """A key injector that sends nothing and remembers it was closed."""

    made = []

    def __init__(self, code):
        self.code = code
        self.closed = False
        KeyRecorder.made.append(self)

    def press(self):
        pass

    def release(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def keys(monkeypatch):
    import crosshair

    KeyRecorder.made = []
    monkeypatch.setattr(crosshair, "system_key_injector", KeyRecorder)

    return KeyRecorder


def test_the_lay_step_says_how_to_turn_auto_lay_on_while_it_is_off(window):
    window.config["auto_hold"] = False

    assert window.lay_step(2.345) == tr("how_lay_off", t="2.35")


def test_the_lay_step_names_the_hotkey_and_the_time_while_auto_lay_is_on(window, keys):
    window.hold_timer.auto_hold = fake_auto_hold()
    window.config["auto_hold"] = True
    window.config["hotkeys"]["auto_hold"] = "F7"

    assert window.lay_step(2.345) == tr("how_lay", hotkey="F7", t="2.35")

    del window.config["hotkeys"]["auto_hold"]
    assert window.lay_step(2.345) == tr("how_lay", hotkey="", t="2.35")

    window.hold_timer.auto_hold = None
    assert window.lay_step(2.345) == tr("how_lay_off", t="2.35")


def test_the_hotkey_with_nothing_to_lay_says_why_on_the_overlay(window):
    del window.config["hotkeys"]["auto_hold"]
    window.select_weapon(M203)

    window.auto_hold()

    assert window.lay_info == tr("lay_key_weapon", key="")


def fake_auto_hold(reset_injector=object()):
    """What the hold timer calls on its AutoHold, without a worker thread."""
    return SimpleNamespace(
        reset_injector=reset_injector, stop=lambda: None, active=False, injector=None
    )


@pytest.fixture
def mortar_with_keys(window):
    lay_a_mortar_shot(window)
    window.hold_timer.auto_hold = fake_auto_hold()
    window.hold_timer.key_reader = lambda code: False
    window.hold_timer.set_active(True)

    yield window

    window.hold_timer.auto_hold = None
    window.hold_timer.set_active(False)


def test_the_timed_lay_blocker_names_the_first_thing_missing(mortar_with_keys):
    window = mortar_with_keys
    weapon = window.current_weapon()
    timer = window.hold_timer

    assert window.timed_lay_blocker(None) == "lay_key_weapon"
    assert window.timed_lay_blocker(weapon) is None

    timer.auto_hold.reset_injector = None
    assert window.timed_lay_blocker(weapon) == "lay_key_no_w"

    ags = window.weapons[AGS]
    assert window.lay_reset_time(ags) == 0.0
    assert window.timed_lay_blocker(ags) != "lay_key_no_w"

    timer.auto_hold = None
    assert window.timed_lay_blocker(weapon) == "lay_key_no_keys"


def test_a_short_reset_without_the_w_key_blocks_the_timed_lay(mortar_with_keys, monkeypatch):
    window = mortar_with_keys
    window.hold_timer.auto_hold.reset_injector = None
    monkeypatch.setattr(window, "lay_reset_time", lambda weapon: 0.5)

    assert window.timed_lay_blocker(window.current_weapon()) == "lay_key_no_w"

    monkeypatch.setattr(window, "lay_reset_time", lambda weapon: 1.0)
    assert window.timed_lay_blocker(window.current_weapon()) == "lay_key_no_w"


def test_a_key_reader_that_is_off_or_missing_blocks_the_timed_lay(mortar_with_keys):
    window = mortar_with_keys
    weapon = window.current_weapon()
    timer = window.hold_timer

    timer.set_active(False)
    assert timer.available and not timer.active
    assert window.timed_lay_blocker(weapon) == "lay_key_no_reader"

    timer.set_active(True)
    timer.key_reader = None
    assert timer.active and not timer.available
    assert window.timed_lay_blocker(weapon) == "lay_key_no_reader"

    timer.key_reader = lambda code: False
    timer.set_target(None)
    assert window.timed_lay_blocker(weapon) == "lay_key_no_target"


def test_the_hotkey_names_the_blocker_and_the_configured_key(mortar_with_keys):
    window = mortar_with_keys
    window.config["hotkeys"]["auto_hold"] = "F7"
    window.hold_timer.set_target(None)

    window.auto_hold()

    assert window.lay_info == tr("lay_key_no_target", key="F7")


def test_the_hotkey_with_s_already_held_for_the_whole_time_says_so(mortar_with_keys, monkeypatch):
    window = mortar_with_keys
    window.config["hotkeys"]["auto_hold"] = "F7"
    window.config["sight_reader"] = False
    monkeypatch.setattr(window.hold_timer, "toggle_auto_hold", lambda reset=0.0: False)

    window.auto_hold()

    assert window.lay_info == tr("lay_key_held", key="F7")


def test_a_lay_that_cannot_start_on_the_sight_falls_back_to_the_timed_lay(mortar_with_keys, monkeypatch):
    window = mortar_with_keys
    window.config["sight_reader"] = True
    window.bearing_layer = SimpleNamespace(active=False, start=lambda: False)
    window.sight_layer = SimpleNamespace(active=False, start=lambda: False)
    asked = []
    monkeypatch.setattr(window.hold_timer, "toggle_auto_hold", lambda reset=0.0: asked.append(reset) or True)

    window.auto_hold()

    assert asked == [window.lay_reset_time(window.current_weapon())]


def test_the_hotkey_stops_the_bearing_lay_and_then_the_elevation_lay(mortar_with_keys):
    window = mortar_with_keys
    stops = []
    window.bearing_layer = SimpleNamespace(active=True, stop=lambda: stops.append("bearing"))
    window.sight_layer = SimpleNamespace(active=True, stop=lambda: stops.append("sight"))

    window.auto_hold()
    window.bearing_layer.active = False
    window.auto_hold()

    assert stops == ["bearing", "sight"]


def test_the_hotkey_turns_to_the_bearing_first_and_stops_the_sight_watch(mortar_with_keys):
    window = mortar_with_keys
    window.config["sight_reader"] = True
    window.sight_timer.start()
    window.bearing_layer = SimpleNamespace(active=False, start=lambda: True)
    window.sight_layer = SimpleNamespace(active=False, start=lambda: False)

    window.auto_hold()

    assert not window.sight_timer.isActive()


def test_the_hotkey_starts_the_elevation_lay_on_the_sight(mortar_with_keys):
    window = mortar_with_keys
    window.config["sight_reader"] = True
    window.sight_timer.start()
    window.bearing_layer = None
    window.sight_layer = SimpleNamespace(active=False, start=lambda: True)

    window.auto_hold()

    assert not window.sight_timer.isActive()
    assert window.lay_info == ""


def test_the_hotkey_releases_a_hold_the_app_is_making(mortar_with_keys, monkeypatch):
    window = mortar_with_keys
    toggled = []
    monkeypatch.setattr(type(window.hold_timer), "auto_holding", property(lambda self: True))
    monkeypatch.setattr(window.hold_timer, "toggle_auto_hold", lambda reset=0.0: toggled.append(reset))

    window.auto_hold()

    assert toggled == [0.0]


def test_a_sight_lay_that_starts_suspends_the_hold_timer(window, monkeypatch):
    suspended = []
    monkeypatch.setattr(window.hold_timer, "suspend", lambda: suspended.append(True))

    window.sight_layer = None
    assert window.start_sight_lay() is False

    window.sight_layer = SimpleNamespace(start=lambda: False)
    assert window.start_sight_lay() is False
    assert suspended == []

    window.sight_timer.start()
    window.sight_layer = SimpleNamespace(start=lambda: True)
    assert window.start_sight_lay() is True
    assert suspended == [True]
    assert not window.sight_timer.isActive()


def test_the_bearing_layer_is_made_when_both_turn_keys_can_be_sent(window, keys):
    window.select_weapon(MORTAR)
    window.make_bearing_layer()

    layer = window.bearing_layer
    right, left = keys.made

    assert (right.code, left.code) == (KEY_D, KEY_A)
    assert layer.raise_key is right and layer.lower_key is left
    assert layer.axis is BEARING
    assert layer.target == window.bearing_target
    assert layer.parent() is window
    assert layer.templates is window.templates()
    assert layer.reader.digits.templates is window.templates()
    assert not right.closed and not left.closed

    layer.read.emit(SimpleNamespace(degrees=12.34))
    assert window.bearing_info == tr("compass_reading", deg="12.3")

    layer.finished.emit(SimpleNamespace(degrees=1.0), True)
    assert window.bearing_info == tr("compass_reading", deg="1.0") + "  ✓"


@pytest.mark.parametrize("missing", ["right", "left"])
def test_without_both_turn_keys_the_one_that_exists_is_closed(window, monkeypatch, missing):
    import crosshair

    made = []

    def injector(code):
        if (code == KEY_D) == (missing == "right") or (code == KEY_A) == (missing == "left"):
            return None
        key = KeyRecorder(code)
        made.append(key)
        return key

    monkeypatch.setattr(crosshair, "system_key_injector", injector)
    window.bearing_layer = None

    window.make_bearing_layer()

    assert window.bearing_layer is None
    assert len(made) == 1 and made[0].closed


def test_the_sight_layer_is_wired_to_the_window_when_both_lay_keys_can_be_sent(window, keys):
    window.config["auto_hold"] = True

    assert window.apply_auto_hold() is True

    layer = window.sight_layer
    assert layer.target == window.sight_target
    assert layer.parent() is window
    assert layer.templates is window.templates()
    assert window.hold_timer.auto_hold.reset_injector is not None

    layer.read.emit(SimpleNamespace(mils=1000.0))
    assert window.sight_info == tr("sight_reading", mils="1000.0")


def test_switching_auto_hold_on_where_keys_cannot_be_sent_turns_it_back_off(window, monkeypatch):
    import crosshair

    monkeypatch.setattr(crosshair, "system_key_injector", lambda code: None)
    calls = []
    monkeypatch.setattr(crosshair, "teardown_hotkeys", lambda target: calls.append(("down", target)))
    monkeypatch.setattr(crosshair, "setup_hotkeys", lambda target: calls.append(("up", target)))
    toggle = window.controls["auto_hold"]
    toggle.setChecked(True)
    toggle.toggled.emit(True)

    assert window.config["auto_hold"] is False
    assert not toggle.isChecked()
    assert window.auto_hold_status.text() == tr("auto_hold_unavailable")
    assert calls[:2] == [("down", window), ("up", window)]


def test_switching_auto_hold_on_where_keys_can_be_sent_keeps_it_on(window, keys):
    toggle = window.controls["auto_hold"]
    toggle.setChecked(True)
    toggle.toggled.emit(True)

    assert window.config["auto_hold"] is True
    assert toggle.isChecked()
    assert window.auto_hold_status.text() == ""


# ---------- the overlay view, the target and the hotkeys that move it ----------

AGS_OPTIC = AGS
AGS_PLAIN = "AGS-17 · emplacement · no optic"


def test_the_view_tag_names_the_optic_the_plain_view_or_nothing(window):
    from crosshair import MainWindow

    assert MainWindow.view_tag(window.weapons[AGS_OPTIC]) == tr("info_view_optic", zoom="2.5")
    assert MainWindow.view_tag(window.weapons[AGS_PLAIN]) == tr("info_view_plain")
    assert MainWindow.view_tag(window.weapons[M203]) == ""


def test_the_overlay_view_step_names_the_other_view_and_the_fov(window):
    optic, plain = window.weapons[AGS_OPTIC], window.weapons[AGS_PLAIN]

    assert window.how_overlay_view(optic, 90.0) == tr(
        "how_view_optic", zoom="2.5", twin=optic.twin, fov="90"
    )
    assert window.how_overlay_view(plain, 90.0) == tr("how_view_plain", twin=AGS_OPTIC, fov="90")


def test_toggling_the_view_picks_the_twin_and_ignores_a_weapon_without_one(window):
    window.select_weapon(AGS_OPTIC)

    window.toggle_view()
    assert window.picker.current == AGS_PLAIN

    window.toggle_view()
    assert window.picker.current == AGS_OPTIC

    window.select_weapon(M203)
    window.toggle_view()
    assert window.picker.current == M203


def test_resetting_the_target_clears_the_result_the_map_target_and_the_mark(window):
    fire_at(window, AGS, 300)
    window.config["arc"] = "high"
    window.calculate()
    window.map_target = MapTarget(300, 0.0, 10.0)
    assert window.direct_solution is not None
    assert window.overlay.offset != 0.0

    window.reset_offset()

    assert window.distance_entry.text() == ""
    assert window.map_target is None
    assert window.last_solution is None
    assert window.direct_solution is None
    assert window.overlay.offset == 0.0
    assert window.info_base == ""


def test_editing_the_distance_forgets_the_map_target_and_solves_after_a_pause(window):
    window.map_target = MapTarget(300, 0.0, 10.0)
    window.select_weapon(M203)

    window.distance_entry.textEdited.emit("200")

    assert window.map_target is None
    assert window.calc_timer.isActive()


def test_editing_the_fov_keeps_the_map_target(window):
    window.map_target = MapTarget(300, 0.0, 10.0)

    window.fov_entry.textEdited.emit("90")

    assert window.map_target is not None


def test_without_auto_calc_an_emptied_distance_clears_the_result_without_an_error(window):
    window.config["auto_calc"] = False
    window.select_weapon(M203)
    window.distance_entry.setText("")

    window.on_input_edited()

    assert not window.calc_timer.isActive()
    assert window.big_label.text() == tr("ready")
    assert window.big_label.property("state") == ""


def test_without_auto_calc_a_typed_distance_waits_for_calculate(window):
    window.config["auto_calc"] = False
    window.select_weapon(M203)
    window.distance_entry.setText("300")

    window.on_input_edited()

    assert window.last_solution is None


def test_changing_the_arc_stores_it_and_clears_the_trim_status(window):
    window.select_weapon(M203)
    window.trim_status.setText("old status")

    window.on_arc_changed("high")

    assert window.config["arc"] == "high"
    assert window.trim_status.text() == ""
    assert window.trim_entry.placeholderText() == tr("trim_hint_high")


def test_the_distance_hotkeys_step_the_distance_and_forget_the_map_target(window):
    window.select_weapon(M203)
    window.config["distance_step"] = 25
    window.distance_entry.setText("100")
    window.map_target = MapTarget(100, 0.0, 10.0)

    window.distance_up()
    assert window.distance_entry.text() == "125"
    assert window.map_target is None
    assert window.last_solution is not None

    window.map_target = MapTarget(100, 0.0, 10.0)
    window.distance_down()
    window.distance_down()
    assert window.distance_entry.text() == "75"
    assert window.map_target is None


def test_a_crosshair_setting_is_stored(window):
    window.set_setting("offset_scale", 120)

    assert window.config["offset_scale"] == 120


def test_a_monitor_that_is_added_is_listed_and_followed(window):
    connected = []
    screen = SimpleNamespace(geometryChanged=SimpleNamespace(connect=connected.append))

    window.watch_screen(screen)

    assert connected == [window.update_monitor_choice]


def test_the_settings_folder_is_opened_or_its_path_is_shown(window, monkeypatch, tmp_path):
    import crosshair

    folder = tmp_path / "settings"
    monkeypatch.setattr(crosshair, "config_dir", lambda: str(folder))
    opened = []
    answers = [True, False]
    monkeypatch.setattr(
        crosshair.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or answers.pop(0)
    )
    window.open_status.setText("old")
    window.open_status.show()

    window.open_config_dir()
    assert opened == [str(folder)]
    assert folder.is_dir()
    assert window.open_status.isHidden()

    window.open_config_dir()
    assert window.open_status.text() == tr("open_failed", target=str(folder))
    assert not window.open_status.isHidden()


def test_keeping_the_window_on_top_sets_the_flag(window):
    from PyQt6.QtCore import Qt

    window.set_on_top(True)
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    window.set_on_top(False)
    assert not window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_the_distance_step_goes_to_both_distance_fields_and_the_config(window):
    window.set_distance_step(50)

    assert window.config["distance_step"] == 50
    assert window.distance_entry.step == 50
    assert window.landed_entry.step == 50
    assert window.save_timer.isActive()


def test_the_chosen_monitor_is_stored(window):
    window.set_monitor(1)

    assert window.config["monitor"] == 1
    assert window.save_timer.isActive()


def test_binding_a_hotkey_takes_it_from_the_action_that_had_it_and_leaves_the_lists_quiet(window):
    heard = []

    for box in window.hotkey_boxes.values():
        box.currentIndexChanged.connect(lambda index: heard.append(index))

    other = next(name for name in window.hotkey_boxes if name != "auto_hold")
    window.set_hotkey(other, "F9")
    window.set_hotkey("auto_hold", "F9")

    assert window.config["hotkeys"]["auto_hold"] == "F9"
    assert window.config["hotkeys"][other] == ""
    assert window.hotkey_boxes[other].currentData() == ""
    assert window.hotkey_boxes["auto_hold"].currentData() == "F9"
    assert heard == []
    assert not any(box.signalsBlocked() for box in window.hotkey_boxes.values())


# ---------- the settings that restart or rebuild ----------

@pytest.fixture
def asked(monkeypatch):
    """Replace the confirmation box; `asked.answer` is what the player says."""
    import crosshair
    from PyQt6.QtWidgets import QMessageBox

    class Box:
        StandardButton = QMessageBox.StandardButton
        answer = QMessageBox.StandardButton.Yes
        calls = []

        @classmethod
        def question(cls, *args):
            cls.calls.append(args)
            return cls.answer

    Box.calls = []
    monkeypatch.setattr(crosshair, "QMessageBox", Box)

    return Box


def test_resetting_the_settings_asks_first_and_does_nothing_on_no(window, asked):
    from PyQt6.QtWidgets import QMessageBox

    asked.answer = QMessageBox.StandardButton.No
    window.config["offset_scale"] = 120

    window.reset_settings()

    assert asked.calls == [(window, "Squad Ballistics", tr("s_reset_confirm"))]
    assert window.config["offset_scale"] == 120


def test_resetting_the_settings_restores_the_defaults_without_sharing_them(window, asked, monkeypatch):
    import crosshair

    saved = []
    monkeypatch.setattr(crosshair, "save_config", lambda config: saved.append(dict(config)))
    on_top = []
    monkeypatch.setattr(window, "set_on_top", on_top.append)
    window.config["offset_scale"] = 120
    window.config["mark_trim"] = {M203: 0.5}

    window.reset_settings()

    assert window.config["offset_scale"] == crosshair.DEFAULT_CONFIG["offset_scale"]
    assert window.config["mark_trim"] == {}
    assert window.config["hotkeys"] is not crosshair.DEFAULT_CONFIG["hotkeys"]
    assert on_top == [False]
    assert saved and saved[-1]["offset_scale"] == crosshair.DEFAULT_CONFIG["offset_scale"]
    assert window.fov_entry.value() == window.config["fov"]


def test_resetting_the_settings_reloads_the_map_only_when_its_address_changes(window, asked, monkeypatch):
    reloads = []
    monkeypatch.setattr(window.map_page, "load_source", lambda: reloads.append(True))

    window.reset_settings()
    assert reloads == []

    window.config["map_source"] = "squadcalc"
    window.reset_settings()
    assert reloads == [True]


def test_rebuilding_keeps_the_typed_inputs_the_page_and_the_map(window):
    from PyQt6 import sip
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QEvent

    window.select_weapon(M203)
    window.distance_entry.setText("300")
    window.height_entry.setText("12")
    window.fov_entry.setText("95")
    window.set_page(2)
    page = window.map_page

    window.rebuild()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert (window.distance_entry.text(), window.height_entry.text(), window.fov_entry.text()) == ("300", "12", "95")
    assert window.pages.currentIndex() == 2
    assert window.map_page is page and not sip.isdeleted(page)
    assert window.pages.indexOf(page) == 3
    assert window.last_solution is not None


def test_changing_the_map_render_saves_it_and_restarts_or_rebuilds(window, asked, monkeypatch):
    import crosshair
    from PyQt6.QtWidgets import QMessageBox

    saved = []
    monkeypatch.setattr(crosshair, "save_config", lambda config: saved.append(config["map_render"]))
    restarted, rebuilt = [], []
    monkeypatch.setattr(window, "restart", lambda: restarted.append(True))
    monkeypatch.setattr(window, "rebuild", lambda: rebuilt.append(True))
    window.config["map_render"] = "auto"

    window.set_map_render("auto")
    assert asked.calls == [] and saved == []

    window.set_map_render("software")
    assert window.config["map_render"] == "software"
    assert saved == ["software"]
    assert asked.calls == [(window, tr("restart_title"), tr("restart_text"))]
    assert restarted == [True] and rebuilt == []

    asked.answer = QMessageBox.StandardButton.No
    window.set_map_render("auto")
    assert restarted == [True] and rebuilt == [True]


def test_restarting_starts_a_new_instance_with_the_same_arguments_and_quits(window, monkeypatch):
    import sys

    import crosshair

    started, quits = [], []
    monkeypatch.setattr(crosshair.QProcess, "startDetached", lambda program, arguments: started.append((program, arguments)))
    monkeypatch.setattr(crosshair.QApplication, "quit", lambda: quits.append(True))
    monkeypatch.setattr(sys, "argv", ["app.py", "--flag", "value"])
    monkeypatch.setattr(window, "close", lambda: quits.append("closed"))

    window.restart()

    assert started == [(sys.executable, [os.path.abspath("app.py"), "--flag", "value"])]
    assert quits == ["closed", True]


def test_following_the_map_preloads_it_on_the_next_turn_of_the_event_loop(window, monkeypatch):
    import crosshair

    calls = []
    monkeypatch.setattr(window.map_page, "update_polling", lambda: calls.append("polling"))
    monkeypatch.setattr(
        crosshair.QTimer, "singleShot", lambda delay, slot: calls.append((delay, slot))
    )

    window.on_map_follow_changed(True)
    assert calls == ["polling", (0, window.preload_map)]

    calls.clear()
    window.on_map_follow_changed(False)
    assert calls == ["polling"]


@pytest.mark.parametrize("follow, external, loads", [
    (True, False, 1),
    (False, False, 0),
    (True, True, 0),
    (False, True, 0),
])
def test_the_map_is_preloaded_only_when_followed_and_not_opened_in_the_browser(window, monkeypatch, follow, external, loads):
    calls = []
    monkeypatch.setattr(window.map_page, "ensure_loaded", lambda: calls.append(True))
    window.config["map_follow"] = follow
    window.config["map_external"] = external

    window.preload_map()

    assert len(calls) == loads


def test_the_picker_groups_the_weapons_by_category_in_file_order(window):
    groups = window.weapon_groups()
    first_category = next(iter(window.weapons.values())).category

    assert groups[0][0] == first_category
    assert groups[0][1][0] == next(iter(window.weapons))
    assert [name for _, names in groups for name in names] == list(window.weapons)
    assert all(
        window.weapons[name].category == category for category, names in groups for name in names
    )
