# Sight data of the emplaced and vehicle weapons

Which emplaced (tripod, open turret) and vehicle (closed turret, hull gun, vehicle mount) weapons of `weapons.json` carry the three pieces of sight data the overlay mark depends on, and why the others do not. The handheld launchers and grenade launchers (26 entries) are out of scope: the game files do not give their sight, so their bore 0 and zoom 1 are assumptions (`bore_assumed`, `zoom_assumed` in `tests/data/game_weapons.json`). The 78 weapons in scope are all the other entries; `tests/test_sight_data.py` checks that both tables below match `weapons.json` and that every missing piece has a reason.

- **Bore** (degrees): how far above the centre of the view the shot leaves. `-` means 0: nothing to apply.
- **Zoom**: the divisor the sight puts on the game's FOV. `-` means the view keeps the game's FOV.
- **Launch point** (`launch_height` / `muzzle_forward` / `muzzle_up`, metres): the barrel pivot's height over the ground and the muzzle's offset along and above the barrel, which is where the shot starts relative to the eye. `-` means the shot starts at the ground at the pivot.
- **Camera offset (parallax)**: none of the weapons carries one. The model puts the camera at the barrel's pivot. The only measured offset is the QLZ87's in the normal view (0.23 m up and 0.34 m right of the pivot, worth -8.5 / -5.6 / -4.2 m of range at 200 / 300 / 400 m; see `docs/aiming.md`); the game files do not give the other cameras' places, so it is not applied.

## Weapons and their data

| Weapon | Bore, deg | Zoom | Launch point, m |
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
| QLZ87 · Lynx / CSK131 · optic (RMB ×3) | 0.85 | 3 | - |
| QLZ87 · Lynx / CSK131 · no optic | 0.85 | - | - |
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
| Mortar (M252 / 2B14 / L16 / Type 63) | - | - | 0.0245 / 1.569 / 0.002 |
| Technical Mortar | - | - | 1.1789 / 1.6137 / 0.0388 |
| M1064 M121 (120mm) | - | - | 0.8174 / 3.4618 / 0.0035 |
| Hell Cannon | - | - | 0.155 / 2.373 / 0.002 |
| UB-32 (S-5 rockets) | - | - | 1.3075 / 1.43 / 0.251 |
| Technical UB-32 | - | - | 2.2659 / 1.4303 / 0.2513 |
| BM-21 Grad | - | - | 1.7694 / 2.7346 / 0.6366 |

## Missing data and why

`Missing` is `bore`, `zoom` or `launch`.

| Weapon | Missing | Reason |
|---|---|---|
| MK19 | bore | the gunner's sight is aligned with the barrel (game files: bore 0.0), so there is nothing to apply |
| MK19 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 | launch | the files hang the turret on a socket 1.2 m below the hull's turret bone while the sight mesh is at 2.6 m, so the pivot is ambiguous and not extracted (tools/game_weapons.py) |
| MK19 · AAVP-7A1 | bore | the gunner's sight is aligned with the barrel (game files: bore 0.0), so there is nothing to apply |
| MK19 · AAVP-7A1 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · PARS III RWS | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · TAPV C16 RWS | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · M113 open turret | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · M113 open turret · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · M113 open turret · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · M1151 open turret | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · M1151 open turret · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · M1151 open turret · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · MATV open turret | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · MATV open turret · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · MATV open turret · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · RHIB open turret | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · RHIB open turret | launch | a boat has no wheels and floats on pontoons, so the files give no ground height (deadline-squad/squad-ballistics#12) |
| MK19 · emplacement / C16 / L134A1 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · emplacement / C16 / L134A1 | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| MK19 · emplacement / C16 / L134A1 · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · emplacement / C16 / L134A1 · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · emplacement / C16 / L134A1 · no sights | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| AGS-17 · emplacement · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · iron sights emplacement | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Technical | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Tigr | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Safir | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · M1151 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · BTR-D | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · optic (RMB ×3) | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| QLZ87 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · no optic | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| QLZ87 · Lynx / CSK131 · optic (RMB ×3) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| QLZ87 · Lynx / CSK131 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · Lynx / CSK131 · no optic | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| AGS-30 / BTR-4 AGS | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| AGS-30 (BMP-1TS) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| AGS-30 (BMP-2M) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · HEAT | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · HEAT · scope · optic (RMB ×4) | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · HEAT · scope · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT · scope · no optic | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · FRAG | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · FRAG · scope · optic (RMB ×4) | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · FRAG · scope · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · scope · no optic | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| SPG-9 · HEAT · technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT · INS armoured technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · INS armoured technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| 2A28 Grom (BMP-1 / BMD-1) · HEAT | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A28 Grom (BMD-1M) · HEAT | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A28 Grom (BMP-1 / BMD-1) · FRAG | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A28 Grom (BMD-1M) · FRAG | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A70 100mm (ZBD-04A) · FRAG | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| 2A70 100mm (BMD-4M) · FRAG | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| ZiS-3 · optic (RMB ×4) | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| ZiS-3 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| ZiS-3 · no optic | launch | a tripod has no vehicle seat in the game files, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3 | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · T-62 (2A20) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · T-64BM2 (KBA3) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · ZTZ-99 (ZPT-98) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · M256 / Rh120 | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · Leopard 2A6 (Rh120) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · M60T (MG253) | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| Tank AP · M60T (MG253) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · L30A1 (Challenger 2) / M68A2 | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank AP · M1128 MGS (M68A2) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2 | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · M1A1 / M1A2 (M256) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · Leopard 2A6 (Rh120) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · M1128 MGS (M68A2) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · M60T (MG253) | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| Tank HEAT/HE · M60T (MG253) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · T-62 (2A20) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HEAT/HE · T-64BM2 (KBA3) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Tank HESH · L30A1 (Challenger 2) | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · AP | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE | launch | a closed turret or hull gun has no vehicle seat entry, so tools/game_weapons.py derives no launch point; the shot starts at the ground (launch_height 0) |
| Mortar (M252 / 2B14 / L16 / Type 63) | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| Mortar (M252 / 2B14 / L16 / Type 63) | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| Technical Mortar | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| Technical Mortar | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| M1064 M121 (120mm) | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| M1064 M121 (120mm) | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| Hell Cannon | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| Hell Cannon | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| UB-32 (S-5 rockets) | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| UB-32 (S-5 rockets) | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| Technical UB-32 | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| Technical UB-32 | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |
| BM-21 Grad | bore | aimed by its own elevation readout, not through a view: the game files give no bore |
| BM-21 Grad | zoom | aimed by its own elevation readout, not through a view: the game files give no zoom |

Counts: 65 of 78 weapons have a bore, 38 a zoom, 32 a launch point; 13 lack a bore, 40 a zoom, 46 a launch point.
