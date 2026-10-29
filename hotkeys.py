"""Hotkeys.

A QShortcut only fires while the Squad Ballistics window has focus, which is
useless while playing. When the physical keys can be read
(`window.key_reader`, see keystate: evdev or X11), they are polled and an
action fires when its key goes down; the game still gets the key. Otherwise
we fall back to a normal window shortcut.
"""

from PyQt6.QtCore import (
    Qt,
    QTimer
)

from PyQt6.QtGui import (
    QShortcut,
    QKeySequence
)

# Bindable keys: name shown in the UI / used by QKeySequence -> Linux input
# event code (linux/input-event-codes.h).
KEYS = {
    **{f"F{i}": 58 + i for i in range(1, 11)},
    "F11": 87,
    "F12": 88,
    "Ins": 110,
    "Home": 102,
    "End": 107,
    "PgUp": 104,
    "PgDown": 109,
    "Pause": 119,
    "ScrollLock": 70,
}

# Actions in UI order; each is a MainWindow method name.
ACTIONS = [
    "toggle_overlay",
    "reset_offset",
    "distance_up",
    "distance_down",
    "auto_hold",
]

# Actions bound only while their setting is on: their key stays free for
# the game otherwise.
OPTIONAL_ACTIONS = {"auto_hold": "auto_hold"}

# How often the hotkeys are read.
POLL_INTERVAL_MS = 30


def bindings(window):
    """[(key name, action)] for every bound action."""
    configured = window.config.get("hotkeys", {})

    result = []
    used = set()

    for action in ACTIONS:
        key = configured.get(action, "")

        setting = OPTIONAL_ACTIONS.get(action)

        if setting and not window.config.get(setting):
            continue

        if key in KEYS and key not in used:
            used.add(key)
            result.append((key, action))

    return result


def _start_polling(window, items, reader):
    """Fire each action when its key goes down (edge, no auto-repeat)."""
    was_down = {key: False for key, _action in items}

    def poll():
        for key, action in items:
            down = reader(KEYS[key])

            if down and not was_down[key]:
                getattr(window, action)()

            was_down[key] = down

    timer = QTimer(window)
    timer.setInterval(POLL_INTERVAL_MS)
    timer.timeout.connect(poll)
    timer.start()

    window._hotkey_poller = timer


def setup_hotkeys(window):
    items = bindings(window)
    local = items

    reader = getattr(window, "key_reader", None)

    if reader is not None and items:
        _start_polling(window, items, reader)
        local = []

    window._shortcuts = []

    for key, action in local:
        shortcut = QShortcut(
            QKeySequence(key),
            window
        )

        shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )

        shortcut.activated.connect(
            getattr(window, action)
        )

        window._shortcuts.append(shortcut)


def teardown_hotkeys(window):
    poller = getattr(window, "_hotkey_poller", None)

    if poller is not None:
        poller.stop()
        poller.deleteLater()
        window._hotkey_poller = None

    for shortcut in getattr(window, "_shortcuts", []):
        shortcut.setEnabled(False)
        shortcut.deleteLater()

    window._shortcuts = []
