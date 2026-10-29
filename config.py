import copy
import json
import os

from ballistics import current_weapon_name

APP_NAME = "SquadBallistics"
APP_VERSION = "1.6.0"

# Versions up to 1.1.0 kept "configs/config.json" relative to the working
# directory. It is read once from there and migrated to the per-user
# location below.
LEGACY_CONFIG_PATH = os.path.join("configs", "config.json")


def legacy_config_paths():
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
    "sight_view": "optic",

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


def is_rgb(value):
    """Whether `value` is a colour as older versions stored it: [r, g, b]."""
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in value)
    )


def nearest_mark_color(rgb):
    """The name of the MARK_COLORS entry closest to `rgb`, by RGB distance."""
    return min(
        MARK_COLORS,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(MARK_COLORS[name], rgb))
    )


def _merge(loaded):
    """Fill missing keys with defaults and drop values of the wrong type."""
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
                    current_weapon_name(name): float(rate)
                    for name, rate in value.items()
                    if isinstance(name, str)
                    and isinstance(rate, (int, float))
                    and not isinstance(rate, bool)
                    and rate > 0
                }
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
