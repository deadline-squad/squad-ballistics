"""Behaviour of config.py found by mutation testing (mutmut): the folders,
the saved trims and rates, the numeric limits and the files written."""

import json
import os
import subprocess
import sys

import pytest

import config

MORTAR = "Mortar (M252 / 2B14 / L16 / Type 63)"


@pytest.mark.parametrize("function, variable, home_part", [
    (config.config_dir, "XDG_CONFIG_HOME", ".config"),
    (config.data_dir, "XDG_CACHE_HOME", ".cache"),
    (config.state_dir, "XDG_DATA_HOME", os.path.join(".local", "share")),
])
def test_the_folders_follow_xdg_and_fall_back_to_home(function, variable, home_part, monkeypatch, tmp_path):
    monkeypatch.setenv(variable, str(tmp_path / "x"))
    assert function() == str(tmp_path / "x" / "SquadBallistics")

    monkeypatch.setenv(variable, "")
    assert function() == os.path.join(os.path.expanduser("~"), home_part, "SquadBallistics")

    monkeypatch.delenv(variable)
    assert function() == os.path.join(os.path.expanduser("~"), home_part, "SquadBallistics")


def test_the_hold_rates_are_those_of_the_weapons_laid_by_elevation():
    assert config.file_hold_rates() == {MORTAR: 9.0}


def test_the_plain_view_of_an_rmb_sight_is_its_twin_and_other_names_stay():
    assert config.plain_view_name("QLZ87 · optic (RMB ×3)") == "QLZ87 · no optic"
    assert config.plain_view_name("Hell Cannon") == "Hell Cannon"
    assert config.plain_view_name("not a weapon") == "not a weapon"


def test_lay_rates_within_30_percent_of_the_file_are_kept_and_others_dropped():
    base = 9.0

    kept = config._valid_lay_rates({
        MORTAR: base * 1.29,
        "Other": 3,
    })
    assert kept == {MORTAR: base * 1.29, "Other": 3.0}

    assert config._valid_lay_rates({MORTAR: base * 1.31}) == {}
    assert config._valid_lay_rates({MORTAR: base * 0.71}) == {MORTAR: base * 0.71}
    assert config._valid_lay_rates({MORTAR: base * 0.69}) == {}
    assert config._valid_lay_rates({MORTAR: 0, "A": -1, "B": True, "C": "9", "D": float("nan")}) == {}
    assert config._valid_lay_rates({5: 9.0}) == {}


def test_mark_trims_are_clamped_and_zero_or_junk_is_dropped():
    trims = config._valid_mark_trims({
        "SPG-9 · HEAT": 0.35,
        "SPG-9 · FRAG": 99,
        "AT-4": -99,
        "Zero": 0,
        "Junk": "1",
        "Bool": True,
        "": 1.0,
        5: 1.0,
        "Inf": float("inf"),
    })

    assert trims == {"SPG-9 · HEAT": 0.35, "SPG-9 · FRAG": config.clamp_trim(99), "AT-4": config.clamp_trim(-99)}
    assert trims["SPG-9 · FRAG"] == 5.0 and trims["AT-4"] == -5.0


def test_a_trim_saved_per_view_keeps_only_the_plain_one_under_the_plain_views_name():
    trims = config._valid_mark_trims({
        "QLZ87|plain": 0.2,
        "QLZ87|optic": 0.4,
        "QLZ87|optic2": 0.6,
        "SPG-9 · HEAT|plain": 0.3,
        "|plain": 0.9,
        "AT-4|plain": 0,
    })

    assert trims == {"QLZ87 · no optic": 0.2, "SPG-9 · HEAT": 0.3}


def test_a_renamed_weapons_trim_follows_its_new_name():
    trims = config._valid_mark_trims({"QLZ87": 0.5})

    assert trims == {"QLZ87 · optic (RMB ×3)": 0.5}


def test_numbers_are_clamped_to_their_range_and_fractions_only_where_allowed():
    assert config._valid_number("fov", 500) == 179
    assert config._valid_number("fov", 0) == 1
    assert config._valid_number("fov", 90.5) == 90.5
    assert config._valid_number("offset_scale", 49) == 50
    assert config._valid_number("offset_scale", 151) == 150
    assert config._valid_number("offset_scale", 100.5) is None
    assert config._valid_number("offset_scale", True) is None
    assert config._valid_number("offset_scale", float("nan")) is None
    assert config._valid_number("target_height", 11.5) == 10.0
    assert config._valid_number("target_height", -1) == 0.0
    assert config._valid_number("unlisted", 123456) == 123456


def test_merge_keeps_valid_values_and_drops_the_rest_one_by_one():
    merged = config._merge({
        "fov": 70,
        "arc": "high",
        "unit_mode": "nonsense",
        "auto_calc": "yes",
        "main_on_top": True,
        "distance_step": 7,
        "recent_weapons": ["QLZ87", 5, "A", "B", "C", "D", "E", "F"],
        "last_weapon": "QLZ87",
        "hotkeys": {"toggle_overlay": "F5", "reset_offset": 5, "bogus": "F1"},
        "map_external": True,
        "mark_trim": "text",
        "lay_rates": [],
    })

    assert merged["fov"] == 70
    assert merged["arc"] == "high"
    assert merged["unit_mode"] == "auto"
    assert merged["auto_calc"] is True
    assert merged["main_on_top"] is True
    assert merged["distance_step"] == config.DEFAULT_CONFIG["distance_step"]
    assert merged["recent_weapons"] == ["QLZ87 · optic (RMB ×3)", "A", "B", "C", "D"]
    assert merged["last_weapon"] == "QLZ87 · optic (RMB ×3)"
    assert merged["hotkeys"]["toggle_overlay"] == "F5"
    assert merged["hotkeys"]["reset_offset"] == "F9"
    assert "bogus" not in merged["hotkeys"]
    assert merged["map_external"] is True
    assert merged["mark_trim"] == {} and merged["lay_rates"] == {}


def test_merge_of_something_else_than_an_object_is_the_defaults():
    for loaded in ([], "x", None, 3):
        assert config._merge(loaded) == config.DEFAULT_CONFIG


def test_a_new_action_whose_key_is_used_by_a_saved_one_is_left_unbound():
    merged = config._merge({"hotkeys": {"toggle_overlay": "F7"}})

    assert merged["hotkeys"]["auto_hold"] == ""
    assert merged["hotkeys"]["toggle_overlay"] == "F7"

    merged = config._merge({"hotkeys": {"toggle_overlay": "F5"}})
    assert merged["hotkeys"]["auto_hold"] == "F7"


def test_the_defaults_are_never_shared_with_a_loaded_config():
    merged = config._merge({})
    merged["hotkeys"]["toggle_overlay"] = "X"
    merged["mark_trim"]["a"] = 1

    assert config.DEFAULT_CONFIG["hotkeys"]["toggle_overlay"] == "F8"
    assert config.DEFAULT_CONFIG["mark_trim"] == {}


def test_reading_nested_json_deeper_than_the_parser_allows_is_an_error(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("[" * 100000 + "]" * 100000)

    with pytest.raises(ValueError, match="nested"):
        config._read(str(path))

    path.write_text("[1]")
    with pytest.raises(ValueError, match="object"):
        config._read(str(path))

    with pytest.raises(OSError):
        config._read(str(tmp_path / "missing.json"))


def test_a_bad_file_is_kept_aside_and_the_defaults_are_saved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken")

    cfg, bad = config.read_config(str(path))

    assert cfg == config.DEFAULT_CONFIG
    assert bad == str(path) + ".bad"
    assert open(bad).read() == "{broken"
    assert json.loads(path.read_text()) == config.DEFAULT_CONFIG

    # An older bad file is replaced
    path.write_text("[2]")
    cfg, bad = config.read_config(str(path))
    assert open(bad).read() == "[2]"


def test_a_bad_file_that_cannot_be_moved_is_left_and_not_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{broken")
    monkeypatch.setattr(config.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("no")))

    cfg, bad = config.read_config(str(path))

    assert bad == str(path)
    assert cfg == config.DEFAULT_CONFIG
    assert path.read_text() == "{broken"


def test_no_file_gives_the_defaults_and_writes_them(tmp_path):
    path = tmp_path / "new" / "config.json"

    cfg, bad = config.read_config(str(path))

    assert bad is None and cfg == config.DEFAULT_CONFIG
    assert json.loads(path.read_text()) == config.DEFAULT_CONFIG


def test_a_file_of_1_1_0_is_migrated_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("configs")
    with open(config.LEGACY_CONFIG_PATH, "w") as f:
        json.dump({"fov": 55}, f)
    path = tmp_path / "home" / "config.json"

    cfg, bad = config.read_config(str(path))

    assert cfg["fov"] == 55 and bad is None
    assert json.loads(path.read_text())["fov"] == 55

    # A broken legacy file is skipped
    with open(config.LEGACY_CONFIG_PATH, "w") as f:
        f.write("{")
    other = tmp_path / "other" / "config.json"
    cfg, _ = config.read_config(str(other))
    assert cfg == config.DEFAULT_CONFIG


def test_a_legacy_file_does_not_overwrite_a_bad_one_that_stayed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("configs")
    with open(config.LEGACY_CONFIG_PATH, "w") as f:
        json.dump({"fov": 55}, f)
    path = tmp_path / "config.json"
    path.write_text("{broken")
    monkeypatch.setattr(config.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("no")))

    cfg, bad = config.read_config(str(path))

    assert cfg["fov"] == 55 and bad == str(path)
    assert path.read_text() == "{broken"


def test_saving_writes_json_privately_over_a_leftover_temp_file(tmp_path):
    folder = tmp_path / "a"
    folder.mkdir(mode=0o755)
    path = folder / "config.json"
    tmp = folder / "config.json.tmp"
    tmp.write_text("old")
    os.chmod(tmp, 0o666)

    config.save_config({"fov": 61}, str(path))

    assert json.loads(path.read_text()) == {"fov": 61}
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(folder).st_mode & 0o777 == 0o700
    assert not tmp.exists()
    assert path.read_text().startswith("{\n    \"fov\"")


def test_saving_where_nothing_can_be_written_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")

    config.save_config({"fov": 1}, str(blocker / "config.json"))


def test_a_folder_that_cannot_be_made_private_is_left_alone(tmp_path, monkeypatch):
    def refuse(*args):
        raise OSError("not yours")

    monkeypatch.setattr(config.os, "chmod", refuse)
    config.make_private_dir(str(tmp_path / "d"))

    assert (tmp_path / "d").is_dir()


def test_a_folder_is_created_private_even_when_chmod_is_refused(tmp_path, monkeypatch):
    def refuse(*args):
        raise OSError("not yours")

    monkeypatch.setattr(config.os, "chmod", refuse)
    config.make_private_dir(str(tmp_path / "d"))

    assert os.stat(tmp_path / "d").st_mode & 0o777 == 0o700


def test_a_settings_file_is_created_private_before_it_is_made_so(tmp_path, monkeypatch):
    monkeypatch.setattr(config.os, "fchmod", lambda *args: None)

    config.save_config({"fov": 61}, str(tmp_path / "config.json"))

    assert os.stat(tmp_path / "config.json").st_mode & 0o777 == 0o600


def test_a_lay_rate_exactly_at_the_tolerance_is_kept(monkeypatch):
    monkeypatch.setattr(config, "LAY_RATE_TOLERANCE", 0.25)

    assert config._valid_lay_rates({MORTAR: 9.0 * 1.25}) == {MORTAR: 11.25}
    assert config._valid_lay_rates({MORTAR: 9.0 * 0.75}) == {MORTAR: 6.75}


def test_a_dropped_lay_rate_does_not_stop_the_ones_after_it():
    rates = config._valid_lay_rates({MORTAR: 99.0, "Other": 3})

    assert rates == {"Other": 3.0}


def test_junk_trim_entries_do_not_stop_the_ones_after_them():
    for junk in ({5: 1.0}, {"": 1.0}, {"Other|optic": 1.0}, {"Other|": 1.0}, {"Other": "x"}):
        assert config._valid_mark_trims({**junk, "AT-4": 0.5}) == {"AT-4": 0.5}


def test_a_trim_key_is_split_at_its_last_bar():
    assert config._valid_mark_trims({"Odd|name|plain": 0.5}) == {"Odd|name": 0.5}
    assert config._valid_mark_trims({"Odd|plain|optic": 0.5}) == {}


def test_a_setting_missing_from_the_file_does_not_stop_the_ones_after_it():
    merged = config._merge({"arc": "high", "map_follow": False})

    assert merged["arc"] == "high"
    assert merged["map_follow"] is False


def test_every_default_setting_is_checked_by_a_branch_of_its_own():
    special = {"hotkeys", "recent_weapons", "lay_rates", "mark_trim", "last_weapon"}
    plain = {
        key: default for key, default in config.DEFAULT_CONFIG.items()
        if key not in special and key not in config.CHOICES
        and not isinstance(default, (bool, int, float))
    }

    assert plain == {}


def test_older_settings_files_are_tried_in_order(tmp_path, monkeypatch):
    unreadable = tmp_path / "unreadable.json"
    unreadable.write_text("{broken")
    older = tmp_path / "older.json"
    older.write_text(json.dumps({"fov": 77}))
    monkeypatch.setattr(config, "legacy_config_paths", lambda: [
        str(tmp_path / "missing.json"), str(unreadable), str(older),
    ])

    cfg, bad = config.read_config(str(tmp_path / "new" / "config.json"))

    assert cfg["fov"] == 77 and bad is None


def test_a_settings_file_is_read_as_utf8_whatever_the_locale(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(json.dumps({"last_weapon": "Mörser"}, ensure_ascii=False).encode("utf-8"))
    assert config._read(str(path))["last_weapon"] == "Mörser"

    script = (
        "import sys, config\n"
        "cfg, bad = config.read_config(sys.argv[1])\n"
        "print(ascii(cfg['last_weapon']), bad)\n"
    )
    environment = {
        **os.environ,
        "PYTHONPATH": os.path.dirname(os.path.abspath(config.__file__)),
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
        "LC_ALL": "C",
    }

    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        env=environment, capture_output=True, text=True, check=True,
        cwd=os.path.dirname(os.path.abspath(config.__file__)),
    )

    assert result.stdout.split() == ["'M\\xf6rser'", "None"]


def test_hotkeys_do_not_stop_the_settings_after_them(monkeypatch):
    defaults = {"hotkeys": {"toggle_overlay": "F8"}, "arc": "auto", "distance_step": 25}
    monkeypatch.setattr(config, "DEFAULT_CONFIG", defaults)

    merged = config._merge({"hotkeys": {"toggle_overlay": "F5"}, "arc": "high"})

    assert merged == {"hotkeys": {"toggle_overlay": "F5"}, "arc": "high", "distance_step": 25}
