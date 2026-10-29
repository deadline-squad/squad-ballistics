"""Ballistic math for Squad Ballistics.

Pure functions only (no Qt), so everything here can be unit-tested.

Projectile model (same idea as the game and SquadCalc): no air drag, a
per-weapon gravity scale and an optional phase right after launch during
which the projectile speeds up (rocket motor, positive acceleration) or
slows down (UB-32 rockets, negative acceleration).

The changing speed is folded into an "equivalent velocity": the constant
speed that covers the distance in the same time. For the low, flat shots
these weapons are used for this gives the correct drop at the target.
"""

import json
import math
from dataclasses import dataclass, field

# Squad's world gravity in m/s^2 (same value SquadCalc uses).
GRAVITY = 9.78

# Squad mortars use the 6400 mil circle.
MILS_PER_DEGREE = 6400 / 360

ARCS = ("low", "high")
UNITS = ("deg", "mil")
AIMS = ("overlay", "elevation")


# Weapons renamed when their data was checked against the game files (Squad build
# 26005357): old weapons.json name -> current name. Settings saved by older
# versions and older SquadCalc pages still send the old names.
RENAMED_WEAPONS = {
    "M203 / M320 / GP-25 / HK79 / MKE MGL": "M203 / M320 / GP-25 / HK79 / SL40",
    "MK19 / AGS-17 / AGS-30": "MK19",
    "BTR-4 AGS": "AGS-30 / BTR-4 AGS",
    "Carl Gustav / M3 MAAWS · HEAT": "M3 MAAWS · HEAT / Smoke",
    "Carl Gustav / M3 MAAWS · Tandem": "M3 MAAWS · Tandem",
    "Tank AP · 2A46 / ZPT98 / 2A20 / M68A2": "Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3",
    "Tank AP · L30A1 (Challenger 2)": "Tank AP · L30A1 (Challenger 2) / M68A2",
    "2A42 / 2A72 30mm · HE": "2A42 30mm (BMP-2) · HE",
    "ZPT99 30mm · AP": "ZPT99 30mm (ZBL-08) · APFSDS",
    "ZPT99 30mm · HE": "ZPT99 30mm (ZBD-04A) · AP / HE",
}


def current_weapon_name(name):
    """The current weapons.json name of `name`, which may be a pre-rename one."""
    return RENAMED_WEAPONS.get(name, name)


class WeaponDataError(ValueError):
    """Raised when weapons.json contains invalid data."""


@dataclass(frozen=True)
class Weapon:
    name: str
    velocity: float
    gravity: float = 1.0
    arc: str = "low"
    unit: str = "deg"
    aim: str = "overlay"
    angle_offset: float = 0.0
    acceleration: float = 0.0
    acceleration_time: float = 0.0
    min_distance: float = 0.0
    elevation_limits: tuple = (-90.0, 90.0)
    launch_height: float = 0.0
    hold_rate: float = 0.0
    hold_elevation: tuple = ()
    category: str = "other"
    note: str = ""
    note_ru: str = ""
    mod: str = ""

    @classmethod
    def from_dict(cls, name, data):
        if not isinstance(data, dict):
            raise WeaponDataError(f"{name}: entry must be an object")

        if "velocity" not in data:
            raise WeaponDataError(f"{name}: 'velocity' is required")

        def number(key, default):
            value = data.get(key, default)
            if isinstance(value, bool):
                raise WeaponDataError(f"{name}: '{key}' must be a number")
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise WeaponDataError(f"{name}: '{key}' must be a number")
            if not math.isfinite(value):
                raise WeaponDataError(f"{name}: '{key}' must be finite")
            return value

        velocity = number("velocity", 0)
        gravity = number("gravity", 1.0)

        # "deceleration" is the older spelling of a negative acceleration.
        acceleration = (
            number("acceleration", 0.0) - number("deceleration", 0.0)
        )
        acceleration_time = number(
            "acceleration_time",
            data.get("deceleration_time", 0.0)
        )

        if velocity <= 0:
            raise WeaponDataError(f"{name}: 'velocity' must be > 0")
        if gravity < 0:
            raise WeaponDataError(f"{name}: 'gravity' must be >= 0")
        if acceleration_time < 0:
            raise WeaponDataError(f"{name}: 'acceleration_time' must be >= 0")
        if velocity + acceleration * acceleration_time <= 0:
            raise WeaponDataError(
                f"{name}: deceleration would stop the projectile"
            )

        arc = data.get("arc", "low")
        if arc not in ARCS:
            raise WeaponDataError(f"{name}: 'arc' must be one of {ARCS}")

        unit = data.get("unit", "deg")
        if unit not in UNITS:
            raise WeaponDataError(f"{name}: 'unit' must be one of {UNITS}")

        aim = data.get("aim", "elevation" if arc == "high" else "overlay")
        if aim not in AIMS:
            raise WeaponDataError(f"{name}: 'aim' must be one of {AIMS}")

        limits = data.get("elevation_limits", [-90, 90])
        try:
            low, high = (float(v) for v in limits)
        except (TypeError, ValueError):
            raise WeaponDataError(
                f"{name}: 'elevation_limits' must be [min, max]"
            )
        if low >= high:
            raise WeaponDataError(f"{name}: invalid 'elevation_limits'")

        hold_rate = number("hold_rate", 0.0)
        if hold_rate < 0:
            raise WeaponDataError(f"{name}: 'hold_rate' must be >= 0")

        hold_elevation = ()
        if hold_rate:
            try:
                lowest, top = (float(v) for v in data["hold_elevation"])
            except (KeyError, TypeError, ValueError):
                raise WeaponDataError(
                    f"{name}: 'hold_rate' needs 'hold_elevation': [lowest, top]"
                )
            if not low <= lowest < top <= high:
                raise WeaponDataError(
                    f"{name}: 'hold_elevation' must lie within "
                    "'elevation_limits' and go from lowest to top"
                )
            hold_elevation = (lowest, top)

        return cls(
            name=name,
            velocity=velocity,
            gravity=gravity,
            arc=arc,
            unit=unit,
            aim=aim,
            angle_offset=number("angle_offset", 0.0),
            acceleration=acceleration,
            acceleration_time=acceleration_time,
            min_distance=number("min_distance", 0.0),
            elevation_limits=(low, high),
            launch_height=number("launch_height", 0.0),
            hold_rate=hold_rate,
            hold_elevation=hold_elevation,
            category=str(data.get("category", "other")),
            note=str(data.get("note", "")),
            note_ru=str(data.get("note_ru", "")),
            mod=str(data.get("mod", "")),
        )

    @property
    def g(self):
        return GRAVITY * self.gravity

    @property
    def has_boost(self):
        return self.acceleration != 0 and self.acceleration_time > 0

    @property
    def boost_distance(self):
        t = self.acceleration_time
        return self.velocity * t + 0.5 * self.acceleration * t * t

    @property
    def has_hold(self):
        """Aimed by holding a key that lowers the barrel (AGS-17)."""
        return self.hold_rate > 0

    def hold_time(self, angle):
        """Seconds to hold the elevation key to reach `angle` degrees.

        Hold weapons start at the top of `hold_elevation` (after a reset the
        barrel points almost straight up) and the key lowers the barrel at
        `hold_rate` degrees per second down to the lowest elevation.
        Returns NaN for other weapons and for angles the key cannot reach.
        """
        if not self.has_hold or not math.isfinite(angle):
            return math.nan

        lowest, top = self.hold_elevation

        if not lowest <= angle <= top:
            return math.nan

        return (top - angle) / self.hold_rate

    def max_hold_time(self):
        """Hold time that lowers the barrel all the way, NaN without hold."""
        if not self.has_hold:
            return math.nan

        lowest, top = self.hold_elevation

        return (top - lowest) / self.hold_rate

    def hold_distance(self, held):
        """Flat-ground range of the barrel after holding the key `held` s.

        The barrel stops at the lowest hold elevation. The shell leaves the
        muzzle `launch_height` above the ground. NaN without hold.
        """
        if not self.has_hold:
            return math.nan

        lowest, top = self.hold_elevation

        rad = math.radians(max(lowest, top - self.hold_rate * max(0.0, held)))

        v = self.velocity
        vertical = v * math.sin(rad)
        flight = (
            vertical
            + math.sqrt(vertical ** 2 + 2 * self.g * self.launch_height)
        ) / self.g

        return v * math.cos(rad) * flight

    @property
    def cruise_velocity(self):
        return self.velocity + self.acceleration * self.acceleration_time

    def time_to(self, distance):
        """Time to cover `distance` metres along the flight path."""
        if distance <= 0:
            return 0.0

        if not self.has_boost:
            return distance / self.velocity

        if distance <= self.boost_distance:
            a = self.acceleration
            root = math.sqrt(
                max(0.0, self.velocity ** 2 + 2 * a * distance)
            )
            return (root - self.velocity) / a

        return (
            self.acceleration_time
            + (distance - self.boost_distance) / self.cruise_velocity
        )

    def velocity_at(self, distance):
        """Equivalent constant velocity over `distance`."""
        if distance <= 0 or not self.has_boost:
            return self.velocity

        return distance / self.time_to(distance)

    def max_range(self):
        """Maximum range on flat ground (45 degrees), inf without gravity."""
        if self.g == 0:
            return math.inf

        if not self.has_boost:
            return self.velocity ** 2 / self.g

        # Range is reachable while v(d)^2 >= g * d.
        def reachable(d):
            return self.velocity_at(d) ** 2 >= self.g * d

        low, high = 0.0, max(self.velocity, self.cruise_velocity) ** 2 / self.g
        while reachable(high):
            high *= 2

        for _ in range(60):
            mid = (low + high) / 2
            if reachable(mid):
                low = mid
            else:
                high = mid

        return low


@dataclass
class Solution:
    reachable: bool
    arc: str
    distance: float
    height_diff: float
    angle: float = math.nan          # elevation in degrees, angle_offset applied
    raw_angle: float = math.nan      # physical barrel angle in degrees
    # Elevation above the line of sight to the target, in degrees: what the
    # overlay mark and sight scales measure (angle on flat ground).
    sight_angle: float = math.nan
    mils: float = math.nan
    time_of_flight: float = math.nan
    velocity: float = math.nan
    apex: float = math.nan           # highest point above the weapon, metres
    impact_angle: float = math.nan   # descent angle at the target, degrees
    hold_time: float = math.nan      # seconds to hold the key, hold weapons
    reason: str = ""
    reason_code: str = ""
    alternatives: dict = field(default_factory=dict)


def resolve_arc(weapon, arc):
    if arc in (None, "", "auto"):
        return weapon.arc
    if arc not in ARCS:
        raise ValueError(f"Unknown arc '{arc}'")
    return arc


def _path(v, g, rad, x):
    """Height of a parabolic path at horizontal distance x."""
    if g == 0:
        return x * math.tan(rad)
    return x * math.tan(rad) - g * x * x / (2 * v * v * math.cos(rad) ** 2)


def solve(weapon, distance, height_diff=0.0, arc=None):
    """Elevation needed to hit a target.

    distance     -- horizontal distance to the target in metres
    height_diff  -- target ground height relative to the weapon ground
                    (positive = higher); the muzzle is `launch_height` above
    arc          -- "low", "high" or None/"auto" for the weapon default

    For hold weapons (AGS-17) the high arc is fired by holding a key, so it
    is only reachable inside `hold_elevation`; `hold_time` is then set.
    """
    arc = resolve_arc(weapon, arc)

    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Distance must be greater than 0")
    if not math.isfinite(height_diff):
        raise ValueError("Height difference must be a number")

    result = Solution(
        reachable=False,
        arc=arc,
        distance=distance,
        height_diff=height_diff,
    )

    if distance < weapon.min_distance:
        result.reason_code = "too_close"
        result.reason = (
            f"Too close: minimum distance is {weapon.min_distance:g} m"
        )
        return result

    g = weapon.g

    # Heights below are measured from the muzzle.
    rise = height_diff - weapon.launch_height

    if g == 0:
        # No gravity: the projectile flies straight along the line of sight.
        v = weapon.velocity_at(math.hypot(distance, rise))
        rad = math.atan2(rise, distance)
        raw = {"low": rad, "high": rad}
    else:
        v = weapon.velocity_at(distance)

        discriminant = (
            v ** 4 - g * (g * distance ** 2 + 2 * rise * v ** 2)
        )

        if discriminant < 0:
            result.reason_code = "out_of_range"
            result.reason = (
                f"Out of range (max ~{weapon.max_range():.0f} m "
                "on flat ground)"
            )
            return result

        root = math.sqrt(discriminant)

        raw = {
            "low": math.atan((v ** 2 - root) / (g * distance)),
            "high": math.atan((v ** 2 + root) / (g * distance)),
        }

    result.velocity = v

    low_limit, high_limit = weapon.elevation_limits

    for name, rad in raw.items():
        angle = math.degrees(rad) - weapon.angle_offset
        if not low_limit <= angle <= high_limit:
            continue
        # The high arc of a hold weapon can only be fired by holding the key.
        if weapon.has_hold and name == "high" \
                and not math.isfinite(weapon.hold_time(angle)):
            continue
        result.alternatives[name] = angle

    rad = raw[arc]
    angle = math.degrees(rad) - weapon.angle_offset

    result.angle = angle
    result.raw_angle = math.degrees(rad)

    if not low_limit <= angle <= high_limit:
        result.reason_code = "elevation_limit"
        result.reason = (
            f"{arc.capitalize()} arc needs {angle:.1f}°, weapon elevation "
            f"is limited to {low_limit:g}°..{high_limit:g}°"
        )
        return result

    if weapon.has_hold and arc == "high":
        result.hold_time = weapon.hold_time(angle)

        if not math.isfinite(result.hold_time):
            lowest, top = weapon.hold_elevation
            result.reason_code = "hold_limit"
            result.reason = (
                f"High arc needs {angle:.1f}°, holding the key is limited "
                f"to {lowest:g}°..{top:g}°"
            )
            return result

    result.reachable = True
    result.mils = angle * MILS_PER_DEGREE

    # The eye is taken at the muzzle: the target is seen this far above the
    # horizon, so aiming at it already raises the barrel by that much.
    result.sight_angle = angle - math.degrees(math.atan2(rise, distance))
    result.time_of_flight = distance / (v * math.cos(rad))

    if g == 0:
        result.apex = max(0.0, rise) + weapon.launch_height
        result.impact_angle = -math.degrees(rad)
    else:
        top_x = v * v * math.sin(rad) * math.cos(rad) / g
        top_x = min(max(top_x, 0.0), distance)
        result.apex = (
            max(0.0, _path(v, g, rad, top_x), rise) + weapon.launch_height
        )

        slope = math.tan(rad) - g * distance / (v * v * math.cos(rad) ** 2)
        result.impact_angle = -math.degrees(math.atan(slope))

    return result


def trajectory(weapon, solution, points=64):
    """Sample the flight path of a solved shot as (x, y) tuples.

    y is relative to the weapon's ground, like `solution.height_diff`.
    """
    if not math.isfinite(solution.raw_angle):
        return []

    rad = math.radians(solution.raw_angle)
    v = solution.velocity
    g = weapon.g
    d = solution.distance

    return [
        (d * i / points, _path(v, g, rad, d * i / points) + weapon.launch_height)
        for i in range(points + 1)
    ]


# The profile this close to the muzzle is the weapon's own spot, and this
# close to the target the target's own spot (same as SquadCalc's coverage).
MUZZLE_CLEARANCE = 3.0
TARGET_CLEARANCE = 3.0


def first_obstacle(weapon, solution, profile, step):
    """First point where a solved shot passes under the terrain profile.

    `profile` holds the heights of the terrain and the buildings every `step`
    metres from the weapon (index 0) towards the target, relative to the
    weapon's ground like `solution.height_diff` (SquadCalc's map, see
    maplink.MapTarget.profile). Returns (distance, height) of the obstacle
    in metres, or None when the path clears it or the shot is unsolved.
    """
    if not solution.reachable or not profile or not step:
        return None

    rad = math.radians(solution.raw_angle)
    v = solution.velocity
    g = weapon.g
    last = solution.distance - TARGET_CLEARANCE

    for i in range(math.ceil(MUZZLE_CLEARANCE / step), len(profile)):
        x = i * step

        if x > last:
            break

        if _path(v, g, rad, x) + weapon.launch_height < profile[i]:
            return x, profile[i]

    return None


def height_at(weapon, angle, distance):
    """Height of the projectile after travelling `distance` metres.

    `angle` is the elevation as returned by `solve` (angle_offset applied);
    the height is relative to the weapon's ground, like `height_diff`.
    Used for verification and tests.
    """
    rad = math.radians(angle + weapon.angle_offset)
    return (
        _path(weapon.velocity_at(distance), weapon.g, rad, distance)
        + weapon.launch_height
    )


def screen_offset(angle, fov, screen_width, scale=1.0):
    """Vertical pixel offset of the aim point for a given elevation.

    Squad renders with a rectilinear projection and a horizontal FOV, so the
    focal length in pixels is (width / 2) / tan(fov / 2). A point that is
    `angle` degrees below the view centre is projected focal * tan(angle)
    pixels below it. Raising the barrel by `angle` therefore means placing
    the target that many pixels BELOW the screen centre.
    """
    if not 1 <= fov <= 179:
        raise ValueError("FOV must be between 1 and 179 degrees")
    if screen_width <= 0:
        raise ValueError("Screen width must be positive")

    if abs(angle) >= 89.9:
        return math.copysign(math.inf, angle)

    focal = (screen_width / 2) / math.tan(math.radians(fov) / 2)
    return focal * math.tan(math.radians(angle)) * scale


def load_weapons(path):
    """Load weapons.json into an ordered {name: Weapon} dict."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise WeaponDataError(f"Weapons file not found: {path}")
    except json.JSONDecodeError as e:
        raise WeaponDataError(f"weapons.json is not valid JSON: {e}")

    return parse_weapons(raw)


def parse_weapons(raw):
    if not isinstance(raw, dict):
        raise WeaponDataError("weapons.json must contain an object")

    weapons = {}
    for name, data in raw.items():
        # Keys starting with "_" are comments / metadata.
        if name.startswith("_"):
            continue
        weapons[name] = Weapon.from_dict(name, data)

    if not weapons:
        raise WeaponDataError("weapons.json does not define any weapons")

    return weapons
