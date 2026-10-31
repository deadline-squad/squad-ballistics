"""The user's settings: defaults, where they are stored, and loading that
never fails.

Settings live in `$XDG_CONFIG_HOME/SquadBallistics/config.json` (see
`config_dir`). `read_config` merges the file over `DEFAULT_CONFIG` setting
by setting: a value of the wrong type, out of `CHOICES`, not finite, or a
fraction for a whole-number setting falls back to its default alone, and
an unreadable file is kept as `config.json.bad` instead of being replaced
silently. `save_config` writes atomically, durably and privately (mode
0600 in a 0700 folder).
"""

import copy
import functools
import json
import math
import os

from ballistics import WeaponDataError, clamp_trim, current_weapon_name, load_weapons
from utils import resource_path

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

    # Metres above the target ground the overlay mark is laid for (a vehicle's
    # hull, a standing soldier), for weapons aimed with the mark: the in-game
    # map marker sits on the ground. 0 = the ground. Shown on the overlay as
    # "aim +1.5 m". Set the trim with it at 0: the trim is the error of the
    # weapon, not of the aim point.
    "target_height": 0.0,

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
    "target_height": (0.0, 10.0),
}

DISTANCE_STEPS = (1, 5, 10, 25, 50, 100)

# A calibrated hold rate (`lay_rates`) is kept only within this fraction of
# weapons.json's: the auto-lay calibration refuses a fit outside it (a typo
# in the mils would give an absurd one), so a saved rate outside it was
# written by hand or by a broken file, and would hold S for hours.
LAY_RATE_TOLERANCE = 0.3

# Numeric settings that take a fraction; every other number is a whole one
# (slider positions, pixels, an index), so a saved fraction there is junk.
FRACTIONAL_SETTINGS = ("fov", "target_height")

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


def state_dir():
    """Per-user folder for data that must survive cache cleaners: the
    embedded map's cookies and localStorage ($XDG_DATA_HOME/SquadBallistics,
    https://specifications.freedesktop.org/basedir-spec/latest/)."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
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


@functools.lru_cache(maxsize=1)
def file_weapons():
    """The weapons of weapons.json; empty when the file cannot be read,
    which the app reports on its own."""
    try:
        return load_weapons(resource_path("weapons.json"))
    except (OSError, WeaponDataError):
        return {}


def file_hold_rates():
    """{weapon name: hold rate} of the weapons in weapons.json laid by
    holding a key (`lay_rates` replaces these)."""
    return {
        name: weapon.hold_rate
        for name, weapon in file_weapons().items()
        if weapon.has_hold and weapon.aim == "elevation"
    }


def plain_view_name(name):
    """The entry of the normal view (RMB not held) of weapon `name`: the
    "· no optic" twin of an RMB sight, else `name` itself."""
    weapon = file_weapons().get(name)

    return weapon.twin if weapon is not None and weapon.twin else name


def _valid_lay_rates(loaded):
    """The usable entries of a saved `lay_rates`: {weapon name: positive
    finite rate}, renamed weapons under their current name. The rate of a
    weapon of weapons.json is dropped (back to the file's) when it is more
    than LAY_RATE_TOLERANCE off the file's rate; other names are kept as
    they are, they change nothing."""
    base_rates = file_hold_rates()
    rates = {}

    for name, rate in loaded.items():
        rate = finite_number(rate)

        if not isinstance(name, str) or rate is None or rate <= 0:
            continue

        name = current_weapon_name(name)
        base = base_rates.get(name)

        if base and abs(rate - base) > LAY_RATE_TOLERANCE * base:
            continue

        rates[name] = rate

    return rates


def _valid_mark_trims(loaded):
    """The usable entries of a saved `mark_trim`: {weapon name: degrees},
    a finite number (clamped), not zero. Anything else is dropped.

    Versions with a view switch kept one trim per weapon and view, under
    "<weapon name>|plain", "|optic" or "|optic2". The plain (unzoomed) one
    becomes the trim of the weapon's plain view: the "· no optic" twin of an
    RMB sight (the plain name now means the sight's optic), else the weapon
    itself; the others are dropped.
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
            name = current_weapon_name(name)

            if bar:
                name = plain_view_name(name)

            trims[name] = trim

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


def _unbind_clashing_new_hotkeys(hotkeys, saved):
    """Unbind an action the `saved` hotkeys predate when its default key
    is one the saved ones already use.

    A file of an older version lacks the newer actions (1.2.0 has no
    "auto_hold", F7 by default); one with F7 bound to another action would
    otherwise leave auto_hold unbound with F7 still shown as its key. The
    newer action is left without a key, so Settings shows it free to bind.
    `hotkeys` (merged) is changed in place.
    """
    used = {key for action, key in hotkeys.items() if action in saved and key}

    for action, key in hotkeys.items():
        if action not in saved and key in used:
            hotkeys[action] = ""


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

                _unbind_clashing_new_hotkeys(config[key], value)
            continue

        if key == "recent_weapons":
            if isinstance(value, list):
                config[key] = [current_weapon_name(v) for v in value if isinstance(v, str)][:5]
            continue

        if key == "lay_rates":
            if isinstance(value, dict):
                config[key] = _valid_lay_rates(value)
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


def make_private_dir(path):
    """Create the folder `path` readable by the owner only (0700), and make
    one an older version created readable by others (0755) private.

    Raises OSError when it cannot be created; a mode that cannot be changed
    (a folder of another user) is left as it is.
    """
    os.makedirs(path, mode=0o700, exist_ok=True)

    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def save_config(config, path=None):
    """Write `config` as JSON, readable by the owner only.

    The folder is made private (`make_private_dir`) and the file written to
    a 0600 temp file that replaces the old one, so a settings file saved
    world-readable by an older version is replaced by a private one. The
    temp file reaches the disk before it replaces the old one: a power loss
    right after the save leaves the old or the new settings, never an
    empty file.
    """
    path = path or CONFIG_PATH

    try:
        make_private_dir(os.path.dirname(path))

        tmp = path + ".tmp"

        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

        # A leftover temp file keeps its old mode through O_CREAT.
        os.fchmod(descriptor, 0o600)

        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, path)
    except OSError:
        # Never crash the UI because the config could not be written.
        pass
