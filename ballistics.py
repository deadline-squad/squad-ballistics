"""Ballistic math for Squad Ballistics.

Pure functions only (no Qt), so everything here can be unit-tested.

Projectile model, the game's own (Squad build 26005357; the same model as
SquadCalc's squadBallistics.js). Addresses are in the Linux server binary
SquadGameServer (deadline-squad/squad-ballistics#4 has the evidence):

* no air drag; gravity is GRAVITY (DefaultGravityZ = -980 cm/s^2) times the
  projectile's gravity scale;
* the weapon spawns the projectile at the barrel socket `Attach_Muzzle` and
  sets its InitialSpeed to WeaponConfig.MuzzleVelocity (ASQWeapon spawn
  0xa750730, vtable slot 0x778 = 0xa7457e0); it leaves at `velocity` along
  the barrel. The barrel pivots `launch_height` above the ground; the muzzle
  is `muzzle_forward` along the barrel and `muzzle_up` above its axis, so the
  launch point moves with the elevation;
* the game moves the projectile in substeps (UProjectileMovementComponent::
  TickComponent 0x7cef0c0) of the frame time, at most 0.05 s
  (MaxSimulationTimeStep, constructor 0x7cee8d0). The dedicated server, whose
  projectile deals the damage, runs at 50 Hz (NetServerMaxTickRate of the
  RedpointEOSNetDriver), so a substep is SUBSTEP = 0.02 s. Per substep, with
  v the velocity and R the projectile's rotation:
      move   p += v dt + (V(R_before) - v) dt / 2   (Velocity Verlet)
      then   R = direction of v when `rotation_follows_velocity`
      then   v = V(R),   V(R) = clamp(v + (A(R) + g) dt) to `max_speed`
  (ComputeMoveDelta 0x7cf09e0, ComputeVelocity 0x7cf08a0 with GetMaxSpeed
  0x7d449c0). The move uses the rotation of the substep before: the thrust
  follows the velocity one substep late;
* A(R) is the rocket motor (USQProjectileMovement::ComputeAcceleration
  0xa747770): `acceleration` along the projectile's rotation for the first
  `acceleration_time` seconds (ConstantAccelerationTimeout; negative:
  the UB-32's rockets slow down). Every projectile turns with its velocity
  (the ASQProjectile constructor 0xa731b80 sets bRotationFollowsVelocity), so
  the motor pushes along the path, unless its Blueprint turns that off
  (`rotation_follows_velocity` false: the S-5 rocket keeps the barrel's
  axis);
* `max_speed` (MaxSpeed) caps the speed at every substep, also on the first
  one: a shell fired faster than its cap (SPG-9 HEAT 435 -> 330 m/s, tank HE
  1100 -> 800 or 850 m/s) is slowed to it at once, a motor holds a rocket at
  it, and a shell coming down faster than it is held there.

The phases that have a closed form are computed exactly: a motor along the
barrel's axis (two parabolas), the parabola of a coasting shell, and a shell
coasting at its cap (speed constant, the path angle gamma turns as
d gamma / dt = -g cos gamma / max_speed; continuous, which the 20 ms substeps
follow to 1e-5 of the turn). A motor along the path and a capped launch have
none: they are flown with the game's substeps above. The boost phase is
tabulated over the barrel elevation (`_BoostTable`) so that the root finding
stays fast; the game's path between two substeps is a straight segment, and so
is the model's.
"""

import json
import math
from dataclasses import dataclass, field, fields, replace
from functools import cached_property

# Squad's world gravity in m/s^2: DefaultGravityZ = -980 cm/s^2 in the game.
GRAVITY = 9.80

# The game's projectile substep on the dedicated server, seconds: one per
# frame of its 50 Hz tick (see the module docstring).
SUBSTEP = 0.02

# Barrel elevations between the nodes of a boost table, radians. Four-point
# Lagrange interpolation between them reproduces the stepped boost to 1e-6 m
# (to 4e-4 m near the substep where the M3 MAAWS reaches its cap).
BOOST_NODE_SPACING = math.radians(1.0)

# Squad mortars use the 6400 mil circle.
MILS_PER_DEGREE = 6400 / 360

ARCS = ("low", "high")
UNITS = ("deg", "mil")
AIMS = ("overlay", "elevation")

# The views of an RMB sight (`Weapon.view`); "" is a weapon without one.
VIEWS = ("", "optic", "plain")


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
    # The RMB sights that have a normal-view twin: the plain name used to be
    # the optic's, so it stays the optic's (a saved weapon keeps its meaning).
    "QLZ87": "QLZ87 · optic (RMB ×3)",
    "QLZ87 · Lynx / CSK131": "QLZ87 · Lynx / CSK131 · optic (RMB ×3)",
    "AGS-17 · emplacement": "AGS-17 · emplacement · optic (RMB ×2.5)",
    "SPG-9 · HEAT · scope": "SPG-9 · HEAT · scope · optic (RMB ×4)",
    "SPG-9 · FRAG · scope": "SPG-9 · FRAG · scope · optic (RMB ×4)",
    "ZiS-3": "ZiS-3 · optic (RMB ×4)",
}


def current_weapon_name(name):
    """The current weapons.json name of `name`, which may be a pre-rename one."""
    return RENAMED_WEAPONS.get(name, name)


def view_twin(weapons, name):
    """The name of the other view of the RMB sight `name` ("optic" <->
    "plain"), None for a weapon without one or a name not in `weapons`.

    Derived from the data: an "optic" entry names its `twin`, a "plain"
    entry is the twin of one "optic" entry (`_check_twins` guarantees it).
    """
    weapon = weapons.get(name)

    if weapon is None:
        return None

    if weapon.view == "optic":
        return weapon.twin

    if weapon.view == "plain":
        return next(other.name for other in weapons.values() if other.twin == name)

    return None


class WeaponDataError(ValueError):
    """Raised when weapons.json contains invalid data."""


@dataclass(frozen=True)
class Weapon:
    """One weapons.json entry: how a weapon fires and is aimed.

    The flight fields follow the game files (see the module docstring):
    `velocity` m/s, `gravity` (scale of GRAVITY), `acceleration` m/s^2 for
    `acceleration_time` s, `max_speed` m/s (0: no cap) and
    `rotation_follows_velocity`; the launch point `launch_height`,
    `muzzle_forward` and `muzzle_up` m. The aiming fields: `arc`, `aim`
    ("overlay" mark or "elevation"), `unit`, `angle_offset` (degrees the
    weapon's readout shows less than the barrel), `elevation_limits` and
    `min_distance`; the view the mark is drawn for, `bore` (degrees) and
    `zoom`; a barrel laid by holding a key, `hold_rate` (deg/s) and
    `hold_elevation`; `category` and `note` for the UI. An RMB sight that
    zooms the screen comes as two entries, `view` "optic" (through the
    sight, RMB held) and its `twin`, `view` "plain" (the normal view, RMB
    not held); the other weapons have no `view`. Build one with
    `from_dict`, which validates the data.
    """

    name: str
    velocity: float
    gravity: float = 1.0
    arc: str = "low"
    unit: str = "deg"
    aim: str = "overlay"
    angle_offset: float = 0.0
    acceleration: float = 0.0
    acceleration_time: float = 0.0
    max_speed: float = 0.0
    rotation_follows_velocity: bool = True
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
    view: str = ""
    twin: str = ""

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

        max_speed = number("max_speed", 0.0)
        follows = data.get("rotation_follows_velocity", True)

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
        if max_speed < 0:
            raise WeaponDataError(f"{name}: 'max_speed' must be >= 0 (0: none)")
        if not isinstance(follows, bool):
            raise WeaponDataError(
                f"{name}: 'rotation_follows_velocity' must be true or false"
            )
        if gravity == 0 and max_speed and velocity > max_speed:
            raise WeaponDataError(
                f"{name}: a projectile without gravity cannot start above "
                "'max_speed'"
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

        view = data.get("view", "")
        twin = data.get("twin", "")
        if view not in VIEWS:
            raise WeaponDataError(f"{name}: 'view' must be one of {VIEWS[1:]}")
        if view == "optic" and not zoom:
            raise WeaponDataError(f"{name}: an 'optic' view needs a 'zoom'")
        if view == "plain" and zoom:
            raise WeaponDataError(f"{name}: a 'plain' view has no 'zoom'")
        if not isinstance(twin, str) or bool(twin) != (view == "optic"):
            raise WeaponDataError(
                f"{name}: 'twin' (the plain view's name) goes with "
                "the 'optic' view, and only there"
            )

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
            max_speed=max_speed,
            rotation_follows_velocity=follows,
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
            view=view,
            twin=twin,
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
    def boost_steps(self):
        """Game substeps the motor acts in: those that start before
        `acceleration_time` (0 without boost)."""
        if not self.has_boost:
            return 0

        return math.ceil(self.acceleration_time / SUBSTEP - 1e-9)

    @property
    def _cap_binds_on_axis(self):
        """`max_speed` could clamp a motor along the barrel's axis: the
        speed of that flight is largest at launch or at the end of the
        boost (it is the length of an affine function of time), and at the
        end it is at most |velocity + a T| + g T."""
        if not self.max_speed:
            return False

        end = abs(self.velocity + self.acceleration * self.acceleration_time)

        return (
            self.velocity > self.max_speed
            or end + self.g * self.acceleration_time > self.max_speed
        )

    @property
    def flies_boost_in_steps(self):
        """The boost has no closed form and is flown with the game's
        substeps (`_BoostTable`): a motor that turns with the velocity, or
        one along the barrel that the cap could clamp. A flight without
        gravity is straight either way."""
        if not self.has_boost or self.g == 0:
            return False

        return self.rotation_follows_velocity or self._cap_binds_on_axis

    @property
    def _launch_clamped(self):
        """Fired faster than `max_speed` without a motor: the first substep
        slows the shell to its cap (tank HE)."""
        return (
            bool(self.max_speed)
            and self.velocity > self.max_speed
            and not self.has_boost
        )

    @property
    def _axis_boost_time(self):
        """Seconds the closed-form motor along the barrel speeds the
        projectile up: `acceleration_time`, ended earlier by the cap in a
        straight flight (no gravity: the NLAW reaches its 250 m/s in 0.6 s
        and is held there). 0 without boost."""
        if not self.has_boost:
            return 0.0

        if self.g == 0 and self.max_speed and self.acceleration > 0:
            to_cap = (self.max_speed - self.velocity) / self.acceleration
            return min(self.acceleration_time, max(0.0, to_cap))

        return self.acceleration_time

    @property
    def boost_distance(self):
        """Distance a straight (gravity-free) flight covers while the motor
        speeds it up (`_axis_boost_time`)."""
        t = self._axis_boost_time
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

    @property
    def cruise_velocity(self):
        """Speed along the barrel once the motor is done, in a straight
        (gravity-free) flight: velocity + acceleration * the boost time,
        held at `max_speed`."""
        speed = self.velocity + self.acceleration * self._axis_boost_time

        return min(speed, self.max_speed) if self.max_speed else speed

    def time_to(self, distance):
        """Time a straight (gravity-free) flight takes to cover `distance`
        metres along the barrel's axis."""
        if distance <= 0:
            return 0.0

        boost = self._axis_boost_time

        if not boost:
            return distance / self.velocity

        if distance <= self.boost_distance:
            return 2 * distance / (
                self.velocity
                + math.sqrt(
                    max(0.0, self.velocity ** 2 + 2 * self.acceleration * distance)
                )
            )

        return boost + (distance - self.boost_distance) / self.cruise_velocity

    def velocity_at(self, distance):
        """Average speed of a straight (gravity-free) flight over `distance`
        metres along the axis."""
        if distance <= 0 or not self._axis_boost_time:
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
        """The flight is one plain parabola from the pivot (no boost, no
        muzzle offset, not fired above its cap), as long as it does not
        come down faster than `max_speed` (`_clamps_before`)."""
        return not (
            self.has_boost or self.muzzle_forward or self.muzzle_up
            or self._launch_clamped
        )

    def _clamps_before(self, height):
        """A plain parabola from the pivot comes down faster than
        `max_speed` before it reaches a target `height` m above the
        weapon's ground: the speed there is sqrt(v^2 + 2 g drop), and the
        lowest point on the way to the target is the pivot or the target."""
        if not self.max_speed:
            return False

        drop = self.launch_height - height

        return self.velocity ** 2 + 2 * self.g * drop > self.max_speed ** 2

    @cached_property
    def _boost_table(self):
        """The `_BoostTable` of this weapon's flight (shared by every
        Weapon with the same projectile)."""
        key = (
            self.velocity, self.g, self.acceleration, self.acceleration_time,
            self.max_speed, self.rotation_follows_velocity,
        )
        table = _BOOST_TABLES.get(key)

        if table is None:
            table = _BOOST_TABLES[key] = _BoostTable(self)

        return table

    def _clamped_launch(self, cos, sin):
        """(x, y, vx, vy) after the first substep of a shell fired above its
        cap, relative to the muzzle: ComputeVelocity clamps v0 + g dt to
        `max_speed`, and the move is the average of the two velocities."""
        v0, cap = self.velocity, self.max_speed
        vx, vy = v0 * cos, v0 * sin - self.g * SUBSTEP
        scale = cap / math.hypot(vx, vy)
        vx, vy = vx * scale, vy * scale

        return (
            0.5 * (v0 * cos + vx) * SUBSTEP,
            0.5 * (v0 * sin + vy) * SUBSTEP,
            vx,
            vy,
        )

    def _coast_height(self, x, y, vx, vy, ahead):
        """Height at `ahead` m of a projectile coasting from (x, y) at
        (vx, vy), all relative to the muzzle: the parabola, and once it comes
        down faster than `max_speed` the capped coast (module docstring).
        Far past where the capped coast turns straight down (it never gets
        there) the height is a very large negative number."""
        g = self.g
        tau = (ahead - x) / vx
        cap = self.max_speed

        if cap and g:
            onset = max(0.0, (vy + math.sqrt(max(0.0, cap * cap - vx * vx))) / g)

            if tau > onset:
                y += onset * (vy - 0.5 * g * onset)
                radius = cap * cap / g
                cos_onset = min(1.0, vx / cap)
                turn = math.acos(cos_onset) + (ahead - x - vx * onset) / radius
                return y + radius * math.log(max(math.cos(turn), 1e-300) / cos_onset)

        return y + tau * (vy - 0.5 * g * tau)

    def _coast_at(self, x, y, vx, vy, t, ahead):
        """(height, time, path angle in radians) at `ahead` m of the coast
        `_coast_height` flies, started at time `t`."""
        g = self.g
        tau = (ahead - x) / vx
        cap = self.max_speed

        if cap and g:
            onset = max(0.0, (vy + math.sqrt(max(0.0, cap * cap - vx * vx))) / g)

            if tau > onset:
                y += onset * (vy - 0.5 * g * onset)
                radius = cap * cap / g
                cos_onset = min(1.0, vx / cap)
                turn = math.acos(cos_onset) + (ahead - x - vx * onset) / radius

                if turn >= math.pi / 2:
                    return -math.inf, math.inf, -math.pi / 2

                # t = (cap / g) (atanh sin gamma_onset - atanh sin gamma)
                since = (cap / g) * (
                    math.atanh(math.sin(turn))
                    - math.atanh(math.sqrt(max(0.0, 1 - cos_onset * cos_onset)))
                )
                return (
                    y + radius * math.log(math.cos(turn) / cos_onset),
                    t + onset + since,
                    -turn,
                )

        return (
            y + tau * (vy - 0.5 * g * tau),
            t + tau,
            math.atan2(vy - g * tau, vx),
        )

    def flight_height(self, rad, distance):
        """Height above the ground of the projectile when it is `distance`
        metres ahead of the pivot, fired at a barrel elevation of `rad`.

        The game's motion (module docstring): closed forms, and the stepped
        boost tabulated over the elevation. A distance behind the muzzle
        extrapolates the first phase backwards. `flight_at` gives the time
        and the path angle as well; this is the fast path of the searches.
        """
        cos, sin = math.cos(rad), math.sin(rad)
        start_x, start_y = self.launch_point(rad)
        ahead = distance - start_x
        v0, g = self.velocity, self.g

        if self.flies_boost_in_steps:
            table = self._boost_table
            weights, nodes = table.stencil(rad)
            x, y, vx, vy = table.end(weights, nodes)

            if ahead < x:
                _, (xa, ya), (xb, yb) = table.segment(weights, nodes, ahead)
                return start_y + ya + (yb - ya) * (ahead - xa) / (xb - xa)

            return start_y + self._coast_height(x, y, vx, vy, ahead)

        if self.has_boost:
            a, boost = self.acceleration, self._axis_boost_time
            length = v0 * boost + 0.5 * a * boost * boost

            if ahead <= cos * length:
                along = ahead / cos
                t = 2 * along / (v0 + math.sqrt(max(0.0, v0 * v0 + 2 * a * along)))
                return start_y + sin * along - 0.5 * g * t * t

            end_speed = v0 + a * boost
            return start_y + self._coast_height(
                cos * length, sin * length - 0.5 * g * boost * boost,
                cos * end_speed, sin * end_speed - g * boost, ahead,
            )

        if self._launch_clamped:
            x, y, vx, vy = self._clamped_launch(cos, sin)

            if ahead < x:
                return start_y + y * ahead / x

            return start_y + self._coast_height(x, y, vx, vy, ahead)

        return start_y + self._coast_height(0.0, 0.0, v0 * cos, v0 * sin, ahead)

    def flight_at(self, rad, distance):
        """(height, time, path angle) of the projectile when it is
        `distance` metres ahead of the pivot, fired at a barrel elevation of
        `rad`: metres above the ground, seconds after launch, radians above
        the horizontal (negative: coming down). Inside a substep the path is
        the game's straight segment. Time and angle are 0 behind the muzzle;
        a point the capped coast never reaches is (-inf, inf, -pi/2).
        """
        cos, sin = math.cos(rad), math.sin(rad)
        start_x, start_y = self.launch_point(rad)
        ahead = distance - start_x
        v0, g = self.velocity, self.g

        if self.flies_boost_in_steps:
            table = self._boost_table
            weights, nodes = table.stencil(rad)
            x, y, vx, vy = table.end(weights, nodes)

            if ahead < x:
                step, (xa, ya), (xb, yb) = table.segment(weights, nodes, ahead)
                part = (ahead - xa) / (xb - xa)
                return (
                    start_y + ya + (yb - ya) * part,
                    max(0.0, (step + part) * SUBSTEP),
                    math.atan2(yb - ya, xb - xa),
                )

            height, t, angle = self._coast_at(
                x, y, vx, vy, table.steps * SUBSTEP, ahead
            )
            return start_y + height, t, angle

        if self.has_boost:
            a, boost = self.acceleration, self._axis_boost_time
            length = v0 * boost + 0.5 * a * boost * boost

            if ahead <= cos * length:
                along = ahead / cos
                t = 2 * along / (v0 + math.sqrt(max(0.0, v0 * v0 + 2 * a * along)))
                speed = v0 + a * t
                return (
                    start_y + sin * along - 0.5 * g * t * t,
                    max(0.0, t),
                    math.atan2(sin * speed - g * t, cos * speed),
                )

            end_speed = v0 + a * boost
            height, t, angle = self._coast_at(
                cos * length, sin * length - 0.5 * g * boost * boost,
                cos * end_speed, sin * end_speed - g * boost, boost, ahead,
            )
            return start_y + height, t, angle

        if self._launch_clamped:
            x, y, vx, vy = self._clamped_launch(cos, sin)

            if ahead < x:
                return (
                    start_y + y * ahead / x,
                    max(0.0, SUBSTEP * ahead / x),
                    math.atan2(y, x),
                )

            height, t, angle = self._coast_at(x, y, vx, vy, SUBSTEP, ahead)
            return start_y + height, t, angle

        height, t, angle = self._coast_at(
            0.0, 0.0, v0 * cos, v0 * sin, 0.0, ahead
        )
        return start_y + height, max(0.0, t), angle

    def flight_time(self, rad, distance):
        """Seconds after launch when the projectile is `distance` metres
        ahead of the pivot, fired at a barrel elevation of `rad`."""
        return self.flight_at(rad, distance)[1]

    def apex_height(self, rad, distance):
        """Highest height above the ground the projectile passes before it
        is `distance` metres ahead of the pivot, fired at a barrel elevation
        of `rad` (-inf if it only comes down after the muzzle). The capped
        coast only comes down, so the top is in the boost or on the
        parabola after it."""
        cos, sin = math.cos(rad), math.sin(rad)
        start_x, start_y = self.launch_point(rad)
        ahead = distance - start_x
        v0, g = self.velocity, self.g
        top = -math.inf

        if self.flies_boost_in_steps:
            table = self._boost_table
            weights, nodes = table.stencil(rad)
            for x, y in table.points(weights, nodes):
                if x > ahead:
                    break
                top = max(top, y)
            x, y, vx, vy = table.end(weights, nodes)
        elif self.has_boost:
            a, boost = self.acceleration, self._axis_boost_time
            length = v0 * boost + 0.5 * a * boost * boost
            # Vertical speed sin (v0 + a t) - g t is zero once, on the way up.
            denominator = g - sin * a
            if denominator > 0:
                rising = sin * v0 / denominator
                if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead:
                    top = sin * (v0 * rising + 0.5 * a * rising ** 2) - 0.5 * g * rising ** 2
            end_speed = v0 + a * boost
            x, y = cos * length, sin * length - 0.5 * g * boost * boost
            vx, vy = cos * end_speed, sin * end_speed - g * boost
        elif self._launch_clamped:
            x, y, vx, vy = self._clamped_launch(cos, sin)
        else:
            x, y, vx, vy = 0.0, 0.0, v0 * cos, v0 * sin

        if vy > 0 and g and x + vx * vy / g <= ahead:
            top = max(top, y + vy * vy / (2 * g))

        return start_y + top

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

        if self.is_parabola and not self._clamps_before(height):
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
        return self._max_range[0]

    @cached_property
    def _max_range(self):
        """(maximum range on flat ground, the elevation in radians that
        reaches it; inf and NaN without gravity), computed once: the
        largest distance whose highest shot (`peak_elevation`) still comes
        down to the ground there, by doubling and then bisection to 1 mm."""
        if self.g == 0:
            return math.inf, math.nan

        if self.is_parabola and not self.launch_height:
            return self.velocity ** 2 / self.g, math.pi / 4

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

        return low, self.peak_elevation(low)

    def flat_low_elevation(self, distance):
        """Low-arc barrel elevation (radians) that lands on flat ground
        `distance` metres away, NaN beyond `max_range`: `elevations_to`
        for a target at the pivot's ground, without its search for the
        highest shot. The shot that reaches the maximum range passes above
        the ground at every shorter distance, so its elevation bounds the
        low root from above. The range ladder solves dozens of ranges in a
        row; this keeps it fast."""
        if self.is_parabola and not self._clamps_before(0.0):
            return self.elevations_to(distance, 0.0)[0]

        longest, top = self._max_range

        if distance > longest:
            return math.nan

        def error(rad):
            return self.flight_height(rad, distance)

        if error(top) < 0:
            return math.nan

        return _find_root(error, top, -1)


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


def _fly_boost(weapon, rad):
    """The boost of `weapon` fired at `rad` radians, flown with the game's
    substeps (module docstring) from the muzzle: ([(x, y)] at the start of
    every substep and at the end, end velocity (vx, vy)), metres and m/s
    relative to the muzzle."""
    dt, g, a, cap = SUBSTEP, weapon.g, weapon.acceleration, weapon.max_speed
    cap_squared = cap * cap
    follows = weapon.rotation_follows_velocity
    cos, sin = math.cos(rad), math.sin(rad)
    vx, vy = weapon.velocity * cos, weapon.velocity * sin
    # The projectile's rotation: the barrel's at spawn.
    ax, ay = a * cos, a * sin
    x = y = 0.0
    points = [(0.0, 0.0)]

    for _ in range(weapon.boost_steps):
        # Move: the velocity this substep would end with, under the
        # rotation of the substep before.
        mx, my = vx + ax * dt, vy + (ay - g) * dt
        if cap:
            speed_squared = mx * mx + my * my
            if speed_squared > cap_squared:
                scale = cap / math.sqrt(speed_squared)
                mx, my = mx * scale, my * scale
        x += 0.5 * (vx + mx) * dt
        y += 0.5 * (vy + my) * dt

        if follows:
            speed = math.hypot(vx, vy)
            ax, ay = a * vx / speed, a * vy / speed

        vx, vy = vx + ax * dt, vy + (ay - g) * dt
        if cap:
            speed_squared = vx * vx + vy * vy
            if speed_squared > cap_squared:
                scale = cap / math.sqrt(speed_squared)
                vx, vy = vx * scale, vy * scale

        points.append((x, y))

    return points, (vx, vy)


class _BoostTable:
    """A stepped boost (`Weapon.flies_boost_in_steps`) tabulated over the
    barrel elevation: nodes every BOOST_NODE_SPACING from -90 to +90
    degrees, each flown by `_fly_boost` the first time it is needed, and
    four-point Lagrange interpolation between them. The searches evaluate
    the flight thousands of times per solution; a node costs a whole
    boost, an interpolated point a few multiplications."""

    def __init__(self, weapon):
        self.weapon = weapon
        self.steps = weapon.boost_steps
        self.count = round(math.pi / BOOST_NODE_SPACING) + 1
        self.nodes = [None] * self.count

    def node(self, index):
        """(xs, ys, vx, vy) of node `index`: the substep points and the
        end velocity at elevation -90 deg + index * spacing."""
        node = self.nodes[index]

        if node is None:
            points, (vx, vy) = _fly_boost(
                self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING
            )
            node = self.nodes[index] = (
                tuple(p[0] for p in points), tuple(p[1] for p in points), vx, vy
            )

        return node

    def stencil(self, rad):
        """(weights, nodes) of the four nodes that interpolate `rad`: the
        two on each side, shifted inwards at the ends of the table."""
        at = (rad + math.pi / 2) / BOOST_NODE_SPACING
        first = min(max(int(at) - 1, 0), self.count - 4)
        u = at - first
        weights = (
            -(u - 1) * (u - 2) * (u - 3) / 6,
            u * (u - 2) * (u - 3) / 2,
            -u * (u - 1) * (u - 3) / 2,
            u * (u - 1) * (u - 2) / 6,
        )

        return weights, tuple(self.node(first + i) for i in range(4))

    def end(self, weights, nodes):
        """(x, y, vx, vy) at the end of the boost."""
        w0, w1, w2, w3 = weights
        n0, n1, n2, n3 = nodes

        return (
            w0 * n0[0][-1] + w1 * n1[0][-1] + w2 * n2[0][-1] + w3 * n3[0][-1],
            w0 * n0[1][-1] + w1 * n1[1][-1] + w2 * n2[1][-1] + w3 * n3[1][-1],
            w0 * n0[2] + w1 * n1[2] + w2 * n2[2] + w3 * n3[2],
            w0 * n0[3] + w1 * n1[3] + w2 * n2[3] + w3 * n3[3],
        )

    def segment(self, weights, nodes, ahead):
        """(k, start, end) of the substep whose straight segment holds the
        distance `ahead` from the muzzle (the first one for a distance
        behind the muzzle, the last one at its end): binary search on the
        interpolated x of the substep points."""
        w0, w1, w2, w3 = weights
        (x0, y0, _, _), (x1, y1, _, _), (x2, y2, _, _), (x3, y3, _, _) = nodes
        low, high = 0, self.steps

        while high - low > 1:
            mid = (low + high) // 2
            if w0 * x0[mid] + w1 * x1[mid] + w2 * x2[mid] + w3 * x3[mid] <= ahead:
                low = mid
            else:
                high = mid

        def point(k):
            return (
                w0 * x0[k] + w1 * x1[k] + w2 * x2[k] + w3 * x3[k],
                w0 * y0[k] + w1 * y1[k] + w2 * y2[k] + w3 * y3[k],
            )

        return low, point(low), point(low + 1)

    def points(self, weights, nodes):
        """The interpolated substep points (x, y), from the muzzle on."""
        w0, w1, w2, w3 = weights
        (x0, y0, _, _), (x1, y1, _, _), (x2, y2, _, _), (x3, y3, _, _) = nodes

        for k in range(self.steps + 1):
            yield (
                w0 * x0[k] + w1 * x1[k] + w2 * x2[k] + w3 * x3[k],
                w0 * y0[k] + w1 * y1[k] + w2 * y2[k] + w3 * y3[k],
            )


# Boost tables by flight parameters, shared by the Weapons that fly alike
# (renamed copies, `dataclasses.replace` for another launch height).
_BOOST_TABLES = {}


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
    """A firing solution from `solve`: whether the target can be hit on the
    requested arc, the elevation and what it takes to get there (sight angle,
    mils, flight time, apex, impact angle, hold time), or why it cannot
    (`reason_code`: "too_close", "out_of_range", "elevation_limit" or
    "hold_limit", and a readable `reason`). `alternatives` maps the arcs that
    can be fired to their elevation in degrees."""

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
    """The arc to solve for: `arc` ("low" or "high"), or the weapon's own
    arc for None, "" or "auto". Raises ValueError for any other value."""
    if arc in (None, "", "auto"):
        return weapon.arc
    if arc not in ARCS:
        raise ValueError(f"Unknown arc '{arc}'")
    return arc


def solve(weapon, distance, height_diff=0.0, arc=None, aim_lift=0.0):
    """Elevation needed to hit a target.

    distance     -- horizontal distance to the target in metres, from the
                    barrel's pivot
    height_diff  -- target ground height relative to the weapon ground
                    (positive = higher); the pivot is `launch_height` above
    arc          -- "low", "high" or None/"auto" for the weapon default
    aim_lift     -- metres above the target ground the shot is aimed at (a
                    vehicle's hull, a standing soldier), 0 = the ground. The
                    elevation is that of the lifted point, but `sight_angle`
                    stays measured over the line of sight to the GROUND, the
                    point the player can see (the map marker sits on it), so
                    the overlay mark of a lifted aim sits lower

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
    aim_height = height_diff + aim_lift
    aim_rise = aim_height - weapon.launch_height

    if weapon.g == 0:
        # No gravity: the projectile flies straight along the line of sight.
        result.velocity = weapon.velocity_at(math.hypot(distance, aim_rise))
        rad = math.atan2(aim_rise, distance)
        raw = {"low": rad, "high": rad}
    else:
        low_rad, high_rad = weapon.elevations_to(distance, aim_height)

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

    _, flight, impact = weapon.flight_at(rad, distance)
    start_x, start_y = weapon.launch_point(rad)

    result.time_of_flight = flight
    # Average speed along the barrel's direction to the target.
    result.velocity = (distance - start_x) / (math.cos(rad) * flight)
    result.impact_angle = -math.degrees(impact)
    result.apex = max(
        start_y, aim_height, weapon.apex_height(rad, distance)
    )

    return result


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


# A shell must land within about this many metres of the aim point to do its
# work: a grenade burst's lethal radius is 1.5-3 m and the research on
# marker aiming (deadline-squad/squad-ballistics#6) counts a hit inside 5 m.
# A pixel of the mark worth more than this cannot hit it.
MARK_PIXEL_LIMIT = 5.0


def _mark_at(weapon, distance, height, fov, screen_width, scale, trim, arc,
             aim_lift):
    """Pixels below the centre of the mark for a target at `distance` and
    `height`, None when the target cannot be hit on `arc`."""
    solution = solve(weapon, distance, height, arc, aim_lift)

    if not solution.reachable:
        return None

    return mark_offset(
        weapon, solution.sight_angle, fov, screen_width, scale, trim
    )


def mark_resolution(weapon, distance, height, fov, screen_width, scale=1.0,
                    trim=0.0, arc="low", aim_lift=0.0):
    """Metres of range one pixel of the mark is worth for a target at
    `distance` and `height`, the same inputs `mark_offset` and `solve` take
    (`arc` is the one the mark is laid for, `aim_lift` as in `solve`).

    How far the shell lands from the target when the player lays the target
    one pixel off the mark: the elevations that land the shell 1 m either
    side (one side at the edge of what the weapon reaches) are put on the
    screen over the line of sight to the target itself, which does not move
    with them. None for a weapon without a mark or without drop, or where the
    target cannot be hit or the mark does not move with the range.
    """
    if weapon.aim != "overlay" or weapon.g == 0:
        return None

    centre = solve(weapon, distance, height, arc, aim_lift)

    if not centre.reachable:
        return None

    # What the sight angle is measured from: the line of sight to the target
    line_of_sight = centre.angle - centre.sight_angle
    points = []

    for at in (distance - 1.0, distance, distance + 1.0):
        if at <= 0:
            continue

        solution = solve(weapon, at, height, arc, aim_lift)

        if solution.reachable:
            points.append((at, mark_offset(
                weapon, solution.angle - line_of_sight, fov, screen_width,
                scale, trim
            )))

    if len(points) < 2:
        return None

    (near, near_offset), (far, far_offset) = points[0], points[-1]
    slope = (far_offset - near_offset) / (far - near)

    if not slope > 0 or not math.isfinite(slope):
        return None

    return 1.0 / slope


def mark_visible_range(weapon, height, fov, screen_width, top, bottom,
                       scale=1.0, trim=0.0, arc="low", aim_lift=0.0):
    """(nearest, farthest) range in metres whose mark lies between `top`
    and `bottom` pixels below the centre (`top` is negative above it), for
    targets `height` metres above the weapon's ground. A side is None when
    the weapon's whole range is inside it; the farthest is 0.0 when even the
    closest target the weapon can take has its mark below `bottom`. (None, None) for a weapon
    without a mark or without drop.

    The mark moves down as the range grows (the low arc), so each side is
    found by bisection. A range the weapon cannot hit counts as beyond the
    farthest.
    """
    if weapon.aim != "overlay" or weapon.g == 0:
        return None, None

    highest = min(weapon.max_range(), LADDER_MAX_DISTANCE)

    def offset_at(distance):
        return _mark_at(
            weapon, distance, height, fov, screen_width, scale, trim, arc, aim_lift
        )

    # The closest range the weapon can take on this arc: the low arc of a
    # lobbing weapon is out of its elevation limits at a few metres
    lowest = next(
        (
            distance
            for distance in (max(weapon.min_distance, 1.0), *LADDER_STEPS)
            if distance >= weapon.min_distance and offset_at(distance) is not None
        ),
        None
    )

    if lowest is None:
        return None, None

    def bisect(low, high, inside):
        """The edge between `low` (inside) and `high` (outside), to 1 cm."""
        while high - low > 0.01:
            middle = (low + high) / 2

            if inside(middle):
                low = middle
            else:
                high = middle

        return (low + high) / 2

    def above_bottom(distance):
        offset = offset_at(distance)

        return offset is not None and offset <= bottom

    def above_top(distance):
        offset = offset_at(distance)

        return offset is not None and offset < top

    if above_bottom(highest):
        farthest = None
    elif above_bottom(lowest):
        farthest = bisect(lowest, highest, above_bottom)

        # The mark did not leave the screen when the weapon's reach ended
        if offset_at(farthest + 0.05) is None:
            farthest = None
    else:
        farthest = 0.0

    nearest = None

    if above_top(lowest):
        nearest = bisect(lowest, highest, above_top)

    return nearest, farthest


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

    low_limit, high_limit = weapon.elevation_limits

    def offset_at(distance):
        # solve(weapon, distance, 0.0, "low").sight_angle, unless it is
        # unreachable or beyond the elevation limits (flat_low_elevation)
        rad = weapon.flat_low_elevation(distance)
        angle = math.degrees(rad) - weapon.angle_offset

        if not low_limit <= angle <= high_limit:
            return None

        rise = -weapon.launch_height
        sight_angle = angle - math.degrees(math.atan2(rise, distance))

        return mark_offset(
            weapon, sight_angle, fov, screen_width, scale, trim
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
    """{name: Weapon} from the parsed weapons.json object `raw`, in its
    order, skipping the keys that start with "_" (comments). Raises
    WeaponDataError when `raw` is not an object, defines no weapon or has an
    invalid entry (`Weapon.from_dict`)."""
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

    _check_twins(weapons)

    return weapons


def _check_twins(weapons):
    """Raise WeaponDataError unless every "optic" entry names a "plain"
    entry as its twin and every "plain" entry is the twin of one."""
    twins = [weapon.twin for weapon in weapons.values() if weapon.view == "optic"]

    for weapon in weapons.values():
        if weapon.view == "optic" and (
            weapon.twin not in weapons or weapons[weapon.twin].view != "plain"
        ):
            raise WeaponDataError(
                f"{weapon.name}: its 'twin' {weapon.twin!r} is not a 'plain' entry"
            )

        if weapon.view == "plain" and twins.count(weapon.name) != 1:
            raise WeaponDataError(
                f"{weapon.name}: a 'plain' entry must be the 'twin' of one 'optic' entry"
            )
