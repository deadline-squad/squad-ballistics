"""Run by test_overlay_x11.py on a real X server: covers the screen with a
white window, shows the overlay over it with a dot mark and prints, as one
JSON line, what the screen shows before and with the overlay.

    DISPLAY=:N QT_QPA_PLATFORM=xcb python tests/overlay_probe.py
"""

import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

import config  # noqa: E402
from overlay import Overlay, compositing_active  # noqa: E402


def settle(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


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

    before = pixel(screen, *probe)

    settings = copy.deepcopy(config.DEFAULT_CONFIG)
    overlay = Overlay(settings)
    settle(app, 1.0)

    warning = overlay.compositor_warning

    print(json.dumps({
        "platform": app.platformName(),
        "compositing": compositing_active(),
        "before": before,
        "with_overlay": pixel(screen, *probe),
        "centre": pixel(screen, *centre),
        "overlay_visible": overlay.isVisible(),
        "warning_visible": warning is not None and warning.isVisible(),
    }), flush=True)


if __name__ == "__main__":
    main()
