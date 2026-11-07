# Данные прицела стационарного и машинного оружия

У каких стационарных (станок, открытая башня) и машинных (закрытая башня, орудие корпуса, установка на машине) оружий из `weapons.json` есть три данные прицела, от которых зависит метка оверлея, и почему у остальных их нет. Ручные гранатомёты и подствольники (26 записей) вне списка: файлы игры не дают их прицел, угол 0 и кратность 1 у них допущение (`bore_assumed`, `zoom_assumed` в `tests/data/game_weapons.json`). В списке 78 оружий, все остальные записи; `tests/test_sight_data.py` проверяет, что обе таблицы совпадают с `weapons.json` и что у каждого недостающего есть причина.

- **Угол канала** (градусы): на сколько выстрел уходит выше центра вида. `-` значит 0: применять нечего.
- **Кратность**: делитель FOV игры в прицеле. `-` значит, вид сохраняет FOV игры.
- **Точка вылета** (`launch_height` / `muzzle_forward` / `muzzle_up`, метры): высота оси ствола над землёй и вынос дульного среза вдоль ствола и над осью, то есть где выстрел начинается относительно глаза. `-` значит, выстрел начинается от земли у оси.
- **Смещение камеры (параллакс)**: ни у одного оружия его нет. Модель ставит камеру в ось ствола. Измерено только смещение QLZ87 в обычном виде (на 0,23 м выше и 0,34 м правее оси, это -8,5 / -5,6 / -4,2 м дальности на 200 / 300 / 400 м; см. `docs/aiming.ru.md`); места остальных камер файлы игры не дают, поэтому оно не применяется.

## Оружия и их данные

| Оружие | Угол, град | Кратность | Точка вылета, м |
|---|---|---|---|
| MK19 | - | - | - |
| MK19 · AAVP-7A1 | - | - | 3.2232 / 1.0868 / 0.0748 |
| MK19 · PARS III RWS | 0.95 | - | 2.6617 / 0.4161 / 0.0257 |
| MK19 · TAPV C16 RWS | 1.55 | - | 3.093 / 0.6256 / -0.0155 |
| MK19 · M113 open turret | 1.6 | - | 2.6316 / 0.6951 / -0.0087 |
| MK19 · M113 open turret · no sights | - | - | 2.6316 / 0.6951 / -0.0087 |
| MK19 · M1151 open turret | 1.7211 | - | 2.3056 / 0.6951 / -0.0087 |
| MK19 · M1151 open turret · no sights | - | - | 2.3056 / 0.6951 / -0.0087 |
| MK19 · MATV open turret | 1.7211 | - | 3.0282 / 0.6951 / -0.0087 |
| MK19 · MATV open turret · no sights | - | - | 3.0282 / 0.6951 / -0.0087 |
| MK19 · RHIB open turret | 1.7286 | - | - |
| MK19 · emplacement / C16 / L134A1 | 1.674 | - | - |
| MK19 · emplacement / C16 / L134A1 · no sights | - | - | - |
| AGS-17 · emplacement · optic (RMB ×2.5) | 0.85 | 2.5 | 1 / 0 / 0 |
| AGS-17 · emplacement · no optic | 0.85 | - | 1 / 0 / 0 |
| AGS-17 · iron sights emplacement | 4.5 | - | 1 / 0 / 0 |
| AGS-17 · Technical | 4.5 | - | 2.2118 / 0.87 / 0.068 |
| AGS-17 · Tigr | 4.5 | - | 2.5927 / 0.87 / 0.068 |
| AGS-17 · Safir | 4.5 | - | 1.7967 / 0.87 / 0.068 |
| AGS-17 · M1151 | 4.5 | - | 2.2891 / 0.87 / 0.068 |
| AGS-17 · BTR-D | 4.5 | - | 2.2635 / 0.87 / 0.068 |
| QLZ87 · optic (RMB ×3) | 0.774 | 3 | - |
| QLZ87 · no optic | -0.9 | - | - |
| QLZ87 · Lynx · optic (RMB ×3) | 0.85 | 3 | - |
| QLZ87 · Lynx · no optic | 0.85 | - | - |
| QLZ87 · CSK131 / WZ551 · optic (RMB ×3) | 0.85 | 3 | - |
| QLZ87 · CSK131 / WZ551 · no optic | 0.85 | - | - |
| QLZ87 · ZBL08 · optic (RMB ×3) | 0.85 | 3 | - |
| QLZ87 · ZBL08 · no optic | 0.85 | - | - |
| QLZ87 · bunker tripod · optic (RMB ×3) | 0.774 | 3 | - |
| QLZ87 · bunker tripod · no optic | -0.9 | - | - |
| AGS-30 / BTR-4 AGS | 1.6 | 3 | - |
| AGS-30 (BMP-1TS) | 1.55 | 3 | - |
| AGS-30 (BMP-2M) | 1.55 | 1.5 | - |
| SPG-9 · HEAT | 0.13 | - | - |
| SPG-9 · HEAT · scope · optic (RMB ×4) | 2.34 | 4 | - |
| SPG-9 · HEAT · scope · no optic | 2.34 | - | - |
| SPG-9 · FRAG | 0.13 | - | - |
| SPG-9 · FRAG · scope · optic (RMB ×4) | 2.34 | 4 | - |
| SPG-9 · FRAG · scope · no optic | 2.34 | - | - |
| SPG-9 · HEAT · technical · optic (RMB ×4) | 2.34 | 4 | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · technical · no optic | 2.34 | - | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · technical · optic (RMB ×4) | 2.34 | 4 | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · technical · no optic | 2.34 | - | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · INS armoured technical · optic (RMB ×4) | 2.34 | 4 | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · INS armoured technical · no optic | 2.34 | - | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · INS armoured technical · optic (RMB ×4) | 2.34 | 4 | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · INS armoured technical · no optic | 2.34 | - | 2.3252 / 1.7773 / 0.0546 |
| 2A28 Grom (BMP-1 / BMD-1) · HEAT | 1.4 | 1.5 | - |
| 2A28 Grom (BMD-1M) · HEAT | 1.57 | 1.5 | - |
| 2A28 Grom (BMP-1 / BMD-1) · FRAG | 1.4 | 1.5 | - |
| 2A28 Grom (BMD-1M) · FRAG | 1.57 | 1.5 | - |
| 2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG | 0.58 | 2.5 | - |
| 2A70 100mm (ZBD-04A) · FRAG | 0.95 | 2.5 | - |
| 2A70 100mm (BMD-4M) · FRAG | 0.57 | 2.5 | - |
| ZiS-3 · optic (RMB ×4) | 0.4 | 4 | - |
| ZiS-3 · no optic | 0.4 | - | - |
| Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3 | 0.28 | 4 | - |
| Tank AP · T-62 (2A20) | 0.05 | 3.5 | - |
| Tank AP · T-64BM2 (KBA3) | 0.29 | 2.7 | - |
| Tank AP · ZTZ-99 (ZPT-98) | 0.1 | 4 | - |
| Tank AP · M256 / Rh120 | 0.31 | 3 | - |
| Tank AP · Leopard 2A6 (Rh120) | 0.25 | 3 | - |
| Tank AP · M60T (MG253) | 0.5 | - | - |
| Tank AP · L30A1 (Challenger 2) / M68A2 | 0.31 | 1.5 | - |
| Tank AP · M1128 MGS (M68A2) | 0.6 | 3 | - |
| Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2 | 0.28 | 4 | - |
| Tank HEAT/HE · M1A1 / M1A2 (M256) | 0.31 | 3 | - |
| Tank HEAT/HE · Leopard 2A6 (Rh120) | 0.25 | 3 | - |
| Tank HEAT/HE · M1128 MGS (M68A2) | 0.6 | 3 | - |
| Tank HEAT/HE · M60T (MG253) | 0.5 | - | - |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) | 0.1 | 4 | - |
| Tank HEAT/HE · T-62 (2A20) | 0.05 | 3.5 | - |
| Tank HEAT/HE · T-64BM2 (KBA3) | 0.29 | 2.7 | - |
| Tank HESH · L30A1 (Challenger 2) | 0.31 | 1.5 | - |
| ZPL-98A 105mm (ZTD-05) · AP | 0.02 | 3.5 | - |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE | 0.02 | 3.5 | - |
| MK19 · AAVP-7A1 · gunner sight ×4.5 | - | 4.5 | 3.2232 / 1.0868 / 0.0748 |
| MK19 · PARS III RWS · gunner sight ×3 | 0.95 | 3 | 2.6617 / 0.4161 / 0.0257 |
| MK19 · PARS III RWS · gunner sight ×9 | 0.95 | 9 | 2.6617 / 0.4161 / 0.0257 |
| MK19 · TAPV C16 RWS · gunner sight ×5 | 1.55 | 5 | 3.093 / 0.6256 / -0.0155 |
| MK19 · TAPV C16 RWS · gunner sight ×12 | 1.55 | 12 | 3.093 / 0.6256 / -0.0155 |
| MK19 · RHIB open turret · no sights | - | - | - |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×6 | 0.31 | 6 | - |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×12 | 0.31 | 12 | - |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×6 | 0.31 | 6 | - |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×12 | 0.31 | 12 | - |
| 2A28 Grom (BMD-1M) · HEAT · gunner sight ×6 | 1.57 | 6 | - |
| 2A28 Grom (BMD-1M) · FRAG · gunner sight ×6 | 1.57 | 6 | - |
| 2A70 100mm (BMD-4M) · FRAG · gunner sight ×5 | 0.575 | 5 | - |
| 2A70 100mm (BMP-3 / BMD-4M) · FRAG · gunner sight ×14 | 0.575 | 14 | - |
| 2A28 Grom (BMP-1) · HEAT · gunner sight ×6 | 1.4 | 6 | - |
| 2A28 Grom (BMP-1) · FRAG · gunner sight ×6 | 1.4 | 6 | - |
| AGS-30 (BMP-2M) · gunner sight ×6 | 1.55 | 6 | - |
| 2A70 100mm (BMP-3) · FRAG · gunner sight ×4 | 0.575 | 4 | - |
| AGS-30 (BMP-1TS) · gunner sight ×9 | 1.55 | 9 | - |
| AGS-30 / BTR-4 AGS · gunner sight ×9 | 1.6 | 9 | - |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×4 | 0.31 | 4 | - |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×10 | 0.31 | 10 | - |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×4 | 0.31 | 4 | - |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×10 | 0.31 | 10 | - |
| Tank AP · Leopard 2A6 (Rh120) · gunner sight ×12 | 0.25 | 12 | - |
| Tank HEAT/HE · Leopard 2A6 (Rh120) · gunner sight ×12 | 0.25 | 12 | - |
| MK19 · M1117 · gunner sight ×4.5 | - | 4.5 | - |
| Tank AP · M1128 MGS (M68A2) · gunner sight ×8 | 0.6 | 8 | - |
| Tank HEAT/HE · M1128 MGS (M68A2) · gunner sight ×8 | 0.6 | 8 | - |
| Tank AP · M60T (MG253) · gunner sight ×3 | 0.5 | 3 | - |
| Tank AP · M60T (MG253) · gunner sight ×8 | 0.5 | 8 | - |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×3 | 0.5 | 3 | - |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×8 | 0.5 | 8 | - |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×4 | 0.29 | 4 | - |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×12 | 0.29 | 12 | - |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×4 | 0.29 | 4 | - |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×12 | 0.29 | 12 | - |
| Tank AP · T-62 (2A20) · gunner sight ×7 | 0.05 | 7 | - |
| Tank HEAT/HE · T-62 (2A20) · gunner sight ×7 | 0.05 | 7 | - |
| Tank AP · T-64BM2 (KBA3) · gunner sight ×12 | 0.29 | 12 | - |
| Tank HEAT/HE · T-64BM2 (KBA3) · gunner sight ×12 | 0.29 | 12 | - |
| Tank AP · T-72 / T-90 (2A46) · gunner sight ×12 | 0.28 | 12 | - |
| Tank HEAT/HE · T-72 / T-90 (2A46) · gunner sight ×12 | 0.28 | 12 | - |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×4 | 0.95 | 4 | - |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×14 | 0.95 | 14 | - |
| ZPL-98A 105mm (ZTD-05) · AP · gunner sight ×7 | 0.02 | 7 | - |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE · gunner sight ×7 | 0.02 | 7 | - |
| Tank AP · ZTZ-99 (ZPT-98) · gunner sight ×12 | 0.1 | 12 | - |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) · gunner sight ×12 | 0.1 | 12 | - |
| Mortar (M252 / 2B14 / L16 / Type 63) | - | - | 0.0245 / 1.569 / 0.002 |
| Technical Mortar | - | - | 1.1789 / 1.6137 / 0.0388 |
| M1064 M121 (120mm) | - | - | 0.8174 / 3.4618 / 0.0035 |
| Hell Cannon | - | - | 0.155 / 2.373 / 0.002 |
| UB-32 (S-5 rockets) | - | - | 1.3075 / 1.43 / 0.251 |
| Technical UB-32 | - | - | 2.2659 / 1.4303 / 0.2513 |
| BM-21 Grad | - | - | 1.7694 / 2.7346 / 0.6366 |

## Чего нет и почему

В столбце «Нет» стоит `bore`, `zoom` или `launch`.

| Оружие | Нет | Причина |
|---|---|---|
| MK19 | bore | прицел наводчика выровнен со стволом (файлы игры: угол 0,0), применять нечего |
| MK19 | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 | launch | по файлам башня висит на гнезде на 1,2 м ниже башенной кости корпуса, а меш прицела на 2,6 м: ось поворота неоднозначна и не извлечена (tools/game_weapons.py) |
| MK19 · AAVP-7A1 | bore | прицел наводчика выровнен со стволом (файлы игры: угол 0,0), применять нечего |
| MK19 · AAVP-7A1 | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · PARS III RWS | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · TAPV C16 RWS | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · M113 open turret | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · M113 open turret · no sights | bore | обычный вид: камера на оси оружия (файлы игры: угол 0,0), выстрел идёт по центру вида |
| MK19 · M113 open turret · no sights | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · M1151 open turret | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · M1151 open turret · no sights | bore | обычный вид: камера на оси оружия (файлы игры: угол 0,0), выстрел идёт по центру вида |
| MK19 · M1151 open turret · no sights | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · MATV open turret | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · MATV open turret · no sights | bore | обычный вид: камера на оси оружия (файлы игры: угол 0,0), выстрел идёт по центру вида |
| MK19 · MATV open turret · no sights | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · RHIB open turret | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · RHIB open turret | launch | у катера нет колёс, он стоит на понтонах, и высоту над землёй файлы не дают (deadline-squad/squad-ballistics#12) |
| MK19 · emplacement / C16 / L134A1 | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · emplacement / C16 / L134A1 | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| MK19 · emplacement / C16 / L134A1 · no sights | bore | обычный вид: камера на оси оружия (файлы игры: угол 0,0), выстрел идёт по центру вида |
| MK19 · emplacement / C16 / L134A1 · no sights | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · emplacement / C16 / L134A1 · no sights | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-17 · emplacement · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · iron sights emplacement | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · Technical | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · Tigr | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · Safir | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · M1151 | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| AGS-17 · BTR-D | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · optic (RMB ×3) | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · no optic | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · Lynx · optic (RMB ×3) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · Lynx · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · Lynx · no optic | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · CSK131 / WZ551 · optic (RMB ×3) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · CSK131 / WZ551 · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · CSK131 / WZ551 · no optic | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · ZBL08 · optic (RMB ×3) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · ZBL08 · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · ZBL08 · no optic | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · bunker tripod · optic (RMB ×3) | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| QLZ87 · bunker tripod · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| QLZ87 · bunker tripod · no optic | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 / BTR-4 AGS | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 (BMP-1TS) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 (BMP-2M) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · HEAT | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · HEAT | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · HEAT · scope · optic (RMB ×4) | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · HEAT · scope · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · HEAT · scope · no optic | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · FRAG | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · FRAG | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · FRAG · scope · optic (RMB ×4) | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · FRAG · scope · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · FRAG · scope · no optic | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| SPG-9 · HEAT · technical · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · FRAG · technical · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · HEAT · INS armoured technical · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| SPG-9 · FRAG · INS armoured technical · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| 2A28 Grom (BMP-1 / BMD-1) · HEAT | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMD-1M) · HEAT | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMP-1 / BMD-1) · FRAG | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMD-1M) · FRAG | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (ZBD-04A) · FRAG | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (BMD-4M) · FRAG | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZiS-3 · optic (RMB ×4) | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZiS-3 · no optic | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| ZiS-3 · no optic | launch | у станка нет гнезда на машине в файлах игры, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · T-62 (2A20) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · T-64BM2 (KBA3) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · ZTZ-99 (ZPT-98) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M256 / Rh120 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Leopard 2A6 (Rh120) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M60T (MG253) | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| Tank AP · M60T (MG253) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · L30A1 (Challenger 2) / M68A2 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M1128 MGS (M68A2) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M1A1 / M1A2 (M256) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · Leopard 2A6 (Rh120) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M1128 MGS (M68A2) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M60T (MG253) | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| Tank HEAT/HE · M60T (MG253) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · T-62 (2A20) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · T-64BM2 (KBA3) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HESH · L30A1 (Challenger 2) | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · AP | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| MK19 · AAVP-7A1 · gunner sight ×4.5 | bore | прицел наводчика выровнен со стволом (файлы игры: угол 0,0), применять нечего |
| MK19 · RHIB open turret · no sights | bore | обычный вид: камера на оси оружия (файлы игры: угол 0,0), выстрел идёт по центру вида |
| MK19 · RHIB open turret · no sights | zoom | вид не увеличивает (файлы игры: кратность x1, остаётся FOV игры) |
| MK19 · RHIB open turret · no sights | launch | у катера нет колёс, он стоит на понтонах, и высоту над землёй файлы не дают (deadline-squad/squad-ballistics#12) |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMD-1M) · HEAT · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMD-1M) · FRAG · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (BMD-4M) · FRAG · gunner sight ×5 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (BMP-3 / BMD-4M) · FRAG · gunner sight ×14 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMP-1) · HEAT · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A28 Grom (BMP-1) · FRAG · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 (BMP-2M) · gunner sight ×6 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (BMP-3) · FRAG · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 (BMP-1TS) · gunner sight ×9 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| AGS-30 / BTR-4 AGS · gunner sight ×9 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×10 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×10 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Leopard 2A6 (Rh120) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · Leopard 2A6 (Rh120) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| MK19 · M1117 · gunner sight ×4.5 | bore | прицел наводчика выровнен со стволом (файлы игры: угол 0,0), применять нечего |
| MK19 · M1117 · gunner sight ×4.5 | launch | по файлам башня висит на гнезде на 1,2 м ниже башенной кости корпуса, а меш прицела на 2,6 м: ось поворота неоднозначна и не извлечена (tools/game_weapons.py) |
| Tank AP · M1128 MGS (M68A2) · gunner sight ×8 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M1128 MGS (M68A2) · gunner sight ×8 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M60T (MG253) · gunner sight ×3 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · M60T (MG253) · gunner sight ×8 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×3 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×8 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · T-62 (2A20) · gunner sight ×7 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · T-62 (2A20) · gunner sight ×7 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · T-64BM2 (KBA3) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · T-64BM2 (KBA3) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · T-72 / T-90 (2A46) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · T-72 / T-90 (2A46) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×4 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×14 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · AP · gunner sight ×7 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE · gunner sight ×7 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank AP · ZTZ-99 (ZPT-98) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) · gunner sight ×12 | launch | у закрытой башни или орудия корпуса нет записи гнезда на машине, tools/game_weapons.py не выводит точку вылета; выстрел идёт от земли (launch_height 0) |
| Mortar (M252 / 2B14 / L16 / Type 63) | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| Mortar (M252 / 2B14 / L16 / Type 63) | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| Technical Mortar | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| Technical Mortar | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| M1064 M121 (120mm) | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| M1064 M121 (120mm) | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| Hell Cannon | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| Hell Cannon | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| UB-32 (S-5 rockets) | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| UB-32 (S-5 rockets) | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| Technical UB-32 | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| Technical UB-32 | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |
| BM-21 Grad | bore | наводится собственной шкалой возвышения, а не через вид: в файлах игры угла канала нет |
| BM-21 Grad | zoom | наводится собственной шкалой возвышения, а не через вид: в файлах игры кратности нет |

Итого: угол канала есть у 65 из 78 оружий, кратность у 38, точка вылета у 32; без угла 13, без кратности 40, без точки вылета 46.

## Метки сеток прицелов игры

Аудит 2026-11-06 по клиенту Squad (сборка 26234431; данные оружия выше взяты из серверного пакета, сборка 26005357). Игра печатает собственные метки дальности на текстуре прицела, оверлей рисует свою метку. Таблица сравнивает их для четырёх оптик, метки которых удалось считать; её фиксирует `tests/test_reticle_parity.py`. Текстуры в репозитории не хранятся.

**Как получены смещения.** Виджет (`W_QLZ87_YMA-87-35_Reticle`, `SPG9_HEAT_Reticle`, `SPG9_Frag_Reticle`, `W_ZiS3_Reticle`, `PAG-17_Reticle_Widget`) — картинка по центру экрана; её размер на экране при 1080p равен размеру слота, умноженному на масштаб отрисовки (QLZ87 1000 px; SPG-9 1200 x 1.5 = 1800 px; ZiS-3 приближённая картинка 1285 px; PAG-17 1200 x 1071.7 px, неравномерное растяжение текстуры 2048 x 2048); масштаб интерфейса принят равным 1 при 1080p (виджеты разложены под 1080, кривой DPI в файлах нет). Строка метки берётся из пикселей текстуры (нулевой мип; центр штриха у QLZ87, вершина `^` у шевронов, то есть примерно +-4 текселя = +-3 px). Смещение = (строка - 1024) x px на тексель, плюс — ниже центра. Смещение оверлея — `mark_offset` при FOV 90 (вид FOV 90 / кратность), ширина 1920 px, ровная земля; последние два столбца — разность и расстояние, на которое метке оверлея надо сместиться, чтобы лечь на метку игры.

| Сетка (вид оружия) | Метка | Строка текстуры | Смещение игры, px | Смещение оверлея, px | Игра - оверлей, px | Разность по дальности, м |
|---|---|---|---|---|---|---|
| QLZ87 optic | 100 м (подпись 1) | 1040.5 | +8.1 | +0.2 | +7.8 | +16 |
| QLZ87 optic | 200 м (подпись 2) | 1131 | +52.2 | +48.9 | +3.3 | +7 |
| QLZ87 optic | 300 м (подпись 3) | 1229 | +100.1 | +97.7 | +2.4 | +5 |
| QLZ87 optic | 400 м (подпись 4) | 1329.5 | +149.2 | +146.6 | +2.6 | +5 |
| QLZ87 optic | 500 м (подпись 5) | 1428.5 | +197.5 | +195.7 | +1.8 | +4 |
| SPG-9 HEAT, red scale | 200 м (подпись 2) | 862 | -142.4 | -146.7 | +4.3 | +17 |
| SPG-9 HEAT, red scale | 400 м (подпись 4) | 908 | -102.0 | -94.9 | -7.1 | -27 |
| SPG-9 HEAT, red scale | 600 м (подпись 6) | 973 | -44.8 | -42.9 | -1.9 | -7 |
| SPG-9 HEAT, red scale | 800 м (подпись 8) | 1031 | +6.2 | +9.1 | -3.0 | -11 |
| SPG-9 HEAT, red scale | 1000 м (подпись 10) | 1090 | +58.0 | +61.2 | -3.2 | -12 |
| SPG-9 HEAT, red scale | 1200 м (подпись 12) | 1159 | +118.7 | +113.3 | +5.3 | +20 |
| SPG-9 FRAG, green scale | 200 м (подпись 2) | 908 | -102.0 | -108.5 | +6.6 | +15 |
| SPG-9 FRAG, green scale | 400 м (подпись 4) | 1008 | -14.1 | -18.3 | +4.2 | +9 |
| SPG-9 FRAG, green scale | 600 м (подпись 6) | 1114 | +79.1 | +72.3 | +6.8 | +15 |
| SPG-9 FRAG, green scale | 800 м (подпись 8) | 1220 | +172.3 | +163.1 | +9.2 | +20 |
| SPG-9 FRAG, green scale | 1000 м (подпись 10) | 1323 | +262.8 | +254.2 | +8.6 | +19 |
| SPG-9 FRAG, green scale | 1200 м (подпись 12) | 1427 | +354.2 | +345.8 | +8.4 | +18 |
| ZiS-3 optic | 400 м (подпись 4) | 1049 | +15.7 | +4.9 | +10.8 | +112 |
| ZiS-3 optic | 700 м (подпись 7) | 1083 | +37.0 | +33.9 | +3.1 | +32 |
| ZiS-3 optic | 900 м (подпись 9) | 1112 | +55.2 | +53.2 | +2.0 | +21 |
| ZiS-3 optic | 1100 м (подпись 11) | 1147 | +77.2 | +72.5 | +4.7 | +48 |
| ZiS-3 optic | 1300 м (подпись 13) | 1175 | +94.7 | +91.9 | +2.9 | +30 |
| ZiS-3 optic | 1500 м (подпись 15) | 1208 | +115.4 | +111.2 | +4.2 | +44 |
| ZiS-3 optic | 1700 м (подпись 17) | 1242 | +136.8 | +130.6 | +6.2 | +64 |
| ZiS-3 optic | 1900 м (подпись 19) | 1275 | +157.5 | +149.9 | +7.6 | +78 |
| ZiS-3 optic | 2100 м (подпись 21) | 1307 | +177.6 | +169.3 | +8.2 | +85 |
| AGS-17 PAG-17 optic | 100 м (подпись 1) | 1106 | +42.9 | +32.3 | +10.6 | +14 |
| AGS-17 PAG-17 optic | 200 м (подпись 2) | 1219 | +102.0 | +108.7 | -6.7 | -9 |
| AGS-17 PAG-17 optic | 300 м (подпись 3) | 1349 | +170.1 | +185.7 | -15.6 | -20 |
| AGS-17 PAG-17 optic | 400 м (подпись 4) | 1489 | +243.3 | +263.5 | -20.2 | -26 |
| AGS-17 PAG-17 optic | 500 м (подпись 5) | 1644 | +324.4 | +342.6 | -18.2 | -23 |
| AGS-17 PAG-17 optic | 600 м (подпись 6) | 1778 | +394.6 | +423.4 | -28.8 | -35 |
| AGS-17 PAG-17 optic | 700 м (подпись 7) | 1925 | +471.5 | +506.2 | -34.7 | -42 |

Подгонка меток каждой сетки к физике оверлея (один масштаб, МНК по tan угла): QLZ87 3639 px/рад против 3583 при FOV 90 / 3, расчётный FOV 88.7; SPG-9 HEAT 4875 (89.1), SPG-9 FRAG 4959 (87.7), ZiS-3 5056 (86.0) против 4826 при FOV 90 / 4; оптика AGS-17 2758 против 2955 (96.0). Сетки нарисованы под FOV 90 по умолчанию и при нём совпадают с баллистикой оверлея. В коде виджетов (`ExecuteUbergraph`, `Tick`) нет FOV, слоты картинок — фиксированные размеры в пикселях, поэтому другой FOV меняет масштаб мира, но не сетки: напечатанные метки тогда расходятся с метками оверлея (нативный `SQVehicleViewWidget` здесь не читается, поэтому «сетка никогда не масштабируется по FOV» — гипотеза; совпадение QLZ87 и SPG-9 при FOV 90 без коэффициента её поддерживает).

**Какая картинка видна.** QLZ87 и SPG-9 — станковые: они открывают виджет через `TryVehicleCreateOverlay(ReticleClass)` и не меняют `CurrentZoomIndex` (0), поэтому видна картинка «Unzoomed» (QLZ87 1000 px, SPG-9 1800 px); «Zoomed» (1085 px, `Collapsed`, у QLZ87 текстура ACOG от M2) — остаток. Числа это подтверждают: наклон QLZ87 при FOV 90 в пределах 1.6 % при 1000 px и разошёлся бы на 10 % при 1085 px. Прицел ZiS-3 переключается кратностью башни (`ZoomLevels[1]`), подходит приближённая картинка (1285 px; 880 px дала бы недобор 31 %).

**FOV приближённого вида.** `BlueprintOnZoom` у `BP_QLZ87_Weapon` ставит камере `FirstPersonDriverCamera` значение `GameUserSettings.FOV / 3` и возвращает `FOV` при отпускании; SPG-9, AGS-17 и остальные делают тот же вызов со своим делителем (`tools/game_weapons.py`). Значит FOV вида следует настройке делением, как и предполагает оверлей. Перелёт QLZ87, измеренный владельцем (около 300 м на 1000 м, FOV 120): сетка доходит только до 500 м и 1000 м показать не может, а метка оверлея строится из того же FOV / 3, что ставит игра. При 120 метка сетки 500 м стоит на 197.5 px ниже центра, а точка мира 500 м — на 144 px, поэтому игрок, накладывающий напечатанные метки при FOV 120, перелетает (метка 500 м ложится около 650 м); это проверенное следствие сетки фиксированного размера при FOV 120. Перелёт собственной метки оверлея это не объясняет. Перелёт 300 м на 1000 м требовал бы реального FOV вида около 52 градусов, а не 40 (подгонка: 328.6 px метки на 1000 м — это цель на 1300 м при 52.4 градусах); в файлах такого значения нет (гипотеза, не проверена; ограничение в нативном коде, иной смысл настройки FOV или баллистика дальше 500 м дали бы это, разделить их может только замер в игре при FOV 90 и 120).

**ADS FOV ручных (задача 17).** Не решено: ручные пусковые и их виджеты вне этого аудита, их `SeparateAdsFov` читает нативный код.

**Не охвачено.** Прицелы наводчика танков и БМП (T-72A/AV/B3, T-90A, T-64BM2, T-62, M1A1/M1A2, M1128, M60T, Leopard 2A6, FV4034, ZTZ-99, ZTD-05, БМП-1/-2M/-3M, BMD-1M/-4M, ZBD-04A, BMP-1TS, BTR-4, AAVP-7A1, M1117) не считаны: каждая текстура — разноцветный лист из нескольких шкал (у T-72B3: зелёная и синяя шкалы шевронов, голубая стадиометрическая), а файлы не говорят, какая шкала к какому боеприпасу (материалы AP, HEAT и FCS одной машины указывают на одну текстуру без параметра выбора шкалы; граф материала `M_LightBleedMaster` вырезан), поэтому метку нельзя связать с видом оружия, не подставляя ответ. Уровни приближения тоже используют одну текстуру на 3x, 6x и 13x (Abrams) без смены масштаба в коде виджета. У MK19 и видов без приближения калиброванных меток нет. Горизонтальная шкала QLZ87 (0-60, штрихи по 5) — не угловая шкала прицела (187 текселей на 10 единиц — 25 мрад при найденном масштабе), а непомеченный длинный штрих под первой меткой в строке 1072.5 подписи не имеет; их не сравнивали.
