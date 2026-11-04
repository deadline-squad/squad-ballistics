"""Reader precision audit (compassreader, sightreader) on degraded frames.

tests/reader_noise.py draws the elevation scale and the mortar view's
compass at 1920x1080 and 2560x1440, cuts the grab regions the app cuts, and
spoils them: Gaussian noise (sigma up to 8/255 on the grey levels), real
JPEG round trips (quality 50 and 25), brightness -30 % and +30 %, shifts of
1 px, and a screen scale the reader is told wrong by 3 % and 5 %. Measured
with `python tests/reader_noise.py 20` (20 random readings per size and
condition; error = reading - truth, absolute values):

  elevation scale, mil     mean     p99    max
    clean                  0.0025   0.0052 0.0052 (1080p)   0.0016 0.0036 0.0036 (1440p)
    worst single spoiling  0.0032   0.0109 0.0109 (noise 8/255, 1080p)
    all combined           0.0047   0.0133 0.0133 (noise 8 + JPEG 50 + 1.3x + shift)
    scale told wrong 5 %   0.0026   0.0051 0.0051 (no effect: spacing is measured)
    misses                 0 of 720 readings
  compass number, deg      0 on every condition read, except at 1080p with
                           noise 8/255 and noise 8 + JPEG 50 + 0.7x + shift:
                           mean 0.05-0.09, one tenths digit misread, 0.9 max
                           (the tenths digit is not checked by design); 7 of
                           720 readings missed (1080p: noise 8, JPEG 50, combined)
  compass strip, deg       mean 0.34, p99 0.65, max 0.65 clean (1080p);
                           max 0.65 under any spoiling at the right scale;
                           scale told off by 3 %: max 1.25; by 5 %: max 2.15
                           (the default tolerance is 2.5)

The bounds below are those numbers with room for the smaller seeded sample
of these tests. The audit found one bug, fixed with it: `find_pointer` took
the first to the last dark row of its column as the pointer, so one noise
speck darker than DARK moved the reading by up to 1.5 mil (1440p, brightness
-30 % with noise 8/255).
"""

import random

import pytest

from PyQt6.QtGui import QColor

import reader_noise as noise
from compassreader import DigitReader
from sightimage import draw_sight
from sightreader import GrayImage, LabelTemplates, find_edge, find_pointer

SAMPLE = 5
CONDITIONS = dict(noise.CONDITIONS)

SIGHT_BOUND = 0.05
SIGHT_COMBINED_BOUND = 0.1
STRIP_BOUND = 1.0
STRIP_SCALE_BOUND = 2.5
COMPASS_WRONG_BOUND = 1.0


@pytest.fixture(scope="module")
def templates():
    return LabelTemplates()


@pytest.fixture(scope="module")
def digits(templates):
    return DigitReader(templates)


@pytest.mark.parametrize("size", noise.SIZES, ids=lambda s: f"{s[1]}p")
@pytest.mark.parametrize("name", CONDITIONS)
def test_the_elevation_scale_is_read_within_a_hundredth_of_a_mil(templates, size, name):
    rng = random.Random(11)
    mils = noise.sample_mils(rng, SAMPLE)
    errors = [noise.sight_error(m, size, CONDITIONS[name], rng, templates) for m in mils]
    bound = SIGHT_COMBINED_BOUND if "+" in name and name.startswith("noise 8 +") else SIGHT_BOUND

    assert None not in errors
    assert max(abs(e) for e in errors) < bound, (name, mils, errors)


@pytest.mark.parametrize("size", noise.SIZES, ids=lambda s: f"{s[1]}p")
@pytest.mark.parametrize("told", noise.SCALE_MISMATCH)
def test_a_wrong_screen_scale_does_not_move_the_elevation(templates, size, told):
    rng = random.Random(12)
    mils = noise.sample_mils(rng, SAMPLE)
    errors = [noise.sight_error(m, size, {}, rng, templates, told) for m in mils]

    assert None not in errors
    assert max(abs(e) for e in errors) < SIGHT_BOUND


@pytest.mark.parametrize("size", noise.SIZES, ids=lambda s: f"{s[1]}p")
@pytest.mark.parametrize("name", CONDITIONS)
def test_the_compass_never_reads_a_wrong_bearing_beyond_the_tenths_digit(digits, size, name):
    rng = random.Random(13)
    bearings = noise.sample_bearings(rng, SAMPLE)
    errors = [noise.compass_error(b, size, CONDITIONS[name], rng, digits) for b in bearings]
    read = [e for e in errors if e is not None]

    # A miss is no reading, which the lay answers by trying again
    assert len(read) >= SAMPLE - 1, (name, bearings, errors)
    assert max(abs(e) for e in read) < COMPASS_WRONG_BOUND, (name, bearings, errors)


@pytest.mark.parametrize("size", noise.SIZES, ids=lambda s: f"{s[1]}p")
@pytest.mark.parametrize("name", ["clean", "noise 8/255", "brightness -30%", "shift +1 px x"])
def test_the_strip_sits_where_the_number_puts_it(size, name):
    rng = random.Random(14)
    bearings = noise.sample_bearings(rng, SAMPLE)
    offsets = [noise.strip_error(b, size, CONDITIONS[name], rng) for b in bearings]

    assert None not in offsets
    assert max(offsets) <= STRIP_BOUND


@pytest.mark.parametrize("told", noise.SCALE_MISMATCH)
def test_a_screen_scale_wrong_by_5_percent_still_passes_the_strip_check(told):
    rng = random.Random(15)
    bearings = noise.sample_bearings(rng, SAMPLE)
    offsets = [noise.strip_error(b, (1920, 1080), {}, rng, told) for b in bearings]

    assert None not in offsets
    assert max(offsets) <= STRIP_SCALE_BOUND


@pytest.mark.parametrize("size", noise.SIZES, ids=lambda s: f"{s[1]}p")
def test_a_noise_speck_in_the_pointer_column_is_not_the_pointer(size):
    """Regression of the audit's bug: the pointer was the first to the last
    dark row of its column, so one dark pixel above it moved it."""
    screen = draw_sight(1111.1, *size)
    crop, cx, cy = noise.sight_crop(screen)
    gray = GrayImage.from_qimage(crop)
    k = size[1] / 1080
    edge = find_edge(gray, round(cx), round(cy), k)
    clean = find_pointer(gray, edge, round(cy), k)

    x = edge + max(1, round(2 * k)) + max(1, round(4 * k / 2))
    speckled = crop.copy()
    speckled.setPixelColor(x, round(cy) - round(25 * k), QColor(0, 0, 0))
    after = find_pointer(GrayImage.from_qimage(speckled), edge, round(cy), k)

    assert after == pytest.approx(clean, abs=0.5)
    assert clean == pytest.approx(cy, abs=1.0)
