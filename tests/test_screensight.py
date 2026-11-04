"""ScreenSight regions and grabs, exactly (mutation survivors of sightlay)."""

import pytest

import sightlay
from sightimage import draw_sight
from compassimage import draw_compass
from test_sightlay import AlignedOverlay, ImageScreen


@pytest.mark.parametrize("size, region", [
    ((1920, 1080), (960 - 508, 540 - 173, 960 - 86, 540 + 173)),
    ((2560, 1440), (1280 - 677, 720 - 230, 1280 - 115, 720 + 230)),
])
def test_the_sight_region_is_left_of_the_centre_by_screen_heights(size, region):
    overlay = AlignedOverlay(ImageScreen(draw_sight(1000.0, *size)), 0, 0)

    left, top, right, bottom = sightlay.ScreenSight(overlay).region()

    assert (left, top, right, bottom) == pytest.approx(region, abs=1)
    assert (right - left) / size[1] == pytest.approx(sightlay.GRAB_LEFT - sightlay.GRAB_RIGHT, abs=0.002)
    assert (bottom - top) / size[1] == pytest.approx(2 * sightlay.GRAB_HALF_HEIGHT, abs=0.002)


def test_the_sight_region_is_cut_at_the_screen_edges():
    overlay = AlignedOverlay(ImageScreen(draw_sight(1000.0, 640, 360)), 0, 0)
    overlay.height = lambda: 100
    overlay.width = lambda: 40
    left, top, right, bottom = sightlay.ScreenSight(overlay).region()

    assert (left, top, right, bottom) == (0, 34, 12, 66)


def test_the_sight_region_is_none_when_empty():
    overlay = AlignedOverlay(ImageScreen(draw_sight(1000.0, 640, 360)), 0, 0)
    overlay.height = lambda: 0

    assert sightlay.ScreenSight(overlay).region() is None


@pytest.mark.parametrize("size", [(1920, 1080), (2560, 1440)])
def test_the_compass_region_is_the_strip_with_its_margin(size):
    overlay = AlignedOverlay(ImageScreen(draw_compass(100.0, *size)), 50, 0)
    scale = size[1] / 1080
    half = (sightlay.STRIP_HALF_WIDTH + sightlay.COMPASS_MARGIN) * scale

    left, top, right, bottom = sightlay.ScreenSight(overlay).compass_region()

    assert left == round(size[0] / 2 - half)
    assert right == round(size[0] / 2 + half)
    assert top == round(size[1] - sightlay.SEARCH_TOP * scale)
    assert bottom == size[1]


def test_the_compass_region_is_cut_at_the_screen_edges_and_none_when_empty():
    narrow = AlignedOverlay(ImageScreen(draw_compass(100.0, 640, 360)), 0, 0)
    narrow.width = lambda: 200
    left, _top, right, _bottom = sightlay.ScreenSight(narrow).compass_region()

    assert (left, right) == (0, 200)

    empty = AlignedOverlay(ImageScreen(draw_compass(100.0, 640, 360)), 0, 0)
    empty.width = lambda: 0
    assert sightlay.ScreenSight(empty).compass_region() is None


def test_the_compass_grab_gives_the_screen_centre_in_the_grab_and_the_scale(qapp):
    screen = ImageScreen(draw_compass(211.4, 2560, 1440))
    sight = sightlay.ScreenSight(AlignedOverlay(screen, 90, 0))
    left, top, right, bottom = sight.compass_region()

    grab = sight.grab_compass()

    assert grab.image.width == right - left and grab.image.height == bottom - top
    assert grab.centre_x == pytest.approx(1280 - left)
    assert grab.centre_y == 0
    assert grab.scale == pytest.approx(1440 / 1080)


def test_the_sight_grab_gives_the_scale_of_the_screen_height(qapp):
    sight = sightlay.ScreenSight(AlignedOverlay(ImageScreen(draw_sight(900.0, 2560, 1440)), 0, 0))

    grab = sight.grab()

    assert grab.scale == pytest.approx(1440 / 1080)
    assert grab.image.width == sight.region()[2] - sight.region()[0]


def test_nothing_is_grabbed_without_a_screen_or_region(qapp, monkeypatch):
    class Blank(ImageScreen):
        def grabWindow(self, *args):
            from PyQt6.QtGui import QPixmap

            return QPixmap()

    overlay = AlignedOverlay(Blank(draw_sight(900.0, 640, 360)), 0, 0)
    sight = sightlay.ScreenSight(overlay)

    assert sight.grab_image() is None
    assert sight.grab() is None
    assert sight.grab_compass() is None

    empty = AlignedOverlay(ImageScreen(draw_sight(900.0, 640, 360)), 0, 0)
    empty.height = lambda: 0
    assert sightlay.ScreenSight(empty).grab_image() is None
    assert sightlay.ScreenSight(empty).grab() is None
    assert sightlay.ScreenSight(empty).grab_compass() is None
