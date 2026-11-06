"""The FOV and the screen the marks are laid for come from the game's own
settings file when it can be found; the window says where the FOV is from.
The settings files here are synthetic (see tests/test_gamesettings.py)."""

import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import config
import gamesettings
from ballistics import load_weapons, mark_offset
from conftest import ROOT
from i18n import tr

WEAPON = "QLZ87 · optic (RMB ×3)"


@pytest.fixture
def steam(tmp_path, monkeypatch):
    """A Steam folder with no game settings yet, found by the app."""
    root = tmp_path / "Steam"
    root.mkdir()
    monkeypatch.setattr(gamesettings, "STEAM_ROOTS", (str(root),))

    return root


def game_file(steam):
    return (
        steam / "steamapps" / "compatdata" / "393380" / "pfx" / "drive_c" / "users"
        / "steamuser" / "AppData" / "Local" / "SquadGame" / "Saved" / "Config"
        / "WindowsNoEditor" / "GameUserSettings.ini"
    )


def write_game_settings(steam, body, mtime=None):
    path = game_file(steam)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[/Script/Squad.SQGameUserSettings]\n{body}\n")

    if mtime is not None:
        os.utime(path, (mtime, mtime))

    return path


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    windows = []

    def make():
        from crosshair import MainWindow

        win = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
        win.overlay.setGeometry(0, 0, 1920, 1080)
        win.show_game_screen()
        windows.append(win)

        return win

    yield make

    for win in windows:
        win.close()


def test_without_the_game_settings_the_fov_field_is_usable_and_says_so(steam, make_window):
    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 120
    assert window.fov_source_label.text() == tr("fov_not_from_game")
    assert window.active_fov() == 120


def test_without_any_steam_folder_the_window_still_opens(make_window):
    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_source_label.text() == tr("fov_not_from_game")


def test_the_fov_of_the_game_is_shown_with_its_source_and_cannot_be_typed_over(steam, make_window):
    write_game_settings(steam, "FOV=105.000000")

    window = make_window()

    assert window.fov_source_label.text() == tr("fov_from_game", fov="105")
    assert window.fov_entry.value() == 105
    assert not window.fov_entry.isEnabled()
    assert window.active_fov() == 105


def test_every_mark_is_laid_for_the_fov_of_the_game(steam, make_window):
    write_game_settings(steam, "FOV=100")
    window = make_window()
    window.config["fov"] = 90
    window.select_weapon(WEAPON)
    window.distance_entry.setText("1000")
    window.calculate()

    weapon = window.current_weapon()
    expected = mark_offset(weapon, window.last_solution.sight_angle, 100, 1920)

    assert window.overlay.offset == pytest.approx(expected)
    assert window.overlay.offset != pytest.approx(
        mark_offset(weapon, window.last_solution.sight_angle, 90, 1920)
    )


def test_the_fov_of_the_game_does_not_overwrite_the_one_typed_and_saved(steam, make_window):
    window = make_window()
    window.fov_entry.set_value(110)
    window.config["fov"] = 110
    write_game_settings(steam, "FOV=100")
    window.select_weapon(WEAPON)
    window.distance_entry.setText("500")

    window.watch_game_settings()
    window.calculate()

    assert window.active_fov() == 100
    assert window.config["fov"] == 110


def test_a_fov_outside_the_games_range_counts_as_not_found(steam, make_window):
    write_game_settings(steam, "FOV=250")

    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_source_label.text() == tr("fov_not_from_game")
    assert window.active_fov() == 120


def test_a_malformed_fov_counts_as_not_found(steam, make_window):
    write_game_settings(steam, "FOV=wide")

    window = make_window()

    assert window.fov_entry.isEnabled()
    assert window.fov_source_label.text() == tr("fov_not_from_game")


def test_the_file_is_watched_by_a_timer(make_window):
    window = make_window()

    assert window.game_settings_timer.isActive()
    assert window.game_settings_timer.interval() > 0


def test_a_rewritten_file_changes_the_fov_and_the_mark_while_the_app_runs(steam, make_window):
    write_game_settings(steam, "FOV=90", mtime=1000)
    window = make_window()
    window.select_weapon(WEAPON)
    window.distance_entry.setText("1000")
    window.calculate()
    before = window.overlay.offset

    write_game_settings(steam, "FOV=120", mtime=2000)
    window.watch_game_settings()

    assert window.fov_source_label.text() == tr("fov_from_game", fov="120")
    assert window.fov_entry.value() == 120
    assert window.overlay.offset != pytest.approx(before)
    assert window.overlay.offset == pytest.approx(
        mark_offset(window.current_weapon(), window.last_solution.sight_angle, 120, 1920)
    )


def test_a_file_that_appears_after_the_start_is_picked_up(steam, make_window):
    window = make_window()
    assert window.fov_entry.isEnabled()

    write_game_settings(steam, "FOV=95")
    window.watch_game_settings()

    assert not window.fov_entry.isEnabled()
    assert window.active_fov() == 95


def test_a_file_that_goes_away_returns_the_field_to_the_typed_fov(steam, make_window):
    path = write_game_settings(steam, "FOV=95")
    window = make_window()
    window.config["fov"] = 108

    path.unlink()
    window.watch_game_settings()

    assert window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 108
    assert window.fov_source_label.text() == tr("fov_not_from_game")
    assert window.active_fov() == 108


def test_a_file_left_as_it_is_is_not_read_again(steam, make_window, monkeypatch):
    write_game_settings(steam, "FOV=95")
    window = make_window()
    reads = []
    monkeypatch.setattr(window, "load_game_settings", lambda: reads.append(1))

    window.watch_game_settings()
    window.watch_game_settings()

    assert reads == []


def test_the_source_survives_rebuilding_the_window(steam, make_window):
    write_game_settings(steam, "FOV=101")
    window = make_window()

    window.rebuild()

    assert not window.fov_entry.isEnabled()
    assert window.fov_entry.value() == 101
    assert window.fov_source_label.text() == tr("fov_from_game", fov="101")


def test_resetting_the_settings_keeps_the_fov_of_the_game(steam, make_window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    write_game_settings(steam, "FOV=101")
    window = make_window()

    window.reset_settings()

    assert window.fov_entry.value() == 101
    assert window.active_fov() == 101


# ---------- the game does not fill the screen ----------

def test_a_game_in_a_window_gets_a_warning(steam, make_window):
    write_game_settings(steam, "FOV=100\nFullscreenMode=2\nResolutionSizeX=1920\nResolutionSizeY=1080")

    window = make_window()

    assert not window.game_screen_label.isHidden()
    assert window.game_screen_label.text() == tr("game_windowed")


def test_a_game_at_another_resolution_gets_a_warning_naming_both_sizes(steam, make_window):
    write_game_settings(steam, "FullscreenMode=0\nResolutionSizeX=1280\nResolutionSizeY=720")

    window = make_window()

    assert window.game_screen_label.text() == tr(
        "game_resolution", game="1280x720", screen="1920x1080"
    )


def test_a_game_that_fills_the_screen_gets_no_warning(steam, make_window):
    write_game_settings(steam, "FullscreenMode=1\nResolutionSizeX=1920\nResolutionSizeY=1080")

    window = make_window()

    assert window.game_screen_label.isHidden()


def test_without_the_game_settings_there_is_no_screen_warning(steam, make_window):
    assert make_window().game_screen_label.isHidden()


def test_the_warning_follows_the_file_and_the_screen(steam, make_window):
    write_game_settings(steam, "FullscreenMode=0\nResolutionSizeX=2560\nResolutionSizeY=1440", mtime=1000)
    window = make_window()
    assert not window.game_screen_label.isHidden()

    window.overlay.setGeometry(0, 0, 2560, 1440)
    window.show_game_screen()
    assert window.game_screen_label.isHidden()

    write_game_settings(steam, "FullscreenMode=2", mtime=2000)
    window.watch_game_settings()
    assert window.game_screen_label.text() == tr("game_windowed")
