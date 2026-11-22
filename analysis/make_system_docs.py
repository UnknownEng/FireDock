"""
System documents: wiring diagram, bill of materials, print guide, operating sequence.
Reads output/report/checks.json (printed-part list, sizes, masses). Writes output/system/.
Run:  .venv\\Scripts\\python analysis\\make_system_docs.py
"""
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "system"
OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((ROOT / "output" / "report" / "checks.json").read_text())
DP = R["dock_params"]


# ------------------------------------------------------------------------------------------ wiring diagram
def block(ax, x, y, w, h, title, lines=(), color="#dfe9f5"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=color, ec="#33415c", lw=1.2))
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=8.6, weight="bold", color="#14213d")
    for i, s in enumerate(lines):
        ax.text(x + 0.12, y + h - 0.55 - i * 0.27, s, ha="left", va="top", fontsize=6.6, family="monospace", color="#222")


def wire(ax, pts, label="", color="#444", lw=1.4, ls="-", lpos=0.5, loff=(0, 0.1)):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=lw, ls=ls, solid_capstyle="round")
    if label:
        i = max(0, min(len(pts) - 2, int(lpos * (len(pts) - 1))))
        mx, my = (pts[i][0] + pts[i + 1][0]) / 2 + loff[0], (pts[i][1] + pts[i + 1][1]) / 2 + loff[1]
        ax.text(mx, my, label, fontsize=6.4, color=color, ha="center", va="bottom",
                bbox=dict(fc="white", ec="none", pad=0.4))


def wiring_diagram():
    fig, ax = plt.subplots(figsize=(17, 11.5), dpi=130)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 16)
    ax.axis("off")
    ax.set_title("Docker Drone - dock and on-drone charging wiring", fontsize=14, weight="bold")
    P24, P12, P5, SIG, CHG = "#c0392b", "#d35400", "#8e44ad", "#2c3e50", "#16a085"
    # power chain
    block(ax, 0.3, 13.2, 3.2, 1.9, "Mains inlet", ["IEC + switch + 5 A fuse", "230/110 V AC"], "#f6e3e1")
    block(ax, 4.2, 13.2, 3.4, 1.9, "24 V 10 A PSU", ["240 W enclosed", "+V / -V screw terminals"], "#f6e3e1")
    block(ax, 8.4, 14.0, 3.4, 1.4, "Buck 24 -> 12 V 5 A", ["cover motors"], "#fbeee0")
    block(ax, 8.4, 12.3, 3.4, 1.4, "Buck 24 -> 5 V 3 A", ["ESP32 5V/VIN"], "#f1e6f7")
    wire(ax, [(3.5, 14.1), (4.2, 14.1)], "AC", "#555")
    wire(ax, [(7.6, 14.6), (8.4, 14.6)], "24 V", P24)
    wire(ax, [(7.6, 13.5), (8.0, 13.5), (8.0, 13.0), (8.4, 13.0)], "24 V", P24, lpos=0.0)
    # controller
    block(ax, 8.2, 4.6, 5.0, 6.9, "ESP32 DevKit (controller)", [
        "GPIO25  X1 STEP     GPIO14  Y1 STEP", "GPIO26  X2 STEP     GPIO13  Y2 STEP",
        "GPIO27  X DIR       GPIO33  Y DIR", "GPIO32  EN (all, 10k pull-up)",
        "GPIO17/16  TMC UART (1k on TX)", "GPIO18/19  cover R IN1/IN2", "GPIO23/4   cover L IN1/IN2",
        "GPIO2   charge relay (HIGH=on)", "GPIO15  DS18B20 x2 (4.7k pull-up)", "GPIO21/22  I2C SDA/SCL",
        "GPIO34  E-stop (LOW=stop)", "5V/VIN <- 5 V buck, GND common", "Wi-Fi: HTTP API, X-Token"], "#e3effa")
    wire(ax, [(10.1, 12.3), (10.1, 11.5)], "5 V", P5)
    # steppers
    block(ax, 14.2, 8.4, 4.3, 3.1, "4x TMC2209", ["VM <- 24 V, VIO <- 3.3 V", "UART addr X1=0 X2=1", "         Y1=2 Y2=3",
                                                 "STEP/DIR/EN from ESP32", "450 mA push / 700 mA move"], "#e8f6ea")
    block(ax, 19.3, 8.4, 4.4, 3.1, "4x NEMA17 pushers", ["X1, X2: X pair (low bars)", "Y1, Y2: Y pair (high bars)",
                                                         "GT2 20T, 80 steps/mm", "each on its own belt"], "#e8f6ea")
    wire(ax, [(13.2, 10.3), (14.2, 10.3)], "STEP/DIR/EN/UART", SIG)
    wire(ax, [(18.5, 9.9), (19.3, 9.9)], "A+/A-/B+/B-", SIG)
    wire(ax, [(7.6, 13.9), (7.9, 13.9), (7.9, 15.6), (16.3, 15.6), (16.3, 11.5)], "24 V motor power", P24, lpos=0.6)
    # covers
    block(ax, 14.2, 4.8, 4.3, 2.9, "2x DRV8871", ["VM <- 12 V", "IN1/IN2 from ESP32", "3.6 A peak each"], "#fdf0e3")
    block(ax, 19.3, 4.8, 4.4, 2.9, "2x worm-gear motor", ["12 V, >= 7 N*m", "right + left cover hinge", "self-locking"], "#fdf0e3")
    wire(ax, [(13.2, 6.3), (14.2, 6.3)], "IN1/IN2 x2", SIG)
    wire(ax, [(18.5, 6.3), (19.3, 6.3)], "OUT1/OUT2", P12)
    wire(ax, [(11.8, 14.7), (12.6, 14.7), (12.6, 15.2), (13.7, 15.2), (13.7, 7.4), (14.2, 7.4)], "12 V", P12, lpos=0.55)
    # inputs
    block(ax, 0.3, 4.6, 6.9, 3.6, "MCP23017 (I2C 0x20) - limit switches", [
        "GPA0..3  pusher home X1 X2 Y1 Y2 (at PARK)", "GPA4/5   right cover OPEN / CLOSED",
        "GPA6/7   left cover  OPEN / CLOSED", "switches to GND, internal pull-ups", "INA226 (I2C 0x40) on the charge line",
        "DS18B20 #0 under the deck pads", "DS18B20 #1 in the electronics bay"], "#eef0f3")
    wire(ax, [(7.2, 6.5), (8.2, 6.5)], "I2C / 1-Wire", SIG)
    # charging
    block(ax, 0.3, 9.3, 3.4, 2.5, "6S CC/CV charger", ["25.2 V, 4 A", "in: 24 V", "(set CV exactly 25.20 V)"], "#e1f5f0")
    block(ax, 4.2, 9.3, 3.4, 2.5, "Relay + INA226", ["relay <- GPIO2", "10 mOhm shunt", "5 A fuse"], "#e1f5f0")
    wire(ax, [(5.9, 13.2), (5.9, 12.6), (2.0, 12.6), (2.0, 11.8)], "24 V", P24, lpos=0.5)
    wire(ax, [(3.7, 10.6), (4.2, 10.6)], "+25.2", CHG)
    block(ax, 0.3, 0.4, 7.4, 3.4, "Deck contact pads (40 x 40 copper)", [
        "pad (+X,+Y) and (-X,-Y):  CHARGE +", "pad (+X,-Y) and (-X,+Y):  CHARGE -",
        "the four feet land on the four pads after centring", "any 90-degree yaw works: the drone has an",
        "ideal-diode bridge, polarity does not matter"], "#e1f5f0")
    wire(ax, [(5.9, 9.3), (5.9, 3.8)], "+ / - to the pads", CHG, lw=2.0)
    # drone side
    block(ax, 8.2, 0.4, 15.5, 3.4, "On the drone", [
        "4 foot contacts (M4 stainless acorn nuts) -> wires up the hollow legs -> charge case under the rear",
        "-> ideal-diode bridge (LT4320, 4 MOSFETs): any polarity in, + / - out (blocks battery voltage from the feet)",
        "-> 5 A fuse -> 6S BMS charge port (BMS on the battery balance lead: cell balancing + over-voltage cut-off)",
        "-> battery. Flight power path unchanged: battery XT60 -> ESC. Charge ~1 h at 3 A.",
        "Pi 5 talks to the dock over Wi-Fi (companion/dock_client.py): /launch before take-off, /dock after landing."],
        "#fff6d8")
    wire(ax, [(7.7, 2.1), (8.2, 2.1)], "feet", CHG, lw=2.0)
    for c, lab in ((P24, "24 V"), (P12, "12 V"), (P5, "5 V"), (CHG, "charge"), (SIG, "signal")):
        pass
    leg = [plt.Line2D([], [], color=c, lw=2, label=lab) for c, lab in
           ((P24, "24 V"), (P12, "12 V"), (P5, "5 V"), (CHG, "charge path"), (SIG, "signal"))]
    ax.legend(handles=leg, loc="upper right", fontsize=8, frameon=True)
    fig.savefig(OUT / "wiring_diagram.png", facecolor="white", bbox_inches="tight")
    fig.savefig(OUT / "wiring_diagram.pdf", facecolor="white", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------------------ bill of materials
def bom_rows():
    h, e = DP["half"], DP["ext"]
    rail_len = DP["rail_end"][1] - DP["rail_end"][0]
    belt_loop = 2 * (DP["motor_end"] + DP["idler_end"]) + 3.1416 * 2 * DP["pulley_r"]
    rows = [
        # section, item, qty, spec / note
        ("Drone - electronics", "Flight controller Matek H743-SLIM V4", 1, "ArduPilot"),
        ("Drone - electronics", "4in1 ESC NewBeeDrone Hummingbird 305 80A AM32", 1, "bidirectional DShot"),
        ("Drone - electronics", "Motor iFlight XING2 2809 1250KV", 4, "M3x10 screws (6 mm printed floor)"),
        ("Drone - electronics", "Prop 7 inch tri-blade (HQProp 7x4x3 / Gemfan 7040-3)", 8, "4 + spares"),
        ("Drone - electronics", "Battery GNB 6S 3000 mAh 100C XT60", 1, "+1 spare"),
        ("Drone - electronics", "VTX RushFPV Tank Ultimate Mini + 5.8 GHz antenna", 1, ""),
        ("Drone - electronics", "FPV camera Caddx Ratel 2", 1, ""),
        ("Drone - electronics", "ELRS receiver RadioMaster RP3 V2", 1, ""),
        ("Drone - electronics", "GPS + compass Matek M10Q-5883", 1, ""),
        ("Drone - electronics", "Raspberry Pi 5 (4 GB) + official active cooler", 1, ""),
        ("Drone - electronics", "Raspberry Pi Camera Module 3 + Pi 5 ribbon (200 mm)", 1, "facing down"),
        ("Drone - electronics", "Matek mR900-30 mLRS (air) + TX kit (ground)", 1, "LoRa 900 MHz MAVLink"),
        ("Drone - electronics", "BEC 5 V 5 A", 1, "for the Pi"),
        ("Drone - charging", "Ideal-diode bridge module (LT4320 + 4 MOSFETs, >= 5 A)", 1, "polarity-independent input"),
        ("Drone - charging", "6S BMS 20 A with cell balancing", 1, "on the battery balance lead"),
        ("Drone - charging", "M4 stainless acorn (dome) nut + M4x12 screw", 4, "foot contacts"),
        ("Drone - charging", "Silicone wire 20 AWG red/black, 2 m; 5 A blade fuse + holder", 1, ""),
        ("Drone - hardware", "Alu standoff M3 x 30 mm", 4, "body"),
        ("Drone - hardware", f"Alu standoff M3 x {R['params']['standoff_len'] + R['params']['mid_t'] + R['params']['arm_t']:.0f} mm", 2, "rear body"),
        ("Drone - hardware", "Alu standoff M3 x 6 mm (F-F)", 4, "battery tray"),
        ("Drone - hardware", "Nylon standoff M2.5 x 10 / M2 x 40", 4, "Pi / GPS mast (4 each)"),
        ("Drone - hardware", "M3 x 45 (FC/ESC stack through the arms)", 4, ""),
        ("Drone - hardware", "M3 x 25 (arm clamp + leg bolts)", 16, "+ M3 nyloc nuts"),
        ("Drone - hardware", "M3 x 10 (motors), M3 x 8 (top plate, rear standoffs)", 24, "16 + 8"),
        ("Drone - hardware", "M2 x 6 (VTX, Pi camera, camera plates, GPS)", 20, ""),
        ("Drone - hardware", "M2.5 x 6 (Pi)", 8, ""),
        ("Drone - hardware", "Battery strap 20 mm x 250 mm (rubberised)", 2, ""),
        ("Dock - frame", f"2020 aluminium extrusion {2 * h:.0f} mm", 4, "top + bottom rings, along X"),
        ("Dock - frame", f"2020 aluminium extrusion {2 * h - 2 * e:.0f} mm", 5, "rings along Y + deck support"),
        ("Dock - frame", f"2020 aluminium extrusion {DP['body_h'] - 2 * e:.0f} mm", 4, "corner posts"),
        ("Dock - frame", "2020 corner brackets + M5 T-nuts + M5x10", 1, "set of ~40"),
        ("Dock - panels", f"3 mm ACM (aluminium composite) {2 * h + 6:.0f} x {DP['body_h']:.0f} mm", 4, "sides"),
        ("Dock - panels", f"3 mm ACM floor {2 * h - 40:.0f} x {2 * h - 40:.0f} mm", 1, ""),
        ("Dock - panels", f"10 mm ACM or HDPE deck {2 * h:.0f} x {2 * h:.0f} mm", 1, "white; contact + marker recesses"),
        ("Dock - covers", f"6 mm twin-wall polycarbonate, opal/white: top {DP['cover_reach']:.0f} x {2 * DP['cover_reach']:.0f}, "
                          f"side {2 * DP['cover_reach']:.0f} x {DP['cover_h']:.0f}, ends {DP['cover_reach']:.0f} x {DP['cover_h']:.0f} (x2)", 2,
         "per cover; join with 20x20 alu angle + the printed corner caps"),
        ("Dock - covers", "20 x 20 x 1.5 aluminium angle", 1, "4 m"),
        ("Dock - covers", "8 mm steel shaft 812 mm + 608 bearings + 8 mm shaft collars", 2, "4 bearings, 4 collars total"),
        ("Dock - covers", "12 V worm-gear motor >= 7 N*m (70 kg*cm), 5-10 rpm, 8 mm shaft", 2, "self-locking"),
        ("Dock - covers", "EPDM D-profile seal strip", 1, "5 m, cover edges"),
        ("Dock - centring", f"MGN12 linear rail {rail_len:.0f} mm + MGN12H carriage x2", 4, "8 carriages total"),
        ("Dock - centring", f"GT2 6 mm belt, {belt_loop / 1000 * 4 + 0.5:.1f} m total", 1, f"4 loops of ~{belt_loop:.0f} mm"),
        ("Dock - centring", "GT2 20T pulley 5 mm bore", 4, "drive"),
        ("Dock - centring", "F625ZZ flanged bearing + M5x30 bolt", 8, "idlers (2 per post)"),
        ("Dock - centring", "NEMA17 stepper 42x40 mm, >= 0.4 N*m", 4, ""),
        ("Dock - centring", "15 x 15 x 1.5 aluminium square tube 604 mm", 4, "pusher bars"),
        ("Dock - electronics", "ESP32 DevKit (WROOM-32)", 1, "firmware/dock_controller"),
        ("Dock - electronics", "TMC2209 stepper driver module (UART)", 4, ""),
        ("Dock - electronics", "DRV8871 motor driver", 2, ""),
        ("Dock - electronics", "MCP23017 I/O expander module", 1, ""),
        ("Dock - electronics", "INA226 current/voltage module (10 mOhm shunt)", 1, ""),
        ("Dock - electronics", "DS18B20 waterproof temperature probe", 2, ""),
        ("Dock - electronics", "24 V 10 A enclosed PSU", 1, ""),
        ("Dock - electronics", "Buck converter 24->12 V 5 A and 24->5 V 3 A", 1, "one of each"),
        ("Dock - electronics", "6S CC/CV charger 25.2 V 4 A (24 V input)", 1, "or a CC/CV buck-boost set to 25.20 V"),
        ("Dock - electronics", "Relay module 10 A (3.3 V logic) + 5 A fuse", 1, ""),
        ("Dock - electronics", "Micro limit switch", 8, "4 pusher home + 4 cover"),
        ("Dock - electronics", "Copper (or stainless) plate 40 x 40 x 1.5 mm", 4, "deck contact pads"),
        ("Dock - electronics", "IEC inlet with switch + fuse, cable glands, terminal blocks, 18 AWG wire", 1, ""),
        ("Dock - electronics", "Emergency-stop button (NC to GND)", 1, ""),
        ("Dock - marker", "ArUco DICT_4X4_50 id 0, 130 mm, matte vinyl", 1, "precision-landing target"),
    ]
    for p in R["print_list"]:
        rows.append(("Printed parts", p["part"], p["qty"], f"{p['material'].upper()}, {p['size_mm'][0]} x {p['size_mm'][1]} x "
                     f"{p['size_mm'][2]} mm, ~{p['mass_each_g']} g each" + (f" - {p['note']}" if p.get("note") else "")))
    return rows


def write_bom():
    rows = bom_rows()
    with open(OUT / "BOM.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Section", "Item", "Qty", "Spec / note"])
        w.writerows(rows)
    md = ["# Bill of materials", "", "Generated from the CAD model (`analysis/make_system_docs.py`). Also as `BOM.csv`.", ""]
    sec = None
    for s, item, q, note in rows:
        if s != sec:
            md += ["", f"## {s}", "| Item | Qty | Spec / note |", "|---|---|---|"]
            sec = s
        md.append(f"| {item} | {q} | {note} |")
    (OUT / "BOM.md").write_text("\n".join(md), encoding="utf-8")
    return rows


# ------------------------------------------------------------------------------------------ print guide
def write_print_guide():
    pl = R["print_list"]
    drone = [p for p in pl if not p["part"].startswith("dock_")]
    dock = [p for p in pl if p["part"].startswith("dock_")]
    tot = lambda ps: sum(p["mass_each_g"] * p["qty"] for p in ps)  # noqa: E731
    md = f"""# Print guide

All STL files in `output/print/` are already turned to their print orientation and sit on the bed (z = 0).
Every part fits a {R['checks']['print_bed_fit']['bed_mm'][0]:.0f} x {R['checks']['print_bed_fit']['bed_mm'][1]:.0f} mm bed.

## Drone frame: PA6-CF (PA-CF), about {tot(drone):.0f} g of filament
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
""" + "\n".join(f"| {p['part']} | {p['qty']} | {p['size_mm'][0]} x {p['size_mm'][1]} x {p['size_mm'][2]} | {p['mass_each_g']} |"
                for p in drone) + f"""

The antenna mount is **TPU 95A** (3 walls, 30 % infill). Print 2 spare arms and 2 spare legs: they are the parts
designed to break in a crash.

## Dock parts: PETG or ASA (outdoor), about {tot(dock):.0f} g
| Setting | Value |
|---|---|
| Walls / infill | 4 walls, 40 % gyroid |
| Layer height | 0.2-0.28 mm |
| Supports | only where the slicer asks (bar brackets, hinge arms): "support on build plate only" |
| Mirrored parts | hinge arms, motor bracket and cover corner caps: print half of them mirrored in the slicer |

| Part | Qty | Size (mm) | g each | Use |
|---|---|---|---|---|
""" + "\n".join(f"| {p['part']} | {p['qty']} | {p['size_mm'][0]} x {p['size_mm'][1]} x {p['size_mm'][2]} | {p['mass_each_g']} | {p.get('note', '')} |"
                for p in dock) + "\n"
    (OUT / "print_guide.md").write_text(md, encoding="utf-8")


# ------------------------------------------------------------------------------------------ operating sequence
def write_sequence():
    c = R["checks"]
    md = f"""# How the dock system works

## Take-off
1. The Pi (or your laptop) calls `POST /launch` on the dock (`companion/dock_client.py`).
2. The dock stops charging, opens both covers (each flips 180 deg outward and hangs beside the body, about
   12 s) and parks the pushers at {DP['park']:.0f} mm from the centre. `/status` then reports `ready_for_takeoff`.
3. The drone arms and climbs straight up. Nothing is around the props: the closest dock part is
   {c['props_to_dock_when_open']['distance_mm']} mm away and the take-off column ({2 * c['takeoff_column_half_width_mm']:.0f} mm square) is empty.

## Landing and docking
1. The mission ends with RTL to the dock. ArduPilot precision landing (PLND) follows the 130 mm ArUco marker in the
   middle of the deck, using the downward Pi Camera 3 (`companion/precision_landing.py`).
2. The pushers catch the drone if it lands within **{c['landing_capture_mm']['aligned_yaw']:.0f} mm** of the centre
   (≥ {c['landing_capture_mm']['worst_yaw_45deg']:.0f} mm at the worst 45-degree yaw).
3. After disarm the Pi calls `POST /dock`: the X pushers then the Y pushers slide the legs to the centre and
   square the yaw; the four feet end up on the four copper pads.
4. The covers close (the drone is held by the pushers while they move), then charging starts.

## Charging
* The dock's 25.2 V CC/CV charger feeds the pads through a relay and a current monitor.
* On the drone the four foot contacts go to an ideal-diode bridge (any polarity, so any of the four square
  yaws works), a fuse and a 6S BMS that balances the cells.
* The controller stops charging when the current falls below 0.3 A (full), above 45 °C, above 25.4 V,
  after 2 h, or if no current flows (feet not on the pads).

## Safety interlocks (firmware)
* The covers never move while the pushers move, and the reverse.
* Every motion has a timeout; the e-stop button or `POST /stop` switches all motors and charging off.
* After any fault the pushers re-home before anything else moves.

## HTTP API (header `X-Token`)
| Call | Does |
|---|---|
| `GET /status` | JSON: cover, pusher, charge state, volts, amps, temperatures, ready_for_takeoff |
| `POST /launch` | stop charge, open, park pushers |
| `POST /dock` | centre, close, charge |
| `POST /open`, `/close`, `/center`, `/release` | single steps |
| `POST /charge/start`, `/charge/stop`, `/home`, `/stop`, `/reset` | |
"""
    (OUT / "operation_sequence.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    wiring_diagram()
    rows = write_bom()
    write_print_guide()
    write_sequence()
    print(f"wrote {OUT}: wiring_diagram.png/pdf, BOM.csv/md ({len(rows)} lines), print_guide.md, operation_sequence.md")
