"""Vehicle gunner sights: the view of weapons mounted on vehicles.

The game fires along the weapon's barrel socket (Attach_Muzzle,
socket_muzzle ...). The gunner's camera is the turret camera, pitched by its
own RelativeRotation, so a view's bore is the socket's pitch minus the
camera's pitch, and the sight zoom comes from the turret's ZoomLevels (the
camera FOV is the game FOV divided by the level; the entry holds the first).
Open turrets move the camera to the ADS position with RMB (the MK19 sights
look 1.6-1.73 degrees under the barrel). Values from the game files, build 26005357.
"""

import json
import os

import pytest

from ballistics import (
    Weapon,
    WeaponDataError,
    load_weapons,
    mark_offset,
    range_ladder,
    screen_offset,
    solve,
)

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

# name, zoom (FOV divisor, 1.0: the plain view), bore in degrees, zero range of
# the sight in metres (flat ground, where the mark is on the screen centre).
# Each entry has one view: the vehicle gunner's first (widest) zoom level, or
# for the open-turret MK19s and the QLZ87 the RMB sight. The open-turret QLZ87
# also has its normal view: the turret's ResetZoom puts the game's FOV back
# whenever the weapon is not zoomed (its ZoomLevels [3.0] are only applied by
# the vehicle zoom key and reset within 0.3 s), and RMB divides the FOV by 3
# (BP_QLZ87_OpenTurret_Weapon: SetFieldOfView(UserSettings.FOV / 3.0)); both
# cameras sit at 0 on the gun mount. The zero ranges are what the game's
# socket, camera and flight give. Some come out round (AGS-30 200 m, MK19 on
# the M113 300 m, Challenger 2 AP 1000 m). The shells the projectile's
# MaxSpeed slows at launch (Grom and tank HEAT/HE) were round without that
# clamp (BMP-1 FRAG 350 m, T-72 HEAT 600 m), as if the sights had been set
# for the muzzle velocity; deadline-squad/squad-ballistics#4 and #5 (D3)
# have that question.
VEHICLE_SIGHTS = [
    ("MK19", 1.0, 0.0, None),
    ("MK19 · PARS III RWS", 1.0, 0.95, 180),
    ("MK19 · TAPV C16 RWS", 1.0, 1.55, 295),
    ("MK19 · M113 open turret", 1.0, 1.6, 300),
    ("MK19 · M1151 / RHIB open turret", 1.0, 1.72, 325),
    ("QLZ87 · Lynx / CSK131 · optic (RMB ×3)", 3.0, 0.85, 110),
    ("QLZ87 · Lynx / CSK131 · no optic", 1.0, 0.85, 110),
    ("MK19 · emplacement / C16 / L134A1 · no sights", 1.0, 0.0, None),
    ("AGS-30 / BTR-4 AGS", 3.0, 1.6, 205),
    ("AGS-30 (BMP-1TS)", 3.0, 1.55, 200),
    ("AGS-30 (BMP-2M)", 1.5, 1.55, 200),
    ("2A28 Grom (BMP-1 / BMD-1) · HEAT", 1.5, 1.4, 460),
    ("2A28 Grom (BMD-1M) · HEAT", 1.5, 1.57, 515),
    ("2A28 Grom (BMP-1 / BMD-1) · FRAG", 1.5, 1.4, 265),
    ("2A28 Grom (BMD-1M) · FRAG", 1.5, 1.57, 295),
    ("2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG", 2.5, 0.58, 130),
    ("2A70 100mm (BMD-4M) · FRAG", 2.5, 0.57, 130),
    ("2A70 100mm (ZBD-04A) · FRAG", 2.5, 0.95, 215),
    ("Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3", 4.0, 0.28, 675),
    ("Tank AP · T-62 (2A20)", 3.5, 0.05, 120),
    ("Tank AP · T-64BM2 (KBA3)", 2.7, 0.29, 700),
    ("Tank AP · ZTZ-99 (ZPT-98)", 4.0, 0.1, 240),
    ("Tank AP · M256 / Rh120", 3.0, 0.31, 635),
    ("Tank AP · Leopard 2A6 (Rh120)", 3.0, 0.25, 515),
    ("Tank AP · M60T (MG253)", 1.0, 0.5, 1030),
    ("Tank AP · L30A1 (Challenger 2) / M68A2", 1.5, 0.31, 995),
    ("Tank AP · M1128 MGS (M68A2)", 3.0, 0.6, 1925),
    ("Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2", 4.0, 0.28, 375),
    ("Tank HEAT/HE · M1A1 / M1A2 (M256)", 3.0, 0.31, 370),
    ("Tank HEAT/HE · Leopard 2A6 (Rh120)", 3.0, 0.25, 300),
    ("Tank HEAT/HE · M1128 MGS (M68A2)", 3.0, 0.6, 700),
    ("Tank HEAT/HE · M60T (MG253)", 1.0, 0.5, 655),
    ("Tank HEAT/HE · ZTZ-99 (ZPT-98)", 4.0, 0.1, 140),
    ("Tank HEAT/HE · T-62 (2A20)", 3.5, 0.05, 76),
    ("Tank HEAT/HE · T-64BM2 (KBA3)", 2.7, 0.29, 385),
    ("Tank HESH · L30A1 (Challenger 2)", 1.5, 0.31, 250),
    ("ZPL-98A 105mm (ZTD-05) · AP", 3.5, 0.02, 35),
    ("ZPL-98A 105mm (ZTD-05) · HEAT / HE", 3.5, 0.02, 20),
]


@pytest.mark.parametrize("name, zoom, bore, zero", VEHICLE_SIGHTS)
def test_the_sight_comes_from_the_game_files(name, zoom, bore, zero):
    weapon = WEAPONS[name]

    assert weapon.zoom == (zoom if zoom > 1 else 0)
    assert weapon.bore == pytest.approx(bore)
    assert weapon.sight_view(90) == (pytest.approx(90 / zoom), pytest.approx(bore))


@pytest.mark.parametrize("name, zoom, bore, zero", [v for v in VEHICLE_SIGHTS if v[3]])
def test_the_sight_is_zeroed_where_the_game_puts_it(name, zoom, bore, zero):
    """At the zero range the shot is on the screen centre; a shot leaving
    above the centre (positive bore) puts nearer targets above the centre and
    farther ones below it."""
    weapon = WEAPONS[name]
    view_fov, _ = weapon.sight_view(90)

    if not bore:
        return

    on_centre = solve(weapon, zero, 0.0, "low").sight_angle

    assert on_centre == pytest.approx(bore, abs=0.02 + 0.02 * bore)
    assert abs(mark_offset(weapon, on_centre, 90, 1920)) < screen_offset(0.03, view_fov, 1920)

    near = solve(weapon, zero / 2, 0.0, "low").sight_angle
    far = solve(weapon, zero * 2, 0.0, "low").sight_angle

    assert mark_offset(weapon, near, 90, 1920) < 0 < mark_offset(weapon, far, 90, 1920)


def test_the_open_turret_mk19_is_aimed_through_its_sights():
    """RMB moves the camera to the sights, which look under the barrel: the
    view keeps the FOV and the shot leaves above the centre."""
    assert WEAPONS["MK19 · M113 open turret"].sight_view(90) == (90, 1.6)
    assert WEAPONS["MK19 · M1151 / RHIB open turret"].sight_view(90) == (90, 1.72)


def test_a_gunner_sight_zooms_by_the_first_level():
    weapon = WEAPONS["Tank AP · M256 / Rh120"]

    assert weapon.sight_view(90) == (30, 0.31)
    assert weapon.sight_view(120) == (40, 0.31)


def test_the_ladder_of_a_gunner_sight_starts_past_its_zero():
    weapon = WEAPONS["Tank AP · M256 / Rh120"]
    ladder = range_ladder(weapon, 90, 1920, 20, 18, 520)

    assert ladder
    assert ladder[0][0] > 635

    for distance, offset in ladder:
        sight_angle = solve(weapon, distance, 0.0, "low").sight_angle
        assert offset == pytest.approx(mark_offset(weapon, sight_angle, 90, 1920))


def entry(**extra):
    return {"velocity": 100, **extra}


@pytest.mark.parametrize("data", [
    entry(views=[{"zoom": 3, "bore": 0.5}, {"zoom": 9}]),
    entry(views=[]),
    entry(zoom_bore=0.774),
    entry(bore=-0.9, zoom=3, zoom_bore=0.774),
    entry(sight_view="optic"),
    entry(sights=[]),
])
def test_the_removed_view_fields_and_unknown_keys_are_rejected(data):
    with pytest.raises(WeaponDataError):
        Weapon.from_dict("w", data)


@pytest.mark.parametrize("zoom", [0.5, 0.99, -3])
def test_a_zoom_below_one_is_rejected(zoom):
    with pytest.raises(WeaponDataError, match="zoom"):
        Weapon.from_dict("w", entry(zoom=zoom))


def test_a_weapon_has_the_one_view_its_entry_gives():
    zoomed = Weapon.from_dict("w", entry(bore=0.774, zoom=3))
    plain = Weapon.from_dict("w", entry(bore=0.3))

    assert zoomed.sight_view(90) == (30, 0.774)
    assert plain.sight_view(80) == (80, 0.3)


def test_no_weapons_json_entry_uses_the_removed_fields():
    with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as stream:
        data = json.load(stream)

    for name, entry_data in data.items():
        if isinstance(entry_data, dict):
            assert "views" not in entry_data
            assert "zoom_bore" not in entry_data
            assert name in WEAPONS


def test_an_older_settings_file_with_a_sight_view_loads_without_it():
    from config import DEFAULT_CONFIG, _merge

    for key in ("plain", "optic", "optic2", "nonsense"):
        merged = _merge({"sight_view": key, "fov": 100})

        assert "sight_view" not in merged
        assert merged["fov"] == 100

    assert "sight_view" not in DEFAULT_CONFIG


def test_an_older_settings_file_with_a_sight_view_is_loaded_and_saved_without_it(tmp_path):
    import config

    path = str(tmp_path / "config.json")
    with open(path, "w", encoding="utf-8") as stream:
        json.dump({"sight_view": "optic2", "fov": 100}, stream)

    loaded = config.load_config(path)

    assert loaded["fov"] == 100
    assert "sight_view" not in loaded

    config.save_config(loaded, path)
    with open(path, encoding="utf-8") as stream:
        assert "sight_view" not in json.load(stream)
