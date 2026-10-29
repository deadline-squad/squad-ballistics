"""Vehicle gunner sights in the window: one fixed view, no view control."""

import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("qtawesome")

import config
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


def test_there_is_no_view_control(window):
    assert not hasattr(window, "view_control")
    assert "sight_view" not in window.config
    assert "sight_view" not in config.CHOICES


def test_the_mark_follows_the_weapons_sight(window):
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("Tank AP · M256 / Rh120")
    window.distance_entry.setText("800")
    window.height_entry.setText("0")
    window.fov_entry.setText("90")
    window.calculate()
    weapon = window.current_weapon()
    angle = window.last_solution.sight_angle

    assert weapon.sight_view(90) == (30, 0.31)
    assert window.current_offset() == pytest.approx(mark_offset(weapon, angle, 90, 1920))
    assert window.overlay.offset == pytest.approx(mark_offset(weapon, angle, 90, 1920))

    window.select_weapon("AT-4")
    window.calculate()
    plain = window.weapons["AT-4"]
    assert window.current_offset() == pytest.approx(
        mark_offset(plain, window.last_solution.sight_angle, 90, 1920)
    )
