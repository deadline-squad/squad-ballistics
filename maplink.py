"""Targets from SquadCalc: distance, height difference and bearing.

The calculator takes the target geometry from the SquadCalc map and solves it
for the weapon picked here, so the map only needs the weapon and target
markers. Two channels deliver the targets:

* Embedded map. The Deadline SquadCalc build exposes
  `window.squadBallistics.targets()`, which `webmap.MapPage` polls (see
  `BRIDGE_SCRIPT`); `parse_bridge_targets` reads its result.
* Relay. A SquadCalc page open anywhere (another PC, a phone) with
  "Link the overlay" enabled sends its targets to the relay of that build
  (`ags17_relay.py` on the SquadCalc host) under a session code. `RelayLink`
  joins the session as an overlay; `parse_target_lines` reads the text.

Relay text, one line per target (the SquadMortarOverlay format plus the
height; older pages omit it):

    "<elevation> | <bearing>° | <distance>m[ | <height>m]"
"""

import json
import math
import re
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import (
    QObject,
    QTimer,
    QUrl,
    pyqtSignal
)

# Relay of the Deadline SquadCalc build (same host as webmap's map).
DEFAULT_RELAY = "wss://calc.tk104.duckdns.org"

CODE_PATTERN = re.compile(r"[A-Z0-9]{6,16}")

RECONNECT_DELAY_MS = 5000

# Script polled on the embedded page; null on SquadCalc builds without it.
BRIDGE_SCRIPT = (
    "window.squadBallistics && typeof window.squadBallistics.targets"
    " === 'function' ? window.squadBallistics.targets() : null"
)


@dataclass(frozen=True)
class MapTarget:
    """One target of the SquadCalc map, relative to the first weapon marker.

    distance -- horizontal distance in metres
    height   -- target ground minus weapon ground in metres, None if unknown
    bearing  -- degrees from north, None if unknown
    """

    distance: float
    height: Optional[float] = None
    bearing: Optional[float] = None


def _number(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def parse_target_lines(text):
    """Targets from relay text; lines without a usable distance are skipped."""
    targets = []

    for line in str(text).splitlines():
        parts = [part.strip() for part in line.split("|")]

        if len(parts) < 3:
            continue

        distance = _number(parts[2].removesuffix("m"))

        if distance is None or distance <= 0:
            continue

        height = _number(parts[3].removesuffix("m")) if len(parts) > 3 else None

        targets.append(
            MapTarget(distance, height, _number(parts[1].rstrip("°")))
        )

    return targets


def parse_bridge_targets(value):
    """Targets from `window.squadBallistics.targets()`.

    The page returns a list of {"distance", "heightDiff", "bearing"}; None
    means the page has no bridge. Invalid entries are skipped.
    """
    if not isinstance(value, list):
        return []

    targets = []

    for item in value:
        if not isinstance(item, dict):
            continue

        distance = _number(item.get("distance"))

        if distance is None or distance <= 0:
            continue

        targets.append(
            MapTarget(
                distance,
                _number(item.get("heightDiff")),
                _number(item.get("bearing"))
            )
        )

    return targets


def normalize_code(text):
    """Session code as the relay expects it ("abcd-2345" -> "ABCD2345")."""
    code = re.sub(r"[\s-]", "", str(text)).upper()

    return code if CODE_PATTERN.fullmatch(code) else None


def relay_url(base, code):
    """Overlay address of session `code` on the relay at `base` (ws/wss)."""
    return f"{base}/relay/{code}?role=overlay"


class RelayLink(QObject):
    """Joins a SquadCalc relay session as an overlay and reports its targets.

    Reconnects every few seconds while a code is set. `status` is one of
    "off", "connecting", "waiting" (connected, no SquadCalc page in the
    session) or "connected".
    """

    targets_received = pyqtSignal(list)
    status_changed = pyqtSignal(str)

    def __init__(self, base=DEFAULT_RELAY, parent=None):
        super().__init__(parent)

        self.base = base
        self.code = None
        self.status = "off"
        self.socket = None

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.setInterval(RECONNECT_DELAY_MS)
        self.reconnect_timer.timeout.connect(self.connect_relay)

    def set_code(self, code):
        """Join the session `code` (already normalized); None disconnects."""
        if code == self.code:
            return

        self.code = code

        self.disconnect_relay()

        if code:
            self.connect_relay()

    def connect_relay(self):
        if not self.code or self.socket is not None:
            return

        from PyQt6.QtWebSockets import QWebSocket

        socket = QWebSocket()

        socket.connected.connect(lambda: self.set_status("waiting"))
        socket.disconnected.connect(lambda: self.on_disconnected(socket))
        socket.textMessageReceived.connect(self.on_message)

        self.socket = socket

        self.set_status("connecting")

        socket.open(QUrl(relay_url(self.base, self.code)))

    def disconnect_relay(self):
        self.reconnect_timer.stop()

        socket, self.socket = self.socket, None

        if socket is not None:
            socket.close()
            socket.deleteLater()

        self.set_status("off")

    def on_disconnected(self, socket):
        # A replaced socket closing late must not touch the new one.
        if socket is not self.socket:
            return

        self.socket = None

        socket.deleteLater()

        self.set_status("connecting")

        self.reconnect_timer.start()

    def on_message(self, raw):
        try:
            message = json.loads(raw)
        except ValueError:
            return

        if not isinstance(message, dict):
            return

        if message.get("type") == "peers":
            pages = message.get("pages")
            self.set_status("connected" if pages else "waiting")
        elif message.get("type") == "targets":
            self.targets_received.emit(
                parse_target_lines(message.get("text", ""))
            )

    def set_status(self, status):
        if status == self.status:
            return

        self.status = status

        self.status_changed.emit(status)
