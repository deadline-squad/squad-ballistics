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

LAUNCH = (
    "the launch point from the game files is in the model and the sight camera's own offset from the barrel "
    "(parallax) is not, which moves the zero by metres; no round zero is evidenced in the files"
)
NO_RISE = (
    "the muzzle sits 1 cm under the sight line and the bore is 0.02 degrees: the shot never rises above a "
    "centred ground target, so the model has no zero (the search stops at its 1 m lower bound)"
)

NOT_ROUND = {
    "MK19 · PARS III RWS": (181.4, SOCKET),
    "MK19 · PARS III RWS · gunner sight ×3": (181.4, SOCKET),
    "MK19 · PARS III RWS · gunner sight ×9": (181.4, SOCKET),
    "MK19 · M1151 open turret": (325.3, SOCKET),
    "MK19 · MATV open turret": (325.3, SOCKET),
    "MK19 · RHIB open turret": (325.5, SOCKET),
    "MK19 · emplacement / C16 / L134A1": (330.2, SOCKET),
    "AGS-17 · emplacement · optic (RMB ×2.5)": (57.6, SOCKET + "; confirmed by the hold fit (85 + 0.85)"),
    "AGS-17 · emplacement · no optic": (57.6, SOCKET),
    "QLZ87 · optic (RMB ×3)": (103.1, LAUNCH),
    "QLZ87 · bunker tripod · optic (RMB ×3)": (103.1, LAUNCH),
    "QLZ87 · CSK131 / WZ551 · optic (RMB ×3)": (121.3, SOCKET),
    "QLZ87 · CSK131 / WZ551 · no optic": (121.3, SOCKET),
    "QLZ87 · Lynx · optic (RMB ×3)": (121.2, SOCKET),
    "QLZ87 · Lynx · no optic": (121.2, SOCKET),
    "QLZ87 · ZBL08 · optic (RMB ×3)": (121.3, SOCKET),
    "QLZ87 · ZBL08 · no optic": (121.3, SOCKET),
    "AGS-30 / BTR-4 AGS": (208.1, LAUNCH),
    "AGS-30 / BTR-4 AGS · gunner sight ×9": (208.1, LAUNCH),
    "AGS-30 (BMP-2M)": (210.2, LAUNCH),
    "AGS-30 (BMP-2M) · gunner sight ×6": (210.2, LAUNCH),
    "SPG-9 · FRAG": (54.9, CLAMP),
    "2A28 Grom (BMD-1M) · HEAT": (517.0, CLAMP),
    "2A28 Grom (BMD-1M) · HEAT · gunner sight ×6": (517.0, CLAMP),
    "2A28 Grom (BMP-1 / BMD-1) · FRAG": (265.6, CLAMP),
    "2A28 Grom (BMP-1) · FRAG · gunner sight ×6": (265.6, CLAMP),
    "2A28 Grom (BMP-1 technical) · FRAG · gunner sight ×6": (265.6, LAUNCH),
    "2A28 Grom (BMP-1 technical) · FRAG": (265.6, LAUNCH),
    "2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG": (131.7, SOCKET),
    "2A70 100mm (BMP-3) · FRAG · gunner sight ×4": (130.5, SOCKET),
    "2A70 100mm (ZBD-04A) · FRAG": (215.9, SOCKET),
    "2A70 100mm (ZBD-04A) · FRAG · gunner sight ×4": (215.9, SOCKET),
    "2A70 100mm (ZBD-04A) · FRAG · gunner sight ×14": (215.9, SOCKET),
    "2A70 100mm (BMD-4M) · FRAG": (130.3, SOCKET),
    "2A70 100mm (BMD-4M) · FRAG · gunner sight ×5": (131.5, SOCKET),
    "2A70 100mm (BMP-3 / BMD-4M) · FRAG · gunner sight ×14": (131.0, SOCKET),
    "ZiS-3 · optic (RMB ×4)": (376.9, LAUNCH),
    "ZiS-3 · no optic": (376.9, LAUNCH),
    "Tank AP · T-90A (2A46M)": (676.1, LAUNCH),
    "Tank AP · T-90A (2A46M) · gunner sight ×12": (676.1, LAUNCH),
    "Tank AP · T-62 (2A20)": (115.2, SOCKET),
    "Tank AP · T-62 (2A20) · gunner sight ×7": (115.2, SOCKET),
    "Tank AP · Leopard 2A6 (Rh120)": (516.1, LAUNCH),
    "Tank AP · Leopard 2A6 (Rh120) · gunner sight ×12": (516.1, LAUNCH),
    "Tank HEAT/HE · T-90A (2A46M)": (374.8, LAUNCH),
    "Tank HEAT/HE · T-90A (2A46M) · gunner sight ×12": (374.8, LAUNCH),
    "Tank HEAT/HE · M1A1 / M1A2 (M256)": (370.7, CLAMP),
    "Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×6": (370.7, CLAMP),
    "Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×12": (370.7, CLAMP),
    "Tank HEAT/HE · ZTZ-99 (ZPT-98)": (141.2, CLAMP),
    "Tank HEAT/HE · ZTZ-99 (ZPT-98) · gunner sight ×12": (141.2, CLAMP),
    "ZPL-98A 105mm (ZTD-05) · AP": (1.0, NO_RISE),
    "ZPL-98A 105mm (ZTD-05) · AP · gunner sight ×7": (1.0, NO_RISE),
    "ZPL-98A 105mm (ZTD-05) · HEAT / HE": (1.0, NO_RISE),
    "ZPL-98A 105mm (ZTD-05) · HEAT / HE · gunner sight ×7": (1.0, NO_RISE),
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
    "MK19 · RHIB open turret · no sights": "normal view: camera on the gun axis",
    "MK19 · emplacement / C16 / L134A1 · no sights": "normal view: camera on the gun axis",
    "MK19 · M1117 · gunner sight ×4.5": "M1117 gunner's sight aligned with the barrel at its second zoom level",
    "MK19 · AAVP-7A1 · gunner sight ×4.5": "gunner's sight aligned with the barrel at its second zoom level",
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
    """Mutation check of the rule itself: 0.1 degree more bore on the tripod
    AGS-17 (zero 304 m) moves the zero to 310 m, which is neither round nor
    explained by the rounding."""
    weapon = WEAPONS["AGS-17 · iron sights emplacement"]
    shifted = dataclasses.replace(weapon, bore=weapon.bore + 0.1)

    assert is_round(weapon, zero_range(weapon, weapon.bore))
    assert not is_round(shifted, zero_range(shifted, shifted.bore))


def test_the_negative_bore_has_no_zero():
    """The tripod QLZ87 without its optic fires 0.9 degrees below the camera:
    even a 1 m shot is above it, so the search finds no zero (it returns its
    lower bound, 1 m, which the launch point's muzzle offset moves to under 2 m)."""
    weapon = WEAPONS["QLZ87 · no optic"]

    assert weapon.bore < 0
    assert zero_range(weapon, weapon.bore) < 2.0


def test_direct_fire_entries_without_a_bore_are_the_documented_ones():
    missing = {
        name for name, weapon in WEAPONS.items()
        if weapon.category in DIRECT_FIRE_CATEGORIES and not weapon.bore
    }

    assert missing == set(NO_BORE)
