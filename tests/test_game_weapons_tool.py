"""tools/game_weapons.py: its entries against the snapshot and the readers that need no game dump."""

import json
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import flight  # noqa: E402
import game_weapons  # noqa: E402

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}


def test_the_tools_entries_are_the_snapshots():
    assert set(game_weapons.ENTRIES) == set(GAME)


# The view entries the files give no launch point for, and why (docs/sight-data.md).
NO_LAUNCH_POINT = {
    "MK19": "the M1117's turret socket and its CROWS socket are 1.9 m apart",
    "MK19 · M1117 · gunner sight ×4.5": "the M1117's turret socket and its CROWS socket are 1.9 m apart",
    "MK19 · RHIB open turret": "a boat",
    "MK19 · RHIB open turret · no sights": "a boat",
    "AGS-17 · emplacement · optic (RMB ×2.5)": "the hold model was fitted with 1 m",
    "AGS-17 · emplacement · no optic": "the hold model was fitted with 1 m",
    "AGS-17 · iron sights emplacement": "the hold model was fitted with 1 m",
}


def test_every_view_has_a_launch_point_but_those_the_files_do_not_give():
    for name, (_, spec) in game_weapons.ENTRIES.items():
        if isinstance(spec, dict):
            assert ("launch" in GAME[name]) == (name not in NO_LAUNCH_POINT), name


def test_a_view_has_a_launch_point_when_a_vehicle_carries_its_mount():
    for name, (_, spec) in game_weapons.ENTRIES.items():
        if isinstance(spec, dict):
            assert bool(spec["seat"] or game_weapons.CARRIERS.get(spec["mount"])) == ("launch" in GAME[name]), name


def vehicle_heights(name):
    """{vehicle Blueprint: launch_height} of the vehicles an entry's launch source lists."""
    source = GAME[name]["sources"]["launch"]
    return {part.split(" ")[0]: float(part.split(" ")[1].rstrip(":")) for part in source.split(" | ")}


# launch_height (m) of each vehicle's gun pivot over the ground, read from the vehicle's mesh seat
# socket, the turret's mount and the wheels' lowest point in the dumps of build 26234431.
VEHICLE_HEIGHTS = {
    "QLZ87 · CSK131 / WZ551 · no optic": {"BP_CSK131_QLZ87": 2.2899, "BP_WZ551B_QLZ-87": 2.5169, "BP_WZ551B_QLZ-87_Desert": 2.5169, "BP_ZSD89_QLZ-87": 2.1196},
    "Tank AP · T-72 (2A46)": {"BP_T72B3": 1.5746, "BP_T72A_IMF": 1.5746, "BP_T72S_GFI": 1.5746},
    "Tank AP · T-90A (2A46M)": {"BP_T90A": 1.8279, "BP_T90A_Desert": 1.8279},
    "Tank AP · Sprut-SDM1 (2A45) · gunner sight ×4": {"BP_Sprut": 2.1443, "BP_Sprut_Desert": 2.1443},
    "Tank AP · M1A1 / M1A2 (M256) · gunner sight ×6": {"BP_AUS_M1A1": 2.447, "BP_M1A1_USMC": 2.447, "BP_M1A2": 2.447},
    "Tank AP · Leopard 2A6 (Rh120)": {"BP_2A6_Woodland": 2.0665},
    "2A28 Grom (BMP-1 / BMD-1) · HEAT": {"BP_BMP1_INS": 1.9452},
    "2A28 Grom (BMP-1 technical) · HEAT": {"BP_Technical2Seater_White_BMP1": 2.3249},
    "2A28 Grom (BMD-1M) · HEAT": {"BP_BMD1M": 1.7853},
    "2A70 100mm (ZBD-04A) · FRAG": {"BP_ZBD04A": 2.1755},
    "AGS-30 (BMP-2M)": {"BP_BMP2M": 2.15},
    "MK19 · emplacement / C16 / L134A1": {"BP_EmplacedMk19_Tripod": 0.4345},
    "QLZ87 · optic (RMB ×3)": {"BP_EmplacedQLZ87_Tripod": 0.446},
}


@pytest.mark.parametrize("name", [n for n, heights in VEHICLE_HEIGHTS.items() if heights])
def test_a_vehicles_pivot_is_the_height_the_dump_gives(name):
    found = vehicle_heights(name)

    for vehicle, height in VEHICLE_HEIGHTS[name].items():
        assert found[vehicle] == pytest.approx(height, abs=5e-5), (name, vehicle)


def test_the_qlz87_of_the_wz551_has_its_own_height_in_the_range_the_entry_takes():
    """The owner's vehicle: the entry takes the middle of the CSK131 (2.29 m), the WZ551 (2.52 m) and the
    ZSD-89 (2.12 m), and the snapshot keeps the range."""
    launch = GAME["QLZ87 · CSK131 / WZ551 · no optic"]["launch"]

    assert launch["spread"]["launch_height"] == [2.1196, 2.5169]
    assert launch["launch_height"] == pytest.approx((2.1196 + 2.5169) / 2, abs=5e-5)


MAX_SHIFT_AT_300 = 10.0


@pytest.mark.parametrize("name", sorted(n for n in GAME if "spread" in GAME[n].get("launch", {})))
def test_an_entry_covering_vehicles_of_different_heights_moves_no_shot_more_than_10_m_at_300_m(name):
    """The rule for splitting an entry: aimed at 300 m with the middle launch point, a shot from the
    highest or the lowest vehicle lands within 10 m of it (flat ground, the game's flight)."""
    game = GAME[name]
    elevation = flight.elevation_to(flight.Shot(game), 300.0, 0.0, False)

    for end in (0, 1):
        moved = dict(game["launch"], **{key: values[end] for key, values in game["launch"]["spread"].items()})
        landed = flight.range_at(flight.Shot(dict(game, launch=moved)), elevation, 0.0)

        assert abs(landed - 300.0) <= MAX_SHIFT_AT_300, (name, end, landed)


def test_a_vehicle_space_turret_mesh_takes_its_root_bone_as_the_attachment(monkeypatch):
    bones = [("root", -1, game_weapons.Transform(game_weapons.IDENTITY, (-103.0, 0.0, 175.3)))]
    monkeypatch.setattr(game_weapons, "skeleton_of", lambda assets, mesh: (None, None, bones))
    turret = type("Turret", (), {
        "types": {"Mesh": "SkeletalMeshComponent", "Mount": "SceneComponent"},
        "components": {"Mesh": {"SkeletalMesh": {"ObjectPath": "/Game/Mesh.1"}}},
        "parents": {"Mount": "Mesh"},
        "chain": ["/Game/Turret"],
    })()

    assert game_weapons.turret_root_offset(None, turret, "Mount") == (-103.0, 0.0, 175.3)


def test_a_turret_mesh_at_its_origin_has_no_root_offset(monkeypatch):
    bones = [("root", -1, game_weapons.Transform(game_weapons.IDENTITY, (3.0, 0.0, 10.0)))]
    monkeypatch.setattr(game_weapons, "skeleton_of", lambda assets, mesh: (None, None, bones))
    turret = type("Turret", (), {
        "types": {"Mesh": "SkeletalMeshComponent", "Mount": "SceneComponent"},
        "components": {"Mesh": {"SkeletalMesh": {"ObjectPath": "/Game/Mesh.1"}}},
        "parents": {"Mount": "Mesh"},
        "chain": ["/Game/Turret"],
    })()

    assert game_weapons.turret_root_offset(None, turret, "Mount") is None


def test_a_config_that_names_its_physics_wheels_simwheel_gives_the_mesh_wheels_their_radius(monkeypatch):
    bones = [(name, -1, game_weapons.Transform(game_weapons.IDENTITY, (0.0, 0.0, z)))
             for name, z in (("wheel_L1", 60.0), ("wheel_R2", 55.0), ("body", 300.0))]
    monkeypatch.setattr(game_weapons, "skeleton_of", lambda assets, mesh: (None, None, bones))
    assets = type("Assets", (), {"require": lambda self, package: [{"Suspension": [
        {"BoneName": "simwheel_L1", "WheelRadius": 44.0}, {"BoneName": "simwheel_R2", "WheelRadius": 44.0}]}]})()
    vehicle = type("Vehicle", (), {
        "components": {"Config": {"VehicleConfigAsset": {"ObjectPath": "/Game/Config.0"}},
                       "Vehicle Mesh": {"SkeletalMesh": {"ObjectPath": "/Game/Mesh.0"}}},
        "chain": ["/Game/Vehicle"],
    })()

    contact, _ = game_weapons.wheel_contact(assets, vehicle)

    assert contact == pytest.approx(11.0)


def test_an_emplacement_stands_on_the_bottom_of_its_mesh_bounds():
    assets = type("Assets", (), {"require": lambda self, package: [
        {"Type": "SkeletalMesh", "ImportedBounds": {"Origin": {"Z": 16.1}, "BoxExtent": {"Z": 21.9}}}]})()
    vehicle = type("Vehicle", (), {"components": {"Vehicle Mesh": {"SkeletalMesh": {"ObjectPath": "/Game/Tripod.1"}}}})()

    contact, _ = game_weapons.standing_contact(assets, vehicle)

    assert contact == pytest.approx(-5.8)


def test_the_launch_of_several_vehicles_is_the_middle_of_their_values_and_keeps_the_range():
    launch, text = game_weapons.Snapshot.merge_launches([
        ("/Game/V/BP_A", {"launch_height": 2.0, "muzzle_forward": 1.0, "muzzle_up": 0.1, "barrel_pitch": 0.5}, "a"),
        ("/Game/V/BP_B", {"launch_height": 2.4, "muzzle_forward": 1.0, "muzzle_up": 0.1, "barrel_pitch": 0.5}, "b"),
    ])

    assert launch["launch_height"] == 2.2
    assert launch["spread"] == {"launch_height": [2.0, 2.4]}
    assert text == "a | b"


def test_the_launch_of_vehicles_that_agree_has_no_range():
    launch, text = game_weapons.Snapshot.merge_launches([
        ("/Game/V/BP_A", {"launch_height": 2.0, "muzzle_forward": 1.0, "muzzle_up": 0.1, "barrel_pitch": 0.5}, "a"),
    ])

    assert "spread" not in launch
    assert text == "a"


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
