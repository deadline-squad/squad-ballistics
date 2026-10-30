"""The overlay on a real X server (Xvfb), read back from the screen.

Without a compositing manager a translucent window is drawn opaque: the
overlay would turn the whole game black. The overlay must then stay hidden
and say why; with a compositor (xcompmgr) the game shows through and only
the mark is drawn. CI installs Xvfb and xcompmgr.
"""

import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import ROOT

PROBE = os.path.join(ROOT, "tests", "overlay_probe.py")

WHITE = "#ffffff"
MARK_GREEN = "#00ff00"


def run_probe(display):
    env = dict(os.environ, DISPLAY=display, QT_QPA_PLATFORM="xcb")
    result = subprocess.run(
        [sys.executable, PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def start_compositor(display):
    if not shutil.which("xcompmgr"):
        pytest.skip("xcompmgr is not installed")

    compositor = subprocess.Popen(
        ["xcompmgr"],
        env=dict(os.environ, DISPLAY=display),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Running once it owns the compositing selection.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if compositor_running(display):
            return compositor
        time.sleep(0.05)

    compositor.terminate()
    pytest.fail("xcompmgr did not take the _NET_WM_CM_S0 selection")


def compositor_running(display):
    code = "import overlay; print(overlay.x11_compositing_manager_running())"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=dict(os.environ, DISPLAY=display),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout.strip() == "True"


def test_without_a_compositor_the_screen_stays_visible_and_a_warning_shows(xvfb_display):
    assert not compositor_running(xvfb_display)

    seen = run_probe(xvfb_display)

    assert seen["platform"] == "xcb"
    assert not seen["compositing"]
    assert seen["before"] == WHITE
    # Not the black full-screen rectangle an uncomposited overlay draws.
    assert seen["with_overlay"] == WHITE
    assert not seen["overlay_visible"]
    assert seen["warning_visible"]


def test_with_a_compositor_the_overlay_draws_only_the_mark(xvfb_display):
    compositor = start_compositor(xvfb_display)

    try:
        seen = run_probe(xvfb_display)
    finally:
        compositor.terminate()
        compositor.wait(10)

    assert seen["compositing"]
    assert seen["overlay_visible"]
    assert not seen["warning_visible"]
    assert seen["before"] == WHITE
    assert seen["with_overlay"] == WHITE
    assert seen["centre"] == MARK_GREEN
