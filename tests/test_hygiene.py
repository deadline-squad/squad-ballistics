"""The test run stays inside its own folders and off the network (see
conftest.py): nothing is written to the developer's ~/.config or ~/.cache
and the live SquadCalc is never loaded."""

import os

import pytest

import conftest
from conftest import ROOT


def real_home_dirs():
    home = os.path.expanduser("~")
    return [os.path.join(home, ".config"), os.path.join(home, ".cache")]


def test_settings_and_caches_live_in_the_test_folder():
    import config

    for path in (config.config_dir(), config.data_dir(), config.CONFIG_PATH):
        assert path.startswith(conftest.USER_DIRS + os.sep), path
        assert not any(path.startswith(real) for real in real_home_dirs())


def test_the_map_profile_lives_in_the_test_folder(qapp):
    webmap = pytest.importorskip("webmap")
    pytest.importorskip("PyQt6.QtWebEngineCore")

    profile = webmap.shared_profile()

    for path in (profile.persistentStoragePath(), profile.cachePath()):
        assert path.startswith(conftest.USER_DIRS + os.sep), path


def test_the_live_map_is_requested_in_name_only(qapp, tmp_path, monkeypatch):
    """The map page asks for the Deadline SquadCalc, and the request is
    refused before it leaves the machine."""
    pytest.importorskip("PyQt6.QtWebEngineWidgets")

    from PyQt6.QtCore import QCoreApplication, QElapsedTimer

    import config
    from ballistics import load_weapons
    from crosshair import MainWindow

    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    window = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    before = len(conftest.BLOCKED_URLS)

    try:
        window.set_page(3)
        assert window.map_page.page.requestedUrl().host() == "calc.tk104.duckdns.org"

        clock = QElapsedTimer()
        clock.start()
        while len(conftest.BLOCKED_URLS) == before and clock.elapsed() < 15000:
            QCoreApplication.processEvents()

        assert conftest.BLOCKED_URLS[before:] == ["https://calc.tk104.duckdns.org/"]
    finally:
        window.close()
