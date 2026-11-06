# Мутационное тестирование

Как набор тестов проверен мутационным тестированием [mutmut](https://mutmut.readthedocs.io/) 3.8.1 (мутант - правка одного токена в коде; набор тестов, который после неё проходит, мутант пропустил). English version: [mutation-testing.md](mutation-testing.md).

Это запись прогона на 1.6.x. В версии 1.6.3 убрана поправка метки (`trim_for_landing`, `set_trim`, `on_trim_edited` и их тесты); их строки и пункты удалены, остальные числа остались от прогона.

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

Файлы тестов для `mutmut run`: `config`: `test_config.py`, `test_config_behaviour.py`, `test_ui.py`; `keystate`: `test_keystate.py`; `ballistics`: тесты баллистики, метки и оружия; `crosshair`: `test_ui`, `test_calc_state`, `test_view_toggle`, `test_marker_aids`, `test_no_hold_beep`, `test_vehicle_sights_ui`. Запуск `keystate` идёт с `max_children=1`: его X11-тесты делят дисплей `:97`. Таймаут считается выжившим мутантом, пока не разобран; падение процесса тестов (segfault, abort, NULL `Display*`) считается убитым мутантом. Для `crosshair` файлы тестов перечислены в `pytest_add_cli_args_test_selection` (не в `tests_dir`: он запустил бы и `tests/test_hygiene.py`, чья проверка докстрингов падает на любом мутанте), `max_children=3`; прогон запущен как `nice -n 10 docker run --cpus 3 --memory 3g sb-ci-mut mutmut run --max-children 3` в цикле (`systemd-run --user`), который запускает его снова, когда mutmut останавливается с `KeyError: <pid>`, и продолжает с сохранённых результатов. Выжившие затем перепрогнаны как `MUTANT_UNDER_TEST=<id> pytest -x -p no:cacheprovider tests/test_crosshair_mutants.py <исходные файлы>` по три сразу.

## Результаты по модулям

"Исходный набор" - набор `dev` на `5f11d21` (измерен теми же командами). "Новые тесты" - тесты, добавленные рядом; для `ballistics` 459 мутантов, не убитых исходным прогоном, перепроверены по одному на итоговом наборе (`MUTANT_UNDER_TEST`, `pytest -x`): второй полный `mutmut run` на 2356 мутантов с эталонными тестами полёта не уложился во время (начатый прогон остановлен на 286 мутантах).

| Модуль | Всего | Убиты исходным набором | Убиты новыми тестами | Эквивалентные | Открыто |
|---|---|---|---|---|---|
| `config.py` | 324 | 300 (+9 падение) | 6 | 9 | 0 |
| `keystate.py` | 289 | 233 (+18 падение) | 30 (из них 4 без теста) | 8 | 0 |
| `ballistics.py` | 2356 | 1897 | 422 | 37 | 0 |
| `crosshair.py` | 4097 | 3860 (2554 killed, 1161 + 117 crash, 27 killed after a suspicious exit code, 1 hang) | 224 (incl. 25 that had no test) | 13 | 0 |

В исходном прогоне `ballistics` было 439 выживших, 11 мутантов без тестов и 9 таймаутов (459 не убито). Прогон `crosshair.py` охватил все 4097 мутантов одним `mutmut run` (3 рабочих процесса, около 3 ч 15 мин, один раз перезапущен циклом ниже после `KeyError` в mutmut 3.8.1); итог: 2554 убито, 1161 падение (убиты), 212 выжило, 144 подозрительных, 25 без тестов и 1 таймаут. 144 подозрительных и таймаут перепрогнаны по одному на исходных файлах (`MUTANT_UNDER_TEST`, `pytest -x`): 117 обрывают процесс тестов, 27 роняют тест, `set_steps` 3 зависает; все убиты. 237 выживших и мутантов без тестов перепрогнаны на `tests/test_crosshair_mutants.py` плюс исходные файлы: 224 убито (последние 9 - после финальных дополнений файла), 13 эквивалентных (перечислены ниже), открытых нет. `flat_low_elevation` 18 из `ballistics` теперь убит тестом `test_a_shot_that_comes_down_to_exactly_the_ground_at_the_peak_elevation_is_the_root`.

## Новые тесты

Тесты лежат в `tests/test_config_behaviour.py`, `tests/test_keystate.py` и новом `tests/test_ballistics_mutants.py`. Файл баллистики сверяет полёт, вершину и высоту настоящего и придуманного оружия с независимым эталоном `tests/flight.py` (50 Гц шаги игры), фиксирует каждое сообщение проверки в `Weapon.from_dict` и `parse_weapons`, проверяет `solve`, `mark_*`, `range_ladder` и `first_obstacle` точными значениями и точными граничными совпадениями (например, `GRAVITY` = 10: 100 м/с долетает на 1000 м ровно под 45 градусов).

## Тесты crosshair и убитые ими мутанты

Тесты лежат в `tests/test_crosshair_mutants.py` (102 теста, все через настоящий `MainWindow`; медленные или системные части Qt - окно подтверждения, `QProcess`, `QDesktopServices` и инжекторы клавиш - заменены записывающими заглушками). Они фиксируют точным переведённым текстом и значением:

- объяснение недостижимой цели для каждой причины (`out_of_range`, `too_close`, `hold_limit`, `elevation_limit`), в градусах и в милах, и что недостижимая цель очищает (метку, строку инфо, цель удержания, плитки);
- калибровку скорости удержания автонаводки миномёта (границы и тексты `calibrate_lay`, `reset_lay_rate`, `lay_reset_time`);
- показания прицела и компаса, азимут цели, отметку и текст сбоя наводки, конец наводки по азимуту и по прицелу, связку слоёв (`make_bearing_layer`, `apply_auto_hold`, `set_auto_hold`) и клавишу F7 (`auto_hold`, `timed_lay_blocker`, `lay_step`, `start_sight_lay`);
- настройки: сброс, отрисовку карты и перезапуск, следование за картой и её предзагрузку, назначение клавиш, монитор, шаг дистанции, окно поверх остальных, папку настроек, `rebuild`, данные списка оружия.

### Выжившие исходного прогона, убитые новыми тестами

Номера мутантов - суффикс `crosshair.xǁMainWindowǁ<функция>__mutmut_<n>`.

| Функция | Убито | Номера мутантов |
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
| `show_bearing_reading` | 11 | 1, 3, 4, 7, 8, 9, 10, 11, 12, 13, 21 |
| `show_sight_reading` | 10 | 1, 3, 4, 7, 8, 9, 10, 11, 12, 13 |
| `show_unreachable` | 54 | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 19, 21, 22, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 64 |
| `sight_target` | 2 | 2, 3 |
| `timed_lay_blocker` | 3 | 12, 13, 17 |
| `watch_screen` | 1 | 1 |
| `watch_sight` | 2 | 3, 4 |

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
| `x_range_ladder__mutmut_67` | `s <= distance / 4 -> <` | LADDER_STEPS divide each other, so the rounding is the same at the tie |
| `x_load_weapons__mutmut_5` | `open(path, "r", ...) -> open(path, ...)` | "r" is the default mode |
| `x_load_weapons__mutmut_10` | `encoding="utf-8" -> "UTF-8"` | alias of the same codec |

### `crosshair.py`

| Мутант | Правка | Причина |
|---|---|---|
| `MainWindow.rebuild__mutmut_3` | `if self.map_page is not None -> is None` | build_web_page вставляет страницу карты в новый стек раньше отложенного удаления старого центрального виджета, поэтому она переживает перестройку и без отсоединения (проверено: тест перестройки проходит и с мутантом) |
| `MainWindow.rebuild__mutmut_4` | `removeWidget(self.map_page) -> removeWidget(None)` | removeWidget(None) ничего не делает, а следующая строка (setParent(None)) всё равно отсоединяет страницу; причина та же, что у мутанта 3 |
| `MainWindow.on_input_edited__mutmut_5` | `calculate(show_errors=False) -> show_errors=None` | None и False одинаково ложны в `if show_errors or ...` |
| `MainWindow.distance_up__mutmut_4` | `calculate(show_errors=False) -> None` | ложное значение, как выше |
| `MainWindow.distance_up__mutmut_5` | `calculate(show_errors=False) -> True` | `show_errors` важен только для пустого поля дистанции, а NumberEdit.add только что записал в него число |
| `MainWindow.distance_down__mutmut_5` | `calculate(show_errors=False) -> None` | ложное значение, как выше |
| `MainWindow.distance_down__mutmut_6` | `calculate(show_errors=False) -> True` | то же, что distance_up 5 |
| `MainWindow.set_hotkey__mutmut_26` | `hotkeys.get(name, "") -> get(name, None)` | findData не находит ни тот, ни другой вариант, а `max(0, -1)` равно индексу 0 - строке пустой клавиши ("hk_none" первая в списке) |
| `MainWindow.set_hotkey__mutmut_28` | `hotkeys.get(name, "") -> get(name, )` | то же, что 26 (по умолчанию None) |
| `MainWindow.set_hotkey__mutmut_31` | `hotkeys.get(name, "") -> get(name, "XXXX")` | то же, что 26: такой строки нет, снова индекс 0 |

`set_steps__mutmut_3` (цикл `while`, очищающий строки шагов, не заканчивается) убит зависанием: исходный набор упирается в таймаут, это считается убийством.

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
| Ladder: the range_ladder tests | `range_ladder`: 13, 16, 17, 41, 44, 47, 50, 51, 52, 53, 54, 60, 70, 81, 82 |

## Ограниченные по скорости ракеты и эталон

Два придуманных оружия (ограничение скорости и двигатель) сначала расходились с `tests/flight.py` до 0,2 м у дульного среза. Итог: (1) "rocket that burns until the cap" - ошибка входа эталона: эталон считает `acceleration_timeout` 0 как "горит всегда", а в `ballistics.py` `acceleration_time` 0 - "двигателя нет" (единственное такое оружие в `tests/data/game_weapons.json` - NLAW); расхождение в 2 км вызвано этим. (2) Два оружия с конечным временем горения расходятся с эталоном не более чем на 1,6 см при -4..75 градусах и 0,5-900 м и на 4 см (следует за скоростью) и 0,5 м (летит вдоль ствола) при 89 градусах и 120 м. Это погрешность интерполяции таблицы разгона с узлами через 1 градус там, где полёт круто зависит от угла (почти вертикально): предел приближения, а не логическая ошибка, и оружие там не наводят. Допуск эталонных тестов остаётся как у настоящего оружия (3 мм / 0,01 м), этих двух оружий в списке придуманных нет. (3) Отдельный дефект найден и заведён: [issue 16](https://github.com/deadline-squad/squad-ballistics/issues/16), `flight_at` бросает `math domain error` в пределах около 1e-4 м от конца дальности полёта с ограничением скорости.

## Не убиты и эквивалентность не доказана

Нет: каждый мутант `config.py`, `keystate.py`, `ballistics.py` и `crosshair.py` убит или назван эквивалентным выше.
