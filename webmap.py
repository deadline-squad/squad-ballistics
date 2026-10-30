"""Embedded SquadCalc map (QtWebEngine).

Three things make the embedded map behave like a normal browser:

* Network. The embedded Chromium tries HTTP/3 (QUIC), Encrypted Client
  Hello and secure-DNS lookups that some networks block or throttle
  (Russia blocks QUIC to foreign sites and, since 2026, Google/Cloudflare
  encrypted DNS). The page then hangs and stays black even though the
  site opens fine in a regular browser. Those features are switched off,
  so the map uses plain HTTPS over the system DNS.
* Rendering. Some GPU/driver combinations show a black web view. A
  "software" render mode disables the GPU for the map; the page offers it
  automatically when the loaded map looks completely black.
* Speed. A persistent profile keeps map tiles in a disk cache and the
  page is created once and kept alive, so it is not reloaded on every
  visit or UI rebuild. The tiles are a cache ($XDG_CACHE_HOME); the
  cookies and SquadCalc's settings (localStorage) are kept with the user's
  data ($XDG_DATA_HOME), out of reach of cache cleaners.

The page is not trusted. It stays on the origin the app loaded it from,
and it never opens the system browser on its own: an address goes there
only after a click (or Enter/Space) on the map, one per click, and the
status line shows it (see `MapWebPage`).

The page is either the Deadline SquadCalc build (AGS-17 support and the
target bridge polled here, see `maplink`) or the public squadcalc.app.
"""

import os
import time

from PyQt6.QtCore import (
    QEvent,
    QObject,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal
)

from PyQt6.QtGui import (
    QColor,
    QDesktopServices
)

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget
)

import theme
from config import data_dir, state_dir
from i18n import tr
from maplink import BRIDGE_SCRIPT, parse_bridge, select_weapon_script

SQUADCALC_URL = "https://squadcalc.app/"
DEADLINE_SQUADCALC_URL = "https://calc.tk104.duckdns.org/"

# config["map_source"] -> page URL
MAP_SOURCES = {
    "deadline": DEADLINE_SQUADCALC_URL,
    "squadcalc": SQUADCALC_URL,
}

# How often the embedded page is asked for its targets.
BRIDGE_POLL_MS = 500

# Plain HTTPS over the system DNS (see the module docstring).
NETWORK_FLAGS = ("--disable-quic",)
DISABLED_FEATURES = (
    "EncryptedClientHello",
    "DnsOverHttps",
    "UseDnsHttpsSvcbAlpn",
)

SOFTWARE_FLAGS = ("--disable-gpu", "--disable-gpu-compositing")

# How long a page may load before help is offered.
LOAD_TIMEOUT_MS = 25000

# Wait for tiles to appear before judging whether the map is black.
BLACK_CHECK_DELAY_MS = 4000

# Keep the original values so a restart does not inherit our flags.
_ORIGINAL_FLAGS = "SB_ORIGINAL_CHROMIUM_FLAGS"
_ORIGINAL_QUICK = "SB_ORIGINAL_QT_QUICK_BACKEND"


def chromium_flags(render_mode, existing=""):
    """Chromium switches for the embedded browser."""
    flags = []
    disabled = []

    for flag in existing.split():
        if flag.startswith("--disable-features="):
            disabled += [f for f in flag.split("=", 1)[1].split(",") if f]
        elif flag not in flags:
            flags.append(flag)

    extra = list(NETWORK_FLAGS)

    if render_mode == "software":
        extra += SOFTWARE_FLAGS

    for flag in extra:
        if flag not in flags:
            flags.append(flag)

    for feature in DISABLED_FEATURES:
        if feature not in disabled:
            disabled.append(feature)

    flags.append("--disable-features=" + ",".join(disabled))

    return " ".join(flags)


def configure_environment(render_mode, environ=None):
    """Set up QtWebEngine. Must run before QApplication is created."""
    environ = os.environ if environ is None else environ

    if _ORIGINAL_FLAGS not in environ:
        environ[_ORIGINAL_FLAGS] = environ.get(
            "QTWEBENGINE_CHROMIUM_FLAGS", ""
        )
        environ[_ORIGINAL_QUICK] = environ.get("QT_QUICK_BACKEND", "")

    environ["QTWEBENGINE_CHROMIUM_FLAGS"] = chromium_flags(
        render_mode,
        environ[_ORIGINAL_FLAGS]
    )

    if render_mode == "software":
        # The web view is drawn through Qt Quick; render that in software
        # too, otherwise a broken GPU path stays black.
        environ["QT_QUICK_BACKEND"] = "software"
    elif environ[_ORIGINAL_QUICK]:
        environ["QT_QUICK_BACKEND"] = environ[_ORIGINAL_QUICK]
    else:
        environ.pop("QT_QUICK_BACKEND", None)


def looks_black(image, threshold=0.97):
    """True when (almost) every sampled pixel of the image is black."""
    if image.isNull() or image.width() < 10 or image.height() < 10:
        return False

    columns, rows = 32, 24
    dark = 0

    for i in range(columns):
        for j in range(rows):
            color = image.pixelColor(
                int((i + 0.5) * image.width() / columns),
                int((j + 0.5) * image.height() / rows)
            )

            if color.red() + color.green() + color.blue() < 24:
                dark += 1

    return dark >= threshold * columns * rows


def map_url(config):
    """SquadCalc URL of the configured map source."""
    return MAP_SOURCES.get(config.get("map_source"), DEADLINE_SQUADCALC_URL)


# Schemes handed to the system: anything else (file:, ssh:, custom handlers)
# would let a web page start local programs through xdg-open.
EXTERNAL_SCHEMES = ("http", "https")


# Ports a URL without one has, so https://host/ and https://host:443/ are
# the same origin.
DEFAULT_PORTS = {"http": 80, "https": 443}

# After a click (or Enter/Space) on the map the page may send one address to
# the system browser within this many seconds; Chromium's own user
# activation, which lets a click open a popup, lasts as long.
USER_ACTIVATION_SECONDS = 5.0


def url_origin(url):
    """(scheme, host, port) of QUrl `url`, the default port filled in."""
    scheme = url.scheme().lower()

    return scheme, url.host().lower(), url.port(DEFAULT_PORTS.get(scheme, -1))


def open_external(url=SQUADCALC_URL):
    """Open `url` in the regular browser; False when it is not an http(s)
    address or there is nothing to open it with (no xdg-open handler)."""
    target = QUrl(url)

    if target.scheme().lower() not in EXTERNAL_SCHEMES:
        return False

    return QDesktopServices.openUrl(target)


class UserActivationFilter(QObject):
    """Event filter on the map view and every widget inside it: calls
    `on_activation()` on a mouse press, and on Enter or Space (a link
    followed from the keyboard). Events are passed on unchanged.

    The widget Chromium draws into is a child of the view that QtWebEngine
    creates (and replaces after a renderer crash) itself, so children added
    later are watched too.
    """

    KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)

    def __init__(self, view, on_activation):
        super().__init__(view)

        self.on_activation = on_activation

        self.watch(view)

    def watch(self, widget):
        """Filter the events of `widget` and of the widgets inside it."""
        widget.installEventFilter(self)

        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Note user activations and new children; never consume an event."""
        kind = event.type()

        if kind == QEvent.Type.ChildAdded:
            if event.child().isWidgetType():
                self.watch(event.child())
        elif kind == QEvent.Type.MouseButtonPress:
            self.on_activation()
        elif kind == QEvent.Type.KeyPress and event.key() in self.KEYS \
                and not event.isAutoRepeat():
            self.on_activation()

        return False


def _make_page_classes():
    """Page classes are created lazily: QtWebEngine may be missing."""
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

    class MapWebPage(QWebEnginePage):
        """The map page: it stays on the origin the app loaded it from.

        The page is not trusted and has no address bar to get back with, so
        a main-frame navigation to another origin (scheme, host and port: a
        link, a script, a redirect, an https -> http downgrade) is refused.
        The app's own loads (`page.load`) are always accepted and set the
        origin.

        Addresses the page asks to leave for, by navigation or as a new
        window, go to the system browser (http and https only, see
        `open_external`) only after a user activation, one per activation:

        * New windows. Scripts cannot open them without a click
          (JavascriptCanOpenWindows is off), and a request Chromium does
          not mark as user-initiated is refused. A target=_blank link the
          user clicks (SquadCalc's wiki, Discord, GitHub, changelog links)
          is user-initiated.
        * Navigations. QtWebEngine reports a script's `location.href = ...`
          as a clicked link (NavigationTypeLinkClicked), so the two cannot
          be told apart; the app counts the user's clicks on the view
          instead (`note_user_activation`, from UserActivationFilter).

        Every such request is reported by `external_requested(url, outcome)`
        with outcome "opened", "failed" (no browser, or not http(s)) or
        "blocked" (no click), for the status line.
        """

        external_requested = pyqtSignal(str, str)

        def __init__(self, *args):
            super().__init__(*args)

            self.map_origin = None

            # Monotonic time until which one address may be opened, None
            # without a pending user activation. `clock` is replaceable in
            # tests.
            self.activation_deadline = None
            self.clock = time.monotonic

            self.settings().setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False
            )

            self.newWindowRequested.connect(self.on_new_window)

        def note_user_activation(self):
            """The user clicked (or pressed Enter/Space on) the map: one
            address may be opened in the next USER_ACTIVATION_SECONDS."""
            self.activation_deadline = self.clock() + USER_ACTIVATION_SECONDS

        def take_user_activation(self):
            """Use up the pending user activation: whether there was one."""
            deadline, self.activation_deadline = self.activation_deadline, None

            return deadline is not None and self.clock() <= deadline

        def open_elsewhere(self, url, user_initiated=True):
            """Send QUrl `url` to the system browser if the user asked for
            it (see the class docstring) and report the outcome."""
            address = url.toString()

            if not user_initiated or not self.take_user_activation():
                self.external_requested.emit(address, "blocked")
                return

            outcome = "opened" if open_external(address) else "failed"

            self.external_requested.emit(address, outcome)

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            """Accept frames, the app's own loads and the map's origin;
            refuse the rest (see the class docstring)."""
            if not is_main_frame:
                return True

            if nav_type == QWebEnginePage.NavigationType.NavigationTypeTyped:
                self.map_origin = url_origin(url)
                return True

            if url_origin(url) == self.map_origin:
                return True

            self.open_elsewhere(url)

            return False

        def createWindow(self, window_type):
            """No window is ever created here: QtWebEngine then emits
            newWindowRequested (see on_new_window)."""
            return None

        def on_new_window(self, request):
            """A popup or target=_blank link: never opened in the app; its
            address may go to the system browser (no `openIn`, so the
            request is dropped afterwards)."""
            self.open_elsewhere(request.requestedUrl(), request.isUserInitiated())

    return MapWebPage


def persistent_storage_path():
    """Folder of the map's cookies and localStorage (SquadCalc's settings):
    $XDG_DATA_HOME/SquadBallistics/WebEngine/Storage.

    Before 1.6 it was under the cache folder, where cache cleaners wipe it.
    An old folder is moved once, by a rename, when the new one does not
    exist yet. If it cannot be renamed (another file system, no permission)
    it is used where it is and nothing is copied or lost.
    """
    path = os.path.join(state_dir(), "WebEngine", "Storage")
    old = os.path.join(data_dir(), "WebEngine", "Storage")

    if os.path.exists(path) or not os.path.isdir(old):
        return path

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.rename(old, path)
    except OSError:
        return old

    return path


def create_profile(name="SquadBallistics"):
    """Persistent profile: cookies and SquadCalc settings (see
    `persistent_storage_path`) and a tile cache in the cache folder."""
    from PyQt6.QtWebEngineCore import QWebEngineProfile

    profile = QWebEngineProfile(name)

    profile.setPersistentStoragePath(persistent_storage_path())
    profile.setCachePath(os.path.join(data_dir(), "WebEngine", "Cache"))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setHttpCacheMaximumSize(512 * 1024 * 1024)

    return profile


_shared_profile = None


def shared_profile():
    """The one profile of the process.

    Chromium does not cope well with a profile being deleted and created
    again under the same name, so it is created once and kept until the
    process exits (pages are deleted before that, see MapPage.shutdown).
    """
    global _shared_profile

    from PyQt6 import sip

    if _shared_profile is None or sip.isdeleted(_shared_profile):
        _shared_profile = create_profile()

        # Owned by C++ without a parent: never destroyed by Python's
        # garbage collector in the middle of the shutdown.
        sip.transferto(_shared_profile, None)

    return _shared_profile


class MapPage(QWidget):
    """Map tab: a small toolbar, the web view and a help panel.

    While the page is loaded it is polled for its targets and weapon; every
    change is emitted as `targets_received` (a list of `maplink.MapTarget`)
    and `weapon_received` (a weapons.json name).

    The page's first bridge answer after a load, a renderer crash or a
    source switch is not a change: the page restored its weapon, nobody
    picked it. That answer is the baseline and is not emitted; the app's
    weapon (the last one given to `select_weapon`) is sent to the page
    instead, so a weapon picked here survives the page's restart.
    """

    compat_requested = pyqtSignal()

    targets_received = pyqtSignal(list)

    weapon_received = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()

        self.config = config

        self.view = None
        self.page = None
        self.profile = None
        self.activation_filter = None

        self.loading = False

        # None until the page answers, then whether it has the bridge.
        self.bridge_found = None

        self.last_targets = None
        self.last_weapon = None

        # The app's weapon, sent to the page after every (re)start of it.
        self.app_weapon = config.get("last_weapon")

        # The next bridge answer is the baseline (see the class docstring).
        self.weapon_baseline_pending = True

        # Where the page last asked to go, and whether it went: shown in the
        # status line until the next load (see on_external_request).
        self.external_notice = ""

        # A bridge poll is waiting for the page's answer: no second one is
        # sent meanwhile (a busy page would queue them up).
        self.bridge_pending = False

        layout = QVBoxLayout(self)

        layout.setContentsMargins(16, 12, 16, 16)

        layout.setSpacing(8)

        toolbar = QHBoxLayout()

        self.status = QLabel()

        self.status.setProperty("role", "muted")

        self.reload_button = QPushButton()
        self.reload_button.setProperty("flat_style", True)
        self.reload_button.clicked.connect(self.reload)

        self.external_button = QPushButton()
        self.external_button.setProperty("flat_style", True)
        self.external_button.clicked.connect(self.open_in_browser)

        toolbar.addWidget(self.status, 1)
        toolbar.addWidget(self.reload_button)
        toolbar.addWidget(self.external_button)

        layout.addLayout(toolbar)

        self.progress = QProgressBar()

        self.progress.setTextVisible(False)

        self.progress.setFixedHeight(3)

        self.progress.setRange(0, 100)

        self.progress.setStyleSheet(
            f"QProgressBar {{ background: transparent; border: none; }}"
            f"QProgressBar::chunk {{ background: {theme.ACCENT}; }}"
        )

        self.progress.hide()

        layout.addWidget(self.progress)

        # Help panel: shown when the map fails, hangs or looks black.
        self.panel = QFrame()

        self.panel.setObjectName("card")

        panel_layout = QVBoxLayout(self.panel)

        panel_layout.setContentsMargins(20, 16, 20, 16)

        self.panel_title = QLabel()
        self.panel_title.setProperty("role", "title")

        self.panel_text = QLabel()
        self.panel_text.setProperty("role", "muted")
        self.panel_text.setWordWrap(True)

        buttons = QHBoxLayout()

        self.retry_button = QPushButton()
        self.retry_button.clicked.connect(self.reload)

        self.panel_external_button = QPushButton()
        self.panel_external_button.setProperty("flat_style", True)
        self.panel_external_button.clicked.connect(self.open_in_browser)

        self.compat_button = QPushButton()
        self.compat_button.setProperty("flat_style", True)
        self.compat_button.clicked.connect(self.compat_requested.emit)

        self.hide_button = QPushButton("✕")
        self.hide_button.setProperty("flat_style", True)
        self.hide_button.setFixedWidth(40)
        self.hide_button.clicked.connect(self.hide_panel)

        for button in (
            self.retry_button,
            self.panel_external_button,
            self.compat_button
        ):
            buttons.addWidget(button)

        buttons.addStretch()
        buttons.addWidget(self.hide_button)

        panel_layout.addWidget(self.panel_title)
        panel_layout.addWidget(self.panel_text)
        panel_layout.addLayout(buttons)

        self.panel.hide()

        layout.addWidget(self.panel)

        self.view_holder = QVBoxLayout()

        self.view_holder.setContentsMargins(0, 0, 0, 0)

        layout.addLayout(self.view_holder, 1)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.setInterval(LOAD_TIMEOUT_MS)
        self.timeout_timer.timeout.connect(self.on_timeout)

        self.black_timer = QTimer(self)
        self.black_timer.setSingleShot(True)
        self.black_timer.setInterval(BLACK_CHECK_DELAY_MS)
        self.black_timer.timeout.connect(self.check_black)

        self.bridge_timer = QTimer(self)
        self.bridge_timer.setInterval(BRIDGE_POLL_MS)
        self.bridge_timer.timeout.connect(self.poll_targets)

        self.panel_kind = None

        self.retranslate()

    # ---------- texts and colours ----------

    def retranslate(self):
        self.reload_button.setText(tr("map_reload"))
        self.external_button.setText(tr("web_open"))
        self.retry_button.setText(tr("map_retry"))
        self.panel_external_button.setText(tr("web_open"))
        self.compat_button.setText(tr("map_compat_button"))

        if self.panel_kind:
            self.show_panel(self.panel_kind)

        self.update_status()

    def update_status(self, progress=None):
        if self.view is None and self.panel_kind == "missing":
            text = ""
        elif self.loading:
            text = tr("map_loading")

            if progress:
                text += f" {progress}%"
        elif self.view is None:
            text = ""
        else:
            text = QUrl(map_url(self.config)).host()

            if self.bridge_found:
                text += "  ·  " + tr("map_bridge_on")
            elif self.bridge_found is False:
                text += "  ·  " + tr("map_bridge_off")

            if self.external_notice:
                text += "  ·  " + self.external_notice

        if self.config.get("map_render") == "software":
            text += ("  ·  " if text else "") + tr("map_compat_on")

        self.status.setText(text)

    def on_external_request(self, url, outcome):
        """Show in the status line, until the next load, where the page
        asked to go and whether it was opened (see MapWebPage)."""
        if outcome == "opened":
            self.external_notice = tr("map_external_opened", url=url)
        elif outcome == "blocked":
            self.external_notice = tr("map_external_blocked", url=url)
        else:
            self.external_notice = tr("open_failed", target=url)

        self.update_status()

    def open_in_browser(self):
        """Open the map in the regular browser; without one, say so in the
        status line with the address to open by hand."""
        url = map_url(self.config)

        if not open_external(url):
            self.status.setText(tr("open_failed", target=url))

    # ---------- loading ----------

    def ensure_loaded(self):
        """Create the browser on first use (it is heavy)."""
        if self.view is not None or self.panel_kind == "missing":
            return

        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self.show_panel("missing")
            self.update_status()
            return

        page_class = _make_page_classes()

        self.profile = shared_profile()

        self.view = QWebEngineView()

        self.page = page_class(self.profile, self.view)

        self.page.setBackgroundColor(QColor(theme.BG))

        self.view.setPage(self.page)

        self.page.external_requested.connect(self.on_external_request)

        self.activation_filter = UserActivationFilter(
            self.view, self.page.note_user_activation
        )

        self.page.loadingChanged.connect(self.on_loading_changed)
        self.page.loadProgress.connect(self.on_load_progress)
        self.page.renderProcessTerminated.connect(self.on_render_crash)

        self.view_holder.addWidget(self.view)

        self.page.load(QUrl(map_url(self.config)))

    def reload(self):
        self.hide_panel()

        if self.view is None:
            self.ensure_loaded()
            return

        if self.page.url().isEmpty():
            self.page.load(QUrl(map_url(self.config)))
        else:
            self.page.triggerAction(self.page.WebAction.ReloadAndBypassCache)

    def load_source(self):
        """Open the configured map source (after it was changed)."""
        self.set_bridge_found(None)

        if self.view is None:
            self.update_status()
            return

        self.hide_panel()

        self.page.load(QUrl(map_url(self.config)))

    def on_loading_changed(self, info):
        """A load of the page started or ended (QWebEngineLoadingInfo).

        A navigation the page refused (to another origin, see MapWebPage)
        is reported too, as started and then stopped: it is not a load of
        the map and is ignored, otherwise the map would show the "failed"
        panel and stop its bridge poll after every link to another site.
        Only the reports with the map's origin count.
        """
        from PyQt6.QtWebEngineCore import QWebEngineLoadingInfo

        if self.page is None or url_origin(info.url()) != self.page.map_origin:
            return

        Status = QWebEngineLoadingInfo.LoadStatus

        if info.status() == Status.LoadStartedStatus:
            self.on_load_started()
            return

        # A load issued while a refused navigation is still being cancelled
        # (a reload right after it) is reported as started with the refused
        # address, so its start was ignored above: it starts here.
        if not self.loading:
            self.on_load_started()

        self.on_load_finished(info.status() == Status.LoadSucceededStatus)

    def on_load_started(self):
        self.loading = True

        self.weapon_baseline_pending = True

        self.external_notice = ""

        self.bridge_timer.stop()

        # The old page's answer may never come
        self.bridge_pending = False

        self.black_timer.stop()

        self.timeout_timer.start()

        self.progress.setValue(0)

        self.progress.show()

        self.update_status()

    def on_load_progress(self, value):
        self.progress.setValue(value)

        self.update_status(value)

    def on_load_finished(self, ok):
        self.loading = False

        self.timeout_timer.stop()

        self.progress.hide()

        self.update_status()

        if ok:
            if self.panel_kind in ("slow", "failed", "crashed"):
                self.hide_panel()

            self.black_timer.start()

            self.bridge_timer.start()
        else:
            # No page, no bridge: the status must not say targets go through
            self.set_bridge_found(None)

            self.show_panel("failed")

    def on_timeout(self):
        if self.loading:
            self.show_panel("slow")

    def on_render_crash(self, status, code):
        """The page's renderer died: stop polling the dead page (a reload
        starts it again) and drop its bridge state."""
        self.loading = False

        self.bridge_timer.stop()
        self.black_timer.stop()
        self.bridge_pending = False

        self.set_bridge_found(None)

        self.progress.hide()

        self.show_panel("crashed")

    # ---------- targets ----------

    def poll_targets(self):
        """Ask the page for its targets and weapon (see on_bridge_result);
        nothing while it loads or while the last question is unanswered."""
        if self.page is None or self.loading or self.bridge_pending:
            return

        self.bridge_pending = True

        self.page.runJavaScript(BRIDGE_SCRIPT, 0, self.on_bridge_result)

    def select_weapon(self, name):
        """Select weapon `name` on the loaded SquadCalc page, if it has it.

        The page then reports it back through the bridge; the calculator
        already has it, so nothing changes there. The name is kept and sent
        again after the page restarts (also when it is loading now).
        """
        self.app_weapon = name

        if self.page is None or self.loading:
            return

        self.page.runJavaScript(select_weapon_script(name), 0)

    def on_bridge_result(self, value):
        """Result of BRIDGE_SCRIPT: {targets, weapon}, None without bridge.

        Answers can arrive after `shutdown` (the window is closing); they
        are dropped.
        """
        self.bridge_pending = False

        if self.page is None:
            return

        state = parse_bridge(value)

        self.set_bridge_found(state is not None)

        targets, weapon = state if state is not None else ([], None)

        if state is not None and self.weapon_baseline_pending:
            self.weapon_baseline_pending = False

            self.last_weapon = weapon

            if self.app_weapon:
                self.page.runJavaScript(select_weapon_script(self.app_weapon), 0)

        # The weapon first: the targets are then solved for it.
        elif weapon is not None and weapon != self.last_weapon:
            self.last_weapon = weapon
            self.weapon_received.emit(weapon)

        if targets == self.last_targets:
            return

        self.last_targets = targets

        self.targets_received.emit(targets)

    def set_bridge_found(self, found):
        """Record whether the page has the bridge (None: unknown, no page)
        and show it. Back to unknown, the page's state is forgotten and its
        next answer is a baseline again."""
        if found == self.bridge_found:
            return

        self.bridge_found = found

        if found is None:
            self.last_targets = None
            self.last_weapon = None
            self.weapon_baseline_pending = True

        self.update_status()

    def check_black(self):
        if self.view is None or not self.view.isVisible() or self.loading:
            return

        if looks_black(self.view.grab().toImage()):
            self.show_panel("black")

    def shutdown(self):
        """Destroy the page and the view now, before the profile.

        Left to the garbage collector at exit, Chromium objects can be torn
        down in the wrong order and crash the process while it closes.
        """
        self.timeout_timer.stop()
        self.black_timer.stop()
        self.bridge_timer.stop()

        if self.view is None:
            return

        from PyQt6 import sip

        view, page = self.view, self.page

        self.view = self.page = self.profile = self.activation_filter = None

        self.view_holder.removeWidget(view)

        sip.delete(page)

        sip.delete(view)

    # ---------- help panel ----------

    def show_panel(self, kind):
        self.panel_kind = kind

        self.panel_title.setText(tr(f"map_{kind}_title"))

        self.panel_text.setText(
            tr(f"map_{kind}_text", host=QUrl(map_url(self.config)).host())
        )

        self.retry_button.setVisible(kind != "missing")

        self.compat_button.setVisible(
            kind != "missing" and self.config.get("map_render") != "software"
        )

        self.panel.show()

    def hide_panel(self):
        self.panel_kind = None

        self.panel.hide()
