# Aiming guide: Squad Ballistics and the Deadline SquadCalc

How to get the best accuracy out of the overlay mark, the range ladder and the SquadCalc map, weapon by weapon. Russian version: [aiming.ru.md](aiming.ru.md).

Scope: Linux, X11 or XWayland, a 16:9 screen (1920x1080 or 2560x1440), the game's FOV 120, flat ground unless a section says otherwise. The mark is a thin red cross, 50 px across and 1 px thick (it has no style, colour or size settings); *Align with the sight* and the range ladder stay. The mouse side button **Mouse4**, which switches the selected weapon between its `· optic (RMB ×N)` and `· no optic` entry, (default key; Settings → hotkeys) is on `dev`.

## How to read this guide

Every number has a source tag. **V** = verified: read in code or game data, or reproduced by a test or script. **C** = computed by a one-off script from V inputs (the model is written out in section 5; the script is not in the repository). **A** = assumed or inferred; the test that settles it is named. Where the game's behaviour is unknown the text says "unknown, test X".

| Tag | Source |
|---|---|
| `B` | `ballistics.py` (`mark_offset`, `mark_resolution`, `mark_visible_range`, `range_ladder`) |
| `Cr` / `Cf` | `crosshair.py` (`marker_notes`, how-to steps) / `config.py` |
| `README` / `RN` | `README.md` / `RELEASE_NOTES.md` (1.6.0) |
| `T-aids`, `T-e2e` | `tests/test_marker_aids.py`, `tests/test_mark_end_to_end.py` (independent oracle `tests/flight.py`) |
| `#6-n`, `#5`, `#8` | `deadline-squad/squad-ballistics` issue #6 research comment n of 6, issue #5, issue #8 |
| `NR` | `/tmp/native/report.md` (decompiled server binary, build 26005357, addresses in the file) |
| `GD` | game-data dumps: `/tmp/mech/ini/*` (input config), `/tmp/mech/vdump2/*` (vehicle blueprints), `~/data/squad-weapons/*` (weapon blueprints and `resolved.json`), `~/data/squad-extract/mortar-ui/*`, `/tmp/native/dis/*` (UI disassembly); decompiled input modifiers in `/tmp/aimwork/gamedata/gh/out/dec/` |
| `SC` | Deadline SquadCalc `~/agl/SquadCalc` (dev `cf636f7f8`, v45.15.0) |

## 1. The ten rules

1. **Two kinds of weapon, two kinds of precision.** A *splash* weapon (grenade launchers, MK19, AGS-17/30, QLZ87, SPG-9 FRAG, Grom FRAG) is hit or missed by the *ground range* of the burst, so "1 px = N m of range" is the number that matters. A *direct-hit* weapon (HEAT/AP rounds: RPG-7, PF98, AT-4, SMAW, MAAWS, Carl Gustav, SPG-9 HEAT, tank and ZiS-3 guns) is hit or missed by the *height at the target*; there one pixel is worth `N m x tan(descent angle)`, i.e. 0.1-1.8 m at 300-1000 m (section 5.2), not tens of metres. Do not read "1 px = 39 m" on a tank gun as a failure. `C`
2. **Marker aiming is honest for:** AGS-17 optic, AGS-30 (BTR-4, BMP-1TS) and QLZ87 optic (1.3-2.8 m per pixel at FOV 120), SPG-9 scope (5.2 m, but a direct hit weapon so the vertical error is 0.1-0.3 m), and every direct-hit weapon in the table above if the aim point is raised to the target's middle. The unzoomed splash views (MK19 19-20 m/px, QLZ87 *no optic* 13 m/px, AGS-17 *no optic* 5-7 m/px) can be put on the ground marker, but one pixel already costs more than the burst radius: use them only for area fire. `V` (resolution) / `C` (verdict)
3. **The mark's centre can be placed to a fraction of a pixel; your hand cannot.** The cross is drawn at its float position, centre error 0.02 px (`T-aids`, `T-e2e`). The limit is the mouse step (section 3) and your eye: plan for +-1 px, +-0.5 px at best.
4. **Lower the in-game mouse sensitivity for the aiming views.** With the Global slider times the per-zoom slider equal to 1, one mouse count is 2.3 px unzoomed and 3.5-3.7 px in the optics (section 3.2), i.e. 3.5 px x 1.7 m = 6 m of range per count on the AGS-17 optic. Aim for at most 1 px per count (the product of the sliders about 0.25 at 1080p). `A` (the engine constant 0.07 behind this is not confirmed, test 7.6)
5. **The position error that counts in marker mode is the range error** (your position and the target position clicked on the map: sigma = sqrt(2) x the error of one click). Bearing does not matter, the marker supplies it. Place both points at map zoom 6 or deeper (0.25 m per screen pixel on a 4 km map) on a landmark visible in the game too. `V`
6. **Raise the aim point for direct-hit weapons.** The in-game marker is a ground trace (terrain, never a roof or tree, `#6-6`), so aiming at it puts half of the shots under a vehicle. Set `target_height` (`config.json`, 0-10 m, no UI yet) to about 1.2 m. At 600 m, with perfect inputs, this lifts the hit chance on a 3.6 x 2.4 m box from about 50 % to 100 % for PF98, AT-4 and SPG-9 scope; with typical errors from 49 % to 71 / 72 / 100 % (section 5.3). `C` / `Cf`
7. **There is nothing to calibrate by shooting.** The app has no trim or other field correction: the FOV comes from the game's settings file and the rest from the game data, so a miss is not entered anywhere. Only *Align with the sight* (where the mark sits on the screen) is yours to set (section 4.3). `Cf`
8. **The marker flash is short.** Beyond 60 m the world icon is fully visible for about 0.5 s only, and at 20 % opacity while you are zoomed (`#6-6`). Pre-turn to the bearing and pre-set the pitch so that the marker appears within 3-5 px of the mark. `V` (file) / `A` (as seen in game: unknown, test 7.1)
9. **Keys are for coarse moves, the mouse is for the last pixel.** A held key turns at a fixed rate with no ramp (tripod MK19/QLZ87/SPG-9: 66 deg/s pitch, 120 deg/s yaw; AGS-17: 9 and 18 deg/s). One frame at 60 fps of the AGS-17 pitch key is 0.15 deg = 5.6 px in its optic. `V` (`NR` 6, `GD`)
10. **Hold Focus (hold breath) on handheld launchers.** The game narrows its FOV to two thirds (`README`); the pixel cost halves at that FOV (section 3.3), but the app reads the FOV from the game's settings file and on handheld launchers does not follow Focus, so its mark is not valid while Focus is held there (on the plain views of open turrets and tripods it does follow the key, section 3.5); the mouse step shrinks with the FOV too. Sway data exists for handheld launchers only, and prone is 4x steadier than standing (12 / 7 / 3 for standing / crouch / prone, units unknown). `V` (data) / `A` (Focus on emplaced weapons: unknown, test 7.4)

## 2. What one pixel is worth (question 1)

### 2.1 Definition and scaling

`mark_resolution` (`B`) takes the elevations that land the shell 1 m either side of the target, puts them on the screen over the line of sight to the target and returns `1 / slope` (metres of range per pixel of the mark's row). It does not depend on the resolution except through the focal length `f = (W/2) / tan(view_FOV/2)`: **the 1440p value is exactly 0.75 times the 1080p value** for every weapon and range (checked over 13 weapons x 4 ranges x 2 resolutions: ratio 0.7500-0.7500; against the independent oracle `tests/flight.py` within 2 % in 100 of 104 cases, worst 3.5 % at 100 m for the PF98 and the T-64BM2 where a finite half-pixel step is coarse; `V`, `T-aids` repeats this for 1080p).

The sight's zoom divides the FOV (`Weapon.sight_view`, `B`), the shot leaves `bore` degrees above the screen centre, and the *Align with the sight* scale `s` (50-150 %, whole percent) multiplies all offsets, so a pixel is worth `m/px / s` (`T-aids`). Rows below are with scale 100 %.

### 2.2 Per weapon and view, FOV 120, flat ground

"–" in a distance column = the weapon does not reach that distance (a 40 mm grenade, 76 m/s, reaches about 590 m). "Off screen past" = the range from which the mark leaves the screen (top and bottom margins of 20 px; `B` `mark_visible_range`, `Cr`); "–" = on screen to the 8000 m search limit (`LADDER_MAX_DISTANCE`, the longest play area of the game; the table was computed with 5000 m, and with 8000 m the mark of 17 entries that show "–" here leaves the screen past 5.1 to 7.9 km, for example RPG-28 6360 m, Carl Gustav FFV441D 6620 m, T-62 AP 6510 m, T-64BM2 HEAT/HE 6120 m; see `sight-scales.md`). `V` (computed with `ballistics.mark_resolution` and `mark_visible_range`, `weapons.json` of `dev` 6e35528).

| Entry (merged when identical) | view FOV | 1080p: m per px at 100 / 300 / 600 / 1000 m | 1440p: same | off screen past (1080p) |
|---|---|---|---|---|
| M203 / M320 / GP-25 / HK79 / SL40 | 120° | 2.1 / 1.7 / – / – | 1.6 / 1.3 / – / – | 590 m (reach) |
| MGL / M32 | 120° | 2.0 / 1.6 / – / – | 1.5 / 1.2 / – / – | 570 m (reach) |
| AK-40GL (MPT-76) | 120° | 1.7 / 1.3 / – / – | 1.3 / 1.0 / – / – | 500 m (reach) |
| QLG10 | 120° | 2.2 / 1.8 / 0.4 / – | 1.6 / 1.4 / 0.3 / – | 620 m (reach) |
| Rifle grenade | 120° | 2.1 / 1.7 / – / – | 1.6 / 1.3 / – / – | 590 m (reach) |
| MK19 (+1 identical) | 120° | 19 / 19 / 19 / 19 | 15 / 15 / 14 / 14 | – |
| MK19 · TAPV C16 RWS (+2 identical) | 120° | 19 / 19 / 19 / 19 | 15 / 15 / 15 / 14 | – |
| MK19 · emplacement / C16 / L134A1 (+1: *no sights*) | 120° | 20 / 20 / 20 / 20 | 15 / 15 / 15 / 15 | – |
| AGS-17 · emplacement · optic (RMB ×2.5) | 48° | 1.3 / 1.7 / 1.7 / 1.4 | 1.0 / 1.3 / 1.2 / 1.1 | 940 m |
| AGS-17 · emplacement · no optic | 120° | 5.0 / 6.6 / 6.5 / 5.6 | 3.8 / 5.0 / 4.8 / 4.2 | 1940 m |
| AGS-17 · iron sights emplacement | 120° | 5.0 / 6.6 / 6.6 / 5.8 | 3.8 / 5.0 / 4.9 / 4.3 | – |
| QLZ87 · optic (RMB ×3) (Lynx / CSK131 / WZ551 / ZBL-08 identical) | 40° | 2.8 / 2.8 / 2.7 / 2.6 | 2.1 / 2.1 / 2.1 / 2.0 | 1490 m |
| QLZ87 · no optic (Lynx / CSK131 / WZ551 / ZBL-08 identical) | 120° | 13 / 13 / 13 / 12 | 10.0 / 9.9 / 9.7 / 9.4 | 3670 m |
| AGS-30 / BTR-4 AGS and (BMP-1TS) | 40° | 2.8 / 2.8 / 2.7 / 2.7 | 2.1 / 2.1 / 2.1 / 2.0 | 1590 m |
| AGS-30 (BMP-2M) | 80° | 6.4 / 6.4 / 6.3 / 6.1 | 4.8 / 4.8 / 4.8 / 4.6 | 2900 m |
| M72A7 LAW / RPG-26 | 120° | 7.6 / 7.5 / 7.2 / 6.3 | 5.7 / 5.6 / 5.4 / 4.7 | 2110 m |
| AT-4 | 120° | 31 / 31 / 31 / 31 | 23 / 23 / 23 / 23 | – |
| MK153 SMAW | 120° | 18 / 18 / 18 / 17 | 14 / 13 / 13 / 13 | – |
| PF98 · Tandem | 120° | 35 / 36 / 36 / 35 | 26 / 27 / 27 / 27 | – |
| PF98 · HE-I | 120° | 18 / 18 / 18 / 18 | 14 / 13 / 13 / 13 | – |
| RPG-29 | 120° | 30 / 29 / 29 / 29 | 22 / 22 / 22 / 22 | – |
| RPG-7 · PG-7V HEAT / OG-7V (RPG-7V1 identical) | 120° | 12 / 19 / 20 / 20 | 9.0 / 14 / 15 / 15 | – |
| RPG-7 · PG-7VR Tandem | 120° | 2.8 / 2.6 / 1.7 / – | 2.1 / 2.0 / 1.2 / – | 810 m (reach) |
| RPG-7 · TBG-7V Thermobaric | 120° | 7.1 / 8.3 / 8.1 / 7.3 | 5.3 / 6.2 / 6.1 / 5.5 | 2340 m |
| M3 MAAWS · HEAT / Smoke (+1: Tandem) | 120° | 11 / 18 / 19 / 19 | 8.3 / 14 / 14 / 14 | – |
| Carl Gustav M2 · FFV551 HEAT | 120° | 35 / 36 / 35 / 35 | 26 / 27 / 27 / 26 | – |
| Carl Gustav M2 · FFV441D HE | 120° | 24 / 24 / 24 / 24 | 18 / 18 / 18 / 18 | – |
| Carl Gustav M2 · FFV751 Tandem | 120° | 20 / 20 / 20 / 19 | 15 / 15 / 15 / 14 | – |
| SPG-9 · HEAT (and · scope · no optic) | 120° | 34 / 33 / 33 / 33 | 25 / 25 / 25 / 25 | – |
| SPG-9 · HEAT · scope · optic (RMB ×4) | 30° | 5.2 / 5.2 / 5.2 / 5.2 | 3.9 / 3.9 / 3.9 / 3.9 | 3400 m |
| SPG-9 · FRAG (and · scope · no optic) | 120° | 20 / 19 / 19 / 19 | 15 / 14 / 14 / 14 | – |
| SPG-9 · FRAG · scope · optic (RMB ×4) | 30° | 3.1 / 3.0 / 3.0 / 2.9 | 2.3 / 2.2 / 2.2 / 2.2 | 1960 m |
| 2A28 Grom (BMP-1 / BMD-1, BMD-1M) · HEAT | 80° | 16 / 16 / 16 / 16 | 12 / 12 / 12 / 12 | – |
| 2A28 Grom (BMP-1 / BMD-1, BMD-1M) · FRAG | 80° | 9.5 / 9.4 / 9.3 / 9.2 | 7.1 / 7.0 / 7.0 / 6.9 | 4350 m |
| 2A70 100mm (BMP-3 / BMD-4 / ZBD04A / BMD-4M) · FRAG | 48° | 6.0 / 6.0 / 5.9 / 5.9 | 4.5 / 4.5 / 4.4 / 4.4 | 3050 m |
| ZiS-3 · optic (RMB ×4) | 30° | 14 / 14 / 14 / 14 | 10 / 10 / 10 / 10 | – |
| ZiS-3 · no optic | 120° | 90 / 90 / 90 / 90 | 68 / 68 / 68 / 68 | – |
| Tank AP · T-72 (2A46), ZTZ-99 | 30° | 39 / 39 / 39 / 39 | 29 / 29 / 29 / 29 | – |
| Tank AP · T-62 (2A20) | 34.3° | 44 / 44 / 44 / 44 | 33 / 33 / 33 / 33 | – |
| Tank AP · T-64BM2 (KBA3) | 44.4° | 59 / 59 / 59 / 59 | 44 / 44 / 44 / 44 | – |
| Tank AP · M256 / Rh120, Leopard 2A6 | 40° | 45 / 45 / 45 / 45 | 33 / 33 / 33 / 33 | – |
| Tank AP · M1128 MGS (M68A2) | 40° | 70 / 70 / 70 / 70 | 52 / 52 / 52 / 52 | – |
| Tank AP · L30A1 (Challenger 2) / M68A2 | 80° | 161 / 161 / 161 / 161 | 120 / 120 / 120 / 120 | – |
| Tank AP · M60T (MG253) | 120° | 212 / 212 / 212 / 212 | 159 / 159 / 159 / 159 | – |
| Tank HEAT/HE · T-72 (2A46), ZTZ-99 | 30° | 21 / 21 / 21 / 21 | 16 / 15 / 15 / 15 | – |
| Tank HEAT/HE · M1A1 / M1A2 / Leopard 2A6 / M1128 MGS | 40° | 25 / 25 / 25 / 25 | 19 / 19 / 19 / 19 | – |
| Tank HEAT/HE · T-62 (2A20) | 34.3° | 24 / 24 / 24 / 24 | 18 / 18 / 18 / 18 | – |
| Tank HEAT/HE · T-64BM2 (KBA3) | 44.4° | 32 / 31 / 31 / 31 | 24 / 24 / 24 / 24 | – |
| Tank HEAT/HE · M60T (MG253) | 120° | 134 / 133 / 133 / 133 | 101 / 100 / 100 / 100 | – |
| Tank HESH · L30A1 (Challenger 2) | 80° | 40 / 40 / 40 / 40 | 30 / 30 / 30 / 30 | – |
| ZPL-98A 105mm (ZTD-05) · AP | 34.3° | 32 / 32 / 32 / 32 | 24 / 24 / 24 / 24 | – |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE | 34.3° | 17 / 17 / 17 / 17 | 13 / 13 / 13 / 13 | – |

Mortars, the Hell Cannon, rocket artillery and the AGS-17 lob have no mark (laid by angle, section 4.4).

### 2.3 Smallest step, maximum range on screen, ranking

- **Smallest step.** The mark moves in whole screen pixels only in the sense that you can place a marker on it to +-1 px; the mark itself is drawn at its float position (0.02 px). The setting steps are: *Align* offsets 1 px, scale 1 % (at 500 px below the centre that is 5 px). `V` (`Cf` `RANGES`)
- **Maximum range on screen at FOV 120, 1080p.** AGS-17 optic 940 m (1440p: 943 m), QLZ87 optic 1490 m (1502 m), AGS-30 BTR-4 1590 m, SPG-9 FRAG scope 1960 m, SPG-9 HEAT scope 3400 m; unzoomed views stay on screen to their reach or further. Beyond it the info line says "mark off screen past N m" and the edge arrow stays. The limit scales only slightly with the resolution because the screen margin is fixed at 20 px. `V` (`T-aids`: 940 and 1490 against the oracle)
- **Ranking by metres of range per pixel (best first), FOV 120, 600 m** (the under-barrel and rifle grenades are 1.3-2.2 m/px within their 500-620 m reach and are not ranked): AGS-17 optic 1.7 < QLZ87 optic = AGS-30 optic 2.7 < SPG-9 FRAG optic 3.0 < SPG-9 HEAT optic 5.2 < 2A70 FRAG 5.9 < AGS-17 iron / no optic 6.5 < M72 LAW 7.2 < TBG-7V 8.1 < Grom FRAG 9.3 < QLZ87 no optic 13 < ZiS-3 optic 14 < SMAW / PF98 HE-I 18 < RPG-7 / MAAWS 19-20 < MK19 19-20 < Carl Gustav 20-35 < AT-4 31 < SPG-9 open 33 < PF98 Tandem 36 < tank AP 39-212 < ZiS-3 open 90. `V`
- **Which view can honestly be aimed at a marker.** Criterion: a pixel (+-1 px of aim) is worth less than the weapon's own range spread (section 5.3, `sd`) and less than the 5 m that `MARK_PIXEL_LIMIT` (`B`) uses.

| Class | Weapon / view | Verdict |
|---|---|---|
| Marker | AGS-17 optic, AGS-30 BTR-4 / BMP-1TS, QLZ87 optic, QLZ87 on Lynx / CSK131 / WZ551 / ZBL-08 optic, SPG-9 FRAG optic, M203 family, QLG10, PG-7VR | 1.3-3.1 m/px, below the spread. This is the whole reason for marker aiming. |
| Marker, direct hit | SPG-9 HEAT optic, PF98, AT-4, SMAW, MAAWS, Carl Gustav, RPG-7 HEAT, tank and ZiS-3 guns | Range per pixel is large, but vertical miss at the target is 0.1-1.8 m per pixel (section 5.2): fine for vehicle-sized targets if the aim point is raised. The app's note now gives these vertical metres (`1 px = 0.17 m high`) and says "too coarse" only above 0.6 m (issue #11, `mark_height_resolution`). |
| Ladder or ground area fire only | MK19 (all), QLZ87 no optic, AGS-17 iron sights / no optic, TBG-7V, Grom FRAG, 2A70 FRAG, AGS-30 BMP-2M | 5-20 m/px: the pixel is larger than the burst radius (VOG-25 / MK19 inner 1 m, outer 15 m; VOG-19 outer 18 m, `#6-3`) and than the spread of the cheaper weapons; the spread already caps a 5 m hit at 42 % (MK19), see section 5.3. |
| Not aimable by the mark at all | Mortars, Hell Cannon, UB-32, BM-21, the AGS-17 lob | No mark; sight angle and compass, section 4.4. |

## 3. Mouse and game settings (question 2)

### 3.1 What the game does with mouse counts

Source: `GD` (`/tmp/mech/ini/*`, `IMC_*.uasset.json`, decompiled modifiers, `GameSettingsWindow.uasset.json`). All `V` unless marked.

- The look action `IA_Look` on `Mouse2D` runs the modifiers **FOVScaling -> Negate (Y) -> Sensitivity -> InvertAxis** in the soldier, mounted-soldier and turret (tank, IFV, tripod, mortar gunner) contexts. FOVScaling is `value x 0.01111 x camera_FOV`: exactly 1.0 at FOV 90, 1.333 at 120, and *proportional to the current camera FOV* (narrower in a zoomed view). Only the driver's context has smoothing and a response curve.
- The Sensitivity modifier multiplies by the user's **Global** slider. The player controller multiplies again by `InputYawScale = 2.5` and then by `CurrentSens`, which comes from the *per-state* sliders: hip fire (**Point shooting**), and when zoomed the **Soldier 1x / 2x / 3x / 4x / 5-6x / 7-9x / 10x+** map (key = optic magnification; the nearest key is used), for turrets and vehicles the **Vehicle 1x / 4x** map (key = default FOV / current camera FOV). **Steady Aim** (hold breath) multiplies on top when ADS. Slider ranges: Global, Point shooting, Vehicle 0.01-4.0; per-zoom sliders 0.01-2.0. The defaults are native code, **not in the data: read them from your settings**.
- Engine axis config: sensitivity 0.07 per count, exponent 1, no dead zone, mouse smoothing off, FOV scaling on. There is **no raw-input option and no mouse-acceleration option in the game**; whether the Proton/XWayland path delivers raw or accelerated motion is unknown (test 3.4).
- Per count, at camera FOV `F` degrees: `deg = k x G x S x F / 90`, with `k = 2.5 x 0.07 = 0.175` **if** the engine's 0.07 reaches the look action (`A`; k = 2.5 otherwise), `G` the Global slider, `S` the active per-state factor. The conversion to pixels uses the same projection as the mark: `px = deg x (W/2) / tan(F/2) x pi/180`.

### 3.2 Pixels per count (G x S = 1, k = 0.175), centre of the screen

`C`, depends on `A` (k):

| View | camera FOV | deg per count | px per count 1080p | px per count 1440p | G x S for 1 px per count (1080p / 1440p) |
|---|---|---|---|---|---|
| Unzoomed, FOV 120 | 120° | 0.233 | 2.26 | 3.01 | 0.44 / 0.33 |
| AGS-30 BMP-2M ×1.5 | 80° | 0.156 | 3.11 | 4.14 | 0.32 / 0.24 |
| AGS-17 optic ×2.5 | 48° | 0.093 | 3.51 | 4.68 | 0.28 / 0.21 |
| QLZ87 / AGS-30 optic ×3 | 40° | 0.078 | 3.58 | 4.77 | 0.28 / 0.21 |
| T-62 ×3.5 | 34.3° | 0.067 | 3.62 | 4.83 | 0.28 / 0.21 |
| SPG-9 scope / tank ×4 | 30° | 0.058 | 3.65 | 4.86 | 0.27 / 0.21 |

What this means: pixels per count is almost the same in every view (FOVScaling is linear in the FOV while pixels per degree grow as the FOV narrows). The per-zoom sliders have native defaults that are not in the data (read yours in the settings). **Set the per-zoom (Soldier ×2/×3/×4, Vehicle ×4) sliders so that G x S is about 0.25 at 1080p and 0.2 at 1440p**; at that value one count is 1 px in the optics, which is 1.3-2.8 m of range on the AGS-17 / QLZ87 / AGS-30 optics. 1440p gives 1.33x more pixels per count at the same sliders, so the same slider is coarser in pixels (finer in metres: section 2.2 divides by 1.33). The minimum step is one count whatever the DPI; **the DPI only decides how far the hand moves per degree**, so raise the DPI (for example 3200) and lower the slider rather than the other way round. Check for acceleration with test 3.4 and, if the desktop applies a pointer profile, set it to flat (libinput: `Accel Profile Enabled` flat). `A`

### 3.3 FOV trade-off (1080p, m per pixel, flat ground)

`V` (`ballistics.mark_resolution`). Reference: 1 px is 0.0597 / 0.0711 / 0.0852 / 0.1034 deg at FOV 90 / 100 / 110 / 120, i.e. the cost scales as `tan(FOV/2)` (ratios 1 : 1.19 : 1.43 : 1.73).

| Entry (distance) | FOV 90 | FOV 100 | FOV 110 | FOV 120 | FOV 80 (Focus key at 120) |
|---|---|---|---|---|---|
| MK19 tripod, no sights (300 m) | 11.7 | 14.0 | 16.7 | 20.3 | 9.8 |
| AGS-17 optic ×2.5 (300 m) | 1.24 | 1.39 | 1.54 | 1.70 | – |
| AGS-17 iron sights (300 m) | 3.8 | 4.6 | 5.5 | 6.6 | 3.2 |
| QLZ87 optic ×3 (300 m) | 2.05 | 2.29 | 2.53 | 2.78 | – |
| QLZ87 no optic (300 m) | 7.6 | 9.1 | 10.9 | 13.2 | 6.4 |
| RPG-7 PG-7V (300 m) | 10.9 | 12.9 | 15.5 | 18.8 | 9.1 |
| AT-4 (300 m) | 17.9 | 21.3 | 25.5 | 30.9 | 15.0 |
| PF98 Tandem (300 m) | 20.6 | 24.6 | 29.5 | 35.7 | 17.3 |
| SPG-9 HEAT scope ×4 (600 m) | 3.85 | 4.29 | 4.73 | 5.18 | – |
| SPG-9 HEAT no optic (600 m) | 19.3 | 23.0 | 27.6 | 33.5 | 16.2 |
| Tank AP 2A46 ×4 (600 m) | 28.6 | 31.9 | 35.2 | 38.5 | – |

Going from FOV 120 to 90 makes every pixel 1.73x cheaper, at the cost of a narrower view: the world marker is only drawn inside the view (clamped to the edge with a 32 px margin otherwise, `#6-6`), and a pre-turn error of 20 degrees is out of the frame earlier. The zoomed views (÷2.5, ÷3, ÷4) already give the biggest gain; if you play at 120 for situational awareness, keep it and use Focus (FOV 80) for the handheld launchers, aiming without the mark while it is held. The mouse step also scales with the FOV (section 3.1), so the narrower FOV is more precise in two ways. SB takes the FOV from the game's settings file. `V` (numbers) / `A` (that the game narrows to exactly 2/3 under Focus, from `README`; test 7.4)

### 3.4 Turret keys, sway, spread, stance, bipod

- **Turret keys.** A held W/S/A/D applies the full rate at once, no ramp, independent of frame rate, sensitivity, FOV and zoom: `rate = |K x multiplier|` (`NR` 6, `V`). Mortar / Hell Cannon: pitch 9.0 deg/s, yaw 50 deg/s (its cap); AGS-17: pitch 9.0, yaw 18 deg/s; MK19 / QLZ87 / SPG-9 / M2 tripods: pitch 66, yaw 120 deg/s; ZiS-3 and UB-32: capped at 20 / 50 deg/s. One 60 fps frame of the AGS-17 key is 0.15 deg (5.6 px in the ×2.5 view, 9 m at 1.7 m/px), of the tripod key 1.1 deg (about 11 px at FOV 120). Therefore keys can only bring the marker into view; the final pixels are mouse work. Closed tank/IFV turrets: `bHasAcceleration` is a native default, not in the data (`A`); speed caps are 30-60 deg/s yaw and 34-60 pitch, CROWS 90 (`GD` turret table), stabilisation toggle on Z where `bCanStabilize`.
- **Round-to-round spread (MOA; cone half-angle = MOA/120 deg, miss radius uniform on [0, R], R = distance x tan(MOA/120 deg); `NR` 1, `V`).** MK19 / AGS-17 / QLZ87 tripods: base 1.5 but `FC_MOACurve_GenericGMG` replaces it, 15 MOA at rest rising to 50 MOA by 0.75 s of sustained fire (what drives the curve's input is unknown, test 7.5). Handheld QLZ87 20; SPG-9 3.0; RPG-7 20 (v1: 15); PF98, SMAW, MAAWS, Carl Gustav 7; AT-4 10; ZiS-3 3.0; tank main guns 1.5 (Leopard 2 1.2); BMP-2 2A42 3.0; BMP-3 2A72 1.35; AGS-30 15; vehicle MK19 50; mortars 50 (M121 40); Hell Cannon 100; UB-32 300; BM-21 200. Source `GD` `resolved.json`, curves in `/tmp/aimwork/gamedata/curves/`.
- **Sway, hold breath, stance.** A `SwayData` block exists for handheld launchers (RPG-7, PF98, AT-4, SMAW, MAAWS, Carl Gustav, RPG-29, NLAW): ADS sway minimum standing 12.0, crouch 7.0, prone 3.0 (units not in the data), breath-hold factor 0.6, low-stamina factor 30, movement sway up to a factor of 60. Hold breath is the **Focus Sight** key (LeftShift, `IMC_Soldier`; also bound as "Turret Focus" in `IMC_Turret`, effect on turrets and tripods: section 3.5) and has a **Steady Aim** sensitivity slider. The tripod weapons (MK19, AGS-17, QLZ87, SPG-9) are separate vehicles with no sway or bipod code and zero recoil data (`GD`); so for them stance and breath do not exist as a mechanism (`V` for the absence in their blueprints, `A` for the engine not adding any). Bipod (C): only the handheld QLZ87 has `bHasBipod`. The compass HUD exposes `TurretSwayMultiplier`, `TurretRecoilMultiplier` (native defaults, unknown, test 7.5).
- **Test 7.6: mouse constant and acceleration.** Stand still in the unzoomed view and turn by exactly the same mouse travel once slowly and once fast: an equal bearing change on the compass means no acceleration. Then count the mouse counts for one full 360-degree turn (the OS reports them, for example with `evtest`): `counts = 360 / (k x G x S x F/90)` with `F` = 120, so `k` follows from the counts and your sliders.

### 3.5 Focus on open turrets and tripods

`V` (bytecode of `BP_GenericVehicleOpenTurret` and `BP_GenericDeployableTripodVehicle`, `tools/game_weapons.py`). While the Focus key (`IA_Focus`) is held, the generic open turret lerps `Camera1pComponent` to 0.666 of the FOV setting (`AllowFocus`, true on the generic open turret), and the generic tripod lerps `FirstPersonDriverCamera` the same way (`bAllowFocus`, which the generic tripod leaves false: the MK19, AGS-17 iron-sights, SPG-9 and M2 tripods set it true). The CSK131, WZ551 and ZBL-08 QLZ87 turrets, the technical's SPG-9, the AGS-17 optic tripod and the SPG-9 scope tripod set it false, the QLZ87 and ZiS-3 tripods never set it: they do not react. The plain view is then 1 / 0.666 = 1.502 times larger, so a mark laid for the full FOV lands far past the target (the vehicle audit computed several hundred metres at 1000 m for the AGS-17).

The app marks those views in `weapons.json` (`focus_narrows_view`, checked against the game files by `tests/test_vehicle_zoom_views.py`) and follows the key: the default Focus key is **Left Shift** (`Content/Input/IMC_Turret`, `IMC_GroundVehicle` and `IMC_MountedSoldier`, `DefaultKeyMappings`), read like the AGS-17's S and W (`keystate`, evdev or X11). The mark, the ladder and the pixel notes switch at once when the key goes down or up; the game's lerp takes time, so the mark is ahead of the picture for a moment. The overlay's info line says "The mark follows Focus (Left Shift)." or, where the keys cannot be read, "The mark assumes Focus (Left Shift) is not held." A Focus bound to another key in the game is not read (`IA_Focus` is a player-mappable action; the file the game keeps remaps in was not available), and Left Shift pressed for another reason while one of these entries is selected narrows the mark wrongly.

That the picture the player aims in is the component the lerp moves is a **hypothesis**: the bytecode is verified, the rendered effect needs a shot in the game (test 7.4).

## 4. Procedures (question 3)

Common preparation (once per session): Linux compositor on, game borderless or fullscreen at 16:9, the **game FOV read by SB from the game's settings file** (the window says "from the game"; under Focus the mark is not valid on handheld launchers, and follows the key on the entries marked for it, section 3.5), weapon entry matching the view (RMB held = `· optic`, not held = `· no optic`; Mouse4 switches it), overlay on (F8). The Calculator page's "How to fire" steps and the info line say the same for the weapon you chose (`Cr`).

**Nothing to set up for the screen.** SB finds the game's own window on the X server (the `WM_CLASS` `steam_app_393380` that Proton gives it, or the title `SquadGame`) and lays the mark for the width of that window: windowed, borderless, fullscreen, on any monitor, or at a lower game mode that the compositor scales to the screen. The overlay follows the window when it is moved or resized, and covers the configured monitor again once the game is closed or not found. The only window that still draws a warning is one that is not 16:9. If SB cannot read the FOV from the game's settings file, the FOV field says "FOV assumed" and so does the overlay's info line: the mark is then only as exact as the FOV you typed. At a FOV other than 90 the game's printed range marks on a sight reticle (optics, gunner sights, launchers) no longer agree with the mark (at FOV 120 the QLZ87 optic's printed 500 m mark lands near 650 m, about 30 % further; see "Reticle marks of the game sights" in `sight-data.md`), so the info line says to put SB's mark on the target and not the printed marks. `V` (code and tests; the window class and title are `A`: not checked against a live Proton window)

### 4.1 (a) Marker-aided direct fire

Goal: land within the section 5.3 numbers. For each step the error it removes or adds is named.

1. **Own position.** Put the weapon point on the SquadCalc map at zoom 6+ on a landmark you can also see in the game (road crossing, building corner) or type the keypad of your spot (section 4.6). Error 1-3 m. `V`/`A`
2. **Target position.** The marker is on the true target; mark the same place on the SquadCalc map (target flag) at zoom 6+. The mark is computed for the distance between the two clicks; with `map_follow` on, distance and height difference reach the calculator at once (`README`). The calculator now shows distance, height difference and the mark.
3. **Height.** The map gives the heights (bilinear, 1 m grid, `SC`); a 1 m height error costs 0.00-0.28 m of range in marker mode (`C`, section 4.5), ignore it unless the target is on a roof or a tree top (the in-game marker lies on the ground below it).
4. **Aim point.** For direct-hit weapons set `target_height` to the height of the vehicle middle (about 1.2-1.5 m). For splash weapons keep 0.
5. **Pre-aim before the marker appears.** Turn to the SquadCalc bearing with the compass (integer degrees; the mortar view shows tenths) and bring the barrel to roughly the pitch where the mark would sit on the terrain (the ladder, `README` step 4). The goal is that the marker's flash lands within 3-5 px of the mark: it is visible in full for about 0.5 s beyond 60 m and its alpha is capped at 0.2 while zoomed (`#6-6`, `V` for the file data, `A` for the look in game).
6. **Lay the centre of the marker's icon on the centre of the cross and fire.** The icon is 46 px at 0 m and 24 px from 50 m on; it is a screen widget centred on the projected point (`#6-6`). Whether the texture's visual centre equals the pixel centre is unknown, test 7.1. Use the mouse (sensitivity per 3.2), not keys.
7. **Expected result** (1 m position error per click, 1 px of aim): section 5.3. Do not expect all shots to hit: the spread alone caps a 5 m hit at 42 % (MK19) and 84 % (AGS-17 optic).

### 4.2 (b) A known target on the SquadCalc map, no in-game marker

The mark is a pitch reference over the line of sight to the target, so you need the target itself, or a reference for the horizon, in view.

- **Target in view:** put the target's ground point on the mark; you do not need the map target or any marker (type the distance, or use the map).
- **Target out of view or behind terrain:** turn to the bearing from the map (the calculator shows it, 0.1 deg on SquadCalc, whole degrees on the game compass: +-0.5 deg is +-2.6 / 5.2 / 8.7 m of lateral error at 300 / 600 / 1000 m; the compass has a 0.1 deg mode in the mortar view, `GD`). For the pitch there is no on-screen reference except visible ground: put a *visible ground point of known distance on the ladder tick of that distance* (the ladder is the flat-ground screen position for each range, `README`); the camera is modelled at the barrel pivot (`B`, `T-aids` oracle), so the error is the difference of the depression angles of the two ground points, about `eye_height x (1/d1 - 1/d2)` rad (2 px at FOV 120 for 2 m, 300 m and 600 m, `A` for the eye height, test 7.3). Treat the result as area fire, not a marker-class shot.
- For the **AGS-17 lob** the aim is not a mark but the S hold time (`README`, 67 measured holds, residual 5.5 m RMS at 9.00 deg/s, `NR` 6).

### 4.3 (c) Aligning the mark: *Align with the sight*

Purpose: remove the difference between the mark's place on the screen and your sight (alignment: where the mark sits on the screen). Do it on flat ground at Training, never on `squad1`.

1. **Setup.** Flat, level ground, a straight line of 300 m (a longer one for the optics: 600 m). Measure the distance on the SquadCalc map with both points at zoom 6+ (error about 0.5 m), or use two placed objects. Weapon entry correct for the view, the FOV read from the game (the window says so), `target_height` 0, alignment reset.
2. **Align with the sight** (Crosshair page). Open the weapon's sight in the game and compare the mark with the sight's reticle at the weapon's zero distance, where the mark should sit on the reticle's zero line: QLZ87 optic 100 m, tripod MK19 330 m, SPG-9 scope about 765 m (HEAT), AGS-17 open sights about 300 m, ZiS-3 about 350 m (`README`, bore values). Move the mark with *Move left/right* and *Move up/down* (arrow keys step 1 px) onto the sight. Accuracy: +-1 px by eye, i.e. one pixel's metres (section 2.2): 1.7 m on the AGS-17 optic, 2.8 m on the QLZ87 optic, 5.2 m on the SPG-9 scope. Leave *Scale* at 100 % unless two reticle marks at different ranges both disagree: the scale is a whole percent (5 px at 500 px below the centre, 8 m on the AGS-17 optic).

### 4.4 (d) Mortars, Hell Cannon, rocket artillery

No mark. The angle comes from the calculator and the sight is the game's.

- **Elevation.** Mortar sight in mils, integer: one mil is 0.05625 deg, 1.4-2.4 m of range at 1000-300 m (`SC` step; `GD` `UMG_MortarControl`: `mil = floor((90 - 0.5 x asin(...)) x 17.78)`). The Hell Cannon HUD shows 0.1 deg (3.0 m at 300 m, 2.5 m at 600 m). The M121 advanced widget shows angle and bearing in 0.1 deg. Rounding is far below the spread (50 MOA mortar 17 m, 100 MOA Hell Cannon 25 m at 300-600 m, `SC` ran), so the displayed resolution is not the limit. There is **no 0.5 mil step in the game's table**; SB's auto-lay (F7) works to 0.5 mil of the sight reading (`sightlay.py` `TOLERANCE`).
- **Keys.** The tube moves 9.0 deg/s on a held key, so one 60 fps frame is 0.15 deg = 2.7 mil (4-6 m of range): tap for coarse, then use the mouse (tube pitch ×0.03 of the look rate, `GD`/`A`: about 0.005 deg = 0.09 mil per count at FOV 90 and G = S = 1) for the last mils.
- **Compass.** Whole degrees outside the mortar view (1 deg is 5.2 / 10.5 / 17.5 m of lateral error at 300 / 600 / 1000 m), 0.1 deg in the mortar view (`NR` 5). Use the mortar view's tenths for the bearing and set the bearing to the SquadCalc value (0.1 deg). With bearing off by 1 deg the lateral error equals the spread at 600 m: this is the dominant term for mortars, not the elevation.
- **Spread** for the plan: 81 mm mortar 17-18 m lateral at 100-600 m, 16 m at 1000 m; Hell Cannon 25-26 m at 300 m; UB-32 9-70 m lateral and 150-350 m along; BM-21 30-75 m lateral (`SC` ran, `squadFiringSolution.js:247-300`).

### 4.5 (e) Elevated and depressed targets, `target_height`

- Type the height difference or take it from the map (target higher `+`). The mark is computed over the *line of sight* to the target, so slopes are handled by the app (`B` `solve`, `sight_angle`).
- The map sets the target's height from the heightmap (bilinear, 1 m grid, centimetre accurate on terrain: median 0.00 m against server markers, `#8`); roofs and treetops make a 1-5 m error on 2-8 % of clicks (`#6-4`).
- **Marker mode:** the marker is on the terrain, so you remove height almost entirely: a 1 m height error costs, at 300 / 600 / 1000 m, MK19 0.03 / 0.05 / 0.09 m, AGS-17 optic 0.07 / 0.16 / 0.28 m, QLZ87 optic 0.04 / 0.08 / 0.14 m, PF98 / SPG-9 / tank under 0.02 m (`C`).
- **Computed-only mode (no marker):** a 1 m height error is a 1/D rad barrel error: 0.19 / 0.096 / 0.058 deg at 300 / 600 / 1000 m (`C`), i.e. 36 / 18 / 10.7 m for the MK19 and 12 / 6 / 3.6 m for the AGS-17 (`#6-4`).
- `target_height` (config only, 0-10 m, default 0): aims that far above the target ground, the mark moves down, the info line shows `aim +1.5 m`. Use ~1.2 m for a vehicle's middle, ~1 m for a standing soldier with a direct-hit weapon, 0 for splash. Mortars ignore it.

### 4.6 (f) Placing your own position precisely on the SquadCalc map

- **Metres per screen pixel** (`SC`, formula `mapSize / (256 x 2^zoom)`, `squadMinimap.js:59-66`, `zoomSnap: 0`, max zoom 8, up to native tile zoom + 2 on the detailed layer; table computed `C`):

| Map size | zoom 4 | zoom 5 | zoom 6 | zoom 7 | zoom 8 |
|---|---|---|---|---|---|
| 2000 m | 0.49 | 0.24 | 0.12 | 0.061 | 0.031 |
| 4081 m | 1.00 | 0.50 | 0.25 | 0.12 | 0.062 |
| 6900 m (Skorpo) | 1.69 | 0.84 | 0.42 | 0.21 | 0.105 |

  At zoom 6 on a 4 km map one screen pixel is 0.25 m (the same figure as `#6-4`); the heightmap is a 1 m grid, so a 0.25 m placement is already below its resolution. On a retina-class display a CSS pixel is two device pixels. `C` from the `SC` formula; the browser was not measured.
- **Keypad.** The game keypad is `A02-3-5-2`: 300 m / 100 m / 33 m / 11 m / 3.7 m; the Weapon dialog's *Move to* field takes any depth (the display stops at 3.7 m; deeper strings resolve to the cell centre: 1.2 m and 0.41 m, `SC` `getPos`). A 3.7 m cell gives a uniform error of 1.07 m RMS per axis; a cell centre is the unbiased estimate. The cursor popup needs `keypadUnderCursor` and zoom 6+ for 3.7 m.
- **Method for 1-3 m.** (1) Choose a spot you can name on both maps (road crossing, building corner, bridge end). (2) In the game open the map, read the keypad of the spot (and note the grid letter). (3) In SquadCalc type it in *Move to*, or double-click the first point, then zoom 6+ and drag the marker onto the same feature in the SquadCalc imagery/heightmap. (4) Place the target flag the same way. (5) Read the displayed distance, which rounds to whole metres (`SC` `squadTargetMarker.js:323`).
- **What the error does.** Range error = metre for metre (own error + target error, sqrt(2) times one click) in marker mode: at 2 m per click that is 2.8 m RMS: 1.7 x the AGS-17 optic pixel and 0.85 x its round spread. For direct-hit weapons 2.8 m of range is `2.8 x tan(descent)` of height: 0.09 m for the PF98 and 0.15 m for the RPG-7 at 600 m. Computed-only mode adds the bearing: a lateral error equal to the position error.
- **Unknowns.** The in-game map's metres per pixel at its five zoom levels (`MapZoomLevels` 1 / 1.5 / 2 / 3.5 / 5, base layer 800 px: 5 m/px at zoom 1 and 1 m/px at zoom 5 if the map fills that layer: `A`, test 7.2) and whether the in-game grid equals SquadCalc's on Skorpo (`maps.js:466-478`: the in-game grid may be about 6900 x 6900 against SDK corners 6849 x 6869, up to about 50 m: hypothesis, test 7.2). On every other map the frames match (corners on 25 maps, markers within 10 cm, `#6-4`).

### 4.7 (g) Map target versus typed distance

- With *Put the map target and weapon into the calculator* on (`map_follow`, Deadline build), the newest map target fills the distance and height difference and the weapon is synchronised both ways (`README`). Typing a distance by hand takes over **until the next map target**; the map's re-delivery of the same target does not overwrite your typed values (`Cr` `last_map_target`).
- A typed distance has no terrain profile, so no obstacle warning (`⛔`) and no bearing. A map target carries the heightmap profile and the bearing.
- **F9** clears the target, the typed distance and the map target (not the alignment); a new target from the map restores the mark.
- Rule: use the map for the first, long shot (bearing + obstacle check); type a distance when you correct by observation (+25 m) or fire at a visible target whose distance you read off a rangefinder; re-pick the map target afterwards.

## 5. Error budget (question 4)

### 5.1 Model

One-off Monte Carlo (`C`; 1500 shots per cell, seed fixed, pure Python over `ballistics.solve`/`Weapon.flight_height`, not in the repository). For each shot: the target is at the distance D on flat ground; the calculator distance is `D + e`, `e ~ N(0, 2 sigma_pos^2)` (own + target click); the barrel is `lambda_true + (theta(D_calc) - lambda_calc) + aim error`; the aim error is `sigma_aim` pixels of the mark row in the view's projection; the cone: pitch error `phi cos psi`, yaw error `phi sin psi`, `phi` uniform on `[0, MOA/120 deg]`, `psi` uniform (`NR` 1). Ground hit: impact within 5 m of the aim point on the ground (a lethal-radius proxy for splash rounds). Box hit: the shell crosses the target plane inside a 3.6 m wide x 2.4 m high box standing on the ground (aim at the foot `L0` or at 1.2 m `L1.2`). Camera at the pivot (parallax of the real camera, 0.23 m up and 0.34 m right on the QLZ87, is -8.5 / -5.6 / -4.2 m at 200 / 300 / 400 m in the plain view, `#5`, and is not in the model). The comparison with the existing SquadCalc model: that model (`hitProbability`, `squadDamage.js`) uses spread only (no target size, no position error, `SC` ran) and has no direct-fire hit probability on `dev` (`#8` of `deadline-squadcalc`; the work is in an uncommitted worktree, and `tools/direct_fire/hit_probability_check.mjs` crashes on `dev` with `getHitSpread is not a function` for that reason). The "ideal" columns agree with `#6-2` (AGS-17 optic 84 %, QLZ87 optic 57 %, MK19 43 %).

Scenarios (sigma per click of position / aim px): **ideal** 0 / 0, **best** 1 / 0.5, **typical** 2 / 1, **poor** 3 / 3. The first run also had a trim error (sigma 0 / 1 / 2 / 3 m of range) as a third source; the app has no trim now, so the totals in 5.2 are the originals less that term in quadrature (`sqrt(total^2 - 2^2)`), and the hit probabilities in 5.3 still include it.

### 5.2 Sources of error at 600 m, 1 sigma in metres of ground range ("typical" scenario)

`C`. Model error is at most 0.5 m against the oracle (`T-e2e` tolerance) but the oracle is itself written from the same decompiled rules (not an independent check against the live game); the AGS-17 hold model has 5.5 m RMS (`NR` 6), the QLZ87 optic beyond 400 m is unexplained (`#5` D11), parallax up to 9 m at 200 m in the plain QLZ87 view.

| Weapon / view | own + target (2 m / click) | aim pixel (1 px) | round spread | total | dominant |
|---|---|---|---|---|---|
| MK19 tripod, sights | 2.8 | 19.3 | 9.7 (15 MOA; sustained 50 MOA: 32) | 21.8 | aim pixel |
| AGS-17 optic ×2.5 | 2.8 | 1.7 | 3.3 | 4.7 | spread |
| AGS-17 iron sights | 2.8 | 6.5 | 3.2 | 7.8 | aim pixel |
| QLZ87 optic ×3 | 2.8 | 2.7 | 6.5 | 7.6 | spread |
| QLZ87 no optic | 2.8 | 13.0 | 6.3 | 14.8 | aim pixel |
| AGS-30 BTR-4 ×3 | 2.8 | 2.8 | 6.4 | 7.5 | spread |
| RPG-7 PG-7V | 2.8 | 20.0 | 13.2 | 24.1 | aim pixel |
| PF98 Tandem | 2.8 | 35.7 | 8.5 | 36.7 | aim pixel |
| AT-4 | 2.8 | 30.9 | 9.8 | 32.5 | aim pixel |
| SPG-9 scope ×4 | 2.8 | 5.2 | 3.4 | 6.8 | aim pixel |
| SPG-9 no optic | 2.8 | 33.5 | 3.3 | 33.7 | aim pixel |
| ZiS-3 optic ×4 | 2.8 | 13.9 | 8.9 | 16.8 | aim pixel |
| Tank AP ×4 (2A46) | 2.8 | 38.5 | 12.7 | 40.7 | aim pixel |

For the **direct-hit weapons** the same pixels are small in the plane that decides the hit:

| Weapon (descent angle) | 1 px high at the target, 300 / 600 / 1000 m | spread radius R = D tan(MOA/120°), 300 / 600 / 1000 m |
|---|---|---|
| RPG-7 PG-7V (1.6 / 3.1 / 5.1 deg) | 0.54 / 1.07 / 1.77 m | 0.87 / 1.75 / 2.91 m |
| PF98 Tandem (0.9 / 1.7 / 2.9 deg) | 0.54 / 1.08 / 1.80 m | 0.31 / 0.61 / 1.02 m |
| AT-4 (1.0 / 2.0 / 3.4 deg) | 0.54 / 1.08 / 1.79 m | 0.44 / 0.87 / 1.45 m |
| SPG-9 HEAT scope ×4 (0.9 / 1.9 / 3.1 deg) | 0.08 / 0.17 / 0.28 m | 0.13 / 0.26 / 0.44 m |
| SPG-9 HEAT no optic | 0.54 / 1.08 / 1.80 m | 0.13 / 0.26 / 0.44 m |
| ZiS-3 optic ×4 (0.3 / 0.7 / 1.2 deg) | 0.08 / 0.17 / 0.28 m | 0.13 / 0.26 / 0.44 m |
| Tank AP ×4 (0.12 / 0.25 / 0.42 deg) | 0.08 / 0.17 / 0.28 m | 0.07 / 0.13 / 0.22 m |

`V` (`solve().impact_angle`, `mark_resolution`) / `C`. So for vehicle-size targets and direct-hit weapons the dominant terms are the aim point (raise it) and, for the unzoomed anti-tank launchers (1 px = 0.5-1.8 m high), the pixel itself; zoomed SPG-9, ZiS-3 and tank sights are limited by the spread.

### 5.3 Hit probability

`C`. P5 = shell lands within 5 m of the aim point on the ground (splash weapons); Box = shell inside the 3.6 x 2.4 m box, aim at the foot (L0) or at 1.2 m (L1.2). Percent.

| Weapon / view | D | ideal P5 | best P5 | typical P5 | poor P5 | Box L0 ideal / typical | Box L1.2 ideal / best / typical / poor |
|---|---|---|---|---|---|---|
| MK19 tripod (15 MOA) | 300 | 44 | 29 | 17 | 8 | | |
| | 600 | 44 | 26 | 17 | 6 | | |
| | 1000 | 42 | 28 | 17 | 6 | | |
| AGS-17 optic ×2.5 | 300 | 85 | 81 | 66 | 47 | | |
| | 600 | 83 | 78 | 66 | 50 | | |
| AGS-17 iron sights | 300 | 83 | 70 | 46 | 19 | | |
| | 600 | 86 | 71 | 46 | 20 | | |
| | 1000 | 89 | 73 | 50 | 19 | | |
| QLZ87 optic ×3 | 300 | 58 | 55 | 48 | 31 | | |
| | 600 | 55 | 54 | 50 | 33 | | |
| | 1000 | 58 | 54 | 47 | 35 | | |
| QLZ87 no optic | 300 | 56 | 42 | 25 | 9 | | |
| | 600 | 57 | 42 | 28 | 9 | | |
| AGS-30 BTR-4 ×3 | 300 | 56 | 54 | 47 | 32 | | |
| | 600 | 57 | 51 | 48 | 32 | | |
| RPG-7 PG-7V (20 MOA) | 300 | 35 | 24 | 19 | 6 | 52 / 53 | 100 / 99 / 94 / 52 |
| | 600 | 34 | 24 | 16 | 6 | 53 / 45 | 89 / 81 / 65 / 30 |
| | 1000 | 35 | 24 | 16 | 6 | 41 / 32 | 57 / 49 / 34 / 15 |
| PF98 Tandem (7 MOA) | 300 | 50 | 20 | 11 | 4 | 52 / 51 | 100 / 100 / 97 / 53 |
| | 600 | 48 | 21 | 12 | 4 | 51 / 49 | 100 / 97 / 71 / 28 |
| | 1000 | 48 | 19 | 10 | 4 | 52 / 40 | 100 / 75 / 47 / 18 |
| AT-4 (10 MOA) | 300 | 42 | 22 | 11 | 5 | 51 / 52 | 100 / 100 / 96 / 54 |
| | 600 | 43 | 19 | 13 | 3 | 48 / 47 | 100 / 94 / 72 / 28 |
| | 1000 | 43 | 22 | 12 | 4 | 51 / 39 | 96 / 73 / 47 / 17 |
| SPG-9 scope ×4 (3 MOA) | 300 | 84 | 71 | 51 | 22 | 50 / 50 | 100 / 100 / 100 / 100 |
| | 600 | 83 | 73 | 50 | 24 | 48 / 50 | 100 / 100 / 100 / 97 |
| | 1000 | 84 | 73 | 53 | 24 | 52 / 51 | 100 / 100 / 100 / 82 |
| SPG-9 no optic | 300 | 86 | 24 | 11 | 5 | 50 / 49 | 100 / 100 / 97 / 53 |
| | 600 | 84 | 26 | 13 | 5 | 50 / 49 | 100 / 97 / 73 / 29 |
| | 1000 | 85 | 23 | 12 | 4 | 48 / 41 | 100 / 82 / 48 / 17 |
| ZiS-3 optic ×4 (3 MOA) | 300 | 46 | 33 | 23 | 9 | 50 / 50 | 100 / 100 / 100 / 100 |
| | 600 | 47 | 37 | 23 | 8 | 51 / 49 | 100 / 100 / 100 / 98 |
| | 1000 | 45 | 33 | 24 | 10 | 52 / 50 | 100 / 100 / 100 / 83 |
| Tank AP ×4 (1.5 MOA) | 300 | 38 | 19 | 10 | 4 | 48 / 52 | 100 / 100 / 100 / 100 |
| | 600 | 36 | 18 | 9 | 3 | 50 / 50 | 100 / 100 / 100 / 98 |
| | 1000 | 36 | 17 | 10 | 3 | 51 / 51 | 100 / 100 / 100 / 87 |

Reading it. (1) "All shots hit" is not reachable for the splash weapons: with the sustained-fire 50 MOA the MK19 is lower still (`#6-4`: single-shot kill chance about 25 % for the MK19 and QLZ87, 67-75 % for the AGS-17). (2) The P5 of a tank gun is a ground-plane artefact (the flat trajectory spreads along the ground): judge direct-hit weapons by the Box columns. (3) Aiming at the foot gives 50 % at best: raise the aim point. (4) In zoomed views position error costs little (AGS-17 optic 83 -> 78 -> 66 %: from perfect to a 2 m click) while in unzoomed views the pixel costs everything (MK19 44 -> 17 %, AGS-17 iron 86 -> 46 %). (5) Cross-check with the SquadCalc spread (a separate probe on the uncommitted `getHitSpread`, ideal conditions): P5 at 300 m is 0.18 for the MK19 at 50 MOA (this model 17.5 %), 0.37 for the tank gun (38 %), 0.84 for the SPG-9 (84 %), 0.36 for RPG-7 HEAT at 20 MOA (35 %); the two models agree within 1-2 points. SquadCalc cannot show any of the columns that matter here (position error, aim pixel, box target) - backlog 5-6. The MK19 under sustained fire (50 MOA) is 18 % at 300 m and 15 % at 1000 m.

## 6. Backlog proposals (question 5)

Ranked by expected gain in metres per effort. These feed the roadmap in `#8` (section B).

| # | Proposal | Where | Gain | Effort |
|---|---|---|---|---|
| 1 (done, issue #11) | Replace "1 px = N m" and "too coarse for marker aiming" for direct-hit weapons by the vertical metres per pixel at the target and a box verdict (e.g. `1 px = 0.17 m high`, ok vs a 2.4 m target). Fixes a wrong verdict for SPG-9 scope, PF98, tank, ZiS-3 (issue #11) | `ballistics.py` `mark_resolution`, `crosshair.py` `marker_notes` | removes a misleading "do not use" for the best AT weapons | S |
| 2 | UI field and F-key step for `target_height` with presets (soldier 1 m, vehicle 1.2 m) | `crosshair.py`, `config.py` | 50 % -> up to 100 % box hits (section 5.3) | S |
| 3 | Show the mouse step: "1 count = N px" for the typed `G x S`, and a one-time 360-degree check to measure `k` | `crosshair.py` | puts the aiming view at 1 px per count (rule 4) | M |
| 4 | Take the target position from the in-game marker's server log line (integer cm, terrain exact) instead of a second map click; the feed from `#6` | host feed | removes the target click (2.8 m RMS becomes 2.0 m) | L (owner approval) |
| 5 | SquadCalc: direct-fire hit probability with target size and position error (`#8` of `deadline-squadcalc`, finish the worktree and fix the two failing 0.01 checks) | `squadDamage.js`, `squadTargetMarker.js`, `gen_squadcalc_weapons.py` | the 5 m hit chance in this guide in the map | M |
| 6 | SquadCalc: position-error input in the hit probability and vertical-target model | `squadDamage.js`, `squadSettings.js` | shows what 1-3 m of click error costs | M |
| 7 | SquadCalc: arrow-key nudge (1 m / 5 m) of the selected weapon / target, a *Move to* keypad field for targets, 3.7 m and 11 m sub-grids drawn at zoom 6+, keypad to 5 sub-levels | `squadMarker.js`, `squadTargetMarker.js`, `squadGrid.js`, `squadMinimap.js` | position repeatability 0.25 m instead of mouse jitter; typed targets | S-M |
| 8 | SquadCalc: show the weapon's and target's ground heights next to the difference; show range per displayed step (0.1 deg of the UB-32 is 6-10 m) | `squadTargetMarker.js:323,348-368,437` | catches a roof/treetop height before firing | S |
| 9 | "Turn N deg" and "pitch about N deg" pre-aim hint for the marker flash (the compass reader exists only for the mortar) | `compassreader.py`, overlay | lands the first 0.5 s flash within 3-5 px | M |
| 10 | In-game-grid overlay for Skorpo (6849 x 6869 against about 6900 x 6900) once measured | SquadCalc `maps.js`, `squadGrid.js` | up to 50 m on one map | M |

## 7. Tests the game has to answer (unknown, test X)

| # | Question | Test | Why it matters |
|---|---|---|---|
| 7.1 | Visual centre of the world marker icon; whether it appears in the optic's view; lifetime at 30 / 55 / 120 / 300 m | 60 fps recording of a Move marker (SL), 2x crop at 30 m, in ×1 and in the ×2.5-×4 views | the centre of the aim; whether zoomed marker aiming works at all (`#6-6` open) |
| 7.2 | In-game map metres per pixel at the five zoom levels; Skorpo grid | screenshots with scale bar, 10 markers on fixed features | own-position repeatability (4.6) |
| 7.3 | Camera height over the pivot, parallax | fire a plain-view shot at 100 / 200 / 300 m, see `#5` QLZ87 | non-marker pitch reference |
| 7.4 | Focus key: the FOV change on the plain views of open turrets and tripods (the camera the game renders), exact factor; Left Shift on turrets | hold Focus on an AGS-17 emplacement or a MK19 tripod and read the FOV change on a map feature, then fire one shot with Focus held and one without at the same target | rules 10, section 3.5 |
| 7.5 | Spread build-up of the GMG curve; turret sway multipliers | MK19 bursts from rest, 30 shots per burst length | MK19 / AGS first-shot MOA |
| 7.6 | Mouse constant `k` and acceleration | 360-degree turn test (3.4) | step section 3.2 |
| 7.7 | Mortar tap step | one-frame tap at a low frame rate, read the dial | 4.4 |

## 8. Verified and assumed, in one place

**Verified (code, data or a reproduced run):** the m/px tables and their 0.75 scaling and agreement with the oracle (within 2 % in 100 of 104 cases); the off-screen ranges (940 / 1490 m, equal to `T-aids`); the FOV, `tan(FOV/2)` scaling; the whole-percent / whole-pixel setting steps; the modifier chain and the slider list of the look input; the 9.0 / 18 / 66 / 120 deg/s key rates; MOA values per weapon and the GMG curve 15 -> 50 MOA; the sway block for handheld launchers; marker facts (icon, 0.5 s flash beyond 60 m, alpha 0.2 zoomed, terrain trace); SquadCalc zoom, keypad, rounding and the missing direct-fire hit model on `dev`.

**Computed (one-off scripts, inputs verified, script not in the repo):** the Monte Carlo tables 5.2 and 5.3; the height-error costs; the pixel-per-count table; the vertical-metres-per-pixel table.

**Assumed (named test):** the engine constant 0.07 reaching the look input (7.6); which per-zoom slider each sight uses (nearest key; 7.6); that the tripod weapons use the Vehicle sliders (7.6); Focus narrowing to 2/3 on handheld launchers (7.4), and that the camera the game renders on the plain view of an open turret or a tripod is the component the Focus lerp moves (7.4: the lerp is verified in the bytecode, the rendered effect is a hypothesis until a shot in the game confirms it); the landing reading error +-2.5 m (calibration); a 1 px eye precision (the estimate in rule 3); the in-game map scale and the Skorpo grid offset (7.2); whether the marker's visual centre is the pixel centre (7.1).
