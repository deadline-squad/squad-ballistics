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
