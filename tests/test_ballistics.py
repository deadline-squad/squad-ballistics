import math
import os

import pytest

from ballistics import (
    GRAVITY,
    MILS_PER_DEGREE,
    Weapon,
    WeaponDataError,
    height_at,
    load_weapons,
    parse_weapons,
    screen_offset,
    solve,
    trajectory,
)

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))


def test_database_loads():
    assert len(WEAPONS) >= 50

    # Weapons of the original release must still be covered.
    for name in (
        "MK19 / AGS-17 / AGS-30",
        "RPG-29",
        "SPG-9 · HEAT",
        "ZiS-3",
        "Rifle grenade",
        "M203 / M320 / GP-25 / HK79 / MKE MGL",
    ):
        assert name in WEAPONS

    # Original values are kept.
    assert WEAPONS["SPG-9 · HEAT"].gravity == 1.2
    assert WEAPONS["ZiS-3"].velocity == 700


def test_every_weapon_has_known_category():
    from i18n import STRINGS

    for weapon in WEAPONS.values():
        assert f"cat_{weapon.category}" in STRINGS, weapon.name


@pytest.mark.parametrize("name", list(WEAPONS))
@pytest.mark.parametrize("fraction", [0.05, 0.25, 0.5, 0.8])
@pytest.mark.parametrize("height", [-30.0, 0.0, 20.0])
def test_every_weapon_hits_target(name, fraction, height):
    weapon = WEAPONS[name]

    distance = max(
        weapon.min_distance + 1,
        min(weapon.max_range() * fraction, 2000)
    )

    for arc in ("low", "high"):
        solution = solve(weapon, distance, height, arc)

        if not solution.reachable:
            # Only acceptable reason: weapon elevation limits.
            assert "limited" in solution.reason or "range" in solution.reason
            continue

        assert math.isfinite(solution.angle)
        assert solution.time_of_flight > 0
        assert solution.mils == pytest.approx(
            solution.angle * MILS_PER_DEGREE
        )

        # The projectile fired at that angle must pass through the target.
        assert height_at(weapon, solution.angle, distance) == pytest.approx(
            height, abs=0.01
        )


@pytest.mark.parametrize("name", list(WEAPONS))
def test_default_arc_reachable_somewhere(name):
    weapon = WEAPONS[name]

    for fraction in (0.3, 0.6, 0.85):
        distance = max(
            weapon.min_distance + 1,
            min(weapon.max_range() * fraction, 2000)
        )
        if solve(weapon, distance).reachable:
            return

    pytest.fail(f"{name} is never reachable with its default arc")


def test_gravity_scale_is_used():
    normal = Weapon("a", velocity=400, gravity=1)
    heavy = Weapon("b", velocity=400, gravity=2)

    a = solve(normal, 1000).angle
    b = solve(heavy, 1000).angle

    assert b > a * 1.9


def test_known_value():
    # Flat ground, no drag: sin(2θ) = g·d / v²
    weapon = Weapon("test", velocity=100)
    solution = solve(weapon, 500)

    expected = math.degrees(math.asin(GRAVITY * 500 / 100 ** 2) / 2)

    assert solution.angle == pytest.approx(expected)


def test_high_arc_is_higher():
    weapon = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    solution = solve(weapon, 800)

    assert solution.arc == "high"
    assert solution.angle > 45
    assert solve(weapon, 800, arc="low").reachable is False


def test_out_of_range():
    weapon = WEAPONS["M203 / M320 / GP-25 / HK79 / MKE MGL"]

    solution = solve(weapon, weapon.max_range() + 50)

    assert not solution.reachable
    assert "range" in solution.reason


def test_min_distance():
    weapon = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    solution = solve(weapon, 20)

    assert not solution.reachable
    assert "close" in solution.reason.lower()


def test_target_above_needs_more_elevation():
    weapon = WEAPONS["SPG-9 · HEAT"]

    assert solve(weapon, 600, 30).angle > solve(weapon, 600, 0).angle
    assert solve(weapon, 600, -30).angle < solve(weapon, 600, 0).angle


@pytest.mark.parametrize("distance", [0, -10, float("nan")])
def test_invalid_distance(distance):
    with pytest.raises(ValueError):
        solve(WEAPONS["SPG-9 · HEAT"], distance)


def test_deceleration_velocity():
    weapon = WEAPONS["UB-32 (S-5 rockets)"]

    assert weapon.velocity_at(1) == pytest.approx(300, abs=0.5)
    assert weapon.velocity_at(5000) < 300
    assert weapon.velocity_at(5000) > weapon.cruise_velocity


def test_angle_offset_applied():
    weapon = WEAPONS["Technical Mortar"]
    plain = Weapon("plain", velocity=110, arc="high")

    assert solve(weapon, 600).angle == pytest.approx(
        solve(plain, 600).angle - 5
    )


def test_screen_offset_projection():
    # 90° horizontal FOV on a 1920 px wide screen: focal length = 960 px.
    assert screen_offset(45, 90, 1920) == pytest.approx(960)
    assert screen_offset(0, 90, 1920) == 0
    assert screen_offset(-10, 90, 1920) < 0

    # Narrower FOV (zoom) means more pixels per degree.
    assert screen_offset(2, 40, 1920) > screen_offset(2, 90, 1920)

    assert screen_offset(2, 90, 1920, scale=1.5) == pytest.approx(
        screen_offset(2, 90, 1920) * 1.5
    )

    assert math.isinf(screen_offset(90, 90, 1920))


@pytest.mark.parametrize("fov", [0, 180, -5])
def test_screen_offset_invalid_fov(fov):
    with pytest.raises(ValueError):
        screen_offset(1, fov, 1920)


@pytest.mark.parametrize("data", [
    {"x": {}},
    {"x": {"velocity": 0}},
    {"x": {"velocity": "fast"}},
    {"x": {"velocity": 100, "gravity": -1}},
    {"x": {"velocity": 100, "aim": "telepathy"}},
    {"x": {"velocity": True}},
    {"x": {"velocity": 100, "arc": "sideways"}},
    {"x": {"velocity": 100, "elevation_limits": [10, 5]}},
    {"x": {"velocity": 100, "deceleration": 100, "deceleration_time": 1}},
    {"_comment": "only comments"},
    [],
])
def test_invalid_weapon_data(data):
    with pytest.raises(WeaponDataError):
        parse_weapons(data)


def test_legacy_format_still_works():
    weapons = parse_weapons({"Old": {"velocity": 230, "gravity": 1}})

    assert weapons["Old"].arc == "low"
    assert solve(weapons["Old"], 300).reachable


def test_rocket_boost_speeds_up():
    weapon = WEAPONS["RPG-7 · PG-7V HEAT / OG-7V"]

    assert weapon.velocity_at(1) == pytest.approx(117, abs=1)
    assert weapon.velocity_at(300) > 117
    assert weapon.velocity_at(5000) < weapon.cruise_velocity
    assert weapon.cruise_velocity == pytest.approx(117 + 187.5 * 0.8)

    # Boosted rocket needs less elevation than one without the motor.
    plain = Weapon("plain", velocity=117)
    assert solve(weapon, 300).angle < solve(plain, 300).angle


def test_boost_max_range_matches_reachability():
    weapon = WEAPONS["Carl Gustav / M3 MAAWS · HEAT"]
    limit = weapon.max_range()

    assert solve(weapon, limit * 0.99).reachable
    assert not solve(weapon, limit * 1.01).reachable


def test_no_gravity_flies_straight():
    weapon = WEAPONS["NLAW"]

    assert weapon.max_range() == math.inf
    assert solve(weapon, 400).angle == pytest.approx(0)
    assert solve(weapon, 400, 40).angle == pytest.approx(
        math.degrees(math.atan2(40, 400))
    )


def test_sight_angle_is_measured_from_the_line_of_sight():
    """The overlay puts the target on the mark: aiming at a target above
    already raises the barrel by the angle the target is seen at."""
    rpg = WEAPONS["RPG-29"]

    uphill = solve(rpg, 300, 30)
    flat = solve(rpg, 300, 0)

    assert flat.sight_angle == pytest.approx(flat.angle)
    assert uphill.angle == pytest.approx(6.78, abs=0.01)
    assert uphill.sight_angle == pytest.approx(
        uphill.angle - math.degrees(math.atan2(30, 300))
    )
    assert uphill.sight_angle == pytest.approx(1.07, abs=0.01)

    # Without gravity the projectile goes where the sight looks.
    for height in (-60, 0, 45):
        assert solve(WEAPONS["NLAW"], 400, height).sight_angle == pytest.approx(0)

    # The muzzle height counts: the line of sight starts there too.
    ags = WEAPONS["AGS-17 · emplacement"]
    low = solve(ags, 400, 0, "low")
    assert low.sight_angle == pytest.approx(
        low.angle - math.degrees(math.atan2(-ags.launch_height, 400))
    )


@pytest.mark.parametrize("name", [
    "Tank AP · M256 / Rh120",
    "M2A1 .50",
    "2A42 / 2A72 30mm · HE",
])
def test_sight_angle_follows_the_riflemans_rule(name):
    # Independent check: for flat fire the angle over the line of sight to
    # a target up or down a slope is close to the flat-ground one at the
    # same horizontal distance. The angle to the horizon is not.
    weapon = WEAPONS[name]
    flat = solve(weapon, 800, 0).sight_angle

    for height in (-120, -40, 40, 120):
        solution = solve(weapon, 800, height)

        assert solution.sight_angle == pytest.approx(flat, rel=0.05)
        assert abs(solution.angle - flat) > 2


@pytest.mark.parametrize("name", list(WEAPONS))
def test_trajectory_ends_on_target(name):
    weapon = WEAPONS[name]

    for fraction in (0.3, 0.6, 0.85):
        distance = max(
            weapon.min_distance + 1,
            min(weapon.max_range() * fraction, 2000)
        )
        solution = solve(weapon, distance, 5)
        if solution.reachable:
            break
    else:
        pytest.skip("not reachable 5 m above")

    path = trajectory(weapon, solution)

    # The path starts at the muzzle, launch_height above the ground.
    assert path[0] == (0.0, weapon.launch_height)
    assert path[-1][0] == pytest.approx(distance)
    assert path[-1][1] == pytest.approx(5, abs=0.01)
    assert solution.apex >= 5 - 1e-6
    assert max(y for _, y in path) <= solution.apex + 1e-6


def test_impact_angle_and_apex():
    weapon = Weapon("flat", velocity=100)
    solution = solve(weapon, 500)

    # Symmetric parabola on flat ground: lands at the launch angle.
    assert solution.impact_angle == pytest.approx(solution.angle)
    assert solution.apex == pytest.approx(
        (100 * math.sin(math.radians(solution.angle))) ** 2 / (2 * GRAVITY)
    )


def test_reason_codes():
    mortar = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    assert solve(mortar, 10).reason_code == "too_close"
    assert solve(mortar, 5000).reason_code == "out_of_range"
    assert solve(mortar, 800, arc="low").reason_code == "elevation_limit"


# In-game AGS-17 measurements: seconds S was held after W -> impact
# distance on flat ground in metres (the table of the original AGS-17
# timer the hold model was fitted on).
AGS17_HOLD_TABLE = [
    (0.000, 280), (0.055, 325), (0.100, 350), (0.150, 375),
    (0.200, 400), (0.250, 425), (0.300, 450), (0.320, 475),
    (0.350, 500), (0.390, 525), (0.420, 550), (0.480, 575),
    (0.520, 600), (0.560, 625), (0.610, 650), (0.650, 675),
    (0.690, 700), (0.730, 725), (0.770, 750), (0.830, 775),
    (0.880, 800), (0.920, 825), (0.950, 850), (1.000, 875),
    (1.050, 900), (1.090, 925), (1.160, 950), (1.195, 975),
    (1.240, 1000), (1.290, 1025), (1.330, 1050), (1.385, 1075),
    (1.430, 1100), (1.470, 1125), (1.540, 1150), (1.575, 1175),
    (1.650, 1200), (1.696, 1225), (1.760, 1250), (1.804, 1275),
    (1.860, 1300), (1.905, 1325), (1.980, 1350), (2.032, 1375),
    (2.070, 1400), (2.160, 1425), (2.210, 1450), (2.272, 1475),
    (2.340, 1500), (2.410, 1525), (2.450, 1550), (2.540, 1575),
    (2.600, 1600), (2.670, 1625), (2.730, 1650), (2.826, 1675),
    (2.920, 1700), (3.010, 1725), (3.120, 1750), (3.193, 1775),
    (3.300, 1800), (3.430, 1825), (3.550, 1850), (3.700, 1875),
    (3.840, 1900), (3.950, 1915), (4.100, 1930),
]

AGS17 = WEAPONS["AGS-17 · emplacement"]


def test_ags17_hold_time_matches_in_game_measurements():
    errors = []

    for held, distance in AGS17_HOLD_TABLE:
        solution = solve(AGS17, distance, 0, "high")

        if distance > 1925:
            # Past the lowest elevation of the mount in the model.
            assert not solution.reachable
            continue

        assert solution.reachable, distance
        errors.append(solution.hold_time - held)

    assert len(errors) == len(AGS17_HOLD_TABLE) - 1
    assert max(abs(e) for e in errors) < 0.1
    assert math.sqrt(sum(e * e for e in errors) / len(errors)) < 0.03


def test_ags17_hold_time_follows_height():
    flat = solve(AGS17, 1000, 0, "high")
    higher = solve(AGS17, 1000, 30, "high")
    lower = solve(AGS17, 1000, -30, "high")

    # A higher target is reached by a flatter high arc: a longer hold.
    assert higher.hold_time > flat.hold_time > lower.hold_time
    assert height_at(AGS17, higher.angle, 1000) == pytest.approx(30, abs=0.01)


def test_ags17_arcs_and_limits():
    lob = solve(AGS17, 1000, 0, "high")
    direct = solve(AGS17, 1000, 0, "low")

    assert lob.hold_time == pytest.approx(
        (85.84 - lob.angle) / 9.17
    )
    assert direct.reachable
    assert math.isnan(direct.hold_time)
    assert direct.angle < 45

    # Closer than the top of the mount lobs: only direct fire.
    close = solve(AGS17, 200, 0, "high")
    assert not close.reachable
    assert solve(AGS17, 200, 0, "low").reachable

    # Between 45° and the lowest hold elevation: the key cannot get there.
    edge = solve(AGS17, 1930, 0, "high")
    assert edge.reason_code == "hold_limit"
    assert "limited" in edge.reason

    # ...so it is not offered as the other arc of a direct shot either.
    direct_edge = solve(AGS17, 1928, 0, "low")
    assert direct_edge.reachable
    assert "high" not in direct_edge.alternatives
    assert "high" in solve(AGS17, 1000, 0, "low").alternatives

    assert AGS17.max_hold_time() == pytest.approx((85.84 - 47.4) / 9.17)
    assert math.isnan(AGS17.hold_time(90))
    assert math.isnan(
        WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"].hold_time(60)
    )


def test_hold_fields_are_validated():
    base = {"velocity": 230, "hold_rate": 9}

    with pytest.raises(WeaponDataError, match="hold_elevation"):
        Weapon.from_dict("x", base)

    with pytest.raises(WeaponDataError, match="hold_elevation"):
        Weapon.from_dict("x", {**base, "hold_elevation": [80, 50]})

    with pytest.raises(WeaponDataError, match="hold_elevation"):
        Weapon.from_dict(
            "x",
            {**base, "hold_elevation": [40, 89], "elevation_limits": [0, 85]}
        )

    with pytest.raises(WeaponDataError, match="hold_rate"):
        Weapon.from_dict("x", {"velocity": 230, "hold_rate": -1})

    weapon = Weapon.from_dict("x", {**base, "hold_elevation": [50, 80]})
    assert weapon.has_hold
    assert weapon.hold_elevation == (50.0, 80.0)
    assert not Weapon.from_dict("y", {"velocity": 230}).has_hold


def test_ags17_hold_distance_matches_in_game_measurements():
    errors = [
        AGS17.hold_distance(held) - distance
        for held, distance in AGS17_HOLD_TABLE
    ]

    # Same model as the hold time: ~6.4 m RMS over the 67 measurements.
    assert math.sqrt(sum(e * e for e in errors) / len(errors)) < 8
    assert AGS17.hold_distance(0) == pytest.approx(279.5, abs=1)
    assert AGS17.hold_distance(99) == AGS17.hold_distance(AGS17.max_hold_time())
    assert AGS17.hold_distance(-1) == AGS17.hold_distance(0)
    assert math.isnan(WEAPONS["RPG-29"].hold_distance(1))
