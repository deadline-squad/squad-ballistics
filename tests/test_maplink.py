import json

import pytest

from maplink import (
    MapTarget,
    make_target,
    normalize_code,
    parse_bridge,
    parse_bridge_targets,
    parse_profile,
    parse_relay_text,
    parse_target_lines,
    parse_weapon_name,
    relay_url,
    select_weapon_script,
)


def test_relay_lines_with_and_without_height():
    text = "1.25s | 123.4° | 1000m | +12m\n---- | 10.0° | 2400m\n710 | 359.9° | 850m"

    assert parse_target_lines(text) == [
        MapTarget(1000.0, 12.0, 123.4),
        MapTarget(2400.0, None, 10.0),
        MapTarget(850.0, None, 359.9),
    ]


@pytest.mark.parametrize("text", [
    "",
    "1.25s | 123.4°",
    "1.25s | 123.4° | NaNm",
    "1.25s | 123.4° | 0m",
    "junk",
    "a | b | -5m",
])
def test_relay_lines_without_distance_are_skipped(text):
    assert parse_target_lines(text) == []


def test_relay_line_with_bad_height_keeps_the_distance():
    assert parse_target_lines("1s | x | 500m | ?m") == [
        MapTarget(500.0, None, None)
    ]


def test_bridge_targets():
    value = [
        {"distance": 812.4, "heightDiff": -7.5, "bearing": 45.0},
        {"distance": 300},
        {"distance": None, "heightDiff": 1},
        {"distance": -1},
        "junk",
    ]

    assert parse_bridge_targets(value) == [
        MapTarget(812.4, -7.5, 45.0),
        MapTarget(300.0, None, None),
    ]

    assert parse_bridge_targets(None) == []
    assert parse_bridge_targets({"distance": 5}) == []


def test_bridge_with_weapon():
    value = {
        "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
        "weapon": "M2A1 .50",
    }

    assert parse_bridge(value) == ([MapTarget(420.0, -6.0, 90.0)], "M2A1 .50")

    # No bridge on the page, a page before the weapon export, no targets.
    assert parse_bridge(None) is None
    assert parse_bridge([{"distance": 300}]) is None
    assert parse_bridge({"targets": [{"distance": 300}]}) == (
        [MapTarget(300.0, None, None)], None
    )
    assert parse_bridge({"targets": None, "weapon": None}) == ([], None)


@pytest.mark.parametrize("value, name", [
    ("RPG-7 · PG-7VR Tandem", "RPG-7 · PG-7VR Tandem"),
    ("  NSV ", "NSV"),
    ("", None),
    ("   ", None),
    (None, None),
    (42, None),
    (["NSV"], None),
    ("x" * 201, None),
])
def test_weapon_names(value, name):
    assert parse_weapon_name(value) == name


def test_select_weapon_script_quotes_the_name():
    name = "RPG-7 · PG-7V HEAT / OG-7V'\"); alert(1); //"
    script = select_weapon_script(name)

    # The name is a single JSON string literal: it cannot end the call.
    argument = script.split("bridge.selectWeapon(", 1)[1].rsplit(");", 1)[0]
    assert json.loads(argument) == name
    assert script.startswith("(function (bridge)")


def test_relay_text_with_weapon_line():
    text = "1.25s | 123.4° | 1000m | +12m\nweapon: AGS-17 · emplacement"

    assert parse_relay_text(text) == (
        [MapTarget(1000.0, 12.0, 123.4)], "AGS-17 · emplacement"
    )
    # The weapon line alone (no targets yet), and an older page without it.
    assert parse_relay_text("weapon: NSV") == ([], "NSV")
    assert parse_relay_text("0.5 | 10° | 300m") == (
        [MapTarget(300.0, None, 10.0)], None
    )
    # Target readers skip the weapon line.
    assert parse_target_lines(text) == [MapTarget(1000.0, 12.0, 123.4)]


def test_untrusted_values_are_bounded():
    # Anyone with the session code can send targets: absurd values must not
    # reach the ballistics (1e200 m overflows it).
    assert parse_target_lines("x | 0° | 1e200m") == []
    assert parse_target_lines("x | 0° | 10001m") == []
    assert parse_target_lines("x | 370° | 10000m | +5000m") == [
        MapTarget(10000.0, None, 10.0)
    ]
    assert parse_bridge_targets([{"distance": 1e308, "heightDiff": 1}]) == []
    assert make_target(500, -2999, -90) == MapTarget(500.0, -2999.0, 270.0)
    assert make_target("nan") is None


@pytest.mark.parametrize("text, code", [
    ("ABCDE", None),
    ("ABCDEFGHJKLMNPQRS", None),
    ("ABCDEF", "ABCDEF"),
    ("abcd-2345", "ABCD2345"),
    (" ABCD 2345 ", "ABCD2345"),
    ("ABC", None),
    ("ABCD-23!5", None),
    ("", None),
])
def test_normalize_code(text, code):
    assert normalize_code(text) == code


def test_relay_url():
    assert relay_url("wss://calc.example", "ABCD2345") == (
        "wss://calc.example/relay/ABCD2345?role=overlay"
    )


def test_relay_messages(qapp):
    from maplink import RelayLink

    link = RelayLink()
    received = []
    statuses = []
    weapons = []
    link.targets_received.connect(received.append)
    link.status_changed.connect(statuses.append)
    link.weapon_received.connect(weapons.append)

    link.on_message(json.dumps({"type": "peers", "pages": 1, "overlays": 1}))
    link.on_message(json.dumps({"type": "targets", "text": "1s | 90° | 700m | -3m"}))
    # The relay repeats the last targets on reconnect; the page resends them
    # when only its own elevation text changes: delivered once.
    link.on_message(json.dumps({"type": "targets", "text": "2s | 90° | 700m | -3m"}))
    link.on_message("not json")
    link.on_message("[1, 2]")
    link.on_message(json.dumps({"type": "peers", "pages": 0, "overlays": 1}))

    assert received == [[MapTarget(700.0, -3.0, 90.0)]]
    assert statuses == ["connected", "waiting"]
    assert weapons == []

    # The weapon is delivered once per change; a page without it keeps it.
    for text in (
        "1s | 90° | 700m | -3m\nweapon: NSV",
        "1s | 90° | 700m | -3m\nweapon: NSV",
        "1s | 90° | 700m | -3m",
        "weapon: AT-4",
    ):
        link.on_message(json.dumps({"type": "targets", "text": text}))

    assert weapons == ["NSV", "AT-4"]
    assert received == [[MapTarget(700.0, -3.0, 90.0)], []]

    # A new session code forgets the last weapon.
    link.connect_relay = lambda: None
    link.set_code("ABCD2345")
    link.on_message(json.dumps({"type": "targets", "text": "weapon: AT-4"}))
    assert weapons == ["NSV", "AT-4", "AT-4"]


def test_relay_link_end_to_end(qapp):
    """RelayLink against a local WebSocket server speaking the relay protocol."""
    pytest.importorskip("PyQt6.QtWebSockets")

    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtNetwork import QHostAddress
    from PyQt6.QtWebSockets import QWebSocketServer

    from maplink import RelayLink

    server = QWebSocketServer(
        "relay", QWebSocketServer.SslMode.NonSecureMode
    )
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 0)

    paths = []
    clients = []

    def on_connection():
        client = server.nextPendingConnection()
        clients.append(client)
        paths.append(client.requestUrl().path() + "?" + client.requestUrl().query())
        client.sendTextMessage(json.dumps({"type": "peers", "pages": 1, "overlays": 1}))
        client.sendTextMessage(json.dumps(
            {"type": "targets", "text": "0.36s | 12.5° | 500m | +4m"}
        ))

    server.newConnection.connect(on_connection)

    link = RelayLink(f"ws://127.0.0.1:{server.serverPort()}")
    received = []

    loop = QEventLoop()
    link.targets_received.connect(lambda targets: (received.append(targets), loop.quit()))
    QTimer.singleShot(5000, loop.quit)

    link.set_code("ABCD2345")
    loop.exec()

    assert paths == ["/relay/ABCD2345?role=overlay"]
    assert received == [[MapTarget(500.0, 4.0, 12.5)]]
    assert link.status == "connected"

    # Dropped by the server: the link goes back to reconnecting.
    loop = QEventLoop()
    link.status_changed.connect(lambda _status: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    clients[0].close()
    loop.exec()

    assert link.status == "connecting"
    assert link.reconnect_timer.isActive()

    link.set_code(None)
    assert link.status == "off"
    assert not link.reconnect_timer.isActive()

    server.close()


def make_server():
    from PyQt6.QtNetwork import QHostAddress
    from PyQt6.QtWebSockets import QWebSocketServer

    server = QWebSocketServer("relay", QWebSocketServer.SslMode.NonSecureMode)
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 0)
    return server


def wait_until(condition, timeout_ms=5000):
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    clock = QElapsedTimer()
    clock.start()
    while not condition() and clock.elapsed() < timeout_ms:
        QCoreApplication.processEvents()
    return condition()


def test_switching_code_keeps_one_connection(qapp):
    pytest.importorskip("PyQt6.QtWebSockets")

    from maplink import RelayLink

    server = make_server()
    clients = []
    server.newConnection.connect(lambda: clients.append(server.nextPendingConnection()))

    link = RelayLink(f"ws://127.0.0.1:{server.serverPort()}")

    link.set_code("AAAAAA")
    assert wait_until(lambda: link.status == "waiting")

    link.set_code("BBBBBB")
    assert wait_until(lambda: link.status == "waiting" and len(clients) == 2)
    assert wait_until(lambda: clients[0].state().name == "UnconnectedState")

    # The first socket closing late did not take the new one down.
    assert link.socket is not None
    assert clients[1].requestUrl().path() == "/relay/BBBBBB"

    link.set_code(None)
    server.close()


def test_refused_connection_backs_off(qapp, monkeypatch):
    pytest.importorskip("PyQt6.QtWebSockets")

    import maplink
    from PyQt6.QtNetwork import QTcpServer, QHostAddress

    probe = QTcpServer()
    probe.listen(QHostAddress.SpecialAddress.LocalHost, 0)
    port = probe.serverPort()
    probe.close()  # nothing listens there now

    monkeypatch.setattr(maplink, "RECONNECT_DELAY_MS", 50)
    monkeypatch.setattr(maplink, "MAX_RECONNECT_DELAY_MS", 200)

    link = maplink.RelayLink(f"ws://127.0.0.1:{port}")
    link.set_code("ABCDEF")

    assert wait_until(lambda: link.reconnect_delay == 200, 5000)
    assert link.status == "connecting"
    assert link.reconnect_timer.isActive() or link.socket is not None

    link.set_code(None)
    assert link.status == "off"
    assert not link.reconnect_timer.isActive()
    assert link.reconnect_delay == 50


def test_silent_server_is_dropped_and_retried(qapp, monkeypatch):
    """A host that accepts TCP but never answers the handshake."""
    pytest.importorskip("PyQt6.QtWebSockets")

    import maplink
    from PyQt6.QtNetwork import QTcpServer, QHostAddress

    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 0)
    accepted = []
    server.newConnection.connect(lambda: accepted.append(server.nextPendingConnection()))

    monkeypatch.setattr(maplink, "CONNECT_TIMEOUT_MS", 200)
    monkeypatch.setattr(maplink, "RECONNECT_DELAY_MS", 50)

    link = maplink.RelayLink(f"ws://127.0.0.1:{server.serverPort()}")
    link.set_code("ABCDEF")

    assert wait_until(lambda: len(accepted) >= 2, 5000)

    link.set_code(None)
    server.close()


def test_missing_pong_drops_the_connection(qapp, monkeypatch):
    pytest.importorskip("PyQt6.QtWebSockets")

    import maplink

    server = make_server()
    clients = []
    server.newConnection.connect(lambda: clients.append(server.nextPendingConnection()))

    monkeypatch.setattr(maplink, "PONG_TIMEOUT_MS", 100)

    link = maplink.RelayLink(f"ws://127.0.0.1:{server.serverPort()}")
    link.set_code("ABCDEF")
    assert wait_until(lambda: link.status == "waiting")

    # A live server answers pings: the watchdog is stopped by the pong.
    link.send_ping()
    assert wait_until(lambda: not link.watchdog.isActive(), 2000)
    assert link.status == "waiting"

    # A dead peer: simulate a pong that never comes.
    link.socket.pong.disconnect()
    link.send_ping()
    assert wait_until(lambda: link.status == "connecting", 2000)
    assert link.reconnect_timer.isActive()

    link.set_code(None)
    server.close()


def test_bridge_target_profile():
    heights = [0.0, 1.5, -2.25, 4.0, 0.0]
    [target] = parse_bridge_targets([
        {"distance": 4.2, "heightDiff": 0, "bearing": 0, "profile": {"step": 1, "heights": heights}},
    ])
    assert target.profile == tuple(heights)
    assert target.profile_step == 1

    # Older pages (bridge version 3) send no profile.
    [target] = parse_bridge_targets([{"distance": 4.2, "heightDiff": 0, "bearing": 0}])
    assert target.profile is None and target.profile_step is None


@pytest.mark.parametrize("profile", [
    None,
    "1,2,3",
    {"step": 1},
    {"step": 1, "heights": "0 0 0 0 0"},
    {"step": 0.1, "heights": [0.0] * 43},          # finer than MIN_PROFILE_STEP
    {"step": 1, "heights": [0.0] * 2},             # does not reach the target
    {"step": 1, "heights": [0.0] * 50},            # far beyond the target
    {"step": 1, "heights": [0, 0, None, 0, 0]},
    {"step": 1, "heights": [0, 0, True, 0, 0]},
    {"step": 1, "heights": [0, 0, "nan", 0, 0]},
    {"step": 1, "heights": [0, 0, 1e9, 0, 0]},     # beyond MAX_HEIGHT
    {"step": float("inf"), "heights": [0, 0, 0, 0, 0]},
])
def test_unusable_profiles_are_dropped(profile):
    assert parse_profile(profile, 4.2) == (None, None)
    [target] = parse_bridge_targets([{"distance": 4.2, "heightDiff": 0, "profile": profile}])
    assert target.distance == 4.2 and target.profile is None


def test_new_session_codes():
    from maplink import CODE_ALPHABET, NEW_CODE_LENGTH, new_session_code

    codes = {new_session_code() for _ in range(200)}

    # 60 bits each: 200 draws never repeat in practice.
    assert len(codes) == 200

    for code in codes:
        assert len(code) == NEW_CODE_LENGTH
        assert set(code) <= set(CODE_ALPHABET)
        # Accepted by the relay as it is.
        assert normalize_code(code) == code


def test_code_format_and_device_link():
    from maplink import DEVICE_LINK_PAGE, device_link, format_code

    assert format_code("ABCDEFGHJKLM") == "ABCD-EFGH-JKLM"
    assert format_code("ABCD2345") == "ABCD-2345"
    assert normalize_code(format_code("ABCDEFGHJKLM")) == "ABCDEFGHJKLM"

    # In the fragment: never sent to the server, so never in its logs.
    assert device_link("ABCDEFGHJKLM") == "https://calc.tk104.duckdns.org/#link=ABCDEFGHJKLM"
    assert device_link("ABCD2345", "http://localhost:3000/") == "http://localhost:3000/#link=ABCD2345"

    from webmap import DEADLINE_SQUADCALC_URL

    assert DEVICE_LINK_PAGE == DEADLINE_SQUADCALC_URL
