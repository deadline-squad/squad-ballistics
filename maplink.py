"""Targets from the embedded SquadCalc map: distance, height difference and bearing.

The calculator takes the target geometry from the SquadCalc map and solves it
itself, so the map only needs the weapon and target markers. The Deadline
SquadCalc build exposes `window.squadBallistics.targets()` and `.weapon()`,
which `webmap.MapPage` polls (see `bridge_script`); `parse_bridge` reads the
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
The answer is read on the GUI thread every poll, so its size is bounded
too: only the newest target (the last one) is sent and parsed, and its
profile has at most `MAX_PROFILE_HEIGHTS` heights.

Cheap polls. A target's profile has up to 10001 heights, so the answer is
parsed only when it changed. A page with the optional change counter
(`revision`, a number or a function returning one, which grows with every
change of the targets) is asked with that counter, and sends the target
again only when the counter differs from the one the app already has; the
page may also give the newest target alone (`lastTarget()`, the target or
null) so that it does not build every target's profile. A page without the
counter sends everything each poll and the app compares the raw answer
before parsing it. A page that announces a change with
`console.info("sb:changed")` (see `CHANGE_MESSAGE`) is asked at once
instead of at the next poll; `WATCH_SCRIPT` makes a page with the counter
do so.
"""

import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Optional, Tuple

# Targets outside these limits are rejected: the data comes from a web page,
# and absurd numbers overflow the ballistics.
MAX_DISTANCE = 10000
MAX_HEIGHT = 3000

# A poll answer longer than this (characters of JSON) is not read: the real
# one, with the longest profile, is about 100 000.
MAX_ANSWER_CHARS = 1000000

# Profile heights are at least this far apart (a finer profile from a hostile
# page would only cost memory and time), in metres.
MIN_PROFILE_STEP = 0.5

# At most this many profile heights (one per metre over MAX_DISTANCE: the
# SquadCalc build samples every metre, PROFILE_STEP in smcConnector.js).
MAX_PROFILE_HEIGHTS = MAX_DISTANCE + 1

# Weapon names longer than this are not weapons.json names (see MAX_DISTANCE).
MAX_WEAPON_NAME = 200

# Unicode categories no weapons.json name has: control and format characters
# (a bidi override would draw a name other than the one it is), surrogates,
# private and unassigned code points, line and paragraph separators.
NAME_REJECTED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})

# The console message a page prints when its targets or weapon changed.
CHANGE_MESSAGE = "sb:changed"

# The script polled on the embedded page (see `bridge_script`): {targets,
# weapon} as JSON text, or null on SquadCalc builds without the bridge, with
# `revision` (the page's change counter, null without one). Builds before
# the weapon export give no weapon. Only the newest target (the last) is
# sent: it is the only one used, and a long list would be converted on the
# GUI thread at every poll. A page with the counter leaves "targets" out
# while the counter is still `known`. "@KNOWN@" is replaced by the counter
# the app has, or null.
_POLL_SCRIPT = (
    "(function (bridge, known) {"
    " if (!bridge || typeof bridge.targets !== 'function') return null;"
    " var revision = bridge.revision;"
    " if (typeof revision === 'function') revision = revision.call(bridge);"
    " if (typeof revision !== 'number') revision = null;"
    " var answer = {revision: revision,"
    " weapon: typeof bridge.weapon === 'function' ? bridge.weapon() : null};"
    " if (revision === null || revision !== known) {"
    "  var targets;"
    "  if (typeof bridge.lastTarget === 'function') {"
    "   var last = bridge.lastTarget();"
    "   targets = last ? [last] : [];"
    "  } else {"
    "   targets = bridge.targets();"
    "   if (Array.isArray(targets)) targets = targets.slice(-1);"
    "  }"
    "  answer.targets = targets;"
    " }"
    " return JSON.stringify(answer);"
    "})(window.squadBallistics, @KNOWN@)"
)

# Injected into the map page (the page's own JavaScript world): prints
# CHANGE_MESSAGE when the page's change counter or weapon changes, so a
# change reaches the app within one tick instead of at the next poll. A page
# without the counter is left alone: finding out what changed there means
# building every target's profile.
WATCH_SCRIPT = (
    "(function () {"
    " var seen = null, weapon = null;"
    " setInterval(function () {"
    "  var bridge = window.squadBallistics;"
    "  if (!bridge) return;"
    "  var revision = bridge.revision;"
    "  if (typeof revision === 'function') revision = revision.call(bridge);"
    "  if (typeof revision !== 'number') return;"
    "  var name = typeof bridge.weapon === 'function' ? bridge.weapon() : null;"
    "  if (revision === seen && name === weapon) return;"
    "  seen = revision; weapon = name;"
    "  console.info(%s);"
    " }, 40);"
    "})()"
) % json.dumps(CHANGE_MESSAGE)


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
    short of it), be at most MAX_PROFILE_HEIGHTS, and each be a number
    within MAX_HEIGHT.
    """
    if not isinstance(value, dict):
        return None, None

    step = _number(value.get("step"))
    heights = value.get("heights")

    if step is None or not MIN_PROFILE_STEP <= step <= distance:
        return None, None

    if not isinstance(heights, list) or len(heights) > MAX_PROFILE_HEIGHTS \
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
    """The newest target from `window.squadBallistics.targets()`, as a list.

    The page returns a list of {"distance", "heightDiff", "bearing",
    "profile"} (profile since bridge version 4) in the order they were
    placed. Only the last one is parsed (the poll script already sends only
    that one): [target], or [] when the list is empty, not a list, or its
    last entry is invalid (an older target is not used in its place).
    """
    if not isinstance(value, list) or not value:
        return []

    item = value[-1]

    if not isinstance(item, dict):
        return []

    target = make_target(
        item.get("distance"),
        item.get("heightDiff"),
        item.get("bearing"),
        item.get("profile")
    )

    return [] if target is None else [target]


def bridge_script(known_revision=None):
    """The script that polls the page: JSON text of {revision, weapon,
    targets}, null without the bridge.

    `known_revision` is the page's change counter the app already has (a
    number, or None): while the page's counter is still that, the answer
    has no "targets" and nothing is parsed again.
    """
    known = "null" if known_revision is None else json.dumps(known_revision)

    return _POLL_SCRIPT.replace("@KNOWN@", known)


def parse_revision(value):
    """The change counter in a decoded poll answer: an int, None when the
    page has none (or sends anything else)."""
    revision = value.get("revision") if isinstance(value, dict) else None

    if isinstance(revision, bool) or not isinstance(revision, (int, float)):
        return None

    if not math.isfinite(revision) or revision != int(revision):
        return None

    return int(revision)


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
    """A weapon name sent by SquadCalc, None if missing or unusable.

    Unusable: not text, empty, longer than MAX_WEAPON_NAME, or with a
    character of NAME_REJECTED_CATEGORIES anywhere (a control character or
    a bidi override is never part of a weapons.json name).
    """
    if not isinstance(value, str):
        return None

    name = value.strip()

    if not name or len(name) > MAX_WEAPON_NAME:
        return None

    if any(unicodedata.category(char) in NAME_REJECTED_CATEGORIES for char in name):
        return None

    return name


def parse_bridge(value):
    """(targets, weapon) from a decoded poll answer (see `bridge_script`).

    None means the page has no bridge. `weapon` is None when the page does
    not tell it (older build, or a weapon without a name here).
    """
    if not isinstance(value, dict):
        return None

    return (
        parse_bridge_targets(value.get("targets")),
        parse_weapon_name(value.get("weapon"))
    )
