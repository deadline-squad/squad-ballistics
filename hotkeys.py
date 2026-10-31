"""Hotkeys.

A QShortcut only fires while the Squad Ballistics window has focus, which is
useless while playing. When the physical keys can be read
(`window.key_reader`, see keystate: evdev or X11), they are polled and an
action fires when its key goes down; the game still gets the key. Otherwise
we fall back to a normal window shortcut. The mouse side buttons (Mouse4,
Mouse5) are read the same way and have no such fallback: without readable
keys they do nothing.
"""

import time

from PyQt6.QtCore import (
    Qt,
    QTimer
)

from PyQt6.QtGui import (
    QShortcut,
    QKeySequence
)

from keystate import BTN_EXTRA, BTN_SIDE

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
    "Mouse4": BTN_SIDE,
    "Mouse5": BTN_EXTRA,
}

# The mouse buttons among KEYS: polled like keys, but a window shortcut
# cannot be bound to them.
MOUSE_KEYS = {"Mouse4", "Mouse5"}

# A mouse button fires again only this long (seconds) after it last fired: a
# worn switch chatters, and a toggle must not flip twice for one click.
MOUSE_DEBOUNCE_SECONDS = 0.15

# Actions in UI order; each is a MainWindow method name.
ACTIONS = [
    "toggle_overlay",
    "reset_offset",
    "distance_up",
    "distance_down",
    "auto_hold",
    "toggle_view",
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


def _start_polling(window, items, reader, clock=time.monotonic):
    """Fire each action when its key goes down (edge, no auto-repeat). A mouse
    button that goes down again within MOUSE_DEBOUNCE_SECONDS of firing is a
    bounce and does not fire; `clock()` is the time in seconds."""
    was_down = {key: False for key, _action in items}
    last_fired = {}

    def poll():
        for key, action in items:
            down = reader(KEYS[key])

            fire = down and not was_down[key]

            if fire and key in MOUSE_KEYS:
                now = clock()
                fire = now - last_fired.get(key, -MOUSE_DEBOUNCE_SECONDS) >= MOUSE_DEBOUNCE_SECONDS

                if fire:
                    last_fired[key] = now

            # Before the action: one that raises must not fire again on
            # every poll while the key stays down.
            was_down[key] = down

            if fire:
                getattr(window, action)()

    timer = QTimer(window)
    timer.setInterval(POLL_INTERVAL_MS)
    timer.timeout.connect(poll)
    timer.start()

    window._hotkey_poller = timer


def setup_hotkeys(window):
    """Bind the window's hotkeys (`bindings`): polled from the physical keys
    when `window.key_reader` is set, so they work while the game has focus,
    otherwise as application shortcuts of the window. Call `teardown_hotkeys`
    before binding again."""
    items = bindings(window)
    local = items

    reader = getattr(window, "key_reader", None)

    if reader is not None and items:
        _start_polling(window, items, reader)
        local = []

    window._shortcuts = []

    for key, action in local:
        if key in MOUSE_KEYS:
            continue

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
    """Stop the key polling and remove the shortcuts that `setup_hotkeys` made;
    safe to call when nothing is bound."""
    poller = getattr(window, "_hotkey_poller", None)

    if poller is not None:
        poller.stop()
        poller.deleteLater()
        window._hotkey_poller = None

    for shortcut in getattr(window, "_shortcuts", []):
        shortcut.setEnabled(False)
        shortcut.deleteLater()

    window._shortcuts = []
