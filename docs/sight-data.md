# Sight data of the emplaced and vehicle weapons

Which emplaced (tripod, open turret) and vehicle (closed turret, hull gun, vehicle mount) weapons of `weapons.json` carry the three pieces of sight data the overlay mark depends on, and why the others do not. The handheld launchers and grenade launchers (26 entries) are out of scope: the game files do not give their sight, so their bore 0 and zoom 1 are assumptions (`bore_assumed`, `zoom_assumed` in `tests/data/game_weapons.json`). The 141 weapons in scope are all the other entries; `tests/test_sight_data.py` checks that both tables below match `weapons.json` and that every missing piece has a reason.

- **Bore** (degrees): how far above the centre of the view the shot leaves. `-` means 0: nothing to apply.
- **Zoom**: the divisor the sight puts on the game's FOV. `-` means the view keeps the game's FOV.
- **Launch point** (`launch_height` / `muzzle_forward` / `muzzle_up`, metres): the barrel pivot's height over the ground and the muzzle's offset along and above the barrel, which is where the shot starts relative to the eye. `-` means the shot starts at the ground at the pivot.
- **Camera offset (parallax)**: none of the weapons carries one. The model puts the camera at the barrel's pivot. The only measured offset is the QLZ87's in the normal view (0.23 m up and 0.34 m right of the pivot, worth -8.5 / -5.6 / -4.2 m of range at 200 / 300 / 400 m; see `docs/aiming.md`); the game files do not give the other cameras' places, so it is not applied.

## Weapons and their data

| Weapon | Bore, deg | Zoom | Launch point, m |
|---|---|---|---|
| MK19 | - | - | - |
| MK19 · M1117 · gunner sight ×4.5 | - | 4.5 | - |
| MK19 · AAVP-7A1 | - | - | 3.2232 / 1.0868 / 0.0748 |
| MK19 · AAVP-7A1 · gunner sight ×4.5 | - | 4.5 | 3.2232 / 1.0868 / 0.0748 |
| MK19 · PARS III RWS | 0.95 | - | 2.6617 / 0.4161 / 0.0257 |
| MK19 · PARS III RWS · gunner sight ×3 | 0.95 | 3 | 2.6617 / 0.4161 / 0.0257 |
| MK19 · PARS III RWS · gunner sight ×9 | 0.95 | 9 | 2.6617 / 0.4161 / 0.0257 |
| MK19 · TAPV C16 RWS | 1.55 | - | 3.093 / 0.6256 / -0.0155 |
| MK19 · TAPV C16 RWS · gunner sight ×5 | 1.55 | 5 | 3.093 / 0.6256 / -0.0155 |
| MK19 · TAPV C16 RWS · gunner sight ×12 | 1.55 | 12 | 3.093 / 0.6256 / -0.0155 |
| MK19 · M113 open turret | 1.6 | - | 2.6316 / 0.6951 / -0.0087 |
| MK19 · M113 open turret · no sights | - | - | 2.6316 / 0.6951 / -0.0087 |
| MK19 · M1151 open turret | 1.7211 | - | 2.3056 / 0.6951 / -0.0087 |
| MK19 · M1151 open turret · no sights | - | - | 2.3056 / 0.6951 / -0.0087 |
| MK19 · MATV open turret | 1.7211 | - | 3.0282 / 0.6951 / -0.0087 |
| MK19 · MATV open turret · no sights | - | - | 3.0282 / 0.6951 / -0.0087 |
| MK19 · RHIB open turret | 1.7286 | - | - |
| MK19 · RHIB open turret · no sights | - | - | - |
| MK19 · emplacement / C16 / L134A1 | 1.674 | - | 0.4345 / 0.6951 / -0.0087 |
| MK19 · emplacement / C16 / L134A1 · no sights | - | - | 0.4345 / 0.6951 / -0.0087 |
| AGS-17 · emplacement · optic (RMB ×2.5) | 0.85 | 2.5 | 1 / 0 / 0 |
| AGS-17 · emplacement · no optic | 0.85 | - | 1 / 0 / 0 |
| AGS-17 · iron sights emplacement | 4.5 | - | 1 / 0 / 0 |
| AGS-17 · Technical | 4.5 | - | 2.2118 / 0.87 / 0.068 |
| AGS-17 · Tigr | 4.5 | - | 2.5927 / 0.87 / 0.068 |
| AGS-17 · Safir | 4.5 | - | 1.7967 / 0.87 / 0.068 |
| AGS-17 · M1151 | 4.5 | - | 2.2891 / 0.87 / 0.068 |
| AGS-17 · BTR-D | 4.5 | - | 2.2635 / 0.87 / 0.068 |
| QLZ87 · optic (RMB ×3) | 0.774 | 3 | 0.446 / 0.7554 / 0.0292 |
| QLZ87 · no optic | -0.9 | - | 0.446 / 0.7554 / 0.0292 |
| QLZ87 · bunker tripod · optic (RMB ×3) | 0.774 | 3 | 0.446 / 0.7554 / 0.0292 |
| QLZ87 · bunker tripod · no optic | -0.9 | - | 0.446 / 0.7554 / 0.0292 |
| QLZ87 · CSK131 / WZ551 · optic (RMB ×3) | 0.85 | 3 | 2.3182 / 0.7265 / 0.1727 |
| QLZ87 · CSK131 / WZ551 · no optic | 0.85 | - | 2.3182 / 0.7265 / 0.1727 |
| QLZ87 · Lynx · optic (RMB ×3) | 0.85 | 3 | 1.901 / 0.7265 / 0.1727 |
| QLZ87 · Lynx · no optic | 0.85 | - | 1.901 / 0.7265 / 0.1727 |
| QLZ87 · ZBL08 · optic (RMB ×3) | 0.85 | 3 | 2.5044 / 0.7265 / 0.1727 |
| QLZ87 · ZBL08 · no optic | 0.85 | - | 2.5044 / 0.7265 / 0.1727 |
| AGS-30 / BTR-4 AGS | 1.6 | 3 | 2.6264 / 0.437 / 0.0444 |
| AGS-30 / BTR-4 AGS · gunner sight ×9 | 1.6 | 9 | 2.6264 / 0.437 / 0.0444 |
| AGS-30 (BMP-1TS) | 1.55 | 3 | 2.1921 / 0.4369 / 0.0448 |
| AGS-30 (BMP-1TS) · gunner sight ×9 | 1.55 | 9 | 2.1921 / 0.4369 / 0.0448 |
| AGS-30 (BMP-2M) | 1.55 | 1.5 | 2.15 / -0.5983 / 0.3476 |
| AGS-30 (BMP-2M) · gunner sight ×6 | 1.55 | 6 | 2.15 / -0.5983 / 0.3476 |
| SPG-9 · HEAT | 0.13 | - | 0.6443 / 1.7739 / 0.1231 |
| SPG-9 · HEAT · scope · optic (RMB ×4) | 2.34 | 4 | 0.6443 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · scope · no optic | 2.34 | - | 0.6443 / 1.7773 / 0.0546 |
| SPG-9 · FRAG | 0.13 | - | 0.6443 / 1.7739 / 0.1231 |
| SPG-9 · FRAG · scope · optic (RMB ×4) | 2.34 | 4 | 0.6443 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · scope · no optic | 2.34 | - | 0.6443 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · technical · optic (RMB ×4) | 2.34 | 4 | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · technical · no optic | 2.34 | - | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · technical · optic (RMB ×4) | 2.34 | 4 | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · technical · no optic | 2.34 | - | 2.4725 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · INS armoured technical · optic (RMB ×4) | 2.34 | 4 | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · HEAT · INS armoured technical · no optic | 2.34 | - | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · INS armoured technical · optic (RMB ×4) | 2.34 | 4 | 2.3252 / 1.7773 / 0.0546 |
| SPG-9 · FRAG · INS armoured technical · no optic | 2.34 | - | 2.3252 / 1.7773 / 0.0546 |
| 2A28 Grom (BMP-1 / BMD-1) · HEAT | 1.4 | 1.5 | 1.9452 / 1.761 / -0.0464 |
| 2A28 Grom (BMP-1) · HEAT · gunner sight ×6 | 1.4 | 6 | 1.9452 / 1.761 / -0.0464 |
| 2A28 Grom (BMP-1 technical) · HEAT · gunner sight ×6 | 1.4 | 6 | 2.3249 / 1.761 / -0.0464 |
| 2A28 Grom (BMD-1M) · HEAT | 1.57 | 1.5 | 1.7853 / 1.5748 / -0.0462 |
| 2A28 Grom (BMP-1 technical) · HEAT | 1.4 | 1.5 | 2.3249 / 1.761 / -0.0464 |
| 2A28 Grom (BMD-1M) · HEAT · gunner sight ×6 | 1.57 | 6 | 1.7853 / 1.5748 / -0.0462 |
| 2A28 Grom (BMP-1 / BMD-1) · FRAG | 1.4 | 1.5 | 1.9452 / 1.761 / -0.0464 |
| 2A28 Grom (BMP-1) · FRAG · gunner sight ×6 | 1.4 | 6 | 1.9452 / 1.761 / -0.0464 |
| 2A28 Grom (BMP-1 technical) · FRAG · gunner sight ×6 | 1.4 | 6 | 2.3249 / 1.761 / -0.0464 |
| 2A28 Grom (BMD-1M) · FRAG | 1.57 | 1.5 | 1.7853 / 1.5748 / -0.0462 |
| 2A28 Grom (BMP-1 technical) · FRAG | 1.4 | 1.5 | 2.3249 / 1.761 / -0.0464 |
| 2A28 Grom (BMD-1M) · FRAG · gunner sight ×6 | 1.57 | 6 | 1.7853 / 1.5748 / -0.0462 |
| 2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG | 0.58 | 2.5 | 2.2419 / 2.8225 / -0.0417 |
| 2A70 100mm (BMP-3) · FRAG · gunner sight ×4 | 0.575 | 4 | 2.2419 / 2.8225 / -0.0417 |
| 2A70 100mm (ZBD-04A) · FRAG | 0.95 | 2.5 | 2.1755 / 2.6772 / -0.0436 |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×4 | 0.95 | 4 | 2.1755 / 2.6772 / -0.0436 |
| 2A70 100mm (ZBD-04A) · FRAG · gunner sight ×14 | 0.95 | 14 | 2.1755 / 2.6772 / -0.0436 |
| 2A70 100mm (BMD-4M) · FRAG | 0.57 | 2.5 | 2.2868 / 2.942 / -0.0347 |
| 2A70 100mm (BMD-4M) · FRAG · gunner sight ×5 | 0.575 | 5 | 2.2868 / 2.942 / -0.0347 |
| 2A70 100mm (BMP-3 / BMD-4M) · FRAG · gunner sight ×14 | 0.575 | 14 | 2.2643 / 2.8822 / -0.0382 |
| ZiS-3 · optic (RMB ×4) | 0.4 | 4 | 0.5519 / 2.976 / 0.1652 |
| ZiS-3 · no optic | 0.4 | - | 0.5519 / 2.976 / 0.1652 |
| Tank AP · T-72 (2A46) | 0.28 | 4 | 1.5746 / 5.3227 / 0.1189 |
| Tank AP · T-90A (2A46M) | 0.28 | 4 | 1.8279 / 5.0319 / -0.0396 |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×4 | 0.29 | 4 | 2.1443 / 5.3216 / -0.0362 |
| Tank AP · Sprut-SDM1 (2A45) · gunner sight ×12 | 0.29 | 12 | 2.1443 / 5.3216 / -0.0362 |
| Tank AP · T-72 (2A46) · gunner sight ×12 | 0.28 | 12 | 1.5746 / 5.3227 / 0.1189 |
| Tank AP · T-90A (2A46M) · gunner sight ×12 | 0.28 | 12 | 1.8279 / 5.0319 / -0.0396 |
| Tank AP · T-62 (2A20) | 0.05 | 3.5 | 1.8356 / 5.1178 / -0.0127 |
| Tank AP · T-62 (2A20) · gunner sight ×7 | 0.05 | 7 | 1.8356 / 5.1178 / -0.0127 |
| Tank AP · T-64BM2 (KBA3) | 0.29 | 2.7 | 1.8422 / 5.3217 / -0.0277 |
| Tank AP · T-64BM2 (KBA3) · gunner sight ×12 | 0.29 | 12 | 1.8422 / 5.3217 / -0.0277 |
| Tank AP · ZTZ-99 (ZPT-98) | 0.1 | 4 | 1.8791 / 5.0718 / -0.0173 |
| Tank AP · ZTZ-99 (ZPT-98) · gunner sight ×12 | 0.1 | 12 | 1.8791 / 5.0718 / -0.0173 |
| Tank AP · M256 / Rh120 | 0.31 | 3 | 2.447 / 4.2328 / -0.0304 |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×6 | 0.31 | 6 | 2.447 / 4.2328 / -0.0304 |
| Tank AP · M1A1 / M1A2 (M256) · gunner sight ×12 | 0.31 | 12 | 2.447 / 4.2328 / -0.0304 |
| Tank AP · Leopard 2A6 (Rh120) | 0.25 | 3 | 2.0665 / 5.2936 / -0.0323 |
| Tank AP · Leopard 2A6 (Rh120) · gunner sight ×12 | 0.25 | 12 | 2.0665 / 5.2936 / -0.0323 |
| Tank AP · M60T (MG253) | 0.5 | - | 2.2123 / 4.2327 / -0.0444 |
| Tank AP · M60T (MG253) · gunner sight ×3 | 0.5 | 3 | 2.2123 / 4.2327 / -0.0444 |
| Tank AP · M60T (MG253) · gunner sight ×8 | 0.5 | 8 | 2.2123 / 4.2327 / -0.0444 |
| Tank AP · L30A1 (Challenger 2) / M68A2 | 0.31 | 1.5 | 2.1982 / 5.019 / -0.041 |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×4 | 0.31 | 4 | 2.1982 / 5.019 / -0.041 |
| Tank AP · Challenger 2 (L30A1) · gunner sight ×10 | 0.31 | 10 | 2.1982 / 5.019 / -0.041 |
| Tank AP · M1128 MGS (M68A2) | 0.6 | 3 | 2.6656 / 4.8496 / -0.0594 |
| Tank AP · M1128 MGS (M68A2) · gunner sight ×8 | 0.6 | 8 | 2.6656 / 4.8496 / -0.0594 |
| Tank HEAT/HE · T-72 (2A46) | 0.28 | 4 | 1.5746 / 5.3227 / 0.1189 |
| Tank HEAT/HE · T-90A (2A46M) | 0.28 | 4 | 1.8279 / 5.0319 / -0.0396 |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×4 | 0.29 | 4 | 2.1443 / 5.3216 / -0.0362 |
| Tank HEAT/HE · Sprut-SDM1 (2A45) · gunner sight ×12 | 0.29 | 12 | 2.1443 / 5.3216 / -0.0362 |
| Tank HEAT/HE · T-72 (2A46) · gunner sight ×12 | 0.28 | 12 | 1.5746 / 5.3227 / 0.1189 |
| Tank HEAT/HE · T-90A (2A46M) · gunner sight ×12 | 0.28 | 12 | 1.8279 / 5.0319 / -0.0396 |
| Tank HEAT/HE · M1A1 / M1A2 (M256) | 0.31 | 3 | 2.447 / 4.2328 / -0.0304 |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×6 | 0.31 | 6 | 2.447 / 4.2328 / -0.0304 |
| Tank HEAT/HE · M1A1 / M1A2 (M256) · gunner sight ×12 | 0.31 | 12 | 2.447 / 4.2328 / -0.0304 |
| Tank HEAT/HE · Leopard 2A6 (Rh120) | 0.25 | 3 | 2.0665 / 5.2936 / -0.0323 |
| Tank HEAT/HE · Leopard 2A6 (Rh120) · gunner sight ×12 | 0.25 | 12 | 2.0665 / 5.2936 / -0.0323 |
| Tank HEAT/HE · M1128 MGS (M68A2) | 0.6 | 3 | 2.6656 / 4.8496 / -0.0594 |
| Tank HEAT/HE · M1128 MGS (M68A2) · gunner sight ×8 | 0.6 | 8 | 2.6656 / 4.8496 / -0.0594 |
| Tank HEAT/HE · M60T (MG253) | 0.5 | - | 2.2123 / 4.2327 / -0.0444 |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×3 | 0.5 | 3 | 2.2123 / 4.2327 / -0.0444 |
| Tank HEAT/HE · M60T (MG253) · gunner sight ×8 | 0.5 | 8 | 2.2123 / 4.2327 / -0.0444 |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) | 0.1 | 4 | 1.8791 / 5.0718 / -0.0173 |
| Tank HEAT/HE · ZTZ-99 (ZPT-98) · gunner sight ×12 | 0.1 | 12 | 1.8791 / 5.0718 / -0.0173 |
| Tank HEAT/HE · T-62 (2A20) | 0.05 | 3.5 | 1.8356 / 5.1178 / -0.0127 |
| Tank HEAT/HE · T-62 (2A20) · gunner sight ×7 | 0.05 | 7 | 1.8356 / 5.1178 / -0.0127 |
| Tank HEAT/HE · T-64BM2 (KBA3) | 0.29 | 2.7 | 1.8422 / 5.3217 / -0.0277 |
| Tank HEAT/HE · T-64BM2 (KBA3) · gunner sight ×12 | 0.29 | 12 | 1.8422 / 5.3217 / -0.0277 |
| Tank HESH · L30A1 (Challenger 2) | 0.31 | 1.5 | 2.1982 / 5.019 / -0.041 |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×4 | 0.31 | 4 | 2.1982 / 5.019 / -0.041 |
| Tank HESH · Challenger 2 (L30A1) · gunner sight ×10 | 0.31 | 10 | 2.1982 / 5.019 / -0.041 |
| ZPL-98A 105mm (ZTD-05) · AP | 0.02 | 3.5 | 2.7708 / 5.5512 / -0.0109 |
| ZPL-98A 105mm (ZTD-05) · AP · gunner sight ×7 | 0.02 | 7 | 2.7708 / 5.5512 / -0.0109 |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE | 0.02 | 3.5 | 2.7708 / 5.5512 / -0.0109 |
| ZPL-98A 105mm (ZTD-05) · HEAT / HE · gunner sight ×7 | 0.02 | 7 | 2.7708 / 5.5512 / -0.0109 |
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
| MK19 | launch | the M1117's turret hangs on a socket 0.71 m above the ground while the hull's CROWS socket is 2.63 m up, so the files do not settle where the shot starts and no launch point is taken (tools/game_weapons.py leaves the M1117 out of CARRIERS); the shot starts at the ground (launch_height 0) |
| MK19 · M1117 · gunner sight ×4.5 | bore | the gunner's sight is aligned with the barrel (game files: bore 0.0), so there is nothing to apply |
| MK19 · M1117 · gunner sight ×4.5 | launch | the M1117's turret hangs on a socket 0.71 m above the ground while the hull's CROWS socket is 2.63 m up, so the files do not settle where the shot starts and no launch point is taken (tools/game_weapons.py leaves the M1117 out of CARRIERS); the shot starts at the ground (launch_height 0) |
| MK19 · AAVP-7A1 | bore | the gunner's sight is aligned with the barrel (game files: bore 0.0), so there is nothing to apply |
| MK19 · AAVP-7A1 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · AAVP-7A1 · gunner sight ×4.5 | bore | the gunner's sight is aligned with the barrel (game files: bore 0.0), so there is nothing to apply |
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
| MK19 · RHIB open turret | launch | a boat has no wheels and floats on pontoons, so the files give no ground height (tools/game_weapons.py); the shot starts at the ground (launch_height 0) |
| MK19 · RHIB open turret · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · RHIB open turret · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · RHIB open turret · no sights | launch | a boat has no wheels and floats on pontoons, so the files give no ground height (tools/game_weapons.py); the shot starts at the ground (launch_height 0) |
| MK19 · emplacement / C16 / L134A1 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| MK19 · emplacement / C16 / L134A1 · no sights | bore | normal view: the camera is on the gun axis (game files: bore 0.0), so the shot leaves along the view centre |
| MK19 · emplacement / C16 / L134A1 · no sights | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · emplacement · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · iron sights emplacement | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Technical | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Tigr | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · Safir | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · M1151 | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| AGS-17 · BTR-D | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · bunker tripod · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · CSK131 / WZ551 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · Lynx · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| QLZ87 · ZBL08 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT · scope · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · scope · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT · technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · HEAT · INS armoured technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| SPG-9 · FRAG · INS armoured technical · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| ZiS-3 · no optic | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| Tank AP · M60T (MG253) | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
| Tank HEAT/HE · M60T (MG253) | zoom | the view does not magnify (game files: zoom x1, the game's FOV is kept) |
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

Counts: 125 of 141 weapons have a bore, 97 a zoom, 137 a launch point; 16 lack a bore, 44 a zoom, 4 a launch point.

## Launch height of every vehicle

Every vehicle entry now starts the shot at its gun, not at the ground. `tools/game_weapons.py` derives the launch point from the game files for each vehicle that carries a turret (`CARRIERS`, found in the vehicle Blueprints' seat configs): the vehicle mesh's seat socket composed with the turret mesh's attach socket and the mount, over the ground. The ground is the lowest wheel bone minus the wheel's `WheelRadius` (a track's thickness is not in the files, so a tracked vehicle can stand a few centimetres higher than listed); a tripod or the ZiS-3 stands on the lowest point of its mesh bounds. Why it matters: with the barrel 2 m up, a QLZ87 aimed at 100 / 300 / 1000 m used to land at 181 / 343 / 1014 m.

- **Owner's case, the QLZ87 on the ZSL (WZ551).** `QLZ87 · CSK131 / WZ551` covers the CSK131 (2.2899 m), the WZ551B (2.5169 m, also its desert Blueprint) and the ZSD-89 (2.1196 m). The entry takes the middle, 2.3182 m; the three differ by at most 8 m at 300 m, so they are not split. The Lynx is 1.901 m and the ZBL-08 2.5044 m.
- **Entries split by height** (more than 10 m at 300 m): the T-72 / T-72A / T-72S (1.5746 m) and the T-90A (1.8279 m; Sprut-SDM1 2.1443 m already had its own entries); the BMP-1 (1.9452 m) and the BMP-1 technical (2.3249 m). The old names of the T-72 entries still work (`RENAMED_WEAPONS`).
- **Spreads kept inside one entry** (under 1 m at 300 m): the BMP-3 and BMD-4M at ×14 (2.2419 and 2.2868 m).
- **Assumed, not read:** the ZSD-89 turret mesh (used on the WZ551 and the ZSD-89) and the ZBD-04A's turret and gun are authored in vehicle space, with the root bone where the seat is. The tool takes that root as the attachment point, so on the WZ551 the turret sits on the hull's own socket for it (2.17 m over the hull origin). The ZBD-04A's gun root lies exactly at the derived pivot, which supports the rule; for the WZ551 it is inferred. A BMP-2M AGS-30 muzzle is 0.6 m behind its pivot (`muzzle_forward` is negative).
- **Evidence from the sights.** With the launch height in, the open sights of the tripod SPG-9 zero at 80 m and the T-72 AP at 708 m, round numbers a designer picks; they were 47 and 674 m without it.
- **Still at 0, and why:** the M1117 (its turret hangs on a socket 0.71 m above the ground, the hull's CROWS socket is 2.63 m up: the files do not say which is the muzzle) and the RHIB (a boat floats on pontoons). The AGS-17 emplacements keep 1 m, the value the hold model was fitted with.

## Reticle marks of the game sights

Audit of 2026-11-06 against the Squad client (build 26234431; the weapon data above are from the server package, build 26005357). The game prints its own range marks on the sight textures; the overlay draws its own mark. This table compares them for the four optics whose marks could be read. `tests/test_reticle_parity.py` pins it. No texture is stored in the repository.

**How the offsets were derived.** The widget (`W_QLZ87_YMA-87-35_Reticle`, `SPG9_HEAT_Reticle`, `SPG9_Frag_Reticle`, `W_ZiS3_Reticle`, `PAG-17_Reticle_Widget`) is a canvas image centred on the screen; its size on screen at 1080p is the slot size times the render scale (QLZ87 1000 px; SPG-9 1200 x 1.5 = 1800 px; ZiS-3 zoomed image 1285 px; PAG-17 1200 x 1071.7 px, a non-uniform stretch of the 2048 x 2048 texture), assuming a UI scale of 1 at 1080p (the widgets are laid out for 1080; the project files hold no DPI curve). The mark's row comes from the texture pixels (decoded mip 0, `QLZ-87_Reticle`, `T_SPG9_Reticles`, `T_ZiS3_Reticle`, `PAG17_Reticle`; tick centre for the QLZ87's ticks, apex of the `^` for the chevrons, so about +-4 texels = +-3 px). Offset = (row - 1024) x px per texel, positive below the centre. The overlay's offset is `mark_offset` at FOV 90 (zoomed view FOV 90 / zoom), 1920 px wide, flat ground; the last two columns are that difference and the distance by which the overlay's mark would have to move to sit on the game's mark.

| Reticle (weapon view) | Mark | Texture row | Game offset, px | Overlay offset, px | Game - overlay, px | Distance difference, m |
|---|---|---|---|---|---|---|
| QLZ87 optic | 100 m (printed 1) | 1040.5 | +8.1 | -1.5 | +9.6 | +19 |
| QLZ87 optic | 200 m (printed 2) | 1131 | +52.2 | +47.6 | +4.6 | +9 |
| QLZ87 optic | 300 m (printed 3) | 1229 | +100.1 | +96.6 | +3.5 | +7 |
| QLZ87 optic | 400 m (printed 4) | 1329.5 | +149.2 | +145.6 | +3.6 | +7 |
| QLZ87 optic | 500 m (printed 5) | 1428.5 | +197.5 | +194.7 | +2.8 | +6 |
| SPG-9 HEAT, red scale | 200 m (printed 2) | 862 | -142.4 | -148.9 | +6.5 | +25 |
| SPG-9 HEAT, red scale | 400 m (printed 4) | 908 | -102.0 | -96.4 | -5.5 | -21 |
| SPG-9 HEAT, red scale | 600 m (printed 6) | 973 | -44.8 | -44.3 | -0.6 | -2 |
| SPG-9 HEAT, red scale | 800 m (printed 8) | 1031 | +6.2 | +7.9 | -1.7 | -7 |
| SPG-9 HEAT, red scale | 1000 m (printed 10) | 1090 | +58.0 | +60.0 | -2.0 | -8 |
| SPG-9 HEAT, red scale | 1200 m (printed 12) | 1159 | +118.7 | +112.2 | +6.4 | +25 |
| SPG-9 FRAG, green scale | 200 m (printed 2) | 908 | -102.0 | -111.4 | +9.5 | +21 |
| SPG-9 FRAG, green scale | 400 m (printed 4) | 1008 | -14.1 | -20.5 | +6.5 | +14 |
| SPG-9 FRAG, green scale | 600 m (printed 6) | 1114 | +79.1 | +70.3 | +8.8 | +19 |
| SPG-9 FRAG, green scale | 800 m (printed 8) | 1220 | +172.3 | +161.2 | +11.1 | +24 |
| SPG-9 FRAG, green scale | 1000 m (printed 10) | 1323 | +262.8 | +252.3 | +10.4 | +23 |
| SPG-9 FRAG, green scale | 1200 m (printed 12) | 1427 | +354.2 | +344.0 | +10.2 | +22 |
| ZiS-3 optic | 400 m (printed 4) | 1049 | +15.7 | +2.4 | +13.3 | +133 |
| ZiS-3 optic | 700 m (printed 7) | 1083 | +37.0 | +32.2 | +4.8 | +49 |
| ZiS-3 optic | 900 m (printed 9) | 1112 | +55.2 | +51.7 | +3.5 | +36 |
| ZiS-3 optic | 1100 m (printed 11) | 1147 | +77.2 | +71.2 | +6.0 | +61 |
| ZiS-3 optic | 1300 m (printed 13) | 1175 | +94.7 | +90.7 | +4.1 | +42 |
| ZiS-3 optic | 1500 m (printed 15) | 1208 | +115.4 | +110.1 | +5.4 | +55 |
| ZiS-3 optic | 1700 m (printed 17) | 1242 | +136.8 | +129.5 | +7.3 | +75 |
| ZiS-3 optic | 1900 m (printed 19) | 1275 | +157.5 | +148.9 | +8.6 | +88 |
| ZiS-3 optic | 2100 m (printed 21) | 1307 | +177.6 | +168.4 | +9.2 | +95 |
| AGS-17 PAG-17 optic | 100 m (printed 1) | 1106 | +42.9 | +32.3 | +10.6 | +14 |
| AGS-17 PAG-17 optic | 200 m (printed 2) | 1219 | +102.0 | +108.7 | -6.7 | -9 |
| AGS-17 PAG-17 optic | 300 m (printed 3) | 1349 | +170.1 | +185.7 | -15.6 | -20 |
| AGS-17 PAG-17 optic | 400 m (printed 4) | 1489 | +243.3 | +263.5 | -20.2 | -26 |
| AGS-17 PAG-17 optic | 500 m (printed 5) | 1644 | +324.4 | +342.6 | -18.2 | -23 |
| AGS-17 PAG-17 optic | 600 m (printed 6) | 1778 | +394.6 | +423.4 | -28.8 | -35 |
| AGS-17 PAG-17 optic | 700 m (printed 7) | 1925 | +471.5 | +506.2 | -34.7 | -42 |

Fit of each reticle's marks to the overlay's physics (one scale, least squares against tan of the angle): QLZ87 3639 px/rad against 3583 for FOV 90 / 3, a design FOV of 88.7; SPG-9 HEAT 4875 (89.1), SPG-9 FRAG 4959 (87.7), ZiS-3 5056 (86.0) against 4826 for FOV 90 / 4; AGS-17 optic 2758 against 2955 (96.0). The reticles are drawn for the default FOV 90 and agree with the overlay's ballistics there. The widget code (`ExecuteUbergraph`, `Tick`) holds no FOV, and the image slots are fixed pixel sizes, so a different FOV changes the world's scale but not the reticle: the printed marks then no longer sit where the overlay's marks do (the engine-side `SQVehicleViewWidget` is native code and cannot be read here, so "the reticle never scales with the FOV" is a hypothesis; the QLZ87 and SPG-9 agreement at FOV 90 with no scale factor supports it).

**Which image is shown.** `QLZ87` and `SPG-9` are tripod weapons: they open the widget with `TryVehicleCreateOverlay(ReticleClass)` and never change `CurrentZoomIndex` (0), so the "Unzoomed" image (QLZ87 1000 px, SPG-9 1800 px) is the visible one; the "Zoomed" image (1085 px, `Collapsed`, for the QLZ87 an M2 ACOG texture) is a leftover. The numbers agree with this: the QLZ87's slope at FOV 90 is within 1.6 % at 1000 px and would be 10 % off at 1085 px. The ZiS-3 sight is a turret zoom (`ZoomLevels[1]`), the zoomed image (1285 px) is the one that matches (the 880 px image would be 31 % short).

**FOV of the zoomed view.** `BP_QLZ87_Weapon` `BlueprintOnZoom` sets `FirstPersonDriverCamera` to `GameUserSettings.FOV / 3` and restores `FOV` on release; the SPG-9, AGS-17 and the others use the same call with their divisor (`tools/game_weapons.py`). So the zoomed FOV follows the setting by division, as the overlay assumes. The QLZ87 overshoot the owner measured (about 300 m at 1000 m, FOV 120): the reticle reaches only 500 m, so it cannot show 1000 m, and the overlay mark is built from the same FOV / 3 the game sets. At 120 the reticle's 500 m mark sits 197.5 px below the centre while the world's 500 m point is 144 px below it, so a player laying the printed marks at FOV 120 overshoots (the 500 m mark lands near 650 m); this is a verified consequence of a fixed-size reticle at FOV 120. It does not explain an overshoot of the overlay's own mark. A 300 m overshoot of the overlay at 1000 m would need the game's real zoomed FOV to be about 52 degrees, not 40 (fit: the mark's 328.6 px at 1000 m is where a target at 1300 m sits at 52.4 degrees); the files do not give such a value (hypothesis, unverified; a native clamp, a different meaning of the FOV setting or ballistics beyond 500 m would each do it, and only an in-game measurement at FOV 90 and 120 separates them).

**Hand-held ADS FOV (issue 17).** Not settled: the hand-held launchers and their widgets are outside this audit, and their `SeparateAdsFov` is read by native code.

**Not covered.** The gunner sights of the tanks and IFVs (T-72A/AV/B3, T-90A, T-64BM2, T-62, M1A1/M1A2, M1128, M60T, Leopard 2A6, FV4034, ZTZ-99, ZTD-05, BMP-1/-2M/-3M, BMD-1M/-4M, ZBD-04A, BMP-1TS, BTR-4, AAVP-7A1, M1117) were not read: each texture is a multi-colour sheet of several ladders (for the T-72B3: a green and a blue chevron ladder, a cyan stadia scale) and the files do not say which ladder belongs to which ammunition (the AP, HEAT and FCS materials of one vehicle all point to the same texture with no parameter that selects a ladder; the Material graph of `M_LightBleedMaster` is cooked out), so a mark cannot be tied to a weapon view without assuming the answer. Their zoom levels also reuse one texture at 3x, 6x and 13x (Abrams) with no scale change in the widget code. The MK19 and the unzoomed views have no calibrated marks. The QLZ87's horizontal scale (0 to 60, ticks of 5) is not an angle scale of the sight (its spacing, 187 texels per 10 units, is 25 mrad at the fitted scale) and the unlabelled long tick under the first mark at row 1072.5 has no label; neither was compared.
