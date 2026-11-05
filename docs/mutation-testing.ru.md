# Мутационное тестирование

Как набор тестов проверен мутационным тестированием [mutmut](https://mutmut.readthedocs.io/) 3.8.1 (мутант - правка одного токена в коде; набор тестов, который после неё проходит, мутант пропустил). English version: [mutation-testing.md](mutation-testing.md).

## Команды

Образ `sb-ci-mut` - это образ CI плюс `pip install mutmut` (mutmut 3.8.1, Python 3.12). Каждый модуль мутируется в своей копии репозитория, с таким `setup.cfg`:

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

Файлы тестов для `mutmut run`: `config`: `test_config.py`, `test_config_behaviour.py`, `test_ui.py`; `keystate`: `test_keystate.py`; `ballistics`: тесты баллистики, поправки, метки и оружия; `crosshair`: `test_ui`, `test_calc_state`, `test_trim`, `test_view_toggle`, `test_marker_aids`, `test_no_hold_beep`, `test_vehicle_sights_ui`. Запуск `keystate` идёт с `max_children=1`: его X11-тесты делят дисплей `:97`. Таймаут считается выжившим мутантом, пока не разобран; падение процесса тестов (segfault, NULL `Display*`) считается убитым мутантом.

## Результаты по модулям

"Исходный набор" - набор `dev` на `5f11d21` (измерен теми же командами). "Новые тесты" - тесты, добавленные рядом; для `ballistics` 459 мутантов, не убитых исходным прогоном, перепроверены по одному на итоговом наборе (`MUTANT_UNDER_TEST`, `pytest -x`): второй полный `mutmut run` на 2356 мутантов с эталонными тестами полёта не уложился во время (начатый прогон остановлен на 286 мутантах).

| Модуль | Всего | Убиты исходным набором | Убиты новыми тестами | Эквивалентные | Открыто |
|---|---|---|---|---|---|
| `config.py` | 324 | 300 (+9 падение) | 6 | 9 | 0 |
| `keystate.py` | 289 | 233 (+18 падение) | 30 (из них 4 без теста) | 8 | 0 |
| `ballistics.py` | 2356 | 1897 | 421 | 37 | 1 |
| `crosshair.py` | 4097 | 700 (проверено 970 из 4097) | 0 | 0 | 3397 (см. ниже) |

В исходном прогоне `ballistics` было 439 выживших, 11 мутантов без тестов и 9 таймаутов (459 не убито). `crosshair.py` не закончен: прогон (4097 мутантов, проверено 970: 700 убито, 158 выжило, 86 подозрительных, 25 без тестов, 1 падение) остановлен по исчерпанию времени; его выжившие перечислены ниже как не разобранные.

## Новые тесты

Тесты лежат в `tests/test_config_behaviour.py`, `tests/test_keystate.py` и новом `tests/test_ballistics_mutants.py`. Файл баллистики сверяет полёт, вершину и высоту настоящего и придуманного оружия с независимым эталоном `tests/flight.py` (50 Гц шаги игры), фиксирует каждое сообщение проверки в `Weapon.from_dict` и `parse_weapons`, проверяет `solve`, `mark_*`, `range_ladder`, `trim_for_landing` и `first_obstacle` точными значениями и точными граничными совпадениями (например, `GRAVITY` = 10: 100 м/с долетает на 1000 м ровно под 45 градусов).

## Эквивалентные выжившие

### `config.py`

| Мутант | Правка | Причина |
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

| Мутант | Правка | Причина |
|---|---|---|
| `_device_name_13` | `split(b"\0", 1) -> split(b"\0")` | only element [0] is used |
| `_device_name_17` | `split(b"\0", 1) -> split(b"\0", 2)` | only element [0] is used |
| `EvdevReader.__init___7` | `next_scan = 0.0 -> None` | overwritten by the first scan before it is read |
| `EvdevReader.__init___8` | `next_scan = 0.0 -> 1.0` | overwritten by the first scan before it is read |
| `EvdevReader.__call___2` | `failed = False -> None` | only its truthiness is used |
| `x11_button_reader_12` | `POINTER(c_int) -> POINTER(None)` | POINTER(None) is c_void_p and accepts any byref |
| `x11_button_reader_81` | `button // 8 < mask_len -> button / 8 <` | mask_len is an integer |
| `x11_reader_16` | `XOpenDisplay.argtypes = None` | ctypes passes the bytes argument the same way |

Мутанты `keystate.py`, роняющие процесс тестов (убиты падением): `x11_button_reader` 11, 14, 26, 27, 32, 33, 34, 43, 47, 55, 58, 59, 60, 61, 62; `x11_reader` 17, 27, 34. Остальные мутанты `POINTER(None)` в `x11_button_reader` (13, 16, 18-23) то убиваются, то выживают; прямыми запусками проверено, что они эквивалентны мутанту 12.

### `ballistics.py`

| Мутант | Правка | Причина |
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

## Не разобраны

## Убитые мутанты по группам тестов

Номера мутантов - суффикс `ballistics.<функция>__mutmut_<n>` (459 не убитых исходным набором). Каждый id строки убит хотя бы одним тестом группы при отдельном запуске `pytest -x`; для строк полёта, вершины и таблицы разгона нужны эталонные тесты.

| Группа тестов | Функция: номера убитых мутантов |
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

## Ограниченные по скорости ракеты и эталон

Два придуманных оружия (ограничение скорости и двигатель) сначала расходились с `tests/flight.py` до 0,2 м у дульного среза. Итог: (1) "rocket that burns until the cap" - ошибка входа эталона: эталон считает `acceleration_timeout` 0 как "горит всегда", а в `ballistics.py` `acceleration_time` 0 - "двигателя нет" (единственное такое оружие в `tests/data/game_weapons.json` - NLAW); расхождение в 2 км вызвано этим. (2) Два оружия с конечным временем горения расходятся с эталоном не более чем на 1,6 см при -4..75 градусах и 0,5-900 м и на 4 см (следует за скоростью) и 0,5 м (летит вдоль ствола) при 89 градусах и 120 м. Это погрешность интерполяции таблицы разгона с узлами через 1 градус там, где полёт круто зависит от угла (почти вертикально): предел приближения, а не логическая ошибка, и оружие там не наводят. Допуск эталонных тестов остаётся как у настоящего оружия (3 мм / 0,01 м), этих двух оружий в списке придуманных нет. (3) Отдельный дефект найден и заведён: [issue 16](https://github.com/deadline-squad/squad-ballistics/issues/16), `flight_at` бросает `math domain error` в пределах около 1e-4 м от конца дальности полёта с ограничением скорости.

## Не убиты и эквивалентность не доказана

Выжившие `ballistics.py` после итогового перепрогона: 1. Они перечислены ниже с правками. `flat_low_elevation` 18 (`error(top) < 0` на `<= 0`) отличается, только если высота при пиковом угле ровно 0.0 до последнего бита, чего ни одно оружие набора не даёт.

| Мутант | Правка |
|---|---|
| `Weapon.flat_low_elevation__mutmut_18` | `-    if error(top) < 0: +    if error(top) <= 0: ` |

### `crosshair.py` (прогон остановлен)

| Мутант | Статус | Правка |
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
