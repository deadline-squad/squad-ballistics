import math
import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("qtawesome")

from PyQt6.QtWidgets import QApplication, QPushButton

import config
from ballistics import load_weapons, screen_offset, solve
from i18n import tr
from widgets import format_angle
from conftest import ROOT


@pytest.fixture
def app(qapp):
    return qapp


@pytest.fixture(autouse=True)
def offline_relay(monkeypatch):
    """The window joins the relay on start: tests stay off the live one."""
    from maplink import RelayLink

    monkeypatch.setattr(RelayLink, "connect_relay", lambda self: None)


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

        if math.isfinite(window.last_solution.hold_time) and window.current_weapon().aim == "overlay":
            # Laid by holding S (AGS-17 high arc): the readout is a time.
            assert window.status_text().startswith("S "), name
        else:
            assert any(
                c in window.status_text() for c in ("°", "mil", "мил")
            )

        assert len(window.current_steps) >= 2, name

        expected = window.current_offset()
        weapon = window.current_weapon()
        if weapon.aim == "elevation":
            # Laid on its own sight: no overlay mark
            assert expected is None and not window.overlay.mark_visible, name
        elif abs(expected) < window.overlay.height():
            assert window.overlay.mark_visible, name
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


@pytest.mark.parametrize("name", ["Mortar (M252 / 2B14 / L16 / Type 63)", "BM-21 Grad", "Hell Cannon"])
def test_no_overlay_mark_for_weapons_laid_by_elevation(window, name):
    # Laid on their own sight in mils/degrees: no mark, the info line stays.
    window.select_weapon(name)
    window.distance_entry.setText("900")
    window.calculate()
    assert window.last_solution.reachable
    assert not window.overlay.mark_visible
    assert window.overlay.target_offset == 0
    assert "900 m" in window.overlay.info_text
    assert window.stats["stat_offset"].value.text() == "—"

    window.reset_offset()
    assert not window.overlay.mark_visible


def test_overlay_mark_follows_the_weapon_aim(window):
    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    window.distance_entry.setText("")
    window.recalculate_if_ready()
    assert not window.overlay.mark_visible

    # Direct fire and the AGS-17 (its direct-fire aim) are aimed with the mark
    for name in ("SPG-9 · HEAT", "AGS-17 · emplacement"):
        window.select_weapon(name)
        window.distance_entry.setText("500")
        window.calculate()
        assert window.overlay.mark_visible, name
        assert window.overlay.target_offset > 0, name

    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    assert not window.overlay.mark_visible


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
    monkeypatch.setattr("crosshair.open_external", lambda url: opened.append(url) or True)

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
    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    window.distance_entry.setText("1000")
    window.height_entry.setText("")
    window.calculate()

    solution = window.last_solution
    assert solution.reachable
    assert window.status_text() == tr("hold_big", t=f"{solution.hold_time:.2f}")
    assert window.hold_timer.target == pytest.approx(solution.hold_time)
    assert any("S" in step for step in window.current_steps)
    assert "S " in window.overlay.info_text

    # The overlay mark shows the direct-fire aim at the same time.
    direct = window.direct_solution
    assert direct.reachable and direct.arc == "low"
    assert direct.angle < 45 < solution.angle
    assert window.overlay.offset == pytest.approx(
        screen_offset(
            direct.sight_angle,
            window.config["fov"],
            window.overlay.screen_width(),
            window.config["offset_scale"] / 100
        )
    )
    assert window.overlay.offset > 0
    direct_text = tr("direct_short", angle=f"{direct.sight_angle:.2f}°")
    assert direct_text in window.overlay.info_text
    assert direct_text in window.sub_label.text()
    assert window.current_steps[-1] == tr(
        "how_hold_direct", angle=f"{direct.sight_angle:.2f}°"
    )

    # Holding S reaches the target and the readout says so.
    window.hold_timer.advance(solution.hold_time + 0.01, True, False)
    assert window.hold_timer.is_reached
    assert "✓" in window.hold_label.text()
    assert "✓" in window.overlay.info_text

    # The low arc of the same weapon is direct fire with the overlay mark.
    window.config["arc"] = "low"
    window.calculate()
    assert window.hold_timer.target is None
    assert window.direct_solution is None
    assert "°" in window.status_text()
    assert window.current_offset() == pytest.approx(window.overlay.offset)
    assert window.current_offset() > 0


def test_ags17_too_close_to_lob_fires_directly(window):
    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    # The top of the hold range lands at 280 m: closer is direct fire only.
    window.distance_entry.setText("150")
    window.height_entry.setText("")
    window.calculate()

    solution = window.last_solution
    assert solution.reachable and solution.arc == "low"
    assert window.direct_solution is None
    assert window.hold_timer.target is None
    # Shown over the line of sight, like the mark.
    assert window.status_text() == f"{solution.sight_angle:.2f}°"
    assert tr("to_horizon", angle=f"{solution.angle:.2f}°") in window.sub_label.text()
    assert window.overlay.offset > 0
    assert any(
        tr("how_overlay_1", angle=f"{solution.sight_angle:.2f}°") in step
        for step in window.current_steps
    )

    # Beyond the reach of both arcs nothing is aimed.
    window.distance_entry.setText("5000")
    window.calculate()
    assert not window.last_solution.reachable
    assert window.direct_solution is None
    assert window.overlay.offset == 0.0


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

    # Kept to a tenth of a metre, not rounded to whole metres
    assert window.distance_entry.text() == "1234.4"
    assert window.height_entry.text() == "-12.6"
    assert window.last_solution.reachable
    assert window.last_solution.distance == pytest.approx(1234.4)
    assert window.last_solution.height_diff == pytest.approx(-12.6)
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

    # A build before the weapon export: targets only, the weapon stays.
    window.select_weapon("AT-4")
    page.on_bridge_result({
        "targets": [{"distance": 950.2, "heightDiff": 3.9, "bearing": 5}]
    })
    assert page.bridge_found is True
    assert window.picker.current == "AT-4"
    assert window.distance_entry.text() == "950.2"
    assert window.height_entry.text() == "3.9"

    # The weapon selected in SquadCalc is selected here and solved.
    page.on_bridge_result({
        "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
        "weapon": "M2A1 .50"
    })
    assert window.picker.current == "M2A1 .50"
    assert window.config["last_weapon"] == "M2A1 .50"
    assert window.distance_entry.text() == "420"
    assert window.last_solution.distance == 420
    expected = solve(window.weapons["M2A1 .50"], 420, -6, "low")
    assert window.last_solution.angle == pytest.approx(expected.angle)
    # The target is put on the mark: below the centre by the angle over the
    # line of sight, not by the (here negative) angle to the horizon.
    assert expected.angle < 0 < expected.sight_angle
    assert window.overlay.offset == pytest.approx(
        screen_offset(
            expected.sight_angle,
            window.config["fov"],
            window.overlay.screen_width(),
            window.config["offset_scale"] / 100
        )
    )
    assert window.overlay.offset > 0

    # A weapon picked here stays until the SquadCalc weapon changes.
    window.select_weapon("AT-4")
    page.on_bridge_result({
        "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
        "weapon": "M2A1 .50"
    })
    assert window.picker.current == "AT-4"

    page.load_source()
    assert page.bridge_found is None

    # A late answer after the map was shut down is ignored.
    page.shutdown()
    page.on_bridge_result({"targets": [{"distance": 300}], "weapon": "NSV"})
    assert page.bridge_found is None
    assert window.distance_entry.text() == "420"
    assert window.picker.current == "AT-4"


def test_map_weapon_is_followed_only_when_known_and_enabled(window):
    window.select_weapon("AT-4")

    window.on_map_weapon("Not a weapon here")
    assert window.picker.current == "AT-4"

    window.config["map_follow"] = False
    window.on_map_weapon("NSV")
    assert window.picker.current == "AT-4"

    window.config["map_follow"] = True
    window.on_map_weapon("NSV")
    assert window.picker.current == "NSV"

    # A SquadCalc page from before a rename sends the old name.
    window.on_map_weapon("BTR-4 AGS")
    assert window.picker.current == "AGS-30 / BTR-4 AGS"
    window.on_map_weapon("NSV")

    # Mod weapons hidden by the filter are not selected behind the user's back.
    mod_weapon = next(n for n, w in window.weapons.items() if w.mod)
    window.config["show_mods"] = False
    window.refresh_weapon_list()
    window.on_map_weapon(mod_weapon)
    assert window.picker.current == "NSV"


def test_relay_weapon_line_selects_the_weapon(window):
    import json

    window.select_weapon("AT-4")
    window.relay.on_message(json.dumps({
        "type": "targets",
        "text": "12.34 | 10.0° | 300m | +2m\nweapon: RPG-29"
    }))
    assert window.picker.current == "RPG-29"
    assert window.distance_entry.text() == "300"
    assert window.last_solution.angle == pytest.approx(
        solve(window.weapons["RPG-29"], 300, 2, "low").angle
    )


def test_relay_code_setting(window, monkeypatch):
    """A code typed in Settings (shown by a SquadCalc page) replaces the app's."""
    connected = []
    monkeypatch.setattr(window.relay, "connect_relay", lambda: connected.append(window.relay.code))
    code = window.config["relay_code"]

    for bad in ("bad!", ""):
        window.set_relay_code(bad)
        assert window.relay_status_label.text() == tr("relay_bad_code")
        assert window.config["relay_code"] == code
        assert window.relay.code == code

    window.set_relay_code("abcd-2345")
    assert window.config["relay_code"] == "ABCD2345"
    assert connected == ["ABCD2345"]
    assert window.relay_entry.text() == "ABCD-2345"
    assert window.device_link_entry.text() == "https://calc.tk104.duckdns.org/#link=ABCD2345"
    # Saved at once: a device paired with it must survive a crash.
    assert config.load_config()["relay_code"] == "ABCD2345"


def test_device_code_is_made_once_and_kept(window):
    from crosshair import MainWindow
    from maplink import CODE_ALPHABET, NEW_CODE_LENGTH, device_link

    code = window.config["relay_code"]

    assert len(code) == NEW_CODE_LENGTH and set(code) <= set(CODE_ALPHABET)
    assert window.relay.code == code
    assert window.device_link_entry.text() == device_link(code)
    assert config.load_config()["relay_code"] == code

    # The next start joins the same session: paired devices relink by themselves.
    restarted = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    try:
        assert restarted.config["relay_code"] == code
        assert restarted.relay.code == code
    finally:
        restarted.close()


def test_device_link_toggle(window):
    code = window.config["relay_code"]
    toggle = window.controls["relay_enabled"]

    toggle.setChecked(False)
    assert window.config["relay_enabled"] is False
    assert window.relay.code is None
    assert window.relay_status_label.text() == tr("relay_off")

    toggle.setChecked(True)
    assert window.relay.code == code
    assert window.config["relay_code"] == code


def test_new_device_code_needs_a_confirmation(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    code = window.config["relay_code"]
    answers = [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: answers.pop(0))

    window.renew_relay_code()
    assert window.config["relay_code"] == code

    window.renew_relay_code()
    new_code = window.config["relay_code"]
    assert new_code != code
    assert window.relay.code == new_code
    assert new_code in window.device_link_entry.text()
    assert config.load_config()["relay_code"] == new_code


def test_device_qr_code_scans_to_the_link(window):
    """The QR code the card shows, read by an independent decoder."""
    zxingcpp = pytest.importorskip("zxingcpp")
    from PyQt6.QtGui import QImage

    image = window.device_qr.pixmap().toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    width, height = image.width(), image.height()
    rows = image.constBits().asstring(image.bytesPerLine() * height)
    pixels = b"".join(
        rows[y * image.bytesPerLine():y * image.bytesPerLine() + width] for y in range(height)
    )

    results = zxingcpp.read_barcodes(
        zxingcpp.ImageView(pixels, width, height, zxingcpp.ImageFormat.Lum)
    )

    assert [result.text for result in results] == [window.device_link_entry.text()]


def test_copy_device_link(window):
    button = next(b for b in window.findChildren(QPushButton) if b.text() == tr("s_device_copy"))

    button.click()

    assert QApplication.clipboard().text() == window.device_link_entry.text()
    assert button.text() == tr("s_device_copied")


def test_switching_map_source_reloads(window):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    window.set_page(3)
    window.set_map_source("squadcalc")

    assert window.config["map_source"] == "squadcalc"
    assert window.map_page.page.requestedUrl().host() == "squadcalc.app"



def test_hold_timer_cleared_on_unreachable_error_and_reset(window):
    window.hold_timer.key_reader = lambda code: False
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
    window.hold_timer.key_reader = lambda code: False

    window.select_weapon(AGS17)
    assert window.hold_timer.active

    window.select_weapon("RPG-29")
    assert not window.hold_timer.active

    window.select_weapon(AGS17)
    window.controls["hold_timer"].setChecked(False)
    window.controls["hold_timer"].toggled.emit(False)
    assert not window.hold_timer.active


def test_hold_readout_survives_rebuild(window):
    window.hold_timer.key_reader = lambda code: False
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
    assert window.relay_status_label.text() == tr(f"relay_{window.relay.status}")


def test_reset_settings_reloads_map_and_keeps_device_code(window, monkeypatch):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    window.set_page(3)
    window.set_map_source("squadcalc")
    window.set_relay_code("ABCD-2345")
    window.controls["relay_enabled"].setChecked(False)
    assert window.relay.code is None

    window.reset_settings()

    assert window.config["map_source"] == "deadline"
    assert window.map_page.page.requestedUrl().host() == "calc.tk104.duckdns.org"
    # The pairing survives the reset; the link is on again (the default).
    assert window.config["relay_code"] == "ABCD2345"
    assert window.config["relay_enabled"] is True
    assert window.relay.code == "ABCD2345"


def test_close_drops_relay_and_key_watch(window):
    window.hold_timer.key_reader = lambda code: False
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
        "data:text/html;charset=utf-8,<script>window.squadBallistics={version:2,"
        "targets:()=>[{distance:612.4,heightDiff:-8.6,bearing:181}],"
        "weapon:()=>'RPG-7V1 · HEAT'}"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.select_weapon("AT-4")
    window.set_page(3)

    clock = QElapsedTimer()
    clock.start()
    while window.distance_entry.text() != "612.4" and clock.elapsed() < 15000:
        QCoreApplication.processEvents()

    assert window.distance_entry.text() == "612.4"
    assert window.height_entry.text() == "-8.6"
    assert window.map_page.bridge_found is True
    assert window.picker.current == "RPG-7V1 · HEAT"
    assert window.last_solution.angle == pytest.approx(
        solve(window.weapons["RPG-7V1 · HEAT"], 612.4, -8.6, "low").angle
    )


def test_weapon_picked_here_is_selected_on_the_embedded_map(window, monkeypatch):
    """Two-way weapon sync: the map draws its coverage for the app's weapon."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    import webmap
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    # A page like SquadCalc: selectWeapon() only accepts the weapons it has.
    html = (
        "data:text/html;charset=utf-8,<script>"
        "var known=['QLZ87','AT-4'];var current='AT-4';var calls=[];"
        "window.squadBallistics={version:3,"
        "targets:()=>[{distance:500,heightDiff:0,bearing:0}],"
        "weapon:()=>current,"
        "selectWeapon:(n)=>{calls.push(n);if(known.indexOf(n)<0)return false;current=n;return true;}};"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.set_page(3)
    page = window.map_page

    def wait_for(condition):
        clock = QElapsedTimer()
        clock.start()
        while not condition() and clock.elapsed() < 15000:
            QCoreApplication.processEvents()
        return condition()

    def page_value(expression):
        result = []
        page.page.runJavaScript(expression, 0, result.append)
        assert wait_for(lambda: result)
        return result[0]

    # The page's weapon comes first (the bridge is polled).
    assert wait_for(lambda: window.picker.current == "AT-4" and page.last_weapon == "AT-4")

    window.select_weapon("QLZ87")
    assert wait_for(lambda: page_value("current") == "QLZ87")
    assert wait_for(lambda: page.last_weapon == "QLZ87")
    assert window.picker.current == "QLZ87"

    # A weapon the page does not have: the page keeps its own and does not
    # switch the app back (no ping-pong).
    window.select_weapon("NSV")
    assert wait_for(lambda: "NSV" in page_value("calls.join(',')"))
    for _ in range(20):
        QCoreApplication.processEvents()
    page.poll_targets()
    assert wait_for(lambda: page_value("current") == "QLZ87")
    assert window.picker.current == "NSV"


def test_embedded_bridge_reads_a_page_without_the_weapon(window, monkeypatch):
    """A SquadCalc build before the weapon export (bridge version 1)."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    import webmap
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    html = (
        "data:text/html,<script>window.squadBallistics={version:1,"
        "targets:()=>[{distance:333,heightDiff:2,bearing:10}]}"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.select_weapon("AT-4")
    window.set_page(3)

    clock = QElapsedTimer()
    clock.start()
    while window.distance_entry.text() != "333" and clock.elapsed() < 15000:
        QCoreApplication.processEvents()

    assert window.distance_entry.text() == "333"
    assert window.map_page.bridge_found is True
    assert window.picker.current == "AT-4"


def test_hotkeys_are_polled_when_keys_can_be_read(app, tmp_path, monkeypatch):
    """The bound keys are read like the hold timer's keys."""
    import crosshair
    from hotkeys import KEYS

    pressed = set()
    monkeypatch.setattr(crosshair, "system_key_reader", lambda: (lambda code: code in pressed))
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

        F8 = KEYS["F8"]
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


def test_timer_panel_on_the_overlay(window):
    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"

    panel = window.overlay.hold_panel
    assert panel is not None
    assert panel.target is None
    assert panel.target_text == tr("panel_no_target")
    assert panel.barrel_text.startswith("~280 ") or panel.barrel_text.startswith("~279 ")

    window.distance_entry.setText("1000")
    window.calculate()
    panel = window.overlay.hold_panel
    assert panel.target == pytest.approx(window.last_solution.hold_time)
    assert "1000" in panel.target_text

    window.hold_timer.advance(0.8, True, False)
    panel = window.overlay.hold_panel
    assert panel.held == pytest.approx(0.8)
    assert panel.s_down
    assert not panel.reached
    assert panel.barrel_text != "~280 м"

    window.hold_timer.advance(0.5, True, False)
    assert window.overlay.hold_panel.reached

    # Panel off, other weapon: hidden.
    window.controls["hold_panel"].toggled.emit(False)
    assert window.overlay.hold_panel is None
    window.controls["hold_panel"].toggled.emit(True)
    assert window.overlay.hold_panel is not None
    window.select_weapon("RPG-29")
    assert window.overlay.hold_panel is None


@pytest.mark.parametrize("corner", ["top_left", "top_right", "bottom_left", "bottom_right"])
def test_timer_panel_corner(window, corner):
    window.set_hold_panel_corner(corner)

    rect = window.overlay.hold_panel_rect()
    overlay = window.overlay

    assert (rect.left() < overlay.width() / 2) == corner.endswith("left")
    assert (rect.top() < overlay.height() / 2) == corner.startswith("top")
    assert window.config["hold_panel_corner"] == corner


def test_auto_hold_setting(window, monkeypatch):
    import crosshair

    pressed = []

    class Injector:
        closed = False

        def press(self):
            pressed.append("press")

        def release(self):
            pressed.append("release")

        def close(self):
            Injector.closed = True

    # Not possible on this system: the setting turns itself off.
    monkeypatch.setattr(crosshair, "system_key_injector", lambda code: None)
    window.controls["auto_hold"].setChecked(True)
    window.controls["auto_hold"].toggled.emit(True)
    assert window.config["auto_hold"] is False
    assert window.hold_timer.auto_hold is None
    assert window.auto_hold_status.text() == tr("auto_hold_unavailable")

    monkeypatch.setattr(crosshair, "system_key_injector", lambda code: Injector())
    window.controls["auto_hold"].toggled.emit(True)
    assert window.config["auto_hold"] is True
    assert window.hold_timer.auto_hold is not None
    assert window.auto_hold_status.text() == ""

    from hotkeys import bindings
    assert ("F7", "auto_hold") in bindings(window)

    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    window.auto_hold()
    assert window.hold_timer.auto_holding
    assert window.overlay.hold_panel is not None

    window.close()
    assert pressed == ["press", "release"]
    assert Injector.closed


MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


def test_mortar_shows_mils_with_the_auto_lay_time(window):
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    solution = window.last_solution
    assert solution.reachable and math.isfinite(solution.hold_time)
    # The sight reads mils: they stay the big readout, the hold time is the auto-lay helper
    assert window.status_text() == format_angle(solution.angle, "mil")
    assert tr("lay_short", t=f"{solution.hold_time:.2f}") in window.sub_label.text()
    assert f"S {solution.hold_time:.2f}" in window.overlay.info_text
    assert not window.overlay.mark_visible
    assert any(tr("how_lay_off", t=f"{solution.hold_time:.2f}") == step for step in window.current_steps)


def test_mortar_auto_lay_hotkey(window, monkeypatch):
    import crosshair

    log = []

    class Injector:
        def __init__(self, code):
            self.code = code

        def press(self):
            log.append((self.code, "press"))

        def release(self):
            log.append((self.code, "release"))

        def close(self):
            pass

    monkeypatch.setattr(crosshair, "system_key_injector", Injector)
    window.controls["auto_hold"].toggled.emit(True)
    window.hold_timer.key_reader = lambda code: False
    window.hold_timer.set_active(True)

    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    weapon = window.current_weapon()
    assert any(tr("how_lay", hotkey="F7", t=f"{window.last_solution.hold_time:.2f}") == step
               for step in window.current_steps)

    started = []
    monkeypatch.setattr(window.hold_timer.auto_hold, "start",
                        lambda seconds, reset_seconds=0.0: started.append((seconds, reset_seconds)) or True)
    window.auto_hold()
    assert started == [(pytest.approx(window.last_solution.hold_time),
                        pytest.approx(weapon.max_hold_time() + crosshair.LAY_RESET_MARGIN))]

    # The AGS-17 still holds only the time left (the player presses W)
    started.clear()
    window.select_weapon(AGS17)
    window.distance_entry.setText("1000")
    window.calculate()
    window.auto_hold()
    assert started == [(pytest.approx(window.hold_timer.target), 0.0)]


def test_mortar_auto_lay_calibration(window):
    window.select_weapon(MORTAR)
    assert window.lay_row.isVisibleTo(window)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    top = window.current_weapon().hold_elevation[1]

    # Too short a hold measures nothing
    window.hold_timer.held = 0.2
    window.lay_entry.setText("1500")
    assert not window.calibrate_lay()
    assert window.lay_status.text() == tr("lay_need_hold", t="0.5")

    # 3 s of S and the sight shows the angle of 8.5°/s: that rate is kept
    window.hold_timer.held = 3.0
    window.lay_entry.setText(f"{(top - 3.0 * 8.5) * 6400 / 360:.4f}")
    assert window.calibrate_lay()
    assert window.config["lay_rates"][MORTAR] == pytest.approx(8.5, abs=1e-4)
    assert window.current_weapon().hold_rate == pytest.approx(8.5, abs=1e-4)
    assert window.last_solution.hold_time == pytest.approx((top - window.last_solution.angle) / 8.5, rel=1e-4)
    assert window.file_weapons[MORTAR].hold_rate == 9.0

    # A typo (15°/s) is refused and changes nothing
    window.lay_entry.setText(f"{(top - 3.0 * 15) * 6400 / 360:.1f}")
    assert not window.calibrate_lay()
    assert window.current_weapon().hold_rate == pytest.approx(8.5, abs=1e-4)

    window.reset_lay_rate()
    assert MORTAR not in window.config["lay_rates"]
    assert window.current_weapon().hold_rate == 9.0

    # Weapons without the auto-lay have no calibration row
    window.select_weapon(AGS17)
    assert not window.lay_row.isVisibleTo(window)


def test_auto_hold_key_is_free_while_disabled(window):
    from hotkeys import bindings

    assert window.config["auto_hold"] is False
    assert all(action != "auto_hold" for _key, action in bindings(window))


def test_map_target_profile_warns_about_the_obstacle(window):
    from maplink import MapTarget

    window.select_weapon("Tank AP · M256 / Rh120")
    profile = [0.0] * 301
    profile[150] = profile[151] = 10.0

    window.on_map_targets([MapTarget(300, 0, 10.0, tuple(profile), 1)])

    assert window.trajectory_view.obstacle == (150, 10.0)
    assert len(window.trajectory_view.terrain) == 301
    assert tr("blocked_short", d="150") in window.overlay.info_text
    assert tr("how_blocked", arc=tr("arc_low"), d="150", h="+10") in window.current_steps

    # A clear profile gives no warning.
    window.on_map_targets([MapTarget(301, 0, 10.0, tuple([0.0] * 302), 1)])
    assert window.trajectory_view.obstacle is None
    assert not any("⛔" in step for step in window.current_steps)


def test_blocked_direct_fire_suggests_the_lob(window):
    from maplink import MapTarget

    window.select_weapon(AGS17)
    window.config["arc"] = "low"
    profile = [0.0] * 601
    profile[300] = 40.0

    window.on_map_targets([MapTarget(600, 0, 10.0, tuple(profile), 1)])

    assert window.last_solution.arc == "low"
    assert window.trajectory_view.obstacle == (300, 40.0)
    hold = solve(window.current_weapon(), 600, 0, "high").hold_time
    assert tr("how_blocked_use", arc=tr("arc_high"), angle=f"S {hold:.2f} {tr('unit_s')}") in window.current_steps

    # Typed inputs have no profile: no warning.
    window.distance_entry.textEdited.emit("600")
    window.calculate()
    assert window.trajectory_view.obstacle is None


def sight_at(mils):
    """A grab of the mortar sight showing `mils` (ScreenSight.grab)."""
    from sightimage import draw_sight
    from sightlay import Sight
    from sightreader import GrayImage

    return Sight(GrayImage.from_qimage(draw_sight(mils, 1280, 720)), 640, 360, 720 / 1080)


def test_mortar_sight_reading_on_the_overlay(window, monkeypatch):
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1043.4))
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    assert window.sight_timer.isActive()

    window.watch_sight()
    target = window.last_solution.angle * 6400 / 360
    assert tr("sight_reading_left", mils="1043.4", left=f"{target - 1043.4:+.1f}") in window.overlay.info_text
    assert window.overlay.info_text.startswith(window.info_base)

    # The sight off the screen: the reading goes
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)
    window.watch_sight()
    assert "1043.4" not in window.overlay.info_text

    # Turned off, or another weapon: not read
    window.controls["sight_reader"].toggled.emit(False)
    assert not window.sight_timer.isActive()
    window.controls["sight_reader"].toggled.emit(True)
    assert window.sight_timer.isActive()
    window.select_weapon(AGS17)
    assert not window.sight_timer.isActive()


def test_mortar_auto_lay_on_the_sight(window, monkeypatch):
    import crosshair

    class Injector:
        def __init__(self, code):
            self.code = code

        def press(self):
            pass

        def release(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(crosshair, "system_key_injector", Injector)
    window.controls["auto_hold"].toggled.emit(True)
    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    layer = window.sight_layer
    assert layer is not None
    assert layer.raise_key.code == crosshair.KEY_W and layer.lower_key.code == crosshair.KEY_S
    assert window.sight_target() == pytest.approx(window.last_solution.angle * 6400 / 360)

    timed = []
    monkeypatch.setattr(window.hold_timer.auto_hold, "start",
                        lambda seconds, reset_seconds=0.0: timed.append(seconds) or True)

    # The sight is seen: the lay is on it, not timed; the key again stops it
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))
    window.auto_hold()
    assert layer.active and timed == []
    assert not window.sight_timer.isActive()
    window.auto_hold()
    assert not layer.active
    assert window.sight_timer.isActive()

    # Not seen: the timed lay
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)
    window.auto_hold()
    assert not layer.active and timed == [pytest.approx(window.last_solution.hold_time)]

    # Reading turned off: timed even with the sight on the screen
    timed.clear()
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))
    window.config["sight_reader"] = False
    window.auto_hold()
    assert not layer.active and len(timed) == 1

    window.close()
    assert window.sight_layer is None


def compass_at(degrees):
    """A grab of the compass strip showing `degrees` (grab_compass)."""
    from compassimage import draw_compass
    from sightlay import Sight
    from sightreader import GrayImage

    strip = draw_compass(degrees, 1280, 720).copy(0, 640, 1280, 80)

    return Sight(GrayImage.from_qimage(strip), 640.0, 0, 720 / 1080)


def test_mortar_auto_lay_turns_to_the_map_bearing_first(window, monkeypatch):
    """A SquadCalc target: F7 turns the mortar on the compass (D/A), then
    lays the elevation on the sight; the bearing left shows on the overlay."""
    import crosshair
    from maplink import MapTarget

    class Injector:
        def __init__(self, code):
            self.code = code

        def press(self):
            pass

        def release(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(crosshair, "system_key_injector", Injector)
    window.controls["auto_hold"].toggled.emit(True)
    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.on_map_targets([MapTarget(900, 4.0, 123.4)])

    turning = window.bearing_layer
    assert turning is not None
    assert turning.raise_key.code == crosshair.KEY_D and turning.lower_key.code == crosshair.KEY_A
    assert window.bearing_target() == pytest.approx(123.4)

    monkeypatch.setattr(window.screen_sight, "grab_compass", lambda: compass_at(120.0))
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(1100.0))

    window.watch_sight()
    assert "+3.4" in window.overlay.info_text

    window.auto_hold()
    assert turning.active and not window.sight_layer.active

    # The key again stops the whole lay, the elevation is not laid
    window.auto_hold()
    assert not turning.active and not window.sight_layer.active
    assert window.sight_timer.isActive()

    # Turned (the lay ended by itself): the elevation is laid next
    window.auto_hold()
    assert turning.active
    turning.finish(True)
    assert window.sight_layer.active

    window.auto_hold()
    assert not window.sight_layer.active

    # A typed target has no bearing: straight to the elevation
    window.distance_entry.setText("1000")
    window.forget_map_target()
    assert window.bearing_target() is None
    window.auto_hold()
    assert not turning.active and window.sight_layer.active
    window.auto_hold()

    window.close()
    assert window.bearing_layer is None


def test_mortar_calibration_reads_the_sight(window, monkeypatch, tmp_path):
    import crosshair

    monkeypatch.setattr(crosshair, "config_dir", lambda: str(tmp_path / "settings"))
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    top = window.current_weapon().hold_elevation[1]
    window.hold_timer.held = 3.0
    window.lay_entry.clear()

    # Not read: what was grabbed is saved for a look
    from PyQt6.QtGui import QImage
    grabbed = QImage(64, 32, QImage.Format.Format_RGB32)
    grabbed.fill(0)
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)
    monkeypatch.setattr(window.screen_sight, "grab_image", lambda: grabbed)
    assert not window.calibrate_lay()
    path = os.path.join(str(tmp_path / "settings"), "sight-grab.png")
    assert window.lay_status.text() == tr("lay_no_sight", path=path)
    assert QImage(path).size() == grabbed.size()

    shown = (top - 3.0 * 8.5) * 6400 / 360
    monkeypatch.setattr(window.screen_sight, "grab", lambda: sight_at(shown))
    assert window.calibrate_lay()
    assert window.config["lay_rates"][MORTAR] == pytest.approx(8.5, abs=0.01)


LONGEST_NAME = "Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2"


def show_at(window, width, height):
    """Show the window at a size and let the layouts settle."""
    from PyQt6.QtCore import QEvent

    window.show()
    window.resize(width, height)

    for _ in range(3):
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def calc_page_overflow(window):
    """Pixels the calculator page is wider than its scroll area (0: fits)."""
    window.set_page(0)
    area = window.pages.currentWidget()
    QApplication.processEvents()

    return max(0, area.widget().width() - area.viewport().width())


@pytest.mark.parametrize("language", ["en", "ru"])
def test_calculator_fits_the_minimum_window(window, language):
    window.set_language(language)
    show_at(window, 900, 600)

    window.select_weapon(AGS17)
    window.distance_entry.setText("600")
    window.calculate()
    assert calc_page_overflow(window) == 0, "stat tiles"

    window.distance_entry.setText("0")
    window.calculate()
    assert calc_page_overflow(window) == 0, "error readout"

    window.select_weapon(MORTAR)
    window.distance_entry.setText("800")
    window.calculate()
    assert calc_page_overflow(window) == 0, "calibration row"

    window.lay_status.setText(tr("lay_no_sight", path="/home/player/.config/SquadBallistics/sight-grab.png"))
    assert calc_page_overflow(window) == 0, "calibration status"

    window.select_weapon(LONGEST_NAME)
    window.distance_entry.setText("300")
    window.calculate()
    assert calc_page_overflow(window) == 0, "weapon name"


def test_long_weapon_name_is_elided_in_the_picker(window):
    show_at(window, 1180, 780)
    window.select_weapon(LONGEST_NAME)
    QApplication.processEvents()

    picker = window.picker
    assert picker.current == LONGEST_NAME
    assert picker.toolTip() == LONGEST_NAME
    assert "…" in picker.text()
    assert picker.sizeHint().width() <= picker.width()

    window.select_weapon(AGS17)
    assert picker.text() == f"{AGS17}   ▾"


@pytest.mark.parametrize("language", ["en", "ru"])
def test_crosshair_page_fits_the_minimum_window(window, language):
    window.set_language(language)
    show_at(window, 900, 600)
    window.set_page(1)
    QApplication.processEvents()

    from crosshair import PRESETS

    names = {tr(f"preset_{key}") for key in PRESETS}
    buttons = [b for b in window.pages.currentWidget().findChildren(QPushButton) if b.text() in names]

    assert len(buttons) == len(PRESETS)

    for button in buttons:
        assert button.width() >= button.sizeHint().width(), button.text()
        # Nothing laid over the preview
        assert button.mapTo(window, button.rect().topLeft()).y() > \
            window.preview.mapTo(window, window.preview.rect().bottomLeft()).y()


def test_window_fits_the_screen(window):
    available = window.screen().availableGeometry()

    assert window.width() == max(900, min(1180, available.width()))
    assert window.height() <= max(600, available.height())
    assert window.height() == max(600, min(780, available.height() - 40))


LONG_INFO = "1150 m  ·  1016 mil  ·  S 3.53 s  ·  S held 1.23 of 2.13 s  ·  sight 1041.5 mil (+4.6)"


def ink_box(overlay, left):
    """(right, top, bottom) of what is painted on the overlay right of `left`."""
    image = overlay.grab().toImage()
    right, top, bottom = None, None, None

    for y in range(0, image.height(), 2):
        for x in range(int(left), image.width(), 2):
            if image.pixelColor(x, y).alpha() > 0:
                right = x if right is None else max(right, x)
                top = y if top is None else top
                bottom = y

    return right, top, bottom


def test_overlay_info_line_is_drawn_whole_on_a_wide_screen(window):
    from PyQt6.QtGui import QFontMetricsF

    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)
    overlay.set_offset(None)
    overlay.set_info(LONG_INFO)

    font = overlay.info_font()
    width = QFontMetricsF(font, overlay).horizontalAdvance(LONG_INFO)
    assert width > 450

    start = overlay.center_x + 20
    right, top, bottom = ink_box(overlay, start)

    # The whole line, not the first 400 px of it
    assert right > start + width - 20
    assert bottom - top < 30


def test_overlay_info_line_wraps_inside_a_narrow_screen(window):
    overlay = window.overlay
    overlay.setGeometry(0, 0, 640, 480)
    overlay.set_offset(None)
    overlay.set_info(LONG_INFO)

    right, top, bottom = ink_box(overlay, overlay.center_x + 20)

    assert right < overlay.width() - 2
    # More than one line
    assert bottom - top > 25


def test_hold_progress_repaints_only_the_info_line(window):
    from PyQt6.QtCore import QEvent, QObject, QPoint

    class Regions(QObject):
        def __init__(self):
            super().__init__()
            self.regions = []

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                self.regions.append(event.region())
            return False

    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(AGS17)
    window.distance_entry.setText("900")
    window.calculate()
    assert window.hold_timer.active

    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)
    QApplication.processEvents()

    regions = Regions()
    overlay.installEventFilter(regions)

    for _ in range(5):
        window.hold_timer.advance(0.01, True, False)
        QApplication.processEvents()

    overlay.removeEventFilter(regions)

    assert regions.regions
    assert tr("hold_progress", held="0.05", t=f"{window.hold_timer.target:.2f}") in overlay.info_text

    # Far from the label and the timer panel: never repainted
    for region in regions.regions:
        assert not region.contains(QPoint(5, 1075))
        assert not region.contains(QPoint(5, 5))


def test_unchanged_info_is_not_repainted(window):
    from PyQt6.QtCore import QEvent, QObject

    class Count(QObject):
        paints = 0

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                self.paints += 1
            return False

    overlay = window.overlay
    overlay.set_info("600 m  ·  12.00°")
    QApplication.processEvents()

    count = Count()
    overlay.installEventFilter(count)
    overlay.set_info("600 m  ·  12.00°")
    QApplication.processEvents()
    overlay.removeEventFilter(count)

    assert count.paints == 0


def test_hold_progress_does_not_lay_out_the_window(window):
    from PyQt6.QtCore import QEvent, QObject

    class Requests(QObject):
        count = 0

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.LayoutRequest:
                self.count += 1
            return False

    window.hold_timer.key_reader = lambda code: False
    show_at(window, 1180, 780)
    window.select_weapon(AGS17)
    window.distance_entry.setText("900")
    window.calculate()
    window.hold_timer.advance(0.01, True, False)

    # Let the layout settle after the solution (a request per level)
    for _ in range(10):
        QApplication.processEvents()

    assert window.hold_label.isVisible()

    requests = Requests()
    QApplication.instance().installEventFilter(requests)

    for _ in range(5):
        window.hold_timer.advance(0.01, True, False)
        QApplication.processEvents()

    QApplication.instance().removeEventFilter(requests)

    assert window.hold_label.text() == tr("hold_progress", held="0.06", t=f"{window.hold_timer.target:.2f}")
    assert requests.count == 0


def test_close_stops_the_sight_watch(window):
    window.select_weapon(MORTAR)
    assert window.sight_timer.isActive()

    window.close()

    assert not window.sight_timer.isActive()


def test_reset_settings_drops_the_calibration_and_the_fov(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window.select_weapon(MORTAR)
    window.config["lay_rates"][MORTAR] = 9.9
    window.apply_lay_rates()
    window.fov_entry.setText("75")
    window.distance_entry.setText("900")
    window.calculate()
    assert window.config["fov"] == 75

    window.reset_settings()

    assert window.weapons[MORTAR].hold_rate == window.file_weapons[MORTAR].hold_rate
    assert window.fov_entry.text() == "90"
    assert window.config["fov"] == 90
    # The typed target stays
    assert window.distance_entry.text() == "900"


def test_calibration_status_is_cleared_with_the_weapon(window):
    window.select_weapon(MORTAR)
    window.lay_status.setText(tr("lay_done", rate="9.10", base="9"))

    window.select_weapon("BM-21 Grad")
    window.select_weapon(MORTAR)

    assert window.lay_status.text() == ""


def test_map_progress_bar_follows_the_accent(window):
    window.set_accent("#22c55e")

    assert "#22c55e" in window.map_page.progress.styleSheet()


def test_map_failed_panel_names_the_map_site(window):
    page = window.map_page

    page.show_panel("failed")
    assert "calc.tk104.duckdns.org" in page.panel_text.text()

    window.config["map_source"] = "squadcalc"
    page.show_panel("failed")
    assert "squadcalc.app" in page.panel_text.text()


def test_auto_hold_toggle_is_off_when_keys_cannot_be_sent(app, tmp_path, monkeypatch):
    import crosshair

    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(crosshair, "system_key_injector", lambda code: None)

    saved = config.load_config()
    saved["auto_hold"] = True
    config.save_config(saved)

    win = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))

    try:
        assert win.config["auto_hold"] is False
        assert not win.controls["auto_hold"].isChecked()
    finally:
        win.close()


def test_hotkey_hint_lists_only_bound_keys(window):
    def hint():
        return window.hotkey_hint.text()

    # Auto-hold is off: its key is not bound and not listed
    assert "F8" in hint()
    assert "F7" not in hint()

    class Injector:
        def press(self):
            pass

        def release(self):
            pass

        def close(self):
            pass

    import crosshair

    original = crosshair.system_key_injector
    crosshair.system_key_injector = lambda code: Injector()

    try:
        window.controls["auto_hold"].toggled.emit(True)
        assert f"F7 — {tr('hk_auto_hold')}".replace(" ", crosshair.NBSP) in hint()

        window.controls["auto_hold"].toggled.emit(False)
        assert "F7" not in hint()
    finally:
        crosshair.system_key_injector = original


def test_calibrate_without_mils_says_what_is_missing(window, monkeypatch):
    window.select_weapon(MORTAR)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()
    window.hold_timer.held = 3.0
    window.lay_entry.clear()

    # Nothing typed and the sight is not read: the mils are asked for
    window.config["sight_reader"] = False
    assert not window.calibrate_lay()
    assert window.lay_status.text() == tr("lay_need_mils")

    # The screen cannot be grabbed at all: no grab to point to
    window.config["sight_reader"] = True
    monkeypatch.setattr(window.screen_sight, "grab", lambda: None)
    monkeypatch.setattr(window.screen_sight, "grab_image", lambda: None)
    assert not window.calibrate_lay()
    assert window.lay_status.text() == tr("lay_no_grab")


def test_range_ladder_follows_the_weapon(window):
    """Direct-fire weapons get range ticks under the mark, without a
    distance typed; weapons laid by elevation get none."""
    from ballistics import range_ladder

    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.distance_entry.setText("")
    window.select_weapon("RPG-7 · PG-7V HEAT / OG-7V")
    window.recalculate_if_ready()

    ladder = window.overlay.ladder
    assert len(ladder) >= 3
    first, spacing, reach = window.overlay.ladder_bounds()
    assert ladder == range_ladder(window.current_weapon(), window.config["fov"], 1920, first, spacing, reach)

    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    assert window.overlay.ladder == []


def test_range_ladder_follows_fov_calibration_and_toggle(window):
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.distance_entry.setText("200")
    window.fov_entry.setText("90")
    window.calculate()
    wide = dict(window.overlay.ladder)

    window.fov_entry.setText("60")
    window.calculate()
    narrow = dict(window.overlay.ladder)
    shared = set(wide) & set(narrow)
    assert shared
    assert all(narrow[d] > wide[d] for d in shared)

    window.set_setting("range_ladder", False)
    assert window.overlay.ladder == []

    window.set_setting("range_ladder", True)
    assert window.overlay.ladder


def test_range_ladder_is_drawn_left_of_the_centre(window):
    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.distance_entry.setText("")
    window.recalculate_if_ready()
    distance, offset = overlay.ladder[0]

    image = overlay.grab().toImage()
    y = round(overlay.center_y + offset)
    centre = int(overlay.center_x)
    painted = [x for x in range(centre - 120, centre) if image.pixelColor(x, y).alpha() > 0]

    # The tick and its label, left of the centre line, clear of the right side
    assert painted and max(painted) < centre
    assert all(image.pixelColor(x, y).alpha() == 0 for x in range(centre + 40, centre + 120))


def test_hotkey_hint_wraps_only_between_entries(window):
    from crosshair import HINT_SEPARATOR

    window.set_hotkey("distance_up", "PgUp")
    window.set_hotkey("distance_down", "PgDown")

    entries = window.hotkey_hint.text().split(HINT_SEPARATOR)

    assert len(entries) == 4
    # A plain space is a line break opportunity: none inside an entry
    assert all(" " not in entry for entry in entries)
    assert entries[2] == f"PgUp — {tr('hk_distance_up')}".replace(" ", "\u00a0")


def test_trajectory_view_keeps_flat_shots_flat():
    from widgets import MIN_VIEW_HEIGHT_SHARE, VIEW_PAD, view_bounds

    # A tank shell rising 0.2 m over 400 m: drawn in a view 40 m tall,
    # not stretched into an arc filling it.
    max_x, low, high = view_bounds([(0.0, 0.0), (200.0, 0.2), (400.0, 0.0)])
    assert max_x == 400
    assert high - low == pytest.approx(400 * MIN_VIEW_HEIGHT_SHARE * (1 + 2 * VIEW_PAD))
    assert low == pytest.approx(-400 * MIN_VIEW_HEIGHT_SHARE * VIEW_PAD)

    # A real arc keeps its own height
    max_x, low, high = view_bounds([(0.0, 0.0), (200.0, 300.0), (400.0, 0.0)])
    assert (low, high) == (pytest.approx(-300 * VIEW_PAD), pytest.approx(300 * (1 + VIEW_PAD)))

    # A target far below: the drop is tall enough on its own
    max_x, low, high = view_bounds([(0.0, 0.0), (250.0, -60.0)])
    assert (low, high) == (pytest.approx(-60 - 60 * VIEW_PAD), pytest.approx(60 * VIEW_PAD))


def test_typing_reports_bad_input_but_not_an_empty_distance(window):
    window.select_weapon("RPG-29")

    window.distance_entry.setText("500")
    window.fov_entry.setText("300")
    window.calculate(show_errors=False)
    assert window.status_text() == tr("bad_fov")
    assert window.big_label.property("state") == "error"

    window.fov_entry.setText("90")
    window.distance_entry.setText("0")
    window.calculate(show_errors=False)
    assert window.status_text() == tr("bad_distance")

    window.distance_entry.setText("")
    window.calculate(show_errors=False)
    assert window.status_text() == tr("ready")
    assert window.big_label.property("state") == ""


def test_message_boxes_are_readable(window, app):
    import theme
    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox(window)
    box.setText("Reset all crosshair and app settings?")
    box.show()
    app.processEvents()

    try:
        image = box.grab().toImage()
        background = image.pixelColor(4, image.height() // 2).name()

        assert theme.contrast(background, theme.TEXT) >= 4.5
    finally:
        box.close()


@pytest.mark.parametrize("accent", __import__("theme").ACCENTS)
def test_text_on_the_accent_is_readable(accent):
    import theme

    text = theme.on_accent(accent)

    assert theme.contrast(text, accent) >= theme.MIN_TEXT_CONTRAST
    # Buttons, checked segments and selected rows all use it
    assert theme.stylesheet(accent).count(f"color: {text};") >= 3
    assert "color: white" not in theme.stylesheet(accent)


def test_light_accents_get_dark_text():
    import theme

    assert theme.on_accent("#c8b98f") == theme.BG
    assert theme.on_accent("#f59e0b") == theme.BG
    assert theme.on_accent("#3b82f6") == theme.TEXT


def test_lay_reset_is_a_secondary_button(window):
    reset = next(
        button for button in window.lay_row.findChildren(QPushButton)
        if button.text() == tr("lay_reset")
    )

    assert reset.property("flat_style") is True


def test_settings_folder_path_shown_when_it_cannot_be_opened(window, monkeypatch, tmp_path):
    from PyQt6.QtGui import QDesktopServices

    folder = str(tmp_path / "settings")
    monkeypatch.setattr("crosshair.config_dir", lambda: folder)
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)

    window.open_config_dir()
    assert not window.open_status.isHidden()
    assert window.open_status.text() == tr("open_failed", target=folder)
    assert os.path.isdir(folder)

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)

    window.open_config_dir()
    assert window.open_status.isHidden()


def test_map_without_a_browser_stays_embedded_and_says_so(window, monkeypatch):
    monkeypatch.setattr("crosshair.open_external", lambda url: False)
    monkeypatch.setattr("webmap.open_external", lambda url: False)
    monkeypatch.setattr(type(window.map_page), "ensure_loaded", lambda self: None)

    window.config["map_external"] = True
    window.set_page(3)
    assert window.pages.currentIndex() == 3

    window.map_page.open_in_browser()
    assert window.map_page.status.text() == tr("open_failed", target="https://calc.tk104.duckdns.org/")
