import json
import os

import pytest

import config


def test_defaults_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "cfg" / "config.json"

    cfg = config.load_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert path.exists()

    # Mutating the returned config must not change the defaults.
    cfg["hotkeys"]["toggle_overlay"] = "F1"
    assert config.DEFAULT_CONFIG["hotkeys"]["toggle_overlay"] == "F8"


def test_missing_keys_are_filled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 110.0, "color": "red"}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 110.0
    assert cfg["color"] == "red"
    assert cfg["mark_size"] == 100


REMOVED_MARK_SETTINGS = {
    "fps": 120,
    "opacity": 100,
    "animated": False,
    "glow_enabled": False,
    "dot_enabled": False,
    "lines_enabled": False,
    "t_style": True,
    "circle_enabled": True,
    "dot_size": 9,
    "line_length": 30,
    "line_gap": 3,
    "line_thickness": 4,
    "circle_radius": 40,
    "outline_enabled": False,
    "outline_thickness": 3,
    "outline_color": "black",
}


def test_old_config_with_removed_mark_settings_loads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    kept = {"offset_scale": 120, "center_offset_x": 40, "center_offset_y": -40}
    path.write_text(json.dumps({**REMOVED_MARK_SETTINGS, **kept, "fov": 75, "range_ladder": False}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 75
    assert cfg["range_ladder"] is False
    assert {key: cfg[key] for key in kept} == kept
    assert not set(REMOVED_MARK_SETTINGS) & set(cfg)

    config.save_config(cfg, str(path))
    assert not set(REMOVED_MARK_SETTINGS) & set(json.loads(path.read_text()))


@pytest.mark.parametrize("old, name", [
    ([0, 255, 0], "green"),
    ([255, 48, 48], "red"),
    ([255, 255, 255], "white"),
    ([250, 20, 20], "red"),
    ([10, 240, 30], "green"),
    ([250, 150, 40], "orange"),
    ([200, 200, 100], "orange"),
    ([255.0, 0.0, 250.0], "magenta"),
    ([20, 200, 255], "cyan"),
    ([40, 100, 240], "blue"),
    ([300, -5, 999], "magenta"),
])
def test_an_old_rgb_colour_becomes_the_nearest_swatch(tmp_path, monkeypatch, old, name):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"color": old}))

    assert config.load_config(str(path))["color"] == name


def test_every_swatch_is_its_own_nearest_swatch():
    for name, rgb in config.MARK_COLORS.items():
        assert config.nearest_mark_color(list(rgb)) == name


def test_the_default_colour_is_the_old_default_green():
    assert config.MARK_COLORS[config.DEFAULT_CONFIG["color"]] == (0, 255, 0)
    assert len(config.MARK_COLORS) == 8


def test_corrupted_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text("{not json")

    assert config.load_config(str(path))["fov"] == 90


def test_wrong_types_ignored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "fov": "wide",
        "info_enabled": 1,
        "color": [1, 2],
        "mark_style": "star",
        "mark_size": "big",
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 90
    assert cfg["info_enabled"] is True
    assert cfg["color"] == "green"
    assert cfg["mark_style"] == "cross_dot"
    assert cfg["mark_size"] == 100


def test_legacy_config_migrated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "configs" / "config.json"
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"fov": 100}))

    path = tmp_path / "new" / "config.json"

    assert config.load_config(str(path))["fov"] == 100
    assert json.loads(path.read_text())["fov"] == 100


def test_hotkeys_merged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "hotkeys": {"distance_up": "PgUp", "toggle_overlay": 5},
        "recent_weapons": ["a", 3, "b"],
    }))

    cfg = config.load_config(str(path))

    assert cfg["hotkeys"]["distance_up"] == "PgUp"
    assert cfg["hotkeys"]["toggle_overlay"] == "F8"
    assert cfg["hotkeys"]["reset_offset"] == "F9"
    assert cfg["recent_weapons"] == ["a", "b"]


def test_renamed_weapons_are_migrated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "last_weapon": "Carl Gustav / M3 MAAWS · HEAT",
        "recent_weapons": ["MK19 / AGS-17 / AGS-30", "RPG-29"],
    }))

    cfg = config.load_config(str(path))

    assert cfg["last_weapon"] == "M3 MAAWS · HEAT / Smoke"
    assert cfg["recent_weapons"] == ["MK19", "RPG-29"]


def test_values_are_validated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "mark_size": 500,
        "mark_style": "t",
        "fov": 0,
        "arc": "sideways",
        "distance_step": 7,
    }))

    cfg = config.load_config(str(path))

    assert cfg["mark_size"] == config.RANGES["mark_size"][1]
    assert cfg["mark_style"] == "t"
    assert cfg["fov"] == 1
    assert cfg["arc"] == "auto"
    assert cfg["distance_step"] == config.DEFAULT_CONFIG["distance_step"]


def test_defaults_are_inside_ranges():
    for key, (low, high) in config.RANGES.items():
        if config.DEFAULT_CONFIG[key] is None:
            continue

        assert low <= config.DEFAULT_CONFIG[key] <= high, key

    for key, choices in config.CHOICES.items():
        assert config.DEFAULT_CONFIG[key] in choices, key


def test_wayland_runs_through_xwayland():
    from app import prefer_x11

    wayland = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    prefer_x11(wayland)
    assert wayland["QT_QPA_PLATFORM"] == "xcb"

    chosen = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0", "QT_QPA_PLATFORM": "wayland"}
    prefer_x11(chosen)
    assert chosen["QT_QPA_PLATFORM"] == "wayland"

    no_xwayland = {"WAYLAND_DISPLAY": "wayland-0"}
    prefer_x11(no_xwayland)
    assert "QT_QPA_PLATFORM" not in no_xwayland

    x11 = {"DISPLAY": ":0"}
    prefer_x11(x11)
    assert "QT_QPA_PLATFORM" not in x11


def test_lay_rates_keep_only_positive_numbers():
    merged = config._merge({"lay_rates": {
        "Mortar (M252 / 2B14 / L16 / Type 63)": 8.7,
        "bad": "fast", "zero": 0, "flag": True, "neg": -1,
    }})
    assert merged["lay_rates"] == {"Mortar (M252 / 2B14 / L16 / Type 63)": 8.7}
    assert config._merge({"lay_rates": [1, 2]})["lay_rates"] == {}


def test_settings_of_the_removed_device_link_are_ignored(tmp_path):
    """Files saved by 1.6.0 builds with the device link still load."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "relay_code": "ABCD2345",
        "relay_enabled": False,
        "fov": 60
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 60
    assert "relay_code" not in cfg
    assert "relay_enabled" not in cfg

def test_settings_of_the_removed_hold_timer_are_ignored(tmp_path):
    """Files saved by 1.6.0 builds with the AGS-17 beep still load."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "hold_timer": False,
        "hold_panel": False,
        "hold_panel_corner": "bottom_left",
        "hold_lead": 0.31,
        "fov": 60
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 60
    for key in ("hold_timer", "hold_panel", "hold_panel_corner", "hold_lead"):
        assert key not in cfg

    config.save_config(cfg, str(path))
    assert "hold_lead" not in json.loads(path.read_text())


def test_saved_settings_are_private(tmp_path):
    folder = tmp_path / "new" / "SquadBallistics"
    path = folder / "config.json"

    config.save_config(config.load_config(str(path)), str(path))

    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(folder).st_mode & 0o777 == 0o700
    assert json.loads(path.read_text())["fov"] == config.DEFAULT_CONFIG["fov"]


def test_saving_replaces_a_world_readable_file_and_temp_file(tmp_path):
    path = tmp_path / "config.json"

    for stale in (path, tmp_path / "config.json.tmp"):
        stale.write_text("{}")
        os.chmod(stale, 0o644)

    config.save_config({"fov": 60}, str(path))

    assert os.stat(path).st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == {"fov": 60}
    assert not (tmp_path / "config.json.tmp").exists()


def test_language_and_accent_settings_are_ignored(tmp_path):
    """Files saved by older versions with the language and accent still load."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "language": "ru",
        "accent": "#22c55e",
        "fov": 60
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 60
    assert "language" not in cfg
    assert "accent" not in cfg
