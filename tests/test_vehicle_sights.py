"""Vehicle gunner sights: the views of weapons mounted on vehicles.

The game fires along the weapon's barrel socket (Attach_Muzzle,
socket_muzzle ...). The gunner's camera is the turret camera, pitched by its
own RelativeRotation, so a view's bore is the socket's pitch minus the
camera's pitch, and the sight zoom levels come from the turret's ZoomLevels
(the camera FOV is the game FOV divided by the level). Open turrets move the
camera to the ADS position with RMB (the MK19 sights look 1.6-1.73 degrees
under the barrel). Values from the game files, build 26005357.
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

# name, views as (zoom, bore), zero range of the sight in metres (flat ground,
# where the mark is on the screen centre). Zero ranges that come out round
# (AGS-30 200 m, BMP-1 FRAG 350 m, MK19 on the M113 300 m, T-72 HEAT 600 m,
# Challenger 2 AP 1000 m) confirm the model; the others are what the game's
# socket and camera give.
VEHICLE_VIEWS = [
    ("MK19", ((1.0, 0.0), (4.5, 0.0)), None),
    ("MK19 · PARS III RWS", ((1.0, 0.95), (3.0, 0.95), (9.0, 0.95)), 180),
    ("MK19 · TAPV C16 RWS", ((1.0, 1.55), (5.0, 1.55), (12.0, 1.55)), 295),
    ("MK19 · M113 open turret", ((1.0, 0.0), (1.0, 1.6)), 300),
    ("MK19 · M1151 / RHIB open turret", ((1.0, 0.0), (1.0, 1.72)), 325),
    ("QLZ87 · Lynx / CSK131", ((1.0, 0.85), (3.0, 0.85)), 110),
    ("AGS-30 / BTR-4 AGS", ((3.0, 1.58), (9.0, 1.58)), 205),
    ("AGS-30 (BMP-2M)", ((1.5, 1.55), (6.0, 1.55)), 200),
    ("2A28 Grom (BMP-1 / BMD-1) · HEAT", ((1.5, 1.4), (6.0, 1.4)), 790),
    ("2A28 Grom (BMD-1M) · HEAT", ((1.5, 1.57), (6.0, 1.57)), 885),
    ("2A28 Grom (BMP-1 / BMD-1) · FRAG", ((1.5, 1.4), (6.0, 1.4)), 350),
    ("2A28 Grom (BMD-1M) · FRAG", ((1.5, 1.57), (6.0, 1.57)), 395),
    ("2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG", ((2.5, 0.58), (4.0, 0.58), (14.0, 0.58)), 130),
    ("2A70 100mm (BMD-4M) · FRAG", ((2.5, 0.57), (5.0, 0.57), (14.0, 0.57)), 130),
    ("2A70 100mm (ZBD-04A) · FRAG", ((2.5, 0.95), (4.0, 0.95), (14.0, 0.95)), 215),
    ("Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3", ((4.0, 0.28), (12.0, 0.28)), 675),
    ("Tank AP · T-62 (2A20)", ((3.5, 0.05), (7.0, 0.05)), 120),
    ("Tank AP · T-64BM2 (KBA3)", ((2.7, 0.29), (12.0, 0.29)), 700),
    ("Tank AP · ZTZ-99 (ZPT-98)", ((4.0, 0.1), (12.0, 0.1)), 240),
    ("Tank AP · M256 / Rh120", ((3.0, 0.31), (6.0, 0.31), (12.0, 0.31)), 635),
    ("Tank AP · Leopard 2A6 (Rh120)", ((3.0, 0.25), (12.0, 0.25)), 515),
    ("Tank AP · M60T (MG253)", ((1.0, 0.5), (3.0, 0.5), (8.0, 0.5)), 1030),
    ("Tank AP · L30A1 (Challenger 2) / M68A2", ((1.5, 0.31), (4.0, 0.31), (10.0, 0.31)), 995),
    ("Tank AP · M1128 MGS (M68A2)", ((3.0, 0.6), (8.0, 0.6)), 1925),
    ("Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2", ((4.0, 0.28), (12.0, 0.28)), 605),
    ("Tank HEAT/HE · M1A1 / M1A2 (M256)", ((3.0, 0.31), (6.0, 0.31), (12.0, 0.31)), 670),
    ("Tank HEAT/HE · Leopard 2A6 (Rh120)", ((3.0, 0.25), (12.0, 0.25)), 540),
    ("Tank HEAT/HE · M1128 MGS (M68A2)", ((3.0, 0.6), (8.0, 0.6)), 1295),
    ("Tank HEAT/HE · M60T (MG253)", ((1.0, 0.5), (3.0, 0.5), (8.0, 0.5)), 1080),
    ("Tank HEAT/HE · ZTZ-99 (ZPT-98)", ((4.0, 0.1), (12.0, 0.1)), 215),
    ("Tank HEAT/HE · T-62 (2A20)", ((3.5, 0.05), (7.0, 0.05)), 110),
    ("Tank HEAT/HE · T-64BM2 (KBA3)", ((2.7, 0.29), (12.0, 0.29)), 625),
    ("Tank HESH · L30A1 (Challenger 2)", ((1.5, 0.31), (4.0, 0.31), (10.0, 0.31)), 250),
    ("ZPL-98A 105mm (ZTD-05) · AP", ((3.5, 0.02), (7.0, 0.02)), 35),
    ("ZPL-98A 105mm (ZTD-05) · HEAT / HE", ((3.5, 0.02), (7.0, 0.02)), 20),
]


@pytest.mark.parametrize("name, views, zero", VEHICLE_VIEWS)
def test_the_views_come_from_the_game_files(name, views, zero):
    assert WEAPONS[name].sight_views == views


@pytest.mark.parametrize("name, views, zero", [v for v in VEHICLE_VIEWS if v[2]])
def test_the_sight_is_zeroed_where_the_game_puts_it(name, views, zero):
    """At the zero range the shot is on the screen centre in every view; a
    shot leaving above the centre (positive bore) puts nearer targets above
    the centre and farther ones below it."""
    weapon = WEAPONS[name]

    for index, (zoom, bore) in enumerate(views):
        view_fov, view_bore = weapon.sight_view(90, index)

        assert view_fov == pytest.approx(90 / zoom)

        if not bore:
            continue

        on_centre = solve(weapon, zero, 0.0, "low").sight_angle

        assert on_centre == pytest.approx(bore, abs=0.02 + 0.02 * bore)
        assert abs(mark_offset(weapon, on_centre, 90, 1920, zoomed=index)) < screen_offset(0.03, view_fov, 1920)

        near = solve(weapon, zero / 2, 0.0, "low").sight_angle
        far = solve(weapon, zero * 2, 0.0, "low").sight_angle

        assert mark_offset(weapon, near, 90, 1920, zoomed=index) < 0 < mark_offset(weapon, far, 90, 1920, zoomed=index)


def test_the_gunner_views_differ_by_their_zoom_only():
    """Cycling a closed turret's zoom levels never tilts the camera, so the
    bore is the same in every view; the open turret MK19 changes the bore with
    RMB (the camera moves to the sights) and not the zoom."""
    weapon = WEAPONS["Tank AP · M256 / Rh120"]

    assert {bore for _, bore in weapon.sight_views} == {0.31}

    mk19 = WEAPONS["MK19 · M113 open turret"]

    assert mk19.sight_view(90, False) == (90, 0.0)
    assert mk19.sight_view(90, True) == (90, 1.6)


def test_a_third_view_is_reached_by_index_and_the_last_one_serves_fewer():
    three = WEAPONS["Tank AP · M256 / Rh120"]
    two = WEAPONS["Tank AP · Leopard 2A6 (Rh120)"]

    assert three.sight_view(90, 2) == (7.5, 0.31)
    assert three.sight_view(90, 1) == (15, 0.31)
    assert three.sight_view(90, 0) == (30, 0.31)
    assert two.sight_view(90, 2) == (7.5, 0.25)
    assert three.sight_view(90, False) == three.sight_view(90, 0)
    assert three.sight_view(90, True) == three.sight_view(90, 1)


def test_the_ladder_of_a_deeper_view_is_longer_and_zeroed():
    weapon = WEAPONS["Tank AP · M256 / Rh120"]
    first = range_ladder(weapon, 90, 1920, 20, 18, 520, zoomed=0)
    deepest = range_ladder(weapon, 90, 1920, 20, 18, 520, zoomed=2)

    assert first and deepest
    assert first[0][0] > 635
    assert deepest[0][0] > 635
    assert len(deepest) <= len(first) or deepest[-1][0] < first[-1][0]


def entry(**extra):
    return {"velocity": 100, **extra}


def test_views_are_parsed_in_order():
    weapon = Weapon.from_dict("w", entry(views=[{"zoom": 3, "bore": 0.5}, {"zoom": 9}]))

    assert weapon.sight_views == ((3.0, 0.5), (9.0, 0.0))
    assert weapon.has_views


def test_a_single_zoomed_view_has_no_switch():
    weapon = Weapon.from_dict("w", entry(views=[{"zoom": 4, "bore": 0.2}]))

    assert not weapon.has_views
    assert weapon.sight_view(80, True) == (20, 0.2)


def test_the_legacy_fields_make_the_same_views():
    plain = Weapon.from_dict("w", entry(bore=0.3))
    optic = Weapon.from_dict("w", entry(bore=-0.9, zoom=3, zoom_bore=0.774))

    assert plain.sight_views == ((1.0, 0.3),)
    assert not plain.has_views
    assert optic.sight_views == ((1.0, -0.9), (3.0, 0.774))
    assert optic.has_views


@pytest.mark.parametrize("data", [
    entry(views=[]),
    entry(views=[{"zoom": 1}] * 4),
    entry(views=[{"zoom": 0.5}]),
    entry(views=[{"zoom": "x"}]),
    entry(views=[{"zoom": True}]),
    entry(views=[{"zoom": 2, "bore": float("inf")}]),
    entry(views=[{"bore": 0.1}]),
    entry(views=[2]),
    entry(views="3"),
    entry(views=[{"zoom": 2}], bore=0.1),
    entry(views=[{"zoom": 2}], zoom=3),
])
def test_invalid_views_are_rejected(data):
    with pytest.raises(WeaponDataError):
        Weapon.from_dict("w", data)


def test_every_entry_with_views_is_valid_json_data():
    with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as stream:
        data = json.load(stream)

    for name, entry_data in data.items():
        if isinstance(entry_data, dict) and "views" in entry_data:
            assert name in WEAPONS
            assert 1 <= len(WEAPONS[name].sight_views) <= 3


def test_an_older_settings_file_with_plain_or_optic_stays_valid():
    from config import _merge

    for key in ("plain", "optic", "optic2"):
        assert _merge({"sight_view": key})["sight_view"] == key

    assert _merge({"sight_view": "nonsense"})["sight_view"] == "optic"
