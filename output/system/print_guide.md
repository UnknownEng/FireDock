# Print guide

All STL files in `output/print/` are already turned to their print orientation and sit on the bed (z = 0).
Every part fits a 256 x 256 mm bed.

## Drone frame: PA6-CF (PA-CF), about 324 g of filament
| Setting | Value |
|---|---|
| Nozzle | 0.4 or 0.6 mm **hardened steel** (carbon fibre wears brass) |
| Filament | dry it first: 80 °C for 8-12 h, print from a dry box |
| Layer height | 0.2 mm |
| Walls | **6** (2.4 mm) |
| Top / bottom | 6 layers |
| Infill | 50 % gyroid (arms 60 %) |
| Bed / chamber | enclosed printer, bed 80-100 °C, chamber warm |
| Orientation | as in the STL: arms upside down (motor face on the bed), legs flange down, plates flat |
| After printing | optional anneal 80-100 °C for 4-6 h (stiffer, more heat resistant) |
| Inserts / bolts | through-bolts with nyloc nuts everywhere; do not overtighten into PA-CF |

| Part | Qty | Size (mm) | g each |
|---|---|---|---|
| bottom_plate | 1 | 160.0 x 84.0 x 4.0 | 44.3 |
| arm | 4 | 164.0 x 36.0 x 14.0 | 35.6 |
| mid_plate | 1 | 80.0 x 80.0 x 4.0 | 23.8 |
| top_plate | 1 | 160.0 x 84.0 x 4.0 | 44.6 |
| camera_plate | 2 | 22.0 x 56.0 x 3.0 | 3.3 |
| battery_tray | 1 | 60.0 x 126.0 x 3.0 | 20.8 |
| gps_plate | 1 | 34.0 x 42.0 x 3.0 | 4.0 |
| landing_leg | 4 | 30.0 x 14.1 x 49.0 | 5.6 |
| foot | 4 | 16.0 x 16.0 x 6.0 | 0.8 |
| charge_case | 1 | 40.0 x 58.0 x 14.0 | 8.1 |
| antenna_mount | 1 | 12.0 x 32.0 x 14.0 | 3.6 |

The antenna mount is **TPU 95A** (3 walls, 30 % infill). Print 2 spare arms and 2 spare legs: they are the parts
designed to break in a crash.

## Dock parts: PETG or ASA (outdoor), about 692 g
| Setting | Value |
|---|---|
| Walls / infill | 4 walls, 40 % gyroid |
| Layer height | 0.2-0.28 mm |
| Supports | only where the slicer asks (bar brackets, hinge arms): "support on build plate only" |
| Mirrored parts | hinge arms, motor bracket and cover corner caps: print half of them mirrored in the slicer |

| Part | Qty | Size (mm) | g each | Use |
|---|---|---|---|---|
| dock_bar_bracket_low_inner | 2 | 45.4 x 50.1 x 21.0 | 11.2 | X pusher end, -X bar (inner belt run) |
| dock_bar_bracket_low_outer | 2 | 45.4 x 63.4 x 21.0 | 11.7 | X pusher end, +X bar (outer belt run) |
| dock_bar_bracket_high_inner | 2 | 45.4 x 50.1 x 40.0 | 14.7 | Y pusher end, -Y bar |
| dock_bar_bracket_high_outer | 2 | 45.4 x 63.4 x 40.0 | 15.2 | Y pusher end, +Y bar |
| dock_stepper_bracket | 4 | 46.3 x 46.3 x 22.0 | 12.3 | NEMA17 above each drive pulley |
| dock_idler_post | 4 | 24.0 x 22.0 x 24.0 | 5.0 | belt idler: 2x F625 flanged bearings on M5 |
| dock_hinge_arm | 4 | 49.0 x 83.0 x 10.0 | 27.9 | cover to hinge shaft (print 2, and 2 mirrored) |
| dock_bearing_block | 4 | 45.0 x 44.0 x 20.0 | 27.2 | 608 pillow block on the body side |
| dock_coupler | 2 | 20.0 x 20.0 x 15.0 | 3.0 | worm motor to hinge shaft |
| dock_motor_bracket | 2 | 122.0 x 112.0 x 105.0 | 121.9 | worm motor mount (print 1, and 1 mirrored) |
| dock_cover_corner | 4 | 43.0 x 43.0 x 43.0 | 11.8 | corner cap of the cover panels (print 2, and 2 mirrored) |
