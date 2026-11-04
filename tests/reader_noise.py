"""Degraded frames for the reader precision audit (tests/test_reader_precision.py).

The frames are cut out of a synthetic screen the way the app grabs them
(sightlay.ScreenSight.region and .compass_region), then spoiled the way a
real capture can be: Gaussian noise on the grey levels (harsher than noise
per colour channel, which averages down in the grey conversion), a real JPEG
round trip (8x8 blocking), brightness scaled by a factor, a shift of the
whole frame under the readers' fixed centre, and a screen scale that differs
from the one the reader is told.

Run `python tests/reader_noise.py` for the full table (hundreds of readings,
about a minute); the tests use a smaller sample of the same frames.
"""

import math
import os
import random
import statistics
import sys

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sightlay  # noqa: E402
from compassimage import draw_compass  # noqa: E402
from compassreader import STRIP_HALF_WIDTH, SEARCH_TOP, DigitReader, read_compass, strip_ticks  # noqa: E402
from sightimage import draw_sight  # noqa: E402
from sightreader import REFERENCE_HEIGHT, GrayImage, LabelTemplates, read_scale  # noqa: E402

SIZES = ((1920, 1080), (2560, 1440))
SIGHT_MILS = (800.0, 1579.0)


def sight_crop(screen):
    """The sight's grab region of `screen` and the screen centre in it."""
    width, height = screen.width(), screen.height()
    left = max(0, round(width / 2 - sightlay.GRAB_LEFT * height))
    right = round(width / 2 - sightlay.GRAB_RIGHT * height)
    top = max(0, round(height / 2 - sightlay.GRAB_HALF_HEIGHT * height))
    bottom = min(height, round(height / 2 + sightlay.GRAB_HALF_HEIGHT * height))

    return screen.copy(left, top, right - left, bottom - top), width / 2 - left, height / 2 - top


def compass_crop(screen):
    """The compass grab region of `screen` and the screen centre's x in it."""
    width, height = screen.width(), screen.height()
    scale = height / REFERENCE_HEIGHT
    half = (STRIP_HALF_WIDTH + sightlay.COMPASS_MARGIN) * scale
    left = max(0, round(width / 2 - half))
    right = min(width, round(width / 2 + half))
    top = max(0, round(height - SEARCH_TOP * scale))

    return screen.copy(left, top, right - left, height - top), width / 2 - left


def jpeg(image, quality):
    """`image` after a JPEG round trip at `quality` (1-100)."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "JPEG", quality)

    return QImage.fromData(buffer.data(), "JPEG")


def grey(image, noise=0.0, gain=1.0, shift=(0, 0), rng=None):
    """The grey image the readers get: `image` shifted by `shift` px (edge
    pixels repeat), scaled by `gain` and with Gaussian noise of `noise`
    levels (sigma, of 255) added."""
    gray = GrayImage.from_qimage(image)
    width, height, data = gray.width, gray.height, gray.data
    dx, dy = shift
    rows = []

    for y in range(height):
        source = min(height - 1, max(0, y - dy))
        row = data[source * gray.stride:source * gray.stride + width]

        if dx > 0:
            row = row[:1] * dx + row[:width - dx]
        elif dx < 0:
            row = row[-dx:] + row[-1:] * -dx

        rows.append(row)

    values = b"".join(rows)

    if gain != 1.0:
        values = values.translate(bytes(min(255, round(v * gain)) for v in range(256)))

    if noise:
        values = bytes(
            min(255, max(0, round(v + rng.gauss(0, noise)))) for v in values
        )

    return GrayImage(values, width, height, width)


# name: how to spoil the colour crop, then the grey one
CONDITIONS = {
    "clean": {},
    "noise 2/255": {"noise": 2},
    "noise 4/255": {"noise": 4},
    "noise 8/255": {"noise": 8},
    "jpeg q50": {"jpeg": 50},
    "jpeg q25": {"jpeg": 25},
    "brightness -30%": {"gain": 0.7},
    "brightness +30%": {"gain": 1.3},
    "shift +1 px x": {"shift": (1, 0)},
    "shift -1 px x": {"shift": (-1, 0)},
    "shift +1 px y": {"shift": (0, 1)},
    "shift -1 px y": {"shift": (0, -1)},
    "noise 8 + jpeg q50 + 0.7 + shift": {"noise": 8, "jpeg": 50, "gain": 0.7, "shift": (1, 1)},
    "noise 8 + jpeg q50 + 1.3 + shift": {"noise": 8, "jpeg": 50, "gain": 1.3, "shift": (-1, -1)},
}

# What the reader is told the screen scale is, against the real one.
SCALE_MISMATCH = (0.97, 1.03, 0.95, 1.05)


def degrade(crop, spec, rng):
    """The grey image of colour `crop` spoiled as `spec` says."""
    if "jpeg" in spec:
        crop = jpeg(crop, spec["jpeg"])

    return grey(crop, spec.get("noise", 0.0), spec.get("gain", 1.0), spec.get("shift", (0, 0)), rng)


def sight_error(mils, size, spec, rng, templates, told=1.0):
    """Reading error (mil, signed) of the elevation scale at `mils`, or None
    when it is not read. `told`: the factor on the screen scale the reader
    is given."""
    crop, cx, cy = sight_crop(draw_sight(mils, *size))
    scale = size[1] / REFERENCE_HEIGHT * told
    reading = read_scale(degrade(crop, spec, rng), round(cx), round(cy), scale, templates)

    return None if reading is None else reading.mils - mils


def compass_error(bearing, size, spec, rng, digits, told=1.0):
    """Reading error (degrees, signed) of the mortar view's compass at
    `bearing`, or None when it is not read."""
    crop, cx = compass_crop(draw_compass(bearing, *size))
    scale = size[1] / REFERENCE_HEIGHT * told
    reading = read_compass(degrade(crop, spec, rng), cx, scale, digits, 2.5)

    if reading is None:
        return None

    return (reading.degrees - bearing + 180) % 360 - 180


def strip_error(bearing, size, spec, rng, told=1.0):
    """How far (degrees) the strip's ticks sit from where the true bearing
    puts them: the smallest tolerance, in steps of 0.05, at which
    `strip_ticks` still accepts them; None if none up to 2.5 degrees does
    (the strip is not seen)."""
    crop, cx = compass_crop(draw_compass(bearing, *size))
    scale = size[1] / REFERENCE_HEIGHT * told
    image = degrade(crop, spec, rng)

    for step in range(0, 51):
        tolerance = step * 0.05

        if strip_ticks(image, cx, scale, bearing, tolerance) is not None:
            return tolerance

    return None


def summary(errors):
    """(readings, misses, mean |error|, p99 |error|, max |error|)."""
    found = sorted(abs(e) for e in errors if e is not None)

    if not found:
        return 0, len(errors), math.nan, math.nan, math.nan

    p99 = found[min(len(found) - 1, math.ceil(0.99 * len(found)) - 1)]

    return len(found), len(errors) - len(found), statistics.fmean(found), p99, found[-1]


def sample_mils(rng, count):
    return [round(rng.uniform(*SIGHT_MILS), 1) for _ in range(count)]


def sample_bearings(rng, count):
    return [round(rng.uniform(0, 360), 1) for _ in range(count)]


def main(count=40):
    rng = random.Random(7)
    templates = LabelTemplates()
    digits = DigitReader(templates)

    for what, unit in (("sight", "mil"), ("compass", "deg")):
        print(f"== {what} ({unit}): readings, misses, mean, p99, max |error|")

        for size in SIZES:
            samples = sample_mils(rng, count) if what == "sight" else sample_bearings(rng, count)
            cases = list(CONDITIONS.items()) + [(f"scale told x{t}", {"told": t}) for t in SCALE_MISMATCH]

            for name, spec in cases:
                told = spec.get("told", 1.0)
                spec = {} if "told" in spec else spec

                if what == "sight":
                    errors = [sight_error(v, size, spec, rng, templates, told) for v in samples]
                else:
                    errors = [compass_error(v, size, spec, rng, digits, told) for v in samples]

                n, miss, mean, p99, worst = summary(errors)
                line = f"{size[1]}p {name:36} {n:3} {miss:3}  {mean:7.4f} {p99:7.4f} {worst:7.4f}"

                if what == "compass":
                    n, miss, mean, p99, worst = summary(
                        [strip_error(v, size, spec, rng, told) for v in samples]
                    )
                    line += f"   strip {n:3} {miss:3}  {mean:5.2f} {p99:5.2f} {worst:5.2f}"

                print(line, flush=True)


if __name__ == "__main__":
    from PyQt6.QtGui import QGuiApplication

    app = QGuiApplication([])
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
