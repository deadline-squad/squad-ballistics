"""The user's settings: defaults, where they are stored, and loading that
never fails.

Settings live in `$XDG_CONFIG_HOME/SquadBallistics/config.json` (see
`config_dir`). `read_config` merges the file over `DEFAULT_CONFIG` setting
by setting: a value of the wrong type, out of `CHOICES`, not finite, or a
fraction for a whole-number setting falls back to its default alone, and
an unreadable file is kept as `config.json.bad` instead of being replaced
silently. `save_config` writes atomically and privately (mode 0600).
"""

import copy
import json
import math
import os

from ballistics import clamp_trim, current_weapon_name

APP_NAME = "SquadBallistics"
APP_VERSION = "1.6.0"

# Versions up to 1.1.0 kept "configs/config.json" relative to the working
# directory. It is read once from there and migrated to the per-user
# location below.
LEGACY_CONFIG_PATH = os.path.join("configs", "config.json")


def legacy_config_paths():
    """Settings files of older versions to migrate from, oldest last."""
    return [LEGACY_CONFIG_PATH]


# The mark's colours (RGB), in the order of the swatches on the Crosshair page.
MARK_COLORS = {
    "white": (255, 255, 255),
    "red": (255, 48, 48),
    "orange": (255, 154, 31),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "blue": (48, 112, 255),
    "magenta": (255, 0, 255),
}

# The shapes the mark can take; overlay.PRESETS gives each one its geometry.
MARK_STYLES = ("dot", "cross", "t", "circle", "cross_dot")

DEFAULT_CONFIG = {
    "fov": 90,

    # The mark: shape, colour (a MARK_COLORS name) and size in percent.
    "mark_style": "cross_dot",
    "color": "green",
    "mark_size": 100,

    # Aligning the mark with the in-game sight: the mark's centre moves by
    # the offsets (px) and its distance from the centre is multiplied by
    # offset_scale (100 = no correction).
    "center_offset_x": 0,
    "center_offset_y": 0,
    "offset_scale": 100,

    "last_weapon": "",
    "recent_weapons": [],
    "arc": "auto",

    "info_enabled": True,

    # Range ticks under the mark for direct-fire weapons: where a target at
    # each range goes, on flat ground, without typing the distance.
    "range_ladder": True,

    # Overlay placement
    "monitor": 0,

    # Interface
    "main_on_top": False,

    # Calculator
    "unit_mode": "auto",
    "auto_calc": True,
    "distance_step": 25,

    # Map page: "software" rendering fixes a black map on some GPUs/drivers;
    # map_external opens SquadCalc in the system browser instead.
    "map_render": "auto",
    "map_external": False,

    # Map source: "deadline" (SquadCalc build with AGS-17 and the target
    # bridge) or "squadcalc" (squadcalc.app). map_follow puts the newest
    # map target into the calculator.
    "map_source": "deadline",
    "map_follow": True,

    # auto_hold lets the app hold S itself (hotkey "auto_hold"); synthetic
    # input may be treated as a macro by the anti-cheat or server rules, so
    # it is off by default.
    "auto_hold": False,

    # Mortars: read the elevation off the sight on the screen (shown on the
    # overlay; the auto-lay then lays on it, see sightlay).
    "sight_reader": True,

    # Mortar auto-lay: hold rate (degrees per second) per weapon, fitted on
    # the mils the sight showed after a lay; replaces weapons.json's.
    "lay_rates": {},

    # Field correction of the overlay mark, in degrees added to the barrel
    # elevation, per weapon: {weapon name: degrees}.
    # Set from one real shot (see ballistics.trim_for_landing).
    "mark_trim": {},

    "hotkeys": {
        "toggle_overlay": "F8",
        "reset_offset": "F9",
        "distance_up": "",
        "distance_down": "",
        "auto_hold": "F7"
    }
}

# Allowed values. RANGES are also the limits of the sliders in the UI.
CHOICES = {
    "arc": ("auto", "low", "high"),
    "unit_mode": ("auto", "deg", "mil"),
    "mark_style": MARK_STYLES,
    "color": tuple(MARK_COLORS),
    "map_render": ("auto", "software"),
    "map_source": ("deadline", "squadcalc"),
}

RANGES = {
    "fov": (1, 179),
    "mark_size": (50, 200),
    "offset_scale": (50, 150),
    "center_offset_x": (-300, 300),
    "center_offset_y": (-300, 300),
    "monitor": (0, 15),
    "distance_step": (1, 100),
}

DISTANCE_STEPS = (1, 5, 10, 25, 50, 100)

# Numeric settings that take a fraction; every other number is a whole one
# (slider positions, pixels, an index), so a saved fraction there is junk.
FRACTIONAL_SETTINGS = ("fov",)

# Suffix of an unreadable settings file kept next to the new one.
BAD_CONFIG_SUFFIX = ".bad"


def config_dir():
    """Per-user settings folder ($XDG_CONFIG_HOME/SquadBallistics)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )

    return os.path.join(base, APP_NAME)


def data_dir():
    """Per-user folder for caches (map tiles), separate from settings."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )

    return os.path.join(base, APP_NAME)


CONFIG_PATH = os.path.join(config_dir(), "config.json")


def finite_number(value):
    """`value` as a float when it is a finite JSON number, else None.

    Booleans are not numbers here, and an integer too big for a float
    (`1e400` written out) is rejected like `Infinity` and `NaN`, which
    Python's json module accepts.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    try:
        number = float(value)
    except OverflowError:
        return None

    return number if math.isfinite(number) else None


def is_rgb(value):
    """Whether `value` is a colour as older versions stored it: [r, g, b],
    three finite numbers."""
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(finite_number(c) is not None for c in value)
    )


def nearest_mark_color(rgb):
    """The name of the MARK_COLORS entry closest to `rgb`, by RGB distance;
    components outside 0..255 count as the nearest end."""
    rgb = [max(0, min(255, c)) for c in rgb]

    return min(
        MARK_COLORS,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(MARK_COLORS[name], rgb))
    )


def _valid_mark_trims(loaded):
    """The usable entries of a saved `mark_trim`: {weapon name: degrees},
    a finite number (clamped), not zero. Anything else is dropped.

    Versions with a view switch kept one trim per weapon and view, under
    "<weapon name>|plain", "|optic" or "|optic2". The plain (unzoomed) one
    becomes the weapon's trim; the others are dropped.
    """
    trims = {}

    for key, trim in loaded.items():
        if not isinstance(key, str) or not key:
            continue

        name, bar, view = key.rpartition("|")

        if bar:
            if view != "plain" or not name:
                continue
        else:
            name = key

        trim = finite_number(trim)

        if trim is None:
            continue

        trim = clamp_trim(trim)

        if trim:
            trims[current_weapon_name(name)] = trim

    return trims


def _valid_number(key, value):
    """`value` for the numeric setting `key` clamped to its range, or None
    when it is not a finite number or is a fraction for a whole-number
    setting."""
    number = finite_number(value)

    if number is None:
        return None

    if key not in FRACTIONAL_SETTINGS:
        if not isinstance(value, int):
            return None

        number = value

    low, high = RANGES.get(key, (-math.inf, math.inf))

    return max(low, min(high, number))


def _merge(loaded):
    """Fill missing keys with defaults and drop values of the wrong type.

    Each setting is checked on its own: a bad value falls back to its
    default and leaves the other settings alone.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(loaded, dict):
        return config

    for key, default in DEFAULT_CONFIG.items():
        if key not in loaded:
            continue

        value = loaded[key]

        if key == "color" and is_rgb(value):
            config[key] = nearest_mark_color(value)
            continue

        if key == "hotkeys":
            if isinstance(value, dict):
                for action in default:
                    if isinstance(value.get(action), str):
                        config[key][action] = value[action]
            continue

        if key == "recent_weapons":
            if isinstance(value, list):
                config[key] = [current_weapon_name(v) for v in value if isinstance(v, str)][:5]
            continue

        if key == "lay_rates":
            if isinstance(value, dict):
                config[key] = {
                    current_weapon_name(name): finite_number(rate)
                    for name, rate in value.items()
                    if isinstance(name, str)
                    and finite_number(rate) is not None
                    and rate > 0
                }
            continue

        if key == "mark_trim":
            if isinstance(value, dict):
                config[key] = _valid_mark_trims(value)
            continue

        if key == "last_weapon":
            if isinstance(value, str):
                config[key] = current_weapon_name(value)
            continue

        if isinstance(default, bool):
            if isinstance(value, bool):
                config[key] = value
        elif isinstance(default, (int, float)):
            number = _valid_number(key, value)

            if number is not None:
                config[key] = number
        elif key in CHOICES:
            if value in CHOICES[key]:
                config[key] = value
        elif isinstance(value, type(default)):
            config[key] = value

    if config["distance_step"] not in DISTANCE_STEPS:
        config["distance_step"] = DEFAULT_CONFIG["distance_step"]

    return config


def _read(path):
    """The settings object in `path`.

    Raises OSError when the file cannot be read and ValueError when it is
    not JSON or not a JSON object.
    """
    with open(path, "r", encoding="utf-8") as f:
        try:
            loaded = json.load(f)
        except RecursionError:
            # Nesting deeper than the parser's recursion limit.
            raise ValueError("nested too deeply")

    if not isinstance(loaded, dict):
        raise ValueError("not a JSON object")

    return loaded


def _keep_bad_file(path):
    """Move the unreadable settings file `path` aside so that the defaults
    do not overwrite it; returns where it is now.

    It becomes `path` + BAD_CONFIG_SUFFIX, replacing an older bad file. When
    it cannot be moved it stays where it is and `path` is returned.
    """
    bad_path = path + BAD_CONFIG_SUFFIX

    try:
        os.replace(path, bad_path)
    except OSError:
        return path

    return bad_path


def read_config(path=None):
    """Load the settings and say whether the settings file was unreadable.

    Returns `(config, bad_path)`. `bad_path` is None when the file was read
    or did not exist. A file that cannot be read or parsed is not replaced
    silently: it is kept as `config.json.bad` (see `_keep_bad_file`) and
    `bad_path` names it, so the app can tell the user that the defaults are
    used. A settings file of an older version (`legacy_config_paths`) is
    migrated when there is no current one.
    """
    path = path or CONFIG_PATH
    bad_path = None

    if os.path.exists(path):
        try:
            return _merge(_read(path)), None
        except (OSError, ValueError):
            bad_path = _keep_bad_file(path)

    for candidate in legacy_config_paths():
        if not os.path.exists(candidate):
            continue

        try:
            config = _merge(_read(candidate))
        except (OSError, ValueError):
            continue

        if bad_path != path:
            save_config(config, path)

        return config, bad_path

    config = copy.deepcopy(DEFAULT_CONFIG)

    if bad_path != path:
        save_config(config, path)

    return config, bad_path


def load_config(path=None):
    """The settings in `path` (default CONFIG_PATH) merged over the defaults;
    see `read_config`."""
    return read_config(path)[0]


def save_config(config, path=None):
    """Write `config` as JSON, readable by the owner only.

    The folder is created with mode 0700 and the file written to a 0600 temp
    file that replaces the old one, so a settings file saved world-readable
    by an older version is replaced by a private one.
    """
    path = path or CONFIG_PATH

    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)

        tmp = path + ".tmp"

        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

        # A leftover temp file keeps its old mode through O_CREAT.
        os.fchmod(descriptor, 0o600)

        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        os.replace(tmp, path)
    except OSError:
        # Never crash the UI because the config could not be written.
        pass
