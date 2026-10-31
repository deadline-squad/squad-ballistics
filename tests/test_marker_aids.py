"""The display aids for aiming at the in-game map marker: the range one pixel
of the mark is worth, the range where the mark leaves the screen, the aim
point lifted above the ground, the pixel rounding and the arming line.

The numbers are checked against the independent flight of tests/flight.py
(the game's substeps, a rectilinear camera written from first principles),
not against the app's own solver.
"""

import json
import math
import os

import pytest

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage

import config
import crosshair
import overlay as overlay_module
from ballistics import (
    MARK_HEIGHT_LIMIT,
    MARK_PIXEL_LIMIT,
    load_weapons,
    mark_height_resolution,
    mark_offset,
    mark_resolution,
    mark_visible_range,
    solve,
)
from conftest import ROOT
from maplink import make_target

import flight

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as _file:
    RAW = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

AGS = "AGS-17 · emplacement · optic (RMB ×2.5)"
QLZ = "QLZ87 · optic (RMB ×3)"
MK19 = "MK19 · emplacement / C16 / L134A1 · no sights"
TANK = "Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3"
SPG = "SPG-9 · HEAT · scope · optic (RMB ×4)"
PF98 = "PF98 · Tandem"
AGS30 = "AGS-30 (BMP-2M)"
ZIS = "ZiS-3 · optic (RMB ×4)"

# FOV 120 at 1920x1080: the mark is on the screen up to this many pixels
# below the centre (the overlay keeps a margin of EDGE_MARGIN at the edges)
BOTTOM = 1080 - overlay_module.Overlay.EDGE_MARGIN - 540
TOP = overlay_module.Overlay.EDGE_MARGIN - 540


def shot_of(name):
    return flight.Shot(GAME[name], RAW[name])


def oracle_pixels(name, fov, distance, ground, aim_height=None, width=1920):
    """Pixels below the centre the player puts the target ground at (`ground`
    m above the weapon's ground) so the shot hits `aim_height`, by the
    oracle's flight: the barrel the game needs, less the view's bore and the
    line of sight to the ground. None when the shot cannot get there."""
    zoom, bore = flight.view(GAME[name])
    elevation = flight.elevation_to(
        shot_of(name), distance, ground if aim_height is None else aim_height, False
    )

    if elevation is None:
        return None

    line = math.atan2(ground - float(RAW[name].get("launch_height", 0.0)), distance)
    focal = flight.focal_length(width, fov, zoom)

    return focal * math.tan(elevation - math.radians(bore) - line)


def oracle_metres_per_pixel(name, fov, distance, width=1920):
    """Range the shell gains per pixel at `distance` on flat ground: fly the
    shell for the barrels half a pixel either side of the mark."""
    zoom, bore = flight.view(GAME[name])
    shot = shot_of(name)
    pixels = oracle_pixels(name, fov, distance, 0.0, width=width)
    ranges = []

    for half in (-0.5, 0.5):
        elevation = flight.barrel_elevation(
            RAW[name], (zoom, bore), fov, width, pixels + half, distance, 0.0
        )
        ranges.append(flight.range_at(shot, elevation, 0.0))

    return ranges[1] - ranges[0]


def oracle_height_per_pixel(name, fov, distance, width=1920):
    """Metres of height at the target one pixel is worth: fly the shell for
    the barrels half a pixel either side of the mark and take the difference
    of the paths' heights at the target's distance (not where they land)."""
    zoom, bore = flight.view(GAME[name])
    shot = shot_of(name)
    pixels = oracle_pixels(name, fov, distance, 0.0, width=width)
    heights = []

    for half in (-0.5, 0.5):
        elevation = flight.barrel_elevation(
            RAW[name], (zoom, bore), fov, width, pixels + half, distance, 0.0
        )
        heights.append(flight.miss(shot, elevation, distance, 0.0).vertical)

    return abs(heights[1] - heights[0])


# ---------------------------------------------------------------------------
# 1. The range one pixel is worth
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, distance", [
    (AGS, 300), (AGS, 800), (QLZ, 500), (QLZ, 1200), (MK19, 600),
    (TANK, 1000), (SPG, 400),
])
def test_a_pixel_is_worth_what_the_oracles_flight_says(name, distance):
    metres = mark_resolution(WEAPONS[name], distance, 0.0, 120, 1920)

    assert metres == pytest.approx(oracle_metres_per_pixel(name, 120, distance), rel=0.02)


def test_a_pixel_is_worth_the_researched_figures():
    """FOV 120: about 19 m for the unzoomed MK19, 1-3 m for the AGS-17 and
    QLZ87 optics (deadline-squad/squad-ballistics#6, research 4)."""
    assert 15 < mark_resolution(WEAPONS[MK19], 600, 0.0, 120, 1920) < 25
    assert 1 < mark_resolution(WEAPONS[AGS], 600, 0.0, 120, 1920) < 3
    assert 2 < mark_resolution(WEAPONS[QLZ], 600, 0.0, 120, 1920) < 3.5


def test_a_calibrated_screen_changes_the_worth_of_a_pixel():
    plain = mark_resolution(WEAPONS[AGS], 500, 0.0, 120, 1920)
    stretched = mark_resolution(WEAPONS[AGS], 500, 0.0, 120, 1920, scale=1.5)

    assert stretched == pytest.approx(plain / 1.5, rel=0.01)


@pytest.mark.parametrize("name, distance", [
    (SPG, 600), (SPG, 300), (TANK, 600), (TANK, 1000), (ZIS, 600), (PF98, 300),
])
def test_a_pixel_is_worth_the_oracles_height_at_the_target(name, distance):
    metres = mark_height_resolution(WEAPONS[name], distance, 0.0, 120, 1920)

    assert metres == pytest.approx(oracle_height_per_pixel(name, 120, distance), rel=0.02)


def test_the_researched_height_of_a_pixel_at_600_m():
    """deadline-squad/squad-ballistics#11: 0.17 m high for the SPG-9 scope,
    the tank gun and the ZiS-3 optic at FOV 120."""
    for name in (SPG, TANK, ZIS):
        assert mark_height_resolution(WEAPONS[name], 600, 0.0, 120, 1920) == pytest.approx(0.17, abs=0.02)


def test_a_pixel_height_is_unknown_where_there_is_no_mark():
    mortar = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    assert mark_height_resolution(mortar, 500, 0.0, 120, 1920) is None
    assert mark_height_resolution(WEAPONS[SPG], 50000, 0.0, 120, 1920) is None


def test_the_weapon_data_tells_direct_hit_from_splash():
    assert all(WEAPONS[name].direct_hit for name in (SPG, TANK, PF98, ZIS))
    assert not any(WEAPONS[name].direct_hit for name in (AGS, QLZ, MK19, AGS30))


def test_a_pixel_worth_is_unknown_where_there_is_no_mark():
    mortar = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    assert mark_resolution(mortar, 500, 0.0, 120, 1920) is None
    assert mark_resolution(WEAPONS[AGS], 50000, 0.0, 120, 1920) is None


# ---------------------------------------------------------------------------
# 2. Where the mark leaves the screen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [(AGS, 940), (QLZ, 1490)])
def test_the_mark_leaves_the_screen_where_the_oracle_puts_it(name, expected):
    nearest, farthest = mark_visible_range(
        WEAPONS[name], 0.0, 120, 1920, TOP, BOTTOM
    )

    assert nearest is None
    assert farthest == pytest.approx(expected, abs=15)
    assert oracle_pixels(name, 120, farthest, 0.0) == pytest.approx(BOTTOM, abs=0.05)
    assert oracle_pixels(name, 120, farthest + 1, 0.0) > BOTTOM
    assert oracle_pixels(name, 120, farthest - 1, 0.0) < BOTTOM


def test_the_mark_enters_the_screen_where_the_oracle_puts_it():
    """A strong optic at a narrow FOV, aimed closer than its zero: the mark
    is above the top of the screen up to a range."""
    nearest, farthest = mark_visible_range(
        WEAPONS[SPG], 0.0, 20, 1920, TOP, BOTTOM
    )

    assert nearest is not None and nearest > 30
    assert oracle_pixels(SPG, 20, nearest, 0.0) == pytest.approx(TOP, abs=0.05)
    assert oracle_pixels(SPG, 20, nearest - 1, 0.0) < TOP
    assert oracle_pixels(SPG, 20, nearest + 1, 0.0) > TOP


def test_a_weapon_whose_mark_never_leaves_has_no_limit():
    assert mark_visible_range(WEAPONS[MK19], 0.0, 90, 1920, TOP, BOTTOM) \
        == (None, None)


# ---------------------------------------------------------------------------
# 4. The aim point lifted above the ground
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, distance, ground, lift", [
    (AGS, 500, 0.0, 1.5), (AGS, 800, 20.0, 2.0), (QLZ, 600, -15.0, 1.0),
    (TANK, 1000, 0.0, 2.5), (MK19, 300, 0.0, 1.0),
])
def test_a_lifted_aim_sits_where_the_oracle_puts_it(name, distance, ground, lift):
    """The player lays the GROUND on the mark; the shot goes `lift` metres
    above it."""
    weapon = WEAPONS[name]
    solution = solve(weapon, distance, ground, "low", lift)
    mark = mark_offset(weapon, solution.sight_angle, 120, 1920)

    assert mark == pytest.approx(
        oracle_pixels(name, 120, distance, ground, ground + lift), abs=0.05
    )


def test_a_lifted_aim_lands_higher_and_the_mark_moves_down():
    weapon = WEAPONS[AGS]
    ground = mark_offset(weapon, solve(weapon, 500, 0.0, "low").sight_angle, 120, 1920)
    lifted = mark_offset(weapon, solve(weapon, 500, 0.0, "low", 1.5).sight_angle, 120, 1920)

    assert lifted > ground


def test_no_lift_changes_nothing():
    weapon = WEAPONS[AGS]

    assert solve(weapon, 500, 12.0, "low") == solve(weapon, 500, 12.0, "low", 0.0)


# ---------------------------------------------------------------------------
# The Calculator page and the overlay
# ---------------------------------------------------------------------------

@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(WEAPONS)
    win.overlay.setGeometry(0, 0, 1920, 1080)
    win.config["info_enabled"] = True
    yield win
    win.close()


def fire(window, name, distance, height="0", fov="120"):
    window.select_weapon(name)
    window.distance_entry.setText(str(distance))
    window.height_entry.setText(height)
    window.fov_entry.setText(fov)
    window.calculate()


def test_the_overlay_says_what_a_pixel_is_worth(window):
    fire(window, AGS, 500)

    metres = mark_resolution(WEAPONS[AGS], 500, 0.0, 120, 1920)

    assert f"1 px = {metres:.1f} m" in window.overlay.info_text
    assert "too coarse" not in window.overlay.info_text


def test_a_zoomed_view_with_a_coarse_pixel_is_told_so(window):
    fire(window, AGS30, 800)

    assert mark_resolution(WEAPONS[AGS30], 800, 0.0, 120, 1920) > MARK_PIXEL_LIMIT
    assert "too coarse for marker aiming" in window.overlay.info_text


@pytest.mark.parametrize("name, distance", [(SPG, 600), (TANK, 1000), (ZIS, 600)])
def test_a_zoomed_direct_hit_weapon_is_told_the_height_of_a_pixel(window, name, distance):
    fire(window, name, distance)

    metres = mark_height_resolution(WEAPONS[name], distance, 0.0, 120, 1920)

    assert metres < MARK_HEIGHT_LIMIT
    assert f"1 px = {metres:.2f} m high" in window.overlay.info_text
    assert "too coarse" not in window.overlay.info_text


def test_the_spg9_scope_at_600_m_reads_about_17_cm(window):
    fire(window, SPG, 600)

    assert "1 px = 0.17 m high" in window.overlay.info_text


def test_a_direct_hit_pixel_taller_than_the_limit_is_too_coarse(window, monkeypatch):
    # No zoomed sight reaches a pixel of 0.6 m inside its range, so lower the limit
    monkeypatch.setattr(crosshair, "MARK_HEIGHT_LIMIT", 0.1)
    fire(window, SPG, 600)

    assert "too coarse for marker aiming" in window.overlay.info_text


def test_an_unzoomed_direct_hit_view_gets_the_height_only(window):
    fire(window, PF98, 300)

    assert "m high" in window.overlay.info_text
    assert "too coarse" not in window.overlay.info_text


def test_a_splash_weapon_keeps_the_range_of_a_pixel(window):
    fire(window, QLZ, 500)

    assert "m high" not in window.overlay.info_text
    assert "1 px = " in window.overlay.info_text


def test_an_unzoomed_view_gets_the_number_only(window):
    fire(window, MK19, 600)

    assert "1 px = " in window.overlay.info_text
    assert "too coarse" not in window.overlay.info_text


def test_the_error_of_aiming_at_the_whole_pixel_is_shown(window):
    shown = 0

    for distance in range(300, 600, 7):
        fire(window, QLZ, distance)

        offset = window.overlay.offset
        metres = mark_resolution(WEAPONS[QLZ], distance, 0.0, 120, 1920)
        error = abs(offset - round(offset)) * metres
        text = f"(whole px: {error:.1f} m off)"

        # Under half a metre the rounding is not worth a word
        assert (text in window.overlay.info_text) == (error >= 0.5), distance
        shown += error >= 0.5

    assert shown > 10


def test_the_offset_tile_keeps_the_tenth_of_a_pixel(window):
    fire(window, QLZ, 500)

    assert window.stats["stat_offset"].value.text() == f"{window.overlay.offset:.1f} px"


def test_a_mark_off_the_screen_says_where_it_leaves(window):
    fire(window, AGS, 1000)

    assert window.overlay.is_offscreen(window.overlay.offset)

    _, farthest = mark_visible_range(WEAPONS[AGS], 0.0, 120, 1920, TOP, BOTTOM)

    assert f"mark off screen past {farthest:.0f} m" in window.overlay.info_text
    assert any(f"past {farthest:.0f} m" in step for step in window.current_steps)
    assert "1 px = " not in window.overlay.info_text


def test_a_mark_above_the_screen_says_how_close_it_returns(window):
    fire(window, SPG, 30, fov="20")

    assert window.overlay.is_offscreen(window.overlay.offset)
    assert "mark off screen closer than " in window.overlay.info_text


def test_a_mark_on_the_screen_has_no_off_screen_text(window):
    fire(window, AGS, 600)

    assert "off screen" not in window.overlay.info_text


def test_the_aim_lift_is_shown_and_moves_the_mark(window):
    fire(window, AGS, 500)
    ground = window.overlay.offset

    window.config["target_height"] = 1.5
    window.calculate()

    assert window.overlay.offset > ground
    assert "aim +1.5 m" in window.overlay.info_text
    assert "aim +1.5 m" in window.arming_label.text()


def test_the_lift_leaves_the_weapons_laid_by_elevation_alone(window):
    mortar = "Mortar (M252 / 2B14 / L16 / Type 63)"

    fire(window, mortar, 500)
    plain = window.last_solution

    window.config["target_height"] = 5.0
    window.calculate()

    assert window.last_solution == plain
    assert "aim +" not in window.overlay.info_text


def test_the_arming_line_names_weapon_view_distance_and_bearing(window):
    window.on_map_targets([make_target(750.0, 0.0, 123.4)])
    window.select_weapon(AGS)
    window.fov_entry.setText("120")
    window.calculate()

    line = window.arming_label.text()

    assert line.startswith(AGS)
    assert "×2.5" in line
    assert "750 m" in line
    assert "bearing 123.4°" in line


def test_the_arming_line_goes_with_the_solution(window):
    fire(window, AGS, 500)
    assert window.arming_label.text()

    window.reset_offset()

    assert window.arming_label.text() == ""


# ---------------------------------------------------------------------------
# 3. The mark and the ticks are drawn to a fraction of a pixel
# ---------------------------------------------------------------------------

def test_the_ladder_ticks_are_drawn_to_a_fraction_of_a_pixel(window):
    """A tick's rendered centre is where the ladder says, to 0.02 px, for
    offsets that fall anywhere between two pixel rows."""
    window.config.update(info_enabled=False)
    ov = window.overlay
    ov.set_offset(0.0)
    x1 = int(ov.center_x) - overlay_module.LADDER_GAP - 1
    x0 = x1 - overlay_module.LADDER_TICK + 2

    for offset in (100.0, 100.25, 100.5, 100.75, 333.33):
        ov.set_ladder([(100, offset)])
        image = ov.grab(QRect(x0, 0, x1 - x0, ov.height())).toImage()
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        data = bytes(image.constBits().asarray(image.sizeInBytes()))
        stride = image.bytesPerLine()
        # The mark's horizontal arm reaches over these columns: start below it.
        below_mark = int(ov.center_y + overlay_module.MARK_REACH) + 3
        rows = [
            sum(data[row * stride + 4 * c + 2] for c in range(x1 - x0))
            for row in range(below_mark, image.height())
        ]
        centre = below_mark + sum((row + 0.5) * w for row, w in enumerate(rows)) / sum(rows)

        assert centre == pytest.approx(ov.center_y + offset, abs=0.02)


def test_target_height_is_a_setting_from_zero_to_ten_metres(tmp_path):
    path = tmp_path / "config.json"

    assert config.load_config(str(path))["target_height"] == 0.0

    path.write_text(json.dumps({"target_height": 1.5}))
    assert config.load_config(str(path))["target_height"] == 1.5

    path.write_text(json.dumps({"target_height": 99}))
    assert config.load_config(str(path))["target_height"] == 10.0

    path.write_text(json.dumps({"target_height": "tall"}))
    assert config.load_config(str(path))["target_height"] == 0.0
