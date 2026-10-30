"""app.py: the crash handler, the splash, the single-instance lock, clean
shutdown on signals and the startup warning about an unreadable settings
file. The last tests start the real app on an X server (Xvfb)."""

import copy
import json
import os
import signal
import subprocess
import sys
import time

import pytest

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QMessageBox

import app
import config
from conftest import ROOT


@pytest.fixture
def dialogs(monkeypatch):
    """Messages shown with QMessageBox.critical/warning/information."""
    shown = []

    def record(kind):
        def show(parent, title, text):
            shown.append((kind, text))
            return QMessageBox.StandardButton.Ok
        return show

    for kind in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(record(kind)))

    return shown


@pytest.fixture
def excepthook():
    saved = sys.excepthook
    yield
    sys.excepthook = saved


def raise_from(where):
    """An exception whose traceback names `where`."""
    try:
        raise ValueError(f"bad value in {where}")
    except ValueError as e:
        return type(e), e, e.__traceback__


def test_qt_debug_logging_is_off_unless_the_user_chose_rules():
    environ = {}
    app.quiet_qt_logging(environ)
    assert environ["QT_LOGGING_RULES"] == "*.debug=false"

    environ = {"QT_LOGGING_RULES": "qt.qpa.*=true"}
    app.quiet_qt_logging(environ)
    assert environ["QT_LOGGING_RULES"] == "qt.qpa.*=true"


def test_a_repeating_error_shows_one_dialog_and_one_log_entry(tmp_path, dialogs, excepthook):
    handler = app.install_crash_handler(str(tmp_path))
    assert sys.excepthook is handler

    # A slot that raises on every timer tick.
    error = raise_from("tick")
    for _ in range(50):
        handler(*error)

    assert len(dialogs) == 1
    assert dialogs[0][0] == "critical"
    assert "bad value in tick" in dialogs[0][1]
    assert str(tmp_path / "crash.log") in dialogs[0][1]

    log = (tmp_path / "crash.log").read_text()
    assert log.count("Traceback") == 1

    # A different error is still reported.
    handler(*raise_from("other slot"))
    assert len(dialogs) == 2
    assert (tmp_path / "crash.log").read_text().count("Traceback") == 2


def test_no_dialog_opens_while_one_is_up(tmp_path, monkeypatch, excepthook):
    """The dialog runs its own event loop, where other slots keep raising:
    their errors are logged, not stacked into more dialogs."""
    opened = []

    def critical(parent, title, text):
        opened.append(text)
        handler(*raise_from(f"inside dialog {len(opened)}"))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(critical))
    handler = app.install_crash_handler(str(tmp_path))

    handler(*raise_from("first"))

    assert len(opened) == 1
    log = (tmp_path / "crash.log").read_text()
    assert "first" in log and "inside dialog 1" in log

    # Once it is closed the next new error gets its dialog.
    handler(*raise_from("later"))
    assert len(opened) == 2


def test_the_crash_log_is_capped(tmp_path):
    log = tmp_path / "crash.log"
    log.write_text("x" * (app.CRASH_LOG_LIMIT + 1))

    app.write_crash_log(str(log), "Traceback: new")

    assert (tmp_path / "crash.log.1").stat().st_size == app.CRASH_LOG_LIMIT + 1
    assert "Traceback: new" in log.read_text()
    assert log.stat().st_size < 100

    # A full log replaces the older rotated one: two files at most.
    log.write_text("y" * (app.CRASH_LOG_LIMIT + 1))
    app.write_crash_log(str(log), "Traceback: newer")
    assert (tmp_path / "crash.log.1").read_text()[0] == "y"
    assert sorted(os.listdir(tmp_path)) == ["crash.log", "crash.log.1"]


def test_the_crash_log_never_raises(tmp_path):
    folder = tmp_path / "file"
    folder.write_text("not a folder")

    app.write_crash_log(str(folder / "crash.log"), "Traceback")


def test_the_splash_style_is_scoped_and_its_corners_transparent(qapp):
    from PyQt6.QtCore import Qt

    from splash import SplashScreen

    splash = SplashScreen()

    assert splash.styleSheet() == ""
    assert splash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert splash.card.objectName() == "splash"
    assert "QFrame#splash" in splash.card.styleSheet()

    image = splash.grab().toImage()
    assert image.pixelColor(1, 1).alpha() == 0
    centre = image.pixelColor(splash.width() // 2, 15)
    assert (centre.name(), centre.alpha()) == ("#070707", 255)

    splash.close()


class StubSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class StubApp:
    """Stands in for QApplication in main(): the test run has its own."""

    def __init__(self, argv):
        self.aboutToQuit = StubSignal()

    def processEvents(self):
        QApplication.processEvents()

    def exec(self):
        return 0


class StubLock:
    def __init__(self):
        self.locked = True

    def unlock(self):
        self.locked = False


@pytest.fixture
def main_parts(monkeypatch, excepthook):
    """main() with stand-ins for what the test process cannot do twice."""
    lock = StubLock()
    monkeypatch.setattr(app, "QApplication", StubApp)
    monkeypatch.setattr(app, "acquire_instance_lock", lambda: lock)
    monkeypatch.setattr(app, "install_signal_handlers", lambda application, window: None)
    monkeypatch.setattr(app, "configure_environment", lambda mode: None)
    monkeypatch.setattr(app, "prefer_x11", lambda: None)
    monkeypatch.setattr(sys, "argv", ["app.py"])
    return lock


def test_a_failing_main_window_does_not_leave_the_splash_over_the_error(main_parts, monkeypatch, dialogs):
    import crosshair
    import splash

    splashes = []

    class Splash(splash.SplashScreen):
        def __init__(self):
            super().__init__()
            splashes.append(self)

    def broken(weapons):
        raise RuntimeError("main window failed")

    monkeypatch.setattr(app, "SplashScreen", Splash)
    monkeypatch.setattr(crosshair, "MainWindow", broken)

    with pytest.raises(RuntimeError, match="main window failed"):
        app.main()

    assert len(splashes) == 1
    assert not splashes[0].isVisible()


def test_a_second_start_says_so_and_exits_without_touching_the_settings(monkeypatch, dialogs):
    monkeypatch.setattr(app, "QApplication", StubApp)
    monkeypatch.setattr(app, "acquire_instance_lock", lambda: None)
    monkeypatch.setattr(app, "read_config", lambda: pytest.fail("settings read"))
    monkeypatch.setattr(app, "prefer_x11", lambda: None)

    assert app.main() == 0
    assert dialogs == [("information", app.tr("already_running"))]


def test_an_unreadable_settings_file_is_kept_and_reported(main_parts, monkeypatch, dialogs, tmp_path):
    import crosshair

    path = tmp_path / "config.json"
    path.write_text('{"fov": 100, "mark_size": 120')
    monkeypatch.setattr(config, "CONFIG_PATH", str(path))
    windows = []

    class Window:
        def __init__(self, weapons):
            windows.append(self)

        def show(self):
            pass

    monkeypatch.setattr(crosshair, "MainWindow", Window)

    assert app.main() == 0

    bad = str(path) + ".bad"
    assert dialogs == [("warning", app.tr("config_unreadable", path=bad))]
    with open(bad) as f:
        assert f.read() == '{"fov": 100, "mark_size": 120'
    assert json.loads(path.read_text()) == config.DEFAULT_CONFIG
    assert windows


def test_the_lock_is_released_when_quitting_begins(main_parts, monkeypatch, dialogs, tmp_path):
    import crosshair

    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    apps = []

    class App(StubApp):
        def __init__(self, argv):
            super().__init__(argv)
            apps.append(self)

    class Window:
        def __init__(self, weapons):
            pass

        def show(self):
            pass

    monkeypatch.setattr(app, "QApplication", App)
    monkeypatch.setattr(crosshair, "MainWindow", Window)

    assert app.main() == 0

    for slot in apps[0].aboutToQuit.slots:
        slot()
    assert not main_parts.locked
    assert dialogs == []


HOLDER = """
import sys, time
sys.path.insert(0, {root!r})
import app
lock = app.acquire_instance_lock({folder!r}, 0)
print("locked" if lock is not None else "busy", flush=True)
time.sleep(60)
"""


def hold_lock(folder):
    """A process that holds the instance lock in `folder` until killed."""
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER.format(root=ROOT, folder=str(folder))],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout.readline().strip() == "locked"
    return holder


def test_only_one_instance_holds_the_lock(tmp_path):
    holder = hold_lock(tmp_path)

    try:
        assert app.acquire_instance_lock(str(tmp_path), 200) is None

        # A lock older than Qt's default 30 s stale time is still held.
        lock_file = tmp_path / app.INSTANCE_LOCK_NAME
        old = time.time() - 3600
        os.utime(lock_file, (old, old))
        assert app.acquire_instance_lock(str(tmp_path), 200) is None
    finally:
        holder.kill()
        holder.wait(10)

    # The holder is gone (a crash or kill -9): its lock is taken over.
    lock = app.acquire_instance_lock(str(tmp_path), 200)
    assert lock is not None and lock.isLocked()
    lock.unlock()


def test_a_restart_waits_for_the_old_instance_to_quit(tmp_path):
    holder = hold_lock(tmp_path)
    started = time.monotonic()

    try:
        # The old instance quits a moment after starting the new one.
        subprocess.Popen(["sh", "-c", f"sleep 0.5; kill {holder.pid}"])
        lock = app.acquire_instance_lock(str(tmp_path), 5000)
    finally:
        holder.kill()
        holder.wait(10)

    assert lock is not None
    assert time.monotonic() - started < 5
    lock.unlock()


class FakeWindow(QObject):
    closed = pyqtSignal()

    def close(self):
        self.closed.emit()


@pytest.fixture
def restore_signals():
    handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    yield
    signal.set_wakeup_fd(-1)
    for number, handler in handlers.items():
        signal.signal(number, handler)


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT])
def test_a_termination_signal_closes_the_window_and_quits(qapp, monkeypatch, restore_signals, number):
    window = FakeWindow()
    events = []
    window.closed.connect(lambda: events.append("closed"))
    monkeypatch.setattr(qapp, "quit", lambda: events.append("quit"))

    keep = app.install_signal_handlers(qapp, window)

    os.kill(os.getpid(), number)

    deadline = time.monotonic() + 5
    while not events and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    assert events == ["closed", "quit"]

    for item in keep[:2]:
        item.close()


def test_closing_releases_the_keys_even_when_saving_fails(qapp, tmp_path, monkeypatch):
    """closeEvent lets go of a key held in the game before anything that
    may raise, and saves the settings even if releasing fails."""
    import crosshair
    from ballistics import load_weapons

    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    window = crosshair.MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    events = []

    monkeypatch.setattr(window, "drop_auto_hold", lambda: events.append("released"))

    def broken_save(settings, path=None):
        events.append("save")
        raise TypeError("not serialisable")

    monkeypatch.setattr(crosshair, "save_config", broken_save)

    with pytest.raises(TypeError):
        window.closeEvent(QCloseEvent())

    assert events == ["released", "save"]

    def broken_release():
        events.append("release failed")
        raise OSError("uinput gone")

    saved = []
    monkeypatch.setattr(window, "drop_auto_hold", broken_release)
    monkeypatch.setattr(crosshair, "save_config", lambda settings, path=None: saved.append(1))

    with pytest.raises(OSError):
        window.closeEvent(QCloseEvent())

    assert saved == [1]

    monkeypatch.undo()
    window.close()


def start_app(display, config_home, *args):
    env = dict(
        os.environ,
        DISPLAY=display,
        QT_QPA_PLATFORM="xcb",
        XDG_CONFIG_HOME=str(config_home),
        XDG_CACHE_HOME=str(config_home / "cache"),
    )
    return subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "app.py"), *args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ), env


def xdotool_output(env, *args):
    result = subprocess.run(["xdotool", *args], env=env, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def window_title(window, env):
    return xdotool_output(env, "getwindowname", window)


def windows_of(process, env, name=""):
    """X window ids the process has mapped whose title matches `name`.

    `xdotool search --pid` also lists the root window, which has no pid:
    only windows that name the process as theirs are kept.
    """
    found = xdotool_output(env, "search", "--onlyvisible", "--pid", str(process.pid), "--name", name)
    return [
        window for window in found.split()
        if xdotool_output(env, "getwindowpid", window) == str(process.pid)
    ]


def wait_for(condition, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def xdotool():
    import shutil

    if not shutil.which("xdotool"):
        pytest.skip("xdotool is not installed")


def test_the_real_app_saves_on_sigterm_and_refuses_a_second_copy(xvfb_display, xdotool, tmp_path):
    folder = tmp_path / "SquadBallistics"
    folder.mkdir()
    settings = folder / "config.json"
    # A compact file from an older version: a clean close rewrites it whole.
    settings.write_text(json.dumps({"fov": 103, "mark_size": 120}, separators=(",", ":")))

    first, env = start_app(xvfb_display, tmp_path)

    try:
        assert wait_for(lambda: windows_of(first, env, "^Squad Ballistics$")), first.stdout.read() if first.poll() is not None else "no window"

        second, _env = start_app(xvfb_display, tmp_path)
        try:
            assert wait_for(lambda: windows_of(second, env)), "no message from the second copy"
            # Only the message: no main window, no overlay.
            assert len(windows_of(second, env)) == 1
            box = windows_of(second, env)[0]
            assert window_title(box, env) == "Squad Ballistics"
            subprocess.run(["xdotool", "windowfocus", "--sync", box], env=env, timeout=30)
            subprocess.run(["xdotool", "key", "Return"], env=env, timeout=30)
            assert second.wait(30) == 0
        finally:
            second.kill()

        assert first.poll() is None

        first.send_signal(signal.SIGTERM)
        assert first.wait(30) == 0, first.stdout.read()
    finally:
        first.kill()

    saved = json.loads(settings.read_text())
    expected = copy.deepcopy(config.DEFAULT_CONFIG)
    expected.update(fov=103, mark_size=120)
    assert saved == expected
    assert not (folder / "config.json.bad").exists()
