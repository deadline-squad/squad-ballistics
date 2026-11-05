"""Squad Ballistics entry point: `python app.py` starts the app,
`python app.py --selftest` runs the smoke test.

Startup order matters: Qt's logging rules, the browser switches and the Qt
platform are environment variables read when QApplication is created, so
they are set before it; the single-instance lock is taken before the
settings are read, so two starts never write the settings file at once.
"""

import os
import signal
import socket
import sys
import tempfile
import threading
import time
import traceback


def quiet_qt_logging(environ=None):
    """Hide Qt's debug messages unless the user set QT_LOGGING_RULES."""
    environ = os.environ if environ is None else environ

    environ.setdefault("QT_LOGGING_RULES", "*.debug=false")


quiet_qt_logging()

from PyQt6.QtCore import QLockFile, QSocketNotifier, QTimer  # noqa: E402

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QMessageBox
)

try:
    # QtWebEngine must be imported before QApplication is created.
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from ballistics import (  # noqa: E402
    load_weapons,
    WeaponDataError
)

import config  # noqa: E402
from config import config_dir, make_private_dir, read_config  # noqa: E402
from i18n import tr  # noqa: E402
from utils import resource_path  # noqa: E402
from splash import SplashScreen  # noqa: E402

from webmap import configure_environment, probe_gl_renderer  # noqa: E402

# crash.log is moved to crash.log.1 (replacing the older one) once it is
# bigger than this, so a crash loop cannot fill the disk.
CRASH_LOG_LIMIT = 256 * 1024

# How long a new instance waits for the lock: a restart from the settings
# starts the new process while the old one is still quitting.
INSTANCE_LOCK_WAIT_MS = 5000

INSTANCE_LOCK_NAME = "instance.lock"

# How long after the window is shown the embedded map is created (see
# `MainWindow.preload_map`): the window has painted by then and the user has
# not yet reached for the map.
MAP_PRELOAD_DELAY_MS = 300


def prefer_x11(environ=None):
    """Run through XWayland on a Wayland session.

    Wayland compositors ignore "stay on top" for ordinary windows, so the
    overlay would end up under a fullscreen game; through XWayland it stays
    on top and lets the mouse through, like on X11. Skipped when the user
    chose a Qt platform or there is no X server.
    """
    environ = os.environ if environ is None else environ

    if environ.get("QT_QPA_PLATFORM"):
        return

    if environ.get("WAYLAND_DISPLAY") and environ.get("DISPLAY"):
        environ["QT_QPA_PLATFORM"] = "xcb"


def write_crash_log(log_path, text, limit=CRASH_LOG_LIMIT):
    """Append `text` with a timestamp to `log_path`, moving a log bigger
    than `limit` bytes to `log_path` + ".1" first. The log and its folder
    are private (0600 and 0700, see `config.make_private_dir`): a traceback
    can name the user's paths. Errors are ignored: the log must never raise
    from inside the crash handler."""
    try:
        make_private_dir(os.path.dirname(log_path))

        if os.path.exists(log_path) and os.path.getsize(log_path) > limit:
            os.replace(log_path, log_path + ".1")

        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)

        # A log written by an older version keeps its mode through O_CREAT.
        os.fchmod(descriptor, 0o600)

        with os.fdopen(descriptor, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except OSError:
        pass


def crash_key(exc_type, tb):
    """What makes two crashes the same: the exception type and where it was
    raised (file, line, function of every frame), not its message, which
    often carries a changing value."""
    frames = tuple(
        (frame.filename, frame.lineno, frame.name)
        for frame in traceback.extract_tb(tb)
    )

    return exc_type, frames


def install_crash_handler(log_dir=None):
    """Show and log unexpected errors instead of silently closing.

    Started from a desktop launcher the app has no console, so without this
    a crash leaves no trace. A slot that raises on every timer tick would
    otherwise bury the screen in dialogs and the disk in log lines, so each
    distinct error (`crash_key`: its type and frames, whatever its message)
    is logged and shown once per run, and no dialog opens while another one
    is up (the dialog runs its own event loop, where the same slot keeps
    raising). The log is capped, see `write_crash_log`.

    Ctrl+C (KeyboardInterrupt) is no crash: it goes to Python's default
    hook. An error in a worker thread is logged through the same handler
    (`threading.excepthook`) but opens no dialog, since widgets belong to
    the main thread; a thread ended by SystemExit is ignored, as Python
    does.

    Returns the handler, which is also set as `sys.excepthook`.
    """
    log_path = os.path.join(log_dir or config_dir(), "crash.log")

    seen = set()
    dialog_open = False

    def handler(exc_type, exc, tb):
        nonlocal dialog_open

        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return

        key = crash_key(exc_type, tb)

        if key in seen:
            return

        seen.add(key)

        write_crash_log(log_path, "".join(traceback.format_exception(exc_type, exc, tb)))

        if dialog_open or not QApplication.instance():
            return

        if threading.current_thread() is not threading.main_thread():
            return

        dialog_open = True

        try:
            QMessageBox.critical(
                None,
                tr("error_title"),
                f"{exc}\n\n" + tr("error_saved", path=log_path)
            )
        finally:
            dialog_open = False

    def thread_handler(args):
        if issubclass(args.exc_type, SystemExit):
            return

        handler(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = handler
    threading.excepthook = thread_handler

    return handler


def acquire_instance_lock(lock_dir=None, wait_ms=INSTANCE_LOCK_WAIT_MS):
    """Lock `instance.lock` in the settings folder; None if another running
    instance holds it.

    Two instances would draw two overlays, poll every hotkey twice, create
    two virtual keyboards and race on config.json. The lock is held for the
    life of the process. Qt also holds a kernel lock on the file while the
    process lives, so a running instance keeps it however old it is, and a
    lock left by a process that is gone (a crash, a kill) is taken over.
    """
    lock_dir = lock_dir or config_dir()

    try:
        make_private_dir(lock_dir)
    except OSError:
        pass

    lock = QLockFile(os.path.join(lock_dir, INSTANCE_LOCK_NAME))

    if lock.tryLock(wait_ms):
        return lock

    if lock.error() != QLockFile.LockError.LockFailedError:
        # The folder is not writable: run unguarded rather than not at all.
        return lock

    return None


def install_signal_handlers(app, window):
    """Close `window` cleanly on SIGTERM, SIGINT and SIGHUP (logout,
    `kill`, Ctrl+C in a terminal, the terminal closed).

    closeEvent releases a key the app holds down in the game and saves the
    settings; the default handlers would kill the process without either.
    Python runs a signal handler only between bytecodes, which never happen
    while Qt's event loop waits, so the signal also writes to a socket that
    Qt watches (`signal.set_wakeup_fd`), which wakes the loop.

    Returns the objects that must stay alive while the app runs.
    """
    receiver, sender = socket.socketpair()

    receiver.setblocking(False)
    sender.setblocking(False)

    signal.set_wakeup_fd(sender.fileno(), warn_on_full_buffer=False)

    notifier = QSocketNotifier(
        receiver.fileno(),
        QSocketNotifier.Type.Read,
        app
    )

    def drain():
        try:
            receiver.recv(64)
        except OSError:
            pass

    notifier.activated.connect(drain)

    def stop(signum, frame):
        window.close()
        app.quit()

    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, stop)

    return receiver, sender, notifier


def selftest():
    """Smoke test: python app.py --selftest

    Loads the data, opens the main window and runs a calculation for every
    weapon through the UI. Exit code 0 means everything works. The report
    (an OK line per weapon, or the error) is printed and written to
    selftest.log in a new temporary folder, which is printed too; nothing is
    written into the app's folder or the user's settings.
    """
    work_dir = tempfile.mkdtemp(prefix="sb-selftest-")
    log_path = os.path.join(work_dir, "selftest.log")

    try:
        # Never touch the user's real settings (last weapon, recent list).
        config.CONFIG_PATH = os.path.join(work_dir, "config.json")

        configure_environment("auto")

        app = QApplication(sys.argv)

        weapons = load_weapons(
            resource_path("weapons.json")
        )

        from crosshair import MainWindow

        window = MainWindow(weapons)

        window.show()

        lines = []

        from ballistics import solve

        for name, weapon in weapons.items():
            # A distance the weapon can reach with its default arc
            # (some artillery cannot fire flat at short range).
            for fraction in (0.3, 0.6, 0.85):
                distance = max(
                    weapon.min_distance + 5,
                    min(weapon.max_range() * fraction, 1500)
                )

                if solve(weapon, distance).reachable:
                    break

            window.select_weapon(name)

            window.distance_entry.setText(f"{distance:.0f}")

            window.calculate()

            app.processEvents()

            solution = window.last_solution

            if solution is None or not solution.reachable:
                raise RuntimeError(
                    f"{name}: {window.status_text()} {window.sub_label.text()}"
                )

            lines.append(
                f"OK  {name}: {distance:.0f} m -> {solution.angle:.2f} deg"
            )

        window.close()

        report = "\n".join(lines) + "\nSELFTEST PASSED\n"
        status = 0

    except Exception:
        report = traceback.format_exc() + "SELFTEST FAILED\n"
        status = 1

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report + f"Log: {log_path}", flush=True)

    return status


def main():
    """Start the app; returns the process exit code."""
    if "--selftest" in sys.argv:
        return selftest()

    prefer_x11()

    lock = acquire_instance_lock()

    if lock is None:
        app = QApplication(sys.argv)

        QMessageBox.information(
            None,
            "Squad Ballistics",
            tr("already_running")
        )
        return 0

    settings, bad_config = read_config()

    # Browser switches must be set before QApplication. "auto" looks at
    # Qt's OpenGL (a few hundred milliseconds) to run the map without the
    # GPU path where OpenGL itself is software.
    configure_environment(settings["map_render"], probe=probe_gl_renderer)

    app = QApplication(sys.argv)

    # A restart (Settings → Map) starts the new process before this one has
    # finished quitting: let it in as soon as the quit begins.
    app.aboutToQuit.connect(lock.unlock)

    install_crash_handler()

    if bad_config is not None:
        QMessageBox.warning(
            None,
            "Squad Ballistics",
            tr("config_unreadable", path=bad_config)
        )

    try:
        weapons = load_weapons(
            resource_path("weapons.json")
        )
    except WeaponDataError as e:
        QMessageBox.critical(
            None,
            "Squad Ballistics",
            str(e)
        )
        return 1

    splash = SplashScreen()

    splash.show()

    app.processEvents()

    try:
        from crosshair import MainWindow

        window = MainWindow(weapons)

        # Before the window shows: once it is up, a SIGTERM closes it cleanly.
        app.signal_wakeup = install_signal_handlers(app, window)

        window.show()

        QTimer.singleShot(MAP_PRELOAD_DELAY_MS, window.preload_map)
    finally:
        # An error in MainWindow goes to the crash dialog, which the splash
        # (always on top) would otherwise cover.
        splash.close()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
