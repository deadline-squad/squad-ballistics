# About Project

## English

Squad Ballistics is a modern ballistic assistant and tactical overlay system created for the game **Squad**.

The application helps players accurately calculate projectile trajectories, offsets, and aiming corrections for indirect fire and long-range shooting using almost every type of weapon available in the game.

The project is designed primarily for:

* mortars
* grenade launchers
* vehicle cannons
* mounted weapons
* indirect fire systems
* high-angle ballistic shooting

Squad Ballistics provides a real-time customizable crosshair overlay, advanced ballistic calculations, FOV scaling, and an integrated browser for SquadCalc support.

The application was built with focus on:

* minimalistic tactical design
* high usability
* modern UI/UX
* fast calculations
* overlay customization
* standalone desktop experience

Main Features:

* Real-time ballistic calculations
* Dynamic crosshair overlay
* True Crosshair Editor
* RGB customization
* Glow / Bloom effects
* Built-in SquadCalc browser
* Auto-update system
* Hotkeys support
* Modern tactical interface
* Transparent overlay technology
* FOV scaling system
* Dynamic weapons database

Squad Ballistics is constantly evolving and aims to become one of the most advanced ballistic utility tools for Squad players.

---

# О проекте

## Русский

Squad Ballistics — это современный баллистический ассистент и система тактического оверлея для игры **Squad**.

Приложение помогает игрокам точно рассчитывать траекторию снарядов, поправки и смещение прицела для стрельбы навесом и ведения огня на дальние дистанции практически из всех видов оружия в игре.

Проект предназначен в первую очередь для:

* миномётов
* гранатомётов
* пушек техники
* стационарного вооружения
* систем непрямого огня
* навесной стрельбы

Squad Ballistics предоставляет:

* настраиваемый overlay-прицел в реальном времени
* баллистические вычисления
* масштабирование под FOV
* встроенный браузер с интеграцией SquadCalc
* современный минималистичный интерфейс

Главная цель проекта — сделать удобный и красивый инструмент для игроков Squad, который позволяет быстрее и точнее вести огонь на больших дистанциях.

Основные возможности:

* Баллистические расчёты в реальном времени
* Overlay-прицел
* True Crosshair Editor
* RGB кастомизация
* Glow / Bloom эффекты
* Встроенный браузер SquadCalc
* Система автообновлений
* Поддержка hotkeys
* Современный tactical UI
* Прозрачный overlay
* FOV scaling system
* Динамическая база оружия

Проект постоянно развивается и со временем должен стать полноценным тактическим инструментом для игроков Squad.

---

# Usage / Использование

1. Pick a weapon (searchable list, recent weapons on top), enter the distance and, optionally, the height difference: target higher `+`, lower `-`.
2. Enter your horizontal FOV: the in-game setting, or the zoomed FOV when aiming through a scope.
3. The result updates while you type. The **How to fire** block tells you exactly what to do for the selected weapon.
4. Direct fire (launchers, grenade launchers, guns): put the overlay mark on the target and fire.
5. Indirect fire (mortars, Hell Cannon, rockets): set the shown elevation (mils or degrees) on the weapon.
6. Or skip typing: place your weapon and a target on the SquadCalc map (tab **SquadCalc**) — distance, height difference and bearing go to the calculator by themselves.

1. Выберите оружие (поиск по списку, недавние сверху), введите дистанцию и при необходимости перепад высот: цель выше `+`, ниже `-`.
2. Укажите горизонтальный FOV: значение из настроек игры или FOV прицела при стрельбе через оптику.
3. Результат пересчитывается при вводе. Блок **«Как стрелять»** говорит, что делать для выбранного оружия.
4. Прямая наводка (гранатомёты, пушки): совместите метку оверлея с целью и стреляйте.
5. Навесной огонь (миномёты, Hell Cannon, ракеты): выставьте показанный угол (милы или градусы) на орудии.
6. Или не вводите ничего: поставьте своё оружие и цель на карте SquadCalc (вкладка **SquadCalc**) — дистанция, перепад высот и азимут подставятся в калькулятор сами.

### AGS-17

Pick **AGS-17 · emplacement**. / Выберите **AGS-17 · emplacement**.

* **High arc / навесная:** the result is how long to hold **S**: press **W** (barrel back to the top), hold **S**, release on the beep. While AGS-17 is selected the app counts every S press since the last W, in any window, so always press W right before laying (Windows: run it as administrator if the game is; Linux: see below). / Результат — сколько держать **S**: нажмите **W** (ствол вверх), зажмите **S**, отпустите по сигналу. Пока выбран АГС-17, программа считает каждое нажатие S с последнего W в любом окне, поэтому всегда жмите W прямо перед наводкой (Windows: если игра запущена от администратора — запустите программу так же; Linux — см. ниже).
* **Low arc / настильная:** direct fire with the overlay mark, like other grenade launchers. / Прямая наводка меткой оверлея, как у других гранатомётов.
* **Uphill and downhill / вверх и вниз по склону:** for weapons aimed with the overlay the angle shown is the one above the line to the target (the target is what you put on the mark), and the angle to the horizon is shown under it. / Для оружия с оверлеем показывается угол над линией на цель (с меткой совмещается цель), угол к горизонту — под ним.
* **Both at once / оба сразу:** on the high arc the overlay mark shows the direct-fire aim at the same time (`S 2.31 s · direct fire 3.21°`), and a target too close to lob (under 280 m) is solved for direct fire. / На навесной метка оверлея одновременно показывает прямую наводку, а цель ближе 280 м считается прямой наводкой.
* **Timer on the overlay / таймер на оверлее:** a panel in a corner of the screen (Settings → Overlay) shows the target and its hold time, where the barrel shoots right now (`~820 m`), the seconds S has been held with a progress bar that turns green when it is time to release, and whether the app sees S and W. / Панель в углу экрана (Настройки → Оверлей): цель и её время, куда бьёт ствол сейчас (`~820 м`), сколько секунд зажата S с полоской, которая зеленеет, когда пора отпускать, и видит ли программа S и W.
* **Auto-hold / автозажатие** (off by default, Settings → Calculator): press **F7** and the app holds S itself for the time left to the target, then releases; F7 again or W cancels. Synthetic key presses may be treated as a macro by EasyAntiCheat or server rules — your risk. Linux needs write access to `/dev/uinput` (Steam's udev rules) or the game on X11/XWayland. / Выключено по умолчанию (Настройки → Калькулятор): **F7** — программа сама держит S оставшееся время и отпускает; повторное F7 или W отменяет. Нажатия от программы античит и правила сервера могут счесть макросом — на свой риск. В Linux нужен доступ к `/dev/uinput` (правила Steam) или игра в X11/XWayland.
* Hold range 280–1925 m on flat ground; the model is fitted on 67 in-game measurements (hold time → distance, 0.02 s RMS) and is the same as in the Deadline SquadCalc. / Зажатием S — от 280 до 1925 м по ровной земле; модель подобрана по 67 замерам в игре (ошибка 0.02 с) и совпадает с SquadCalc Deadline.

Tips / Советы:

* Both `.` and `,` work as the decimal separator on any keyboard layout; `-` anywhere in the height field flips the sign. / Дробную часть можно вводить через `.` или `,` в любой раскладке (на русской подойдут и клавиши «ю»/«б»); `-` в любом месте поля высоты меняет знак.
* The mouse wheel over a field changes the value (Shift ×0.1, Ctrl ×10). / Колесо мыши над полем меняет значение (Shift ×0.1, Ctrl ×10).

| Hotkey (default) | Action / Действие |
|------------------|-------------------|
| F8 | Show / hide overlay — показать / скрыть оверлей |
| F9 | Reset aim mark — сбросить метку |
| — | Distance + / − (bind in Settings) — дистанция + / − (назначается в настройках) |
| F7 | AGS-17 auto-hold, when enabled — автозажатие S АГС-17, если включено |

Hotkeys can be changed in **Settings**. They are global, so they work while the game is focused: on Windows always, on Linux when the keys can be read (see *Linux* below). / Клавиши меняются в **Настройках**. Они глобальные и работают поверх игры: в Windows всегда, в Linux — когда программа видит клавиатуру (см. *Linux* ниже).

If the mark is slightly off in your setup, adjust **Offset calibration** in Settings. / Если метка немного не совпадает, подстройте **Калибровку смещения** в настройках.

### Linux

Squad runs on Linux through Proton; the S timer, its beep and the in-game hotkeys work there too. The `.exe` is Windows-only: run from source with `pip install -r requirements.txt` and `python app.py`. On a Wayland session the app runs itself through XWayland so the overlay stays above the game (set `QT_QPA_PLATFORM` to override). / Squad запускается в Linux через Proton; таймер S, его сигнал и горячие клавиши в игре работают и там. `.exe` только для Windows: запуск из исходников — `pip install -r requirements.txt` и `python app.py`. В сессии Wayland программа сама запускается через XWayland, чтобы оверлей был поверх игры (`QT_QPA_PLATFORM` переопределяет).

The app reads the keyboard in one of two ways: / Клавиатура читается одним из двух способов:

* **input group / группа input** (any session, X11 or Wayland): `sudo usermod -aG input $USER`, then log out and in. / Любая сессия; после команды перезайдите в систему.
* **X11 / XWayland** without extra rights, while the game window has the focus (Proton games run on XWayland). / Без прав, пока в фокусе окно игры (игры Proton работают через XWayland).

The beep is played with `pw-play`, `paplay` or `aplay`, whichever is installed. Unlike Windows, the game still receives the hotkeys, so bind keys the game does not use. / Сигнал играет `pw-play`, `paplay` или `aplay` — что установлено. В отличие от Windows, игра тоже получает горячие клавиши: назначайте те, что игра не использует.

### Map / Карта

The map tab embeds SquadCalc: by default the Deadline build (`calc.tk104.duckdns.org`, with AGS-17 and every direct-fire weapon of this app), or [squadcalc.app](https://squadcalc.app) (Settings → Map). Map tiles are cached on disk, so a map you have opened loads instantly next time. / Вкладка карты встраивает SquadCalc: по умолчанию сборку Deadline (с АГС-17 и всеми оружиями прямой наводки этой программы), либо squadcalc.app (Настройки → Карта); тайлы кэшируются на диске.

* **Map → calculator / карта → калькулятор:** with the Deadline build, the newest target on the map fills the distance and the height difference, and the bearing appears in the steps and next to the mark (Settings → Map → *Put the map target and weapon into the calculator*). Typing a value by hand takes over until the next map target. squadcalc.app does not share its targets. / Со сборкой Deadline последняя цель на карте подставляет дистанцию и перепад высот, азимут виден в шагах и у метки. Ручной ввод действует до следующей цели с карты. squadcalc.app цели не передаёт.
* **Direct fire from the map / прямая наводка с карты:** the Deadline SquadCalc has a *Direct fire (Squad Ballistics)* group with every weapon aimed by the overlay mark here (launchers, under-barrel and automatic grenade launchers, recoilless and tank guns, autocannons, HMGs), computed with the same data, so the angle on the map is the one the mark aims at. The weapon selected there is selected here too (also for mortars and rockets that exist in both); put the weapon and the target on the map and the overlay mark moves to the target by itself. A weapon picked here stays until the selection there changes. / В SquadCalc Deadline есть группа «Прямая наводка (Squad Ballistics)» со всеми оружиями, которые здесь наводятся меткой оверлея (гранатомёты, подствольники, АГС, безоткатки и танковые пушки, автопушки, пулемёты), посчитанными по тем же данным: угол на карте — тот, на который ставит метка. Оружие, выбранное там, выбирается и здесь (и миномёты/РСЗО, которые есть в обеих программах); поставьте оружие и цель на карте — метка оверлея встанет сама. Оружие, выбранное здесь, остаётся до следующей смены выбора в SquadCalc.
* **SquadCalc on another device / SquadCalc на другом устройстве:** in the Deadline SquadCalc enable the overlay link in its settings and enter the code it shows in Settings → Map → *SquadCalc session code*. / Включите «Связать оверлей-таймер» в настройках SquadCalc Deadline и введите показанный код в Настройки → Карта → «Код сессии SquadCalc».

* **Black map / чёрная карта:** the app offers **Compatibility mode** (draws without the GPU) when the map looks black; it can also be switched in Settings → Map. / Если карта чёрная, программа предложит **режим совместимости** (Настройки → Карта).
* **Does not load / не грузится:** press **Retry** or **Open in browser**; Settings → Map → *Open the map in the regular browser* makes that the default. / Кнопки **Повторить** и **Открыть в браузере**; в настройках можно всегда открывать карту в обычном браузере.
* The embedded browser does not use QUIC, Encrypted Client Hello or secure DNS, which networks with blocking (e.g. in Russia) break. / Встроенный браузер не использует QUIC, ECH и защищённый DNS, которые ломаются в сетях с блокировками.

## Features / Возможности

* 65 standard weapons in 8 groups plus 9 popular mod weapons (hidden by default). / 65 стандартных видов оружия в 8 группах и 9 модовых (по умолчанию скрыты).
* Rocket boost and slow-down phases (RPG-7, Carl Gustav, NLAW, UB-32). / Учёт разгона и торможения ракет.
* Trajectory view, flight time, apex, impact angle, lead for moving targets. / График траектории, время полёта, высота подъёма, угол падения, упреждение.
* Crosshair page with live preview, presets, color swatches, outline and glow. / Прицел с живым предпросмотром, пресетами, палитрой, обводкой и свечением.
* Russian / English interface, accent colors, monitor choice, overlay center offset, label next to the mark. / Русский и английский интерфейс, цвет акцента, выбор монитора, смещение центра, подпись у метки.

## How it works / Как считается

* No air drag, gravity `9.78 m/s² × gravity scale` of the weapon. Rocket boost/slow-down is folded into the equivalent velocity over the distance.
* Elevation: `θ = atan((v² ∓ √(v⁴ − g(g·d² + 2·h·v²))) / (g·d))`, low or high arc; `h` is measured from the muzzle (`launch_height` above the ground).
* Hold weapons (AGS-17): `hold = (top − θ) / rate` seconds of S after W, within `hold_elevation`.
* Screen offset: rectilinear projection, `offset = (screen_width / 2) / tan(FOV / 2) × tan(θ)`, so it works on any resolution.
* Data: velocity, gravity scale and rocket boost are read from the game files (Squad build 26005357): the weapon's `WeaponConfig.MuzzleVelocity`, the projectile's `ProjectileGravityScale` and its `ConstantAcceleration` for `ConstantAccelerationTimeout`, stopped at `MaxSpeed` (raised to the muzzle velocity when that is higher). Elevation limits, arcs and the AGS-17 hold model come from in-game measurements, the [official Squad wiki](https://squad.fandom.com/wiki/Weapons) and [SquadCalc](https://github.com/sh4rkman/SquadCalc). After a game patch, check `weapons.json` against the game files again and edit it; a renamed weapon goes to `RENAMED_WEAPONS` in `ballistics.py` so saved settings and older SquadCalc pages follow.

## Weapons database / База оружия

Weapons live in `weapons.json`. Only `velocity` is required:

```json
"RPG-7 · PG-7V HEAT / OG-7V": {
    "velocity": 117,
    "gravity": 1,
    "acceleration": 150,
    "acceleration_time": 0.8,
    "category": "launchers",
    "note": "English tip",
    "note_ru": "Подсказка"
}
```

* `gravity`: projectile gravity scale (1 = normal, 0 = no drop).
* `acceleration` / `acceleration_time`: rocket motor phase in m/s² and seconds (negative = slows down, UB-32).
* `arc`: default trajectory, `low` or `high`; `aim`: `overlay` (direct fire) or `elevation` (set the angle on the weapon).
* `unit`: `mil` shows mils first (mortars).
* `angle_offset`: subtracted from the elevation, for weapons whose readout is shifted (technical mortar).
* `launch_height`: muzzle height above the ground in metres (the map height difference is ground to ground).
* `hold_rate` / `hold_elevation`: weapons laid by holding a key (AGS-17): degrees per second and `[lowest, top]` elevation; the high arc is then shown as a hold time.
* `min_distance`, `elevation_limits` `[min, max]`, `category`, `mod`.

## Development / Разработка

Windows, quick start (downloads the project into `Desktop\Squad-Ballistics`
and installs everything). Paste into PowerShell:

Windows, быстрый старт (скачает проект в `Рабочий стол\Squad-Ballistics` и
всё установит). Вставьте в PowerShell:

```powershell
irm https://raw.githubusercontent.com/DelineDelorian/Squad-Ballistics/refs/heads/claude/trusting-cray-6sbies/tools/get.ps1 | iex
```

| File | What it does / Что делает |
|------|---------------------------|
| `setup.bat` | Installs Python (if missing) and dependencies — установка |
| `run.bat` | Runs the app from source — запуск без сборки |
| `build.bat` | Builds and self-checks the single-file `dist\SquadBallistics.exe` — сборка exe |
| `test.bat` | Runs the tests — тесты |

Manual / вручную:

```bash
pip install -r requirements-dev.txt
python app.py                     # run from source
pytest                            # tests (every weapon is checked)
pyinstaller SquadBallistics.spec  # build dist/SquadBallistics
```

Every push builds the exe on GitHub Actions (**build-windows**, see
*Artifacts*) without publishing a release. How to publish an update:
[RELEASING.md](RELEASING.md).

Каждый push собирает exe в GitHub Actions (**build-windows**, раздел
*Artifacts*) без публикации релиза. Как выпустить обновление:
[RELEASING.md](RELEASING.md).

The app is a single `SquadBallistics.exe` and writes nothing next to it. / Программа — один файл `SquadBallistics.exe`, рядом с ним ничего не создаётся:

| What / Что | Where / Где |
|------------|-------------|
| Settings / настройки, `crash.log` | `%APPDATA%\SquadBallistics` |
| Map cache, SquadCalc settings / кэш карты | `%LOCALAPPDATA%\SquadBallistics\WebEngine` |
| Update download / загрузка обновления | `%TEMP%\SquadBallisticsUpdate` |

The old `configs/config.json` of versions ≤ 1.1.0 is migrated automatically, and their leftover `_internal` folder is removed after updating.
