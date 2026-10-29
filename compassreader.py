"""The bearing read off the HUD compass on the screen.

Squad's compass (UI/Widgets/HUD/Compass/UMG_Compass) is a strip of ticks
at the bottom centre of the screen: one tick per degree, a longer one every
5 and every 15 degrees, 126 degrees across 800 px at 1080p (6.345 px per
degree), labels below. The current bearing is at the screen's centre
column, where a box shows it in whole degrees ("000"). Angles grow to the
right. Measured on 1080p frames of the game: short ticks 8 px, 5-degree
ticks 14 px, 15-degree ticks 18 px tall, white; the box digits 13 px tall.

The compass is on the screen in the mortar's own view (before the sight is
zoomed in with the right mouse button), together with its elevation
scale, so one frame gives both axes of a lay (see sightlay).

Reading:
1. the tick row is the row with the most narrow bright runs near the
   bottom; each run's centre is found to a fraction of a pixel and its
   tick's length measured up and down;
2. a straight line x = x0 + spacing * n is fitted through the ticks
   (n: the tick's index), which gives the bearing's fraction of a degree
   at the centre to about a twentieth of a degree;
3. the 15-degree ticks fix the bearing modulo 15 degrees;
4. the box's three digits, matched against Roboto Condensed digits (the
   HUD's font), give the bearing to a degree, which picks the right
   15-degree turn. While laying, a recent reading can stand in for the
   digits (`near`).

Only 16:9 screens are supported. The HUD scale is measured from the tick
spacing, so any resolution works.
"""

import math
import re
from dataclasses import dataclass

from PyQt6.QtGui import QImage

from sightreader import (
    DIGIT_ASPECT,
    GrayImage,
    _equal_split,
    _vector,
    split_digits,
)

REFERENCE_HEIGHT = 1080

# Pixels per degree at 1080p and HUD scale 1.
DEGREE_SPACING = 6.345

# Half the strip's width, and the band searched for its tick row: from
# SEARCH_TOP to SEARCH_BOTTOM px above the bottom of the screen (1080p).
STRIP_HALF_WIDTH = 400
SEARCH_TOP = 110
SEARCH_BOTTOM = 15

# A pixel is tick ink when it is this much brighter than its row's median
# and at least TICK_MIN bright; a tick is at most TICK_MAX_WIDTH px wide.
TICK_CONTRAST = 60
TICK_MIN = 140
TICK_MAX_WIDTH = 4

# Ticks needed for a reading, and the largest misfit of one tick to the
# fitted line (in degrees) before it is dropped as not a tick.
MIN_TICKS = 25
MAX_RESIDUAL = 0.25

# Tick lengths relative to the 1-degree ticks: 5-degree ticks are longer
# than MEDIUM, 15-degree ticks longer than LONG.
MEDIUM = 1.4
LONG = 2.0

# The bearing box around the centre (1080p px; the box is 32 x 20, the
# 1-degree ticks either side of it start 17 px from the centre).
BOX_HALF_WIDTH = 15
BOX_HALF_HEIGHT = 10

# The digits must read a bearing within this many degrees of the ticks'
# (the box shows whole degrees, rounded or cut).
DIGIT_AGREEMENT = 1.5

# A digit read below this match is no reading.
MIN_DIGIT_MATCH = 0.3


@dataclass(frozen=True)
class CompassReading:
    """The bearing at the screen centre.

    `degrees`: 0 <= degrees < 360; `spacing`: px per degree measured;
    `ticks`: ticks fitted; `residual`: their RMS misfit (degrees);
    `digits`: the box's bearing, or None when `near` was used instead.
    """

    degrees: float
    spacing: float
    ticks: int
    residual: float
    digits: int | None


def _bright_runs(row, left, threshold):
    """Centres (sub-pixel, weighted by brightness over the threshold) and
    widths of the runs of pixels at least `threshold` bright."""
    runs = []
    start = None

    for i, value in enumerate(bytes(row) + b"\0"):
        if value >= threshold:
            if start is None:
                start = i
        elif start is not None:
            weights = [row[j] - threshold + 1 for j in range(start, i)]
            centre = sum((start + k) * w for k, w in enumerate(weights)) / sum(weights)
            runs.append((left + centre, i - start))
            start = None

    return runs


def _row_threshold(row):
    median = sorted(row)[len(row) // 2]

    return max(TICK_MIN, median + TICK_CONTRAST)


# Byte tables mapping a grey level to 1 at or over a threshold, else 0.
_THRESHOLD_TABLES = [bytes(1 if v >= t else 0 for v in range(256)) for t in range(257)]


def _count_narrow_runs(row, threshold, width):
    """How many runs of bright pixels at most `width` wide the row has
    (bytes operations: this runs on every row of the search band)."""
    bits = row.translate(_THRESHOLD_TABLES[min(256, threshold)])

    return sum(1 for run in re.finditer(rb"\x01+", bits) if run.end() - run.start() <= width)


def find_tick_row(image, centre_x, scale):
    """(row, threshold) of the compass ticks: the row with the most narrow
    bright runs in the band at the bottom; None without one."""
    half = round(STRIP_HALF_WIDTH * scale)
    left, right = max(0, round(centre_x) - half), min(image.width, round(centre_x) + half)
    top = max(0, image.height - round(SEARCH_TOP * scale))
    bottom = max(top, image.height - round(SEARCH_BOTTOM * scale))
    width = max(2, round(TICK_MAX_WIDTH * scale))
    counts = []

    for y in range(top, bottom):
        row = image.row(y, left, right)
        threshold = _row_threshold(row)
        counts.append((_count_narrow_runs(row, threshold, width), y, threshold))

    if not counts:
        return None

    best = max(count for count, _, _ in counts)

    if best < MIN_TICKS:
        return None

    # The middle of the rows that cross (nearly) every tick
    rows = [(y, threshold) for count, y, threshold in counts if count >= 0.8 * best]

    return rows[len(rows) // 2]


def _tick_length(image, x, y, threshold):
    """Rows of column x that are tick ink, up and down from row y."""
    length = 1

    for step in (-1, 1):
        row = y + step

        while 0 <= row < image.height and image.pixel(x, row) >= threshold:
            length += 1
            row += step

    return length


def _fit(points):
    """Least-squares line x = x0 + spacing * n through (n, x) points."""
    count = len(points)
    mean_n = sum(n for n, _ in points) / count
    mean_x = sum(x for _, x in points) / count
    var = sum((n - mean_n) ** 2 for n, _ in points)

    if var == 0:
        return None

    spacing = sum((n - mean_n) * (x - mean_x) for n, x in points) / var

    return mean_x - spacing * mean_n, spacing


# Spacings tried for the tick grid, relative to DEGREE_SPACING at the
# expected scale: a coarse search in steps of SPACING_STEP (relative),
# then a fine one in steps of FINE_STEP around its best.
SPACING_RANGE = (0.7, 1.4)
SPACING_STEP = 0.004
FINE_STEP = 0.0002


def _grid(xs, low, high):
    """(x0, spacing) of the evenly spaced grid the points fit best.

    The spacing maximises the periodogram |sum exp(2 pi i x / spacing)|
    over low..high, so ticks hidden or missing anywhere (the box, a map
    marker) cannot shift the count between two groups of ticks; x0 is the
    grid's phase there.
    """
    def search(low, high, step):
        best = None
        spacing = low

        while spacing <= high:
            k = 2 * math.pi / spacing
            real = sum(math.cos(k * x) for x in xs)
            imag = sum(math.sin(k * x) for x in xs)
            power = real * real + imag * imag

            if best is None or power > best[0]:
                best = (power, spacing, math.atan2(imag, real))

            spacing *= 1 + step

        return best

    # Relative to the first point: the phase does not wind up over the
    # strip's absolute position (a coarse step must keep the peak).
    origin = xs[0]
    xs = [x - origin for x in xs]
    _, coarse, _ = search(low, high, SPACING_STEP)
    _, spacing, phase = search(coarse * (1 - SPACING_STEP), coarse * (1 + SPACING_STEP), FINE_STEP)

    return origin + phase / (2 * math.pi) * spacing, spacing


def find_ticks(image, centre_x, scale):
    """The compass ticks as [(index, x, length)] with the fitted line
    (x0, spacing), or None.

    x is the tick's sub-pixel centre (pixel centres at +0.5, as
    `centre_x`); index n counts degrees along the strip from the grid
    origin; length is the tick's height in px. The bearing box's digits
    are left out.
    """
    found = find_tick_row(image, centre_x, scale)

    if found is None:
        return None

    y, threshold = found
    half = round(STRIP_HALF_WIDTH * scale)
    left, right = max(0, round(centre_x) - half), min(image.width, round(centre_x) + half)
    width = max(2, round(TICK_MAX_WIDTH * scale))
    box = (BOX_HALF_WIDTH + 1) * scale
    runs = [x + 0.5 for x, run_width in _bright_runs(image.row(y, left, right), left, threshold)
            if run_width <= width and abs(x + 0.5 - centre_x) > box]

    if len(runs) < MIN_TICKS:
        return None

    low, high = (DEGREE_SPACING * scale * f for f in SPACING_RANGE)
    x0, spacing = _grid(runs, low, high)
    points = [(round((x - x0) / spacing), x) for x in runs]
    points = [(n, x) for n, x in points if abs(x - x0 - spacing * n) <= MAX_RESIDUAL * spacing]

    if len(points) < MIN_TICKS:
        return None

    line = _fit(points)

    if line is None:
        return None

    ticks = [(n, x, _tick_length(image, math.floor(x), y, threshold)) for n, x in points]

    return ticks, line


def _mode(values):
    counts = {}

    for value in values:
        counts[value] = counts.get(value, 0) + 1

    return max(counts, key=counts.get) if counts else None


# Share of the ticks that must have the length their place calls for
# (every 5th longer, every 15th longest, the rest short).
PATTERN_AGREEMENT = 0.85


def fifteen_phase(ticks):
    """Index modulo 15 of the 15-degree ticks, or None.

    The lengths must follow the compass's pattern: every 15th tick the
    longest, every 5th (the others) medium, the rest short, for at least
    PATTERN_AGREEMENT of the ticks and two 15-degree ticks. Anything else
    with evenly spaced bright lines (a sight's scale) is not the compass.
    """
    lengths = sorted(length for _, _, length in ticks)
    short = lengths[len(lengths) // 3]
    long_ticks = [n for n, _, length in ticks if length >= LONG * short]

    if len(long_ticks) < 2:
        return None

    phase = _mode(n % 15 for n in long_ticks)

    def kind(length):
        return 2 if length >= LONG * short else 1 if length >= MEDIUM * short else 0

    def expected(n):
        return 2 if n % 15 == phase else 1 if n % 5 == phase % 5 else 0

    agree = sum(kind(length) == expected(n) for n, _, length in ticks)

    if agree < PATTERN_AGREEMENT * len(ticks) or sum(expected(n) == 2 for n, _, _ in ticks) < 2:
        return None

    return phase


class DigitReader:
    """Reads the bearing box's three digits (light on the dark box) with
    the sight reader's digit pictures (sightreader.LabelTemplates)."""

    def __init__(self, templates):
        self.templates = templates

    def read(self, image, centre_x, row, scale):
        """(bearing in whole degrees, mean digit match) or None."""
        half_width = round(BOX_HALF_WIDTH * scale)
        half_height = round(BOX_HALF_HEIGHT * scale)
        left = max(0, round(centre_x) - half_width)
        right = min(image.width, round(centre_x) + half_width)
        top = max(0, row - half_height)
        bottom = min(image.height, row + half_height + 1)

        if right - left < 6 or bottom - top < 6:
            return None

        # Dark digits on light, as the sight's labels and the templates
        crop = bytes(255 - v for v in image.crop(left, top, right, bottom))
        box = GrayImage(crop, right - left, bottom - top, right - left)
        values = sorted(crop)
        level = (values[len(values) // 2] + values[len(values) // 100]) / 2

        if values[len(values) // 2] - values[len(values) // 100] < 40:
            return None

        ink_rows = [r for r in range(box.height)
                    if any(v < level for v in box.row(r, 0, box.width))]
        ink_columns = [c for c in range(box.width)
                       if any(v < level for v in box.column(c, 0, box.height))]

        if not ink_rows or not ink_columns:
            return None

        digit_box = (ink_columns[0], ink_rows[0], ink_columns[-1] + 1, ink_rows[-1] + 1)
        height = digit_box[3] - digit_box[1]

        if (digit_box[2] - digit_box[0]) < 2 * DIGIT_ASPECT * height:
            return None

        best = None

        for digits in (split_digits(box, digit_box, level), _equal_split(box, digit_box, 3, level)):
            if len(digits) != 3:
                continue

            vectors = []

            for a, b, c, d in digits:
                picture = QImage(box.crop(a, b, c, d), c - a, d - b, c - a, QImage.Format.Format_Grayscale8)
                vectors.append(_vector(picture))

            matches = [[sum(p * q for p, q in zip(vector, template)) for template in self.templates.digits]
                       for vector in vectors]
            hundreds = max(range(4), key=lambda d: matches[0][d])
            tens = max(range(10), key=lambda d: matches[1][d])
            ones = max(range(10), key=lambda d: matches[2][d])
            value = 100 * hundreds + 10 * tens + ones
            match = (matches[0][hundreds] + matches[1][tens] + matches[2][ones]) / 3

            if value < 360 and (best is None or match > best[1]):
                best = (value, match)

        if best is None or best[1] < MIN_DIGIT_MATCH:
            return None

        return best


def _circular(a, b):
    """Signed smallest difference a - b in degrees (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def read_compass(image, centre_x, scale, digits=None, near=None):
    """The bearing at `centre_x` of a grab of the screen's bottom
    (sightreader.GrayImage), or None.

    `centre_x` is continuous: the left edge of pixel column c is at c, its
    centre at c + 0.5, so a screen's centre is width / 2.

    `scale`: screen height / 1080 (the HUD scale is measured from the tick
    spacing within a factor of 1.6 of it). `digits`: a DigitReader for the
    box; `near`: a bearing the reading is known to be within 7 degrees of
    (a recent reading while laying), used when the box cannot be read.
    """
    found = find_ticks(image, centre_x, scale)

    if found is None:
        return None

    ticks, (x0, spacing) = found
    measured = spacing / DEGREE_SPACING

    if not scale / 1.6 <= measured <= scale * 1.6:
        return None

    phase = fifteen_phase(ticks)

    if phase is None:
        return None

    residual = math.sqrt(sum((x - x0 - spacing * n) ** 2 for n, x, _ in ticks) / len(ticks)) / spacing

    # The bearing modulo 15: tick `phase` is at a multiple of 15 degrees
    within = (centre_x - x0) / spacing - phase

    box = None

    if digits is not None:
        row = find_tick_row(image, centre_x, measured)
        box = digits.read(image, centre_x, row[0], measured) if row else None

    coarse = box[0] if box is not None else near

    if coarse is None:
        return None

    turns = round((coarse - within) / 15.0)
    degrees = (within + 15.0 * turns) % 360.0

    if box is not None and abs(_circular(degrees, coarse)) > DIGIT_AGREEMENT:
        # The digits disagree with the ticks: trust neither
        return None

    if box is None and abs(_circular(degrees, coarse)) > 7.0:
        return None

    return CompassReading(degrees, spacing, len(ticks), residual, box[0] if box else None)
