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
    pytest.importorskip("PyQt6.QtWebEngineCore")
    import webmap

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


def app_sources():
    """{file name: source} of the app's modules (not the tests)."""
    import glob

    sources = {}

    for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        with open(path, encoding="utf-8") as f:
            sources[os.path.basename(path)] = f.read()

    return sources


def test_every_signal_of_the_window_has_a_listener(qapp, tmp_path, monkeypatch):
    """A signal of the app's own classes that nothing in the app listens
    to is dead code (HoldTimer.changed, review 1.6.0 slice 1 #10)."""
    from PyQt6.QtCore import QObject, pyqtBoundSignal

    import config
    from ballistics import load_weapons
    from crosshair import MainWindow

    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    window = MainWindow(load_weapons(os.path.join(ROOT, "weapons.json")))
    modules = set(app_sources())
    # {"Class.signal": heard by some instance}
    heard = {}

    try:
        objects = [window, window.overlay] + window.findChildren(QObject)

        for item in objects:
            cls = type(item)

            if cls.__module__ + ".py" not in modules:
                continue

            for name in vars(cls):
                signal = getattr(item, name, None)

                if isinstance(signal, pyqtBoundSignal):
                    key = f"{cls.__name__}.{name}"
                    heard[key] = heard.get(key, False) or item.receivers(signal) > 0
    finally:
        window.close()

    # The scan found the signals (the picker, the sliders, the overlay, ...)
    assert len(heard) >= 8
    assert sorted(key for key, listened in heard.items() if not listened) == []


def test_the_tests_set_only_settings_the_app_has():
    """A test that sets a removed setting ("animated") tests nothing."""
    import glob
    import re

    from config import DEFAULT_CONFIG

    for path in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
        with open(path, encoding="utf-8") as f:
            source = f.read()

        for key in re.findall(r"\bconfig\[\"(\w+)\"\] = ", source):
            assert key in DEFAULT_CONFIG, f"{os.path.basename(path)}: {key}"


@pytest.mark.parametrize("file", ["crosshair.py", "widgets.py", "hotkeys.py"])
def test_the_public_interface_is_documented(file):
    """Review 1.6.0 slice 1 #9: every public class, function and method
    (not dunder methods) has a docstring."""
    import ast

    tree = ast.parse(app_sources()[file])
    missing = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.ClassDef)):
                continue

            if not child.name.startswith("_") and ast.get_docstring(child) is None:
                missing.append(prefix + child.name)

            if isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")

    walk(tree)

    assert missing == []


def test_the_readme_counts_the_weapon_entries():
    """The README says how many entries weapons.json has, in both languages."""
    import json
    import re

    with open(os.path.join(ROOT, "weapons.json"), encoding="utf-8") as f:
        entries = [name for name in json.load(f) if not name.startswith("_")]

    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()

    counts = re.findall(r"covers (\d+) weapon entries|В ней (\d+) позиций", readme)

    assert len(counts) == 2
    assert {int(n) for pair in counts for n in pair if n} == {len(entries)}
