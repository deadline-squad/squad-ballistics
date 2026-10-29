"""Reads the elevation off the mortar sight on the screen.

The sight (the game's MortarReticle widget) shows the elevation on a scale
left of the centre: a tick every mil, a longer one every 5, a longer one
with a label every 10 (the label is the elevation in mils), and the scale
moves behind a triangle pointer on the screen's centre line:

    830 ────────────┐
              ──────│      ticks end a few pixels left of the scale's
              ──────│      edge line; the pointer's tip touches them
          ──────────│
              ──────│◀───  pointer, on the screen's centre line

The reading:

1. the edge line of the scale, found near the centre line as a dark column
   with a bright gap on either side (`find_edge`), then followed row by row
   (it is an arc, `trace_edge`);
2. the ticks crossing a line just left of the edge, with sub-pixel centres
   (`find_ticks`);
3. the labels of the 10-mil ticks, decoded together: their values go up by
   10 per label upwards, so the sequence of values that best matches the
   pictures of all of them wins (`decode_labels`);
4. the elevation at the pointer, interpolated between the ticks around it.

Geometry is measured in pixels on 1080p frames of the 81 mm mortar sight
(REFERENCE_HEIGHT) and scales with the screen height, as the game scales its
HUD; a sight drawn at another HUD scale is found from its tick spacing.
Pixels come as bytes of an 8-bit grey image (`GrayImage`), read with bytes
operations, which run in C: a reading takes 10-30 ms without numpy.
"""

import math
import os
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter
)

from utils import resource_path

REFERENCE_HEIGHT = 1080

# Where the scale's edge is looked for, in screen heights left of the centre.
EDGE_SEARCH = (0.45, 0.12)

# Rows read above and below the pointer, in screen heights: about 18 mils,
# so 3 or 4 labels.
WINDOW = 0.13

# Rows the pointer covers on either side of the centre line (1080p px).
POINTER_HALF = 10

# Edge line width and the bright gaps on either side of it, and the rows
# above and below the pointer it is first looked for in (1080p px).
EDGE_WIDTH = 2
EDGE_GAP = 4
EDGE_BAND = 40

# Columns left of the edge: every tick crosses TICK_PROBE, only the 5- and
# 10-mil ticks reach past SHORT_TICK (1080p px; the ticks are about 32, 56
# and 60 long).
TICK_PROBE = 12
SHORT_TICK = 45

# Label box left of a 10-mil tick's left end (1080p px).
LABEL_GAP = 2
LABEL_WIDTH = 70
LABEL_HALF_HEIGHT = 14
LABEL_SPACE = 10

# Grey levels: ticks, the edge and the pointer are darker than DARK; the
# scale is lighter. A label's ink is at least MIN_INK_CONTRAST darker than
# the scale around it (see ink_level).
DARK = 110
MIN_INK_CONTRAST = 40

# Column dark fractions telling the edge line, the gaps and the ticks.
EDGE_FILL = 0.85
GAP_FILL = 0.12
TICK_FILL = (0.12, 0.75)

# Ticks this far from the median spacing (fraction) are not in the
# sequence: a label's ink, a gap, two ticks seen as one.
SPACING_TOLERANCE = 0.25

# Tick spacing of a mil at 1080p (px). A sight whose spacing is more than
# HUD_TOLERANCE off is drawn at another HUD scale; HUD_SCALES are tried
# when the scale is not found at all.
MIL_SPACING = 8.2
HUD_TOLERANCE = 0.1
HUD_SCALES = (1.0, 0.8, 1.25)

# Digits are compared at this size; a digit is about DIGIT_ASPECT times as
# wide as it is high. Labels are decoded among LABEL_VALUES: the mortar's
# 800-1580 mils and the labels seen around them.
DIGIT_SIZE = (10, 14)
DIGIT_ASPECT = 0.68
LABEL_VALUES = range(760, 1630, 10)

# Decoding fails below this mean match (normalised cross-correlation), or
# when the next best sequence of values matches within MIN_MARGIN.
MIN_MATCH = 0.3
MIN_MARGIN = 0.02

FONT_FILE = os.path.join("assets", "fonts", "RobotoCondensed-Digits.ttf")


@dataclass(frozen=True)
class GrayImage:
    """An 8-bit grey image: `data[y * stride + x]`."""

    data: bytes
    width: int
    height: int
    stride: int

    @classmethod
    def from_qimage(cls, image):
        gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
        stride = gray.bytesPerLine()
        data = bytes(gray.constBits().asarray(stride * gray.height()))

        return cls(data, gray.width(), gray.height(), stride)

    def pixel(self, x, y):
        return self.data[y * self.stride + x]

    def column(self, x, top, bottom):
        """Grey levels of column `x`, rows top..bottom-1."""
        start = top * self.stride + x
        return self.data[start:bottom * self.stride + x:self.stride]

    def row(self, y, left, right):
        start = y * self.stride
        return self.data[start + left:start + right]

    def crop(self, left, top, right, bottom):
        """The rectangle as a row-major bytes string."""
        return b"".join(self.row(y, left, right) for y in range(top, bottom))


@dataclass(frozen=True)
class Tick:
    y: float        # sub-pixel centre where it crosses the tick probe column
    long: bool      # a 5- or 10-mil tick
    left: tuple     # (x, y) of its left end


@dataclass(frozen=True)
class Reading:
    """The elevation at the pointer.

    `mils`: the reading; `labels`: labels decoded; `match`: their mean
    match to the decoded values (1 is a perfect match); `margin`: how much
    better than the next best sequence of values (0 is a tie).
    """

    mils: float
    labels: int
    match: float
    margin: float


def _dark_table(threshold):
    return bytes(1 if value < threshold else 0 for value in range(256))


DARK_TABLE = _dark_table(DARK)


def dark_fraction(values):
    if not values:
        return 0.0

    return values.translate(DARK_TABLE).count(1) / len(values)


def find_edge(image, centre_x, centre_y, scale):
    """x of the scale's edge line (its left column) near the centre line,
    or None.

    Columns are scored over the rows just above and below the pointer: the
    edge line is dark in all of them, the gaps on either side of it in none,
    and the tick ends left of the gap in some. The rows are few because the
    edge is an arc.
    """
    pointer = round(POINTER_HALF * scale)
    band = round(EDGE_BAND * scale)
    screen = REFERENCE_HEIGHT * scale
    left = max(0, round(centre_x - EDGE_SEARCH[0] * screen))
    right = min(image.width - 1, round(centre_x - EDGE_SEARCH[1] * screen))
    fills = {}

    def fill(x):
        if x < 0 or x >= image.width:
            return 1.0

        if x not in fills:
            above = image.column(x, max(0, centre_y - pointer - band), centre_y - pointer)
            below = image.column(x, centre_y + pointer + 1,
                                 min(image.height, centre_y + pointer + 1 + band))
            fills[x] = dark_fraction(above + below)

        return fills[x]

    width = max(1, round(EDGE_WIDTH * scale))
    gap = max(2, round(EDGE_GAP * scale))
    probe = round(TICK_PROBE * scale)

    for x in range(right, left, -1):
        # The left column of the line
        if fill(x) < EDGE_FILL or fill(x - 1) >= EDGE_FILL:
            continue

        gap_left = min(fill(x - offset) for offset in range(1, gap))
        gap_right = min(fill(x + width + offset) for offset in range(0, gap - 1))

        if gap_left <= GAP_FILL and gap_right <= GAP_FILL \
                and TICK_FILL[0] <= fill(x - probe) <= TICK_FILL[1]:
            return x

    return None


def trace_edge(image, edge, centre_y, scale):
    """The edge line's x in every row of the window, as (top row, list).

    The line is followed up and down from the centre: in each row, the dark
    pixel with a bright one on its left nearest to the row before.
    """
    window = round(WINDOW * REFERENCE_HEIGHT * scale)
    top = max(0, centre_y - window)
    bottom = min(image.height, centre_y + window)
    xs = [edge] * (bottom - top)
    reach = 2

    def follow(rows):
        x = edge

        for y in rows:
            candidates = [
                c for c in range(x - reach, x + reach + 1)
                if 0 < c < image.width
                and image.pixel(c, y) < DARK <= image.pixel(c - 1, y)
            ]

            if candidates:
                x = min(candidates, key=lambda c: abs(c - x))

            xs[y - top] = x

    follow(range(centre_y, top - 1, -1))
    follow(range(centre_y, bottom))

    return top, xs


def find_pointer(image, edge, centre_y, scale):
    """Row of the pointer's tip: the centre of the dark rows in the gap
    right of the edge line, near the centre line; `centre_y` if none."""
    x = edge + max(1, round(EDGE_WIDTH * scale)) + max(1, round(EDGE_GAP * scale / 2))
    reach = round(3 * POINTER_HALF * scale)
    top = max(0, centre_y - reach)
    values = image.column(x, top, min(image.height, centre_y + reach + 1))
    rows = [top + i for i, value in enumerate(values) if value < DARK]

    if not rows:
        return float(centre_y)

    return (rows[0] + rows[-1]) / 2


def _trace_left(image, x, y, length):
    """Follow a dark line leftwards from (x, y), a row up or down per step.

    Returns the (x, y) of its last dark pixel.
    """
    for _ in range(length):
        candidates = [
            (image.pixel(x - 1, row), row)
            for row in (y, y - 1, y + 1)
            if 0 <= row < image.height and x > 0
        ]

        if not candidates:
            break

        value, row = min(candidates)

        if value >= DARK:
            break

        x, y = x - 1, row

    return x, y


def find_ticks(image, edge, centre_y, scale):
    """Ticks crossing the probe line (TICK_PROBE left of the traced edge),
    top to bottom."""
    top, edges = trace_edge(image, edge, centre_y, scale)
    probe = round(TICK_PROBE * scale)
    xs = [max(0, x - probe) for x in edges]
    values = bytes(image.pixel(x, top + i) for i, x in enumerate(xs))

    background = sorted(values)[len(values) // 2]
    ticks = []
    row = 0

    while row < len(values):
        if values[row] >= DARK:
            row += 1
            continue

        end = row
        while end < len(values) and values[end] < DARK:
            end += 1

        # Weighted centre, with the half-dark rows on either side
        first, last = max(0, row - 1), min(len(values), end + 1)
        weights = [max(0, background - values[i]) for i in range(first, last)]
        total = sum(weights)
        centre = sum((first + i) * w for i, w in enumerate(weights)) / total \
            if total else (row + end - 1) / 2

        middle = (row + end - 1) // 2
        left = _trace_left(image, xs[middle], top + middle, round(2 * LABEL_WIDTH * scale))
        long = xs[middle] - left[0] >= (SHORT_TICK - TICK_PROBE) * scale
        ticks.append(Tick(top + centre, long, left))
        row = end

    return ticks


def ink_level(image, left, top, right, bottom):
    """Grey level between a label's ink and the scale behind it, or None if
    the box holds no ink.

    The labels' grey is lighter where they are blurred (thin strokes of a
    small label, a lower render scale), so the level is taken from the box:
    halfway between its background (the median) and its darkest pixels.
    """
    values = sorted(image.crop(left, top, right, bottom))
    background = values[len(values) // 2]
    darkest = values[len(values) // 100]

    if background - darkest < MIN_INK_CONTRAST:
        return None

    return (background + darkest) / 2


def label_box(image, tick, scale):
    """Bounding box of the label left of a tick and its ink level, as
    (box, level), or None.

    The label is the ink right of a column gap, starting just left of the
    tick's end.
    """
    x, y = tick.left
    right = x - round(LABEL_GAP * scale)
    left = max(0, right - round(LABEL_WIDTH * scale))
    half = round(LABEL_HALF_HEIGHT * scale)
    top, bottom = max(0, y - half), min(image.height, y + half + 1)

    if right <= left or bottom <= top:
        return None

    level = ink_level(image, left, top, right, bottom)

    if level is None:
        return None

    ink = _dark_table(level)
    columns = [image.column(c, top, bottom).translate(ink).count(1) > 0
               for c in range(left, right)]

    # The label starts within a gap of the tick, ends at a gap
    space = max(2, round(LABEL_SPACE * scale))
    start = None

    for i in range(len(columns) - 1, -1, -1):
        if columns[i]:
            start = i
            break

        if len(columns) - 1 - i > space:
            return None

    if start is None:
        return None

    end = start
    blank = 0

    for i in range(start, -1, -1):
        if columns[i]:
            end, blank = i, 0
        else:
            blank += 1

            if blank > space:
                break

    # Ink up to the box's left edge: the sight's dark rim, not a label
    if end == 0:
        return None

    box_left, box_right = left + end, left + start + 1
    rows = [r for r in range(top, bottom)
            if image.row(r, box_left, box_right).translate(ink).count(1)]

    if not rows:
        return None

    return (box_left, rows[0], box_right, rows[-1] + 1), level


def _normalised(values):
    """Zero mean, unit norm (for the normalised cross-correlation)."""
    mean = sum(values) / len(values)
    centred = [v - mean for v in values]
    norm = math.sqrt(sum(v * v for v in centred))

    return [v / norm for v in centred] if norm else centred


def _vector(image):
    """A grey QImage resized to DIGIT_SIZE, normalised."""
    width, height = DIGIT_SIZE
    scaled = image.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)

    return _normalised(list(GrayImage.from_qimage(scaled).crop(0, 0, width, height)))


def _ink_rows(image, left, right, top, bottom, ink):
    rows = [r for r in range(top, bottom) if image.row(r, left, right).translate(ink).count(1)]

    return (rows[0], rows[-1] + 1) if rows else None


def split_digits(image, box, level):
    """Boxes of a label's digits, left to right.

    A digit is a run of columns with ink; a run as wide as several digits
    (touching glyphs) is cut into equal parts.
    """
    left, top, right, bottom = box
    ink = _dark_table(level)
    filled = [image.column(c, top, bottom).translate(ink).count(1) > 0
              for c in range(left, right)]
    runs = []
    start = None

    for i, on in enumerate(filled + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((left + start, left + i))
            start = None

    digit_width = DIGIT_ASPECT * (bottom - top)
    digits = []

    for run_left, run_right in runs:
        parts = max(1, round((run_right - run_left) / digit_width))

        for part in range(parts):
            a = run_left + (run_right - run_left) * part // parts
            b = run_left + (run_right - run_left) * (part + 1) // parts
            rows = _ink_rows(image, a, b, top, bottom, ink)

            if rows is not None:
                digits.append((a, rows[0], b, rows[1]))

    return digits


def _equal_split(image, box, count, level):
    """The box cut into `count` equal digit boxes (glyphs blurred together)."""
    left, top, right, bottom = box
    ink = _dark_table(level)
    digits = []

    for part in range(count):
        a = left + (right - left) * part // count
        b = left + (right - left) * (part + 1) // count
        rows = _ink_rows(image, a, b, top, bottom, ink)

        if rows is None:
            return []

        digits.append((a, rows[0], b, rows[1]))

    return digits


def digit_vectors(image, box, level):
    """Ways to read the label as digits: the digits found by
    `split_digits`, and the box cut into as many equal parts as the labels
    have digits. Each is a list of digit pictures, resized to DIGIT_SIZE and
    normalised."""
    splits = [split_digits(image, box, level)]
    splits += [_equal_split(image, box, count, level)
               for count in sorted({len(str(value)) for value in LABEL_VALUES})]
    readings = []

    for digits in splits:
        if not digits:
            continue

        vectors = []

        for left, top, right, bottom in digits:
            crop = QImage(image.crop(left, top, right, bottom), right - left, bottom - top,
                          right - left, QImage.Format.Format_Grayscale8)
            vectors.append(_vector(crop))

        readings.append(vectors)

    return readings


class LabelTemplates:
    """Pictures of the digits drawn with the sight's font (Roboto
    Condensed), dark on light like the scale, and the label values they are
    matched against.

    Needs a QGuiApplication (fonts).
    """

    def __init__(self, values=LABEL_VALUES):
        family = "sans-serif"
        font_id = QFontDatabase.addApplicationFont(resource_path(FONT_FILE))

        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)

            if families:
                family = families[0]

        font = QFont(family)
        font.setPixelSize(48)
        self.values = list(values)
        self.digits = [self._draw(font, str(digit)) for digit in range(10)]

    @staticmethod
    def _draw(font, text):
        image = QImage(160, 72, QImage.Format.Format_Grayscale8)
        image.fill(QColor(255, 255, 255))
        painter = QPainter(image)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        gray = GrayImage.from_qimage(image)
        ink = _dark_table(128)
        columns = [c for c in range(gray.width)
                   if gray.column(c, 0, gray.height).translate(ink).count(1)]
        top, bottom = _ink_rows(gray, 0, gray.width, 0, gray.height, ink)

        return _vector(image.copy(columns[0], top, columns[-1] - columns[0] + 1, bottom - top))

    def scores(self, readings):
        """Match of a label to every value: the best mean match of its digit
        pictures, over the ways to read it with as many digits as the value."""
        best = {}

        for vectors in readings:
            matches = [[sum(a * b for a, b in zip(vector, template)) for template in self.digits]
                       for vector in vectors]

            for value in self.values:
                text = str(value)

                if len(text) != len(matches):
                    continue

                score = sum(match[int(digit)] for match, digit in zip(matches, text)) / len(matches)
                best[value] = max(score, best.get(value, -1.0))

        return best


def decode_labels(steps, scores):
    """Values of labels `steps[i]` 10-mil steps above the first one.

    `scores[i]` maps every value to the match of label i. Returns
    (first value, mean match, margin over the next best first value), or
    None if no first value keeps every label among the scored values.
    """
    totals = []

    for value in scores[0]:
        matches = [score.get(value + 10 * step) for score, step in zip(scores, steps)]

        if any(match is None for match in matches):
            continue

        totals.append((sum(matches) / len(matches), value))

    if not totals:
        return None

    totals.sort(reverse=True)
    best, value = totals[0]
    margin = best - totals[1][0] if len(totals) > 1 else best

    return value, best, margin


def _sequence(ticks):
    """Ticks with their mil index (0 at the top, +1 per tick downwards),
    and the median spacing; ticks off the spacing are left out."""
    if len(ticks) < 3:
        return [], 0.0

    gaps = sorted(b.y - a.y for a, b in zip(ticks, ticks[1:]))
    spacing = gaps[len(gaps) // 2]

    if spacing <= 0:
        return [], 0.0

    indexed = [(0, ticks[0])]

    for tick in ticks[1:]:
        steps = (tick.y - indexed[-1][1].y) / spacing

        if abs(steps - round(steps)) > SPACING_TOLERANCE or round(steps) < 1:
            continue

        indexed.append((indexed[-1][0] + round(steps), tick))

    return indexed, spacing


def read_scale(image, centre_x, centre_y, scale, templates):
    """The elevation at the pointer, or None if the scale is not seen.

    `centre_x`, `centre_y`: the screen's centre in the image; `scale`:
    screen height / REFERENCE_HEIGHT. The sight may be drawn larger or
    smaller (the game's HUD scale): the scales of HUD_SCALES are tried, and
    a reading whose tick spacing shows another scale is read again at it.
    """
    for hud in HUD_SCALES:
        reading, spacing = _read(image, centre_x, centre_y, scale * hud, templates)

        if spacing:
            measured = spacing / MIL_SPACING

            if abs(measured / (scale * hud) - 1) > HUD_TOLERANCE:
                reading, _ = _read(image, centre_x, centre_y, measured, templates)

        if reading is not None:
            return reading

    return None


def _read(image, centre_x, centre_y, scale, templates):
    """read_scale at one scale: (Reading or None, tick spacing or 0)."""
    edge = find_edge(image, centre_x, centre_y, scale)

    if edge is None:
        return None, 0.0

    pointer = find_pointer(image, edge, centre_y, scale)
    indexed, spacing = _sequence(find_ticks(image, edge, centre_y, scale))

    labelled = []

    for index, tick in indexed:
        if not tick.long:
            continue

        label = label_box(image, tick, scale)

        if label is None:
            continue

        scores = templates.scores(digit_vectors(image, *label))

        if scores:
            labelled.append((index, scores))

    if not labelled:
        return None, spacing

    # Labels every 10 ticks; values go up by 10 per label upwards
    base = labelled[-1][0]
    steps = [round((base - index) / 10) for index, _ in labelled]
    decoded = decode_labels(steps, [scores for _, scores in labelled])

    if decoded is None:
        return None, spacing

    lowest, match, margin = decoded

    if match < MIN_MATCH or margin < MIN_MARGIN:
        return None, spacing

    # Mils of a tick: the bottom label's value plus one per tick above it
    def mils(index):
        return lowest + (base - index)

    above = [(index, tick) for index, tick in indexed if tick.y <= pointer]
    below = [(index, tick) for index, tick in indexed if tick.y > pointer]

    if above and below:
        (i, a), (j, b) = above[-1], below[0]
        value = mils(i) + (mils(j) - mils(i)) * (pointer - a.y) / (b.y - a.y)
    elif above:
        i, a = above[-1]
        value = mils(i) - (pointer - a.y) / spacing
    else:
        j, b = below[0]
        value = mils(j) + (b.y - pointer) / spacing

    return Reading(value, len(labelled), match, margin), spacing
