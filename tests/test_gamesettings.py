"""Reading the game's GameUserSettings.ini (gamesettings.py): where the file
is found and what is taken from it. The files here are synthetic: the layout
follows Unreal Engine's config format, not a file written by the game."""

import os

import pytest

import gamesettings
from gamesettings import (
    FULLSCREEN,
    WINDOWED,
    WINDOWED_FULLSCREEN,
    GameSettings,
    find_game_settings,
    read_game_settings,
    screen_mismatch,
    steam_libraries,
)

SECTION = "[/Script/Squad.SQGameUserSettings]"


def write_ini(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    return str(path)


def settings_in(tmp_path, body, section=SECTION):
    return read_game_settings(write_ini(tmp_path / "GameUserSettings.ini", f"{section}\n{body}\n"))


def prefix_settings_path(library, platform="WindowsNoEditor"):
    return (
        library / "steamapps" / "compatdata" / "393380" / "pfx" / "drive_c" / "users"
        / "steamuser" / "AppData" / "Local" / "SquadGame" / "Saved" / "Config"
        / platform / "GameUserSettings.ini"
    )


# ---------- reading the file ----------

def test_values_are_read_from_a_game_user_settings_section(tmp_path):
    settings = settings_in(
        tmp_path,
        "FOV=105.000000\nResolutionSizeX=2560\nResolutionSizeY=1440\nFullscreenMode=1"
    )

    assert settings == GameSettings(105.0, 2560, 1440, WINDOWED_FULLSCREEN)


def test_keys_match_in_any_case_and_around_spaces(tmp_path):
    settings = settings_in(tmp_path, "  fov = 100 \nRESOLUTIONSIZEX=1920\nresolutionsizey=1080\n")

    assert settings.fov == 100.0
    assert (settings.width, settings.height) == (1920, 1080)


def test_the_section_name_only_has_to_hold_game_user_settings(tmp_path):
    assert settings_in(tmp_path, "FOV=95", "[SquadGameUserSettings]").fov == 95.0
    assert settings_in(tmp_path, "FOV=95", "[/script/engine.gameusersettings]").fov == 95.0


def test_a_fov_in_another_section_is_ignored(tmp_path):
    assert settings_in(tmp_path, "FOV=95", "[/Script/Engine.Player]").fov is None


def test_a_fov_after_another_section_starts_is_not_taken_from_the_first(tmp_path):
    path = write_ini(
        tmp_path / "GameUserSettings.ini",
        f"{SECTION}\nResolutionSizeX=1920\n[/Script/Squad.Other]\nFOV=70\n"
    )

    assert read_game_settings(path).fov is None


def test_the_last_line_of_a_repeated_key_wins(tmp_path):
    assert settings_in(tmp_path, "FOV=90\nFOV=110").fov == 110.0


def test_comments_and_lines_without_a_value_are_skipped(tmp_path):
    settings = settings_in(tmp_path, ";FOV=70\n#FOV=71\nnonsense\n+Array=1\nFOV=99")

    assert settings.fov == 99.0


def test_a_byte_order_mark_does_not_hide_the_first_section(tmp_path):
    path = tmp_path / "GameUserSettings.ini"
    path.write_bytes(f"﻿{SECTION}\nFOV=101\n".encode("utf-8"))

    assert read_game_settings(str(path)).fov == 101.0


@pytest.mark.parametrize("value", ["", "abc", "nan", "inf", "-inf", "1e999x", "90,5"])
def test_a_malformed_fov_is_not_found_and_the_rest_is_kept(tmp_path, value):
    settings = settings_in(tmp_path, f"FOV={value}\nResolutionSizeX=1920\nResolutionSizeY=1080")

    assert settings.fov is None
    assert settings.width == 1920


@pytest.mark.parametrize("value", ["0", "-90", "30", "59.9", "120.1", "360", "1e9"])
def test_a_fov_outside_the_games_range_is_not_found(tmp_path, value):
    assert settings_in(tmp_path, f"FOV={value}").fov is None


@pytest.mark.parametrize("value", ["60", "90", "120"])
def test_the_ends_of_the_games_fov_range_are_accepted(tmp_path, value):
    assert settings_in(tmp_path, f"FOV={value}").fov == float(value)


@pytest.mark.parametrize("body", [
    "ResolutionSizeX=1920",
    "ResolutionSizeX=1920\nResolutionSizeY=0",
    "ResolutionSizeX=-1920\nResolutionSizeY=1080",
    "ResolutionSizeX=wide\nResolutionSizeY=1080",
    "ResolutionSizeX=1920.5\nResolutionSizeY=1080",
])
def test_a_resolution_needs_two_positive_whole_numbers(tmp_path, body):
    settings = settings_in(tmp_path, body)

    assert settings.width is None and settings.height is None


@pytest.mark.parametrize("value", ["3", "-1", "x", ""])
def test_an_unknown_window_mode_is_not_found(tmp_path, value):
    assert settings_in(tmp_path, f"FullscreenMode={value}").window_mode is None


def test_a_file_without_the_values_gives_an_empty_result(tmp_path):
    assert settings_in(tmp_path, "") == GameSettings()


def test_an_empty_or_binary_file_does_not_crash(tmp_path):
    path = tmp_path / "GameUserSettings.ini"
    path.write_bytes(b"")
    assert read_game_settings(str(path)) == GameSettings()

    path.write_bytes(bytes(range(256)) * 20)
    assert read_game_settings(str(path)) == GameSettings()


def test_a_missing_file_reads_as_none(tmp_path):
    assert read_game_settings(str(tmp_path / "nothing.ini")) is None


def test_a_folder_in_place_of_the_file_reads_as_none(tmp_path):
    assert read_game_settings(str(tmp_path)) is None


# ---------- finding the file ----------

def test_the_file_in_the_default_steam_library_is_found(tmp_path):
    expected = write_ini(prefix_settings_path(tmp_path), SECTION)

    assert find_game_settings([str(tmp_path)]) == expected


def test_the_platform_folder_can_be_any(tmp_path):
    expected = write_ini(prefix_settings_path(tmp_path, "Windows"), SECTION)

    assert find_game_settings([str(tmp_path)]) == expected


def test_the_file_in_a_library_listed_by_libraryfolders_vdf_is_found(tmp_path):
    steam = tmp_path / "Steam"
    library = tmp_path / "games" / "SteamLibrary"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t\t"label"\t\t""\n\t}\n'
        '\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' % (steam, library)
    )
    expected = write_ini(prefix_settings_path(library), SECTION)

    assert steam_libraries([str(steam)]) == [str(steam), str(library)]
    assert find_game_settings([str(steam)]) == expected


def test_a_listed_library_that_is_gone_is_skipped(tmp_path):
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text('"path"\t"%s"\n' % (tmp_path / "gone"))

    assert steam_libraries([str(steam)]) == [str(steam)]
    assert find_game_settings([str(steam)]) is None


def test_the_most_recently_written_file_of_several_libraries_wins(tmp_path):
    old = write_ini(prefix_settings_path(tmp_path / "a"), SECTION)
    new = write_ini(prefix_settings_path(tmp_path / "b"), SECTION)
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))

    assert find_game_settings([str(tmp_path / "a"), str(tmp_path / "b")]) == new


def test_no_file_means_none(tmp_path):
    assert find_game_settings([str(tmp_path)]) is None
    assert find_game_settings([]) is None


def test_the_steam_folders_of_the_user_are_the_default_roots(tmp_path, monkeypatch):
    home = tmp_path / "home"
    expected = write_ini(prefix_settings_path(home / ".local" / "share" / "Steam"), SECTION)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(gamesettings, "STEAM_ROOTS", ("~/.local/share/Steam", "~/.steam/steam"))

    assert find_game_settings() == os.path.realpath(expected)


def test_a_steam_folder_reached_by_a_symlink_is_listed_once(tmp_path, monkeypatch):
    real = tmp_path / "home" / ".local" / "share" / "Steam"
    real.mkdir(parents=True)
    (tmp_path / "home" / ".steam").mkdir()
    (tmp_path / "home" / ".steam" / "steam").symlink_to(real)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(gamesettings, "STEAM_ROOTS", ("~/.local/share/Steam", "~/.steam/steam"))

    assert gamesettings.steam_roots() == [str(real)]


# ---------- the game does not fill the screen ----------

def test_windowed_fullscreen_fills_the_screen_whatever_resolution_is_saved():
    settings = GameSettings(120.0, 1280, 720, WINDOWED_FULLSCREEN)

    assert not screen_mismatch(settings, 1920, 1080)


def test_a_windowed_game_does_not_fill_the_screen():
    assert screen_mismatch(GameSettings(120.0, 1920, 1080, WINDOWED), 1920, 1080)


def test_a_fullscreen_game_at_another_resolution_does_not_fill_the_screen():
    assert screen_mismatch(GameSettings(120.0, 1280, 720, FULLSCREEN), 1920, 1080)
    assert not screen_mismatch(GameSettings(120.0, 1920, 1080, FULLSCREEN), 1920, 1080)


def test_without_a_window_mode_only_the_resolution_decides():
    assert screen_mismatch(GameSettings(120.0, 1280, 720, None), 1920, 1080)
    assert not screen_mismatch(GameSettings(120.0, 1920, 1080, None), 1920, 1080)


def test_a_file_without_resolution_or_mode_raises_no_warning():
    assert not screen_mismatch(GameSettings(120.0), 1920, 1080)
