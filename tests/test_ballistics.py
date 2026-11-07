from dataclasses import replace

import math
import os
import re

import pytest

from ballistics import (
    GRAVITY,
    MILS_PER_DEGREE,
    RENAMED_WEAPONS,
    Weapon,
    WeaponDataError,
    current_weapon_name,
    first_obstacle,
    height_at,
    load_weapons,
    mark_offset,
    parse_weapons,
    range_ladder,
    screen_offset,
    solve,
    trajectory,
)

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))


def test_database_loads():
    assert len(WEAPONS) >= 40

    # Weapons of the original release must still be covered (some renamed).
    for name in (
        "MK19 / AGS-17 / AGS-30",
        "RPG-29",
        "SPG-9 · HEAT",
        "ZiS-3 · optic (RMB ×4)",
        "Rifle grenade",
        "M203 / M320 / GP-25 / HK79 / MKE MGL",
    ):
        assert current_weapon_name(name) in WEAPONS

    # Original values are kept.
    assert WEAPONS["SPG-9 · HEAT"].gravity == 1.2
    assert WEAPONS["ZiS-3 · optic (RMB ×4)"].velocity == 700


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

    for fraction in (0.3, 0.6, 0.85, 0.05):
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
    weapon = WEAPONS["M203 / M320 / GP-25 / HK79 / SL40"]

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
    plain = replace(weapon, angle_offset=0.0)

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


@pytest.mark.parametrize("name", [
    "M203 / M320 / GP-25 / HK79 / SL40",
    "RPG-7 · PG-7V HEAT / OG-7V",
    "AGS-17 · emplacement · optic (RMB ×2.5)",
    "SPG-9 · FRAG",
])
def test_range_ladder_matches_the_mark(name):
    """Each tick is where the mark would be for a target at its range on
    flat ground; ticks are round, apart, in order and on the screen."""
    weapon = WEAPONS[name]
    ticks = range_ladder(weapon, 90, 1920, first=20, spacing=18, reach=520)

    assert len(ticks) >= 3

    for distance, offset in ticks:
        solution = solve(weapon, distance, 0.0, "low")
        assert offset == pytest.approx(mark_offset(weapon, solution.sight_angle, 90, 1920))
        assert distance % 25 == 0
        assert offset <= 520

    assert ticks[0][1] >= 20
    distances = [d for d, _ in ticks]
    offsets = [o for _, o in ticks]
    assert distances == sorted(distances)
    assert all(b - a >= 18 for a, b in zip(offsets, offsets[1:]))


def test_range_ladder_is_as_dense_as_the_spacing_allows():
    """Each tick is the nearest range that clears the previous one by
    `spacing` pixels, rounded up to a round step that grows with range:
    the QLZ87's optic gets a tick every 50 m, not every 200 m."""
    weapon = WEAPONS["QLZ87 · optic (RMB ×3)"]
    ticks = range_ladder(weapon, 90, 1920, 20, 18, 520)
    distances = [d for d, _ in ticks]

    # The 100 m zero is on the centre; the next ranges follow every 50 m
    assert distances[:4] == [150, 200, 250, 300]

    offsets = [o for _, o in ticks]
    assert all(b - a >= 18 for a, b in zip(offsets, offsets[1:]))

    steps = [b - a for a, b in zip(distances, distances[1:])]
    assert max(steps) >= 4 * min(steps)


def test_range_ladder_scales_with_zoom_and_calibration():
    weapon = WEAPONS["RPG-7 · PG-7V HEAT / OG-7V"]
    wide = dict(range_ladder(weapon, 90, 1920, 20, 18, 5000))
    scaled = dict(range_ladder(weapon, 90, 1920, 20, 18, 5000, scale=1.5))

    for distance in set(wide) & set(scaled):
        assert scaled[distance] == pytest.approx(wide[distance] * 1.5)


def test_range_ladder_ends_at_the_reach_and_the_tick_limit():
    weapon = WEAPONS["M203 / M320 / GP-25 / HK79 / SL40"]

    assert all(o <= 100 for _, o in range_ladder(weapon, 90, 1920, 20, 18, 100))
    assert len(range_ladder(weapon, 90, 1920, 1, 1, 10 ** 6)) <= 24


def test_no_range_ladder_without_a_mark_or_gravity():
    assert range_ladder(WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"], 90, 1920, 20, 18, 520) == []

    straight = Weapon(name="laser", velocity=900, gravity=0)
    assert range_ladder(straight, 90, 1920, 20, 18, 520) == []


def test_range_ladder_starts_past_the_minimum_distance():
    weapon = Weapon(name="slow", velocity=80, min_distance=60)

    assert range_ladder(weapon, 90, 1920, 1, 1, 520)[0][0] >= 60


# The game fires along the barrel socket (Attach_Muzzle), whose tilt
# against the camera zeroes the weapon's view at a round range (game files,
# build 26005357): there the mark is on the screen centre.
@pytest.mark.parametrize("name, zero", [
    ("QLZ87 · optic (RMB ×3)", 100),
    ("QLZ87 · Lynx · optic (RMB ×3)", 110),
])
def test_views_are_zeroed_where_the_game_puts_them(name, zero):
    weapon = WEAPONS[name]
    sight_angle = solve(weapon, zero, 0.0, "low").sight_angle
    view_fov, bore = weapon.sight_view(90)

    assert sight_angle == pytest.approx(bore, abs=0.05)
    assert abs(mark_offset(weapon, sight_angle, 90, 1920)) < screen_offset(0.05, view_fov, 1920)


def zero_range(weapon, bore):
    """Range (m, flat ground) at which a shot leaving `bore` degrees above
    the view centre comes back to the centre: the view's zero."""
    low, high = 1.0, 6000.0

    for _ in range(60):
        middle = (low + high) / 2
        solution = solve(weapon, middle, 0.0, "low")

        if not solution.reachable or solution.sight_angle > bore:
            high = middle
        else:
            low = middle

    return low


# Tripod geometry from the game files (build 26005357): the pitch of the
# weapon's barrel socket (`Attach_Muzzle*` of its skeleton, composed with the
# bone rotations), the pitch of the tripod's `AdsCamera1pPositionComponent`
# against the gun mount (the plain camera, `FirstPersonVehicleCam`, sits at
# 0 on the mount), the divisor the RMB handler puts on the FOV
# (`SetFieldOfView(UserSettings.FOV / k)`, None: no RMB sight; the ZiS-3's
# ×4 is its second `ZoomLevels` entry, the first is ×1) and the view the
# entry is aimed through: RMB (the sight) or PLAIN (the normal view, which
# keeps the game's FOV). The shot leaves `socket` above the plain camera's
# centre and `socket - ads_camera` above the RMB camera's. Each entry has one
# view; a weapon with an RMB sight has one entry per view.
RMB, PLAIN = "rmb", "plain"

EMPLACED_GEOMETRY = {
    "QLZ87 · optic (RMB ×3)": (-0.9, -1.6738, 3.0, RMB),
    "QLZ87 · no optic": (-0.9, -1.6738, 3.0, PLAIN),
    "MK19 · emplacement / C16 / L134A1": (0.0, -1.6738, 1.0, RMB),
    "AGS-17 · emplacement · optic (RMB ×2.5)": (0.85, 0.0, 2.5, RMB),
    "AGS-17 · emplacement · no optic": (0.85, 0.0, 2.5, PLAIN),
    "AGS-17 · iron sights emplacement": (4.5, None, None, PLAIN),
    "SPG-9 · HEAT": (0.13, None, None, PLAIN),
    "SPG-9 · FRAG": (0.13, None, None, PLAIN),
    "SPG-9 · HEAT · scope · optic (RMB ×4)": (2.34, 0.0, 4.0, RMB),
    "SPG-9 · HEAT · scope · no optic": (2.34, 0.0, 4.0, PLAIN),
    "SPG-9 · FRAG · scope · optic (RMB ×4)": (2.34, 0.0, 4.0, RMB),
    "SPG-9 · FRAG · scope · no optic": (2.34, 0.0, 4.0, PLAIN),
    "ZiS-3 · optic (RMB ×4)": (0.4, 0.0, 4.0, RMB),
    "ZiS-3 · no optic": (0.4, 0.0, 4.0, PLAIN),
}


@pytest.mark.parametrize("name", EMPLACED_GEOMETRY)
def test_weapons_json_matches_the_tripod_geometry(name):
    socket, ads_camera, divisor, view = EMPLACED_GEOMETRY[name]
    weapon = WEAPONS[name]

    if view == PLAIN:
        assert weapon.bore == pytest.approx(socket, abs=0.01)
        assert weapon.zoom == 0
        assert weapon.sight_view(90) == (90, weapon.bore)
        return

    assert weapon.bore == pytest.approx(socket - ads_camera, abs=0.01)
    assert weapon.zoom == (divisor if divisor > 1 else 0)
    assert weapon.sight_view(90) == (90 / divisor, weapon.bore)


NO_OPTIC = " · no optic"


def optic_suffix(weapon):
    """The end of an RMB sight's name: the view and its zoom."""
    return f" · optic (RMB ×{weapon.zoom:g})"


def aimed_through_rmb(weapon):
    """Whether the note says the entry is for the sight RMB zooms to its
    `zoom` (not merely that such a sight exists)."""
    return re.search(rf"aimed through (its|the) \w+ \(RMB, ×{weapon.zoom:g}\)", weapon.note) is not None


# Entries aimed through a sight that zooms the screen on RMB: the same gun can
# be fired from its normal view, so each has a "· no optic" twin.
RMB_SIGHTS = [name for name, weapon in WEAPONS.items() if weapon.zoom > 1 and aimed_through_rmb(weapon)]


def test_the_rmb_sights_are_the_known_ones():
    assert sorted(RMB_SIGHTS) == sorted([
        "QLZ87 · optic (RMB ×3)",
        "QLZ87 · bunker tripod · optic (RMB ×3)",
        "QLZ87 · Lynx · optic (RMB ×3)",
        "QLZ87 · CSK131 / WZ551 · optic (RMB ×3)",
        "QLZ87 · ZBL08 · optic (RMB ×3)",
        "AGS-17 · emplacement · optic (RMB ×2.5)",
        "SPG-9 · HEAT · scope · optic (RMB ×4)",
        "SPG-9 · FRAG · scope · optic (RMB ×4)",
        "SPG-9 · HEAT · technical · optic (RMB ×4)",
        "SPG-9 · FRAG · technical · optic (RMB ×4)",
        "SPG-9 · HEAT · INS armoured technical · optic (RMB ×4)",
        "SPG-9 · FRAG · INS armoured technical · optic (RMB ×4)",
        "ZiS-3 · optic (RMB ×4)",
    ])


@pytest.mark.parametrize("name", [n for n, w in WEAPONS.items() if w.zoom > 1])
def test_every_zoomed_entry_names_its_view(name):
    """A zoomed entry's mark is only right in that view: the note says it is
    aimed through the RMB sight or the gunner's sight, at its zoom."""
    weapon = WEAPONS[name]
    gunner = re.compile(rf"the gunner's sight at its \w+ zoom level, ×{weapon.zoom:g};")

    assert aimed_through_rmb(weapon) or gunner.search(weapon.note)


@pytest.mark.parametrize("name", RMB_SIGHTS)
def test_the_name_of_an_rmb_sight_says_optic_and_rmb(name):
    """The QLZ87 trap: a bare "QLZ87" was the ×3 optic's entry, and a player
    who fired from the normal view with it overshot by hundreds of metres
    without being told. The name itself says that RMB is held, with the zoom."""
    weapon = WEAPONS[name]

    assert name.endswith(optic_suffix(weapon))
    assert weapon.view == "optic"
    assert "optic" in name and "RMB" in name


@pytest.mark.parametrize("name", RMB_SIGHTS)
def test_every_rmb_sight_has_a_no_optic_twin(name):
    """An entry for the ×3 optic used from the normal view puts the mark
    three times too low and the shot far past the target. The twin has the
    same gun and only the normal view's bore and zoom."""
    optic = WEAPONS[name]
    base = name[: -len(optic_suffix(optic))]
    twin = WEAPONS[base + NO_OPTIC]

    assert optic.twin == twin.name
    assert twin.view == "plain"
    assert f'"{twin.name}"' in optic.note
    assert f'"{name}"' in twin.note
    assert "aimed from the normal view: no RMB, no zoom (×1)" in twin.note
    assert f"(RMB, ×{optic.zoom:g})" in twin.note
    assert twin.zoom == 0
    assert twin.sight_view(120) == (120, twin.bore)

    same_gun = {"name", "bore", "zoom", "note", "view", "twin", "focus_narrows_view"}
    for field in optic.__dataclass_fields__:
        if field not in same_gun:
            assert getattr(twin, field) == getattr(optic, field), field


def test_only_rmb_sights_have_a_view_and_a_twin():
    optics = {name for name, weapon in WEAPONS.items() if weapon.view == "optic"}
    plains = {name for name, weapon in WEAPONS.items() if weapon.view == "plain"}

    assert optics == set(RMB_SIGHTS)
    assert plains == {WEAPONS[name].twin for name in RMB_SIGHTS}
    assert {name for name in WEAPONS if name.endswith(NO_OPTIC)} == plains


def test_a_twin_must_exist_and_be_the_plain_view():
    entry = {"velocity": 190, "zoom": 3, "view": "optic"}

    with pytest.raises(WeaponDataError, match="'twin'"):
        parse_weapons({"A": entry})

    with pytest.raises(WeaponDataError, match="not a 'plain' entry"):
        parse_weapons({"A": {**entry, "twin": "B"}, "B": {"velocity": 190}})

    with pytest.raises(WeaponDataError, match="must be the 'twin' of one"):
        parse_weapons({"A": {"velocity": 190, "view": "plain"}})

    with pytest.raises(WeaponDataError, match="needs a 'zoom'"):
        parse_weapons({"A": {"velocity": 190, "view": "optic", "twin": "B"}, "B": {"velocity": 190, "view": "plain"}})

    with pytest.raises(WeaponDataError, match="has no 'zoom'"):
        parse_weapons({"A": {"velocity": 190, "zoom": 2, "view": "plain"}})

    with pytest.raises(WeaponDataError, match="'view' must be"):
        parse_weapons({"A": {"velocity": 190, "view": "ads"}})

    with pytest.raises(WeaponDataError, match="'twin'"):
        parse_weapons({"A": {"velocity": 190, "twin": "B"}})

    pair = {
        "A": {**entry, "twin": "B"},
        "B": {"velocity": 190, "view": "plain"},
    }
    assert parse_weapons(pair)["A"].twin == "B"


# (weapon, round zero range in m): the zero each view comes out at
# is a round number, which is what the tilt was built for; a model that put
# a view elsewhere would not land on one. Not here: the open-sight SPG-9
# (0.13 degrees, zero 47 m HEAT / 27 m FRAG) and the AGS-17 optic (0.85
# degrees, 58 m) have no round zero; the AGS-17 optic is confirmed instead
# by the hold fit, whose top 85.85 is the mount's 85 + 0.85. Nor the SPG-9's
# PGO-9 scope: its 2.34 degrees zero the HEAT shell at 765 m and the FRAG
# shell at 440 m, because MaxSpeed slows them to 330 and 250 m/s at launch;
# at the full muzzle velocity they would be 1313 and 688 m, close to round
# (deadline-squad/squad-ballistics#4).
ROUND_ZEROS = [
    ("MK19 · emplacement / C16 / L134A1", 330),
    ("AGS-17 · iron sights emplacement", 300),
    ("ZiS-3 · optic (RMB ×4)", 350),
    ("ZiS-3 · no optic", 350),
]


@pytest.mark.parametrize("name, zero", ROUND_ZEROS)
def test_emplaced_views_are_zeroed_at_a_round_range(name, zero):
    weapon = WEAPONS[name]
    view_fov, bore = weapon.sight_view(90)

    assert zero_range(weapon, bore) == pytest.approx(zero, rel=0.05)

    # Sign convention: inside the zero the mark is above the centre, at the
    # zero on it, beyond it below (positive offsets are below)
    def offset(distance):
        sight_angle = solve(weapon, distance, 0.0, "low").sight_angle
        return mark_offset(weapon, sight_angle, 90, 1920)

    assert offset(zero_range(weapon, bore)) == pytest.approx(0, abs=0.5)
    assert offset(zero / 2) < 0
    assert offset(zero * 1.5) > 0


def test_the_mk19_sight_does_not_zoom_but_looks_below_the_barrel():
    """RMB on the tripod MK19 keeps the FOV and tilts the view 1.674
    degrees under the barrel: the shot leaves that much above the centre."""
    weapon = WEAPONS["MK19 · emplacement / C16 / L134A1"]
    sight_angle = solve(weapon, 500, 0.0, "low").sight_angle

    assert weapon.sight_view(90) == (90, 1.674)
    assert mark_offset(weapon, sight_angle, 90, 1920) == pytest.approx(
        screen_offset(sight_angle - 1.674, 90, 1920)
    )


def test_the_scope_spg9_has_a_deeper_view_than_the_open_sights():
    iron = WEAPONS["SPG-9 · HEAT"]
    scope = WEAPONS["SPG-9 · HEAT · scope · optic (RMB ×4)"]

    assert (iron.velocity, iron.g) == (scope.velocity, scope.g)
    assert iron.sight_view(90) == (90, 0.13)
    assert scope.sight_view(90) == (22.5, 2.34)


def test_the_iron_sight_ags17_lobs_closer_than_the_optic_one():
    """Same mount, but the open-sight socket is 3.65 degrees higher: its top
    of the hold is that much higher and it lobs where the optic gun fires
    directly."""
    optic = WEAPONS["AGS-17 · emplacement · optic (RMB ×2.5)"]
    iron = WEAPONS["AGS-17 · iron sights emplacement"]

    assert iron.hold_elevation[1] - optic.hold_elevation[1] == pytest.approx(4.5 - 0.85, abs=0.01)
    assert iron.hold_elevation[0] == optic.hold_elevation[0]
    assert iron.hold_rate == optic.hold_rate
    assert not solve(optic, 100, 0.0, "high").reachable
    assert solve(iron, 100, 0.0, "high").reachable


def test_a_fov_below_the_zoom_is_held_at_one_degree():
    """A small FOV through a strong optic is a view narrower than the
    narrowest screen_offset takes: it must not raise."""
    weapon = WEAPONS["QLZ87 · optic (RMB ×3)"]
    sight_angle = solve(weapon, 300, 0.0, "low").sight_angle

    assert mark_offset(weapon, sight_angle, 2, 1920) == pytest.approx(
        screen_offset(sight_angle - 0.774, 1, 1920)
    )

    with pytest.raises(ValueError):
        mark_offset(weapon, sight_angle, 0.5, 1920)


def test_the_optic_view_narrows_the_fov_by_its_zoom():
    weapon = WEAPONS["QLZ87 · optic (RMB ×3)"]
    sight_angle = solve(weapon, 400, 0.0, "low").sight_angle

    assert weapon.sight_view(90) == (30, 0.774)
    assert mark_offset(weapon, sight_angle, 90, 1920) == pytest.approx(
        screen_offset(sight_angle - 0.774, 30, 1920)
    )


def test_the_tripod_qlz87_fires_below_the_centre_without_the_optic():
    """From the normal view (no RMB, game FOV) the barrel socket is 0.9
    degrees under the camera: the mark is that much lower than for a barrel
    on the centre, and far higher than the optic's mark at the same FOV."""
    plain = WEAPONS["QLZ87 · no optic"]
    optic = WEAPONS["QLZ87 · optic (RMB ×3)"]
    sight_angle = solve(plain, 300, 0.0, "low").sight_angle

    assert plain.sight_view(120) == (120, -0.9)
    assert mark_offset(plain, sight_angle, 120, 1920) == pytest.approx(
        screen_offset(sight_angle + 0.9, 120, 1920)
    )
    assert mark_offset(plain, sight_angle, 120, 1920) == pytest.approx(31.3, abs=0.05)
    assert mark_offset(optic, sight_angle, 120, 1920) == pytest.approx(71.9, abs=0.05)


def test_a_weapon_without_an_optic_is_aimed_through_the_plain_view():
    weapon = WEAPONS["AT-4"]
    sight_angle = solve(weapon, 200, 0.0, "low").sight_angle

    assert weapon.sight_view(90) == (90, 0.0)
    assert mark_offset(weapon, sight_angle, 90, 1920) == pytest.approx(
        screen_offset(sight_angle, 90, 1920)
    )


def test_the_optic_ladder_starts_past_the_zero_and_matches_the_mark():
    weapon = WEAPONS["QLZ87 · optic (RMB ×3)"]
    ticks = range_ladder(weapon, 90, 1920, 20, 18, 520)

    assert ticks and ticks[0][0] > 100

    for distance, offset in ticks:
        sight_angle = solve(weapon, distance, 0.0, "low").sight_angle
        assert offset == pytest.approx(mark_offset(weapon, sight_angle, 90, 1920))


@pytest.mark.parametrize("data", [
    {"x": {}},
    {"x": {"velocity": 0}},
    {"x": {"velocity": "fast"}},
    {"x": {"velocity": 100, "zoom": 0.5}},
    {"x": {"velocity": 100, "gravity": -1}},
    {"x": {"velocity": 100, "aim": "telepathy"}},
    {"x": {"velocity": True}},
    {"x": {"velocity": 100, "arc": "sideways"}},
    {"x": {"velocity": 100, "warhead": "nuclear"}},
    {"x": {"velocity": 100, "elevation_limits": [10, 5]}},
    {"x": {"velocity": 100, "deceleration": 100, "deceleration_time": 1}},
    {"_comment": "only comments"},
    [],
])
def test_invalid_weapon_data(data):
    with pytest.raises(WeaponDataError):
        parse_weapons(data)


@pytest.mark.parametrize("key, value", [
    ("views", [{"zoom": 1, "bore": 0.5}]),
    ("zoom_bore", 1.2),
    ("scope_zoom", 4),
])
def test_removed_and_unknown_weapon_keys_are_rejected(key, value):
    with pytest.raises(WeaponDataError, match=key):
        Weapon.from_dict("x", {"velocity": 100, key: value})


@pytest.mark.parametrize("zoom", [0.5, 0.99, -2])
def test_a_zoom_below_one_is_rejected(zoom):
    with pytest.raises(WeaponDataError, match="zoom"):
        Weapon.from_dict("x", {"velocity": 100, "zoom": zoom})


def test_a_weapon_has_one_view_with_its_zoom_and_bore():
    weapon = Weapon.from_dict("x", {"velocity": 100, "zoom": 2.5, "bore": 0.85})

    assert weapon.sight_view(90) == (36, 0.85)
    assert Weapon.from_dict("y", {"velocity": 100}).sight_view(90) == (90, 0.0)


def test_legacy_format_still_works():
    weapons = parse_weapons({"Old": {"velocity": 230, "gravity": 1}})

    assert weapons["Old"].arc == "low"
    assert solve(weapons["Old"], 300).reachable


def test_rocket_boost_speeds_up():
    weapon = WEAPONS["RPG-7 · PG-7V HEAT / OG-7V"]

    assert weapon.velocity_at(1) == pytest.approx(117, abs=1)
    assert weapon.velocity_at(300) > 117
    assert weapon.velocity_at(5000) < weapon.cruise_velocity
    assert weapon.cruise_velocity == pytest.approx(117 + 150 * 0.8)

    # Boosted rocket needs less elevation than one without the motor.
    plain = Weapon("plain", velocity=117)
    assert solve(weapon, 300).angle < solve(plain, 300).angle


def test_boost_max_range_matches_reachability():
    # The geometric range: the 4 s lifespan of the rocket is tested apart
    weapon = replace(WEAPONS["M3 MAAWS · HEAT / Smoke"], lifespan=0.0)
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
    ags = WEAPONS["AGS-17 · emplacement · optic (RMB ×2.5)"]
    low = solve(ags, 400, 0, "low")
    assert low.sight_angle == pytest.approx(
        low.angle - math.degrees(math.atan2(-ags.launch_height, 400))
    )


@pytest.mark.parametrize("name", [
    "Tank AP · M256 / Rh120",
    "MK19",
    "SPG-9 · HEAT",
])
def test_sight_angle_follows_the_riflemans_rule(name):
    # Independent check: for flat fire the angle over the line of sight to
    # a target up or down a slope is close to the flat-ground one at the
    # same horizontal distance. The angle to the horizon is not.
    weapon = WEAPONS[name]
    flat = solve(weapon, 800, 0).sight_angle

    # Within the mounts' limits (the SPG-9 tripod: +-10 degrees)
    for height in (-80, -40, 40, 80):
        solution = solve(weapon, 800, height)

        assert solution.sight_angle == pytest.approx(flat, rel=0.05)
        assert abs(solution.angle - flat) > 2


@pytest.mark.parametrize("name", list(WEAPONS))
def test_trajectory_ends_on_target(name):
    weapon = WEAPONS[name]

    for fraction in (0.3, 0.6, 0.85, 0.05):
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

    # The path starts at the muzzle, which moves with the elevation.
    start = weapon.launch_point(math.radians(solution.raw_angle))
    assert path[0] == pytest.approx(start)
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

AGS17 = WEAPONS["AGS-17 · emplacement · optic (RMB ×2.5)"]

# The distance of the lob from the top of the mount, the first point of the table.
AGS17_TOP_DISTANCE = 280

# The game files put the tripod's pivot 0.347 m above its foot (#13); the
# entries keep `launch_height` 1 because the hold fit was made with it. With
# the fitted rate and top unchanged, 0.347 fits the 67 measurements worse
# (distance RMS 7.43 -> 7.49 m, worst hold-time error 0.064 -> 0.073 s, past
# the 0.07 s bound below). Refitting rate and top gives the same RMS for both
# heights (5.34 m: 9.030 deg/s, top 85.73 for 1 m; 9.034 deg/s, top 85.73 for
# 0.347 m), so the measurements cannot tell the heights apart and a refit
# would only move the fitted values the Deadline SquadCalc shares.


def test_ags17_hold_time_matches_in_game_measurements():
    errors = []

    for held, distance in AGS17_HOLD_TABLE:
        solution = solve(AGS17, distance, 0, "high")

        if distance == AGS17_TOP_DISTANCE:
            # The first point is the lob from the very top of the mount: it needs 85.8523 degrees, the
            # game's limit (mount 85 + socket 0.85, which replaced the fitted 85.87) is 85.85.
            assert solution.reason_code == "elevation_limit"
            assert solution.raw_angle == pytest.approx(AGS17.elevation_limits[1], abs=0.01)
            continue

        assert solution.reachable, distance
        errors.append(solution.hold_time - held)

    # Game velocity and gravity (9.80 m/s^2), fitted hold rate and mount top:
    # 0.0173 s RMS, as with the 9.78 the fit was made with; the worst error
    # rose from 0.048 s to 0.064 s. The 1900-1930 m points sit where 0.2 % of
    # gravity is 4 m of range, which the 67 hand-timed measurements (7 m RMS)
    # cannot tell apart; refitting rate and mount top by least squares only
    # lowers the RMS to 0.0151 s and still leaves a 0.066 s worst error, so
    # the fitted values stay (they are the Deadline SquadCalc's too).
    assert max(abs(e) for e in errors) < 0.07
    assert math.sqrt(sum(e * e for e in errors) / len(errors)) < 0.02


def test_ags17_keeps_the_launch_height_the_hold_fit_was_made_with():
    assert AGS17.launch_height == 1
    game_height = replace(AGS17, launch_height=0.347)

    worst = max(
        abs(solve(game_height, distance, 0, "high").hold_time - held)
        for held, distance in AGS17_HOLD_TABLE
        if distance != AGS17_TOP_DISTANCE
    )

    assert worst > 0.07


def test_ags17_hold_time_follows_height():
    flat = solve(AGS17, 1000, 0, "high")
    higher = solve(AGS17, 1000, 30, "high")
    lower = solve(AGS17, 1000, -30, "high")

    # A higher target is reached by a flatter high arc: a longer hold.
    assert higher.hold_time > flat.hold_time > lower.hold_time
    assert height_at(AGS17, higher.angle, 1000) == pytest.approx(30, abs=0.01)


def test_mortar_auto_lay_model():
    # W to the top (1580 mil), S lowers 9°/s: keyboard pitch ×300 × input ×0.03 in the game files
    mortar = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]
    assert mortar.aim == "elevation" and mortar.has_hold
    assert mortar.hold_time(88.875) == 0
    assert mortar.hold_time(60) == pytest.approx((88.875 - 60) / 9.0)
    assert mortar.max_hold_time() == pytest.approx(43.875 / 9.0)
    assert math.isnan(mortar.hold_time(44))

    # Every reachable shot can be laid by the hold, across the whole range
    for distance in (51, 300, 800, 1236):
        solution = solve(mortar, distance, 0, "high")
        assert solution.reachable, distance
        assert solution.hold_time == pytest.approx((88.875 - solution.angle) / 9.0), distance


def test_ags17_arcs_and_limits():
    lob = solve(AGS17, 1000, 0, "high")
    direct = solve(AGS17, 1000, 0, "low")

    assert lob.hold_time == pytest.approx(
        (85.85 - lob.angle) / 9.08
    )
    assert direct.reachable
    assert math.isnan(direct.hold_time)
    assert direct.angle < 45

    # Closer than the top of the mount lobs: only direct fire.
    close = solve(AGS17, 200, 0, "high")
    assert not close.reachable
    assert solve(AGS17, 200, 0, "low").reachable

    # Between 45° and the lowest hold elevation: the key cannot get there.
    edge = solve(AGS17, 1940, 0, "high")
    assert edge.reason_code == "hold_limit"
    assert "limited" in edge.reason

    # ...so it is not offered as the other arc of a direct shot either.
    direct_edge = solve(AGS17, 1938, 0, "low")
    assert direct_edge.reachable
    assert "high" not in direct_edge.alternatives
    assert "high" in solve(AGS17, 1000, 0, "low").alternatives

    assert AGS17.max_hold_time() == pytest.approx((85.85 - 47.81) / 9.08)
    assert math.isnan(AGS17.hold_time(90))
    # Weapons without a hold model have no hold time
    assert math.isnan(WEAPONS["Hell Cannon"].hold_time(60))


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


def lob_range(weapon, held):
    """Flat-ground range (m) of a hold weapon's lob after holding the key
    `held` seconds from the top of the hold: the barrel stops at the lowest
    hold elevation, and the range is where the descending path comes back
    to the ground (bisection on the distance past the apex)."""
    lowest, top = weapon.hold_elevation
    rad = math.radians(max(lowest, top - weapon.hold_rate * max(0.0, held)))
    near, far = weapon.velocity ** 2 / weapon.g * math.sin(2 * rad) / 2, 1e4

    for _ in range(80):
        middle = (near + far) / 2
        if weapon.flight_height(rad, middle) > 0:
            near = middle
        else:
            far = middle

    return near


def test_ags17_hold_distance_matches_in_game_measurements():
    errors = [
        lob_range(AGS17, held) - distance
        for held, distance in AGS17_HOLD_TABLE
    ]

    # Same model as the hold time: ~7 m RMS over the 67 measurements.
    assert math.sqrt(sum(e * e for e in errors) / len(errors)) < 8
    assert lob_range(AGS17, 0) == pytest.approx(279.5, abs=1)
    # The lob of the hold time solve() gives lands on its target.
    for distance in (400, 1000, 1800):
        lob = solve(AGS17, distance, 0, "high")
        assert lob_range(AGS17, lob.hold_time) == pytest.approx(distance, abs=1e-3)


def test_renamed_weapons_point_at_current_names():
    for old, new in RENAMED_WEAPONS.items():
        assert old not in WEAPONS
        assert new in WEAPONS
        assert current_weapon_name(old) == new

    assert current_weapon_name("RPG-29") == "RPG-29"


def test_every_rmb_sight_keeps_its_old_name_as_the_optic():
    """The bare name was the optic's entry: a saved weapon, a recent list or
    a SquadCalc page that still sends it must land on the optic, never on
    the normal view."""
    for old in ("QLZ87", "QLZ87 · Lynx / CSK131", "AGS-17 · emplacement",
                "SPG-9 · HEAT · scope", "SPG-9 · FRAG · scope", "ZiS-3"):
        assert WEAPONS[current_weapon_name(old)].view == "optic"


# Values read from the game files (Squad build 26005357): WeaponConfig.MuzzleVelocity,
# the projectile's ProjectileGravityScale, and its ConstantAcceleration for
# ConstantAccelerationTimeout, stopped at MaxSpeed.
@pytest.mark.parametrize("name, velocity, gravity, cruise", [
    ("AGS-17 · emplacement · optic (RMB ×2.5)", 185, 1.8, 185),
    ("MK19", 230, 1, 230),
    ("MK19 · emplacement / C16 / L134A1", 235, 1, 235),
    ("MGL / M32", 75, 1, 75),
    ("AK-40GL (MPT-76)", 70, 1, 70),
    ("Rifle grenade", 76, 1, 76),
    ("RPG-7 · PG-7V HEAT / OG-7V", 117, 1, 117 + 150 * 0.8),
    ("RPG-7 · PG-7VR Tandem", 63, 1, 63 + 45 * 0.6),
    ("M3 MAAWS · HEAT / Smoke", 63, 1, 230),
    ("M3 MAAWS · Tandem", 63, 1, 230),
    ("Carl Gustav M2 · FFV551 HEAT", 310, 1, 310),
    ("Tank HESH · L30A1 (Challenger 2)", 670, 2, 670),
    ("Tank AP · L30A1 (Challenger 2) / M68A2", 1500, 2.5, 1500),
])
def test_game_ballistics(name, velocity, gravity, cruise):
    weapon = WEAPONS[name]

    assert weapon.velocity == velocity
    assert weapon.gravity == gravity
    assert weapon.cruise_velocity == pytest.approx(cruise, abs=0.05)


TANK = WEAPONS["Tank AP · M256 / Rh120"]
MORTAR = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]


def wall(length, at, height, step=1):
    """Flat profile of `length` metres with a wall `height` m high at `at` m."""
    profile = [0.0] * (int(length / step) + 1)
    profile[int(at / step)] = float(height)
    return profile


def test_first_obstacle_on_flat_ground_is_none():
    shot = solve(TANK, 300, 0, "low")
    assert first_obstacle(TANK, shot, [0.0] * 301, 1) is None


def test_first_obstacle_finds_the_wall():
    shot = solve(TANK, 300, 0, "low")
    assert first_obstacle(TANK, shot, wall(300, 150, 10), 1) == (150, 10)
    # A coarser profile is indexed in metres.
    assert first_obstacle(TANK, shot, wall(300, 150, 10, step=2), 2) == (150, 10)
    # A wall half as high as the trajectory above it is cleared.
    below = height_at(TANK, shot.angle, 150) / 2
    assert below > 0
    assert first_obstacle(TANK, shot, wall(300, 150, below), 1) is None


def test_first_obstacle_starts_at_the_shoulder_without_launch_height():
    # The tank's launch_height is 0: a path from the ground would graze a
    # 0.3 m hump in front of the weapon; from the shoulder it clears it.
    assert TANK.launch_height == 0
    hump = [0.0] * 301
    hump[3:6] = [0.3, 0.3, 0.3]
    assert first_obstacle(TANK, solve(TANK, 300, 0, "low"), hump, 1) is None


def test_first_obstacle_ignores_the_weapon_and_target_spots():
    shot = solve(TANK, 300, 0, "low")
    assert first_obstacle(TANK, shot, wall(300, 1, 50), 1) is None
    assert first_obstacle(TANK, shot, wall(300, 299, 50), 1) is None


def test_mortar_lob_clears_a_wall_the_low_shot_would_hit():
    lob = solve(MORTAR, 400, 0, "high")
    assert lob.reachable
    assert first_obstacle(MORTAR, lob, wall(400, 200, 20), 1) is None
    assert first_obstacle(MORTAR, lob, wall(400, 5, 60), 1) == (5, 60)


def test_first_obstacle_without_solution_or_profile():
    assert first_obstacle(TANK, solve(TANK, 300, 0, "low"), None, None) is None
    assert first_obstacle(TANK, solve(TANK, 300, 0, "low"), [], 1) is None
    unreachable = solve(MORTAR, 5000, 0, "high")
    assert not unreachable.reachable
    assert first_obstacle(MORTAR, unreachable, wall(5000, 10, 100), 1) is None


def test_the_game_flight_model_fields_are_validated():
    base = {"velocity": 100}

    for bad in (
        {"launch_height": -1},
        {"muzzle_forward": -0.5},
        {"hold_rate": 9, "hold_elevation": [45, 80], "acceleration": 10, "acceleration_time": 1},
    ):
        with pytest.raises(WeaponDataError):
            Weapon.from_dict("x", {**base, **bad})

    weapon = Weapon.from_dict(
        "x", {**base, "launch_height": 1.2, "muzzle_forward": 2.0, "muzzle_up": 0.25}
    )
    assert not weapon.is_parabola
    assert Weapon.from_dict("y", base).is_parabola


def test_the_muzzle_moves_with_the_elevation():
    weapon = Weapon.from_dict(
        "x", {"velocity": 100, "launch_height": 1.0, "muzzle_forward": 2.0, "muzzle_up": 0.5}
    )

    flat = weapon.launch_point(0.0)
    steep = weapon.launch_point(math.pi / 2)

    assert flat == pytest.approx((2.0, 1.5))
    assert steep == pytest.approx((-0.5, 3.0))


def test_the_mortar_reaches_1236_9_m_from_its_barrel_socket():
    mortar = WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"]

    # SquadCalc's squadBallistics.js gives the same 1236.936 m
    assert mortar.max_range() == pytest.approx(1236.936, abs=0.001)
    assert solve(mortar, 1236, 0, "high").reachable
    assert not solve(mortar, 1237, 0, "high").reachable


def test_a_motor_along_the_barrel_flies_the_exact_two_phase_parabola():
    """A rocket whose rotation keeps the barrel's axis (the S-5's
    rotation_follows_velocity false): constant acceleration on each phase,
    which the game's Velocity Verlet substeps follow exactly."""
    rocket = Weapon.from_dict(
        "r", {"velocity": 100, "acceleration": 50, "acceleration_time": 1.0,
              "rotation_follows_velocity": False}
    )
    rad = math.radians(10)

    # After the boost: x = cos(a) * (100 + 25 + 150 * (t - 1)), t = 3
    distance = math.cos(rad) * (125 + 150 * 2)
    height = (
        math.sin(rad) * 125 - 0.5 * GRAVITY
        + (math.sin(rad) * 150 - GRAVITY) * 2 - 0.5 * GRAVITY * 4
    )
    climb = math.atan2(math.sin(rad) * 150 - 3 * GRAVITY, math.cos(rad) * 150)

    assert not rocket.flies_boost_in_steps
    assert rocket.flight_height(rad, distance) == pytest.approx(height)
    assert rocket.flight_time(rad, distance) == pytest.approx(3.0)
    assert rocket.flight_at(rad, distance) == pytest.approx((height, 3.0, climb))


# The game's flight (review 1.6.0 slice 2, deadline-squad/squad-ballistics#4):
# 20 ms substeps, MaxSpeed clamped every substep, a motor along the path. The
# oracle is tests/flight.py, which flies the game's rules substep by substep
# from the game snapshot tests/data/game_weapons.json, without ballistics.py.

def _game_flight(name):
    import json

    import flight

    with open(os.path.join(ROOT, "tests", "data", "game_weapons.json"), encoding="utf-8") as stream:
        game = json.load(stream)[name]
    with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as stream:
        raw = json.load(stream)[name]

    return flight, flight.Shot(game, raw)


@pytest.mark.parametrize("name", [
    "RPG-7 · PG-7V HEAT / OG-7V",
    "M3 MAAWS · HEAT / Smoke",
    "PF98 · HE-I",
    "SPG-9 · HEAT",
    "Carl Gustav M2 · FFV751 Tandem",
    "Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2",
])
@pytest.mark.parametrize("distance", [200, 500, 800])
def test_the_elevation_lands_where_the_game_flies_it(name, distance):
    """Claim 2 and #4: the motor turns with the velocity and MaxSpeed caps
    the speed, so the old model (motor along the barrel, no cap) landed the
    RPG-7 metres low and tank HE hundreds of metres long."""
    flight, shot = _game_flight(name)

    for height in (-20, 0, 20):
        solution = solve(WEAPONS[name], distance, height, "low")
        miss = flight.miss(shot, math.radians(solution.raw_angle), distance, height)

        assert miss.distance < 0.02, (height, miss)


def test_a_shell_fired_faster_than_its_cap_is_slowed_in_the_first_substep():
    """Tank HE leaves at 1100 m/s with a 850 m/s cap: the first 20 ms
    substep ends at 850 m/s and moves by the mean of the two, then the shell
    flies at the cap (its path turning down very slowly when level)."""
    shell = WEAPONS["Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2"]
    first = (1100 + 850) / 2 * 0.02

    assert shell.max_speed == 850
    assert shell.flight_time(0.0, first) == pytest.approx(0.02, rel=1e-6)
    assert shell.flight_time(0.0, first / 2) == pytest.approx(0.01, rel=1e-6)
    assert shell.flight_time(0.0, 1000.0) == pytest.approx(0.02 + (1000 - first) / 850, rel=1e-3)
    assert solve(shell, 1000.0, 0.0).time_of_flight > 1000.0 / 1100 + 0.2


def test_a_shell_coming_down_faster_than_its_cap_is_held_at_it():
    """A plain parabola until the speed reaches the cap, the capped coast
    after it: lower than the parabola from there on."""
    capped = Weapon.from_dict("c", {"velocity": 300, "max_speed": 310})
    free = Weapon.from_dict("f", {"velocity": 300})
    rad = math.radians(30)
    # The speed reaches 310 m/s sqrt(310^2 - 300^2) / g after the apex
    apex_x = 300 ** 2 * math.sin(2 * rad) / (2 * GRAVITY)
    onset_x = apex_x + 300 * math.cos(rad) * math.sqrt(310 ** 2 - (300 * math.cos(rad)) ** 2) / GRAVITY

    assert capped.flight_height(rad, onset_x - 1) == pytest.approx(free.flight_height(rad, onset_x - 1))
    # Held at the cap it takes longer to get there and falls further
    assert capped.flight_height(rad, onset_x + 500) < free.flight_height(rad, onset_x + 500) - 0.1
    # 1500 m down the shell would reach 345 m/s: the cap changes the aim
    low = capped.elevations_to(5000, -1500)[0]
    assert low != pytest.approx(free.elevations_to(5000, -1500)[0], abs=1e-4)
    assert capped.flight_height(low, 5000) == pytest.approx(-1500, abs=1e-6)


@pytest.mark.parametrize("name", [
    "RPG-7 · PG-7V HEAT / OG-7V", "M3 MAAWS · HEAT / Smoke", "SPG-9 · HEAT", "PF98 · Tandem",
])
def test_the_boost_table_reproduces_the_stepped_boost(name):
    """The searches read the stepped boost from a table over the elevation
    (nodes every degree, 4-point interpolation): within 1 mm of flying it."""
    from ballistics import _fly_boost

    weapon = WEAPONS[name]
    assert weapon.flies_boost_in_steps

    for degrees in (-7.3, 0.4, 3.77, 12.5, 33.3, 61.9):
        rad = math.radians(degrees)
        points, _ = _fly_boost(weapon, rad)
        start_x, start_y = weapon.launch_point(rad)

        for x, y in points[1::7]:
            assert weapon.flight_height(rad, start_x + x) == pytest.approx(start_y + y, abs=1e-3)


@pytest.mark.parametrize("name", ["M3 MAAWS · HEAT / Smoke", "Tank HEAT/HE · M1A1 / M1A2 (M256)"])
def test_the_range_ladder_is_the_solution_at_each_tick(name):
    weapon = WEAPONS[name]
    ladder = range_ladder(weapon, 90, 1920, 100, 18, 1500)

    assert ladder
    for distance, offset in ladder:
        sight_angle = solve(weapon, distance, 0.0, "low").sight_angle
        assert offset == pytest.approx(mark_offset(weapon, sight_angle, 90, 1920))


def test_the_flight_time_starts_at_the_muzzle():
    """Claim 10: the time of flight counts from the muzzle, 2 m ahead of the
    pivot here, not from the pivot."""
    gun = Weapon.from_dict("g", {"velocity": 100, "gravity": 0, "muzzle_forward": 2.0})

    assert gun.flight_time(0.0, 102.0) == pytest.approx(1.0)
    assert solve(gun, 102.0, 0.0).time_of_flight == pytest.approx(1.0)


@pytest.mark.parametrize("data, match", [
    ({"velocity": 100, "max_speed": -1}, "max_speed"),
    ({"velocity": 100, "rotation_follows_velocity": "no"}, "rotation_follows_velocity"),
    ({"velocity": 300, "gravity": 0, "max_speed": 250}, "max_speed"),
    ({"velocity": 100, "lifespan": -1}, "lifespan"),
    ({"velocity": 100, "lifespan": "long"}, "lifespan"),
])
def test_invalid_flight_fields_are_rejected(data, match):
    with pytest.raises(WeaponDataError, match=match):
        Weapon.from_dict("x", data)


def test_every_public_item_of_the_model_is_documented():
    """Claim 9 of the 1.6.0 review."""
    import inspect

    import ballistics

    for name, item in vars(ballistics).items():
        if name.startswith("_") or getattr(item, "__module__", None) != "ballistics":
            continue
        if inspect.isclass(item) or inspect.isfunction(item):
            assert inspect.getdoc(item), name
            for member, value in vars(item).items() if inspect.isclass(item) else ():
                if not member.startswith("_") and (inspect.isfunction(value) or isinstance(value, property)):
                    assert inspect.getdoc(value), f"{name}.{member}"


def test_gravity_is_the_games_980_cm_per_s2():
    """DefaultGravityZ = -980 (game files) and SquadCalc's 9.80: the two apps
    must agree, tools/direct_fire/compare.py checks them at 1e-6 degrees."""
    assert GRAVITY == 9.80


def test_a_shot_that_takes_longer_than_the_lifespan_is_refused():
    """The game destroys the projectile `lifespan` seconds after it spawns
    (InitialLifeSpan): a target it would reach later cannot be hit."""
    plain = Weapon.from_dict("p", {"velocity": 100, "gravity": 1})
    mortal = Weapon.from_dict("m", {"velocity": 100, "gravity": 1, "lifespan": 3})

    near = solve(mortal, 250)
    far = solve(mortal, 400)

    assert near.reachable
    assert near.time_of_flight < 3
    assert solve(plain, 400).time_of_flight > 3
    assert not far.reachable
    assert far.reason_code == "out_of_range"
    assert "3 s" in far.reason
    assert solve(plain, 400).reachable


def test_the_lifespan_is_compared_with_the_time_of_the_requested_arc():
    """The high arc of a lob takes longer than the low one: with a lifespan
    between the two times only the low arc is left, in `alternatives` too."""
    shell = Weapon.from_dict("s", {"velocity": 100, "gravity": 1, "lifespan": 12})
    low, high = solve(shell, 800, arc="low"), solve(shell, 800, arc="high")
    unlimited = solve(replace(shell, lifespan=0.0), 800, arc="high")

    assert low.time_of_flight < 12 < unlimited.time_of_flight
    assert low.reachable
    assert not high.reachable
    assert high.reason_code == "out_of_range"
    assert list(low.alternatives) == ["low"]


def test_the_range_ladder_ends_where_the_projectile_is_gone():
    rocket = Weapon.from_dict("r", {"velocity": 120, "gravity": 1, "lifespan": 3})
    unlimited = replace(rocket, lifespan=0.0)
    ticks = range_ladder(rocket, 90, 1920, first=20, spacing=18, reach=2000)

    assert ticks
    assert len(range_ladder(unlimited, 90, 1920, first=20, spacing=18, reach=2000)) > len(ticks)
    assert all(solve(rocket, distance, 0.0, "low").reachable for distance, _ in ticks)


def test_the_real_weapons_carry_the_games_lifespan():
    """RPG-7 4 s, M203 grenade 20 s, AGS-17 VOG 40 s, the mortar's shell none."""
    assert WEAPONS["RPG-7 · PG-7V HEAT / OG-7V"].lifespan == 4
    assert WEAPONS["M203 / M320 / GP-25 / HK79 / SL40"].lifespan == 20
    assert WEAPONS["AGS-17 · emplacement · optic (RMB ×2.5)"].lifespan == 40
    assert WEAPONS["Mortar (M252 / 2B14 / L16 / Type 63)"].lifespan == 0

    rpg = WEAPONS["RPG-7 · PG-7V HEAT / OG-7V"]

    assert solve(rpg, 600).reachable
    assert not solve(rpg, 1500).reachable
