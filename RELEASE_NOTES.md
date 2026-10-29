## Squad Ballistics 1.6.0

### Что нового
- **Наводка миномёта по азимуту:** для цели с карты SquadCalc F7 теперь сначала поворачивает миномёт клавишами D/A, пока компас внизу экрана не покажет азимут цели (азимут читается с десятыми градуса, остановка в пределах 0,1° или половины шага кадра игры), а затем, как раньше, поднимает ствол по шкале прицела. Наводите из обычного вида миномёта, без приближения: там видны и шкала, и компас. Остаток азимута виден на оверлее.
- **Шкала дальности под меткой:** у оружия прямой наводки под меткой оверлея нарисованы риски 100, 200, 300 м… — куда ставить цель на этой дальности, без ввода дистанции. Шкала следует за оружием, FOV и калибровкой; выключается на странице прицела.
- **Сигнал удержания АГС-17 раньше на время реакции:** игрок отпускает S через 150–300 мс после сигнала, а это 40–120 м перелёта. Теперь сигнал звучит раньше — сначала на 0,2 с, затем программа подстраивает запас по вашим отпусканиям и запоминает его.
- **Подключение устройства без кода:** Настройки → «Подключить устройство» показывают ссылку и QR-код. Отсканируйте его телефоном или откройте ссылку на втором мониторе — SquadCalc Deadline там свяжется с программой сам, и цели с его карты придут сюда. Вводить код больше не нужно, а связь переживает перезапуск программы и браузера: у программы теперь постоянный код сессии (12 символов), «Новый код» отвязывает все устройства, переключатель «Связь с устройствами» выключает связь. Код передаётся во фрагменте ссылки (`#link=`), который не уходит на сервер.

### Изменено
- **Только Linux:** поддержка Windows убрана целиком — нет больше exe, автообновления, сборки PyInstaller и Windows-клавиш. Программа запускается из исходников (`python app.py`), обновление — `git pull`. Клавиши читаются через evdev или X11, нажимаются через uinput или XTest; настройки лежат в `~/.config/SquadBallistics`, кэш карты — в `~/.cache/SquadBallistics`.

### Исправлено
- **QLZ87: метка без недолёта.** Игра стреляет вдоль гнезда ствола, повёрнутого относительно камеры, а оптика станкового QLZ87 (ПКМ) делит FOV на 3. Программа этого не учитывала, и метка давала недолёт и с оптикой, и без неё. Теперь у оружия с такой оптикой есть переключатель вида «Оптика (ПКМ) / Без приближения»: метка и шкала дальности учитывают приближение и пристрелку вида (оптика QLZ87 пристреляна на 100 м, без неё выстрел уходит на 0,9° ниже центра). QLZ87 на Lynx и CSK131 вынесен отдельно (+0,85°); у «Корда» с СПП (×4,5, +0,45°) и M2 с ACOG (+0,22°) поправка тоже учтена. Всё взято из файлов игры.
- **Цель с карты точнее:** дистанция и перепад высот из SquadCalc больше не округляются до целого метра (теряли до 0,5 м, а метр высоты сдвигает близкий выстрел UB-32 на 20–40 м) — теперь до 0,1 м.
- **Ошибки ввода видны сразу:** при расчёте во время ввода FOV вне 1–179 или нулевая дистанция показывали «Введите дистанцию». Теперь показывается сама ошибка; подсказка «Введите дистанцию» — только при пустом поле дистанции.
- **Диалоги читаются:** в окнах «Перезапустить?» и «Сбросить настройки?» светлый текст стоял на светлом фоне и почти не был виден.
- **Контраст на акценте:** на зелёном, янтарном и песочном акценте белый текст кнопок, выбранных переключателей и пунктов списка почти не читался. На светлом акценте текст теперь тёмный.
- **Боковой вид траектории:** настильный выстрел (танк: 0,2 м над линией на 400 м) растягивался в высокую дугу, как у миномёта. Теперь высота вида — не меньше 10 % дистанции, и такой выстрел выглядит почти прямой линией.
- **Подсказка горячих клавиш** переносится только между клавишами, а не посередине «PgUp — Дистанция +».
- Мелочи: «Папка настроек» и «Открыть в браузере» показывают путь или адрес, если в системе нечем их открыть (раньше ничего не происходило), а при включённом «Открывать карту в обычном браузере» вкладка карты тогда открывает встроенную карту; «Сброс» скорости автонаводки оформлен как второстепенная кнопка, как остальные «Сброс»; в английском тексте шаг про автонаводку говорил, что она «включена», когда она выключена.

### What's new
- **Mortar bearing lay:** for a SquadCalc map target F7 now first turns the mortar with D/A until the HUD compass at the bottom of the screen shows the target's bearing (read to a tenth of a degree, stopped within 0.1° or half the game's frame step), then lays the elevation on the sight as before. Lay from the mortar's own view, not zoomed in: it shows both the scale and the compass. The bearing left is on the overlay.
- **Range ladder under the mark:** direct-fire weapons get ticks at 100, 200, 300 m… under the overlay mark — where a target at that range goes, with no distance typed. The ladder follows the weapon, FOV and calibration; turn it off on the crosshair page.
- **AGS-17 hold beep early by your reaction time:** a player releases S 150–300 ms after the beep, 40–120 m long. The beep now comes early — 0.2 s at first, then the app fits the lead to your own releases and keeps it.
- **Connect a device without typing a code:** Settings → *Connect a device* shows a link and a QR code. Scan it with the phone or open the link on the second monitor: the Deadline SquadCalc there links up with the app by itself and its map targets come here. No code to type any more, and the link survives restarts of the app and the browser: the app now keeps one session code (12 characters), *New code* unlinks every device, the *Link with devices* toggle turns the link off. The code travels in the link's fragment (`#link=`), which never reaches the server.

### Changed
- **Linux only:** Windows support is gone entirely — no exe, auto-update, PyInstaller build or Windows key handling. The app runs from source (`python app.py`) and updates with `git pull`. Keys are read through evdev or X11 and sent through uinput or XTest; settings live in `~/.config/SquadBallistics`, the map cache in `~/.cache/SquadBallistics`.

### Fixed
- **QLZ87: no more falling short.** The game fires along the barrel socket, tilted against the camera, and the tripod QLZ87's optic (RMB) divides the FOV by 3. The app ignored both, so the mark fell short zoomed and unzoomed. Weapons with such an optic now have a view switch, *Optic (RMB) / Unzoomed*: the mark and the range ladder follow that view's zoom and zero (the QLZ87 optic is zeroed at 100 m; unzoomed the shot leaves 0.9° below the centre). The QLZ87 on the Lynx and CSK131 is a separate entry (+0.85°); the Kord SPP (×4.5, +0.45°) and the M2 ACOG (+0.22°) get the correction too. All from the game files.
- **Map targets more exact:** the distance and height difference from SquadCalc are no longer rounded to whole metres (up to 0.5 m lost, and a metre of height moves a short UB-32 shot 20–40 m) — they keep a tenth of a metre.
- **Input errors show right away:** while calculating as you type, a FOV outside 1–179 or a zero distance showed "Enter the distance". The error itself is shown now; "Enter the distance" only when the distance field is empty.
- **Readable dialogs:** the "Restart?" and "Reset settings?" boxes had light text on a light background.
- **Contrast on the accent:** with the green, amber and sand accents the white text of buttons, checked segments and selected list rows was hard to read. Light accents get dark text now.
- **Trajectory side view:** a flat shot (a tank shell 0.2 m above the line over 400 m) was stretched into a tall arc like a mortar's. The view is now at least 10 % of the distance tall, so such a shot looks nearly straight.
- **The hotkey hint** wraps only between keys, never inside "PgUp — Distance +".
- Small things: "Settings folder" and "Open in browser" show the path or address when the system has nothing to open them with (they used to do nothing), and with "Open the map in the regular browser" on, the map tab then shows the embedded map; the auto-lay rate "Reset" is a secondary button like the app's other resets; the English auto-lay step said auto-lay "is turned on" while it is off.

## Squad Ballistics 1.5.1

## Squad Ballistics 1.5.1

### Исправлено
- **Строка на оверлее целиком:** строка рядом с меткой обрезалась на 400 пикселях, и у миномёта пропадало чтение прицела («прицел 1041.5 мил (+4.6)»). Теперь она видна полностью, а если не помещается до края экрана — переносится.
- **Меньше нагрузки, пока зажата S:** таймер удержания 100 раз в секунду перерисовывал весь оверлей и пересчитывал разметку окна. Теперь перерисовываются только строка и панель таймера: процессору работы примерно в 3,5 раза меньше.
- **Маленькое окно и масштаб 150 %:** в окне 900×600 правая часть «Решения» обрезалась, а кнопки пресетов налезали на предпросмотр; на экране 1080p с масштабом 150 % окно не помещалось по высоте. Теперь всё помещается, а длинные названия оружия сокращаются (полное — во всплывающей подсказке).
- **«Сбросить настройки»** сбрасывает и уточнённую скорость автонаводки, и FOV (раньше они оставались до перезапуска).
- **Подсказка горячих клавиш** показывает только работающие клавиши: F7 — только при включённом автозажатии. Переключатель автозажатия больше не показывает «включено», если в этой системе программа не может нажимать клавиши.
- Мелочи: после закрытия окна прицел больше не читается с экрана; статус «Уточнить» не переходит на другое оружие; полоса загрузки карты меняет цвет вместе с акцентом; сообщение «Карта не загрузилась» называет нужный сайт; «Уточнить» с пустым полем подсказывает, чего не хватает, вместо того чтобы молча ничего не делать.

### Fixed
- **The whole overlay line:** the line next to the mark was cut at 400 pixels, and mortars lost the sight reading ("sight 1041.5 mil (+4.6)"). It is shown in full now, and wraps when it would run past the screen edge.
- **Less load while S is held:** the hold timer repainted the whole overlay and re-laid out the window 100 times a second. Only the line and the timer panel are repainted now: about 3.5 times less CPU work.
- **Small window and 150 % scaling:** at 900×600 the right side of "Solution" was cut off and the preset buttons overlapped the preview; on a 1080p screen at 150 % the window did not fit vertically. Everything fits now, and long weapon names are shortened (the full name is in the tooltip).
- **"Reset settings"** also resets the calibrated auto-lay rate and the FOV (they used to stay until a restart).
- **The hotkey hint** lists only keys that work: F7 only while auto-hold is on. The auto-hold toggle no longer shows "on" when the app cannot send key presses on this system.
- Small things: the sight is no longer read off the screen after the window closes; the "Calibrate" status no longer carries over to another weapon; the map loading bar follows the accent colour; "The map did not load" names the right site; "Calibrate" with an empty field says what is missing instead of silently doing nothing.

## Squad Ballistics 1.5.0

### Что нового
- **Чтение прицела миномёта с экрана:** пока выбран миномёт, программа читает милы со шкалы его прицела и пишет их на оверлее рядом с нужными, например «прицел 1041.5 мил (+4.6)». Точность около 0,1 мил, любое разрешение и соотношение сторон.
- **Автонаводка по прицелу:** F7 в прицеле миномёта теперь держит W или S, пока прицел не покажет решение с точностью до 0,5 мил: не нужно поднимать ствол до упора, и скорость ствола не важна. Если прицел не читается, работает прежняя наводка по времени.
- **«Уточнить» без ввода:** с пустым полем милы берутся с прицела на экране.

### What's new
- **Mortar sight read off the screen:** while a mortar is selected the app reads the mils off its sight's scale and shows them on the overlay next to the target ones, e.g. "sight 1041.5 mil (+4.6)". About 0.1 mil, any resolution and aspect ratio.
- **Auto-lay on the sight:** F7 in the mortar sight now holds W or S until the sight shows the solution within 0.5 mil — no trip to the top, and the barrel rate does not matter. If the sight cannot be read, the timed lay works as before.
- **Calibrate without typing:** with the field empty the mils are read off the sight on the screen.

## Squad Ballistics 1.4.1

### Что нового
- **Автонаводка миномёта:** с включённым автозажатием нажмите F7 в прицеле миномёта — программа поднимет ствол до упора (W) и опустит его, держа S нужное время; крупно по-прежнему показаны милы для проверки по прицелу. Скорость ствола (9°/с) взята из файлов игры. Чтобы подогнать её под вашу игру, введите после наводки милы с прицела и нажмите «Уточнить» — программа запомнит уточнённую скорость.

### Исправлено
- **Метка оверлея только для оружия, которое ей наводится:** миномёты, Hell Cannon и реактивная артиллерия наводятся своим прицелом по углу, поэтому метки и стрелки у края экрана для них больше нет, остаётся строка с дальностью и углом. Раньше метка уезжала за экран на угол возвышения и сбивала с толку.

### What's new
- **Mortar auto-lay:** with auto-hold on, press F7 in the mortar sight — the app raises the barrel to its top (W) and lowers it by holding S for the right time; the mils stay the big readout to check on the sight. The barrel rate (9°/s) comes from the game files. To fit it to your game, type the mils the sight shows after a lay and press "Calibrate": the app keeps the fitted rate.

### Fixed
- **Overlay mark only for weapons aimed with it:** mortars, Hell Cannon and rocket artillery are laid on their own sight by elevation, so they no longer get a mark or an edge arrow, only the info line with the range and angle. The mark used to fly off-screen by the elevation angle.

## Squad Ballistics 1.4.0

### Что нового
- **Предупреждение о препятствии:** для цели с карты SquadCalc программа знает рельеф и здания до цели (карта высот из самой игры, точность ~1,6 см). Если траектория упрётся в гребень, стену или крышу раньше цели, решение пишет где и на какой высоте, оверлей показывает «⛔ 230 м», а если другая траектория проходит, программа предлагает её (например навес АГС-17 с временем удержания). На боковом виде траектории нарисованы рельеф и точка удара.
- **Баллистика из файлов игры (сборка 26005357):** скорость, гравитация и разгон ракет сверены с самой игрой. Исправлено: АГС-17 — 185 м/с и гравитация ×1.8 (модель удержания S переподобрана по тем же 67 замерам), РПГ-7 — разгон 150 м/с² (PG-7VR — 45 м/с² за 0.6 с), M3 MAAWS — 63 м/с с разгоном до 230 м/с, Carl Gustav M2 — отдельные FFV551 (310 м/с), FFV441D и FFV751 (255 м/с), HESH Challenger 2 — 670 м/с, винтовочная граната — 76 м/с.
- **Новые позиции:** MGL / M32 (75 м/с), AK-40GL (70 м/с), станковый MK19 / C16 / L134A1 (235 м/с), РПГ-7 TBG-7V, ZTD-05 (105 мм), 2A72 БМД-4М и БМП-3М, ZPT99 ЗБЛ-08 / ЗБД-05, станковые M2 с ACOG и «Корд» с СПП (у них гравитация пули ×3).
- **Переименованы** позиции, объединявшие оружие с разной баллистикой (например «MK19 / AGS-17 / AGS-30» → «MK19»). Сохранённый выбор и оружие со старой страницы SquadCalc переводятся на новые названия сами.

### What's new
- **Obstacle warning:** for a target from the SquadCalc map the app knows the terrain and the buildings on the way (heightmap built from the game itself, ~1.6 cm). When the trajectory would hit a ridge, a wall or a roof before the target, the solution says where and how high, the overlay shows "⛔ 230 m", and if the other trajectory clears it the app suggests that one (e.g. the AGS-17 lob with its hold time). The side view draws the terrain and the hit point.
- **Ballistics read from the game files (build 26005357):** velocity, gravity and rocket boost checked against the game itself. Fixed: AGS-17 185 m/s with gravity ×1.8 (S hold model refitted on the same 67 measurements), RPG-7 boost 150 m/s² (PG-7VR 45 m/s² for 0.6 s), M3 MAAWS 63 m/s boosted to 230 m/s, Carl Gustav M2 split into FFV551 (310 m/s), FFV441D and FFV751 (255 m/s), Challenger 2 HESH 670 m/s, rifle grenade 76 m/s.
- **New entries:** MGL / M32 (75 m/s), AK-40GL (70 m/s), tripod MK19 / C16 / L134A1 (235 m/s), RPG-7 TBG-7V, ZTD-05 (105 mm), 2A72 BMD-4M and BMP-3M, ZPT99 ZBL-08 / ZBD-05, tripod M2 ACOG and Kord SPP (bullet gravity ×3).
- **Renamed** entries that mixed weapons with different ballistics (e.g. "MK19 / AGS-17 / AGS-30" → "MK19"). Saved selections and weapons sent by an older SquadCalc page follow the new names.

## Squad Ballistics 1.3.1

### Что нового
- **Оружие синхронизируется с картой в обе стороны:** оружие, выбранное в программе, выбирается и на встроенной карте SquadCalc Deadline — зона поражения и подсказки на карте рисуются для него (раньше карта знала только своё оружие).

### What's new
- **Two-way weapon sync with the map:** the weapon picked in the app is selected on the embedded Deadline SquadCalc map, so its fire coverage and popups are for that weapon.

## Squad Ballistics 1.3.0

### Что нового
- **Метка оверлея с учётом перепада высот:** метка ставится по углу над линией на цель, а не к горизонту. Раньше перепад высот учитывался дважды, и по цели выше или ниже снаряд уходил мимо на величину перепада. Крупная цифра — угол над линией на цель, угол к горизонту — под ней.
- **Карта SquadCalc Deadline → калькулятор:** цель с карты подставляет дистанцию, перепад высот и азимут, а оружие, выбранное в SquadCalc, выбирается и здесь — метка оверлея встаёт на цель сама. В SquadCalc Deadline есть группа «Прямая наводка (Squad Ballistics)» со всеми оружиями оверлея, посчитанными по тем же данным, и кнопка «Зона поражения»: куда оружие достаёт с позиции с учётом рельефа и зданий. С другого устройства — по коду сессии.
- **АГС-17 (станковый):** навесная стрельба по времени удержания S (модель по 67 замерам в игре), таймер с сигналом, панель таймера на оверлее, автозажатие S (выключено по умолчанию). Одновременно метка оверлея показывает прямую наводку; цель ближе 280 м считается прямой наводкой.
- **Linux:** таймер, сигнал, горячие клавиши и автозажатие работают (evdev, X11/XWayland, uinput).

### What's new
- **Overlay mark accounts for the height difference:** it is placed by the angle above the line to the target, not to the horizon (the height difference used to be counted twice).
- **Deadline SquadCalc map → calculator:** the map target fills distance, height and bearing, and the weapon selected there is selected here; the Deadline SquadCalc has a direct-fire group with every overlay weapon and a fire coverage map (terrain and buildings). Remote devices link with a session code.
- **AGS-17 emplacement:** lob by S hold time (fitted on 67 in-game measurements), beep timer, timer panel on the overlay, opt-in auto-hold; the overlay mark shows direct fire at the same time.
- **Linux:** timer, beep, hotkeys and auto-hold work (evdev, X11/XWayland, uinput).

## Squad Ballistics 1.2.0

### Что нового
- **59 видов оружия** (было 6): подствольные и автоматические гранатомёты, РПГ и другие ПТ-гранатомёты с разгоном ракеты, безоткатные орудия, танковые и автоматические пушки, пулемёты, миномёты и РСЗО, плюс оружие из популярных модов.
- **Правильная баллистика:** учитывается гравитация каждого снаряда, разгон и торможение ракет, настильная и навесная траектории, ограничения угла орудия; смещение метки считается по FOV и разрешению экрана.
- **Новый интерфейс:** поиск оружия, расчёт при вводе, график траектории, время полёта, упреждение и пошаговое «Как стрелять» для каждого оружия.
- **Прицел:** живой предпросмотр, пресеты, палитра, обводка, подпись у метки.
- **Настройки:** русский и английский язык, цвет акцента, монитор, смещение центра, калибровка, свои горячие клавиши (в том числе «дистанция ±» прямо из игры).
- **Карта SquadCalc:** быстрее (кэш на диске, без перезагрузок); встроенный браузер больше не использует QUIC, ECH и защищённый DNS, из-за которых карта могла оставаться чёрной в сетях с блокировками (например, в России). Если карта всё равно чёрная — кнопка «Режим совместимости»; карту всегда можно открыть в обычном браузере.
- Дробные числа вводятся через точку или запятую в любой раскладке.

### What's new
- **59 weapons** with correct gravity, rocket boost, low/high arcs and resolution-independent overlay offset.
- New minimal interface with weapon search, live calculation, trajectory view and step-by-step firing instructions.
- Crosshair preview and presets, Russian/English UI, rebindable hotkeys.
- Faster SquadCalc map; the embedded browser no longer uses QUIC, ECH and secure DNS, which could keep the map black on restricted networks; compatibility mode for black maps; open in browser.

Данные оружия: официальная вики Squad и [SquadCalc](https://github.com/sh4rkman/SquadCalc).
