"""Behaviour of ballistics.py found by mutation testing (mutmut) that the other
test files did not pin: the flight of every weapon against the game's own
step integration (tests/flight.py, no code of the app), the straight-flight
helpers, the weapons.json checks and the mark geometry."""

import json
import math
import os
import subprocess
import sys
from dataclasses import replace

import pytest

import flight
from ballistics import (
    Weapon,
    WeaponDataError,
    LADDER_MAX_DISTANCE,
    LADDER_MAX_TICKS,
    first_obstacle,
    load_weapons,
    mark_height_resolution,
    mark_offset,
    mark_resolution,
    mark_visible_range,
    parse_weapons,
    range_ladder,
    resolve_arc,
    screen_offset,
    solve,
    trajectory,
    view_twin,
)
import ballistics

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as stream:
    GAME = json.load(stream)

with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as stream:
    RAW = json.load(stream)

GAME_WEAPONS = [name for name in WEAPONS if name in GAME]

# The closed forms and the tabulated boost follow the game's steps to a
# few millimetres; the path angle is compared with the slope of the step's
# straight segment, which differs from the velocity's direction by up to 2 mrad.
HEIGHT_TOLERANCE = 0.01
TIME_TOLERANCE = 1e-4
ANGLE_TOLERANCE = 5e-3


def distances_to_check(shot, rad):
    """Two distances the shot passes over: 30 % and 80 % of its range on flat
    ground, or 150 m and 600 m for a flight that never comes down."""
    reach = flight.range_at(shot, rad, 0.0)

    return (0.3 * reach, 0.8 * reach) if math.isfinite(reach) else (150.0, 600.0)


@pytest.mark.parametrize("name", GAME_WEAPONS)
def test_the_flight_follows_the_games_steps(name):
    weapon = WEAPONS[name]
    shot = flight.Shot(GAME[name], RAW[name])

    for degrees in (-4, 4, 20, 45, 75):
        rad = math.radians(degrees)

        for distance in distances_to_check(shot, rad):
            reached = flight.fly_to(shot, rad, distance)

            if reached is None:
                continue

            height, slope, _, seconds = reached
            at_height, at_seconds, at_angle = weapon.flight_at(rad, distance)

            assert at_height == pytest.approx(height, abs=HEIGHT_TOLERANCE), (degrees, distance)
            assert at_seconds == pytest.approx(seconds, abs=TIME_TOLERANCE), (degrees, distance)
            assert at_angle == pytest.approx(math.atan(slope), abs=ANGLE_TOLERANCE), (degrees, distance)
            assert weapon.flight_height(rad, distance) == pytest.approx(height, abs=HEIGHT_TOLERANCE)
            assert weapon.flight_time(rad, distance) == pytest.approx(seconds, abs=TIME_TOLERANCE)


def oracle_apex(shot, rad, distance):
    """(top, height at `distance`, muzzle height) of the game's step flight
    up to `distance` m ahead of the pivot, `top` being the highest corner of
    its steps; None when it never gets there."""
    reached = flight.fly_to(shot, rad, distance)

    if reached is None:
        return None

    path = flight._Flight(shot, rad)
    muzzle_height = top = path.y

    while path.x < distance:
        path.advance()
        if path.x <= distance:
            top = max(top, path.y)

    return top, reached[0], muzzle_height


@pytest.mark.parametrize("name", GAME_WEAPONS)
def test_the_apex_follows_the_games_steps(name):
    """The apex is the top the flight has passed and come down from by `distance`."""
    weapon = WEAPONS[name]
    shot = flight.Shot(GAME[name], RAW[name])

    for degrees in (-4, 4, 20, 45, 75, 89):
        rad = math.radians(degrees)

        for distance in (*distances_to_check(shot, rad), 40.0):
            found = oracle_apex(shot, rad, distance)

            if found is None:
                continue

            top, at_distance, muzzle_height = found

            if top > muzzle_height + 0.05 and top > at_distance + 0.05:
                assert weapon.apex_height(rad, distance) == pytest.approx(
                    top, abs=HEIGHT_TOLERANCE
                ), (degrees, distance)


CUSTOM_HEIGHT_TOLERANCE = HEIGHT_TOLERANCE
CUSTOM_TIME_TOLERANCE = 1e-3

CUSTOM_FLIGHTS = {
    "rocket that turns with the velocity": {
        "velocity": 60, "acceleration": 40, "acceleration_time": 2.5, "rotation_follows_velocity": True,
    },
    "rocket flying along the barrel": {
        "velocity": 60, "acceleration": 40, "acceleration_time": 2.5, "rotation_follows_velocity": False,
    },
    "shell that nearly stops": {
        "velocity": 1, "deceleration": 0.5, "deceleration_time": 1.9, "rotation_follows_velocity": False,
    },
    "slowing shell": {
        "velocity": 120, "deceleration": 20, "deceleration_time": 4.0,
    },
    "shell from a raised muzzle": {
        "velocity": 90, "launch_height": 1.4, "muzzle_forward": 0.9, "muzzle_up": 0.3,
    },
}


def custom_game(raw):
    """The snapshot entry of the game for a weapons.json entry of CUSTOM_FLIGHTS."""
    return {
        "velocity": raw["velocity"],
        "gravity_scale": raw.get("gravity", 1.0),
        "max_speed": raw.get("max_speed", 0.0),
        "acceleration": raw.get("acceleration", -raw.get("deceleration", 0.0)),
        "acceleration_timeout": raw.get("acceleration_time", raw.get("deceleration_time", 0.0)),
        "rotation_follows_velocity": raw.get("rotation_follows_velocity", True),
    }


@pytest.mark.parametrize("name", CUSTOM_FLIGHTS)
def test_the_flight_of_made_up_weapons_follows_the_games_steps(name):
    raw = CUSTOM_FLIGHTS[name]
    weapon = Weapon.from_dict("w", raw)
    shot = flight.Shot(custom_game(raw), raw)

    for degrees in (-4, 0, 4, 20, 45, 75, 89):
        rad = math.radians(degrees)

        for distance in (0.5, 0.99, 5.0, 20.0, 60.0, 120.0, 250.0, 400.0, 900.0):
            reached = flight.fly_to(shot, rad, distance)

            if reached is None:
                continue

            height, slope, _, seconds = reached
            at_height, at_seconds, at_angle = weapon.flight_at(rad, distance)

            assert at_height == pytest.approx(height, abs=CUSTOM_HEIGHT_TOLERANCE), (degrees, distance)
            assert at_seconds == pytest.approx(seconds, abs=CUSTOM_TIME_TOLERANCE), (degrees, distance)
            assert at_angle == pytest.approx(math.atan(slope), abs=ANGLE_TOLERANCE), (degrees, distance)
            assert weapon.flight_height(rad, distance) == pytest.approx(height, abs=CUSTOM_HEIGHT_TOLERANCE)

            found = oracle_apex(shot, rad, distance)
            top, at_distance, muzzle_height = found

            if top > muzzle_height + 0.05 and top > at_distance + 0.05:
                assert weapon.apex_height(rad, distance) == pytest.approx(
                    top, abs=CUSTOM_HEIGHT_TOLERANCE
                ), (degrees, distance)


# ---------- the weapons.json entry ----------

def entry_error(data, name="w"):
    with pytest.raises(WeaponDataError) as caught:
        Weapon.from_dict(name, data)

    return str(caught.value)


@pytest.mark.parametrize("data, message", [
    ([1], "w: entry must be an object"),
    ({"velocity": 1, "zeta": 1, "alpha": 2}, "w: unknown keys alpha, zeta"),
    ({}, "w: 'velocity' is required"),
    ({"velocity": True}, "w: 'velocity' must be a number"),
    ({"velocity": "fast"}, "w: 'velocity' must be a number"),
    ({"velocity": None}, "w: 'velocity' must be a number"),
    ({"velocity": float("inf")}, "w: 'velocity' must be finite"),
    ({"velocity": 0}, "w: 'velocity' must be > 0"),
    ({"velocity": 10, "gravity": -1}, "w: 'gravity' must be >= 0"),
    ({"velocity": 10, "acceleration_time": -1}, "w: 'acceleration_time' must be >= 0"),
    ({"velocity": 10, "acceleration": -10, "acceleration_time": 1}, "w: deceleration would stop the projectile"),
    ({"velocity": 10, "max_speed": -1}, "w: 'max_speed' must be >= 0 (0: none)"),
    ({"velocity": 10, "rotation_follows_velocity": 1}, "w: 'rotation_follows_velocity' must be true or false"),
    ({"velocity": 300, "gravity": 0, "max_speed": 250},
     "w: a projectile without gravity cannot start above 'max_speed'"),
    ({"velocity": 10, "launch_height": -1}, "w: 'launch_height' must be >= 0"),
    ({"velocity": 10, "arc": "flat"}, "w: 'arc' must be one of ('low', 'high')"),
    ({"velocity": 10, "unit": "rad"}, "w: 'unit' must be one of ('deg', 'mil')"),
    ({"velocity": 10, "aim": "eye"}, "w: 'aim' must be one of ('overlay', 'elevation')"),
    ({"velocity": 10, "elevation_limits": 5}, "w: 'elevation_limits' must be [min, max]"),
    ({"velocity": 10, "elevation_limits": [1, 2, 3]}, "w: 'elevation_limits' must be [min, max]"),
    ({"velocity": 10, "elevation_limits": [10, 10]}, "w: invalid 'elevation_limits'"),
    ({"velocity": 10, "elevation_limits": [20, 10]}, "w: invalid 'elevation_limits'"),
    ({"velocity": 10, "zoom": 0.5}, "w: 'zoom' must be >= 1 (or 0: none)"),
    ({"velocity": 10, "view": "sideways"}, "w: 'view' must be one of ('optic', 'plain')"),
    ({"velocity": 10, "view": "optic"}, "w: an 'optic' view needs a 'zoom'"),
    ({"velocity": 10, "view": "plain", "zoom": 2}, "w: a 'plain' view has no 'zoom'"),
    ({"velocity": 10, "twin": "x"},
     "w: 'twin' (the plain view's name) goes with the 'optic' view, and only there"),
    ({"velocity": 10, "view": "optic", "zoom": 2},
     "w: 'twin' (the plain view's name) goes with the 'optic' view, and only there"),
    ({"velocity": 10, "view": "optic", "zoom": 2, "twin": 5},
     "w: 'twin' (the plain view's name) goes with the 'optic' view, and only there"),
    ({"velocity": 10, "hold_rate": -1}, "w: 'hold_rate' must be >= 0"),
    ({"velocity": 10, "warhead": "nuclear"}, "w: 'warhead' must be one of direct, splash"),
    ({"velocity": 10, "hold_rate": 5, "hold_elevation": [0, 80], "acceleration": 1},
     "w: a weapon laid by holding a key cannot have a boost"),
    ({"velocity": 10, "hold_rate": 5}, "w: 'hold_rate' needs 'hold_elevation': [lowest, top]"),
    ({"velocity": 10, "hold_rate": 5, "hold_elevation": 5}, "w: 'hold_rate' needs 'hold_elevation': [lowest, top]"),
    ({"velocity": 10, "hold_rate": 5, "hold_elevation": [10, 10]},
     "w: 'hold_elevation' must lie within 'elevation_limits' and go from lowest to top"),
    ({"velocity": 10, "hold_rate": 5, "hold_elevation": [0, 95]},
     "w: 'hold_elevation' must lie within 'elevation_limits' and go from lowest to top"),
    ({"velocity": 10, "hold_rate": 5, "hold_elevation": [-95, 10]},
     "w: 'hold_elevation' must lie within 'elevation_limits' and go from lowest to top"),
])
def test_an_invalid_entry_is_refused_with_its_reason(data, message):
    assert entry_error(data) == message


def test_limits_that_the_entry_reaches_exactly_are_valid():
    assert Weapon.from_dict("w", {"velocity": 0.5}).velocity == 0.5
    assert Weapon.from_dict("w", {"velocity": 10, "acceleration": -9.5, "acceleration_time": 1}).acceleration == -9.5
    assert Weapon.from_dict("w", {"velocity": 300, "gravity": 0, "max_speed": 300}).max_speed == 300
    assert Weapon.from_dict("w", {"velocity": 10, "zoom": 1}).zoom == 1
    assert Weapon.from_dict("w", {"velocity": 10, "zoom": 0}).zoom == 0
    assert Weapon.from_dict("w", {"velocity": 10, "launch_height": 0, "muzzle_forward": 0}).launch_height == 0
    held = Weapon.from_dict("w", {
        "velocity": 10, "hold_rate": 5, "hold_elevation": [-90, 90], "elevation_limits": [-90, 90],
    })
    assert held.hold_elevation == (-90.0, 90.0)


def test_an_entry_with_every_field_is_read_field_by_field():
    weapon = Weapon.from_dict("w", {
        "velocity": 120, "gravity": 0.5, "arc": "high", "unit": "mil", "aim": "overlay",
        "angle_offset": 1.5, "acceleration": 10, "deceleration": 4, "acceleration_time": 2,
        "max_speed": 300, "rotation_follows_velocity": False, "min_distance": 35,
        "elevation_limits": [5, 85], "launch_height": 1.5, "muzzle_forward": 0.7, "muzzle_up": 0.2,
        "bore": 0.4, "zoom": 3, "category": "guns",
        "warhead": "splash", "note": "a note", "view": "optic", "twin": "w plain",
    })

    assert weapon == Weapon(
        name="w", velocity=120.0, gravity=0.5, arc="high", unit="mil", aim="overlay",
        angle_offset=1.5, acceleration=6.0, acceleration_time=2.0, max_speed=300.0,
        rotation_follows_velocity=False, min_distance=35.0, elevation_limits=(5.0, 85.0),
        launch_height=1.5, muzzle_forward=0.7, muzzle_up=0.2, bore=0.4, zoom=3.0,
        category="guns", warhead="splash",
        note="a note", view="optic", twin="w plain",
    )


def test_an_entry_with_only_a_velocity_gets_the_defaults():
    assert Weapon.from_dict("w", {"velocity": 100}) == Weapon(
        name="w", velocity=100.0, gravity=1.0, arc="low", unit="deg", aim="overlay",
        angle_offset=0.0, acceleration=0.0, acceleration_time=0.0, max_speed=0.0,
        rotation_follows_velocity=True, min_distance=0.0, elevation_limits=(-90.0, 90.0),
        launch_height=0.0, muzzle_forward=0.0, muzzle_up=0.0, bore=0.0, zoom=0.0,
        hold_rate=0.0, hold_elevation=(), category="other", warhead="direct", note="",
        view="", twin="",
    )
    assert Weapon.from_dict("w", {"velocity": 100, "arc": "high"}).aim == "elevation"


def test_a_deceleration_is_a_negative_acceleration_with_its_own_time():
    weapon = Weapon.from_dict("w", {"velocity": 100, "deceleration": 5, "deceleration_time": 3})

    assert (weapon.acceleration, weapon.acceleration_time) == (-5.0, 3.0)
    assert Weapon.from_dict("w", {"velocity": 100, "deceleration": 5}).acceleration_time == 0.0
    assert Weapon.from_dict(
        "w", {"velocity": 100, "acceleration_time": 1, "deceleration_time": 3}
    ).acceleration_time == 1.0


def test_the_weapons_file_is_checked_with_a_message_each_for_what_is_wrong(tmp_path):
    with pytest.raises(WeaponDataError) as caught:
        parse_weapons([])
    assert str(caught.value) == "weapons.json must contain an object"

    with pytest.raises(WeaponDataError) as caught:
        parse_weapons({"_comment": "only a comment"})
    assert str(caught.value) == "weapons.json does not define any weapons"

    missing = tmp_path / "missing.json"
    with pytest.raises(WeaponDataError) as caught:
        load_weapons(str(missing))
    assert str(caught.value) == f"Weapons file not found: {missing}"

    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(WeaponDataError) as caught:
        load_weapons(str(broken))
    assert str(caught.value).startswith("weapons.json is not valid JSON: Expecting property name")


def test_the_weapons_file_is_read_as_utf8_whatever_the_locale(tmp_path):
    path = tmp_path / "weapons.json"
    path.write_bytes(json.dumps({"Mörser": {"velocity": 100}}, ensure_ascii=False).encode("utf-8"))

    assert list(load_weapons(str(path))) == ["Mörser"]

    script = (
        "import sys, ballistics\n"
        "print(ascii(list(ballistics.load_weapons(sys.argv[1]))))\n"
    )
    environment = {
        **os.environ,
        "PYTHONPATH": ROOT,
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
        "LC_ALL": "C",
    }
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        env=environment, capture_output=True, text=True, check=True, cwd=ROOT,
    )

    assert result.stdout.strip() == "['M\\xf6rser']"


# ---------- the two views of an RMB sight ----------

def test_the_two_views_of_an_rmb_sight_name_each_other():
    assert view_twin(WEAPONS, "QLZ87 · optic (RMB ×3)") == "QLZ87 · no optic"
    assert view_twin(WEAPONS, "QLZ87 · no optic") == "QLZ87 · optic (RMB ×3)"
    assert view_twin(WEAPONS, "RPG-29") is None
    assert view_twin(WEAPONS, "not a weapon") is None


# ---------- the hold weapons ----------

def test_the_key_holds_the_barrel_down_to_the_lowest_elevation_inclusive():
    lob = Weapon.from_dict("w", {
        "velocity": 100, "arc": "high", "aim": "elevation", "hold_rate": 10, "hold_elevation": [20, 80],
    })

    assert (lob.hold_rate, lob.hold_elevation) == (10.0, (20.0, 80.0))
    assert lob.hold_time(80) == 0.0
    assert lob.hold_time(20) == 6.0
    assert math.isnan(lob.hold_time(19.9))
    assert math.isnan(lob.hold_time(80.1))


# ---------- a straight (gravity-free) flight ----------

BOOSTED = {"velocity": 100, "gravity": 0, "acceleration": 50, "acceleration_time": 2}


def test_a_straight_flight_covers_a_distance_in_the_time_the_motor_and_the_cruise_take():
    plain = Weapon.from_dict("p", {"velocity": 100, "gravity": 0})
    boosted = Weapon.from_dict("b", BOOSTED)
    mid = 150.0

    assert plain.time_to(250.0) == 2.5
    assert plain.time_to(0) == 0.0
    assert plain.time_to(-5) == 0.0
    assert boosted.time_to(-5) == 0.0
    assert boosted.time_to(mid) == pytest.approx((-100 + math.sqrt(100 ** 2 + 2 * 50 * mid)) / 50)
    # The 2 s motor acts on 99 steps: 99 / 49.87 s under the motor, then its end speed
    burn = 99 / 49.87
    assert boosted.boost_distance == pytest.approx(100 * burn + 25 * burn ** 2)
    assert boosted.cruise_velocity == pytest.approx(100 + 50 * burn)
    assert boosted.time_to(500.0) == pytest.approx(burn + (500 - boosted.boost_distance) / boosted.cruise_velocity)


def test_a_motor_that_slows_the_shell_to_a_crawl_takes_the_whole_boost_to_cover_its_distance():
    slowed = Weapon.from_dict("s", {"velocity": 10, "gravity": 0, "acceleration": -4.9, "acceleration_time": 2})

    burn = 99 / 49.87
    assert slowed.boost_distance == pytest.approx(10 * burn - 2.45 * burn ** 2)
    assert slowed.time_to(slowed.boost_distance) == pytest.approx(burn)


def test_the_average_speed_of_a_straight_flight_is_distance_over_time():
    plain = Weapon.from_dict("p", {"velocity": 100, "gravity": 0})
    boosted = Weapon.from_dict("b", BOOSTED)

    for distance in (-5, 0):
        assert plain.velocity_at(distance) == 100
        assert boosted.velocity_at(distance) == 100
    assert plain.velocity_at(1.0) == 100
    assert boosted.velocity_at(1.0) == pytest.approx(1.0 / boosted.time_to(1.0))
    assert boosted.velocity_at(250.0) == pytest.approx(250.0 / boosted.time_to(250.0))


# ---------- the steps the motor acts on ----------

def test_a_motor_of_a_whole_number_of_frames_up_to_1e_9_of_a_frame_does_not_gain_a_step():
    def motor(frames, gravity=0):
        return Weapon(
            name="m", velocity=100, gravity=gravity, acceleration=100,
            acceleration_time=frames * ballistics.FRAME_TIME, max_speed=1000,
        )

    assert motor(40 + 1e-10).boost_steps == 39      # a rounding above 40 frames
    assert motor(40 - 1e-10).boost_steps == 39      # a rounding below
    assert motor(40 + 2e-9).boost_steps == 40       # 2e-9 of a frame past 40
    assert motor(40 + 1e-10).burn_time == 39 * ballistics.FRAME_TIME
    assert motor(40 + 1e-10)._axis_boost_time == 39 * ballistics.FRAME_TIME
    # a motor of one frame and a rounding never acts
    assert not motor(1 + 1e-10, gravity=1).has_boost
    assert motor(1 + 2e-9, gravity=1).has_boost
    assert motor(1 + 1e-10)._axis_boost_time == 0.0
    assert motor(1 + 2e-9)._axis_boost_time == ballistics.FRAME_TIME


def test_the_axis_motor_ends_at_the_cap_when_it_is_reached_before_the_burn_ends():
    nlaw = Weapon(
        name="n", velocity=40, gravity=0, acceleration=350,
        acceleration_time=0.65, max_speed=250,
    )

    assert nlaw.boost_steps == 32
    assert nlaw.burn_time > 0.64                    # the burn is 0.6417 s
    assert nlaw._axis_boost_time == pytest.approx(0.6, abs=1e-12)  # the time to the cap
    assert replace(nlaw, max_speed=1000)._axis_boost_time == nlaw.burn_time  # a cap not reached
    assert replace(nlaw, max_speed=0)._axis_boost_time == nlaw.burn_time     # no cap
    assert replace(nlaw, velocity=260)._axis_boost_time == 0.0  # fired above the cap
    # with gravity the cap does not end the motor; a motor that slows down is not ended by it
    assert replace(nlaw, gravity=1)._axis_boost_time == nlaw.burn_time
    slowing = replace(nlaw, acceleration=-50)
    assert slowing._axis_boost_time == slowing.burn_time


def test_the_cap_of_an_axis_motor_binds_on_the_speed_after_its_steps_not_after_its_time():
    # 100 m/s and 100 m/s^2 for 49 steps (0.98255 s): 198.255 m/s, 207.88 with
    # gravity; the 1 s of the motor's time would reach 209.8
    motor = Weapon(
        name="m", velocity=100, gravity=1, acceleration=100, acceleration_time=1,
        rotation_follows_velocity=False,
    )

    def capped(**fields):
        return replace(motor, **fields).flies_boost_in_steps

    assert motor.boost_steps == 49
    assert not capped(max_speed=209)                # the steps do not reach the cap
    assert not capped(max_speed=207.95)             # the gravity term is that of the steps, not of the time (208.06)
    assert capped(max_speed=207.8)                  # the steps do reach it
    at_end = abs(motor.velocity + motor.acceleration * motor.burn_time) + motor.g * motor.burn_time
    assert not capped(max_speed=at_end)             # a speed at the cap is not clamped
    assert capped(max_speed=90, acceleration=1)     # fired above the cap
    assert capped(velocity=300, acceleration=-100, max_speed=250)  # and slowed under it by the motor
    assert not capped(max_speed=0)
    # a motor that slows the projectile past zero: the speed at the end is the magnitude of v0 + a T
    assert capped(velocity=10, acceleration=-200, max_speed=150)   # 186 m/s backwards
    assert not capped(velocity=10, acceleration=-200, max_speed=250)


# ---------- the speed cap on a parabola ----------

def test_a_parabola_is_checked_against_the_cap_only_when_there_is_one():
    uncapped = Weapon.from_dict("u", {"velocity": 300})
    capped = Weapon.from_dict("c", {"velocity": 300, "max_speed": 310})

    assert uncapped._clamps_before(-5000.0) is False
    # v^2 + 2 g drop = 310^2 at a drop of (310^2 - 300^2) / (2 g) = 311.2 m
    assert capped._clamps_before(-311.0) is False
    assert capped._clamps_before(-311.5) is True


def test_a_shell_that_reaches_its_cap_exactly_has_not_been_clamped():
    exact = Weapon.from_dict("e", {"velocity": 48, "max_speed": 50, "launch_height": 0})
    drop = (50 ** 2 - 48 ** 2) / (2 * exact.g)

    assert exact._clamps_before(-drop * 1.001) is True
    assert exact._clamps_before(-drop * 0.999) is False


# ---------- solving ----------

SHELL = {"velocity": 100}
MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


def refusal(call, *args, **kwargs):
    with pytest.raises(ValueError) as caught:
        call(*args, **kwargs)

    return str(caught.value)


def test_an_arc_is_the_weapons_own_for_nothing_empty_or_auto():
    weapon = Weapon.from_dict("w", {**SHELL, "arc": "high"})

    for arc in (None, "", "auto"):
        assert resolve_arc(weapon, arc) == "high"
    assert resolve_arc(weapon, "low") == "low"
    assert refusal(resolve_arc, weapon, "flat") == "Unknown arc 'flat'"


def test_a_solution_is_refused_with_the_reason_in_words():
    weapon = Weapon.from_dict("w", SHELL)

    assert refusal(solve, weapon, 0) == "Distance must be greater than 0"
    assert refusal(solve, weapon, math.inf) == "Distance must be greater than 0"
    assert refusal(solve, weapon, 100, math.nan) == "Height difference must be a number"


def test_a_target_beyond_the_range_is_refused_with_the_maximum_range():
    weapon = Weapon.from_dict("w", SHELL)
    solution = solve(weapon, 5000.0)

    assert not solution.reachable
    assert solution.reason_code == "out_of_range"
    assert solution.reason == "Out of range (max ~1020 m on flat ground)"


# 100 m/s lands 349.0 m away on level ground at the 10 degrees this mount stops at
STOPPED = {"velocity": 100, "min_distance": 349, "elevation_limits": [10, 45]}


def test_a_target_closer_than_the_minimum_distance_that_no_arc_reaches_is_refused_in_words():
    weapon = Weapon.from_dict("w", STOPPED)

    for arc in ("low", "high"):
        solution = solve(weapon, 348.0, 0.0, arc)

        assert not solution.reachable
        assert (solution.reason_code, solution.reason) == (
            "too_close", "Too close: minimum distance on level ground is 349 m"
        )
        assert solution.alternatives == {}
    assert solve(weapon, 350.0).reachable


def test_the_minimum_distance_refuses_nothing_the_mount_can_be_laid_on():
    weapon = Weapon.from_dict("w", STOPPED)
    uphill = solve(weapon, 200.0, 60.0)

    assert uphill.reachable and 10 <= uphill.angle <= 45
    assert ballistics.height_at(weapon, uphill.angle, 200.0) == pytest.approx(60.0, abs=1e-6)
    # without limits nothing stops the barrel: the minimum is only a figure
    assert solve(Weapon.from_dict("w", {**SHELL, "min_distance": 35}), 20.0).reachable


def test_nearer_than_the_minimum_an_arc_that_can_be_fired_is_offered_instead_of_too_close():
    weapon = Weapon.from_dict("w", STOPPED)
    high = solve(weapon, 200.0, 60.0, "high")

    assert not high.reachable
    assert high.reason_code == "elevation_limit"
    assert list(high.alternatives) == ["low"]


def test_a_target_that_is_not_past_the_muzzle_is_refused_in_words():
    weapon = Weapon.from_dict("w", {"velocity": 100, "muzzle_forward": 2.0, "launch_height": 1.0})
    # the barrel that points at a target 1 m ahead and 1.5 m up has its muzzle 1.79 m ahead
    solution = solve(weapon, 1.0, 1.5)

    assert not solution.reachable
    assert (solution.reason_code, solution.reason) == ("behind_muzzle", "Too close: the target is not past the muzzle")
    assert "low" not in solution.alternatives
    # no elevation puts the muzzle farther ahead than the barrel is long
    assert solve(weapon, 2.01, 1.5).reachable


def test_an_angle_beyond_the_elevation_limits_is_refused_in_words():
    weapon = Weapon.from_dict("w", {**SHELL, "elevation_limits": [20, 80]})
    solution = solve(weapon, 500.0)

    assert solution.reason_code == "elevation_limit"
    assert solution.reason == "Low arc needs 14.7°, weapon elevation is limited to 20°..80°"


def test_a_lob_beyond_what_the_key_can_hold_is_refused_in_words():
    lob = Weapon.from_dict("w", {
        **SHELL, "arc": "high", "aim": "elevation", "hold_rate": 10, "hold_elevation": [80, 85],
    })
    solution = solve(lob, 500.0)

    assert solution.reason_code == "hold_limit"
    assert solution.reason == "High arc needs 75.3°, holding the key is limited to 80°..85°"


def test_the_straight_shot_of_a_launcher_above_the_ground_aims_down_to_the_target_ground():
    gun = Weapon.from_dict("g", {"velocity": 100, "gravity": 0, "launch_height": 2.0})
    solution = solve(gun, 100.0, 0.0)

    assert solution.raw_angle == pytest.approx(-math.degrees(math.atan2(2.0, 100.0)))
    assert solve(gun, 100.0, 0.0, aim_lift=2.0).raw_angle == pytest.approx(0.0)


def test_the_speed_along_the_path_is_the_distance_from_the_muzzle_over_the_time():
    gun = Weapon.from_dict("g", {"velocity": 100, "gravity": 0, "muzzle_forward": 2.0})
    solution = solve(gun, 52.0)

    assert solution.time_of_flight == pytest.approx(0.5)
    assert solution.velocity == pytest.approx(100.0)


def test_the_angles_a_weapon_can_take_are_inclusive_and_each_arc_is_judged_alone():
    gun = Weapon.from_dict("g", {"velocity": 100, "gravity": 0, "elevation_limits": [-90, 45]})
    assert solve(gun, 100.0, 100.0).reachable
    assert solve(gun, 100.0, 100.0).alternatives["low"] == pytest.approx(45.0)

    gun = Weapon.from_dict("g", {"velocity": 100, "gravity": 0, "elevation_limits": [45, 90]})
    assert solve(gun, 100.0, 100.0).reachable

    shell = Weapon.from_dict("s", {**SHELL, "elevation_limits": [45, 90]})
    both = solve(shell, 500.0, arc="high")
    assert both.reachable and list(both.alternatives) == ["high"]


def test_the_alternatives_are_read_off_the_weapons_scale():
    shell = Weapon.from_dict("s", {**SHELL, "angle_offset": 3.0})
    solution = solve(shell, 500.0)

    assert solution.alternatives["low"] == pytest.approx(solution.raw_angle - 3.0)
    assert solution.angle == solution.alternatives["low"]


def test_a_path_is_sampled_at_sixty_five_points_by_default():
    weapon = Weapon.from_dict("w", SHELL)

    assert len(trajectory(weapon, solve(weapon, 500.0))) == 65
    assert len(trajectory(weapon, solve(weapon, 500.0), points=8)) == 9


# ---------- the first obstacle on the way ----------

def test_a_path_that_cannot_be_checked_has_no_obstacle():
    weapon = Weapon.from_dict("w", SHELL)
    solution = solve(weapon, 500.0)
    profile = [0.0] * 101

    assert first_obstacle(weapon, solution, profile, 0) is None
    assert first_obstacle(weapon, solution, [], 5) is None
    assert first_obstacle(weapon, solve(weapon, 5000.0), [1000.0] * 100, 5) is None


def test_the_obstacle_is_found_on_the_arc_that_was_solved_for():
    weapon = Weapon.from_dict("w", SHELL)
    wall = [0.0] * 101
    wall[50] = 100.0

    assert first_obstacle(weapon, solve(weapon, 500.0, 0.0, "low"), wall, 5) == (250, 100.0)
    assert first_obstacle(weapon, solve(weapon, 500.0, 0.0, "high"), wall, 5) is None


def test_the_ground_near_the_muzzle_and_up_to_the_target_clearance_is_checked():
    weapon = Weapon.from_dict("w", SHELL)
    solution = solve(weapon, 503.0)
    near = [0.0] * 101
    near[2] = 50.0
    last = [0.0] * 101
    last[100] = 1000.0

    assert first_obstacle(weapon, solution, near, 5) == (10, 50.0)
    assert first_obstacle(weapon, solution, last, 5) == (500, 1000.0)
    assert first_obstacle(weapon, solve(weapon, 502.0), last, 5) is None


# ---------- the screen ----------

def test_a_screen_offset_needs_a_sensible_view():
    assert refusal(screen_offset, 1.0, 0.5, 1920) == "FOV must be between 1 and 179 degrees"
    assert refusal(screen_offset, 1.0, 180, 1920) == "FOV must be between 1 and 179 degrees"
    assert refusal(screen_offset, 1.0, 90, 0) == "Screen width must be positive"
    assert refusal(screen_offset, 1.0, 90, -5) == "Screen width must be positive"
    assert screen_offset(1.0, 1, 1920) > 0
    assert screen_offset(1.0, 179, 1920) > 0
    assert screen_offset(1.0, 90, 1) > 0


def test_a_screen_offset_of_nearly_straight_up_or_down_is_infinite():
    assert screen_offset(89.9, 90, 1920) == math.inf
    assert screen_offset(-89.9, 90, 1920) == -math.inf
    assert math.isfinite(screen_offset(89.89, 90, 1920))


def test_a_mark_needs_a_sensible_fov():
    weapon = Weapon.from_dict("w", SHELL)
    message = "FOV must be between 1 and 179 degrees"

    assert refusal(mark_offset, weapon, 1.0, 0.99, 1920) == message
    assert refusal(mark_offset, weapon, 1.0, 180, 1920) == message
    assert refusal(mark_offset, weapon, 1.0, 181, 1920) == message
    assert mark_offset(weapon, 1.0, 1, 1920) > 0
    assert mark_offset(weapon, 1.0, 179, 1920) > 0


# ---------- the mark ----------

FOV = 90
WIDTH = 1920


def mark_at(weapon, distance, height=0.0, scale=1.0, arc="low", lift=0.0):
    """Pixels below the centre of the mark of a target, None if it cannot be hit."""
    solution = solve(weapon, distance, height, arc, lift)

    if not solution.reachable:
        return None

    return mark_offset(weapon, solution.sight_angle, FOV, WIDTH, scale)


def pixel_resolution(weapon, distance, height=0.0, scale=1.0, arc="low", lift=0.0):
    """Metres of range per pixel from the marks 1 cm either side of `distance`,
    all laid over the line of sight to the target itself."""
    centre = solve(weapon, distance, height, arc, lift)
    line_of_sight = centre.angle - centre.sight_angle

    def offset(at):
        angle = solve(weapon, at, height, arc, lift).angle - line_of_sight
        return mark_offset(weapon, angle, FOV, WIDTH, scale)

    return 0.02 / (offset(distance + 0.01) - offset(distance - 0.01))


@pytest.mark.parametrize("kwargs", [
    {},
    {"height": 20.0},
    {"height": -15.0, "lift": 2.0},
    {"scale": 1.25},
])
def test_a_pixel_of_the_mark_is_worth_the_range_the_marks_either_side_show(kwargs):
    weapon = Weapon.from_dict("w", {**SHELL, "launch_height": 1.5})
    lift = {"aim_lift": kwargs["lift"]} if "lift" in kwargs else {}

    result = mark_resolution(
        weapon, 500.0, kwargs.get("height", 0.0), FOV, WIDTH, kwargs.get("scale", 1.0),
        "low", **lift
    )

    assert result == pytest.approx(pixel_resolution(weapon, 500.0, **kwargs), rel=1e-5)


def test_the_mark_resolution_defaults_are_the_low_arc_and_no_lift():
    weapon = Weapon.from_dict("w", SHELL)

    assert mark_resolution(weapon, 500.0, 0.0, FOV, WIDTH) == mark_resolution(
        weapon, 500.0, 0.0, FOV, WIDTH, 1.0, "low", 0.0
    )
    assert mark_height_resolution(weapon, 500.0, 0.0, FOV, WIDTH) == mark_height_resolution(
        weapon, 500.0, 0.0, FOV, WIDTH, 1.0, "low", 0.0
    )


def test_a_pixel_of_the_mark_is_worth_range_even_one_metre_from_the_weapon():
    weapon = Weapon.from_dict("w", SHELL)

    assert mark_resolution(weapon, 1.0, 0.0, FOV, WIDTH) == pytest.approx(
        pixel_resolution(weapon, 1.0), rel=1e-3
    )
    assert mark_resolution(weapon, 2.0, 0.0, FOV, WIDTH) == pytest.approx(
        pixel_resolution(weapon, 2.0), rel=1e-3
    )


def test_there_is_no_mark_resolution_without_a_mark_or_drop_or_a_target():
    mortar = WEAPONS[MORTAR]
    straight = Weapon.from_dict("s", {"velocity": 100, "gravity": 0})
    shell = Weapon.from_dict("w", SHELL)

    assert mark_resolution(mortar, 300.0, 0.0, FOV, WIDTH) is None
    assert mark_resolution(straight, 300.0, 0.0, FOV, WIDTH) is None
    assert mark_resolution(shell, 5000.0, 0.0, FOV, WIDTH) is None
    assert mark_height_resolution(mortar, 300.0, 0.0, FOV, WIDTH) is None


def test_the_mark_of_a_high_arc_moves_up_with_the_range_so_a_pixel_is_worth_nothing():
    weapon = Weapon.from_dict("w", SHELL)

    assert mark_resolution(weapon, 500.0, 0.0, FOV, WIDTH, arc="high") is None
    assert mark_height_resolution(weapon, 500.0, 0.0, FOV, WIDTH, arc="high") is None


def test_a_mark_that_does_not_move_with_the_range_is_worth_nothing(monkeypatch):
    weapon = Weapon.from_dict("w", SHELL)
    monkeypatch.setattr(ballistics, "mark_offset", lambda *args, **kwargs: 5.0)

    assert mark_resolution(weapon, 500.0, 0.0, FOV, WIDTH) is None


def test_a_pixel_of_the_mark_is_worth_the_height_the_path_passes_the_target_by():
    weapon = Weapon.from_dict("w", {**SHELL, "launch_height": 1.5})

    for lift in (0.0, 2.0):
        metres = mark_resolution(weapon, 400.0, 10.0, FOV, WIDTH, aim_lift=lift)
        impact = solve(weapon, 400.0, 10.0, "low", lift).impact_angle

        assert mark_height_resolution(weapon, 400.0, 10.0, FOV, WIDTH, aim_lift=lift) == pytest.approx(
            metres * math.tan(math.radians(impact))
        )


def test_the_mark_of_a_lifted_aim_is_what_the_visible_range_is_judged_by():
    weapon = Weapon.from_dict("w", {**SHELL, "min_distance": 100})
    options = {"scale": 1.1, "arc": "low", "aim_lift": 2.0}

    def lifted(distance):
        return mark_at(weapon, distance, 0.0, 1.1, "low", 2.0)

    top = lifted(200.0)
    bottom = lifted(600.0)
    near, far = mark_visible_range(weapon, 0.0, FOV, WIDTH, top, bottom, **options)

    assert lifted(near - 0.01) < top <= lifted(near + 0.02)
    assert lifted(far - 0.01) <= bottom < lifted(far + 0.02)
    assert near == pytest.approx(200.0, abs=0.02)
    assert far == pytest.approx(600.0, abs=0.02)


def test_the_visible_range_ends_where_the_mark_reaches_the_edges_of_the_screen():
    weapon = Weapon.from_dict("w", SHELL)
    near, far = mark_visible_range(weapon, 0.0, FOV, WIDTH, 50.0, 300.0)

    assert mark_at(weapon, near - 0.01) < 50.0 <= mark_at(weapon, near + 0.02)
    assert mark_at(weapon, far - 0.01) <= 300.0 < mark_at(weapon, far + 0.02)


def test_the_visible_range_has_no_end_where_the_whole_range_is_on_the_screen():
    weapon = Weapon.from_dict("w", SHELL)

    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, -1e9, 1e9) == (None, None)


def test_the_farthest_is_zero_when_even_the_closest_target_is_below_the_edge():
    weapon = Weapon.from_dict("w", SHELL)

    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, -1e9, -1.0) == (None, 0.0)


def test_there_is_no_visible_range_without_a_mark_or_without_a_target_the_weapon_can_take():
    assert mark_visible_range(WEAPONS[MORTAR], 0.0, FOV, WIDTH, 0.0, 500.0) == (None, None)
    assert mark_visible_range(Weapon.from_dict("s", {"velocity": 100, "gravity": 0}), 0.0, FOV, WIDTH, 0.0, 500.0) == (
        None, None
    )
    unreachable = Weapon.from_dict("u", {**SHELL, "elevation_limits": [80, 90]})
    assert mark_visible_range(unreachable, 0.0, FOV, WIDTH, 0.0, 500.0) == (None, None)


def test_a_mark_exactly_on_an_edge_is_on_the_screen():
    weapon = Weapon.from_dict("w", SHELL)
    closest = mark_at(weapon, 1.0)

    near, far = mark_visible_range(weapon, 0.0, FOV, WIDTH, closest, closest)

    assert near is None
    assert 1.0 <= far < 1.02


def test_the_closest_range_taken_is_the_minimum_distance():
    weapon = Weapon.from_dict("w", {**SHELL, "min_distance": 25})
    closest = mark_at(weapon, 25.0)

    near, far = mark_visible_range(weapon, 0.0, FOV, WIDTH, closest, closest)

    assert near is None
    assert 25.0 <= far < 25.02


def test_the_farthest_is_kept_when_the_mark_leaves_the_screen_just_before_the_end_of_the_reach():
    weapon = Weapon.from_dict("w", SHELL)
    bottom = mark_at(weapon, weapon.max_range() - 0.5)

    near, far = mark_visible_range(weapon, 0.0, FOV, WIDTH, 0.0, bottom)

    assert far == pytest.approx(weapon.max_range() - 0.5, abs=0.02)


def test_the_farthest_is_none_when_the_mark_stays_on_the_screen_to_the_end_of_the_reach():
    weapon = Weapon.from_dict("w", SHELL)
    bottom = mark_at(weapon, weapon.max_range() - 0.01)

    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, 0.0, bottom)[1] is None


# ---------- the range ladder ----------

def ladder_distances(weapon, *args, **kwargs):
    return [distance for distance, _ in range_ladder(weapon, FOV, WIDTH, *args, **kwargs)]


def test_the_ladder_puts_a_tick_where_the_mark_has_moved_by_the_gap_each_time():
    weapon = Weapon.from_dict("w", SHELL)
    ticks = range_ladder(weapon, FOV, WIDTH, 40, 30, 5000)

    assert [distance for distance, _ in ticks] == [100, 175, 250, 350, 500, 600, 700, 800, 1000]
    for distance, offset in ticks:
        assert offset == pytest.approx(mark_at(weapon, distance))
    offsets = [0.0] + [offset for _, offset in ticks]
    assert offsets[1] >= 40
    assert all(later - earlier >= 30 for earlier, later in zip(offsets[1:], offsets[2:]))


def test_a_gap_the_mark_has_exactly_moved_by_is_enough():
    weapon = Weapon.from_dict("w", SHELL)
    first = mark_at(weapon, 100.0)
    spacing = mark_at(weapon, 175.0) - first

    assert ladder_distances(weapon, first, spacing, 5000)[:2] == [100, 175]


def test_the_ladder_starts_at_the_minimum_distance_and_rounds_to_round_numbers():
    weapon = Weapon.from_dict("w", {**SHELL, "min_distance": 100})

    assert ladder_distances(weapon, 40, 30, 5000)[:2] == [100, 175]
    near = Weapon.from_dict("w", {"velocity": 200})
    assert ladder_distances(near, 1, 1, 5000)[:3] == [25, 50, 75]


def test_the_ladder_is_at_most_a_screens_worth_of_ticks_long():
    weapon = Weapon.from_dict("w", {"velocity": 200})

    assert len(ladder_distances(weapon, 1, 1, 100000)) == LADDER_MAX_TICKS


def test_the_ladder_ends_at_the_reach_and_a_tick_exactly_at_the_reach_is_kept():
    weapon = Weapon.from_dict("w", SHELL)
    third = mark_at(weapon, 250.0)

    assert ladder_distances(weapon, 40, 30, third) == [100, 175, 250]
    assert ladder_distances(weapon, 40, 30, third - 0.01) == [100, 175]


def test_the_ladder_ends_at_the_greatest_distance_and_a_tick_exactly_there_is_kept():
    far = Weapon.from_dict("f", {"velocity": 500, "min_distance": LADDER_MAX_DISTANCE})

    assert ladder_distances(far, 1, 1, 100000) == [LADDER_MAX_DISTANCE]
    past = Weapon.from_dict("f", {"velocity": 500, "min_distance": LADDER_MAX_DISTANCE + 1})
    assert ladder_distances(past, 1, 1, 100000) == []


def test_the_ladder_follows_the_weapons_launch_height_and_angle_scale():
    base = {"velocity": 100}

    assert ladder_distances(Weapon.from_dict("w", {**base, "angle_offset": 2.0}), 40, 30, 5000)[:3] == [175, 250, 350]
    lifted = Weapon.from_dict("w", {**base, "launch_height": 2.0})
    for distance, offset in range_ladder(lifted, FOV, WIDTH, 40, 30, 5000):
        assert offset == pytest.approx(mark_at(lifted, distance))


def test_the_ladder_takes_the_angles_up_to_the_limit_inclusive(monkeypatch):
    monkeypatch.setattr(ballistics, "GRAVITY", 10.0)
    # 100 m/s at 10 m/s^2 reaches 1000 m at exactly 45 degrees
    upper = Weapon.from_dict("w", {"velocity": 100, "elevation_limits": [0, 45]})
    lower = Weapon.from_dict("w", {"velocity": 100, "min_distance": 1000, "elevation_limits": [45, 90]})

    assert ladder_distances(upper, 40, 30, 100000)[-1] == 1000
    assert ladder_distances(lower, 1, 1, 100000) == [1000]


def test_a_weapon_without_a_mark_or_drop_has_no_ladder():
    assert range_ladder(WEAPONS[MORTAR], FOV, WIDTH, 40, 30, 5000) == []
    assert range_ladder(Weapon.from_dict("s", {"velocity": 100, "gravity": 0}), FOV, WIDTH, 40, 30, 5000) == []


def test_a_fall_that_ends_exactly_at_the_speed_cap_does_not_clamp_the_flight(monkeypatch):
    monkeypatch.setattr(ballistics, "GRAVITY", 2.0)
    weapon = Weapon.from_dict("w", {"velocity": 3, "max_speed": 5, "launch_height": 4.0})

    assert not weapon._clamps_before(0.0)
    assert weapon._clamps_before(-0.01)


def test_a_shell_fired_faster_than_its_cap_is_followed_close_to_the_muzzle():
    raw = {"velocity": 200, "max_speed": 150, "gravity": 0.8}
    weapon = Weapon.from_dict("w", raw)
    shot = flight.Shot(custom_game(raw), raw)

    for degrees in (4, 20, 45):
        rad = math.radians(degrees)

        for distance in (1.0, 2.0, 3.0, 20.0, 60.0):
            height = flight.fly_to(shot, rad, distance)[0]

            assert weapon.flight_height(rad, distance) == pytest.approx(height, abs=0.05), (degrees, distance)
            assert weapon.flight_at(rad, distance)[0] == pytest.approx(height, abs=0.05), (degrees, distance)


# ---------- the boost table ----------

ROCKET = {"velocity": 60, "acceleration": 40, "acceleration_time": 2.5}
SPACING = ballistics.BOOST_NODE_SPACING


def rocket_table():
    weapon = Weapon.from_dict("rocket", ROCKET)
    assert weapon.flies_boost_in_steps

    return weapon, ballistics._BoostTable(weapon)


def test_the_boost_table_has_a_node_per_degree_from_straight_down_to_straight_up():
    _, table = rocket_table()

    assert table.count == 181
    assert len(table.nodes) == 181
    # The 2.5 s motor acts on ceil(2.5 / dt) - 1 = 124 steps of 1/49.87 s
    assert table.steps == 124


@pytest.mark.parametrize("index", [0, 1, 90, 135, 180])
def test_a_boost_node_is_the_boost_flown_at_its_elevation_and_is_kept(index):
    weapon, table = rocket_table()
    points, (vx, vy) = ballistics._fly_boost(weapon, -math.pi / 2 + index * SPACING)

    node = table.node(index)

    assert node == (
        tuple(point[0] for point in points), tuple(point[1] for point in points), vx, vy
    )
    assert table.nodes[index] is node
    assert table.node(index) is node
    assert all(other is None for position, other in enumerate(table.nodes) if position != index)


@pytest.mark.parametrize("degrees, first", [
    (-90.0, 0), (-89.5, 0), (-88.0, 1), (-60.3, 28), (0.0, 89), (10.5, 99), (89.0, 177), (89.9, 177), (90.0, 177),
])
def test_four_nodes_around_the_elevation_are_interpolated_and_the_ends_shift_inwards(degrees, first):
    _, table = rocket_table()
    rad = math.radians(degrees)
    at = (rad + math.pi / 2) / SPACING

    weights, nodes = table.stencil(rad)

    assert nodes == tuple(table.node(first + i) for i in range(4))
    for power in range(4):
        assert sum(w * (first + i) ** power for i, w in enumerate(weights)) == pytest.approx(
            at ** power, rel=1e-9, abs=1e-9
        )


@pytest.mark.parametrize("degrees", [-70.2, 7.3, 33.0, 88.4])
def test_the_step_points_are_the_weighted_sum_of_the_nodes(degrees):
    _, table = rocket_table()
    weights, nodes = table.stencil(math.radians(degrees))

    points = list(table.points(weights, nodes))

    assert len(points) == table.steps + 1
    for k, (x, y) in enumerate(points):
        assert x == pytest.approx(sum(w * n[0][k] for w, n in zip(weights, nodes)), abs=1e-9)
        assert y == pytest.approx(sum(w * n[1][k] for w, n in zip(weights, nodes)), abs=1e-9)
    assert table.end(weights, nodes)[:2] == pytest.approx(points[-1], abs=1e-9)


@pytest.mark.parametrize("degrees", [-30.0, 7.3, 45.0, 80.0])
def test_the_step_holding_a_distance_is_found_by_halving(degrees):
    _, table = rocket_table()
    weights, nodes = table.stencil(math.radians(degrees))
    points = list(table.points(weights, nodes))
    xs = [x for x, _ in points]
    inside = [(a + b) / 2 for a, b in zip(xs, xs[1:])]
    probes = [xs[0] - 5.0, xs[0], *xs[1:-1], *inside, xs[-1] - 1e-6, xs[-1], xs[-1] + 5.0]

    for ahead in probes:
        expected = max(k for k in range(table.steps) if xs[k] <= ahead or k == 0)
        step, start, end = table.segment(weights, nodes, ahead)

        assert step == expected, ahead
        assert start == pytest.approx(points[expected], abs=1e-9)
        assert end == pytest.approx(points[expected + 1], abs=1e-9)


# ---------- the searches ----------

class Counter:
    """Wraps a function and counts its calls."""

    def __init__(self, function):
        self.function = function
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        return self.function(*args)


@pytest.mark.parametrize("direction, root, calls", [
    (1, 1.0, 16), (-1, -1.0, 16), (1, 0.4, 15), (-1, -1.3, 17),
])
def test_a_root_is_bracketed_by_doubling_steps_and_narrowed_by_the_illinois_method(direction, root, calls):
    """The number of evaluations pins the step doubling, the starting point of
    the bracket and the halving of the stale end."""
    error = Counter(lambda x: math.cos(x) - math.cos(root))

    found = ballistics._find_root(error, 0.0, direction)

    assert found == pytest.approx(root, abs=1e-9)
    assert error.calls == calls


CAPPED_FROM_A_TOWER = {"velocity": 100, "max_speed": 105.67, "launch_height": 60.0}
ROCKET_ALONG_THE_BARREL = {**ROCKET, "rotation_follows_velocity": False}


@pytest.mark.parametrize("raw, method, arguments, calls, expected", [
    (ROCKET, "elevations_to", (300.0, 0.0), 89, (0.16495432916330008, 1.515343942743068)),
    (ROCKET, "elevations_to", (300.0, 5.0), 86, (0.18174746459187735, 1.5152840885980854)),
    (ROCKET, "flat_low_elevation", (300.0,), 1312, 0.16495432916330013),
    (ROCKET, "peak_elevation", (300.0,), 53, 1.4605315032597859),
    (CAPPED_FROM_A_TOWER, "elevations_to", (300.0, 0.0), 87, (-0.05254497560751504, 1.425945743544563)),
    (CAPPED_FROM_A_TOWER, "flat_low_elevation", (300.0,), 1258, -0.052544975608577245),
    (CAPPED_FROM_A_TOWER, "peak_elevation", (300.0,), 53, 1.284853166329401),
    (ROCKET_ALONG_THE_BARREL, "elevations_to", (300.0, 0.0), 88, (0.11587411546281558, 1.5098965217388325)),
    (ROCKET_ALONG_THE_BARREL, "flat_low_elevation", (300.0,), 1312, 0.11587411546281559),
    (ROCKET_ALONG_THE_BARREL, "peak_elevation", (300.0,), 53, 1.4500202751490407),
])
def test_the_elevation_searches_find_their_roots_in_the_expected_number_of_flights(
    monkeypatch, raw, method, arguments, calls, expected
):
    """The count of flights pins the brackets, directions and step sizes of the
    searches, which otherwise converge to the same root."""
    weapon = Weapon.from_dict("w", raw)
    counted = Counter(lambda self, rad, distance: original_flight_height(self, rad, distance))
    monkeypatch.setattr(Weapon, "flight_height", lambda self, rad, distance: counted(self, rad, distance))

    found = getattr(weapon, method)(*arguments)

    assert found == pytest.approx(expected, abs=1e-8)
    assert counted.calls == calls


original_flight_height = Weapon.flight_height


def test_the_low_elevation_to_the_longest_range_exists_and_one_just_short_of_it_too():
    weapon = Weapon.from_dict("w", ROCKET)
    longest, top = weapon._max_range

    assert weapon.flat_low_elevation(longest) == pytest.approx(top, abs=1e-3)
    assert weapon.flat_low_elevation(longest - 0.3) == pytest.approx(top, abs=2e-2)
    assert math.isnan(weapon.flat_low_elevation(longest + 0.01))


def test_a_flat_low_elevation_lands_where_the_game_lands_for_a_capped_launch_from_a_tower():
    """A cap that binds only for the fall to the ground (not for a target a metre
    higher) still takes the numeric search."""
    weapon = Weapon.from_dict("w", CAPPED_FROM_A_TOWER)
    shot = flight.Shot(custom_game(CAPPED_FROM_A_TOWER), CAPPED_FROM_A_TOWER)

    elevation = weapon.flat_low_elevation(300.0)

    assert flight.range_at(shot, elevation, 0.0) == pytest.approx(300.0, abs=0.05)


# ---------- the apex of a plain parabola and of a boost along the barrel ----------

RAISED_MUZZLE = {"velocity": 90, "launch_height": 1.4, "muzzle_forward": 0.9, "muzzle_up": 0.3}
SLOW_ROCKET_ALONG_THE_BARREL = {
    "velocity": 20, "acceleration": 3, "acceleration_time": 4.0, "rotation_follows_velocity": False,
}


def parabola_apex(weapon, rad):
    """(x, height) of the top of the plain parabola from the muzzle."""
    start_x, start_y = weapon.launch_point(rad)
    vx, vy = weapon.velocity * math.cos(rad), weapon.velocity * math.sin(rad)

    return start_x + vx * vy / weapon.g, start_y + vy * vy / (2 * weapon.g)


@pytest.mark.parametrize("degrees", [10.0, 45.0, 80.0])
def test_the_apex_of_a_parabola_from_a_raised_muzzle_is_its_top_if_it_has_been_passed(degrees):
    weapon = Weapon.from_dict("w", RAISED_MUZZLE)
    rad = math.radians(degrees)
    top_x, top = parabola_apex(weapon, rad)

    assert weapon.apex_height(rad, top_x + 1.0) == pytest.approx(top, abs=1e-9)
    assert weapon.apex_height(rad, top_x - 1.0) == -math.inf
    assert weapon.apex_height(rad, top_x * 3) == pytest.approx(top, abs=1e-9)


def test_the_apex_is_reached_when_the_distance_is_exactly_where_the_top_is(monkeypatch):
    weapon = Weapon.from_dict("w", {"velocity": 90})
    rad = math.radians(30.0)
    vx, vy = weapon.velocity * math.cos(rad), weapon.velocity * math.sin(rad)
    top_distance = vx * vy / weapon.g

    assert weapon.apex_height(rad, top_distance) == pytest.approx(vy * vy / (2 * weapon.g))


def test_a_flat_shot_has_no_apex_above_its_muzzle():
    weapon = Weapon.from_dict("w", {"velocity": 90, "launch_height": 2.0})

    assert weapon.apex_height(0.0, 100.0) == -math.inf
    assert weapon.apex_height(math.radians(-5.0), 100.0) == -math.inf


@pytest.mark.parametrize("degrees", [30.0, 45.0, 75.0])
def test_a_slow_boost_along_the_barrel_peaks_while_it_burns(degrees):
    weapon = Weapon.from_dict("w", SLOW_ROCKET_ALONG_THE_BARREL)
    shot = flight.Shot(custom_game(SLOW_ROCKET_ALONG_THE_BARREL), SLOW_ROCKET_ALONG_THE_BARREL)
    rad = math.radians(degrees)

    for distance in (20.0, 40.0, 80.0, 200.0):
        found = oracle_apex(shot, rad, distance)

        if found is None:
            continue

        top, at_distance, _ = found

        if top > at_distance + 0.05:
            assert weapon.apex_height(rad, distance) == pytest.approx(top, abs=0.01), distance
        else:
            assert weapon.apex_height(rad, distance) <= at_distance + 0.01 or math.isinf(
                weapon.apex_height(rad, distance)
            )


def test_a_boost_along_the_barrel_that_is_still_climbing_at_the_distance_has_no_apex_yet():
    weapon = Weapon.from_dict("w", SLOW_ROCKET_ALONG_THE_BARREL)
    rad = math.radians(45.0)
    rising = math.sin(rad) * 20 / (weapon.g - math.sin(rad) * 3)
    reached = math.cos(rad) * (20 * rising + 0.5 * 3 * rising ** 2)

    assert weapon.apex_height(rad, reached - 0.1) == -math.inf
    assert weapon.apex_height(rad, reached + 0.1) == pytest.approx(
        math.sin(rad) * (20 * rising + 1.5 * rising ** 2) - 0.5 * weapon.g * rising ** 2, abs=1e-9
    )
    exactly = math.cos(rad) * (weapon.velocity * rising + 0.5 * weapon.acceleration * rising ** 2)
    assert weapon.apex_height(rad, exactly) == pytest.approx(
        math.sin(rad) * (20 * rising + 1.5 * rising ** 2) - 0.5 * weapon.g * rising ** 2, abs=1e-9
    )


def test_a_boost_that_pushes_harder_than_gravity_pulls_has_no_apex_while_it_burns():
    weapon = Weapon.from_dict("w", {
        "velocity": 20, "acceleration": 15, "acceleration_time": 2.0, "rotation_follows_velocity": False,
    })

    assert weapon.apex_height(math.radians(60.0), 25.0) == -math.inf


# ---------- solve and the ladder: what is left ----------

def test_a_target_the_elevation_limits_refuse_still_has_the_speed_of_its_straight_line():
    weapon = Weapon.from_dict("w", {
        "velocity": 100, "gravity": 0, "acceleration": 10, "acceleration_time": 5.0,
        "elevation_limits": [-5, 5], "launch_height": 2.0,
    })

    solution = solve(weapon, 300.0, 100.0, aim_lift=20.0)

    assert solution.reason_code == "elevation_limit"
    assert solution.velocity == weapon.velocity_at(math.hypot(300.0, 100.0 + 20.0 - 2.0))
    assert solution.velocity != weapon.velocity_at(100.0 + 20.0 - 2.0)


def test_an_arc_at_exactly_the_lowest_elevation_limit_is_an_alternative():
    weapon = Weapon.from_dict("w", {"velocity": 100, "gravity": 0, "elevation_limits": [45, 89]})

    solution = solve(weapon, 300.0, 300.0)

    assert solution.reachable
    assert solution.alternatives == {"low": 45.0, "high": 45.0}


def test_an_arc_beyond_the_limits_does_not_hide_the_one_after_it():
    weapon = Weapon.from_dict("w", {"velocity": 100, "elevation_limits": [45, 89]})

    solution = solve(weapon, 500.0, 0.0, "high")

    assert list(solution.alternatives) == ["high"]
    assert solution.alternatives["high"] == solution.angle


def test_the_apex_of_a_shot_that_only_falls_is_its_muzzle():
    weapon = Weapon.from_dict("w", {"velocity": 100, "launch_height": 50.0})

    solution = solve(weapon, 100.0, 0.0)

    assert solution.angle < 0
    assert solution.apex == pytest.approx(weapon.launch_point(math.radians(solution.raw_angle))[1])


def test_an_obstacle_search_for_a_target_out_of_reach_finds_nothing():
    weapon = Weapon.from_dict("w", {**SHELL, "launch_height": 2.0})

    assert first_obstacle(weapon, solve(weapon, 5000.0), [1000.0] * 1200, 5) is None


def test_a_path_that_just_touches_the_terrain_does_not_pass_under_it():
    weapon = Weapon.from_dict("w", {**SHELL, "launch_height": 2.0})
    solution = solve(weapon, 500.0)
    rad = math.radians(solution.raw_angle)
    touching = [weapon.flight_height(rad, index * 5) for index in range(101)]

    assert first_obstacle(weapon, solution, touching, 5) is None


def test_a_weapon_with_a_gravity_of_exactly_one_has_a_mark(monkeypatch):
    monkeypatch.setattr(ballistics, "GRAVITY", 1.0)
    weapon = Weapon.from_dict("w", {"velocity": 10})

    assert weapon.g == 1.0
    assert mark_resolution(weapon, 20.0, 0.0, FOV, WIDTH) is not None
    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, 0.0, 1e6)[0] is None
    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, 0.0, 100.0)[1] is not None
    assert range_ladder(weapon, FOV, WIDTH, 40, 30, 5000)


def test_a_weapon_laid_by_elevation_has_no_mark_resolution_or_visible_range():
    weapon = Weapon.from_dict("w", {**SHELL, "aim": "elevation"})

    assert mark_resolution(weapon, 500.0, 0.0, FOV, WIDTH) is None
    assert mark_visible_range(weapon, 0.0, FOV, WIDTH, 0.0, 500.0) == (None, None)
    assert range_ladder(weapon, FOV, WIDTH, 40, 30, 5000) == []


# ---------- the capped coast and the last ties ----------

FASTER_THAN_ITS_CAP = {"velocity": 200, "max_speed": 150, "gravity": 0.8}


def test_a_capped_flight_never_reaches_a_point_beyond_where_it_has_turned_straight_down():
    weapon = Weapon.from_dict("w", FASTER_THAN_ITS_CAP)
    rad = math.radians(20.0)
    near, far = 1000.0, 1.0e6

    assert math.isfinite(weapon.flight_at(rad, near)[0])
    assert weapon.flight_at(rad, far) == (-math.inf, math.inf, -math.pi / 2)

    for _ in range(25):
        middle = (near + far) / 2
        near, far = (middle, far) if math.isfinite(weapon.flight_at(rad, middle)[0]) else (near, middle)

    assert far - near < 0.1
    assert near == pytest.approx(5353.14, abs=0.1)
    assert math.isfinite(weapon.flight_at(rad, near)[0])
    assert weapon.flight_at(rad, far + 1.0) == (-math.inf, math.inf, -math.pi / 2)
    assert weapon.flight_at(rad, near - 1.0)[2] > -math.pi / 2
    assert weapon.flight_at(rad, near - 1.0)[0] > -math.inf


def test_a_capped_flight_within_rounding_of_the_end_of_its_reach_does_not_raise():
    """deadline-squad/squad-ballistics#16: just below the end of the reach,
    sin(turn) rounds to 1.0 and atanh used to raise a math domain error."""
    weapon = Weapon.from_dict("w", FASTER_THAN_ITS_CAP)
    rad = math.radians(20.0)
    unreachable = (-math.inf, math.inf, -math.pi / 2)

    assert weapon.flight_at(rad, 5353.144287109375) == unreachable
    assert math.isfinite(weapon.flight_at(rad, 5353.1441650390625)[0])

    step = 2.0 ** -13
    for index in range(-2000, 2000):
        height, _, angle = weapon.flight_at(rad, 5353.1442 + index * step * 1e-3)
        assert height == -math.inf or math.isfinite(height)
        assert -math.pi / 2 <= angle < 0.0


def test_a_capped_flight_comes_down_more_and_more_steeply_to_the_end_of_its_reach():
    weapon = Weapon.from_dict("w", FASTER_THAN_ITS_CAP)
    rad = math.radians(20.0)
    angles = [weapon.flight_at(rad, distance)[2] for distance in (500.0, 1500.0, 3000.0, 4000.0)]

    assert angles == sorted(angles, reverse=True)
    assert angles[-1] < -math.pi / 3 or math.isinf(weapon.flight_at(rad, 4000.0)[0])


def test_a_shot_that_comes_down_to_exactly_the_ground_at_the_peak_elevation_is_the_root(monkeypatch):
    """The height at the highest elevation is bit-exactly 0.0 (the target is
    the longest range): that elevation is the answer, not NaN."""
    weapon = Weapon.from_dict("w", ROCKET)
    longest, top = weapon._max_range
    monkeypatch.setattr(Weapon, "flight_height", lambda self, rad, distance: 100.0 * (rad - top))

    assert weapon.flat_low_elevation(longest) == top


def test_the_peak_search_height_is_a_target_the_shot_can_just_reach():
    weapon = Weapon.from_dict("w", ROCKET)
    peak = weapon.flight_height(weapon.peak_elevation(500.0), 500.0)

    low, high = weapon.elevations_to(500.0, peak)

    assert not math.isnan(low) and not math.isnan(high)
    assert low == pytest.approx(high, abs=1e-3)


def test_an_axis_boost_pushing_almost_as_hard_as_gravity_peaks_late_in_a_long_burn():
    raw = {"velocity": 2, "acceleration": 9.3, "acceleration_time": 10.0, "rotation_follows_velocity": False}
    weapon = Weapon.from_dict("w", raw)
    shot = flight.Shot(custom_game(raw), raw)
    rad = math.radians(85.0)
    top, at_distance, _ = oracle_apex(shot, rad, 60.0)

    assert top > at_distance + 0.05
    assert weapon.apex_height(rad, 60.0) == pytest.approx(top, abs=0.05)


def test_a_horizontal_boost_along_the_barrel_has_no_apex():
    raw = {"velocity": 20, "acceleration": 3, "acceleration_time": 4.0, "rotation_follows_velocity": False}
    weapon = Weapon.from_dict("w", raw)

    assert weapon.apex_height(0.0, 50.0) == -math.inf


def test_a_boost_that_peaks_exactly_when_it_ends_still_has_its_apex(monkeypatch):
    monkeypatch.setattr(ballistics, "GRAVITY", 10.0)
    # The 2 s motor acts on 99 steps; straight up, the thrust that stops the rise exactly at
    # the end of the burn: 10 + (a - g) * burn = 0
    burn = 99 / 49.87
    raw = {
        "velocity": 10, "acceleration": 10 - 10 / burn, "acceleration_time": 2.0,
        "rotation_follows_velocity": False,
    }
    weapon = Weapon.from_dict("w", raw)

    assert weapon.apex_height(math.pi / 2, 1.0) == pytest.approx(5 * burn)


def test_the_apex_of_an_axis_boost_after_the_burn_is_the_top_of_the_parabola_it_ends_in():
    raw = ROCKET_ALONG_THE_BARREL
    weapon = Weapon.from_dict("w", raw)
    shot = flight.Shot(custom_game(raw), raw)
    rad = math.radians(45.0)
    top, at_distance, _ = oracle_apex(shot, rad, 4000.0)

    assert top > at_distance + 0.05
    assert weapon.apex_height(rad, 4000.0) == pytest.approx(top, abs=0.05)
    assert weapon.apex_height(rad, 40.0) == -math.inf


def test_the_top_after_the_burn_is_reported_only_from_the_distance_where_the_shot_gets_there():
    raw = ROCKET_ALONG_THE_BARREL
    weapon = Weapon.from_dict("w", raw)
    rad = math.radians(45.0)
    cos, sin, g = math.cos(rad), math.sin(rad), weapon.g
    # The 2.5 s motor acts on 124 steps
    v0, a, boost = weapon.velocity, weapon.acceleration, 124 / 49.87
    end_speed = v0 + a * boost
    x = cos * (v0 * boost + 0.5 * a * boost * boost)
    y = sin * (v0 * boost + 0.5 * a * boost * boost) - 0.5 * g * boost * boost
    vx, vy = cos * end_speed, sin * end_speed - g * boost
    top_x = x + vx * vy / g

    assert weapon.apex_height(rad, top_x - 1.0) == -math.inf
    assert weapon.apex_height(rad, top_x + 1.0) == pytest.approx(y + vy * vy / (2 * g))
