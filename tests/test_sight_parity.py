"""Sight parity (issue 2): every weapon with a bore has a zero range that is
a round number, or the exception is named here with its cause.

The game's designers zero a sight at a round range (100, 200, 400 m ...), so a
bore taken from the wrong socket, camera or view comes out at an odd one.
A weapon passes when its zero (`zero_range`, flat ground) is within
ROUND_TOLERANCE of the nearest multiple of 10 m (below 100 m) or 50 m, or
when that round number lies inside the span the two-decimal rounding of the
bore allows (BORE_ROUNDING, the precision weapons.json carries; a 0.02 degree
bore moves its zero by 8 m). Every other weapon is in NOT_ROUND with its
zero and the cause; the test fails on a weapon that is round but listed, on
one that is not round and not listed, and on a listed zero that has moved.
"""

import dataclasses
import os

import pytest

from ballistics import load_weapons

from conftest import ROOT
from test_ballistics import zero_range

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))

ROUND_TOLERANCE = 0.03
BORE_ROUNDING = 0.0051
PINNED_ZERO_TOLERANCE = 1.5

CLAMP = (
    "the projectile's MaxSpeed slows the shell at launch (deadline-squad/squad-ballistics#4); "
    "the zero is not round with or without the clamp (unclamped values were checked)"
)
SOCKET = (
    "bore from the game's socket and camera pitches (re-read in #2); "
    "no round zero is evidenced in the files and the 2-decimal rounding does not reach one"
)

NOT_ROUND = {
    "MK19 · PARS III RWS": (181.4, SOCKET),
    "MK19 · M1151 open turret": (325.3, SOCKET),
    "MK19 · MATV open turret": (325.3, SOCKET),
    "MK19 · RHIB open turret": (325.5, SOCKET),
    "MK19 · emplacement / C16 / L134A1": (329.1, SOCKET),
    "AGS-17 · emplacement · optic (RMB ×2.5)": (57.6, SOCKET + "; confirmed by the hold fit (85 + 0.85)"),
    "AGS-17 · emplacement · no optic": (57.6, SOCKET),
    "QLZ87 · Lynx / CSK131 · optic (RMB ×3)": (109.3, SOCKET),
    "QLZ87 · Lynx / CSK131 · no optic": (109.3, SOCKET),
    "2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG": (130.2, SOCKET),
    "2A70 100mm (ZBD-04A) · FRAG": (213.2, SOCKET),
    "2A70 100mm (BMD-4M) · FRAG": (127.9, SOCKET),
    "Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3": (674.2, SOCKET),
    "Tank AP · T-62 (2A20)": (120.4, SOCKET),
    "SPG-9 · HEAT": (47.3, CLAMP),
    "SPG-9 · FRAG": (27.2, CLAMP),
    "2A28 Grom (BMD-1M) · HEAT": (515.6, CLAMP),
    "2A28 Grom (BMP-1 / BMD-1) · FRAG": (264.0, CLAMP),
    "Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2": (372.8, CLAMP),
    "Tank HEAT/HE · M1A1 / M1A2 (M256)": (367.8, CLAMP),
    "Tank HEAT/HE · ZTZ-99 (ZPT-98)": (140.8, CLAMP),
    "Tank HEAT/HE · T-64BM2 (KBA3)": (385.6, CLAMP),
}

# Direct-fire entries (agl, guns, tanks) with no bore, and why. Everything
# else in those categories has one; the hand-held launchers and grenade
# launchers fire from the camera and carry bore 0 as an assumption
# (`bore_assumed` in tests/data/game_weapons.json: not extracted), the mortars
# and rocket batteries are aimed by elevation.
NO_BORE = {
    "MK19": "M1117 gunner's sight aligned with the barrel (issue 2, comment 2)",
    "MK19 · AAVP-7A1": "gunner's sight aligned with the barrel, first zoom level x1 (issue 2)",
    "MK19 · M113 open turret · no sights": "normal view: camera on the gun axis",
    "MK19 · M1151 open turret · no sights": "normal view: camera on the gun axis",
    "MK19 · MATV open turret · no sights": "normal view: camera on the gun axis",
    "MK19 · emplacement / C16 / L134A1 · no sights": "normal view: camera on the gun axis",
}

DIRECT_FIRE_CATEGORIES = ("agl", "guns", "tanks")


def round_zero(zero):
    """The nearest round range: a multiple of 10 m below 100 m, of 50 m above."""
    step = 10 if zero < 100 else 50
    return round(zero / step) * step


def explained_by_bore_rounding(weapon, round_range):
    """Whether `round_range` is the zero of some bore the two-decimal
    rounding of weapons.json allows."""
    low = zero_range(weapon, weapon.bore - BORE_ROUNDING)
    high = zero_range(weapon, weapon.bore + BORE_ROUNDING)

    return low <= round_range <= high


def is_round(weapon, zero):
    nearest = round_zero(zero)

    return abs(zero - nearest) <= ROUND_TOLERANCE * nearest or explained_by_bore_rounding(weapon, nearest)


WITH_BORE = [name for name, weapon in WEAPONS.items() if weapon.bore > 0]


@pytest.mark.parametrize("name", WITH_BORE)
def test_the_zero_is_round_or_the_exception_is_named(name):
    weapon = WEAPONS[name]
    zero = zero_range(weapon, weapon.bore)

    if name in NOT_ROUND:
        pinned, reason = NOT_ROUND[name]

        assert reason
        assert zero == pytest.approx(pinned, abs=PINNED_ZERO_TOLERANCE)
        assert not is_round(weapon, zero), f"{name} is round now: remove it from NOT_ROUND"
        return

    assert is_round(weapon, zero), f"{name}: zero {zero:.1f} m is not round and has no listed cause"


def test_every_listed_exception_is_a_weapon_with_a_bore():
    assert set(NOT_ROUND) <= set(WITH_BORE)


def test_a_bore_that_puts_the_zero_off_a_round_range_is_caught():
    """Mutation check of the rule itself: 0.1 degree more bore on the QLZ87
    optic (zero 100 m) moves the zero to 162 m, which is neither round nor
    explained by the rounding."""
    weapon = WEAPONS["QLZ87 · optic (RMB ×3)"]
    shifted = dataclasses.replace(weapon, bore=weapon.bore + 0.1)

    assert is_round(weapon, zero_range(weapon, weapon.bore))
    assert not is_round(shifted, zero_range(shifted, shifted.bore))


def test_the_negative_bore_has_no_zero():
    """The tripod QLZ87 without its optic fires 0.9 degrees below the camera:
    even a 1 m shot is above it, so the search finds no zero (it returns its
    lower bound)."""
    weapon = WEAPONS["QLZ87 · no optic"]

    assert weapon.bore < 0
    assert zero_range(weapon, weapon.bore) == 1.0


def test_direct_fire_entries_without_a_bore_are_the_documented_ones():
    missing = {
        name for name, weapon in WEAPONS.items()
        if weapon.category in DIRECT_FIRE_CATEGORIES and not weapon.bore
    }

    assert missing == set(NO_BORE)
