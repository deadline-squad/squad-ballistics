import errno
import http.server
import json
import os
import threading
import time

import pytest

from PyQt6.QtGui import QColor, QImage

import webmap


def flags_of(text):
    return text.split()


def disabled_features(text):
    for flag in flags_of(text):
        if flag.startswith("--disable-features="):
            return flag.split("=", 1)[1].split(",")
    return []


def test_network_flags_always_on():
    flags = webmap.chromium_flags("auto")

    assert "--disable-quic" in flags_of(flags)
    for feature in ("EncryptedClientHello", "DnsOverHttps", "UseDnsHttpsSvcbAlpn"):
        assert feature in disabled_features(flags)

    assert "--disable-gpu" not in flags_of(flags)


def test_software_mode_disables_gpu():
    flags = flags_of(webmap.chromium_flags("software"))

    assert "--disable-gpu" in flags
    assert "--disable-gpu-compositing" in flags


def test_user_flags_are_kept_and_merged():
    flags = webmap.chromium_flags(
        "auto",
        "--lang=ru --disable-features=Foo,Bar --disable-quic"
    )

    assert flags_of(flags).count("--disable-quic") == 1
    assert "--lang=ru" in flags_of(flags)
    assert disabled_features(flags)[:2] == ["Foo", "Bar"]
    assert sum(f.startswith("--disable-features=") for f in flags_of(flags)) == 1


def test_configure_environment_survives_restarts():
    env = {"QTWEBENGINE_CHROMIUM_FLAGS": "--lang=ru"}

    webmap.configure_environment("software", env)
    assert "--disable-gpu" in env["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert env["QT_QUICK_BACKEND"] == "software"

    # A restarted app inherits the environment; switching back must not
    # keep the software flags from the previous run.
    child = dict(env)
    webmap.configure_environment("auto", child)

    assert "--disable-gpu" not in child["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert "--lang=ru" in child["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert "QT_QUICK_BACKEND" not in child

    # Running it again does not duplicate anything.
    webmap.configure_environment("auto", child)
    assert flags_of(child["QTWEBENGINE_CHROMIUM_FLAGS"]).count("--disable-quic") == 1


def test_user_quick_backend_is_restored():
    env = {"QT_QUICK_BACKEND": "opengl"}

    webmap.configure_environment("software", env)
    assert env["QT_QUICK_BACKEND"] == "software"

    webmap.configure_environment("auto", env)
    assert env["QT_QUICK_BACKEND"] == "opengl"


def image(color, size=(200, 100)):
    img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    return img


def test_looks_black():
    assert webmap.looks_black(image("#000000"))
    assert webmap.looks_black(image("#050505"))
    assert not webmap.looks_black(image("#1a2130"))
    assert not webmap.looks_black(QImage())

    # A dark page with some content (UI, map) is not "black".
    img = image("#000000")
    for x in range(0, 200):
        for y in range(0, 20):
            img.setPixelColor(x, y, QColor("#3b82f6"))
    assert not webmap.looks_black(img)


def test_profile_keeps_tiles_in_the_cache_and_settings_in_the_data_dir():
    """Cache cleaners wipe $XDG_CACHE_HOME: only the tiles live there, the
    cookies and SquadCalc's settings live in $XDG_DATA_HOME (#5, review
    1.6.0 slice 5 claim 12)."""
    pytest.importorskip("PyQt6.QtWebEngineCore")

    from config import data_dir, state_dir

    profile = webmap.shared_profile()

    assert not profile.isOffTheRecord()
    assert profile.cachePath().startswith(data_dir())
    assert profile.persistentStoragePath() == os.path.join(state_dir(), "WebEngine", "Storage")
    assert profile.httpCacheMaximumSize() >= 256 * 1024 * 1024


@pytest.fixture
def user_dirs(tmp_path, monkeypatch):
    """Empty $XDG_CACHE_HOME and $XDG_DATA_HOME: (old storage, new storage)."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    return (
        tmp_path / "cache" / "SquadBallistics" / "WebEngine" / "Storage",
        tmp_path / "data" / "SquadBallistics" / "WebEngine" / "Storage",
    )


def test_old_storage_is_moved_to_the_data_dir_once(user_dirs):
    old, new = user_dirs
    (old / "Local Storage").mkdir(parents=True)
    (old / "Cookies").write_bytes(b"cookie")
    inode = old.stat().st_ino

    assert webmap.persistent_storage_path() == str(new)

    # Moved, not copied: the same folder, nothing left behind.
    assert not old.exists()
    assert new.stat().st_ino == inode
    assert (new / "Cookies").read_bytes() == b"cookie"
    assert (new / "Local Storage").is_dir()

    # Later starts leave it alone, even if an old folder appears again.
    old.mkdir(parents=True)
    assert webmap.persistent_storage_path() == str(new)
    assert old.exists() and (new / "Cookies").exists()


def test_a_fresh_install_starts_in_the_data_dir(user_dirs):
    old, new = user_dirs

    assert webmap.persistent_storage_path() == str(new)
    assert not old.exists() and not new.exists()


def test_storage_that_cannot_be_moved_is_used_where_it_is(user_dirs, monkeypatch):
    """Another file system (EXDEV): nothing is copied, nothing is lost."""
    old, new = user_dirs
    old.mkdir(parents=True)
    (old / "Cookies").write_bytes(b"cookie")

    def cross_device(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(webmap.os, "rename", cross_device)

    assert webmap.persistent_storage_path() == str(old)
    assert (old / "Cookies").read_bytes() == b"cookie"
    assert not new.exists()


def test_shutdown_is_safe_and_idempotent():
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    page = webmap.MapPage({"map_render": "auto"})
    page.ensure_loaded()
    assert page.view is not None

    page.shutdown()
    page.shutdown()
    assert page.view is None and page.profile is None

    # The shared profile is reused, never recreated.
    assert webmap.shared_profile() is webmap.shared_profile()


@pytest.fixture
def opened(monkeypatch):
    """The addresses handed to the system browser."""
    urls = []

    monkeypatch.setattr(
        webmap.QDesktopServices, "openUrl",
        lambda url: urls.append(url.toString()) or True
    )

    return urls


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ssh://host",
    "smb://host/share",
    "javascript:alert(1)",
    "steam://run/1",
    "mailto:a@b.c",
    "no scheme",
    "",
])
def test_only_web_addresses_go_to_the_system(opened, url):
    assert webmap.open_external(url) is False
    assert opened == []


@pytest.mark.parametrize("url", ["https://squadcalc.app/", "http://localhost:3000/x", "HTTPS://Example.org"])
def test_web_addresses_go_to_the_system(opened, url):
    assert webmap.open_external(url) is True
    assert len(opened) == 1


def map_page(qapp):
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineCore import QWebEnginePage

    page = webmap._make_page_classes()(webmap.shared_profile())

    Navigation = QWebEnginePage.NavigationType

    def navigate(url, nav_type=Navigation.NavigationTypeLinkClicked, main=True):
        return page.acceptNavigationRequest(QUrl(url), nav_type, main)

    return page, navigate, Navigation


def test_map_page_does_not_leave_the_map_origin(qapp, opened):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    page, navigate, Navigation = map_page(qapp)

    # The app's own load sets the origin.
    assert navigate("https://calc.example/", Navigation.NavigationTypeTyped)

    # Same origin: links, redirects, form posts and reloads stay in the view.
    assert navigate("https://calc.example/other")
    assert navigate("https://calc.example:443/", Navigation.NavigationTypeRedirect)
    assert navigate("https://CALC.example/", Navigation.NavigationTypeReload)

    # Frames of other hosts (map tiles, embeds) are not navigations away.
    assert navigate("https://tiles.example/", main=False)

    # Another host, or the same host on another scheme or port (an https ->
    # http downgrade; #5, review 1.6.0 slice 5 claim 5): refused.
    assert not navigate("https://evil.example/")
    assert not navigate("http://calc.example/")
    assert not navigate("https://calc.example:8443/")
    assert not navigate("https://evil.example/", Navigation.NavigationTypeRedirect)

    # Without a click on the map, none of them reached the system browser.
    assert opened == []

    # Choosing another map source (the app loads it) moves the origin.
    assert navigate("https://squadcalc.app/", Navigation.NavigationTypeTyped)
    assert navigate("https://squadcalc.app/map")
    assert not navigate("https://calc.example/")


def test_a_click_lets_one_address_out(qapp, opened):
    """One address per user activation, within USER_ACTIVATION_SECONDS; a
    page cannot open the browser on its own (#5, review 1.6.0 slice 5
    claim 1)."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    page, navigate, Navigation = map_page(qapp)
    outcomes = []
    page.external_requested.connect(lambda url, outcome: outcomes.append((url, outcome)))
    now = [100.0]
    page.clock = lambda: now[0]

    assert navigate("https://calc.example/", Navigation.NavigationTypeTyped)

    page.note_user_activation()
    assert not navigate("https://wiki.example/")
    assert not navigate("https://second.example/")
    assert opened == ["https://wiki.example/"]

    # A click long ago does not count.
    page.note_user_activation()
    now[0] += webmap.USER_ACTIVATION_SECONDS + 0.1
    assert not navigate("https://late.example/")

    # Other schemes never reach the system, with a click or not.
    page.note_user_activation()
    assert not navigate("file:///etc/passwd")
    page.note_user_activation()
    assert not navigate("steam://run/1")

    assert opened == ["https://wiki.example/"]
    assert outcomes == [
        ("https://wiki.example/", "opened"),
        ("https://second.example/", "blocked"),
        ("https://late.example/", "blocked"),
        ("file:///etc/passwd", "failed"),
        ("steam://run/1", "failed"),
    ]


class FakeWindowRequest:
    """The QWebEngineNewWindowRequest calls the page makes."""

    def __init__(self, url, user_initiated):
        from PyQt6.QtCore import QUrl

        self.url = QUrl(url)
        self.user_initiated = user_initiated

    def requestedUrl(self):
        return self.url

    def isUserInitiated(self):
        return self.user_initiated


def test_new_windows_open_externally_only_when_the_user_asked(qapp, opened):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

    page = webmap._make_page_classes()(webmap.shared_profile())

    # No window is ever created in the app; scripts cannot open one alone.
    assert page.createWindow(QWebEnginePage.WebWindowType.WebBrowserTab) is None
    assert not page.settings().testAttribute(
        QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows
    )

    # A script's popup: refused even right after a click.
    page.note_user_activation()
    page.on_new_window(FakeWindowRequest("https://ads.example/", False))
    assert opened == []

    page.note_user_activation()
    page.on_new_window(FakeWindowRequest("https://discord.example/", True))
    page.on_new_window(FakeWindowRequest("https://again.example/", True))
    page.note_user_activation()
    page.on_new_window(FakeWindowRequest("file:///etc/passwd", True))

    assert opened == ["https://discord.example/"]


# ---------- the bridge poll (#3 item 31) ----------

class FakePage:
    """The QWebEnginePage calls the bridge poll makes; answers by hand."""

    def __init__(self):
        self.pending = []
        self.pending_scripts = []

    def runJavaScript(self, script, world, callback=None):
        self.pending.append(callback)
        self.pending_scripts.append(script)


BRIDGE_ANSWER = {"targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}], "weapon": "RPG-29"}


@pytest.fixture
def bridge_page(qapp):
    page = webmap.MapPage({"map_render": "auto", "map_source": "deadline", "map_follow": True})
    page.page = FakePage()
    yield page
    page.page = None
    page.shutdown()


def test_no_second_poll_while_the_page_has_not_answered(bridge_page):
    fake = bridge_page.page

    bridge_page.poll_targets()
    bridge_page.poll_targets()
    bridge_page.poll_targets()
    assert len(fake.pending) == 1

    fake.pending.pop()(json.dumps(BRIDGE_ANSWER))
    assert bridge_page.bridge_found

    bridge_page.poll_targets()
    assert len(fake.pending) == 1


def test_a_new_load_does_not_wait_for_the_old_pages_answer(bridge_page):
    bridge_page.poll_targets()
    bridge_page.on_load_started()
    bridge_page.on_load_finished(True)

    bridge_page.poll_targets()
    assert len(bridge_page.page.pending) == 2


def test_a_renderer_crash_stops_the_poll_and_forgets_the_bridge(bridge_page):
    received = []
    bridge_page.targets_received.connect(received.append)
    bridge_page.on_load_finished(True)
    assert bridge_page.bridge_timer.isActive()

    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(json.dumps(BRIDGE_ANSWER))
    assert bridge_page.bridge_found and len(received) == 1

    bridge_page.poll_targets()
    bridge_page.on_render_crash(None, 1)

    assert not bridge_page.bridge_timer.isActive()
    assert not bridge_page.black_timer.isActive()
    assert bridge_page.bridge_found is None
    assert bridge_page.panel_kind == "crashed"

    # After the reload the same targets are delivered again
    bridge_page.on_load_started()
    bridge_page.on_load_finished(True)
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(json.dumps(BRIDGE_ANSWER))
    assert len(received) == 2


def test_a_failed_load_forgets_the_bridge(bridge_page):
    bridge_page.on_load_finished(True)
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(json.dumps(BRIDGE_ANSWER))
    assert bridge_page.bridge_found

    bridge_page.on_load_started()
    bridge_page.on_load_finished(False)

    assert bridge_page.bridge_found is None
    assert bridge_page.last_targets is None
    assert bridge_page.panel_kind == "failed"


def test_a_new_page_start_takes_the_pages_weapon_as_a_baseline(bridge_page):
    """After a load, a renderer crash or a source switch the page's first
    answer is not emitted: the app's weapon is sent to the page instead
    (#5, review 1.6.0 slice 5 claim 4)."""
    received = []
    bridge_page.weapon_received.connect(received.append)
    fake = bridge_page.page
    bridge_page.select_weapon("AT-4")
    fake.pending.clear()

    for restart in (
        lambda: None,
        lambda: (bridge_page.on_load_started(), bridge_page.on_load_finished(True)),
        lambda: bridge_page.on_render_crash(None, 1),
        lambda: (bridge_page.on_load_started(), bridge_page.on_load_finished(False)),
        bridge_page.load_source,
    ):
        restart()

        bridge_page.on_bridge_result(BRIDGE_ANSWER)

        # The app's weapon went to the page (a script without a callback).
        assert fake.pending == [None]
        fake.pending.clear()

        # The page kept its own weapon: still no change.
        bridge_page.on_bridge_result(BRIDGE_ANSWER)
        assert received == []
        assert fake.pending == []

    # A change made on the page afterwards is followed.
    bridge_page.on_bridge_result(dict(BRIDGE_ANSWER, weapon="QLZ87"))
    assert received == ["QLZ87"]


def test_a_page_without_the_bridge_yet_does_not_take_the_baseline(bridge_page):
    """SquadCalc defines the bridge after loading; the null answers before
    that are not the baseline."""
    received = []
    bridge_page.weapon_received.connect(received.append)

    bridge_page.on_bridge_result(None)
    bridge_page.on_bridge_result(BRIDGE_ANSWER)

    assert received == []
    assert bridge_page.last_weapon == "RPG-29"


@pytest.fixture
def main_window(qapp, tmp_path, monkeypatch):
    import config
    from ballistics import load_weapons
    from conftest import ROOT

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))

    from crosshair import MainWindow

    window = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    yield window
    window.close()


TANK_ANSWER = {
    "targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}],
    "weapon": "Tank AP · M256 / Rh120",
}


@pytest.mark.parametrize("event", ["renderer_crash", "failed_load", "source_reload"])
def test_weapon_picked_here_survives_a_page_restart(main_window, event):
    """The verifier's proof of #5 review 1.6.0 slice 5 claim 4: with
    map_follow on, the page's unchanged weapon used to replace the one
    picked here after the page restarted."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    window = main_window
    window.set_page(3)
    page = window.map_page
    assert window.config["map_follow"]

    page.on_bridge_result({"targets": [], "weapon": None})
    page.on_bridge_result(TANK_ANSWER)
    assert window.picker.current == "Tank AP · M256 / Rh120"

    # Picked here; the page keeps its weapon (it does not have it, or the
    # select was sent while it was loading).
    window.select_weapon("AT-4")
    page.on_bridge_result(TANK_ANSWER)
    assert window.picker.current == "AT-4"

    if event == "renderer_crash":
        page.on_render_crash(None, 1)
        page.on_load_started()
        page.on_load_finished(True)
    elif event == "failed_load":
        page.on_load_started()
        page.on_load_finished(False)
        page.on_load_started()
        page.on_load_finished(True)
    else:
        page.load_source()

    # The page, restarted, reports the same weapon it always had.
    page.on_bridge_result(TANK_ANSWER)
    page.on_bridge_result(TANK_ANSWER)
    assert window.picker.current == "AT-4", \
        f"after {event} the unchanged SquadCalc weapon replaced the one picked here"


# ---------- a real page: the bridge script and the system browser ----------

def spin(qapp, seconds, until=lambda: False):
    """Run the event loop for `seconds` or until `until()` is true."""
    deadline = time.monotonic() + seconds

    while not until() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)

    return until()


def test_the_bridge_script_sends_only_the_newest_target(qapp):
    """The page converts one target per poll, not the whole list (#5,
    review 1.6.0 slice 5 claim 6)."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWebEngineCore import QWebEnginePage

    from maplink import bridge_script

    page = QWebEnginePage(webmap.shared_profile())
    loaded = []
    page.loadFinished.connect(loaded.append)
    page.setHtml(
        "<script>window.squadBallistics={targets:()=>"
        "[{distance:1},{distance:2},{distance:3}],weapon:()=>'AT-4'}</script>"
    )
    assert spin(qapp, 15, lambda: loaded)

    result = []
    page.runJavaScript(bridge_script(), 0, result.append)
    assert spin(qapp, 15, lambda: result)

    assert json.loads(result[0]) == {"revision": None, "targets": [{"distance": 3}], "weapon": "AT-4"}

    page.deleteLater()
    qapp.processEvents()


@pytest.fixture
def local_site(qapp):
    """Two origins on this machine, 127.0.0.1 (the map) and localhost (the
    "other site"): (map origin, other origin, {path: html}). The profile's
    network block is lifted for the test; the map page refuses every
    navigation to the other origin, so nothing else is loaded."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    pages = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = pages.get(self.path, "<!doctype html><title>x</title>").encode()
            kind = "application/javascript" if self.path.endswith(".js") else "text/html"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    profile = webmap.shared_profile()
    profile.setUrlRequestInterceptor(None)

    try:
        yield f"http://127.0.0.1:{port}", f"http://localhost:{port}", pages
    finally:
        profile.setUrlRequestInterceptor(getattr(profile, "_test_interceptor", None))
        server.shutdown()
        server.server_close()


@pytest.fixture
def live_map(qapp, local_site, monkeypatch, opened):
    """A MapPage on the local map origin: (page, other origin, pages); the
    page's HTML is set in `pages["/"]` before `load()`."""
    origin, other, pages = local_site
    monkeypatch.setitem(webmap.MAP_SOURCES, "local", origin + "/")

    page = webmap.MapPage({"map_render": "auto", "map_source": "local"})
    page.resize(800, 700)
    page.show()

    def load():
        page.ensure_loaded()
        assert spin(qapp, 15, lambda: page.page.url().toString() == origin + "/"
                    and not page.loading)
        assert spin(qapp, 5, lambda: page.view.focusProxy() is not None)

    yield page, other, pages, load

    page.shutdown()
    page.hide()
    qapp.processEvents()


def test_a_page_cannot_open_the_system_browser_on_its_own(qapp, live_map, opened):
    """Script popups and a script navigation to another site, no click:
    nothing reaches the system browser; the status line names the address
    (#5, review 1.6.0 slice 5 claim 1: 20 opens a second before)."""
    page, other, pages, load = live_map
    pages["/"] = (
        "<!doctype html><script>"
        "let n = 0;"
        "const t = setInterval(() => { window.open('%s/popup' + n++);"
        " if (n >= 20) clearInterval(t); }, 50);"
        "setTimeout(() => { location.href = '%s/elsewhere'; }, 1500);"
        "</script>" % (other, other)
    )
    load()

    spin(qapp, 3)

    assert opened == [], f"{len(opened)} system-browser opens without a click"
    assert page.status.text().endswith(webmap.tr("map_external_blocked", url=other + "/elsewhere"))
    assert page.panel_kind is None and page.bridge_timer.isActive()


LINKS_PAGE = (
    "<!doctype html><style>body{margin:0} a,button{display:block;width:800px;"
    "height:80px;margin:0;padding:0;border:0}</style>"
    "<a target=_blank rel=noopener href='%(o)s/wiki'>wiki</a>"
    "<a href='%(o)s/same-tab'>same tab</a>"
    "<button onclick=\"window.open('%(o)s/clicked-popup')\">popup</button>"
    "<button onclick=\"location.href='%(o)s/one';"
    "setTimeout(() => { location.href = '%(o)s/two'; }, 300)\">two</button>"
)


def test_links_the_user_clicks_open_in_the_system_browser(qapp, live_map, opened):
    """SquadCalc's own external links (wiki, squad-armor, battlemetrics,
    discord, github, changelog) are target=_blank links the user clicks:
    they keep working, one address per click."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest

    page, other, pages, load = live_map
    pages["/"] = LINKS_PAGE % {"o": other}
    load()

    def click(y):
        QTest.mouseClick(page.view.focusProxy(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, QPoint(100, y))

    for y, path in ((40, "/wiki"), (120, "/same-tab"), (200, "/clicked-popup")):
        click(y)
        assert spin(qapp, 10, lambda: len(opened) and opened[-1] == other + path), opened
        assert page.status.text().endswith(webmap.tr("map_external_opened", url=other + path))

    # One click, two navigations: only the first one goes out.
    click(280)
    assert spin(qapp, 10, lambda: "two" in page.status.text())
    assert opened == [other + p for p in ("/wiki", "/same-tab", "/clicked-popup", "/one")]
    assert page.status.text().endswith(webmap.tr("map_external_blocked", url=other + "/two"))

    # The map never left its origin, and the refused navigations are not
    # failed loads of it: no help panel, the bridge poll goes on.
    assert page.page.url().toString() == page.page.requestedUrl().toString()
    assert page.panel_kind is None
    assert page.bridge_timer.isActive()

    # The next load of the map starts with a clean status line.
    page.reload()
    assert spin(qapp, 15, lambda: "two" not in page.status.text())
    assert spin(qapp, 15, lambda: not page.loading and page.bridge_timer.isActive())


class FakeLoadingInfo:
    """The QWebEngineLoadingInfo calls MapPage.on_loading_changed makes."""

    def __init__(self, status, url):
        from PyQt6.QtCore import QUrl

        self._status = status
        self._url = QUrl(url)

    def status(self):
        return self._status

    def url(self):
        return self._url


def test_loads_of_other_origins_are_not_loads_of_the_map(bridge_page):
    """A refused navigation reports a start and a stop of its own address;
    a reload issued while it is cancelled is reported started with that
    address too and must still start (QtWebEngine 6.11, seen in CI run
    41057783601)."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineCore import QWebEngineLoadingInfo

    Status = QWebEngineLoadingInfo.LoadStatus
    bridge_page.page.map_origin = webmap.url_origin(QUrl("https://calc.example/"))
    starts = []
    real_start = bridge_page.on_load_started
    bridge_page.on_load_started = lambda: (starts.append(True), real_start())

    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadStartedStatus, "https://calc.example/"))
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadSucceededStatus, "https://calc.example/"))
    assert starts == [True] and bridge_page.bridge_timer.isActive()

    # Refused: neither a start nor a failure of the map.
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadStartedStatus, "https://evil.example/"))
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadStoppedStatus, "https://evil.example/"))
    assert starts == [True]
    assert not bridge_page.loading and bridge_page.panel_kind is None
    assert bridge_page.bridge_timer.isActive()

    # A reload right after it: started under the refused address.
    bridge_page.external_notice = "notice"
    bridge_page.weapon_baseline_pending = False
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadStartedStatus, "https://evil.example/"))
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadSucceededStatus, "https://calc.example/"))
    assert starts == [True, True]
    assert bridge_page.external_notice == ""
    assert bridge_page.weapon_baseline_pending
    assert bridge_page.bridge_timer.isActive() and not bridge_page.loading

    # A failed load of the map is still a failure.
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadStartedStatus, "https://calc.example/"))
    bridge_page.on_loading_changed(FakeLoadingInfo(Status.LoadFailedStatus, "https://calc.example/"))
    assert bridge_page.panel_kind == "failed"


# ---------- polling cost and latency (#5, performance audit of the map) ----------

def raw(answer):
    """A poll answer as the page sends it: JSON text."""
    return json.dumps(answer)


def test_an_unchanged_answer_is_not_parsed_again(bridge_page, monkeypatch):
    """A target's profile has up to 10001 numbers (3.5 ms to validate on the
    GUI thread, 6.8 ms to hand over): an answer equal to the last one is
    compared as text and nothing more."""
    parsed = []
    real = webmap.parse_bridge
    monkeypatch.setattr(webmap, "parse_bridge", lambda value: parsed.append(value) or real(value))
    received = []
    bridge_page.targets_received.connect(received.append)

    for _ in range(5):
        bridge_page.poll_targets()
        bridge_page.page.pending.pop()(raw(BRIDGE_ANSWER))

    assert len(parsed) == 1 and len(received) == 1
    assert not bridge_page.bridge_pending

    changed = dict(BRIDGE_ANSWER, targets=[{"distance": 500, "heightDiff": 0, "bearing": 10}])
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(raw(changed))

    assert len(parsed) == 2 and len(received) == 2


def test_a_restarted_page_is_read_again_even_if_it_answers_the_same(bridge_page):
    """After a load the page's first answer is the baseline again: an answer
    equal to the one before the load must not be skipped."""
    bridge_page.weapon_baseline_pending = False
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(raw(BRIDGE_ANSWER))

    bridge_page.on_load_started()
    bridge_page.on_load_finished(True)

    assert bridge_page.weapon_baseline_pending
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(raw(BRIDGE_ANSWER))
    assert not bridge_page.weapon_baseline_pending


@pytest.mark.parametrize("answer", [
    "not json",
    "[1, 2]",
    '{"targets": ' + "[" * 100000,
    "x" * (webmap.MAX_ANSWER_CHARS + 1),
    5,
])
def test_an_answer_that_is_not_a_poll_answer_is_no_bridge(bridge_page, answer):
    bridge_page.on_bridge_answer(raw(BRIDGE_ANSWER))
    assert bridge_page.bridge_found

    bridge_page.on_bridge_answer(answer)

    assert bridge_page.bridge_found is False
    assert not bridge_page.bridge_pending


def test_the_counter_decides_whether_the_targets_are_read(bridge_page, monkeypatch):
    """With the page's change counter the poll is a number: the answer has
    no targets while the counter is the one the app has, and the weapon is
    still followed."""
    received, weapons = [], []
    bridge_page.targets_received.connect(received.append)
    bridge_page.weapon_received.connect(weapons.append)
    bridge_page.weapon_baseline_pending = False
    first = dict(BRIDGE_ANSWER, revision=7)

    bridge_page.poll_targets()
    assert "null" in bridge_page.page.pending_scripts[-1]
    bridge_page.page.pending.pop()(raw(first))

    assert bridge_page.known_revision == 7 and len(received) == 1
    weapons.clear()
    bridge_page.poll_targets()
    assert bridge_page.page.pending_scripts[-1].endswith(", 7)")

    # The counter did not move: no targets in the answer, none emitted.
    bridge_page.page.pending.pop()(raw({"revision": 7, "weapon": "RPG-29"}))
    assert len(received) == 1 and weapons == []

    # A weapon change alone is still followed.
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(raw({"revision": 7, "weapon": "AT-4"}))
    assert weapons == ["AT-4"] and len(received) == 1

    # The counter moved: the targets come with it.
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(raw(dict(first, revision=8, targets=[{"distance": 900}])))
    assert bridge_page.known_revision == 8 and len(received) == 2

    # The page restarts: its counter starts again.
    bridge_page.on_load_started()
    assert bridge_page.known_revision is None


def test_the_poll_is_fast_while_the_map_is_shown_and_free_with_a_counter(bridge_page, qapp):
    bridge_page.on_load_finished(True)
    bridge_page.show()

    assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_MS

    bridge_page.on_bridge_result(dict(BRIDGE_ANSWER, revision=1))
    assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_COUNTER_MS

    bridge_page.hide()
    assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_HIDDEN_MS

    bridge_page.show()
    assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_COUNTER_MS
    assert webmap.BRIDGE_POLL_COUNTER_MS <= 100 and webmap.BRIDGE_POLL_MS <= 150
    assert webmap.BRIDGE_POLL_HIDDEN_MS > webmap.BRIDGE_POLL_MS


@pytest.mark.parametrize("follow", [True, False])
def test_a_hidden_map_is_polled_only_while_the_calculator_follows_it(bridge_page, qapp, follow):
    """The map tab not shown: with map_follow the calculator's targets still
    come from the page, so the poll goes on (slowly); without it nothing is
    read from the page and the poll stops."""
    bridge_page.config["map_follow"] = follow
    bridge_page.on_load_finished(True)
    assert not bridge_page.isVisible()

    assert bridge_page.bridge_timer.isActive() is follow
    if follow:
        assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_HIDDEN_MS

    bridge_page.show()
    assert bridge_page.bridge_timer.isActive()
    assert bridge_page.bridge_timer.interval() == webmap.BRIDGE_POLL_MS

    bridge_page.hide()
    assert bridge_page.bridge_timer.isActive() is follow

    # Switching the setting while the map is hidden takes effect at once.
    bridge_page.config["map_follow"] = not follow
    bridge_page.update_polling()
    assert bridge_page.bridge_timer.isActive() is (not follow)


@pytest.mark.parametrize("follow", [True, False])
def test_a_minimised_window_counts_as_hidden(qapp, follow):
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    window = QWidget()
    QVBoxLayout(window)
    page = webmap.MapPage({"map_render": "auto", "map_source": "deadline", "map_follow": follow})
    window.layout().addWidget(page)
    window.show()

    try:
        page.on_load_finished(True)
        assert page.bridge_timer.interval() == webmap.BRIDGE_POLL_MS

        window.showMinimized()
        qapp.processEvents()
        assert window.isMinimized() and not page.on_screen()
        page.update_polling()

        assert page.bridge_timer.isActive() is follow
        if follow:
            assert page.bridge_timer.interval() == webmap.BRIDGE_POLL_HIDDEN_MS
    finally:
        page.shutdown()
        window.close()


def test_the_poll_stops_with_the_page_whatever_is_shown(bridge_page):
    bridge_page.show()
    bridge_page.on_load_finished(True)
    assert bridge_page.bridge_timer.isActive()

    bridge_page.on_load_started()
    assert not bridge_page.bridge_timer.isActive()

    bridge_page.on_load_finished(False)
    assert not bridge_page.bridge_timer.isActive()

    bridge_page.on_load_finished(True)
    bridge_page.on_render_crash(None, 1)
    assert not bridge_page.bridge_timer.isActive()
    bridge_page.show()
    bridge_page.hide()
    assert not bridge_page.bridge_timer.isActive()


def test_an_announced_change_is_polled_at_once_but_one_at_a_time(bridge_page):
    bridge_page.on_load_finished(True)

    for _ in range(50):
        bridge_page.on_change_announced()

    assert len(bridge_page.page.pending) == 1

    bridge_page.config["map_follow"] = False
    bridge_page.page.pending.pop()(raw(BRIDGE_ANSWER))
    bridge_page.on_change_announced()
    assert bridge_page.page.pending == []


def test_only_the_change_message_is_an_announcement(qapp):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWebEngineCore import QWebEnginePage

    from maplink import CHANGE_MESSAGE

    page = webmap._make_page_classes()(webmap.shared_profile())
    announced = []
    page.change_announced.connect(lambda: announced.append(True))
    Level = QWebEnginePage.JavaScriptConsoleMessageLevel

    page.javaScriptConsoleMessage(Level.InfoMessageLevel, "hello", 1, "page.js")
    page.javaScriptConsoleMessage(Level.InfoMessageLevel, CHANGE_MESSAGE + " ", 1, "page.js")
    assert announced == []

    page.javaScriptConsoleMessage(Level.InfoMessageLevel, CHANGE_MESSAGE, 1, "page.js")
    assert announced == [True]


def test_reload_uses_the_cache(bridge_page):
    """The page was reloaded bypassing the cache: 3.2 MB and about a second
    per press. Clearing the cache is its own button."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineCore import QWebEnginePage

    actions = []
    fake = bridge_page.page
    fake.url = lambda: QUrl("https://calc.example/")
    fake.WebAction = QWebEnginePage.WebAction
    fake.triggerAction = actions.append
    bridge_page.view = object()

    try:
        bridge_page.reload()
    finally:
        bridge_page.view = None

    assert actions == [QWebEnginePage.WebAction.Reload]


COUNTER_BRIDGE = (
    "<!doctype html><script>"
    "window.calls = {targets: 0, lastTarget: 0};"
    "window.rev = 1; window.weaponName = 'AT-4'; window.list = [{distance: 100}, {distance: 250}];"
    "window.squadBallistics = {version: 5, revision: () => window.rev,"
    " targets: () => { window.calls.targets++; return window.list; },"
    " lastTarget: () => { window.calls.lastTarget++; return window.list[window.list.length - 1] || null; },"
    " weapon: () => window.weaponName};"
    "</script>"
)


def run_script(qapp, page, script):
    result = []
    page.runJavaScript(script, 0, result.append)
    assert spin(qapp, 15, lambda: result)

    return result[0]


@pytest.fixture
def blank_page(qapp):
    """A QWebEnginePage that loads the HTML given to it: (page, load)."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWebEngineCore import QWebEnginePage

    page = QWebEnginePage(webmap.shared_profile())

    def load(html):
        loaded = []
        page.loadFinished.connect(loaded.append)
        page.setHtml(html)
        assert spin(qapp, 15, lambda: loaded)

    yield page, load

    page.deleteLater()
    qapp.processEvents()


def test_the_poll_script_reads_the_targets_only_when_the_counter_moved(qapp, blank_page):
    """A page with `revision` is polled with its counter: the targets (each
    with a profile of up to 10001 heights) are built only when it moved,
    through `lastTarget()` when the page has it."""
    from maplink import bridge_script

    page, load = blank_page
    load(COUNTER_BRIDGE)

    first = json.loads(run_script(qapp, page, bridge_script()))
    assert first == {"revision": 1, "weapon": "AT-4", "targets": [{"distance": 250}]}

    same = json.loads(run_script(qapp, page, bridge_script(1)))
    assert same == {"revision": 1, "weapon": "AT-4"}
    assert run_script(qapp, page, "window.calls.targets") == 0
    assert run_script(qapp, page, "window.calls.lastTarget") == 1

    run_script(qapp, page, "window.rev = 2; window.list = []; 1")
    moved = json.loads(run_script(qapp, page, bridge_script(1)))
    assert moved == {"revision": 2, "weapon": "AT-4", "targets": []}

    # A counter the page has is a number or a function giving one.
    run_script(qapp, page, "window.squadBallistics.revision = 5; 1")
    assert json.loads(run_script(qapp, page, bridge_script(5))).get("targets") is None


def test_the_poll_script_works_with_the_bridge_as_it_is_today(qapp, blank_page):
    """No counter, no lastTarget: everything is sent each poll, the newest
    target alone, as before."""
    from maplink import bridge_script

    page, load = blank_page
    load(
        "<script>window.squadBallistics={version:4,"
        "targets:()=>[{distance:1},{distance:2},{distance:3}],"
        "weapon:()=>'AT-4'}</script>"
    )

    for known in (None, 3):
        answer = json.loads(run_script(qapp, page, bridge_script(known)))
        assert answer == {"revision": None, "targets": [{"distance": 3}], "weapon": "AT-4"}

    load("<script>window.squadBallistics={}</script>")
    assert run_script(qapp, page, bridge_script()) is None


def test_a_page_with_a_counter_is_read_as_soon_as_it_changes(qapp, live_map):
    """No poll runs in this test (the timer is stopped): the page itself
    announces the change (maplink.WATCH_SCRIPT, injected into it) and the
    target reaches the app within a few tens of milliseconds, where the
    500 ms poll took 184-258 ms at the median and up to 450 ms."""
    page, other, pages, load = live_map
    pages["/"] = COUNTER_BRIDGE
    received = []
    page.targets_received.connect(lambda targets: received.append((time.monotonic(), targets)))
    load()

    # The first announcement, when the bridge appears, delivers the baseline.
    assert spin(qapp, 10, lambda: received)
    page.bridge_timer.stop()
    received.clear()

    for distance in (300, 410, 520):
        started = time.monotonic()
        run_script(qapp, page.page, "window.list.push({distance: %d}); window.rev++; 1" % distance)

        assert spin(qapp, 5, lambda: received), f"no target after {distance}"
        assert received[-1][1][0].distance == distance
        assert received[-1][0] - started < 0.35
        received.clear()

    assert not page.bridge_timer.isActive()


def test_a_page_without_a_counter_is_not_watched(qapp, live_map):
    """Without a counter a change can only be found by building every
    target's profile, which the page's timer must not do 25 times a second."""
    page, other, pages, load = live_map
    pages["/"] = (
        "<!doctype html><script>window.calls = 0; window.squadBallistics = {version: 4,"
        " targets: () => { window.calls++; return [{distance: 100}]; }, weapon: () => 'AT-4'};</script>"
    )
    page.bridge_timer.setInterval(60000)
    load()
    page.bridge_timer.stop()

    spin(qapp, 1)

    assert run_script(qapp, page.page, "window.calls") == 0


def test_clearing_the_cache_removes_the_service_worker_but_keeps_the_settings(qapp, live_map):
    """"Clear map cache" cleared only the HTTP cache: the service worker
    (SquadCalc's about 22 MB) stayed. Cookies and localStorage, where
    SquadCalc keeps its settings, must stay."""
    page, other, pages, load = live_map
    pages["/sw.js"] = "self.addEventListener('fetch', () => {});"
    pages["/"] = (
        "<!doctype html><script>"
        "navigator.serviceWorker.register('/sw.js').then(() => navigator.serviceWorker.ready)"
        ".then(() => caches.open('tiles')).then(() => { window.ready = true; });"
        "localStorage.setItem('squadcalc-setting', 'kept');"
        "</script>"
    )
    load()
    assert spin(qapp, 20, lambda: run_script(qapp, page.page, "window.ready === true"))

    def count(what):
        run_script(qapp, page.page, "window.counted = null; %s; 1" % what)
        assert spin(qapp, 15, lambda: run_script(qapp, page.page, "window.counted !== null"))

        return run_script(qapp, page.page, "window.counted")

    registrations = "navigator.serviceWorker.getRegistrations().then(r => window.counted = r.length)"
    caches = "caches.keys().then(k => window.counted = k.length)"
    assert count(registrations) == 1 and count(caches) == 1

    page.clear_cache()

    assert spin(qapp, 15, lambda: count(registrations) == 0 and count(caches) == 0)
    assert run_script(qapp, page.page, "localStorage.getItem('squadcalc-setting')") == "kept"


def test_clearing_the_cache_of_a_map_never_opened_removes_the_folders(user_dirs):
    old_unused, storage = user_dirs
    worker = storage / "Service Worker"
    worker.mkdir(parents=True)
    (worker / "CacheStorage").write_bytes(b"x" * 100)
    (storage / "Local Storage").mkdir()
    (storage / "Local Storage" / "leveldb").write_bytes(b"settings")
    (storage / "Cookies").write_bytes(b"cookie")

    from config import data_dir

    cache = os.path.join(data_dir(), "WebEngine", "Cache")
    os.makedirs(cache)
    open(os.path.join(cache, "f_000001"), "wb").write(b"tile")

    page = webmap.MapPage({"map_render": "auto", "map_source": "deadline"})
    assert page.profile is None

    page.clear_cache()

    assert not worker.exists() and not os.path.exists(cache)
    assert (storage / "Local Storage" / "leveldb").read_bytes() == b"settings"
    assert (storage / "Cookies").read_bytes() == b"cookie"


# ---------- software OpenGL (#5, performance audit of the map) ----------

@pytest.mark.parametrize("renderer", [
    "llvmpipe (LLVM 19.1.7, 256 bits)",
    "softpipe",
    "Software Rasterizer",
    "Mesa DRI swrast",
    "llvmpipe",
    "Google SwiftShader",
])
def test_software_opengl_is_recognised(renderer):
    assert webmap.is_software_renderer(renderer)


@pytest.mark.parametrize("renderer", [
    "NVIDIA GeForce RTX 4070/PCIe/SSE2",
    "AMD Radeon RX 6800 (radeonsi, navi21, LLVM 17.0.6, DRM 3.57, 6.8.0)",
    "Mesa Intel(R) UHD Graphics 620 (WHL GT2)",
    "",
    None,
])
def test_a_gpu_is_not_software_opengl(renderer):
    assert not webmap.is_software_renderer(renderer)


def test_auto_runs_without_the_gpu_path_when_opengl_is_software():
    """On llvmpipe the web view is composed twice (Qt Quick, then the
    compositor): 143-146 % of a core against 76-82 % in the software mode,
    a 10 ms timer up to 67 ms late against 25-41 ms."""
    env = {"QTWEBENGINE_CHROMIUM_FLAGS": "--lang=ru"}

    choice = webmap.configure_environment("auto", env, probe=lambda: "llvmpipe (LLVM 19.1.7, 256 bits)")

    assert choice == webmap.RenderChoice("auto", "software", "llvmpipe (LLVM 19.1.7, 256 bits)")
    assert webmap.render_choice == choice
    assert env["QT_QUICK_BACKEND"] == "software"
    assert "--disable-gpu" in flags_of(env["QTWEBENGINE_CHROMIUM_FLAGS"])
    assert "--disable-gpu-compositing" in flags_of(env["QTWEBENGINE_CHROMIUM_FLAGS"])
    assert "--lang=ru" in flags_of(env["QTWEBENGINE_CHROMIUM_FLAGS"])


def test_auto_stays_on_the_gpu_on_a_real_gpu():
    env = {}

    choice = webmap.configure_environment("auto", env, probe=lambda: "NVIDIA GeForce RTX 4070/PCIe/SSE2")

    assert choice == webmap.RenderChoice("auto", "hardware", None)
    assert "QT_QUICK_BACKEND" not in env
    assert "--disable-gpu" not in flags_of(env["QTWEBENGINE_CHROMIUM_FLAGS"])


def test_auto_stays_on_the_gpu_when_opengl_cannot_be_read():
    env = {}

    choice = webmap.configure_environment("auto", env, probe=lambda: None)

    assert choice.mode == "hardware"
    assert "QT_QUICK_BACKEND" not in env


def test_the_manual_choice_and_the_users_backend_are_not_second_guessed():
    probed = []

    def probe():
        probed.append(True)
        return "llvmpipe"

    env = {}
    choice = webmap.configure_environment("software", env, probe=probe)
    assert choice == webmap.RenderChoice("software", "software", None)
    assert env["QT_QUICK_BACKEND"] == "software"

    env = {"QT_QUICK_BACKEND": "opengl"}
    choice = webmap.configure_environment("auto", env, probe=probe)
    assert choice.mode == "hardware" and env["QT_QUICK_BACKEND"] == "opengl"

    assert probed == []


def test_a_restart_does_not_inherit_the_automatic_software_mode():
    env = {}
    webmap.configure_environment("auto", env, probe=lambda: "llvmpipe")

    child = dict(env)
    choice = webmap.configure_environment("auto", child, probe=lambda: "AMD Radeon RX 6800")

    assert choice.mode == "hardware"
    assert "QT_QUICK_BACKEND" not in child
    assert "--disable-gpu" not in flags_of(child["QTWEBENGINE_CHROMIUM_FLAGS"])


def test_no_probe_leaves_auto_as_it_was():
    env = {}

    assert webmap.configure_environment("auto", env).mode == "hardware"
    assert "QT_QUICK_BACKEND" not in env


def test_the_probe_that_fails_reads_nothing(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no python")

    monkeypatch.setattr(webmap.subprocess, "run", broken)
    assert webmap.probe_gl_renderer() is None

    class Result:
        returncode, stdout = 1, "llvmpipe\n"

    monkeypatch.setattr(webmap.subprocess, "run", lambda *a, **k: Result)
    assert webmap.probe_gl_renderer() is None

    monkeypatch.setattr(
        webmap.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(webmap.subprocess.TimeoutExpired("python", 1))
    )
    assert webmap.probe_gl_renderer() is None


REAL_SOFTWARE_RUN = """
import os, sys, time
sys.path.insert(0, {root!r})
import webmap
choice = webmap.configure_environment("auto", probe=webmap.probe_gl_renderer)
import PyQt6.QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
webmap.MAP_SOURCES["deadline"] = "data:text/html,<body style='margin:0;background:%233b82f6'>x</body>"
page = webmap.MapPage({{"map_render": "auto", "map_source": "deadline", "map_follow": True}})
page.resize(400, 300)
page.show()
page.ensure_loaded()

def spin(seconds, until=lambda: False):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not until():
        app.processEvents()
        time.sleep(0.01)

spin(30, lambda: page.page_ready)
spin(1.5)
image = page.view.grab().toImage()
print("RESULT", choice.mode, bool(choice.renderer), os.environ.get("QT_QUICK_BACKEND"),
      webmap.looks_black(image), image.pixelColor(200, 150).name(),
      page.status.text().endswith(webmap.tr("map_compat_on")), flush=True)
page.shutdown()
os._exit(0)
"""


def test_a_real_software_opengl_runs_the_map_without_the_gpu_path(xvfb_display):
    """The whole path on a real llvmpipe (Xvfb has no GPU): the probe reads
    it, `auto` becomes the software mode, and the map still draws (it is not
    black)."""
    import subprocess
    import sys

    from conftest import ROOT

    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    env = dict(os.environ, DISPLAY=xvfb_display, QT_QPA_PLATFORM="xcb")
    env.pop("QT_QUICK_BACKEND", None)

    assert webmap.is_software_renderer(webmap.probe_gl_renderer(env))

    result = subprocess.run(
        [sys.executable, "-c", REAL_SOFTWARE_RUN.format(root=ROOT)],
        env=env, capture_output=True, text=True, timeout=120
    )

    lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT")]
    assert lines, result.stdout + result.stderr
    assert lines[-1].split() == ["RESULT", "software", "True", "software", "False", "#3b82f6", "True"]


# ---------- the window: the map made at idle, its settings (#5) ----------

def test_the_map_is_created_before_the_first_visit_when_the_calculator_follows_it(main_window):
    """The first open of the tab froze the window for 108-241 ms (up to 338
    ms of gaps while the page loaded); `app.main` has the window create the
    map once it is up."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    window = main_window
    assert window.config["map_follow"] and not window.config["map_external"]
    assert window.map_page.view is None

    window.preload_map()

    assert window.map_page.view is not None
    assert window.pages.currentIndex() == 0

    view = window.map_page.view
    window.preload_map()
    window.set_page(3)
    assert window.map_page.view is view


@pytest.mark.parametrize("setting", ["map_follow", "map_external"])
def test_the_map_is_not_created_early_when_nothing_needs_it(main_window, setting):
    """Without `map_follow` the calculator does not use the map; with
    `map_external` the map is the regular browser."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    main_window.config["map_follow"] = setting != "map_follow"
    main_window.config["map_external"] = setting == "map_external"

    main_window.preload_map()

    assert main_window.map_page.view is None


def test_switching_the_map_follow_on_creates_the_map_and_starts_its_poll(main_window, qapp):
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    window = main_window
    window.config["map_follow"] = False
    page = window.map_page
    page.page_ready = True
    page.update_polling()
    assert not page.bridge_timer.isActive()

    window.config["map_follow"] = True
    window.on_map_follow_changed(True)

    assert page.bridge_timer.isActive()
    assert spin(qapp, 5, lambda: page.view is not None)

    window.config["map_follow"] = False
    window.on_map_follow_changed(False)
    assert not page.bridge_timer.isActive()


def test_the_settings_say_how_the_map_is_drawn(main_window, monkeypatch):
    """What "Normal" does depends on the machine: the settings page says
    whether the map runs with the GPU or without it, and why."""
    window = main_window

    def line():
        window.rebuild()

        return window.render_in_use_label.text()

    monkeypatch.setattr(webmap, "render_choice", webmap.RenderChoice("auto", "hardware", None))
    assert line() == webmap.tr("s_map_render_in_use", mode=webmap.tr("s_map_render_in_use_hardware"))

    monkeypatch.setattr(
        webmap, "render_choice",
        webmap.RenderChoice("auto", "software", "llvmpipe (LLVM 19.1.7, 256 bits)")
    )
    assert "llvmpipe (LLVM 19.1.7, 256 bits)" in line()
    assert webmap.tr("s_map_render_in_use_hardware") not in line()

    monkeypatch.setattr(webmap, "render_choice", webmap.RenderChoice("software", "software", None))
    assert line() == webmap.tr("s_map_render_in_use", mode=webmap.tr("s_map_render_in_use_software"))

    # The status line above the map and the "Compatibility mode" offer
    # follow what the map really does, not only the setting.
    monkeypatch.setattr(webmap, "render_choice", webmap.RenderChoice("auto", "software", "llvmpipe"))
    page = window.map_page
    page.show_panel("black")
    assert not page.compat_button.isVisibleTo(page.panel)
    assert page.software_in_use()


def test_a_minimised_main_window_slows_the_map_poll(main_window, qapp):
    window = main_window
    page = window.map_page
    window.show()
    window.set_page(3)
    page.page_ready = True
    page.update_polling()
    assert page.bridge_timer.interval() == webmap.BRIDGE_POLL_MS

    window.showMinimized()
    qapp.processEvents()
    window.changeEvent(webmap.QEvent(webmap.QEvent.Type.WindowStateChange))

    assert page.bridge_timer.interval() == webmap.BRIDGE_POLL_HIDDEN_MS
