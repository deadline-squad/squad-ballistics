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


class _Mounts:
    """A Snapshot whose Blueprints are plain objects holding the given CDO properties."""

    def __init__(self, **cdos):
        self.snapshot = game_weapons.Snapshot.__new__(game_weapons.Snapshot)
        self.snapshot.blueprint = lambda path: type("Blueprint", (), {"cdo": cdos[path]})()


def test_an_open_turret_that_allows_focus_narrows_its_plain_view():
    snapshot = _Mounts(turret={"AllowFocus": True}).snapshot

    assert snapshot.allow_focus("turret", game_weapons.OPEN_PLAIN)


def test_a_tripod_that_never_sets_its_focus_flag_does_not_narrow():
    snapshot = _Mounts(open={"AllowFocus": False}, tripod={}, set_tripod={"bAllowFocus": True}).snapshot

    assert not snapshot.allow_focus("open", game_weapons.OPEN_PLAIN)
    assert not snapshot.allow_focus("tripod", game_weapons.TRIPOD_PLAIN)
    assert snapshot.allow_focus("set_tripod", game_weapons.TRIPOD_PLAIN)


def test_only_the_plain_views_have_a_focus_lerp():
    snapshot = _Mounts(mount={"AllowFocus": True, "bAllowFocus": True}).snapshot

    assert not snapshot.allow_focus("mount", game_weapons.ADS)
    assert not snapshot.allow_focus("mount", game_weapons.CLOSED_SIGHT)


def test_the_focus_factor_is_the_constant_of_the_fov_lerp():
    statements = [{"Token": "EX_CallMath", "Function": "Multiply_DoubleDouble",
                   "Parameters": [{"Token": "EX_DoubleConst", "Value": 0.666}, {"Token": "EX_LocalVariable"}]},
                  {"Token": "EX_CallMath", "Function": "Multiply_DoubleDouble",
                   "Parameters": [{"Token": "EX_DoubleConst", "Value": 2.0}, {"Token": "EX_LocalVariable"}]}]

    assert game_weapons.focus_multipliers(statements) == [0.666, 2.0]


def test_gunner_sights_name_the_reference_turret_first_and_the_distinct_weapons():
    classes, spec = game_weapons.gunner_sights(2, (
        ("T/Turrets/BP_A", "T/Weapons/BP_AP"),
        ("T/Turrets/BP_B", "T/Weapons/BP_AP"),
        ("T/Turrets/BP_B", "T/Weapons/BP_HE"),
    ))

    assert classes == ["Vehicles/T/Weapons/BP_AP", "Vehicles/T/Weapons/BP_HE"]
    assert spec["mount"] == "Vehicles/T/Turrets/BP_A"
    assert spec["zoom"] == ("levels", 2)
    assert spec["also"] == (("Vehicles/T/Turrets/BP_B", "Vehicles/T/Weapons/BP_AP"), ("Vehicles/T/Turrets/BP_B", "Vehicles/T/Weapons/BP_HE"))


def test_every_gunner_sight_entry_is_named_after_its_zoom():
    for name, (_, spec) in game_weapons.ENTRIES.items():
        if "gunner sight ×" in name:
            assert spec["zoom"][0] == "levels", name
            assert name.rsplit("×", 1)[1] == f"{GAME[name]['zoom']:g}", name
