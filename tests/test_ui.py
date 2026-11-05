import math
import os
import shutil

import pytest

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

import config
import theme
from ballistics import load_weapons, mark_offset, screen_offset, solve
from i18n import tr
from widgets import format_angle
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
                c in window.status_text() for c in ("°", "mil")
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
    assert window.overlay.offset == 0


@pytest.mark.parametrize("name, distance", [
    ("Mortar (M252 / 2B14 / L16 / Type 63)", "900"),
    # The rail starts 14.2 degrees up: nothing closer than about 985 m
    ("BM-21 Grad", "1200"),
    ("Hell Cannon", "900"),
])
def test_no_overlay_mark_for_weapons_laid_by_elevation(window, name, distance):
    # Laid on their own sight in mils/degrees: no mark, the info line stays.
    window.select_weapon(name)
    window.distance_entry.setText(distance)
    window.calculate()
    assert window.last_solution.reachable
    assert not window.overlay.mark_visible
    assert window.overlay.offset == 0
    assert f"{distance} m" in window.overlay.info_text
    assert window.stats["stat_offset"].value.text() == "—"

    window.reset_offset()
    assert not window.overlay.mark_visible


def test_overlay_mark_follows_the_weapon_aim(window):
    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    window.distance_entry.setText("")
    window.recalculate_if_ready()
    assert not window.overlay.mark_visible

    # Direct fire and the AGS-17 (its direct-fire aim) are aimed with the mark
    for name in ("SPG-9 · HEAT", "AGS-17 · emplacement · optic (RMB ×2.5)"):
        window.select_weapon(name)
        window.distance_entry.setText("500")
        window.calculate()
        assert window.overlay.mark_visible, name
        assert window.overlay.offset > 0, name

    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    assert not window.overlay.mark_visible


def test_reset_toggle_and_distance_keys(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("500")
    window.calculate()
    assert window.overlay.offset > 0
    assert "500 m" in window.overlay.info_text

    window.config["distance_step"] = 25
    window.distance_up()
    assert window.last_solution.distance == 525
    window.distance_down()
    window.distance_down()
    assert window.last_solution.distance == 475

    window.reset_offset()
    assert window.overlay.offset == 0
    assert window.overlay.info_text == ""

    visible = window.overlay.isVisible()
    window.toggle_overlay()
    assert window.overlay.isVisible() != visible


def test_unit_mode_and_arc(window):
    window.select_weapon("Mortar (M252 / 2B14 / L16 / Type 63)")
    window.distance_entry.setText("800")
    window.calculate()
    assert "mil" in window.status_text()

    window.set_unit_mode("deg")
    assert "°" in window.status_text()

    window.on_arc_changed("low")
    assert not window.last_solution.reachable


REMOVED_WEAPONS = ("M109", "NSV", "M2A1 .50", "2A42 / 2A72 30mm · HE")


def test_removed_weapons_are_gone_and_a_saved_one_falls_back(app, tmp_path, monkeypatch):
    """Mods, machine guns and autocannons are no longer in the database; a
    settings file naming one starts the app on the first weapon."""
    import json

    from crosshair import MainWindow

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    weapons = load_weapons(os.path.join(ROOT, "weapons.json"))

    assert not any(name in weapons for name in REMOVED_WEAPONS)
    assert {weapon.category for weapon in weapons.values()} == {
        "grenade_launchers", "agl", "launchers", "guns", "tanks", "indirect"
    }

    for removed in REMOVED_WEAPONS:
        (tmp_path / "config.json").write_text(json.dumps({
            "last_weapon": removed,
            "recent_weapons": [removed, "RPG-29"],
            "show_mods": True
        }))

        win = MainWindow(weapons)
        try:
            assert win.picker.current == next(iter(weapons)), removed
            assert win.recent_weapons() == ["RPG-29"]
        finally:
            win.close()


def test_recent_weapons(window):
    window.select_weapon("RPG-29")
    window.select_weapon("AT-4")

    assert window.config["recent_weapons"][:2] == ["AT-4", "RPG-29"]
    assert window.config["last_weapon"] == "AT-4"


def test_off_screen_aim_point_is_drawn_as_an_edge_arrow(window):
    window.overlay.set_offset(1e9)
    window.overlay.repaint()


def test_rebuild_keeps_the_inputs(window):
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("400")
    window.calculate()

    window.rebuild()

    assert window.distance_entry.text() == "400"
    assert window.last_solution.reachable


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


def test_selftest_does_not_touch_user_config_or_the_app_folder(tmp_path):
    import subprocess
    import sys

    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "cfg")
    env["QT_QPA_PLATFORM"] = "offscreen"
    before = set(os.listdir(ROOT))

    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "app.py"), "--selftest"],
        cwd=tmp_path,
        env=env,
        timeout=300,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SELFTEST PASSED" in result.stdout

    log = result.stdout.rstrip().splitlines()[-1].removeprefix("Log: ")
    assert not os.path.abspath(log).startswith(ROOT + os.sep)
    with open(log, encoding="utf-8") as f:
        assert "SELFTEST PASSED" in f.read()
    shutil.rmtree(os.path.dirname(log))

    assert set(os.listdir(ROOT)) == before
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

    window.rebuild()

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


AGS17 = "AGS-17 · emplacement · optic (RMB ×2.5)"


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

    # The overlay mark shows the direct-fire aim at the same time, through
    # the optic's view (the default): ×2.5 and the optic's 0.85 degree socket.
    direct = window.direct_solution
    assert direct.reachable and direct.arc == "low"
    assert direct.angle < 45 < solution.angle
    assert window.overlay.offset == pytest.approx(
        screen_offset(
            direct.sight_angle - 0.85,
            window.config["fov"] / 2.5,
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

    # Holding S is counted towards the target.
    window.hold_timer.advance(solution.hold_time + 0.01, True, False)
    assert window.hold_timer.held == pytest.approx(solution.hold_time + 0.01)

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


def test_hold_weapon_gets_its_target_without_key_reader(window):
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("800")

    window.hold_timer.key_reader = None
    window.calculate()
    assert window.hold_timer.target == pytest.approx(
        window.last_solution.hold_time
    )
    assert not window.hold_timer.poll_timer.isActive()


def test_hold_weapon_gets_key_watch_and_target_without_any_setting(window):
    window.hold_timer.key_reader = lambda code: False

    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("800")
    window.calculate()

    assert "hold_timer" not in window.config
    assert "hold_timer" not in window.controls

    assert window.hold_timer.active
    assert window.hold_timer.target == pytest.approx(window.last_solution.hold_time)


def test_ags17_card_shows_the_hold_seconds(window):
    window.select_weapon(AGS17)
    window.config["arc"] = "high"
    window.distance_entry.setText("1000")
    window.calculate()

    hold = window.last_solution.hold_time
    seconds = f"{hold:.2f}"

    assert window.status_text() == f"S {seconds} {tr('unit_s')}"
    assert tr("how_hold_2", t=seconds) in window.current_steps
    assert window.overlay.info_text.startswith(window.info_base)
    assert seconds in window.overlay.info_text

    window.rebuild()

    assert window.status_text() == f"S {seconds} {tr('unit_s')}"


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
    assert window.overlay.info_text.startswith(tr("info_view_optic", zoom="2.5") + "  ·  1234 ")
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
        "weapon": "Tank AP · M256 / Rh120"
    })
    assert window.picker.current == "Tank AP · M256 / Rh120"
    assert window.config["last_weapon"] == "Tank AP · M256 / Rh120"
    assert window.distance_entry.text() == "420"
    assert window.last_solution.distance == 420
    expected = solve(window.weapons["Tank AP · M256 / Rh120"], 420, -6, "low")
    assert window.last_solution.angle == pytest.approx(expected.angle)
    # The target is put on the mark: below the centre by the angle over the
    # line of sight, not by the (here negative) angle to the horizon, through
    # the gunner's sight.
    weapon = window.weapons["Tank AP · M256 / Rh120"]
    assert expected.angle < 0 < expected.sight_angle
    assert window.overlay.offset == pytest.approx(
        mark_offset(
            weapon,
            expected.sight_angle,
            window.config["fov"],
            window.overlay.screen_width(),
            window.config["offset_scale"] / 100
        )
    )
    # 420 m is inside this gun's 635 m zero: the mark is above the centre.
    assert window.overlay.offset < 0

    # A weapon picked here stays until the SquadCalc weapon changes.
    window.select_weapon("AT-4")
    page.on_bridge_result({
        "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
        "weapon": "Tank AP · M256 / Rh120"
    })
    assert window.picker.current == "AT-4"

    page.load_source()
    assert page.bridge_found is None

    # A late answer after the map was shut down is ignored.
    page.shutdown()
    page.on_bridge_result({"targets": [{"distance": 300}], "weapon": "RPG-29"})
    assert page.bridge_found is None
    assert window.distance_entry.text() == "420"
    assert window.picker.current == "AT-4"


def test_map_weapon_is_followed_only_when_known_and_enabled(window):
    window.select_weapon("AT-4")

    window.on_map_weapon("Not a weapon here")
    assert window.picker.current == "AT-4"

    window.config["map_follow"] = False
    window.on_map_weapon("RPG-29")
    assert window.picker.current == "AT-4"

    window.config["map_follow"] = True
    window.on_map_weapon("RPG-29")
    assert window.picker.current == "RPG-29"

    # A SquadCalc page from before a rename sends the old name.
    window.on_map_weapon("BTR-4 AGS")
    assert window.picker.current == "AGS-30 / BTR-4 AGS"
    window.on_map_weapon("RPG-29")

    # SquadCalc keeps weapons removed here (mods, machine guns): ignored.
    for removed in REMOVED_WEAPONS:
        window.on_map_weapon(removed)
        assert window.picker.current == "RPG-29"


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


def test_hold_watch_follows_the_weapon(window):
    window.hold_timer.key_reader = lambda code: False

    window.select_weapon(AGS17)
    assert window.hold_timer.active

    window.select_weapon("RPG-29")
    assert not window.hold_timer.active


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


def test_reset_settings_reloads_map(window, monkeypatch):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    window.set_page(3)
    window.set_map_source("squadcalc")

    window.reset_settings()

    assert window.config["map_source"] == "deadline"
    assert window.map_page.page.requestedUrl().host() == "calc.tk104.duckdns.org"


def test_close_drops_the_key_watch(window):
    window.hold_timer.key_reader = lambda code: False
    window.select_weapon(AGS17)

    window.close()

    assert not window.hold_timer.active


def test_embedded_bridge_reads_a_real_page(window, monkeypatch):
    """The real poll: BRIDGE_SCRIPT runs in a page defining the bridge."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    import webmap
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    html = (
        "data:text/html;charset=utf-8,<script>var current='RPG-7V1 · HEAT';"
        "window.squadBallistics={version:2,"
        "targets:()=>[{distance:612.4,heightDiff:-8.6,bearing:181}],"
        "weapon:()=>current}"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.select_weapon("AT-4")
    window.set_page(3)

    def wait_for(condition):
        clock = QElapsedTimer()
        clock.start()
        while not condition() and clock.elapsed() < 15000:
            QCoreApplication.processEvents()
        return condition()

    assert wait_for(lambda: window.distance_entry.text() == "612.4")
    assert window.height_entry.text() == "-8.6"
    assert window.map_page.bridge_found is True

    # The weapon the page starts with is only restored there, not picked:
    # the app keeps its own and solves for it.
    assert window.picker.current == "AT-4"
    assert window.last_solution.angle == pytest.approx(
        solve(window.weapons["AT-4"], 612.4, -8.6, "low").angle
    )

    # A weapon then selected on the page is followed and solved.
    window.map_page.page.runJavaScript("current = 'RPG-29';", 0)
    assert wait_for(lambda: window.picker.current == "RPG-29")
    assert window.last_solution.angle == pytest.approx(
        solve(window.weapons["RPG-29"], 612.4, -8.6, "low").angle
    )


def test_weapon_picked_here_is_selected_on_the_embedded_map(window, monkeypatch):
    """Two-way weapon sync: the map draws its coverage for the app's weapon."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    import webmap
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    # A page like SquadCalc: selectWeapon() only accepts the weapons it has.
    html = (
        "data:text/html;charset=utf-8,<script>"
        "var known=['QLZ87 · optic (RMB ×3)','AT-4'];var current='AT-4';var calls=[];"
        "window.squadBallistics={version:3,"
        "targets:()=>[{distance:500,heightDiff:0,bearing:0}],"
        "weapon:()=>current,"
        "selectWeapon:(n)=>{calls.push(n);if(known.indexOf(n)<0)return false;current=n;return true;}};"
        "</script>"
    )
    monkeypatch.setitem(webmap.MAP_SOURCES, "deadline", html)

    window.select_weapon("QLZ87 · optic (RMB ×3)")
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

    # The app's weapon goes to the page once it answers; the page's own
    # starting weapon does not switch the app.
    assert wait_for(lambda: page.bridge_found)
    assert wait_for(lambda: page_value("current") == "QLZ87 · optic (RMB ×3)")
    assert wait_for(lambda: page.last_weapon == "QLZ87 · optic (RMB ×3)")
    assert window.picker.current == "QLZ87 · optic (RMB ×3)"

    # Picked here while the page runs.
    window.select_weapon("AT-4")
    assert wait_for(lambda: page_value("current") == "AT-4")
    assert wait_for(lambda: page.last_weapon == "AT-4")
    assert window.picker.current == "AT-4"

    # Picked on the page: followed here.
    page_value("current = 'QLZ87 · optic (RMB ×3)'")
    assert wait_for(lambda: window.picker.current == "QLZ87 · optic (RMB ×3)")

    # A weapon the page does not have: the page keeps its own and does not
    # switch the app back (no ping-pong).
    window.select_weapon("RPG-29")
    assert wait_for(lambda: "RPG-29" in page_value("calls.join(',')"))
    for _ in range(20):
        QCoreApplication.processEvents()
    page.poll_targets()
    assert wait_for(lambda: page_value("current") == "QLZ87 · optic (RMB ×3)")
    assert window.picker.current == "RPG-29"


def test_an_older_squadcalc_page_sending_the_bare_name_selects_the_optic_entry(window):
    """Before the optic names, SquadCalc's "QLZ87" was the optic's entry and
    the plain-view twin had its own name: the bare name never means the
    normal view."""
    window.config["map_follow"] = True
    window.select_weapon("QLZ87 · no optic")

    window.on_map_weapon("QLZ87")

    assert window.picker.current == "QLZ87 · optic (RMB ×3)"

    window.on_map_weapon("QLZ87 · no optic")

    assert window.picker.current == "QLZ87 · no optic"


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


def test_calculator_fits_the_minimum_window(window):
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

    window.select_weapon("RPG-29")
    assert picker.text() == "RPG-29   ▾"

    # The end of an RMB sight's name says which view it is: it stays.
    window.select_weapon(AGS17)
    assert picker.text().endswith("optic (RMB ×2.5)   ▾")


def test_crosshair_page_fits_the_minimum_window(window):
    show_at(window, 900, 600)
    window.set_page(1)
    QApplication.processEvents()

    page = window.pages.currentWidget()
    # The preview and the caption under it are on the page, whole
    caption = next(l for l in page.findChildren(QLabel) if l.text() == tr("mark_caption"))

    for widget in (window.preview, caption):
        assert widget.isVisible()
        assert page.rect().contains(widget.mapTo(page, widget.rect().bottomRight()))


def mark_ink(overlay, half=40):
    """(left, top, right, bottom) pixel box of what is painted within `half`
    px of the overlay's centre, as image coordinates (right/bottom included)."""
    image = overlay.grab().toImage()
    cx, cy = int(overlay.width() / 2), int(overlay.height() / 2)
    points = [
        (x, y)
        for y in range(cy - half, cy + half)
        for x in range(cx - half, cx + half)
        if image.pixelColor(x, y).alpha() > 0
    ]
    xs, ys = [p[0] for p in points], [p[1] for p in points]

    return min(xs), min(ys), max(xs), max(ys)


@pytest.fixture
def full_hd_overlay(window):
    window.set_setting("range_ladder", False)
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.overlay.set_offset(0)
    return window.overlay


@pytest.mark.parametrize("width, height", [(1920, 1080), (2560, 1440)])
def test_the_mark_is_centred_on_the_screen_centre(window, full_hd_overlay, width, height):
    """The mark is symmetric about the exact centre of the screen (between
    pixels 959/960 and 539/540 at 1080p)."""
    full_hd_overlay.setGeometry(0, 0, width, height)

    left, top, right, bottom = mark_ink(full_hd_overlay)

    assert (left + right + 1, top + bottom + 1) == (width, height)
    assert right - left + 1 >= 50


def test_the_mark_is_centred_on_the_chosen_monitor(window, full_hd_overlay):
    """The overlay covers the monitor, so its centre is the monitor's centre
    whatever the monitor's size."""
    full_hd_overlay.setGeometry(0, 0, 1280, 720)

    left, top, right, bottom = mark_ink(full_hd_overlay)

    assert (left + right + 1, top + bottom + 1) == (1280, 720)


def test_crosshair_settings_persist_and_reload(window, tmp_path):
    from crosshair import MainWindow

    window.controls["range_ladder"].setChecked(False)
    window.controls["info_enabled"].setChecked(False)
    window.controls["center_offset_x"].slider.setValue(-12)
    window.controls["center_offset_y"].slider.setValue(7)
    window.controls["offset_scale"].slider.setValue(110)

    config.save_config(window.config)
    saved = config.load_config()

    assert (saved["range_ladder"], saved["info_enabled"]) == (False, False)
    assert (saved["center_offset_x"], saved["center_offset_y"], saved["offset_scale"]) == (-12, 7, 110)

    again = MainWindow(window.weapons)
    try:
        assert not again.controls["range_ladder"].isChecked()
        assert not again.controls["info_enabled"].isChecked()
        assert again.controls["center_offset_x"].slider.value() == -12
        assert again.controls["center_offset_y"].slider.value() == 7
        assert again.controls["offset_scale"].slider.value() == 110
        assert again.overlay.center_x == again.overlay.width() / 2 - 12
    finally:
        again.close()


def test_the_alignment_moves_and_scales_the_mark_and_reset_undoes_it(window):
    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("SPG-9 · HEAT")
    window.distance_entry.setText("500")
    window.calculate()
    plain = overlay.offset
    assert plain > 0

    window.controls["offset_scale"].slider.setValue(150)
    assert overlay.offset == pytest.approx(plain * 1.5)

    window.controls["center_offset_x"].slider.setValue(30)
    window.controls["center_offset_y"].slider.setValue(-20)
    assert (overlay.center_x, overlay.center_y) == (990, 520)

    window.set_setting("range_ladder", True)
    ladder = dict(overlay.ladder)

    window.reset_alignment()

    assert overlay.offset == pytest.approx(plain)
    assert (overlay.center_x, overlay.center_y) == (960, 540)
    assert [window.controls[k].slider.value() for k in ("center_offset_x", "center_offset_y", "offset_scale")] == [0, 0, 100]
    assert dict(overlay.ladder) != ladder


def test_alignment_sliders_step_by_one_with_the_arrow_keys(window):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    for key in ("center_offset_x", "center_offset_y", "offset_scale"):
        slider = window.controls[key].slider
        before = slider.value()

        QTest.keyClick(slider, Qt.Key.Key_Right)

        assert slider.value() == before + 1, key
        assert window.config[key] == before + 1


def inventory(window, page_index):
    """The user-operable controls of a page: (switch keys, sliders, segmented
    rows, drop-downs, plain buttons)."""
    from PyQt6.QtWidgets import QComboBox
    from widgets import Segmented, SliderRow, Toggle

    page = window.pages.widget(page_index)

    def keys(kind):
        return [k for k, c in window.controls.items() if isinstance(c, kind) and page.isAncestorOf(c)]

    inside = [b for b in page.findChildren(QPushButton)
              if not any(isinstance(a, Segmented) for a in _ancestors(b))]

    return {
        "switches": keys(Toggle),
        "sliders": keys(SliderRow),
        "segmented": [[b.text() for b in row.buttons.values()] for row in page.findChildren(Segmented)],
        # The monitor choice exists with one monitor too, hidden
        "dropdowns": len([c for c in page.findChildren(QComboBox) if c.isVisibleTo(page)]),
        "buttons": [b.text() for b in inside],
    }


def _ancestors(widget):
    while widget is not None:
        widget = widget.parentWidget()
        yield widget


def test_the_crosshair_page_has_exactly_these_controls(window):
    assert inventory(window, 1) == {
        "switches": ["range_ladder", "info_enabled"],
        "sliders": ["center_offset_x", "center_offset_y", "offset_scale"],
        "segmented": [],
        "dropdowns": 0,
        "buttons": [tr("align_reset")],
    }


def test_the_settings_page_has_exactly_these_controls(window):
    assert inventory(window, 2) == {
        "switches": ["main_on_top", "auto_calc", "auto_hold", "sight_reader", "map_follow", "map_external"],
        "sliders": [],
        "segmented": [
            [tr("s_units_auto"), tr("s_units_deg"), tr("s_units_mil")],
            [tr("s_map_source_deadline"), "squadcalc.app"],
            [tr("s_map_render_auto"), tr("s_map_render_software")],
        ],
        # distance step + the six hotkeys; the monitor row needs two monitors
        "dropdowns": 7,
        "buttons": [tr("s_map_clear"), tr("s_open_config"), tr("s_reset")],
    }


def test_the_monitor_row_shows_only_with_several_monitors(window, monkeypatch):
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QComboBox
    from crosshair import MainWindow

    screen = QGuiApplication.primaryScreen()
    assert len(QGuiApplication.screens()) == 1

    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: [screen, screen]))
    two = MainWindow(window.weapons)
    try:
        assert len(two.pages.widget(2).findChildren(QComboBox)) == 8
    finally:
        two.close()


def test_the_hotkeys_are_unchanged():
    from hotkeys import ACTIONS

    assert ACTIONS == ["toggle_overlay", "reset_offset", "distance_up", "distance_down", "auto_hold", "toggle_view"]
    assert config.DEFAULT_CONFIG["hotkeys"] == {
        "toggle_overlay": "F8",
        "reset_offset": "F9",
        "distance_up": "",
        "distance_down": "",
        "auto_hold": "F7",
        "toggle_view": "Mouse4",
    }


def test_window_fits_the_screen(window):
    available = window.screen().availableGeometry()

    assert window.width() == max(900, min(1180, available.width()))
    assert window.height() <= max(600, available.height())
    assert window.height() == max(600, min(780, available.height() - 40))


# The longest line show_overlay_info writes: a mortar's solution with an
# obstacle and the map bearing, then the compass and the sight readings.
LONG_INFO = "  ·  ".join([
    "1150 m",
    "1016 mil",
    "S 3.53 s",
    tr("blocked_short", d="640"),
    "47.5°",
    tr("compass_reading_left", deg="46.9", left="+0.6"),
    tr("sight_reading_left", mils="1041.5", left="+4.6"),
])


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


def test_map_progress_bar_uses_the_accent(window):
    assert theme.ACCENT in window.map_page.progress.styleSheet()


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


def test_range_ladder_follows_fov_and_toggle(window):
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


def test_optic_view_moves_the_mark_and_the_ladder(window):
    """The QLZ87 tripod has one view, the optic: it zooms x3 and is zeroed
    at 100 m; a weapon without an optic is aimed through the plain view."""
    from ballistics import mark_offset

    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("QLZ87 · optic (RMB ×3)")
    window.distance_entry.setText("400")
    window.height_entry.setText("0")
    window.fov_entry.setText("90")
    window.calculate()
    weapon = window.current_weapon()
    angle = window.last_solution.sight_angle

    assert weapon.sight_view(90) == (30, 0.774)
    assert window.current_offset() == pytest.approx(mark_offset(weapon, angle, 90, 1920))
    assert window.overlay.offset == pytest.approx(mark_offset(weapon, angle, 90, 1920))
    optic_ladder = window.overlay.ladder
    assert optic_ladder and optic_ladder[0][0] > 100

    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.distance_entry.setText("400")
    window.calculate()
    assert window.overlay.ladder != optic_ladder
    assert window.current_weapon().sight_view(90) == (90, 0.0)


def test_the_view_of_an_rmb_sight_is_said_in_the_header_the_overlay_and_the_steps(window):
    """The QLZ87 trap: used from the normal view, the optic's mark flew
    hundreds of metres past the target and nothing on screen said which view
    the entry was for. The header, the overlay's info line and the how-to
    steps name it for both entries of every RMB sight."""
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.distance_entry.setText("300")
    window.height_entry.setText("0")
    window.fov_entry.setText("120")

    for name, line, tag, step in [
        ("QLZ87 · optic (RMB ×3)", tr("view_optic", zoom="3"), tr("info_view_optic", zoom="3"),
         "hold RMB (zoom ×3)"),
        ("QLZ87 · no optic", tr("view_plain"), tr("info_view_plain"), "do not press RMB"),
    ]:
        window.select_weapon(name)
        window.calculate()

        assert window.view_label.text() == line
        assert not window.view_label.isHidden()
        assert window.overlay.info_text.startswith(tag + "  ·  300 ")
        assert any(step in text for text in window.current_steps)

    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.calculate()

    assert window.view_label.isHidden()
    assert not window.overlay.info_text.startswith(tr("info_view_plain"))
    assert not any("RMB" in text for text in window.current_steps)


def test_each_view_step_names_the_other_entry(window):
    window.fov_entry.setText("120")
    window.distance_entry.setText("300")

    for name, other in [
        ("QLZ87 · optic (RMB ×3)", "QLZ87 · no optic"),
        ("QLZ87 · no optic", "QLZ87 · optic (RMB ×3)"),
        ("ZiS-3 · no optic", "ZiS-3 · optic (RMB ×4)"),
    ]:
        window.select_weapon(name)
        window.calculate()

        assert any(f'"{other}"' in text for text in window.current_steps)


def test_fov_edit_moves_the_ladder_without_a_distance(window):
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.distance_entry.setText("")
    window.fov_entry.setText("90")
    window.calculate(show_errors=False)
    wide = dict(window.overlay.ladder)

    window.fov_entry.setText("60")
    window.calculate(show_errors=False)
    narrow = dict(window.overlay.ladder)

    assert window.config["fov"] == 60
    assert narrow[100] > wide[100] * 1.5


def test_small_fov_through_the_optic_neither_raises_nor_stops_the_app(window):
    """FOV 2 through the QLZ87's x3 optic is a view under 1 degree."""
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("QLZ87 · optic (RMB ×3)")
    window.distance_entry.setText("300")
    window.fov_entry.setText("2")
    window.calculate()

    assert window.last_solution is not None
    assert window.current_offset() > 0
    window.fov_entry.setText("1")
    window.calculate()
    assert window.last_solution is not None


def painted_rows(overlay, width=25):
    """Rows (y) with something painted in the `width` px right of the
    overlay's centre line: the aim mark, clear of the ladder and the label."""
    image = overlay.grab().toImage()
    left = int(overlay.center_x)

    return [
        y for y in range(image.height())
        if any(image.pixelColor(x, y).alpha() > 0 for x in range(left, left + width))
    ]


@pytest.mark.parametrize("name, zero", [
    ("MK19 · emplacement / C16 / L134A1", 330),
    ("SPG-9 · HEAT · scope · optic (RMB ×4)", 765),
    ("ZiS-3 · optic (RMB ×4)", 350),
])
def test_emplaced_mark_is_drawn_where_the_view_puts_it(window, name, zero):
    """The painted mark is `mark_offset` below the centre and the ladder of
    the weapon's sight view starts past that view's zero."""
    from ballistics import mark_offset, solve

    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon(name)
    weapon = window.current_weapon()
    distance = zero * 1.6
    window.distance_entry.setText(str(distance))
    window.height_entry.setText("0")
    window.fov_entry.setText("90")

    window.calculate()
    angle = solve(weapon, distance, 0.0, "low").sight_angle
    expected = mark_offset(weapon, angle, 90, 1920)
    rows = painted_rows(overlay)

    assert window.current_offset() == pytest.approx(expected)
    assert overlay.offset == pytest.approx(expected)
    assert (min(rows) + max(rows)) / 2 == pytest.approx(overlay.center_y + expected, abs=1.5)
    assert overlay.ladder
    assert overlay.ladder[0][0] > zero


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
    assert all(image.pixelColor(x, y).alpha() == 0 for x in range(centre, centre + 120))

    # The tick itself ends LADDER_GAP px left of the centre line.
    from overlay import LADDER_GAP, LADDER_TICK
    tick = range(centre - LADDER_GAP - LADDER_TICK + 1, centre - LADDER_GAP)
    assert all(image.pixelColor(x, y).alpha() > 0 for x in tick)


def test_hotkey_hint_wraps_only_between_entries(window):
    from crosshair import HINT_SEPARATOR

    window.set_hotkey("distance_up", "PgUp")
    window.set_hotkey("distance_down", "PgDown")

    entries = window.hotkey_hint.text().split(HINT_SEPARATOR)

    assert len(entries) == 5
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


def test_the_accent_is_blue_with_readable_text():
    import theme

    assert theme.ACCENT == "#3b82f6"
    assert theme.ACCENT_TEXT == theme.on_accent(theme.ACCENT)
    assert theme.contrast(theme.ACCENT_TEXT, theme.ACCENT) >= theme.MIN_TEXT_CONTRAST
    # Buttons, checked segments and selected rows all use it
    assert theme.stylesheet().count(f"color: {theme.ACCENT_TEXT};") >= 3
    assert "color: white" not in theme.stylesheet()


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


def test_a_weapon_with_one_view_keeps_the_old_off_screen_text(window):
    window.overlay.setGeometry(0, 0, 1920, 1080)
    window.select_weapon("AT-4")
    window.distance_entry.setText("300")
    window.fov_entry.setText("3")
    window.calculate()

    assert window.overlay.is_offscreen(window.overlay.offset)
    assert window.current_steps[0].startswith("The mark is off-screen: raise the barrel")


# Review 1.6.0, slice 1 #4-#8
def test_the_other_arc_tile_reads_as_the_main_result(window):
    """An overlay weapon's direct fire is read over the line of sight (as
    its "direct fire" text), its lob by the hold; mortars to the horizon,
    in the chosen unit."""
    window.select_weapon(AGS17)
    window.on_arc_changed("high")
    window.fov_entry.setText("90")
    window.height_entry.setText("40")
    window.distance_entry.setText("600")
    window.calculate()

    unit = window.primary_unit(window.current_weapon())
    direct = format_angle(window.direct_solution.sight_angle, unit)
    assert window.stats["stat_alt"].value.text() == direct
    assert tr("direct_short", angle=direct) in window.overlay.info_text

    window.on_arc_changed("low")
    hold = solve(window.current_weapon(), 600, 40, "high").hold_time
    assert window.stats["stat_alt"].value.text() == f"S {hold:.2f} {tr('unit_s')}"

    for mode in ("mil", "deg"):
        window.set_unit_mode(mode)
        assert window.stats["stat_alt"].value.text() == f"S {hold:.2f} {tr('unit_s')}"

        window.on_arc_changed("high")
        direct = format_angle(window.direct_solution.sight_angle, mode)
        assert window.stats["stat_alt"].value.text() == direct, mode
        window.on_arc_changed("low")

    window.select_weapon("Hell Cannon")
    window.on_arc_changed("auto")
    window.height_entry.setText("0")
    window.distance_entry.setText("600")

    for mode in ("mil", "deg"):
        window.set_unit_mode(mode)
        assert window.last_solution.arc == "high"
        alt = window.last_solution.alternatives["low"]
        assert window.stats["stat_alt"].value.text() == format_angle(alt, mode), mode


def test_reset_clears_the_target_for_good(window):
    """Reset (F9) clears the distance and the map target: a later arc,
    trim or alignment change does not bring the mark back."""
    from maplink import MapTarget

    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.on_map_targets([MapTarget(300, 0, 90.0)])
    assert window.overlay.offset > 0

    window.reset_offset()
    assert window.distance_entry.text() == ""
    assert window.map_target is None
    assert window.overlay.offset == 0

    window.on_arc_changed("low")
    window.set_trim(0.5)
    window.controls["center_offset_y"].slider.setValue(10)
    assert window.last_solution is None
    assert window.overlay.offset == 0
    assert window.overlay.info_text == ""


def test_the_alignment_caption_names_the_reset_key(window):
    assert "F9 clears the target" in window.align_caption.text()

    window.set_hotkey("reset_offset", "PgUp")
    assert "PgUp clears the target" in window.align_caption.text()
    assert "F9" not in window.align_caption.text()

    window.set_hotkey("reset_offset", "")
    assert f"{tr('reset_aim')} clears the target" in window.align_caption.text()


def test_the_distance_step_applies_to_the_landed_distance_too(window):
    assert window.config["distance_step"] != 50
    window.set_distance_step(50)

    assert window.distance_entry.step == 50
    assert window.landed_entry.step == 50


def test_the_ladder_ends_at_the_screen_edge_below_the_aligned_centre(window):
    overlay = window.overlay
    overlay.setGeometry(0, 0, 1920, 1080)

    window.controls["center_offset_y"].slider.setValue(100)

    _first, _spacing, reach = overlay.ladder_bounds()
    assert overlay.center_y == 640
    assert reach == 1080 - overlay.EDGE_MARGIN - 640


def test_editing_the_fov_keeps_the_map_target(window):
    from maplink import MapTarget

    window.on_map_targets([MapTarget(600, 5, 90.0)])

    window.fov_entry.setText("80")
    window.fov_entry.textEdited.emit("80")
    assert window.map_target is not None

    window.height_entry.textEdited.emit("3")
    assert window.map_target is None


@pytest.mark.parametrize("change", ["slider", "weapon"])
def test_the_ladder_is_computed_once_per_change(window, monkeypatch, change):
    """range_ladder takes ~14 ms for the RPG-7: one call per slider tick or
    weapon change, not two."""
    import crosshair

    calls = []
    real = crosshair.range_ladder

    def counted(*args, **kwargs):
        calls.append(args[0].name)
        return real(*args, **kwargs)

    window.select_weapon("M203 / M320 / GP-25 / HK79 / SL40")
    window.distance_entry.setText("300")
    window.calculate()
    monkeypatch.setattr(crosshair, "range_ladder", counted)

    if change == "slider":
        window.controls["center_offset_y"].slider.setValue(30)
    else:
        window.select_weapon("RPG-7 · PG-7V HEAT / OG-7V")

    assert len(calls) == 1
    assert window.overlay.ladder


# =========================
# Screen aspect ratio (#10)
# =========================

@pytest.mark.parametrize("width, height", [
    (1920, 1080), (2560, 1440), (3840, 2160), (1280, 720), (1366, 768),
    (1600, 900),
])
def test_16_9_screens_are_accepted(width, height):
    from utils import is_16_9

    assert is_16_9(width, height)


@pytest.mark.parametrize("width, height", [
    (1920, 1200), (2560, 1080), (3440, 1440), (1280, 1024), (1024, 768),
    (1080, 1920), (0, 0), (1920, 0), (-1920, 1080),
])
def test_other_screens_are_not_16_9(width, height):
    from utils import is_16_9

    assert not is_16_9(width, height)


def test_a_non_16_9_screen_is_reported_once(window, caplog):
    window.screen_ratio_text = ""
    window.overlay.setGeometry(0, 0, 1920, 1200)

    with caplog.at_level("WARNING", logger="squad_ballistics"):
        window.check_screen_ratio()
        window.check_screen_ratio()
        window.overlay.setGeometry(0, 0, 2560, 1080)
        window.check_screen_ratio()

    assert window.screen_ratio_text == tr("screen_not_16_9", size="1920x1200")
    assert "1920x1200" in window.screen_ratio_text
    assert window.screen_ratio_label.text() == window.screen_ratio_text
    assert not window.screen_ratio_label.isHidden()
    assert [r.getMessage() for r in caplog.records] == [window.screen_ratio_text]


def test_a_16_9_screen_shows_no_message(window, caplog):
    window.screen_ratio_text = ""
    window.screen_ratio_label.setText("")
    window.screen_ratio_label.hide()
    window.overlay.setGeometry(0, 0, 2560, 1440)

    with caplog.at_level("WARNING", logger="squad_ballistics"):
        window.check_screen_ratio()

    assert window.screen_ratio_text == ""
    assert window.screen_ratio_label.isHidden()
    assert caplog.records == []


def test_the_screen_message_survives_a_rebuild(window):
    window.screen_ratio_text = ""
    window.overlay.setGeometry(0, 0, 1920, 1200)
    window.check_screen_ratio()

    window.rebuild()

    assert window.screen_ratio_label.text() == window.screen_ratio_text
    assert not window.screen_ratio_label.isHidden()
