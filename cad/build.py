"""
Parametric 7-inch autonomous FPV drone frame + drone dock (box with clam-shell lid).

Electronics layout (bottom -> top):
    under bottom plate : battery tray + 6S battery, downward Raspberry Pi camera (precision landing)
    between plates     : FC + 4in1 ESC stack (30.5x30.5), FPV camera (front, 19 mm micro),
                         VTX (rear, 20x20), ELRS receiver (rear, on clamp plate),
                         telemetry radio (rear, hung under top plate)
    top deck           : Raspberry Pi 4/5 (or Zero 2 W) on 10 mm standoffs, 5 V 5 A BEC under it,
                         GPS + compass on a 40 mm mast at the rear
    rear               : TPU antenna mount (VTX SMA + ELRS antenna tubes)
    arms               : 4 replaceable 6 mm carbon arms, printed landing legs with TPU feet

Run from the project folder:
    .venv\\Scripts\\python cad\\build.py

Outputs (./output): parts/*.step|stl|igs, dxf/*.dxf, svg/*.svg, assembly/*.step|glb|stl,
report/checks.json. Units: mm. Axes: X forward, Y left, Z up, origin = centre of the
frame at the bottom face of the bottom plate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq
from cadquery.selectors import AndSelector, BoxSelector, ParallelDirSelector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
V = cq.Vector
L = cq.Location

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
P = dict(
    wheelbase=320.0,          # motor-to-motor diagonal
    prop_d=177.8,             # 7 inch
    # long hexagonal body plates (stay clear of the prop discs)
    plate_outline=[(80, -22), (80, 22), (42, 42), (-42, 42), (-80, 22), (-80, -22), (-42, -42), (42, -42)],
    plate_corner_r=8.0,
    # every frame part is 3D printed in PA-CF (nylon + carbon fibre); a printed arm has to be ~2.3x taller than
    # a 6 mm carbon arm to get the same bending stiffness (E ~4.5 GPa printed vs 55 GPa carbon plate)
    material="pa_cf",
    bottom_t=4.0,
    arm_t=14.0,               # arm height (printed upside down, motor face on the bed)
    arm_floor=6.0,            # material left under the motor; the pad is pocketed from below
    arm_pocket_d=28.0,
    mid_t=4.0,
    top_t=4.0,
    mid_size=80.0,            # arm clamp plate (square), also the floor for ESC/FC/RX
    mid_r=8.0,
    arm_start=14.0,
    arm_w_root=18.0,
    arm_w_tip=14.0,
    motor_pad_d=36.0,
    arm_bolts=(21.57, 32.0, 46.0),  # 21.57 = 30.5x30.5 stack hole on the diagonal
    leg_at=130.0,             # landing leg centre along arm
    leg_bolt_off=11.0,        # leg bolts at leg_at +/- this
    leg_len=49.0,             # printed leg (PA-CF), hollow for the charging wire
    foot_h=6.0,               # printed foot cap
    contact_h=3.0,            # M4 stainless acorn nut under each foot = charging contact
    standoff_len=30.0,        # body height (stack + VTX + radio space)
    standoff_af=5.0,          # hex across flats
    rear_standoff=(-66.0, 20.0),
    cam_plate_t=3.0,
    cam_plate_y=10.0,         # inner face -> 20 mm bay for 19 mm micro cameras
    cam_x=(56.0, 78.0),
    cam_tab_x=(61.0, 73.0),
    # battery: GNB 6S 3000 mAh 100C LiPo, 138 x 44 x 32 mm, 418 g (slung under a carbon tray)
    # mounted CROSSWISE (long side along Y): centred CG and a clear view for the down camera
    battery=(138.0, 44.0, 32.0),
    battery_cx=0.0,
    battery_mah=3000,
    tray=(60.0, 126.0, 3.0),  # X x Y x thickness
    tray_cx=0.0,
    tray_gap=6.0,
    # tray standoffs sit on the 32 mm arm bolts -> one bolt clamps tray, plate, arm and clamp plate
    tray_standoffs=[(22.63, 22.63), (22.63, -22.63), (-22.63, 22.63), (-22.63, -22.63)],
    tray_strap_x=24.6,        # strap slots just outside the battery faces
    tray_strap_y=(45.0, -45.0),
    # motor: iFlight XING2 2809 1250KV, 35.3 mm dia x 21.7 mm body, 19x19 M3, 60.7 g
    motor_d=35.3,
    motor_h=21.7,
    # top deck
    rpi_x=(-36.0, 49.0),      # Pi 4/5 board 85 x 56
    rpi_standoff=10.0,
    gps_mast=40.0,
    gps_plate_t=3.0,
    gps_holes=[(-50, 17), (-50, -17), (-72, 17), (-72, -17)],
    # charging module (ideal-diode bridge + 6S BMS) in a printed case under the rear of the bottom plate
    charge_case=(-72.0, -32.0, 23.0, 14.0),   # x0, x1, half-width y, depth
    charge_case_holes=[(-40.0, 26.0), (-40.0, -26.0), (-64.0, 26.0), (-64.0, -26.0)],
    bed=(256.0, 256.0, 256.0),                # printer build volume
)

R = P["wheelbase"] / 2.0
Z_ARM = P["bottom_t"]
Z_MID = Z_ARM + P["arm_t"]
Z_STAND = Z_MID + P["mid_t"]
Z_TOP = Z_STAND + P["standoff_len"]
Z_DECK = Z_TOP + P["top_t"]
REAR_STANDOFF_LEN = Z_TOP - Z_ARM
LEG_BOTTOM = Z_ARM - P["leg_len"] - P["foot_h"] - P["contact_h"]   # bottom of the contact domes
ARM_ANGLES = (45.0, 135.0, 225.0, 315.0)
RPI_HOLES_X = (P["rpi_x"][0] + 3.5, P["rpi_x"][0] + 61.5)
RPI45_HOLES = [(x, y) for x in RPI_HOLES_X for y in (24.5, -24.5)]      # Pi 4 / Pi 5
RPI_ZERO_HOLES = [(x, y) for x in RPI_HOLES_X for y in (11.5, -11.5)]  # Pi Zero 2 W
DOWNCAM_C = (66.0, 0.0)
RIBBON_X = 51.0
VTX_C = (-57.0, 0.0)

DENSITY = {"carbon": 1.55e-3, "al7075": 2.81e-3, "tpu": 1.21e-3, "pa_cf": 1.20e-3, "nylon": 1.14e-3,
           "petg": 1.27e-3, "steel": 7.9e-3, "al6063": 2.70e-3}
# printed parts are not solid: 6 walls + 50 % gyroid infill comes out at about 80 % of solid mass
PRINT_FILL = {"pa_cf": 0.80, "tpu": 0.70, "petg": 0.60}
PRINTED = set(PRINT_FILL)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def rounded_plate(length, width, radius, thickness):
    return (cq.Workplane("XY").box(length, width, thickness, centered=(True, True, False))
            .edges("|Z").fillet(radius))


def body_plate(thickness):
    return (cq.Workplane("XY").polyline(P["plate_outline"]).close().extrude(thickness)
            .edges("|Z").fillet(P["plate_corner_r"]))


def drill(wp, points, dia):
    if not points:
        return wp
    return wp.cut(cq.Workplane("XY").pushPoints(points).circle(dia / 2).extrude(500, both=True))


def cut_rects(wp, rects):
    """rects: list of (cx, cy, sx, sy)"""
    for cx, cy, sx, sy in rects:
        wp = wp.cut(cq.Workplane("XY").center(cx, cy).rect(sx, sy).extrude(500, both=True))
    return wp


def polar(d, ang_deg):
    a = math.radians(ang_deg)
    return (d * math.cos(a), d * math.sin(a))


def arm_bolt_points():
    return [polar(d, a) for a in ARM_ANGLES for d in P["arm_bolts"]]


def standoff_points():
    d = P["arm_bolts"][-1]
    rx, ry = P["rear_standoff"]
    return [polar(d, a) for a in ARM_ANGLES], [(rx, ry), (rx, -ry)]


def cam_slots():
    x0, x1 = P["cam_tab_x"]
    yc = P["cam_plate_y"] + P["cam_plate_t"] / 2
    return [((x0 + x1) / 2, s * yc, (x1 - x0) + 0.2, P["cam_plate_t"] + 0.2) for s in (1, -1)]


def arm_width(d):
    s, wr, wt = P["arm_start"], P["arm_w_root"], P["arm_w_tip"]
    return wr - (wr - wt) * (d - s) / (R - s)


def leg_bolts():
    return (P["leg_at"] - P["leg_bolt_off"], P["leg_at"] + P["leg_bolt_off"])


def box_at(sx, sy, sz, x0, y0, z0):
    """axis-aligned box from its min corner"""
    return cq.Workplane("XY").box(sx, sy, sz, centered=False).translate((x0, y0, z0))


# --------------------------------------------------------------------------
# Frame parts (each modelled flat in its own XY plane, thickness along +Z)
# --------------------------------------------------------------------------

def make_bottom_plate():
    p = body_plate(P["bottom_t"])
    p = drill(p, arm_bolt_points(), 3.2)
    p = drill(p, standoff_points()[1], 3.2)
    p = drill(p, P["tray_standoffs"], 3.2)                                       # battery tray
    p = drill(p, [(VTX_C[0] + dx, dy) for dx in (-10, 10) for dy in (-10, 10)], 2.2)  # VTX 20x20 M2
    p = drill(p, [(DOWNCAM_C[0] + dx, dy) for dx in (-10.5, 10.5) for dy in (-6.25, 6.25)], 2.2)  # Pi cam M2
    p = drill(p, [(-77.0, 12.0), (-77.0, -12.0)], 3.2)                          # antenna mount
    p = drill(p, P["charge_case_holes"], 3.2)                                   # charging module case
    p = cut_rects(p, [(-52.0, 0.0, 10.0, 4.0)])                                 # charge wires up to the battery lead
    p = cut_rects(p, cam_slots())
    p = cut_rects(p, [(RIBBON_X, 0.0, 2.5, 18.0)])                              # Pi camera ribbon
    return p


def make_arm():
    s, t = P["arm_start"], P["arm_t"]
    wr, wt = P["arm_w_root"] / 2, P["arm_w_tip"] / 2
    arm = (cq.Workplane("XY").polyline([(s, -wr), (R, -wt), (R, wt), (s, wr)]).close().extrude(t)
           .union(cq.Workplane("XY").center(R, 0).circle(P["motor_pad_d"] / 2).extrude(t)))
    try:
        arm = arm.edges(AndSelector(ParallelDirSelector(V(0, 0, 1)),
                                    BoxSelector((s - 1, -20, -1), (s + 1, 20, t + 1)))).fillet(4.0)
    except Exception:
        pass
    xj = R - math.sqrt((P["motor_pad_d"] / 2) ** 2 - wt ** 2)
    try:
        arm = arm.edges(AndSelector(ParallelDirSelector(V(0, 0, 1)),
                                    BoxSelector((xj - 2, -12, -1), (xj + 2, 12, t + 1)))).fillet(6.0)
    except Exception:
        pass
    arm = drill(arm, [(d, 0.0) for d in P["arm_bolts"] + leg_bolts()], 3.2)
    m16 = [(R + 8 * math.sqrt(2) * math.cos(math.radians(a)), 8 * math.sqrt(2) * math.sin(math.radians(a)))
           for a in (45, 135, 225, 315)]
    m19 = [(R + 9.5 * math.sqrt(2) * math.cos(math.radians(a)), 9.5 * math.sqrt(2) * math.sin(math.radians(a)))
           for a in (0, 90, 180, 270)]
    arm = drill(arm, m16 + m19, 3.2)
    arm = drill(arm, [(R, 0.0)], 8.5)
    # pocket under the motor pad: leaves arm_floor under the motor so M3x10 motor screws reach from below.
    # Printed upside down (motor face on the bed) the pocket opens upward, so it needs no support.
    pocket = cq.Workplane("XY").center(R, 0).circle(P["arm_pocket_d"] / 2).extrude(P["arm_t"] - P["arm_floor"])
    return arm.cut(pocket)


def make_mid_plate():
    p = rounded_plate(P["mid_size"], P["mid_size"], P["mid_r"], P["mid_t"])
    p = drill(p, arm_bolt_points(), 3.2)
    p = cut_rects(p, [(-30.0, 0.0, 4.0, 14.0)])  # zip-tie / wire pass for the ELRS receiver
    return p


def make_top_plate():
    p = body_plate(P["top_t"])
    diag, rear = standoff_points()
    p = drill(p, diag + rear, 3.2)
    p = drill(p, RPI45_HOLES + RPI_ZERO_HOLES, 2.7)          # M2.5
    p = drill(p, P["gps_holes"], 2.2)                         # M2 GPS mast
    p = cut_rects(p, cam_slots())
    p = cut_rects(p, [(RIBBON_X, 0.0, 2.5, 18.0)])            # Pi camera ribbon
    # zip-tie slots that hold the LoRa telemetry radio under the plate
    p = cut_rects(p, [(x, y, 3.5, 1.8) for x in (-52.0, -71.0) for y in (12.5, -12.5)])
    # BEC zip-tie slots under the Pi
    p = cut_rects(p, [(x, y, 1.8, 3.5) for x in (3.0, 20.0) for y in (11.5, -11.5)])
    return p


def make_cam_plate():
    """Flat in XY where local Y = drone Z. Tabs lock into the bottom & top plates."""
    x0, x1 = P["cam_x"]
    tx0, tx1 = P["cam_tab_x"]
    t = P["cam_plate_t"]
    p = (box_at(x1 - x0, Z_TOP - Z_ARM, t, x0, Z_ARM, 0)
         .union(box_at(tx1 - tx0, Z_ARM, t, tx0, 0, 0))
         .union(box_at(tx1 - tx0, P["top_t"], t, tx0, Z_TOP, 0)))
    try:
        p = p.edges(AndSelector(ParallelDirSelector(V(0, 0, 1)),
                                BoxSelector((x1 - 1, Z_ARM - 1, -1), (x1 + 1, Z_TOP + 1, t + 1)))).fillet(3.0)
    except Exception:
        pass
    pivot = ((x0 + x1) / 2, (Z_ARM + Z_TOP) / 2)
    locks = [(pivot[0] - 8 * math.cos(math.radians(a)), pivot[1] + 8 * math.sin(math.radians(a))) for a in (0, 25, 50)]
    return drill(p, [pivot] + locks, 2.2)


def make_tray():
    """Modelled in frame coordinates (offset to tray_cx) so the holes line up with the bottom plate."""
    lx, ly, t = P["tray"]
    p = rounded_plate(lx, ly, 6.0, t).translate((P["tray_cx"], 0, 0))
    p = drill(p, P["tray_standoffs"], 3.2)
    sx = P["tray_strap_x"]
    return cut_rects(p, [(x, y, 3.2, 22.0) for x in (sx, -sx) for y in P["tray_strap_y"]])  # 20 mm straps


def make_hex_standoff(length, af, hole):
    circ = af / math.cos(math.radians(30))
    return drill(cq.Workplane("XY").polygon(6, circ).extrude(length), [(0, 0)], hole)


def make_leg():
    """Local: arm axis = X, top face of the flange at z=0, leg hangs down. Printed in PA-CF, flange on the bed.
    Hollow: the charging wire runs from the foot contact up the leg and out of the side under the arm."""
    off = P["leg_bolt_off"]
    flange = cq.Workplane("XY").box(2 * off + 8, 14, 4, centered=(True, True, False)).translate((0, 0, -4))
    flange = flange.edges("|Z").fillet(3.0)
    column = (cq.Workplane("XY").workplane(offset=-4).circle(7)
              .workplane(offset=-(P["leg_len"] - 4)).circle(5).loft())
    leg = flange.union(column)
    leg = leg.cut(cq.Workplane("XY").pushPoints([(-off, 0), (off, 0)]).circle(1.6).extrude(-4))
    leg = leg.cut(cq.Workplane("XY").circle(2.3).extrude(-P["leg_len"] - 1))            # wire / M4 screw channel
    return leg.cut(cq.Workplane("XZ").center(-4.0, -9.0).circle(2.0).extrude(-10))       # wire exit, inner side


def make_foot():
    """Printed cap glued over the leg end; an M4 screw through it holds the stainless acorn-nut contact."""
    h = P["foot_h"]
    cap = cq.Workplane("XY").circle(8.0).extrude(h).faces("<Z").edges().fillet(2.0)
    cap = cap.cut(cq.Workplane("XY").workplane(offset=h - 4).circle(5.15).extrude(4))   # socket for the leg end
    return cap.cut(cq.Workplane("XY").circle(2.2).extrude(h))                            # M4 screw


def make_charge_case():
    """Open-top printed case for the charging electronics, screwed under the rear of the bottom plate.
    Modelled in frame coordinates; its open side touches the plate, so it prints open side up with no support."""
    x0, x1, hy, d = P["charge_case"]
    case = box_at(x1 - x0, 2 * hy, d, x0, -hy, -d).edges("|Z").fillet(3.0)
    case = case.cut(box_at(x1 - x0 - 4, 2 * hy - 4, d - 2, x0 + 2, -hy + 2, -d + 2))
    ears = box_at(32.0, 2 * hy + 12, 3.0, (x0 + x1) / 2 - 16, -hy - 6, -3.0).edges("|Z").fillet(2.0)
    case = case.union(ears)
    case = case.cut(box_at(x1 - x0 - 4, 2 * hy - 4, 3.0, x0 + 2, -hy + 2, -3.0))
    case = drill(case, P["charge_case_holes"], 3.2)
    for y in (10.0, -10.0):                                               # wire entries from the 4 legs (front wall)
        case = case.cut(cq.Workplane("YZ").center(y, -d / 2).circle(3.0).extrude(10).translate((x1 - 5, 0, 0)))
    return case


def make_gps_plate():
    p = rounded_plate(34.0, 42.0, 4.0, P["gps_plate_t"])
    return drill(p, [(dx, dy) for dx in (-11, 11) for dy in (-17, 17)], 2.2)


def make_antenna_mount():
    """TPU block on the rear of the bottom plate: VTX SMA bulkhead + 2 ELRS antenna tubes."""
    m = box_at(12, 32, 14, -84, -16, Z_ARM).edges("|Z").fillet(3.0)
    m = drill(m, [(-77.0, 12.0), (-77.0, -12.0)], 3.2)
    holes = [
        cq.Solid.makeCylinder(3.25, 60, V(-78, 0, 12) - V(-0.5, 0, -0.866) * 30, V(-0.5, 0, -0.866)),
        cq.Solid.makeCylinder(1.6, 60, V(-78, 6, 10) - V(-0.45, 0.55, -0.7).normalized() * 30,
                              V(-0.45, 0.55, -0.7).normalized()),
        cq.Solid.makeCylinder(1.6, 60, V(-78, -6, 10) - V(-0.45, -0.55, -0.7).normalized() * 30,
                              V(-0.45, -0.55, -0.7).normalized()),
    ]
    for h in holes:
        m = m.cut(cq.Workplane().add(h))
    return m


# --------------------------------------------------------------------------
# Reference (bought) components - real dimensions of the chosen parts, for fit checks
# --------------------------------------------------------------------------
BATT_Z = -P["tray_gap"] - P["tray"][2]  # top of the battery = underside of the tray

def cyl(r, h, p, d):
    return cq.Workplane().add(cq.Solid.makeCylinder(r, h, V(*p), V(*d).normalized()))


def ref_rpi():
    x0, x1 = P["rpi_x"]
    z = Z_DECK + P["rpi_standoff"]
    board = box_at(x1 - x0, 56, 1.6, x0, -28, z)
    cooler = box_at(40, 40, 9, -2, -20, z + 1.6)
    ports = box_at(21, 53, 16, x0 - 2, -26.5, z + 1.6)  # USB + Ethernet (rear)
    return board.union(cooler).union(ports)


# name -> (shape factory, colour key, mass g, description)
BL, BW, BH = P["battery"]
REF = {
    "REF_battery": (lambda: box_at(BW, BL, BH, P["battery_cx"] - BW / 2, -BL / 2, BATT_Z - BH), "batt", 418,
                    "GNB 6S 3000 mAh 100C LiPo, 138x44x32 mm, XT60 (crosswise under the tray)"),
    "REF_esc": (lambda: box_at(43, 43, 7, -21.5, -21.5, Z_STAND + 3), "pcb", 18,
                "NewBeeDrone Hummingbird 305 80A 3-8S AM32 4in1 ESC, 43x43 mm, 30.5x30.5 (14.5 g bare + cap/leads)"),
    "REF_fc": (lambda: box_at(36, 36, 5, -18, -18, Z_STAND + 14), "pcb2", 7,
               "Matek H743-SLIM V4 flight controller (ArduPilot/INAV), 36x36x5 mm, 30.5x30.5"),
    "REF_vtx": (lambda: box_at(28, 28, 6, VTX_C[0] - 14, -14, Z_ARM + 3), "pcb", 5.4,
                "RushFPV Tank Ultimate Mini 800 mW analog VTX, 28x28 mm, 20x20 M2"),
    "REF_elrs_rx": (lambda: box_at(13, 22, 4, -36, -11, Z_STAND), "pcb2", 4.6,
                    "RadioMaster RP3 V2 ELRS 2.4 GHz diversity receiver, 22x13x4 mm, incl. 2 antennas"),
    "REF_fpv_cam": (lambda: box_at(20, 19, 19, 57, -9.5, (Z_ARM + Z_TOP) / 2 - 9.5)
                    .union(cyl(6, 6, (77, 0, (Z_ARM + Z_TOP) / 2), (1, 0, 0))), "cam", 6,
                    "Caddx Ratel 2 (19 mm micro) analog FPV camera"),
    "REF_down_cam": (lambda: box_at(25, 24, 1, DOWNCAM_C[0] - 12.5, -12, -4)
                     .union(box_at(9, 9, 6, DOWNCAM_C[0] - 4.5, -4.5, -10)), "pcb2", 4,
                     "Raspberry Pi Camera Module 3, 25x24 mm, facing down (precision landing)"),
    "REF_rpi": (ref_rpi, "rpi", 66, "Raspberry Pi 5 + official active cooler"),
    "REF_bec": (lambda: box_at(25, 18, 8, 0, -9, Z_DECK), "pcb2", 6, "5 V 5 A BEC for the Pi (under the Pi)"),
    "REF_gps": (lambda: box_at(20, 20, 12.4, -71, -10, Z_DECK + P["gps_mast"] + P["gps_plate_t"]), "gps", 8,
                "Matek M10Q-5883 GPS (u-blox M10) + QMC5883L compass, 20x20x12.4 mm"),
    "REF_telemetry": (lambda: box_at(29, 21, 8, -76, -10.5, Z_TOP - 8), "radio", 5.3,
                      "Matek mR900-30 mLRS LoRa MAVLink telemetry, 900 MHz 1 W, ~29x21 mm + heatsink"),
    "REF_ant_telemetry": (lambda: cyl(2, 80, (-86, 0, Z_TOP - 2), (0, 0, 1)), "ant", 0,
                          "900 MHz dipole, 8 cm (weight included with the radio)"),
    "REF_ant_vtx": (lambda: cyl(5, 35, (-89.5, 0, 12), (-0.5, 0, -0.866)), "ant", 8, "5.8 GHz VTX antenna (down-back)"),
    "REF_ant_elrs_L": (lambda: cyl(1.5, 45, (-86.5, 7.5, 8), (-0.45, 0.55, -0.7)), "ant", 0,
                       "ELRS T-antenna (weight included with RP3)"),
    "REF_ant_elrs_R": (lambda: cyl(1.5, 45, (-86.5, -7.5, 8), (-0.45, -0.55, -0.7)), "ant", 0,
                       "ELRS T-antenna (weight included with RP3)"),
    # dock charging: 4 foot contacts -> ideal-diode bridge (any polarity / any 90 deg landing yaw) -> 6S BMS -> pack
    "REF_charge_bridge": (lambda: box_at(30, 30, 8, -67, -15, -11), "pcb2", 8,
                          "Ideal-diode bridge (LT4320 + 4 MOSFETs, 5 A) + 5 A fuse, in the printed case"),
    "REF_bms": (lambda: box_at(40, 60, 4, -20, -30, BATT_Z - BH - 4), "pcb", 15,
                "6S 20 A BMS with cell balancing, on the battery's balance lead (taped under the pack)"),
}
MOTOR_G, PROP_G, WIRING_G, CONTACT_G = 60.7, 11, 65, 3.0   # wiring incl. the charging leads up the legs


def ref_motor():
    return cq.Workplane("XY").circle(P["motor_d"] / 2).extrude(P["motor_h"])


def ref_prop_disc():
    return cq.Workplane("XY").circle(P["prop_d"] / 2).extrude(3)


def ref_contact():
    """M4 stainless acorn (dome) nut under each foot: the charging contact that touches the dock pads."""
    return cq.Workplane("XY").circle(3.5).extrude(P["contact_h"]).faces("<Z").edges().fillet(2.4)


# --------------------------------------------------------------------------
# Assemblies
# --------------------------------------------------------------------------
import dock as DK  # noqa: E402  flat-top dock (cad/dock.py)

DENSITY.update({"acm": 1.5e-3, "pc": 0.22e-3, "al2020": 1.25e-3})   # twin-wall PC and 2020 profile: effective

C = {
    "carbon": (0.12, 0.12, 0.13), "al": (0.85, 0.25, 0.15), "tpu": (0.95, 0.75, 0.1), "pa_cf": (0.24, 0.25, 0.28),
    "nylon": (0.9, 0.9, 0.85), "motor": (0.55, 0.55, 0.6), "prop": (0.2, 0.5, 0.95), "batt": (0.9, 0.85, 0.2),
    "pcb": (0.1, 0.45, 0.2), "pcb2": (0.15, 0.3, 0.6), "cam": (0.35, 0.35, 0.4), "rpi": (0.1, 0.6, 0.3),
    "gps": (0.85, 0.85, 0.85), "radio": (0.25, 0.25, 0.3), "ant": (0.05, 0.05, 0.05), "steel": (0.75, 0.75, 0.78),
}

# manufactured drone part -> (factory, material, qty). Printed parts are PA-CF except the TPU antenna mount.
PARTS = {
    "bottom_plate": (make_bottom_plate, "pa_cf", 1),
    "arm": (make_arm, "pa_cf", 4),
    "mid_plate": (make_mid_plate, "pa_cf", 1),
    "top_plate": (make_top_plate, "pa_cf", 1),
    "camera_plate": (make_cam_plate, "pa_cf", 2),
    "battery_tray": (make_tray, "pa_cf", 1),
    "gps_plate": (make_gps_plate, "pa_cf", 1),
    "landing_leg": (make_leg, "pa_cf", 4),
    "foot": (make_foot, "pa_cf", 4),
    "charge_case": (make_charge_case, "pa_cf", 1),
    "antenna_mount": (make_antenna_mount, "tpu", 1),
    "standoff_30mm": (lambda: make_hex_standoff(P["standoff_len"], 5.0, 2.5), "al7075", 4),
    "standoff_rear": (lambda: make_hex_standoff(REAR_STANDOFF_LEN, 5.0, 2.5), "al7075", 2),
    "standoff_tray_6mm": (lambda: make_hex_standoff(P["tray_gap"], 5.0, 2.5), "al7075", 4),
    "standoff_rpi_m2_5x10": (lambda: make_hex_standoff(P["rpi_standoff"], 5.0, 2.1), "nylon", 4),
    "standoff_gps_m2x40": (lambda: make_hex_standoff(P["gps_mast"], 4.0, 1.6), "nylon", 4),
}
FLAT_PARTS = {"bottom_plate": P["bottom_t"], "arm": P["arm_t"] - 1.0, "mid_plate": P["mid_t"], "top_plate": P["top_t"],
              "camera_plate": P["cam_plate_t"], "battery_tray": P["tray"][2], "gps_plate": P["gps_plate_t"]}
MAT_COLOR = {"carbon": "carbon", "al7075": "al", "tpu": "tpu", "pa_cf": "pa_cf", "nylon": "nylon"}
# rotation (axis, degrees) that puts each printed part in its print orientation (flat, no or minimal support)
PRINT_ORIENT = {"arm": ((1, 0, 0), 180), "landing_leg": ((1, 0, 0), 180), "dock_bar_bracket_low_inner": ((1, 0, 0), 180),
                "dock_bar_bracket_low_outer": ((1, 0, 0), 180), "dock_bar_bracket_high_inner": ((1, 0, 0), 180),
                "dock_bar_bracket_high_outer": ((1, 0, 0), 180), "dock_stepper_bracket": ((1, 0, 0), 180),
                "dock_hinge_arm": ((1, 0, 0), 90), "dock_bearing_block": ((1, 0, 0), 90),
                "dock_coupler": ((1, 0, 0), 90), "dock_cover_corner": ((1, 0, 0), 180)}


def drone_items(S, with_refs=True):
    """List of (name, shape, Location, colour, is_reference)."""
    Zax = V(0, 0, 1)
    c = lambda part: C[MAT_COLOR[PARTS[part][1]]]  # noqa: E731
    it = [("bottom_plate", S["bottom_plate"], L(V(0, 0, 0)), c("bottom_plate"), False)]
    for i, a in enumerate(ARM_ANGLES):
        it.append((f"arm_{i+1}", S["arm"], L(V(0, 0, Z_ARM), Zax, a), c("arm"), False))
        lx, ly = polar(P["leg_at"], a)
        it.append((f"landing_leg_{i+1}", S["landing_leg"], L(V(lx, ly, Z_ARM), Zax, a), c("landing_leg"), False))
        it.append((f"foot_{i+1}", S["foot"], L(V(lx, ly, LEG_BOTTOM + P["contact_h"])), c("foot"), False))
    it.append(("mid_plate", S["mid_plate"], L(V(0, 0, Z_MID)), c("mid_plate"), False))
    it.append(("top_plate", S["top_plate"], L(V(0, 0, Z_TOP)), c("top_plate"), False))
    diag, rear = standoff_points()
    for i, (x, y) in enumerate(diag):
        it.append((f"standoff_{i+1}", S["standoff_30mm"], L(V(x, y, Z_STAND)), c("standoff_30mm"), False))
    for i, (x, y) in enumerate(rear):
        it.append((f"standoff_rear_{i+1}", S["standoff_rear"], L(V(x, y, Z_ARM)), c("standoff_rear"), False))
    t, yi = P["cam_plate_t"], P["cam_plate_y"]
    it.append(("camera_plate_L", S["camera_plate"], L(V(0, yi + t, 0), V(1, 0, 0), 90), c("camera_plate"), False))
    it.append(("camera_plate_R", S["camera_plate"], L(V(0, -yi, 0), V(1, 0, 0), 90), c("camera_plate"), False))
    it.append(("battery_tray", S["battery_tray"], L(V(0, 0, BATT_Z)), c("battery_tray"), False))
    for i, (x, y) in enumerate(P["tray_standoffs"]):
        it.append((f"standoff_tray_{i+1}", S["standoff_tray_6mm"], L(V(x, y, -P["tray_gap"])), c("standoff_tray_6mm"), False))
    for i, (x, y) in enumerate(RPI45_HOLES):
        it.append((f"standoff_rpi_{i+1}", S["standoff_rpi_m2_5x10"], L(V(x, y, Z_DECK)), c("standoff_rpi_m2_5x10"), False))
    for i, (x, y) in enumerate(P["gps_holes"]):
        it.append((f"standoff_gps_{i+1}", S["standoff_gps_m2x40"], L(V(x, y, Z_DECK)), c("standoff_gps_m2x40"), False))
    it.append(("gps_plate", S["gps_plate"], L(V(-61, 0, Z_DECK + P["gps_mast"])), c("gps_plate"), False))
    it.append(("antenna_mount", S["antenna_mount"], L(V(0, 0, 0)), c("antenna_mount"), False))
    it.append(("charge_case", S["charge_case"], L(V(0, 0, 0)), c("charge_case"), False))
    if with_refs:
        for i, a in enumerate(ARM_ANGLES):
            mx, my = polar(R, a)
            lx, ly = polar(P["leg_at"], a)
            it.append((f"REF_motor_{i+1}", S["REF_motor"], L(V(mx, my, Z_MID)), C["motor"], True))
            it.append((f"REF_prop_{i+1}", S["REF_prop"], L(V(mx, my, Z_MID + P["motor_h"] + 1.5)), C["prop"], True))
            it.append((f"REF_contact_{i+1}", S["REF_contact"], L(V(lx, ly, LEG_BOTTOM)), C["steel"], True))
        for name, (_, col, _, _) in REF.items():
            it.append((name, S[name], L(V(0, 0, 0)), C[col], True))
    return it


def leg_radius_above_deck(h):
    """Radius of the leg cone h mm above the deck (drone standing on the deck)."""
    z = LEG_BOTTOM + h
    z_bot, z_top = Z_ARM - P["leg_len"], Z_ARM - 4.0
    return 5.0 + 2.0 * min(max((z - z_bot) / (z_top - z_bot), 0.0), 1.0)


BAR_X_CENTRED = DK.bar_stop(leg_radius_above_deck, DK.D["x_bar_z"])
BAR_Y_CENTRED = DK.bar_stop(leg_radius_above_deck, DK.D["y_bar_z"])
DOCK_STATES = {   # name -> (cover angle, X pushers, Y pushers)
    "closed": (0.0, BAR_X_CENTRED, BAR_Y_CENTRED),
    "open": (180.0, DK.D["park"], DK.D["park"]),
    "centering": (180.0, BAR_X_CENTRED, BAR_Y_CENTRED),
}


def dock_items(S, state="closed", cover_deg=None):
    deg, bx, by = DOCK_STATES[state]
    return DK.items(S, deg if cover_deg is None else cover_deg, bx, by)


def drone_in_dock_location():
    return L(V(0, 0, DK.Z_DECK - LEG_BOTTOM))  # contact domes stand on the deck pads


def build_shapes():
    S = {name: fac().val() for name, (fac, _, _) in PARTS.items()}
    S["REF_motor"] = ref_motor().val()
    S["REF_prop"] = ref_prop_disc().val()
    S["REF_contact"] = ref_contact().val()
    for name, (fac, _, _, _) in REF.items():
        S[name] = fac().val()
    S.update(DK.build_shapes())
    return S


def to_assembly(name, items, extra_loc=None):
    a = cq.Assembly(name=name)
    for n, shp, loc, col, _ in items:
        a.add(shp, name=n, loc=extra_loc * loc if extra_loc is not None else loc, color=cq.Color(*col))
    return a


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def placed(items, extra_loc=None):
    return [(n, shp.moved(extra_loc * loc if extra_loc is not None else loc), ref) for n, shp, loc, _, ref in items]


def bb_overlap(a, b, tol=0.01):
    return not (a.xmax < b.xmin - tol or b.xmax < a.xmin - tol or a.ymax < b.ymin - tol
                or b.ymax < a.ymin - tol or a.zmax < b.zmin - tol or b.zmax < a.zmin - tol)


def interference(pl, skip_pair=lambda a, b: False, only=None):
    """Pairwise solid overlap. only: optional predicate - at least one of the pair must match it."""
    clashes = []
    bbs = [s.BoundingBox() for _, s, _ in pl]
    for i in range(len(pl)):
        for j in range(i + 1, len(pl)):
            (na, a, _), (nb, b, _) = pl[i], pl[j]
            if only is not None and not (only(na) or only(nb)):
                continue
            if skip_pair(na, nb) or not bb_overlap(bbs[i], bbs[j]):
                continue
            v = a.intersect(b).Volume()
            if v > 1e-3:
                clashes.append({"a": na, "b": nb, "volume_mm3": round(v, 3)})
    return clashes


def min_dist(pl, pred_a, pred_b):
    best = (1e9, None, None)
    for na, a, _ in pl:
        if not pred_a(na):
            continue
        for nb, b, _ in pl:
            if nb == na or not pred_b(nb):
                continue
            d = a.distance(b)
            if d < best[0]:
                best = (d, na, nb)
    return {"distance_mm": round(best[0], 2), "between": [best[1], best[2]]}


DRONE_PREFIXES = ("REF", "arm", "bottom", "mid", "top", "cam", "stand", "foot", "landing_leg", "battery", "gps",
                  "antenna", "charge")


def is_drone(n):
    return n.startswith(DRONE_PREFIXES)


def is_cover(n):
    return n.startswith("dockCOVER")


def dock_skip(a, b):
    """Pairs that touch by design: drone-drone (checked separately), a cover with its own arms/corners."""
    if is_drone(a) and is_drone(b):
        return True
    return is_cover(a) and is_cover(b) and a.split("_")[-1][0] == b.split("_")[-1][0]


def print_oriented(shape, name):
    ax, deg = PRINT_ORIENT.get(name, ((1, 0, 0), 0))
    s = shape.rotate(V(0, 0, 0), V(*ax), deg) if deg else shape
    bb = s.BoundingBox()
    return s.translate(V(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def export_all():
    for sub in ("parts", "dxf", "svg", "assembly", "report", "print"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    for old in [f for d in ("parts", "dxf", "svg", "assembly", "print") for f in (OUT / d).glob("*")]:
        old.unlink()

    S = build_shapes()
    from OCP.IGESControl import IGESControl_Writer

    def export_part(name, shape, fine=True):
        wp = cq.Workplane("XY").add(shape)
        cq.exporters.export(wp, str(OUT / "parts" / f"{name}.step"))
        cq.exporters.export(wp, str(OUT / "parts" / f"{name}.stl"), tolerance=0.02 if fine else 0.1,
                            angularTolerance=0.1 if fine else 0.2)
        w = IGESControl_Writer("MM", 1)
        w.AddShape(shape.wrapped)
        w.ComputeModel()
        w.Write(str(OUT / "parts" / f"{name}.igs"))

    bed = P["bed"]
    print_list, masses, dock_masses = [], {}, {}

    def add_print(name, shape, mat, qty, note=""):
        s = print_oriented(shape, name)
        cq.exporters.export(cq.Workplane().add(s), str(OUT / "print" / f"{name}.stl"), tolerance=0.02,
                            angularTolerance=0.1)
        bb = s.BoundingBox()
        dims = sorted([bb.xlen, bb.ylen])
        fits = dims[1] <= min(bed[:2]) and dims[0] <= max(bed[:2]) and bb.zlen <= bed[2]
        print_list.append({"part": name, "qty": qty, "material": mat, "size_mm": [round(bb.xlen, 1), round(bb.ylen, 1),
                           round(bb.zlen, 1)], "fits_bed": fits,
                           "mass_each_g": round(shape.Volume() * DENSITY[mat] * PRINT_FILL[mat], 1), "note": note})

    for name, (_, mat, qty) in PARTS.items():
        export_part(name, S[name])
        vol = S[name].Volume()
        each = vol * DENSITY[mat] * PRINT_FILL.get(mat, 1.0)
        masses[name] = {"material": mat, "qty": qty, "volume_mm3": round(vol, 1), "printed": mat in PRINTED,
                        "mass_each_g": round(each, 2), "mass_total_g": round(each * qty, 2)}
        if mat in PRINTED:
            add_print(name, S[name], mat, qty)
        if name in FLAT_PARTS:
            sec = cq.Workplane("XY").add(S[name]).section(FLAT_PARTS[name] / 2)
            cq.exporters.export(sec, str(OUT / "dxf" / f"{name}.dxf"), exportType="DXF")
            cq.exporters.export(cq.Workplane("XY").add(S[name]), str(OUT / "svg" / f"{name}.svg"),
                                opt={"projectionDir": (0, 0, 1), "showHidden": False, "width": 800, "height": 500})
    for name, (_, mat, qty, note) in DK.PRINT_PARTS.items():
        export_part(name, S[name])
        add_print(name, S[name], mat, qty, note)
        dock_masses[name] = {"material": mat, "qty": qty, "kind": "print",
                             "mass_each_g": round(S[name].Volume() * DENSITY[mat] * PRINT_FILL[mat], 1), "note": note}
    for name, (_, mat, qty, note) in DK.CUT_PARTS.items():
        mat = "al2020" if name == "dock_frame" else mat
        export_part(name, S[name], fine=False)
        dock_masses[name] = {"material": mat, "qty": qty, "kind": "cut",
                             "mass_each_g": round(S[name].Volume() * DENSITY[mat], 0), "note": note}

    drone = drone_items(S)
    frame_only = drone_items(S, with_refs=False)
    dloc = drone_in_dock_location()
    asm = {"drone_frame_only": to_assembly("drone_frame_only", frame_only),
           "drone_full": to_assembly("drone_full", drone)}
    for st in DOCK_STATES:
        asm[f"dock_{st}_with_drone"] = to_assembly(f"dock_{st}", dock_items(S, st)).add(to_assembly("drone", drone), loc=dloc)
    for n, a in asm.items():
        a.export(str(OUT / "assembly" / f"{n}.step"))
        a.export(str(OUT / "assembly" / f"{n}.glb"))
    comp = cq.Compound.makeCompound([shp.moved(loc) for _, shp, loc, _, _ in frame_only])
    cq.exporters.export(cq.Workplane().add(comp), str(OUT / "assembly" / "drone_frame_only.stl"),
                        tolerance=0.05, angularTolerance=0.15)

    # ---- drone checks
    pd = placed(drone)
    checks = {"drone_interference": interference(pd)}
    not_prop_motor = lambda n: not n.startswith(("REF_prop", "REF_motor", "arm"))  # noqa: E731
    checks["prop_to_anything_min_clearance"] = min_dist(pd, lambda n: n.startswith("REF_prop"), not_prop_motor)
    checks["prop_to_prop_min_gap"] = min_dist(pd, lambda n: n == "REF_prop_1",
                                              lambda n: n in ("REF_prop_2", "REF_prop_4"))
    low = min(s.BoundingBox().zmin for n, s, _ in pd if n in ("REF_battery", "REF_bms"))
    checks["battery_ground_clearance_mm"] = round(low - LEG_BOTTOM, 2)
    checks["gps_to_rpi_mm"] = min_dist(pd, lambda n: n == "REF_gps", lambda n: n == "REF_rpi")
    checks["compass_to_esc_mm"] = min_dist(pd, lambda n: n == "REF_gps", lambda n: n == "REF_esc")
    checks["compass_to_battery_mm"] = min_dist(pd, lambda n: n == "REF_gps", lambda n: n == "REF_battery")
    checks["gps_to_telemetry_antenna_mm"] = min_dist(pd, lambda n: n == "REF_gps", lambda n: n == "REF_ant_telemetry")

    # ---- dock checks: every state, the cover sweep, take-off column, pushers on the legs
    st = {k: placed(dock_items(S, k)) + placed(drone, dloc) for k in DOCK_STATES}
    for k, pl in st.items():
        checks[f"dock_{k}_interference"] = interference(pl, dock_skip)
    sweep = []
    statics = [x for x in placed(dock_items(S, "closed")) if not is_cover(x[0])] + placed(drone, dloc)
    for deg in range(0, 181, 15):
        moving = [x for x in placed(dock_items(S, "closed", cover_deg=float(deg))) if is_cover(x[0])]
        for c in interference(moving + statics, dock_skip, only=is_cover):
            sweep.append({"cover_deg": deg, **c})
    checks["cover_sweep_0_to_180deg_interference"] = sweep
    checks["drone_top_to_closed_cover"] = min_dist(st["closed"], is_drone, is_cover)
    checks["props_to_dock_when_open"] = min_dist(st["open"], lambda n: n.startswith("REF_prop"),
                                                 lambda n: n.startswith("dock"))
    half = R / math.sqrt(2) + P["prop_d"] / 2 + 10
    prop_z = DK.Z_DECK - LEG_BOTTOM + Z_MID + P["motor_h"] + 1.5
    corridor = cq.Workplane("XY").rect(2 * half, 2 * half).extrude(1500).val().moved(L(V(0, 0, prop_z)))
    checks["takeoff_column_half_width_mm"] = round(half, 1)
    checks["takeoff_column_vs_dock_open_mm3"] = round(sum(corridor.intersect(s).Volume() for n, s, _ in st["open"]
                                                          if n.startswith("dock") and bb_overlap(s.BoundingBox(), corridor.BoundingBox())), 3)
    checks["pusher_to_leg_when_centred"] = min_dist(st["centering"], lambda n: n.startswith("dock_bar_"),
                                                    lambda n: n.startswith(("landing_leg", "foot")))
    checks["pushers_to_drone_body_when_centred"] = min_dist(
        st["centering"], lambda n: n.startswith("dock_bar_"),
        lambda n: is_drone(n) and not n.startswith(("landing_leg", "foot", "REF_contact")))
    rx = DK.D["park"] - DK.D["bar"] / 2 - leg_radius_above_deck(DK.D["x_bar_z"] + DK.D["bar"])
    checks["landing_capture_mm"] = {
        "aligned_yaw": round(rx - P["leg_at"] / math.sqrt(2), 1),
        "worst_yaw_45deg": round(rx - P["leg_at"], 1),
        "pusher_park_mm": DK.D["park"], "x_pusher_centred_mm": round(BAR_X_CENTRED, 2),
        "y_pusher_centred_mm": round(BAR_Y_CENTRED, 2)}
    checks["print_bed_fit"] = {"bed_mm": list(bed), "all_fit": all(p["fits_bed"] for p in print_list),
                               "too_big": [p["part"] for p in print_list if not p["fits_bed"]]}

    bb = cq.Compound.makeCompound([s for _, s, _ in pd]).BoundingBox()
    checks["drone_envelope_mm"] = {"x": round(bb.xlen, 1), "y": round(bb.ylen, 1), "z": round(bb.zlen, 1)}
    for k in ("closed", "open"):
        db = cq.Compound.makeCompound([s for n, s, _ in st[k] if n.startswith("dock")]).BoundingBox()
        checks[f"dock_{k}_size_mm"] = {"x": round(db.xlen), "y": round(db.ylen), "z": round(db.zlen)}
    checks["frame_mass_g"] = round(sum(m["mass_total_g"] for m in masses.values()), 1)
    checks["printed_frame_mass_g"] = round(sum(m["mass_total_g"] for m in masses.values() if m["printed"]), 1)

    components = {n.replace("REF_", ""): {"mass_g": m, "description": d} for n, (_, _, m, d) in REF.items()}
    components["motors_4x"] = {"mass_g": 4 * MOTOR_G, "description": "iFlight XING2 2809 1250KV, 19x19 M3, 60.7 g each"}
    components["props_4x"] = {"mass_g": 4 * PROP_G, "description": "7 inch tri-blade (e.g. HQProp 7x4x3 / Gemfan 7040-3)"}
    components["contacts_4x"] = {"mass_g": 4 * CONTACT_G, "description": "M4 stainless acorn nuts + M4 screws (foot contacts)"}
    components["wiring_hardware"] = {"mass_g": WIRING_G, "description": "screws, XT60, wires, charging leads, straps, ribbon"}

    # ---- centre of gravity: every part's mass at its real position
    part_mass = {id(S[k]): m["mass_each_g"] for k, m in masses.items()}
    tot, mx, my, mz = 0.0, 0.0, 0.0, 0.0
    for n, shp, _ in pd:
        if n.startswith("REF_motor"):
            m = MOTOR_G
        elif n.startswith("REF_prop"):
            m = PROP_G
        elif n.startswith("REF_contact"):
            m = CONTACT_G
        elif n in REF:
            m = REF[n][2]
        else:
            m = part_mass[id(next(s for nn, s, _, _, _ in drone if nn == n))]
        c = shp.Center()
        tot, mx, my, mz = tot + m, mx + m * c.x, my + m * c.y, mz + m * c.z
    tot, mz = tot + WIRING_G, mz + WIRING_G * Z_STAND  # wiring lumped at the stack
    cg = (mx / tot, my / tot, mz / tot)
    prop_plane = Z_MID + P["motor_h"] + 3
    checks["cg_mm"] = {"x": round(cg[0], 1), "y": round(cg[1], 1), "z": round(cg[2], 1),
                       "offset_from_centre_mm": round(math.hypot(cg[0], cg[1]), 1),
                       "below_prop_plane_mm": round(prop_plane - cg[2], 1)}
    checks["auw_from_cg_sum_g"] = round(tot, 0)

    # ---- downward camera field of view (Camera Module 3: 66 x 41 deg) must be clear down to the ground
    lens_z = -10.0
    depth = lens_z - LEG_BOTTOM
    hx = 4.5 + depth * math.tan(math.radians(41 / 2))
    hy = 4.5 + depth * math.tan(math.radians(66 / 2))
    cone = (cq.Workplane("XY").workplane(offset=lens_z - 0.5).center(*DOWNCAM_C).rect(9, 9)
            .workplane(offset=-(depth - 0.5)).rect(2 * hx, 2 * hy).loft().val())
    blocked = [n for n, s, _ in pd if n != "REF_down_cam" and bb_overlap(s.BoundingBox(), cone.BoundingBox())
               and s.intersect(cone).Volume() > 1e-3]
    checks["down_camera_view_blocked_by"] = blocked

    clamp_edge = (P["mid_size"] / 2 - P["mid_r"]) * math.sqrt(2) + P["mid_r"]
    geom = {"R_motor_mm": R, "clamp_edge_mm": round(clamp_edge, 2), "arm_free_len_mm": round(R - clamp_edge, 2),
            "arm_w_at_clamp_mm": round(arm_width(clamp_edge), 2), "arm_t_mm": P["arm_t"],
            "arm_floor_mm": P["arm_floor"], "arm_pocket_d_mm": P["arm_pocket_d"], "material": P["material"],
            "leg_bolts_mm": list(leg_bolts()), "leg_len_mm": P["leg_len"]}
    report = {"params": P, "dock_params": DK.D, "geometry": geom, "masses": masses, "dock_parts": dock_masses,
              "print_list": print_list, "components": components, "checks": checks}
    (OUT / "report" / "checks.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    r = export_all()
    print(json.dumps(r["checks"], indent=2))
