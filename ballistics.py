"""Ballistic math for Squad Ballistics.

Pure functions only (no Qt), so everything here can be unit-tested.

Projectile model, the game's own (Squad build 26005357, USQProjectileMovement
and the weapon's barrel socket; same model as SquadCalc's squadBallistics.js):

* no air drag; gravity is GRAVITY (DefaultGravityZ = -980 cm/s^2) times the
  projectile's gravity scale;
* the projectile leaves the muzzle, the barrel socket `Attach_Muzzle`, at
  `velocity` along the barrel. The barrel pivots `launch_height` above the
  ground; the muzzle is `muzzle_forward` along the barrel and `muzzle_up`
  above its axis, so the launch point moves with the elevation;
* for `acceleration_time` seconds a constant `acceleration` acts along the
  barrel's axis as it was at launch (rocket motor: positive; UB-32 rockets:
  negative). The game ends it at ConstantAccelerationTimeout or when the
  speed reaches the projectile's MaxSpeed, whichever comes first;
  weapons.json holds that time;
* between those, the flight is two exact parabolas, so no integration step is
  needed: the elevation that hits a target is found by root finding on the
  closed form.
"""

import json
import math
from dataclasses import dataclass, field, fields, replace

# Squad's world gravity in m/s^2: DefaultGravityZ = -980 cm/s^2 in the game.
GRAVITY = 9.80

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
    muzzle_forward: float = 0.0
    muzzle_up: float = 0.0
    bore: float = 0.0
    zoom: float = 0.0
    hold_rate: float = 0.0
    hold_elevation: tuple = ()
    category: str = "other"
    note: str = ""

    @classmethod
    def from_dict(cls, name, data):
        """Build a weapon from its weapons.json entry.

        Raises WeaponDataError for a malformed entry, a missing `velocity`
        or a key that is not a weapon field (a misspelt key would otherwise
        silently fall back to its default).
        """
        if not isinstance(data, dict):
            raise WeaponDataError(f"{name}: entry must be an object")

        unknown = sorted(set(data) - WEAPON_KEYS)
        if unknown:
            raise WeaponDataError(f"{name}: unknown keys {', '.join(unknown)}")

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

        launch_height = number("launch_height", 0.0)
        muzzle_forward = number("muzzle_forward", 0.0)
        muzzle_up = number("muzzle_up", 0.0)
        if launch_height < 0:
            raise WeaponDataError(f"{name}: 'launch_height' must be >= 0")
        if muzzle_forward < 0:
            raise WeaponDataError(f"{name}: 'muzzle_forward' must be >= 0")

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

        zoom = number("zoom", 0.0)
        if zoom and zoom < 1:
            raise WeaponDataError(f"{name}: 'zoom' must be >= 1 (or 0: none)")

        hold_rate = number("hold_rate", 0.0)
        if hold_rate < 0:
            raise WeaponDataError(f"{name}: 'hold_rate' must be >= 0")

        hold_elevation = ()
        if hold_rate and acceleration:
            raise WeaponDataError(
                f"{name}: a weapon laid by holding a key cannot have a boost"
            )
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
            launch_height=launch_height,
            muzzle_forward=muzzle_forward,
            muzzle_up=muzzle_up,
            bore=number("bore", 0.0),
            zoom=zoom,
            hold_rate=hold_rate,
            hold_elevation=hold_elevation,
            category=str(data.get("category", "other")),
            note=str(data.get("note", "")),
        )

    @property
    def g(self):
        """Gravity of the projectile in m/s^2."""
        return GRAVITY * self.gravity

    @property
    def has_boost(self):
        """A phase right after launch with a constant acceleration."""
        return self.acceleration != 0 and self.acceleration_time > 0

    @property
    def boost_distance(self):
        """Distance covered along the barrel's axis while the boost acts."""
        t = self.acceleration_time if self.has_boost else 0.0
        return self.velocity * t + 0.5 * self.acceleration * t * t

    def sight_view(self, fov):
        """(field of view, bore) of the view the weapon is aimed through.

        `fov` is the game's FOV setting; the game draws the weapon's sight
        at fov / `zoom` (a scope, an optic or a gunner's sight; 0 = the
        plain view). The bore (degrees) is how far above the screen centre
        the shot leaves: the game fires along the barrel socket
        (`Attach_Muzzle`), which can be tilted against the camera, so the
        view is zeroed at some range.
        """
        return fov / (self.zoom or 1.0), self.bore

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
        muzzle (`launch_point`) with no boost: a parabola from there. NaN
        without hold.
        """
        if not self.has_hold:
            return math.nan

        lowest, top = self.hold_elevation

        rad = math.radians(max(lowest, top - self.hold_rate * max(0.0, held)))

        start_x, start_y = self.launch_point(rad)
        vertical = self.velocity * math.sin(rad)
        flight = (
            vertical + math.sqrt(vertical ** 2 + 2 * self.g * start_y)
        ) / self.g

        return start_x + self.velocity * math.cos(rad) * flight

    @property
    def cruise_velocity(self):
        """Speed along the barrel once the boost is over."""
        return self.velocity + self.acceleration * self.acceleration_time

    def time_to(self, distance):
        """Time to cover `distance` metres along the barrel's axis."""
        if distance <= 0:
            return 0.0

        if not self.has_boost:
            return distance / self.velocity

        if distance <= self.boost_distance:
            return 2 * distance / (
                self.velocity
                + math.sqrt(
                    max(0.0, self.velocity ** 2 + 2 * self.acceleration * distance)
                )
            )

        return (
            self.acceleration_time
            + (distance - self.boost_distance) / self.cruise_velocity
        )

    def velocity_at(self, distance):
        """Equivalent constant velocity over `distance` along the axis."""
        if distance <= 0 or not self.has_boost:
            return self.velocity

        return distance / self.time_to(distance)

    def launch_point(self, rad):
        """(x, y) of the muzzle for a barrel elevation of `rad` radians:
        metres ahead of the pivot and above the ground. The muzzle sits
        `muzzle_forward` along the barrel and `muzzle_up` above its axis,
        so it moves as the barrel is raised.
        """
        cos, sin = math.cos(rad), math.sin(rad)

        return (
            self.muzzle_forward * cos - self.muzzle_up * sin,
            self.launch_height + self.muzzle_forward * sin + self.muzzle_up * cos,
        )

    @property
    def is_parabola(self):
        """The flight is one plain parabola (no boost, no muzzle offset)."""
        return not (self.has_boost or self.muzzle_forward or self.muzzle_up)

    def flight_height(self, rad, distance):
        """Height above the ground of the projectile when it is `distance`
        metres ahead of the pivot, fired at a barrel elevation of `rad`.

        Closed form of the game's motion (see the module docstring), exact
        for the model. A distance behind the muzzle extrapolates the same
        equations backwards.
        """
        cos, sin = math.cos(rad), math.sin(rad)
        v0, g, a = self.velocity, self.g, self.acceleration
        boost = self.acceleration_time
        start_x, start_y = self.launch_point(rad)
        ahead = distance - start_x
        reach = cos * (v0 * boost + 0.5 * a * boost * boost)

        if boost == 0 or ahead <= reach:
            along = ahead / cos
            t = 2 * along / (v0 + math.sqrt(max(0.0, v0 * v0 + 2 * a * along)))
            return start_y + sin * along - 0.5 * g * t * t

        end_speed = v0 + a * boost
        after = (ahead - reach) / (cos * end_speed)

        return (
            start_y
            + sin * (v0 * boost + 0.5 * a * boost * boost)
            - 0.5 * g * boost * boost
            + (sin * end_speed - g * boost) * after
            - 0.5 * g * after * after
        )

    def flight_time(self, rad, distance):
        """Seconds after launch when the projectile is `distance` metres
        ahead of the pivot, fired at a barrel elevation of `rad`."""
        cos = math.cos(rad)
        start_x, _ = self.launch_point(rad)
        ahead = distance - start_x

        if ahead <= 0:
            return 0.0

        return self.time_to(ahead / cos)

    def flight_state(self, rad, t):
        """(x, y, vx, vy) of the projectile `t` seconds after launch."""
        cos, sin = math.cos(rad), math.sin(rad)
        v0, g, a = self.velocity, self.g, self.acceleration
        boost = self.acceleration_time
        start_x, start_y = self.launch_point(rad)

        if t <= boost:
            along = v0 * t + 0.5 * a * t * t
            speed = v0 + a * t
            return (
                start_x + cos * along,
                start_y + sin * along - 0.5 * g * t * t,
                cos * speed,
                sin * speed - g * t,
            )

        after = t - boost
        along = v0 * boost + 0.5 * a * boost * boost
        end_speed = v0 + a * boost

        return (
            start_x + cos * (along + end_speed * after),
            start_y + sin * along - 0.5 * g * boost * boost
            + (sin * end_speed - g * boost) * after - 0.5 * g * after * after,
            cos * end_speed,
            sin * end_speed - g * t,
        )

    def elevations_to(self, distance, height):
        """Barrel elevations (low, high) in radians that land the projectile
        on a target `distance` metres away and `height` metres above the
        ground of the pivot; (NaN, NaN) when it is out of range.

        Pure parabolas use the closed form. Otherwise: the elevation that
        sends the projectile highest at `distance` is found by a golden
        section search (the height there rises to a single peak), the target
        is out of range when even that misses, and each root is bracketed on
        its side of the peak and narrowed with the Illinois method. Needs
        gravity.
        """
        g, v = self.g, self.velocity

        if self.is_parabola:
            rise = height - self.launch_height
            discriminant = v ** 4 - g * (g * distance ** 2 + 2 * rise * v ** 2)
            if discriminant < 0:
                return math.nan, math.nan
            root = math.sqrt(discriminant)
            return (
                math.atan((v ** 2 - root) / (g * distance)),
                math.atan((v ** 2 + root) / (g * distance)),
            )

        top = self.peak_elevation(distance)
        if self.flight_height(top, distance) < height:
            return math.nan, math.nan

        def error(rad):
            return self.flight_height(rad, distance) - height

        return _find_root(error, top, -1), _find_root(error, top, 1)

    def peak_elevation(self, distance):
        """Elevation (radians) that sends the projectile highest when it is
        `distance` metres ahead of the pivot (golden section search)."""
        low, high = -ELEVATION_LIMIT, ELEVATION_LIMIT
        left = high - _GOLDEN * (high - low)
        right = low + _GOLDEN * (high - low)
        left_height = self.flight_height(left, distance)
        right_height = self.flight_height(right, distance)

        for _ in range(MAX_ITERATIONS):
            if high - low <= ANGLE_TOLERANCE:
                break
            if left_height < right_height:
                low = left
                left, left_height = right, right_height
                right = low + _GOLDEN * (high - low)
                right_height = self.flight_height(right, distance)
            else:
                high = right
                right, right_height = left, left_height
                left = high - _GOLDEN * (high - low)
                left_height = self.flight_height(left, distance)

        return (low + high) / 2

    def max_range(self):
        """Maximum range on flat ground (the ground of the pivot), inf
        without gravity."""
        if self.g == 0:
            return math.inf

        if self.is_parabola and not self.launch_height:
            return self.velocity ** 2 / self.g

        def reachable(distance):
            return self.flight_height(self.peak_elevation(distance), distance) >= 0

        low = 0.0
        high = max(self.velocity, self.cruise_velocity) ** 2 / self.g
        while reachable(high):
            low, high = high, high * 2

        for _ in range(MAX_ITERATIONS):
            if high - low <= 1e-3:
                break
            mid = (low + high) / 2
            if reachable(mid):
                low = mid
            else:
                high = mid

        return low


# Keys of a weapons.json entry: the Weapon fields, plus the older spelling of
# a negative acceleration.
WEAPON_KEYS = frozenset(
    {field.name for field in fields(Weapon)} - {"name"}
    | {"deceleration", "deceleration_time"}
)

# Elevations are searched within +-ELEVATION_LIMIT: the barrel is never
# vertical.
ELEVATION_LIMIT = math.pi / 2 - 1e-6

# The searches stop when their bracket is narrower than this many radians
# (1e-10 rad is 0.2 mm at 2 km) or the height error is below HEIGHT_TOLERANCE
# metres.
ANGLE_TOLERANCE = 1e-10
HEIGHT_TOLERANCE = 1e-9

# First half-width of the bracket around the highest elevation (radians),
# doubled until it holds the root.
BRACKET_STEP = 0.02

# Safety cap of every search; the tolerances are reached long before.
MAX_ITERATIONS = 200

_GOLDEN = (math.sqrt(5) - 1) / 2


def _find_root(error, top, direction):
    """Root of `error` (metres, F(top) >= 0) on one side of `top`: towards
    lower elevations for direction -1, higher for +1. The bracket is expanded
    from `top` until F is negative, then narrowed with the Illinois method
    (regula falsi that halves the stale end's F).
    """
    far = top
    far_error = error(far)
    step = BRACKET_STEP

    while far_error >= 0:
        far = min(max(top + direction * step, -ELEVATION_LIMIT), ELEVATION_LIMIT)
        far_error = error(far)
        if abs(far) == ELEVATION_LIMIT:
            break
        step *= 2

    near, near_error = top, error(top)
    kept = 0
    root = far

    for _ in range(MAX_ITERATIONS):
        if abs(far - near) <= ANGLE_TOLERANCE:
            break
        root = (near * far_error - far * near_error) / (far_error - near_error)
        root_error = error(root)
        if abs(root_error) <= HEIGHT_TOLERANCE:
            break
        if root_error < 0:
            far, far_error = root, root_error
            if kept == -1:
                near_error /= 2
            kept = -1
        else:
            near, near_error = root, root_error
            if kept == 1:
                far_error /= 2
            kept = 1

    return root


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


def solve(weapon, distance, height_diff=0.0, arc=None):
    """Elevation needed to hit a target.

    distance     -- horizontal distance to the target in metres, from the
                    barrel's pivot
    height_diff  -- target ground height relative to the weapon ground
                    (positive = higher); the pivot is `launch_height` above
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

    # The target's height above the pivot, for the line of sight.
    rise = height_diff - weapon.launch_height

    if weapon.g == 0:
        # No gravity: the projectile flies straight along the line of sight.
        result.velocity = weapon.velocity_at(math.hypot(distance, rise))
        rad = math.atan2(rise, distance)
        raw = {"low": rad, "high": rad}
    else:
        low_rad, high_rad = weapon.elevations_to(distance, height_diff)

        if math.isnan(low_rad):
            result.reason_code = "out_of_range"
            result.reason = (
                f"Out of range (max ~{weapon.max_range():.0f} m "
                "on flat ground)"
            )
            return result

        raw = {"low": low_rad, "high": high_rad}

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

    # The eye is taken at the pivot: the target is seen this far above the
    # horizon, so aiming at it already raises the barrel by that much.
    result.sight_angle = angle - math.degrees(math.atan2(rise, distance))

    if weapon.g == 0:
        result.time_of_flight = distance / (result.velocity * math.cos(rad))
        result.apex = max(0.0, rise) + weapon.launch_height
        result.impact_angle = -math.degrees(rad)
        return result

    flight = weapon.flight_time(rad, distance)
    start_x, start_y = weapon.launch_point(rad)
    _, _, impact_vx, impact_vy = weapon.flight_state(rad, flight)

    result.time_of_flight = flight
    result.velocity = (distance - start_x) / (math.cos(rad) * flight)
    result.impact_angle = -math.degrees(math.atan2(impact_vy, impact_vx))
    result.apex = max(
        start_y, height_diff, _apex_height(weapon, rad, flight)
    )

    return result


def _apex_height(weapon, rad, until):
    """Highest height of the flight before `until` seconds, NaN if it only
    descends (the vertical speed is zero at most once, on the way up)."""
    g, boost = weapon.g, weapon.acceleration_time
    sin = math.sin(rad)

    # Vertical speed: sin * (v0 + a t) - g t while boosting, then
    # sin * end_speed - g t.
    denominator = g - sin * weapon.acceleration
    top = math.nan
    if boost > 0 and denominator > 0:
        top = sin * weapon.velocity / denominator
    if not 0 < top <= boost:
        top = sin * weapon.cruise_velocity / g

    if not 0 < top < until:
        return math.nan

    return weapon.flight_state(rad, top)[1]


def trajectory(weapon, solution, points=64):
    """Sample the flight path of a solved shot as (x, y) tuples.

    The path runs from the muzzle (where the projectile starts, which moves
    with the elevation) to the target; y is relative to the weapon's ground,
    like `solution.height_diff`.
    """
    if not math.isfinite(solution.raw_angle):
        return []

    rad = math.radians(solution.raw_angle)
    start_x = weapon.launch_point(rad)[0]
    d = solution.distance

    return [
        (x, weapon.flight_height(rad, x))
        for x in (start_x + (d - start_x) * i / points for i in range(points + 1))
    ]


# The profile this close to the muzzle is the weapon's own spot, and this
# close to the target the target's own spot (same as SquadCalc's coverage).
MUZZLE_CLEARANCE = 3.0
TARGET_CLEARANCE = 3.0

# Muzzle height used to check obstacles for weapons whose launch_height is 0
# (handheld and vehicle direct fire): the shoulder, like SquadCalc's coverage.
SHOULDER_HEIGHT = 1.5


def first_obstacle(weapon, solution, profile, step):
    """First point where a solved shot passes under the terrain profile.

    `profile` holds the heights of the terrain and the buildings every `step`
    metres from the weapon (index 0) towards the target, relative to the
    weapon's ground like `solution.height_diff` (SquadCalc's map, see
    maplink.MapTarget.profile). The path starts at the real muzzle,
    `launch_height` above the ground or SHOULDER_HEIGHT when that is 0, and is
    aimed from there at the target on the same arc. Returns (distance,
    height) of the obstacle in metres, or None when the path clears it, the
    shot is unsolved, or the target cannot be reached from that muzzle.
    """
    if not solution.reachable or not profile or not step:
        return None

    shot = solution

    if not weapon.launch_height:
        weapon = replace(weapon, launch_height=SHOULDER_HEIGHT)
        shot = solve(
            weapon, solution.distance, solution.height_diff, solution.arc
        )

        if not shot.reachable:
            return None

    rad = math.radians(shot.raw_angle)
    last = solution.distance - TARGET_CLEARANCE

    for i in range(math.ceil(MUZZLE_CLEARANCE / step), len(profile)):
        x = i * step

        if x > last:
            break

        if weapon.flight_height(rad, x) < profile[i]:
            return x, profile[i]

    return None


def height_at(weapon, angle, distance):
    """Height of the projectile when it is `distance` metres ahead of the
    pivot.

    `angle` is the elevation as returned by `solve` (angle_offset applied);
    the height is relative to the weapon's ground, like `height_diff`.
    Used for verification and tests.
    """
    return weapon.flight_height(math.radians(angle + weapon.angle_offset), distance)


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


# Range steps of the overlay's ladder (m): ranges are rounded up to the
# largest of these that is at most a quarter of the range, so every label
# is a round number and the ladder stays dense near the weapon.
LADDER_STEPS = (25, 50, 100, 200, 250, 500, 1000)

# A ladder longer than this is clutter (ticks, nearest first); no Squad
# map is wider than LADDER_MAX_DISTANCE (m) diagonally across its play area.
LADDER_MAX_TICKS = 24
LADDER_MAX_DISTANCE = 5000


# The most the field trim may add to or take off the barrel elevation (degrees).
TRIM_LIMIT = 5.0


def clamp_trim(trim):
    """`trim` limited to +-TRIM_LIMIT degrees."""
    return max(-TRIM_LIMIT, min(TRIM_LIMIT, trim))


def mark_offset(weapon, sight_angle, fov, screen_width, scale=1.0, trim=0.0):
    """Pixels below the screen centre to put the target on, for a shot
    `sight_angle` degrees over the line of sight (`Solution.sight_angle`)
    from the view `Weapon.sight_view` gives: the shot already leaves `bore`
    degrees above the centre, so the mark is that much higher.

    `trim` (degrees, limited to +-TRIM_LIMIT) is the player's field
    correction of the weapon, added to the barrel elevation: positive raises
    the barrel, so the shot goes farther and the mark moves down. It is an
    angle, so one value is right at every range.

    A view narrower than 1 degree (a small FOV through a strong sight) is
    held at 1 degree, the narrowest `screen_offset` takes; the mark is not
    exact then.
    """
    if not 1 <= fov <= 179:
        raise ValueError("FOV must be between 1 and 179 degrees")

    view_fov, bore = weapon.sight_view(fov)

    return screen_offset(
        sight_angle - bore + clamp_trim(trim),
        max(view_fov, 1.0),
        screen_width,
        scale
    )


def trim_for_landing(weapon, distance, height, landed, trim=0.0, arc="low"):
    """The trim that would have made a shot land at `distance`.

    The player fired at `distance` (with `height` metres between the weapon
    and the target ground, as in `solve`) on `arc` ("low", "high", or
    None/"auto" for the weapon's default) with `trim` set, and the shot
    landed at the horizontal distance `landed` on the same ground. The
    barrel was off by the difference between the elevations for the two
    ranges on that arc, so the new trim is
    `trim + elevation(distance) - elevation(landed)`, limited to
    +-TRIM_LIMIT. On the low arc it is positive when the shot landed short
    (the barrel needs more elevation); on the high arc more elevation
    shortens the shot, so it is negative then.

    A hold weapon's high arc (the AGS-17 lob) is laid by holding a key, not
    with the overlay mark, so its landing says nothing about the trim and
    is refused.

    Raises ValueError, with a message fit to show the player, when an
    input is not a finite number, the arc is unknown or a hold lob, the
    weapon is not aimed with the overlay or has no drop, or `distance` or
    `landed` cannot be reached on that arc.
    """
    if weapon.aim != "overlay":
        raise ValueError("This weapon is not aimed with the overlay mark")

    if weapon.g == 0:
        raise ValueError("This weapon has no drop, so there is nothing to trim")

    arc = resolve_arc(weapon, arc)

    if weapon.has_hold and arc == "high":
        raise ValueError(
            "The lob is laid by holding the key, not with the mark: "
            "set the trim from a direct-fire shot"
        )

    for value in (distance, height, landed, trim):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Enter numbers for the distance, height and landing")

    if distance <= 0:
        raise ValueError("Distance must be greater than 0")

    if landed <= 0:
        raise ValueError("Landed distance must be greater than 0")

    aimed = solve(weapon, distance, height, arc)

    if not aimed.reachable:
        raise ValueError(f"Distance: {aimed.reason}")

    hit = solve(weapon, landed, height, arc)

    if not hit.reachable:
        raise ValueError(f"Landed at: {hit.reason}")

    return clamp_trim(trim + aimed.angle - hit.angle)


def range_ladder(weapon, fov, screen_width, first, spacing, reach, scale=1.0,
                 trim=0.0):
    """Range ticks of the overlay ladder: where to put a target at each
    range on flat ground, as [(distance m, pixels below the centre)].

    The first tick is the nearest range at least `first` pixels below the
    centre (clear of the crosshair), each next one the nearest at least
    `spacing` pixels below the previous. Ranges are rounded up to a step
    of LADDER_STEPS that grows with the range (a quarter of it at most),
    so every label is a round number. The ladder ends where the weapon
    cannot reach, at `reach` pixels, after LADDER_MAX_TICKS or at
    LADDER_MAX_DISTANCE.
    The offsets are those of the overlay mark (`mark_offset` of the
    low-arc `Solution.sight_angle`, with the weapon's `trim`); ranges
    above the centre (inside the sight's zero) get no tick. Empty for
    weapons laid by elevation and for weapons without gravity (every range
    is on the centre).
    """
    if weapon.aim != "overlay" or weapon.g == 0:
        return []

    def offset_at(distance):
        solution = solve(weapon, distance, 0.0, "low")

        if not solution.reachable:
            return None

        return mark_offset(
            weapon, solution.sight_angle, fov, screen_width, scale, trim
        )

    ticks = []
    last_offset = 0.0
    distance = 0

    while len(ticks) < LADDER_MAX_TICKS:
        gap = first if not ticks else spacing

        # The nearest range that clears the previous tick
        while True:
            distance += LADDER_STEPS[0]

            if distance > LADDER_MAX_DISTANCE:
                return ticks

            if distance < weapon.min_distance:
                continue

            offset = offset_at(distance)

            if offset is None:
                return ticks

            if offset - last_offset >= gap:
                break

        step = max(
            (s for s in LADDER_STEPS if s <= distance / 4), default=LADDER_STEPS[0]
        )
        distance = -(-distance // step) * step
        offset = offset_at(distance)

        if offset is None or offset > reach or distance > LADDER_MAX_DISTANCE:
            return ticks

        ticks.append((distance, offset))
        last_offset = offset

    return ticks


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
