"""Sight data of the emplaced and vehicle weapons (docs/sight-data.md, .ru.md).

The weapons in scope are the entries of tests/data/game_weapons.json whose
view was read from the game files (the handheld launchers and grenade
launchers carry an assumed bore and zoom and are out of scope). For each one
the app holds, or lacks, three pieces of sight data:

* bore: the degrees the shot leaves above the view's centre;
* zoom: the divisor the sight puts on the game's FOV;
* launch point: the barrel pivot's height and the muzzle's offset, which is
  where the shot starts relative to the eye (the model's parallax; the camera
  itself is taken at the pivot for every weapon).

The tests keep the documents honest: the tables in both languages must list
exactly what weapons.json holds, and name a reason for each missing piece.
Then, for every weapon with a bore, the round-zero test: the zero range found
by flying the shot in the independent oracle (tests/flight.py, the game's
flight from the game snapshot, the launch point from the snapshot) must land
the app's mark on the screen centre, and a farther target must be marked as
many pixels below it as the oracle's elevation difference at the sight's own
zoom gives. A bore, zoom or launch point applied wrongly moves one of the two.
"""

import json
import math
import os
from dataclasses import replace

import pytest

from ballistics import load_weapons, mark_offset, solve

import flight
from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as _file:
    RAW = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

IN_SCOPE = [name for name, entry in GAME.items() if not entry.get("bore_assumed")]

FOV = 90
WIDTH = 1920
ZERO_TOLERANCE_PX = 0.5
OFFSET_TOLERANCE_PX = 1.0
FAR_FACTOR = 1.5
MAX_ZERO = 6000.0
SEARCH_WINDOW = 0.05

DOCS = {
    "en": os.path.join(ROOT, "docs", "sight-data.md"),
    "ru": os.path.join(ROOT, "docs", "sight-data.ru.md"),
}

LAUNCH_KEYS = ("launch_height", "muzzle_forward", "muzzle_up")


def has_bore(name):
    return bool(WEAPONS[name].bore)


def has_zoom(name):
    return bool(WEAPONS[name].zoom)


def has_launch(name):
    return any(RAW[name].get(key) for key in LAUNCH_KEYS)


def present(name):
    """The sight data weapons.json holds for `name`: a subset of
    {"bore", "zoom", "launch"}."""
    return {
        field for field, check in (("bore", has_bore), ("zoom", has_zoom), ("launch", has_launch))
        if check(name)
    }


def table_cell(value):
    return f"{value:g}" if value else "-"


def parse_docs(path):
    """({weapon: (bore, zoom, launch cells)}, {(weapon, field): reason}) from
    the two tables of a sight-data document."""
    data, missing = {}, {}

    with open(path, encoding="utf-8") as source:
        for line in source:
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]

            if len(cells) == 4 and cells[0] in GAME:
                data[cells[0]] = tuple(cells[1:])
            elif len(cells) == 3 and cells[0] in GAME and cells[1] in ("bore", "zoom", "launch"):
                missing[(cells[0], cells[1])] = cells[2]

    return data, missing


@pytest.fixture(scope="module", params=sorted(DOCS))
def document(request):
    return parse_docs(DOCS[request.param])


def test_the_scope_is_the_emplaced_and_vehicle_weapons():
    assert len(IN_SCOPE) == 141
    assert set(IN_SCOPE) <= set(WEAPONS)
    assert all(WEAPONS[name].category in ("agl", "guns", "tanks", "indirect") for name in IN_SCOPE)


def test_the_document_lists_the_data_of_every_weapon_in_scope(document):
    data, _ = document

    assert set(data) == set(IN_SCOPE)

    for name, (bore, zoom, launch) in data.items():
        weapon = WEAPONS[name]

        assert bore == table_cell(weapon.bore), name
        assert zoom == table_cell(weapon.zoom), name
        assert launch == (
            "{:g} / {:g} / {:g}".format(*(RAW[name].get(key, 0.0) for key in LAUNCH_KEYS))
            if has_launch(name) else "-"
        ), name


def test_the_document_names_a_reason_for_every_missing_piece(document):
    _, missing = document
    expected = {
        (name, field) for name in IN_SCOPE for field in {"bore", "zoom", "launch"} - present(name)
    }

    assert set(missing) == expected
    assert all(len(reason) > 20 for reason in missing.values())


def test_both_documents_say_the_same(document):
    reference = parse_docs(DOCS["en"])

    assert document[0] == reference[0]
    assert set(document[1]) == set(reference[1])


def shot(name):
    return flight.Shot(GAME[name], RAW[name])


def pivot_height(name):
    """The pivot's height from the game snapshot, else from the raw entry (as
    flight.Shot takes it)."""
    return float((GAME[name].get("launch") or RAW[name]).get("launch_height", 0.0))


def height_over_target(name, distance):
    """Height (m) of the oracle's shot over a ground target `distance` m away that the player has
    centred in the sight (the view axis points at it from the pivot, the barrel is `bore` above)."""
    bore = math.radians(flight.view(GAME[name])[1])
    flown = flight.fly_to(shot(name), bore - math.atan2(pivot_height(name), distance), distance)

    return -math.inf if flown is None else flown[0]


def first_distance_above_target(name):
    """The nearest distance on a 1.5 x grid, from 1 m past the muzzle, at which the oracle's shot
    passes above the centred ground target; None when it never does (a muzzle under the sight line
    and a bore too small to make up for it)."""
    first = max(1.0, shot(name).muzzle_forward + 1.0)

    return next((d for d in (first * 1.5 ** k for k in range(40)) if height_over_target(name, d) > 0), None)


def oracle_zero(name):
    """The range (m) at which a ground target centred in the sight is hit,
    for the bore and the launch point the game snapshot gives.

    The player centres the target, so the view axis points at it from the
    pivot, `atan(pivot / distance)` below the horizon, and the barrel is
    `bore` above the axis. The oracle flies that shot and the zero is where
    it comes down on the ground, found by bisection on the height it has
    there, starting where the shot first passes above the ground target:
    a gun whose muzzle sits under the sight line (a tank's) crosses it
    twice, and the zero is the farther crossing."""
    near, far = first_distance_above_target(name), MAX_ZERO

    assert near is not None and height_over_target(name, far) < 0, name

    for _ in range(60):
        middle = (near + far) / 2

        if height_over_target(name, middle) > 0:
            near = middle
        else:
            far = middle

    return near


def oracle_pixels(name, distance):
    """Pixels below the centre the oracle puts a flat-ground target at
    `distance`: the elevation the game's flight needs, less the bore, seen
    from the pivot through the sight's zoom."""
    zoom, bore = flight.view(GAME[name])
    sight_line = math.atan2(-pivot_height(name), distance)
    start = math.radians(bore) + sight_line
    elevation = flight.elevation_to(shot(name), distance, 0.0, False, (start - SEARCH_WINDOW, start + SEARCH_WINDOW))

    return flight.focal_length(WIDTH, FOV, zoom) * math.tan(elevation - math.radians(bore) - sight_line)


def app_pixels(weapon, distance):
    return mark_offset(weapon, solve(weapon, distance, 0.0, "low").sight_angle, FOV, WIDTH)


# The ZTD-05's sights leave 0.02 degrees above the centre from a muzzle 1 cm under the sight line: the
# shot never rises above a centred ground target, so there is no zero to test the mark at.
NO_ZERO = [name for name in IN_SCOPE if WEAPONS[name].bore > 0 and first_distance_above_target(name) is None]

WITH_ZERO = [name for name in IN_SCOPE if WEAPONS[name].bore > 0 and name not in NO_ZERO]


def test_only_the_ztd05_sights_never_rise_above_a_centred_ground_target():
    assert NO_ZERO == [
        "ZPL-98A 105mm (ZTD-05) \u00b7 AP", "ZPL-98A 105mm (ZTD-05) \u00b7 HEAT / HE",
        "ZPL-98A 105mm (ZTD-05) \u00b7 AP \u00b7 gunner sight \u00d77", "ZPL-98A 105mm (ZTD-05) \u00b7 HEAT / HE \u00b7 gunner sight \u00d77",
    ]



@pytest.mark.parametrize("name", WITH_ZERO)
def test_the_mark_is_on_the_centre_at_the_oracles_zero(name):
    zero = oracle_zero(name)

    assert abs(app_pixels(WEAPONS[name], zero)) < ZERO_TOLERANCE_PX, (name, zero)


@pytest.mark.parametrize("name", WITH_ZERO)
def test_a_farther_target_is_marked_where_the_oracle_and_the_zoom_put_it(name):
    far = oracle_zero(name) * FAR_FACTOR
    expected = oracle_pixels(name, far)

    assert expected > 0
    assert app_pixels(WEAPONS[name], far) == pytest.approx(expected, abs=OFFSET_TOLERANCE_PX, rel=0.01), name


@pytest.mark.parametrize("name, wrong, check", [
    ("AGS-17 \u00b7 Technical", {"bore": 4.6}, "zero"),
    ("AGS-17 \u00b7 Technical", {"muzzle_up": 0.6}, "zero"),
    ("QLZ87 \u00b7 Lynx \u00b7 optic (RMB \u00d73)", {"zoom": 1.0}, "far"),
    ("QLZ87 \u00b7 Lynx \u00b7 optic (RMB \u00d73)", {"bore": 0.95}, "zero"),
    ("Tank AP \u00b7 T-62 (2A20)", {"zoom": 7.0}, "far"),
])
def test_a_bore_zoom_or_launch_point_applied_wrongly_takes_the_mark_off_the_oracle(name, wrong, check):
    """The mutation check of the two tests above: the right entry passes,
    the same entry with one value wrong does not. (The pivot's height is not
    among the values: the mark is read from the pivot, so a pivot raised or
    lowered raises or lowers the sight line with the shot and moves the mark
    of a ground target by hundredths of a pixel; the muzzle offset moves it.)"""
    right = WEAPONS[name]
    zero = oracle_zero(name)
    distance = zero if check == "zero" else zero * FAR_FACTOR
    expected = 0.0 if check == "zero" else oracle_pixels(name, distance)
    tolerance = ZERO_TOLERANCE_PX if check == "zero" else OFFSET_TOLERANCE_PX

    assert app_pixels(right, distance) == pytest.approx(expected, abs=tolerance, rel=0.01)
    assert app_pixels(replace(right, **wrong), distance) != pytest.approx(expected, abs=tolerance, rel=0.01)


def test_the_sight_below_the_camera_has_no_zero():
    """The tripod QLZ87 without its optic fires below the camera (negative
    bore): every flat-ground target is marked below the centre."""
    negative = [name for name in IN_SCOPE if WEAPONS[name].bore < 0]

    assert negative == ["QLZ87 \u00b7 no optic", "QLZ87 \u00b7 bunker tripod \u00b7 no optic"]
    assert all(app_pixels(WEAPONS[name], distance) > 0 for name in negative for distance in (50, 300, 800))
