"""End-to-end proof that the aim-by-mark system and the range ladder put the
shell on the target.

Nothing is read from the app's own physics. For every weapon aimed with the
overlay mark the test drives the real main window (weapon, view, FOV,
distance, height), RENDERS the overlay offscreen and finds the mark (a pure
magenta dot) or the ladder ticks by pixel scan. The row of the mark is turned
into a camera pitch with a rectilinear camera written from first principles
(tests/flight.py), the barrel is pointed there (plus the view's bore) and the
shot is flown with an independent Runge-Kutta 4 integrator at a 1 ms step. The
miss is measured against flat ground at the target's distance and height.

Tolerance. A miss up to max(0.5 m, 0.05 % of the distance) is accepted. That
is far above the integrator's error (RK4 is exact for the piecewise-constant
acceleration; the result is the same at 0.25 ms, see
test_oracle_is_converged_and_exact) and above the 8-bit anti-aliasing of the
rendered dot, whose centre is read to 0.005 px. It is also below one pixel for
the short ranges but NOT for the long ones: a pixel is worth up to hundreds of
metres of range for a fast shell at long range, so the player cannot place the
mark more exactly than that. The mark is measured at sub-pixel precision, so
the bound is relaxed there only by the measurement noise: a miss must stay
within MEASURE_PX (0.02 px) of the range a pixel is worth, the "pixel floor",
which the report prints next to the worst miss.

With SB_PROOF_FULL=1 the whole matrix runs (every FOV x width x calibration x
8 distances x 3 heights per weapon and view, both arcs); the default run takes
a deterministic stratified sample of it that still covers every weapon and
view, each FOV, width, calibration, height and distance step. SB_PROOF_REPORT=1
prints the worst miss per weapon and view (use `pytest -s`).
"""

import json
import math
import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPainter

import config
import overlay as overlay_module
from ballistics import load_weapons
from conftest import ROOT

import flight

WEAPONS_JSON = os.path.join(ROOT, "weapons.json")

with open(WEAPONS_JSON, encoding="utf-8") as _file:
    RAW = {k: v for k, v in json.load(_file).items() if not k.startswith("_")}

# The owner plays at 120; the game's slider goes 90-120. 60 is a spot check.
FOVS = (90, 100, 110, 120)
SPOT_FOV = 60
WIDTHS = (1920, 2560)
SCALES = (100, 125)
HEIGHTS = (-30, 0, 30)
DISTANCE_STEPS = 8
# The map is at most this wide (m), the ladder never goes past it either.
LONGEST = 5000.0

# A target this close (m) to the highest the shell can get is on the edge of
# the range: either answer is right.
BOUNDARY = 0.05

# Sub-pixel precision of the rendered mark's centre, in pixels: the centroid of
# the 8-bit anti-aliased mark is off by up to 0.005 px (test_the_rendered_mark_is_
# read_to_a_hundredth_of_a_pixel); the bound allows four times that.
MEASURE_PX = 0.02

FULL = os.environ.get("SB_PROOF_FULL") == "1"
REPORT = os.environ.get("SB_PROOF_REPORT") == "1"


def tolerance(distance):
    return max(0.5, 5e-4 * distance)


# ---------------------------------------------------------------------------
# The rig: the real window, rendered
# ---------------------------------------------------------------------------

class Rig:
    """The main window with the overlay set up to be read by pixel scan."""

    def __init__(self, window):
        self.window = window
        self.overlay = window.overlay
        self.texts = []
        self.set_crosshair()

    def set_crosshair(self, style="cross_dot", ladder=False):
        """A magenta mark of the given style (the default one) at full size.
        It is outlined in white and symmetric about its centre, so the
        centroid of its rendering is its centre (to 0.004 px for this style;
        a lone dot is only good to 0.04)."""
        settings = self.window.config
        settings.update(
            mark_style=style, color="magenta", mark_size=100,
            range_ladder=ladder, info_enabled=False,
        )
        self.window.refresh_crosshair()

    def set_screen(self, width):
        self.overlay.setGeometry(0, 0, width, width * 9 // 16)

    def click(self, control, key):
        control.buttons[key].click()

    def aim(self, name, fov=90, scale=100, distance=500, height=0,
            arc="auto", width=1920, ox=0, oy=0):
        """Everything the player types and picks, through the window."""
        win = self.window
        self.set_screen(width)
        win.config["center_offset_x"] = ox
        win.config["center_offset_y"] = oy
        win.config["offset_scale"] = scale
        win.select_weapon(name)
        self.click(win.arc_control, arc)

        win.fov_entry.setText(f"{fov:g}")
        win.height_entry.setText("" if height == 0 else f"{height:g}")

        win.distance_entry.setText("" if distance is None else f"{distance:g}")
        win.calculate(show_errors=False)
        win.update_ladder()

    def grab(self, x0, x1):
        """(weights per row of the red channel, rows) of the overlay between
        columns x0 and x1, from a rendering."""
        height = self.overlay.height()
        image = self.overlay.grab(QRect(x0, 0, x1 - x0, height)).toImage()
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        pointer = image.constBits()
        data = bytes(pointer.asarray(image.sizeInBytes()))
        stride = image.bytesPerLine()
        columns = x1 - x0

        # Premultiplied BGRA: red is byte 2. Magenta is the only red thing
        # drawn (the shadow is black), so this is the coverage of the mark.
        return [
            sum(data[row * stride + 4 * c + 2] for c in range(columns))
            for row in range(height)
        ]

    def mark_row(self):
        """Row (pixel edges: the centre of row r is r + 0.5) of the dot's
        centre by the centroid of its rendered coverage, or None."""
        centre = int(self.overlay.center_x)
        weights = self.grab(centre - 12, centre + 12)
        total = sum(weights)

        if not total:
            return None

        return sum((row + 0.5) * w for row, w in enumerate(weights)) / total

    def mark_column(self):
        """Column of the dot's centre by the centroid of its rendering."""
        ov = self.overlay
        image = ov.grab(QRect(0, int(ov.center_y + ov.offset) - 8, ov.width(), 16))
        image = image.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        data = bytes(image.constBits().asarray(image.sizeInBytes()))
        stride = image.bytesPerLine()
        columns = [
            sum(data[row * stride + 4 * c + 2] for row in range(image.height()))
            for c in range(image.width())
        ]
        total = sum(columns)

        return sum((c + 0.5) * w for c, w in enumerate(columns)) / total

    def ladder(self):
        """[(label text, tick row, label centre row)] of the rendered
        ladder, nearest first, and the recorded label rectangles. The ticks
        are found by pixel scan of their columns, the labels by recording
        what the overlay asks Qt to draw."""
        ov = self.overlay
        recorded = []

        class Recorder(QPainter):
            def drawText(self, *args):
                if len(args) == 3 and isinstance(args[2], str) \
                        and self.pen().color().red() > 0:
                    recorded.append((args[0], args[2]))
                return super().drawText(*args)

        real = overlay_module.QPainter
        overlay_module.QPainter = Recorder
        try:
            ov.update()
            weights_x1 = int(ov.center_x) - overlay_module.LADDER_GAP - 1
            weights_x0 = weights_x1 - overlay_module.LADDER_TICK + 2
            # Rendering paints the overlay: the recorder sees every label.
            weights = self.grab(weights_x0, weights_x1)
        finally:
            overlay_module.QPainter = real

        rows = []
        run = []

        for row, weight in enumerate(weights):
            if weight:
                run.append((row, weight))
            elif run:
                rows.append(run)
                run = []

        if run:
            rows.append(run)

        ticks = [
            sum((r + 0.5) * w for r, w in run) / sum(w for _, w in run)
            for run in rows
        ]
        labels = [(text, rect.center().y()) for rect, text in recorded]

        return ticks, labels, [rect for rect, _ in recorded]


@pytest.fixture(scope="module")
def rig(qapp, tmp_path_factory):
    patch = pytest.MonkeyPatch()
    folder = tmp_path_factory.mktemp("proof")
    patch.chdir(folder)
    patch.setattr(config, "CONFIG_PATH", str(folder / "config.json"))

    from crosshair import MainWindow

    window = MainWindow(load_weapons(WEAPONS_JSON))
    yield Rig(window)
    window.close()
    patch.undo()


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------

LOADED = load_weapons(WEAPONS_JSON)

# Weapons aimed with the overlay mark (each has one fixed sight view).
MARKED = [name for name, weapon in LOADED.items() if weapon.aim == "overlay"]


def distances(name):
    """8 distances from 30 m to ~95 % of the weapon's longest range (at most
    the map's width)."""
    weapon = LOADED[name]
    low = max(weapon.min_distance, 30.0)
    high = min(0.95 * weapon.max_range(), LONGEST)

    return sorted({
        round(low + (high - low) * i / (DISTANCE_STEPS - 1))
        for i in range(DISTANCE_STEPS)
    })


def other_arc(name):
    return "low" if LOADED[name].arc == "high" else "high"


def cases(name):
    """(arc, fov, width, scale, distance, height) of one weapon and view:
    the whole matrix with SB_PROOF_FULL, else a deterministic stratified
    sample that covers every FOV, width, calibration, height and distance
    step several times, the longest range at the widest FOV, a spot check at
    FOV 60 and a few shots on the other arc."""
    ds = distances(name)
    full = [
        ("auto", fov, width, scale, d, h)
        for fov in FOVS for width in WIDTHS for scale in SCALES
        for d in ds for h in HEIGHTS
    ]
    arcs = [
        (other_arc(name), fov, width, scale, d, h)
        for fov in FOVS for width in WIDTHS for scale in SCALES
        for d in ds for h in HEIGHTS
    ]

    if FULL:
        return full + arcs

    n = len(ds)
    sample = [
        ("auto", FOVS[k % 4], WIDTHS[(k // 4) % 2], SCALES[(k // 8) % 2],
         ds[(5 * k + k // 8) % n], HEIGHTS[(2 * k + k // 3) % 3])
        for k in range(12)
    ]
    sample += [
        ("auto", 120, 2560, 125, ds[-1], 30),
        ("auto", 120, 2560, 100, ds[-1], -30),
        ("auto", 90, 1920, 100, ds[0], -30),
        ("auto", SPOT_FOV, 1920, 100, ds[n // 2], 0),
        ("auto", SPOT_FOV, 2560, 125, ds[-2], 30),
    ]
    sample += [
        (other_arc(name), FOVS[k % 4], WIDTHS[k % 2], 100,
         ds[(3 * k) % n], HEIGHTS[k % 3])
        for k in range(3)
    ]

    return sample


RESULTS = {}


def measure_case(rig, name, case):
    """Drive the window through `case`, render the mark and fly the shot.
    Returns (miss m, pixel floor m or None, on_screen)."""
    arc, fov, width, scale, distance, height = case
    entry = RAW[name]
    view = flight.view(entry)

    rig.aim(name, fov, scale, distance, height, arc, width)

    ov = rig.overlay
    solution = rig.window.last_solution

    assert solution is not None, (name, case)

    if not solution.reachable:
        # Unreachable must mean unreachable for the game's physics too: no
        # barrel elevation brings the shell up to the target.
        assert flight.highest_at(flight.Shot(entry), distance, height + BOUNDARY) < height + BOUNDARY, (
            "the app calls a reachable target unreachable", name, case,
            solution.reason,
        )
        return None

    if ov.is_offscreen(ov.offset):
        return None

    row = rig.mark_row()
    assert row is not None, ("mark not rendered", name, case)

    pixels = row - ov.center_y
    shot = flight.Shot(entry)
    elevation = flight.barrel_elevation(
        entry, view, fov, width, pixels, distance, height, scale / 100
    )
    result = flight.miss(shot, elevation, distance, height)
    floor = None

    if result.distance > tolerance(distance) or distance == distances(name)[-1]:
        # What one pixel of the mark is worth here.
        focal = flight.focal_length(width, fov, view[0]) * scale / 100
        step = math.atan((pixels + 1) / focal) - math.atan(pixels / focal)
        floor = flight.miss(shot, elevation + step, distance, height)

    return result, floor, True


def check_measurement(name, case, result):
    miss, floor, on_screen = result
    allowed = tolerance(case[4])

    if floor is not None:
        allowed = max(allowed, MEASURE_PX * floor.distance)

    assert miss.distance <= allowed, (name, case, miss, allowed, floor)


@pytest.mark.parametrize("name", MARKED)
def test_mark_puts_the_shell_on_the_target(rig, name):
    worst = (0.0, 0.0)
    floor = 0.0
    checked = skipped = 0

    for case in cases(name):
        result = measure_case(rig, name, case)

        if result is None:
            skipped += 1
            continue

        check_measurement(name, case, result)
        checked += 1
        miss, pixel_floor, _ = result
        worst = max(worst, (miss.distance, 100 * miss.distance / case[4]))

        if pixel_floor is not None:
            floor = max(floor, pixel_floor.distance)

    assert checked >= 5, (name, "too few shots on the screen")
    RESULTS[name] = (worst[0], worst[1], floor, checked, skipped)


@pytest.fixture(scope="module", autouse=True)
def print_report(request):
    yield

    if not REPORT:
        return

    print("\nworst miss per weapon and view (m, % of range, pixel floor m, shots, off screen or unreachable)")
    for name, (miss, percent, floor, checked, off) in RESULTS.items():
        print(f"{name} | {miss:.4f} m | {percent:.5f} % | {floor:.1f} m | {checked} | {off}")


# ---------------------------------------------------------------------------
# The oracle itself
# ---------------------------------------------------------------------------

def test_oracle_is_converged_and_exact():
    """The integrator is checked against hand-made closed forms and against
    itself at a smaller step, so a pass of the matrix means something."""
    # Vacuum, no boost, from the ground: R = v^2 sin(2a) / g
    plain = flight.Shot({"velocity": 100.0})
    angle = math.radians(30)
    expected = 100.0 ** 2 * math.sin(2 * angle) / 9.80
    assert flight.range_at(plain, angle, 0.0) == pytest.approx(expected, abs=1e-3)

    # Gravity scale 2 doubles g.
    heavy = flight.Shot({"velocity": 100.0, "gravity": 2})
    assert flight.range_at(heavy, angle, 0.0) == pytest.approx(expected / 2, abs=1e-3)

    # A boost of a m/s^2 for T s along a level barrel, no gravity effect on
    # the horizontal motion: x = v0 T + a T^2 / 2 + (v0 + a T) (t - T) at
    # t = 2 s, read off the flight time at that distance.
    rocket = flight.Shot({"velocity": 100.0, "acceleration": 50.0, "acceleration_time": 1.0})
    x = 100.0 * 1.0 + 0.5 * 50.0 + 150.0 * (2.0 - 1.0)
    height, slope, _, t = flight.fly_to(rocket, 0.0, x)
    assert t == pytest.approx(2.0, abs=1e-9)
    assert height == pytest.approx(-0.5 * 9.80 * 4.0, abs=1e-9)

    # A muzzle moves with the elevation: 2 m along, 0.5 m up at 90 degrees
    # (nearly) is 0.5 m ahead and 2 m up.
    gun = flight.Shot({"velocity": 100.0, "launch_height": 1.0, "muzzle_forward": 2.0, "muzzle_up": 0.5})
    x0, y0 = gun.muzzle(math.pi / 2)
    assert (x0, y0) == pytest.approx((-0.5, 3.0))

    # Same answer at a quarter of the step.
    for entry in (RAW["RPG-7 · PG-7V HEAT / OG-7V"], RAW["UB-32 (S-5 rockets)"]):
        shot = flight.Shot(entry)
        coarse = flight.fly_to(shot, math.radians(7), 400.0)
        fine = flight.fly_to(shot, math.radians(7), 400.0, step=flight.STEP / 4)
        assert coarse[0] == pytest.approx(fine[0], abs=1e-6)
        assert coarse[3] == pytest.approx(fine[3], abs=1e-9)


def test_the_rendered_mark_is_read_to_a_hundredth_of_a_pixel(rig):
    """The mark's row is read from a rendering by the centroid of its
    anti-aliased dot: compare with where the overlay was told to draw it,
    over offsets from above the centre to the bottom of the screen."""
    rig.set_screen(2560)
    worst = 0.0

    for step in range(60):
        offset = -300 + step * 15.37
        rig.overlay.set_offset(offset)
        worst = max(worst, abs(rig.mark_row() - (rig.overlay.center_y + offset)))

    assert worst < 0.01 + 1e-3


# ---------------------------------------------------------------------------
# The range ladder
# ---------------------------------------------------------------------------

LADDER_COMBOS = [
    (90, 1920, 100), (120, 2560, 125), (110, 1920, 125), (120, 1920, 100),
    (SPOT_FOV, 1920, 100),
]

# The labels, spacing and clearance are checked on every tick; the flights
# on the first, the last and a few between (all of them with SB_PROOF_FULL).
FLOWN_TICKS = 6


def ladder_combos():
    if FULL:
        return [
            (fov, width, scale)
            for fov in FOVS + (SPOT_FOV,) for width in WIDTHS for scale in SCALES
        ]
    return LADDER_COMBOS


LADDER_SEEN = {}


@pytest.mark.parametrize("name", [m for m in MARKED if LOADED[m].g])
def test_ladder_ticks_are_where_their_labels_say(rig, name):
    entry = RAW[name]
    view = flight.view(entry)
    shot = flight.Shot(entry)
    ticks_seen = 0
    # The default crosshair shape, so the first tick's clearance is checked
    # against its real reach (a dot, three lines of 14 px 6 px out).
    rig.set_crosshair(ladder=True)

    try:
        for fov, width, scale in ladder_combos():
            rig.aim(name, fov, scale, None, 0, "auto", width)
            ov = rig.overlay
            centre = ov.center_y
            ticks, labels, rects = rig.ladder()
            # The crosshair's own left line is at the centre row.
            ticks = [t for t in ticks if t - centre > 3]
            case = (name, fov, width, scale)

            assert len(ticks) == len(labels) == len(ov.ladder), case

            flown = range(len(ticks)) if FULL else sorted(
                {round(i * (len(ticks) - 1) / (FLOWN_TICKS - 1)) for i in range(FLOWN_TICKS)}
            ) if ticks else []

            for index, (tick, (text, label_row)) in enumerate(zip(ticks, labels)):
                distance = int(text)
                assert label_row == pytest.approx(tick, abs=0.02), (case, text)

                if index not in flown:
                    continue

                elevation = flight.barrel_elevation(
                    entry, view, fov, width, tick - centre, distance, 0.0, scale / 100
                )
                result = flight.miss(shot, elevation, distance, 0.0)
                allowed = tolerance(distance)

                if result.distance > allowed:
                    focal = flight.focal_length(width, fov, view[0]) * scale / 100
                    pixels = tick - centre
                    step = math.atan((pixels + 1) / focal) - math.atan(pixels / focal)
                    floor = flight.miss(shot, elevation + step, distance, 0.0)
                    allowed = max(allowed, MEASURE_PX * floor.distance)

                assert result.distance <= allowed, (case, text, result, allowed)

            # Labels are the ranges, nearest first, and they do not overlap
            texts = [int(text) for text, _ in labels]
            assert texts == sorted(set(texts)), case

            for upper, lower in zip(rects, rects[1:]):
                assert upper.bottom() <= lower.top(), (case, "labels overlap")

            # Ticks keep their spacing and the first one clears the crosshair
            spacing = max(14.0, overlay_module.LADDER_SPACING * ov.height())
            clearance = 6 + 14 + overlay_module.LADDER_CLEAR
            for upper, lower in zip(ticks, ticks[1:]):
                assert lower - upper >= spacing - 0.05, (case, "ticks too close")

            if ticks:
                assert ticks[0] - centre >= clearance - 0.05, (case, "first tick")
                assert ticks[-1] <= ov.height() - ov.EDGE_MARGIN + 0.05, case

            ticks_seen += len(ticks)
    finally:
        rig.set_crosshair()

    LADDER_SEEN[name] = ticks_seen
    assert ticks_seen > 0, (name, "no ladder at all")


# ---------------------------------------------------------------------------
# Calibration, centre offsets, FOV 120 and the edges
# ---------------------------------------------------------------------------

def mark_pixels(rig):
    return rig.mark_row() - rig.overlay.center_y


def test_calibration_multiplies_the_offset_and_the_shell_still_lands(rig):
    """offset_scale multiplies the pixel offset below the centre (50..150 %,
    its range): the drawn offset is scale x the one at 100 %, and dividing it
    back by the scale lands the shell."""
    entry = RAW["SPG-9 · HEAT"]
    view = flight.view(entry)
    shot = flight.Shot(entry)

    for fov, width in ((90, 1920), (120, 2560)):
        rig.aim("SPG-9 · HEAT", fov, 100, 700, 5, "auto", width)
        base = mark_pixels(rig)

        for scale in (50, 75, 125, 150):
            rig.aim("SPG-9 · HEAT", fov, scale, 700, 5, "auto", width)
            drawn = mark_pixels(rig)

            assert drawn == pytest.approx(base * scale / 100, abs=0.03), scale

            elevation = flight.barrel_elevation(entry, view, fov, width, drawn, 700, 5, scale / 100)
            assert flight.miss(shot, elevation, 700, 5).distance < 0.5, scale

            # Taken at face value (no division) the shell lands off: the
            # scale really does move the mark.
            raw = flight.barrel_elevation(entry, view, fov, width, drawn, 700, 5, 1.0)
            if scale != 100:
                assert flight.miss(shot, raw, 700, 5).distance > 1.0, scale


def test_centre_offsets_move_the_mark_by_exactly_the_offset(rig):
    rig.aim("SPG-9 · HEAT", 110, 100, 600, 0, "auto", 1920, 0, 0)
    row, column = rig.mark_row(), rig.mark_column()

    for ox, oy in ((40, 0), (0, -70), (-55, 33), (130, 90)):
        rig.aim("SPG-9 · HEAT", 110, 100, 600, 0, "auto", 1920, ox, oy)

        assert rig.mark_row() == pytest.approx(row + oy, abs=0.03), (ox, oy)
        assert rig.mark_column() == pytest.approx(column + ox, abs=0.03), (ox, oy)

    # Through the real sliders of the settings page
    win = rig.window
    win.controls["center_offset_y"].slider.setValue(25)
    win.controls["center_offset_x"].slider.setValue(-15)
    win.controls["offset_scale"].slider.setValue(100)
    assert rig.mark_row() == pytest.approx(row + 25, abs=0.03)
    assert rig.mark_column() == pytest.approx(column - 15, abs=0.03)

    win.controls["center_offset_y"].slider.setValue(0)
    win.controls["center_offset_x"].slider.setValue(0)
    assert rig.mark_row() == pytest.approx(row, abs=0.03)


def test_the_mark_of_a_shifted_centre_still_lands(rig):
    entry = RAW["Tank AP · M256 / Rh120"]
    view = flight.view(entry)

    for oy in (-60, 45):
        rig.aim("Tank AP · M256 / Rh120", 120, 100, 1800, 10, "auto", 2560, 20, oy)
        pixels = rig.mark_row() - (rig.overlay.height() / 2 + oy)
        elevation = flight.barrel_elevation(entry, view, 120, 2560, pixels, 1800, 10)

        assert flight.miss(flight.Shot(entry), elevation, 1800, 10).distance < 0.5


def test_fov_120_is_accepted_everywhere(rig, tmp_path):
    """The game's FOV slider goes 90-120, the player uses 120."""
    win = rig.window
    rig.aim("SPG-9 · HEAT", 120, 100, 500, 0)

    assert win.config["fov"] == 120
    assert win.fov_entry.value() == 120
    assert win.last_solution.reachable

    # Saved and read back unchanged
    saved = str(tmp_path / "config.json")
    config.save_config(win.config, saved)
    assert config.load_config(saved)["fov"] == 120

    # The arrow keys of the field step by one and do not clamp 120
    win.fov_entry.add(1)
    assert win.fov_entry.value() == 121
    win.fov_entry.add(-1)
    assert win.fov_entry.value() == 120

    # Out of range is still refused, 1 and 179 are the limits
    for text, ok in (("0", False), ("180", False), ("1", True), ("179", True)):
        win.fov_entry.setText(text)
        win.calculate()
        assert (win.big_label.property("state") != "error") == ok, text


def test_the_mark_is_physical_at_the_extreme_fovs(rig):
    """FOV 179 (a focal length of 8 px) and FOV 1 (of 55 000 px): nothing
    crashes, the mark stays where the camera model puts it, and when it is on
    the screen the shell lands."""
    entry = RAW["SPG-9 · HEAT"]
    view = flight.view(entry)
    shot = flight.Shot(entry)
    on_screen = 0

    for fov in (1, 179):
        for distance in (150, 600, 1500):
            rig.aim("SPG-9 · HEAT", fov, 100, distance, 0, "auto", 1920)
            ov = rig.overlay

            if ov.is_offscreen(ov.offset):
                assert rig.mark_row() is not None
                continue

            pixels = rig.mark_row() - ov.center_y
            elevation = flight.barrel_elevation(entry, view, fov, 1920, pixels, distance, 0)
            focal = flight.focal_length(1920, fov)
            step = math.atan((pixels + 1) / focal) - math.atan(pixels / focal)
            floor = flight.miss(shot, elevation + step, distance, 0).distance
            result = flight.miss(shot, elevation, distance, 0)

            assert result.distance <= max(tolerance(distance), MEASURE_PX * floor), (fov, distance)
            on_screen += 1

    assert on_screen >= 3


def test_a_fov_below_the_zoom_is_held_at_one_degree_and_is_not_exact(rig):
    """The 4x scope at FOV 3 sees 0.75 degrees; the overlay holds the view at
    1 degree (documented, not exact): the mark is the 1 degree one and the
    real 0.75 degree view would need a different mark."""
    name = "SPG-9 · HEAT · scope"
    entry = RAW[name]
    zoom, bore = flight.view(entry)
    shot = flight.Shot(entry)
    distance = 1440

    rig.aim(name, 3, 100, distance, 0, "auto", 1920)
    assert not rig.overlay.is_offscreen(rig.overlay.offset)
    pixels = mark_pixels(rig)

    held = flight.barrel_elevation(entry, (zoom, bore), 3, 1920, pixels, distance, 0)
    assert flight.miss(shot, held, distance, 0).distance < 0.5

    true_focal = (1920 / 2) / math.tan(math.radians(3 / zoom) / 2)
    true = math.atan(pixels / true_focal) + math.radians(bore)
    assert flight.miss(shot, true, distance, 0).distance > 1.0


def test_a_mark_off_the_screen_becomes_an_arrow_at_the_edge(rig):
    ov = rig.overlay

    # Far below: a high arc of a direct-fire weapon
    rig.aim("SPG-9 · HEAT", 90, 100, 500, 0, "high", 1920)
    assert ov.is_offscreen(ov.offset) and ov.offset > 0
    rows = rig.grab(int(ov.center_x) - 20, int(ov.center_x) + 20)
    mass = [(r, w) for r, w in enumerate(rows) if w]
    assert mass and all(ov.height() - 24 <= r <= ov.height() - 7 for r, _ in mass)

    # Far above: a strong optic at a narrow FOV, aimed closer than its zero
    rig.aim("SPG-9 · HEAT · scope", 20, 100, 30, 0, "auto", 1920)
    assert ov.is_offscreen(ov.offset) and ov.offset < 0
    rows = rig.grab(int(ov.center_x) - 20, int(ov.center_x) + 20)
    mass = [(r, w) for r, w in enumerate(rows) if w]
    assert mass and all(6 <= r <= 24 for r, _ in mass)

    # ...and back on the screen the dot returns
    rig.aim("SPG-9 · HEAT", 90, 100, 500, 0, "auto", 1920)
    assert not ov.is_offscreen(ov.offset)


def test_unreachable_ranges_are_unreachable_for_the_game_too(rig):
    for name, distance, height in (
        ("M203 / M320 / GP-25 / HK79 / SL40", 700, 0),
        ("RPG-7 · PG-7V HEAT / OG-7V", 6000, 0),
        ("AGS-17 · emplacement", 2500, 0),
    ):
        rig.aim(name, 90, 100, distance, height)
        solution = rig.window.last_solution

        assert not solution.reachable, name
        assert rig.window.big_label.property("state") == "error", name
        assert rig.overlay.offset == 0, name
        assert flight.highest_at(flight.Shot(RAW[name]), distance) < height, name


# ---------------------------------------------------------------------------
# The solver on every weapon, with the oracle
# ---------------------------------------------------------------------------

def solver_cases(name):
    weapon = LOADED[name]
    low = max(weapon.min_distance, 30.0)
    high = min(0.97 * weapon.max_range(), LONGEST)
    n = 5
    ds = sorted({round(low + (high - low) * i / (n - 1)) for i in range(n)})

    return [
        (arc, d, HEIGHTS[(i + j) % 3])
        for j, arc in enumerate(("low", "high"))
        for i, d in enumerate(ds)
    ]


@pytest.mark.parametrize("name", list(LOADED))
def test_solver_lands_on_the_target_for_every_weapon(name):
    """solve() against the independent flight, both arcs, with the raw
    barrel angle (the launch point moving with it, boosts, muzzle heights)."""
    from ballistics import solve

    weapon = LOADED[name]
    shot = flight.Shot(RAW[name])
    flown = 0

    for arc, distance, height in solver_cases(name):
        solution = solve(weapon, distance, height, arc)

        if solution.reason_code == "out_of_range":
            assert flight.highest_at(shot, distance, height + BOUNDARY) < height + BOUNDARY, (arc, distance, height)
            continue

        if not math.isfinite(solution.raw_angle) or not solution.reachable:
            continue

        # Steep shots of fast shells fly for minutes: not worth integrating.
        if solution.time_of_flight > 45:
            continue

        result = flight.miss(shot, math.radians(solution.raw_angle), distance, height)

        assert result.distance <= tolerance(distance), (arc, distance, height, result)
        assert result.vertical == pytest.approx(0, abs=tolerance(distance)), (arc, distance, height)
        flown += 1

    assert flown >= 2, name


def test_max_range_is_the_longest_the_game_flies():
    """Weapon.max_range() against the integrator: flown at the elevation
    that gives the longest range (the app's own peak_elevation), the shell
    lands on max_range() on flat ground, and 0.5 degrees either side it falls
    short (so no better elevation is hiding nearby)."""
    for name, weapon in LOADED.items():
        if not weapon.g:
            assert weapon.max_range() == math.inf, name
            continue

        shot = flight.Shot(RAW[name])
        longest = weapon.max_range()
        best = weapon.peak_elevation(longest)

        if longest > 30000:
            # 60 000 steps a flight: a plain parabola, checked by its formula
            assert shot.boost_time == shot.muzzle_forward == shot.pivot_height == 0, name
            assert longest == pytest.approx(shot.velocity ** 2 / shot.gravity), name
            continue

        assert flight.range_at(shot, best, 0.0) == pytest.approx(longest, abs=0.02), name

        if longest <= 12000:
            for side in (-1, 1):
                nearby = flight.range_at(shot, best + side * math.radians(0.5), 0.0)
                assert nearby < longest + 0.02, (name, side)


def test_min_distance_and_the_arc_that_is_chosen():
    from ballistics import solve

    for name, weapon in LOADED.items():
        if weapon.min_distance:
            closer = solve(weapon, weapon.min_distance - 1, 0)
            assert closer.reason_code == "too_close", name
            assert solve(weapon, weapon.min_distance, 0).reason_code != "too_close", name

        # "auto" picks the weapon's own arc, and it is the reachable one:
        # a high-arc weapon is flagged high and aims above 45 degrees (the
        # technical mortars read their own scale, 5 degrees off).
        distance = max(weapon.min_distance + 5, 100.0)
        if not weapon.g or distance >= 0.9 * weapon.max_range():
            continue

        solution = solve(weapon, distance, 0, None)
        assert solution.arc == weapon.arc, name

        if solution.reachable and weapon.arc == "high":
            assert solution.raw_angle > 45, name
            assert "low" in solution.alternatives or not solve(weapon, distance, 0, "low").reachable


def test_mils_and_degrees_agree_for_the_weapons_in_mils():
    from ballistics import MILS_PER_DEGREE, solve

    assert MILS_PER_DEGREE == pytest.approx(6400 / 360)

    for name, weapon in LOADED.items():
        if weapon.unit != "mil":
            continue

        solution = solve(weapon, 600, 0)
        assert solution.mils == pytest.approx(solution.angle * 6400 / 360), name
