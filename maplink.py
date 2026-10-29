"""Targets from the embedded SquadCalc map: distance, height difference and bearing.

The calculator takes the target geometry from the SquadCalc map and solves it
itself, so the map only needs the weapon and target markers. The Deadline
SquadCalc build exposes `window.squadBallistics.targets()` and `.weapon()`,
which `webmap.MapPage` polls (see `BRIDGE_SCRIPT`); `parse_bridge` reads the
result. `.weapon()` tells which weapon is selected on the map, by its name in
weapons.json (null when the weapon has no counterpart here); the calculator
then switches to it. The other way, `.selectWeapon(name)` (bridge version 3)
selects the weapon picked here on the map (see `select_weapon_script`), so
its fire coverage and popups are for the same weapon. Since bridge version 4
each target also carries the heights of the terrain and the buildings on the
line from the weapon to it (`MapTarget.profile`), so a trajectory that hits a
ridge or a roof first is detected (`ballistics.first_obstacle`).

The page is not trusted: every number is bounded (`MAX_DISTANCE`,
`MAX_HEIGHT`) and only real numbers are accepted, not strings or booleans.
"""

import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple

# Targets outside these limits are rejected: the data comes from a web page,
# and absurd numbers overflow the ballistics.
MAX_DISTANCE = 10000
MAX_HEIGHT = 3000

# Profile heights are at least this far apart (a finer profile from a hostile
# page would only cost memory and time), in metres.
MIN_PROFILE_STEP = 0.5

# Weapon names longer than this are not weapons.json names (see MAX_DISTANCE).
MAX_WEAPON_NAME = 200

# Script polled on the embedded page: {targets, weapon}, or null on SquadCalc
# builds without the bridge. Builds before the weapon export give no weapon.
BRIDGE_SCRIPT = (
    "(function (bridge) {"
    " if (!bridge || typeof bridge.targets !== 'function') return null;"
    " return {targets: bridge.targets(), weapon: typeof bridge.weapon"
    " === 'function' ? bridge.weapon() : null};"
    "})(window.squadBallistics)"
)


@dataclass(frozen=True)
class MapTarget:
    """One target of the SquadCalc map, relative to the first weapon marker.

    distance -- horizontal distance in metres
    height   -- target ground minus (weapon ground + the weapon marker's
                height padding) in metres, as SquadCalc computes it; the
                muzzle height is not included. None if unknown
    bearing  -- degrees from north in [0, 360), None if unknown
    profile  -- heights of the terrain and buildings every `profile_step`
                metres from the weapon (index 0) to the target, relative to
                the weapon like `height`; None if unknown
    profile_step -- metres between two profile heights, None without profile
    """

    distance: float
    height: Optional[float] = None
    bearing: Optional[float] = None
    profile: Optional[Tuple[float, ...]] = None
    profile_step: Optional[float] = None


def _number(value):
    """`value` as a float if it is a finite int or float (not a bool, not text)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value) if math.isfinite(value) else None


def parse_profile(value, distance):
    """(heights, step) of a bridge target's profile, (None, None) if unusable.

    `value` is {"step": metres, "heights": [...]} from SquadCalc; the heights
    must cover the distance to the target (one per step, up to one step
    short of it) and each be a number within MAX_HEIGHT.
    """
    if not isinstance(value, dict):
        return None, None

    step = _number(value.get("step"))
    heights = value.get("heights")

    if step is None or not MIN_PROFILE_STEP <= step <= distance:
        return None, None

    if not isinstance(heights, list) \
            or not distance / step <= len(heights) <= distance / step + 2:
        return None, None

    numbers = tuple(_number(h) for h in heights)

    if any(h is None or abs(h) > MAX_HEIGHT for h in numbers):
        return None, None

    return numbers, step


def make_target(distance, height=None, bearing=None, profile=None):
    """MapTarget from raw bridge values, None when the distance is unusable.

    Only int and float count as numbers (not bool, not text); anything else
    is unknown.

    The distance must be in (0, MAX_DISTANCE]; a height beyond MAX_HEIGHT
    becomes unknown and the bearing is wrapped to [0, 360). `profile` is the
    bridge's raw profile (see parse_profile); an unusable one is dropped.
    """
    distance, height, bearing = _number(distance), _number(height), _number(bearing)

    if distance is None or not 0 < distance <= MAX_DISTANCE:
        return None

    if height is not None and abs(height) > MAX_HEIGHT:
        height = None

    if bearing is not None:
        # A tiny negative bearing wraps to exactly 360.0 in floating point.
        bearing %= 360

        if bearing >= 360:
            bearing = 0.0

    heights, step = parse_profile(profile, distance)

    return MapTarget(distance, height, bearing, heights, step)


def parse_bridge_targets(value):
    """Targets from `window.squadBallistics.targets()`.

    The page returns a list of {"distance", "heightDiff", "bearing",
    "profile"} (profile since bridge version 4); None means the page has no
    bridge. Invalid entries are skipped.
    """
    if not isinstance(value, list):
        return []

    targets = []

    for item in value:
        if not isinstance(item, dict):
            continue

        target = make_target(
            item.get("distance"),
            item.get("heightDiff"),
            item.get("bearing"),
            item.get("profile")
        )

        if target is not None:
            targets.append(target)

    return targets


def select_weapon_script(name):
    """Script selecting weapon `name` on the embedded SquadCalc page.

    Evaluates to whether the page knows the weapon; null on builds without
    `selectWeapon`.
    """
    return (
        "(function (bridge) {"
        " if (!bridge || typeof bridge.selectWeapon !== 'function') return null;"
        f" return bridge.selectWeapon({json.dumps(name)});"
        "})(window.squadBallistics)"
    )


def parse_weapon_name(value):
    """A weapon name sent by SquadCalc, None if missing or unusable."""
    if not isinstance(value, str):
        return None

    name = value.strip()

    if not name or len(name) > MAX_WEAPON_NAME:
        return None

    return name


def parse_bridge(value):
    """(targets, weapon) from the result of `BRIDGE_SCRIPT`.

    None means the page has no bridge. `weapon` is None when the page does
    not tell it (older build, or a weapon without a name here).
    """
    if not isinstance(value, dict):
        return None

    return (
        parse_bridge_targets(value.get("targets")),
        parse_weapon_name(value.get("weapon"))
    )
