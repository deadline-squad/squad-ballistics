"""The game's own display settings, read from its `GameUserSettings.ini`.

The overlay mark depends on the FOV the game renders with, and a wrong one
puts a shot hundreds of metres off, so the app reads it from the game
instead of asking the player to keep a copy of it right.

The game runs through Steam Proton on Linux, so its settings live in the
Wine prefix of Steam app 393380 inside any Steam library:

    <library>/steamapps/compatdata/393380/pfx/drive_c/users/steamuser/
        AppData/Local/SquadGame/Saved/Config/<platform folder>/GameUserSettings.ini

Unreal Engine writes a config property as a `Name=value` line in the section
of its class. The FOV is `SQGameUserSettings::FOV` (read by the vehicle
weapons through `GetSquadGameUserSettings()->FOV`), so it is expected as a
`FOV=<number>` line in a section whose name holds `GameUserSettings`; the
resolution and the window mode are the engine's `ResolutionSizeX`,
`ResolutionSizeY` and `FullscreenMode`. The layout was checked against
documentation and a synthetic file, not against a real file of the game.
"""

import glob
import math
import os
import re
from dataclasses import dataclass

# Steam app id of Squad: the name of its Wine prefix folder.
SQUAD_APP_ID = "393380"

# Where the game's settings are inside a Steam library.
SETTINGS_PATTERN = os.path.join(
    "steamapps", "compatdata", SQUAD_APP_ID, "pfx", "drive_c", "users",
    "steamuser", "AppData", "Local", "SquadGame", "Saved", "Config", "*",
    "GameUserSettings.ini"
)

# Steam's own folders on Linux (the native install, its usual symlink and
# the Flatpak one); each may list more libraries in libraryfolders.vdf.
STEAM_ROOTS = (
    "~/.local/share/Steam",
    "~/.steam/steam",
    "~/.var/app/com.valvesoftware.Steam/.local/share/Steam"
)

# The FOVs (degrees) taken as the game's: the game's slider goes 90-120, and
# a number far outside is a damaged file, not a setting.
GAME_FOV_RANGE = (60.0, 120.0)

# Unreal's EWindowMode values of `FullscreenMode`.
FULLSCREEN = 0
WINDOWED_FULLSCREEN = 1
WINDOWED = 2


@dataclass(frozen=True)
class GameSettings:
    """What the game's settings file says; a value it does not hold, or
    holds in a form that cannot be used, is None.

    `fov` is the horizontal FOV in degrees, `width` and `height` the game's
    resolution in pixels and `window_mode` the engine's EWindowMode number
    (`FULLSCREEN`, `WINDOWED_FULLSCREEN`, `WINDOWED`).
    """

    fov: float | None = None
    width: int | None = None
    height: int | None = None
    window_mode: int | None = None


def steam_roots():
    """The existing Steam folders of this user, without duplicates."""
    roots = []

    for root in STEAM_ROOTS:
        root = os.path.realpath(os.path.expanduser(root))

        if os.path.isdir(root) and root not in roots:
            roots.append(root)

    return roots


def steam_libraries(roots):
    """The Steam library folders under the Steam folders `roots`: the
    folders themselves and those their `libraryfolders.vdf` lists."""
    libraries = []

    for root in roots:
        found = [root]

        try:
            with open(
                os.path.join(root, "steamapps", "libraryfolders.vdf"),
                encoding="utf-8", errors="replace"
            ) as f:
                text = f.read()
        except OSError:
            text = ""

        for path in re.findall(r'"path"\s+"([^"]*)"', text):
            found.append(path.replace("\\\\", "\\"))

        for library in found:
            if library not in libraries and os.path.isdir(library):
                libraries.append(library)

    return libraries


def find_game_settings(roots=None):
    """The path of the game's `GameUserSettings.ini`, or None when there is
    none. `roots` are Steam folders (default `steam_roots()`); when several
    libraries hold one, the most recently written wins."""
    if roots is None:
        roots = steam_roots()

    candidates = [
        path
        for library in steam_libraries(roots)
        for path in glob.glob(os.path.join(glob.escape(library), SETTINGS_PATTERN))
    ]

    try:
        return max(candidates, key=os.path.getmtime, default=None)
    except OSError:
        return None


def _number(text):
    """`text` as a finite number, or None."""
    try:
        value = float(text)
    except ValueError:
        return None

    return value if math.isfinite(value) else None


def _whole(text):
    """`text` as a whole number, or None."""
    value = _number(text)

    return int(value) if value is not None and value == int(value) else None


def read_game_settings(path):
    """The `GameSettings` in the ini file `path`, or None when it cannot be
    read.

    Keys are matched case-insensitively in every section whose name holds
    `GameUserSettings`; when a key repeats, the last line wins, as in the
    engine. A malformed value, or a FOV outside `GAME_FOV_RANGE`, leaves that
    field None and the rest usable.
    """
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None

    values = {}
    in_settings = False

    for line in lines:
        line = line.strip()

        if line.startswith("[") and line.endswith("]"):
            in_settings = "gameusersettings" in line.lower()
        elif in_settings and "=" in line and not line.startswith((";", "#")):
            key, _, value = line.partition("=")
            values[key.strip().lower()] = value.strip()

    fov = _number(values.get("fov", ""))

    if fov is not None and not GAME_FOV_RANGE[0] <= fov <= GAME_FOV_RANGE[1]:
        fov = None

    width = _whole(values.get("resolutionsizex", ""))
    height = _whole(values.get("resolutionsizey", ""))

    if width is None or height is None or width <= 0 or height <= 0:
        width = height = None

    window_mode = _whole(values.get("fullscreenmode", ""))

    if window_mode not in (FULLSCREEN, WINDOWED_FULLSCREEN, WINDOWED):
        window_mode = None

    return GameSettings(fov, width, height, window_mode)


def screen_mismatch(settings, width, height):
    """Whether the game does not fill a `width` x `height` screen, so the
    mark (laid on the screen's size) lands off: the game runs in a window,
    or at another resolution than the screen's. Windowed fullscreen always
    fills the screen, whatever resolution is saved. False when the settings
    say nothing about it."""
    if settings.window_mode == WINDOWED_FULLSCREEN:
        return False

    if settings.window_mode == WINDOWED:
        return True

    if settings.width is None:
        return False

    return (settings.width, settings.height) != (width, height)
