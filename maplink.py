"""Targets from SquadCalc: distance, height difference and bearing.

The calculator takes the target geometry from the SquadCalc map and solves it
itself, so the map only needs the weapon and target markers. The Deadline
SquadCalc build also tells which weapon is selected there, by its name in
weapons.json (null when the weapon has no counterpart here); the calculator
then switches to it. Two channels deliver the targets:

* Embedded map. The Deadline SquadCalc build exposes
  `window.squadBallistics.targets()` and `.weapon()`, which
  `webmap.MapPage` polls (see `BRIDGE_SCRIPT`); `parse_bridge` reads the
  result. The other way, `.selectWeapon(name)` (bridge version 3) selects
  the weapon picked here on the map (see `select_weapon_script`), so its
  fire coverage and popups are for the same weapon. Since bridge version 4
  each target also carries the heights of the terrain and the buildings on
  the line from the weapon to it (`MapTarget.profile`), so a trajectory that
  hits a ridge or a roof first is detected (`ballistics.first_obstacle`).
* Relay. A SquadCalc page open anywhere (another PC, a phone) with
  "Link the overlay" enabled sends its targets to the relay of that build
  (`ags17_relay.py` on the SquadCalc host) under a session code. `RelayLink`
  joins the session as an overlay; `parse_relay_text` reads the text.

Relay text, one line per target (the SquadMortarOverlay format plus the
height; older pages omit it), then the selected weapon when it has a name
here (older pages omit it; it has no "|", so target readers skip it):

    "<elevation> | <bearing>° | <distance>m[ | <height>m]"
    "weapon: <name>"
"""

import json
import math
import random
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from PyQt6.QtCore import (
    QObject,
    QTimer,
    QUrl,
    pyqtSignal
)

# Relay of the Deadline SquadCalc build (same host as webmap's map).
DEFAULT_RELAY = "wss://calc.tk104.duckdns.org"

CODE_PATTERN = re.compile(r"[A-Z0-9]{6,16}")

# Reconnect after the first failure, doubling up to the maximum (±20 %).
RECONNECT_DELAY_MS = 5000
MAX_RECONNECT_DELAY_MS = 60000

# Liveness: a ping while connected; no pong in time (or a handshake that
# never ends) means a dead connection, which is dropped and reconnected.
PING_INTERVAL_MS = 20000
PONG_TIMEOUT_MS = 10000
CONNECT_TIMEOUT_MS = 15000

# Targets outside these limits are rejected: the data comes from anyone who
# knows the session code, and absurd numbers overflow the ballistics.
MAX_DISTANCE = 10000
MAX_HEIGHT = 3000

# Profile heights are at least this far apart (a finer profile from a hostile
# page would only cost memory and time), in metres.
MIN_PROFILE_STEP = 0.5

# Weapon names longer than this are not weapons.json names (see MAX_DISTANCE).
MAX_WEAPON_NAME = 200

WEAPON_PREFIX = "weapon:"

# Script polled on the embedded page: {targets, weapon}, or null on SquadCalc
# builds without the bridge. Builds before the weapon export give no weapon.
BRIDGE_SCRIPT = (
    "(function (bridge) {"
    " if (!bridge || typeof bridge.targets !== 'function') return null;"
    " return {targets: bridge.targets(), weapon: typeof bridge.weapon"
    " === 'function' ? bridge.weapon() : null};"
    "})(window.squadBallistics)"
)


@dataclass(frozen=True)
class MapTarget:
    """One target of the SquadCalc map, relative to the first weapon marker.

    distance -- horizontal distance in metres
    height   -- target ground minus (weapon ground + the weapon marker's
                height padding) in metres, as SquadCalc computes it; the
                muzzle height is not included. None if unknown
    bearing  -- degrees from north in [0, 360), None if unknown
    profile  -- heights of the terrain and buildings every `profile_step`
                metres from the weapon (index 0) to the target, relative to
                the weapon like `height`; None if unknown
    profile_step -- metres between two profile heights, None without profile
    """

    distance: float
    height: Optional[float] = None
    bearing: Optional[float] = None
    profile: Optional[Tuple[float, ...]] = None
    profile_step: Optional[float] = None


def _number(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def parse_profile(value, distance):
    """(heights, step) of a bridge target's profile, (None, None) if unusable.

    `value` is {"step": metres, "heights": [...]} from SquadCalc; the heights
    must cover the distance to the target (one per step, up to one step
    short of it) and each be a number within MAX_HEIGHT.
    """
    if not isinstance(value, dict):
        return None, None

    step = _number(value.get("step"))
    heights = value.get("heights")

    if step is None or not MIN_PROFILE_STEP <= step <= distance:
        return None, None

    if not isinstance(heights, list) \
            or not distance / step <= len(heights) <= distance / step + 2:
        return None, None

    numbers = tuple(_number(h) if not isinstance(h, bool) else None for h in heights)

    if any(h is None or abs(h) > MAX_HEIGHT for h in numbers):
        return None, None

    return numbers, step


def make_target(distance, height=None, bearing=None, profile=None):
    """MapTarget from raw numbers, None when the distance is unusable.

    The distance must be in (0, MAX_DISTANCE]; a height beyond MAX_HEIGHT
    becomes unknown and the bearing is wrapped to [0, 360). `profile` is the
    bridge's raw profile (see parse_profile); an unusable one is dropped.
    """
    distance, height, bearing = _number(distance), _number(height), _number(bearing)

    if distance is None or not 0 < distance <= MAX_DISTANCE:
        return None

    if height is not None and abs(height) > MAX_HEIGHT:
        height = None

    if bearing is not None:
        bearing %= 360

    heights, step = parse_profile(profile, distance)

    return MapTarget(distance, height, bearing, heights, step)


def parse_target_lines(text):
    """Targets from relay text; lines without a usable distance are skipped."""
    targets = []

    for line in str(text).splitlines():
        parts = [part.strip() for part in line.split("|")]

        if len(parts) < 3:
            continue

        target = make_target(
            parts[2].removesuffix("m"),
            parts[3].removesuffix("m") if len(parts) > 3 else None,
            parts[1].rstrip("°")
        )

        if target is not None:
            targets.append(target)

    return targets


def parse_bridge_targets(value):
    """Targets from `window.squadBallistics.targets()`.

    The page returns a list of {"distance", "heightDiff", "bearing",
    "profile"} (profile since bridge version 4); None means the page has no
    bridge. Invalid entries are skipped.
    """
    if not isinstance(value, list):
        return []

    targets = []

    for item in value:
        if not isinstance(item, dict):
            continue

        target = make_target(
            item.get("distance"),
            item.get("heightDiff"),
            item.get("bearing"),
            item.get("profile")
        )

        if target is not None:
            targets.append(target)

    return targets


def select_weapon_script(name):
    """Script selecting weapon `name` on the embedded SquadCalc page.

    Evaluates to whether the page knows the weapon; null on builds without
    `selectWeapon`.
    """
    return (
        "(function (bridge) {"
        " if (!bridge || typeof bridge.selectWeapon !== 'function') return null;"
        f" return bridge.selectWeapon({json.dumps(name)});"
        "})(window.squadBallistics)"
    )


def parse_weapon_name(value):
    """A weapon name sent by SquadCalc, None if missing or unusable."""
    if not isinstance(value, str):
        return None

    name = value.strip()

    if not name or len(name) > MAX_WEAPON_NAME:
        return None

    return name


def parse_bridge(value):
    """(targets, weapon) from the result of `BRIDGE_SCRIPT`.

    None means the page has no bridge. `weapon` is None when the page does
    not tell it (older build, or a weapon without a name here).
    """
    if not isinstance(value, dict):
        return None

    return (
        parse_bridge_targets(value.get("targets")),
        parse_weapon_name(value.get("weapon"))
    )


def parse_relay_text(text):
    """(targets, weapon) from the text a SquadCalc page sent to the relay."""
    weapon = None

    for line in str(text).splitlines():
        if line.startswith(WEAPON_PREFIX):
            weapon = parse_weapon_name(line[len(WEAPON_PREFIX):])

    return parse_target_lines(text), weapon


def normalize_code(text):
    """Session code as the relay expects it ("abcd-2345" -> "ABCD2345")."""
    code = re.sub(r"[\s-]", "", str(text)).upper()

    return code if CODE_PATTERN.fullmatch(code) else None


def relay_url(base, code):
    """Overlay address of session `code` on the relay at `base` (ws/wss)."""
    return f"{base}/relay/{code}?role=overlay"


class RelayLink(QObject):
    """Joins a SquadCalc relay session as an overlay and reports its targets.

    `status` is one of "off", "connecting", "waiting" (connected, no
    SquadCalc page in the session) or "connected". While a code is set the
    link keeps itself alive: it reconnects after a failure (5 s, doubling up
    to a minute, with jitter so clients do not retry in sync), pings the
    relay every 20 s and drops a connection that stops answering or never
    finishes its handshake. A target list or weapon equal to the last one
    delivered (the relay repeats them on every reconnect) is not emitted
    again.
    """

    targets_received = pyqtSignal(list)

    # Name of the weapon selected in SquadCalc (see parse_relay_text).
    weapon_received = pyqtSignal(str)

    status_changed = pyqtSignal(str)

    def __init__(self, base=DEFAULT_RELAY, parent=None):
        super().__init__(parent)

        self.base = base
        self.code = None
        self.status = "off"
        self.socket = None
        self.last_targets = None
        self.last_weapon = None
        self.reconnect_delay = RECONNECT_DELAY_MS

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self.connect_relay)

        self.ping_timer = QTimer(self)
        self.ping_timer.setInterval(PING_INTERVAL_MS)
        self.ping_timer.timeout.connect(self.send_ping)

        # Running while waiting for a handshake or a pong; firing = dead.
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.drop_connection)

    def set_code(self, code):
        """Join the session `code` (already normalized); None disconnects."""
        if code == self.code:
            return

        self.code = code

        self.disconnect_relay()

        self.last_targets = None
        self.last_weapon = None
        self.reconnect_delay = RECONNECT_DELAY_MS

        if code:
            self.connect_relay()

    def connect_relay(self):
        if not self.code or self.socket is not None:
            return

        from PyQt6.QtWebSockets import QWebSocket

        socket = QWebSocket()

        socket.connected.connect(lambda: self.on_connected(socket))
        socket.disconnected.connect(lambda: self.on_disconnected(socket))
        socket.pong.connect(lambda *_args: self.watchdog.stop())
        socket.textMessageReceived.connect(self.on_message)

        self.socket = socket

        self.set_status("connecting")

        self.watchdog.start(CONNECT_TIMEOUT_MS)

        socket.open(QUrl(relay_url(self.base, self.code)))

    def disconnect_relay(self):
        self.reconnect_timer.stop()
        self.ping_timer.stop()
        self.watchdog.stop()

        socket, self.socket = self.socket, None

        if socket is not None:
            socket.close()
            socket.deleteLater()

        self.set_status("off")

    def on_connected(self, socket):
        if socket is not self.socket:
            return

        self.watchdog.stop()

        self.reconnect_delay = RECONNECT_DELAY_MS

        self.ping_timer.start()

        self.set_status("waiting")

    def send_ping(self):
        if self.socket is None:
            return

        self.socket.ping()

        if not self.watchdog.isActive():
            self.watchdog.start(PONG_TIMEOUT_MS)

    def drop_connection(self):
        """No handshake or pong in time: abort, which reconnects."""
        if self.socket is not None:
            # abort() emits disconnected -> on_disconnected.
            self.socket.abort()

    def on_disconnected(self, socket):
        # A replaced socket closing late must not touch the new one.
        if socket is not self.socket:
            return

        self.socket = None

        self.ping_timer.stop()
        self.watchdog.stop()

        socket.deleteLater()

        self.set_status("connecting")

        jitter = random.uniform(0.8, 1.2)

        self.reconnect_timer.start(int(self.reconnect_delay * jitter))

        self.reconnect_delay = min(
            self.reconnect_delay * 2, MAX_RECONNECT_DELAY_MS
        )

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
            targets, weapon = parse_relay_text(message.get("text", ""))

            # The weapon first: the targets are then solved for it.
            if weapon is not None and weapon != self.last_weapon:
                self.last_weapon = weapon
                self.weapon_received.emit(weapon)

            if targets == self.last_targets:
                return

            self.last_targets = targets

            self.targets_received.emit(targets)

    def set_status(self, status):
        if status == self.status:
            return

        self.status = status

        self.status_changed.emit(status)
