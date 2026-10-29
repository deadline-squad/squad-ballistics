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
* Simple mark setup: style, colour, size
* Built-in SquadCalc browser
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
* Простая настройка метки: вид, цвет, размер
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
2. Enter your horizontal FOV: the in-game setting, or the zoomed FOV when aiming through a scope. Tripod weapons whose view with RMB differs from the plain one (an optic that zooms the screen: QLZ87, SPG-9 scope, AGS-17 optic, ZiS-3; or sights that look below the barrel: MK19) show a *view* switch instead: keep the game's FOV and pick *Sight (RMB)* or *No RMB*; the mark follows that view's zoom and zero. Holding the Focus key narrows the game's FOV to two thirds: type that FOV in.
3. The result updates while you type. The **How to fire** block tells you exactly what to do for the selected weapon.
4. Direct fire (launchers, grenade launchers, guns): put the overlay mark on the target and fire. Without a distance typed, the *range ladder* under the mark shows where a target at each round range (every 25–1000 m, finer near the weapon) goes (flat ground, the weapon's own ballistics); turn it off on the crosshair page.
5. Indirect fire (mortars, Hell Cannon, rockets): set the shown elevation (mils or degrees) on the weapon. These weapons are laid on their own sight, so the overlay shows only the info line, no aim mark.
6. Or skip typing: place your weapon and a target on the SquadCalc map (tab **SquadCalc**) — distance, height difference and bearing go to the calculator by themselves.

1. Выберите оружие (поиск по списку, недавние сверху), введите дистанцию и при необходимости перепад высот: цель выше `+`, ниже `-`.
2. Укажите горизонтальный FOV: значение из настроек игры или FOV прицела при стрельбе через оптику. У станкового оружия, у которого вид с ПКМ отличается от обычного (оптика приближает весь экран: QLZ87, оптика СПГ-9, оптика АГС-17, ЗиС-3; или прицел смотрит ниже ствола: MK19), вместо этого есть переключатель вида: оставьте FOV игры и выберите «Прицел (ПКМ)» или «Без ПКМ» — метка учтёт приближение и пристрелку этого вида. Клавиша Focus (удержание) сужает FOV игры до двух третей: введите этот FOV.
3. Результат пересчитывается при вводе. Блок **«Как стрелять»** говорит, что делать для выбранного оружия.
4. Прямая наводка (гранатомёты, пушки): совместите метку оверлея с целью и стреляйте.
5. Навесной огонь (миномёты, Hell Cannon, ракеты): выставьте показанный угол (милы или градусы) на орудии. Они наводятся своим прицелом, поэтому оверлей показывает только строку с данными, без метки.
6. Или не вводите ничего: поставьте своё оружие и цель на карте SquadCalc (вкладка **SquadCalc**) — дистанция, перепад высот и азимут подставятся в калькулятор сами.

### AGS-17

Pick **AGS-17 · emplacement** for the gun with the PAG-17 optic, **AGS-17 · iron sights emplacement** for the open-sight one (its barrel is tilted 4.5° up, so it lobs 3.65° higher and the hold times differ). / Выберите **AGS-17 · emplacement** для АГС-17 с оптикой ПАГ-17 и **AGS-17 · iron sights emplacement** для АГС-17 с открытым прицелом (его ствол наклонён на 4,5° вверх, поэтому он стреляет навесом на 3,65° выше и время удержания другое).

* **High arc / навесная:** the result is how long to hold **S**: press **W** (barrel back to the top), hold **S** for the shown time, release. While AGS-17 is selected the app counts every S press since the last W, in any window, so always press W right before laying (see *Linux* below). / Результат — сколько держать **S**: нажмите **W** (ствол вверх), зажмите **S** на показанное время и отпустите. Пока выбран АГС-17, программа считает каждое нажатие S с последнего W в любом окне, поэтому всегда жмите W прямо перед наводкой (см. *Linux* ниже).
* **Low arc / настильная:** direct fire with the overlay mark, like other grenade launchers. / Прямая наводка меткой оверлея, как у других гранатомётов.
* **Uphill and downhill / вверх и вниз по склону:** for weapons aimed with the overlay the angle shown is the one above the line to the target (the target is what you put on the mark), and the angle to the horizon is shown under it. / Для оружия с оверлеем показывается угол над линией на цель (с меткой совмещается цель), угол к горизонту — под ним.
* **Both at once / оба сразу:** on the high arc the overlay mark shows the direct-fire aim at the same time (`S 2.31 s · direct fire 3.21°`), and a target too close to lob (under 280 m) is solved for direct fire. / На навесной метка оверлея одновременно показывает прямую наводку, а цель ближе 280 м считается прямой наводкой.
* **Auto-hold / автозажатие** (off by default, Settings → Calculator): press **F7** and the app holds S itself for the time left to the target, then releases; F7 again or W cancels. Synthetic key presses may be treated as a macro by EasyAntiCheat or server rules — your risk. Linux needs write access to `/dev/uinput` (Steam's udev rules) or the game on X11/XWayland. / Выключено по умолчанию (Настройки → Калькулятор): **F7** — программа сама держит S оставшееся время и отпускает; повторное F7 или W отменяет. Нажатия от программы античит и правила сервера могут счесть макросом — на свой риск. В Linux нужен доступ к `/dev/uinput` (правила Steam) или игра в X11/XWayland.
* **Mortar auto-lay / автонаводка миномёта** (with auto-hold on): in the mortar sight press **F7** — the app holds W until the barrel is at its top (1580 mil), then S for the shown time; the sight then shows the mils of the solution. The rate (9°/s) comes from the game files: keyboard pitch ×300 × input ×0.03, the rule that gives the AGS-17's measured 9.08°/s. To make it exact for your game, after a lay type the mils the sight shows into *Sight shows (mil)* and press *Calibrate*: the rate is fitted on the time S was held and kept for that weapon (*Reset* goes back to 9°/s). With *Read the mortar sight off the screen* on (default), F7 lays on the screen instead whenever the mortar's view is on it: for a SquadCalc map target it first turns the mortar with D/A until the HUD compass shows the target's bearing, then reads the mils off the sight's scale and holds W or S until it shows the solution within 0.5 mil (see below); the timed lay is the fallback. Lay from the mortar's own view, not zoomed in with the right mouse button: only that view shows both the scale and the compass. A typed target has no bearing: set it yourself. / С включённым автозажатием: в прицеле миномёта **F7** — программа держит W до упора (1580 мил), затем S показанное время; прицел покажет милы решения. Скорость (9°/с) — из файлов игры: клавиатура ×300 × ввод ×0.03, то же правило даёт измеренные у АГС-17 9.08°/с. Для точности под вашу игру после наводки введите милы с прицела в «Прицел показал (мил)» и нажмите «Уточнить»: скорость подгоняется по времени удержания S и запоминается (кнопка «Сброс» вернёт 9°/с). С включённым «Читать прицел миномёта с экрана» (по умолчанию) F7 наводит по экрану, когда на нём вид миномёта: для цели с карты SquadCalc программа сначала поворачивает миномёт клавишами D/A, пока компас внизу экрана не покажет азимут цели, затем читает милы со шкалы прицела и держит W или S, пока он не покажет решение с точностью до 0,5 мил (см. ниже); наводка по времени остаётся запасной. Наводите из обычного вида миномёта, без приближения правой кнопкой: только там видны и шкала, и компас. У введённой вручную цели нет азимута — его выставляйте сами.
* **Compass reading / чтение компаса:** the bearing is the number under the centre of the HUD compass at the bottom of the screen. The mortar's own view shows it with tenths ("182.2", the camera's yaw rounded to 0.1°); other views show whole degrees ("182", cut, read as 182.5). The digits are matched against the same digit pictures as the sight's scale, and the strip's ticks (one every 15 degrees, 6.33 px per degree at 1080p) must sit where the number puts them within 3°, so a misread number or anything that is not the compass gives no reading. Checked on 1080p frames of current game videos (mortar and AGS-17): no frame gave a wrong bearing: the compass read right wherever its number was clear, and a frame where a marker covered the number or with no compass gave no reading. The game turns the mortar 0.25° × view sensitivity per frame it holds A or D: the lay stops within 0.1° or half that step. While a mortar is laid on a map target the overlay shows the bearing left, e.g. `bearing 120.0° (+3.4)`. / Азимут — это число под центром компаса внизу экрана. В обычном виде миномёта оно с десятыми («182.2», поворот камеры, округлённый до 0,1°), в других видах — целые градусы («182», дробная часть отброшена, читается как 182,5). Цифры сравниваются с теми же образцами, что и цифры шкалы прицела, а деления ленты компаса (через каждые 15 градусов, 6,33 пикселя на градус на 1080p) должны стоять там, где их ставит число, с точностью до 3°: неверно прочитанное число или что-то, кроме компаса, не даёт показания. Проверено на кадрах 1080p из свежих видео игры (миномёт и АГС-17): ни один кадр не дал неверного азимута: там, где число видно чисто, компас прочитан верно, а кадр, где число закрыла метка, и кадры без компаса показаний не дали. Игра поворачивает миномёт на 0,25° × чувствительность вида за каждый кадр, пока зажата A или D: наводка останавливается в пределах 0,1° или половины этого шага. Пока миномёт наводится на цель с карты, оверлей показывает остаток азимута, например `азимут 120.0° (+3.4)`.
* **Mortar sight reading / чтение прицела миномёта:** while a mortar is selected the app reads the elevation off the sight's scale left of the screen centre (several times a second) and shows it on the overlay with what is left to the solution, e.g. `sight 1041.5 mil (+4.6)`. It finds the scale's edge line, the ticks (sub-pixel) and the labels every 10 mils, reads the labels' digits against Roboto Condensed and decodes all visible labels together (they go up by 10), then interpolates the pointer between the ticks: about 0.1 mil on 1080p, any resolution and aspect ratio, HUD scale ±25 %. A lay on the sight: two agreeing readings, then W or S held with the rate measured from the readings and released just before the target, then taps (the shortest tap that moves the barrel and its step are learnt); it stops within 0.5 mil or half the game's frame step, after 12 moves, or when the sight is lost (the key is always released). With an empty *Sight shows (mil)*, *Calibrate* reads the sight off the screen; when it cannot, it saves what it grabbed to `sight-grab.png` in the settings folder. The screen is grabbed under X11 and XWayland, not under pure Wayland. / Пока выбран миномёт, программа несколько раз в секунду читает угол со шкалы прицела слева от центра экрана и пишет его на оверлее вместе с остатком до решения, например `прицел 1041.5 мил (+4.6)`. Она находит край шкалы, деления (с долями пикселя) и подписи через 10 мил, распознаёт цифры подписей по шрифту Roboto Condensed и расшифровывает все видимые подписи вместе (они растут на 10), затем интерполирует указатель между делениями: около 0,1 мил на 1080p, при любом разрешении и соотношении сторон, масштаб интерфейса ±25 %. Наводка по прицелу: два совпавших чтения, затем W или S с измеренной по чтениям скоростью и отпусканием перед целью, затем короткие нажатия (программа узнаёт самое короткое нажатие, которое двигает ствол, и его шаг); останавливается в пределах 0,5 мил или половины шага кадра игры, после 12 движений или если прицел пропал (клавиша всегда отпускается). С пустым полем «Прицел показал (мил)» кнопка «Уточнить» сама читает прицел с экрана, а если не может — сохраняет снимок в `sight-grab.png` в папке настроек. Экран снимается под X11 и XWayland, под чистым Wayland — нет.
* Hold range 280–1925 m on flat ground; the model is fitted on 67 in-game measurements (hold time → distance, 0.02 s RMS) and is the same as in the Deadline SquadCalc. / Зажатием S — от 280 до 1925 м по ровной земле; модель подобрана по 67 замерам в игре (ошибка 0.02 с) и совпадает с SquadCalc Deadline.

Tips / Советы:

* Both `.` and `,` work as the decimal separator on any keyboard layout; `-` anywhere in the height field flips the sign. / Дробную часть можно вводить через `.` или `,` в любой раскладке (на русской подойдут и клавиши «ю»/«б»); `-` в любом месте поля высоты меняет знак.
* The mouse wheel over a field changes the value (Shift ×0.1, Ctrl ×10). / Колесо мыши над полем меняет значение (Shift ×0.1, Ctrl ×10).

| Hotkey (default) | Action / Действие |
|------------------|-------------------|
| F8 | Show / hide overlay — показать / скрыть оверлей |
| F9 | Reset aim mark — сбросить метку |
| — | Distance + / − (bind in Settings) — дистанция + / − (назначается в настройках) |
| F7 | AGS-17 auto-hold / mortar auto-lay, when enabled — автозажатие S АГС-17 / автонаводка миномёта, если включено |

Hotkeys can be changed in **Settings**. They are global, so they work while the game is focused, when the keys can be read (see *Linux* below). / Клавиши меняются в **Настройках**. Они глобальные и работают поверх игры, когда программа видит клавиатуру (см. *Linux* ниже).

### The mark / Метка

The **Crosshair** page has everything about the mark: the live preview, *Align with the sight*, *Style* (dot, cross, T, circle, cross + dot), *Color* (8 swatches), *Size* (one slider, 50–200 %) and two switches, *Range ladder* and *Info text*. The outline is always on and the mark jumps straight to its place.

*Align with the sight* is for when the mark does not sit on the game's sight (for example when you open the MK19's sight): *Move left/right* and *Move up/down* shift the mark and the range ladder (±300 px), *Scale* stretches them (50–150 %), the arrow keys step by 1 and *Reset* puts them back. The F9 hotkey does not touch the alignment: it clears the target. With several monitors, pick the one with the overlay in **Settings → Overlay**. Settings files of older versions load as before: their colour becomes the nearest swatch, the removed options are dropped. / На странице **Crosshair** есть всё про метку: предпросмотр, *Align with the sight*, *Style* (точка, крест, T, круг, крест с точкой), *Color* (8 цветов), *Size* (один ползунок, 50–200 %) и два переключателя, *Range ladder* и *Info text*. Обводка всегда включена, метка сразу встаёт на место.

*Align with the sight* нужен, когда метка не совпадает с прицелом в игре (например, при открытом прицеле MK19): *Move left/right* и *Move up/down* сдвигают метку и шкалу дальности (±300 px), *Scale* растягивает их (50–150 %), стрелки двигают на 1, *Reset* возвращает всё назад. Клавиша F9 выравнивание не трогает: она сбрасывает цель. При нескольких мониторах монитор с оверлеем выбирается в **Settings → Overlay**. Файлы настроек старых версий загружаются как раньше: цвет становится ближайшим из восьми, убранные пункты отбрасываются.

### Linux

The app runs on Linux only, from source: `pip install -r requirements.txt` and `python app.py` (Squad itself runs through Proton). On a Wayland session the app runs itself through XWayland so the overlay stays above the game (set `QT_QPA_PLATFORM` to override). / Программа работает только в Linux, из исходников: `pip install -r requirements.txt` и `python app.py` (сам Squad — через Proton). В сессии Wayland программа сама запускается через XWayland, чтобы оверлей был поверх игры (`QT_QPA_PLATFORM` переопределяет).

The app reads the keyboard in one of two ways: / Клавиатура читается одним из двух способов:

* **input group / группа input** (any session, X11 or Wayland): `sudo usermod -aG input $USER`, then log out and in. / Любая сессия; после команды перезайдите в систему.
* **X11 / XWayland** without extra rights, while the game window has the focus (Proton games run on XWayland). / Без прав, пока в фокусе окно игры (игры Proton работают через XWayland).

The mortar's "lay finished" beep is played with `pw-play`, `paplay` or `aplay`, whichever is installed. The game still receives the hotkeys, so bind keys the game does not use. / Сигнал окончания наводки миномёта играет `pw-play`, `paplay` или `aplay` — что установлено. Игра тоже получает горячие клавиши: назначайте те, что игра не использует.

### Map / Карта

The map tab embeds SquadCalc: by default the Deadline build (`calc.tk104.duckdns.org`, with AGS-17 and every direct-fire weapon of this app), or [squadcalc.app](https://squadcalc.app) (Settings → Map). Map tiles are cached on disk, so a map you have opened loads instantly next time. / Вкладка карты встраивает SquadCalc: по умолчанию сборку Deadline (с АГС-17 и всеми оружиями прямой наводки этой программы), либо squadcalc.app (Настройки → Карта); тайлы кэшируются на диске.

* **Map → calculator / карта → калькулятор:** with the Deadline build, the newest target on the map fills the distance and the height difference, and the bearing appears in the steps and next to the mark (Settings → Map → *Put the map target and weapon into the calculator*). Typing a value by hand takes over until the next map target. squadcalc.app does not share its targets. / Со сборкой Deadline последняя цель на карте подставляет дистанцию и перепад высот, азимут виден в шагах и у метки. Ручной ввод действует до следующей цели с карты. squadcalc.app цели не передаёт.
* **Direct fire from the map / прямая наводка с карты:** the Deadline SquadCalc has a *Direct fire (Squad Ballistics)* group with every weapon aimed by the overlay mark here (launchers, under-barrel and automatic grenade launchers, recoilless and tank guns), computed with the same data, so the angle on the map is the one the mark aims at. The weapon selected there is selected here too (also for mortars and rockets that exist in both); put the weapon and the target on the map and the overlay mark moves to the target by itself. A weapon picked here stays until the selection there changes. / В SquadCalc Deadline есть группа «Прямая наводка (Squad Ballistics)» со всеми оружиями, которые здесь наводятся меткой оверлея (гранатомёты, подствольники, АГС, безоткатки и танковые пушки), посчитанными по тем же данным: угол на карте — тот, на который ставит метка. Оружие, выбранное там, выбирается и здесь (и миномёты/РСЗО, которые есть в обеих программах); поставьте оружие и цель на карте — метка оверлея встанет сама. Оружие, выбранное здесь, остаётся до следующей смены выбора в SquadCalc.
* **Obstacles / препятствия:** with the Deadline build each map target also carries the heights of the terrain and the buildings on the line to it (heightmap built from the game files, ~1.6 cm steps). When the shown trajectory hits them before the target, the solution says where and how high (`⛔ 230 m` on the overlay), suggests the other trajectory when it clears, and the side view draws the terrain and the hit point. Typed values have no profile, so no check. / Со сборкой Deadline к каждой цели с карты приходят высоты рельефа и зданий на линии до неё (карта высот из файлов игры, шаг ~1,6 см). Если траектория упрётся в них раньше цели, решение покажет где и на какой высоте («⛔ 230 м» в оверлее), предложит другую траекторию, если она проходит, а боковой вид нарисует рельеф и точку удара. Для введённых вручную значений проверки нет.

* **Black map / чёрная карта:** the app offers **Compatibility mode** (draws without the GPU) when the map looks black; it can also be switched in Settings → Map. / Если карта чёрная, программа предложит **режим совместимости** (Настройки → Карта).
* **Does not load / не грузится:** press **Retry** or **Open in browser**; Settings → Map → *Open the map in the regular browser* makes that the default. / Кнопки **Повторить** и **Открыть в браузере**; в настройках можно всегда открывать карту в обычном браузере.
* The embedded browser does not use QUIC, Encrypted Client Hello or secure DNS, which networks with blocking (e.g. in Russia) break. / Встроенный браузер не использует QUIC, ECH и защищённый DNS, которые ломаются в сетях с блокировками.

## Features / Возможности

* 50 weapons in 6 groups: grenade launchers, automatic grenade launchers, anti-tank launchers, recoilless and field guns, tank guns, indirect fire. / 50 видов оружия в 6 группах: гранатомёты, автоматические гранатомёты, противотанковые, безоткатные и полевые орудия, танковые пушки, миномёты и РСЗО.
* Rocket boost and slow-down phases (RPG-7, Carl Gustav, NLAW, UB-32). / Учёт разгона и торможения ракет.
* Trajectory view, flight time, apex, impact angle, lead for moving targets. / График траектории, время полёта, высота подъёма, угол падения, упреждение.
* Crosshair page with live preview, five styles, eight colours and one size slider. / Прицел с живым предпросмотром, пятью видами, восемью цветами и одним ползунком размера.
* Aligning the mark with the in-game sight, monitor choice (with several monitors), label next to the mark. The interface is in English. / Выравнивание метки по прицелу игры, выбор монитора (если их несколько), подпись у метки. Интерфейс на английском.

## How it works / Как считается

* No air drag, gravity `9.78 m/s² × gravity scale` of the weapon. Rocket boost/slow-down is folded into the equivalent velocity over the distance.
* Elevation: `θ = atan((v² ∓ √(v⁴ − g(g·d² + 2·h·v²))) / (g·d))`, low or high arc; `h` is measured from the muzzle (`launch_height` above the ground).
* Hold weapons (AGS-17): `hold = (top − θ) / rate` seconds of S after W, within `hold_elevation`.
* Screen offset: rectilinear projection, `offset = (screen_width / 2) / tan(FOV / 2) × tan(θ − bore)`, so it works on any resolution. The game fires along the barrel socket `Attach_Muzzle`, which can be tilted against the camera: `bore` is how far above the screen centre the shot leaves, so each view is zeroed at some range (QLZ87 tripod: −0.9° unzoomed, +0.774° = 100 m in its optic; tripod MK19 +1.674° = 330 m with RMB; SPG-9 scope +2.34° ≈ 1300 m HEAT; AGS-17 open sights +4.5° ≈ 300 m; ZiS-3 +0.4° ≈ 350 m). `bore` is the barrel socket's pitch against the plain camera, `zoom_bore` the same against the RMB camera (the tripod's `AdsCamera1pPositionComponent` is tilted 1.674° on the MK19 and QLZ87 tripods). An optic that zooms the screen narrows the FOV by its `zoom` (the game sets FOV / 3 on the QLZ87, FOV / 4 on the SPG-9 scope, FOV / 2.5 on the AGS-17 optic). / Игра стреляет вдоль гнезда ствола `Attach_Muzzle`, повёрнутого относительно камеры: `bore` — насколько выше центра экрана уходит выстрел, так что каждый вид пристрелян на свою дальность; оптика, приближающая экран, делит FOV на `zoom`.
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
    "note": "English tip"
}
```

* `gravity`: projectile gravity scale (1 = normal, 0 = no drop).
* `acceleration` / `acceleration_time`: rocket motor phase in m/s² and seconds (negative = slows down, UB-32).
* `arc`: default trajectory, `low` or `high`; `aim`: `overlay` (direct fire, aimed with the overlay mark) or `elevation` (set the angle on the weapon; no overlay mark). Defaults to `elevation` for `high` and `overlay` for `low`.
* `unit`: `mil` shows mils first (mortars).
* `angle_offset`: subtracted from the elevation, for weapons whose readout is shifted (technical mortar).
* `launch_height`: muzzle height above the ground in metres (the map height difference is ground to ground).
* `hold_rate` / `hold_elevation`: weapons laid by holding a key (AGS-17): degrees per second and `[lowest, top]` elevation; the high arc is then shown as a hold time.
* `bore`: degrees above the screen centre the shot leaves in the plain view (the barrel socket's tilt against the camera); `zoom`: the FOV divisor of the RMB view (1 = the sights, no zoom) and `zoom_bore`: the bore in that view. A weapon with `zoom` gets the *view* switch.
* `min_distance`, `elevation_limits` `[min, max]`, `category`.

## Development / Разработка

```bash
pip install -r requirements-dev.txt
python app.py              # run / запуск
python app.py --selftest   # smoke test of every weapon through the UI / проверка всех оружий через интерфейс
pytest                     # tests / тесты (every weapon is checked)
```

Every push runs the tests on GitHub Actions (**tests**). A release is a tag `v<version>` on the default branch with its entry in [RELEASE_NOTES.md](RELEASE_NOTES.md); the version is `APP_VERSION` in `config.py` ([RELEASING.md](RELEASING.md)). / Каждый push запускает тесты в GitHub Actions (**tests**). Выпуск — тег `v<версия>` на основной ветке и запись в RELEASE_NOTES.md; версия — `APP_VERSION` в `config.py`.

| What / Что | Where / Где |
|------------|-------------|
| Settings / настройки, `crash.log`, `sight-grab.png` | `~/.config/SquadBallistics` (`$XDG_CONFIG_HOME`) |
| Map cache, SquadCalc settings / кэш карты | `~/.cache/SquadBallistics` (`$XDG_CACHE_HOME`) |

The old `configs/config.json` of versions ≤ 1.1.0 (relative to the working directory) is migrated automatically. / Старый `configs/config.json` версий ≤ 1.1.0 переносится автоматически.

`assets/fonts/RobotoCondensed-Digits.ttf` is the digits of Roboto Condensed (© The Roboto Project Authors), used by the sight reader, under the SIL Open Font License 1.1 (`assets/fonts/RobotoCondensed-OFL.txt`). / Цифры шрифта Roboto Condensed для чтения прицела, лицензия SIL OFL 1.1.
