"""The AGS-17 hold beep and the hold-timer panel are gone; the mortar's
lay-finished beep and the timed auto-lay stay (issue 3 finding 27, branch
chore/remove-hold-beep). Settings files that still carry the removed keys
load (tests/test_config.py::test_settings_of_the_removed_hold_timer_are_ignored).
"""

import glob
import os
import re

import pytest

import config
from ballistics import load_weapons

from conftest import ROOT

AGS17 = "AGS-17 · emplacement · optic (RMB ×2.5)"
MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"

REMOVED_NAMES = re.compile(r"hold_panel|hold_beep|beep_lead|hold_lead|timer_panel|HoldPanel|panel_corner")


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    yield win
    win.close()


@pytest.fixture
def beeps(monkeypatch):
    """The calls of the beep crosshair plays."""
    calls = []
    monkeypatch.setattr("crosshair.beep", lambda: calls.append(1))

    return calls


def test_no_source_names_the_removed_panel_or_beep_settings():
    """Only config.py may name the removed keys, to drop them from old files."""
    for path in glob.glob(os.path.join(ROOT, "*.py")):
        if os.path.basename(path) == "config.py":
            continue

        with open(path, encoding="utf-8") as source:
            assert not REMOVED_NAMES.search(source.read()), path


def test_the_hold_timer_module_does_not_beep():
    with open(os.path.join(ROOT, "holdtimer.py"), encoding="utf-8") as source:
        text = source.read()

    assert "beep" not in text.lower()


def test_ags17_hold_reaching_its_time_does_not_beep(window, beeps):
    window.select_weapon(AGS17)
    window.distance_entry.setText("900")
    window.calculate()

    timer = window.hold_timer
    assert timer.target is not None

    for _ in range(int(timer.target / 0.01) + 50):
        timer.advance(0.01, True, False)

    assert timer.held > timer.target
    assert beeps == []
    assert not hasattr(window.overlay, "hold_panel")
    assert not hasattr(window, "hold_panel")


def test_the_overlay_has_no_timer_panel(window):
    window.select_weapon(AGS17)
    window.distance_entry.setText("900")
    window.calculate()
    window.hold_timer.advance(0.5, True, False)

    assert not [name for name in vars(window.overlay) if "panel" in name.lower()]
    assert not [name for name in vars(window) if "hold_panel" in name]


def test_the_mortar_beeps_once_when_the_sight_lay_ends_on_target(window, beeps):
    window.select_weapon(MORTAR)

    window.on_sight_lay_finished(None, True)
    assert beeps == [1]

    window.on_sight_lay_finished(None, False)
    assert beeps == [1]


def test_the_mortar_auto_lay_still_resets_and_holds(window):
    window.select_weapon(MORTAR)
    window.distance_entry.setText("800")
    window.calculate()

    weapon = window.current_weapon()
    timer = window.hold_timer

    assert timer.target is not None
    assert window.lay_reset_time(weapon) > 0
    assert window.timed_lay_blocker(weapon) in (None, "lay_key_no_keys", "lay_key_no_reader")
