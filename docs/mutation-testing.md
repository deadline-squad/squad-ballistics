# Mutation testing

How the test suite was checked with [mutmut](https://mutmut.readthedocs.io/) 3.8.1 (a mutant is a one-token change of the code; a test suite that still passes has missed it). Russian version: [mutation-testing.ru.md](mutation-testing.ru.md).

## Commands

Image `sb-ci-mut` is the CI image plus `pip install mutmut` (mutmut 3.8.1, Python 3.12). Each module is mutated in its own copy of the repository, with this `setup.cfg`:

```ini
[mutmut]
paths_to_mutate=<module>.py
tests_dir=tests/
max_children=4
pytest_add_cli_args=--deselect=tests/test_ui.py::test_selftest_does_not_touch_user_config_or_the_app_folder
also_copy=
    weapons.json
    README.md
    assets/
    tools/
    <the other *.py files of the repository>
```

```sh
mutmut run              # stats phase, then only the tests that call each mutated function
mutmut results --all true
mutmut show <id>        # the diff of one mutant
# one mutant against given tests, from the mutants/ directory:
MUTANT_UNDER_TEST=<module>.<id> python -m pytest -x -q -p no:cacheprovider <test files>
```

Test files given to `mutmut run`: `config`: `test_config.py`, `test_config_behaviour.py`, `test_ui.py`; `keystate`: `test_keystate.py`; `ballistics`: the ballistics, trim, mark and weapons tests of the suite; `crosshair`: `test_ui`, `test_calc_state`, `test_trim`, `test_view_toggle`, `test_marker_aids`, `test_no_hold_beep`, `test_vehicle_sights_ui`. The `keystate` run uses `max_children=1`: its X11 tests share the display `:97`. A timeout counts as a survivor until it is examined; a crash of the test process (segfault, abort, a NULL `Display*`) counts as killed. `crosshair` lists its test files with `pytest_add_cli_args_test_selection` (not `tests_dir`, which would also run `tests/test_hygiene.py`, whose docstring check fails on every mutant), `max_children=3`; the run was started as `nice -n 10 docker run --cpus 3 --memory 3g sb-ci-mut mutmut run --max-children 3` in a loop (`systemd-run --user`) that starts it again when mutmut stops with `KeyError: <pid>`, and resumes from the saved results. The survivors were then re-run by `MUTANT_UNDER_TEST=<id> pytest -x -p no:cacheprovider tests/test_crosshair_mutants.py <original files>` with three at a time.

## Results per module

"Original suite" is the suite of `dev` at `5f11d21` (measured again with the same commands, so the baseline of `config` and `keystate` can differ slightly from earlier runs). "New tests" are the tests added next to it; for `ballistics` the 459 mutants that the original run did not kill were re-run one by one against the final suite (`MUTANT_UNDER_TEST`, `pytest -x`), because a second full `mutmut run` of 2356 mutants with the flight-oracle tests did not fit in the time available (a started run was stopped at 286 mutants).

| Module | Total | Killed by original suite | Killed by new tests | Equivalent | Open |
|---|---|---|---|---|---|
| `config.py` | 324 | 300 (+9 crash) | 6 | 9 | 0 |
| `keystate.py` | 289 | 233 (+18 crash) | 30 (incl. 4 that had no test) | 8 | 0 |
| `ballistics.py` | 2356 | 1897 | 422 | 37 | 0 |
| `crosshair.py` | 4097 | 3860 (2554 killed, 1161 + 117 crash, 27 killed after a suspicious exit code, 1 hang) | 224 (incl. 25 that had no test) | 13 | 0 |

The original `ballistics` run had 439 survivors, 11 mutants without tests and 9 timeouts (459 not killed). The `crosshair.py` run covered all 4097 mutants in one `mutmut run` (3 worker processes, about 3 h 15 min, restarted once by the loop below after a `KeyError` of mutmut 3.8.1); it ended with 2554 killed, 1161 crash (killed), 212 survived, 144 suspicious, 25 without tests and 1 timeout. The 144 suspicious and the timeout were re-run one by one against the original files (`MUTANT_UNDER_TEST`, `pytest -x`): 117 abort the test process, 27 fail a test, `set_steps` 3 hangs; all killed. The 237 survivors and mutants without tests were re-run against `tests/test_crosshair_mutants.py` plus the original files: 224 killed (the last 9 after the final additions to the file), 13 equivalent (listed below), none open. `ballistics` `flat_low_elevation` 18 is now killed by `test_a_shot_that_comes_down_to_exactly_the_ground_at_the_peak_elevation_is_the_root`.

## New tests and the mutants they kill

Tests are in `tests/test_config_behaviour.py`, `tests/test_keystate.py` and the new `tests/test_ballistics_mutants.py`. The ballistics file checks the flight, the apex and the height of real and made-up weapons against the independent oracle `tests/flight.py` (the game's 50 Hz substeps), pins every validation message of `Weapon.from_dict` and `parse_weapons`, and checks `solve`, `mark_*`, `range_ladder`, `trim_for_landing` and `first_obstacle` with exact values and with exact boundary ties (for example `GRAVITY` patched to 10 so that 100 m/s reaches 1000 m at exactly 45 degrees).

## Crosshair tests and the mutants they kill

Tests are in `tests/test_crosshair_mutants.py` (102 tests, all through the real `MainWindow`; Qt objects that are slow or need a system, such as the confirmation box, `QProcess`, `QDesktopServices` and the key injectors, are replaced by recorders). They pin, with the exact translated text and value:

- the trim: `set_trim` rounding, limit and zero removal, `on_trim_edited`, `reset_trim`, `apply_landing` (height default, chosen arc, trim already set, limit text, lob refusal, direct-fire fallback, overflow message, a hold weapon whose own arc is the low one);
- the explanation of an unreachable target for each reason (`out_of_range`, `too_close`, `hold_limit`, `elevation_limit`), in degrees and in mils, and what an unreachable target clears (mark, info line, hold target, tiles);
- the hold-rate calibration of the mortar auto-lay (`calibrate_lay` boundaries and texts, `reset_lay_rate`, `lay_reset_time`);
- the sight and compass readings, the bearing target, the lay mark and failure text, the end of a bearing or sight lay, the layer wiring (`make_bearing_layer`, `apply_auto_hold`, `set_auto_hold`) and the F7 hotkey (`auto_hold`, `timed_lay_blocker`, `lay_step`, `start_sight_lay`);
- the settings: reset, map render and restart, map follow and preload, hotkey binding, monitor, distance step, window on top, the settings folder, `rebuild`, the weapon picker data.

### Survivors of the original run killed by the new tests

Mutant numbers are the suffix of `crosshair.xǁMainWindowǁ<function>__mutmut_<n>`.

| Function | Killed | Mutant numbers |
|---|---|---|
| `apply_landing` | 11 | 7, 32, 36, 62, 63, 64, 65, 74, 76, 77, 79 |
| `auto_hold` | 3 | 41, 43, 48 |
| `bearing_target` | 1 | 8 |
| `calibrate_lay` | 16 | 35, 36, 42, 49, 66, 68, 70, 71, 75, 76, 85, 86, 88, 89, 93, 94 |
| `compass_reader` | 5 | 1, 2, 3, 4, 5 |
| `lay_mark` | 3 | 1, 4, 7 |
| `lay_reset_time` | 1 | 2 |
| `lay_step` | 4 | 1, 21, 23, 28 |
| `make_bearing_layer` | 6 | 5, 8, 12, 16, 24, 25 |
| `on_arc_changed` | 1 | 5 |
| `on_bearing_lay_finished` | 4 | 2, 3, 5, 26 |
| `on_input_edited` | 1 | 6 |
| `on_map_follow_changed` | 5 | 1, 2, 3, 4, 5 |
| `on_sight_lay_finished` | 2 | 7, 13 |
| `on_trim_edited` | 2 | 6, 10 |
| `open_config_dir` | 2 | 7, 8 |
| `preload_map` | 6 | 1, 2, 3, 4, 5, 6 |
| `rebuild` | 1 | 7 |
| `reset_lay_rate` | 6 | 6, 10, 12, 14, 15, 16 |
| `reset_offset` | 3 | 2, 3, 4 |
| `reset_settings` | 17 | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 20, 23, 27, 31 |
| `restart` | 10 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| `save_sight_grab` | 4 | 5, 7, 8, 16 |
| `set_auto_hold` | 3 | 4, 9, 11 |
| `set_distance_step` | 3 | 1, 2, 3 |
| `set_hotkey` | 2 | 17, 33 |
| `set_map_render` | 14 | 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 |
| `set_monitor` | 3 | 1, 2, 3 |
| `set_on_top` | 1 | 4 |
| `set_trim` | 1 | 17 |
| `show_bearing_reading` | 11 | 1, 3, 4, 7, 8, 9, 10, 11, 12, 13, 21 |
| `show_sight_reading` | 10 | 1, 3, 4, 7, 8, 9, 10, 11, 12, 13 |
| `show_unreachable` | 54 | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 19, 21, 22, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 64 |
| `sight_target` | 2 | 2, 3 |
| `timed_lay_blocker` | 3 | 12, 13, 17 |
| `watch_screen` | 1 | 1 |
| `watch_sight` | 2 | 3, 4 |

## Equivalent survivors

### `config.py`

| Mutant | Diff | Reason |
|---|---|---|
| `_merge_53` | `config[key] = value -> None` | dead branch: every default key is handled by an earlier branch (pinned by test_every_default_setting_is_checked_by_a_branch_of_its_own) |
| `_read_5` | `open(path, "r", ...) -> open(path, ...)` | "r" is the default mode |
| `_read_10` | `encoding="utf-8" -> "UTF-8"` | alias of the same codec |
| `_read_14` | `message "nested too deeply" changed` | the ValueError text is swallowed by the caller |
| `_read_18` | `message "not a JSON object" changed` | the ValueError text is swallowed by the caller |
| `_read_19` | `message "not a JSON object" lowercased` | the ValueError text is swallowed by the caller |
| `save_config_26` | `fdopen(..., encoding=None)` | the file is written with json.dump (ensure_ascii), so it is pure ASCII |
| `save_config_29` | `fdopen(..., no encoding)` | same |
| `save_config_33` | `fdopen(..., encoding="UTF-8")` | same, and an alias |

### `keystate.py`

| Mutant | Diff | Reason |
|---|---|---|
| `_device_name_13` | `split(b"\0", 1) -> split(b"\0")` | only element [0] is used |
| `_device_name_17` | `split(b"\0", 1) -> split(b"\0", 2)` | only element [0] is used |
| `EvdevReader.__init___7` | `next_scan = 0.0 -> None` | overwritten by the first scan before it is read |
| `EvdevReader.__init___8` | `next_scan = 0.0 -> 1.0` | overwritten by the first scan before it is read |
| `EvdevReader.__call___2` | `failed = False -> None` | only its truthiness is used |
| `x11_button_reader_12` | `POINTER(c_int) -> POINTER(None)` | POINTER(None) is c_void_p and accepts any byref |
| `x11_button_reader_81` | `button // 8 < mask_len -> button / 8 <` | mask_len is an integer |
| `x11_reader_16` | `XOpenDisplay.argtypes = None` | ctypes passes the bytes argument the same way |

`keystate.py` mutants that crash the test process (killed by the crash): `x11_button_reader` 11, 14, 26, 27, 32, 33, 34, 43, 47, 55, 58, 59, 60, 61, 62; `x11_reader` 17, 27, 34. The other `POINTER(None)` mutants of `x11_button_reader` (13, 16, 18-23) alternate between killed and survived and were checked equivalent to mutant 12 by direct runs.

### `ballistics.py`

| Mutant | Diff | Reason |
|---|---|---|
| `Weapon.from_dict__mutmut_28` | `number("velocity", 0) -> None` | dead default: velocity is required and checked before |
| `Weapon.from_dict__mutmut_33` | `number("velocity", 0) -> 1` | dead default: velocity is required and checked before |
| `Weapon.time_to__mutmut_1` | `distance <= 0 -> distance < 0` | at 0 both branches return 0.0 |
| `Weapon.time_to__mutmut_7` | `distance <= boost_distance -> <` | branches meet at boost_distance (continuous) |
| `Weapon._coast_height__mutmut_24` | `tau > onset -> >=` | branches agree at tau == onset (continuous) |
| `Weapon._coast_height__mutmut_40` | `min(1.0, vx / cap) -> min(2.0, ...)` | vx never exceeds the cap, so vx / cap is at most 1 |
| `Weapon._coast_at__mutmut_24` | `tau > onset -> >=` | branches agree at tau == onset (continuous) |
| `Weapon._coast_at__mutmut_40` | `min(1.0, vx / cap) -> min(2.0, ...)` | vx never exceeds the cap, so vx / cap is at most 1 |
| `Weapon._coast_at__mutmut_49` | `turn >= pi/2 -> >` | needs turn == pi/2 to the last bit; both sides give the same limit |
| `Weapon.flight_height__mutmut_17` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `Weapon.flight_height__mutmut_51` | `ahead <= cos*length -> <` | branches agree at ahead == cos*length (continuous) |
| `Weapon.flight_height__mutmut_108` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `Weapon.flight_at__mutmut_17` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `Weapon.flight_at__mutmut_69` | `ahead <= cos*length -> <` | branches agree at ahead == cos*length (continuous) |
| `Weapon.flight_at__mutmut_145` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `Weapon.apex_height__mutmut_18` | `x > ahead -> >=` | point at x == ahead: the apex there is also covered by the next test (continuous) |
| `Weapon.peak_elevation__mutmut_23` | `high - low <= ANGLE_TOLERANCE -> <` | tie on a tolerance |
| `Weapon.peak_elevation__mutmut_25` | `left_height < right_height -> <=` | a tie only happens on a -inf plateau, where every caller treats the peak as unreachable |
| `x__fly_boost__mutmut_30` | `speed_squared > cap_squared -> >=` | at equality the cap factor is 1 |
| `x__fly_boost__mutmut_69` | `speed_squared > cap_squared -> >=` | at equality the cap factor is 1 |
| `x__find_root__mutmut_5` | `far_error >= 0 -> > 0` | far_error == 0 means far is already the root; the bracket then closes on it |
| `x__find_root__mutmut_29` | `kept = 0 -> None` | kept is only compared with -1 and 1 |
| `x__find_root__mutmut_35` | `abs(far - near) <= ANGLE_TOLERANCE -> <` | tie on a tolerance; the root is the same |
| `x__find_root__mutmut_46` | `abs(root_error) <= HEIGHT_TOLERANCE -> <` | tie on a tolerance; the root is the same |
| `x__find_root__mutmut_48` | `root_error < 0 -> <= 0` | root_error == 0 is caught by the tolerance test just before |
| `x_solve__mutmut_95` | `continue -> break` | the high arc is the last one of the loop |
| `x_first_obstacle__mutmut_2` | `not reachable or not profile -> and` | an unsolved shot has a NaN angle: every height comparison is false and None is returned anyway |
| `x_first_obstacle__mutmut_36` | `break -> return` | the function returns None right after the loop |
| `x_mark_offset__mutmut_7` | `fov <= 179 -> fov <= 180` | screen_offset repeats the guard with the same message |
| `x_mark_resolution__mutmut_16` | `solve(..., arc) -> solve(..., None)` | only the line of sight (angle - sight_angle) is used, the same on every arc |
| `x_mark_resolution__mutmut_22` | `solve(..., arc, aim_lift) -> solve(..., arc)` | only the line of sight is used, the same on every arc and for every aim_lift |
| `x_mark_height_resolution__mutmut_30` | `solve(..., arc) -> solve(..., None)` | the high arc has a negative slope, so mark_resolution returns None first |
| `x_mark_visible_range__mutmut_50` | `high - low > 0.01 -> >=` | one more halving; the edge is only specified to 1 cm |
| `x_trim_for_landing__mutmut_40` | `distance <= 0 -> < 0` | solve raises the same message for distance 0 |
| `x_range_ladder__mutmut_67` | `s <= distance / 4 -> <` | LADDER_STEPS divide each other, so the rounding is the same at the tie |
| `x_load_weapons__mutmut_5` | `open(path, "r", ...) -> open(path, ...)` | "r" is the default mode |
| `x_load_weapons__mutmut_10` | `encoding="utf-8" -> "UTF-8"` | alias of the same codec |

### `crosshair.py`

| Mutant | Diff | Reason |
|---|---|---|
| `MainWindow.set_trim__mutmut_4` | `round(...) + 0.0 -> - 0.0` | only a zero trim differs (0.0 vs -0.0) and a zero trim is not stored |
| `MainWindow.rebuild__mutmut_3` | `if self.map_page is not None -> is None` | build_web_page puts the map page into the new stack before the old central widget's deferred delete runs, so it survives without the detach (checked: test_rebuilding_keeps_the_typed_inputs_the_page_and_the_map passes with the mutant) |
| `MainWindow.rebuild__mutmut_4` | `removeWidget(self.map_page) -> removeWidget(None)` | removeWidget(None) is a no-op and the next line (setParent(None)) detaches the page anyway; same reason as mutant 3 |
| `MainWindow.on_trim_edited__mutmut_9` | `trim_status.setText("") -> setText(None)` | QLabel.setText(None) shows the empty text (checked with PyQt6 6.12.0) |
| `MainWindow.on_arc_changed__mutmut_4` | `trim_status.setText("") -> setText(None)` | same: QLabel.setText(None) is the empty text |
| `MainWindow.on_input_edited__mutmut_5` | `calculate(show_errors=False) -> show_errors=None` | None and False are both falsy in `if show_errors or ...` |
| `MainWindow.distance_up__mutmut_4` | `calculate(show_errors=False) -> None` | falsy, as above |
| `MainWindow.distance_up__mutmut_5` | `calculate(show_errors=False) -> True` | `show_errors` only matters for an empty distance field, and NumberEdit.add has just written a number into it |
| `MainWindow.distance_down__mutmut_5` | `calculate(show_errors=False) -> None` | falsy, as above |
| `MainWindow.distance_down__mutmut_6` | `calculate(show_errors=False) -> True` | same as distance_up 5 |
| `MainWindow.set_hotkey__mutmut_26` | `hotkeys.get(name, "") -> get(name, None)` | findData misses either default and `max(0, -1)` is index 0, the entry of the empty key ("hk_none" is the first item) |
| `MainWindow.set_hotkey__mutmut_28` | `hotkeys.get(name, "") -> get(name, )` | same as 26 (default None) |
| `MainWindow.set_hotkey__mutmut_31` | `hotkeys.get(name, "") -> get(name, "XXXX")` | same as 26: no item has that data, index 0 again |

`set_steps__mutmut_3` (the `while` that empties the step rows never ends) is killed by a hang: the original suite times out on it, which counts as killed.

## Killed mutants per test group

Mutant numbers are the suffix of `ballistics.<function>__mutmut_<n>` (the 459 not killed by the original suite). Every id of a row was killed by at least one test of its group when run alone with `pytest -x`; the flight, apex and boost-table rows need the oracle tests.

| Test group | Function: killed mutant numbers |
|---|---|
| Entry and file validation: test_an_invalid_entry_is_refused_with_its_reason, test_limits_that_the_entry_reaches_exactly_are_valid, test_an_entry_with_every_field_is_read_field_by_field, test_an_entry_with_only_a_velocity_gets_the_defaults, test_a_deceleration_is_a_negative_acceleration_with_its_own_time, test_the_weapons_file_is_checked_with_a_message_each_for_what_is_wrong, test_the_weapons_file_is_read_as_utf8_whatever_the_locale, test_the_two_views_of_an_rmb_sight_name_each_other | `Weapon.from_dict`: 2, 9, 13, 19, 22, 25, 71, 87, 88, 89, 90, 93, 96, 100, 101, 111, 113, 141, 144, 155, 157, 161, 162, 166, 184, 193, 194, 197, 198, 199, 209, 230, 250, 251, 273, 275, 276, 278, 286, 289, 290, 296, 302, 312, 313, 314, 320, 321, 323, 328, 329, 337, 338, 339, 342, 346, 347, 349, 353, 354, 355, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379<br>`load_weapons`: 3, 6, 13, 14<br>`parse_weapons`: 2, 3, 4, 15, 16, 17<br>`view_twin`: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11<br>`Weapon.hold_time`: 7 |
| Straight flight and clamp: the time_to / velocity_at tests, test_the_key_holds_the_barrel_down_to_the_lowest_elevation_inclusive, test_a_fall_that_ends_exactly_at_the_speed_cap_does_not_clamp_the_flight | `Weapon.time_to`: 3, 6, 9, 17, 18, 21, 22, 23<br>`Weapon.velocity_at`: 1, 2, 3<br>`Weapon._clamps_before`: 2, 7, 10, 11, 12<br>`Weapon._clamped_launch`: 20 |
| Game-substep oracle: test_the_flight_follows_the_games_substeps, test_the_flight_of_made_up_weapons_follows_the_games_substeps, test_a_shell_fired_faster_than_its_cap_is_followed_close_to_the_muzzle, the "shell that nearly stops" case of the made-up test | `Weapon.flight_at`: 26, 27, 28, 29, 30, 31, 32, 37, 38, 59, 60, 64, 65, 66, 70, 72, 74, 75, 76, 77, 83, 84, 85, 86, 87, 88, 90, 91, 92, 93, 94, 95, 96, 97, 98, 103, 108, 109, 110, 111, 114, 131, 132, 138, 146, 147, 148, 173, 188, 192, 197<br>`Weapon.flight_height`: 54, 65, 109, 110<br>`_fly_boost`: 17, 18 |
| Apex: test_the_apex_follows_the_games_substeps, test_the_apex_of_a_parabola_from_a_raised_muzzle_is_its_top_if_it_has_been_passed, test_a_slow_boost_along_the_barrel_*, test_a_boost_along_the_barrel_that_is_still_climbing_*, test_the_top_after_the_burn_*, test_an_axis_boost_pushing_*, test_a_horizontal_boost_*, test_a_boost_that_peaks_exactly_when_it_ends_*, test_a_flat_shot_has_no_apex_above_its_muzzle | `Weapon.apex_height`: 7, 32, 33, 34, 35, 36, 37, 42, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 62, 64, 65, 69, 70, 75, 76, 78, 79, 80, 81, 82, 84, 86, 87, 88, 89, 96, 102, 103, 104, 106, 107 |
| Capped coast: test_a_capped_flight_never_reaches_a_point_beyond_where_it_has_turned_straight_down, test_a_capped_flight_comes_down_more_and_more_steeply_to_the_end_of_its_reach | `Weapon._coast_at`: 5, 12, 13, 20, 21, 23, 25, 26, 27, 28, 30, 31, 50, 51, 52, 53, 54, 55, 72, 75 |
| Boost table: test_the_boost_table_has_a_node_per_degree_*, test_a_boost_node_is_the_boost_flown_*, test_four_nodes_around_the_elevation_*, test_the_substep_points_are_the_weighted_sum_*, test_the_substep_holding_a_distance_is_found_by_halving | `_BoostTable.__init__`: 1, 2, 3, 4, 5, 6, 7, 8, 9<br>`_BoostTable.node`: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17<br>`_BoostTable.stencil`: 15, 17, 18, 20<br>`_BoostTable.segment`: 5, 6, 7, 11, 19<br>`_BoostTable.points`: 4, 6, 7, 8, 13, 14, 15 |
| Elevation searches: test_a_root_is_bracketed_by_doubling_steps_*, test_the_elevation_searches_find_their_roots_in_the_expected_number_of_flights, test_the_low_elevation_to_the_longest_range_*, test_a_flat_low_elevation_lands_where_the_game_lands_*, test_the_peak_search_height_is_a_target_the_shot_can_just_reach | `_find_root`: 17, 24, 25, 26, 30, 34, 54, 56, 65<br>`Weapon.elevations_to`: 21, 22, 43, 56, 63<br>`Weapon.flat_low_elevation`: 1, 2, 4, 12, 19, 27 |
| solve and trajectory: test_a_target_the_elevation_limits_refuse_*, test_an_arc_at_exactly_the_lowest_elevation_limit_*, test_an_arc_beyond_the_limits_*, test_the_apex_of_a_shot_that_only_falls_is_its_muzzle, the solve message / aim / limit tests, test_a_path_is_sampled_at_sixty_five_points_by_default | `solve`: 13, 14, 15, 16, 19, 20, 21, 22, 43, 46, 50, 51, 72, 73, 81, 84, 85, 86, 105, 106, 144, 145, 146, 155<br>`trajectory`: 1<br>`resolve_arc`: 2, 6 |
| Obstacle search: the first_obstacle tests, test_a_path_that_just_touches_the_terrain_does_not_pass_under_it, test_an_obstacle_search_for_a_target_out_of_reach_finds_nothing | `first_obstacle`: 1, 17, 21, 32, 35, 41 |
| Mark: test_a_pixel_of_the_mark_is_worth_*, the mark_visible_range tests, test_a_weapon_with_a_gravity_of_exactly_one_has_a_mark, test_a_weapon_laid_by_elevation_has_no_mark_*, the screen_offset / mark_offset tests | `mark_resolution`: 2, 6, 11, 25, 28, 30, 31, 32, 33, 44, 57, 58, 59, 60, 62, 63, 64, 69, 71<br>`mark_height_resolution`: 2, 5, 14, 24, 36<br>`mark_visible_range`: 6, 11, 38, 43, 45, 49, 55, 66, 71, 73, 84, 87, 88<br>`_mark_at`: 11, 24<br>`mark_offset`: 4, 5, 6, 8, 9, 10, 11<br>`screen_offset`: 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18 |
| Trim and ladder: test_a_trim_is_refused_with_the_reason_in_words, test_a_shot_one_metre_away_*, the range_ladder tests | `trim_for_landing`: 8, 9, 14, 15, 27, 28, 30, 31, 37, 38, 41, 43, 47, 49<br>`range_ladder`: 13, 16, 17, 41, 44, 47, 50, 51, 52, 53, 54, 60, 70, 81, 82 |

## Capped boost weapons against the oracle

Two made-up weapons (a speed cap with a motor) first differed from `tests/flight.py` by up to 0.2 m near the muzzle. Findings: (1) "rocket that burns until the cap" was an oracle-input error: the oracle treats `acceleration_timeout` 0 as "burns forever" while `acceleration_time` 0 means "no motor" in `ballistics.py` (the only game weapon with that combination in `tests/data/game_weapons.json` is NLAW); the 2 km differences came from that. (2) The two cap weapons with a finite burn differ from the oracle by at most 1.6 cm over -4..75 degrees at 0.5-900 m (4 mm for the follow-velocity one, 9 mm at 900 m, -4 degrees) and by 4 cm (follows velocity) and 0.5 m (flies along the barrel) at 89 degrees and 120 m. That is the interpolation error of the boost table, whose nodes are 1 degree apart, where the flight depends steeply on the elevation (near vertical); it is an approximation limit, not a logic defect, and no weapon is aimed there. The tolerance of the oracle tests stays at the 3 mm / 0.01 m of the real weapons and these two weapons are not in the made-up list. (3) A separate defect was found and filed: [issue 16](https://github.com/deadline-squad/squad-ballistics/issues/16), `flight_at` raises `math domain error` within about 1e-4 m of the end of a capped flight's reach.

## Not killed and not proven equivalent

None: every mutant of `config.py`, `keystate.py`, `ballistics.py` and `crosshair.py` is killed or named equivalent above.
