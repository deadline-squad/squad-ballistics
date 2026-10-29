"""The bearing read off the HUD compass on the screen.

Squad's compass (USQCompassMK2, game build 26005357) runs along the bottom
centre of the screen: a tick every 15 degrees (letters at N, NE, E...),
labels under them, and under the centre the current bearing in bold. On
the mortar's own view the bearing has a tenth of a degree ("182.2",
"%.1f" of the camera's yaw, rounded); elsewhere whole degrees ("182",
truncated). The number follows the camera at once, while the strip lags
behind a turn (its yaw is smoothed), so the number is the reading and the
strip only confirms it: its ticks must sit where the number puts them.

Measured on 1080p frames of the game (Oct 2026): the bearing's digits are
12 px tall with their centre 22.5 px above the bottom of the screen, about
8 px wide; the 15-degree ticks are 6.33 px per degree apart, centred 43 px
above the bottom. Only 16:9 screens are supported; every size scales with
the screen height.

The mortar's view shows its elevation scale too, so one frame gives both
axes of a lay (see sightlay).
"""

from dataclasses import dataclass

from PyQt6.QtGui import QImage

from sightreader import DIGIT_ASPECT, _vector

REFERENCE_HEIGHT = 1080

# The bearing number: centre above the bottom, half its height, half the
# width searched for it either side of the centre (1080p px).
TEXT_FROM_BOTTOM = 22.5
TEXT_HALF_HEIGHT = 9
TEXT_HALF_WIDTH = 45

# Characters of the number are at most this far apart (px at 1080p);
# further ink is a label of the strip.
CHARACTER_GAP = 4

# The ink: halfway between the box's median grey and its brightest, which
# must be this much brighter than the median.
MIN_INK_CONTRAST = 40

# The strip: its ticks' row above the bottom, half the strip's width,
# px per degree (1080p), and a tick at most TICK_MAX_WIDTH px wide.
TICKS_FROM_BOTTOM = 43
STRIP_HALF_WIDTH = 400
DEGREE_SPACING = 6.33
TICK_MAX_WIDTH = 4

# Ticks (or the letters standing for them) that must be where the bearing
# puts the 15-degree marks, within TICK_TOLERANCE degrees (the strip lags
# behind a turn), and the share of all narrow ink on the row that must be.
MIN_TICKS = 3
TICK_TOLERANCE = 3.0
TICK_AGREEMENT = 0.7

# A number read below this mean digit match is no reading.
MIN_DIGIT_MATCH = 0.5

# How far above the bottom of the screen the compass reaches (1080p px),
# for callers grabbing it.
SEARCH_TOP = 70


@dataclass(frozen=True)
class CompassReading:
    """The bearing at the screen centre.

    `degrees`: 0 <= degrees < 360, the middle of what the number allows;
    `resolution`: 0.1 for "182.2" (the mortar's view), 1 for "182"
    (truncated: the bearing is 182 to 183, read as 182.5); `text`: the
    number as read; `match`: its digits' mean match; `ticks`: strip ticks
    that agreed with it.
    """

    degrees: float
    resolution: float
    text: str
    match: float
    ticks: int


def _ink_table(level):
    return bytes(1 if v >= level else 0 for v in range(256))


def _bright_level(values):
    """Grey level between the background (median) and the brightest ink,
    or None when nothing is brighter by MIN_INK_CONTRAST."""
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    bright = ordered[-max(1, len(ordered) // 100)]

    if bright - median < MIN_INK_CONTRAST:
        return None

    return (median + bright) / 2


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


class DigitReader:
    """Reads the compass number (light on the scene) with the sight
    reader's digit pictures (sightreader.LabelTemplates)."""

    def __init__(self, templates):
        self.templates = templates

    def read(self, image, centre_x, scale):
        """(text, value, resolution, match) of the number under the centre,
        or None."""
        half_width = round(TEXT_HALF_WIDTH * scale)
        half_height = round(TEXT_HALF_HEIGHT * scale)
        middle = image.height - TEXT_FROM_BOTTOM * scale
        left = max(0, round(centre_x) - half_width)
        right = min(image.width, round(centre_x) + half_width)
        top = max(0, round(middle) - half_height)
        bottom = min(image.height, round(middle) + half_height + 1)

        if right - left < 10 or bottom - top < 6:
            return None

        level = _bright_level(image.crop(left, top, right, bottom))

        if level is None:
            return None

        ink = _ink_table(level)
        columns = [image.column(c, top, bottom).translate(ink).count(1) > 0
                   for c in range(left, right)]
        runs = [(left + a, left + b) for a, b in _runs(columns)]

        if not runs:
            return None

        # The number: the ink nearest the centre and what follows it closely
        gap = max(2, round(CHARACTER_GAP * scale))
        first = last = min(range(len(runs)), key=lambda i: abs((runs[i][0] + runs[i][1]) / 2 - centre_x))

        while first > 0 and runs[first][0] - runs[first - 1][1] <= gap:
            first -= 1

        while last < len(runs) - 1 and runs[last + 1][0] - runs[last][1] <= gap:
            last += 1

        cluster = runs[first:last + 1]
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

        return self._decode(image, characters, text_top, text_bottom)

    def _decode(self, image, characters, top, bottom):
        shape = ["." if c == "." else "d" for c in characters]

        if shape == ["d", "d", "d", ".", "d"]:
            resolution = 0.1
        elif shape == ["d", "d", "d"]:
            resolution = 1.0
        else:
            return None

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

        match = sum(matches) / len(matches)
        value = float(text)

        if match < MIN_DIGIT_MATCH or not 0 < value <= 360:
            return None

        return text, value, resolution, match


def strip_ticks(image, centre_x, scale, degrees):
    """How many ticks of the strip sit on the 15-degree marks `degrees`
    puts them at, or None when too few of them, or of the row's narrow
    ink, do (not the compass, or another bearing)."""
    row = round(image.height - TICKS_FROM_BOTTOM * scale)

    if not 0 <= row < image.height:
        return None

    half = round(STRIP_HALF_WIDTH * scale)
    left, right = max(0, round(centre_x) - half), min(image.width, round(centre_x) + half)
    values = image.row(row, left, right)
    level = _bright_level(values)

    if level is None:
        return None

    width = max(2, round(TICK_MAX_WIDTH * scale))
    ink = values.translate(_ink_table(level))
    centres = [left + (a + b) / 2 for a, b in _runs(v == 1 for v in ink) if b - a <= width]
    spacing = DEGREE_SPACING * scale
    agree = 0

    for x in centres:
        angle = degrees + (x - centre_x) / spacing

        if abs((angle + 7.5) % 15.0 - 7.5) <= TICK_TOLERANCE:
            agree += 1

    if agree < MIN_TICKS or agree < TICK_AGREEMENT * len(centres):
        return None

    return agree


def read_compass(image, centre_x, scale, digits):
    """The bearing at `centre_x` of a grab of the screen's bottom
    (sightreader.GrayImage), or None.

    `centre_x` is continuous (a screen's centre is width / 2); `scale` is
    the screen height / 1080; `digits` a DigitReader.
    """
    number = digits.read(image, centre_x, scale)

    if number is None:
        return None

    text, value, resolution, match = number

    # "%.1f" rounds; whole degrees are cut, the bearing is n to n + 1
    degrees = (value if resolution < 1 else value + 0.5) % 360.0
    ticks = strip_ticks(image, centre_x, scale, degrees)

    if ticks is None:
        return None

    return CompassReading(degrees, resolution, text, match, ticks)
