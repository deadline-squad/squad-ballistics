"""Independent oracle for the end-to-end proof of the aim-by-mark system.

Nothing here imports ballistics.py or any other module of the app: it reads
raw weapons.json entries (plain dicts) and applies the game's rules as written
down in the decompiled server (Squad build 26005357, USQProjectileMovement):

* gravity = ProjectileGravityScale * 9.80 m/s^2 (DefaultGravityZ = -980 cm/s^2),
  no drag;
* the projectile starts at the barrel socket `Attach_Muzzle`: `muzzle_forward`
  along the barrel and `muzzle_up` above its axis, the barrel pivoting
  `launch_height` above the ground, at `velocity` along the barrel;
* ConstantAcceleration, rotated by the projectile's rotation, which stays the
  barrel's at launch (bRotationFollowsVelocity is off for every boosted
  projectile), acts for ConstantAccelerationTimeout seconds or until MaxSpeed;
  weapons.json stores the shorter of the two as `acceleration_time`;
* the camera is rectilinear with the horizontal FOV, so a point `p` pixels
  below the centre of an image `W` pixels wide is
  atan(p / ((W / 2) / tan(fov / 2))) below the view axis; the shot leaves
  `bore` degrees above that axis and the weapon's sight divides the FOV by
  its zoom.

The flight is integrated with classical Runge-Kutta 4 at a 1 ms step (the
acceleration is piecewise constant, so RK4 is exact between the switch at the
end of the boost, which the steps land on; the tests also check the result is
the same at a 0.25 ms step).
"""

import math

GRAVITY_Z = 9.80

STEP = 0.001


class Shot:
    """How a weapon fires, from its raw weapons.json entry."""

    def __init__(self, entry):
        self.velocity = float(entry["velocity"])
        self.gravity = GRAVITY_Z * float(entry.get("gravity", 1.0))
        self.acceleration = float(entry.get("acceleration", 0.0))
        self.boost_time = float(entry.get("acceleration_time", 0.0))
        self.pivot_height = float(entry.get("launch_height", 0.0))
        self.muzzle_forward = float(entry.get("muzzle_forward", 0.0))
        self.muzzle_up = float(entry.get("muzzle_up", 0.0))

    def muzzle(self, elevation):
        """(x, y) of the muzzle relative to the pivot's ground point."""
        c, s = math.cos(elevation), math.sin(elevation)

        return (
            self.muzzle_forward * c - self.muzzle_up * s,
            self.pivot_height + self.muzzle_forward * s + self.muzzle_up * c,
        )


def view(entry):
    """(zoom, bore in degrees) of the view a raw entry is aimed through: the
    sight's own magnification (`zoom`, the FOV divisor; absent = 1) and the
    degrees above the view axis the shot leaves (`bore`)."""
    return float(entry.get("zoom", 1.0)), float(entry.get("bore", 0.0))


def focal_length(width, fov, zoom=1.0):
    """Focal length in pixels of a view `width` pixels wide whose game FOV
    setting is `fov` degrees (horizontal), divided by the optic's `zoom`."""
    return (width / 2) / math.tan(math.radians(max(fov / zoom, 1.0)) / 2)


def pitch_of_pixel(pixels_below_centre, width, fov, zoom=1.0):
    """How far (radians) below the view axis a point `pixels_below_centre`
    pixels under the image centre is."""
    return math.atan(pixels_below_centre / focal_length(width, fov, zoom))


def barrel_elevation(entry, view, fov, width, pixels_below_centre, distance,
                     height, scale=1.0):
    """Elevation (radians) of the barrel when the player lays the target at
    `distance` m and `height` m (above the weapon's ground) on a mark
    `pixels_below_centre` below the screen centre, in `view` = (zoom, bore).

    `scale` is the overlay's calibration: it multiplies the offset below the
    centre, so the pixels to convert are the drawn ones divided by it. The
    eye is taken at the barrel's pivot. The target is seen
    atan2(height - pivot, distance) above the horizon and the mark pitch
    below the view axis, so the view axis is at the sum; the barrel is `bore`
    above the axis.
    """
    zoom, bore = view
    below = pitch_of_pixel(pixels_below_centre / scale, width, fov, zoom)
    line_of_sight = math.atan2(height - float(entry.get("launch_height", 0.0)), distance)

    return line_of_sight + below + math.radians(bore)


def _rk4(x, y, vx, vy, ax, ay, h):
    """One classical Runge-Kutta 4 step of the motion
    d(x, y)/dt = (vx, vy), d(vx, vy)/dt = (ax, ay).

    The acceleration depends on neither the state nor the time inside the
    step (the caller never lets a step straddle the end of the boost), so the
    four stages differ only in the velocity they sample.
    """
    k1x, k1y = vx, vy
    k2x, k2y = vx + ax * h / 2, vy + ay * h / 2
    k3x, k3y = vx + ax * h / 2, vy + ay * h / 2
    k4x, k4y = vx + ax * h, vy + ay * h

    return (
        x + h / 6 * (k1x + 2 * k2x + 2 * k3x + k4x),
        y + h / 6 * (k1y + 2 * k2y + 2 * k3y + k4y),
        vx + ax * h,
        vy + ay * h,
    )


class _Flight:
    """A shot being integrated: its state and the acceleration that applies
    to the next step."""

    def __init__(self, shot, elevation):
        self.shot = shot
        c, s = math.cos(elevation), math.sin(elevation)
        self.boost = (shot.acceleration * c, shot.acceleration * s - shot.gravity)
        self.coast = (0.0, -shot.gravity)
        self.x, self.y = shot.muzzle(elevation)
        self.vx, self.vy = shot.velocity * c, shot.velocity * s
        self.t = 0.0

    def acceleration(self, h):
        """Acceleration over the next step of length `h`: boosting while the
        step lies before the end of the boost."""
        if self.t + h / 2 < self.shot.boost_time:
            return self.boost
        return self.coast

    def step_length(self, h):
        """`h`, shortened so that a step ends exactly at the end of the boost."""
        end = self.shot.boost_time
        if self.t < end < self.t + h * (1 - 1e-9):
            return end - self.t
        return h

    def advance(self, h):
        ax, ay = self.acceleration(h)
        self.x, self.y, self.vx, self.vy = _rk4(
            self.x, self.y, self.vx, self.vy, ax, ay, h
        )
        self.t += h


def fly_to(shot, elevation, distance, step=STEP):
    """Integrate a shot fired at barrel `elevation` (radians) until it is
    `distance` m ahead of the pivot.

    Returns (height, slope, curvature, time): the height above the ground,
    dy/dx, d2y/dx2 there and the flight time, or None when it never gets
    there (it lands first, or the speed is exhausted).
    """
    flight = _Flight(shot, elevation)

    while flight.x < distance:
        h = flight.step_length(step)
        ax, ay = flight.acceleration(h)
        x, y, vx, vy = _rk4(flight.x, flight.y, flight.vx, flight.vy, ax, ay, h)

        if x >= distance:
            # Bisect the last step down to the distance.
            low, high = 0.0, h
            for _ in range(60):
                mid = (low + high) / 2
                reached = _rk4(
                    flight.x, flight.y, flight.vx, flight.vy, ax, ay, mid
                )[0]
                if reached < distance:
                    low = mid
                else:
                    high = mid
            flight.advance((low + high) / 2)
            break

        flight.x, flight.y, flight.vx, flight.vy = x, y, vx, vy
        flight.t += h

        if flight.y < -1e5 or flight.t > 600:
            return None

    ax, ay = flight.acceleration(0.0)
    slope = flight.vy / flight.vx

    return (
        flight.y,
        slope,
        (ay - slope * ax) / (flight.vx * flight.vx),
        flight.t,
    )


class Miss:
    """How far a shot passes from a target point on the ground.

    `distance` is the shortest distance in the vertical plane between the
    target point and the path (first order in the miss: the vertical error
    times cos of the path's slope angle): the miss a target of any size
    sees. `vertical` is the path's height minus the target's at the target's
    horizontal distance. `ground` is how far along the ground the path meets
    the ground from there (nearest root of the local parabola, exact to the
    second order); it blows up for a flat path, where a tiny vertical error
    moves the ground hit by metres.
    """

    def __init__(self, distance, vertical, ground):
        self.distance = distance
        self.vertical = vertical
        self.ground = ground

    def __repr__(self):
        return (f"Miss(distance={self.distance:.4g}, vertical={self.vertical:.4g},"
                f" ground={self.ground:.4g})")


def miss(shot, elevation, distance, height, step=STEP):
    """The Miss of a shot at barrel `elevation` (radians) against the
    ground `height` m above the weapon's, `distance` m away; infinite when
    the shot never gets there."""
    flight = fly_to(shot, elevation, distance, step)

    if flight is None:
        return Miss(math.inf, math.inf, math.inf)

    y, slope, curvature, _ = flight
    error = y - height
    closest = abs(error) / math.sqrt(1 + slope * slope)

    # error + slope * dx + curvature / 2 * dx^2 = 0, nearest root to dx = 0
    if abs(curvature) < 1e-15:
        ground = abs(error / slope) if slope else math.inf
    else:
        discriminant = slope * slope - 2 * curvature * error
        if discriminant < 0:
            ground = math.inf
        else:
            ground = min(
                abs((-slope + sign * math.sqrt(discriminant)) / curvature)
                for sign in (-1, 1)
            )

    return Miss(closest, error, ground)


def range_at(shot, elevation, height, step=STEP, limit=200000.0):
    """Horizontal distance at which the path first comes down to `height`
    after its apex, found by integrating until it does (flat-ground range).
    Used for the largest range of a weapon and for the range one pixel of
    elevation is worth."""
    flight = _Flight(shot, elevation)

    while flight.vy > 0 or flight.y > height:
        x, y = flight.x, flight.y
        flight.advance(flight.step_length(step))

        if flight.y <= height and flight.vy < 0:
            # Linear interpolation inside the last (1 ms) step.
            fraction = (y - height) / (y - flight.y)
            return x + fraction * (flight.x - x)

        if flight.x > limit or flight.t > 600:
            return math.inf

    return flight.x


def highest_at(shot, distance, reaches=math.inf, step=STEP):
    """The greatest height the shot can have when it is `distance` m ahead of
    the pivot, over every barrel elevation: the height is unimodal in the
    elevation, so a golden-section search finds it (to 1e-5 rad, which is
    far below a millimetre of height). -inf if it never gets there. The
    search stops early as soon as a height of at least `reaches` is found."""
    golden = (math.sqrt(5) - 1) / 2

    def height(elevation):
        flight = fly_to(shot, elevation, distance, step)
        return -math.inf if flight is None else flight[0]

    low, high = math.radians(-5.0), math.radians(89.9)
    left = high - golden * (high - low)
    right = low + golden * (high - low)
    left_height, right_height = height(left), height(right)

    while high - low > 1e-5 and max(left_height, right_height) < reaches:
        if left_height < right_height:
            low, left, left_height = left, right, right_height
            right = low + golden * (high - low)
            right_height = height(right)
        else:
            high, right, right_height = right, left, left_height
            left = high - golden * (high - low)
            left_height = height(left)

    return max(left_height, right_height)
