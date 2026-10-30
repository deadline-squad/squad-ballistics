# About Project

## English

Squad Ballistics is a ballistic calculator and aim overlay for the game **Squad**, on Linux.

For a target at a given distance and height difference it tells you how to hit it: the elevation to set on a mortar or a rocket launcher, how long to hold S on the AGS-17, or, for a grenade launcher, an anti-tank launcher or a gun, where to put the target on the screen, shown by a transparent overlay mark over the game.

It covers 78 weapon entries in 6 groups:

* grenade launchers
* automatic grenade launchers
* anti-tank launchers
* recoilless and field guns
* tank guns (and the guns of other vehicles)
* indirect fire: mortars, the Hell Cannon and rockets

Machine guns, autocannons and weapons from mods are not covered.

Main features:

* Solutions while you type, from the game's own projectile model and data (gravity, rocket boost and slow-down)
* Overlay aim mark and range ladder, computed for your FOV, your screen and the weapon's sight
* Mark setup: style, colour, size, alignment with the in-game sight, monitor choice
* Trajectory view, flight time, apex, impact angle, lead for moving targets
* Built-in SquadCalc map whose target and weapon go into the calculator, with a check for terrain and buildings in the way
* AGS-17 hold time and auto-hold, mortar auto-lay by the sight and the compass (F7)
* Global hotkeys
* English interface

---

# О проекте

## Русский

Squad Ballistics — баллистический калькулятор и оверлей-прицел для игры **Squad** в Linux.

Для цели на заданной дистанции и с заданным перепадом высот программа говорит, как в неё попасть: какой угол выставить на миномёте или РСЗО, сколько держать S на АГС-17 или, для гранатомёта, противотанкового гранатомёта или пушки, куда на экране поставить цель — это показывает прозрачная метка оверлея поверх игры.

В ней 78 позиций оружия в 6 группах:

* гранатомёты
* автоматические гранатомёты
* противотанковые гранатомёты
* безоткатные и полевые орудия
* танковые пушки (и пушки другой техники)
* навесной огонь: миномёты, Hell Cannon и реактивные системы

Пулемётов, автопушек и оружия из модов нет.

Основные возможности:

* Решение пересчитывается при вводе, по модели снаряда и данным самой игры (гравитация, разгон и торможение ракет)
* Метка оверлея и шкала дальности, посчитанные под ваш FOV, экран и прицел оружия
* Настройка метки: вид, цвет, размер, выравнивание по прицелу игры, выбор монитора
* График траектории, время полёта, высота подъёма, угол падения, упреждение по движущейся цели
* Встроенная карта SquadCalc: цель и оружие с карты подставляются в калькулятор, с проверкой рельефа и зданий на пути
* Время удержания S и автозажатие для АГС-17, автонаводка миномёта по прицелу и компасу (F7)
* Глобальные горячие клавиши
* Интерфейс на английском

---

# Install / Установка

## English

Requirements:

* Linux on x86_64 with glibc 2.34 or newer (Ubuntu 22.04, Debian 12, Fedora 35 and later), or on aarch64 (ARM) with glibc 2.39 or newer (Ubuntu 24.04 and later). `ldd --version` shows your glibc. Squad itself runs through Proton.
* Python 3.10 or newer: `python3 --version`.
* A compositor for the transparent overlay: KDE Plasma and GNOME have one on; for Xfce, i3, Openbox and the like see *The overlay needs a compositor* below.
* Access to the private GitHub repository **deadline-squad/squad-ballistics** (ask the maintainer), with an SSH key on your GitHub account.

Install into a virtual environment in the app's folder (Ubuntu and Debian refuse a system-wide `pip install` with "externally-managed-environment"):

```bash
sudo apt install git python3-venv libxcb-cursor0   # Debian/Ubuntu; Arch: git python xcb-util-cursor; Fedora: git python3 xcb-util-cursor
git clone git@github.com:deadline-squad/squad-ballistics.git
cd squad-ballistics
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Upgrade: in the `squad-ballistics` folder,

```bash
git pull
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` pins the exact PyQt6 and PyQt6-WebEngine versions the tests pass with, so the pip step after each pull keeps a tested Qt. Without **libxcb-cursor0** Qt stops at the start with "Could not load the Qt platform plugin xcb".

## Русский

Что нужно:

* Linux на x86_64 с glibc 2.34 и новее (Ubuntu 22.04, Debian 12, Fedora 35 и новее) или на aarch64 (ARM) с glibc 2.39 и новее (Ubuntu 24.04 и новее). Версию glibc показывает `ldd --version`. Сам Squad запускается через Proton.
* Python 3.10 и новее: `python3 --version`.
* Композитор для прозрачного оверлея: в KDE Plasma и GNOME он включён; для Xfce, i3, Openbox и подобных см. *оверлею нужен композитор* ниже.
* Доступ к закрытому репозиторию GitHub **deadline-squad/squad-ballistics** (попросите у сопровождающего) и SSH-ключ в вашем аккаунте GitHub.

Установка в виртуальное окружение в папке программы (Ubuntu и Debian не дают ставить `pip install` в систему: «externally-managed-environment»):

```bash
sudo apt install git python3-venv libxcb-cursor0   # Debian/Ubuntu; Arch: git python xcb-util-cursor; Fedora: git python3 xcb-util-cursor
git clone git@github.com:deadline-squad/squad-ballistics.git
cd squad-ballistics
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Обновление: в папке `squad-ballistics`

```bash
git pull
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` закрепляет точные версии PyQt6 и PyQt6-WebEngine, на которых проходят тесты, поэтому шаг с pip после каждого обновления ставит проверенный Qt. Без **libxcb-cursor0** Qt не запускается с ошибкой «Could not load the Qt platform plugin xcb».

---

# Usage / Использование

1. Pick a weapon (searchable list, recent weapons on top; the search also finds a weapon by a vehicle or mount named in its note, so "M1117" or "AAVP" finds *MK19*), enter the distance and, optionally, the height difference: target higher `+`, lower `-`.
2. Enter your horizontal FOV: the in-game setting (the game's slider goes 90-120; 1-179 are accepted). Weapons aimed through a scope, optic or gunner's sight (QLZ87, SPG-9 scope, AGS-17 optic, ZiS-3, tank and IFV guns) are computed for that sight's own zoom and tilt: keep the game's FOV, the app divides it by the sight's zoom. A tripod weapon whose sight zooms the screen on RMB (QLZ87, the QLZ87 on the Lynx / CSK131, AGS-17 optic, SPG-9 scope, ZiS-3) has a second entry, *· no optic*, for its normal view (no RMB, ×1): pick the entry for the view you aim from, the note under the weapon says which. The optic entry used from the normal view puts the mark several times too low and the shot far past the target (QLZ87 at FOV 120: 300 m lands at ~830 m). Holding the Focus key narrows the game's FOV to two thirds: type that FOV in.
3. The result updates while you type. The **How to fire** block tells you exactly what to do for the selected weapon.
4. Direct fire (launchers, grenade launchers, guns): put the overlay mark on the target and fire. Without a distance typed, the *range ladder* under the mark shows where a target at each round range (every 25–1000 m, finer near the weapon) goes (flat ground, the weapon's own ballistics); turn it off on the crosshair page.
   *Vehicle guns:* the mark and the ladder are computed for the gunner's base sight view (its zoom and the gun's tilt against the camera come from the game files; the sight's other zoom levels are not offered). Entries are split per vehicle where the zoom or the tilt differ (*Tank AP · T-62 (2A20)*, *MK19 · M1151 / RHIB open turret* ...).
   *If the mark is off:* the mark comes from the game files, and a weapon or sight can still sit a little differently in the game. Fire once at a known distance (say 300 m: type 300 in *Distance*), find where the shot landed (the map, a rangefinder or a marker) and type that in *Landed at, m*, then press **Apply**. The app works out the correction and shows it in *Trim, deg*; the mark and the range ladder move at once, and the overlay line reads "trim +0.35" while it is on. The trim is an angle, so one shot fixes every range. It is kept per weapon, survives restarts, can be typed or stepped by hand (the mouse wheel moves it 0.05°) and **Reset trim** removes it. Every angle the app shows for the mark includes the trim. On the high arc the landing is solved on the high arc, where more elevation brings the shot nearer (the field's hint then reads "+ nearer"). The AGS-17's lob is laid by holding S, not with the mark, so *Apply* refuses its landing: set the trim from a direct-fire shot on the *Low* arc. It is not the same as *Align with the sight* on the crosshair page: that stretches and shifts the mark on the screen to line it up with an opened sight, while the trim corrects where the shot actually goes.
5. Indirect fire (mortars, Hell Cannon, rockets): set the shown elevation (mils or degrees) on the weapon. These weapons are laid on their own sight, so the overlay shows only the info line, no aim mark.
6. Or skip typing: place your weapon and a target on the SquadCalc map (tab **SquadCalc**) — distance, height difference and bearing go to the calculator by themselves.

1. Выберите оружие (поиск по списку, недавние сверху; поиск находит оружие и по машине или станку из его описания: «M1117» или «AAVP» находит *MK19*), введите дистанцию и при необходимости перепад высот: цель выше `+`, ниже `-`.
2. Укажите горизонтальный FOV: значение из настроек игры (ползунок игры 90–120; принимается 1–179). Оружие, из которого целятся через прицел, оптику или прицел наводчика (QLZ87, оптика СПГ-9, оптика АГС-17, ЗиС-3, пушки танков и БМП), считается для приближения и наклона этого прицела: оставьте FOV игры, программа сама делит его на приближение прицела. У станкового оружия, чей прицел приближает экран по ПКМ (QLZ87, QLZ87 на Lynx / CSK131, оптика АГС-17, оптика СПГ-9, ЗиС-3), есть вторая запись «· no optic» для обычного вида (без ПКМ, ×1): выберите запись для того вида, из которого целитесь, — это написано в заметке под оружием. Запись с оптикой в обычном виде ставит метку в несколько раз ниже, и снаряд улетает далеко за цель (QLZ87 при FOV 120: цель на 300 м — выстрел на ~830 м). Клавиша Focus (удержание) сужает FOV игры до двух третей: введите этот FOV.
3. Результат пересчитывается при вводе. Блок **«Как стрелять»** говорит, что делать для выбранного оружия.
4. Прямая наводка (гранатомёты, противотанковые, пушки): совместите метку оверлея с целью и стреляйте. Если дистанция не введена, *шкала дальности* под меткой показывает, куда ставить цель на каждой круглой дальности (через 25–1000 м, чаще у самого оружия; по ровной земле, по баллистике этого оружия); выключается на странице прицела.
   *Пушки техники:* метка и шкала считаются для базового вида прицела наводчика (его приближение и наклон пушки относительно камеры взяты из файлов игры; другие уровни приближения прицела не предлагаются). Записи разделены по машинам там, где приближение или наклон отличаются (*Tank AP · T-62 (2A20)*, *MK19 · M1151 / RHIB open turret* ...).
   *Если метка мажет:* метка посчитана по файлам игры, но оружие или прицел в игре могут стоять чуть иначе. Выстрелите один раз на известную дистанцию (например 300 м: введите 300 в *Distance*), найдите, куда упал снаряд (карта, дальномер или маркер), впишите это в *Landed at, m* и нажмите **Apply**. Программа посчитает поправку и покажет её в *Trim, deg*; метка и шкала дальности сразу сдвинутся, а пока поправка включена, строка оверлея пишет «trim +0.35». Поправка — это угол, поэтому один выстрел исправляет все дальности. Она хранится отдельно для каждого оружия, сохраняется между запусками, её можно ввести или менять вручную (колесо мыши — шаг 0,05°), а **Reset trim** её убирает. Все углы, которые программа показывает для метки, уже включают поправку. На навесной траектории попадание считается по навесной, где больший угол даёт недолёт (подсказка поля тогда «+ nearer»). Навесную АГС-17 наводят удержанием S, а не меткой, поэтому *Apply* её попадание не принимает: поправку задают по выстрелу прямой наводкой на *Low*. Это не то же самое, что *Align with the sight* на странице прицела: там метка растягивается и сдвигается по экрану, чтобы совпасть с открытым прицелом, а поправка исправляет, куда на самом деле летит выстрел.
5. Навесной огонь (миномёты, Hell Cannon, ракеты): выставьте показанный угол (милы или градусы) на орудии. Они наводятся своим прицелом, поэтому оверлей показывает только строку с данными, без метки.
6. Или не вводите ничего: поставьте своё оружие и цель на карте SquadCalc (вкладка **SquadCalc**) — дистанция, перепад высот и азимут подставятся в калькулятор сами.

### AGS-17

Pick **AGS-17 · emplacement** for the gun with the PAG-17 optic, **AGS-17 · iron sights emplacement** for the open-sight one (its barrel is tilted 4.5° up, so it lobs 3.65° higher and the hold times differ). / Выберите **AGS-17 · emplacement** для АГС-17 с оптикой ПАГ-17 и **AGS-17 · iron sights emplacement** для АГС-17 с открытым прицелом (его ствол наклонён на 4,5° вверх, поэтому он стреляет навесом на 3,65° выше и время удержания другое).

* **High arc / навесная:** the result is how long to hold **S**: press **W** (barrel back to the top), hold **S** for the shown time, release. While AGS-17 is selected the app counts every S press since the last W, in any window, so always press W right before laying (see *Linux* below). / Результат — сколько держать **S**: нажмите **W** (ствол вверх), зажмите **S** на показанное время и отпустите. Пока выбран АГС-17, программа считает каждое нажатие S с последнего W в любом окне, поэтому всегда жмите W прямо перед наводкой (см. *Linux* ниже).
* **Low arc / настильная:** direct fire with the overlay mark, like other grenade launchers. / Прямая наводка меткой оверлея, как у других гранатомётов.
* **Uphill and downhill / вверх и вниз по склону:** for weapons aimed with the overlay the angle shown is the one above the line to the target (the target is what you put on the mark), and the angle to the horizon is shown under it. / Для оружия с оверлеем показывается угол над линией на цель (с меткой совмещается цель), угол к горизонту — под ним.
* **Both at once / оба сразу:** on the high arc the overlay mark shows the direct-fire aim at the same time (`S 2.31 s · direct fire 3.21°`), and a target too close to lob (under 279 m) is solved for direct fire. / На навесной метка оверлея одновременно показывает прямую наводку, а цель ближе 279 м считается прямой наводкой.
* **Auto-hold / автозажатие** (off by default, Settings → Calculator): press **F7** and the app holds S itself for the time left to the target, then releases; F7 again or W cancels. Synthetic key presses may be treated as a macro by EasyAntiCheat or server rules — your risk. Linux needs write access to `/dev/uinput` (Steam's udev rules) or the game on X11/XWayland. / Выключено по умолчанию (Настройки → Калькулятор): **F7** — программа сама держит S оставшееся время и отпускает; повторное F7 или W отменяет. Нажатия от программы античит и правила сервера могут счесть макросом — на свой риск. В Linux нужен доступ к `/dev/uinput` (правила Steam) или игра в X11/XWayland.
* **Mortar auto-lay / автонаводка миномёта** (with auto-hold on): in the mortar sight press **F7** — the app holds W until the barrel is at its top (1580 mil), then S for the shown time; the sight then shows the mils of the solution. The rate (9°/s) comes from the game files: keyboard pitch ×300 × input ×0.03, the rule that gives the AGS-17's measured 9.08°/s. To make it exact for your game, after a lay type the mils the sight shows into *Sight shows (mil)* and press *Calibrate*: the rate is fitted on the time S was held and kept for that weapon if it is within 30 % of 9°/s (*Reset* goes back to 9°/s; a saved rate outside that range is ignored). With *Read the mortar sight off the screen* on (default), F7 lays on the screen instead whenever the mortar's view is on it: for a SquadCalc map target it first turns the mortar with D/A until the HUD compass shows the target's bearing, then reads the mils off the sight's scale and holds W or S until it shows the solution within 0.5 mil (see below); the timed lay is the fallback. Lay from the mortar's own view, not zoomed in with the right mouse button: only that view shows both the scale and the compass. A typed target has no bearing: set it yourself. / С включённым автозажатием: в прицеле миномёта **F7** — программа держит W до упора (1580 мил), затем S показанное время; прицел покажет милы решения. Скорость (9°/с) — из файлов игры: клавиатура ×300 × ввод ×0.03, то же правило даёт измеренные у АГС-17 9.08°/с. Для точности под вашу игру после наводки введите милы с прицела в «Прицел показал (мил)» и нажмите «Уточнить»: скорость подгоняется по времени удержания S и запоминается, если отличается от 9°/с не больше чем на 30 % (кнопка «Сброс» вернёт 9°/с; сохранённая скорость вне этих пределов не используется). С включённым «Читать прицел миномёта с экрана» (по умолчанию) F7 наводит по экрану, когда на нём вид миномёта: для цели с карты SquadCalc программа сначала поворачивает миномёт клавишами D/A, пока компас внизу экрана не покажет азимут цели, затем читает милы со шкалы прицела и держит W или S, пока он не покажет решение с точностью до 0,5 мил (см. ниже); наводка по времени остаётся запасной. Наводите из обычного вида миномёта, без приближения правой кнопкой: только там видны и шкала, и компас. У введённой вручную цели нет азимута — его выставляйте сами.
* **Compass reading / чтение компаса:** the bearing is the number under the centre of the HUD compass at the bottom of the screen. The mortar's own view shows it with tenths ("182.2", the camera's yaw rounded to 0.1°); other views show whole degrees ("182", cut, read as 182.5). The digits are matched against the same digit pictures as the sight's scale. The strip must confirm the number: its ticks (one every 15 degrees, 6.33 px per degree at 1080p) must sit where the number puts them, and the labels under the nearest ticks (the 3-digit numbers 12 to 40° either side) must read as the values the number implies and sit where it puts them; so a misread number or anything that is not the compass gives no reading. The tolerance is 1.5° while the mortar stands still (the lay's confirm and settle phases) and 2.5° otherwise (the strip lags behind a turn); while the barrel turns, the lay takes the number alone and checks it against the last reading. The compass is found at HUD scales 0.8 to 1.25, and a compass drawn without its ticks is read from its labels. Checked on 270 1080p frames of current game videos (mortar, Grad and AGS-17): 245 read (201 with the earlier reader, which also gave one wrong bearing, 271 for 274); replacing every digit of those numbers with every other digit, no tens or hundreds digit passed (20% of tens did before), a units digit 2° or more off never passes on a still strip and one 3° or more never on a turning one, and no frame without a compass (236) gave a reading; the tenths digit is not checked (under 1°). A frame where a marker covered the number or with no compass gives no reading. The game turns the mortar 0.25° × view sensitivity per frame it holds A or D: the lay stops within 0.1° or half that step. While a mortar is laid on a map target the overlay shows the bearing left, e.g. `bearing 120.0° (+3.4)`. / Азимут — это число под центром компаса внизу экрана. В обычном виде миномёта оно с десятыми («182.2», поворот камеры, округлённый до 0,1°), в других видах — целые градусы («182», дробная часть отброшена, читается как 182,5). Цифры сравниваются с теми же образцами, что и цифры шкалы прицела. Лента должна подтвердить число: её деления (через каждые 15 градусов, 6,33 пикселя на градус на 1080p) стоят там, где их ставит число, а подписи под ближайшими делениями (трёхзначные числа в 12–40° по обе стороны) читаются как значения, которые подразумевает число, и стоят там, где оно их ставит; поэтому неверно прочитанное число или что-то, кроме компаса, не даёт показания. Допуск 1,5°, пока миномёт стоит (фазы подтверждения и остановки наводки), и 2,5° в остальное время (лента отстаёт при повороте); пока ствол поворачивается, наводка берёт одно число и сверяет его с предыдущим показанием. Компас находится при масштабе HUD от 0,8 до 1,25, а компас без делений читается по подписям. Проверено на 270 кадрах 1080p из свежих видео игры (миномёт, Град и АГС-17): прочитано 245 (201 прежним чтением, которое к тому же дало один неверный азимут: 271 вместо 274); при замене каждой цифры этих чисел любой другой цифра десятков или сотен не прошла ни разу (раньше проходило 20 % десятков), единицы с ошибкой от 2° не проходят на неподвижной ленте, а от 3° — на поворачивающейся, и ни один из 236 кадров без компаса показания не дал; цифра десятых не проверяется (ошибка меньше 1°). Кадр, где число закрыла метка, и кадры без компаса показаний не дают. Игра поворачивает миномёт на 0,25° × чувствительность вида за каждый кадр, пока зажата A или D: наводка останавливается в пределах 0,1° или половины этого шага. Пока миномёт наводится на цель с карты, оверлей показывает остаток азимута, например `азимут 120.0° (+3.4)`.
* **Mortar sight reading / чтение прицела миномёта:** while a mortar is selected the app reads the elevation off the sight's scale left of the screen centre (several times a second) and shows it on the overlay with what is left to the solution, e.g. `sight 1041.5 mil (+4.6)`. It finds the scale's edge line, the ticks (sub-pixel) and the labels every 10 mils, reads the labels' digits against Roboto Condensed and decodes all visible labels together (they go up by 10), then interpolates the pointer between the ticks: about 0.1 mil on 1080p, any resolution and aspect ratio, HUD scale ±25 %. A lay on the sight: two agreeing readings, then W or S held with the rate measured from the readings and released just before the target, then taps (the shortest tap that moves the barrel and its step are learnt); it stops within 0.5 mil or half the game's frame step, after 12 moves, or when the sight is lost (the key is always released). With an empty *Sight shows (mil)*, *Calibrate* reads the sight off the screen; when it cannot, it saves what it grabbed to `sight-grab.png` in the settings folder. The screen is grabbed under X11 and XWayland, not under pure Wayland. / Пока выбран миномёт, программа несколько раз в секунду читает угол со шкалы прицела слева от центра экрана и пишет его на оверлее вместе с остатком до решения, например `прицел 1041.5 мил (+4.6)`. Она находит край шкалы, деления (с долями пикселя) и подписи через 10 мил, распознаёт цифры подписей по шрифту Roboto Condensed и расшифровывает все видимые подписи вместе (они растут на 10), затем интерполирует указатель между делениями: около 0,1 мил на 1080p, при любом разрешении и соотношении сторон, масштаб интерфейса ±25 %. Наводка по прицелу: два совпавших чтения, затем W или S с измеренной по чтениям скоростью и отпусканием перед целью, затем короткие нажатия (программа узнаёт самое короткое нажатие, которое двигает ствол, и его шаг); останавливается в пределах 0,5 мил или половины шага кадра игры, после 12 движений или если прицел пропал (клавиша всегда отпускается). С пустым полем «Прицел показал (мил)» кнопка «Уточнить» сама читает прицел с экрана, а если не может — сохраняет снимок в `sight-grab.png` в папке настроек. Экран снимается под X11 и XWayland, под чистым Wayland — нет.
* Hold range 279–1931 m on flat ground; the model is fitted on 67 in-game measurements (hold time → distance, 0.02 s RMS) and is the same as in the Deadline SquadCalc. / Зажатием S — от 279 до 1931 м по ровной земле; модель подобрана по 67 замерам в игре (ошибка 0.02 с) и совпадает с SquadCalc Deadline.

Tips / Советы:

* Both `.` and `,` work as the decimal separator on any keyboard layout; `-` anywhere in the height field flips the sign. / Дробную часть можно вводить через `.` или `,` в любой раскладке (на русской подойдут и клавиши «ю»/«б»); `-` в любом месте поля высоты меняет знак.
* The mouse wheel over a field changes the value (Shift ×0.1, Ctrl ×10). / Колесо мыши над полем меняет значение (Shift ×0.1, Ctrl ×10).

| Hotkey (default) | Action / Действие |
|------------------|-------------------|
| F8 | Show / hide overlay — показать / скрыть оверлей |
| F9 | Clear the target (distance, map target, mark) — сбросить цель (дистанцию, цель с карты, метку) |
| — | Distance + / − (bind in Settings) — дистанция + / − (назначается в настройках) |
| F7 | AGS-17 auto-hold / mortar auto-lay, when enabled — автозажатие S АГС-17 / автонаводка миномёта, если включено |

When F7 cannot start a lay (no target, the keyboard cannot be read, W cannot be sent, a weapon not laid by a key) or a lay stops short (the sight or the compass is lost, the key moved nothing, too many moves), the overlay line says why, e.g. `F7: no target, enter a distance in range` or `Elevation lay stopped: the key moved nothing (end of travel?)`; F7 again or another weapon clears it. A lay you stop yourself shows no ✗. A new SquadCalc target during the elevation part of a mortar lay starts the lay again from the bearing. The overlay angles follow *Primary angle unit*. / Если F7 не может начать наводку (нет цели, клавиатура не читается, нельзя нажать W, оружие не наводится клавишей) или наводка остановилась раньше цели (прицел или компас пропали, клавиша ничего не сдвинула, слишком много движений), строка оверлея пишет почему; повторное F7 или другое оружие её убирает. Остановленная вами наводка не показывает ✗. Новая цель SquadCalc во время наводки миномёта по углу начинает наводку заново с азимута. Углы на оверлее — в единицах «Primary angle unit».

Hotkeys can be changed in **Settings**. They are global, so they work while the game is focused, when the keys can be read (see *Linux* below). / Клавиши меняются в **Настройках**. Они глобальные и работают поверх игры, когда программа видит клавиатуру (см. *Linux* ниже).

### The mark / Метка

The **Crosshair** page has everything about the mark: the live preview, *Align with the sight*, *Style* (dot, cross, T, circle, cross + dot), *Color* (8 swatches), *Size* (one slider, 50–200 %) and two switches, *Range ladder* and *Info text*. The outline is always on and the mark jumps straight to its place.

*Align with the sight* is for when the mark does not sit on the game's sight (for example when you open the MK19's sight): *Move left/right* and *Move up/down* shift the mark and the range ladder (±300 px), *Scale* stretches them (50–150 %), the arrow keys step by 1 and *Reset* puts them back. The F9 hotkey (and the *Reset* button on the Calculator page) does not touch the alignment: it clears the target, the distance and the map target included, so the mark does not come back until a new target is given. The mortar's sight and compass are read at the screen's centre, wherever the mark is aligned. With several monitors, pick the one with the overlay in **Settings → Overlay**. Settings files of older versions load as before: their colour becomes the nearest swatch, the removed options are dropped. / На странице **Crosshair** есть всё про метку: предпросмотр, *Align with the sight*, *Style* (точка, крест, T, круг, крест с точкой), *Color* (8 цветов), *Size* (один ползунок, 50–200 %) и два переключателя, *Range ladder* и *Info text*. Обводка всегда включена, метка сразу встаёт на место.

*Align with the sight* нужен, когда метка не совпадает с прицелом в игре (например, при открытом прицеле MK19): *Move left/right* и *Move up/down* сдвигают метку и шкалу дальности (±300 px), *Scale* растягивает их (50–150 %), стрелки двигают на 1, *Reset* возвращает всё назад. Клавиша F9 (и кнопка *Reset* на странице «Калькулятор») выравнивание не трогает: она сбрасывает цель вместе с дистанцией и целью с карты, поэтому метка не вернётся, пока не задана новая цель. Прицел и компас миномёта читаются в центре экрана, куда бы ни была выровнена метка. При нескольких мониторах монитор с оверлеем выбирается в **Settings → Overlay**. Файлы настроек старых версий загружаются как раньше: цвет становится ближайшим из восьми, убранные пункты отбрасываются.

### Linux

On a Wayland session the app runs itself through XWayland so the overlay stays above the game (set `QT_QPA_PLATFORM` to override). Install and upgrade: see *Install* above. / В сессии Wayland программа сама запускается через XWayland, чтобы оверлей был поверх игры (`QT_QPA_PLATFORM` переопределяет). Установка и обновление — в разделе *Установка* выше.

**The overlay needs a compositor / оверлею нужен композитор.** The overlay is a transparent window; on X11 transparency exists only while a compositing manager runs (KDE Plasma and GNOME have one on by default; Xfce: Window Manager Tweaks → Compositor; i3, Openbox and similar: start `picom`). Without one the overlay would cover the screen in black, so the app does not show it and says why. The app keeps watching: when compositing stops while the overlay is up, the overlay hides with the same warning, and once compositing runs again it comes back by itself (or press the overlay hotkey, F8). On **KDE Plasma (X11)** the usual cause is the game itself: KWin lets a fullscreen window block compositing, and games under Proton ask for it. Untick System Settings → Display & Monitor → Compositor → "Allow applications to block compositing", or add a rule for the game in System Settings → Window Management → Window Rules ("Block compositing": Force, No); if compositing is off altogether, tick "Enable on startup" there and press Alt+Shift+F12. Wayland sessions always composite. / Оверлей — прозрачное окно, а в X11 прозрачность есть, только пока работает композитный менеджер (в KDE Plasma и GNOME включён по умолчанию; Xfce: Настройки диспетчера окон → Композитинг; i3, Openbox и т. п.: запустите `picom`). Без него оверлей закрыл бы экран чёрным, поэтому программа его не показывает и объясняет почему. Программа следит за композитором и дальше: если композитинг остановился, пока оверлей на экране, оверлей прячется с тем же предупреждением, а когда композитинг снова работает, возвращается сам (или нажмите клавишу оверлея, F8). В **KDE Plasma (X11)** обычно виновата сама игра: KWin разрешает полноэкранному окну отключать композитинг, а игры через Proton об этом просят. Снимите флажок System Settings → Display & Monitor → Compositor → «Allow applications to block compositing» (в русском интерфейсе: Параметры системы → Экран и монитор → раздел композитора) или добавьте для игры правило в System Settings → Window Management → Window Rules («Block compositing»: Force, No); если композитинг выключен совсем, отметьте там «Enable on startup» и нажмите Alt+Shift+F12. Сессии Wayland композитор есть всегда.

Only one copy runs at a time: a second start says that the app is already running and closes. When the settings file cannot be read, it is kept as `config.json.bad` next to the new one and the app says so; a setting with an impossible value (wrong type, `NaN`, a fraction where a whole number belongs) falls back to its default alone. / Одновременно работает только одна копия: второй запуск сообщает, что программа уже запущена, и закрывается. Если файл настроек не читается, он сохраняется как `config.json.bad` рядом с новым и программа сообщает об этом; настройка с невозможным значением (не тот тип, `NaN`, дробь вместо целого) сбрасывается к умолчанию одна, остальные остаются.

The app reads the keyboard in one of two ways: / Клавиатура читается одним из двух способов:

* **input group / группа input** (any session, X11 or Wayland): `sudo usermod -aG input $USER`, then log out and in. Mind what it grants: every program you run can then read every key you press, passwords included, not only this app. A keyboard plugged in or reconnected later (a KVM switch, a dock, Bluetooth) is picked up within a few seconds. / Любая сессия; после команды перезайдите в систему. Учтите, что это даёт: любая ваша программа сможет читать все нажатия клавиш, включая пароли, а не только эта. Клавиатура, подключённая или переподключённая позже (KVM, док-станция, Bluetooth), подхватывается за несколько секунд.
* **X11 / XWayland** without extra rights, while the game window has the focus (Proton games run on XWayland). / Без прав, пока в фокусе окно игры (игры Proton работают через XWayland).

The auto-lay presses W, S, A and D by their position on a US QWERTY keyboard (Linux key codes), not by the letter: with AZERTY, Dvorak, Colemak or a key remapper, or with the game's movement keys rebound, the lay moves the wrong way or not at all. Keep the game on the default W/A/S/D bindings for the mortar and the AGS-17. / Автонаводка нажимает W, S, A и D по их месту на клавиатуре US QWERTY (коды клавиш Linux), а не по букве: при AZERTY, Dvorak, Colemak, переназначении клавиш или других клавишах движения в игре наводка пойдёт не туда или не пойдёт. Для миномёта и АГС-17 оставьте в игре стандартные W/A/S/D.

The mortar's "lay finished" beep is played with `pw-play`, `paplay` or `aplay`, whichever is installed. The game still receives the hotkeys, so bind keys the game does not use. / Сигнал окончания наводки миномёта играет `pw-play`, `paplay` или `aplay` — что установлено. Игра тоже получает горячие клавиши: назначайте те, что игра не использует.

### Map / Карта

The map tab embeds SquadCalc: by default the Deadline build (`calc.tk104.duckdns.org`, with AGS-17 and every direct-fire weapon of this app), or [squadcalc.app](https://squadcalc.app) (Settings → Map). Map tiles are cached on disk, so a map you have opened loads instantly next time. / Вкладка карты встраивает SquadCalc: по умолчанию сборку Deadline (с АГС-17 и всеми оружиями прямой наводки этой программы), либо squadcalc.app (Настройки → Карта); тайлы кэшируются на диске.

* **Map → calculator / карта → калькулятор:** with the Deadline build, the newest target on the map fills the distance and the height difference, and the bearing appears in the steps and next to the mark (Settings → Map → *Put the map target and weapon into the calculator*). Typing a value by hand takes over until the next map target. squadcalc.app does not share its targets. / Со сборкой Deadline последняя цель на карте подставляет дистанцию и перепад высот, азимут виден в шагах и у метки. Ручной ввод действует до следующей цели с карты. squadcalc.app цели не передаёт.
* **Direct fire from the map / прямая наводка с карты:** the Deadline SquadCalc has a *Direct fire (Squad Ballistics)* group with every weapon aimed by the overlay mark here (launchers, under-barrel and automatic grenade launchers, recoilless and tank guns), computed with the same data, so the angle on the map is the one the mark aims at. The *· no optic* entries are not on the map: they fly the same trajectory as their optic entry, so pick that one on the map and the *· no optic* one here (it stays until the selection on the map changes). The weapon selected there is selected here too (also for mortars and rockets that exist in both); put the weapon and the target on the map and the overlay mark moves to the target by itself. A weapon picked here stays until the selection there changes. / В SquadCalc Deadline есть группа «Прямая наводка (Squad Ballistics)» со всеми оружиями, которые здесь наводятся меткой оверлея (гранатомёты, подствольники, АГС, безоткатки и танковые пушки), посчитанными по тем же данным: угол на карте — тот, на который ставит метка. Записей «· no optic» на карте нет: их траектория та же, что у записи с оптикой, поэтому на карте выберите её, а здесь — «· no optic» (выбор держится до смены оружия на карте). Оружие, выбранное там, выбирается и здесь (и миномёты/РСЗО, которые есть в обеих программах); поставьте оружие и цель на карте — метка оверлея встанет сама. Оружие, выбранное здесь, остаётся до следующей смены выбора в SquadCalc.
* **Obstacles / препятствия:** with the Deadline build each map target also carries the heights of the terrain and the buildings on the line to it (heightmap built from the game files, ~1.6 cm steps). When the shown trajectory hits them before the target, the solution says where and how high (`⛔ 230 m` on the overlay), suggests the other trajectory when it clears, and the side view draws the terrain and the hit point. Typed values have no profile, so no check. / Со сборкой Deadline к каждой цели с карты приходят высоты рельефа и зданий на линии до неё (карта высот из файлов игры, шаг ~1,6 см). Если траектория упрётся в них раньше цели, решение покажет где и на какой высоте («⛔ 230 м» в оверлее), предложит другую траекторию, если она проходит, а боковой вид нарисует рельеф и точку удара. Для введённых вручную значений проверки нет.

* **Black map / чёрная карта:** the app offers **Compatibility mode** (draws without the GPU) when the map looks black; it can also be switched in Settings → Map. / Если карта чёрная, программа предложит **режим совместимости** (Настройки → Карта).
* **Does not load / не грузится:** press **Retry** or **Open in browser**; Settings → Map → *Open the map in the regular browser* makes that the default. / Кнопки **Повторить** и **Открыть в браузере**; в настройках можно всегда открывать карту в обычном браузере.
* The embedded browser does not use QUIC, Encrypted Client Hello or secure DNS, which networks with blocking (e.g. in Russia) break. / Встроенный браузер не использует QUIC, ECH и защищённый DNS, которые ломаются в сетях с блокировками.

## How it works / Как считается

* The game's own projectile model (Squad build 26005357, `USQProjectileMovement`): no air drag, gravity `9.80 m/s² × gravity scale` of the weapon (`DefaultGravityZ` −980 cm/s²). The shell leaves the muzzle, the barrel socket `Attach_Muzzle`, which sits `muzzle_forward` along the barrel and `muzzle_up` above its axis, the barrel pivoting `launch_height` above the ground, so the launch point moves with the elevation. A rocket motor (or the UB-32's braking) pushes with a constant `acceleration` along the barrel's axis for `acceleration_time` seconds. Both phases are exact parabolas; the elevation is found by root finding on that closed form (a plain parabola uses the formula below). The result is checked against an independent 1 ms Runge-Kutta flight (`tests/test_mark_end_to_end.py`) and agrees with SquadCalc to 1e-6°.
* Elevation: `θ = atan((v² ∓ √(v⁴ − g(g·d² + 2·h·v²))) / (g·d))`, low or high arc; `h` is the target height above the barrel's pivot (`launch_height` above the ground).
* Hold weapons (AGS-17): `hold = (top − θ) / rate` seconds of S after W, within `hold_elevation`.
* Screen offset: rectilinear projection, `offset = (screen_width / 2) / tan(FOV / 2) × tan(θ − bore)`, so it works on any resolution. The game fires along the barrel socket `Attach_Muzzle`, which can be tilted against the camera: `bore` is how far above the screen centre the shot leaves, so each sight is zeroed at some range (QLZ87 tripod: +0.774° = 100 m in its optic, −0.9° from its normal view, no zero; tripod MK19 +1.674° = 330 m; SPG-9 scope +2.34° ≈ 1300 m HEAT; AGS-17 open sights +4.5° ≈ 300 m; ZiS-3 +0.4° ≈ 350 m). `bore` is the barrel socket's pitch against the camera of the view the weapon is aimed through (the tripod's `AdsCamera1pPositionComponent` is tilted 1.674° on the MK19 and QLZ87 tripods). A sight that zooms the screen narrows the FOV by its `zoom` (the game sets FOV / 3 on the QLZ87, FOV / 4 on the SPG-9 scope, FOV / 2.5 on the AGS-17 optic); an FOV that the sight would narrow below 1° is held at 1° (the mark is then not exact). / Игра стреляет вдоль гнезда ствола `Attach_Muzzle`, повёрнутого относительно камеры: `bore` — насколько выше центра экрана уходит выстрел, так что каждый вид пристрелян на свою дальность; оптика, приближающая экран, делит FOV на `zoom`.
* Data: velocity, gravity scale and rocket boost are read from the game files (Squad build 26005357): the weapon's `WeaponConfig.MuzzleVelocity`, the projectile's `ProjectileGravityScale` and its `ConstantAcceleration` for `ConstantAccelerationTimeout`, with the rocket's time at the `MaxSpeed` cap folded into `acceleration_time` (the cap itself is not simulated: see issue #4 in deadline-squad/squad-ballistics). Elevation limits, arcs and the AGS-17 hold model come from in-game measurements, the [official Squad wiki](https://squad.fandom.com/wiki/Weapons) and [SquadCalc](https://github.com/sh4rkman/SquadCalc). After a game patch, check `weapons.json` against the game files again and edit it; a renamed weapon goes to `RENAMED_WEAPONS` in `ballistics.py` so saved settings and older SquadCalc pages follow.

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
* `launch_height`: height of the barrel's pivot above the ground in metres (the map height difference is ground to ground); `muzzle_forward` / `muzzle_up`: where the barrel socket `Attach_Muzzle` is, metres along the barrel and above its axis from the pivot. The shell starts there, so the launch point moves with the elevation (mortar, Hell Cannon, UB-32).
* `hold_rate` / `hold_elevation`: weapons laid by holding a key (AGS-17): degrees per second and `[lowest, top]` elevation; the high arc is then shown as a hold time.
* `bore`: degrees above the screen centre the shot leaves in the view the weapon is aimed through (the barrel socket's tilt against that camera); `zoom`: the FOV divisor of that view (a scope, an optic or a gunner's sight; leave it out for ×1). One entry has one view; there is no view switch. A weapon whose RMB sight zooms the screen has a second entry, `<name> · no optic`, for its normal view: the same gun with no `zoom` and the plain camera's `bore` (the QLZ87 tripod's plain camera is level with the gun mount, its RMB camera 1.674° down, so −0.9° and +0.774°). Each note says which view the entry is for.
* Unknown keys are rejected when `weapons.json` is loaded (a misspelt key used to fall back to its default silently).
* `min_distance`, `elevation_limits` `[min, max]`, `category`.

## Development / Разработка

```bash
.venv/bin/pip install -r requirements-dev.txt     # in the venv from *Install* / в окружении из «Установки»
.venv/bin/python app.py                           # run / запуск
.venv/bin/python app.py --selftest                # smoke test of every weapon through the UI / проверка всех оружий через интерфейс
.venv/bin/python -m pytest                        # tests / тесты (every weapon is checked)
.venv/bin/python -m pyflakes *.py tests           # Python 3.11+; only the two QtWebEngineWidgets imports may be reported
```

`--selftest` prints its report and the path of `selftest.log`, which it writes to a new temporary folder (never into the app's folder or your settings). The tests use their own temporary settings and cache folders, never `~/.config` or `~/.cache`, and the embedded map refuses every network request during the tests. The X11 tests run Xvfb and xcompmgr when they are installed. / `--selftest` печатает отчёт и путь к `selftest.log` во временной папке (не в папке программы и не в настройках). Тесты работают со своими временными папками настроек и кэша, не трогая `~/.config` и `~/.cache`, а встроенная карта во время тестов отклоняет все сетевые запросы. Тесты X11 используют Xvfb и xcompmgr, если они установлены.

Every push runs the tests on GitHub Actions (**tests**, Ubuntu 24.04, Python 3.10 and 3.12) with exactly the versions in `requirements-dev.txt`, PyQt6-WebEngine included; the run fails on any pyflakes report other than the two deliberate imports and on any skipped test other than the two that need a writable `/dev/uinput`. A release is a tag `v<version>` on the default branch with its entry in [RELEASE_NOTES.md](RELEASE_NOTES.md); the version is `APP_VERSION` in `config.py` ([RELEASING.md](RELEASING.md)). / Каждый push запускает тесты в GitHub Actions (**tests**, Ubuntu 24.04, Python 3.10 и 3.12). Выпуск — тег `v<версия>` на основной ветке и запись в RELEASE_NOTES.md; версия — `APP_VERSION` в `config.py`.

| What / Что | Where / Где |
|------------|-------------|
| Settings / настройки (`config.json`, an unreadable one kept as `config.json.bad`), `crash.log` (moved to `crash.log.1` past 256 KB), `sight-grab.png`, `instance.lock`; the folder is private (0700), `config.json` and `crash.log` too (0600) / папка и файлы закрыты от других пользователей | `~/.config/SquadBallistics` (`$XDG_CONFIG_HOME`) |
| Map cache, SquadCalc settings / кэш карты | `~/.cache/SquadBallistics` (`$XDG_CACHE_HOME`) |

The old `configs/config.json` of versions ≤ 1.1.0 (relative to the working directory) is migrated automatically. / Старый `configs/config.json` версий ≤ 1.1.0 переносится автоматически.

`assets/fonts/RobotoCondensed-Digits.ttf` is the digits of Roboto Condensed (© The Roboto Project Authors), used by the sight reader, under the SIL Open Font License 1.1 (`assets/fonts/RobotoCondensed-OFL.txt`). / Цифры шрифта Roboto Condensed для чтения прицела, лицензия SIL OFL 1.1.

The sidebar icons in `assets/icons/` (bullseye, crosshairs, sliders-h, map) are Font Awesome Free 5.15.4 icons by Fonticons, Inc. (https://fontawesome.com), under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); the attribution is in each file. They are only tinted. / Иконки боковой панели — Font Awesome Free 5.15.4, лицензия CC BY 4.0, только перекрашены.
