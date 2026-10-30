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


def test_an_unreadable_file_is_kept_as_bad_and_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"fov": 100, "mark_size": 120')

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert bad == str(path) + ".bad"
    assert (tmp_path / "config.json.bad").read_text() == '{"fov": 100, "mark_size": 120'
    assert json.loads(path.read_text()) == config.DEFAULT_CONFIG

    # The next start reads the new file and reports nothing.
    assert config.read_config(str(path)) == (config.DEFAULT_CONFIG, None)


@pytest.mark.parametrize("text", [
    "",
    "{not json",
    "[]",
    "null",
    '"settings"',
    "42",
    "[" * 100000 + "]" * 100000,
    '{"fov": 1' + "0" * 5000,
])
def test_any_unreadable_content_is_kept(tmp_path, text):
    path = tmp_path / "config.json"
    path.write_text(text)

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert bad == str(path) + ".bad"
    assert (tmp_path / "config.json.bad").read_text() == text


def test_a_file_that_is_not_utf8_is_kept(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'{"fov": "\xff\xfe"}')

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert (tmp_path / "config.json.bad").read_bytes() == b'{"fov": "\xff\xfe"}'


def test_a_bad_file_that_cannot_be_moved_is_not_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{broken")

    def refuse(source, target):
        raise PermissionError(source)

    monkeypatch.setattr(config.os, "replace", refuse)

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert bad == str(path)
    assert path.read_text() == "{broken"


def test_a_missing_file_is_not_reported(tmp_path):
    cfg, bad = config.read_config(str(tmp_path / "config.json"))

    assert (cfg, bad) == (config.DEFAULT_CONFIG, None)


NUMERIC_SETTINGS = [
    key for key, value in config.DEFAULT_CONFIG.items()
    if isinstance(value, (int, float)) and not isinstance(value, bool)
]


@pytest.mark.parametrize("key", NUMERIC_SETTINGS)
@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "1" + "0" * 400])
def test_a_non_finite_number_falls_back_to_its_default_alone(tmp_path, key, junk):
    """Python's json reads NaN and Infinity, and a 400-digit integer does
    not fit a float: none of them may crash or clamp to a range end."""
    other = "mark_size" if key != "mark_size" else "fov"
    path = tmp_path / "config.json"
    path.write_text(f'{{"{key}": {junk}, "{other}": 120}}')

    cfg = config.load_config(str(path))

    assert cfg[key] == config.DEFAULT_CONFIG[key]
    assert cfg[other] == 120


@pytest.mark.parametrize("key", [k for k in NUMERIC_SETTINGS if k not in config.FRACTIONAL_SETTINGS])
def test_a_fraction_for_a_whole_number_setting_falls_back_to_its_default(tmp_path, key):
    low, high = config.RANGES[key]
    path = tmp_path / "config.json"
    path.write_text(json.dumps({key: (low + high) / 2 + 0.5, "fov": 100}))

    cfg = config.load_config(str(path))

    assert cfg[key] == config.DEFAULT_CONFIG[key]
    assert type(cfg[key]) is int
    assert cfg["fov"] == 100


def test_the_fov_keeps_its_fraction(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 103.5}))

    assert config.load_config(str(path))["fov"] == 103.5


def test_lay_rates_and_colours_reject_numbers_that_do_not_fit_a_float(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"lay_rates": {"A": Infinity, "B": 1' + "0" * 400 + ', "C": 2.5},'
        ' "color": [1e308, 0, 0]}'
    )

    cfg = config.load_config(str(path))

    assert cfg["lay_rates"] == {"C": 2.5}
    assert cfg["color"] == "red"


def test_an_old_colour_with_a_non_finite_part_falls_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"color": [Infinity, 0, 0]}')

    assert config.load_config(str(path))["color"] == config.DEFAULT_CONFIG["color"]


def random_json(rng, depth=0):
    """Any JSON value, with the numbers and strings that break parsers."""
    kind = rng.randrange(9 if depth < 3 else 6)

    if kind == 0:
        return None
    if kind == 1:
        return rng.choice([True, False])
    if kind == 2:
        return rng.choice([0, -1, 1, 7, 15, 16, 100, 10 ** 30, -10 ** 30, 10 ** 400])
    if kind == 3:
        return rng.choice([0.5, -0.0, 1e308, -1e308, 5e-324, 90.0, 179.9, float("nan"), float("inf"), float("-inf")])
    if kind == 4:
        return rng.choice(["", "F8", "Ins", "auto", "red", "dot", "\ud800", "\x00", "Ctrl+Q", "MK19", "x" * 10000])
    if kind == 5:
        return rng.choice(list(config.DEFAULT_CONFIG.values()))
    if kind == 6:
        return [random_json(rng, depth + 1) for _ in range(rng.randrange(5))]

    keys = list(config.DEFAULT_CONFIG) + list(config.DEFAULT_CONFIG["hotkeys"]) + ["", "MK19", "x|plain"]
    return {rng.choice(keys): random_json(rng, depth + 1) for _ in range(rng.randrange(6))}


def assert_valid(cfg):
    """Every setting has its default's type and lies in its range or choices."""
    assert cfg.keys() == config.DEFAULT_CONFIG.keys()

    for key, default in config.DEFAULT_CONFIG.items():
        value = cfg[key]

        if isinstance(default, bool):
            assert type(value) is bool, key
        elif isinstance(default, (int, float)):
            assert isinstance(value, (int, float)) and not isinstance(value, bool), key
            assert value == value and abs(value) != float("inf"), key
            if key not in config.FRACTIONAL_SETTINGS:
                assert type(value) is int, key
            if key in config.RANGES:
                low, high = config.RANGES[key]
                assert low <= value <= high, key
        elif key in config.CHOICES:
            assert value in config.CHOICES[key], key
        else:
            assert isinstance(value, type(default)), key

    assert all(isinstance(v, str) for v in cfg["hotkeys"].values())
    assert all(isinstance(v, str) for v in cfg["recent_weapons"])
    for table in ("lay_rates", "mark_trim"):
        assert all(
            isinstance(v, float) and v == v and abs(v) != float("inf")
            for v in cfg[table].values()
        ), table
    json.dumps(cfg, allow_nan=False)


def test_any_json_gives_valid_settings(tmp_path):
    import random

    rng = random.Random(20261030)
    path = tmp_path / "config.json"

    for _ in range(2000):
        document = {}
        for key in rng.sample(list(config.DEFAULT_CONFIG), rng.randrange(1, 8)):
            document[key] = random_json(rng)

        path.write_text(json.dumps(document))
        cfg, bad = config.read_config(str(path))

        assert bad is None, document
        assert_valid(cfg)


def test_the_app_starts_from_any_settings_file(qapp, tmp_path, monkeypatch):
    """Whatever the settings file holds, the main window opens, calculates
    and saves (hostile values per setting, then random documents)."""
    import random

    from ballistics import load_weapons
    from conftest import ROOT
    from crosshair import MainWindow

    weapons = load_weapons(os.path.join(ROOT, "weapons.json"))
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", str(path))

    hostile = [
        '{"last_weapon": "\\ud800", "recent_weapons": ["\\ud800", "\\u0000", "MK19"],'
        ' "hotkeys": {"toggle_overlay": "\\ud800", "reset_offset": "F8"}}',
        '{"fov": NaN, "mark_size": Infinity, "monitor": 1' + "0" * 400 + ', "offset_scale": 75.5}',
        '{"color": [1e308, -1e308, NaN], "mark_style": ["dot"], "lay_rates": {"MK19": -1}}',
        '{"mark_trim": {"MK19|plain": 1e308, "\\ud800": 0.5, "": 1}, "unit_mode": null}',
        '{"monitor": 15, "center_offset_x": 300, "center_offset_y": -300, "distance_step": 100}',
    ]
    rng = random.Random(7)
    for _ in range(10):
        document = {
            key: random_json(rng)
            for key in rng.sample(list(config.DEFAULT_CONFIG), rng.randrange(3, 10))
        }
        hostile.append(json.dumps(document))

    for text in hostile:
        path.write_text(text)

        window = MainWindow(weapons)
        try:
            window.select_weapon("SPG-9 · HEAT")
            window.distance_entry.setText("500")
            window.calculate()
            assert window.last_solution.reachable, text
        finally:
            window.close()

        assert_valid(json.loads(path.read_text()))
