"""Test setup shared by every test module.

The tests never touch the developer's files or the network:

* $XDG_CONFIG_HOME, $XDG_CACHE_HOME and $XDG_DATA_HOME point into a
  temporary folder before any app module is imported, so
  `config.CONFIG_PATH`, `crash.log`, the instance lock and the map's
  WebEngine profile (cookies, tile cache) live there, not in ~/.config,
  ~/.cache and ~/.local/share.
* The map's WebEngine profile refuses every http(s) request
  (`BlockedRequests`): pages load the live SquadCalc only in name, so a
  test still sees which URL was asked for (`requestedUrl()`) without the
  test run depending on, or loading, the live site.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Containers often run tests as root, where Chromium refuses its sandbox.
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

USER_DIRS = tempfile.mkdtemp(prefix="sb-tests-home-")

os.environ["XDG_CONFIG_HOME"] = os.path.join(USER_DIRS, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(USER_DIRS, "cache")
os.environ["XDG_DATA_HOME"] = os.path.join(USER_DIRS, "data")

atexit.register(shutil.rmtree, USER_DIRS, True)

try:
    # Like app.py: QtWebEngine must be imported before QApplication exists.
    import PyQt6.QtWebEngineWidgets  # noqa: F401,E402
except ImportError:
    pass

import pytest  # noqa: E402

_APP = []

# Every http(s) URL the WebEngine profile refused during the run.
BLOCKED_URLS = []


def _block_network(profile):
    """Make `profile` refuse every http(s) request, recording its URL."""
    from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

    class BlockedRequests(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            url = info.requestUrl()

            if url.scheme() in ("http", "https", "ws", "wss"):
                BLOCKED_URLS.append(url.toString())
                info.block(True)

    interceptor = BlockedRequests(profile)

    profile.setUrlRequestInterceptor(interceptor)

    # Python must keep the interceptor: the profile does not own it.
    profile._test_interceptor = interceptor


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """One QApplication for the whole test run, like the real app.

    Destroying it between test modules would tear down QtWebEngine while
    its profile is still alive.
    """
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        yield None
        return

    if not _APP:
        _APP.append(
            QApplication.instance()
            or QApplication(["squad-ballistics-tests"])
        )

        try:
            import webmap

            _block_network(webmap.shared_profile())
        except ImportError:
            pass

    yield _APP[0]


@pytest.fixture
def xvfb_display(tmp_path):
    """A private Xvfb server (1280x720, 24 bit) for one test: its DISPLAY
    string. Xvfb picks a free display number itself (-displayfd)."""
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb is not installed")

    read_end, write_end = os.pipe()

    server = subprocess.Popen(
        ["Xvfb", "-displayfd", str(write_end), "-screen", "0", "1280x720x24",
         "-nolisten", "tcp"],
        pass_fds=(write_end,),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    os.close(write_end)

    try:
        with os.fdopen(read_end) as pipe:
            number = pipe.readline().strip()

        if not number:
            pytest.fail("Xvfb did not start")

        yield ":" + number
    finally:
        server.terminate()
        server.wait(10)
