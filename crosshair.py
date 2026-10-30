import copy
import math
import os
import sys


from PyQt6.QtCore import (
    Qt,
    QProcess,
    QSize,
    QTimer,
    QUrl
)

from PyQt6.QtGui import (
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QPixmap
)

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget
)

import theme

from dataclasses import replace

from ballistics import (
    MILS_PER_DEGREE,
    TRIM_LIMIT,
    clamp_trim,
    current_weapon_name,
    first_obstacle,
    solve,
    mark_offset,
    range_ladder,
    screen_offset,
    trajectory,
    trim_for_landing
)

from beep import beep

from config import (
    APP_VERSION,
    DEFAULT_CONFIG,
    DISTANCE_STEPS,
    MARK_COLORS,
    MARK_STYLES,
    RANGES,
    config_dir,
    load_config,
    save_config,
)

from holdtimer import HoldTimer

from hotkeys import (
    ACTIONS,
    KEYS,
    bindings,
    setup_hotkeys,
    teardown_hotkeys
)

from i18n import tr

from keyinject import AutoHold, system_key_injector

from keystate import KEY_A, KEY_D, KEY_S, KEY_W, system_key_reader

from overlay import Overlay

from compassreader import DigitReader
from sightlay import MAX_MOVES, BEARING, CompassReader, ScreenSight, SightLayer, read_sight

from sightreader import LabelTemplates

from utils import resource_path

from webmap import MapPage, map_url, open_external

from widgets import (
    CrosshairPreview,
    NumberEdit,
    Segmented,
    SliderRow,
    StatTile,
    Swatches,
    Toggle,
    TrajectoryView,
    WeaponPicker,
    card,
    format_angle,
    label,
    repolish
)

# Extra W time of a mortar auto-lay past the full travel of the barrel: the
# barrel stops at its top, so holding longer only makes sure it got there.
LAY_RESET_MARGIN = 0.3

# Auto-lay calibration: S held at least this long (a short hold measures the
# rate poorly), and a fitted rate within this fraction of weapons.json's
# (a typo in the mils would give an absurd one).
LAY_CALIBRATION_MIN_HOLD = 0.5
LAY_RATE_TOLERANCE = 0.3

# How often the mortar sight is read while a mortar is selected (ms), and
# where a grab it could not read is saved (in the settings folder).
SIGHT_WATCH_MS = 300
SIGHT_GRAB_FILE = "sight-grab.png"

# The hotkey hint under the inputs: no-break spaces keep a "key — action"
# entry together, the line may break only after the separator's dot.
NBSP = "\u00a0"
HINT_SEPARATOR = NBSP * 3 + "·   "

# The settings that align the mark with the in-game sight.
ALIGNMENT_KEYS = ("center_offset_x", "center_offset_y", "offset_scale")


def scrolled(widget, width=None):
    """Wrap a widget in a transparent vertical scroll area."""
    scroll = QScrollArea()

    scroll.setWidgetResizable(True)

    scroll.setFrameShape(QFrame.Shape.NoFrame)

    scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    content = QWidget()

    content.setObjectName("scrollContent")

    layout = QVBoxLayout(content)

    layout.setContentsMargins(0, 0, 0, 0)

    layout.addWidget(widget)

    if width:
        # Room for the scrollbar so the content is never clipped.
        scroll.setFixedWidth(width + 14)

        layout.setContentsMargins(0, 0, 14, 0)

        layout.addStretch()

    scroll.setWidget(content)

    scroll.viewport().setAutoFillBackground(False)

    return scroll


class MainWindow(QMainWindow):
    def __init__(self, weapons):
        super().__init__()

        # weapons.json as loaded; `weapons` may carry calibrated hold rates
        self.file_weapons = weapons
        self.weapons = dict(weapons)

        self.config = load_config()

        # Trims of weapons that weapons.json no longer has are dropped.
        self.config["mark_trim"] = {
            key: trim
            for key, trim in self.config["mark_trim"].items()
            if key in self.weapons
        }

        self.apply_lay_rates()

        self.last_solution = None

        # Direct-fire (low arc) solution of a hold weapon while it lobs,
        # for the overlay mark; None otherwise.
        self.direct_solution = None

        self.current_steps = []

        # Created once and kept across UI rebuilds, so the map is not
        # reloaded when the UI is rebuilt.
        self.map_page = None

        self.overlay = Overlay(
            self.config
        )

        # A resolution change or a monitor plugged in or out moves the
        # overlay: the mark and the ladder follow the new screen size.
        self.overlay.screen_changed.connect(self.recalculate_if_ready)

        # The SquadCalc target currently in the inputs; None once the
        # distance or height is edited by hand.
        self.map_target = None

        # The newest target the map delivered, kept after a manual edit so a
        # re-delivery of the same target does not overwrite typed values.
        self.last_map_target = None

        # Text of the overlay label for the current solution; mortars append
        # the bearing and the sight reading to it.
        self.info_base = ""
        self.sight_info = ""

        # Mortar sight on the screen: digit pictures (made on first use),
        # the grabber, and the lay on the sight (with the key injectors).
        self.sight_templates = None
        self.screen_sight = ScreenSight(self.overlay)
        self.sight_layer = None

        # The lay's first part for a map target: the bearing on the HUD
        # compass, turned with D and A (None without the key injectors).
        self.bearing_layer = None
        self.bearing_info = ""
        self.own_compass_reader = None

        # Why the auto-lay key did nothing or the last lay stopped short
        # (overlay); kept until the key is pressed again or the weapon
        # changes.
        self.lay_info = ""

        self.sight_timer = QTimer(self)
        self.sight_timer.setInterval(SIGHT_WATCH_MS)
        self.sight_timer.timeout.connect(self.watch_sight)

        # Physical keys read system-wide (None where impossible): the hold
        # timer and the in-game hotkeys use it.
        self.key_reader = system_key_reader()

        self.hold_timer = HoldTimer(self.key_reader, self)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(
            lambda: save_config(self.config)
        )

        self.calc_timer = QTimer(self)
        self.calc_timer.setSingleShot(True)
        self.calc_timer.setInterval(120)
        self.calc_timer.timeout.connect(
            lambda: self.calculate(show_errors=False)
        )

        self.setWindowTitle("Squad Ballistics")

        icon_path = resource_path("assets/icon.ico")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumSize(900, 600)

        # Within the screen it opens on (1080p at 150 % is 1280×720), with
        # room for the title bar, and centred on it.
        available = self.screen().availableGeometry()
        title_bar = 40

        self.resize(
            min(1180, available.width()),
            min(780, available.height() - title_bar)
        )

        self.move(
            available.x() + max(0, (available.width() - self.width()) // 2),
            available.y() + max(0, (available.height() - title_bar - self.height()) // 2)
        )

        if self.config["main_on_top"]:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Before the UI: a saved "on" that cannot work here is turned off
        # first, so the settings toggle shows it off.
        self.apply_auto_hold()

        self.build_ui()

        self.watch_monitors()

        # Only after the UI exists: a hotkey may fire right away.
        setup_hotkeys(self)

    # =========================
    # LAYOUT
    # =========================

    def build_ui(self):
        self.setStyleSheet(theme.stylesheet())

        root = QWidget()

        root.setObjectName("root")

        layout = QHBoxLayout(root)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        self.controls = {}

        self.pages = QStackedWidget()

        self.pages.addWidget(self.build_calc_page())
        self.pages.addWidget(self.build_crosshair_page())
        self.pages.addWidget(self.build_settings_page())
        self.pages.addWidget(self.build_web_page())

        layout.addWidget(self.build_sidebar())
        layout.addWidget(self.pages)

        self.setCentralWidget(root)

        self.on_weapon_changed(self.picker.current, user=False)

        self.update_map_status()

    def rebuild(self):
        """Recreate the UI (texts and bindings), keeping the inputs."""
        page = self.pages.currentIndex()

        texts = (
            self.distance_entry.text(),
            self.height_entry.text(),
            self.fov_entry.text()
        )

        if self.map_page is not None:
            # Detach the map so it survives the old pages being deleted.
            self.pages.removeWidget(self.map_page)
            self.map_page.setParent(None)

        self.build_ui()

        self.distance_entry.setText(texts[0])
        self.height_entry.setText(texts[1])
        self.fov_entry.setText(texts[2])

        self.set_page(page)

        self.recalculate_if_ready()

    def build_sidebar(self):
        sidebar = QFrame()

        sidebar.setObjectName("sidebar")

        sidebar.setFixedWidth(64)

        layout = QVBoxLayout(sidebar)

        layout.setContentsMargins(8, 14, 8, 14)

        layout.setSpacing(8)

        logo_path = resource_path("assets/icon.ico")

        if os.path.exists(logo_path):
            logo = label("")
            logo.setPixmap(
                QPixmap(logo_path).scaled(
                    32, 32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)
            layout.addSpacing(10)

        self.nav_buttons = []

        # Font Awesome Free 5.15.4 solid icons (CC BY 4.0, attribution in
        # each file), tinted with theme.TEXT. Files instead of qtawesome,
        # whose import and fonts cost ~0.2 s of the start for four icons.
        for index, (icon, key) in enumerate([
            ("bullseye", "nav_calc"),
            ("crosshairs", "nav_crosshair"),
            ("sliders-h", "nav_settings"),
            ("map", "nav_web")
        ]):
            button = QPushButton()

            button.setObjectName("nav")

            button.setIcon(QIcon(resource_path(f"assets/icons/{icon}.svg")))

            button.setIconSize(QSize(20, 20))

            button.setFixedSize(48, 44)

            button.setCheckable(True)

            button.setToolTip(tr(key))

            # Icon only: screen readers need the page's name
            button.setAccessibleName(tr(key))

            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.clicked.connect(
                lambda _checked, i=index: self.set_page(i)
            )

            layout.addWidget(button)

            self.nav_buttons.append(button)

        layout.addStretch()

        version = label(f"v{APP_VERSION}", "small")

        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(version)

        self.nav_buttons[0].setChecked(True)

        return sidebar

    def set_page(self, index):
        # The map in the regular browser; the embedded one when it can't open.
        if index == 3 and self.config["map_external"] \
                and open_external(map_url(self.config)):
            index = self.pages.currentIndex()

        self.pages.setCurrentIndex(index)

        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

        if index == 3:
            self.map_page.ensure_loaded()

    # =========================
    # CALCULATOR PAGE
    # =========================

    def weapon_groups(self):
        groups = {}

        for name, weapon in self.weapons.items():
            groups.setdefault(weapon.category, []).append(name)

        return list(groups.items())

    def recent_weapons(self):
        return [
            name for name in self.config["recent_weapons"]
            if name in self.weapons
        ]

    def build_calc_page(self):
        page = QWidget()

        layout = QHBoxLayout(page)

        layout.setContentsMargins(24, 24, 24, 24)

        layout.setSpacing(18)

        layout.addWidget(self.build_target_card(), 0)
        layout.addWidget(self.build_solution_card(), 1)

        return scrolled(page)

    def build_target_card(self):
        frame, layout = card()

        frame.setFixedWidth(380)

        layout.addWidget(label(tr("target"), "title"))

        layout.addWidget(label(tr("weapon").upper(), "section"))

        self.picker = WeaponPicker()

        self.picker.set_data(self.weapon_groups(), self.recent_weapons())

        # Vehicles and mounts are named in the notes: "M1117" finds "MK19".
        self.picker.set_notes({name: weapon.note for name, weapon in self.weapons.items()})

        # A saved weapon that weapons.json no longer has falls back to the first.
        current = self.config["last_weapon"]

        if current not in self.weapons:
            current = next(iter(self.weapons))

        self.picker.set_current(current, emit=False)

        self.picker.changed.connect(self.on_weapon_changed)

        layout.addWidget(self.picker)

        self.weapon_info = label("", "small")

        self.weapon_info.setWordWrap(True)

        layout.addWidget(self.weapon_info)

        self.arc_control = Segmented(
            [
                ("auto", tr("arc_auto")),
                ("low", tr("arc_low")),
                ("high", tr("arc_high"))
            ],
            self.config["arc"]
        )

        self.arc_control.changed.connect(self.on_arc_changed)

        layout.addWidget(self.arc_control)

        self.distance_entry = NumberEdit(
            allow_negative=False,
            step=self.config["distance_step"]
        )

        self.height_entry = NumberEdit(allow_negative=True, step=1)

        self.height_entry.setPlaceholderText(tr("height_hint"))

        self.fov_entry = NumberEdit(allow_negative=False, step=1)

        self.fov_entry.setPlaceholderText(tr("fov_hint"))

        self.fov_entry.set_value(self.config["fov"])

        for caption, entry in (
            (tr("distance"), self.distance_entry),
            (tr("height"), self.height_entry),
            (tr("fov"), self.fov_entry)
        ):
            layout.addWidget(label(caption.upper(), "section"))

            layout.addWidget(entry)

            entry.textEdited.connect(self.on_input_edited)

            entry.stepped.connect(self.calc_timer.start)

            if entry is not self.fov_entry:
                entry.stepped.connect(self.forget_map_target)

            entry.returnPressed.connect(lambda: self.calculate())

        self.map_label = label("", "small")

        self.map_label.setWordWrap(True)

        layout.addWidget(self.build_trim_box())

        layout.addWidget(self.map_label)

        buttons = QHBoxLayout()

        self.calc_button = QPushButton(tr("calculate"))

        self.calc_button.clicked.connect(lambda: self.calculate())

        self.calc_button.setVisible(not self.config["auto_calc"])

        reset_button = QPushButton(tr("reset_aim"))

        reset_button.setProperty("flat_style", True)

        reset_button.clicked.connect(lambda: self.reset_offset())

        buttons.addWidget(self.calc_button, 2)
        buttons.addWidget(reset_button, 1)

        layout.addSpacing(4)
        layout.addLayout(buttons)

        layout.addStretch()

        self.hotkey_hint = label("", "small")

        self.hotkey_hint.setWordWrap(True)

        self.update_hotkey_hint()

        layout.addWidget(self.hotkey_hint)

        return frame

    def build_trim_box(self):
        """The field correction of the mark: the trim of the weapon and view,
        and the landing that sets it. Shown for weapons aimed with the overlay."""
        self.trim_box = QWidget()

        column = QVBoxLayout(self.trim_box)

        column.setContentsMargins(0, 0, 0, 0)

        column.setSpacing(10)

        self.trim_entry = NumberEdit(allow_negative=True, step=0.05)

        self.trim_entry.setPlaceholderText(tr("trim_hint"))

        self.trim_entry.textEdited.connect(self.on_trim_edited)

        self.trim_entry.stepped.connect(self.on_trim_edited)

        self.landed_entry = NumberEdit(allow_negative=False, step=self.config["distance_step"])

        self.landed_entry.setPlaceholderText(tr("landed_hint"))

        self.landed_entry.returnPressed.connect(self.apply_landing)

        apply_button = QPushButton(tr("trim_apply"))

        apply_button.clicked.connect(lambda: self.apply_landing())

        reset_button = QPushButton(tr("trim_reset"))

        reset_button.setProperty("flat_style", True)

        reset_button.clicked.connect(lambda: self.reset_trim())

        for caption, entry, button in (
            (tr("trim"), self.trim_entry, reset_button),
            (tr("landed"), self.landed_entry, apply_button)
        ):
            column.addWidget(label(caption.upper(), "section"))

            row = QHBoxLayout()

            row.addWidget(entry, 1)

            row.addWidget(button)

            column.addLayout(row)

        self.trim_status = label("", "small")

        self.trim_status.setWordWrap(True)

        column.addWidget(self.trim_status)

        return self.trim_box

    def update_hotkey_hint(self):
        """The keys that work now (auto-hold's only while it is on).

        Each "key — action" is kept on one line with no-break spaces, so
        the hint wraps only after a separator dot.
        """
        entries = (
            f"{key} — {tr('hk_' + action)}".replace(" ", NBSP)
            for key, action in bindings(self)
        )

        self.hotkey_hint.setText(HINT_SEPARATOR.join(entries))

    def build_solution_card(self):
        frame, layout = card()

        header = QHBoxLayout()

        header.addWidget(label(tr("solution"), "title"))

        # Long texts here wrap: the card must fit the smallest window.
        self.solution_weapon = label("", "small")

        self.solution_weapon.setWordWrap(True)

        self.solution_weapon.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        header.addWidget(self.solution_weapon, 1)

        layout.addLayout(header)

        self.big_label = label(tr("ready"), "big")

        self.big_label.setWordWrap(True)

        self.sub_label = label("", "sub")

        self.sub_label.setWordWrap(True)

        layout.addWidget(self.big_label)
        layout.addWidget(self.sub_label)
        layout.addWidget(self.build_lay_calibration())

        grid = QGridLayout()

        grid.setSpacing(8)

        self.stats = {}

        for index, key in enumerate([
            "stat_tof",
            "stat_apex",
            "stat_impact",
            "stat_offset",
            "stat_velocity",
            "stat_alt"
        ]):
            tile = StatTile(tr(key))

            grid.addWidget(tile, index // 3, index % 3)

            self.stats[key] = tile

        layout.addLayout(grid)

        self.trajectory_view = TrajectoryView()

        layout.addWidget(self.trajectory_view, 1)

        layout.addWidget(label(tr("how_to").upper(), "section"))

        self.steps_layout = QVBoxLayout()

        self.steps_layout.setSpacing(6)

        layout.addLayout(self.steps_layout)

        self.note_label = label("", "small")

        self.note_label.setWordWrap(True)

        layout.addWidget(self.note_label)

        return frame

    def current_weapon(self):
        return self.weapons.get(self.picker.current)

    def select_weapon(self, name):
        self.picker.set_current(name)

    def on_weapon_changed(self, name, user=True):
        weapon = self.weapons.get(name)

        if weapon is None:
            return

        if user:
            # Picked here: the embedded map follows (its coverage and popups).
            if self.map_page is not None:
                self.map_page.select_weapon(name)

            self.config["last_weapon"] = name

            recent = [n for n in self.config["recent_weapons"] if n != name]

            self.config["recent_weapons"] = [name] + recent[:4]

            self.picker.set_data(self.weapon_groups(), self.recent_weapons())

            self.schedule_save()

        self.update_weapon_info(weapon)

        self.show_trim()

        # The calibration status and the lay's note are about the previous
        # weapon.
        self.lay_status.setText("")
        self.set_lay_info("")

        self.solution_weapon.setText(name)

        self.update_ladder()

        self.update_hold_watch()

        self.recalculate_if_ready()

    def update_weapon_info(self, weapon):
        parts = [
            tr("chip_velocity", v=f"{weapon.velocity:g}"),
            tr("chip_gravity", g=f"{weapon.gravity:g}"),
        ]

        max_range = weapon.max_range()

        if math.isinf(max_range):
            parts.append(tr("chip_range_inf"))
        elif max_range < 5000:
            # Beyond that the number is a physics limit, not a useful range.
            parts.append(tr("chip_range", r=f"{max_range:.0f}"))

        if weapon.has_boost:
            parts.append(
                tr(
                    "chip_boost",
                    a=weapon.acceleration,
                    t=weapon.acceleration_time
                )
            )

        if weapon.min_distance:
            parts.append(tr("chip_min", m=f"{weapon.min_distance:g}"))

        self.weapon_info.setText("  ·  ".join(parts))

    def current_trim(self, weapon):
        """The trim (degrees) set for `weapon`."""
        if weapon is None:
            return 0.0

        return self.config["mark_trim"].get(weapon.name, 0.0)

    def show_trim(self):
        """Load the trim of the current weapon into the controls."""
        weapon = self.current_weapon()

        self.trim_box.setVisible(weapon is not None and weapon.aim == "overlay")

        self.trim_entry.set_value(self.current_trim(weapon))

        self.landed_entry.clear()

        self.trim_status.setText("")

    def set_trim(self, trim):
        """Store `trim` (degrees, limited and rounded to 0.001) for the
        current weapon; the mark and the ladder follow at once."""
        weapon = self.current_weapon()

        if weapon is None:
            return

        trim = round(clamp_trim(trim), 3) + 0.0

        if trim:
            self.config["mark_trim"][weapon.name] = trim
        else:
            self.config["mark_trim"].pop(weapon.name, None)

        self.schedule_save()

        self.recalculate_if_ready()

    def on_trim_edited(self, *_):
        value = self.trim_entry.value(0.0)

        self.set_trim(value)

        if abs(value) > TRIM_LIMIT:
            self.trim_entry.set_value(self.current_trim(self.current_weapon()))

        self.trim_status.setText("")

    def reset_trim(self):
        """Remove the trim of the current weapon."""
        self.set_trim(0.0)

        self.show_trim()

    def apply_landing(self):
        """Set the trim from one real shot: fired at the typed distance (and
        height difference), landed at the typed landed distance. The status
        shows the new trim, or what is wrong with the numbers."""
        weapon = self.current_weapon()

        if weapon is None:
            return

        distance = self.distance_entry.value()
        landed = self.landed_entry.value()

        try:
            if distance is None:
                raise ValueError(tr("enter_distance"))

            if landed is None:
                raise ValueError(tr("enter_landed"))

            trim = trim_for_landing(
                weapon,
                distance,
                self.height_entry.value(0.0),
                landed,
                self.current_trim(weapon)
            )
        except ValueError as e:
            self.trim_status.setText(str(e))
            return
        except ArithmeticError:
            self.trim_status.setText(tr("bad_number"))
            return

        self.set_trim(trim)

        trim = self.current_trim(weapon)

        self.show_trim()

        self.trim_status.setText(
            tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}")
        )

    def on_arc_changed(self, key):
        self.config["arc"] = key

        self.schedule_save()

        self.recalculate_if_ready()

    def on_input_edited(self, *_):
        """An input was typed in: solve it (while typing, with auto-calc).

        Without auto-calc an emptied distance still clears the result: the
        overlay must not keep showing a shot for a distance that is gone.
        """
        if self.sender() in (self.distance_entry, self.height_entry):
            self.forget_map_target()

        if self.config["auto_calc"]:
            self.calc_timer.start()
        elif not self.distance_entry.text().strip():
            self.calculate(show_errors=False)

    # =========================
    # TARGETS FROM THE MAP
    # =========================

    def on_map_targets(self, targets):
        """Put the newest SquadCalc target into the inputs and solve it.

        `targets` comes from the embedded map (see maplink); the last one is the most recently placed marker. An empty list, or
        the same newest target delivered again (even after the inputs were
        edited by hand), keeps the current inputs.
        """
        if not self.config["map_follow"] or not targets:
            return

        target = targets[-1]

        if target == self.last_map_target:
            return

        self.last_map_target = target

        # Tenths of a metre: whole metres would throw away up to 0.5 m the
        # map delivered (and a metre of height moves a short UB-32 shot
        # 20-40 m).
        self.distance_entry.set_value(round(target.distance, 1))

        if target.height is None:
            self.height_entry.setText("")
        else:
            self.height_entry.set_value(round(target.height, 1))

        self.map_target = target

        self.update_map_status()

        # The distance was just filled: any remaining error (FOV) is real.
        self.calculate()

        self.restart_lay_for_new_target()

    def on_map_weapon(self, name):
        """Switch to the weapon selected in SquadCalc (with `map_follow`).

        `name` is a weapons.json name sent by the Deadline SquadCalc build
        when its weapon changes; a weapon picked here afterwards stays until
        the next change there. Names this app does not have are ignored;
        names from before a rename (an older SquadCalc page) are mapped to
        the current ones.
        """
        name = current_weapon_name(name)

        if not self.config["map_follow"] or name == self.picker.current:
            return

        if name not in self.weapons:
            return

        self.select_weapon(name)

    def forget_map_target(self):
        if self.map_target is None:
            return

        self.map_target = None

        self.update_map_status()

    def update_map_status(self):
        target = self.map_target

        if target is None:
            text = tr("map_follow_hint") if self.config["map_follow"] else ""
        else:
            parts = [f"{target.distance:.0f} {tr('unit_m')}"]

            if target.height is not None:
                parts.append(f"{target.height:+.0f} {tr('unit_m')}")

            if target.bearing is not None:
                parts.append(tr("bearing_short", b=f"{target.bearing:.1f}"))

            text = tr("map_target", t="  ·  ".join(parts))

        self.map_label.setText(text)

    def recalculate_if_ready(self):
        """Solve again after the weapon, the FOV, the calibration or the
        centre changed. Without a distance the result is cleared (the mark
        waits at the centre, or stays hidden for weapons laid by
        elevation), so nothing of the previous weapon stays on the overlay."""
        self.update_ladder()

        self.calculate(show_errors=False)

    def primary_unit(self, weapon):
        mode = self.config["unit_mode"]

        if mode in ("deg", "mil"):
            return mode

        return weapon.unit

    def set_big(self, text, error=False):
        self.big_label.setText(text)

        self.big_label.setProperty("state", "error" if error else "")

        repolish(self.big_label)

    def status_text(self):
        return self.big_label.text()

    def clear_result(self, text=None, error=False):
        self.set_big(text or tr("ready"), error)

        self.sub_label.setText("")

        for tile in self.stats.values():
            tile.set("—")

        self.trajectory_view.clear()

        self.set_steps([])

        self.note_label.setText("")

    def set_steps(self, steps):
        self.current_steps = list(steps)

        # Detach the old rows right away; deleteLater alone would leave them
        # visible until the event loop runs.
        while self.steps_layout.count():
            widget = self.steps_layout.takeAt(0).widget()

            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for index, text in enumerate(steps, start=1):
            row = QWidget()

            row_layout = QHBoxLayout(row)

            row_layout.setContentsMargins(0, 0, 0, 0)

            row_layout.setSpacing(10)

            number = label(str(index), "step_num")

            row_layout.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)

            body = label(text)

            body.setWordWrap(True)

            row_layout.addWidget(body, 1)

            self.steps_layout.addWidget(row)

    def read_inputs(self):
        distance = self.distance_entry.value()

        if distance is None:
            raise ValueError(tr("enter_distance"))

        if distance <= 0:
            raise ValueError(tr("bad_distance"))

        height = self.height_entry.value(0.0)

        fov = self.fov_entry.value()

        low, high = RANGES["fov"]

        if fov is None or not low <= fov <= high:
            raise ValueError(tr("bad_fov"))

        return distance, height, fov

    def calculate(self, show_errors=True):
        """Solve the inputs for the current weapon and show the result.

        `show_errors` False (calculation while typing, hotkeys): an empty
        distance shows the "Enter the distance" prompt rather than an
        error; any other bad input (zero distance, FOV out of range) is
        still reported.
        """
        weapon = self.current_weapon()

        if weapon is None:
            return

        # The FOV applies without a distance too: the range ladder follows it.
        fov = self.fov_entry.value()

        if fov is not None and RANGES["fov"][0] <= fov <= RANGES["fov"][1] \
                and self.config["fov"] != fov:
            self.config["fov"] = fov
            self.schedule_save()
            self.update_ladder()

        try:
            distance, height, fov = self.read_inputs()

            solution = solve(
                weapon,
                distance,
                height,
                self.config["arc"]
            )

            direct = None

            # A hold weapon lobbing (AGS-17) can also fire directly through
            # its sight: the overlay mark shows that aim at the same time.
            if weapon.has_hold and weapon.aim == "overlay" and solution.arc == "high":
                direct = solve(weapon, distance, height, "low")

                if not direct.reachable:
                    direct = None
        except (ValueError, ArithmeticError) as e:
            # ArithmeticError: absurd numbers (1e200 m) overflow the math.
            message = str(e) if isinstance(e, ValueError) else tr("bad_number")

            self.last_solution = None
            self.direct_solution = None

            self.overlay.set_offset(self.current_offset())

            self.set_overlay_info("")

            self.hold_timer.set_target(None)

            # While typing, only an empty distance is not worth an error:
            # a bad FOV or a zero distance must not read "Enter the distance".
            if show_errors or self.distance_entry.text().strip():
                self.clear_result(message, error=True)
            else:
                self.clear_result()

            return

        # Too close or too far to lob (AGS-17 under 280 m): fire directly.
        if not solution.reachable and direct is not None:
            solution, direct = direct, None

        self.last_solution = solution
        self.direct_solution = direct

        if not solution.reachable:
            self.show_unreachable(weapon, solution)
            return

        self.show_solution(weapon, solution, fov)

    def show_unreachable(self, weapon, solution):
        """The target cannot be hit: say why, in the weapon's angle unit."""
        unit = self.primary_unit(weapon)

        self.overlay.set_offset(self.current_offset())

        self.set_overlay_info("")

        self.hold_timer.set_target(None)

        self.clear_result(tr("unreachable"), error=True)

        if solution.reason_code == "out_of_range":
            text = tr("how_unreachable_range", max=f"{weapon.max_range():.0f}")
        elif solution.reason_code == "too_close":
            text = tr("how_unreachable_close", min=f"{weapon.min_distance:g}")
        elif solution.reason_code == "hold_limit":
            lowest, top = weapon.hold_elevation
            text = tr(
                "how_unreachable_hold",
                angle=format_angle(solution.angle, unit),
                low=format_angle(lowest, unit),
                high=format_angle(top, unit)
            )
        else:
            low, high = weapon.elevation_limits
            text = tr(
                "how_unreachable_limit",
                angle=format_angle(solution.angle, unit),
                low=format_angle(low, unit),
                high=format_angle(high, unit)
            )

        self.sub_label.setText(text)

    def show_solution(self, weapon, solution, fov):
        unit = self.primary_unit(weapon)
        other = "deg" if unit == "mil" else "mil"

        s = tr("unit_s")
        m = tr("unit_m")

        # Hold weapons on the high arc are laid by holding S, not by aiming;
        # the overlay mark then shows the direct-fire aim (`direct`).
        hold = solution.hold_time
        holding = math.isfinite(hold)
        direct = self.direct_solution if holding else None

        # Mortars are laid on their sight by the angle; the hold time is for
        # the auto-lay (W to the top, then S), not what the player reads.
        laid_by_angle = holding and weapon.aim == "elevation"

        # Terrain and buildings on the line to the SquadCalc target: where the
        # shown trajectories hit them first (None: clear, or no profile).
        profile, step = self.map_profile()
        obstacle = first_obstacle(weapon, solution, profile, step)
        direct_obstacle = (
            first_obstacle(weapon, direct, profile, step)
            if direct is not None else None
        )

        offset = self.current_offset()

        offscreen = offset is not None and self.overlay.is_offscreen(offset)

        self.overlay.set_offset(offset)

        # Weapons aimed with the overlay are laid relative to the target, not
        # the horizon (see Solution.sight_angle).
        aimed = solution.sight_angle if weapon.aim == "overlay" else solution.angle

        if holding and not laid_by_angle:
            readout = f"S {hold:.2f} {s}"
        elif laid_by_angle:
            readout = f"{format_angle(aimed, unit)}  ·  S {hold:.2f} {s}"
        else:
            readout = format_angle(aimed, unit)

        info = f"{solution.distance:.0f} {m}  ·  {readout}"

        trim = self.current_trim(weapon) if weapon.aim == "overlay" else 0.0

        if trim:
            info += "  ·  " + tr("info_trim", trim=f"{trim:+g}")

        if direct is not None:
            info += "  ·  " + tr(
                "direct_short", angle=format_angle(direct.sight_angle, unit)
            )

            if direct_obstacle is not None:
                info += " ⛔"

        if obstacle is not None:
            info += "  ·  " + tr("blocked_short", d=f"{obstacle[0]:.0f}")

        bearing = self.map_bearing()

        if bearing is not None:
            info += f"  ·  {bearing:.1f}°"

        self.set_overlay_info(info)

        if holding and not laid_by_angle:
            self.set_big(tr("hold_big", t=f"{hold:.2f}"))

            sub = (
                f"{format_angle(solution.angle, 'deg')}  ·  "
                f"{format_angle(solution.angle, 'mil')}"
            )

            if direct is not None:
                sub += "  ·  " + tr(
                    "direct_short", angle=format_angle(direct.sight_angle, unit)
                )

            self.sub_label.setText(sub)
        else:
            self.set_big(format_angle(aimed, unit))

            sub = format_angle(aimed, other)

            if weapon.aim == "overlay":
                sub += "  ·  " + tr(
                    "to_horizon", angle=format_angle(solution.angle, "deg")
                )

            if laid_by_angle:
                sub += "  ·  " + tr("lay_short", t=f"{hold:.2f}")

            self.sub_label.setText(sub)

        self.hold_timer.set_target(hold if holding else None)

        self.stats["stat_tof"].set(f"{solution.time_of_flight:.1f} {s}")
        self.stats["stat_apex"].set(f"{solution.apex:.0f} {m}")
        self.stats["stat_impact"].set(f"{solution.impact_angle:.1f}°")
        self.stats["stat_velocity"].set(
            f"{solution.velocity:.0f} {tr('unit_mps')}"
        )

        if offset is None or (holding and direct is None):
            self.stats["stat_offset"].set("—")
        elif offscreen:
            self.stats["stat_offset"].set(tr("off_screen"))
        else:
            self.stats["stat_offset"].set(f"{offset:.0f} {tr('unit_px')}")

        other_arc = "high" if solution.arc == "low" else "low"

        # The other arc only matters for weapons aimed by elevation and for
        # hold weapons (direct fire or lob); for other direct-fire weapons
        # it is a useless near-vertical lob.
        alt = None

        if weapon.aim == "elevation" or weapon.has_hold:
            alt = solution.alternatives.get(other_arc)

            if alt is not None and abs(alt - solution.angle) < 0.01:
                alt = None

        alt_path = []
        alt_solution = None

        if alt is None:
            self.stats["stat_alt"].set("—")
        else:
            self.stats["stat_alt"].set(format_angle(alt, unit))

            alt_solution = solve(
                weapon, solution.distance, solution.height_diff, other_arc
            )

            alt_path = trajectory(weapon, alt_solution)

        self.trajectory_view.set_data(
            trajectory(weapon, solution),
            alt_path,
            (solution.distance, solution.height_diff),
            [(i * step, h) for i, h in enumerate(profile)] if profile else None,
            obstacle
        )

        angle_text = format_angle(aimed, unit)

        tof = f"{solution.time_of_flight:.1f}"

        if holding and not laid_by_angle:
            steps = [
                tr("how_hold_1"),
                tr("how_hold_2", t=f"{hold:.2f}"),
                tr("how_tof_adjust", tof=tof)
            ]

            if direct is not None:
                steps.append(
                    tr(
                        "how_hold_direct_offscreen" if offscreen
                        else "how_hold_direct",
                        angle=format_angle(direct.sight_angle, unit)
                    )
                )
        elif weapon.aim == "overlay":
            if offscreen:
                steps = [tr("how_overlay_offscreen", angle=angle_text)]
            else:
                toggle_key = self.config["hotkeys"].get("toggle_overlay")

                steps = [
                    tr("how_overlay_1", angle=angle_text),
                    self.how_overlay_view(weapon, fov)
                ]

                if toggle_key:
                    steps[0] = (
                        tr("how_overlay_on", hotkey=toggle_key)
                        + " " + steps[0]
                    )

            if trim:
                steps.append(tr("how_trim", trim=f"{trim:+g}"))

            steps.append(
                tr(
                    "how_tof_moving",
                    tof=tof,
                    lead=f"{solution.time_of_flight * 10:.0f}"
                )
            )
        else:
            steps = [
                tr("how_elevation_1"),
                tr("how_elevation_2", angle=angle_text),
                tr("how_tof_adjust", tof=tof)
            ]

            if laid_by_angle:
                steps.insert(2, self.lay_step(hold))

        steps = self.obstacle_steps(
            weapon, solution, obstacle, alt_solution, profile, step, unit
        ) + steps

        if direct_obstacle is not None:
            steps.append(
                tr("how_direct_blocked", d=f"{direct_obstacle[0]:.0f}")
            )

        if bearing is not None:
            steps.insert(0, tr("how_bearing", b=f"{bearing:.1f}"))

        self.set_steps(steps)

        self.note_label.setText(weapon.note)

    def obstacle_steps(self, weapon, solution, obstacle, alt_solution,
                       profile, step, unit):
        """What to do when the shown trajectory hits the terrain first.

        Names the obstacle, then the other arc when it is fireable and
        clears the profile, or says that both are blocked. Empty when the
        shown trajectory is clear.
        """
        if obstacle is None:
            return []

        steps = [
            tr(
                "how_blocked",
                arc=tr(f"arc_{solution.arc}"),
                d=f"{obstacle[0]:.0f}",
                h=f"{obstacle[1]:+.0f}"
            )
        ]

        if alt_solution is None or not alt_solution.reachable:
            return steps

        if first_obstacle(weapon, alt_solution, profile, step) is not None:
            steps.append(tr("how_blocked_all"))
            return steps

        if weapon.has_hold and alt_solution.arc == "high":
            aim = f"S {alt_solution.hold_time:.2f} {tr('unit_s')}"
        elif weapon.aim == "overlay" or weapon.has_hold:
            aim = format_angle(alt_solution.sight_angle, unit)
        else:
            aim = format_angle(alt_solution.angle, unit)

        steps.append(
            tr("how_blocked_use", arc=tr(f"arc_{alt_solution.arc}"), angle=aim)
        )

        return steps

    def map_profile(self):
        """(heights, step) of the SquadCalc target in the inputs: terrain
        and buildings from the weapon to it. (None, None) if typed or the
        page sent none."""
        target = self.map_target

        if target is None or not target.profile:
            return None, None

        return target.profile, target.profile_step

    def map_bearing(self):
        """Bearing of the SquadCalc target in the inputs, None if typed."""
        if self.map_target is None:
            return None

        return self.map_target.bearing

    def set_overlay_info(self, text):
        self.info_base = text

        self.show_overlay_info()

    def show_overlay_info(self):
        """The overlay label: the solution, the bearing, the sight, and why
        the auto-lay did not run or stopped short."""
        parts = (self.info_base, self.bearing_info, self.sight_info, self.lay_info)

        self.overlay.set_info("  ·  ".join(part for part in parts if part))

    def update_hold_watch(self):
        """Watch S/W only while a hold weapon is selected."""
        weapon = self.current_weapon()

        self.lay_row.setVisible(
            weapon is not None and weapon.has_hold and weapon.aim == "elevation"
        )

        self.hold_timer.set_active(weapon is not None and weapon.has_hold)

        self.update_sight_watch()

    def build_lay_calibration(self):
        """Mortar auto-lay calibration: the mils the sight shows.

        The caption, the field with its buttons and the status are on lines
        of their own, so the card fits the smallest window.
        """
        self.lay_row = QWidget()

        column = QVBoxLayout(self.lay_row)

        column.setContentsMargins(0, 0, 0, 0)

        column.setSpacing(4)

        caption = label(tr("lay_read"), "small")

        caption.setWordWrap(True)

        column.addWidget(caption)

        row = QHBoxLayout()

        column.addLayout(row)

        self.lay_entry = NumberEdit(allow_negative=False, step=1)

        self.lay_entry.setFixedWidth(80)

        self.lay_entry.returnPressed.connect(self.calibrate_lay)

        row.addWidget(self.lay_entry)

        calibrate = QPushButton(tr("lay_calibrate"))

        calibrate.clicked.connect(lambda: self.calibrate_lay())

        row.addWidget(calibrate)

        reset = QPushButton(tr("lay_reset"))

        # Secondary, like the app's other reset buttons: Calibrate is the action.
        reset.setProperty("flat_style", True)

        reset.clicked.connect(lambda: self.reset_lay_rate())

        row.addWidget(reset)

        row.addStretch()

        self.lay_status = label("", "small")

        self.lay_status.setWordWrap(True)

        column.addWidget(self.lay_status)

        self.lay_row.hide()

        return self.lay_row

    def apply_lay_rates(self):
        """Use the calibrated hold rates of `config["lay_rates"]`."""
        self.weapons = dict(self.file_weapons)

        for name, rate in self.config["lay_rates"].items():
            weapon = self.weapons.get(name)

            if weapon is not None and weapon.has_hold and weapon.aim == "elevation":
                self.weapons[name] = replace(weapon, hold_rate=rate)

    def calibrate_lay(self):
        """Fit the hold rate on the mils the sight shows after a lay.

        The barrel went down from the top for the time S was held since the
        last W (the hold timer's count, auto-lay or by hand), so the rate is
        (top - shown angle) / held. A lay on the sight moves the barrel in
        taps that do not start at the top, so after one the rate is not
        fitted until W is pressed again. The mils are the typed ones, or read off
        the sight on the screen when none are typed. Returns True when the
        rate was saved; otherwise the status says what is missing.
        """
        weapon = self.current_weapon()
        mils = self.lay_entry.value()
        held = self.hold_timer.held

        # After a lay on the sight `held` is only its last taps of S
        if self.lays_by_sight(weapon) and not self.hold_timer.measures_lay:
            self.lay_status.setText(tr("lay_after_sight"))
            return False

        # Nothing typed: the mils the sight shows on the screen
        if mils is None and self.config["sight_reader"] and self.lays_by_sight(weapon):
            reading = self.read_sight_now()

            if reading is None:
                path = self.save_sight_grab()

                # No path: the screen cannot be grabbed (fullscreen, Wayland)
                self.lay_status.setText(
                    tr("lay_no_sight", path=path) if path else tr("lay_no_grab")
                )
                return False

            mils = reading.mils

        if weapon is None or not weapon.has_hold or weapon.aim != "elevation":
            return False

        if mils is None:
            self.lay_status.setText(tr("lay_need_mils"))
            return False

        if held < LAY_CALIBRATION_MIN_HOLD:
            self.lay_status.setText(tr("lay_need_hold", t=f"{LAY_CALIBRATION_MIN_HOLD:g}"))
            return False

        lowest, top = weapon.hold_elevation
        rate = (top - mils / MILS_PER_DEGREE) / held
        base = self.file_weapons[weapon.name].hold_rate

        if abs(rate - base) > LAY_RATE_TOLERANCE * base:
            self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}"))
            return False

        self.config["lay_rates"][weapon.name] = round(rate, 4)
        self.schedule_save()
        self.apply_lay_rates()
        self.lay_entry.clear()
        self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}"))
        self.recalculate_if_ready()

        return True

    def reset_lay_rate(self):
        """Back to the hold rate of weapons.json for the current weapon."""
        weapon = self.current_weapon()

        if weapon is None or self.config["lay_rates"].pop(weapon.name, None) is None:
            return

        self.schedule_save()
        self.apply_lay_rates()
        self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}"))
        self.recalculate_if_ready()

    def lay_reset_time(self, weapon):
        """Seconds of W that surely put the barrel at its top, 0 if not needed.

        Only for weapons laid by the angle (mortars): the player may have left
        the barrel anywhere, the AGS-17 player presses W before holding S.
        """
        if weapon is None or not weapon.has_hold or weapon.aim != "elevation":
            return 0.0

        return weapon.max_hold_time() + LAY_RESET_MARGIN

    def lay_step(self, hold):
        """How-to line of the mortar auto-lay, by the state of the setting."""
        if not self.config["auto_hold"] or self.hold_timer.auto_hold is None:
            return tr("how_lay_off", t=f"{hold:.2f}")

        return tr(
            "how_lay",
            hotkey=self.config["hotkeys"].get("auto_hold", ""),
            t=f"{hold:.2f}"
        )

    def auto_hold(self):
        """Hotkey: hold S for the time left to the target (again: release).

        Mortars are laid on their sight when it is seen on the screen (W or
        S until it shows the target), otherwise from scratch: W to the top
        first, then S for the hold time. When nothing can be started the
        overlay says why (see `timed_lay_blocker`).
        """
        layer = self.sight_layer
        turning = self.bearing_layer

        self.set_lay_info("")

        if turning is not None and turning.active:
            turning.stop()
            return

        if layer is not None and layer.active:
            layer.stop()
            return

        weapon = self.current_weapon()
        timer = self.hold_timer
        on_screen = not timer.auto_holding \
            and self.config["sight_reader"] and self.lays_by_sight(weapon)

        # A map target's bearing first (then the elevation, see
        # on_bearing_lay_finished), when the compass is on the screen.
        if on_screen and turning is not None and layer is not None and turning.start():
            self.sight_timer.stop()
            return

        if on_screen and self.start_sight_lay():
            return

        if timer.auto_holding:
            timer.toggle_auto_hold()
            return

        blocker = self.timed_lay_blocker(weapon)

        if blocker is None and not timer.toggle_auto_hold(self.lay_reset_time(weapon)):
            # Nothing left to hold: S was held for the whole time already
            blocker = "lay_key_held"

        if blocker is not None:
            self.set_lay_info(tr(blocker, key=self.config["hotkeys"].get("auto_hold", "")))

    def timed_lay_blocker(self, weapon):
        """Why the timed lay of `weapon` cannot start, as the i18n key of
        the reason, or None when it can."""
        timer = self.hold_timer

        if weapon is None or not weapon.has_hold:
            return "lay_key_weapon"

        if timer.auto_hold is None:
            return "lay_key_no_keys"

        if self.lay_reset_time(weapon) > 0 and timer.auto_hold.reset_injector is None:
            return "lay_key_no_w"

        if not timer.active or not timer.available:
            return "lay_key_no_reader"

        if timer.target is None:
            return "lay_key_no_target"

        return None

    def start_sight_lay(self):
        """Start laying the elevation on the mortar's sight; False when it
        cannot (no lay, no target, the sight not seen).

        The hold timer stops counting meanwhile: the lay's taps of W and S
        are not a lay from the top (see HoldTimer.suspend).
        """
        layer = self.sight_layer

        if layer is None or not layer.start():
            return False

        self.hold_timer.suspend()
        self.sight_timer.stop()

        return True

    def set_lay_info(self, text):
        """Show on the overlay why the auto-lay did not run or stopped."""
        if text == self.lay_info:
            return

        self.lay_info = text
        self.show_overlay_info()

    @staticmethod
    def lay_failure_text(layer, axis):
        """Why `layer`'s lay stopped short, for the overlay; "" when it is
        on the target or the player stopped it. `axis` names what was laid
        ("lay_bearing" or "lay_elevation")."""
        failure = layer.failure

        if failure is None or failure == "stopped":
            return ""

        return tr(
            "lay_failed",
            what=tr(axis),
            why=tr(f"lay_why_{failure}", moves=MAX_MOVES)
        )

    @staticmethod
    def lays_by_sight(weapon):
        """Mortars: laid by holding W/S while looking at the elevation on
        their sight."""
        return weapon is not None and weapon.has_hold and weapon.aim == "elevation"

    def templates(self):
        """Digit pictures for the sight reader, made on first use."""
        if self.sight_templates is None:
            self.sight_templates = LabelTemplates()

        return self.sight_templates

    def sight_target(self):
        """Mils the sight should show for the current solution, or None."""
        solution = self.last_solution

        if not self.lays_by_sight(self.current_weapon()) or solution is None \
                or not math.isfinite(solution.hold_time):
            return None

        return solution.angle * MILS_PER_DEGREE

    def bearing_target(self):
        """Bearing to turn the mortar to: the SquadCalc map target's, while
        a mortar is laid on it; None otherwise."""
        target = self.map_target

        if self.sight_target() is None or target is None or target.bearing is None:
            return None

        return target.bearing % 360.0

    def read_sight_now(self):
        """The elevation on the mortar sight now (sightreader.Reading), or
        None when the sight is not on the screen."""
        return read_sight(self.screen_sight.grab(), self.templates())

    def save_sight_grab(self):
        """Save what the sight reader sees, for a sight it could not read;
        returns the file's path, or "" if the screen can't be grabbed."""
        image = self.screen_sight.grab_image()

        if image is None:
            return ""

        os.makedirs(config_dir(), exist_ok=True)
        path = os.path.join(config_dir(), SIGHT_GRAB_FILE)

        if not image.save(path):
            return ""

        return path

    def laying(self):
        """Whether a lay on the screen (bearing or elevation) is running."""
        return any(
            layer is not None and layer.active
            for layer in (self.bearing_layer, self.sight_layer)
        )

    def update_sight_watch(self):
        """Read the sight periodically while a mortar is selected and no
        lay is running (a lay reads the screen itself)."""
        watch = self.config["sight_reader"] and self.lays_by_sight(self.current_weapon())

        if not watch:
            self.sight_timer.stop()
            self.set_sight_info("")
            self.set_bearing_info("")
            return

        if not self.sight_timer.isActive() and not self.laying():
            self.sight_timer.start()

    def watch_sight(self):
        self.show_sight_reading(self.read_sight_now())

        # The bearing left to a map target, off the compass
        if self.bearing_target() is None:
            self.set_bearing_info("")
        else:
            self.show_bearing_reading(self.compass_reader()(self.screen_sight.grab_compass()))

    def compass_reader(self):
        """The compass reader of the bearing lay, or one of its own without
        it (made on first use)."""
        if self.bearing_layer is not None:
            return self.bearing_layer.reader

        if self.own_compass_reader is None:
            self.own_compass_reader = CompassReader(DigitReader(self.templates()))

        return self.own_compass_reader

    def show_sight_reading(self, reading, mark=""):
        """The sight reading and what is left to the target on the overlay."""
        if reading is None:
            self.set_sight_info("")
            return

        target = self.sight_target()

        if target is None:
            text = tr("sight_reading", mils=f"{reading.mils:.1f}")
        else:
            text = tr(
                "sight_reading_left",
                mils=f"{reading.mils:.1f}",
                left=f"{target - reading.mils:+.1f}"
            )

        self.set_sight_info(f"{text}{mark}")

    def set_sight_info(self, text):
        if text == self.sight_info:
            return

        self.sight_info = text
        self.show_overlay_info()

    def show_bearing_reading(self, reading, mark=""):
        """The compass reading and what is left to the target bearing."""
        if reading is None:
            self.set_bearing_info("")
            return

        target = self.bearing_target()

        if target is None:
            text = tr("compass_reading", deg=f"{reading.degrees:.1f}")
        else:
            left = BEARING.difference(target, reading.degrees)
            text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}")

        self.set_bearing_info(f"{text}{mark}")

    def set_bearing_info(self, text):
        if text == self.bearing_info:
            return

        self.bearing_info = text
        self.show_overlay_info()

    @staticmethod
    def lay_mark(layer, on_target):
        """✓ on the target, ✗ when the lay stopped short by itself, nothing
        when the player stopped it."""
        if on_target:
            return "  ✓"

        return "" if layer is not None and layer.stopped else "  ✗"

    def on_bearing_lay_finished(self, reading, on_target):
        """The bearing is laid (or could not be): lay the elevation next,
        unless the player stopped the lay."""
        turning = self.bearing_layer

        self.show_bearing_reading(reading, self.lay_mark(turning, on_target))

        if turning is not None:
            self.set_lay_info(self.lay_failure_text(turning, "lay_bearing"))

        stopped = turning is not None and turning.stopped

        if stopped or not self.start_sight_lay():
            self.update_sight_watch()

    def on_sight_lay_finished(self, reading, on_target):
        """The lay on the sight ended: show where it stopped and why it
        stopped short, beep on target, and go back to watching the sight."""
        layer = self.sight_layer

        self.hold_timer.resume()

        self.show_sight_reading(reading, self.lay_mark(layer, on_target))

        failure = "" if layer is None else self.lay_failure_text(layer, "lay_elevation")

        # A failure of the bearing before it stays unless this one replaces it
        if failure:
            self.set_lay_info(failure)

        if on_target:
            beep()

        self.update_sight_watch()

    def restart_lay_for_new_target(self):
        """A new map target arrived while the elevation is being laid: lay
        again from the bearing, which the new target changes too. During
        the bearing phase nothing is needed: its target follows the map."""
        layer, turning = self.sight_layer, self.bearing_layer

        if layer is None or not layer.active or turning is None \
                or self.bearing_target() is None:
            return

        layer.stop()

        self.set_lay_info("")

        if turning.start():
            self.sight_timer.stop()
        else:
            # The compass is not seen: at least the elevation is laid again
            self.start_sight_lay()

    def apply_auto_hold(self):
        """Create or drop the key injector according to the setting.

        Returns False when auto-hold is enabled but keys cannot be sent;
        the setting is then turned off.
        """
        self.drop_auto_hold()

        if not self.config["auto_hold"]:
            return True

        injector = system_key_injector(KEY_S)

        if injector is None:
            self.config["auto_hold"] = False
            return False

        # W puts a mortar's barrel to its top before the hold (auto-lay)
        reset_injector = system_key_injector(KEY_W)

        self.hold_timer.auto_hold = AutoHold(injector, reset_injector)

        # Mortars: laying on the sight needs both keys (W up, S down)
        if reset_injector is not None:
            self.sight_layer = SightLayer(
                lambda: self.screen_sight.grab(),
                self.templates(),
                self.sight_target,
                reset_injector,
                injector,
                self
            )
            self.sight_layer.read.connect(self.show_sight_reading)
            self.sight_layer.finished.connect(self.on_sight_lay_finished)

            self.make_bearing_layer()

        return True

    def make_bearing_layer(self):
        """The bearing lay (D turns right, A left), if both keys can be
        sent."""
        right = system_key_injector(KEY_D)
        left = system_key_injector(KEY_A)

        if right is None or left is None:
            for injector in (right, left):
                if injector is not None:
                    injector.close()
            return

        templates = self.templates()
        self.bearing_layer = SightLayer(
            lambda: self.screen_sight.grab_compass(),
            templates,
            self.bearing_target,
            right,
            left,
            self,
            axis=BEARING,
            reader=CompassReader(DigitReader(templates))
        )
        self.bearing_layer.read.connect(self.show_bearing_reading)
        self.bearing_layer.finished.connect(self.on_bearing_lay_finished)

    def drop_auto_hold(self):
        """Release S if it is being held and close the injector."""
        timer = self.hold_timer

        timer.stop_auto_hold()

        if self.bearing_layer is not None:
            self.bearing_layer.stop()
            self.bearing_layer.raise_key.close()
            self.bearing_layer.lower_key.close()
            self.bearing_layer.deleteLater()
            self.bearing_layer = None

        if self.sight_layer is not None:
            self.sight_layer.stop()
            self.sight_layer.deleteLater()
            self.sight_layer = None

        if timer.auto_hold is not None:
            timer.auto_hold.injector.close()
            if timer.auto_hold.reset_injector is not None:
                timer.auto_hold.reset_injector.close()
            timer.auto_hold = None

    def set_auto_hold(self, checked):
        teardown_hotkeys(self)

        ok = self.apply_auto_hold()

        setup_hotkeys(self)

        self.schedule_save()

        if not ok:
            toggle = self.controls["auto_hold"]
            toggle.blockSignals(True)
            toggle.setChecked(False)
            toggle.update()
            toggle.blockSignals(False)

        self.auto_hold_status.setText("" if ok else tr("auto_hold_unavailable"))

        self.update_hotkey_hint()

    def current_offset(self):
        """Pixels the overlay mark sits below the centre, None without a mark.

        Weapons laid by elevation (`aim` "elevation": mortars, rocket
        artillery) are set on their own sight, so they get no mark.
        """
        weapon = self.current_weapon()

        if weapon is not None and weapon.aim != "overlay":
            return None

        solution = self.last_solution

        if solution is None or not solution.reachable:
            return 0.0

        # The barrel is laid by holding S: the mark shows the direct-fire
        # aim instead, when there is one.
        if math.isfinite(solution.hold_time):
            solution = self.direct_solution

            if solution is None:
                return 0.0

        # The player puts the target, not the horizon, on the mark: the
        # mark is below the centre by the angle over the line of sight, less
        # what the view is zeroed for.
        if weapon is None:
            return screen_offset(
                solution.sight_angle,
                self.config["fov"],
                self.overlay.screen_width(),
                self.config["offset_scale"] / 100
            )

        return mark_offset(
            weapon,
            solution.sight_angle,
            self.config["fov"],
            self.overlay.screen_width(),
            self.config["offset_scale"] / 100,
            trim=self.current_trim(weapon)
        )

    def how_overlay_view(self, weapon, fov):
        """The how-to step about the in-game FOV and the view the mark is
        for."""
        if weapon.zoom:
            return tr("how_overlay_optic", fov=f"{fov:g}", zoom=f"{weapon.zoom:g}")

        return tr("how_overlay_2", fov=f"{fov:g}")

    def update_ladder(self):
        """Put the current weapon's range ladder on the overlay, or clear
        it (weapons laid by elevation, or the ladder turned off)."""
        weapon = self.current_weapon()

        if weapon is None or not self.config["range_ladder"]:
            self.overlay.set_ladder([])
            return

        first, spacing, reach = self.overlay.ladder_bounds()

        self.overlay.set_ladder(range_ladder(
            weapon,
            self.config["fov"],
            self.overlay.screen_width(),
            first,
            spacing,
            reach,
            self.config["offset_scale"] / 100,
            trim=self.current_trim(weapon)
        ))

    def reset_offset(self):
        self.last_solution = None
        self.direct_solution = None

        self.overlay.set_offset(self.current_offset())

        self.set_overlay_info("")

        self.hold_timer.set_target(None)

        self.clear_result()

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

    def distance_up(self):
        self.forget_map_target()
        self.distance_entry.add(self.config["distance_step"])
        self.calculate(show_errors=False)

    def distance_down(self):
        self.forget_map_target()
        self.distance_entry.add(-self.config["distance_step"])
        self.calculate(show_errors=False)

    # =========================
    # CROSSHAIR PAGE
    # =========================

    def build_crosshair_page(self):
        page = QWidget()

        layout = QHBoxLayout(page)

        layout.setContentsMargins(24, 24, 24, 24)

        layout.setSpacing(18)

        preview_card, preview_layout = card()

        preview_layout.addWidget(label(tr("preview"), "title"))

        self.preview = CrosshairPreview(self.config)

        preview_layout.addWidget(self.preview, 1)

        caption = label(tr("mark_caption"), "small")

        caption.setWordWrap(True)

        preview_layout.addWidget(caption)

        preview_layout.addWidget(label(tr("align_title").upper(), "section"))

        align_caption = label(tr("align_caption"), "small")

        align_caption.setWordWrap(True)

        preview_layout.addWidget(align_caption)

        for text, key, suffix in [
            ("align_x", "center_offset_x", f" {tr('unit_px')}"),
            ("align_y", "center_offset_y", f" {tr('unit_px')}"),
            ("align_scale", "offset_scale", "%"),
        ]:
            self.add_slider(
                preview_layout, tr(text), key, suffix,
                on_change=self.recalculate_if_ready
            )

        reset_alignment = QPushButton(tr("align_reset"))

        reset_alignment.setProperty("flat_style", True)

        reset_alignment.clicked.connect(self.reset_alignment)

        reset_row = QHBoxLayout()

        reset_row.addWidget(reset_alignment)

        reset_row.addStretch()

        preview_layout.addLayout(reset_row)

        layout.addWidget(scrolled(preview_card), 1)

        settings, settings_layout = card()

        settings_layout.addWidget(label(tr("nav_crosshair"), "title"))

        settings_layout.addWidget(label(tr("style").upper(), "section"))

        style = Segmented(
            [(key, tr(f"style_{key}")) for key in MARK_STYLES],
            self.config["mark_style"]
        )

        style.changed.connect(lambda key: self.set_setting("mark_style", key))

        settings_layout.addWidget(style)

        settings_layout.addWidget(label(tr("color").upper(), "section"))

        self.color_swatches = Swatches(MARK_COLORS, self.config["color"])

        self.color_swatches.picked.connect(
            lambda name: self.set_setting("color", name)
        )

        settings_layout.addWidget(self.color_swatches)

        self.add_slider(settings_layout, tr("size"), "mark_size", "%")

        self.add_toggle(settings_layout, tr("opt_ladder"), "range_ladder")

        self.add_toggle(settings_layout, tr("opt_info"), "info_enabled")

        settings_layout.addStretch()

        layout.addWidget(scrolled(settings, 400), 0)

        return page

    def add_toggle(self, layout, text, key, on_change=None):
        toggle = Toggle(text, bool(self.config[key]))

        def handle(checked):
            self.set_setting(key, checked)

            if on_change:
                on_change(checked)

        toggle.toggled.connect(handle)

        layout.addWidget(toggle)

        self.controls[key] = toggle

        return toggle

    def add_slider(self, layout, text, key, suffix, on_change=None):
        low, high = RANGES[key]

        row = SliderRow(text, low, high, self.config[key], suffix)

        def handle(value):
            self.set_setting(key, value)

            if on_change:
                on_change()

        row.changed.connect(handle)

        layout.addWidget(row)

        self.controls[key] = row

        return row

    def reset_alignment(self):
        """Put the mark back at the centre of the screen, unscaled."""
        for key in ALIGNMENT_KEYS:
            self.controls[key].slider.setValue(DEFAULT_CONFIG[key])

    def set_setting(self, key, value):
        self.config[key] = value

        self.refresh_crosshair()

    def refresh_crosshair(self):
        # The crosshair's size moves the ladder's first tick.
        self.update_ladder()

        self.overlay.update()

        self.preview.update()

        self.color_swatches.set_current(self.config["color"])

        self.schedule_save()

    # =========================
    # SETTINGS PAGE
    # =========================

    def build_settings_page(self):
        page = QWidget()

        column = QVBoxLayout(page)

        column.setContentsMargins(24, 24, 24, 24)

        column.setSpacing(18)

        column.addWidget(self.build_interface_card())
        column.addWidget(self.build_calc_settings_card())

        column.addWidget(self.build_overlay_card())

        column.addWidget(self.build_map_card())
        column.addWidget(self.build_hotkeys_card())
        column.addWidget(self.build_about_card())

        column.addStretch()

        wrapper = QWidget()

        outer = QHBoxLayout(wrapper)

        outer.setContentsMargins(0, 0, 0, 0)

        page.setMaximumWidth(640)

        outer.addStretch()

        outer.addWidget(page, 1)

        outer.addStretch()

        return scrolled(wrapper)

    def setting_row(self, layout, text, widget):
        row = QHBoxLayout()

        row.addWidget(label(text))

        row.addStretch()

        row.addWidget(widget)

        layout.addLayout(row)

    def combo(self, items, current, on_change):
        box = QComboBox()

        for value, text in items:
            box.addItem(text, value)

        index = box.findData(current)

        box.setCurrentIndex(max(0, index))

        box.setMinimumWidth(180)

        box.currentIndexChanged.connect(
            lambda _i: on_change(box.currentData())
        )

        return box

    def build_interface_card(self):
        frame, layout = card()

        layout.addWidget(label(tr("s_interface"), "title"))

        self.add_toggle(
            layout,
            tr("s_on_top"),
            "main_on_top",
            self.set_on_top
        )

        return frame

    def build_calc_settings_card(self):
        frame, layout = card()

        layout.addWidget(label(tr("s_calc"), "title"))

        units = Segmented(
            [
                ("auto", tr("s_units_auto")),
                ("deg", tr("s_units_deg")),
                ("mil", tr("s_units_mil"))
            ],
            self.config["unit_mode"]
        )

        units.changed.connect(self.set_unit_mode)

        self.setting_row(layout, tr("s_units"), units)

        self.setting_row(
            layout,
            tr("s_step"),
            self.combo(
                [(step, f"{step} {tr('unit_m')}") for step in DISTANCE_STEPS],
                self.config["distance_step"],
                self.set_distance_step
            )
        )

        self.add_toggle(
            layout,
            tr("s_auto_calc"),
            "auto_calc",
            lambda checked: self.calc_button.setVisible(not checked)
        )

        self.add_toggle(
            layout,
            tr(
                "s_auto_hold",
                key=self.config["hotkeys"].get("auto_hold") or tr("hk_none")
            ),
            "auto_hold",
            self.set_auto_hold
        )

        auto_hint = label(tr("s_auto_hold_hint"), "small")

        auto_hint.setWordWrap(True)

        layout.addWidget(auto_hint)

        self.auto_hold_status = label("", "small")

        self.auto_hold_status.setProperty("state", "error")

        layout.addWidget(self.auto_hold_status)

        self.add_toggle(
            layout,
            tr("s_sight_reader"),
            "sight_reader",
            lambda _checked: self.update_sight_watch()
        )

        sight_hint = label(tr("s_sight_reader_hint"), "small")

        sight_hint.setWordWrap(True)

        layout.addWidget(sight_hint)

        return frame

    def build_overlay_card(self):
        """The monitor choice; shown only with more than one monitor."""
        frame, layout = card()

        self.overlay_card = frame

        layout.addWidget(label(tr("s_overlay"), "title"))

        self.monitor_box = self.combo([], None, self.set_monitor)

        self.setting_row(layout, tr("s_monitor"), self.monitor_box)

        self.update_monitor_choice()

        return frame

    @staticmethod
    def shown_monitor(index):
        """Index in QGuiApplication.screens() of the monitor the overlay is
        on for the saved `index`: that one, or the primary monitor when it
        no longer exists (as Overlay.move_to_screen does)."""
        screens = QGuiApplication.screens()

        if 0 <= index < len(screens):
            return index

        primary = QGuiApplication.primaryScreen()

        return screens.index(primary) if primary in screens else 0

    def update_monitor_choice(self, *_):
        """Refill the monitor list from the monitors there are now and
        select the one the overlay is on, even when the saved one is gone
        (the saved choice is kept: the monitor may come back). Called when
        a monitor is added, removed or changes its resolution."""
        box = getattr(self, "monitor_box", None)

        if box is None:
            return

        screens = QGuiApplication.screens()

        box.blockSignals(True)
        box.clear()

        for index, screen in enumerate(screens):
            size = screen.geometry()
            box.addItem(f"{index + 1}: {screen.name()} ({size.width()}×{size.height()})", index)

        box.setCurrentIndex(max(0, box.findData(self.shown_monitor(int(self.config["monitor"])))))
        box.blockSignals(False)

        self.overlay_card.setVisible(len(screens) > 1)

    def watch_monitors(self):
        """Keep the monitor list current when monitors come, go or change
        their resolution (the overlay follows them itself). Bound methods:
        PyQt drops the connections when the window is deleted."""
        app = QGuiApplication.instance()

        for screen in app.screens():
            screen.geometryChanged.connect(self.update_monitor_choice)

        app.screenAdded.connect(self.watch_screen)
        app.screenRemoved.connect(self.update_monitor_choice)

    def watch_screen(self, screen):
        """A monitor was added: list it, and follow its resolution."""
        screen.geometryChanged.connect(self.update_monitor_choice)

        self.update_monitor_choice()

    def build_hotkeys_card(self):
        frame, layout = card()

        layout.addWidget(label(tr("s_hotkeys"), "title"))

        keys = [("", tr("hk_none"))] + [(key, key) for key in KEYS]

        for action in ACTIONS:
            self.setting_row(
                layout,
                tr(f"hk_{action}"),
                self.combo(
                    keys,
                    self.config["hotkeys"].get(action, ""),
                    lambda key, a=action: self.set_hotkey(a, key)
                )
            )

        hint = label(tr("s_hotkeys_hint"), "small")

        hint.setWordWrap(True)

        layout.addWidget(hint)

        return frame

    def build_about_card(self):
        frame, layout = card()

        layout.addWidget(label(tr("s_about"), "title"))

        layout.addWidget(label(tr("s_version", v=APP_VERSION), "muted"))

        row = QHBoxLayout()

        open_button = QPushButton(tr("s_open_config"))

        open_button.setProperty("flat_style", True)

        open_button.clicked.connect(self.open_config_dir)

        reset_button = QPushButton(tr("s_reset"))

        reset_button.setProperty("flat_style", True)

        reset_button.clicked.connect(self.reset_settings)

        row.addWidget(open_button)
        row.addWidget(reset_button)
        row.addStretch()

        layout.addLayout(row)

        self.open_status = label("", "small")

        self.open_status.setWordWrap(True)

        self.open_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.open_status.hide()

        layout.addWidget(self.open_status)

        return frame

    def open_config_dir(self):
        """Open the settings folder in the file manager; without one (no
        xdg-open handler) show its path to open by hand."""
        path = config_dir()

        os.makedirs(path, exist_ok=True)

        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self.open_status.hide()
            return

        self.open_status.setText(tr("open_failed", target=path))

        self.open_status.show()

    def set_on_top(self, checked):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)

        self.show()

    def set_unit_mode(self, mode):
        self.config["unit_mode"] = mode

        self.schedule_save()

        self.recalculate_if_ready()

    def set_distance_step(self, step):
        self.config["distance_step"] = step

        self.distance_entry.step = step

        self.schedule_save()

    def set_monitor(self, index):
        self.config["monitor"] = index

        self.overlay.move_to_screen()

        self.schedule_save()

        self.recalculate_if_ready()

    def set_hotkey(self, action, key):
        teardown_hotkeys(self)

        # A key can only do one thing.
        for other, bound in self.config["hotkeys"].items():
            if key and bound == key and other != action:
                self.config["hotkeys"][other] = ""

        self.config["hotkeys"][action] = key

        setup_hotkeys(self)

        self.schedule_save()

        self.rebuild()

    def reset_settings(self):
        answer = QMessageBox.question(
            self,
            "Squad Ballistics",
            tr("s_reset_confirm")
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        teardown_hotkeys(self)

        old_map_url = map_url(self.config)

        # The overlay keeps a reference to this dict, so update it in place.
        self.config.clear()

        self.config.update(copy.deepcopy(DEFAULT_CONFIG))

        setup_hotkeys(self)

        self.overlay.move_to_screen()

        self.set_on_top(False)

        self.apply_auto_hold()

        self.apply_lay_rates()

        # rebuild() keeps the typed inputs; the FOV is a setting.
        self.fov_entry.set_value(self.config["fov"])

        self.update_ladder()

        if self.map_page is not None and map_url(self.config) != old_map_url:
            self.map_page.load_source()

        save_config(self.config)

        self.rebuild()

        self.update_hold_watch()

    def schedule_save(self):
        self.save_timer.start()

    # =========================
    # MAP PAGE
    # =========================

    def build_web_page(self):
        if self.map_page is None:
            self.map_page = MapPage(self.config)

            self.map_page.compat_requested.connect(
                lambda: self.set_map_render("software")
            )

            self.map_page.targets_received.connect(self.on_map_targets)
            self.map_page.weapon_received.connect(self.on_map_weapon)
        else:
            self.map_page.retranslate()

        return self.map_page

    def build_map_card(self):
        frame, layout = card()

        layout.addWidget(label(tr("s_map"), "title"))

        source = Segmented(
            [
                ("deadline", tr("s_map_source_deadline")),
                ("squadcalc", "squadcalc.app")
            ],
            self.config["map_source"]
        )

        source.changed.connect(self.set_map_source)

        self.setting_row(layout, tr("s_map_source"), source)

        self.add_toggle(
            layout,
            tr("s_map_follow"),
            "map_follow",
            lambda _checked: self.update_map_status()
        )

        render = Segmented(
            [
                ("auto", tr("s_map_render_auto")),
                ("software", tr("s_map_render_software"))
            ],
            self.config["map_render"]
        )

        render.changed.connect(self.set_map_render)

        self.setting_row(layout, tr("s_map_render"), render)

        hint = label(tr("s_map_render_hint"), "small")

        hint.setWordWrap(True)

        layout.addWidget(hint)

        self.add_toggle(layout, tr("s_map_external"), "map_external")

        clear_button = QPushButton(tr("s_map_clear"))

        clear_button.setProperty("flat_style", True)

        def clear_cache():
            profile = self.map_page.profile if self.map_page else None

            if profile is not None:
                profile.clearHttpCache()

            clear_button.setText(tr("s_map_cleared"))

        clear_button.clicked.connect(clear_cache)

        row = QHBoxLayout()

        row.addWidget(clear_button)

        row.addStretch()

        layout.addLayout(row)

        return frame

    def set_map_source(self, source):
        if source == self.config["map_source"]:
            return

        self.config["map_source"] = source

        self.schedule_save()

        self.map_page.load_source()

    def set_map_render(self, mode):
        if mode == self.config["map_render"]:
            return

        self.config["map_render"] = mode

        save_config(self.config)

        answer = QMessageBox.question(
            self,
            tr("restart_title"),
            tr("restart_text")
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.restart()
        else:
            self.rebuild()

    def restart(self):
        """Start a new instance and quit (Chromium flags need a restart)."""
        program = sys.executable
        arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:]

        self.close()

        QProcess.startDetached(program, arguments)

        QApplication.quit()

    def closeEvent(self, event):
        # Release a held key and remove the virtual keyboard first, and save
        # the settings even if that fails: an error in a later step must not
        # leave a key down in the game.
        try:
            self.drop_auto_hold()
        finally:
            if self.save_timer.isActive():
                self.save_timer.stop()

            save_config(self.config)

        teardown_hotkeys(self)

        self.hold_timer.set_target(None)

        self.hold_timer.set_active(False)

        self.sight_timer.stop()

        if self.map_page is not None:
            self.map_page.shutdown()

        self.overlay.close()

        event.accept()
