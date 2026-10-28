import math
import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("qtawesome")

from PyQt6.QtWidgets import QApplication

import config
from ballistics import load_weapons, solve
from i18n import tr
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


def reachable_distance(weapon):
    for fraction in (0.3, 0.6, 0.85):
        distance = max(
            weapon.min_distance + 5,
            min(weapon.max_range() * fraction, 1500)
        )
        if solve(weapon, distance).reachable:
            return distance


def test_every_weapon_through_ui(window):
    for name, weapon in window.weapons.items():
        window.select_weapon(name)

        distance = reachable_distance(weapon)

        window.distance_entry.setText(f"{distance:.0f}")
        window.height_entry.setText("")
        window.fov_entry.setText("90")
        window.calculate()

        assert window.last_solution is not None, name
        assert window.last_solution.reachable, (name, window.status_text())

        if math.isfinite(window.last_solution.hold_time):
            # Laid by holding S (AGS-17 high arc): the readout is a time.
            assert window.status_text().startswith("S "), name
        else:
            assert any(
                c in window.status_text() for c in ("°", "mil", "мил")
            )

        assert len(window.current_steps) >= 2, name

        expected = window.current_offset()
        if abs(expected) < window.overlay.height():
            assert window.overlay.offset == pytest.approx(expected), name


def test_comma_decimal_and_errors(window):
    window.select_weapon("SPG-9 · HEAT")

    window.distance_entry.setText("350,5")
    window.height_entry.setText("-3,5")
    window.calculate()
    assert window.last_solution.distance == pytest.approx(350.5)
    assert window.last_solution.height_diff == pytest.approx(-3.5)

    window.distance_entry.setText("")
    window.calculate()
    assert window.last_solution is None
    assert window.big_label.property("state") == "error"

    window.distance_entry.setText("100000")
    window.calculate()
    assert not window.last_solution.reachable
    assert window.overlay.target_offset == 0


def test_reset_toggle_and_distance_keys(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("500")
    window.calculate()
    assert window.overlay.target_offset > 0
    assert "500 m" in window.overlay.info_text

    window.config["distance_step"] = 25
    window.distance_up()
    assert window.last_solution.distance == 525
    window.distance_down()
    window.distance_down()
    assert window.last_solution.distance == 475

    window.reset_offset()
    assert window.overlay.target_offset == 0
    assert window.overlay.info_text == ""

    visible = window.overlay.isVisible()
    window.toggle_overlay()
    assert window.overlay.isVisible() != visible


def test_unit_mode_and_arc(window):
    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    window.distance_entry.setText("800")
    window.calculate()
    assert "mil" in window.status_text() or "мил" in window.status_text()

    window.set_unit_mode("deg")
    assert "°" in window.status_text()

    window.on_arc_changed("low")
    assert not window.last_solution.reachable


def test_mods_hidden_by_default(window):
    mods = [n for n, w in window.weapons.items() if w.mod]
    assert mods

    assert not any(n in window.visible_weapons() for n in mods)

    window.config["show_mods"] = True
    assert all(n in window.visible_weapons() for n in mods)


def test_recent_weapons(window):
    window.select_weapon("RPG-29")
    window.select_weapon("AT-4")

    assert window.config["recent_weapons"][:2] == ["AT-4", "RPG-29"]
    assert window.config["last_weapon"] == "AT-4"


def test_presets_and_colors(window):
    window.apply_preset("circle")
    assert window.config["circle_enabled"] is True
    assert window.controls["circle_enabled"].isChecked()

    window.pick_crosshair_color("#ff00ff")
    assert window.config["color"] == [255, 0, 255]
    assert window.controls[("color", 1)].slider.value() == 0

    window.set_setting(("color", 2), 200)
    assert window.config["color"][2] == 200

    for key in ("circle_enabled", "glow_enabled", "lines_enabled",
                "outline_enabled"):
        window.set_setting(key, True)
    window.set_setting("outline_color", "black")
    window.overlay.repaint()
    window.preview.repaint()

    # Off-screen aim point is drawn as an edge arrow.
    window.overlay.set_offset(1e9)
    window.overlay.repaint()


def test_language_and_accent_rebuild(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.calculate()

    window.set_language("en")
    assert window.distance_entry.text() == "400"
    assert window.last_solution.reachable

    window.set_language("ru")
    window.set_accent("#22c55e")
    assert window.config["accent"] == "#22c55e"
    assert window.distance_entry.text() == "400"


def test_hotkey_rebinding(window):
    window.set_hotkey("distance_up", "PgUp")
    assert window.config["hotkeys"]["distance_up"] == "PgUp"

    # Binding a key that is already used moves it.
    window.set_hotkey("reset_offset", "PgUp")
    assert window.config["hotkeys"]["reset_offset"] == "PgUp"
    assert window.config["hotkeys"]["distance_up"] == ""


def type_text(widget, text):
    """Send key presses like a real keyboard, including Cyrillic layouts."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    widget.setFocus()

    for char in text:
        for kind in (QKeyEvent.Type.KeyPress, QKeyEvent.Type.KeyRelease):
            QApplication.sendEvent(
                widget,
                QKeyEvent(kind, 0, Qt.KeyboardModifier.NoModifier, char)
            )


@pytest.mark.parametrize("typed, expected", [
    ("2.5", "2.5"),
    ("-2.5", "-2.5"),
    ("2,5", "2.5"),
    ("2ю5", "2.5"),       # "." key on a Russian layout
    ("-2б75", "-2.75"),   # "," key on a Russian layout
    ("−3.5", "-3.5"),     # typographic minus
    ("+4", "4"),
    ("1.2345", "1.234"),  # at most 3 decimals
    ("abc7", "7"),
])
def test_height_accepts_fractions_on_any_layout(window, typed, expected):
    window.height_entry.clear()

    type_text(window.height_entry, typed)

    assert window.height_entry.text() == expected
    assert window.height_entry.value() == pytest.approx(float(expected))


def test_minus_flips_sign_and_distance_has_no_sign(window):
    window.height_entry.setText("12.5")
    window.height_entry.setCursorPosition(4)

    type_text(window.height_entry, "-")
    assert window.height_entry.text() == "-12.5"

    type_text(window.height_entry, "-")
    assert window.height_entry.text() == "12.5"

    window.distance_entry.clear()
    type_text(window.distance_entry, "-300ю5")
    assert window.distance_entry.text() == "300.5"


def test_typed_height_reaches_the_solution(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.fov_entry.setText("90")
    window.height_entry.clear()

    type_text(window.height_entry, "-7ю25")
    window.calculate()

    assert window.last_solution.height_diff == pytest.approx(-7.25)


def test_offscreen_follows_center_offset(window):
    overlay = window.overlay
    edge = overlay.height() / 2 - overlay.EDGE_MARGIN

    window.config["center_offset_y"] = 0
    assert not overlay.is_offscreen(edge - 1)

    window.config["center_offset_y"] = 50
    assert overlay.is_offscreen(edge - 1)


def test_overlay_hint_uses_bound_key(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.fov_entry.setText("90")
    window.calculate()

    assert "F8" in window.current_steps[0]

    window.config["hotkeys"]["toggle_overlay"] = ""
    window.calculate()
    assert "F8" not in window.current_steps[0]


def test_selftest_does_not_touch_user_config(tmp_path):
    import subprocess
    import sys

    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "cfg")
    env["APPDATA"] = str(tmp_path / "cfg")
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "app.py"), "--selftest"],
        cwd=tmp_path,
        env=env,
        timeout=120,
    )

    log = os.path.join(ROOT, "selftest.log")
    try:
        with open(log, encoding="utf-8") as f:
            text = f.read()
    finally:
        os.remove(log)

    assert result.returncode == 0, text
    assert "SELFTEST PASSED" in text
    assert not (tmp_path / "cfg" / "SquadBallistics" / "config.json").exists()


def test_map_page_survives_rebuild(window, monkeypatch):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    window.set_page(3)

    page = window.map_page
    view = page.view

    assert view is not None
    # The Deadline build is the default: it has AGS-17 and the target bridge.
    assert view.page().requestedUrl().host() == "calc.tk104.duckdns.org"
    assert window.pages.currentIndex() == 3

    window.set_language("en")

    assert window.map_page is page
    assert window.map_page.view is view
    assert window.pages.currentIndex() == 3
    assert page.reload_button.text() == "Reload"


def test_map_help_panel_and_external_mode(window, monkeypatch):
    opened = []
    monkeypatch.setattr("crosshair.open_external", opened.append)

    window.set_page(1)
    window.config["map_external"] = True
    window.set_page(3)

    assert opened == ["https://calc.tk104.duckdns.org/"]

    window.config["map_source"] = "squadcalc"
    window.set_page(3)

    assert opened[-1] == "https://squadcalc.app/"
    assert window.pages.currentIndex() == 1

    page = window.map_page
    page.show_panel("slow")
    assert page.panel.isVisibleTo(window) or not window.isVisible()
    assert page.panel_title.text()
    assert page.compat_button.isVisibleTo(page.panel)

    window.config["map_render"] = "software"
    page.show_panel("black")
    assert not page.compat_button.isVisibleTo(page.panel)


def test_switching_map_render_asks_for_restart(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.No
    )

    window.set_map_render("software")

    assert window.config["map_render"] == "software"
    assert config.load_config()["map_render"] == "software"


AGS17 = "AGS-17 · emplacement"


def test_ags17_lob_is_laid_by_holding_s(window):
    window.hold_timer.key_reader = lambda vk: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    window.distance_entry.setText("1000")
    window.height_entry.setText("")
    window.calculate()

    solution = window.last_solution
    assert solution.reachable
    assert window.status_text() == tr("hold_big", t=f"{solution.hold_time:.2f}")
    assert window.overlay.offset == 0.0
    assert window.hold_timer.target == pytest.approx(solution.hold_time)
    assert any("S" in step for step in window.current_steps)
    assert "S " in window.overlay.info_text

    # Holding S reaches the target and the readout says so.
    window.hold_timer.advance(solution.hold_time + 0.01, True, False)
    assert window.hold_timer.is_reached
    assert "✓" in window.hold_label.text()
    assert "✓" in window.overlay.info_text

    # The low arc of the same weapon is direct fire with the overlay mark.
    window.config["arc"] = "low"
    window.calculate()
    assert window.hold_timer.target is None
    assert "°" in window.status_text()
    assert window.current_offset() > 0


def test_hold_timer_setting_and_missing_keys(window):
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("800")

    window.hold_timer.key_reader = None
    window.calculate()
    assert window.hold_timer.target == pytest.approx(
        window.last_solution.hold_time
    )
    assert not window.hold_timer.poll_timer.isActive()
    assert window.hold_label.isHidden()

    window.config["hold_timer"] = False
    window.calculate()
    assert window.hold_timer.target is None


def test_map_target_fills_the_inputs(window):
    from maplink import MapTarget

    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    window.on_map_targets([
        MapTarget(500, 0, 10.0),
        MapTarget(1234.4, -12.6, 271.25),
    ])

    assert window.distance_entry.text() == "1234"
    assert window.height_entry.text() == "-13"
    assert window.last_solution.reachable
    assert window.last_solution.height_diff == -13
    bearing = f"{271.25:.1f}"
    assert bearing in window.map_label.text()
    assert window.current_steps[0] == tr("how_bearing", b=bearing)
    assert window.overlay.info_text.startswith("1234 ")
    assert f"{bearing}°" in window.overlay.info_text

    # The same list again changes nothing; an empty list keeps the inputs.
    window.distance_entry.setText("900")
    window.on_map_targets([MapTarget(1234.4, -12.6, 271.25)])
    assert window.distance_entry.text() == "900"
    window.on_map_targets([])
    assert window.distance_entry.text() == "900"

    # Unknown height (older SquadCalc page) clears the field.
    window.on_map_targets([MapTarget(700, None, None)])
    assert window.height_entry.text() == ""
    assert window.distance_entry.text() == "700"


def test_typing_forgets_the_map_target(window):
    from maplink import MapTarget

    window.on_map_targets([MapTarget(600, 5, 90.0)])
    assert window.map_target is not None

    window.distance_entry.textEdited.emit("650")
    assert window.map_target is None
    assert window.map_label.text() == tr("map_follow_hint")

    window.config["map_follow"] = False
    window.on_map_targets([MapTarget(800, 0, 10.0)])
    assert window.map_target is None


def test_embedded_map_bridge_feeds_the_calculator(window):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    window.set_page(3)
    page = window.map_page

    page.on_bridge_result(None)
    assert page.bridge_found is False

    page.on_bridge_result([{"distance": 950.2, "heightDiff": 3.9, "bearing": 5}])
    assert page.bridge_found is True
    assert window.distance_entry.text() == "950"
    assert window.height_entry.text() == "4"

    page.load_source()
    assert page.bridge_found is None

    # A late answer after the map was shut down is ignored.
    page.shutdown()
    page.on_bridge_result([{"distance": 300}])
    assert page.bridge_found is None
    assert window.distance_entry.text() == "950"


def test_relay_code_setting(window, monkeypatch):
    connected = []
    monkeypatch.setattr(window.relay, "connect_relay", lambda: connected.append(window.relay.code))

    window.set_relay_code("bad!")
    assert window.relay_status_label.text() == tr("relay_bad_code")
    assert window.config["relay_code"] == ""

    window.set_relay_code("abcd-2345")
    assert window.config["relay_code"] == "ABCD2345"
    assert connected == ["ABCD2345"]

    window.set_relay_code("")
    assert window.config["relay_code"] == ""
    assert window.relay.code is None
    assert window.relay_status_label.text() == tr("relay_off")


def test_switching_map_source_reloads(window):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    window.set_page(3)
    window.set_map_source("squadcalc")

    assert window.config["map_source"] == "squadcalc"
    assert window.map_page.page.requestedUrl().host() == "squadcalc.app"



def test_hold_timer_cleared_on_unreachable_error_and_reset(window):
    window.hold_timer.key_reader = lambda vk: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    def lay():
        window.distance_entry.setText("1000")
        window.fov_entry.setText("90")
        window.calculate()
        assert window.hold_timer.target is not None

    lay()
    window.distance_entry.setText("5000")
    window.calculate()
    assert window.hold_timer.target is None

    lay()
    window.fov_entry.setText("500")
    window.calculate()
    assert window.hold_timer.target is None

    lay()
    window.reset_offset()
    assert window.hold_timer.target is None


def test_hold_watch_follows_weapon_and_setting(window):
    window.hold_timer.key_reader = lambda vk: False

    window.select_weapon(AGS17)
    assert window.hold_timer.active

    window.select_weapon("RPG-29")
    assert not window.hold_timer.active

    window.select_weapon(AGS17)
    window.controls["hold_timer"].setChecked(False)
    window.controls["hold_timer"].toggled.emit(False)
    assert not window.hold_timer.active


def test_hold_readout_survives_rebuild(window):
    window.hold_timer.key_reader = lambda vk: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    window.set_language("en")

    assert not window.hold_label.isHidden()
    assert window.hold_label.text().startswith("S held 0.00 of")


def test_typed_value_survives_redelivery_of_the_same_target(window):
    from maplink import MapTarget

    target = MapTarget(1100, 4, 33.0)
    window.on_map_targets([target])
    assert window.distance_entry.text() == "1100"

    window.distance_entry.setText("1500")
    window.distance_entry.textEdited.emit("1500")
    assert window.map_target is None

    window.on_map_targets([target])
    assert window.distance_entry.text() == "1500"

    # A new target does take over again.
    window.on_map_targets([MapTarget(800, 0, 10.0)])
    assert window.distance_entry.text() == "800"


@pytest.mark.parametrize("edit", ["wheel", "hotkey_up", "hotkey_down"])
def test_wheel_and_distance_keys_forget_the_map_target(window, edit):
    from maplink import MapTarget

    window.on_map_targets([MapTarget(1100, 4, 33.0)])
    assert window.map_target is not None

    if edit == "wheel":
        window.distance_entry.stepped.emit()
    elif edit == "hotkey_up":
        window.distance_up()
    else:
        window.distance_down()

    assert window.map_target is None


def test_map_target_with_bad_fov_shows_the_fov_error(window):
    from maplink import MapTarget

    window.fov_entry.setText("")
    window.on_map_targets([MapTarget(900, 0, 1.0)])

    assert window.status_text() == tr("bad_fov")


def test_absurd_typed_distance_does_not_crash(window):
    window.select_weapon(AGS17)
    window.distance_entry.setText("1" + "0" * 200)
    window.calculate()

    assert window.status_text() == tr("bad_number")
    assert window.last_solution is None


def test_map_status_is_shown_on_start(window):
    assert window.map_label.text() == tr("map_follow_hint")
    assert window.relay_status_label.text() == tr("relay_off")


def test_reset_settings_reloads_map_and_drops_relay(window, monkeypatch):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(window.relay, "connect_relay", lambda: None)
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    window.set_page(3)
    window.set_map_source("squadcalc")
    window.set_relay_code("ABCD-2345")
    assert window.relay.code == "ABCD2345"

    window.reset_settings()

    assert window.config["map_source"] == "deadline"
    assert window.map_page.page.requestedUrl().host() == "calc.tk104.duckdns.org"
    assert window.relay.code is None


def test_close_drops_relay_and_key_watch(window, monkeypatch):
    monkeypatch.setattr(window.relay, "connect_relay", lambda: None)
    window.hold_timer.key_reader = lambda vk: False
    window.select_weapon(AGS17)
    window.set_relay_code("ABCD-2345")

    window.close()

    assert window.relay.code is None
    assert not window.hold_timer.active


def test_embedded_bridge_reads_a_real_page(window, monkeypatch):
    """The real poll: BRIDGE_SCRIPT runs in a page defining the bridge."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    import webmap
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    html = (
        "data:text/html,<script>window.squadBallistics={version:1,"
        "targets:()=>[{distance:612.4,heightDiff:-8.6,bearing:181}]}"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.set_page(3)

    clock = QElapsedTimer()
    clock.start()
    while window.distance_entry.text() != "612" and clock.elapsed() < 15000:
        QCoreApplication.processEvents()

    assert window.distance_entry.text() == "612"
    assert window.height_entry.text() == "-9"
    assert window.map_page.bridge_found is True


def test_hotkeys_are_polled_when_keys_can_be_read(app, tmp_path, monkeypatch):
    """Off Windows the bound keys are read like the hold timer's keys."""
    import sys as real_sys

    if real_sys.platform == "win32":
        pytest.skip("Windows registers hotkeys instead")

    import crosshair

    pressed = set()
    monkeypatch.setattr(crosshair, "system_key_reader", lambda: (lambda vk: vk in pressed))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    win = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))

    try:
        assert win._hotkey_poller.isActive()
        assert win._shortcuts == []

        calls = []
        monkeypatch.setattr(win, "toggle_overlay", lambda: calls.append("F8"))
        # Re-bind so the poller picks up the patched method.
        win.set_hotkey("toggle_overlay", "F8")
        poller = win._hotkey_poller

        F8 = 0x77
        pressed.add(F8)
        poller.timeout.emit()
        poller.timeout.emit()  # held: fires once
        pressed.discard(F8)
        poller.timeout.emit()
        pressed.add(F8)
        poller.timeout.emit()

        assert calls == ["F8", "F8"]
    finally:
        win.close()

    assert win._hotkey_poller is None
