import json

import config


def test_defaults_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "cfg" / "config.json"

    cfg = config.load_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert path.exists()

    # Mutating the returned config must not change the defaults.
    cfg["color"][0] = 1
    assert config.DEFAULT_CONFIG["color"][0] == 0


def test_missing_keys_are_filled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fov": 110.0, "color": [255, 0, 0]}))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 110.0
    assert cfg["color"] == [255, 0, 0]
    assert cfg["offset_scale"] == 100


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
        "dot_enabled": 1,
        "color": [1, 2],
        "dot_size": 7,
    }))

    cfg = config.load_config(str(path))

    assert cfg["fov"] == 90
    assert cfg["dot_enabled"] is True
    assert cfg["color"] == [0, 255, 0]
    assert cfg["dot_size"] == 7


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
        "dot_size": 500,
        "opacity": -4,
        "fov": 0,
        "language": "klingon",
        "arc": "sideways",
        "accent": "red; background: url(x)",
        "distance_step": 7,
        "outline_color": "black",
    }))

    cfg = config.load_config(str(path))

    assert cfg["dot_size"] == config.RANGES["dot_size"][1]
    assert cfg["opacity"] == config.RANGES["opacity"][0]
    assert cfg["fov"] == 1
    assert cfg["language"] == "auto"
    assert cfg["arc"] == "auto"
    assert cfg["accent"] == config.DEFAULT_CONFIG["accent"]
    assert cfg["distance_step"] == config.DEFAULT_CONFIG["distance_step"]
    assert cfg["outline_color"] == "black"


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


def test_device_link_settings_from_older_versions(tmp_path):
    """A typed relay code stays and the link is on; no code means the app makes one."""
    path = tmp_path / "config.json"

    path.write_text(json.dumps({"relay_code": "ABCD2345"}))
    cfg = config.load_config(str(path))
    assert cfg["relay_code"] == "ABCD2345"
    assert cfg["relay_enabled"] is True

    path.write_text(json.dumps({"relay_code": 5, "relay_enabled": "no"}))
    cfg = config.load_config(str(path))
    assert cfg["relay_code"] == ""
    assert cfg["relay_enabled"] is True


def test_learnt_hold_lead_survives_a_restart(tmp_path):
    from holdtimer import MAX_LEAD

    path = tmp_path / "config.json"
    cfg = config.load_config(str(path))
    assert cfg["hold_lead"] is None

    cfg["hold_lead"] = 0.31
    config.save_config(cfg, str(path))
    assert config.load_config(str(path))["hold_lead"] == 0.31

    assert config.RANGES["hold_lead"] == (0.0, MAX_LEAD)

    for stored, loaded in ((9.0, MAX_LEAD), (-1, 0.0), (True, None), ("0.3", None), (float("nan"), None)):
        path.write_text(json.dumps({"hold_lead": stored}))
        assert config.load_config(str(path))["hold_lead"] == loaded
