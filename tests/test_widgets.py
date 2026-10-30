"""The input widgets on their own: the segmented control, the weapon
picker's search and pick, and the mouse wheel on number fields."""

import pytest

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication

from widgets import NumberEdit, Segmented, WeaponPicker

GROUPS = [
    ("launchers", ["RPG-7V1 · HEAT", "RPG-29", "AT-4"]),
    ("agl", ["MK19", "AGS-17 · emplacement"]),
]


def test_each_segment_reports_its_own_key(qapp):
    control = Segmented([("auto", "Auto"), ("low", "Low"), ("high", "High")], "auto")
    keys = []
    control.changed.connect(keys.append)

    for key in ("low", "auto", "high"):
        control.buttons[key].click()

    assert keys == ["low", "auto", "high"]
    assert control.buttons["high"].isChecked()
    assert not control.buttons["auto"].isChecked()


def picker_with_data(recent=()):
    picker = WeaponPicker()
    picker.set_data(GROUPS, list(recent))
    return picker


def listed(picker):
    """The weapon names in the open list, without the section headers."""
    names = []
    widget = picker.popup.list
    for row in range(widget.count()):
        name = widget.item(row).data(Qt.ItemDataRole.UserRole)
        if name:
            names.append(name)
    return names


def test_the_search_lists_only_matching_weapons(qapp):
    picker = picker_with_data(recent=["MK19"])
    picker.open_popup()

    assert listed(picker) == ["MK19", "RPG-7V1 · HEAT", "RPG-29", "AT-4", "MK19", "AGS-17 · emplacement"]

    picker.popup.search.setText("rpg")
    assert listed(picker) == ["RPG-7V1 · HEAT", "RPG-29"]

    picker.popup.search.setText("AGS")
    assert listed(picker) == ["AGS-17 · emplacement"]

    picker.popup.search.setText("no such gun")
    assert listed(picker) == []
    picker.popup.hide()


def test_enter_in_the_search_picks_the_first_match(qapp):
    picker = picker_with_data()
    changed = []
    picker.changed.connect(changed.append)
    picker.open_popup()

    picker.popup.search.setText("29")
    picker.popup.search.returnPressed.emit()

    assert changed == ["RPG-29"]
    assert picker.current == "RPG-29"
    assert not picker.popup.isVisible()


def test_clicking_a_weapon_picks_it_and_headers_pick_nothing(qapp):
    picker = picker_with_data()
    picked = []
    picker.popup.picked.connect(picked.append)
    picker.open_popup()

    header = picker.popup.list.item(0)
    picker.popup.pick_item(header)
    assert picked == []

    item = picker.popup.list.findItems("AT-4", Qt.MatchFlag.MatchExactly)[0]
    picker.popup.list.itemClicked.emit(item)

    assert picked == ["AT-4"]
    assert picker.current == "AT-4"
    picker.popup.hide()


def wheel(edit, notches, modifiers=Qt.KeyboardModifier.NoModifier):
    event = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120 * notches),
        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False
    )
    QApplication.sendEvent(edit, event)


@pytest.mark.parametrize("notches, modifiers, expected", [
    (1, Qt.KeyboardModifier.NoModifier, 525),
    (-1, Qt.KeyboardModifier.NoModifier, 475),
    (2, Qt.KeyboardModifier.NoModifier, 550),
    (1, Qt.KeyboardModifier.ShiftModifier, 502.5),
    (-1, Qt.KeyboardModifier.ControlModifier, 250),
])
def test_the_wheel_steps_up_away_from_the_user(qapp, notches, modifiers, expected):
    edit = NumberEdit(step=25)
    edit.set_value(500)
    stepped = []
    edit.stepped.connect(lambda: stepped.append(1))

    wheel(edit, notches, modifiers)

    assert edit.value() == expected
    assert stepped == [1]


def test_the_wheel_never_takes_a_distance_below_zero(qapp):
    edit = NumberEdit(step=25)
    edit.set_value(10)

    wheel(edit, -1)

    assert edit.value() == 0
