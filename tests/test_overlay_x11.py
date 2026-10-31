"""The overlay on a real X server (Xvfb), read back from the screen.

Without a compositing manager a translucent window is drawn opaque: the
overlay would turn the whole game black. The overlay must then stay hidden
and say why; with a compositor (xcompmgr) the game shows through and only
the mark is drawn. A compositor that stops while the overlay is up hides
it, and one that starts again brings it back. CI installs Xvfb and
xcompmgr.
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
LOSS_PROBE = os.path.join(ROOT, "tests", "compositor_loss_probe.py")

WHITE = "#ffffff"
MARK_RED = "#ff3030"


def run_probe(display, probe=PROBE, **environ):
    env = dict(os.environ, DISPLAY=display, QT_QPA_PLATFORM="xcb", **environ)
    result = subprocess.run(
        [sys.executable, probe],
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
    assert seen["centre"] == MARK_RED


def test_compositing_lost_while_shown_hides_the_overlay_and_brings_it_back(xvfb_display):
    """Compositing that stops under a shown overlay (KWin suspends it for
    a fullscreen game) must not leave a black screen."""
    compositor = start_compositor(xvfb_display)

    try:
        seen = run_probe(xvfb_display, LOSS_PROBE, SB_COMPOSITOR_PID=str(compositor.pid))
    finally:
        compositor.terminate()
        compositor.wait(10)

    assert seen["watching"]
    assert seen["visible_before"]
    assert seen["shown_with"] == WHITE

    assert not seen["compositing_after"]
    assert seen["after_loss"] == WHITE
    assert not seen["overlay_visible_after"]
    assert seen["warning_after"]

    assert seen["overlay_visible_back"]
    assert not seen["warning_back"]
    assert seen["probe_back"] == WHITE
    assert seen["centre_back"] == MARK_RED
