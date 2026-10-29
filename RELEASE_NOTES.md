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

**Скачайте только `SquadBallistics.exe`** — это вся программа, ничего распаковывать не нужно. На Linux — запуск из исходников (см. README). Настройки и кэш карты сохраняются.

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

**Скачайте только `SquadBallistics.exe`** — это вся программа, ничего распаковывать не нужно. Настройки хранятся в `%APPDATA%\SquadBallistics`, кэш карты — в `%LOCALAPPDATA%\SquadBallistics`. Если у вас стоит старая версия, она обновится сама.

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
- One file: settings live in `%APPDATA%\SquadBallistics`, map cache in `%LOCALAPPDATA%\SquadBallistics`.

Данные оружия: официальная вики Squad и [SquadCalc](https://github.com/sh4rkman/SquadCalc).
