"""Run by test_overlay_x11.py on a real X server with a compositor
(xcompmgr, pid in $SB_COMPOSITOR_PID): shows the overlay over a white
window, kills the compositor, starts a new one, and prints as one JSON line
what the screen and the overlay show at each step.

    DISPLAY=:N QT_QPA_PLATFORM=xcb SB_COMPOSITOR_PID=... python tests/compositor_loss_probe.py
"""

import copy
import json
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

import config  # noqa: E402
from overlay import Overlay, compositing_active  # noqa: E402


def settle(app, seconds, done=lambda: False):
    """Run the event loop for `seconds`, or until `done()`."""
    end = time.monotonic() + seconds
    while time.monotonic() < end and not done():
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def pixel(screen, x, y):
    """The colour on the screen (the X server's framebuffer) at (x, y)."""
    return screen.grabWindow(0).toImage().pixelColor(x, y).name()


def main():
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.geometry()

    background = QWidget()
    background.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    background.setStyleSheet("background: white")
    background.setGeometry(size)
    background.show()
    settle(app, 0.5)

    centre = (size.width() // 2, size.height() // 2)
    # Left of the centre, clear of the mark, the ladder and a dialog.
    probe = (100, size.height() // 2)

    settings = copy.deepcopy(config.DEFAULT_CONFIG)
    overlay = Overlay(settings)
    settle(app, 1.0)

    def warning_visible():
        warning = overlay.compositor_warning
        return warning is not None and warning.isVisible()

    result = {
        "watching": overlay.compositor_watch is not None,
        "visible_before": overlay.isVisible(),
        "shown_with": pixel(screen, *probe),
    }

    os.kill(int(os.environ["SB_COMPOSITOR_PID"]), signal.SIGTERM)
    settle(app, 2.0)

    result.update(
        compositing_after=compositing_active(),
        after_loss=pixel(screen, *probe),
        overlay_visible_after=overlay.isVisible(),
        warning_after=warning_visible(),
    )

    compositor = subprocess.Popen(["xcompmgr"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        settle(app, 10.0, overlay.isVisible)
        settle(app, 1.0)

        result.update(
            overlay_visible_back=overlay.isVisible(),
            warning_back=warning_visible(),
            probe_back=pixel(screen, *probe),
            centre_back=pixel(screen, *centre),
        )
    finally:
        overlay.close()
        compositor.terminate()
        compositor.wait(10)

    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
