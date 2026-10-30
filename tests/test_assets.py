"""Every file in assets/ is used: the app loads it or the README cites it."""

import glob
import os

from conftest import ROOT

ASSETS = os.path.join(ROOT, "assets")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def is_referenced(asset, sources):
    """`asset` (a path relative to the repository) is named by `sources`.

    A file is referenced by its name (`icon.ico`). A file in a subfolder can
    also be loaded by a computed path (f"assets/icons/{icon}.svg"): then a
    source that names the folder and quotes the file's stem counts.
    """
    folder, name = os.path.split(asset)
    stem = os.path.splitext(name)[0]

    for text in sources:
        if name in text:
            return True
        if folder != "assets" and folder + "/" in text and f'"{stem}"' in text:
            return True

    return False


def test_every_asset_is_referenced():
    sources = [read(path) for path in glob.glob(os.path.join(ROOT, "*.py"))]
    sources.append(read(os.path.join(ROOT, "README.md")))

    assets = [
        os.path.relpath(path, ROOT)
        for path in glob.glob(os.path.join(ASSETS, "**", "*"), recursive=True)
        if os.path.isfile(path)
    ]

    assert assets
    unused = [asset for asset in sorted(assets) if not is_referenced(asset, sources)]
    assert unused == []
