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
    return [LEGACY_CONFIG_PATH]

DEFAULT_CONFIG = {
    "fov": 90,

    "fps": 60,

    "opacity": 255,

    "color": [0, 255, 0],

    "dot_enabled": True,
    "dot_size": 4,

    "lines_enabled": True,
    "line_length": 14,
    "line_thickness": 2,
    "line_gap": 6,

    "outline_enabled": True,
    "outline_thickness": 1,

    "glow_enabled": True,

    "t_style": False,

    "circle_enabled": False,
    "circle_radius": 20,

    "animated": True,

    # Multiplier for the pixel offset, to fine-tune the overlay if it does
    # not line up perfectly with the game (100 = no correction).
    "offset_scale": 100,

    "last_weapon": "",
    "recent_weapons": [],
    "arc": "auto",
    "sight_view": "optic",

    "outline_color": "white",
    "info_enabled": True,

    # Range ticks under the mark for direct-fire weapons: where a target at
    # each range goes, on flat ground, without typing the distance.
    "range_ladder": True,

    # Overlay placement
    "monitor": 0,
    "center_offset_x": 0,
    "center_offset_y": 0,

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
    # elevation, per weapon and view: "<weapon name>|plain" or "|optic".
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
    "sight_view": ("plain", "optic"),
    "unit_mode": ("auto", "deg", "mil"),
    "outline_color": ("white", "black"),
    "map_render": ("auto", "software"),
    "map_source": ("deadline", "squadcalc"),
}

RANGES = {
    "fov": (1, 179),
    "fps": (10, 240),
    "opacity": (20, 255),
    "dot_size": (1, 20),
    "line_length": (1, 40),
    "line_gap": (0, 30),
    "line_thickness": (1, 10),
    "outline_thickness": (1, 5),
    "circle_radius": (5, 80),
    "offset_scale": (50, 150),
    "monitor": (0, 15),
    "center_offset_x": (-300, 300),
    "center_offset_y": (-300, 300),
    "distance_step": (1, 100),
}

DISTANCE_STEPS = (1, 5, 10, 25, 50, 100)


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


TRIM_VIEWS = ("plain", "optic")


def trim_key(weapon_name, view):
    """The `mark_trim` key of a weapon's view ("plain" or "optic")."""
    return f"{weapon_name}|{view}"


def _valid_mark_trims(loaded):
    """The usable entries of a saved `mark_trim`: a known view, a finite
    number (clamped), not zero. Anything else is dropped."""
    trims = {}

    for key, trim in loaded.items():
        if not isinstance(key, str) or "|" not in key:
            continue

        name, _, view = key.rpartition("|")

        if view not in TRIM_VIEWS or not name:
            continue

        if not isinstance(trim, (int, float)) or isinstance(trim, bool):
            continue

        try:
            trim = float(trim)
        except OverflowError:
            continue

        if not math.isfinite(trim):
            continue

        trim = clamp_trim(trim)

        if trim:
            trims[trim_key(current_weapon_name(name), view)] = trim

    return trims


def _merge(loaded):
    """Fill missing keys with defaults and drop values of the wrong type."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(loaded, dict):
        return config

    for key, default in DEFAULT_CONFIG.items():
        if key not in loaded:
            continue

        value = loaded[key]

        if key == "color":
            if (
                isinstance(value, list)
                and len(value) == 3
                and all(isinstance(c, (int, float)) for c in value)
            ):
                config[key] = [max(0, min(255, int(c))) for c in value]
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
                    current_weapon_name(name): float(rate)
                    for name, rate in value.items()
                    if isinstance(name, str)
                    and isinstance(rate, (int, float))
                    and not isinstance(rate, bool)
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
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                low, high = RANGES.get(key, (-float("inf"), float("inf")))
                config[key] = max(low, min(high, value))
        elif key in CHOICES:
            if value in CHOICES[key]:
                config[key] = value
        elif isinstance(value, type(default)):
            config[key] = value

    if config["distance_step"] not in DISTANCE_STEPS:
        config["distance_step"] = DEFAULT_CONFIG["distance_step"]

    return config


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path=None):
    path = path or CONFIG_PATH

    for candidate in [path] + legacy_config_paths():
        if not os.path.exists(candidate):
            continue

        try:
            config = _merge(_read(candidate))
        except (OSError, ValueError):
            # Corrupted file: fall back to defaults instead of crashing.
            continue

        if candidate != path:
            save_config(config, path)

        return config

    config = copy.deepcopy(DEFAULT_CONFIG)
    save_config(config, path)
    return config


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
