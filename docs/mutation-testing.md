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

Test files given to `mutmut run`: `config`: `test_config.py`, `test_config_behaviour.py`, `test_ui.py`; `keystate`: `test_keystate.py`; `ballistics`: the ballistics, trim, mark and weapons tests of the suite; `crosshair`: `test_ui`, `test_calc_state`, `test_trim`, `test_view_toggle`, `test_marker_aids`, `test_no_hold_beep`, `test_vehicle_sights_ui`. The `keystate` run uses `max_children=1`: its X11 tests share the display `:97`. A timeout counts as a survivor until it is examined; a crash of the test process (segfault, a NULL `Display*`) counts as killed.

## Results per module

"Original suite" is the suite of `dev` at `5f11d21` (measured again with the same commands, so the baseline of `config` and `keystate` can differ slightly from earlier runs). "New tests" are the tests added next to it; for `ballistics` they were checked mutant by mutant against the survivors of the original run (one mutant, `pytest -x`), not by a second full `mutmut run`.

| Module | Total | Killed by original suite | Killed by new tests | Equivalent | Not examined |
|---|---|---|---|---|---|
| `config.py` | 324 | 300 (+9 crash) | 6 | 9 | 0 |
| `keystate.py` | 289 | 233 (+18 crash) | 30 (incl. 4 that had no test) | 8 | 0 |
| `ballistics.py` | 2356 | 1897 | 339 | 11 | 109 |
| `crosshair.py` | 4097 | 700 (970 of 4097 run) | 0 | 0 | 3397 (see below) |

The original `ballistics` run had 439 survivors, 11 mutants without tests and 9 timeouts (459 not killed). `crosshair.py` was not finished: the run (4097 mutants, 970 checked: 700 killed, 158 survived, 86 suspicious, 25 without tests, 1 crash) was stopped when the time budget ran out; its survivors are listed below as not examined.

## New tests and the mutants they kill

Tests are in `tests/test_config_behaviour.py`, `tests/test_keystate.py` and the new `tests/test_ballistics_mutants.py`. The ballistics file checks the flight, the apex and the height of real and made-up weapons against the independent oracle `tests/flight.py` (the game's 50 Hz substeps), pins every validation message of `Weapon.from_dict` and `parse_weapons`, and checks `solve`, `mark_*`, `range_ladder`, `trim_for_landing` and `first_obstacle` with exact values and with exact boundary ties (for example `GRAVITY` patched to 10 so that 100 m/s reaches 1000 m at exactly 45 degrees).

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
| `Weapon.flight_height__mutmut_17` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `Weapon.flight_height__mutmut_51` | `ahead <= cos*length -> <` | branches agree at ahead == cos*length (continuous) |
| `Weapon.flight_height__mutmut_108` | `ahead < x -> ahead <= x` | branches agree at ahead == x (continuous) |
| `x_mark_offset__mutmut_7` | `fov <= 179 -> fov <= 180` | screen_offset repeats the guard with the same message |
| `x_mark_visible_range__mutmut_50` | `high - low > 0.01 -> >=` | one more halving; the edge is only specified to 1 cm |
| `x_load_weapons__mutmut_5` | `open(path, "r", ...) -> open(path, ...)` | "r" is the default mode |
| `x_load_weapons__mutmut_10` | `encoding="utf-8" -> "UTF-8"` | alias of the same codec |

## Not examined

Survivors of `ballistics.py` that no new test kills yet and that are not proven equivalent (the time budget ended): 109. Most are in `_find_root`, `flat_low_elevation`, `elevations_to`, `peak_elevation`, `_BoostTable` and the coast of a capped flight, which need more oracle tests (bracket and step-size changes there probably change only the iteration count). They are not declared equivalent.

| Mutant | Diff |
|---|---|
| `x__find_root__mutmut_17` | `-        far = min(max(top + direction * step, -ELEVATION_LIMIT), ELEVATION_LIMIT) +        far = min(max(top + direction / step, -ELEVATION` |
| `x__find_root__mutmut_24` | `-        step *= 2 +        step = 2 ` |
| `x__find_root__mutmut_25` | `-        step *= 2 +        step /= 2 ` |
| `x__find_root__mutmut_26` | `-        step *= 2 +        step *= 3 ` |
| `x__find_root__mutmut_29` | `-    kept = 0 +    kept = None ` |
| `x__find_root__mutmut_30` | `-    kept = 0 +    kept = 1 ` |
| `x__find_root__mutmut_34` | `-        if abs(far - near) <= ANGLE_TOLERANCE: +        if abs(far + near) <= ANGLE_TOLERANCE: ` |
| `x__find_root__mutmut_35` | `-        if abs(far - near) <= ANGLE_TOLERANCE: +        if abs(far - near) < ANGLE_TOLERANCE: ` |
| `x__find_root__mutmut_46` | `-        if abs(root_error) <= HEIGHT_TOLERANCE: +        if abs(root_error) < HEIGHT_TOLERANCE: ` |
| `x__find_root__mutmut_48` | `-        if root_error < 0: +        if root_error <= 0: ` |
| `x__find_root__mutmut_5` | `-    while far_error >= 0: +    while far_error > 0: ` |
| `x__find_root__mutmut_54` | `-                near_error /= 2 +                near_error = 2 ` |
| `x__find_root__mutmut_56` | `-                near_error /= 2 +                near_error /= 3 ` |
| `x__find_root__mutmut_65` | `-                far_error /= 2 +                far_error /= 3 ` |
| `x__fly_boost__mutmut_30` | `-            if speed_squared > cap_squared: +            if speed_squared >= cap_squared: ` |
| `x__fly_boost__mutmut_69` | `-            if speed_squared > cap_squared: +            if speed_squared >= cap_squared: ` |
| `x_first_obstacle__mutmut_2` | `-    if not solution.reachable or not profile or not step: +    if not solution.reachable and not profile or not step: ` |
| `x_first_obstacle__mutmut_36` | `-            break +            return ` |
| `x_first_obstacle__mutmut_41` | `-        if weapon.flight_height(rad, x) < profile[i]: +        if weapon.flight_height(rad, x) <= profile[i]: ` |
| `x_mark_height_resolution__mutmut_30` | `-    solution = solve(weapon, distance, height, arc, aim_lift) +    solution = solve(weapon, distance, height, None, aim_lift) ` |
| `x_mark_resolution__mutmut_11` | `-    if weapon.aim != "overlay" or weapon.g == 0: +    if weapon.aim != "overlay" or weapon.g == 1: ` |
| `x_mark_resolution__mutmut_16` | `-    centre = solve(weapon, distance, height, arc, aim_lift) +    centre = solve(weapon, distance, height, None, aim_lift) ` |
| `x_mark_resolution__mutmut_22` | `-    centre = solve(weapon, distance, height, arc, aim_lift) +    centre = solve(weapon, distance, height, arc, ) ` |
| `x_mark_resolution__mutmut_6` | `-    if weapon.aim != "overlay" or weapon.g == 0: +    if weapon.aim != "overlay" and weapon.g == 0: ` |
| `x_mark_visible_range__mutmut_11` | `-    if weapon.aim != "overlay" or weapon.g == 0: +    if weapon.aim != "overlay" or weapon.g == 1: ` |
| `x_mark_visible_range__mutmut_6` | `-    if weapon.aim != "overlay" or weapon.g == 0: +    if weapon.aim != "overlay" and weapon.g == 0: ` |
| `x_range_ladder__mutmut_50` | `-            distance += LADDER_STEPS[0] +            distance = LADDER_STEPS[0] ` |
| `x_range_ladder__mutmut_51` | `-            distance += LADDER_STEPS[0] +            distance -= LADDER_STEPS[0] ` |
| `x_range_ladder__mutmut_67` | `-            (s for s in LADDER_STEPS if s <= distance / 4), default=LADDER_STEPS[0] +            (s for s in LADDER_STEPS if s < distance /` |
| `x_solve__mutmut_155` | `-        start_y, aim_height, weapon.apex_height(rad, distance) +        aim_height, weapon.apex_height(rad, distance) ` |
| `x_solve__mutmut_46` | `-        result.velocity = weapon.velocity_at(math.hypot(distance, aim_rise)) +        result.velocity = None ` |
| `x_solve__mutmut_50` | `-        result.velocity = weapon.velocity_at(math.hypot(distance, aim_rise)) +        result.velocity = weapon.velocity_at(math.hypot(aim_r` |
| `x_solve__mutmut_51` | `-        result.velocity = weapon.velocity_at(math.hypot(distance, aim_rise)) +        result.velocity = weapon.velocity_at(math.hypot(dista` |
| `x_solve__mutmut_84` | `-        if not low_limit <= angle <= high_limit: +        if not low_limit < angle <= high_limit: ` |
| `x_solve__mutmut_95` | `-            continue +            break ` |
| `x_trim_for_landing__mutmut_40` | `-    if distance <= 0: +    if distance < 0: ` |
| `Weapon._coast_at__mutmut_24` | `-        if tau > onset: +        if tau >= onset: ` |
| `Weapon._coast_at__mutmut_40` | `-            cos_onset = min(1.0, vx / cap) +            cos_onset = min(2.0, vx / cap) ` |
| `Weapon._coast_at__mutmut_49` | `-            if turn >= math.pi / 2: +            if turn > math.pi / 2: ` |
| `Weapon._coast_at__mutmut_50` | `-            if turn >= math.pi / 2: +            if turn >= math.pi * 2: ` |
| `Weapon._coast_at__mutmut_51` | `-            if turn >= math.pi / 2: +            if turn >= math.pi / 3: ` |
| `Weapon._coast_at__mutmut_52` | `-                return -math.inf, math.inf, -math.pi / 2 +                return +math.inf, math.inf, -math.pi / 2 ` |
| `Weapon._coast_at__mutmut_53` | `-                return -math.inf, math.inf, -math.pi / 2 +                return -math.inf, math.inf, -math.pi * 2 ` |
| `Weapon._coast_at__mutmut_54` | `-                return -math.inf, math.inf, -math.pi / 2 +                return -math.inf, math.inf, +math.pi / 2 ` |
| `Weapon._coast_at__mutmut_55` | `-                return -math.inf, math.inf, -math.pi / 2 +                return -math.inf, math.inf, -math.pi / 3 ` |
| `Weapon._coast_height__mutmut_24` | `-        if tau > onset: +        if tau >= onset: ` |
| `Weapon._coast_height__mutmut_40` | `-            cos_onset = min(1.0, vx / cap) +            cos_onset = min(2.0, vx / cap) ` |
| `Weapon.apex_height__mutmut_102` | `-    if vy > 0 and g and x + vx * vy / g <= ahead: +    if vy >= 0 and g and x + vx * vy / g <= ahead: ` |
| `Weapon.apex_height__mutmut_104` | `-    if vy > 0 and g and x + vx * vy / g <= ahead: +    if vy > 0 and g and x - vx * vy / g <= ahead: ` |
| `Weapon.apex_height__mutmut_106` | `-    if vy > 0 and g and x + vx * vy / g <= ahead: +    if vy > 0 and g and x + vx / vy / g <= ahead: ` |
| `Weapon.apex_height__mutmut_107` | `-    if vy > 0 and g and x + vx * vy / g <= ahead: +    if vy > 0 and g and x + vx * vy / g < ahead: ` |
| `Weapon.apex_height__mutmut_18` | `-            if x > ahead: +            if x >= ahead: ` |
| `Weapon.apex_height__mutmut_42` | `-        if denominator > 0: +        if denominator > 1: ` |
| `Weapon.apex_height__mutmut_46` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost or cos * (` |
| `Weapon.apex_height__mutmut_48` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 <= rising <= boost and cos *` |
| `Weapon.apex_height__mutmut_49` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising < boost and cos * (` |
| `Weapon.apex_height__mutmut_50` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos / ` |
| `Weapon.apex_height__mutmut_51` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_54` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_55` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_56` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_57` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_58` | `-            if 0 < rising <= boost and cos * (v0 * rising + 0.5 * a * rising ** 2) <= ahead: +            if 0 < rising <= boost and cos * ` |
| `Weapon.apex_height__mutmut_7` | `-    ahead = distance - start_x +    ahead = distance + start_x ` |
| `Weapon.apex_height__mutmut_78` | `-        x, y = cos * length, sin * length - 0.5 * g * boost * boost +        x, y = cos / length, sin * length - 0.5 * g * boost * boost ` |
| `Weapon.apex_height__mutmut_86` | `-        vx, vy = cos * end_speed, sin * end_speed - g * boost +        vx, vy = cos / end_speed, sin * end_speed - g * boost ` |
| `Weapon.apex_height__mutmut_96` | `-        x, y, vx, vy = 0.0, 0.0, v0 * cos, v0 * sin +        x, y, vx, vy = 1.0, 0.0, v0 * cos, v0 * sin ` |
| `Weapon.elevations_to__mutmut_43` | `-    if self.flight_height(top, distance) < height: +    if self.flight_height(top, distance) <= height: ` |
| `Weapon.elevations_to__mutmut_56` | `-    return _find_root(error, top, -1), _find_root(error, top, 1) +    return _find_root(error, top, -2), _find_root(error, top, 1) ` |
| `Weapon.elevations_to__mutmut_63` | `-    return _find_root(error, top, -1), _find_root(error, top, 1) +    return _find_root(error, top, -1), _find_root(error, top, 2) ` |
| `Weapon.flat_low_elevation__mutmut_1` | `-    if self.is_parabola and not self._clamps_before(0.0): +    if self.is_parabola or not self._clamps_before(0.0): ` |
| `Weapon.flat_low_elevation__mutmut_12` | `-    if distance > longest: +    if distance >= longest: ` |
| `Weapon.flat_low_elevation__mutmut_18` | `-    if error(top) < 0: +    if error(top) <= 0: ` |
| `Weapon.flat_low_elevation__mutmut_19` | `-    if error(top) < 0: +    if error(top) < 1: ` |
| `Weapon.flat_low_elevation__mutmut_27` | `-    return _find_root(error, top, -1) +    return _find_root(error, top, -2) ` |
| `Weapon.flat_low_elevation__mutmut_4` | `-    if self.is_parabola and not self._clamps_before(0.0): +    if self.is_parabola and not self._clamps_before(1.0): ` |
| `Weapon.flight_at__mutmut_145` | `-        if ahead < x: +        if ahead <= x: ` |
| `Weapon.flight_at__mutmut_17` | `-        if ahead < x: +        if ahead <= x: ` |
| `Weapon.flight_at__mutmut_69` | `-        if ahead <= cos * length: +        if ahead < cos * length: ` |
| `Weapon.peak_elevation__mutmut_23` | `-        if high - low <= ANGLE_TOLERANCE: +        if high - low < ANGLE_TOLERANCE: ` |
| `Weapon.peak_elevation__mutmut_25` | `-        if left_height < right_height: +        if left_height <= right_height: ` |
| `_BoostTable.__init____mutmut_7` | `-    self.count = round(math.pi / BOOST_NODE_SPACING) + 1 +    self.count = round(math.pi / BOOST_NODE_SPACING) + 2 ` |
| `_BoostTable.node__mutmut_1` | `-    node = self.nodes[index] +    node = None ` |
| `_BoostTable.node__mutmut_13` | `-        node = self.nodes[index] = ( -            tuple(p[0] for p in points), tuple(p[1] for p in points), vx, vy -        ) +        node` |
| `_BoostTable.node__mutmut_14` | `-            tuple(p[0] for p in points), tuple(p[1] for p in points), vx, vy +            tuple(None), tuple(p[1] for p in points), vx, vy ` |
| `_BoostTable.node__mutmut_16` | `-            tuple(p[0] for p in points), tuple(p[1] for p in points), vx, vy +            tuple(p[0] for p in points), tuple(None), vx, vy ` |
| `_BoostTable.node__mutmut_17` | `-            tuple(p[0] for p in points), tuple(p[1] for p in points), vx, vy +            tuple(p[0] for p in points), tuple(p[2] for p in ` |
| `_BoostTable.node__mutmut_4` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING +            None, -math.pi / 2 + index * BOOST_NODE_SPACING ` |
| `_BoostTable.node__mutmut_5` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING +            self.weapon, None ` |
| `_BoostTable.node__mutmut_6` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING +            -math.pi / 2 + index * BOOST_NODE_SPACING ` |
| `_BoostTable.node__mutmut_7` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING -        ) +            self.weapon, ) ` |
| `_BoostTable.node__mutmut_8` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING +            self.weapon, -math.pi / 2 - index * BOOST_NODE_SPACING ` |
| `_BoostTable.node__mutmut_9` | `-            self.weapon, -math.pi / 2 + index * BOOST_NODE_SPACING +            self.weapon, -math.pi * 2 + index * BOOST_NODE_SPACING ` |
| `_BoostTable.points__mutmut_13` | `-            w0 * y0[k] + w1 * y1[k] + w2 * y2[k] + w3 * y3[k], +            w0 * y0[k] + w1 * y1[k] + w2 * y2[k] - w3 * y3[k], ` |
| `_BoostTable.points__mutmut_14` | `-            w0 * y0[k] + w1 * y1[k] + w2 * y2[k] + w3 * y3[k], +            w0 * y0[k] + w1 * y1[k] - w2 * y2[k] + w3 * y3[k], ` |
| `_BoostTable.points__mutmut_15` | `-            w0 * y0[k] + w1 * y1[k] + w2 * y2[k] + w3 * y3[k], +            w0 * y0[k] - w1 * y1[k] + w2 * y2[k] + w3 * y3[k], ` |
| `_BoostTable.points__mutmut_4` | `-    for k in range(self.steps + 1): +    for k in range(self.steps - 1): ` |
| `_BoostTable.points__mutmut_6` | `-            w0 * x0[k] + w1 * x1[k] + w2 * x2[k] + w3 * x3[k], +            w0 * x0[k] + w1 * x1[k] + w2 * x2[k] - w3 * x3[k], ` |
| `_BoostTable.points__mutmut_7` | `-            w0 * x0[k] + w1 * x1[k] + w2 * x2[k] + w3 * x3[k], +            w0 * x0[k] + w1 * x1[k] - w2 * x2[k] + w3 * x3[k], ` |
| `_BoostTable.points__mutmut_8` | `-            w0 * x0[k] + w1 * x1[k] + w2 * x2[k] + w3 * x3[k], +            w0 * x0[k] - w1 * x1[k] + w2 * x2[k] + w3 * x3[k], ` |
| `_BoostTable.segment__mutmut_11` | `-        mid = (low + high) // 2 +        mid = (low + high) // 3 ` |
| `_BoostTable.segment__mutmut_19` | `-        if w0 * x0[mid] + w1 * x1[mid] + w2 * x2[mid] + w3 * x3[mid] <= ahead: +        if w0 * x0[mid] + w1 * x1[mid] + w2 * x2[mid] + w3 ` |
| `_BoostTable.segment__mutmut_5` | `-    while high - low > 1: +    while high + low > 1: ` |
| `_BoostTable.segment__mutmut_6` | `-    while high - low > 1: +    while high - low >= 1: ` |
| `_BoostTable.segment__mutmut_7` | `-    while high - low > 1: +    while high - low > 2: ` |
| `_BoostTable.stencil__mutmut_15` | `-    first = min(max(int(at) - 1, 0), self.count - 4) +    first = min(max(int(at) + 1, 0), self.count - 4) ` |
| `_BoostTable.stencil__mutmut_17` | `-    first = min(max(int(at) - 1, 0), self.count - 4) +    first = min(max(int(at) - 2, 0), self.count - 4) ` |
| `_BoostTable.stencil__mutmut_18` | `-    first = min(max(int(at) - 1, 0), self.count - 4) +    first = min(max(int(at) - 1, 1), self.count - 4) ` |
| `_BoostTable.stencil__mutmut_20` | `-    first = min(max(int(at) - 1, 0), self.count - 4) +    first = min(max(int(at) - 1, 0), self.count - 5) ` |

### `crosshair.py` (run stopped)

| Mutant | Status | Diff |
|---|---|---|
| `MainWindow.rebuild__mutmut_3` | survived | `-    if self.map_page is not None: +    if self.map_page is None: ` |
| `MainWindow.rebuild__mutmut_4` | survived | `-        self.pages.removeWidget(self.map_page) +        self.pages.removeWidget(None) ` |
| `MainWindow.rebuild__mutmut_7` | survived | `-    self.height_entry.setText(texts[1]) +    self.height_entry.setText(None) ` |
| `MainWindow.preload_map__mutmut_1` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if not self.config["map_follow"] and self.config["map_external"]:` |
| `MainWindow.preload_map__mutmut_2` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if self.config["map_follow"] or self.config["map_external"]: ` |
| `MainWindow.preload_map__mutmut_3` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if not self.config["XXmap_followXX"] or self.config["map_external` |
| `MainWindow.preload_map__mutmut_4` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if not self.config["MAP_FOLLOW"] or self.config["map_external"]: ` |
| `MainWindow.preload_map__mutmut_5` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if not self.config["map_follow"] or self.config["XXmap_externalXX` |
| `MainWindow.preload_map__mutmut_6` | no tests | `-    if not self.config["map_follow"] or self.config["map_external"]: +    if not self.config["map_follow"] or self.config["MAP_EXTERNAL"]: ` |
| `MainWindow.view_tag__mutmut_13` | suspicious | `-        return tr("info_view_plain") +        return tr(None) ` |
| `MainWindow.set_trim__mutmut_4` | survived | `-    trim = round(clamp_trim(trim), 3) + 0.0 +    trim = round(clamp_trim(trim), 3) - 0.0 ` |
| `MainWindow.set_trim__mutmut_16` | suspicious | `-        self.config["mark_trim"].pop(weapon.name, None) +        self.config["mark_trim"].pop(None) ` |
| `MainWindow.set_trim__mutmut_17` | survived | `-        self.config["mark_trim"].pop(weapon.name, None) +        self.config["mark_trim"].pop(weapon.name, ) ` |
| `MainWindow.set_trim__mutmut_18` | suspicious | `-        self.config["mark_trim"].pop(weapon.name, None) +        self.config["XXmark_trimXX"].pop(weapon.name, None) ` |
| `MainWindow.set_trim__mutmut_19` | suspicious | `-        self.config["mark_trim"].pop(weapon.name, None) +        self.config["MARK_TRIM"].pop(weapon.name, None) ` |
| `MainWindow.on_trim_edited__mutmut_1` | suspicious | `-    value = self.trim_entry.value(0.0) +    value = None ` |
| `MainWindow.on_trim_edited__mutmut_2` | suspicious | `-    value = self.trim_entry.value(0.0) +    value = self.trim_entry.value(None) ` |
| `MainWindow.on_trim_edited__mutmut_4` | suspicious | `-    self.set_trim(value) +    self.set_trim(None) ` |
| `MainWindow.on_trim_edited__mutmut_5` | suspicious | `-    if abs(value) > TRIM_LIMIT: +    if abs(None) > TRIM_LIMIT: ` |
| `MainWindow.on_trim_edited__mutmut_6` | survived | `-    if abs(value) > TRIM_LIMIT: +    if abs(value) >= TRIM_LIMIT: ` |
| `MainWindow.on_trim_edited__mutmut_7` | suspicious | `-        self.trim_entry.set_value(self.current_trim(self.current_weapon())) +        self.trim_entry.set_value(None) ` |
| `MainWindow.on_trim_edited__mutmut_9` | survived | `-    self.trim_status.setText("") +    self.trim_status.setText(None) ` |
| `MainWindow.on_trim_edited__mutmut_10` | survived | `-    self.trim_status.setText("") +    self.trim_status.setText("XXXX") ` |
| `MainWindow.reset_trim__mutmut_1` | suspicious | `-    self.set_trim(0.0) +    self.set_trim(None) ` |
| `MainWindow.apply_landing__mutmut_7` | survived | `-    height = self.height_entry.value(0.0) +    height = self.height_entry.value(1.0) ` |
| `MainWindow.apply_landing__mutmut_19` | suspicious | `-        arc = resolve_arc(weapon, self.config["arc"]) +        arc = resolve_arc(None, self.config["arc"]) ` |
| `MainWindow.apply_landing__mutmut_21` | suspicious | `-        arc = resolve_arc(weapon, self.config["arc"]) +        arc = resolve_arc(self.config["arc"]) ` |
| `MainWindow.apply_landing__mutmut_22` | suspicious | `-        arc = resolve_arc(weapon, self.config["arc"]) +        arc = resolve_arc(weapon, ) ` |
| `MainWindow.apply_landing__mutmut_23` | suspicious | `-        arc = resolve_arc(weapon, self.config["arc"]) +        arc = resolve_arc(weapon, self.config["XXarcXX"]) ` |
| `MainWindow.apply_landing__mutmut_24` | suspicious | `-        arc = resolve_arc(weapon, self.config["arc"]) +        arc = resolve_arc(weapon, self.config["ARC"]) ` |
| `MainWindow.apply_landing__mutmut_29` | suspicious | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(None, distance, height, "high").reachable: ` |
| `MainWindow.apply_landing__mutmut_30` | suspicious | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(weapon, None, height, "high").reachable: ` |
| `MainWindow.apply_landing__mutmut_31` | suspicious | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(weapon, distance, None, "high").reachable: ` |
| `MainWindow.apply_landing__mutmut_32` | survived | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(weapon, distance, height, None).reachable: ` |
| `MainWindow.apply_landing__mutmut_33` | suspicious | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(distance, height, "high").reachable: ` |
| `MainWindow.apply_landing__mutmut_35` | suspicious | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(weapon, distance, "high").reachable: ` |
| `MainWindow.apply_landing__mutmut_36` | survived | `-            if solve(weapon, distance, height, "high").reachable: +            if solve(weapon, distance, height, ).reachable: ` |
| `MainWindow.apply_landing__mutmut_46` | suspicious | `-        trim = trim_for_landing( -            weapon, -            distance, -            height, -            landed, -            self.cu` |
| `MainWindow.apply_landing__mutmut_47` | suspicious | `-            weapon, +            None, ` |
| `MainWindow.apply_landing__mutmut_53` | suspicious | `-            weapon, ` |
| `MainWindow.apply_landing__mutmut_62` | survived | `-        self.trim_status.setText(tr("bad_number")) +        self.trim_status.setText(None) ` |
| `MainWindow.apply_landing__mutmut_63` | survived | `-        self.trim_status.setText(tr("bad_number")) +        self.trim_status.setText(tr(None)) ` |
| `MainWindow.apply_landing__mutmut_64` | survived | `-        self.trim_status.setText(tr("bad_number")) +        self.trim_status.setText(tr("XXbad_numberXX")) ` |
| `MainWindow.apply_landing__mutmut_65` | survived | `-        self.trim_status.setText(tr("bad_number")) +        self.trim_status.setText(tr("BAD_NUMBER")) ` |
| `MainWindow.apply_landing__mutmut_66` | suspicious | `-    self.set_trim(trim) +    self.set_trim(None) ` |
| `MainWindow.apply_landing__mutmut_67` | suspicious | `-    trim = self.current_trim(weapon) +    trim = None ` |
| `MainWindow.apply_landing__mutmut_70` | suspicious | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr(None, trim=f"{trim:+g}") ` |
| `MainWindow.apply_landing__mutmut_72` | suspicious | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr(trim=f"{trim:+g}") ` |
| `MainWindow.apply_landing__mutmut_74` | survived | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr("trim_set_limit" if (abs(trim) >= TR` |
| `MainWindow.apply_landing__mutmut_76` | survived | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr("XXtrim_set_limitXX" if abs(trim) >=` |
| `MainWindow.apply_landing__mutmut_77` | survived | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr("TRIM_SET_LIMIT" if abs(trim) >= TRI` |
| `MainWindow.apply_landing__mutmut_78` | suspicious | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr("trim_set_limit" if abs(None) >= TRI` |
| `MainWindow.apply_landing__mutmut_79` | survived | `-        tr("trim_set_limit" if abs(trim) >= TRIM_LIMIT else "trim_set", trim=f"{trim:+g}") +        tr("trim_set_limit" if abs(trim) > TRIM` |
| `MainWindow.on_arc_changed__mutmut_4` | survived | `-    self.trim_status.setText("") +    self.trim_status.setText(None) ` |
| `MainWindow.on_arc_changed__mutmut_5` | survived | `-    self.trim_status.setText("") +    self.trim_status.setText("XXXX") ` |
| `MainWindow.on_input_edited__mutmut_2` | suspicious | `-    if self.config["auto_calc"]: +    if self.config["XXauto_calcXX"]: ` |
| `MainWindow.on_input_edited__mutmut_3` | suspicious | `-    if self.config["auto_calc"]: +    if self.config["AUTO_CALC"]: ` |
| `MainWindow.on_input_edited__mutmut_5` | survived | `-        self.calculate(show_errors=False) +        self.calculate(show_errors=None) ` |
| `MainWindow.on_input_edited__mutmut_6` | survived | `-        self.calculate(show_errors=False) +        self.calculate(show_errors=True) ` |
| `MainWindow.forget_map_target__mutmut_2` | suspicious | `-    self.map_target = None +    self.map_target = "" ` |
| `MainWindow.calibrate_lay__mutmut_35` | survived | `-    if weapon is None or not weapon.has_hold or weapon.aim != "elevation": +    if weapon is None or not weapon.has_hold and weapon.aim != ` |
| `MainWindow.calibrate_lay__mutmut_36` | survived | `-    if weapon is None or not weapon.has_hold or weapon.aim != "elevation": +    if weapon is None and not weapon.has_hold or weapon.aim != ` |
| `MainWindow.calibrate_lay__mutmut_42` | survived | `-        return False +        return True ` |
| `MainWindow.calibrate_lay__mutmut_49` | survived | `-    if held < LAY_CALIBRATION_MIN_HOLD: +    if held <= LAY_CALIBRATION_MIN_HOLD: ` |
| `MainWindow.calibrate_lay__mutmut_66` | survived | `-    if abs(rate - base) > LAY_RATE_TOLERANCE * base: +    if abs(rate - base) >= LAY_RATE_TOLERANCE * base: ` |
| `MainWindow.calibrate_lay__mutmut_68` | survived | `-        self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}")) +        self.lay_status.setText(None) ` |
| `MainWindow.calibrate_lay__mutmut_70` | survived | `-        self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}")) +        self.lay_status.setText(tr("lay_out_` |
| `MainWindow.calibrate_lay__mutmut_71` | survived | `-        self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}")) +        self.lay_status.setText(tr("lay_out_` |
| `MainWindow.calibrate_lay__mutmut_75` | survived | `-        self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}")) +        self.lay_status.setText(tr("XXlay_ou` |
| `MainWindow.calibrate_lay__mutmut_76` | survived | `-        self.lay_status.setText(tr("lay_out_of_range", rate=f"{rate:.2f}", base=f"{base:g}")) +        self.lay_status.setText(tr("LAY_OUT_` |
| `MainWindow.calibrate_lay__mutmut_85` | survived | `-    self.config["lay_rates"][weapon.name] = round(rate, 4) +    self.config["lay_rates"][weapon.name] = round(rate, 5) ` |
| `MainWindow.calibrate_lay__mutmut_86` | survived | `-    self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}")) +    self.lay_status.setText(None) ` |
| `MainWindow.calibrate_lay__mutmut_88` | survived | `-    self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}")) +    self.lay_status.setText(tr("lay_done", rate=None, ba` |
| `MainWindow.calibrate_lay__mutmut_89` | survived | `-    self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}")) +    self.lay_status.setText(tr("lay_done", rate=f"{rate:` |
| `MainWindow.calibrate_lay__mutmut_93` | survived | `-    self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}")) +    self.lay_status.setText(tr("XXlay_doneXX", rate=f"{r` |
| `MainWindow.calibrate_lay__mutmut_94` | survived | `-    self.lay_status.setText(tr("lay_done", rate=f"{rate:.2f}", base=f"{base:g}")) +    self.lay_status.setText(tr("LAY_DONE", rate=f"{rate:` |
| `MainWindow.reset_lay_rate__mutmut_6` | survived | `-    if weapon is None or self.config["lay_rates"].pop(weapon.name, None) is None: +    if weapon is None or self.config["lay_rates"].pop(we` |
| `MainWindow.reset_lay_rate__mutmut_10` | survived | `-    self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}")) +    self.lay_status.setText(None) ` |
| `MainWindow.reset_lay_rate__mutmut_12` | survived | `-    self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}")) +    self.lay_status.setText(tr("la` |
| `MainWindow.reset_lay_rate__mutmut_14` | survived | `-    self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}")) +    self.lay_status.setText(tr("la` |
| `MainWindow.reset_lay_rate__mutmut_15` | survived | `-    self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}")) +    self.lay_status.setText(tr("XX` |
| `MainWindow.reset_lay_rate__mutmut_16` | survived | `-    self.lay_status.setText(tr("lay_reset_done", base=f"{self.file_weapons[weapon.name].hold_rate:g}")) +    self.lay_status.setText(tr("LA` |
| `MainWindow.lay_reset_time__mutmut_2` | survived | `-    if weapon is None or not weapon.has_hold or weapon.aim != "elevation": +    if weapon is None and not weapon.has_hold or weapon.aim != ` |
| `MainWindow.lay_step__mutmut_1` | survived | `-    if not self.config["auto_hold"] or self.hold_timer.auto_hold is None: +    if not self.config["auto_hold"] and self.hold_timer.auto_hol` |
| `MainWindow.lay_step__mutmut_21` | survived | `-        hotkey=self.config["hotkeys"].get("auto_hold", ""), +        hotkey=self.config["hotkeys"].get("auto_hold", None), ` |
| `MainWindow.lay_step__mutmut_23` | survived | `-        hotkey=self.config["hotkeys"].get("auto_hold", ""), +        hotkey=self.config["hotkeys"].get("auto_hold", ), ` |
| `MainWindow.lay_step__mutmut_28` | survived | `-        hotkey=self.config["hotkeys"].get("auto_hold", ""), +        hotkey=self.config["hotkeys"].get("auto_hold", "XXXX"), ` |
| `MainWindow.auto_hold__mutmut_41` | survived | `-        self.set_lay_info(tr(blocker, key=self.config["hotkeys"].get("auto_hold", ""))) +        self.set_lay_info(tr(blocker, key=self.con` |
| `MainWindow.auto_hold__mutmut_43` | survived | `-        self.set_lay_info(tr(blocker, key=self.config["hotkeys"].get("auto_hold", ""))) +        self.set_lay_info(tr(blocker, key=self.con` |
| `MainWindow.auto_hold__mutmut_48` | survived | `-        self.set_lay_info(tr(blocker, key=self.config["hotkeys"].get("auto_hold", ""))) +        self.set_lay_info(tr(blocker, key=self.con` |
| `MainWindow.timed_lay_blocker__mutmut_12` | survived | `-    if self.lay_reset_time(weapon) > 0 and timer.auto_hold.reset_injector is None: +    if self.lay_reset_time(weapon) >= 0 and timer.auto_` |
| `MainWindow.timed_lay_blocker__mutmut_13` | survived | `-    if self.lay_reset_time(weapon) > 0 and timer.auto_hold.reset_injector is None: +    if self.lay_reset_time(weapon) > 1 and timer.auto_h` |
| `MainWindow.timed_lay_blocker__mutmut_17` | survived | `-    if not timer.active or not timer.available: +    if not timer.active and not timer.available: ` |
| `MainWindow.lay_failure_text__mutmut_8` | suspicious | `-        "lay_failed", +        None, ` |
| `MainWindow.lay_failure_text__mutmut_11` | suspicious | `-        "lay_failed", ` |
| `MainWindow.lay_failure_text__mutmut_12` | suspicious | `-        what=tr(axis), ` |
| `MainWindow.lay_failure_text__mutmut_13` | suspicious | `-        why=tr(f"lay_why_{failure}", moves=MAX_MOVES) -    ) +        ) ` |
| `MainWindow.lay_failure_text__mutmut_17` | suspicious | `-        why=tr(f"lay_why_{failure}", moves=MAX_MOVES) +        why=tr(None, moves=MAX_MOVES) ` |
| `MainWindow.lay_failure_text__mutmut_19` | suspicious | `-        why=tr(f"lay_why_{failure}", moves=MAX_MOVES) +        why=tr(moves=MAX_MOVES) ` |
| `MainWindow.sight_target__mutmut_2` | survived | `-    if not self.lays_by_sight(self.current_weapon()) or solution is None \ -                or not math.isfinite(solution.hold_time): +    ` |
| `MainWindow.sight_target__mutmut_3` | survived | `-    if not self.lays_by_sight(self.current_weapon()) or solution is None \ +    if not self.lays_by_sight(self.current_weapon()) and soluti` |
| `MainWindow.bearing_target__mutmut_8` | survived | `-    return target.bearing % 360.0 +    return target.bearing % 361.0 ` |
| `MainWindow.save_sight_grab__mutmut_5` | survived | `-    os.makedirs(config_dir(), exist_ok=True) +    os.makedirs(config_dir(), exist_ok=None) ` |
| `MainWindow.save_sight_grab__mutmut_7` | survived | `-    os.makedirs(config_dir(), exist_ok=True) +    os.makedirs(config_dir(), ) ` |
| `MainWindow.save_sight_grab__mutmut_8` | survived | `-    os.makedirs(config_dir(), exist_ok=True) +    os.makedirs(config_dir(), exist_ok=False) ` |
| `MainWindow.save_sight_grab__mutmut_16` | survived | `-        return "" +        return "XXXX" ` |
| `MainWindow.laying__mutmut_1` | suspicious | `-        layer is not None and layer.active -        for layer in (self.bearing_layer, self.sight_layer) +        None ` |
| `MainWindow.laying__mutmut_2` | suspicious | `-        layer is not None and layer.active +        layer is not None or layer.active ` |
| `MainWindow.laying__mutmut_3` | suspicious | `-        layer is not None and layer.active +        layer is None and layer.active ` |
| `MainWindow.watch_sight__mutmut_3` | survived | `-        self.set_bearing_info("") +        self.set_bearing_info(None) ` |
| `MainWindow.watch_sight__mutmut_4` | survived | `-        self.set_bearing_info("") +        self.set_bearing_info("XXXX") ` |
| `MainWindow.compass_reader__mutmut_1` | survived | `-    if self.bearing_layer is not None: +    if self.bearing_layer is None: ` |
| `MainWindow.compass_reader__mutmut_2` | survived | `-    if self.own_compass_reader is None: +    if self.own_compass_reader is not None: ` |
| `MainWindow.compass_reader__mutmut_3` | survived | `-        self.own_compass_reader = CompassReader(DigitReader(self.templates())) +        self.own_compass_reader = None ` |
| `MainWindow.compass_reader__mutmut_4` | survived | `-        self.own_compass_reader = CompassReader(DigitReader(self.templates())) +        self.own_compass_reader = CompassReader(None) ` |
| `MainWindow.compass_reader__mutmut_5` | survived | `-        self.own_compass_reader = CompassReader(DigitReader(self.templates())) +        self.own_compass_reader = CompassReader(DigitReader` |
| `MainWindow.show_sight_reading__mutmut_1` | survived | `-def show_sight_reading(self, reading, mark=""): +def show_sight_reading(self, reading, mark="XXXX"): ` |
| `MainWindow.show_sight_reading__mutmut_3` | survived | `-        self.set_sight_info("") +        self.set_sight_info(None) ` |
| `MainWindow.show_sight_reading__mutmut_4` | survived | `-        self.set_sight_info("") +        self.set_sight_info("XXXX") ` |
| `MainWindow.show_sight_reading__mutmut_7` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = None ` |
| `MainWindow.show_sight_reading__mutmut_8` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr(None, mils=f"{reading.mils:.1f}") ` |
| `MainWindow.show_sight_reading__mutmut_9` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr("sight_reading", mils=None) ` |
| `MainWindow.show_sight_reading__mutmut_10` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr(mils=f"{reading.mils:.1f}") ` |
| `MainWindow.show_sight_reading__mutmut_11` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr("sight_reading", ) ` |
| `MainWindow.show_sight_reading__mutmut_12` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr("XXsight_readingXX", mils=f"{reading.mils:.1f}") ` |
| `MainWindow.show_sight_reading__mutmut_13` | survived | `-        text = tr("sight_reading", mils=f"{reading.mils:.1f}") +        text = tr("SIGHT_READING", mils=f"{reading.mils:.1f}") ` |
| `MainWindow.show_bearing_reading__mutmut_1` | survived | `-def show_bearing_reading(self, reading, mark=""): +def show_bearing_reading(self, reading, mark="XXXX"): ` |
| `MainWindow.show_bearing_reading__mutmut_3` | survived | `-        self.set_bearing_info("") +        self.set_bearing_info(None) ` |
| `MainWindow.show_bearing_reading__mutmut_4` | survived | `-        self.set_bearing_info("") +        self.set_bearing_info("XXXX") ` |
| `MainWindow.show_bearing_reading__mutmut_7` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = None ` |
| `MainWindow.show_bearing_reading__mutmut_8` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr(None, deg=f"{reading.degrees:.1f}") ` |
| `MainWindow.show_bearing_reading__mutmut_9` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr("compass_reading", deg=None) ` |
| `MainWindow.show_bearing_reading__mutmut_10` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr(deg=f"{reading.degrees:.1f}") ` |
| `MainWindow.show_bearing_reading__mutmut_11` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr("compass_reading", ) ` |
| `MainWindow.show_bearing_reading__mutmut_12` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr("XXcompass_readingXX", deg=f"{reading.degrees:.1f}") ` |
| `MainWindow.show_bearing_reading__mutmut_13` | survived | `-        text = tr("compass_reading", deg=f"{reading.degrees:.1f}") +        text = tr("COMPASS_READING", deg=f"{reading.degrees:.1f}") ` |
| `MainWindow.show_bearing_reading__mutmut_14` | suspicious | `-        left = BEARING.difference(target, reading.degrees) +        left = None ` |
| `MainWindow.show_bearing_reading__mutmut_15` | suspicious | `-        left = BEARING.difference(target, reading.degrees) +        left = BEARING.difference(None, reading.degrees) ` |
| `MainWindow.show_bearing_reading__mutmut_16` | suspicious | `-        left = BEARING.difference(target, reading.degrees) +        left = BEARING.difference(target, None) ` |
| `MainWindow.show_bearing_reading__mutmut_17` | suspicious | `-        left = BEARING.difference(target, reading.degrees) +        left = BEARING.difference(reading.degrees) ` |
| `MainWindow.show_bearing_reading__mutmut_18` | suspicious | `-        left = BEARING.difference(target, reading.degrees) +        left = BEARING.difference(target, ) ` |
| `MainWindow.show_bearing_reading__mutmut_20` | suspicious | `-        text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}") +        text = tr(None, deg=f"{reading.degree` |
| `MainWindow.show_bearing_reading__mutmut_21` | survived | `-        text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}") +        text = tr("compass_reading_left", deg` |
| `MainWindow.show_bearing_reading__mutmut_23` | suspicious | `-        text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}") +        text = tr(deg=f"{reading.degrees:.1f}` |
| `MainWindow.show_bearing_reading__mutmut_24` | suspicious | `-        text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}") +        text = tr("compass_reading_left", lef` |
| `MainWindow.show_bearing_reading__mutmut_25` | suspicious | `-        text = tr("compass_reading_left", deg=f"{reading.degrees:.1f}", left=f"{left:+.1f}") +        text = tr("compass_reading_left", deg` |
| `MainWindow.lay_mark__mutmut_1` | survived | `-        return "  ✓" +        return "XX  ✓XX" ` |
| `MainWindow.lay_mark__mutmut_4` | survived | `-    return "" if layer is not None and layer.stopped else "  ✗" +    return "XXXX" if layer is not None and layer.stopped else "  ✗" ` |
| `MainWindow.lay_mark__mutmut_7` | survived | `-    return "" if layer is not None and layer.stopped else "  ✗" +    return "" if layer is not None and layer.stopped else "XX  ✗XX" ` |
| `MainWindow.on_bearing_lay_finished__mutmut_2` | survived | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(None, self.lay_mark(turning, on_ta` |
| `MainWindow.on_bearing_lay_finished__mutmut_3` | survived | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(reading, None) ` |
| `MainWindow.on_bearing_lay_finished__mutmut_4` | suspicious | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(self.lay_mark(turning, on_target))` |
| `MainWindow.on_bearing_lay_finished__mutmut_5` | survived | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(reading, ) ` |
| `MainWindow.on_bearing_lay_finished__mutmut_8` | suspicious | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(reading, self.lay_mark(on_target))` |
| `MainWindow.on_bearing_lay_finished__mutmut_9` | suspicious | `-    self.show_bearing_reading(reading, self.lay_mark(turning, on_target)) +    self.show_bearing_reading(reading, self.lay_mark(turning, ))` |
| `MainWindow.on_bearing_lay_finished__mutmut_12` | suspicious | `-        self.set_lay_info(self.lay_failure_text(turning, "lay_bearing")) +        self.set_lay_info(self.lay_failure_text(None, "lay_bearin` |
| `MainWindow.on_bearing_lay_finished__mutmut_14` | suspicious | `-        self.set_lay_info(self.lay_failure_text(turning, "lay_bearing")) +        self.set_lay_info(self.lay_failure_text("lay_bearing")) ` |
| `MainWindow.on_bearing_lay_finished__mutmut_15` | suspicious | `-        self.set_lay_info(self.lay_failure_text(turning, "lay_bearing")) +        self.set_lay_info(self.lay_failure_text(turning, )) ` |
| `MainWindow.on_bearing_lay_finished__mutmut_26` | survived | `-    if stopped or not self.start_sight_lay(): +    if stopped or self.start_sight_lay(): ` |
| `MainWindow.on_sight_lay_finished__mutmut_7` | survived | `-    self.show_sight_reading(reading, self.lay_mark(layer, on_target)) +    self.show_sight_reading(reading, self.lay_mark(layer, None)) ` |
| `MainWindow.on_sight_lay_finished__mutmut_13` | survived | `-    failure = "" if layer is None else self.lay_failure_text(layer, "lay_elevation") +    failure = "XXXX" if layer is None else self.lay_f` |
| `MainWindow.on_sight_lay_finished__mutmut_15` | suspicious | `-    failure = "" if layer is None else self.lay_failure_text(layer, "lay_elevation") +    failure = "" if layer is None else self.lay_failu` |
| `MainWindow.on_sight_lay_finished__mutmut_17` | suspicious | `-    failure = "" if layer is None else self.lay_failure_text(layer, "lay_elevation") +    failure = "" if layer is None else self.lay_failu` |
| `MainWindow.on_sight_lay_finished__mutmut_18` | suspicious | `-    failure = "" if layer is None else self.lay_failure_text(layer, "lay_elevation") +    failure = "" if layer is None else self.lay_failu` |
| `MainWindow.make_bearing_layer__mutmut_5` | survived | `-    if right is None or left is None: +    if right is None and left is None: ` |
| `MainWindow.make_bearing_layer__mutmut_8` | survived | `-            if injector is not None: +            if injector is None: ` |
| `MainWindow.make_bearing_layer__mutmut_10` | suspicious | `-    self.bearing_layer = SightLayer( -        lambda: self.screen_sight.grab_compass(), -        templates, -        self.bearing_target, -` |
| `MainWindow.make_bearing_layer__mutmut_12` | survived | `-        templates, +        None, ` |
| `MainWindow.make_bearing_layer__mutmut_14` | suspicious | `-        right, +        None, ` |
| `MainWindow.make_bearing_layer__mutmut_15` | suspicious | `-        left, +        None, ` |
| `MainWindow.make_bearing_layer__mutmut_16` | survived | `-        self, +        None, ` |
| `MainWindow.make_bearing_layer__mutmut_17` | suspicious | `-        axis=BEARING, +        axis=None, ` |
| `MainWindow.make_bearing_layer__mutmut_19` | suspicious | `-        lambda: self.screen_sight.grab_compass(), ` |
| `MainWindow.make_bearing_layer__mutmut_20` | suspicious | `-        templates, ` |
| `MainWindow.make_bearing_layer__mutmut_21` | suspicious | `-        self.bearing_target, ` |
| `MainWindow.make_bearing_layer__mutmut_22` | suspicious | `-        right, ` |
| `MainWindow.make_bearing_layer__mutmut_23` | suspicious | `-        left, ` |
| `MainWindow.make_bearing_layer__mutmut_24` | survived | `-        self, ` |
| `MainWindow.make_bearing_layer__mutmut_25` | survived | `-        axis=BEARING, ` |
| `MainWindow.make_bearing_layer__mutmut_30` | suspicious | `-    self.bearing_layer.read.connect(self.show_bearing_reading) +    self.bearing_layer.read.connect(None) ` |
| `MainWindow.make_bearing_layer__mutmut_31` | suspicious | `-    self.bearing_layer.finished.connect(self.on_bearing_lay_finished) +    self.bearing_layer.finished.connect(None) ` |
| `MainWindow.set_auto_hold__mutmut_1` | suspicious | `-    teardown_hotkeys(self) +    teardown_hotkeys(None) ` |
| `MainWindow.set_auto_hold__mutmut_3` | suspicious | `-    setup_hotkeys(self) +    setup_hotkeys(None) ` |
| `MainWindow.set_auto_hold__mutmut_4` | survived | `-    if not ok: +    if ok: ` |
| `MainWindow.set_auto_hold__mutmut_5` | suspicious | `-        toggle = self.controls["auto_hold"] +        toggle = None ` |
| `MainWindow.set_auto_hold__mutmut_6` | suspicious | `-        toggle = self.controls["auto_hold"] +        toggle = self.controls["XXauto_holdXX"] ` |
| `MainWindow.set_auto_hold__mutmut_7` | suspicious | `-        toggle = self.controls["auto_hold"] +        toggle = self.controls["AUTO_HOLD"] ` |
| `MainWindow.set_auto_hold__mutmut_8` | suspicious | `-        toggle.blockSignals(True) +        toggle.blockSignals(None) ` |
| `MainWindow.set_auto_hold__mutmut_9` | survived | `-        toggle.blockSignals(True) +        toggle.blockSignals(False) ` |
| `MainWindow.set_auto_hold__mutmut_10` | suspicious | `-        toggle.setChecked(False) +        toggle.setChecked(None) ` |
| `MainWindow.set_auto_hold__mutmut_11` | survived | `-        toggle.setChecked(False) +        toggle.setChecked(True) ` |
| `MainWindow.set_auto_hold__mutmut_12` | suspicious | `-        toggle.blockSignals(False) +        toggle.blockSignals(None) ` |
| `MainWindow.how_overlay_view__mutmut_18` | suspicious | `-            name for name, other in self.weapons.items() if other.twin == weapon.name +            None ` |
| `MainWindow.how_overlay_view__mutmut_20` | suspicious | `-        return tr("how_view_plain", twin=optic, fov=f"{fov:g}") +        return tr(None, twin=optic, fov=f"{fov:g}") ` |
| `MainWindow.how_overlay_view__mutmut_23` | suspicious | `-        return tr("how_view_plain", twin=optic, fov=f"{fov:g}") +        return tr(twin=optic, fov=f"{fov:g}") ` |
| `MainWindow.how_overlay_view__mutmut_24` | suspicious | `-        return tr("how_view_plain", twin=optic, fov=f"{fov:g}") +        return tr("how_view_plain", fov=f"{fov:g}") ` |
| `MainWindow.how_overlay_view__mutmut_25` | suspicious | `-        return tr("how_view_plain", twin=optic, fov=f"{fov:g}") +        return tr("how_view_plain", twin=optic, ) ` |
| `MainWindow.reset_offset__mutmut_2` | survived | `-    self.direct_solution = None +    self.direct_solution = "" ` |
| `MainWindow.reset_offset__mutmut_3` | survived | `-    self.overlay.set_offset(self.current_offset()) +    self.overlay.set_offset(None) ` |
| `MainWindow.reset_offset__mutmut_4` | survived | `-    self.set_overlay_info("") +    self.set_overlay_info(None) ` |
| `MainWindow.toggle_view__mutmut_2` | suspicious | `-    twin = view_twin(self.weapons, self.picker.current) +    twin = view_twin(None, self.picker.current) ` |
| `MainWindow.toggle_view__mutmut_4` | suspicious | `-    twin = view_twin(self.weapons, self.picker.current) +    twin = view_twin(self.picker.current) ` |
| `MainWindow.toggle_view__mutmut_5` | suspicious | `-    twin = view_twin(self.weapons, self.picker.current) +    twin = view_twin(self.weapons, ) ` |
| `MainWindow.distance_up__mutmut_4` | survived | `-    self.calculate(show_errors=False) +    self.calculate(show_errors=None) ` |
| `MainWindow.distance_up__mutmut_5` | survived | `-    self.calculate(show_errors=False) +    self.calculate(show_errors=True) ` |
| `MainWindow.distance_down__mutmut_5` | survived | `-    self.calculate(show_errors=False) +    self.calculate(show_errors=None) ` |
| `MainWindow.distance_down__mutmut_6` | survived | `-    self.calculate(show_errors=False) +    self.calculate(show_errors=True) ` |
| `MainWindow.set_setting__mutmut_1` | suspicious | `-    self.config[key] = value +    self.config[key] = None ` |
| `MainWindow.watch_screen__mutmut_1` | no tests | `-    screen.geometryChanged.connect(self.update_monitor_choice) +    screen.geometryChanged.connect(None) ` |
| `MainWindow.open_config_dir__mutmut_7` | survived | `-    if QDesktopServices.openUrl(QUrl.fromLocalFile(path)): +    if QDesktopServices.openUrl(None): ` |
| `MainWindow.open_config_dir__mutmut_8` | survived | `-    if QDesktopServices.openUrl(QUrl.fromLocalFile(path)): +    if QDesktopServices.openUrl(QUrl.fromLocalFile(None)): ` |
| `MainWindow.set_on_top__mutmut_4` | survived | `-    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked) +    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, ) ` |
| `MainWindow.set_distance_step__mutmut_1` | survived | `-    self.config["distance_step"] = step +    self.config["distance_step"] = None ` |
| `MainWindow.set_distance_step__mutmut_2` | survived | `-    self.config["distance_step"] = step +    self.config["XXdistance_stepXX"] = step ` |
| `MainWindow.set_distance_step__mutmut_3` | survived | `-    self.config["distance_step"] = step +    self.config["DISTANCE_STEP"] = step ` |
| `MainWindow.set_monitor__mutmut_1` | no tests | `-    self.config["monitor"] = index +    self.config["monitor"] = None ` |
| `MainWindow.set_monitor__mutmut_2` | no tests | `-    self.config["monitor"] = index +    self.config["XXmonitorXX"] = index ` |
| `MainWindow.set_monitor__mutmut_3` | no tests | `-    self.config["monitor"] = index +    self.config["MONITOR"] = index ` |
| `MainWindow.set_hotkey__mutmut_17` | survived | `-        box.blockSignals(True) +        box.blockSignals(False) ` |
| `MainWindow.set_hotkey__mutmut_26` | survived | `-        box.setCurrentIndex(max(0, box.findData(self.config["hotkeys"].get(name, "")))) +        box.setCurrentIndex(max(0, box.findData(se` |
| `MainWindow.set_hotkey__mutmut_28` | survived | `-        box.setCurrentIndex(max(0, box.findData(self.config["hotkeys"].get(name, "")))) +        box.setCurrentIndex(max(0, box.findData(se` |
| `MainWindow.set_hotkey__mutmut_31` | survived | `-        box.setCurrentIndex(max(0, box.findData(self.config["hotkeys"].get(name, "")))) +        box.setCurrentIndex(max(0, box.findData(se` |
| `MainWindow.set_hotkey__mutmut_33` | survived | `-        box.blockSignals(False) +        box.blockSignals(True) ` |
| `MainWindow.reset_settings__mutmut_2` | survived | `-        self, +        None, ` |
| `MainWindow.reset_settings__mutmut_3` | survived | `-        "Squad Ballistics", +        None, ` |
| `MainWindow.reset_settings__mutmut_4` | survived | `-        tr("s_reset_confirm") +        None ` |
| `MainWindow.reset_settings__mutmut_5` | survived | `-        self, ` |
| `MainWindow.reset_settings__mutmut_6` | survived | `-        "Squad Ballistics", ` |
| `MainWindow.reset_settings__mutmut_7` | survived | `-        tr("s_reset_confirm") -    ) +        ) ` |
| `MainWindow.reset_settings__mutmut_8` | survived | `-        "Squad Ballistics", +        "XXSquad BallisticsXX", ` |
| `MainWindow.reset_settings__mutmut_9` | survived | `-        "Squad Ballistics", +        "squad ballistics", ` |
| `MainWindow.reset_settings__mutmut_10` | survived | `-        "Squad Ballistics", +        "SQUAD BALLISTICS", ` |
| `MainWindow.reset_settings__mutmut_11` | survived | `-        tr("s_reset_confirm") +        tr(None) ` |
| `MainWindow.reset_settings__mutmut_12` | survived | `-        tr("s_reset_confirm") +        tr("XXs_reset_confirmXX") ` |
| `MainWindow.reset_settings__mutmut_13` | survived | `-        tr("s_reset_confirm") +        tr("S_RESET_CONFIRM") ` |
| `MainWindow.reset_settings__mutmut_16` | survived | `-    old_map_url = map_url(self.config) +    old_map_url = None ` |
| `MainWindow.reset_settings__mutmut_20` | survived | `-    self.config.update(copy.deepcopy(DEFAULT_CONFIG)) +    self.config.update(copy.copy(DEFAULT_CONFIG)) ` |
| `MainWindow.reset_settings__mutmut_23` | survived | `-    self.set_on_top(False) +    self.set_on_top(True) ` |
| `MainWindow.reset_settings__mutmut_27` | survived | `-    if self.map_page is not None and map_url(self.config) != old_map_url: +    if self.map_page is not None or map_url(self.config) != old_` |
| `MainWindow.reset_settings__mutmut_31` | survived | `-    save_config(self.config) +    save_config(None) ` |
| `MainWindow.on_map_follow_changed__mutmut_1` | no tests | `-        QTimer.singleShot(0, self.preload_map) +        QTimer.singleShot(None, self.preload_map) ` |
| `MainWindow.on_map_follow_changed__mutmut_2` | no tests | `-        QTimer.singleShot(0, self.preload_map) +        QTimer.singleShot(0, None) ` |
| `MainWindow.on_map_follow_changed__mutmut_3` | no tests | `-        QTimer.singleShot(0, self.preload_map) +        QTimer.singleShot(self.preload_map) ` |
| `MainWindow.on_map_follow_changed__mutmut_4` | no tests | `-        QTimer.singleShot(0, self.preload_map) +        QTimer.singleShot(0, ) ` |
| `MainWindow.on_map_follow_changed__mutmut_5` | no tests | `-        QTimer.singleShot(0, self.preload_map) +        QTimer.singleShot(1, self.preload_map) ` |
| `MainWindow.set_map_render__mutmut_8` | survived | `-    answer = QMessageBox.question( -        self, -        tr("restart_title"), -        tr("restart_text") -    ) +    answer = None ` |
| `MainWindow.set_map_render__mutmut_9` | survived | `-        self, +        None, ` |
| `MainWindow.set_map_render__mutmut_10` | survived | `-        tr("restart_title"), +        None, ` |
| `MainWindow.set_map_render__mutmut_11` | survived | `-        tr("restart_text") +        None ` |
| `MainWindow.set_map_render__mutmut_12` | survived | `-        self, ` |
| `MainWindow.set_map_render__mutmut_13` | survived | `-        tr("restart_title"), ` |
| `MainWindow.set_map_render__mutmut_14` | survived | `-        tr("restart_text") -    ) +        ) ` |
| `MainWindow.set_map_render__mutmut_15` | survived | `-        tr("restart_title"), +        tr(None), ` |
| `MainWindow.set_map_render__mutmut_16` | survived | `-        tr("restart_title"), +        tr("XXrestart_titleXX"), ` |
| `MainWindow.set_map_render__mutmut_17` | survived | `-        tr("restart_title"), +        tr("RESTART_TITLE"), ` |
| `MainWindow.set_map_render__mutmut_18` | survived | `-        tr("restart_text") +        tr(None) ` |
| `MainWindow.set_map_render__mutmut_19` | survived | `-        tr("restart_text") +        tr("XXrestart_textXX") ` |
| `MainWindow.set_map_render__mutmut_20` | survived | `-        tr("restart_text") +        tr("RESTART_TEXT") ` |
| `MainWindow.set_map_render__mutmut_21` | survived | `-    if answer == QMessageBox.StandardButton.Yes: +    if answer != QMessageBox.StandardButton.Yes: ` |
| `MainWindow.restart__mutmut_1` | no tests | `-    program = sys.executable +    program = None ` |
| `MainWindow.restart__mutmut_2` | no tests | `-    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:] +    arguments = None ` |
| `MainWindow.restart__mutmut_3` | no tests | `-    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:] +    arguments = [os.path.abspath(sys.argv[0])] - sys.argv[1:] ` |
| `MainWindow.restart__mutmut_4` | no tests | `-    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:] +    arguments = [os.path.abspath(None)] + sys.argv[1:] ` |
| `MainWindow.restart__mutmut_5` | no tests | `-    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:] +    arguments = [os.path.abspath(sys.argv[1])] + sys.argv[1:] ` |
| `MainWindow.restart__mutmut_6` | no tests | `-    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[1:] +    arguments = [os.path.abspath(sys.argv[0])] + sys.argv[2:] ` |
| `MainWindow.restart__mutmut_7` | no tests | `-    QProcess.startDetached(program, arguments) +    QProcess.startDetached(None, arguments) ` |
| `MainWindow.restart__mutmut_8` | no tests | `-    QProcess.startDetached(program, arguments) +    QProcess.startDetached(program, None) ` |
| `MainWindow.restart__mutmut_9` | no tests | `-    QProcess.startDetached(program, arguments) +    QProcess.startDetached(arguments) ` |
| `MainWindow.restart__mutmut_10` | no tests | `-    QProcess.startDetached(program, arguments) +    QProcess.startDetached(program, ) ` |
