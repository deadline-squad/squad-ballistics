import json

import pytest

from maplink import (
    MapTarget,
    normalize_code,
    parse_bridge_targets,
    parse_target_lines,
    relay_url,
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


@pytest.mark.parametrize("text, code", [
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
    link.targets_received.connect(received.append)
    link.status_changed.connect(statuses.append)

    link.on_message(json.dumps({"type": "peers", "pages": 1, "overlays": 1}))
    link.on_message(json.dumps({"type": "targets", "text": "1s | 90° | 700m | -3m"}))
    link.on_message("not json")
    link.on_message("[1, 2]")
    link.on_message(json.dumps({"type": "peers", "pages": 0, "overlays": 1}))

    assert received == [[MapTarget(700.0, -3.0, 90.0)]]
    assert statuses == ["connected", "waiting"]


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
