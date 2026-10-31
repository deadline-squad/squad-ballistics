"""The weapons aimed by elevation against the game's launch geometry and flight.

Squad Ballistics and SquadCalc once disagreed for these weapons (up to 3 degrees)
because neither had the point the shell starts from: SquadCalc guessed the height
of the muzzle, Squad Ballistics took the ground. The values here are read from the
game files (tests/data/game_weapons.json, tools/game_weapons.py), not from
weapons.json, and the shot is flown by the game's own rules (tests/flight.py)
without ballistics.py, so a wrong value in weapons.json fails here.
"""

import json
import math
import os
import statistics
from dataclasses import replace

import pytest

import flight
from ballistics import load_weapons, solve

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as _file:
    RAW = json.load(_file)

# Every entry whose launch point the snapshot holds: the weapons of a vehicle that are aimed by
# elevation (bore null) and the direct-fire weapons of a vehicle (a bore, flown by the overlay mark in
# test_mark_end_to_end.py).
LAUNCHED = [name for name in GAME if "launch" in GAME[name]]

# The weapons of a vehicle aimed by elevation: the snapshot holds the launch point and the limits.
VEHICLE = [name for name in LAUNCHED if GAME[name]["bore"] is None]

# The emplaced ones: the launch point is hand-derived in weapons.json, the
# flight is the game's.
EMPLACED = ["Mortar (M252 / 2B14 / L16 / Type 63)", "Hell Cannon", "UB-32 (S-5 rockets)"]

ELEVATION = VEHICLE + EMPLACED

# Metres either way the elevation of the oracle may differ from the app's, and the
# fractions of the reachable distances on flat ground to try.
MISS = 0.02
FRACTIONS = (0.02, 0.25, 0.5, 0.75, 0.98)


def _shot(name):
    return flight.Shot(GAME[name], RAW[name])


def _barrel_limits(name):
    """The lowest and highest barrel elevation (radians): the readout limits plus the app's offset."""
    weapon = WEAPONS[name]
    low, high = weapon.elevation_limits

    return math.radians(low + weapon.angle_offset), math.radians(high + weapon.angle_offset)


def _flat_window(name):
    """(nearest, farthest) distance the weapon reaches on flat ground by its own arc, from the
    oracle: the range at the end of the elevation limits that gives the near end of the arc, and
    the widest range."""
    weapon, shot = WEAPONS[name], _shot(name)
    low, high = _barrel_limits(name)
    _, widest = flight.widest_range(shot, low, high)
    end = low if weapon.arc == "low" else high

    return flight.range_at(shot, end, 0.0), widest


@pytest.mark.parametrize("name", LAUNCHED)
def test_the_launch_point_is_the_games(name):
    launch, weapon = GAME[name]["launch"], WEAPONS[name]

    assert weapon.launch_height == pytest.approx(launch["launch_height"], abs=5e-5)
    assert weapon.muzzle_forward == pytest.approx(launch["muzzle_forward"], abs=5e-5)
    assert weapon.muzzle_up == pytest.approx(launch["muzzle_up"], abs=5e-5)


@pytest.mark.parametrize("name", ELEVATION)
def test_the_elevation_lands_where_the_game_flies_it(name):
    """Five distances across what the weapon reaches on flat ground, three target heights at
    the middle: the barrel the app lays puts the shell on the target in the game's flight."""
    weapon, shot = WEAPONS[name], _shot(name)
    near, far = _flat_window(name)

    for fraction in FRACTIONS:
        distance = near + fraction * (far - near)
        solution = solve(weapon, distance, 0.0)

        assert solution.reachable, (name, distance, solution.reason)
        assert flight.miss(shot, math.radians(solution.raw_angle), distance, 0.0).distance < MISS, (name, distance)

    middle = near + 0.5 * (far - near)
    for height in (-30.0, 30.0):
        solution = solve(weapon, middle, height)

        assert solution.reachable, (name, height, solution.reason)
        assert flight.miss(shot, math.radians(solution.raw_angle), middle, height).distance < MISS, (name, height)


@pytest.mark.parametrize("name", ELEVATION)
def test_the_reach_ends_where_the_game_barrel_does(name):
    """Just past the widest range, and just short of the nearest the barrel's limits allow,
    there is no solution; the oracle's own search agrees that the shell cannot land there."""
    weapon, shot = WEAPONS[name], _shot(name)
    near, far = _flat_window(name)
    low, high = _barrel_limits(name)

    assert not solve(weapon, far * 1.002, 0.0).reachable
    if near > 1.0:
        assert not solve(weapon, near * 0.98, 0.0).reachable

    # the farthest is the oracle's, within a metre
    assert solve(weapon, far - 1.0, 0.0).reachable
    assert flight.elevation_to(shot, far * 1.002, 0.0, weapon.arc == "high", (low, high)) is None


@pytest.mark.parametrize("name", VEHICLE)
def test_the_old_launch_points_miss_in_the_games_flight(name):
    """The oracle tells the old data from the new: from the ground (Squad Ballistics before) or
    from SquadCalc's guessed 2.5 m, the elevation lands metres off the target in the game's flight."""
    near, far = _flat_window(name)
    distance = near + 0.5 * (far - near)
    shot = _shot(name)

    for wrong in ({"launch_height": 0.0, "muzzle_forward": 0.0, "muzzle_up": 0.0},
                  {"launch_height": 2.5, "muzzle_forward": 0.0, "muzzle_up": 0.0}):
        solution = solve(replace(WEAPONS[name], **wrong), distance, 0.0)

        assert solution.reachable
        assert flight.miss(shot, math.radians(solution.raw_angle), distance, 0.0).distance > 4 * MISS, wrong


def test_the_technical_mortar_readout_is_the_huds_table():
    """The game's HUD for the technical's mortar prints 14 pairs of degrees and range (40 degrees
    for 1250 m ... 83.8 for 50 m). The barrel that reaches each range, less the degrees the
    HUD shows, is the readout's offset: about 5 degrees. The offset in weapons.json has to be
    that one, not 0 and not the 9.6 degrees between the tube mesh's pose and the readout's zero."""
    game, weapon = GAME["Technical Mortar"], WEAPONS["Technical Mortar"]
    table = game["launch"]["hud"]
    shot = _shot("Technical Mortar")
    offsets = []

    for metres, degrees in zip(table["ranges"], table["degrees"]):
        elevation = flight.elevation_to(shot, metres, 0.0, True)
        if elevation is not None:
            offsets.append(math.degrees(elevation) - degrees)

    assert len(offsets) >= 12
    assert statistics.median(offsets) == pytest.approx(weapon.angle_offset, abs=0.3)
    assert max(offsets) - min(offsets) < 1.5


def test_the_technical_mortar_laid_at_the_huds_ends_reaches_its_table_ends():
    """The readout's ends are the HUD's 40 and 83.8 degrees: 1.24 km and 52 m on flat ground."""
    near, far = _flat_window("Technical Mortar")
    weapon = WEAPONS["Technical Mortar"]

    assert (weapon.elevation_limits[0], weapon.elevation_limits[1]) == pytest.approx((40, 83.8))
    assert far == pytest.approx(1238, abs=2)
    assert near == pytest.approx(52, abs=2)
    assert weapon.min_distance <= near


def test_the_bm21_has_a_nearest_distance_from_the_rail():
    """The rail rests 14.2 degrees up and goes to 55: a target at 500 m needs less than the rail
    can give, in Squad Ballistics and in the game's flight alike."""
    weapon, shot = WEAPONS["BM-21 Grad"], _shot("BM-21 Grad")
    solution = solve(weapon, 500.0, 0.0)

    assert not solution.reachable
    assert solution.reason_code == "elevation_limit"
    assert flight.elevation_to(shot, 500.0, 0.0, False) < math.radians(14.2)
