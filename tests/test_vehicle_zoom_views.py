"""Every sight mode of the vehicle and emplacement guns the app models, and the Focus key.

A gunner's sight with several zoom levels has one entry per level, named after its
vehicle and zoom; the snapshot tests/data/game_weapons.json (written by
tools/game_weapons.py from the game files) holds each mount's `ZoomLevels` and whether
holding Focus narrows the view, so none of these values is read from weapons.json.
"""

import json
import math
import os

import pytest

import config
from ballistics import (
    FOCUS_FOV_FACTOR,
    load_weapons,
    mark_offset,
    screen_offset,
    solve,
)
from conftest import ROOT
from i18n import tr
from keystate import KEY_LEFTSHIFT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    _SNAPSHOT = json.load(_file)

GAME = {k: v for k, v in _SNAPSHOT.items() if not k.startswith("_")}
FOCUS_ENTRIES = sorted(n for n in GAME if GAME[n].get("focus_narrows_view"))
GUNNER_SIGHTS = sorted(n for n in WEAPONS if "gunner sight ×" in n)
LEVEL_ENTRIES = sorted(n for n in GAME if "zoom_levels" in GAME[n])

FOV = 120
WIDTH = 1920


def test_the_m1117_mk19_has_its_second_zoom_level():
    """ZoomLevels [1, 4.5]: at ×4.5 the view is FOV / 4.5 wide and the mark is the focal length
    of that view times the tangent of the angle over the line of sight, less the bore."""
    weapon = WEAPONS["MK19 · M1117 · gunner sight ×4.5"]
    assert GAME[weapon.name]["zoom_levels"] == [1.0, 4.5]

    for distance in (200, 500, 800):
        solution = solve(weapon, distance, 0.0, "low")
        view_fov = FOV / 4.5
        focal = (WIDTH / 2) / math.tan(math.radians(view_fov) / 2)

        expected = focal * math.tan(math.radians(solution.sight_angle - weapon.bore))

        assert mark_offset(weapon, solution.sight_angle, FOV, WIDTH) == pytest.approx(expected)

    first_level = WEAPONS["MK19"]
    assert first_level.zoom == 0
    assert mark_offset(weapon, 3.0, FOV, WIDTH) > 4 * mark_offset(first_level, 3.0, FOV, WIDTH)


@pytest.mark.parametrize("name", LEVEL_ENTRIES)
def test_a_gunner_sights_zoom_is_one_of_its_mounts_zoom_levels(name):
    game, weapon = GAME[name], WEAPONS[name]

    assert game["zoom"] in game["zoom_levels"]
    assert (weapon.zoom or 1.0) == pytest.approx(game["zoom"])


@pytest.mark.parametrize("name", GUNNER_SIGHTS)
def test_a_gunner_sights_name_gives_its_zoom(name):
    zoom = float(name.rsplit("gunner sight ×", 1)[1])

    assert WEAPONS[name].zoom == pytest.approx(zoom)
    assert zoom in GAME[name]["zoom_levels"]


def test_no_name_shows_a_class_name():
    for name in WEAPONS:
        assert "BP_" not in name, name


def test_no_note_of_a_gunner_sight_shows_a_class_name():
    for name in GUNNER_SIGHTS:
        assert "BP_" not in WEAPONS[name].note, name


def test_the_names_of_the_gunner_sights_are_the_vehicles_players_know():
    for name in GUNNER_SIGHTS:
        assert "(+" not in name and "Turret" not in name, name
        assert not name.startswith("Tank HEAT/HE · M256 / Rh120 / 2A46"), name


@pytest.mark.parametrize("name, bore, limits", [
    ("Tank AP · Sprut-SDM1 (2A45) · gunner sight ×4", 0.29, (-5.61, 14.39)),
    ("Tank AP · Sprut-SDM1 (2A45) · gunner sight ×12", 0.29, (-5.61, 14.39)),
    ("Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×4", 0.29, (-5.61, 14.39)),
    ("Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×12", 0.29, (-5.61, 14.39)),
    ("Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3", 0.28, (-5.62, 14.38)),
    ("QLZ87 · ZBL08 · optic (RMB ×3)", 0.85, (-11.65, 68.35)),
    ("QLZ87 · ZBL08 · no optic", 0.85, (-11.65, 68.35)),
    ("QLZ87 · Lynx · no optic", 0.85, (-13.15, 55.85)),
    ("QLZ87 · CSK131 / WZ551 · no optic", 0.85, (-13.15, 55.85)),
    ("QLZ87 · bunker tripod · optic (RMB ×3)", 0.774, (-20.9, 25.1)),
    ("QLZ87 · bunker tripod · no optic", -0.9, (-20.9, 25.1)),
    ("QLZ87 · no optic", -0.9, (-23.4, 44.1)),
    ("AGS-17 · emplacement · optic (RMB ×2.5)", 0.85, (-12.15, 85.85)),
    ("AGS-17 · emplacement · no optic", 0.85, (-12.15, 85.85)),
    ("AGS-17 · iron sights emplacement", 4.5, (-8.5, 89.5)),
    ("MK19 · RHIB open turret · no sights", 0.0, (-20.0, 30.0)),
])
def test_the_mismatches_the_audit_found_are_the_games_values(name, bore, limits):
    weapon = WEAPONS[name]

    assert weapon.bore == pytest.approx(bore, abs=0.005)
    assert weapon.elevation_limits == pytest.approx(limits)
    assert GAME[name]["elevation_limits"] == pytest.approx(limits)


def test_a_hold_weapons_top_is_the_mount_limit_plus_the_socket():
    for name in ("AGS-17 · emplacement · optic (RMB ×2.5)", "AGS-17 · emplacement · no optic", "AGS-17 · iron sights emplacement"):
        weapon = WEAPONS[name]

        assert weapon.hold_elevation[1] == pytest.approx(weapon.elevation_limits[1])


def test_the_frag_and_he_rounds_the_game_does_not_turn_along_their_path_say_so():
    for name, game in GAME.items():
        if game["elevation_limits"] is not None and not game["acceleration"]:
            assert WEAPONS[name].rotation_follows_velocity == game["rotation_follows_velocity"], name


def test_the_qlz87_pairs_are_twins_of_their_own_vehicle():
    for vehicle in ("Lynx", "CSK131 / WZ551", "ZBL08", "bunker tripod"):
        optic = WEAPONS[f"QLZ87 · {vehicle} · optic (RMB ×3)"]

        assert optic.twin == f"QLZ87 · {vehicle} · no optic"
        assert WEAPONS[optic.twin].view == "plain"


def test_a_saved_lynx_csk131_weapon_still_loads():
    from ballistics import current_weapon_name

    assert current_weapon_name("QLZ87 · Lynx / CSK131 · optic (RMB ×3)") in WEAPONS
    assert current_weapon_name("QLZ87 · Lynx / CSK131 · no optic") in WEAPONS
    assert current_weapon_name("QLZ87 · Lynx / CSK131") in WEAPONS


# ---- Focus ----------------------------------------------------------------------------------

def test_the_focus_factor_is_the_games():
    assert _SNAPSHOT["_source"]["focus_view_factor"] == FOCUS_FOV_FACTOR == 0.666


def test_the_entries_the_game_marks_for_focus_are_marked():
    assert FOCUS_ENTRIES
    assert sorted(n for n, w in WEAPONS.items() if w.focus_narrows_view) == FOCUS_ENTRIES


@pytest.mark.parametrize("name", FOCUS_ENTRIES)
def test_a_marked_view_is_a_plain_one(name):
    assert WEAPONS[name].zoom == 0
    assert WEAPONS[name].view in ("", "plain")


@pytest.mark.parametrize("name", FOCUS_ENTRIES)
def test_held_focus_narrows_a_marked_view_to_0_666_of_the_fov(name):
    weapon = WEAPONS[name]

    assert weapon.sight_view(FOV) == (FOV, weapon.bore)
    assert weapon.sight_view(FOV, focus=True) == (pytest.approx(FOV * 0.666), weapon.bore)


@pytest.mark.parametrize("name", [n for n in WEAPONS if not WEAPONS[n].focus_narrows_view])
def test_held_focus_changes_no_other_view(name):
    weapon = WEAPONS[name]

    assert weapon.sight_view(FOV, focus=True) == weapon.sight_view(FOV)


def test_the_mark_of_a_marked_view_follows_focus():
    weapon = WEAPONS["AGS-17 · Technical"]
    solution = solve(weapon, 600, 0.0, "low")

    plain = mark_offset(weapon, solution.sight_angle, FOV, WIDTH)
    focused = mark_offset(weapon, solution.sight_angle, FOV, WIDTH, focus=True)
    expected = screen_offset(solution.sight_angle - weapon.bore, FOV * 0.666, WIDTH)

    assert focused == pytest.approx(expected)
    assert focused == pytest.approx(plain * math.tan(math.radians(FOV / 2)) / math.tan(math.radians(FOV * 0.666 / 2)), rel=0.02)


def test_the_mark_of_an_unmarked_view_ignores_focus():
    weapon = WEAPONS["AGS-17 · emplacement · no optic"]

    assert mark_offset(weapon, 3.0, FOV, WIDTH, focus=True) == mark_offset(weapon, 3.0, FOV, WIDTH)


@pytest.mark.parametrize("name", [
    "QLZ87 · no optic",
    "QLZ87 · bunker tripod · no optic",
    "QLZ87 · CSK131 / WZ551 · no optic",
    "QLZ87 · ZBL08 · no optic",
    "AGS-17 · emplacement · no optic",
    "SPG-9 · HEAT · scope · no optic",
    "SPG-9 · HEAT · technical · no optic",
    "ZiS-3 · no optic",
])
def test_the_mounts_that_do_not_allow_focus_are_not_marked(name):
    """The mount leaves AllowFocus / bAllowFocus false (the CSK131, WZ551 and ZBL-08 QLZ turrets, the
    scope and optic tripods, the technical's SPG-9) or never sets bAllowFocus (the QLZ87 and ZiS-3 tripods)."""
    assert not WEAPONS[name].focus_narrows_view


def test_a_zoomed_view_cannot_be_marked_for_focus():
    from ballistics import Weapon, WeaponDataError

    with pytest.raises(WeaponDataError):
        Weapon.from_dict("x", {"velocity": 100, "zoom": 3, "focus_narrows_view": True})

    with pytest.raises(WeaponDataError):
        Weapon.from_dict("x", {"velocity": 100, "focus_narrows_view": "yes"})


# ---- The window follows the key ---------------------------------------------------------------

@pytest.fixture
def focus_window(qapp, tmp_path, monkeypatch):
    """The main window wired to a key reader that answers from the set `pressed`."""
    import crosshair

    pressed = set()
    monkeypatch.setattr(crosshair, "system_key_reader", lambda: (lambda code: code in pressed))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    win = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    win.fov_entry.setText("120")

    yield win, pressed

    win.close()


def lay(window, name, distance="300"):
    window.select_weapon(name)
    window.distance_entry.setText(distance)
    window.height_entry.setText("")
    window.calculate()


def test_the_mark_follows_the_focus_key(focus_window):
    window, pressed = focus_window
    lay(window, "AGS-17 · Technical", "600")
    weapon = window.current_weapon()
    width = window.overlay.screen_width()
    scale = window.config["offset_scale"] / 100
    angle = window.direct_solution.sight_angle

    assert window.focus_timer.isActive()
    assert window.overlay.offset == pytest.approx(mark_offset(weapon, angle, FOV, width, scale))

    plain = window.overlay.offset
    pressed.add(KEY_LEFTSHIFT)
    window.focus_timer.timeout.emit()

    assert window.overlay.offset == pytest.approx(mark_offset(weapon, angle, FOV, width, scale, focus=True))
    assert window.overlay.offset > 1.8 * plain
    assert tr("info_focus_follows") in window.overlay.info_text

    pressed.discard(KEY_LEFTSHIFT)
    window.focus_timer.timeout.emit()

    assert window.overlay.offset == pytest.approx(plain)


def test_the_ladder_follows_the_focus_key_too(focus_window):
    window, pressed = focus_window
    lay(window, "AGS-17 · Technical")

    plain = list(window.overlay.ladder)
    pressed.add(KEY_LEFTSHIFT)
    window.focus_timer.timeout.emit()

    assert window.overlay.ladder != plain


def test_a_view_focus_does_not_narrow_ignores_the_key(focus_window):
    window, pressed = focus_window
    lay(window, "AGS-17 · emplacement · no optic")

    assert not window.focus_timer.isActive()

    plain = window.overlay.offset
    pressed.add(KEY_LEFTSHIFT)
    window.focus_timer.timeout.emit()

    assert window.overlay.offset == plain
    assert tr("info_focus_follows") not in window.overlay.info_text
    assert tr("info_focus_assumed") not in window.overlay.info_text


def test_changing_the_weapon_forgets_a_held_focus(focus_window):
    window, pressed = focus_window
    lay(window, "AGS-17 · Technical")
    pressed.add(KEY_LEFTSHIFT)
    window.focus_timer.timeout.emit()
    assert window.focus_held

    lay(window, "AGS-17 · emplacement · no optic")

    assert not window.focus_held
    assert not window.focus_timer.isActive()


def test_without_readable_keys_the_info_line_says_the_mark_assumes_no_focus(qapp, tmp_path, monkeypatch):
    import crosshair

    monkeypatch.setattr(crosshair, "system_key_reader", lambda: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    window = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))

    try:
        lay(window, "AGS-17 · Technical")

        assert not window.focus_timer.isActive()
        assert tr("info_focus_assumed") in window.overlay.info_text
        assert tr("info_focus_follows") not in window.overlay.info_text
    finally:
        window.close()


def test_every_marked_entry_tells_the_player_in_its_note():
    for name in FOCUS_ENTRIES:
        assert "Holding Focus (Left Shift)" in WEAPONS[name].note, name


# ---- The picker with about 160 entries ----------------------------------------------------------

@pytest.fixture
def full_picker(qapp):
    from widgets import WeaponPicker

    picker = WeaponPicker()
    groups = {}

    for name, weapon in WEAPONS.items():
        groups.setdefault(weapon.category, []).append(name)

    picker.set_data(list(groups.items()), [])
    picker.set_notes({name: weapon.note for name, weapon in WEAPONS.items()})
    picker.resize(300, 40)
    picker.open_popup()

    yield picker

    picker.popup.hide()


def listed(picker):
    widget = picker.popup.list
    names = [widget.item(row).data(0x100) for row in range(widget.count())]

    return [name for name in names if name]


def test_the_picker_lists_every_entry_once_without_a_search(full_picker):
    assert sorted(listed(full_picker)) == sorted(WEAPONS)


def test_searching_gunner_sight_lists_exactly_the_gunner_sight_entries(full_picker):
    full_picker.popup.search.setText("gunner sight")

    assert sorted(n for n in listed(full_picker) if "gunner sight" in n) == GUNNER_SIGHTS
    assert len(GUNNER_SIGHTS) > 40


@pytest.mark.parametrize("query, expected", [
    ("M1117", "MK19 · M1117 · gunner sight ×4.5"),
    ("sprut", "Tank AP · Sprut-SDM1 (2A45) · gunner sight ×12"),
    ("×12", "Tank HEAT/HE · ZTZ-99 (ZPT-98) · gunner sight ×12"),
])
def test_the_picker_finds_a_vehicle_or_a_zoom(full_picker, query, expected):
    full_picker.popup.search.setText(query)

    assert expected in listed(full_picker)


def test_a_long_name_keeps_its_zoom_visible_in_the_list(full_picker):
    from PyQt6.QtCore import Qt

    assert full_picker.popup.list.textElideMode() == Qt.TextElideMode.ElideMiddle
