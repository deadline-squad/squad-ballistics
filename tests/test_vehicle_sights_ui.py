"""The view control for vehicle gunner sights."""

import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("qtawesome")

import config
from i18n import tr
from ballistics import load_weapons, mark_offset
from conftest import ROOT


@pytest.fixture
def app(qapp):
    return qapp


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    win.config["animated"] = False
    yield win
    win.close()


def test_the_view_control_follows_the_vehicle_weapon(window):
    from config import CHOICES

    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("AT-4")
    assert window.view_control.isHidden()

    window.select_weapon("Tank AP · M256 / Rh120")
    buttons = list(window.view_control.buttons.values())

    assert not window.view_control.isHidden()
    assert [b.text() for b in buttons] == ["×3", "×6", "×12"]
    assert not any(b.isHidden() for b in buttons)

    window.select_weapon("Tank AP · Leopard 2A6 (Rh120)")
    assert [b.text() for b in buttons if not b.isHidden()] == ["×3", "×12"]

    window.select_weapon("QLZ87 · Lynx / CSK131")
    assert [b.text() for b in buttons if not b.isHidden()] == [tr("view_plain"), tr("view_optic")]

    window.select_weapon("Tank HESH · L30A1 (Challenger 2)")
    window.view_control.changed.emit("optic2")
    assert window.config["sight_view"] == "optic2"
    assert "optic2" in CHOICES["sight_view"]
    assert window.optic_view(window.current_weapon()) == 2

    window.select_weapon("ZPL-98A 105mm (ZTD-05) · AP")
    assert window.optic_view(window.current_weapon()) == 1
    assert buttons[1].isChecked()


def test_the_mark_follows_the_chosen_zoom_level(window):
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("Tank AP · M256 / Rh120")
    window.distance_entry.setText("800")
    window.height_entry.setText("0")
    window.fov_entry.setText("90")
    window.view_control.changed.emit("plain")
    window.calculate()
    weapon = window.current_weapon()
    angle = window.last_solution.sight_angle

    assert window.current_offset() == pytest.approx(mark_offset(weapon, angle, 90, 1920, zoomed=0))
    shallow = window.current_offset()

    window.view_control.changed.emit("optic2")
    assert window.current_offset() == pytest.approx(mark_offset(weapon, angle, 90, 1920, zoomed=2))
    assert window.current_offset() > shallow
