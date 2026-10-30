"""The bearing read off the HUD compass on the screen.

Squad's compass (USQCompassMK2, game build 26005357) runs along the bottom
centre of the screen: a tick every 15 degrees (letters at N, NE, E...),
labels under them, and under the centre the current bearing in bold. On
the mortar's own view the bearing has a tenth of a degree ("182.2",
"%.1f" of the camera's yaw, rounded); elsewhere whole degrees ("182",
truncated). The number follows the camera at once, while the strip lags
behind a turn (its yaw is smoothed), so the number is the reading and the
strip only confirms it: its ticks must sit where the number puts them, and
the labels under the marks near the centre must be the ones it implies,
where it puts them. Ticks alone only pin the bearing modulo 15 degrees: a
tens digit misread by 30, 60 or 90 passed them every time. A label is
read like the number and is placed within a degree of its mark, so the
labels also say the units digit when foliage hides the ticks or the strip
is drawn without them.

What the checks leave (measured by replacing each digit of the numbers of
245 real frames with every other digit, see tests/test_compassreader):
a hundreds or tens digit misread is never accepted; a units digit that is 2
or more degrees off is rejected while the barrel is still (STILL_TOLERANCE,
the lay's confirm and settle phases), 1 or more on the mortar's view with
tenths (STILL_TENTHS_TOLERANCE), 3 or more on a strip that may lag behind a
turn (TICK_TOLERANCE, the default); a tenths digit is not checked (an error
under 1 degree; the lay asks for two readings, of two grabs, that agree,
which a misread of one frame does not, though one the reader makes on every
frame alike does). During a turn the lay takes the number alone
(read_compass with no tolerance) and relies on its continuity check.

Measured on 1080p frames of the game (Oct 2026): the bearing's digits are
12 px tall with their centre 22.5 px above the bottom of the screen, about
8 px wide; the labels are 9 px tall; the 15-degree ticks are 6.33 px per
degree apart, centred 43 px above the bottom. Only 16:9 screens are
supported; every size scales with the screen height and with the HUD scale
(HUD_SCALES are tried).

The mortar's view shows its elevation scale too, so one frame gives both
axes of a lay (see sightlay).
"""

from dataclasses import dataclass

from PyQt6.QtGui import QImage

from sightreader import DIGIT_ASPECT, _vector

# The bearing number: centre above the bottom, half its height, half the
# width searched for it either side of the centre (1080p px).
TEXT_FROM_BOTTOM = 22.5
TEXT_HALF_HEIGHT = 9
TEXT_HALF_WIDTH = 45

# The number's ink is centred on the screen's centre within NUMBER_SYMMETRY
# px (measured -1.5 to +0.5 on 245 real frames) and is NUMBER_WIDTH px wide
# (22-26 for "182", 36-39 for "182.2", more when it is packed loosely); a
# label of the strip or foliage beside it breaks the symmetry. The number is
# cut out of at most MAX_RUNS runs of ink (digits and a point; touching
# digits are one run).
NUMBER_SYMMETRY = 2
NUMBER_WIDTH = (16, 50)
MAX_RUNS = 5

# The ink: halfway between the box's median grey and its brightest, which
# must be this much brighter than the median (the HUD's white against a
# snow-white scene of 235 is still 20 levels brighter, and real frames were
# at 44 to 46 on the brightest scenes, 4 above the old limit of 40).
MIN_INK_CONTRAST = 12

# The strip: its ticks' row above the bottom, half the strip's width,
# px per degree (1080p), and a tick at most TICK_MAX_WIDTH px wide.
TICKS_FROM_BOTTOM = 43
STRIP_HALF_WIDTH = 400
DEGREE_SPACING = 6.33
TICK_MAX_WIDTH = 4

# The strip's ticks (and its labels) sit this many degrees after the number's
# bearing: measured on the mortar's own view, 0.46 to 0.64 degree on every
# frame with the barrel still, and the labels' ink within 0.8 degree of it
# on 99% of 870 labels.
STRIP_BIAS = 0.5

# Ticks (or the letters standing for them) that must be where the bearing
# puts the 15-degree marks, within a tolerance in degrees (TICK_TOLERANCE
# while the strip may lag behind a turn, STILL_TOLERANCE when it cannot,
# STILL_TENTHS_TOLERANCE for a still strip under a number with tenths, which
# the ticks follow within 0.14 degree of STRIP_BIAS: it rejects a units
# digit read one off, and every real frame of tests/data reads at it), and
# the share of all narrow ink on the row that must be (TICK_AGREEMENT: real
# frames have foliage on the row; SCALED_AGREEMENT at a HUD scale found by
# the search, where a wrong scale would otherwise do with the few ticks near
# the centre).
MIN_TICKS = 3
TICK_TOLERANCE = 2.5
STILL_TOLERANCE = 1.5
STILL_TENTHS_TOLERANCE = 0.8
TICK_AGREEMENT = 0.5
SCALED_AGREEMENT = 0.8

# The labels read under the strip's marks between LABEL_NEAR and LABEL_FAR
# degrees from the number (the game hides those within 6 degrees of the
# centre): at least MIN_LABELS must read as the marks' values, and more than
# read as other values; MIN_LABELS_WITHOUT_TICKS when the ticks are missing
# or lost in foliage (the mortar's view fades them out on some frames). A
# label is 9 px high and LABEL_WIDTH px wide, smaller and fainter than the
# number, so its digits are accepted from LABEL_MIN_MATCH (of 819 labels of
# the real frames 96% read right; the wrong readings mostly match below
# 0.5); only a label read at LABEL_CONFLICT_MATCH or better counts as another
# value, and the search for one stops at a reading matching LABEL_SURE_MATCH.
LABEL_NEAR = 12
LABEL_FAR = 40
LABEL_WIDTH = (12, 36)
MIN_LABELS = 1
MIN_LABELS_WITHOUT_TICKS = 3
LABEL_MIN_MATCH = 0.35
LABEL_CONFLICT_MATCH = 0.5
LABEL_SURE_MATCH = 0.65

# A label's ink is the HUD's white over foliage nearly as bright: its box is
# cut at these shares of the way from the median to the brightest, the best
# reading of the three taken (785 of 819 labels right, against 733 at one).
LABEL_INK_SHARES = (0.5, 0.65, 0.8)

# A number with any digit matching its picture below this is no reading.
MIN_DIGIT_MATCH = 0.5

# HUD scales of the compass tried, the usual one first.
HUD_SCALES = (1.0, 0.9, 1.1, 0.8, 1.25)

# How far above the bottom of the screen the compass reaches (1080p px),
# for callers grabbing it.
SEARCH_TOP = 70


@dataclass(frozen=True)
class CompassReading:
    """The bearing at the screen centre.

    `degrees`: 0 <= degrees < 360, the middle of what the number allows;
    `resolution`: 0.1 for "182.2" (the mortar's view), 1 for "182"
    (truncated: the bearing is 182 to 183, read as 182.5); `text`: the
    number as read; `ticks`, `labels`: strip ticks and labels that agreed
    with it (0 when the strip was not looked at, see read_compass).
    """

    degrees: float
    resolution: float
    text: str
    ticks: int
    labels: int


def _ink_table(level):
    return bytes(1 if v >= level else 0 for v in range(256))


def _bright_level(values, share=0.5):
    """Grey level `share` of the way from the background (median) to the
    brightest ink, or None when nothing is brighter by MIN_INK_CONTRAST."""
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    bright = ordered[-max(1, len(ordered) // 100)]

    if bright - median < MIN_INK_CONTRAST:
        return None

    return median + share * (bright - median)


def _runs(flags):
    """(start, end) of the runs of true values."""
    runs = []
    start = None

    for i, on in enumerate(list(flags) + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((start, i))
            start = None

    return runs


def _ink_runs(image, left, top, right, bottom, share=0.5):
    """(ink table, runs of columns with ink as (start, end)) of a box, or
    None when it holds no ink."""
    level = _bright_level(image.crop(left, top, right, bottom), share)

    if level is None:
        return None

    ink = _ink_table(level)
    columns = [image.column(c, top, bottom).translate(ink).count(1) > 0
               for c in range(left, right)]

    return ink, [(left + a, left + b) for a, b in _runs(columns)]


def _clusters(runs, centre, tolerance, widths, scale):
    """Consecutive runs (at most MAX_RUNS) whose span is within `widths`
    (1080p px) and centred within `tolerance` px of `centre`, the most
    central first."""
    smallest, largest = widths[0] * scale, widths[1] * scale
    found = []

    for first in range(len(runs)):
        for last in range(first, min(len(runs), first + MAX_RUNS)):
            width = runs[last][1] - runs[first][0]

            if width > largest:
                break

            offset = abs((runs[first][0] + runs[last][1]) / 2 - centre)

            if width >= smallest and offset <= tolerance:
                found.append((offset, runs[first:last + 1]))

    return [cluster for _, cluster in sorted(found, key=lambda item: item[0])]


class DigitReader:
    """Reads the compass number (light on the scene) with the sight
    reader's digit pictures (sightreader.LabelTemplates)."""

    def __init__(self, templates):
        self.templates = templates

    def _band(self, image, centre_x, half_width, scale):
        """(left, top, right, bottom) of the text's band around `centre_x`,
        or None when it does not fit the image."""
        half_height = round(TEXT_HALF_HEIGHT * scale)
        middle = image.height - TEXT_FROM_BOTTOM * scale
        left = max(0, round(centre_x) - half_width)
        right = min(image.width, round(centre_x) + half_width)
        top = max(0, round(middle) - half_height)
        bottom = min(image.height, round(middle) + half_height + 1)

        if right - left < 10 or bottom - top < 6:
            return None

        return left, top, right, bottom

    def read(self, image, centre_x, scale):
        """(text, value, resolution, match) of the number under the centre,
        or None; `match` is the worst of its digits' matches."""
        band = self._band(image, centre_x, round(TEXT_HALF_WIDTH * scale), scale)

        if band is None:
            return None

        found = _ink_runs(image, *band)

        if found is None:
            return None

        ink, runs = found
        best = None

        for cluster in _clusters(runs, centre_x, NUMBER_SYMMETRY * scale, NUMBER_WIDTH, scale):
            glyphs = self._glyphs(image, cluster, ink, band[1], band[3], scale)

            if glyphs is None:
                continue

            number = self._number(image, *glyphs)

            if number is not None and (best is None or number[3] > best[3]):
                best = number

        return best

    def read_label(self, image, centre_x, half_width, scale, wanted=()):
        """(value, match, x) of the three-digit label of the strip centred
        within `half_width` px of `centre_x` (its ink centred at x), or
        None: the best reading of LABEL_INK_SHARES; the search ends early on
        a reading among `wanted` values matching LABEL_SURE_MATCH or
        better."""
        band = self._band(image, centre_x, round(half_width + LABEL_WIDTH[1] / 2 * scale), scale)

        if band is None:
            return None

        best = None

        for share in LABEL_INK_SHARES:
            found = _ink_runs(image, *band, share)

            if found is None:
                continue

            ink, runs = found

            for cluster in _clusters(runs, centre_x, half_width, LABEL_WIDTH, scale):
                glyphs = self._glyphs(image, cluster, ink, band[1], band[3], scale)

                if glyphs is None or len(glyphs[0]) != 3 or "." in glyphs[0]:
                    continue

                text, matches = self._decode(image, *glyphs)

                if min(matches) < LABEL_MIN_MATCH:
                    continue

                found = (int(text), min(matches), (cluster[0][0] + cluster[-1][1]) / 2)

                if found[0] in wanted and found[1] >= LABEL_SURE_MATCH:
                    return found

                if best is None or found[1] > best[1]:
                    best = found

        return best

    def _glyphs(self, image, cluster, ink, top, bottom, scale):
        """(characters, text top, text bottom) of the ink in `cluster`'s
        columns: a character is a (left, right) pair of columns or ".";
        None when the ink is too low to be text."""
        rows = [r for r in range(top, bottom)
                if image.row(r, cluster[0][0], cluster[-1][1]).translate(ink).count(1)]

        if not rows:
            return None

        text_top, text_bottom = rows[0], rows[-1] + 1
        height = text_bottom - text_top

        if height < 6 * scale:
            return None

        characters = []

        for a, b in cluster:
            ink_rows = [r for r in range(text_top, text_bottom)
                        if image.row(r, a, b).translate(ink).count(1)]

            # The decimal point: low and narrow
            if ink_rows and ink_rows[0] >= text_top + 0.65 * height \
                    and b - a <= 0.6 * DIGIT_ASPECT * height:
                characters.append(".")
                continue

            # Touching digits are cut into equal parts
            count = max(1, round((b - a) / (DIGIT_ASPECT * height * 0.95)))

            for part in range(count):
                characters.append((a + (b - a) * part // count, a + (b - a) * (part + 1) // count))

        return characters, text_top, text_bottom

    def _decode(self, image, characters, top, bottom):
        """(text, matches of its digits) of the characters."""
        text = ""
        matches = []

        for character in characters:
            if character == ".":
                text += "."
                continue

            x0, x1 = character
            # Dark digits on light, as the templates
            crop = bytes(255 - v for v in image.crop(x0, top, x1, bottom))
            picture = QImage(crop, x1 - x0, bottom - top, x1 - x0, QImage.Format.Format_Grayscale8)
            vector = _vector(picture)
            scores = [sum(p * q for p, q in zip(vector, template)) for template in self.templates.digits]
            digit = max(range(10), key=scores.__getitem__)
            text += str(digit)
            matches.append(scores[digit])

        return text, matches

    def _number(self, image, characters, top, bottom):
        """(text, value, resolution, match) of characters shaped like the
        compass number, or None."""
        shape = ["." if c == "." else "d" for c in characters]

        if shape == ["d", "d", "d", ".", "d"]:
            resolution = 0.1
        elif shape == ["d", "d", "d"]:
            resolution = 1.0
        else:
            return None

        text, matches = self._decode(image, characters, top, bottom)
        value = float(text)

        if min(matches) < MIN_DIGIT_MATCH or not 0 <= value <= 360:
            return None

        return text, value, resolution, min(matches)


def strip_ticks(image, centre_x, scale, degrees, tolerance=TICK_TOLERANCE, agreement=TICK_AGREEMENT):
    """How many ticks of the strip sit on the 15-degree marks `degrees`
    puts them at (within `tolerance` degrees); 0 when the row shows fewer
    than MIN_TICKS ticks to tell (the strip drawn without them); None when
    ticks are there but too few of them, or fewer than the share
    `agreement` of the row's narrow ink, sit on the marks (not the compass,
    or another bearing), or when `centre_x` leaves no strip in the image."""
    row = round(image.height - TICKS_FROM_BOTTOM * scale)

    if not 0 <= row < image.height:
        return None

    half = round(STRIP_HALF_WIDTH * scale)
    left, right = max(0, round(centre_x) - half), min(image.width, round(centre_x) + half)

    if right - left < 2 * MIN_TICKS:
        return None

    values = image.row(row, left, right)
    level = _bright_level(values)

    if level is None:
        return 0

    width = max(2, round(TICK_MAX_WIDTH * scale))
    ink = values.translate(_ink_table(level))
    centres = [left + (a + b) / 2 for a, b in _runs(v == 1 for v in ink) if b - a <= width]

    if len(centres) < MIN_TICKS:
        return 0
    spacing = DEGREE_SPACING * scale
    agreeing = []

    for x in centres:
        angle = degrees + (x - centre_x) / spacing - STRIP_BIAS

        if abs((angle + 7.5) % 15.0 - 7.5) <= tolerance:
            agreeing.append(x)

    if len(agreeing) < agreement * len(centres) or len(agreeing) < MIN_TICKS:
        return None

    return len(agreeing)


def strip_labels(image, centre_x, scale, digits, degrees, tolerance=TICK_TOLERANCE):
    """(agreeing, disagreeing) labels of the strip: those under the marks
    LABEL_NEAR to LABEL_FAR degrees from `degrees` that read as the marks'
    values (0 and 360 are the same mark) and sit within `tolerance` degrees
    of where the strip puts them, and those that read as another value. A
    label that cannot be read is neither; the count stops at
    MIN_LABELS_WITHOUT_TICKS agreeing."""
    spacing = DEGREE_SPACING * scale
    # A lagging strip moves its labels by up to the tolerance
    half_width = (tolerance + 0.5) * spacing
    agree = disagree = 0

    for mark in range(15 * int((degrees - LABEL_FAR) // 15), int(degrees + LABEL_FAR) + 1, 15):
        if not LABEL_NEAR <= abs(mark - degrees) <= LABEL_FAR:
            continue

        x = centre_x + (mark - degrees + STRIP_BIAS) * spacing
        # North is labelled 000 or 360
        wanted = (0, 360) if mark % 360 == 0 else (mark % 360,)
        label = digits.read_label(image, x, half_width, scale, wanted)

        if label is None:
            continue

        # A label's ink is placed within a degree of where the strip puts it
        if label[0] in wanted and abs(label[2] - x) <= tolerance * spacing:
            agree += 1
        elif label[1] >= LABEL_CONFLICT_MATCH:
            disagree += 1

        if agree >= MIN_LABELS_WITHOUT_TICKS:
            break

    return agree, disagree


def read_compass(image, centre_x, scale, digits, tolerance=TICK_TOLERANCE, tenths_tolerance=None):
    """The bearing at `centre_x` of a grab of the screen's bottom
    (sightreader.GrayImage), or None.

    `centre_x` is continuous (a screen's centre is width / 2); `scale` is
    the screen height / 1080 (the HUD's own scale is searched, HUD_SCALES);
    `digits` a DigitReader. The strip must confirm the number within
    `tolerance` degrees (TICK_TOLERANCE where it may lag behind a turn,
    STILL_TOLERANCE when the camera is still), or `tenths_tolerance` when
    given and the number has tenths (STILL_TENTHS_TOLERANCE when still);
    `tolerance` None takes the number alone, for a strip known to lag, when
    the caller checks it another way.
    """
    for hud in HUD_SCALES:
        agreement = TICK_AGREEMENT if hud == 1.0 else SCALED_AGREEMENT
        reading = _read(image, centre_x, scale * hud, digits, tolerance, agreement, tenths_tolerance)

        if reading is not None:
            return reading

    return None


def _read(image, centre_x, scale, digits, tolerance, agreement, tenths_tolerance=None):
    """read_compass at one scale."""
    number = digits.read(image, centre_x, scale)

    if number is None:
        return None

    text, value, resolution, _ = number

    # "%.1f" rounds; whole degrees are cut, the bearing is n to n + 1
    degrees = (value if resolution < 1 else value + 0.5) % 360.0

    if tolerance is None:
        return CompassReading(degrees, resolution, text, 0, 0)

    if tenths_tolerance is not None and resolution < 1:
        tolerance = tenths_tolerance

    ticks = strip_ticks(image, centre_x, scale, degrees, tolerance, agreement)
    agree, disagree = strip_labels(image, centre_x, scale, digits, degrees, tolerance)

    # The ticks may be missing (the mortar's view fades them out) or lost in
    # foliage: then the labels, placed as exactly as ticks, have to say it
    # is the strip
    needed = MIN_LABELS if ticks else MIN_LABELS_WITHOUT_TICKS

    if agree < needed or agree <= disagree:
        return None

    return CompassReading(degrees, resolution, text, ticks or 0, agree)
