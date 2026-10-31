"""Mouse4 switches an RMB sight between its optic and no-optic entries."""

import os

import pytest

import config
from ballistics import load_weapons, view_twin
from conftest import ROOT
from hotkeys import KEYS

WEAPONS = load_weapons(os.path.join(ROOT, "weapons.json"))
OPTICS = [name for name, weapon in WEAPONS.items() if weapon.view == "optic"]
PLAINS = [name for name, weapon in WEAPONS.items() if weapon.view == "plain"]
SIGHTLESS = [name for name, weapon in WEAPONS.items() if not weapon.view]

OPTIC = "ZiS-3 · optic (RMB ×4)"
PLAIN = "ZiS-3 · no optic"


def test_weapons_json_has_optic_twins():
    assert len(OPTICS) == len(PLAINS) == 6


@pytest.mark.parametrize("optic", OPTICS)
def test_every_pair_is_found_both_ways(optic):
    plain = view_twin(WEAPONS, optic)

    assert WEAPONS[plain].view == "plain"
    assert view_twin(WEAPONS, plain) == optic


@pytest.mark.parametrize("name", SIGHTLESS)
def test_every_other_weapon_has_no_twin(name):
    assert view_twin(WEAPONS, name) is None


def test_an_unknown_name_has_no_twin():
    assert view_twin(WEAPONS, "no such weapon") is None


def test_mouse4_is_the_default_key_of_the_view_toggle():
    assert config.DEFAULT_CONFIG["hotkeys"]["toggle_view"] == "Mouse4"
    assert KEYS["Mouse4"] == 0x113


def test_an_older_settings_file_gets_the_new_key(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"hotkeys": {"toggle_overlay": "F8", "reset_offset": "F9"}}')

    assert config.load_config(str(path))["hotkeys"]["toggle_view"] == "Mouse4"


@pytest.fixture
def pressed_window(qapp, tmp_path, monkeypatch):
    """The main window wired the real way to a key reader that reads the
    set `pressed` (what keystate's readers answer), plus that set."""
    import crosshair

    pressed = set()
    monkeypatch.setattr(crosshair, "system_key_reader", lambda: (lambda code: code in pressed))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    win = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    # The debounce clock is real: clicks in a test are far closer than a human's.
    import hotkeys
    monkeypatch.setattr(hotkeys, "MOUSE_DEBOUNCE_SECONDS", 0)
    win.set_hotkey("toggle_view", "Mouse4")

    yield win, pressed

    win.close()


def click(window, pressed, key="Mouse4"):
    """One press and release of `key` seen by the window's poller."""
    poller = window._hotkey_poller
    pressed.add(KEYS[key])
    poller.timeout.emit()
    pressed.discard(KEYS[key])
    poller.timeout.emit()


def test_mouse4_switches_the_view_and_everything_follows(pressed_window):
    window, pressed = pressed_window
    window.select_weapon(OPTIC)
    window.distance_entry.setText("500")
    window.calculate()
    optic_offset = window.overlay.offset

    assert "optic ×4" in window.overlay.info_text

    click(window, pressed)

    assert window.picker.current == PLAIN
    assert window.picker.text().startswith(PLAIN)
    assert window.distance_entry.text() == "500"
    assert window.overlay.info_text.count("no optic") == 1
    assert window.overlay.offset != optic_offset

    click(window, pressed)

    assert window.picker.current == OPTIC
    assert window.overlay.offset == pytest.approx(optic_offset)
    assert "optic ×4" in window.overlay.info_text


def test_the_trim_belongs_to_each_entry(pressed_window):
    window, pressed = pressed_window
    window.select_weapon(OPTIC)
    window.set_trim(0.5)

    click(window, pressed)
    assert window.current_trim(window.current_weapon()) == 0.0
    window.set_trim(-0.25)

    click(window, pressed)
    assert window.current_trim(window.current_weapon()) == 0.5
    assert window.trim_entry.value() == 0.5


def test_mouse4_does_nothing_for_a_weapon_without_an_rmb_sight(pressed_window):
    window, pressed = pressed_window
    window.select_weapon("AT-4")
    window.distance_entry.setText("100")

    click(window, pressed)

    assert window.picker.current == "AT-4"
    assert window.distance_entry.text() == "100"


def test_mouse4_follows_the_hotkey_setting(pressed_window):
    window, pressed = pressed_window
    window.select_weapon(OPTIC)

    window.set_hotkey("toggle_view", "")
    click(window, pressed)
    assert window.picker.current == OPTIC

    window.set_hotkey("toggle_view", "Mouse5")
    click(window, pressed, "Mouse4")
    assert window.picker.current == OPTIC
    click(window, pressed, "Mouse5")
    assert window.picker.current == PLAIN


def test_the_settings_page_offers_the_mouse_buttons(pressed_window):
    window, _pressed = pressed_window
    box = window.hotkey_boxes["toggle_view"]

    assert box.currentData() == "Mouse4"
    assert {"Mouse4", "Mouse5"} <= {box.itemData(i) for i in range(box.count())}
