import os
import sys
import tempfile
import traceback

os.environ["QT_LOGGING_RULES"] = "*.debug=false"

from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox
)

try:
    # QtWebEngine must be imported before QApplication is created.
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from ballistics import (
    load_weapons,
    WeaponDataError
)

import config
from config import config_dir, load_config
from i18n import tr
from utils import resource_path
from splash import SplashScreen

from webmap import configure_environment


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


def install_crash_handler():
    """Show and log unexpected errors instead of silently closing.

    Started from a desktop launcher the app has no console, so without this
    a crash leaves no trace.
    """
    log_path = os.path.join(config_dir(), "crash.log")

    def handler(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))

        try:
            os.makedirs(config_dir(), exist_ok=True)

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass

        if QApplication.instance():
            QMessageBox.critical(
                None,
                tr("error_title"),
                f"{exc}\n\n" + tr("error_saved", path=log_path)
            )

    sys.excepthook = handler


def selftest():
    """Smoke test: python app.py --selftest

    Loads the data, opens the main window and runs a calculation for every
    weapon through the UI. Exit code 0 means everything works; otherwise the
    error is written to selftest.log next to app.py.
    """
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(sys.argv[0])),
        "selftest.log"
    )

    try:
        # Never touch the user's real settings (last weapon, recent list).
        config.CONFIG_PATH = os.path.join(
            tempfile.mkdtemp(prefix="sb-selftest-"),
            "config.json"
        )

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

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\nSELFTEST PASSED\n")

        return 0

    except Exception:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "SELFTEST FAILED\n")

        return 1


def main():
    if "--selftest" in sys.argv:
        return selftest()

    settings = load_config()

    # Browser switches and the Qt platform must be set before QApplication.
    configure_environment(settings["map_render"])

    prefer_x11()

    app = QApplication(sys.argv)

    install_crash_handler()

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

    from crosshair import MainWindow

    window = MainWindow(weapons)

    window.show()

    splash.close()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
