"""The FOV is entered by hand: the field is always editable, the typed FOV is
saved and is the one every mark and the overlay use, and the sentence about
the app's mark follows it. Nothing is read from the game."""

import json
import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import config
from ballistics import load_weapons, mark_offset
from conftest import ROOT
from crosshair import has_printed_reticle
from i18n import tr

WEAPON = "QLZ87 · optic (RMB ×3)"


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    return tmp_path / "config.json"


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, config_path):
    monkeypatch.chdir(tmp_path)
    windows = []

    def make():
        from crosshair import MainWindow

        win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
        win.overlay.setGeometry(0, 0, 1920, 1080)
        windows.append(win)

        return win

    yield make

    for win in windows:
        win.close()


def calculate_at(window, name, distance):
    window.select_weapon(name)
    window.distance_entry.setText(distance)
    window.calculate()


def test_the_fov_field_is_editable_and_starts_at_120_with_no_game(make_window):
    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 120
    assert window.active_fov() == 120


def test_the_typed_fov_is_the_one_mark_offset_and_the_overlay_use(make_window):
    window = make_window()
    window.fov_entry.setText("100")
    calculate_at(window, WEAPON, "1000")

    weapon = window.current_weapon()
    angle = window.last_solution.sight_angle

    assert window.active_fov() == 100
    assert window.overlay.offset == pytest.approx(mark_offset(weapon, angle, 100, 1920))
    assert window.overlay.offset != pytest.approx(mark_offset(weapon, angle, 120, 1920))


def test_a_typed_fov_is_saved(make_window, config_path):
    window = make_window()
    window.fov_entry.setText("105")
    calculate_at(window, WEAPON, "500")
    config.save_config(window.config)

    assert json.loads(config_path.read_text())["fov"] == 105


def test_a_fov_saved_by_1_7_0_loads_and_fills_the_field(make_window, config_path):
    config_path.write_text(json.dumps({"fov": 95, "language": "en"}))

    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 95
    assert window.active_fov() == 95


def test_the_typed_fov_survives_rebuilding_the_window(make_window):
    window = make_window()
    window.fov_entry.setText("101")
    calculate_at(window, WEAPON, "500")

    window.rebuild()

    assert window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 101
    assert window.active_fov() == 101


def test_the_overlay_says_nothing_about_an_assumed_fov(make_window):
    window = make_window()
    calculate_at(window, WEAPON, "500")

    assert "assumed" not in window.overlay.info_text


# ---------- what to aim with when the FOV is not 90 ----------

def shoot(window, name, distance="500"):
    calculate_at(window, name, distance)

    return window.overlay.info_text


def test_a_printed_reticle_at_fov_120_says_to_aim_with_the_apps_mark(make_window):
    window = make_window()

    assert tr("info_printed_reticle") in shoot(window, WEAPON)


def test_a_printed_reticle_at_a_typed_fov_90_says_nothing(make_window):
    window = make_window()
    window.fov_entry.setText("90")

    assert tr("info_printed_reticle") not in shoot(window, WEAPON)


def test_a_sight_without_a_printed_reticle_says_nothing_at_fov_120(make_window):
    window = make_window()
    plain = next(
        name for name, weapon in window.weapons.items()
        if weapon.aim == "overlay" and not has_printed_reticle(weapon)
    )

    assert tr("info_printed_reticle") not in shoot(window, plain)


def test_the_sentence_follows_a_fov_typed_in_the_field(make_window):
    window = make_window()
    window.fov_entry.setText("90")
    assert tr("info_printed_reticle") not in shoot(window, WEAPON)

    window.fov_entry.setText("100")

    assert tr("info_printed_reticle") in shoot(window, WEAPON)


@pytest.mark.parametrize("name, printed", [
    ("QLZ87 · optic (RMB ×3)", True),
    ("SPG-9 · HEAT · scope · optic (RMB ×4)", True),
    ("AGS-17 · emplacement · optic (RMB ×2.5)", True),
    ("Tank AP · T-72 (2A46) · gunner sight ×12", True),
    ("RPG-7 · PG-7V HEAT / OG-7V", True),
    ("M72A7 LAW / RPG-26", True),
    ("MK19 · M1151 open turret", False),
    ("AGS-17 · Technical", False),
    ("M203 / M320 / GP-25 / HK79 / SL40", False),
])
def test_which_weapons_have_a_printed_reticle(name, printed):
    weapons = load_weapons(os.path.join(ROOT, "weapons.json"))

    assert has_printed_reticle(weapons[name]) is printed
