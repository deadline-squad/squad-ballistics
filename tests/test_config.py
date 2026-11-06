import json
import os
import re

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
    path.write_text(json.dumps({"fov": 110.0}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 110.0
    assert cfg["info_enabled"] is True


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
    "mark_style": "dot",
    "color": "green",
    "mark_size": 150,
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


def test_corrupted_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text("{not json")

    assert config.load_config(str(path))["fov"] == 120


def test_wrong_types_ignored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "fov": "wide",
        "info_enabled": 1,
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 120
    assert cfg["info_enabled"] is True


def test_the_default_fov_is_120(tmp_path):
    cfg = config.load_config(str(tmp_path / "config.json"))

    assert config.DEFAULT_CONFIG["fov"] == 120
    assert cfg["fov"] == 120
    assert cfg["settings_version"] == config.SETTINGS_VERSION


def test_a_file_of_before_the_new_default_keeps_no_90(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 90, "offset_scale": 110}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 120
    assert cfg["offset_scale"] == 110
    assert cfg["settings_version"] == config.SETTINGS_VERSION


def test_a_file_of_before_the_new_default_keeps_another_fov(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 100}))

    assert config.load_config(str(path))["fov"] == 100


def test_a_90_chosen_after_the_new_default_stays(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 90, "settings_version": config.SETTINGS_VERSION}))

    assert config.load_config(str(path))["fov"] == 90


def test_the_migrated_fov_is_saved_with_the_version(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 90}))

    config.save_config(config.load_config(str(path)), str(path))

    saved = json.loads(path.read_text())

    assert saved["fov"] == 120
    assert saved["settings_version"] == config.SETTINGS_VERSION
    assert config.load_config(str(path))["fov"] == 120


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
        "offset_scale": 500,
        "fov": 0,
        "arc": "sideways",
        "distance_step": 7,
    }))

    cfg = config.load_config(str(path))

    assert cfg["offset_scale"] == config.RANGES["offset_scale"][1]
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


MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


def test_a_lay_rate_beyond_the_calibration_tolerance_falls_back_to_the_file():
    """A hand-edited 1e-6 deg/s would hold S for 4e7 s: rates more than
    LAY_RATE_TOLERANCE off weapons.json's are dropped on load, like the
    calibration refuses them."""
    base = config.file_hold_rates()[MORTAR]
    tolerance = config.LAY_RATE_TOLERANCE

    for rate in (1e-6, base * (1 - tolerance) - 0.01, base * (1 + tolerance) + 0.01, 1e6):
        assert config._merge({"lay_rates": {MORTAR: rate}})["lay_rates"] == {}, rate

    for rate in (base * (1 - tolerance) + 0.001, base, base * (1 + tolerance) - 0.001):
        assert config._merge({"lay_rates": {MORTAR: rate}})["lay_rates"] == {MORTAR: rate}

    # A name weapons.json does not lay by hold changes nothing and is kept.
    assert config._merge({"lay_rates": {"Gone": 0.5}})["lay_rates"] == {"Gone": 0.5}


def test_the_load_bound_is_the_calibration_tolerance():
    import crosshair

    assert config.LAY_RATE_TOLERANCE == crosshair.LAY_RATE_TOLERANCE


def test_a_migrated_key_on_a_newer_actions_default_unbinds_the_newer_action():
    """1.2.0 had no auto_hold (F7 by default): a 1.2.0 file with F7 bound
    elsewhere keeps that binding and leaves auto_hold visibly unbound
    instead of shown on F7 but never bound."""
    import hotkeys

    cfg = config._merge({"hotkeys": {"toggle_overlay": "F8", "distance_up": "F7"}})

    assert cfg["hotkeys"]["distance_up"] == "F7"
    assert cfg["hotkeys"]["auto_hold"] == ""

    cfg["auto_hold"] = True
    window = type("Window", (), {"config": cfg})()
    assert hotkeys.bindings(window) == [
        ("F8", "toggle_overlay"), ("F9", "reset_offset"), ("F7", "distance_up"), ("Mouse4", "toggle_view"),
    ]

    # No clash: the newer action gets its default key.
    assert config._merge({"hotkeys": {"distance_up": "F6"}})["hotkeys"]["auto_hold"] == "F7"

    # A file that names the newer action keeps what it says.
    saved = {"distance_up": "F7", "auto_hold": "F7"}
    assert config._merge({"hotkeys": saved})["hotkeys"]["auto_hold"] == "F7"


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


SECRET_WORDS = re.compile(r"token|secret|password|passwd|credential|api_?key|steam|relay|session|cookie", re.I)


def test_no_setting_is_a_secret():
    """The settings file is readable by its owner only, but it must not hold
    secrets at all: no setting is named like one."""
    assert not [key for key in config.DEFAULT_CONFIG if SECRET_WORDS.search(key)]


def test_keys_that_are_not_settings_are_not_written_back(tmp_path):
    """A key the app does not know (a secret pasted into the file by hand,
    one of a removed feature) is dropped at the next save, not copied."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 60, "api_token": "hunter2", "steam_id": "x"}))

    config.save_config(config.load_config(str(path)), str(path))

    saved = json.loads(path.read_text())
    assert set(saved) <= set(config.DEFAULT_CONFIG)
    assert "hunter2" not in path.read_text()


def test_a_settings_folder_of_an_older_version_is_made_private(tmp_path):
    """1.2.0 created the folder 0755: the next save closes it to others."""
    folder = tmp_path / "SquadBallistics"
    folder.mkdir()
    os.chmod(folder, 0o755)

    config.save_config({"fov": 60}, str(folder / "config.json"))

    assert os.stat(folder).st_mode & 0o777 == 0o700


def test_settings_reach_the_disk_before_they_replace_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    events = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(descriptor):
        events.append("fsync")
        real_fsync(descriptor)

    def replace(source, target):
        events.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)

    config.save_config({"fov": 60}, str(path))

    assert events == ["fsync", "replace"]
    assert json.loads(path.read_text()) == {"fov": 60}


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
    path.write_text('{"fov": 100, "offset_scale": 120')

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert bad == str(path) + ".bad"
    assert (tmp_path / "config.json.bad").read_text() == '{"fov": 100, "offset_scale": 120'
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


# settings_version marks the file format, it is not a setting with a range.
NUMERIC_SETTINGS = [
    key for key, value in config.DEFAULT_CONFIG.items()
    if isinstance(value, (int, float)) and not isinstance(value, bool)
    and key != "settings_version"
]


@pytest.mark.parametrize("key", NUMERIC_SETTINGS)
@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "1" + "0" * 400])
def test_a_non_finite_number_falls_back_to_its_default_alone(tmp_path, key, junk):
    """Python's json reads NaN and Infinity, and a 400-digit integer does
    not fit a float: none of them may crash or clamp to a range end."""
    other = "offset_scale" if key != "offset_scale" else "fov"
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


def test_lay_rates_reject_numbers_that_do_not_fit_a_float(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"lay_rates": {"A": Infinity, "B": 1' + "0" * 400 + ', "C": 2.5}}'
    )

    cfg = config.load_config(str(path))

    assert cfg["lay_rates"] == {"C": 2.5}


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
    assert all(
        isinstance(v, float) and v == v and abs(v) != float("inf")
        for v in cfg["lay_rates"].values()
    )
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
        '{"fov": NaN, "offset_scale": Infinity, "monitor": 1' + "0" * 400 + ', "offset_scale": 75.5}',
        '{"lay_rates": {"MK19": -1}}',
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
