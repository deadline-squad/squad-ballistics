"""Independent oracle for the end-to-end proof of the aim-by-mark system.

Nothing here imports ballistics.py or any other module of the app. The flight
values come from tests/data/game_weapons.json, the snapshot
tools/game_weapons.py writes from the game files (not from weapons.json); the
launch geometry (pivot height, muzzle offset) from the raw weapons.json entry.
The flight is the game's own integration, written down from the decompiled
server (Squad build 26005357), step by step as the game takes them, not
solved in closed form:

* the dedicated server ticks at 50 Hz (NetServerMaxTickRate of its
  RedpointEOSNetDriver) and the projectile moves once per tick: substeps of
  SUBSTEP = 0.02 s (UProjectileMovementComponent::TickComponent 0x7cef0c0;
  its MaxSimulationTimeStep 0.05 s is never reached);
* each substep (ComputeMoveDelta 0x7cf09e0, ComputeVelocity 0x7cf08a0): the
  move is v dt + (V - v) dt / 2, V the velocity the substep ends with under
  the projectile's rotation from the substep before; then the rotation turns
  to the old velocity's direction when bRotationFollowsVelocity is set
  (ASQProjectile's constructor sets it, 0xa731eb8; the UB-32's S-5 clears
  it); then the velocity becomes V under the new rotation;
* V = v + (A + gravity) dt, clamped to MaxSpeed (every substep, the first one
  too; 0 = no cap). gravity = ProjectileGravityScale * 9.80 m/s^2
  (DefaultGravityZ = -980 cm/s^2), no drag. A
  (USQProjectileMovement::ComputeAcceleration 0xa747770) is
  ConstantAcceleration along the projectile's rotation while the time since
  spawn, counted at the start of the substep, is under
  ConstantAccelerationTimeout (0: the whole flight); gravity is left out while
  A acts when bIgnoreGravityDuringConstantAcceleration is set (NLAW);
* the projectile starts at the barrel socket `Attach_Muzzle`, `muzzle_forward`
  along the barrel and `muzzle_up` above its axis, the barrel pivoting
  `launch_height` above the ground, at MuzzleVelocity along the barrel
  (InitializeComponent 0x7ceea60 does not clamp it; the first substep does);
  between two substeps it moves along the straight segment of the move;
* the camera is rectilinear with the horizontal FOV, so a point `p` pixels
  below the centre of an image `W` pixels wide is
  atan(p / ((W / 2) / tan(fov / 2))) below the view axis; the shot leaves
  `bore` degrees above that axis and the weapon's sight divides the FOV by
  its zoom.
"""

import math

GRAVITY_Z = 9.80

SUBSTEP = 0.02


class Shot:
    """How a weapon fires: the flight from its game snapshot entry (a dict
    of tests/data/game_weapons.json), the launch geometry from its `launch`
    when the snapshot has one, else from its raw weapons.json entry (absent:
    from the ground, no muzzle offset)."""

    def __init__(self, game, entry=None):
        entry = entry or {}
        self.velocity = float(game["velocity"])
        self.gravity = GRAVITY_Z * float(game.get("gravity_scale", 1.0))
        self.max_speed = float(game.get("max_speed", 0.0))
        self.acceleration = float(game.get("acceleration", 0.0))
        self.timeout = float(game.get("acceleration_timeout", 0.0))
        self.follows = bool(game.get("rotation_follows_velocity", True))
        self.ignore_gravity = bool(game.get("ignore_gravity_while_boosting", False))
        launch = game.get("launch") or entry
        self.pivot_height = float(launch.get("launch_height", 0.0))
        self.muzzle_forward = float(launch.get("muzzle_forward", 0.0))
        self.muzzle_up = float(launch.get("muzzle_up", 0.0))

    def muzzle(self, elevation):
        """(x, y) of the muzzle relative to the pivot's ground point."""
        c, s = math.cos(elevation), math.sin(elevation)

        return (
            self.muzzle_forward * c - self.muzzle_up * s,
            self.pivot_height + self.muzzle_forward * s + self.muzzle_up * c,
        )


def view(game):
    """(zoom, bore in degrees) of the view a game snapshot entry is aimed
    through: the FOV divisor of its sight (null: the game's FOV) and the
    degrees above the view axis the shot leaves (null: 0)."""
    return float(game.get("zoom") or 1.0), float(game.get("bore") or 0.0)


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
    eye is taken at the barrel's pivot (`launch_height` of the raw entry).
    The target is seen atan2(height - pivot, distance) above the horizon and
    the mark pitch below the view axis, so the view axis is at the sum; the
    barrel is `bore` above the axis.
    """
    zoom, bore = view
    below = pitch_of_pixel(pixels_below_centre / scale, width, fov, zoom)
    line_of_sight = math.atan2(height - float(entry.get("launch_height", 0.0)), distance)

    return line_of_sight + below + math.radians(bore)


class _Flight:
    """A shot being flown substep by substep: position, velocity, the
    projectile's rotation (a unit vector) and the substeps taken."""

    def __init__(self, shot, elevation):
        self.shot = shot
        c, s = math.cos(elevation), math.sin(elevation)
        self.x, self.y = shot.muzzle(elevation)
        self.vx, self.vy = shot.velocity * c, shot.velocity * s
        self.rx, self.ry = c, s
        self.steps = 0

    @property
    def t(self):
        return self.steps * SUBSTEP

    def _velocity_after(self, rx, ry):
        """The velocity this substep ends with under the rotation (rx, ry)."""
        shot = self.shot
        thrusting = shot.acceleration != 0 and (
            shot.timeout <= 0 or self.steps * SUBSTEP < shot.timeout - 1e-9
        )
        ax = ay = 0.0
        gravity = shot.gravity

        if thrusting:
            ax, ay = shot.acceleration * rx, shot.acceleration * ry
            if shot.ignore_gravity:
                gravity = 0.0

        vx = self.vx + ax * SUBSTEP
        vy = self.vy + (ay - gravity) * SUBSTEP
        speed = math.hypot(vx, vy)

        if shot.max_speed and speed > shot.max_speed:
            vx, vy = vx * shot.max_speed / speed, vy * shot.max_speed / speed

        return vx, vy

    def advance(self):
        """One substep of the game."""
        end_vx, end_vy = self._velocity_after(self.rx, self.ry)
        self.x += self.vx * SUBSTEP + (end_vx - self.vx) * SUBSTEP / 2
        self.y += self.vy * SUBSTEP + (end_vy - self.vy) * SUBSTEP / 2

        if self.shot.follows:
            speed = math.hypot(self.vx, self.vy)
            self.rx, self.ry = self.vx / speed, self.vy / speed

        self.vx, self.vy = self._velocity_after(self.rx, self.ry)
        self.steps += 1


def fly_to(shot, elevation, distance):
    """Fly a shot fired at barrel `elevation` (radians) until it is
    `distance` m ahead of the pivot.

    Returns (height, slope, curvature, time): the height above the ground
    and the time there (on the substep's straight segment), the segment's
    dy/dx and d2y/dx2 from it and the next segment; or None when it never
    gets there (it falls 100 km or flies 600 s first).
    """
    flight = _Flight(shot, elevation)

    while True:
        x0, y0, step = flight.x, flight.y, flight.steps
        flight.advance()

        if flight.x >= distance:
            break

        if flight.y < -1e5 or flight.t > 600:
            return None

    x1, y1 = flight.x, flight.y
    flight.advance()
    slope = (y1 - y0) / (x1 - x0)
    following = (flight.y - y1) / (flight.x - x1)
    part = (distance - x0) / (x1 - x0)

    return (
        y0 + (y1 - y0) * part,
        slope,
        (following - slope) / ((flight.x - x0) / 2),
        max(0.0, (step + part) * SUBSTEP),
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


def miss(shot, elevation, distance, height):
    """The Miss of a shot at barrel `elevation` (radians) against the
    ground `height` m above the weapon's, `distance` m away; infinite when
    the shot never gets there."""
    flight = fly_to(shot, elevation, distance)

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


def range_at(shot, elevation, height, limit=200000.0):
    """Horizontal distance at which the path first comes down to `height`
    after its apex, found by flying it until it does (flat-ground range).
    Used for the largest range of a weapon and for the range one pixel of
    elevation is worth."""
    flight = _Flight(shot, elevation)

    while True:
        x, y = flight.x, flight.y
        flight.advance()

        if flight.y <= height < y:
            return x + (y - height) / (y - flight.y) * (flight.x - x)

        if flight.x > limit or flight.t > 600:
            return math.inf


def highest_at(shot, distance, reaches=math.inf):
    """The greatest height the shot can have when it is `distance` m ahead of
    the pivot, over every barrel elevation: the height is unimodal in the
    elevation, so a golden-section search finds it (to 1e-5 rad, which is
    far below a millimetre of height). -inf if it never gets there. The
    search stops early as soon as a height of at least `reaches` is found."""
    golden = (math.sqrt(5) - 1) / 2

    def height(elevation):
        flight = fly_to(shot, elevation, distance)
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


def widest_range(shot, low, high, height=0.0):
    """(elevation, range) in radians and metres of the barrel elevation in
    [low, high] that sends the shot farthest over ground `height` m above the
    weapon's: range_at is unimodal in the elevation for these flights, so a
    golden-section search finds it (to 1e-7 rad); an end of the interval when
    the range still grows there."""
    golden = (math.sqrt(5) - 1) / 2
    a, b = low, high
    left, right = b - golden * (b - a), a + golden * (b - a)
    left_range, right_range = range_at(shot, left, height), range_at(shot, right, height)

    while b - a > 1e-7:
        if left_range < right_range:
            a, left, left_range = left, right, right_range
            right = a + golden * (b - a)
            right_range = range_at(shot, right, height)
        else:
            b, right, right_range = right, left, left_range
            left = b - golden * (b - a)
            left_range = range_at(shot, left, height)

    best = (left, left_range) if left_range >= right_range else (right, right_range)
    ends = [(low, range_at(shot, low, height)), (high, range_at(shot, high, height))]

    return max([best] + ends, key=lambda pair: pair[1])


def elevation_to(shot, distance, height, high, limits=(math.radians(-60), math.radians(89.9))):
    """The barrel elevation (radians) that puts the shot at `height` m when it
    is `distance` m ahead of the pivot: the low or the `high` root of the
    height, found by bisection (1e-10 rad) either side of the elevation that
    reaches highest; None when the shot cannot get that high there or the
    root is outside `limits`."""
    golden = (math.sqrt(5) - 1) / 2
    low, top = limits

    def rise(elevation):
        flight = fly_to(shot, elevation, distance)
        return -math.inf if flight is None else flight[0] - height

    a, b = low, top
    left, right = b - golden * (b - a), a + golden * (b - a)
    left_rise, right_rise = rise(left), rise(right)
    while b - a > 1e-9:
        if left_rise < right_rise:
            a, left, left_rise = left, right, right_rise
            right = a + golden * (b - a)
            right_rise = rise(right)
        else:
            b, right, right_rise = right, left, left_rise
            left = b - golden * (b - a)
            left_rise = rise(left)
    peak = (a + b) / 2
    if rise(peak) < 0:
        return None

    outer = top if high else low
    if rise(outer) > 0:
        return None
    inner, far = peak, outer
    for _ in range(80):
        middle = (inner + far) / 2
        if rise(middle) > 0:
            inner = middle
        else:
            far = middle

    return (inner + far) / 2
