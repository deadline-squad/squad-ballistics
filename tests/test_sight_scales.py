"""The scales the overlay draws in the sights (docs/sight-scales.md, .ru.md): what their constants must cover.

The mark and the range ladder are computed from the weapon, the game's FOV, the sight's zoom and bore; the zoom and
bore are checked against the game files in test_game_weapons.py and test_sight_data.py. What these tests pin is the
constants that are not weapon data: the ladder's greatest distance against the game's play areas
(tests/data/play_areas.json: SQMapBoundary.XYBoundary of each map, build 26005357) and the mil circle.
"""

import json
import os

from ballistics import (
    LADDER_MAX_DISTANCE,
    MILS_PER_DEGREE,
    load_weapons,
    range_ladder,
)

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "play_areas.json"), encoding="utf-8") as _file:
    PLAY_AREAS = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}


def test_the_ladder_covers_the_longest_line_across_a_play_area_of_the_game():
    longest = max(area["diagonal"] for area in PLAY_AREAS.values())

    assert longest > 5000, "the data has to hold a play area longer than the old limit"
    assert LADDER_MAX_DISTANCE >= longest


def test_a_tank_gun_ladder_goes_past_5000_m_on_a_screen_that_still_shows_the_marks():
    weapon = WEAPONS["Tank AP · M256 / Rh120"]
    fov, width = weapon.sight_view(120)[0], 1920

    ticks = range_ladder(weapon, fov, width, first=30, spacing=30, reach=10000)

    assert ticks, "the tank gun has a ladder"
    assert ticks[-1][0] > 5000


def test_a_mil_is_a_6400th_of_the_circle_as_in_the_games_mortar_firetable():
    assert MILS_PER_DEGREE * 360 == 6400
