"""Hotkeys.

A QShortcut only fires while the Squad Ballistics window has focus, which is
useless while playing. On Windows the keys are registered system-wide with
RegisterHotKey so they also work in game. Elsewhere, when the physical keys
can be read (`window.key_reader`, see keystate: Linux evdev or X11), they
are polled and an action fires when its key goes down; the game still gets
the key. Otherwise (or if another program already owns the key on Windows)
we fall back to a normal window shortcut.
"""

import sys

from PyQt6.QtCore import (
    Qt,
    QAbstractNativeEventFilter,
    QCoreApplication,
    QTimer
)

from PyQt6.QtGui import (
    QShortcut,
    QKeySequence
)

# Bindable keys: name shown in the UI / used by QKeySequence -> Windows VK.
KEYS = {
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    "Ins": 0x2D,
    "Home": 0x24,
    "End": 0x23,
    "PgUp": 0x21,
    "PgDown": 0x22,
    "Pause": 0x13,
    "ScrollLock": 0x91,
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

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000

# How often polled hotkeys are read (off Windows).
POLL_INTERVAL_MS = 30


class _WindowsHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callbacks):
        super().__init__()

        from ctypes import wintypes

        self._msg_type = wintypes.MSG
        self.callbacks = callbacks

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG"
        ):
            msg = self._msg_type.from_address(int(message))

            if msg.message == WM_HOTKEY:
                callback = self.callbacks.get(msg.wParam)

                if callback:
                    callback()
                    return True, 0

        return False, 0


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


def _register_global(window, items):
    """Register hotkeys system-wide. Returns the bindings that failed."""
    import ctypes

    user32 = ctypes.windll.user32

    callbacks = {}
    failed = []

    for index, (key, action) in enumerate(items, start=1):
        if user32.RegisterHotKey(None, index, MOD_NOREPEAT, KEYS[key]):
            callbacks[index] = getattr(window, action)
        else:
            failed.append((key, action))

    if callbacks:
        event_filter = _WindowsHotkeyFilter(callbacks)

        QCoreApplication.instance().installNativeEventFilter(
            event_filter
        )

        # Keep a reference, otherwise the filter is garbage collected.
        window._hotkey_filter = event_filter
        window._hotkey_ids = list(callbacks)

    return failed


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

    if sys.platform == "win32":
        try:
            local = _register_global(window, items)
        except Exception:
            local = items
    elif reader is not None and items:
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

    ids = getattr(window, "_hotkey_ids", [])

    if not ids or sys.platform != "win32":
        return

    import ctypes

    for hotkey_id in ids:
        ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)

    window._hotkey_ids = []

    event_filter = getattr(window, "_hotkey_filter", None)

    if event_filter is not None:
        QCoreApplication.instance().removeNativeEventFilter(event_filter)
        window._hotkey_filter = None
