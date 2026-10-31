"""tools/game_weapons.py: its entries against the snapshot and the readers that need no game dump."""

import json
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "tools"))

import game_weapons  # noqa: E402

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}


def test_the_tools_entries_are_the_snapshots():
    assert set(game_weapons.ENTRIES) == set(GAME)


def test_a_view_with_a_seat_gets_a_launch_point_and_no_other_view_does():
    for name, (_, spec) in game_weapons.ENTRIES.items():
        if isinstance(spec, dict):
            assert bool(spec["seat"]) == ("launch" in GAME[name]), name


def test_a_tracked_config_gives_each_wheel_its_own_radius():
    config = [{"Suspension": [{"BoneName": "wheel_L1", "WheelRadius": 47.0}, {"BoneName": "wheel_L2", "WheelRadius": 55.0}]}]

    assert game_weapons.wheel_radii(config) == {"wheel_l1": 47.0, "wheel_l2": 55.0}


def test_a_wheeled_config_gives_one_radius_for_all_wheels():
    config = {"Wheels": [{"WheelRadius": 52.0}, {"WheelRadius": 52.0}]}

    assert game_weapons.wheel_radii(config) == {None: 52.0}


def test_a_wheeled_config_with_two_radii_is_refused():
    with pytest.raises(game_weapons.GameDataError):
        game_weapons.wheel_radii({"Wheels": [{"WheelRadius": 52.0}, {"WheelRadius": 60.0}]})
