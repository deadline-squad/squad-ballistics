"""Every `tr()` call of the app names an existing text and fills its placeholders."""

import ast
import glob
import os
import re
from string import Formatter

from conftest import ROOT
from i18n import STRINGS, category_name, tr

# Texts picked by a computed id: f"hk_{action}", f"style_{key}", ...
COMPUTED_PREFIXES = ("arc_", "cat_", "hk_", "style_", "map_")


def placeholders(text):
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def tr_calls():
    """(file, line, id node, keyword names) of every tr() call in the app."""
    calls = []

    for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        if os.path.basename(path) == "i18n.py":
            continue

        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args:
                keywords = {k.arg for k in node.keywords}
                calls.append((os.path.basename(path), node.lineno, node.args[0], keywords))

    return calls


def literal_ids(node):
    """The ids a tr() argument can take: a constant, or both sides of `a if c else b`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]

    if isinstance(node, ast.IfExp):
        return literal_ids(node.body) + literal_ids(node.orelse)

    return []


def test_the_calls_were_found():
    assert len(tr_calls()) > 100


def test_every_literal_id_exists_and_its_placeholders_match_the_call():
    for file, line, node, keywords in tr_calls():
        for key in literal_ids(node):
            where = f"{file}:{line} tr({key!r})"

            assert key in STRINGS, where
            assert placeholders(STRINGS[key]) == keywords, where


def test_computed_ids_have_texts_for_their_prefix():
    for file, line, node, _keywords in tr_calls():
        if isinstance(node, ast.JoinedStr):
            prefix = node.values[0].value if isinstance(node.values[0], ast.Constant) else ""

            assert any(prefix.startswith(p) or p.startswith(prefix) for p in COMPUTED_PREFIXES), f"{file}:{line}"
            assert any(key.startswith(prefix) for key in STRINGS), f"{file}:{line}"


def test_no_text_is_unused():
    used = set()
    names = set()

    for path in glob.glob(os.path.join(ROOT, "*.py")):
        if os.path.basename(path) == "i18n.py":
            continue

        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.add(node.value)

    for key in STRINGS:
        if key in names or key.startswith(COMPUTED_PREFIXES):
            used.add(key)

    assert sorted(set(STRINGS) - used) == []


def test_texts_are_plain_english_strings():
    for key, text in STRINGS.items():
        assert isinstance(text, str), key
        assert not re.search("[А-Яа-яЁё]", text), key


def test_tr_formats_and_passes_unknown_ids_through():
    assert tr("nav_calc") == "Calculator"
    assert tr("no such id") == "no such id"
    assert tr("how_hold_2", t="1.50") == "Hold S for 1.50 s, then release."
    assert category_name("grenade_launchers") == STRINGS["cat_grenade_launchers"]
    assert category_name("unknown") == "unknown"
