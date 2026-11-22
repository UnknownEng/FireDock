# Bill of materials

Generated from the CAD model (`analysis/make_system_docs.py`). Also as `BOM.csv`.


## Drone - electronics
| Item | Qty | Spec / note |
|---|---|---|
| Flight controller Matek H743-SLIM V4 | 1 | ArduPilot |
| 4in1 ESC NewBeeDrone Hummingbird 305 80A AM32 | 1 | bidirectional DShot |
| Motor iFlight XING2 2809 1250KV | 4 | M3x10 screws (6 mm printed floor) |
| Prop 7 inch tri-blade (HQProp 7x4x3 / Gemfan 7040-3) | 8 | 4 + spares |
| Battery GNB 6S 3000 mAh 100C XT60 | 1 | +1 spare |
| VTX RushFPV Tank Ultimate Mini + 5.8 GHz antenna | 1 |  |
| FPV camera Caddx Ratel 2 | 1 |  |
| ELRS receiver RadioMaster RP3 V2 | 1 |  |
| GPS + compass Matek M10Q-5883 | 1 |  |
| Raspberry Pi 5 (4 GB) + official active cooler | 1 |  |
| Raspberry Pi Camera Module 3 + Pi 5 ribbon (200 mm) | 1 | facing down |
| Matek mR900-30 mLRS (air) + TX kit (ground) | 1 | LoRa 900 MHz MAVLink |
| BEC 5 V 5 A | 1 | for the Pi |

## Drone - charging
| Item | Qty | Spec / note |
|---|---|---|
| Ideal-diode bridge module (LT4320 + 4 MOSFETs, >= 5 A) | 1 | polarity-independent input |
| 6S BMS 20 A with cell balancing | 1 | on the battery balance lead |
| M4 stainless acorn (dome) nut + M4x12 screw | 4 | foot contacts |
| Silicone wire 20 AWG red/black, 2 m; 5 A blade fuse + holder | 1 |  |

## Drone - hardware
| Item | Qty | Spec / note |
|---|---|---|
| Alu standoff M3 x 30 mm | 4 | body |
| Alu standoff M3 x 48 mm | 2 | rear body |
| Alu standoff M3 x 6 mm (F-F) | 4 | battery tray |
| Nylon standoff M2.5 x 10 / M2 x 40 | 4 | Pi / GPS mast (4 each) |
| M3 x 45 (FC/ESC stack through the arms) | 4 |  |
| M3 x 25 (arm clamp + leg bolts) | 16 | + M3 nyloc nuts |
| M3 x 10 (motors), M3 x 8 (top plate, rear standoffs) | 24 | 16 + 8 |
| M2 x 6 (VTX, Pi camera, camera plates, GPS) | 20 |  |
| M2.5 x 6 (Pi) | 8 |  |
| Battery strap 20 mm x 250 mm (rubberised) | 2 |  |

## Dock - frame
| Item | Qty | Spec / note |
|---|---|---|
| 2020 aluminium extrusion 730 mm | 4 | top + bottom rings, along X |
| 2020 aluminium extrusion 690 mm | 5 | rings along Y + deck support |
| 2020 aluminium extrusion 260 mm | 4 | corner posts |
| 2020 corner brackets + M5 T-nuts + M5x10 | 1 | set of ~40 |

## Dock - panels
| Item | Qty | Spec / note |
|---|---|---|
| 3 mm ACM (aluminium composite) 736 x 300 mm | 4 | sides |
| 3 mm ACM floor 690 x 690 mm | 1 |  |
| 10 mm ACM or HDPE deck 730 x 730 mm | 1 | white; contact + marker recesses |

## Dock - covers
| Item | Qty | Spec / note |
|---|---|---|
| 6 mm twin-wall polycarbonate, opal/white: top 385 x 770, side 770 x 255, ends 385 x 255 (x2) | 2 | per cover; join with 20x20 alu angle + the printed corner caps |
| 20 x 20 x 1.5 aluminium angle | 1 | 4 m |
| 8 mm steel shaft 812 mm + 608 bearings + 8 mm shaft collars | 2 | 4 bearings, 4 collars total |
| 12 V worm-gear motor >= 7 N*m (70 kg*cm), 5-10 rpm, 8 mm shaft | 2 | self-locking |
| EPDM D-profile seal strip | 1 | 5 m, cover edges |

## Dock - centring
| Item | Qty | Spec / note |
|---|---|---|
| MGN12 linear rail 610 mm + MGN12H carriage x2 | 4 | 8 carriages total |
| GT2 6 mm belt, 5.5 m total | 1 | 4 loops of ~1260 mm |
| GT2 20T pulley 5 mm bore | 4 | drive |
| F625ZZ flanged bearing + M5x30 bolt | 8 | idlers (2 per post) |
| NEMA17 stepper 42x40 mm, >= 0.4 N*m | 4 |  |
| 15 x 15 x 1.5 aluminium square tube 604 mm | 4 | pusher bars |

## Dock - electronics
| Item | Qty | Spec / note |
|---|---|---|
| ESP32 DevKit (WROOM-32) | 1 | firmware/dock_controller |
| TMC2209 stepper driver module (UART) | 4 |  |
| DRV8871 motor driver | 2 |  |
| MCP23017 I/O expander module | 1 |  |
| INA226 current/voltage module (10 mOhm shunt) | 1 |  |
| DS18B20 waterproof temperature probe | 2 |  |
| 24 V 10 A enclosed PSU | 1 |  |
| Buck converter 24->12 V 5 A and 24->5 V 3 A | 1 | one of each |
| 6S CC/CV charger 25.2 V 4 A (24 V input) | 1 | or a CC/CV buck-boost set to 25.20 V |
| Relay module 10 A (3.3 V logic) + 5 A fuse | 1 |  |
| Micro limit switch | 8 | 4 pusher home + 4 cover |
| Copper (or stainless) plate 40 x 40 x 1.5 mm | 4 | deck contact pads |
| IEC inlet with switch + fuse, cable glands, terminal blocks, 18 AWG wire | 1 |  |
| Emergency-stop button (NC to GND) | 1 |  |

## Dock - marker
| Item | Qty | Spec / note |
|---|---|---|
| ArUco DICT_4X4_50 id 0, 130 mm, matte vinyl | 1 | precision-landing target |

## Printed parts
| Item | Qty | Spec / note |
|---|---|---|
| bottom_plate | 1 | PA_CF, 160.0 x 84.0 x 4.0 mm, ~44.3 g each |
| arm | 4 | PA_CF, 164.0 x 36.0 x 14.0 mm, ~35.6 g each |
| mid_plate | 1 | PA_CF, 80.0 x 80.0 x 4.0 mm, ~23.8 g each |
| top_plate | 1 | PA_CF, 160.0 x 84.0 x 4.0 mm, ~44.6 g each |
| camera_plate | 2 | PA_CF, 22.0 x 56.0 x 3.0 mm, ~3.3 g each |
| battery_tray | 1 | PA_CF, 60.0 x 126.0 x 3.0 mm, ~20.8 g each |
| gps_plate | 1 | PA_CF, 34.0 x 42.0 x 3.0 mm, ~4.0 g each |
| landing_leg | 4 | PA_CF, 30.0 x 14.1 x 49.0 mm, ~5.6 g each |
| foot | 4 | PA_CF, 16.0 x 16.0 x 6.0 mm, ~0.8 g each |
| charge_case | 1 | PA_CF, 40.0 x 58.0 x 14.0 mm, ~8.1 g each |
| antenna_mount | 1 | TPU, 12.0 x 32.0 x 14.0 mm, ~3.6 g each |
| dock_bar_bracket_low_inner | 2 | PETG, 45.4 x 50.1 x 21.0 mm, ~11.2 g each - X pusher end, -X bar (inner belt run) |
| dock_bar_bracket_low_outer | 2 | PETG, 45.4 x 63.4 x 21.0 mm, ~11.7 g each - X pusher end, +X bar (outer belt run) |
| dock_bar_bracket_high_inner | 2 | PETG, 45.4 x 50.1 x 40.0 mm, ~14.7 g each - Y pusher end, -Y bar |
| dock_bar_bracket_high_outer | 2 | PETG, 45.4 x 63.4 x 40.0 mm, ~15.2 g each - Y pusher end, +Y bar |
| dock_stepper_bracket | 4 | PETG, 46.3 x 46.3 x 22.0 mm, ~12.3 g each - NEMA17 above each drive pulley |
| dock_idler_post | 4 | PETG, 24.0 x 22.0 x 24.0 mm, ~5.0 g each - belt idler: 2x F625 flanged bearings on M5 |
| dock_hinge_arm | 4 | PETG, 49.0 x 83.0 x 10.0 mm, ~27.9 g each - cover to hinge shaft (print 2, and 2 mirrored) |
| dock_bearing_block | 4 | PETG, 45.0 x 44.0 x 20.0 mm, ~27.2 g each - 608 pillow block on the body side |
| dock_coupler | 2 | PETG, 20.0 x 20.0 x 15.0 mm, ~3.0 g each - worm motor to hinge shaft |
| dock_motor_bracket | 2 | PETG, 122.0 x 112.0 x 105.0 mm, ~121.9 g each - worm motor mount (print 1, and 1 mirrored) |
| dock_cover_corner | 4 | PETG, 43.0 x 43.0 x 43.0 mm, ~11.8 g each - corner cap of the cover panels (print 2, and 2 mirrored) |