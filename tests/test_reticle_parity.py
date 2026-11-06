"""Reticle parity: the range marks the game prints on its sight textures against the marks the overlay computes.

The rows are read from the Squad client (build 26234431): the widget gives the texture's size on screen at 1080p (slot size
times render scale; `docs/sight-data.md`, "Reticle marks"), the texture pixels give each mark's row. The texture's centre
(row 1024 of 2048) is the screen centre. The overlay's offset is `mark_offset` at the game's default FOV of 90; the game's
reticle is a fixed-size picture, so it can only agree with the world at the FOV it was drawn for. Each reticle must agree
within its listed tolerance and its fitted design FOV (the zoomed horizontal FOV, from a least-squares fit of the marks
against tan(angle), times the zoom) must be near the game's default of 90 degrees.
"""

import math
import os

import pytest

from ballistics import load_weapons, mark_offset

from conftest import ROOT

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

SCREEN_WIDTH = 1920
DEFAULT_FOV = 90.0

# (weapon, on-screen px per texel, tolerance px, [(distance m, texture row of the mark)])
RETICLES = {
    "QLZ87 optic (YMA-87-35)": (
        "QLZ87 · optic (RMB ×3)", 1000 / 2048, 8.5,
        [(100, 1040.5), (200, 1131.0), (300, 1229.0), (400, 1329.5), (500, 1428.5)],
    ),
    "SPG-9 HEAT, red scale": (
        "SPG-9 · HEAT · scope · optic (RMB ×4)", 1800 / 2048, 8.0,
        [(200, 862), (400, 908), (600, 973), (800, 1031), (1000, 1090), (1200, 1159)],
    ),
    "SPG-9 FRAG, green scale": (
        "SPG-9 · FRAG · scope · optic (RMB ×4)", 1800 / 2048, 10.0,
        [(200, 908), (400, 1008), (600, 1114), (800, 1220), (1000, 1323), (1200, 1427)],
    ),
    "ZiS-3 optic": (
        "ZiS-3 · optic (RMB ×4)", 1285 / 2048, 11.5,
        [(400, 1049), (700, 1083), (900, 1112), (1100, 1147), (1300, 1175), (1500, 1208), (1700, 1242),
         (1900, 1275), (2100, 1307)],
    ),
    "AGS-17 PAG-17 optic": (
        "AGS-17 · emplacement · optic (RMB ×2.5)", 1071.6866 / 2048, 35.0,
        [(100, 1106), (200, 1219), (300, 1349), (400, 1489), (500, 1644), (600, 1778), (700, 1925)],
    ),
}


def overlay_angle_and_offset(weapon, distance):
    """(angle below the view centre in degrees, mark offset in px at FOV 90) for flat ground at `distance`."""
    rad = weapon.flat_low_elevation(distance)
    angle = math.degrees(rad) - weapon.angle_offset
    sight_angle = angle - math.degrees(math.atan2(-weapon.launch_height, distance))
    return sight_angle - weapon.bore, mark_offset(weapon, sight_angle, DEFAULT_FOV, SCREEN_WIDTH)


@pytest.mark.parametrize("name", RETICLES)
def test_marks_agree_with_the_overlay_at_fov_90(name):
    weapon_name, px_per_texel, tolerance, marks = RETICLES[name]
    weapon = WEAPONS[weapon_name]

    for distance, row in marks:
        game = (row - 1024) * px_per_texel
        _, overlay = overlay_angle_and_offset(weapon, distance)
        assert game == pytest.approx(overlay, abs=tolerance), f"{name} {distance} m"


@pytest.mark.parametrize("name", RETICLES)
def test_design_fov_is_the_default_fov(name):
    weapon_name, px_per_texel, _, marks = RETICLES[name]
    weapon = WEAPONS[weapon_name]
    tangents = []
    offsets = []

    for distance, row in marks:
        angle, _ = overlay_angle_and_offset(weapon, distance)
        if angle > 0:
            tangents.append(math.tan(math.radians(angle)))
            offsets.append((row - 1024) * px_per_texel)

    pixels_per_radian = sum(t * o for t, o in zip(tangents, offsets)) / sum(t * t for t in tangents)
    zoomed_fov = 2 * math.degrees(math.atan((SCREEN_WIDTH / 2) / pixels_per_radian))

    assert zoomed_fov * weapon.zoom == pytest.approx(DEFAULT_FOV, abs=8.0), name
