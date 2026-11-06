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
AGS = "AGS-17 · emplacement · optic (RMB ×2.5)"
QLZ87 = "QLZ87 · optic (RMB ×3)"
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


@pytest.mark.parametrize("name", [M203, RPG7, AGS, QLZ87, "AT-4", "ZiS-3 · optic (RMB ×4)"])
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

    cfg["mark_trim"][M203] = 0.35
    cfg["mark_trim"][QLZ87] = -1.25
    config.save_config(cfg, path)

    assert config.load_config(path)["mark_trim"] == {M203: 0.35, QLZ87: -1.25}


def test_files_without_mark_trim_load(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 100}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 100
    assert cfg["mark_trim"] == {}


def test_mark_trim_ignores_what_is_malformed():
    merged = config._merge({"mark_trim": {
        M203: 9,
        QLZ87: -9,
        RPG7: 0,
        AGS: "far",
        MORTAR: math.nan,
        "Tank AP · M256 / Rh120": math.inf,
        "Tank AP · T-62 (2A20)": 10 ** 400,
        "Tank AP · ZTZ-99 (ZPT-98)": True,
        "": 1.0,
        "|plain": 1.0,
        3: 1.0,
    }})

    assert merged["mark_trim"] == {M203: TRIM_LIMIT, QLZ87: -TRIM_LIMIT}

    for junk in ([1, 2], "x", 5, None):
        assert config._merge({"mark_trim": junk})["mark_trim"] == {}


def test_a_trim_per_view_from_an_older_file_keeps_only_the_plain_one():
    merged = config._merge({"mark_trim": {
        f"{M203}|plain": 0.35,
        f"{QLZ87}|plain": 9,
        f"{QLZ87}|optic": -1.25,
        f"{QLZ87}|optic2": 0.5,
        f"{AGS}|optic": 0.2,
        f"{RPG7}|plain": 0,
        f"{MORTAR}|plain": math.nan,
        f"{MORTAR}|sideways": 1.0,
        "|plain": 1.0,
    }})

    # The sight's name is the optic's now: a trim of the plain view goes to
    # the "· no optic" twin, not to the entry for the other view.
    assert merged["mark_trim"] == {M203: 0.35, "QLZ87 · no optic": TRIM_LIMIT}


def test_a_config_saved_before_the_optic_names_keeps_its_meaning():
    """Settings written by the version whose "QLZ87" was the ×3 optic's entry
    (and by the one with the view switch): the bare name is still the optic,
    its plain-view trim goes to the "· no optic" twin."""
    old = {
        "last_weapon": "QLZ87",
        "recent_weapons": ["AGS-17 · emplacement", "ZiS-3", "RPG-29", "QLZ87"],
        "mark_trim": {
            "QLZ87": 0.4,
            "QLZ87|plain": 0.9,
            "QLZ87|optic": -0.2,
            "SPG-9 · HEAT · scope|plain": 0.1,
            "QLZ87 · Lynx / CSK131": 0.3,
        },
    }

    merged = config._merge(old)

    assert merged["last_weapon"] == "QLZ87 · optic (RMB ×3)"
    assert merged["recent_weapons"] == [
        "AGS-17 · emplacement · optic (RMB ×2.5)",
        "ZiS-3 · optic (RMB ×4)",
        "RPG-29",
        "QLZ87 · optic (RMB ×3)",
    ]
    assert merged["mark_trim"] == {
        "QLZ87 · optic (RMB ×3)": 0.4,
        "QLZ87 · no optic": 0.9,
        "SPG-9 · HEAT · scope · no optic": 0.1,
        "QLZ87 · Lynx / CSK131 · optic (RMB ×3)": 0.3,
    }


def test_mark_trim_follows_renamed_weapons():
    merged = config._merge({"mark_trim": {
        "BTR-4 AGS": 0.5,
        "Old MK19|plain": 0.1,
    }})

    assert merged["mark_trim"] == {"AGS-30 / BTR-4 AGS": 0.5, "Old MK19": 0.1}

    assert config._merge({"mark_trim": {"BTR-4 AGS|plain": 0.5}})["mark_trim"] == {
        "AGS-30 / BTR-4 AGS": 0.5
    }


# The Calculator page

@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    win.overlay.setGeometry(0, 0, 1920, 1080)
    yield win
    win.close()


def button(window, text):
    from PyQt6.QtWidgets import QPushButton

    return next(b for b in window.findChildren(QPushButton) if b.text() == text)


def expected_pixels(weapon, sight_angle, fov, trim):
    """Pixels below the centre, from the projection formula alone."""
    view_fov, bore = weapon.sight_view(fov)
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

    assert before == pytest.approx(expected_pixels(weapon, sight, float(fov), 0.0))

    window.miss_entry.setText("-40")
    button(window, "Apply").click()

    trim = trim_for_landing(weapon, 300, 0.0, 260)
    assert trim > 0

    assert window.trim_entry.value() == pytest.approx(round(trim, 3))
    assert window.trim_status.text() == f"Trim set to {round(trim, 3):+g} deg"
    assert window.config["mark_trim"] == {M203: pytest.approx(round(trim, 3))}
    assert window.overlay.offset == pytest.approx(
        expected_pixels(weapon, sight, float(fov), round(trim, 3))
    )
    assert window.overlay.offset > before
    assert window.miss_entry.text() == ""
    assert f"trim {round(trim, 3):+g}" in window.overlay.info_text
    assert any(f"trim {round(trim, 3):+g}" in step for step in window.current_steps)


def test_apply_with_a_height_difference(window):
    fire_at(window, M203, 300, height="12")
    weapon = window.current_weapon()

    window.miss_entry.setText("30")
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

    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, 0.5))
    assert window.overlay.ladder != plain_ladder

    first, spacing, reach = window.overlay.ladder_bounds()
    assert window.overlay.ladder == range_ladder(
        weapon, 90, 1920, first, spacing, reach, trim=0.5
    )

    window.trim_entry.setText("-0.2")
    window.trim_entry.textEdited.emit("-0.2")
    assert window.config["mark_trim"] == {M203: -0.2}

    window.trim_entry.setText("")
    window.trim_entry.textEdited.emit("")
    assert window.config["mark_trim"] == {}
    assert window.overlay.ladder == plain_ladder


def test_the_typed_trim_is_limited(window):
    fire_at(window, M203, 300)

    window.trim_entry.setText("50")
    window.trim_entry.textEdited.emit("50")

    assert window.config["mark_trim"] == {M203: TRIM_LIMIT}
    assert window.trim_entry.value() == TRIM_LIMIT


def test_the_wheel_steps_the_trim_by_a_twentieth_of_a_degree(window):
    fire_at(window, M203, 300)

    window.trim_entry.add(0.05)
    window.trim_entry.stepped.emit()
    window.trim_entry.add(0.05)
    window.trim_entry.stepped.emit()

    assert window.config["mark_trim"] == {M203: pytest.approx(0.1)}


def test_each_weapon_keeps_its_own_trim(window):
    fire_at(window, QLZ87, 400)
    weapon = window.current_weapon()
    sight = window.last_solution.sight_angle

    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, 0.4))
    assert window.config["mark_trim"] == {QLZ87: 0.4}
    optic_ladder = window.overlay.ladder

    window.select_weapon(M203)
    assert window.trim_entry.value() == 0.0
    assert M203 not in window.config["mark_trim"]

    window.select_weapon(QLZ87)
    assert window.trim_entry.value() == 0.4
    window.calculate()
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, 0.4))
    assert window.overlay.ladder == optic_ladder


def test_a_vehicle_sight_keeps_one_trim(window):
    tank = "Tank AP · M256 / Rh120"

    fire_at(window, tank, 800)
    weapon = window.current_weapon()
    sight = window.last_solution.sight_angle

    window.trim_entry.setText("-0.2")
    window.trim_entry.textEdited.emit("-0.2")

    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, -0.2))
    assert window.config["mark_trim"] == {tank: -0.2}


def test_reset_trim_clears_only_this_weapon(window):
    fire_at(window, M203, 300)
    sight = window.last_solution.sight_angle
    weapon = window.current_weapon()
    window.config["mark_trim"][RPG7] = 0.9

    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    button(window, "Reset trim").click()

    assert window.trim_entry.value() == 0.0
    assert window.config["mark_trim"] == {RPG7: 0.9}
    assert window.overlay.offset == pytest.approx(expected_pixels(weapon, sight, 90, 0.0))
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
    window.config["mark_trim"][RPG7] = 0.9

    window.reset_settings()

    assert window.config["mark_trim"] == {}
    assert window.trim_entry.value() == 0.0
    assert "trim" not in window.overlay.info_text


def test_the_trim_survives_a_restart_and_unknown_weapons_are_dropped(window, tmp_path):
    from crosshair import MainWindow

    fire_at(window, M203, 300)
    window.trim_entry.setText("0.4")
    window.trim_entry.textEdited.emit("0.4")
    window.config["mark_trim"]["Removed weapon"] = 1.0
    config.save_config(window.config)

    restarted = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    try:
        assert restarted.config["mark_trim"] == {M203: 0.4}
        assert restarted.trim_entry.value() == 0.4
    finally:
        restarted.close()


@pytest.mark.parametrize("distance, miss, message", [
    ("300", "", "Enter how far the shot missed"),
    ("", "-50", "Enter the distance"),
    ("300", "600", "Landed at: Out of range"),
    ("900", "-650", "Distance: Out of range"),
    ("300", "-300", "Landed distance must be greater than 0"),
])
def test_apply_says_what_is_wrong(window, distance, miss, message):
    window.select_weapon(M203)
    window.distance_entry.setText(distance)
    window.miss_entry.setText(miss)

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


# The high arc and the AGS-17 lob (review 1.6.0, slice 1 #2, slice 2 #1)
@pytest.mark.parametrize("error", [0.4, -0.7])
def test_trim_for_landing_round_trip_on_the_high_arc(error):
    """On the high arc more elevation shortens the shot: the trim from a
    high-arc landing is solved on the high arc, and fired again it lands on
    the target."""
    weapon = WEAPONS[M203]
    distance, start_trim = 300.0, 0.25

    aimed = solve(weapon, distance, 0.0, "high")
    barrel = aimed.angle + start_trim + error
    landed = landing_distance(weapon, barrel, 0.0)

    # Too much elevation on the high arc lands short
    assert (landed < distance) == (error > -start_trim)

    new_trim = trim_for_landing(weapon, distance, 0.0, landed, start_trim, "high")

    assert new_trim == pytest.approx(-error, abs=1e-6)

    for target in (distance, 250.0, 400.0):
        needed = solve(weapon, target, 0.0, "high")
        assert landing_distance(weapon, needed.angle + new_trim + error, 0.0) \
            == pytest.approx(target, abs=0.01)


def test_a_short_high_arc_landing_lowers_the_barrel():
    weapon = WEAPONS[M203]

    assert trim_for_landing(weapon, 300, 0.0, 270, 0.0, "high") < 0
    assert trim_for_landing(weapon, 300, 0.0, 330, 0.0, "high") > 0
    # The weapon's default arc is the low one
    assert trim_for_landing(weapon, 300, 0.0, 270, 0.0, "auto") \
        == trim_for_landing(weapon, 300, 0.0, 270)


def test_a_hold_lob_landing_is_refused():
    """The AGS-17 lob is laid by holding S, not with the mark."""
    with pytest.raises(ValueError, match="holding the key"):
        trim_for_landing(WEAPONS[AGS], 600, 0.0, 560, 0.0, "high")

    with pytest.raises(ValueError, match="holding the key"):
        trim_for_landing(WEAPONS[AGS], 600, 0.0, 560, 0.0, None)


def test_apply_on_the_ags_lob_keeps_the_direct_fire_trim(window):
    """Applying the lob's landing again and again must not build up a
    direct-fire trim (it reached -4.7° after six)."""
    window.select_weapon(AGS)
    window.on_arc_changed("high")
    fire_at(window, AGS, 600)

    assert window.last_solution.arc == "high"
    direct_offset = window.overlay.offset

    for _ in range(3):
        window.miss_entry.setText("-40")
        button(window, "Apply").click()
        window.calculate()

    from i18n import tr

    assert window.config["mark_trim"] == {}
    assert window.trim_status.text() == tr("trim_lob_refused")
    assert window.overlay.offset == pytest.approx(direct_offset)
    # The lob's hint: the trim field moves the direct-fire mark
    assert window.trim_entry.placeholderText() == tr("trim_hint")


def test_apply_on_the_ags_high_arc_inside_the_lob_minimum_is_direct_fire(window):
    """Under 300 m the AGS-17 cannot lob and fires directly (calculate):
    that landing trims the direct-fire mark, on the low arc."""
    window.select_weapon(AGS)
    window.on_arc_changed("high")
    fire_at(window, AGS, 250)

    assert window.last_solution.arc == "low"

    window.miss_entry.setText("-10")
    button(window, "Apply").click()

    expected = trim_for_landing(window.current_weapon(), 250, 0.0, 240, 0.0, "low")
    assert expected > 0
    assert window.config["mark_trim"] == {AGS: pytest.approx(round(expected, 3))}


def test_apply_on_the_high_arc_solves_the_high_arc(window):
    from i18n import tr

    window.select_weapon(M203)
    assert window.trim_entry.placeholderText() == tr("trim_hint")

    window.on_arc_changed("high")
    assert window.trim_entry.placeholderText() == tr("trim_hint_high")

    fire_at(window, M203, 300)
    assert window.last_solution.arc == "high"

    window.miss_entry.setText("-30")
    button(window, "Apply").click()

    expected = trim_for_landing(window.current_weapon(), 300, 0.0, 270, 0.0, "high")
    assert expected < 0
    assert window.config["mark_trim"] == {M203: pytest.approx(round(expected, 3))}

    window.on_arc_changed("low")
    assert window.trim_entry.placeholderText() == tr("trim_hint")


def test_apply_starts_from_the_current_trim(window):
    """A landing at the aimed distance keeps the trim already set."""
    fire_at(window, M203, 300)
    window.set_trim(0.5)

    window.miss_entry.setText("0")
    button(window, "Apply").click()

    assert window.config["mark_trim"] == {M203: 0.5}


# Every angle shown with the mark includes the trim (review 1.6.0, slice 1 #3)
@pytest.mark.parametrize("distance, fov", [(250, "90"), (390, "90"), (390, "20")])
def test_the_angle_the_player_is_told_includes_the_trim(window, distance, fov):
    from i18n import tr
    from widgets import format_angle

    fire_at(window, M203, distance, fov=fov)
    window.set_trim(2.0)
    solution = window.last_solution
    unit = window.primary_unit(window.current_weapon())
    plain = format_angle(solution.sight_angle, unit)
    trimmed = format_angle(solution.sight_angle + 2.0, unit)

    assert window.status_text() == trimmed
    assert f"  ·  {trimmed}  ·  " in window.overlay.info_text
    assert tr("to_horizon", angle=format_angle(solution.angle + 2.0, "deg")) \
        in window.sub_label.text()
    assert any(trimmed in step for step in window.current_steps)
    assert not any(plain in step for step in window.current_steps)

    if fov == "20":
        assert window.overlay.is_offscreen(window.overlay.offset)
        assert tr("how_overlay_offscreen", angle=trimmed) in window.current_steps


def test_the_ags_direct_fire_angle_includes_the_trim(window):
    """The lob's readouts name the direct-fire aim the mark shows: with the
    trim, in the info line, the sub-line, the step and the Other arc tile."""
    from i18n import tr
    from widgets import format_angle

    window.select_weapon(AGS)
    window.on_arc_changed("high")
    fire_at(window, AGS, 600)
    window.set_trim(0.5)

    unit = window.primary_unit(window.current_weapon())
    direct = format_angle(window.direct_solution.sight_angle + 0.5, unit)
    text = tr("direct_short", angle=direct)

    assert text in window.overlay.info_text
    assert text in window.sub_label.text()
    assert tr("how_hold_direct", angle=direct) in window.current_steps
    assert window.stats["stat_alt"].value.text() == direct


def test_the_other_arc_suggested_past_an_obstacle_includes_the_trim(window):
    from widgets import format_angle

    window.select_weapon(AGS)
    window.on_arc_changed("high")
    fire_at(window, AGS, 600)
    window.set_trim(0.5)
    weapon = window.current_weapon()
    unit = window.primary_unit(weapon)

    steps = window.obstacle_steps(
        weapon, window.last_solution, (300, 40.0), window.direct_solution, None, None, unit
    )

    assert format_angle(window.direct_solution.sight_angle + 0.5, unit) in steps[-1]
