import errno
import http.server
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

    def runJavaScript(self, script, world, callback=None):
        self.pending.append(callback)


BRIDGE_ANSWER = {"targets": [{"distance": 420, "heightDiff": -6, "bearing": 90}], "weapon": "RPG-29"}


@pytest.fixture
def bridge_page(qapp):
    page = webmap.MapPage({"map_render": "auto", "map_source": "deadline"})
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

    fake.pending.pop()(BRIDGE_ANSWER)
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
    bridge_page.page.pending.pop()(BRIDGE_ANSWER)
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
    bridge_page.page.pending.pop()(BRIDGE_ANSWER)
    assert len(received) == 2


def test_a_failed_load_forgets_the_bridge(bridge_page):
    bridge_page.on_load_finished(True)
    bridge_page.poll_targets()
    bridge_page.page.pending.pop()(BRIDGE_ANSWER)
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

    from maplink import BRIDGE_SCRIPT

    page = QWebEnginePage(webmap.shared_profile())
    loaded = []
    page.loadFinished.connect(loaded.append)
    page.setHtml(
        "<script>window.squadBallistics={targets:()=>"
        "[{distance:1},{distance:2},{distance:3}],weapon:()=>'AT-4'}</script>"
    )
    assert spin(qapp, 15, lambda: loaded)

    result = []
    page.runJavaScript(BRIDGE_SCRIPT, 0, result.append)
    assert spin(qapp, 15, lambda: result)

    assert result[0] == {"targets": [{"distance": 3}], "weapon": "AT-4"}

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
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
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
