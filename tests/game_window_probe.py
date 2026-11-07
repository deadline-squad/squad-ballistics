"""Run by test_gamewindow.py on a real X server: opens the overlay (Qt's
xcb platform), then puts a stand-in for the game's window on the server,
moves it, resizes it and closes it, and prints as one JSON line the
geometry the overlay had after each step.

    DISPLAY=:N QT_QPA_PLATFORM=xcb python tests/game_window_probe.py
"""

import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402
import gamewindow  # noqa: E402
from overlay import Overlay  # noqa: E402
from xclient import XClient  # noqa: E402


def settle(app, seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def rect(overlay):
    geometry = overlay.geometry()

    return [geometry.x(), geometry.y(), geometry.width(), geometry.height()]


def main():
    app = QApplication(sys.argv)
    gamewindow.POLL_MS = 50
    overlay = Overlay(copy.deepcopy(config.DEFAULT_CONFIG))
    changes = []
    overlay.screen_changed.connect(lambda: changes.append(rect(overlay)))
    settle(app)

    seen = {"watching": overlay.game_window_watch is not None, "start": rect(overlay)}

    client = XClient()
    game = client.create(100, 50, 960, 540, wm_class="steam_app_393380", title="SquadGame")
    settle(app)
    seen["found"] = rect(overlay)

    client.move_resize(game, 200, 80, 640, 360)
    settle(app)
    seen["moved"] = rect(overlay)

    client.destroy(game)
    settle(app)
    seen["destroyed_before_the_list_changed"] = rect(overlay)

    client.forget(game)
    settle(app)
    seen["closed"] = rect(overlay)
    seen["monitor"] = overlay.config["monitor"]
    seen["changes"] = changes

    client.close()
    overlay.close()
    print(json.dumps(seen), flush=True)


if __name__ == "__main__":
    main()
