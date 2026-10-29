import json

import pytest

from maplink import (
    MapTarget,
    make_target,
    parse_bridge,
    parse_bridge_targets,
    parse_profile,
    parse_weapon_name,
    select_weapon_script,
)


def test_bridge_targets():
    value = [
        {"distance": 812.4, "heightDiff": -7.5, "bearing": 45.0},
        {"distance": 300},
        {"distance": None, "heightDiff": 1},
        {"distance": -1},
        "junk",
    ]

    assert parse_bridge_targets(value) == [
        MapTarget(812.4, -7.5, 45.0),
        MapTarget(300.0, None, None),
    ]

    assert parse_bridge_targets(None) == []
    assert parse_bridge_targets({"distance": 5}) == []


def test_bridge_with_weapon():
    value = {
        "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
        "weapon": "RPG-29",
    }

    assert parse_bridge(value) == ([MapTarget(420.0, -6.0, 90.0)], "RPG-29")

    # No bridge on the page, a page before the weapon export, no targets.
    assert parse_bridge(None) is None
    assert parse_bridge([{"distance": 300}]) is None
    assert parse_bridge({"targets": [{"distance": 300}]}) == (
        [MapTarget(300.0, None, None)], None
    )
    assert parse_bridge({"targets": None, "weapon": None}) == ([], None)


@pytest.mark.parametrize("value, name", [
    ("RPG-7 · PG-7VR Tandem", "RPG-7 · PG-7VR Tandem"),
    ("  RPG-29 ", "RPG-29"),
    ("", None),
    ("   ", None),
    (None, None),
    (42, None),
    (["RPG-29"], None),
    ("x" * 201, None),
])
def test_weapon_names(value, name):
    assert parse_weapon_name(value) == name


def test_select_weapon_script_quotes_the_name():
    name = "RPG-7 · PG-7V HEAT / OG-7V'\"); alert(1); //"
    script = select_weapon_script(name)

    # The name is a single JSON string literal: it cannot end the call.
    argument = script.split("bridge.selectWeapon(", 1)[1].rsplit(");", 1)[0]
    assert json.loads(argument) == name
    assert script.startswith("(function (bridge)")


def test_bridge_target_profile():
    heights = [0.0, 1.5, -2.25, 4.0, 0.0]
    [target] = parse_bridge_targets([
        {"distance": 4.2, "heightDiff": 0, "bearing": 0, "profile": {"step": 1, "heights": heights}},
    ])
    assert target.profile == tuple(heights)
    assert target.profile_step == 1

    # Older pages (bridge version 3) send no profile.
    [target] = parse_bridge_targets([{"distance": 4.2, "heightDiff": 0, "bearing": 0}])
    assert target.profile is None and target.profile_step is None


@pytest.mark.parametrize("profile", [
    None,
    "1,2,3",
    {"step": 1},
    {"step": 1, "heights": "0 0 0 0 0"},
    {"step": 0.1, "heights": [0.0] * 43},          # finer than MIN_PROFILE_STEP
    {"step": 1, "heights": [0.0] * 2},             # does not reach the target
    {"step": 1, "heights": [0.0] * 50},            # far beyond the target
    {"step": 1, "heights": [0, 0, None, 0, 0]},
    {"step": 1, "heights": [0, 0, True, 0, 0]},
    {"step": 1, "heights": [0, 0, "nan", 0, 0]},
    {"step": 1, "heights": [0, 0, 1e9, 0, 0]},     # beyond MAX_HEIGHT
    {"step": float("inf"), "heights": [0, 0, 0, 0, 0]},
])
def test_unusable_profiles_are_dropped(profile):
    assert parse_profile(profile, 4.2) == (None, None)
    [target] = parse_bridge_targets([{"distance": 4.2, "heightDiff": 0, "profile": profile}])
    assert target.distance == 4.2 and target.profile is None


def test_untrusted_values_are_bounded():
    # The page is not trusted: absurd values must not reach the ballistics
    # (1e200 m overflows it).
    assert parse_bridge_targets([{"distance": 1e200}]) == []
    assert parse_bridge_targets([{"distance": 10001}]) == []
    assert parse_bridge_targets([
        {"distance": 10000, "heightDiff": 5000, "bearing": 370}
    ]) == [MapTarget(10000.0, None, 10.0)]
    assert parse_bridge_targets([{"distance": 1e308, "heightDiff": 1}]) == []
    assert make_target(500, -2999, -90) == MapTarget(500.0, -2999.0, 270.0)
    assert make_target(float("nan")) is None


@pytest.mark.parametrize("bad", ["500", True, None, [500], {"v": 500}, float("inf")])
def test_only_real_numbers_are_accepted(bad):
    assert make_target(bad) is None
    assert make_target(500, bad, 10) == MapTarget(500.0, None, 10.0)
    assert make_target(500, 5, bad) == MapTarget(500.0, 5.0, None)
    assert parse_bridge_targets([{"distance": bad}]) == []


def test_numbers_may_be_int_or_float():
    assert make_target(500, 5, 90) == MapTarget(500.0, 5.0, 90.0)
    assert make_target(500.5, -5.5, 90.5) == MapTarget(500.5, -5.5, 90.5)


@pytest.mark.parametrize("bearing", [-1e-20, -1e-300, 360, 720.0, -360, 359.99999999999999])
def test_bearing_stays_below_360(bearing):
    assert 0 <= make_target(500, 0, bearing).bearing < 360
