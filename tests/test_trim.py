"""The field trim of the overlay mark: the model, the shot-landing solver, the
settings and the Calculator page."""

import json
import math
import os

import pytest

import config
from ballistics import (
    TRIM_LIMIT,
    height_at,
    load_weapons,
    mark_offset,
    range_ladder,
    solve,
    trim_for_landing,
)
from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

M203 = "M203 / M320 / GP-25 / HK79 / SL40"
RPG7 = "RPG-7 · PG-7V HEAT / OG-7V"
AGS = "AGS-17 · emplacement"
QLZ87 = "QLZ87"
MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


def landing_distance(weapon, angle, height):
    """Horizontal distance where a shot fired at `angle` (as `solve` returns
    it) first reaches the ground at `height` (coming down onto lower ground,
    or up onto higher ground), found from the flight path alone (`height_at`)
    and not from `solve`."""
    def above(x):
        return height_at(weapon, angle, x) - height > 0

    step = 0.25
    x = step
    start = above(x)

    while x < 20000:
        x += step

        if above(x) != start:
            low, high = x - step, x

            for _ in range(60):
                middle = (low + high) / 2
                low, high = (low, middle) if above(middle) != start else (middle, high)

            return (low + high) / 2

    raise AssertionError("the shot never reaches the ground")


def test_mark_offset_trim_is_added_to_the_elevation():
    weapon = WEAPONS[M203]
    angle = solve(weapon, 300, 0.0, "low").sight_angle
    focal = (1920 / 2) / math.tan(math.radians(90) / 2)

    assert mark_offset(weapon, angle, 90, 1920, trim=0.5) == pytest.approx(
        focal * math.tan(math.radians(angle - weapon.bore + 0.5))
    )
    assert mark_offset(weapon, angle, 90, 1920, trim=0.0) == mark_offset(
        weapon, angle, 90, 1920
    )


def test_mark_offset_trim_moves_the_mark_by_the_same_angle_at_every_range():
    weapon = WEAPONS[M203]
    focal = (1920 / 2) / math.tan(math.radians(120) / 2)

    for distance in (100, 250, 400):
        angle = solve(weapon, distance, 0.0, "low").sight_angle
        plain = mark_offset(weapon, angle, 120, 1920)
        trimmed = mark_offset(weapon, angle, 120, 1920, trim=0.3)

        expected = focal * (
            math.tan(math.radians(angle - weapon.bore + 0.3))
            - math.tan(math.radians(angle - weapon.bore))
        )
        assert trimmed - plain == pytest.approx(expected)
        assert trimmed > plain


def test_mark_offset_trim_is_limited():
    weapon = WEAPONS[M203]

    assert mark_offset(weapon, 1.0, 90, 1920, trim=50) == mark_offset(
        weapon, 1.0, 90, 1920, trim=TRIM_LIMIT
    )
    assert mark_offset(weapon, 1.0, 90, 1920, trim=-50) == mark_offset(
        weapon, 1.0, 90, 1920, trim=-TRIM_LIMIT
    )


def test_range_ladder_follows_the_trim():
    weapon = WEAPONS[M203]
    plain = range_ladder(weapon, 90, 1920, 20, 18, 5000)
    trimmed = range_ladder(weapon, 90, 1920, 20, 18, 5000, trim=0.4)

    assert trimmed != plain

    for distance, offset in trimmed:
        sight = solve(weapon, distance, 0.0, "low").sight_angle
        assert offset == pytest.approx(mark_offset(weapon, sight, 90, 1920, trim=0.4))


@pytest.mark.parametrize("name", [M203, RPG7, AGS, QLZ87, "AT-4", "ZiS-3"])
@pytest.mark.parametrize("height", [0.0, -15.0, -40.0])
@pytest.mark.parametrize("error", [0.4, -0.7])
def test_trim_for_landing_round_trip(name, height, error):
    """The barrel is off by `error` degrees. Fire at D with a trim, see where
    it lands, apply the new trim, fire again: the shot lands at D, and at
    every other range too (the trim is an angle)."""
    weapon = WEAPONS[name]
    distance = min(400.0, weapon.max_range() * 0.6)
    start_trim = 0.25

    aimed = solve(weapon, distance, height, "low")
    assert aimed.reachable

    barrel = aimed.angle + start_trim + error
    landed = landing_distance(weapon, barrel, height)

    assert (landed < distance) == (error < -start_trim)

    new_trim = trim_for_landing(weapon, distance, height, landed, start_trim)

    assert new_trim == pytest.approx(-error, abs=1e-6)

    for target in (distance, distance * 0.5, distance * 1.4):
        needed = solve(weapon, target, height, "low")

        if needed.reachable:
            assert landing_distance(weapon, needed.angle + new_trim + error, height) \
                == pytest.approx(target, abs=0.01)


def test_short_landing_gives_a_positive_trim_and_a_lower_mark():
    weapon = WEAPONS[M203]
    trim = trim_for_landing(weapon, 300, 0.0, 270)

    assert trim > 0

    angle = solve(weapon, 300, 0.0, "low").sight_angle

    assert mark_offset(weapon, angle, 90, 1920, trim=trim) > mark_offset(
        weapon, angle, 90, 1920
    )


def test_long_landing_gives_a_negative_trim_and_a_higher_mark():
    weapon = WEAPONS[M203]
    trim = trim_for_landing(weapon, 300, 0.0, 330)

    assert trim < 0

    angle = solve(weapon, 300, 0.0, "low").sight_angle

    assert mark_offset(weapon, angle, 90, 1920, trim=trim) < mark_offset(
        weapon, angle, 90, 1920
    )


def test_landing_at_the_aimed_distance_keeps_the_trim():
    weapon = WEAPONS[M203]

    assert trim_for_landing(weapon, 300, 0.0, 300) == pytest.approx(0.0)
    assert trim_for_landing(weapon, 300, 0.0, 300, 0.35) == pytest.approx(0.35)


def test_trim_for_landing_is_limited():
    weapon = WEAPONS[M203]

    assert trim_for_landing(weapon, 580, 0.0, 20) == TRIM_LIMIT
    assert trim_for_landing(weapon, 20, 0.0, 580) == -TRIM_LIMIT


@pytest.mark.parametrize("args, message", [
    ((WEAPONS[M203], 300, 0.0, 700), "Landed at"),
    ((WEAPONS[M203], 700, 0.0, 300), "Distance"),
    ((WEAPONS[M203], 300, 0.0, 0), "Landed distance"),
    ((WEAPONS[M203], 300, 0.0, -5), "Landed distance"),
    ((WEAPONS[M203], 0, 0.0, 300), "Distance must be"),
    ((WEAPONS[M203], 300, 0.0, math.nan), "numbers"),
    ((WEAPONS[M203], 300, math.inf, 250), "numbers"),
    ((WEAPONS[M203], math.nan, 0.0, 250), "numbers"),
    ((WEAPONS[M203], 300, 0.0, "far"), "numbers"),
    ((WEAPONS[MORTAR], 300, 0.0, 250), "not aimed with the overlay"),
    ((WEAPONS["NLAW"], 300, 0.0, 250), "no drop"),
])
def test_trim_for_landing_rejects_what_it_cannot_use(args, message):
    with pytest.raises(ValueError, match=message):
        trim_for_landing(*args)


# Settings

def test_mark_trim_is_saved_and_loaded(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = config.load_config(path)

    assert cfg["mark_trim"] == {}

    cfg["mark_trim"][config.trim_key(M203, "plain")] = 0.35
    cfg["mark_trim"][config.trim_key(QLZ87, "optic")] = -1.25
    config.save_config(cfg, path)

    assert config.load_config(path)["mark_trim"] == {
        f"{M203}|plain": 0.35,
        f"{QLZ87}|optic": -1.25,
    }


def test_files_without_mark_trim_load(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 100}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 100
    assert cfg["mark_trim"] == {}


def test_mark_trim_ignores_what_is_malformed():
    merged = config._merge({"mark_trim": {
        f"{M203}|plain": 9,
        f"{QLZ87}|optic": -9,
        f"{RPG7}|plain": 0,
        f"{AGS}|plain": "far",
        f"{AGS}|optic": True,
        f"{MORTAR}|plain": math.nan,
        f"{MORTAR}|optic": math.inf,
        f"{QLZ87}|plain": 10 ** 400,
        f"{QLZ87}|sideways": 1.0,
        "no view": 1.0,
        "|plain": 1.0,
        3: 1.0,
    }})

    assert merged["mark_trim"] == {
        f"{M203}|plain": TRIM_LIMIT,
        f"{QLZ87}|optic": -TRIM_LIMIT,
    }

    for junk in ([1, 2], "x", 5, None):
        assert config._merge({"mark_trim": junk})["mark_trim"] == {}


def test_mark_trim_follows_renamed_weapons():
    merged = config._merge({"mark_trim": {"BTR-4 AGS|plain": 0.5}})

    assert merged["mark_trim"] == {"AGS-30 / BTR-4 AGS|plain": 0.5}


# The Calculator page

@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    win.config["animated"] = False
    win.overlay.setGeometry(0, 0, 1920, 1080)
    yield win
    win.close()


def button(window, text):
    from PyQt6.QtWidgets import QPushButton

    return next(b for b in window.findChildren(QPushButton) if b.text() == text)


def expected_pixels(weapon, sight_angle, fov, zoomed, trim):
    """Pixels below the centre, from the projection formula alone."""
    view_fov, bore = weapon.sight_view(fov, zoomed)
    focal = (1920 / 2) / math.tan(math.radians(view_fov) / 2)

    return focal * math.tan(math.radians(sight_angle - bore + trim))


def fire_at(window, name, distance, height="0", fov="90"):
    window.select_weapon(name)
    window.distance_entry.setText(str(distance))
    window.height_entry.setText(height)
    window.fov_entry.setText(fov)
    window.calculate()


@pytest.mark.parametrize("fov", ["90", "120"])
def test_apply_sets_the_trim_and_moves_the_mark(window, fov):
    fire_at(window, M203, 300, fov=fov)
    weapon = window.current_weapon()
    sight = window.last_solution.sight_angle
    before = window.overlay.offset

    assert before == pytest.approx(expected_pixels(weapon, sight, float(fov), False, 0.0))

    window.landed_entry.setText("260")
    button(window, "Apply").click()

    trim = trim_for_landing(weapon, 300, 0.0, 260)
    assert trim > 0

    assert window.trim_entry.value() == pytest.approx(round(trim, 3))
    assert window.trim_status.text() == f"Trim set to {round(trim, 3):+g} deg"
    assert window.config["mark_trim"] == {f"{M203}|plain": pytest.approx(round(trim, 3))}
    assert window.overlay.offset == pytest.approx(
        expected_pixels(weapon, sight, float(fov), False, round(trim, 3))
    )
    assert window.overlay.offset > before
    assert window.landed_entry.text() == ""
    assert f"trim {round(trim, 3):+g}" in window.overlay.info_text
    assert any(f"trim {round(trim, 3):+g}" in step for step in window.current_steps)


def test_apply_with_a_height_difference(window):
    fire_at(window, M203, 300, height="12")
    weapon = window.current_weapon()

    window.landed_entry.setText("330")
    button(window, "Apply").click()

    trim = trim_for_landing(weapon, 300, 12.0, 330)
    assert trim < 0
    assert window.trim_entry.value() == pytest.approx(round(trim, 3))


def test_typing_the_trim_moves_the_mark_and_the_ladder(window):
    fire_at(window, M203, 300)
    weapon = window.current_weapon()
    sight = window.last_solution.sight_angle
    plain_ladder = window.overlay.ladder

    window.trim_entry.setText("0.5")
    window.trim_entry.textEdited.emit("0.5")

    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, False, 0.5))
    assert window.overlay.ladder != plain_ladder

    first, spacing, reach = window.overlay.ladder_bounds()
    assert window.overlay.ladder == range_ladder(
        weapon, 90, 1920, first, spacing, reach, trim=0.5
    )

    window.trim_entry.setText("-0.2")
    window.trim_entry.textEdited.emit("-0.2")
    assert window.config["mark_trim"] == {f"{M203}|plain": -0.2}

    window.trim_entry.setText("")
    window.trim_entry.textEdited.emit("")
    assert window.config["mark_trim"] == {}
    assert window.overlay.ladder == plain_ladder


def test_the_typed_trim_is_limited(window):
    fire_at(window, M203, 300)

    window.trim_entry.setText("50")
    window.trim_entry.textEdited.emit("50")

    assert window.config["mark_trim"] == {f"{M203}|plain": TRIM_LIMIT}
    assert window.trim_entry.value() == TRIM_LIMIT


def test_the_wheel_steps_the_trim_by_a_twentieth_of_a_degree(window):
    fire_at(window, M203, 300)

    window.trim_entry.add(0.05)
    window.trim_entry.stepped.emit()
    window.trim_entry.add(0.05)
    window.trim_entry.stepped.emit()

    assert window.config["mark_trim"] == {f"{M203}|plain": pytest.approx(0.1)}


def test_each_weapon_and_view_keeps_its_own_trim(window):
    fire_at(window, QLZ87, 400)
    weapon = window.current_weapon()
    sight = window.last_solution.sight_angle

    assert window.config["sight_view"] == "optic"
    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, True, 0.4))
    optic_ladder = window.overlay.ladder

    window.view_control.changed.emit("plain")
    assert window.trim_entry.value() == 0.0
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, False, 0.0))

    window.trim_entry.setText("-0.3")
    window.trim_entry.textEdited.emit("-0.3")
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, False, -0.3))
    assert window.config["mark_trim"] == {f"{QLZ87}|optic": 0.4, f"{QLZ87}|plain": -0.3}

    window.view_control.changed.emit("optic")
    assert window.trim_entry.value() == 0.4
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, True, 0.4))
    assert window.overlay.ladder == optic_ladder

    window.select_weapon(M203)
    assert window.trim_entry.value() == 0.0
    assert f"{M203}|plain" not in window.config["mark_trim"]

    window.select_weapon(QLZ87)
    assert window.trim_entry.value() == 0.4


def test_a_weapon_without_a_zoom_uses_the_plain_view_whatever_the_view_setting(window):
    window.config["sight_view"] = "optic"
    fire_at(window, M203, 300)

    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")

    assert window.config["mark_trim"] == {f"{M203}|plain": 0.4}


def test_reset_trim_clears_only_this_weapon_and_view(window):
    fire_at(window, M203, 300)
    sight = window.last_solution.sight_angle
    weapon = window.current_weapon()
    window.config["mark_trim"][f"{RPG7}|plain"] = 0.9

    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    button(window, "Reset trim").click()

    assert window.trim_entry.value() == 0.0
    assert window.config["mark_trim"] == {f"{RPG7}|plain": 0.9}
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, False, 0.0))
    assert "trim" not in window.overlay.info_text
    assert not any("trim" in step for step in window.current_steps)


def test_reset_settings_removes_all_trims(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    fire_at(window, M203, 300)
    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    window.config["mark_trim"][f"{RPG7}|plain"] = 0.9

    window.reset_settings()

    assert window.config["mark_trim"] == {}
    assert window.trim_entry.value() == 0.0
    assert "trim" not in window.overlay.info_text


def test_the_trim_survives_a_restart_and_unknown_weapons_are_dropped(window, tmp_path):
    from crosshair import MainWindow

    fire_at(window, M203, 300)
    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    window.config["mark_trim"]["Removed weapon|plain"] = 1.0
    config.save_config(window.config)

    restarted = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    try:
        assert restarted.config["mark_trim"] == {f"{M203}|plain": 0.4}
        assert restarted.trim_entry.value() == 0.4
    finally:
        restarted.close()


@pytest.mark.parametrize("distance, landed, message", [
    ("300", "", "Enter where the shot landed"),
    ("", "250", "Enter the distance"),
    ("300", "900", "Landed at: Out of range"),
    ("900", "250", "Distance: Out of range"),
])
def test_apply_says_what_is_wrong(window, distance, landed, message):
    window.select_weapon(M203)
    window.distance_entry.setText(distance)
    window.landed_entry.setText(landed)

    button(window, "Apply").click()

    assert message in window.trim_status.text()
    assert window.config["mark_trim"] == {}


def test_the_trim_controls_are_only_for_weapons_aimed_with_the_overlay(window):
    window.select_weapon(M203)
    assert not window.trim_box.isHidden()

    window.select_weapon(MORTAR)
    assert window.trim_box.isHidden()

    window.select_weapon(AGS)
    assert not window.trim_box.isHidden()
