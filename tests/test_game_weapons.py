"""weapons.json against the game files.

tests/data/game_weapons.json is the snapshot tools/game_weapons.py writes from
the game's paks (build and date in its `_source`), one entry per weapons.json
entry: the muzzle velocity, the projectile's movement (gravity scale,
MaxSpeed, ConstantAcceleration and its timeout, bRotationFollowsVelocity,
bIgnoreGravityDuringConstantAcceleration), the view (bore, zoom) and the
elevation limits of the shot. Nothing in it is read from weapons.json, so an
entry copied from the wrong view or projectile fails here.
"""

import json
import os

import pytest

from ballistics import load_weapons

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as _file:
    GAME = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

# weapons.json writes a bore to two decimals; the 2A70's socket is at 0.675
# against the camera's 0.1, so its 0.575 is written 0.58 and 0.57.
BORE_ROUNDING = 0.0051

# The AGS-17 hold tops are where the measured lay stops (85.87 and 89.52
# degrees, tests/test_ballistics.py), 0.02 above the mount limits plus the
# socket (85.85 and 89.5); the entries keep the measurement as their top.
HOLD_TOP_OVER_LIMIT = 0.03


def test_every_entry_has_its_game_values():
    assert set(GAME) == set(WEAPONS)


@pytest.mark.parametrize("name", GAME)
def test_the_flight_is_the_games(name):
    game, weapon = GAME[name], WEAPONS[name]
    boosted = bool(game["acceleration"])

    assert weapon.velocity == pytest.approx(game["velocity"])
    assert weapon.max_speed == pytest.approx(game["max_speed"])

    if boosted and game["ignore_gravity_while_boosting"] and game["acceleration_timeout"] <= 0:
        # Gravity waits for a motor that never stops (NLAW): a straight flight.
        assert weapon.gravity == 0
    else:
        assert weapon.gravity == pytest.approx(game["gravity_scale"])

    if not boosted:
        assert not weapon.has_boost
        return

    assert weapon.acceleration == pytest.approx(game["acceleration"])
    assert weapon.rotation_follows_velocity == game["rotation_follows_velocity"]

    if game["acceleration_timeout"] > 0:
        assert weapon.acceleration_time == pytest.approx(game["acceleration_timeout"])
    else:
        # The motor never stops; the cap holds the speed from the moment it
        # reaches it, which the entry's time must cover.
        to_cap = (game["max_speed"] - game["velocity"]) / game["acceleration"]
        assert game["max_speed"] and weapon.acceleration_time >= to_cap - 1e-9


@pytest.mark.parametrize("name", [n for n in GAME if GAME[n]["bore"] is not None])
def test_the_view_is_the_games(name):
    game, weapon = GAME[name], WEAPONS[name]

    if not game.get("bore_assumed"):
        assert weapon.bore == pytest.approx(game["bore"], abs=BORE_ROUNDING)

    if not game.get("zoom_assumed"):
        assert weapon.zoom == (game["zoom"] if game["zoom"] > 1 else 0)


@pytest.mark.parametrize("name", [n for n in GAME if GAME[n]["elevation_limits"]])
def test_the_elevation_limits_are_the_games(name):
    (game_low, game_top), weapon = GAME[name]["elevation_limits"], WEAPONS[name]
    low, top = weapon.elevation_limits

    assert low == pytest.approx(game_low)

    if weapon.has_hold:
        assert game_top <= top <= game_top + HOLD_TOP_OVER_LIMIT
    else:
        assert top == pytest.approx(game_top)


def test_the_tripod_mk19_has_a_view_without_its_sights():
    """Claim 3 of the 1.6.0 review: without RMB the tripod MK19's camera is
    on the barrel's axis (bore 0), at the tripod's 235 m/s."""
    plain = WEAPONS["MK19 · emplacement / C16 / L134A1 · no sights"]

    assert (plain.velocity, plain.bore, plain.zoom) == (235, 0.0, 0)


def test_the_btr4_and_the_bmp1ts_have_their_own_ags30_bores():
    """Claim 7: 1.70 - 0.10 on the BTR-4, 1.65 - 0.10 on the BMP-1TS."""
    assert WEAPONS["AGS-30 / BTR-4 AGS"].bore == pytest.approx(1.6)
    assert WEAPONS["AGS-30 (BMP-1TS)"].bore == pytest.approx(1.55)


# The direct-fire weapons of a vehicle: the snapshot holds their launch point beside the view.
VEHICLE_MOUNTS = [n for n in GAME if "launch" in GAME[n] and GAME[n]["bore"] is not None]

VEHICLE_AGS17 = [n for n in VEHICLE_MOUNTS if n.startswith("AGS-17 · ") and "emplacement" not in n]


def test_the_vehicles_that_carry_the_ags17_mk19_and_spg9_have_entries():
    """The mounts found in the vehicle Blueprints of build 26005357 (tools/game_weapons.py ENTRIES)."""
    assert {n.split(" · ")[1] for n in VEHICLE_AGS17} == {"Technical", "Tigr", "Safir", "M1151", "BTR-D"}
    assert {n for n in VEHICLE_MOUNTS if n.startswith("MK19 · ")} == {
        "MK19 · AAVP-7A1", "MK19 · PARS III RWS", "MK19 · TAPV C16 RWS", "MK19 · M113 open turret",
        "MK19 · M113 open turret · no sights", "MK19 · M1151 open turret", "MK19 · M1151 open turret · no sights",
        "MK19 · MATV open turret", "MK19 · MATV open turret · no sights"}
    assert {n for n in VEHICLE_MOUNTS if n.startswith("SPG-9 · ")} == {
        f"SPG-9 · {shell} · {mount} · {view}" for shell in ("HEAT", "FRAG") for mount in ("technical", "INS armoured technical")
        for view in ("optic (RMB ×4)", "no optic")}


@pytest.mark.parametrize("name", VEHICLE_MOUNTS)
def test_every_blueprint_variant_of_a_vehicle_mount_fires_the_same(name):
    """Desert, Woodland, USMC, cage and camo Blueprints of a vehicle (the snapshot's `same_view`) have
    the entry's bore, zoom, limits and launch point: a variant that differs would be listed under
    `view_variants`."""
    assert "view_variants" not in GAME[name]


@pytest.mark.parametrize("name", VEHICLE_MOUNTS)
def test_a_vehicle_mount_launches_above_its_barrel_pivot(name):
    launch, weapon = GAME[name]["launch"], WEAPONS[name]

    assert weapon.launch_height == pytest.approx(launch["launch_height"], abs=5e-5)
    assert weapon.launch_height > 1.5
    assert weapon.muzzle_forward == pytest.approx(launch["muzzle_forward"], abs=5e-5)
    assert weapon.muzzle_up == pytest.approx(launch["muzzle_up"], abs=5e-5)


@pytest.mark.parametrize("name", VEHICLE_AGS17)
def test_a_vehicle_ags17_is_the_open_sight_gun_on_the_tripods_hold_model(name):
    """The vehicle turrets take the tripod's pitch input (x0.6) and limits (-13..85 degrees) and carry
    its open-sight gun (socket 4.5 degrees up): same bore, limits and hold as the iron-sights tripod."""
    iron = WEAPONS["AGS-17 · iron sights emplacement"]
    weapon = WEAPONS[name]

    assert (weapon.velocity, weapon.gravity, weapon.bore) == (iron.velocity, iron.gravity, iron.bore)
    assert (weapon.hold_rate, weapon.hold_elevation[0]) == (iron.hold_rate, iron.hold_elevation[0])
    assert weapon.arc == iron.arc == "high"
    assert weapon.elevation_limits[0] == iron.elevation_limits[0]
    assert weapon.hold_elevation[1] == pytest.approx(85 + 4.5)


def test_the_rpg7_tandem_rounds_leave_at_the_speed_of_their_class():
    """Issue 9: BP_RPG7_Tandem 63 m/s, BP_RPG7V1_Tandem 65, BP_RPG7V2_Tandem_2mag 117, all with the same
    projectile (motor 45 m/s^2 for 0.6 s, MaxSpeed 160)."""
    speeds = {n: WEAPONS[n].velocity for n in ("RPG-7 · PG-7VR Tandem", "RPG-7V1 · PG-7VR Tandem", "RPG-7V2 · PG-7VR Tandem")}

    assert speeds == {"RPG-7 · PG-7VR Tandem": 63, "RPG-7V1 · PG-7VR Tandem": 65, "RPG-7V2 · PG-7VR Tandem": 117}
    for name in speeds:
        assert (WEAPONS[name].acceleration, WEAPONS[name].acceleration_time, WEAPONS[name].max_speed) == (45, 0.6, 160)
